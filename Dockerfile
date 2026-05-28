# Production image for the borrower portal.
#
# Build strategy:
#   * uv-managed, Python 3.13 (matches .python-version / requires-python).
#   * `uv sync --frozen --no-dev` installs runtime deps ONLY — the dev group
#     (pytest, ruff, ty, and the teatree CLI) is excluded, so teatree never
#     reaches the production image.
#   * `collectstatic` runs at build time; whitenoise serves the compressed,
#     manifest-hashed assets at runtime (no separate static server needed).
#   * Runs as a non-root user.
#   * Migrations run on container start (see docker-entrypoint.sh) because the
#     SQLite database lives on a Fly volume the release Machine cannot mount.

FROM ghcr.io/astral-sh/uv:python3.13-bookworm-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    # Compile to bytecode at install time for faster cold starts.
    UV_COMPILE_BYTECODE=1 \
    # Copy packages into the environment rather than symlinking the cache.
    UV_LINK_MODE=copy \
    # The project's own managed environment lives here.
    UV_PROJECT_ENVIRONMENT=/app/.venv \
    PATH=/app/.venv/bin:$PATH \
    # Production defaults; fly.toml / fly secrets override the rest.
    DJANGO_SETTINGS_MODULE=config.settings \
    DEBUG=False

WORKDIR /app

# Install runtime dependencies first, in their own layer, so they are cached
# across source-only changes. --no-install-project defers the app itself.
RUN --mount=type=cache,target=/root/.cache/uv \
    --mount=type=bind,source=pyproject.toml,target=pyproject.toml \
    --mount=type=bind,source=uv.lock,target=uv.lock \
    uv sync --frozen --no-dev --no-install-project

# Copy the application source and install the project into the environment.
COPY . .
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev

# Collect static assets into STATIC_ROOT at build time. DEBUG=False selects the
# whitenoise CompressedManifestStaticFilesStorage backend. A throwaway SECRET_KEY
# is fine here: collectstatic touches no secrets and the real key is injected at
# runtime via `fly secrets`.
RUN SECRET_KEY=build-time-collectstatic-only python manage.py collectstatic --noinput

# Run as a non-root user. /data is created and chowned so the volume mount
# (and the SQLite file + media written under it) is writable at runtime.
RUN useradd --create-home --uid 1000 appuser \
    && mkdir -p /data \
    && chown -R appuser:appuser /app /data
USER appuser

EXPOSE 8000

ENTRYPOINT ["./docker-entrypoint.sh"]
CMD ["gunicorn", "config.wsgi", "--bind", "0.0.0.0:8000", "--workers", "2", "--timeout", "60", "--access-logfile", "-", "--error-logfile", "-"]
