#!/bin/bash

# DreamGuard backend - Development Startup Script
# Run from the backend folder: ./start.sh

echo "DreamGuard backend - Development Setup"
echo "========================================"

# Check if Python is installed
if ! command -v python3 &> /dev/null; then
    echo "Python 3 is not installed. Please install Python 3.12 and try again."
    exit 1
fi

echo "Python found: $(python3 --version)"

# Shared virtual environment lives at the repository root
if [ ! -d "../.venv" ]; then
    echo "Creating virtual environment in ../.venv ..."
    python3 -m venv ../.venv
    echo "Virtual environment created"
fi

# Activate virtual environment
echo "Activating virtual environment..."
source ../.venv/bin/activate

# Install dependencies (DreamGuard core library with the simulator, then the backend)
echo "Installing dependencies..."
python -m pip install -e "..[sim]"
python -m pip install -r requirements.txt

# Environment variables are read from the repository-level .env (loaded by main.py)
if [ ! -f "../.env" ]; then
    echo "Creating ../.env from ../.env.example ..."
    cp ../.env.example ../.env
    echo "../.env created - please update it with your configuration"
fi

# Create logs directory if it doesn't exist
mkdir -p logs

echo ""
echo "Setup complete! Choose how to run:"
echo "1. Development mode (with reload)"
echo "2. Production mode"
echo "3. Docker mode"
echo ""
read -p "Enter choice (1-3): " choice

case $choice in
    1)
        echo "Starting in development mode with hot reload..."
        uvicorn main:app --host 127.0.0.1 --port 8000 --reload
        ;;
    2)
        echo "Starting in production mode..."
        python main.py
        ;;
    3)
        echo "Starting with Docker..."
        docker compose up --build
        ;;
    *)
        echo "Invalid choice. Starting in development mode..."
        uvicorn main:app --host 127.0.0.1 --port 8000 --reload
        ;;
esac
