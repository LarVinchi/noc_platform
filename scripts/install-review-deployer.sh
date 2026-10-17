#!/usr/bin/env bash
# Run as steve on the current review server, never as root.
set -euo pipefail
ROOT=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)
if [[ "$ROOT" != '/home/steve/Downloads/noc_platform' || "$(id -un)" != 'steve' ]]; then
  echo 'These units target steve on /home/steve/Downloads/noc_platform; adapt unit paths for another server.' >&2
  exit 1
fi
umask 077
mkdir -p "$ROOT/.review-access/cd" "$HOME/.config/systemd/user"
install -m 700 "$ROOT/scripts/deploy-review-release.py" "$ROOT/.review-access/cd/deploy-review-release.py"
install -m 600 "$ROOT/deploy/systemd/noc-review-deploy.service" "$HOME/.config/systemd/user/noc-review-deploy.service"
install -m 600 "$ROOT/deploy/systemd/noc-review-deploy.timer" "$HOME/.config/systemd/user/noc-review-deploy.timer"
systemctl --user daemon-reload
systemctl --user enable --now noc-review-deploy.timer
systemctl --user start noc-review-deploy.service
systemctl --user list-timers noc-review-deploy.timer --no-pager
