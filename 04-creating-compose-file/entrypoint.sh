#!/bin/sh
set -e

VENV_DIR="/app/venv"

# Create venv dir
if [ ! -d "$VENV_DIR" ]; then
	echo ">>> Creating virtual environment..."
	python -m venv $VENV_DIR
fi

echo ">>> Activating virtual environment..."
. $VENV_DIR/bin/activate

echo ">>> Installing dependencies..."
pip install --no-cache-dir -r requirements.txt

echo ">>> Starting application..."
uvicorn src.main:app --host 0.0.0.0 --port 8080
