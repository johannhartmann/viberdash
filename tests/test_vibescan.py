"""
Tests for the vibescan module.
"""

import signal
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from viberdash.vibescan import ViberDashRunner, cli, load_config


@pytest.fixture
def temp_source_dir():
    """Create a temporary directory with Python files."""
    with tempfile.TemporaryDirectory() as tmpdir:
        source_dir = Path(tmpdir)

        # Create some Python files
        (source_dir / "module1.py").write_text(
            """
def hello():
    return "Hello"
"""
        )
        (source_dir / "module2.py").write_text(
            """
def world():
    return "World"
"""
        )

        yield source_dir


@pytest.fixture
def mock_analyzer():
    """Mock CodeAnalyzer."""
    analyzer = MagicMock()
    analyzer.run_analysis.return_value = {
        "avg_complexity": 5.0,
        "maintainability_index": 75.0,
        "test_coverage": 85.0,
        "code_duplication": 3.0,
    }
    return analyzer


@pytest.fixture
def mock_storage():
    """Mock MetricsStorage."""
    storage = MagicMock()
    storage.get_history.return_value = [
        {"avg_complexity": 5.0, "maintainability_index": 75.0},
        {"avg_complexity": 5.5, "maintainability_index": 74.0},
    ]
    return storage


@pytest.fixture
def mock_ui():
    """Mock DashboardUI."""
    ui = MagicMock()
    return ui


def test_viberdash_runner_init(temp_source_dir):
    """Test ViberDashRunner initialization."""
    config = {"thresholds": {"cyclomatic_complexity": {"good": 5.0, "bad": 10.0}}}

    runner = ViberDashRunner(temp_source_dir, config)

    assert runner.source_dir == temp_source_dir
    assert runner.config == config
    assert runner.running is True


def test_signal_handler(temp_source_dir):
    """Test signal handler for graceful shutdown."""
    runner = ViberDashRunner(temp_source_dir)

    with pytest.raises(SystemExit):
        runner._signal_handler(signal.SIGINT, None)

    assert runner.running is False


@patch("viberdash.vibescan.CodeAnalyzer")
@patch("viberdash.vibescan.MetricsStorage")
@patch("viberdash.vibescan.DashboardUI")
def test_perform_scan(
    mock_ui_cls, mock_storage_cls, mock_analyzer_cls, temp_source_dir
):
    """Test performing a single scan."""
    # Set up mocks
    mock_analyzer = MagicMock()
    mock_analyzer.run_analysis.return_value = ({"avg_complexity": 5.0}, [])
    mock_analyzer_cls.return_value = mock_analyzer

    mock_storage = MagicMock()
    mock_storage.get_history.return_value = [{"avg_complexity": 5.0}]
    mock_storage.get_recent_errors.return_value = []
    mock_storage_cls.return_value = mock_storage

    mock_ui = MagicMock()
    mock_ui_cls.return_value = mock_ui

    runner = ViberDashRunner(temp_source_dir)
    runner._perform_scan()

    # Verify calls
    mock_ui.show_scanning.assert_called_once()
    mock_analyzer.run_analysis.assert_called_once()
    mock_storage.save_metrics.assert_called_once_with({"avg_complexity": 5.0}, [])
    mock_storage.get_history.assert_called_once_with(limit=20)
    mock_storage.get_recent_errors.assert_called_once_with(limit=5)
    mock_ui.display_dashboard.assert_called_once()


@patch("viberdash.vibescan.CodeAnalyzer")
@patch("viberdash.vibescan.MetricsStorage")
@patch("viberdash.vibescan.DashboardUI")
def test_perform_scan_error_handling(
    mock_ui_cls, mock_storage_cls, mock_analyzer_cls, temp_source_dir
):
    """Test error handling during scan."""
    # Set up analyzer to raise an exception
    mock_analyzer = MagicMock()
    mock_analyzer.run_analysis.side_effect = Exception("Analysis failed")
    mock_analyzer_cls.return_value = mock_analyzer

    mock_storage_cls.return_value = MagicMock()
    mock_ui_cls.return_value = MagicMock()

    runner = ViberDashRunner(temp_source_dir)

    # Should not raise exception
    runner._perform_scan()

    # Verify error was caught
    assert mock_analyzer.run_analysis.called


@patch("viberdash.vibescan.time.sleep")
@patch("viberdash.vibescan.CodeAnalyzer")
@patch("viberdash.vibescan.MetricsStorage")
@patch("viberdash.vibescan.DashboardUI")
def test_run_main_loop(
    mock_ui_cls, mock_storage_cls, mock_analyzer_cls, mock_sleep, temp_source_dir
):
    """Test the main monitoring loop."""
    # Set up mocks
    mock_analyzer = MagicMock()
    mock_analyzer.run_analysis.return_value = {"avg_complexity": 5.0}
    mock_analyzer_cls.return_value = mock_analyzer

    mock_storage = MagicMock()
    mock_storage.get_history.return_value = [{"avg_complexity": 5.0}]
    mock_storage_cls.return_value = mock_storage

    mock_ui_cls.return_value = MagicMock()

    runner = ViberDashRunner(temp_source_dir)

    # Simulate running for 2 iterations then stop
    call_count = 0

    def side_effect(interval):
        nonlocal call_count
        call_count += 1
        if call_count >= 2:
            runner.running = False
        return

    mock_sleep.side_effect = side_effect

    runner.run(interval=1)

    # Should have performed initial scan + 1 loop iteration
    assert mock_analyzer.run_analysis.call_count >= 2


def test_load_config_no_file():
    """Test load_config when pyproject.toml doesn't exist."""
    with (
        tempfile.TemporaryDirectory() as tmpdir,
        patch("viberdash.vibescan.Path.cwd", return_value=Path(tmpdir)),
    ):
        config = load_config()
        assert config == {}


def test_load_config_with_file():
    """Test load_config with valid pyproject.toml."""
    with tempfile.TemporaryDirectory() as tmpdir:
        config_path = Path(tmpdir) / "pyproject.toml"
        config_path.write_text(
            """
[tool.viberdash]
source_dir = "src"

[tool.viberdash.thresholds]
cyclomatic_complexity = { good = 5.0, bad = 10.0 }
"""
        )

        with patch("viberdash.vibescan.Path.cwd", return_value=Path(tmpdir)):
            config = load_config()
            assert config["source_dir"] == "src"
            assert config["thresholds"]["cyclomatic_complexity"]["good"] == 5.0


def test_load_config_invalid_toml():
    """Test load_config with invalid TOML file."""
    with tempfile.TemporaryDirectory() as tmpdir:
        config_path = Path(tmpdir) / "pyproject.toml"
        config_path.write_text("invalid toml {{{")

        with patch("viberdash.vibescan.Path.cwd", return_value=Path(tmpdir)):
            config = load_config()
            assert config == {}


@patch("viberdash.vibescan.ViberDashRunner")
@patch("viberdash.vibescan.Console")
@patch("viberdash.vibescan.load_config")
def test_main_command_default_args(mock_load_config, mock_console_cls, mock_runner_cls):
    """Test main command with default arguments."""
    from click.testing import CliRunner

    # Mock config loading
    mock_load_config.return_value = {}

    # Mock console
    mock_console = MagicMock()
    mock_console_cls.return_value = mock_console

    # Mock the runner
    mock_runner = MagicMock()
    mock_runner_cls.return_value = mock_runner

    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir_path = Path(tmpdir)

        # Create a Python file
        (tmpdir_path / "test.py").write_text("print('test')")

        # Run the command
        runner = CliRunner()
        result = runner.invoke(cli, ["monitor", "--source-dir", str(tmpdir_path)])

        # Should have created runner and called run
        if result.exit_code != 0:
            print(f"DEBUG: Exit code: {result.exit_code}")
            print(f"DEBUG: Output: {result.output}")
            if result.exception:
                import traceback

                exc_info = traceback.format_exception(
                    type(result.exception),
                    result.exception,
                    result.exception.__traceback__,
                )
                print(f"DEBUG: Exception: {''.join(exc_info)}")
        assert result.exit_code == 0
        mock_runner_cls.assert_called_once()
        mock_runner.run.assert_called_once_with(180)


@patch("viberdash.vibescan.Console")
def test_main_command_no_python_files(mock_console_cls):
    """Test main command when no Python files are found."""
    from click.testing import CliRunner

    with tempfile.TemporaryDirectory() as tmpdir:
        runner = CliRunner()
        result = runner.invoke(cli, ["monitor", "--source-dir", tmpdir])

        assert result.exit_code == 1
        assert "No Python files found" in str(
            mock_console_cls.return_value.print.call_args_list
        )


@patch("viberdash.vibescan.Console")
def test_main_command_invalid_source_dir(mock_console_cls):
    """Test main command with invalid source directory."""
    from click.testing import CliRunner

    runner = CliRunner()
    result = runner.invoke(cli, ["monitor", "--source-dir", "/nonexistent/path"])

    # Click validates path exists, so this should fail before our code
    assert result.exit_code != 0


@patch("viberdash.vibescan.ViberDashRunner")
@patch("viberdash.vibescan.Console")
def test_main_command_with_config(mock_console_cls, mock_runner_cls):
    """Test main command with custom config file."""
    from click.testing import CliRunner

    # Mock console
    mock_console = MagicMock()
    mock_console_cls.return_value = mock_console

    # Mock the runner
    mock_runner = MagicMock()
    mock_runner_cls.return_value = mock_runner

    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir_path = Path(tmpdir)

        # Create a Python file
        (tmpdir_path / "test.py").write_text("print('test')")

        # Create custom config
        config_path = tmpdir_path / "custom.toml"
        config_path.write_text(
            """
[tool.viberdash]
source_dir = "."
"""
        )

        # Run the command
        runner = CliRunner()
        result = runner.invoke(
            cli,
            ["monitor", "--config", str(config_path), "--source-dir", str(tmpdir_path)],
        )

        assert result.exit_code == 0
        mock_runner_cls.assert_called_once()


@patch("viberdash.vibescan.ViberDashRunner")
@patch("viberdash.vibescan.Console")
@patch("viberdash.vibescan.load_config")
def test_main_command_custom_interval(
    mock_load_config, mock_console_cls, mock_runner_cls
):
    """Test main command with custom interval."""
    from click.testing import CliRunner

    # Mock config loading
    mock_load_config.return_value = {}

    # Mock console
    mock_console = MagicMock()
    mock_console_cls.return_value = mock_console

    # Mock the runner
    mock_runner = MagicMock()
    mock_runner_cls.return_value = mock_runner

    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir_path = Path(tmpdir)

        # Create a Python file
        (tmpdir_path / "test.py").write_text("print('test')")

        # Run the command
        runner = CliRunner()
        result = runner.invoke(
            cli, ["monitor", "--source-dir", str(tmpdir_path), "--interval", "30"]
        )

        assert result.exit_code == 0
        mock_runner.run.assert_called_once_with(30)


@patch("viberdash.vibescan.ViberDashRunner")
def test_main_command_runner_exception(mock_runner_cls):
    """Test main command when runner raises exception."""
    from click.testing import CliRunner

    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir_path = Path(tmpdir)

        # Create a Python file
        (tmpdir_path / "test.py").write_text("print('test')")

        # Mock runner to raise exception
        mock_runner_cls.side_effect = Exception("Runner failed")

        # Run the command
        runner = CliRunner()
        result = runner.invoke(cli, ["monitor", "--source-dir", str(tmpdir_path)])

        assert result.exit_code == 1
