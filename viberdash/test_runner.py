

import subprocess
import tomli
from pathlib import Path
from rich.console import Console
from rich.panel import Panel

console = Console()

def find_project_root(start_path: Path) -> Path | None:
    """Find the project root by looking for pyproject.toml."""
    path = start_path.resolve()
    while path.parent != path:
        if (path / "pyproject.toml").is_file():
            return path
        path = path.parent
    return None

def run_external_tests():
    """
    Finds and runs the test command specified in the target project's pyproject.toml.
    """
    project_root = find_project_root(Path.cwd())
    if not project_root:
        console.print("[bold red]Error: pyproject.toml not found in the current directory or any parent directory.[/bold red]")
        return

    pyproject_path = project_root / "pyproject.toml"
    with open(pyproject_path, "rb") as f:
        config = tomli.load(f)

    test_command = config.get("tool", {}).get("viberdash", {}).get("test_command")

    if not test_command:
        console.print(f"[bold yellow]Warning: No 'test_command' found in {pyproject_path} under [tool.viberdash].[/bold yellow]")
        return

    console.print(Panel(f"Running command: [bold cyan]{test_command}[/bold cyan] in [dim]{project_root}[/dim]", title="[bold green]External Test Runner[/bold green]", expand=False))

    try:
        process = subprocess.run(
            test_command,
            shell=True,
            capture_output=True,
            text=True,
            cwd=project_root,
            check=False,  # Do not raise exception on non-zero exit code
        )

        if process.stdout:
            console.print(Panel(process.stdout, title="[bold]Test Output (stdout)[/bold]", border_style="green"))
        
        if process.stderr:
            console.print(Panel(process.stderr, title="[bold]Test Output (stderr)[/bold]", border_style="red"))

        if process.returncode == 0:
            console.print("[bold green]✅ Tests passed successfully![/bold green]")
        else:
            console.print(f"[bold red]❌ Tests failed with exit code {process.returncode}.[/bold red]")

    except Exception as e:
        console.print(Panel(f"An error occurred while trying to run the test command:\n{e}", title="[bold red]Execution Error[/bold red]"))

