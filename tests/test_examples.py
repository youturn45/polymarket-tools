"""Tests for example scripts - basic import and structure validation."""


def test_phase2_demo_imports():
    """Test that phase2_demo can be imported without errors."""
    # Just verify the file exists and has valid Python syntax
    from pathlib import Path

    demo_path = Path(__file__).parent.parent / "examples" / "phase2_demo.py"
    assert demo_path.exists(), "phase2_demo.py should exist"

    # Verify it's valid Python by compiling it
    with open(demo_path) as f:
        code = f.read()
        compile(code, str(demo_path), "exec")
