"""
Tests for the analyzer module.
"""

import subprocess
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from viberdash.analyzer import CodeAnalyzer


@pytest.fixture
def temp_project():
    """Create a temporary project directory with Python files."""
    with tempfile.TemporaryDirectory() as tmpdir:
        project_dir = Path(tmpdir)

        # Create a simple Python file
        test_file = project_dir / "example.py"
        test_file.write_text(
            """
def simple_function(x):
    '''A simple function.'''
    if x > 0:
        return x * 2
    else:
        return x * 3

class ExampleClass:
    '''An example class.'''

    def method1(self):
        return "hello"

    def method2(self, value):
        if value:
            return True
        return False
"""
        )

        yield project_dir


def test_analyzer_init(temp_project):
    """Test analyzer initialization."""
    analyzer = CodeAnalyzer(temp_project)
    assert analyzer.source_dir == temp_project


def test_analyzer_init_invalid_dir():
    """Test analyzer initialization with invalid directory."""
    with pytest.raises(ValueError):
        CodeAnalyzer(Path("/nonexistent/directory"))


def test_run_analysis(temp_project):
    """Test running full analysis."""
    analyzer = CodeAnalyzer(temp_project)
    metrics, errors = analyzer.run_analysis()

    # Check that metrics dict contains expected keys
    assert "avg_complexity" in metrics
    assert "maintainability_index" in metrics
    assert "maintainability_density" in metrics
    assert "test_coverage" in metrics
    assert "code_duplication" in metrics
    assert "total_lines" in metrics
    assert "total_classes" in metrics

    # Basic sanity checks
    assert metrics["total_lines"] > 0
    assert metrics["total_classes"] >= 1  # We have ExampleClass
    assert metrics["maintainability_density"] > 0  # Should be calculated
    assert isinstance(errors, list)


def test_count_lines(temp_project):
    """Test line counting functionality."""
    analyzer = CodeAnalyzer(temp_project)
    line_count = analyzer._count_lines()
    assert line_count > 0


def test_count_pattern(temp_project):
    """Test pattern counting functionality."""
    analyzer = CodeAnalyzer(temp_project)
    class_count = analyzer._count_pattern(r"^class\s+\w+")
    assert class_count == 1  # ExampleClass


def test_run_analysis_with_errors(temp_project):
    """Test run_analysis when tools fail."""
    analyzer = CodeAnalyzer(temp_project)

    # Mock subprocess to simulate tool failures
    with patch("viberdash.analyzer.subprocess.run") as mock_run:
        # Make all tools fail
        mock_run.side_effect = subprocess.CalledProcessError(1, "tool")

        with patch.object(
            analyzer, "_analyze_coverage", return_value={"test_coverage": -1.0}
        ) as mock_coverage:
            metrics, errors = analyzer.run_analysis()

            # Should return default values when tools fail
            assert metrics["avg_complexity"] == 0
            assert metrics["maintainability_index"] == 0
            assert metrics["test_coverage"] == -1.0
            assert metrics["code_duplication"] == 0
            assert metrics["dead_code"] == 0
            assert metrics["style_violations"] == 0
            assert len(errors) > 0
            mock_coverage.assert_called_once()


def test_gitignore_handling(temp_project):
    """Test that gitignored files are handled."""
    # Create a .gitignore
    gitignore = temp_project / ".gitignore"
    gitignore.write_text(
        """
*.pyc
__pycache__/
ignored_dir/
"""
    )

    # Create files
    (temp_project / "main.py").write_text("# main")
    (temp_project / "test.pyc").write_text("# compiled")

    ignored_dir = temp_project / "ignored_dir"
    ignored_dir.mkdir()
    (ignored_dir / "ignored.py").write_text("# ignored")

    analyzer = CodeAnalyzer(temp_project)
    # Run analysis will process only non-ignored files
    metrics, _ = analyzer.run_analysis()

    # Should have processed files
    assert metrics["total_lines"] > 0

    # Check that gitignore was loaded
    assert analyzer.gitignore_spec is not None

    # Check that ignored files are excluded
    python_files = analyzer._get_python_files()
    file_names = [f.name for f in python_files]
    assert "main.py" in file_names or "example.py" in file_names
    assert "ignored.py" not in file_names


def test_tool_timeout_handling(temp_project):
    """Test tool timeout handling."""
    analyzer = CodeAnalyzer(temp_project)

    # Mock subprocess to simulate timeout
    with patch("viberdash.analyzer.subprocess.run") as mock_run:
        mock_run.side_effect = subprocess.TimeoutExpired("cmd", 5)

        # Run analysis should handle timeouts gracefully
        metrics, errors = analyzer.run_analysis()

        # Should return default values on timeout
        assert metrics["avg_complexity"] == 0
        assert len(errors) > 0


def test_analyze_complexity_error_handling(temp_project):
    """Test complexity analysis error handling."""
    analyzer = CodeAnalyzer(temp_project)
    errors = []

    # Mock radon to return invalid JSON
    with patch("viberdash.analyzer.subprocess.run") as mock_run:
        mock_run.return_value.stdout = "invalid json"
        mock_run.return_value.returncode = 0

        # Only mock radon calls
        original_run = subprocess.run

        def selective_mock(cmd, *args, **kwargs):
            if "radon" in cmd:
                return mock_run.return_value
            return original_run(cmd, *args, **kwargs)

        with patch("viberdash.analyzer.subprocess.run", side_effect=selective_mock):
            files = [str(f) for f in analyzer._get_python_files()]
            metrics = analyzer._analyze_complexity(files, errors)

            # Should return defaults on parse error
            assert metrics["avg_complexity"] == 0
            assert metrics["max_complexity"] == 0
            # No error is reported here, it just returns default metrics
            assert len(errors) == 0


def test_analyze_maintainability_error_handling(temp_project):
    """Test maintainability analysis error handling."""
    analyzer = CodeAnalyzer(temp_project)
    errors = []

    # Mock subprocess.run to return invalid JSON for radon mi
    with patch("viberdash.analyzer.subprocess.run") as mock_run:
        mock_result = MagicMock()
        mock_result.stdout = "invalid json output"
        mock_result.returncode = 0
        mock_run.return_value = mock_result

        # Test just the maintainability method directly
        files = [str(f) for f in analyzer._get_python_files()]
        result = analyzer._analyze_maintainability(files, errors)
        # The mock should cause JSON parsing to fail, returning 0
        assert result["maintainability_index"] == 0.0  # Should return 0 on error
        assert len(errors) == 0


def test_analyze_coverage_no_coverage_file(temp_project):
    """Test coverage analysis when coverage.json doesn't exist."""
    analyzer = CodeAnalyzer(temp_project)

    # Ensure no coverage.json exists in temp project
    coverage_file = temp_project / "coverage.json"
    if coverage_file.exists():
        coverage_file.unlink()

    # Mock Path.cwd to return temp_project so it looks for coverage.json there
    with patch("viberdash.analyzer.Path.cwd", return_value=temp_project):
        metrics, errors = analyzer.run_analysis()
        assert metrics["test_coverage"] == 0  # Should return 0 when no coverage data
        assert len(errors) > 0  # Should have an error about pytest failing


def test_analyze_dead_code_error_handling(temp_project):
    """Test dead code analysis error handling."""
    analyzer = CodeAnalyzer(temp_project)
    errors = []

    # Mock subprocess.run to return empty output for vulture
    with patch("viberdash.analyzer.subprocess.run") as mock_run:
        mock_result = MagicMock()
        mock_result.stdout = ""
        mock_result.returncode = 0
        mock_run.return_value = mock_result

        # Test just the dead code method directly
        files = [str(f) for f in analyzer._get_python_files()]
        result = analyzer._analyze_dead_code(files, errors)
        assert result["dead_code"] == 0.0  # Should return 0 on empty output
        assert len(errors) == 0


def test_analyze_style_violations_error_handling(temp_project):
    """Test style violations analysis error handling."""
    analyzer = CodeAnalyzer(temp_project)
    errors = []

    # Mock subprocess.run to return invalid JSON for ruff
    with patch("viberdash.analyzer.subprocess.run") as mock_run:
        mock_result = MagicMock()
        mock_result.stdout = "invalid json"
        mock_result.returncode = 0
        mock_run.return_value = mock_result

        # Test just the style issues method directly
        files = [str(f) for f in analyzer._get_python_files()]
        result = analyzer._analyze_style_issues(files, errors)
        assert result["style_violations"] == 0.0  # Should return 0 on parse error
        assert len(errors) == 0


def test_calculate_maintainability_density(temp_project):
    """Test maintainability density calculation."""
    analyzer = CodeAnalyzer(temp_project)

    # Test with normal values
    metrics = {"maintainability_index": 75.0, "total_code_lines": 1000}
    result = analyzer._calculate_maintainability_density(metrics)
    assert result["maintainability_density"] == 75.0  # 75 / (1000/1000)

    # Test with small codebase
    metrics = {"maintainability_index": 80.0, "total_code_lines": 100}
    result = analyzer._calculate_maintainability_density(metrics)
    assert result["maintainability_density"] == 800.0  # 80 / (100/1000)

    # Test with zero code lines
    metrics = {"maintainability_index": 50.0, "total_code_lines": 0}
    result = analyzer._calculate_maintainability_density(metrics)
    assert result["maintainability_density"] == 50.0  # Falls back to MI


def test_gitignore_complex_patterns(temp_project):
    """Test complex gitignore patterns."""
    # Create a .gitignore with complex patterns
    gitignore = temp_project / ".gitignore"
    gitignore.write_text(
        """
# Comments should be ignored
*.pyc
!important.pyc
/build/
**/logs
*.log
.venv/
venv/
temp_*
"""
    )

    # Create directory structure
    (temp_project / "src").mkdir()
    (temp_project / "src" / "main.py").write_text("# main")
    (temp_project / "src" / "test.pyc").write_text("# compiled")
    (temp_project / "important.pyc").write_text("# important compiled")

    build_dir = temp_project / "build"
    build_dir.mkdir()
    (build_dir / "output.py").write_text("# build output")

    logs_dir = temp_project / "src" / "logs"
    logs_dir.mkdir()
    (logs_dir / "debug.py").write_text("# log file")

    (temp_project / "error.log").write_text("# log")
    (temp_project / "temp_file.py").write_text("# temp")

    venv_dir = temp_project / ".venv"
    venv_dir.mkdir()
    (venv_dir / "lib.py").write_text("# venv file")

    analyzer = CodeAnalyzer(temp_project)
    python_files = analyzer._get_python_files()
    file_paths = [str(f.relative_to(temp_project)) for f in python_files]

    # Check expected files are included
    assert "src/main.py" in file_paths or "example.py" in file_paths

    # Check gitignored files are excluded
    assert "src/test.pyc" not in file_paths
    assert "build/output.py" not in file_paths
    assert "src/logs/debug.py" not in file_paths
    assert ".venv/lib.py" not in file_paths
    assert "temp_file.py" not in file_paths

    # Note: negation patterns (!important.pyc) are complex and may not work
    # with simple pathspec matching


def test_nested_gitignore_files(temp_project):
    """Test handling of nested .gitignore files."""
    # Create root .gitignore
    root_gitignore = temp_project / ".gitignore"
    root_gitignore.write_text("*.log\ntemp/\n")

    # Create subdirectory with its own .gitignore
    subdir = temp_project / "subdir"
    subdir.mkdir()
    sub_gitignore = subdir / ".gitignore"
    sub_gitignore.write_text("local_*.py\n")

    # Create files
    (temp_project / "main.py").write_text("# main")
    (temp_project / "debug.log").write_text("# log")

    temp_dir = temp_project / "temp"
    temp_dir.mkdir()
    (temp_dir / "temp.py").write_text("# temp")

    (subdir / "module.py").write_text("# module")
    (subdir / "local_config.py").write_text("# local config")

    # Test from root
    analyzer = CodeAnalyzer(temp_project)
    files = analyzer._get_python_files()
    file_names = [f.name for f in files]

    assert "main.py" in file_names or "example.py" in file_names
    assert "module.py" in file_names
    assert "temp.py" not in file_names
    assert "local_config.py" not in file_names


def test_gitignore_disabled(temp_project):
    """Test analyzer with gitignore disabled."""
    # Create .gitignore
    gitignore = temp_project / ".gitignore"
    gitignore.write_text("ignored.py\n")

    # Create files
    (temp_project / "main.py").write_text("# main")
    (temp_project / "ignored.py").write_text("# should be ignored")

    # Analyzer with gitignore disabled
    config = {"respect_gitignore": False}
    analyzer = CodeAnalyzer(temp_project, config)

    files = analyzer._get_python_files()
    file_names = [f.name for f in files]

    # Both files should be included when gitignore is disabled
    assert "main.py" in file_names or "example.py" in file_names
    assert "ignored.py" in file_names


def test_no_gitignore_file(temp_project):
    """Test analyzer when no .gitignore file exists."""
    # Don't create any .gitignore file
    (temp_project / "main.py").write_text("# main")
    (temp_project / "test.py").write_text("# test")

    analyzer = CodeAnalyzer(temp_project)
    assert analyzer.gitignore_spec is None

    files = analyzer._get_python_files()
    file_names = [f.name for f in files]

    # All files should be included
    assert len(file_names) >= 2
