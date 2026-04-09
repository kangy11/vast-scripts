# Vast Template Setup

## Launch mode

Use Vast template launch mode `SSH`.

## Docker image

Start from the same official-compatible ComfyUI base image you currently trust. Pin a tag instead of using `latest`.

On the official Vast ComfyUI SSH images, ComfyUI is already managed by the built-in supervisor and normally listens on internal port `18188`, which Vast exposes through the standard web entrypoint.

## On-start

Paste the contents of [`templates/on-start.sh`](/Users/yongkang/Documents/Gemma4/templates/on-start.sh) into the Vast `on-start` field.

This script should return quickly and let bootstrap continue in the background. That helps the official Vast portal come up instead of waiting for every node and model sync to finish first.

## Suggested env vars

Use [`templates/vast-template.env.example`](/Users/yongkang/Documents/Gemma4/templates/vast-template.env.example) as the base set.

For the official Vast ComfyUI image, keep:

```bash
AUTO_START_COMFYUI=0
OFFICIAL_COMFYUI_FALLBACK=1
COMFYUI_PORT=18188
COMFYUI_LOG_FILE=/var/log/portal/comfyui.log
```

That lets the bootstrap restore nodes, models, shell config, and user config without blindly launching a second ComfyUI process. If the official image fails to expose internal port `18188`, bootstrap now starts a fallback ComfyUI on that same internal port.

For a stable ComfyUI web login through the Vast portal, explicitly set:

```bash
WEB_USERNAME=vastai
WEB_PASSWORD=your-strong-password
```

If you omit `WEB_PASSWORD`, the portal may auto-generate a token, which is harder to remember across instances.

## Shell behavior

- The instance installs `zsh` and `oh-my-zsh`
- The default shell is changed to `zsh` when possible
- `tmux` stays installed but is never auto-started
- `attach-comfy` only matters if you manually start ComfyUI with `start-comfy --tmux`
- On official Vast images, `start-comfy` is a manual fallback tool, not part of the default boot flow

## Logs

For the official Vast ComfyUI image, watch:

```bash
tail -f /workspace/bootstrap/bootstrap.log
tail -f /var/log/portal/comfyui.log
```

## Packing small ComfyUI config

Run:

```bash
COMFYUI_ROOT=/path/to/ComfyUI /path/to/repo/bin/package-comfy-config
```

Then commit or otherwise distribute the generated `config/comfyui-config.tar.zst` if your repository is private.
