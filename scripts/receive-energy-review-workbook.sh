#!/usr/bin/env bash
# Fixed receiver for this server's existing review deployment.
# Use only after deploying the new backend and applying the delivery overlay.
set -euo pipefail
cd -- "$(dirname -- "$(readlink -f -- "$0")")/.."
exec docker --context desktop-linux compose \
  --env-file .env.review -f compose.review.yaml -f compose.review.public.yaml \
  -f compose.energy-file-delivery.yaml \
  exec -T api python -m app.energy_file_push
