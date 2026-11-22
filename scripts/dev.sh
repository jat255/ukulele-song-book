#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."
compose=(docker compose -p tab-app-songbook -f compose.yaml -f compose.dev.yaml)

case "${1:-start}" in
  start)
    if [[ ! -d node_modules ]]; then
      npm ci
    fi
    "${compose[@]}" up -d --no-build
    printf '\nSongbook development: http://127.0.0.1:5173\n'
    printf 'Press Ctrl+C to stop Vite; the API and worker remain running.\n\n'
    exec npm run dev
    ;;
  restart-worker)
    "${compose[@]}" restart worker
    ;;
  *)
    printf 'Usage: %s [start|restart-worker]\n' "$0" >&2
    exit 2
    ;;
esac
