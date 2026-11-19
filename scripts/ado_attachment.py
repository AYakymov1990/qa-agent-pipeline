#!/usr/bin/env python3
"""Завантаження вкладення задачі Azure DevOps (запасний шлях, якщо MCP не віддає вміст вкладення).

  ado_attachment.py --url "<url вкладення з relations задачі>" --out tasks/<ID>/input/checklist.xlsx

Потрібен ADO_PAT у .env (права: Work Items — Read). Тільки читання: виконується лише GET.
Хост — тільки dev.azure.com/<організація з pipeline.config.json>.
"""
import argparse
import base64
import json
import sys
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def env(key):
    p = ROOT / '.env'
    if not p.exists():
        return ''
    val = ''
    for line in p.read_text(encoding='utf-8').splitlines():
        if line.startswith(key + '='):
            val = line.split('=', 1)[1].strip().strip('"')
    return val


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--url', required=True)
    ap.add_argument('--out', required=True)
    a = ap.parse_args()
    org = json.loads((ROOT / 'pipeline.config.json').read_text(encoding='utf-8'))['azure_devops']['organization']
    u = urllib.parse.urlparse(a.url)
    if u.scheme != 'https' or u.netloc != 'dev.azure.com' or not u.path.startswith(f'/{org}/') or '/_apis/wit/attachments/' not in u.path:
        sys.exit(f'Дозволені тільки вкладення https://dev.azure.com/{org}/…/_apis/wit/attachments/…')
    pat = env('ADO_PAT')
    if not pat:
        sys.exit('Немає ADO_PAT у .env — або збережіть файл вручну в tasks/<ID>/input/checklist.xlsx')
    q = dict(urllib.parse.parse_qsl(u.query))
    q.update({'download': 'true', 'api-version': q.get('api-version', '7.1')})
    url = urllib.parse.urlunparse(u._replace(query=urllib.parse.urlencode(q)))
    req = urllib.request.Request(url, method='GET', headers={'Authorization': 'Basic ' + base64.b64encode(f':{pat}'.encode()).decode()})
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            data = r.read()
    except Exception as e:  # PAT у повідомлення не потрапляє
        sys.exit(f'Не вдалося завантажити: {e}')
    if not data.startswith(b'PK'):
        sys.exit('Отримано не xlsx (можливо, сторінка входу) — перевірте ADO_PAT і права')
    out = Path(a.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_bytes(data)
    print(f'{out} · {len(data)} байт')


if __name__ == '__main__':
    main()
