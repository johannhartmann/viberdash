"""Main orchestrator for ViberDash - continuous code quality monitoring."""

import signal
import sys
import time
from pathlib import Path
from typing import Any

import click
import tomli
from rich.console import Console

from .analyzer import CodeAnalyzer
from .storage import MetricsStorage
from .test_runner import run_external_tests
from .tui import DashboardUI


class ViberDashRunner:
    """Main application runner that orchestrates the monitoring loop."""

    def __init__(self, source_dir: Path, config: dict[str, Any] | None = None):
        """Initialize runner with source directory and configuration."""
        self.source_dir = Path(source_dir).resolve()
        self.config = config or {}
        self.console = Console()

        # Initialize components
        self.analyzer = CodeAnalyzer(self.source_dir, config=self.config)
        self.storage = MetricsStorage()
        self.ui = DashboardUI(thresholds=self.config.get("thresholds"))

        # Control flag for graceful shutdown
        self.running = True

        # Set up signal handlers
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)

    def _signal_handler(self, signum: int, frame: Any) -> None:
        """Handle shutdown signals gracefully."""
        _ = signum, frame  # Unused but required by signal handler interface
        self.running = False
        self.console.print("\n[yellow]Shutting down ViberDash...[/yellow]")
        sys.exit(0)

    def run(self, interval: int = 60) -> None:
        """Run the main monitoring loop.

        Args:
            interval: Update interval in seconds

        """
        self.console.print(
            f"[green]Starting 🤖📊 ViberDash monitoring on:[/green] {self.source_dir}"
        )
        self.console.print(f"[green]Update interval:[/green] {interval} seconds")
        self.console.print(
            "[yellow]Note: Coverage analysis runs live tests on each scan[/yellow]\n"
        )

        # Initial scan
        self._perform_scan()

        # Main loop
        while self.running:
            try:
                # Wait for the specified interval
                time.sleep(interval)

                # Perform scan
                if self.running:
                    self._perform_scan()

            except KeyboardInterrupt:
                break
            except Exception as e:
                self.console.print(f"[red]Error in main loop: {e}[/red]")
                time.sleep(5)  # Brief pause before retrying

    def _perform_scan(self) -> None:
        """Perform a single scan cycle."""
        try:
            # Show scanning status
            self.ui.show_scanning()

            # Run analysis
            metrics = self.analyzer.run_analysis()

            # Save to database
            self.storage.save_metrics(metrics)

            # Get history for trends
            history = self.storage.get_history(limit=20)

            # Update display
            if history:
                self.ui.display_dashboard(history[0], history)

        except Exception as e:
            self.console.print(f"[red]Error during scan: {e}[/red]")


def load_config() -> dict[str, Any]:
    """Load configuration from pyproject.toml."""
    config_path = Path.cwd() / "pyproject.toml"

    if not config_path.exists():
        return {}

    try:
        with open(config_path, "rb") as f:
            pyproject = tomli.load(f)
            tool_config = pyproject.get("tool", {})
            viberdash_config: dict[str, Any] = tool_config.get("viberdash", {})
            return viberdash_config
    except Exception as e:
        Console().print(f"[yellow]Warning: Could not load config: {e}[/yellow]")
        return {}


@click.group()
def cli() -> None:
    """🤖📊 ViberDash main entry point."""
    pass


@cli.command()
@click.option(
    "--source-dir",
    "-s",
    type=click.Path(file_okay=False, dir_okay=True, path_type=Path),
    default=None,
    help="Source directory to analyze (default: from config or current directory)",
)
@click.option(
    "--interval",
    "-i",
    type=int,
    default=180,
    help="Update interval in seconds (default: 180)",
)
@click.option(
    "--config",
    "-c",
    type=click.Path(exists=True, dir_okay=False, path_type=Path),
    help="Path to configuration file (default: pyproject.toml)",
)
def monitor(source_dir: Path | None, interval: int, config: Path | None) -> None:
    """🤖📊 ViberDash - Real-time code quality monitoring dashboard.

    Monitor your Python codebase with live metrics including complexity,
    maintainability, test coverage, and code duplication.
    """
    console = Console()

    # Print banner
    console.print(
        """
[bold cyan]🤖📊 ViberDash[/bold cyan]
[dim]Real-time Code Quality Dashboard[/dim]
"""
    )

    # Load configuration
    if config:
        try:
            with open(config, "rb") as f:
                config_data = tomli.load(f)
                viberdash_config = config_data.get("tool", {}).get("viberdash", {})
        except Exception as e:
            console.print(f"[red]Error loading config: {e}[/red]")
            sys.exit(1)
    else:
        viberdash_config = load_config()

    # Determine source directory
    if source_dir is None:
        source_dir = Path(viberdash_config.get("source_dir", "."))

    source_dir = source_dir.resolve()

    # Validate source directory
    if not source_dir.exists():
        console.print(
            f"[red]Error: Source directory does not exist: {source_dir}[/red]"
        )
        sys.exit(1)

    # Check if it contains Python files
    # Create a temporary analyzer to check filtered file count
    temp_analyzer = CodeAnalyzer(source_dir, viberdash_config)
    py_files = temp_analyzer._get_python_files()
    if not py_files:
        console.print(f"[red]Error: No Python files found in: {source_dir}[/red]")
        console.print(
            "[yellow]Note: Files may be excluded by patterns in config[/yellow]"
        )
        sys.exit(1)

    console.print(f"[green]Found {len(py_files)} Python files to analyze[/green]")
    if viberdash_config.get("exclude_patterns"):
        patterns = viberdash_config["exclude_patterns"][:5]
        suffix = "..." if len(viberdash_config["exclude_patterns"]) > 5 else ""
        console.print(f"[dim](excluding patterns: {', '.join(patterns)}{suffix})[/dim]")
    console.print()

    # Create and run the application
    try:
        runner = ViberDashRunner(source_dir, viberdash_config)
        runner.run(interval)
    except Exception as e:
        console.print(f"[red]Fatal error: {e}[/red]")
        sys.exit(1)


@cli.command()
def test() -> None:
    """Run external tests for a project."""
    run_external_tests()


def main() -> None:
    cli()


if __name__ == "__main__":
    main()
