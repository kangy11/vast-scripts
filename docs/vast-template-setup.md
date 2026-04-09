# Vast Template Setup

## Launch mode

Use Vast template launch mode `SSH`.

## Docker image

Start from the same official-compatible ComfyUI base image you currently trust. Pin a tag instead of using `latest`.

## On-start

Paste the contents of [`templates/on-start.sh`](/Users/yongkang/Documents/Gemma4/templates/on-start.sh) into the Vast `on-start` field.

## Suggested env vars

Use [`templates/vast-template.env.example`](/Users/yongkang/Documents/Gemma4/templates/vast-template.env.example) as the base set.

## Shell behavior

- The instance installs `zsh` and `oh-my-zsh`
- The default shell is changed to `zsh` when possible
- `tmux` stays installed but is never auto-started
- `attach-comfy` only matters if you manually start ComfyUI with `start-comfy --tmux`

## Packing small ComfyUI config

Run:

```bash
COMFYUI_ROOT=/path/to/ComfyUI /path/to/repo/bin/package-comfy-config
```

Then commit or otherwise distribute the generated `config/comfyui-config.tar.zst` if your repository is private.
