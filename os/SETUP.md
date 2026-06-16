# Install Nvidia container runtime

## Install toolkit

```bash
curl -s -L https://nvidia.github.io/libnvidia-container/stable/rpm/nvidia-container-toolkit.repo | \
  sudo tee /etc/yum.repos.d/nvidia-container-toolkit.repo
sudo rpm-ostree install nvidia-container-toolkit-base --allow-inactive
sudo reboot
```

## Generate CDI configuration

```bash
sudo nvidia-ctk cdi generate --output=/etc/cdi/nvidia.yaml
nvidia-ctk cdi list
```

## Run

```bash
podman run -it --device nvidia.com/gpu=all --security-opt=label=disable -p 8000:8000 ghcr.io/ggerganov/llama.cpp:server-cuda-b4719 -hfr unsloth/gemma-4-12b-it-GGUF:Q4_K_M -ctk q8_0 -ctv q4_0 -np 1 -c 131072
```
