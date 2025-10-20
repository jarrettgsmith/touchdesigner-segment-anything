#!/bin/bash

# Setup script for SAM 2 + Syphon + OSC

set -e

echo "=========================================="
echo "SAM 2 TouchDesigner Setup"
echo "=========================================="
echo ""

# Check for Python 3.10+
python_version=$(python3 --version 2>&1 | awk '{print $2}')
echo "Python version: $python_version"

# Create venv
echo ""
echo "[1/5] Creating virtual environment..."
python3 -m venv venv_sam

# Activate
echo "[2/5] Activating virtual environment..."
source venv_sam/bin/activate

# Upgrade pip
echo ""
echo "[3/5] Upgrading pip..."
pip install --upgrade pip

# Install PyTorch first (required for SAM 2)
echo ""
echo "[4/5] Installing PyTorch..."
pip install torch>=2.5.1 torchvision>=0.20.1

# Install SAM 2 from git
echo ""
echo "[5/5] Installing SAM 2..."
pip install git+https://github.com/facebookresearch/sam2.git

# Install other requirements
echo ""
echo "Installing communication dependencies..."
pip install -r requirements.txt

echo ""
echo "=========================================="
echo "✓ Setup complete!"
echo "=========================================="
echo ""
echo "Next steps:"
echo "1. The SAM 2 checkpoints will be downloaded automatically on first run"
echo "2. Run the server:"
echo "   ./run.sh"
echo ""
