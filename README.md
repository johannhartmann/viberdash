# 🤖📊 ViberDash

A real-time terminal dashboard for monitoring Python code quality metrics. ViberDash continuously analyzes your codebase and displays key metrics in a beautiful, auto-updating terminal interface.

![ViberDash Screenshot](docs/screenshot.png)

## Quick Start

ViberDash is a development tool that monitors your Python project's code quality in real-time. It must be installed in your project's development environment:

```bash
# In your project's virtual environment
pip install viberdash

# Start monitoring
viberdash monitor
```

**Note**: ViberDash executes `pytest`, `ruff`, `pylint`, and other tools on your code. These must be installed in the same environment.

[![GitHub](https://img.shields.io/badge/GitHub-johannhartmann%2Fviberdash-blue)](https://github.com/johannhartmann/viberdash)
[![Python](https://img.shields.io/badge/python-3.12+-blue.svg)](https://www.python.org/)
[![License](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)
[![Code style: black](https://img.shields.io/badge/code%20style-black-000000.svg)](https://github.com/psf/black)

## Features

- **Real-time Monitoring**: Automatically scans your code every 180 seconds (3 minutes)
- **Live Test Coverage**: Runs your test suite on each scan to provide real-time coverage metrics
- **Rich Terminal UI**: Beautiful, color-coded metrics display using Rich
- **Comprehensive Metrics**:
  - Cyclomatic Complexity (Radon)
  - Maintainability Index (Radon)
  - Test Coverage (Pytest + Coverage.py) - **runs tests live!**
  - Code Duplication (Radon)
  - Dead Code Detection (Vulture)
  - Style Violations (Ruff)
  - Documentation Coverage (Ruff docstring checks)
- **Historical Tracking**: SQLite-based storage with trend visualization
- **Configurable Thresholds**: Customize what constitutes "good" or "bad" metrics
- **Sparkline Trends**: Visual representation of metric changes over time
- **No Static Files**: Coverage is calculated fresh on each scan, not read from outdated files

## Installation

⚠️ **Important**: ViberDash must be installed in your project's development environment where pytest, ruff, pylint, and other analysis tools are available. It cannot analyze your code from an isolated installation.

### Install as a Development Dependency (Recommended)

Add ViberDash to your project's development dependencies:

```toml
# In your project's pyproject.toml
[project.optional-dependencies]
dev = [
    "viberdash",
    "pytest",          # Required for test coverage
    "pytest-cov",      # Required for test coverage
    "ruff",            # Required for style analysis
    "pylint",          # Required for duplication detection
    "radon",           # Required for complexity analysis
    "vulture",         # Required for dead code detection
    # ... your other dev dependencies
]
```

Then install your project with dev dependencies:

```bash
# Using pip
pip install -e ".[dev]"

# Using uv
uv pip install -e ".[dev]"

# Using poetry
poetry install --with dev

# Using pdm
pdm install --dev
```

### Quick Test Installation

For a quick test without modifying your project:

```bash
# In your project's virtual environment
pip install viberdash

# Or with uv
uv pip install viberdash
```

### Installing from Source

To contribute to ViberDash or run the latest development version:

```bash
# Clone the repository
git clone https://github.com/johannhartmann/viberdash.git
cd viberdash

# Using Nix (includes all required tools)
nix develop
python -m viberdash.vibescan monitor --source-dir /path/to/your/project

# Or install in your project's environment
cd /path/to/your/project
source .venv/bin/activate  # or your virtual environment
pip install -e /path/to/viberdash
```

## Usage

Run ViberDash from your project's root directory (where your `pyproject.toml` or tests are located):

### Basic Usage

```bash
# From your project directory with activated virtual environment
cd /path/to/your/project
source .venv/bin/activate  # or your activation method

# Monitor current directory
viberdash monitor

# Monitor a specific subdirectory
viberdash monitor --source-dir src/

# Set custom update interval (default: 180 seconds)
viberdash monitor --interval 30

# Use a specific config file
viberdash monitor --config custom-config.toml
```

### Command Line Options

```
Commands:
  monitor  Start the real-time monitoring dashboard
  test     Run external tests for a project

Monitor Options:
  -s, --source-dir PATH  Source directory to analyze
  -i, --interval INT     Update interval in seconds (default: 180)
  -c, --config PATH      Path to configuration file (default: pyproject.toml)
  --help                 Show this message and exit
```

## Configuring Your Python Project for ViberDash

ViberDash can monitor any Python project. Here's how to configure your application:

### 1. Basic Setup

Add ViberDash configuration to your project's `pyproject.toml`:

```toml
[tool.viberdash]
# Directory to analyze (relative to project root)
# If not specified, defaults to current directory
source_dir = "src/"  # or "mypackage/" or wherever your Python code is

# Optional: Custom metric thresholds
[tool.viberdash.thresholds.cyclomatic_complexity]
good = 5.0      # Below this = green
bad = 10.0      # Above this = red

[tool.viberdash.thresholds.maintainability_index]
good = 85.0     # Above this = green
bad = 65.0      # Below this = red

[tool.viberdash.thresholds.test_coverage]
good = 80.0     # Above this = green
bad = 60.0      # Below this = red

[tool.viberdash.thresholds.code_duplication]
good = 5.0      # Below this = green
bad = 15.0      # Above this = red

[tool.viberdash.thresholds.dead_code]
good = 5.0      # Below this = green
bad = 15.0      # Above this = red

[tool.viberdash.thresholds.style_violations]
good = 10.0     # Below this = green
bad = 25.0      # Above this = red

[tool.viberdash.thresholds.doc_coverage]
good = 80.0     # Above this = green
bad = 60.0      # Below this = red
```

### 2. Required Analysis Tools

ViberDash runs the following tools to analyze your code. They must be installed in the same environment as ViberDash:

| Tool | Purpose | Required For |
|------|---------|--------------|
| `pytest` + `pytest-cov` | Test coverage | Coverage metrics |
| `radon` | Complexity & maintainability | Complexity metrics |
| `ruff` | Style checking & docs | Style & documentation metrics |
| `pylint` | Code duplication | Duplication metrics |
| `vulture` | Dead code detection | Dead code metrics |

If any tool is missing, its metrics will show as 0 or unavailable.

### 3. Making ViberDash Work

Since ViberDash needs to execute these tools on your code, it must be installed in your project's development environment:

```bash
# ❌ Won't work - isolated environment
pipx install viberdash
viberdash monitor  # Can't find pytest, ruff, etc.

# ✅ Works - same environment as your tools
source .venv/bin/activate
pip install viberdash
viberdash monitor  # Can access all your dev tools
```

This ensures that when ViberDash runs `pytest` in your project directory, all necessary dependencies are available.

### 3. Example: Adding ViberDash to Your Project

Here's a complete example for different package managers:

#### Using pip/setuptools

```toml
# pyproject.toml
[project.optional-dependencies]
dev = [
    "viberdash",
    "pytest>=7.0",
    "pytest-cov>=4.0",
    "ruff>=0.1.0",
    "pylint>=3.0",
    "radon>=6.0",
    "vulture>=2.7",
]
```

#### Using Poetry

```toml
# pyproject.toml
[tool.poetry.group.dev.dependencies]
viberdash = "^0.1.0"
pytest = "^7.0"
pytest-cov = "^4.0"
ruff = "^0.1.0"
# ... etc
```

#### Using uv

```toml
# pyproject.toml
[tool.uv]
dev-dependencies = [
    "viberdash>=0.1.0",
    "pytest>=7.0",
    "pytest-cov>=4.0",
    # ... etc
]
```

### 4. Running ViberDash

From your project root:

```bash
# If pyproject.toml has [tool.viberdash] config
viberdash monitor

# Or specify the source directory explicitly
viberdash monitor --source-dir src/

# Or from anywhere, pointing to your project
viberdash monitor --source-dir /path/to/project/src/
```

### 4. Example Configurations

#### Django Project
```toml
[tool.viberdash]
source_dir = "myapp/"  # Your Django app directory

[tool.viberdash.thresholds.test_coverage]
good = 90.0  # Django projects often aim for high coverage
bad = 75.0
```

#### FastAPI Project
```toml
[tool.viberdash]
source_dir = "app/"  # Common FastAPI structure

[tool.viberdash.thresholds.maintainability_index]
good = 80.0  # API endpoints can be complex
bad = 60.0
```

#### Data Science Project
```toml
[tool.viberdash]
source_dir = "src/"

[tool.viberdash.thresholds.cyclomatic_complexity]
good = 10.0  # Data processing can be complex
bad = 20.0

[tool.viberdash.thresholds.doc_coverage]
good = 90.0  # Documentation is crucial for data science
bad = 70.0
```

### 5. Handling False Positives

If ViberDash reports dead code that isn't actually dead (e.g., dynamic imports, entry points), create a `.vulture_whitelist` file:

```python
# .vulture_whitelist
_.my_dynamic_function  # Function called dynamically
_.MyClass.method      # Method used via getattr
_.api_endpoint        # FastAPI/Flask routes
```

### 6. Optimizing for Live Monitoring

Since ViberDash runs tests every scan interval (default: 180 seconds):

- **Keep tests fast**: Aim for < 2 minutes total runtime
- **Use pytest markers**: Run only unit tests if needed
- **Adjust interval**: Use `--interval 300` for slower test suites

```toml
# If you want ViberDash to run only fast tests
[tool.pytest.ini_options]
markers = [
    "slow: marks tests as slow",
    "fast: marks tests as fast",
]
```

Then tag your tests:
```python
@pytest.mark.fast
def test_quick_function():
    pass

@pytest.mark.slow
def test_integration():
    pass
```

### 7. Tips for Effective Monitoring

- **Run in a dedicated terminal**: Keep ViberDash visible while coding
- **Watch the trends**: Sparklines show if metrics are improving or degrading
- **Act on red metrics**: Address issues as they appear in real-time
- **Adjust thresholds**: Customize based on your project's needs and standards

## Real-time Test Coverage

ViberDash's standout feature is its **live test coverage analysis**. Unlike other tools that read stale `coverage.json` files, ViberDash:

- **Runs your full test suite** on each scan (every 3 minutes by default)
- **Calculates fresh coverage** by parsing pytest's terminal output directly
- **Shows real coverage changes** as you add/remove tests or modify code
- **Provides truly real-time feedback** on how your changes affect test coverage

This means you can:
- Watch your coverage improve as you add tests
- See coverage drop immediately when you add untested code
- Get accurate coverage metrics without manually running tests
- Trust that the coverage displayed is current, not from hours or days ago

⚠️ **Note**: Since ViberDash runs your full test suite on each scan, make sure your tests run reasonably fast (under 2 minutes recommended). You can adjust the scan interval with `--interval` if needed.

## Architecture

ViberDash consists of four main components:

1. **`vibescan.py`** - Main orchestrator that runs the continuous monitoring loop (default: 180s)
2. **`analyzer.py`** - Executes code analysis tools and runs live test coverage
3. **`storage.py`** - SQLite-based persistence for historical data and trends
4. **`tui.py`** - Rich-based terminal UI with live updates and sparkline trends

### Data Flow

```
[Configuration] → [Main Loop] → [Analyzer] → [Storage]
                      ↑             ↓             ↓
                      └─ [Terminal UI] ←─────────┘
                                    ↓
[Pytest + Coverage] ←─ [Live Test Execution]
```

On each scan cycle, ViberDash:
1. Runs static analysis tools (radon, vulture, ruff)
2. Executes your full test suite with coverage
3. Stores results in SQLite database
4. Updates the terminal display with trends and sparklines

## Development

### Running Tests

```bash
# Run tests with coverage
pytest --cov=viberdash

# Watch mode for development
pytest-watch
```

### Code Quality

```bash
# Format code
black viberdash/ tests/

# Lint code
ruff check viberdash/ tests/

# Type checking
mypy viberdash/
```

### Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

## Requirements

- Python 3.12+
- Unix-like environment (Linux, macOS, WSL)
- Terminal with color support

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## Acknowledgments

- Built with [Rich](https://github.com/Textualize/rich) for beautiful terminal output
- Uses [Radon](https://radon.readthedocs.io/) for complexity metrics
- Powered by [UV](https://github.com/astral-sh/uv) for fast Python package management
