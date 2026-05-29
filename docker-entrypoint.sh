#!/usr/bin/env bash
# Container entrypoint.
#
# Why migrations run here as well as in the Fly `release_command`:
#   A Fly release Machine does NOT mount the app's persistent volume, so the
#   `release_command` migrate runs against a throwaway database, not the SQLite
#   file on /data. Running migrate on boot too guarantees the schema is applied
#   on the Machine that actually has the volume mounted. `migrate` is idempotent,
#   so running it in both places is safe.
#
# Why the task worker is started here instead of as its own Fly process group:
#   The queue is the SQLite database on the Fly volume, and a volume attaches to
#   exactly one Machine. A separate `worker` Machine would mount no volume and
#   poll an empty database, so it would never see the rows the web Machine
#   enqueues. The worker therefore runs co-located with gunicorn on the single
#   volume-backed web Machine. It is launched only for the web command so a
#   one-off `manage.py` invocation (`fly ssh`, the release Machine) does not
#   spawn one.
#
# Static files are already collected into the image at build time, so there is
# nothing static-related to do here.
set -euo pipefail

mkdir -p "${MEDIA_ROOT:-/data/media}"

python manage.py migrate --noinput

if [[ "${1:-}" == "gunicorn" ]]; then
  python manage.py db_worker --no-startup-delay &
fi

exec "$@"
