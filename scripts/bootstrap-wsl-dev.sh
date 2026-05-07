#!/usr/bin/env bash

set -euo pipefail

SCRIPT_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
REPO_ROOT=$(cd "$SCRIPT_DIR/.." && pwd)
BACKEND_DIR="$REPO_ROOT/backend"
FRONTEND_DIR="$REPO_ROOT/frontend"

if [[ ! -f "$BACKEND_DIR/pyproject.toml" || ! -f "$FRONTEND_DIR/package.json" ]]; then
  echo "Run this script from inside the Eventboard repository." >&2
  exit 1
fi

log() {
  printf '\n[%s] %s\n' "$(date '+%H:%M:%S')" "$*"
}

have_cmd() {
  command -v "$1" >/dev/null 2>&1
}

ensure_apt_packages() {
  log "Installing apt packages"
  sudo apt-get update
  sudo apt-get install -y \
    build-essential \
    ca-certificates \
    curl \
    git \
    libffi-dev \
    libnss3 \
    libpq-dev \
    libssl-dev \
    pkg-config \
    python3 \
    python3-dev \
    python3-pip \
    python3-venv
}

ensure_uv() {
  if have_cmd uv; then
    log "uv already installed: $(uv --version)"
    return
  fi

  log "Installing uv"
  curl -LsSf https://astral.sh/uv/install.sh | sh
  export PATH="$HOME/.local/bin:$PATH"
}

ensure_nvm_loaded() {
  export NVM_DIR="$HOME/.nvm"
  if [[ -s "$NVM_DIR/nvm.sh" ]]; then
    # shellcheck source=/dev/null
    . "$NVM_DIR/nvm.sh"
  fi
}

ensure_node() {
  ensure_nvm_loaded

  local need_install=1
  if have_cmd node; then
    local node_major
    node_major=$(node -p 'process.versions.node.split(".")[0]')
    if [[ "$node_major" -ge 18 ]]; then
      need_install=0
      log "Node.js already installed: $(node --version)"
    fi
  fi

  if [[ "$need_install" -eq 1 ]]; then
    if [[ ! -s "$HOME/.nvm/nvm.sh" ]]; then
      log "Installing nvm"
      curl -fsSL https://raw.githubusercontent.com/nvm-sh/nvm/v0.40.3/install.sh | bash
    fi

    ensure_nvm_loaded
    log "Installing Node.js 20"
    nvm install 20
    nvm alias default 20
    nvm use 20 >/dev/null
  fi

  if ! have_cmd npm; then
    echo "npm is not available after Node.js installation." >&2
    exit 1
  fi
}

setup_backend() {
  log "Setting up backend dependencies"
  export PATH="$HOME/.local/bin:$PATH"
  cd "$BACKEND_DIR"
  uv venv
  uv sync --extra test

  if [[ ! -f "$BACKEND_DIR/app/config/config.local.json" ]]; then
    cp "$BACKEND_DIR/app/config/config.example" "$BACKEND_DIR/app/config/config.local.json"
    log "Created backend/app/config/config.local.json from example"
  fi

  if [[ ! -f "$BACKEND_DIR/app/config/config.json" ]]; then
    cp "$BACKEND_DIR/app/config/config.example" "$BACKEND_DIR/app/config/config.json"
    log "Created backend/app/config/config.json from example"
  fi
}

setup_frontend() {
  log "Setting up frontend dependencies"
  cd "$FRONTEND_DIR"
  npm ci

  if [[ ! -f "$FRONTEND_DIR/.env" ]]; then
    cat <<'EOF'

frontend/.env is missing.
Create it manually with your FB_* values if you use Firebase messaging.
EOF
  fi
}

print_next_steps() {
  cat <<'EOF'

Bootstrap completed.

Next steps:
1. Restore local secrets into backend/app/config/ and frontend/.env.
2. Run backend checks:
   cd backend && uv run pytest
3. Start backend:
   cd backend && uv run python main.py
4. Start frontend:
   cd frontend && npx quasar dev

If Git is not configured yet, set it now:
  git config --global user.name "Your Name"
  git config --global user.email "you@example.com"
EOF
}

main() {
  ensure_apt_packages
  ensure_uv
  ensure_node
  setup_backend
  setup_frontend
  print_next_steps
}

main "$@"