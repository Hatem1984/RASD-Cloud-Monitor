#!/bin/sh
set -eu
cd "$(dirname "$0")"
if [ ! -x .venv/bin/python ]; then
  python3 -m venv .venv
fi
.venv/bin/python -m pip install -q -r requirements-test.txt
printf '%s\n' 'RASD demo: http://127.0.0.1:8765' \
  'Owner email: owner@rasd.demo' \
  'Owner password: RasdLocalDemo!2026' \
  'DEMO ONLY; no production data, mail or cron.'
exec .venv/bin/python -m rasd_app.server --seed-demo \
  --data "$HOME/.rasd-manual-client-demo" \
  --owner-email owner@rasd.demo --owner-password "RasdLocalDemo!2026" \
  --host 127.0.0.1 --port 8765
