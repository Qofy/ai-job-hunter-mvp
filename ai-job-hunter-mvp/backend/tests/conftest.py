import pytest


@pytest.fixture(autouse=True)
def isolated_local_data(tmp_path, monkeypatch):
    """Never write test accounts/CVs into the desktop user's real application data."""
    monkeypatch.setenv('JOBPILOT_DATA_DIR', str(tmp_path / 'app-data'))
    from app.auth import _attempts
    _attempts.clear()
