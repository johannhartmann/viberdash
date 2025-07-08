#!/bin/bash
# Simple installation script for ViberDash

echo "🚀 Installing ViberDash..."

# Check if uv is available
if command -v uv &> /dev/null; then
    echo "Using UV for installation..."
    uv pip install -e .
    echo "✅ ViberDash installed successfully with UV!"
# Check if pip is available
elif command -v pip &> /dev/null; then
    echo "Using pip for installation..."
    pip install -e .
    echo "✅ ViberDash installed successfully with pip!"
else
    echo "❌ Error: Neither UV nor pip found. Please install Python and pip first."
    exit 1
fi

echo ""
echo "You can now use ViberDash by running: viberdash"
echo "Try: viberdash --help"
