#!/usr/bin/env bash


SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

VENV_PATH="$SCRIPT_DIR/venv"


source "$VENV_PATH/bin/activate"

python "$SCRIPT_DIR/summoner.py"


deactivate
