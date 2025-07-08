# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Development Commands

### Environment Setup

- Use `nix develop` to start python development environment

### Running ViberDash

In `nix develop` environment:
```bash
# Direct module execution
python -m viberdash.vibescan

# Or if you have it installed via pip
viberdash
```

### Testing

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=viberdash

# Run specific test file
pytest tests/test_analyzer.py

# Run specific test
pytest tests/test_analyzer.py::test_run_analysis

# Watch mode for development
pytest-watch
```

### Code Quality

```bash
# Format code
black viberdash/ tests/

# Lint with ruff
ruff check viberdash/ tests/

# Type checking
mypy viberdash/

# All quality checks
black viberdash/ tests/ && ruff check viberdash/ tests/ && mypy viberdash/
```

## Architecture Overview

ViberDash is a real-time terminal dashboard for monitoring Python code quality metrics. It follows a modular architecture with clear separation of concerns:

### Core Components

1. **`vibescan.py`** - Main orchestrator
   - `ViberDashRunner` class manages the monitoring loop
   - Handles initialization, signal handling, and graceful shutdown
   - Loads configuration from `pyproject.toml` or CLI args
   - Default scan interval: 180 seconds (3 minutes) to allow time for test execution

2. **`analyzer.py`** - Code analysis engine
   - `CodeAnalyzer` class integrates multiple analysis tools
   - Executes radon, pylint, coverage.py, and vulture as subprocesses
   - Returns metrics dict with complexity, maintainability, coverage, duplication, dead code, style score, documentation coverage

3. **`storage.py`** - Metrics persistence
   - `MetricsStorage` class manages SQLite database (`viberdash.db`)
   - Stores timestamped metrics for historical tracking
   - Provides methods for saving, retrieving, and getting trend data

4. **`tui.py`** - Terminal UI
   - `DashboardUI` class uses Rich for terminal rendering
   - Displays color-coded metrics based on configurable thresholds
   - Shows delta changes and sparkline trends

### Data Flow

```
CLI → ViberDashRunner → CodeAnalyzer → MetricsStorage → DashboardUI
         ↑                                                    ↓
         └────────────── 60s loop ────────────────────────────┘
```

### Key Metrics

- **Cyclomatic Complexity**: Average and maximum (lower is better)
- **Maintainability Index**: Code maintainability score (higher is better)
- **Test Coverage**: Percentage covered by tests (higher is better)
- **Code Duplication**: Estimated duplication percentage (lower is better)
- **Dead Code**: Percentage of unused code detected by Vulture (lower is better)
- **Style Violations**: Percentage of lines with style issues detected by Ruff (lower is better)
- **Documentation Coverage**: Percentage of code with proper docstrings detected by Ruff (higher is better)

### Configuration

Thresholds configured in `pyproject.toml` under `[tool.viberdash.thresholds]`:
- Each metric has `good` and `bad` thresholds
- Values between thresholds show as yellow
- Can override with custom config file via `--config`

### Testing Approach

- Uses pytest with fixtures for temporary directories
- Tests create sample Python files to analyze
- Each module has corresponding test file
- Focus on integration testing with real tool execution
