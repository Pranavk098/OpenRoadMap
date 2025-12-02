#!/usr/bin/env bash
# Exit on error
set -o errexit

echo "--------------------------------------"
echo "Build Script Started"
echo "--------------------------------------"

# 1. Upgrade pip to the latest version (Fixes 'No matching distribution' errors)
echo "Upgrading pip..."
python -m pip install --upgrade pip

# 2. Install dependencies from requirements.txt
echo "Installing dependencies..."
pip install -r requirements.txt

echo "--------------------------------------"
echo "Build Script Completed Successfully"
echo "--------------------------------------"
