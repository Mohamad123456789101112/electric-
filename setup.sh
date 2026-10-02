#!/usr/bin/env bash
# تجهيز بيئة التشغيل: ينشئ .venv ويثبّت الاعتماديات (مطلوب مرة واحدة بعد الاستنساخ)
set -e
cd "$(dirname "$0")"
python3 -m venv .venv
./.venv/bin/pip install --quiet --upgrade pip
./.venv/bin/pip install --quiet -r requirements.txt
echo "✅ البيئة جاهزة: ./.venv/bin/python -m uvicorn mirsad.main:app --host 0.0.0.0 --port 8000"
