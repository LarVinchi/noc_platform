#!/usr/bin/env bash
# Fixed receiver for this server's existing review deployment.
# Use only after deploying the new backend and applying the delivery overlay.
set -euo pipefail
cd -- "$(dirname -- "$(readlink -f -- "$0")")/.."
exec docker --context desktop-linux exec -i noc-review-api-1 python -m app.energy_file_push
