#!/usr/bin/env bash
# One-time setup inside WSL Ubuntu (Windows: `wsl --install -d Ubuntu`, then open "Ubuntu").
set -euo pipefail
sudo apt-get update -y
sudo apt-get install -y python3-venv python3-pip git curl ca-certificates
if ! command -v node >/dev/null || [ "$(node -v | cut -c2- | cut -d. -f1)" -lt 18 ]; then
  curl -fsSL https://deb.nodesource.com/setup_20.x | sudo -E bash -
  sudo apt-get install -y nodejs
fi
sudo npm install -g brainlife
python3 -m venv ~/neuro-env
source ~/neuro-env/bin/activate
pip install --upgrade pip
pip install -r "$(dirname "$0")/requirements.txt"
[ -f "$(dirname "$0")/config.json" ] || cp "$(dirname "$0")/config.example.json" "$(dirname "$0")/config.json"
python -m pytest -q "$(dirname "$0")/tests" -k "not pipeline" || true
echo "Listo. Ahora: bl login   y edita local/config.json (brainlife_project)."
