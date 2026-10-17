#!/usr/bin/env bash
# Fixed authorized_keys command. Configure this wrapper on the Linux host once.
set -euo pipefail
cd -- "$(dirname -- "$(readlink -f -- "$0")")/.."

# Production defaults. For another deployment, edit these fixed values here;
# never take command names, file paths or Compose options from the SSH sender.
exec docker --context default compose \
  --env-file .env.production -f compose.production.example.yaml \
  exec -T api python -m app.energy_file_push
