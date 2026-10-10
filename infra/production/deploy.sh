#!/usr/bin/env bash
# Run in a clean, committed checkout on the target server. Planned downtime.
set -euo pipefail
root=$(cd "$(dirname "$0")/../.." && pwd)
cd "$root"
if [[ ! -f infra/production/.env ]]; then
  echo 'Missing infra/production/.env; follow docs/deployment/first-server.md.' >&2
  exit 1
fi
if ! git diff --quiet || ! git diff --cached --quiet; then
  echo 'Commit tracked changes before tagging release images.' >&2
  exit 1
fi
export RELEASE_SHA
authoritative_sha=$(git rev-parse HEAD)
RELEASE_SHA=$authoritative_sha
compose=(docker compose --env-file infra/production/.env -f infra/production/compose.yml)
"${compose[@]}" config --quiet
# Build all three images before interrupting traffic. Never prune previous releases.
"${compose[@]}" build frontend backend ai
# Prevent requests during mixed AI/backend policy versions.
"${compose[@]}" stop proxy frontend backend ai
if ! "${compose[@]}" up -d --no-build --wait --wait-timeout 300 postgres redis backend ai frontend; then
  echo 'Readiness failed; public proxy remains stopped. Follow rollback runbook.' >&2
  exit 1
fi
"${compose[@]}" up -d --no-build --wait --wait-timeout 60 proxy
printf 'Internal services ready at release %s. Verify public HTTPS and application flows.\n' "$RELEASE_SHA"
