"""Code analysis engine that runs various tools and collects metrics."""

import fnmatch
import json
import logging
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any

import pathspec

logger = logging.getLogger(__name__)


class CodeAnalyzer:
    """Runs code analysis tools and collects metrics."""

    def __init__(self, source_dir: Path, config: dict[str, Any] | None = None):
        """Initialize analyzer with source directory and configuration."""
        self.source_dir = Path(source_dir).resolve()
        if not self.source_dir.exists():
            raise ValueError(f"Source directory does not exist: {self.source_dir}")

        self.config = config or {}
        self.exclude_patterns = self.config.get("exclude_patterns", [])
        self.respect_gitignore = self.config.get("respect_gitignore", True)

        # Create pathspec for gitignore patterns if requested
        self.gitignore_spec: pathspec.PathSpec | None = None
        if self.respect_gitignore:
            self._load_gitignore_patterns()

    def _load_gitignore_patterns(self) -> None:
        """Load patterns from .gitignore file if it exists."""
        # Collect all gitignore patterns from repo root to source dir
        # Note: This doesn't perfectly replicate git's behavior
        gitignore_patterns = []

        # Find all .gitignore files from source_dir up to repository root
        gitignore_files = self._find_gitignore_files()

        for gitignore_path in gitignore_files:
            try:
                with open(gitignore_path, encoding="utf-8") as f:
                    # For subdirectory .gitignore files, we need to adjust patterns
                    # to be relative to the source directory
                    base_dir = gitignore_path.parent
                    for line in f:
                        line = line.strip()
                        if line and not line.startswith("#"):
                            if base_dir != self.source_dir:
                                # Adjust pattern to be relative to source_dir
                                try:
                                    rel_dir = base_dir.relative_to(self.source_dir)
                                    # Prepend the relative directory path
                                    if line.startswith("/"):
                                        # Absolute path in gitignore
                                        adjusted = str(rel_dir / line[1:])
                                    else:
                                        # Relative pattern - applies to subdirs
                                        adjusted = str(rel_dir / line)
                                    gitignore_patterns.append(adjusted + "\n")
                                except ValueError:
                                    # If base_dir is not under source_dir, use as-is
                                    gitignore_patterns.append(line + "\n")
                            else:
                                gitignore_patterns.append(line + "\n")
            except Exception as e:
                logger.debug(f"Could not load .gitignore from {gitignore_path}: {e}")

        if gitignore_patterns:
            # Create PathSpec from all collected patterns
            self.gitignore_spec = pathspec.PathSpec.from_lines(
                "gitwildmatch", gitignore_patterns
            )

    def _find_gitignore_files(self) -> list[Path]:
        """Find all .gitignore files from source directory up to repository root."""
        gitignore_files = []

        # First, find the repository root (where .git directory is)
        repo_root = self._find_repo_root()
        if not repo_root:
            # If no repo root found, just check source directory
            gitignore = self.source_dir / ".gitignore"
            if gitignore.exists():
                gitignore_files.append(gitignore)
            # Also check for gitignore files in subdirectories
            for gitignore in self.source_dir.rglob(".gitignore"):
                if gitignore not in gitignore_files:
                    gitignore_files.append(gitignore)
            return gitignore_files

        # Collect .gitignore files from repo root down to source directory
        current = self.source_dir
        while True:
            gitignore = current / ".gitignore"
            if gitignore.exists():
                gitignore_files.append(gitignore)

            if current == repo_root:
                break

            parent = current.parent
            if parent == current:  # Reached filesystem root
                break
            current = parent

        # Also find .gitignore files in subdirectories of source_dir
        for gitignore in self.source_dir.rglob(".gitignore"):
            if gitignore not in gitignore_files:
                gitignore_files.append(gitignore)

        # Return in order from repo root to source directory, then subdirectories
        return list(reversed(gitignore_files))

    def _find_repo_root(self) -> Path | None:
        """Find the repository root by looking for .git directory."""
        current = self.source_dir
        while True:
            if (current / ".git").exists():
                return current

            parent = current.parent
            if parent == current:  # Reached filesystem root
                return None
            current = parent

    def _should_exclude_path(self, path: Path) -> bool:
        """Check if a path should be excluded based on patterns."""
        # Convert to relative path from source_dir for pattern matching
        try:
            rel_path = path.relative_to(self.source_dir)
        except ValueError:
            # Path is not under source_dir
            return True

        path_str = str(rel_path)
        path_parts = path_str.split("/")

        # Check against exclude patterns
        for pattern in self.exclude_patterns:
            # Check if any part of the path matches the pattern
            for part in path_parts:
                if fnmatch.fnmatch(part, pattern):
                    return True
            # Also check the full path
            if fnmatch.fnmatch(path_str, pattern):
                return True

        # Check against gitignore patterns using pathspec
        if self.respect_gitignore and self.gitignore_spec:
            # For gitignore, we need to check from the perspective of the repo root
            repo_root = self._find_repo_root()
            if repo_root:
                try:
                    # Get path relative to repo root for gitignore matching
                    repo_rel_path = path.relative_to(repo_root)
                    if self.gitignore_spec.match_file(str(repo_rel_path)):
                        return True
                except ValueError:
                    # Path is not under repo root, use source-relative path
                    if self.gitignore_spec.match_file(path_str):
                        return True
            else:
                # No repo root, use source-relative path
                if self.gitignore_spec.match_file(path_str):
                    return True

        return False

    def _get_python_files(self) -> list[Path]:
        """Get all Python files that should be analyzed (after filtering)."""
        all_files = list(self.source_dir.rglob("*.py"))
        return [f for f in all_files if not self._should_exclude_path(f)]

    def _create_exclude_args(self, tool_name: str) -> list[str]:
        """Create exclusion arguments for different tools."""
        exclude_args = []

        # Combine exclude patterns with gitignore patterns
        all_patterns = list(self.exclude_patterns)

        # Add gitignore patterns if available
        if self.respect_gitignore and self.gitignore_spec:
            # Extract patterns from pathspec (these are already in gitignore format)
            # We'll add common gitignore patterns that tools understand
            common_gitignore_patterns = [
                ".git",
                ".venv",
                "venv",
                "__pycache__",
                "*.pyc",
                ".mypy_cache",
                ".pytest_cache",
                ".coverage",
                "*.egg-info",
                "build",
                "dist",
                "node_modules",
            ]
            all_patterns.extend(common_gitignore_patterns)

        # Remove duplicates while preserving order
        all_patterns = list(dict.fromkeys(all_patterns))

        if tool_name in ["radon", "vulture"]:
            # These tools support --exclude parameter
            if all_patterns:
                exclude_args.extend(["--exclude", ",".join(all_patterns)])

        elif tool_name == "ruff" and all_patterns:
            # Ruff uses --extend-exclude
            # Ruff expects patterns separated by commas
            exclude_args.extend(["--extend-exclude", ",".join(all_patterns)])

        return exclude_args

    def run_analysis(self) -> dict[str, Any]:
        """Run all analysis tools and return aggregated metrics.

        Returns:
            Dictionary containing all collected metrics

        """
        metrics = {}

        # Run each analysis tool
        metrics.update(self._analyze_complexity())
        metrics.update(self._analyze_maintainability())
        metrics.update(self._analyze_duplication())
        metrics.update(self._analyze_coverage())
        metrics.update(self._analyze_dead_code())
        metrics.update(self._analyze_style_issues())
        metrics.update(self._analyze_documentation())
        metrics.update(self._count_code_elements())

        # Calculate maintainability density
        metrics.update(self._calculate_maintainability_density(metrics))

        return metrics

    def _run_tool(
        self, cmd: list[str], timeout: int = 60
    ) -> subprocess.CompletedProcess:
        """Run a subprocess command with standard settings.

        Args:
            cmd: Command to run as list of strings
            timeout: Timeout in seconds

        Returns:
            Completed process result
        """
        return subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            check=False,
            timeout=timeout,
        )

    def _parse_json_output(self, output: str, default: Any = None) -> Any:
        """Parse JSON output safely.

        Args:
            output: JSON string to parse
            default: Default value if parsing fails

        Returns:
            Parsed JSON or default value
        """
        try:
            return json.loads(output) if output else default
        except json.JSONDecodeError:
            return default

    def _calculate_percentage(self, count: int, total: int) -> float:
        """Calculate percentage safely.

        Args:
            count: Number of items
            total: Total items

        Returns:
            Percentage (0-100)
        """
        if total <= 0:
            return 0.0
        return min((count / total) * 100, 100.0)

    def _analyze_complexity(self) -> dict[str, float]:
        """Analyze cyclomatic complexity using radon."""
        try:
            cmd = [
                sys.executable,
                "-m",
                "radon",
                "cc",
                str(self.source_dir),
                "-j",
                "-a",
            ]
            cmd.extend(self._create_exclude_args("radon"))
            result = self._run_tool(cmd)

            if result.returncode != 0:
                return self._default_complexity_metrics()

            data = self._parse_json_output(result.stdout, {})
            if not data:
                return self._default_complexity_metrics()

            return self._calculate_complexity_stats(data)

        except Exception as e:
            logger.debug(f"Error analyzing complexity: {e}")
            return self._default_complexity_metrics()

    def _default_complexity_metrics(self) -> dict[str, float]:
        """Return default complexity metrics."""
        return {"avg_complexity": 0.0, "max_complexity": 0.0, "total_functions": 0}

    def _calculate_complexity_stats(self, data: dict) -> dict[str, float]:
        """Calculate complexity statistics from radon output."""
        complexities = self._extract_complexities(data)

        if not complexities:
            return self._default_complexity_metrics()

        return {
            "avg_complexity": sum(complexities) / len(complexities),
            "max_complexity": max(complexities),
            "total_functions": len(complexities),
        }

    def _extract_complexities(self, data: dict) -> list[int]:
        """Extract complexity values from radon output.

        Args:
            data: JSON data from radon cc command

        Returns:
            List of complexity values

        """
        complexities = []
        for _file_path, file_data in data.items():
            for item in file_data:
                if isinstance(item, dict) and "complexity" in item:
                    complexities.append(item["complexity"])
        return complexities

    def _analyze_maintainability(self) -> dict[str, float]:
        """Analyze maintainability index using radon."""
        try:
            cmd = [sys.executable, "-m", "radon", "mi", str(self.source_dir), "-j"]
            cmd.extend(self._create_exclude_args("radon"))
            result = self._run_tool(cmd)

            if result.returncode != 0:
                return {"maintainability_index": 0.0}

            data = self._parse_json_output(result.stdout, {})
            return self._calculate_avg_maintainability(data)

        except Exception as e:
            logger.debug(f"Error analyzing maintainability: {e}")
            return {"maintainability_index": 0.0}

    def _calculate_avg_maintainability(self, data: dict) -> dict[str, float]:
        """Calculate average maintainability index from radon output."""
        mi_values = [
            file_data["mi"]
            for file_data in data.values()
            if isinstance(file_data, dict) and "mi" in file_data
        ]

        if mi_values:
            return {"maintainability_index": sum(mi_values) / len(mi_values)}
        return {"maintainability_index": 0.0}

    def _analyze_duplication(self) -> dict[str, float]:
        """Analyze code duplication using pylint."""
        try:
            pylintrc_path = self._create_duplication_pylintrc()

            try:
                result = self._run_pylint_duplication(pylintrc_path)

                if result.stdout:
                    messages = self._parse_json_output(result.stdout, [])
                    return self._calculate_duplication_metrics(messages)

                return {"code_duplication": 0.0}

            finally:
                Path(pylintrc_path).unlink(missing_ok=True)

        except Exception as e:
            logger.debug(f"Error analyzing duplication: {e}")
            return {"code_duplication": 0.0}

    def _create_duplication_pylintrc(self) -> str:
        """Create temporary pylintrc for duplication checking."""
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".pylintrc", delete=False
        ) as f:
            # Build ignore patterns for pylint
            ignore_patterns = list(self.exclude_patterns)

            # Add common gitignore patterns if gitignore is respected
            if self.respect_gitignore and self.gitignore_spec:
                common_gitignore_patterns = [
                    ".git",
                    ".venv",
                    "venv",
                    "__pycache__",
                    "*.pyc",
                    ".mypy_cache",
                    ".pytest_cache",
                    ".coverage",
                    "*.egg-info",
                    "build",
                    "dist",
                    "node_modules",
                ]
                ignore_patterns.extend(common_gitignore_patterns)

            # Remove duplicates while preserving order
            ignore_patterns = list(dict.fromkeys(ignore_patterns))

            pylintrc_content = """[MESSAGES CONTROL]
disable=all
enable=duplicate-code

[REPORTS]
output-format=json
"""

            if ignore_patterns:
                pylintrc_content += (
                    f"\n[MASTER]\nignore-patterns={','.join(ignore_patterns)}\n"
                )

            f.write(pylintrc_content)
            return f.name

    def _run_pylint_duplication(
        self, pylintrc_path: str
    ) -> subprocess.CompletedProcess:
        """Run pylint for duplication analysis."""
        cmd = [
            sys.executable,
            "-m",
            "pylint",
            str(self.source_dir),
            f"--rcfile={pylintrc_path}",
            "--output-format=json",
        ]
        return self._run_tool(cmd)

    def _calculate_duplication_metrics(self, messages: list) -> dict[str, float]:
        """Calculate duplication percentage from pylint messages."""
        duplicate_count = sum(
            1 for msg in messages if msg.get("symbol") == "duplicate-code"
        )

        if duplicate_count == 0:
            return {"code_duplication": 0.0}

        total_lines = self._count_lines()
        # Each duplicate typically affects ~4-5 lines
        duplication_percentage = self._calculate_percentage(
            duplicate_count * 5, total_lines
        )
        return {"code_duplication": duplication_percentage}

    def _analyze_coverage(self) -> dict[str, float]:
        """Analyze test coverage by running tests."""
        try:
            test_dir, project_root = self._find_test_directory()
            if not test_dir or not project_root:
                logger.debug("No test directory found or coverage analysis failed")
                return {"test_coverage": 0.0}

            coverage = self._run_and_parse_coverage(test_dir, project_root)
            return {"test_coverage": coverage}

        except subprocess.TimeoutExpired:
            logger.info("Coverage analysis timed out (tests took too long)")
            return {"test_coverage": 0.0}
        except Exception as e:
            logger.debug(f"Error analyzing coverage: {e}")
            return {"test_coverage": 0.0}

    def _run_and_parse_coverage(self, test_dir: Path, project_root: Path) -> float:
        """Run pytest with coverage and parse the result."""
        module_name = self.source_dir.name
        logger.info(f"Running coverage analysis for {module_name}...")

        result = self._run_pytest_coverage(test_dir, project_root, module_name)
        coverage = self._parse_coverage_output(result.stdout)

        if coverage is not None:
            logger.info(f"Test coverage: {coverage:.1f}%")
            return coverage

        # Check if tests ran but couldn't parse coverage
        if "failed" in result.stdout or "passed" in result.stdout:
            logger.debug("Tests ran but couldn't parse coverage")
        else:
            logger.debug("No tests found or pytest failed to run")

        return 0.0

    def _analyze_dead_code(self) -> dict[str, float]:
        """Analyze dead code using vulture."""
        try:
            result = self._run_vulture()

            if not result.stdout.strip():
                return {"dead_code": 0.0}

            dead_code_count = self._count_vulture_findings(result.stdout)
            total_elements = max(1, self._count_pattern(r"^\s*(def|class)\s+\w+"))

            dead_code_percentage = (dead_code_count / total_elements) * 100
            return {"dead_code": min(dead_code_percentage, 100.0)}

        except Exception as e:
            logger.debug(f"Error analyzing dead code: {e}")
            return {"dead_code": 0.0}

    def _run_vulture(self) -> subprocess.CompletedProcess:
        """Run vulture to find dead code.

        Returns:
            Completed process result from vulture run

        """
        whitelist_path = self.source_dir.parent / ".vulture_whitelist"
        cmd = [sys.executable, "-m", "vulture", str(self.source_dir)]

        if whitelist_path.exists():
            cmd.append(str(whitelist_path))

        cmd.extend(self._create_exclude_args("vulture"))

        return self._run_tool(cmd)

    def _count_vulture_findings(self, output: str) -> int:
        """Count the number of dead code items from vulture output.

        Args:
            output: The stdout from vulture run

        Returns:
            Number of dead code items found

        """
        count = 0
        for line in output.strip().split("\n"):
            if line and ":" in line:
                count += 1
        return count

    def _analyze_style_issues(self) -> dict[str, float | int]:
        """Analyze code style issues using ruff."""
        try:
            violations = self._run_ruff_check()
            total_issues = len(violations)

            total_lines = self._count_lines()
            style_percentage = self._calculate_percentage(total_issues, total_lines)

            return {
                "style_issues": total_issues,
                "style_violations": style_percentage,
            }

        except Exception as e:
            logger.debug(f"Error analyzing style issues: {e}")
            return {"style_issues": 0, "style_violations": 0.0}

    def _run_ruff_check(self, select: str | None = None) -> list:
        """Run ruff and return violations."""
        cmd = [
            sys.executable,
            "-m",
            "ruff",
            "check",
            "--output-format=json",
            str(self.source_dir),
        ]

        if select:
            cmd.extend(["--select", select])

        # Add exclusions
        cmd.extend(self._create_exclude_args("ruff"))

        result = self._run_tool(cmd)
        violations = self._parse_json_output(result.stdout, [])
        return violations if isinstance(violations, list) else []

    def _analyze_documentation(self) -> dict[str, float]:
        """Analyze documentation coverage using Ruff docstring checks."""
        try:
            violations = self._run_ruff_check(select="D")
            total_doc_issues = len(violations)

            total_elements = self._count_pattern(r"^\s*(def|class)\s+\w+")
            doc_coverage = self._calculate_doc_coverage(
                total_doc_issues, total_elements
            )

            return {
                "doc_issues": total_doc_issues,
                "doc_coverage": doc_coverage,
            }

        except Exception as e:
            logger.debug(f"Error analyzing documentation: {e}")
            return {"doc_issues": 0, "doc_coverage": 100.0}

    def _calculate_doc_coverage(self, issues: int, elements: int) -> float:
        """Calculate documentation coverage percentage."""
        if elements <= 0:
            return 100.0
        # Higher issues = lower coverage
        return max(0, 100 - (issues / elements * 100))

    def _count_code_elements(self) -> dict[str, int]:
        """Count lines, classes, and functions in the codebase."""
        try:
            line_counts = self._get_line_counts_from_radon()
            total_classes = self._count_pattern(r"^class\s+\w+")

            return {
                "total_lines": line_counts["total_lines"],
                "total_code_lines": line_counts["total_code_lines"],
                "total_classes": total_classes,
            }

        except Exception as e:
            logger.debug(f"Error counting code elements: {e}")
            return {"total_lines": 0, "total_code_lines": 0, "total_classes": 0}

    def _get_line_counts_from_radon(self) -> dict[str, int]:
        """Get line counts using radon raw metrics."""
        cmd = [sys.executable, "-m", "radon", "raw", str(self.source_dir), "-j"]
        cmd.extend(self._create_exclude_args("radon"))
        result = self._run_tool(cmd)

        if result.returncode != 0:
            return {"total_lines": 0, "total_code_lines": 0}

        data = self._parse_json_output(result.stdout, {})

        total_lines = 0
        total_code_lines = 0

        for file_data in data.values():
            if isinstance(file_data, dict):
                total_lines += file_data.get("loc", 0)
                total_code_lines += file_data.get("sloc", 0)

        return {"total_lines": total_lines, "total_code_lines": total_code_lines}

    def _calculate_maintainability_density(
        self, metrics: dict[str, Any]
    ) -> dict[str, float]:
        """Calculate maintainability density (MI per 1000 lines of code).

        Args:
            metrics: Dictionary containing maintainability_index and total_code_lines

        Returns:
            Dictionary with maintainability_density metric
        """
        mi = metrics.get("maintainability_index", 0.0)
        code_lines = metrics.get("total_code_lines", 0)

        if code_lines <= 0:
            # No code or very small codebase - use MI directly
            return {"maintainability_density": mi}

        # Calculate density: MI per 1000 lines of code
        # This normalizes MI by code size
        density = mi / (code_lines / 1000.0)
        return {"maintainability_density": density}

    def _count_lines(self) -> int:
        """Count total lines in Python files."""
        total = 0
        for py_file in self._get_python_files():
            try:
                with open(py_file, encoding="utf-8") as f:
                    total += len(f.readlines())
            except Exception:
                pass
        return total

    def _count_pattern(self, pattern: str) -> int:
        """Count occurrences of a pattern in Python files."""
        import re

        regex = re.compile(pattern, re.MULTILINE)
        count = 0

        for py_file in self._get_python_files():
            try:
                with open(py_file, encoding="utf-8") as f:
                    content = f.read()
                    count += len(regex.findall(content))
            except Exception:
                pass

        return count

    def _find_test_directory(self) -> tuple[Path | None, Path | None]:
        """Find the test directory by searching up from source_dir.

        Returns:
            Tuple of (test_dir, project_root) or (None, None) if not found

        """
        current = self.source_dir
        search_depth = 5  # Limit search depth

        for _ in range(search_depth):
            potential_test_dir = current / "tests"
            if potential_test_dir.exists() and potential_test_dir.is_dir():
                return potential_test_dir, current

            # Stop if we've reached the root
            if current.parent == current:
                break
            current = current.parent

        return None, None

    def _run_pytest_coverage(
        self, test_dir: Path, project_root: Path, module_name: str
    ) -> subprocess.CompletedProcess:
        """Run pytest with coverage for the specified module.

        Args:
            test_dir: Path to tests directory
            project_root: Project root directory
            module_name: Name of module to measure coverage for

        Returns:
            Completed process result from pytest run

        """
        return subprocess.run(
            [
                sys.executable,
                "-m",
                "pytest",
                "tests",  # Use relative path from project root
                f"--cov={module_name}",
                "--cov-report=term",
                "--no-header",
                "--tb=no",
                "-q",
            ],
            capture_output=True,
            text=True,
            check=False,
            cwd=project_root,
            timeout=120,  # 2 minute timeout
        )

    def _parse_coverage_output(self, output: str) -> float | None:
        """Parse coverage percentage from pytest terminal output.

        Args:
            output: The stdout from pytest coverage run

        Returns:
            Coverage percentage or None if parsing failed

        """
        for line in output.split("\n"):
            if line.strip().startswith("TOTAL"):
                # Line format: "TOTAL    454    36    92%"
                parts = line.split()
                if len(parts) >= 4 and parts[-1].endswith("%"):
                    try:
                        return float(parts[-1].rstrip("%"))
                    except ValueError:
                        pass
        return None
