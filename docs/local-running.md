# Running the songbook locally

The local Compose setup binds the application to `127.0.0.1:8000`. It runs
one unprivileged API container and one worker using the same image and private
named volume. It is intended for one local operator; it is not a remote
service or a deployment configuration.

```sh
docker compose build
docker compose run --rm api songbook auth set-password
docker compose up -d
docker compose ps
```

Open `http://127.0.0.1:8000`. The password prompt does not echo input. The API
uses a small local TCP relay inside its container to preserve the app's
loopback-only request check; Compose exposes that relay on the host loopback
address. Other containers on the same Docker network can reach it, so do not
attach untrusted containers to that network. The API health check requires a
recent worker heartbeat. For logs use `docker compose logs api worker`; stop
services with `docker compose stop`. Stopping services retains the named volume.

For an optional input directory, set `SONGBOOK_INPUT_DIR` to an absolute path
and add the override file:

```sh
export SONGBOOK_INPUT_DIR=/path/to/read-only-input
docker compose -f compose.yaml -f compose.sources.yaml up -d
```

The source mount is read-only; imported files are copied into managed storage.
The worker needs no access to the input mount. A missing input directory does
not remove already managed originals. For backups and restore see
[backup and restore](backup-restore.md) and [portable exports](portability.md).
Container backups should be written outside `/data`; copy them to protected
operator-controlled storage. To restore, provide an empty new path within a
separately prepared private volume; restore does not merge existing libraries.

The optional vision adapter requires `SONGBOOK_ALLOW_EXTERNAL_AI=true`,
`ANTHROPIC_API_KEY`, and `SONGBOOK_ANTHROPIC_MODEL` in the API and worker
environments. Do not enable it without separately authorizing external
submission and possible charges. PDF extraction remains review-only.

For local development without containers, install Node 22.12+, Python 3.12+,
and uv, then run `uv sync`, `npm ci`, `npm run build`, provision a password
with `uv run songbook auth set-password`, and start `uv run songbook serve`
and `uv run songbook worker` in separate terminals with the same
`SONGBOOK_LIBRARY_ROOT`. `SONGBOOK_WORKER_REQUIRED=true` makes readiness depend
on the worker heartbeat. See the README for test commands.

AI services can also be configured from **Settings → Configure AI conversion**,
including OpenAI-compatible image endpoints. Saved settings override the legacy
Anthropic environment variables for both API and worker. Read [AI conversion](ai-conversion.md)
for key storage, explicit page authorization, synthetic connection testing,
endpoint/model compatibility and archive-restore requirements.
