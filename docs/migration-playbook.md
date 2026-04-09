# Migration Playbook

## On your current Vast instance

1. Clone this repository onto the current working instance.
2. Export your live custom node state:

```bash
COMFYUI_ROOT=/workspace/ComfyUI /workspace/bootstrap/bin/export-custom-nodes-lock
```

3. Inventory your current models:

```bash
COMFYUI_ROOT=/workspace/ComfyUI /workspace/bootstrap/bin/inventory-model-files
```

4. Package small ComfyUI config:

```bash
COMFYUI_ROOT=/workspace/ComfyUI /workspace/bootstrap/bin/package-comfy-config
```

## After export

- Replace `config/custom-nodes.lock.yaml` with `config/custom-nodes.generated.yaml` after reviewing it.
- Convert `config/models.inventory.txt` into real Hugging Face-backed entries in `config/models.lock.yaml`.
- Keep only the user config you really want inside `config/comfyui-config.tar.zst`.
- Push this repository to a private git repo and point `BOOTSTRAP_REPO` at it.

## On the new Vast template

1. Use `SSH` launch mode.
2. Set the environment variables from [`templates/vast-template.env.example`](/Users/yongkang/Documents/Gemma4/templates/vast-template.env.example).
3. Paste [`templates/on-start.sh`](/Users/yongkang/Documents/Gemma4/templates/on-start.sh) into the `on-start` field.
4. Start a fresh instance and watch `/workspace/bootstrap/bootstrap.log`.
