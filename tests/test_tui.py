"""
Tests for the TUI module.
"""

from viberdash.tui import DashboardUI


def test_dashboard_ui_init():
    """Test DashboardUI initialization."""
    ui = DashboardUI()
    assert ui.thresholds is not None
    assert "cyclomatic_complexity" in ui.thresholds


def test_dashboard_ui_custom_thresholds():
    """Test DashboardUI with custom thresholds."""
    custom_thresholds = {"cyclomatic_complexity": {"good": 3.0, "bad": 8.0}}
    ui = DashboardUI(thresholds=custom_thresholds)
    assert ui.thresholds["cyclomatic_complexity"]["good"] == 3.0


def test_get_status():
    """Test status determination based on thresholds."""
    ui = DashboardUI()

    # Test lower_is_better metric (complexity)
    status, color = ui._get_status(3.0, "cyclomatic_complexity", lower_is_better=True)
    assert status == "✓ Good"
    assert color == "green"

    status, color = ui._get_status(15.0, "cyclomatic_complexity", lower_is_better=True)
    assert status == "✗ Bad"
    assert color == "red"

    # Test higher_is_better metric (coverage)
    status, color = ui._get_status(90.0, "test_coverage", lower_is_better=False)
    assert status == "✓ Good"
    assert color == "green"


def test_format_delta():
    """Test delta formatting."""
    ui = DashboardUI()

    # Test improvement (lower is better)
    delta = ui._format_delta(4.0, 5.0, lower_is_better=True)
    assert "↓" in delta
    assert "green" in delta

    # Test deterioration (lower is better)
    delta = ui._format_delta(6.0, 5.0, lower_is_better=True)
    assert "↑" in delta
    assert "red" in delta

    # Test no previous value
    delta = ui._format_delta(5.0, None, lower_is_better=True)
    assert delta == "-"


def test_create_sparkline():
    """Test sparkline creation."""
    ui = DashboardUI()

    # Test with valid data (quality scores where 1.0 is good, 0.0 is bad)
    # The function inverts these, so 1.0 becomes low bar, 0.0 becomes high bar
    data = [0.0, 0.25, 0.5, 0.75, 1.0]
    sparkline = ui._create_sparkline(data)
    assert len(sparkline) == 5
    assert sparkline[0] == "█"  # 0.0 inverted to 1.0 = highest bar
    assert sparkline[-1] == "▁"  # 1.0 inverted to 0.0 = lowest bar

    # Test with empty data
    sparkline = ui._create_sparkline([])
    assert sparkline == ""

    # Test with single value
    sparkline = ui._create_sparkline([5.0])
    assert sparkline == ""

    # Test with constant values
    sparkline = ui._create_sparkline([0.5, 0.5, 0.5])
    assert len(sparkline) == 3


def test_convert_to_quality_scores():
    """Test converting values to quality scores."""
    ui = DashboardUI()
    
    # Test lower_is_better metric
    values = [3.0, 7.0, 12.0]  # good, middle, bad for cyclomatic complexity
    scores = ui._convert_to_quality_scores(values, "cyclomatic_complexity", lower_is_better=True)
    assert scores[0] == 1.0  # 3.0 is good (below threshold)
    assert 0 < scores[1] < 1  # 7.0 is in the middle
    assert scores[2] == 0.0  # 12.0 is bad (above threshold)
    
    # Test higher_is_better metric
    values = [95.0, 75.0, 50.0]  # good, middle, bad for test coverage
    scores = ui._convert_to_quality_scores(values, "test_coverage", lower_is_better=False)
    assert scores[0] == 1.0  # 95% is good
    assert 0 < scores[1] < 1  # 75% is in the middle
    assert scores[2] == 0.0  # 50% is bad
    
    # Test empty values
    scores = ui._convert_to_quality_scores([], "test_coverage", lower_is_better=False)
    assert scores == []


def test_format_int_delta():
    """Test integer delta formatting."""
    ui = DashboardUI()
    
    # Test increase
    delta = ui._format_int_delta(10, 8)
    assert "↑" in delta
    assert "2" in delta
    
    # Test decrease
    delta = ui._format_int_delta(8, 10)
    assert "↓" in delta
    assert "2" in delta
    
    # Test no change
    delta = ui._format_int_delta(10, 10)
    assert "→ 0" in delta
    
    # Test no previous value
    delta = ui._format_int_delta(10, None)
    assert delta == "-"


def test_display_dashboard(capsys):
    """Test dashboard display."""
    from unittest.mock import MagicMock
    
    ui = DashboardUI()
    
    # Mock console to prevent actual output
    ui.console = MagicMock()
    
    # Test data
    latest = {
        "avg_complexity": 5.0,
        "max_complexity": 10.0,
        "maintainability_index": 75.0,
        "test_coverage": 85.0,
        "code_duplication": 3.0,
        "dead_code": 2.0,
        "style_violations": 1.0,
        "total_functions": 50,
        "total_classes": 10,
        "total_lines": 1000,
        "timestamp": "2023-07-05 10:00:00"
    }
    
    history = [latest]
    
    # Should not raise exception
    ui.display_dashboard(latest, history)
    
    # Verify console methods were called
    assert ui.console.clear.called
    assert ui.console.print.called


def test_show_scanning(capsys):
    """Test scanning status display."""
    from unittest.mock import MagicMock
    from rich.panel import Panel
    
    ui = DashboardUI()
    
    # Mock console
    ui.console = MagicMock()
    
    ui.show_scanning()
    
    # Verify print was called with a Panel
    ui.console.print.assert_called_once()
    call_args = ui.console.print.call_args[0][0]
    assert isinstance(call_args, Panel)


def test_create_footer():
    """Test footer creation."""
    ui = DashboardUI()
    
    footer = ui._create_footer()
    
    # Footer should be a Panel
    from rich.panel import Panel
    assert isinstance(footer, Panel)
