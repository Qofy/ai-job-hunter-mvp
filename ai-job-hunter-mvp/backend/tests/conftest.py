import pytest


@pytest.fixture(autouse=True)
def isolated_local_data(tmp_path, monkeypatch):
    """Never write test accounts/CVs into the desktop user's real application data."""
    monkeypatch.setenv('JOBPILOT_DATA_DIR', str(tmp_path / 'app-data'))
    monkeypatch.setenv('JOBPILOT_AGENT_ENABLED','0')
    monkeypatch.setenv('JOBPILOT_ENABLE_DEMO','1')
    from app.auth import _attempts
    _attempts.clear()
