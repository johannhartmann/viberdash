# Contributing to ViberDash

Thank you for your interest in contributing to ViberDash! We welcome contributions from the community.

## Development Setup

1. Fork the repository
2. Clone your fork:
   ```bash
   git clone https://github.com/yourusername/viberdash.git
   cd viberdash
   ```

3. Set up development environment:
   ```bash
   # Using nix (recommended)
   nix develop
   # Pre-commit hooks are installed automatically

   # Or using pip
   python -m venv .venv
   source .venv/bin/activate
   pip install -e ".[dev]"

   # Install pre-commit hooks
   pre-commit install
   ```

## Making Changes

1. Create a new branch:
   ```bash
   git checkout -b feature/your-feature-name
   ```

2. Make your changes and ensure tests pass:
   ```bash
   pytest

   # Pre-commit hooks will automatically run:
   # - black (formatting)
   # - ruff (linting)
   # - mypy (type checking)

   # Or run checks manually:
   pre-commit run --all-files
   ```

3. Commit your changes:
   ```bash
   # If using nix, ensure you're in the dev environment
   nix develop

   git add .
   git commit -m "feat: describe your changes"
   # Pre-commit hooks will run automatically
   ```

   **Note**: Pre-commit hooks require the development environment tools (black, ruff, mypy).
   If using nix, always commit from within `nix develop`.

## Submitting a Pull Request

1. Push your changes:
   ```bash
   git push origin feature/your-feature-name
   ```

2. Create a pull request on GitHub
3. Ensure all CI checks pass
4. Wait for review

## Code Style

- We use Black for code formatting
- We use Ruff for linting
- All code must have type hints
- All functions/classes must have docstrings
- Maintain test coverage above 80%

## Questions?

Feel free to open an issue for any questions or discussions!
