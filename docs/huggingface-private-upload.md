# Upload Private Models To Hugging Face

This repository now includes a repeatable uploader for your private ComfyUI models.

## Input file

Review and adjust [`config/private-models.upload.yaml`](/Users/yongkang/Documents/Gemma4/config/private-models.upload.yaml).

Each entry maps:

- `local_path`: file path relative to `COMFYUI_ROOT`
- `path_in_repo`: path inside the single private model repo
- `lock_target_dir`: where bootstrap should download relative to `COMFYUI_ROOT`

## Required auth

You need:

- `HF_NAMESPACE`: your Hugging Face username or org
- `HF_PRIVATE_REPO`: optional single repo name, defaults to `comfyui-private-models`
- `HF_TOKEN`: a token with permission to create and upload private model repos

## Dry run

Generate lock entries without uploading:

```bash
HF_NAMESPACE=your-name \
HF_PRIVATE_REPO=comfyui-private-models \
COMFYUI_ROOT=/workspace/ComfyUI \
./bin/upload-private-models-to-hf --skip-upload
```

This writes `config/private-models.generated.lock.yaml`.

## Upload

On the Vast machine:

```bash
HF_NAMESPACE=your-name \
HF_PRIVATE_REPO=comfyui-private-models \
HF_TOKEN=hf_xxx \
COMFYUI_ROOT=/workspace/ComfyUI \
./bin/upload-current-private-models
```

After upload, you do not need to keep merging individual private files into [`config/models.lock.yaml`](/Users/yongkang/Documents/Gemma4/config/models.lock.yaml) if you keep the single whole-repo sync entry for `wykang/comfyui-private-models`.

## Pull only the private repo

On the Vast machine:

```bash
cd /workspace/bootstrap
sync-private-models
```

That pulls only the private Hugging Face repo entries from [`config/models.lock.yaml`](/Users/yongkang/Documents/Gemma4/config/models.lock.yaml) and leaves the public model sync alone.

## Repo layout

The uploader now pushes everything into one private model repo and preserves the ComfyUI-relative path, for example:

- `models/diffusion_models/...`
- `models/loras/...`
- `models/embeddings/...`

Bootstrap can then download the whole private repo directly into `COMFYUI_ROOT`, so newly uploaded private models appear automatically on the next sync without editing the lock file.
