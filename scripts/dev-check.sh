#!/usr/bin/env bash
# Кнопка для розробника: агентна перевірка основного функціоналу задачі без участі людини.
#   scripts/dev-check.sh <ID> [стенд] [площадка]      напр.: scripts/dev-check.sh 129469 seller2 es
# Що робить: оновлює репозиторій → запускає Claude Code headless з /dev-check → комітить папку прогону
# → відкриває report.html. Потрібно: Claude Code, Node (npx для Playwright MCP), .env, вхід в Azure DevOps MCP.
set -euo pipefail
cd "$(dirname "$0")/.."
. scripts/_env.sh

ID="${1:-}"; STAND="${2:-$(envget TEST_STAND)}"; SITE="${3:-$(envget TEST_SITE)}"
if [ -z "$ID" ]; then echo "Використання: scripts/dev-check.sh <ID> [стенд] [площадка]"; exit 2; fi
if [ ! -f .env ]; then echo "Немає .env — скопіюйте .env.example і заповніть (docs/setup.md)"; exit 2; fi
USER_TAG="$(envget QA_USER)"; [ -n "$USER_TAG" ] || { echo "Заповніть QA_USER у .env"; exit 2; }
[ -n "$STAND" ] && [ -n "$SITE" ] || { echo "Вкажіть стенд і площадку або TEST_STAND / TEST_SITE у .env"; exit 2; }
command -v claude >/dev/null || { echo "Не знайдено claude (Claude Code)"; exit 2; }

git pull --rebase --autostash -q || echo "⚠️  git pull не вдався — працюю з локальною версією"

ADD_DIRS=()
for v in CODEWIKI_PATH AUTOMATION_PATH AVTOPRO_PATH; do
  p="$(envget "$v")"; [ -n "$p" ] && [ -d "$p" ] && ADD_DIRS+=(--add-dir "$p")
done

LOG="$(mktemp -t dev-check-"$ID".XXXX)"
echo "▶ dev-check $ID на $SITE.$STAND.vus.us … (журнал: $LOG)"
claude -p "/dev-check $ID $STAND $SITE" \
  --permission-mode acceptEdits \
  ${ADD_DIRS[@]+"${ADD_DIRS[@]}"} \
  | tee "$LOG"

RUN="$(ls -1dt tasks/"$ID"/runs/*-dev-"$USER_TAG" 2>/dev/null | head -1 || true)"
if [ -z "$RUN" ]; then echo "❌ Прогін не створено — дивіться журнал $LOG"; exit 1; fi

scripts/commit-run.sh "$ID" "$RUN" || echo "⚠️  Коміт / push не вдався — прогін лишився локально: $RUN"
[ -f "$RUN/report.html" ] && { command -v open >/dev/null && open "$RUN/report.html" || echo "Звіт: $RUN/report.html"; }
grep -m1 '^\*\*Вердикт:\*\*' "$RUN/report.md" 2>/dev/null || true
