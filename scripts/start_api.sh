#!/bin/bash
# Startup script for FastAPI backend

cd "$(dirname "$0")"
source .venv/bin/activate

export PYTHONPATH=src

echo "Starting FastAPI server on http://127.0.0.1:8008"
echo "API documentation: http://127.0.0.1:8008/docs"
echo "Press Ctrl+C to stop"

uvicorn lab_auto.api.main:app --host 127.0.0.1 --port 8008 --reload
