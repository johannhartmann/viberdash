#!/usr/bin/env bash
# Setup script for development environment

set -e

echo "Setting up ViberDash development environment..."

# Install pre-commit hooks
if command -v pre-commit &> /dev/null; then
    echo "Installing pre-commit hooks..."
    pre-commit install
    echo "✓ Pre-commit hooks installed"
else
    echo "⚠️  pre-commit not found. Install it with: pip install pre-commit"
fi

echo ""
echo "✅ Development environment setup complete!"
echo ""
echo "Pre-commit hooks will now run automatically before each commit."
echo "To run hooks manually: pre-commit run --all-files"
