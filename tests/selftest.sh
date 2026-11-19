#!/usr/bin/env bash
# Самоперевірка скриптів на синтетичному чек-листі: import → set → select (qa, dev) → fill → metrics → html.
# Нічого не відкриває в мережі; працює в тимчасовій задачі tasks/_selftest (видаляється наприкінці).
set -euo pipefail
cd "$(dirname "$0")/.."
PY="${PY:-$( [ -x .venv/bin/python ] && echo .venv/bin/python || echo python3 )}"
T=_selftest; D=tasks/$T; trap 'rm -rf "$D"' EXIT
mkdir -p "$D/input"
$PY tests/make_example.py "$D/input/checklist.xlsx" >/dev/null
$PY scripts/checklist.py import --task $T
$PY scripts/checklist.py set --task $T CHK-001 CHK-002 CHK-003 CHK-005 CHK-006 data_status=ok >/dev/null
$PY scripts/checklist.py set --task $T CHK-007 autotests=covered exec=автотести >/dev/null
R=$D/runs/20000101-0000-dev-selftest
$PY scripts/checklist.py import --task $T --state $R >/dev/null
$PY scripts/checklist.py select --task $T --state $R --mode dev --run $R
$PY - "$R/selection.json" <<'PY'
import json, sys
take = json.load(open(sys.argv[1]))['take']
assert take == ['CHK-001', 'CHK-002', 'CHK-003'], take  # P1 першими; без вручну, допущення, P3, регресу, передумов QA
PY
$PY scripts/checklist.py select --task $T --mode qa --run $D/runs/qa
echo '{"CHK-001":{"status":"PASS","tc":"TC-001"},"CHK-002":{"status":"FAIL","tc":"TC-002","note":"тест"}}' > $R/results.json
printf '# Звіт прогону: selftest\n\n**Вердикт:** ❌ Не готово — тест\n\n**Підсумок:** PASS 1 · FAIL 1\n\n## По кейсах\n\n| TC | Результат |\n| --- | --- |\n| TC-001 | PASS |\n| TC-002 | FAIL |\n' > $R/report.md
$PY scripts/checklist.py fill --task $T --state $R --run $R
M=.claude/skills/qa-agent-run/scripts/metrics.py
$PY $M mark --run $R --tc RUN --event start >/dev/null; $PY $M mark --run $R --tc RUN --event end >/dev/null
$PY $M run --run $R --task $T >/dev/null
$PY .claude/skills/qa-agent-run/scripts/report_html.py $R >/dev/null && grep -q 'verdict bad' $R/report.html
echo "✅ selftest пройдено"
