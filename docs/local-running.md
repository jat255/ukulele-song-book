# Running the songbook locally

The local Compose setup binds the application to `127.0.0.1:8000`. It runs
one unprivileged API container and one worker using the same image and private
named volume. It is intended for one local operator; it is not a remote
service or a deployment configuration.

```sh
docker compose build
docker compose up -d
docker compose ps
```

Open `http://127.0.0.1:8000`. The local app opens without a password. The API
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
and uv, then run `uv sync`, `npm ci`, `npm run build`, start `uv run songbook serve`
and `uv run songbook worker` in separate terminals with the same
`SONGBOOK_LIBRARY_ROOT`. `SONGBOOK_WORKER_REQUIRED=true` makes readiness depend
on the worker heartbeat. See the README for test commands.

## Codex subscription and private network access

In Settings, use **Sign in to Codex** and follow the device-code link. The sign-in is managed by Codex, and the selected account's image-capable models are available on Imports. The usage display shows Codex's primary and secondary rate-limit windows when the service provides them; unavailable data is not treated as zero. Choose the model and select Queue PDFs to send the selected files. Each included PDF must be one song and no more than five pages. Jobs run in the existing worker and every result remains a review draft. In the import queue, open **View Codex conversation and logs** to see the prompt, available reasoning summaries, response, lifecycle events, usage and redacted error details; the log can also be copied or downloaded. Logs can contain song content. They retain up to the latest 1,000,000 characters across attempts; the SDK runtime log contains at most its last 400 lines. Logs are excluded from library backups and exports. Per-draft token counts appear when Codex reports them.

The API and worker share a dedicated `codex-data` volume at `/codex`, separate from the library and its archives. Treat this volume as sensitive: it holds the signed-in credentials in Codex's file store. Removing the volume signs out the app. The volume isn't part of portable library exports or operational library backups; restoring a library requires signing in again. Sign out from Settings when the connection is no longer needed.

The worker runs with Docker's default seccomp filter disabled because Codex must create its own Linux user-namespace sandbox. This relaxes a container-level protection for the worker; Codex conversion threads still use a restricted filesystem profile, no network access for tools, and disabled shell and image tools. The API container keeps Docker's default seccomp filter. The host must support unprivileged user namespaces.

The standard Compose configuration remains loopback-only. To use an existing trusted HTTPS reverse proxy on the host, set the exact browser origin (for example, `https://songbook.example.test`) and add the optional override:

```sh
export SONGBOOK_PUBLIC_ORIGIN='https://your-songbook-hostname'
docker compose -f compose.yaml -f compose.lan.yaml up -d --build
```

Configure the trusted reverse proxy to terminate TLS and forward requests to `127.0.0.1:8000`, overwriting `X-Forwarded-Proto` with `https`. The app accepts this one configured origin and uses secure session cookies. Keep port 8000 bound to loopback; do not expose the backend directly. The API and worker use separate Docker networks so the worker cannot reach the API relay. Do not attach untrusted containers to the API network: its loopback relay treats forwarded protocol headers from that network as trusted. Configure DNS, certificate trust, and the reverse proxy separately. This override does not create or publish a hostname or change your network configuration.
