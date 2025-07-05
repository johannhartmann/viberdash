"""Code analysis engine that runs various tools and collects metrics."""

import json
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any


class CodeAnalyzer:
    """Runs code analysis tools and collects metrics."""

    def __init__(self, source_dir: Path):
        """Initialize analyzer with source directory."""
        self.source_dir = Path(source_dir).resolve()
        if not self.source_dir.exists():
            raise ValueError(f"Source directory does not exist: {self.source_dir}")

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

        return metrics

    def _analyze_complexity(self) -> dict[str, float]:
        """Analyze cyclomatic complexity using radon."""
        try:
            result = subprocess.run(
                [sys.executable, "-m", "radon", "cc", str(self.source_dir), "-j", "-a"],
                capture_output=True,
                text=True,
                check=False,
            )

            if result.returncode != 0:
                return {"avg_complexity": 0.0, "max_complexity": 0.0}

            data = json.loads(result.stdout)
            complexities = self._extract_complexities(data)

            if not complexities:
                return {
                    "avg_complexity": 0.0,
                    "max_complexity": 0.0,
                    "total_functions": 0,
                }

            return {
                "avg_complexity": sum(complexities) / len(complexities),
                "max_complexity": max(complexities),
                "total_functions": len(complexities),
            }

        except Exception as e:
            print(f"Error analyzing complexity: {e}")
            return {"avg_complexity": 0.0, "max_complexity": 0.0, "total_functions": 0}

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
            # Run radon mi with JSON output
            result = subprocess.run(
                [sys.executable, "-m", "radon", "mi", str(self.source_dir), "-j"],
                capture_output=True,
                text=True,
                check=False,
            )

            if result.returncode != 0:
                return {"maintainability_index": 0.0}

            data = json.loads(result.stdout)

            # Calculate average maintainability index
            mi_values = []
            for _file_path, file_data in data.items():
                if isinstance(file_data, dict) and "mi" in file_data:
                    mi_values.append(file_data["mi"])

            if mi_values:
                return {"maintainability_index": sum(mi_values) / len(mi_values)}

            return {"maintainability_index": 0.0}

        except Exception as e:
            print(f"Error analyzing maintainability: {e}")
            return {"maintainability_index": 0.0}

    def _analyze_duplication(self) -> dict[str, float]:
        """Analyze code duplication using pylint."""
        try:
            # Create a minimal pylintrc to only check for duplicates
            with tempfile.NamedTemporaryFile(
                mode="w", suffix=".pylintrc", delete=False
            ) as f:
                f.write(
                    """[MESSAGES CONTROL]
disable=all
enable=duplicate-code

[REPORTS]
output-format=json
"""
                )
                pylintrc_path = f.name

            try:
                # Run pylint with JSON output
                result = subprocess.run(
                    [
                        sys.executable,
                        "-m",
                        "pylint",
                        str(self.source_dir),
                        f"--rcfile={pylintrc_path}",
                        "--output-format=json",
                    ],
                    capture_output=True,
                    text=True,
                    check=False,
                )

                if result.stdout:
                    messages = json.loads(result.stdout)
                    duplicate_count = sum(
                        1 for msg in messages if msg.get("symbol") == "duplicate-code"
                    )

                    # Calculate duplication percentage (rough estimate)
                    total_lines = self._count_lines()
                    if total_lines > 0:
                        # Each duplicate typically affects ~4-5 lines
                        duplication_percentage = (
                            duplicate_count * 5 / total_lines
                        ) * 100
                        return {"code_duplication": min(duplication_percentage, 100.0)}

                return {"code_duplication": 0.0}

            finally:
                # Clean up temporary file
                Path(pylintrc_path).unlink(missing_ok=True)

        except Exception as e:
            print(f"Error analyzing duplication: {e}")
            return {"code_duplication": 0.0}

    def _analyze_coverage(self) -> dict[str, float]:
        """Analyze test coverage by running tests."""
        try:
            # Find test directory
            test_dir, project_root = self._find_test_directory()
            if not test_dir:
                print("No test directory found or coverage analysis failed")
                return {"test_coverage": 0.0}

            # Get module name and run coverage
            module_name = self.source_dir.name
            print(f"Running coverage analysis for {module_name}...")

            result = self._run_pytest_coverage(test_dir, project_root, module_name)

            # Parse coverage from output
            coverage = self._parse_coverage_output(result.stdout)
            if coverage is not None:
                print(f"Test coverage: {coverage:.1f}%")
                return {"test_coverage": coverage}

            # Check if tests ran but couldn't parse coverage
            if "failed" in result.stdout or "passed" in result.stdout:
                print("Tests ran but couldn't parse coverage")
            else:
                print("No tests found or pytest failed to run")

            return {"test_coverage": 0.0}

        except subprocess.TimeoutExpired:
            print("Coverage analysis timed out (tests took too long)")
            return {"test_coverage": 0.0}
        except Exception as e:
            print(f"Error analyzing coverage: {e}")
            return {"test_coverage": 0.0}

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
            print(f"Error analyzing dead code: {e}")
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

        return subprocess.run(cmd, capture_output=True, text=True, check=False)

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

    def _analyze_style_issues(self) -> dict[str, int]:
        """Analyze code style issues using ruff."""
        try:
            # Run ruff with JSON output
            result = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "ruff",
                    "check",
                    str(self.source_dir),
                    "--output-format=json",
                ],
                capture_output=True,
                text=True,
                check=False,
            )

            # Default values
            total_issues = 0

            # Parse JSON output from stdout
            if result.stdout:
                try:
                    # Ruff returns an array of violations
                    violations = json.loads(result.stdout)
                    total_issues = len(violations)
                except json.JSONDecodeError:
                    pass

            # Calculate percentage based on total lines
            total_lines = self._count_lines()
            style_percentage = (
                (total_issues / max(1, total_lines)) * 100 if total_lines > 0 else 0
            )

            return {"style_issues": total_issues, "style_violations": style_percentage}

        except Exception as e:
            print(f"Error analyzing style issues: {e}")
            return {"style_issues": 0, "style_violations": 0.0}

    def _analyze_documentation(self) -> dict[str, float]:
        """Analyze documentation coverage using Ruff docstring checks."""
        try:
            # Run ruff with only docstring rules
            result = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "ruff",
                    "check",
                    "--select=D",  # Only docstring rules
                    "--output-format=json",
                    str(self.source_dir),
                ],
                capture_output=True,
                text=True,
                check=False,
            )

            # Default values
            total_doc_issues = 0

            # Parse JSON output from stdout
            if result.stdout:
                try:
                    # Ruff returns an array of violations
                    violations = json.loads(result.stdout)
                    total_doc_issues = len(violations)
                except json.JSONDecodeError:
                    pass

            # Count total documentable elements (classes, functions, methods)
            # This is an approximation - counts def/class statements
            total_elements = self._count_pattern(r"^\s*(def|class)\s+\w+")

            # Calculate documentation coverage percentage
            # Higher issues = lower coverage
            if total_elements > 0:
                doc_coverage = max(0, 100 - (total_doc_issues / total_elements * 100))
            else:
                doc_coverage = 100.0

            return {
                "doc_issues": total_doc_issues,
                "doc_coverage": doc_coverage,
            }

        except Exception as e:
            print(f"Error analyzing documentation: {e}")
            return {"doc_issues": 0, "doc_coverage": 100.0}

    def _count_code_elements(self) -> dict[str, int]:
        """Count lines, classes, and functions in the codebase."""
        try:
            # Run radon raw for line counts
            result = subprocess.run(
                [sys.executable, "-m", "radon", "raw", str(self.source_dir), "-j"],
                capture_output=True,
                text=True,
                check=False,
            )

            total_lines = 0
            total_code_lines = 0

            if result.returncode == 0:
                data = json.loads(result.stdout)
                for _file_path, file_data in data.items():
                    if isinstance(file_data, dict):
                        total_lines += file_data.get("loc", 0)
                        total_code_lines += file_data.get("sloc", 0)

            # Count classes using grep-like approach
            total_classes = self._count_pattern(r"^class\s+\w+")

            return {
                "total_lines": total_lines,
                "total_code_lines": total_code_lines,
                "total_classes": total_classes,
            }

        except Exception as e:
            print(f"Error counting code elements: {e}")
            return {"total_lines": 0, "total_code_lines": 0, "total_classes": 0}

    def _count_lines(self) -> int:
        """Count total lines in Python files."""
        total = 0
        for py_file in self.source_dir.rglob("*.py"):
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

        for py_file in self.source_dir.rglob("*.py"):
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
