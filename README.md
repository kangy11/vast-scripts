# Vast.ai ComfyUI Bootstrap Kit

This repository turns a Vast.ai ComfyUI SSH instance into a reproducible setup that can be rebuilt on a different host without depending on host-local volumes.

## What it does

- Bootstraps an official-style ComfyUI SSH instance from a Vast `on-start` script
- Clones or updates the main ComfyUI repository
- Installs pinned Python and system dependencies
- Installs pinned custom nodes from `config/custom-nodes.lock.yaml`
- Downloads pinned models from Hugging Face using `config/models.lock.yaml`
- Restores small ComfyUI user config from a local archive or include list
- Sets the default shell to `zsh` with `oh-my-zsh`
- Installs `tmux` but never auto-starts or auto-attaches to it
- Exposes helper commands: `start-comfy`, `logs-comfy`, `attach-comfy`, `bootstrap-rerun`

## Repository layout

- `bootstrap.sh`: main entrypoint for Vast `on-start`
- `bootstrap/bootstrap.py`: orchestration logic
- `.bootstrap-venv/`: bootstrap runtime virtualenv created on first run
- `bin/`: helper commands installed into the shell `PATH`
- `config/system-packages.txt`: apt packages to install when available
- `config/python-requirements.lock`: pinned Python requirements
- `config/custom-nodes.lock.yaml`: pinned custom node repositories
- `config/models.lock.yaml`: pinned Hugging Face model downloads
- `config/private-models.upload.yaml`: candidate private model uploads extracted from your live instance
- `config/comfyui-config.include`: relative ComfyUI paths to pack into an archive
- `config/zsh/.zshrc`: default shell configuration
- `templates/on-start.sh`: Vast `on-start` example
- `templates/vast-template.env.example`: suggested Vast template variables
- `docs/migration-playbook.md`: extraction steps for your current live instance
- `docs/huggingface-private-upload.md`: private model upload workflow

## Quick start

1. Put this repository somewhere reachable by the target instance.
2. Set Vast template env vars using [`templates/vast-template.env.example`](/Users/yongkang/Documents/Gemma4/templates/vast-template.env.example).
3. Use [`templates/on-start.sh`](/Users/yongkang/Documents/Gemma4/templates/on-start.sh) as the template `on-start` script.
4. Fill in your actual models and custom nodes.
5. Optionally create `config/comfyui-config.tar.zst` with [`bin/package-comfy-config`](/Users/yongkang/Documents/Gemma4/bin/package-comfy-config).
6. If you are migrating an already-tuned instance, follow [`docs/migration-playbook.md`](/Users/yongkang/Documents/Gemma4/docs/migration-playbook.md).
7. If some models are private and should live in your own HF account, use [`docs/huggingface-private-upload.md`](/Users/yongkang/Documents/Gemma4/docs/huggingface-private-upload.md).

## Expected environment variables

- `BOOTSTRAP_REPO`: git URL for this repository
- `BOOTSTRAP_REF`: git ref to check out, defaults to the repo default branch
- `BOOTSTRAP_ROOT`: where this repo is cloned on the instance, defaults to `/workspace/bootstrap`
- `WORKSPACE_ROOT`: defaults to `/workspace`
- `COMFYUI_ROOT`: defaults to `/workspace/ComfyUI`
- `COMFYUI_REPO`: defaults to `https://github.com/comfyanonymous/ComfyUI.git`
- `COMFYUI_REF`: optional git ref for ComfyUI itself
- `HF_TOKEN`: optional but required for private Hugging Face repositories
- `COMFYUI_PORT`: defaults to `8188`
- `COMFYUI_ARGS`: extra arguments passed to `python main.py`

## Notes

- Vast local volumes can still be used as a same-host cache optimization, but the bootstrap flow does not depend on them.
- `config/comfyui-config.tar.zst` is intentionally not committed here because it is user-specific. Generate it from your live ComfyUI install with `bin/package-comfy-config`.
- This repository is safe to rerun. Existing matching clones and model downloads are reused.
