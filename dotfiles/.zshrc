export ZSH="$HOME/.oh-my-zsh"

ZSH_THEME="robbyrussell"
plugins=(git gh kubectl kube-ps1 zsh-autosuggestions)

PROMPT='$(kube_ps1)'$PROMPT

HYPHEN_INSENSITIVE="true"
zstyle ':omz:update' mode reminder  # just remind me to update when it's time
HIST_STAMPS="yyyy-mm-dd"

source $ZSH/oh-my-zsh.sh

eval "$(zoxide init zsh)"

# Aliases
alias c="clear"
alias cd="z"
alias ll="eza --icons=auto --git --long --octal-permissions --time=modified --sort=modified"
alias la="eza --icons=auto --git --long --octal-permissions --time=modified --sort=modified --all"
alias cat="bat --theme=ansi"
alias kctx="kubectx"
alias kns="kubens"
alias vi='nvim'
alias vim='nvim'
alias python='python3'
alias zellij='zellij --layout .config/zellij/layouts/custom.kdl'

# K9s config
K9S_CONFIG_DIR="~/.config/k9s"

# Krew path
export PATH="${KREW_ROOT:-$HOME/.krew}/bin:$PATH"

# Oh-my-posh
eval "$(oh-my-posh init zsh --config ~/.cache/oh-my-posh/themes/catppuccin_mocha.omp.json)"

# Load FZF shell integration
source <(fzf --zsh)

