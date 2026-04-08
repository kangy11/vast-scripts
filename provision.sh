#!/bin/bash
set -euo pipefail

export DEBIAN_FRONTEND=noninteractive

apt-get update
apt-get install -y zsh git curl wget vim fzf ca-certificates

TARGET_USER=root
TARGET_HOME=/root

if [ ! -d "$TARGET_HOME/.oh-my-zsh" ]; then
  RUNZSH=no CHSH=no KEEP_ZSHRC=yes \
  sh -c "$(curl -fsSL https://raw.githubusercontent.com/ohmyzsh/ohmyzsh/master/tools/install.sh)"
fi

ZSH_CUSTOM="${ZSH_CUSTOM:-$TARGET_HOME/.oh-my-zsh/custom}"

if [ ! -d "$ZSH_CUSTOM/plugins/zsh-autosuggestions" ]; then
  git clone https://github.com/zsh-users/zsh-autosuggestions \
    "$ZSH_CUSTOM/plugins/zsh-autosuggestions"
fi

if [ ! -d "$ZSH_CUSTOM/plugins/zsh-syntax-highlighting" ]; then
  git clone https://github.com/zsh-users/zsh-syntax-highlighting \
    "$ZSH_CUSTOM/plugins/zsh-syntax-highlighting"
fi

if [ ! -d "$ZSH_CUSTOM/plugins/you-should-use" ]; then
  git clone https://github.com/MichaelAquilina/zsh-you-should-use \
    "$ZSH_CUSTOM/plugins/you-should-use"
fi

cat > "$TARGET_HOME/.zshrc" <<'EOF'
export ZSH="$HOME/.oh-my-zsh"
ZSH_THEME="robbyrussell"

plugins=(
  git
  fzf
  zsh-autosuggestions
  zsh-syntax-highlighting
  you-should-use
)

source $ZSH/oh-my-zsh.sh

autoload -Uz compinit
compinit

HISTFILE=~/.zsh_history
HISTSIZE=10000
SAVEHIST=10000
setopt HIST_IGNORE_DUPS
setopt SHARE_HISTORY

alias ll='ls -alF'
alias la='ls -A'
alias l='ls -CF'
alias gs='git status'
alias cfy='cd /workspace/ComfyUI'
alias cwm='cd /workspace/ComfyUI/models'
EOF

chsh -s /usr/bin/zsh "$TARGET_USER" || true

if ! grep -q 'exec zsh' "$TARGET_HOME/.bashrc"; then
  cat >> "$TARGET_HOME/.bashrc" <<'EOF'

case $- in
  *i*) [ -x /usr/bin/zsh ] && exec zsh ;;
esac
EOF
fi
