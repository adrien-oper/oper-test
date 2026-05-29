"""Deploy topology guards for the single-volume SQLite queue.

The task queue is the SQLite database on the Fly volume, and a volume attaches
to exactly one Machine. A separate worker Machine would mount no volume and
poll an empty database, never draining the queue the web Machine fills — which
left uploaded documents stuck forever. These guards pin the co-located layout.
"""

import tomllib
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
_FLY = tomllib.loads((_ROOT / "fly.toml").read_text())
_ENTRYPOINT = (_ROOT / "docker-entrypoint.sh").read_text()


def test_volume_is_mounted_on_a_single_process_group():
    mounts = _FLY["mounts"]
    assert len(mounts) == 1
    assert mounts[0]["processes"] == ["web"]


def test_no_separate_worker_process_group():
    processes = _FLY["processes"]
    assert list(processes) == ["web"]


def test_entrypoint_starts_the_worker_for_the_web_command():
    assert "db_worker" in _ENTRYPOINT
    assert 'if [[ "${1:-}" == "gunicorn" ]]; then' in _ENTRYPOINT
