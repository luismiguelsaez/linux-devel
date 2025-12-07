#!/bin/bash

# Tools

curl -sL https://github.com/junegunn/fzf/releases/download/v0.67.0/fzf-0.67.0-linux_amd64.tar.gz -o - | tar -xzvf - fzf -C /usr/local/bin
curl -sL https://github.com/sharkdp/bat/releases/download/v0.26.0/bat-v0.26.0-x86_64-unknown-linux-gnu.tar.gz -o - | tar -tzvf - bat -C /usr/local/bin
curl -sL https://github.com/ajeetdsouza/zoxide/releases/download/v0.9.8/zoxide-0.9.8-x86_64-unknown-linux-musl.tar.gz -o - | tar -xzvf - zoxide -C /usr/local/bin
curl -sL https://github.com/eza-community/eza/releases/download/v0.23.4/eza_x86_64-unknown-linux-gnu.tar.gz | tar -tzvf - ./eza -C /usr/local/bin

# Neovim

curl -sL https://github.com/neovim/neovim/releases/latest/download/nvim-linux-x86_64.tar.gz | sudo tar -xzf - --transform 's/nvim-linux-x86_64//g' -C /usr/

# Lazyvim

mv ~/.config/nvim{,.bak}

# optional but recommended
mv ~/.local/share/nvim{,.bak}
mv ~/.local/state/nvim{,.bak}
mv ~/.cache/nvim{,.bak}

git clone https://github.com/LazyVim/starter ~/.config/nvim
rm -rf ~/.config/nvim/.git

# Copy Neovim plugin

cp -rp nvim/lua/plugins/* ~/.config/nvim/lua/plugins/
