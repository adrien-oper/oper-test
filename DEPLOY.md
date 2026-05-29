# Deploying to Fly.io

The borrower portal ships as a single container: gunicorn behind Fly's HTTPS
edge, whitenoise serving the hashed static assets, and SQLite + uploaded media
on a persistent volume. The image is built **remotely** by Fly, so you do not
need a local Docker daemon.

## What runs where

- **App:** one Fly Machine running `gunicorn config.wsgi` on port 8000.
- **Static files:** collected into the image at build time, served by
  whitenoise (compressed, manifest-hashed). No CDN or static server needed.
- **Database + media:** SQLite at `/data/db.sqlite3` and uploads under
  `/data/media`, both on a persistent Fly volume mounted at `/data`.
- **Migrations:** run on container start (`docker-entrypoint.sh`) on the Machine
  that mounts the volume. (`fly.toml` also sets a `release_command` migrate, but
  the release Machine has no volume, so the on-boot run is the effective one.)
- **AI document analysis:** runs **stubbed**. With `ANTHROPIC_API_KEY` unset the
  analyzer returns a deterministic, clearly-labelled result, so the demo incurs
  **no metered API spend**. Do not set the key unless you want live analysis.

## One-time prerequisites

- Install flyctl: `curl -L https://fly.io/install.sh | sh` (or `brew install flyctl`).
- A Fly.io account with a payment card on file (new orgs have no free tier and a
  card is required to deploy at all; running this demo is a few dollars a month —
  see the *Hosting cost* note in [`COST.md`](COST.md)).

## Deploy steps (in order)

### 1. Authenticate — the only manual/interactive step

```bash
fly auth login
```

This opens a browser to sign in (or create) your Fly.io account. Everything
after this is non-interactive.

### 2. Create the app (without deploying yet)

The repo already contains `fly.toml`, so create the app and reuse this config:

```bash
fly apps create borrower-portal-demo
# If that slug is taken, pick another and update `app`, `ALLOWED_HOSTS` and
# `CSRF_TRUSTED_ORIGINS` in fly.toml to the new <app>.fly.dev host first, e.g.:
#   fly apps create borrower-portal-demo-<suffix>
```

(Equivalently: `fly launch --no-deploy --copy-config --name borrower-portal-demo
--region ams`, which scaffolds from the existing `fly.toml` without deploying.)

### 3. Create the persistent volume

```bash
fly volumes create data --region ams --size 1
```

`data` matches `[[mounts]] source` in `fly.toml`; `--size 1` is 1 GB (smallest,
free-tier friendly). Provision it in the same region as the app (`ams`).

### 4. Set the secret key (never commit it)

```bash
fly secrets set SECRET_KEY="$(python3 -c 'import secrets; print(secrets.token_urlsafe(64))')"
```

A startup system check refuses to boot with `DEBUG=False` and the insecure
default key, so this step is mandatory. `ANTHROPIC_API_KEY` is intentionally
**not** set — the analyzer stays in free stub mode.

### 5. Deploy (remote build — no local Docker needed)

```bash
fly deploy --remote-only
```

Fly builds the image on its remote builders from the `Dockerfile`, runs the
release-command migrate, boots the Machine (which mounts the volume, runs
migrate again, and starts gunicorn), and routes HTTPS traffic to it.

### 6. Create the first admin user (optional)

```bash
fly ssh console -C "python manage.py createsuperuser"
```

Then visit `https://borrower-portal-demo.fly.dev/`.

## SQLite + the background worker (important)

A Fly volume attaches to exactly one Machine and SQLite is a single-file,
single-host database. `fly.toml` therefore mounts the volume on the `web`
process only. The durable document-analysis worker (`db_worker`) needs the
**same** SQLite file, so it must run on the **same Machine** as the web server —
running it as its own Fly Machine would give it a separate, empty volume.

For this stubbed-AI demo, keep a single web Machine:

```bash
fly scale count web=1 worker=0
```

If you need a truly separate worker Machine (or multi-region), move the database
off single-host SQLite to **LiteFS** or **Postgres** first; only then is the
`worker` process group safe to scale up.

## Free-tier notes

- `auto_stop_machines`/`auto_start_machines` let the single Machine sleep when
  idle and wake on the next request, keeping it within free-tier usage.
- `shared-cpu-1x` / 512 MB and a 1 GB volume are the small/free-friendly sizes.
- The stubbed AI path means **no Anthropic spend**.

## Updating later

```bash
fly deploy --remote-only
```

The volume (and your SQLite data + uploads) persists across deploys.
