#!/usr/bin/env bash

#set -eo pipefail

# Functions

log_error() {
	echo -e "\e[31m${1}\e[0m"
}

log_info() {
	echo -e "\e[32m${1}\e[0m"
}

log_blue() {
	echo -e "\e[34m${1}\e[0m"
}

log_yellow() {
	echo -e "\e[1;33m${1}\e[0m"
}

log_light_blue() {
	echo -e "\e[1;34m${1}\e[0m"
}

run_cmd() {
	CMD=$1
	DESC=${2:-"[default] Execute command"}
	TMP_OUTPUT=$(mktemp)

	${CMD} >${TMP_OUTPUT} 2>&1

	if [ $? -eq 0 ]; then
		log_yellow "${DESC} - OK"
	else
		log_error "${DESC} - ERROR: $(cat ${TMP_OUTPUT})"
	fi
}

# Set variables
ZELLIJ_VERSION=${ZELLIJ_VERSION:-"v0.40.1"}
EZA_VERSION=${EZA_VERSION:-"v0.18.19"}
FZF_VERSION=${FZF_VERSION:-"0.54.3"}
ZOXIDE_VERSION=${ZOXIDE_VERSION:-"0.9.4"}

# Setup extra repos
if [ ! -f /etc/apt/sources.list.d/nodesource.list ]; then
	curl -fsSL https://deb.nodesource.com/setup_16.x | sudo -E bash -
else
	log_blue "Skipping NodeJS repo. File already exists"
fi

# System
## Disable sleep
run_cmd "sudo systemctl mask sleep.target suspend.target hibernate.target hybrid-sleep.target" "[systemctl] Disable sleep"

# Install os packages

run_cmd "sudo apt-get -y install gcc make cmake gettext git curl bat stow nodejs golang python3-pip python3-venv kitty zsh btop yazi" "[apt] Install tools"

# Install fonts
#[ ! -d ~/.local/share/fonts ] && mkdir -p ~/.local/share/fonts
#run_cmd "curl -sL https://github.com/romkatv/powerlevel10k-media/raw/master/MesloLGS%20NF%20Regular.ttf -o ~/.local/share/fonts/MesloLGSNFRegular.ttf" "[curl] Install font MesloGLS"
#run_cmd "fc-cache -fv" "[fc-cache] Refresh fonts cache"

# Install ohmyzsh
if [ ! -e ~/.oh-my-zsh ]; then
	sh -c "$(curl -fsSL https://raw.githubusercontent.com/ohmyzsh/ohmyzsh/master/tools/install.sh)" "" --unattended
else
	log_yellow "Skipping ohmyzsh install"
fi

# Install ZSH plugins
# Autosuggestions: https://github.com/zsh-users/zsh-autosuggestions/blob/master/INSTALL.md#oh-my-zsh
#git clone https://github.com/zsh-users/zsh-autosuggestions ${ZSH_CUSTOM:-~/.oh-my-zsh/custom}/plugins/zsh-autosuggestions
# Kube-ps1: https://github.com/jonmosco/kube-ps1?tab=readme-ov-file#oh-my-zsh

# Install oh-my-posh
#curl -s https://ohmyposh.dev/install.sh | bash -s -- -d ~/.local/bin

# Install fzf
if [ "$(uname -m)" == "x86_64" ]; then
	curl -sLO https://github.com/junegunn/fzf/releases/download/v${FZF_VERSION}/fzf-${FZF_VERSION}-linux_amd64.tar.gz
	sudo tar -C /usr/local/bin -xzf fzf-${FZF_VERSION}-linux_amd64.tar.gz
	sudo rm fzf-${FZF_VERSION}-linux_amd64.tar.gz
else
	curl -sLO https://github.com/junegunn/fzf/releases/download/v${FZF_VERSION}/fzf-${FZF_VERSION}-linux_arm64.tar.gz
	sudo tar -C /usr/local/bin -xzf fzf-${FZF_VERSION}-linux_arm64.tar.gz
	sudo rm fzf-${FZF_VERSION}-linux_arm64.tar.gz
fi

# Install zoxide
if [ "$(uname -m)" == "x86_64" ]; then
	curl -sLO https://github.com/ajeetdsouza/zoxide/releases/download/v${ZOXIDE_VERSION}/zoxide-${ZOXIDE_VERSION}-x86_64-unknown-linux-musl.tar.gz
	sudo tar -C /usr/local/bin -xzf zoxide-${ZOXIDE_VERSION}-x86_64-unknown-linux-musl.tar.gz
	sudo rm zoxide-${ZOXIDE_VERSION}-x86_64-unknown-linux-musl.tar.gz
else
	curl -sLO https://github.com/ajeetdsouza/zoxide/releases/download/v${ZOXIDE_VERSION}/zoxide-${ZOXIDE_VERSION}-aarch64-unknown-linux-musl.tar.gz
	sudo tar -C /usr/local/bin -xzf zoxide-${ZOXIDE_VERSION}-aarch64-unknown-linux-musl.tar.gz
	sudo rm zoxide-${ZOXIDE_VERSION}-aarch64-unknown-linux-musl.tar.gz
fi

# Install eza
if [ "$(uname -m)" == "x86_64" ]; then
	curl -sLO https://github.com/eza-community/eza/releases/download/${EZA_VERSION}/eza_x86_64-unknown-linux-gnu.tar.gz
	sudo tar -C /usr/local/bin -xzf eza_x86_64-unknown-linux-gnu.tar.gz
	sudo rm eza_x86_64-unknown-linux-gnu.tar.gz
else
	curl -sLO https://github.com/eza-community/eza/releases/download/${EZA_VERSION}/eza_aarch64-unknown-linux-gnu.tar.gz
	sudo tar -C /usr/local/bin -xzf eza_aarch64-unknown-linux-gnu.tar.gz
	sudo rm eza_aarch64-unknown-linux-gnu.tar.gz
fi

# Install neovim
if [ "$(uname -m)" == "x86_64" ]; then
	curl -sLO https://github.com/neovim/neovim/releases/latest/download/nvim-linux64.tar.gz
	sudo rm -rf /opt/nvim
	sudo tar -C /opt --transform 's/nvim-linux64/nvim/g' -xzf nvim-linux64.tar.gz
	sudo rm nvim-linux64.tar.gz
	sudo stow -d /opt nvim
else
	curl -sLO https://github.com/neovim/neovim/archive/refs/tags/nightly.tar.gz
	tar -C /opt -xzf nightly.tar.gz
	cd /opt/neovim-nightly
	make -j$(nproc) install
	cd -
	rm nightly.tar.gz
fi

# Install Zellij
if [ ! -f /usr/local/bin/zellij ]; then
	log_yellow "Installing Zellij"
	if [ "$(uname -m)" == "x86_64" ]; then
		curl -sLO https://github.com/zellij-org/zellij/releases/download/${ZELLIJ_VERSION}/zellij-x86_64-unknown-linux-musl.tar.gz
		tar -C /usr/local/bin -xzvf zellij-x86_64-unknown-linux-musl.tar.gz
		rm zellij-x86_64-unknown-linux-musl.tar.gz
	else
		curl -sLO https://github.com/zellij-org/zellij/releases/download/${ZELLIJ_VERSION}/zellij-aarch64-unknown-linux-musl.tar.gz
		tar -C /usr/local/bin -xzvf zellij-aarch64-unknown-linux-musl.tar.gz
		rm zellij-aarch64-unknown-linux-musl.tar.gz
	fi
else
	log_blue "Skipping Zellij, already exists"
fi

# Bootstrap LazyVim
if [ ! -d ~/.config/nvim ]; then
	log_yellow "Bootstrapping LazyVim"
	git clone https://github.com/LazyVim/starter ~/.config/nvim
	check_output $? "[git] Clone LazyVim starter"
else
	log_blue "Skipping Lazyvim bootstrap, already exists"
fi
