#!/bin/bash
# Startup script for React frontend
set -euo pipefail

cd "$(dirname "$0")/../frontend"

if [ ! -d "node_modules" ]; then
    echo "Installing dependencies..."
    npm ci
fi

echo "Starting Vite dev server on http://localhost:5173"
echo "Backend API should be running on http://127.0.0.1:8008"
echo "Press Ctrl+C to stop"

npm run dev
