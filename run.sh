#!/usr/bin/env bash
# تشغيل منظومة مِرصاد
set -e
cd "$(dirname "$0")"
if [ ! -d .venv ]; then python3 -m venv .venv; fi
./.venv/bin/pip install -q -r requirements.txt
exec ./.venv/bin/python -m uvicorn mirsad.main:app --host 0.0.0.0 --port "${PORT:-8000}"
