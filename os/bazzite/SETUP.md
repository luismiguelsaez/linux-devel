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
podman run -it --device nvidia.com/gpu=all --security-opt=label=disable -p 8000:8000 ghcr.io/ggml-org/llama.cpp:server-cuda13 -hfr unsloth/gemma-4-12b-it-GGUF:Q4_K_M -ctk q8_0 -ctv q4_0 -np 1 -c 131072
```

# Enable hibernation

## Add kernel args

```bash
rpm-ostree kargs \
--append-if-missing=nvidia.NVreg_PreserveVideoMemoryAllocations=1 \
--append-if-missing=nvidia.NVreg_TemporaryFilePath=/var/tmp

rpm-ostree kargs --append mem_sleep_default=s2idle
```

# Access to serial devices

```bash
sudo setfacl -m u:luismi:rw /dev/ttyACM0
```

*This is the device created after connecting an external serial port through USB*
