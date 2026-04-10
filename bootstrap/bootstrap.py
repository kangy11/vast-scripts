#!/usr/bin/env python3
from __future__ import annotations

import argparse
import os
import re
import shutil
import signal
import socket
import subprocess
import sys
from pathlib import Path
from typing import Any

import yaml
from huggingface_hub import get_token, login, snapshot_download


ROOT_USER = os.environ.get("BOOTSTRAP_USER", "root")
OFFICIAL_COMFY_SUPERVISOR = Path("/opt/supervisor-scripts/comfyui.sh")
OFFICIAL_COMFY_LOG = Path("/var/log/portal/comfyui.log")
HF_TOKEN_ENV_NAMES = (
    "HF_TOKEN",
    "HUGGING_FACE_HUB_TOKEN",
    "HUGGINGFACEHUB_API_TOKEN",
)
PORTAL_ENV_NAMES = (
    "WORKSPACE",
    "PORTAL_CONFIG",
    "WEB_USERNAME",
    "WEB_PASSWORD",
    "OPEN_BUTTON_TOKEN",
    "ENABLE_AUTH",
    "ENABLE_HTTPS",
    "AUTH_EXCLUDE",
    "PUBLIC_IPADDR",
    "VAST_CONTAINERLABEL",
    "VAST_TCP_PORT_1111",
    "VAST_TCP_PORT_8188",
    "VAST_TCP_PORT_8288",
    "VAST_TCP_PORT_8384",
    "VAST_TCP_PORT_8080",
    "COMFYUI_ARGS",
    "COMFYUI_PORT",
)
TMUX_PATTERNS = (
    re.compile(r"tmux\s+attach"),
    re.compile(r"tmux\s+new"),
    re.compile(r"attach-session"),
    re.compile(r"new-session"),
    re.compile(r"has-session"),
)


def repo_root_from_arg(value: str | None) -> Path:
    if value:
        return Path(value).resolve()
    return Path(__file__).resolve().parents[1]


def getenv_path(name: str, default: str) -> Path:
    return Path(os.environ.get(name, default)).expanduser().resolve()


def log(message: str) -> None:
    print(f"[bootstrap] {message}", flush=True)


def run(
    cmd: list[str],
    *,
    cwd: Path | None = None,
    env: dict[str, str] | None = None,
    check: bool = True,
) -> subprocess.CompletedProcess[str]:
    log("$ " + " ".join(cmd))
    return subprocess.run(
        cmd,
        cwd=str(cwd) if cwd else None,
        env=env,
        check=check,
        text=True,
    )


def read_text_lines(path: Path) -> list[str]:
    if not path.exists():
        return []
    return [
        line.strip()
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    ]


def load_yaml(path: Path) -> Any:
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8") as handle:
        data = yaml.safe_load(handle) or []
    if not isinstance(data, list):
        raise ValueError(f"{path} must contain a YAML list")
    return data


def requirement_name(line: str) -> str | None:
    stripped = line.strip()
    if not stripped or stripped.startswith("#"):
        return None
    if stripped.startswith(("-", "--", "git+", "http://", "https://")):
        return None
    base = stripped.split(";", 1)[0].strip()
    if "@" in base:
        base = base.split("@", 1)[0].strip()
    match = re.match(r"([A-Za-z0-9_.-]+)", base)
    if not match:
        return None
    return match.group(1).lower().replace("_", "-")


def ensure_dirs(paths: list[Path]) -> None:
    for path in paths:
        path.mkdir(parents=True, exist_ok=True)


def write_if_changed(path: Path, content: str, mode: int | None = None) -> None:
    if path.exists() and path.read_text(encoding="utf-8") == content:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    if mode is not None:
        path.chmod(mode)


def install_requirements(
    python_bin: str,
    req_path: Path,
    excluded_packages: list[str] | None = None,
) -> None:
    excluded = {item.strip().lower().replace("_", "-") for item in (excluded_packages or []) if item.strip()}
    install_path = req_path
    temp_path: Path | None = None
    if excluded:
        kept_lines: list[str] = []
        for line in req_path.read_text(encoding="utf-8").splitlines():
            package = requirement_name(line)
            if package and package in excluded:
                log(f"Filtering requirement '{package}' from {req_path.name}")
                continue
            kept_lines.append(line)
        temp_path = req_path.with_name(f".filtered-{req_path.name}")
        temp_path.write_text("\n".join(kept_lines).rstrip() + "\n", encoding="utf-8")
        install_path = temp_path
    try:
        run([python_bin, "-m", "pip", "install", "-r", str(install_path)])
    finally:
        if temp_path and temp_path.exists():
            temp_path.unlink()


def default_portal_config() -> str:
    return (
        "localhost:1111:11111:/:Instance Portal|"
        "localhost:8188:18188:/:ComfyUI|"
        "localhost:8288:18288:/docs:API Wrapper|"
        "localhost:8384:18384:/:Syncthing"
    )


def default_hf_home() -> Path:
    return Path.home() / ".cache" / "huggingface"


def resolve_hf_token() -> str:
    for name in HF_TOKEN_ENV_NAMES:
        value = os.environ.get(name, "").strip()
        if value:
            return value
    saved_token = get_token() or ""
    return saved_token.strip()


def shell_quote(value: str) -> str:
    return "'" + value.replace("'", "'\"'\"'") + "'"


def prepare_hf_auth() -> str:
    token = resolve_hf_token()
    if not token:
        log("No Hugging Face token detected from env vars or default login state")
        return ""
    for name in HF_TOKEN_ENV_NAMES:
        os.environ[name] = token
    try:
        login(token=token, add_to_git_credential=False, skip_if_logged_in=False)
        log("Hugging Face authentication prepared")
    except Exception as exc:
        log(f"Hugging Face login step failed, continuing with direct token auth: {exc}")
    return token


def prepare_portal_env(env_info: dict[str, Any]) -> None:
    os.environ.setdefault("WORKSPACE", str(env_info["workspace_root"]))
    if env_info["official_image"]:
        os.environ.setdefault("PORTAL_CONFIG", default_portal_config())


def persist_official_env(env_info: dict[str, Any]) -> None:
    env_lines: list[str] = []
    for name in PORTAL_ENV_NAMES + HF_TOKEN_ENV_NAMES:
        value = os.environ.get(name, "").strip()
        if value:
            env_lines.append(f"export {name}={shell_quote(value)}")
    if not env_lines:
        return
    env_file = env_info["workspace_root"] / ".env"
    write_if_changed(env_file, "\n".join(env_lines) + "\n", 0o600)

    etc_environment = Path("/etc/environment")
    try:
        existing = etc_environment.read_text(encoding="utf-8") if etc_environment.exists() else ""
        filtered = []
        managed_names = set(PORTAL_ENV_NAMES + HF_TOKEN_ENV_NAMES)
        for line in existing.splitlines():
            key = line.split("=", 1)[0].strip()
            if key in managed_names:
                continue
            filtered.append(line)
        filtered.extend([line.replace("export ", "", 1) for line in env_lines])
        write_if_changed(etc_environment, "\n".join(filtered).rstrip() + "\n", 0o644)
    except PermissionError:
        log("Skipping /etc/environment update because permissions are insufficient")


def supervisord_running() -> bool:
    socket_path = Path("/var/run/supervisor.sock")
    pid_path = Path("/var/run/supervisord.pid")
    if socket_path.exists():
        return True
    if pid_path.exists():
        try:
            pid = int(pid_path.read_text(encoding="utf-8").strip())
            os.kill(pid, 0)
            return True
        except (ValueError, OSError):
            return False
    return False


def ensure_supervisord(env_info: dict[str, Any]) -> None:
    if not env_info["official_image"]:
        return
    if supervisord_running():
        return
    if shutil.which("supervisord") is None:
        log("supervisord is unavailable; skipping official portal startup")
        return
    log("Starting supervisord for official Vast portal stack")
    run(["supervisord", "-c", "/etc/supervisor/supervisord.conf"], check=False)


def bootstrap_env(repo_root: Path) -> dict[str, Any]:
    workspace_root = getenv_path("WORKSPACE_ROOT", "/workspace")
    bootstrap_root = getenv_path("BOOTSTRAP_ROOT", str(repo_root))
    comfyui_root = getenv_path("COMFYUI_ROOT", str(workspace_root / "ComfyUI"))
    hf_home = getenv_path("HF_HOME", str(default_hf_home()))
    hf_hub_cache = getenv_path("HF_HUB_CACHE", str(hf_home / "hub"))
    log_dir = getenv_path("LOG_DIR", str(workspace_root / "logs"))
    comfy_log_default = OFFICIAL_COMFY_LOG if OFFICIAL_COMFY_LOG.exists() else log_dir / "comfyui.log"
    comfy_log = Path(os.environ.get("COMFYUI_LOG_FILE", str(comfy_log_default)))
    pid_file = Path(os.environ.get("COMFYUI_PID_FILE", str(log_dir / "comfyui.pid")))
    state_dir = workspace_root / ".bootstrap-state"
    runtime_python = resolve_runtime_python()
    return {
        "repo_root": repo_root,
        "workspace_root": workspace_root,
        "bootstrap_root": bootstrap_root,
        "comfyui_root": comfyui_root,
        "hf_home": hf_home,
        "hf_hub_cache": hf_hub_cache,
        "log_dir": log_dir,
        "comfy_log": comfy_log,
        "pid_file": pid_file,
        "state_dir": state_dir,
        "config_dir": repo_root / "config",
        "bin_dir": repo_root / "bin",
        "runtime_python": runtime_python,
        "official_image": OFFICIAL_COMFY_SUPERVISOR.exists(),
    }


def resolve_runtime_python() -> str:
    candidates = [
        os.environ.get("COMFYUI_PYTHON", "").strip(),
        "/venv/main/bin/python",
        sys.executable,
    ]
    for candidate in candidates:
        if candidate and Path(candidate).exists():
            return candidate
    return sys.executable


def profile_exports(env_info: dict[str, Any]) -> str:
    bootstrap_bin = env_info["bin_dir"]
    lines = [
        "export WORKSPACE_ROOT=\"%s\"" % env_info["workspace_root"],
        "export BOOTSTRAP_ROOT=\"%s\"" % env_info["bootstrap_root"],
        "export COMFYUI_ROOT=\"%s\"" % env_info["comfyui_root"],
    ]
    if "HF_HOME" in os.environ:
        lines.append("export HF_HOME=\"%s\"" % env_info["hf_home"])
    if "HF_HUB_CACHE" in os.environ:
        lines.append("export HF_HUB_CACHE=\"%s\"" % env_info["hf_hub_cache"])
    lines.extend(
        [
            "export PATH=\"%s:$PATH\"" % bootstrap_bin,
            "",
        ]
    )
    return "\n".join(lines)


def persist_profile_env(env_info: dict[str, Any]) -> None:
    profile_script = Path("/etc/profile.d/comfyui-bootstrap.sh")
    content = "# Generated by Vast.ai ComfyUI bootstrap\n" + profile_exports(env_info)
    try:
        write_if_changed(profile_script, content, 0o644)
    except PermissionError:
        log("Skipping /etc/profile.d update because permissions are insufficient")


def sanitize_rc_file(path: Path) -> None:
    if not path.exists():
        return
    original = path.read_text(encoding="utf-8").splitlines()
    filtered: list[str] = []
    changed = False
    for line in original:
        if any(pattern.search(line) for pattern in TMUX_PATTERNS):
            changed = True
            continue
        filtered.append(line)
    if changed:
        path.write_text("\n".join(filtered).rstrip() + "\n", encoding="utf-8")


def ensure_comfyui_repo(env_info: dict[str, Any]) -> None:
    if env_info.get("safe_rerun_mode"):
        log("Safe rerun mode: skipping ComfyUI repo/dependency mutations while official service is live")
        return
    target = env_info["comfyui_root"]
    repo_url = os.environ.get("COMFYUI_REPO", "https://github.com/comfyanonymous/ComfyUI.git")
    repo_ref = os.environ.get("COMFYUI_REF", "").strip()
    if (target / ".git").exists():
        run(["git", "fetch", "--all", "--tags"], cwd=target)
    elif target.exists() and any(target.iterdir()):
        log(f"ComfyUI root {target} exists and is not empty; leaving it untouched")
    else:
        ensure_dirs([target.parent])
        run(["git", "clone", repo_url, str(target)])
    if repo_ref and (target / ".git").exists():
        run(["git", "checkout", repo_ref], cwd=target)
    requirements = target / "requirements.txt"
    if requirements.exists():
        run([env_info["runtime_python"], "-m", "pip", "install", "-r", str(requirements)])


def install_system_packages(env_info: dict[str, Any]) -> None:
    if os.environ.get("INSTALL_SYSTEM_PACKAGES", "1") == "0":
        log("Skipping apt packages because INSTALL_SYSTEM_PACKAGES=0")
        return
    if shutil.which("apt-get") is None:
        log("Skipping apt packages because apt-get is unavailable")
        return
    packages = read_text_lines(env_info["config_dir"] / "system-packages.txt")
    if not packages:
        return
    run(["apt-get", "update"])
    run(["apt-get", "install", "-y", "--no-install-recommends", *packages])


def install_shell(env_info: dict[str, Any]) -> None:
    home = Path(os.environ.get("BOOTSTRAP_HOME") or os.environ.get("HOME", f"/{ROOT_USER}"))
    zsh_path = shutil.which("zsh")
    if not zsh_path:
        log("zsh was not found after package installation; skipping shell switch")
        return

    oh_my_zsh_dir = home / ".oh-my-zsh"
    plugin_root = oh_my_zsh_dir / "custom" / "plugins"
    plugin_sources = {
        "zsh-autosuggestions": "https://github.com/zsh-users/zsh-autosuggestions.git",
        "zsh-syntax-highlighting": "https://github.com/zsh-users/zsh-syntax-highlighting.git",
    }
    if not oh_my_zsh_dir.exists():
        run(["git", "clone", "https://github.com/ohmyzsh/ohmyzsh.git", str(oh_my_zsh_dir)])
    ensure_dirs([plugin_root])
    for name, source in plugin_sources.items():
        destination = plugin_root / name
        if not destination.exists():
            run(["git", "clone", source, str(destination)])

    for rc_path in (home / ".bashrc", home / ".profile", home / ".zshrc"):
        try:
            sanitize_rc_file(rc_path)
        except PermissionError:
            log(f"Skipping tmux cleanup for {rc_path} because it is not writable")

    zshrc_template = (env_info["config_dir"] / "zsh" / ".zshrc").read_text(encoding="utf-8")
    zshrc = (
        zshrc_template.replace("__COMFYUI_ROOT__", str(env_info["comfyui_root"]))
        .replace("__BOOTSTRAP_ROOT__", str(env_info["bootstrap_root"]))
        .replace("__WORKSPACE_ROOT__", str(env_info["workspace_root"]))
    )
    try:
        write_if_changed(home / ".zshrc", zshrc, 0o644)
    except PermissionError:
        log(f"Skipping .zshrc install because {home} is not writable")

    if shutil.which("chsh"):
        subprocess.run(["chsh", "-s", zsh_path, ROOT_USER], check=False, text=True)
    elif shutil.which("usermod"):
        subprocess.run(["usermod", "-s", zsh_path, ROOT_USER], check=False, text=True)


def install_custom_nodes(env_info: dict[str, Any]) -> None:
    if env_info.get("safe_rerun_mode"):
        log("Safe rerun mode: skipping custom node code/dependency mutations while official service is live")
        return
    nodes = load_yaml(env_info["config_dir"] / "custom-nodes.lock.yaml")
    custom_root = env_info["comfyui_root"] / "custom_nodes"
    ensure_dirs([custom_root])
    for node in nodes:
        name = node["name"]
        repo = node["repo"]
        commit = node.get("commit")
        path = custom_root / node.get("path", name)
        optional = bool(node.get("optional", False))
        requirement_excludes = node.get("requirements_exclude") or []
        try:
            if (path / ".git").exists():
                run(["git", "fetch", "--all", "--tags"], cwd=path)
            elif path.exists() and any(path.iterdir()):
                log(f"Custom node path {path} already exists and is not a git repo; skipping clone")
            else:
                run(["git", "clone", repo, str(path)])
            if commit and str(commit).lower() != "null" and (path / ".git").exists():
                run(["git", "checkout", commit], cwd=path)

            requirements = node.get("requirements")
            if requirements:
                req_path = path / requirements
                if req_path.exists():
                    install_requirements(
                        env_info["runtime_python"],
                        req_path,
                        excluded_packages=requirement_excludes,
                    )

            for install_cmd in node.get("install", []) or []:
                run(["bash", "-lc", install_cmd], cwd=path)
        except subprocess.CalledProcessError as exc:
            if optional:
                log(f"Skipping optional node {name} after failure: {exc}")
                continue
            raise


def sync_models(env_info: dict[str, Any]) -> None:
    hf_token = resolve_hf_token()
    models = load_yaml(env_info["config_dir"] / "models.lock.yaml")
    for model in models:
        if model.get("private") and not hf_token:
            raise RuntimeError(
                f"Model {model['name']} is marked private but no Hugging Face token was found "
                "from environment variables or the default Hugging Face login state"
            )
        target_dir = Path(model["target_dir"])
        if not target_dir.is_absolute():
            target_dir = env_info["comfyui_root"] / target_dir
        ensure_dirs([target_dir])
        log(f"Syncing model {model['name']} into {target_dir}")
        try:
            snapshot_download(
                repo_id=model["repo_id"],
                revision=model["revision"],
                local_dir=str(target_dir),
                allow_patterns=model.get("include") or None,
                ignore_patterns=model.get("exclude") or None,
                token=hf_token or None,
                resume_download=True,
            )
        except Exception as exc:
            raise RuntimeError(
                f"Failed to sync model {model['name']} from {model['repo_id']}: {exc}"
            ) from exc


def restore_comfy_config(env_info: dict[str, Any]) -> None:
    archive = env_info["config_dir"] / "comfyui-config.tar.zst"
    if not archive.exists():
        log(f"Skipping ComfyUI config restore because {archive.name} does not exist")
        return
    ensure_dirs([env_info["workspace_root"]])
    run(
        [
            "tar",
            "--zstd",
            "-xf",
            str(archive),
            "-C",
            str(env_info["workspace_root"]),
        ]
    )


def pid_running(pid_file: Path) -> bool:
    if not pid_file.exists():
        return False
    try:
        pid = int(pid_file.read_text(encoding="utf-8").strip())
    except ValueError:
        return False
    try:
        os.kill(pid, 0)
    except OSError:
        return False
    return True


def build_comfy_command(env_info: dict[str, Any]) -> list[str]:
    host = os.environ.get("COMFYUI_HOST", "0.0.0.0")
    default_port = "18188" if env_info["official_image"] else "8188"
    port = os.environ.get("COMFYUI_PORT", default_port)
    extra_args = os.environ.get("COMFYUI_ARGS", "").strip()
    command = [env_info["runtime_python"], "main.py", "--listen", host, "--port", port]
    if extra_args:
        command.extend(extra_args.split())
    return command


def comfy_target_port(env_info: dict[str, Any]) -> int:
    default_port = "18188" if env_info["official_image"] else "8188"
    return int(os.environ.get("COMFYUI_PORT", default_port))


def tcp_port_open(port: int, host: str = "127.0.0.1") -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.settimeout(0.5)
        return sock.connect_ex((host, port)) == 0


def start_comfy(env_info: dict[str, Any], *, tmux: bool, foreground: bool) -> None:
    comfyui_root = env_info["comfyui_root"]
    log_file = env_info["comfy_log"]
    pid_file = env_info["pid_file"]
    ensure_dirs([env_info["log_dir"]])

    if pid_running(pid_file):
        log(f"ComfyUI already running with pid from {pid_file}")
        return

    command = build_comfy_command(env_info)
    if tmux:
        if shutil.which("tmux") is None:
            raise RuntimeError("tmux is not installed")
        session = os.environ.get("COMFYUI_TMUX_SESSION", "comfyui")
        subprocess.run(["tmux", "has-session", "-t", session], check=False, text=True)
        run(
            [
                "tmux",
                "new-session",
                "-d",
                "-s",
                session,
                "cd %s && %s >> %s 2>&1"
                % (comfyui_root, " ".join(command), log_file),
            ]
        )
        return

    if foreground:
        os.chdir(comfyui_root)
        os.execvpe(command[0], command, os.environ.copy())

    with log_file.open("a", encoding="utf-8") as handle:
        process = subprocess.Popen(
            command,
            cwd=str(comfyui_root),
            stdout=handle,
            stderr=subprocess.STDOUT,
            text=True,
            start_new_session=True,
        )
    pid_file.write_text(str(process.pid), encoding="utf-8")
    log(f"ComfyUI started in background with pid {process.pid}")


def show_logs(env_info: dict[str, Any], follow: bool) -> None:
    log_file = env_info["comfy_log"]
    if not log_file.exists():
        raise RuntimeError(f"Log file not found: {log_file}")
    command = ["tail", "-n", "200", str(log_file)]
    if follow:
        command.insert(1, "-f")
    os.execvp(command[0], command)


def attach_tmux() -> None:
    session = os.environ.get("COMFYUI_TMUX_SESSION", "comfyui")
    if shutil.which("tmux") is None:
        raise RuntimeError("tmux is not installed")
    os.execvp("tmux", ["tmux", "attach", "-t", session])


def bootstrap_all(repo_root: Path) -> None:
    env_info = bootstrap_env(repo_root)
    state_file = env_info["state_dir"] / "bootstrap.complete"
    target_port = comfy_target_port(env_info)
    ensure_dirs(
        [
            env_info["workspace_root"],
            env_info["bootstrap_root"],
            env_info["hf_home"],
            env_info["hf_hub_cache"],
            env_info["log_dir"],
            env_info["state_dir"],
        ]
    )
    safe_rerun_mode = (
        env_info["official_image"]
        and state_file.exists()
        and tcp_port_open(target_port)
        and os.environ.get("ALLOW_LIVE_RUNTIME_MUTATIONS", "0") != "1"
    )
    env_info["safe_rerun_mode"] = safe_rerun_mode
    if safe_rerun_mode:
        log(
            "Safe rerun mode enabled: official ComfyUI is already live, so bootstrap will avoid mutating "
            "the running Python/code environment"
        )
    prepare_portal_env(env_info)
    prepare_hf_auth()
    persist_official_env(env_info)
    persist_profile_env(env_info)
    install_system_packages(env_info)
    install_shell(env_info)
    ensure_comfyui_repo(env_info)
    ensure_supervisord(env_info)
    install_custom_nodes(env_info)
    sync_models(env_info)
    restore_comfy_config(env_info)
    auto_start_comfy = os.environ.get("AUTO_START_COMFYUI")
    should_start = False
    if env_info["official_image"]:
        if tcp_port_open(target_port):
            log(f"Official ComfyUI port {target_port} is already reachable; skipping bootstrap start")
        elif os.environ.get("OFFICIAL_COMFYUI_FALLBACK", "0") == "1":
            should_start = True
            log(
                f"Official ComfyUI port {target_port} is not reachable; starting manual fallback ComfyUI"
            )
        else:
            log(
                f"Official ComfyUI port {target_port} is not reachable; leaving startup to the official stack"
            )
    elif auto_start_comfy != "0":
        should_start = True
    if should_start:
        start_comfy(env_info, tmux=False, foreground=False)
    else:
        if env_info["official_image"]:
            log("Skipping automatic ComfyUI start because the official Vast path is disabled or already healthy")
        else:
            log("Skipping automatic ComfyUI start because AUTO_START_COMFYUI is not enabled")
    state_file.write_text("ok\n", encoding="utf-8")
    log("Bootstrap completed successfully")


def main() -> None:
    parser = argparse.ArgumentParser(description="Vast.ai ComfyUI bootstrap")
    parser.add_argument("--repo-root", default=None)
    subparsers = parser.add_subparsers(dest="command", required=True)

    subparsers.add_parser("bootstrap")

    start_parser = subparsers.add_parser("start-comfy")
    start_parser.add_argument("--tmux", action="store_true")
    start_parser.add_argument("--foreground", action="store_true")

    logs_parser = subparsers.add_parser("logs-comfy")
    logs_parser.add_argument("--follow", action="store_true")

    subparsers.add_parser("attach-comfy")
    subparsers.add_parser("install-shell")
    subparsers.add_parser("install-nodes")
    subparsers.add_parser("sync-models")
    subparsers.add_parser("restore-config")

    args = parser.parse_args()
    repo_root = repo_root_from_arg(args.repo_root)
    env_info = bootstrap_env(repo_root)

    if args.command == "bootstrap":
        bootstrap_all(repo_root)
    elif args.command == "start-comfy":
        start_comfy(env_info, tmux=args.tmux, foreground=args.foreground)
    elif args.command == "logs-comfy":
        show_logs(env_info, follow=args.follow)
    elif args.command == "attach-comfy":
        attach_tmux()
    elif args.command == "install-shell":
        install_shell(env_info)
    elif args.command == "install-nodes":
        install_custom_nodes(env_info)
    elif args.command == "sync-models":
        sync_models(env_info)
    elif args.command == "restore-config":
        restore_comfy_config(env_info)
    else:
        raise SystemExit(f"Unknown command: {args.command}")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        os.kill(os.getpid(), signal.SIGINT)
