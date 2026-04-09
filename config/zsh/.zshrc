umask 002

export ZSH="$HOME/.oh-my-zsh"
export COMFYUI_ROOT="__COMFYUI_ROOT__"
export BOOTSTRAP_ROOT="__BOOTSTRAP_ROOT__"
export WORKSPACE_ROOT="__WORKSPACE_ROOT__"
export PATH="$BOOTSTRAP_ROOT/bin:$PATH"

ZSH_THEME="robbyrussell"
plugins=(
  git
  sudo
  history-substring-search
  zsh-autosuggestions
  zsh-syntax-highlighting
)

source "$ZSH/oh-my-zsh.sh"
autoload -Uz compinit && compinit

if [[ -r "$HOME/.vast_containerlabel" ]]; then
  export VAST_CONTAINERLABEL="$(<"$HOME/.vast_containerlabel")"
fi

if [[ -n "${VAST_CONTAINERLABEL:-}" ]]; then
  PROMPT="%F{blue}%n%f%F{yellow}@%f%F{cyan}${VAST_CONTAINERLABEL}%f:%F{white}%~%f%# "
  _vast_set_title() {
    print -Pn "\e]0;%n@${VAST_CONTAINERLABEL}: %~\a"
  }
  precmd_functions+=(_vast_set_title)
else
  PROMPT='%F{cyan}%n@%m%f:%F{green}%~%f %# '
fi

if [[ -z "${KEEP_PWD:-}" && -d "${WORKSPACE_ROOT}" ]]; then
  cd "${WORKSPACE_ROOT}"
fi

set -a
[[ -f /etc/environment ]] && source /etc/environment
[[ -f "${WORKSPACE_ROOT}/.env" ]] && source "${WORKSPACE_ROOT}/.env"
set +a

if [[ -f /opt/nvm/nvm.sh ]]; then
  source /opt/nvm/nvm.sh
fi

if [[ -x /opt/miniforge3/bin/conda ]]; then
  __conda_setup="$(/opt/miniforge3/bin/conda shell.zsh hook 2>/dev/null)"
  if [[ $? -eq 0 ]]; then
    eval "$__conda_setup"
  elif [[ -f /opt/miniforge3/etc/profile.d/conda.sh ]]; then
    source /opt/miniforge3/etc/profile.d/conda.sh
  else
    export PATH="/opt/miniforge3/bin:$PATH"
  fi
  unset __conda_setup
fi

if [[ ${CONDA_SHLVL:-0} = 0 && -f /venv/${ACTIVE_VENV:-main}/bin/activate ]]; then
  source /venv/${ACTIVE_VENV:-main}/bin/activate
fi

setopt HIST_IGNORE_DUPS
setopt SHARE_HISTORY
bindkey '^[[A' history-substring-search-up
bindkey '^[[B' history-substring-search-down

alias ll='ls -lah'
alias la='ls -A'
alias l='ls -CF'
alias comfy='cd "$COMFYUI_ROOT"'
alias bootstrap='cd "$BOOTSTRAP_ROOT"'
