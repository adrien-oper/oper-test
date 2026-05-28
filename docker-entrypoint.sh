#!/usr/bin/env bash
# Container entrypoint, used by every process group (web and worker).
#
# Why migrations run here as well as in the Fly `release_command`:
#   A Fly release Machine does NOT mount the app's persistent volume, so the
#   `release_command` migrate runs against a throwaway database, not the SQLite
#   file on /data. Running migrate on boot too guarantees the schema is applied
#   on the Machine that actually has the volume mounted. `migrate` is idempotent,
#   so running it in both places is safe.
#
# Static files are already collected into the image at build time, so there is
# nothing static-related to do here.
set -euo pipefail

mkdir -p "${MEDIA_ROOT:-/data/media}"

python manage.py migrate --noinput

exec "$@"
