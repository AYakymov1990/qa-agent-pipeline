#!/usr/bin/env python3
"""Чек-лист задачі: імпорт з xlsx, класифікація, відбір під режим, запис результатів прогону.

Джерело правди після імпорту — tasks/<ID>/checklist.json (QA-режим) або <run>/checklist.json
(dev-режим, --state <run>: dev-прогін не змінює спільних файлів задачі, класифікацію QA бере як основу);
checklist.md генерується з нього.

  import   xlsx → checklist.json + checklist.md (+ чернетка класифікації за маркерами)
           checklist.py import --task 129469 [--xlsx tasks/129469/input/checklist.xlsx]
  set      змінити поля рядків (класифікація, дані, покриття автотестами)
           checklist.py set --task 129469 CHK-014 CHK-015 exec=вручну "why=візуальний порядок" confirmed=1
  render   перегенерувати checklist.md
  select   відбір перевірок під режим → <run>/selection.json + selection.md
           checklist.py select --task 129469 --mode dev --run tasks/129469/runs/20261119-1030-dev-ivan [--max 15]
  fill     результати прогону (<run>/results.json) → копія xlsx з колонкою «Прогон N»
           checklist.py fill --task 129469 --run tasks/129469/runs/<прогін> [--column "Прогон 2"]
  status   коротка зведена таблиця по чек-листу (для pipeline.md)

Поля рядка (checklist.json → rows[]):
  id, row, check, expected, note, priority (P1/P2/P3/?), test_env_only, data, source, precondition,
  assumption (Q-xx або текст), regression, runs {«Прогін 1»: «Успешно», …},
  exec (агент / вручну / API / автотести / ?), why, confirmed, needs_qa,
  data_refs (TD-…), data_status (ok / missing / ?), autotests (covered / partial / none / ?), warnings[]
"""
import argparse
import json
import re
import shutil
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CONFIG = json.loads((ROOT / 'pipeline.config.json').read_text(encoding='utf-8'))
CL = CONFIG['checklist']
EXEC_VALUES = ('агент', 'вручну', 'API', 'автотести', '?')
ORDER = {'P1': 1, 'P2': 2, 'P3': 3, '?': 9}


def load_openpyxl():
    try:
        import openpyxl
        return openpyxl
    except ImportError:
        sys.exit('Потрібен openpyxl: python3 -m pip install -r requirements.txt (або .venv)')


def task_dir(task):
    return ROOT / 'tasks' / str(task)


def state_dir(a):
    """Де лежить checklist.json: tasks/<ID>/ (QA-режим) або папка прогону (dev-режим, --state)."""
    return Path(a.state) if getattr(a, 'state', None) else task_dir(a.task)


def norm(s):
    return re.sub(r'\s+', ' ', str(s or '')).strip()


def find_cols(ws):
    """Колонки за заголовками першого рядка (назви — з pipeline.config.json)."""
    head = {c: norm(ws.cell(1, c).value) for c in range(1, ws.max_column + 1)}
    cols, runs = {}, []
    for key in ('id', 'check', 'expected', 'note'):
        for c, h in head.items():
            if h in CL['columns'][key]:
                cols[key] = c
                break
    for c, h in head.items():
        if any(h.startswith(p) for p in CL['columns']['run_prefix']):
            runs.append((c, h))
    missing = [k for k in ('id', 'check', 'expected') if k not in cols]
    if missing:
        sys.exit(f'У листі «{ws.title}» не знайдено колонок: {missing}. Заголовки: {list(head.values())}')
    return cols, runs


def starts(token, keys):
    for k in keys:
        if token.lower().startswith(k.lower()):
            return token[len(k):].strip()
    return None


def parse_note(note):
    """«P1 · Только тест-среда · Данные: … · Источник: … · Предусловие: … · Пока считаем: Q-01»."""
    t = CL['note_tokens']
    out = {'priority': '?', 'test_env_only': False, 'data': '', 'source': '', 'precondition': '', 'assumption': '', 'other': []}
    for tok in [x.strip() for x in re.split(r'\s+·\s+', norm(note)) if x.strip()]:
        if re.fullmatch(t['priority'], tok):
            out['priority'] = tok
        elif tok in t['test_env_only']:
            out['test_env_only'] = True
        elif (v := starts(tok, t['data'])) is not None:
            out['data'] = v
        elif (v := starts(tok, t['source'])) is not None:
            out['source'] = v
        elif (v := starts(tok, t['precondition'])) is not None:
            out['precondition'] = v
        elif (v := starts(tok, t['assumption'])) is not None:
            out['assumption'] = v
        else:
            out['other'].append(tok)
    return out


def draft_exec(r):
    """Чернетка «Виконання» за маркерами з конфігу. Остаточно вирішує скіл / QA (confirmed)."""
    text = ' '.join((r['check'], r['expected'], r['data'], r['precondition'])).lower()
    for marker, why in CONFIG['classification']['manual'].items():
        if marker in text:
            return 'вручну', f'маркер «{marker}»: {why}'
    return 'агент', 'маркерів ручної перевірки немає'


def needs_qa(r):
    text = ' '.join((r['precondition'], r['data'])).lower()
    for marker, why in CONFIG['classification']['needs_qa'].items():
        if marker in text:
            return why
    return ''


def read_analysis(wb):
    name = CL.get('analysis_sheet')
    if not name or name not in wb.sheetnames:
        return {}
    ws = wb[name]
    res = {'questions': [], 'service': [], 'meta': {}}
    for row in ws.iter_rows(min_row=2, values_only=True):
        a, b, c = (norm(x) for x in (row + (None,) * 3)[:3])
        if a:
            q = re.match(r'(Q-\d+)\.?\s*(.*)', a)
            if c == 'Служебное' or not q:
                res['service'].append(a)
            else:
                res['questions'].append({'id': q.group(1), 'title': q.group(2)[:300], 'ask': b[:500], 'type': c})
        # мета праворуч: «Региональная версия:», «Тип PBI:»
        for i in range(3, len(row) - 1):
            k, v = norm(row[i]), norm(row[i + 1])
            if k.endswith(':') and v:
                res['meta'][k.rstrip(':')] = v
    return res


def side_meta(ws, used_cols):
    """Пари «Ключ:» → значення у вільних колонках (Автор, PBI)."""
    meta = {}
    for r in range(1, min(ws.max_row, 40) + 1):
        for c in range(1, ws.max_column):
            if c in used_cols:
                continue
            k = norm(ws.cell(r, c).value)
            if k.endswith(':'):
                v = ws.cell(r, c + 1).value
                v = str(v or '')
                m = re.search(r'HYPERLINK\("([^"]+)"\s*,\s*"([^"]*)"', v)
                meta[k.rstrip(':')] = f'{m.group(2)} — {m.group(1)}' if m else norm(v)
    return meta


def cmd_import(a):
    openpyxl = load_openpyxl()
    td = task_dir(a.task)
    xlsx = Path(a.xlsx) if a.xlsx else td / 'input' / 'checklist.xlsx'
    if not xlsx.exists():
        sys.exit(f'Немає файлу {xlsx}. Спершу ado-fetch або --xlsx <шлях>.')
    wb = openpyxl.load_workbook(xlsx)
    ws = wb[CL['sheet']] if CL['sheet'] in wb.sheetnames else wb.worksheets[0]
    cols, runs = find_cols(ws)
    sd = state_dir(a)
    old = {}
    jpath = sd / 'checklist.json'
    base = jpath if jpath.exists() else td / 'checklist.json'  # dev: класифікація QA як основа
    if base.exists() and not a.reset:
        old = {r['id']: r for r in json.loads(base.read_text(encoding='utf-8'))['rows']}
    rows, seen = [], set()
    for i in range(2, ws.max_row + 1):
        rid = norm(ws.cell(i, cols['id']).value)
        check = norm(ws.cell(i, cols['check']).value)
        if not rid and not check:
            continue
        note = norm(ws.cell(i, cols['note']).value) if 'note' in cols else ''
        n = parse_note(note)
        r = {
            'id': rid or f'ROW-{i}', 'row': i, 'check': check,
            'expected': norm(ws.cell(i, cols['expected']).value), 'note': note,
            'priority': n['priority'], 'test_env_only': n['test_env_only'], 'data': n['data'],
            'source': n['source'], 'precondition': n['precondition'], 'assumption': n['assumption'],
            'regression': any(check.startswith(m) for m in CL['regression_marker']),
            'runs': {h: norm(ws.cell(i, c).value) for c, h in runs},
            'warnings': [],
        }
        q = re.search(r'Q-\d+', r['expected'])
        if not r['assumption'] and q and re.search(r'допущени|припущенн', r['expected'], re.I):
            r['assumption'] = q.group(0)
        if r['priority'] == '?':
            if a.default_priority:
                r['priority'] = a.default_priority
                r['warnings'].append(f'пріоритет не вказано — взято {a.default_priority} (--default-priority)')
            else:
                r['warnings'].append('пріоритет не вказано')
        if not r['data']:
            r['warnings'].append('немає «Данные:»')
        if not r['expected']:
            r['warnings'].append('немає очікуваного результату')
        if r['id'] in seen:
            r['warnings'].append('дубль ID')
        if n['other']:
            r['warnings'].append('нерозпізнані позначки: ' + '; '.join(n['other']))
        seen.add(r['id'])
        prev = old.get(r['id'])
        same = prev and (prev['check'], prev['expected'], prev['note']) == (r['check'], r['expected'], r['note'])
        if same:  # формулювання не змінились — зберігаємо класифікацію і дані
            for k in ('exec', 'why', 'confirmed', 'needs_qa', 'data_refs', 'data_status', 'autotests'):
                r[k] = prev.get(k)
        else:
            r['exec'], r['why'] = draft_exec(r)
            r['confirmed'] = False
            r['needs_qa'] = needs_qa(r)
            r['data_refs'], r['data_status'], r['autotests'] = [], '?', '?' if r['regression'] else ''
            if prev:
                r['warnings'].append('рядок змінено з минулого імпорту — класифікацію скинуто')
        rows.append(r)
    nums = sorted(int(m.group(1)) for r in rows if (m := re.fullmatch(r'CHK-(\d+)', r['id'])))
    gaps = [f'CHK-{x:03d}' for x in range(nums[0], nums[-1]) if x not in nums] if nums else []
    data = {
        'task': str(a.task), 'source_file': xlsx.name, 'imported': datetime.now().isoformat(timespec='seconds'),
        'sheet': ws.title, 'run_columns': [h for _, h in runs], 'meta': side_meta(ws, set(cols.values()) | {c for c, _ in runs}),
        'analysis': read_analysis(wb), 'id_gaps': gaps, 'removed': sorted(set(old) - seen), 'rows': rows,
    }
    sd.mkdir(parents=True, exist_ok=True)
    jpath.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding='utf-8')
    render(data, sd)
    print(summary(data))


def load(a):
    p = state_dir(a) / 'checklist.json'
    if not p.exists():
        sys.exit(f'Немає {p}. Спершу: checklist.py import --task {a.task}' + (f' --state {a.state}' if getattr(a, 'state', None) else ''))
    return json.loads(p.read_text(encoding='utf-8'))


def save(a, data):
    (state_dir(a) / 'checklist.json').write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding='utf-8')
    render(data, state_dir(a))


def cmd_set(a):
    data = load(a)
    ids = [x for x in a.items if '=' not in x]
    kv = dict(x.split('=', 1) for x in a.items if '=' in x)
    if not ids or not kv:
        sys.exit('Формат: set --task <ID> CHK-001 [CHK-002 …] ключ=значення [ключ=значення …]')
    if 'exec' in kv and kv['exec'] not in EXEC_VALUES:
        sys.exit(f'exec: одне з {EXEC_VALUES}')
    byid = {r['id']: r for r in data['rows']}
    unknown = [i for i in ids if i not in byid and i != 'ALL']
    if unknown:
        sys.exit(f'Немає рядків: {unknown}')
    targets = data['rows'] if ids == ['ALL'] else [byid[i] for i in ids]
    for r in targets:
        for k, v in kv.items():
            if k == 'data_refs':
                r[k] = [x for x in re.split(r'[,\s]+', v) if x]
            elif k == 'confirmed':
                r[k] = v.lower() in ('1', 'true', 'так', 'yes')
            elif k in ('exec', 'why', 'needs_qa', 'data_status', 'autotests', 'priority'):
                r[k] = v
            else:
                sys.exit(f'Невідоме поле {k}')
    save(a, data)
    print(f'оновлено {len(targets)} рядк.: {", ".join(kv)}')


def esc(s):
    return str(s or '').replace('|', '\\|').replace('\n', ' ')


def summary(data):
    rows = data['rows']
    from collections import Counter
    pr = Counter(r['priority'] for r in rows)
    ex = Counter(r['exec'] for r in rows)
    warn = sum(1 for r in rows if r['warnings'])
    s = [f"Рядків: {len(rows)} · " + ', '.join(f'{k}: {pr[k]}' for k in sorted(pr, key=lambda x: ORDER.get(x, 9))),
         'Виконання: ' + ', '.join(f'{k}: {v}' for k, v in ex.most_common()) + f" · підтверджено: {sum(1 for r in rows if r['confirmed'])}",
         f"Регрес: {sum(1 for r in rows if r['regression'])} · тільки тест-середовище: {sum(1 for r in rows if r['test_env_only'])} · з допущенням: {sum(1 for r in rows if r['assumption'])} · з попередженнями: {warn}"]
    if data.get('id_gaps'):
        s.append('Пропуски в нумерації: ' + ', '.join(data['id_gaps']))
    return '\n'.join(s)


def render(data, td):
    L = [f"# Чек-лист задачі {data['task']}", '',
         f"Джерело: `input/{data['source_file']}`, лист «{data['sheet']}» · імпорт {data['imported']} · колонки прогонів: {', '.join(data['run_columns']) or '—'}", '']
    for k, v in data.get('meta', {}).items():
        L.append(f'- {k}: {v}')
    for k, v in data.get('analysis', {}).get('meta', {}).items():
        L.append(f'- {k}: {v}')
    L += ['', '## Зведення', '', summary(data).replace('\n', '  \n'), '',
          '## Перевірки', '',
          '| ID | P | Перевірка | Очікуваний результат | Тест-сер. | Дані | Допущення | Виконання | Чому | ✔ | Дані TD | Автотести |',
          '| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |']
    for r in data['rows']:
        L.append('| ' + ' | '.join(esc(x) for x in (
            r['id'], r['priority'], r['check'], r['expected'], 'так' if r['test_env_only'] else '',
            r['data'] + (f" · Передумова: {r['precondition']}" if r['precondition'] else ''),
            r['assumption'], r['exec'] + (f" (QA: {r['needs_qa']})" if r.get('needs_qa') else ''), r['why'],
            '✔' if r['confirmed'] else '', ', '.join(r.get('data_refs') or []) + (f" ({r['data_status']})" if r.get('data_status') not in ('', None) else ''),
            r.get('autotests') or '')) + ' |')
    w = [r for r in data['rows'] if r['warnings']]
    if w:
        L += ['', '## Попередження імпорту', '']
        L += [f"- {r['id']}: {'; '.join(r['warnings'])}" for r in w]
    an = data.get('analysis') or {}
    if an.get('questions'):
        L += ['', '## Питання з аналізу PBI (лист «Анализ PBI»)', '', 'Рядки з допущенням за цими питаннями — тільки в QA-режимі, результат «потребує рішення QA».', '']
        L += [f"- **{q['id']}** ({q['type']}): {q['title']}" for q in an['questions']]
    if an.get('service'):
        L += ['', '## Службові позначки аналізу', ''] + [f'- {s}' for s in an['service']]
    if data.get('removed'):
        L += ['', '## Зникли з чек-листа з минулого імпорту', '', ', '.join(data['removed'])]
    (td / 'checklist.md').write_text('\n'.join(L) + '\n', encoding='utf-8')


def cmd_render(a):
    render(load(a), state_dir(a))
    print(state_dir(a) / 'checklist.md')


def pick(data, mode, max_cases=None):
    """Відбір під режим. Повертає (взяті, пропущені з причиною)."""
    S = CONFIG['selection'][mode]
    take, skip = [], []
    for r in sorted(data['rows'], key=lambda r: (ORDER.get(r['priority'], 9), r['row'])):
        why = None
        if r['regression'] and (r.get('autotests') == 'covered' or r['exec'] == 'автотести'):
            why = 'регрес покрито автотестами'
        elif mode == 'dev' and r['regression']:
            why = 'регрес — не для dev-перевірки'
        elif r['exec'] != 'агент':
            why = f"виконання: {r['exec']}" + (' (регрес)' if r['regression'] else '')
        elif r['priority'] not in S['priorities']:
            why = f"пріоритет {r['priority']}" + (' — граничні випадки не входять у dev' if mode == 'dev' else '')
        elif mode == 'dev':
            if r['assumption']:
                why = f"допущення {r['assumption']}"
            elif r.get('needs_qa'):
                why = f"потрібен QA: {r['needs_qa']}"
            elif r.get('data_status') != 'ok':
                why = f"дані не підтверджено ({r.get('data_status') or '?'})"
        else:
            if r.get('data_status') == 'missing':
                why = 'немає даних — BLOCKED до підготовки'
        (skip if why else take).append((r, why))
    if mode == 'dev':
        cap = max_cases or CONFIG['dev_check']['default_max_cases']
        for r, _ in take[cap:]:
            skip.append((r, f'понад ліміт dev-перевірки ({cap})'))
        take = take[:cap]
    return [r for r, _ in take], skip


def cmd_select(a):
    data = load(a)
    run = Path(a.run)
    run.mkdir(parents=True, exist_ok=True)
    take, skip = pick(data, a.mode, a.max)
    sel = {'task': data['task'], 'mode': a.mode, 'created': datetime.now().isoformat(timespec='seconds'),
           'checklist_imported': data['imported'], 'take': [r['id'] for r in take],
           'skip': {r['id']: why for r, why in skip}}
    (run / 'selection.json').write_text(json.dumps(sel, ensure_ascii=False, indent=1), encoding='utf-8')
    L = [f"# Відбір перевірок — {a.mode}-режим, задача {data['task']}", '',
         f"Взято **{len(take)}** з {len(data['rows'])}. Порядок прогону — нижче (P1 першими).", '',
         '| # | ID | P | Перевірка | Очікуваний результат | Дані TD |', '| --- | --- | --- | --- | --- | --- |']
    L += [f"| {i} | {r['id']} | {r['priority']} | {esc(r['check'])} | {esc(r['expected'])} | {esc(', '.join(r.get('data_refs') or []))} |" for i, r in enumerate(take, 1)]
    from collections import defaultdict
    groups = defaultdict(list)
    for r, why in skip:
        groups[re.sub(r'\s*\(.*', '', why) if why.startswith('дані') else why].append(r['id'])
    L += ['', '## Не взято', '', '| Причина | Перевірки |', '| --- | --- |']
    L += [f"| {esc(k)} | {', '.join(v)} |" for k, v in sorted(groups.items(), key=lambda x: -len(x[1]))]
    manual = [r['id'] for r in data['rows'] if r['exec'] == 'вручну' and r.get('autotests') != 'covered']
    if manual and a.mode == 'qa':
        L += ['', f"Вручну для QA: {', '.join(manual)}"]
    (run / 'selection.md').write_text('\n'.join(L) + '\n', encoding='utf-8')
    print(f"взято {len(take)}: {', '.join(sel['take'])}\nне взято {len(skip)} → {run / 'selection.md'}")


def cmd_fill(a):
    openpyxl = load_openpyxl()
    from openpyxl.comments import Comment
    data = load(a)
    td, run = task_dir(a.task), Path(a.run)
    src = td / 'input' / data['source_file']
    res_p = run / 'results.json'
    if not src.exists():
        sys.exit(f'Немає оригіналу {src} — повторіть ado-fetch.')
    if not res_p.exists():
        sys.exit(f'Немає {res_p}')
    results = json.loads(res_p.read_text(encoding='utf-8'))
    out = run / f'checklist-{run.name}.xlsx'
    shutil.copyfile(src, out)
    wb = openpyxl.load_workbook(out)
    ws = wb[data['sheet']]
    _, runs = find_cols(ws)
    byid = {r['id']: r for r in data['rows']}
    rows = [byid[i]['row'] for i in results if i in byid]
    if a.column:
        col = next((c for c, h in runs if h == a.column), None)
        if not col:
            sys.exit(f'Колонки «{a.column}» немає. Є: {[h for _, h in runs]}')
    else:
        col = next((c for c, h in runs if all(not ws.cell(r, c).value for r in rows)), None)
        if not col:
            sys.exit(f'Усі колонки прогонів уже заповнені для цих рядків — вкажіть --column. Є: {[h for _, h in runs]}')
    st = CL['statuses']
    n = 0
    for cid, res in results.items():
        if cid not in byid:
            print(f'! {cid} немає в чек-листі — пропущено')
            continue
        cell = ws.cell(byid[cid]['row'], col)
        cell.value = st.get(res['status'], st['SKIPPED'])
        if res['status'] != 'PASS' or res.get('note'):
            txt = f"{res['status']} · {res.get('tc', '')} · {run.name}\n{res.get('note', '')}".strip()
            cell.comment = Comment(txt[:1000], 'qa-agent')
        n += 1
    wb.save(out)
    print(f"{out} · колонка «{ws.cell(1, col).value}» · записано {n}")


def cmd_status(a):
    print(summary(load(a)))


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sp = p.add_subparsers(dest='cmd', required=True)
    s = sp.add_parser('import'); s.add_argument('--task', required=True); s.add_argument('--xlsx')
    s.add_argument('--default-priority', choices=['P1', 'P2', 'P3']); s.add_argument('--reset', action='store_true')
    s.set_defaults(f=cmd_import)
    s = sp.add_parser('set'); s.add_argument('--task', required=True); s.add_argument('items', nargs='+'); s.set_defaults(f=cmd_set)
    s = sp.add_parser('render'); s.add_argument('--task', required=True); s.set_defaults(f=cmd_render)
    s = sp.add_parser('select'); s.add_argument('--task', required=True); s.add_argument('--mode', choices=['dev', 'qa'], required=True)
    s.add_argument('--run', required=True); s.add_argument('--max', type=int, help='ліміт перевірок dev-режиму (за маршрутом)')
    s.set_defaults(f=cmd_select)
    s = sp.add_parser('fill'); s.add_argument('--task', required=True); s.add_argument('--run', required=True); s.add_argument('--column')
    s.set_defaults(f=cmd_fill)
    s = sp.add_parser('status'); s.add_argument('--task', required=True); s.set_defaults(f=cmd_status)
    for sub in sp.choices.values():
        sub.add_argument('--state', help='папка з checklist.json замість tasks/<ID>/ (dev-режим: папка прогону)')
    a = p.parse_args()
    a.f(a)


if __name__ == '__main__':
    main()
