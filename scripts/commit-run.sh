#!/usr/bin/env bash
# Коміт результатів прогону, щоб їх бачила команда (QA бачить dev-прогони і навпаки).
#   scripts/commit-run.sh <ID> [папка прогону]
# Без папки — комітить усе змінене в tasks/<ID>/ (QA-режим: спільні файли задачі + прогони).
# З папкою — тільки її (dev-режим: спільних файлів задачі не чіпає).
# input/ (кеш з Azure DevOps) і відео — у .gitignore.
set -euo pipefail
cd "$(dirname "$0")/.."
ID="${1:?Використання: scripts/commit-run.sh <ID> [папка прогону]}"; RUN="${2:-}"
TARGET="${RUN:-tasks/$ID}"
[ -e "$TARGET" ] || { echo "Немає $TARGET"; exit 1; }

# Захист: секрети не комітимо ніколи
if git ls-files --others --modified --exclude-standard -- "$TARGET" | grep -E '(^|/)\.env($|\.)' | grep -v '\.env\.example$'; then
  echo "❌ У $TARGET є .env — коміт скасовано"; exit 1
fi

git add -- "$TARGET"
if git diff --cached --quiet; then echo "Немає змін для коміту"; exit 0; fi
MSG="Прогін $ID: ${RUN:+$(basename "$RUN")}${RUN:-оновлення задачі}"
git commit -q -m "$MSG"
git pull --rebase -q && git push -q && echo "✅ $MSG — запушено"
