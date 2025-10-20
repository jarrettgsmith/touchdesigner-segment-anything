#!/bin/bash

# Run SAM 2 Server with Syphon + OSC

# Check if venv exists
if [ ! -d "venv_sam" ]; then
    echo "Error: Virtual environment not found."
    echo "Please run ./setup.sh first"
    exit 1
fi

# Activate venv
source venv_sam/bin/activate

# Run server
echo "Starting SAM 2 Server..."
python3 sam_server_syphon.py "$@"
