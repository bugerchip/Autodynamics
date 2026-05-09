"""Smoke tests for the autodynamics package."""

import autodynamics


def test_version_is_pinned() -> None:
    assert autodynamics.__version__ == "0.3.0a0"


def test_package_imports() -> None:
    import autodynamics  # noqa: F401


def test_public_api_is_exposed() -> None:
    assert hasattr(autodynamics, "ProfileTrajectory")
    assert hasattr(autodynamics, "ProfileSnapshot")
    assert hasattr(autodynamics, "ProfileDelta")
    assert hasattr(autodynamics, "CSVTrajectoryAdapter")
    assert hasattr(autodynamics, "BatchTrajectoryAdapter")
