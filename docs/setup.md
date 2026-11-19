# Встановлення (macOS)

Однаково для QA і розробника. Браузерні етапи працюють тільки на компʼютері з IP, якому відкриті тестові стенди, — не в пісочниці.

## 1. Програми

```bash
node -v        # потрібен v20+; інакше: brew install node
python3 -V     # 3.10+
claude -v      # Claude Code; інакше — встановити за інструкцією Anthropic
```

## 2. Репозиторій і Python

```bash
cd ~/Desktop/ABP/avto
git clone <url цього репозиторію> qa-agent-pipeline
cd qa-agent-pipeline
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
git config pull.rebase true
tests/selftest.sh          # ✅ selftest пройдено
```

## 3. `.env`

```bash
cp .env.example .env
```

Заповніть: `QA_USER` (латиницею — так підписуються ваші прогони), шляхи `AVTOPRO_PATH`, `CODEWIKI_PATH` (папка вікі, `…/CodeWiki/CodeWiki`), `AUTOMATION_PATH`, стенд за замовчуванням, `TEST_ENV_PASSWORD`, тестові акаунти. **Тільки користувачі зі `StaticUserHelper.TestUsers`** — під іншими працюють бойові Stripe і Recalvi. `.env` не комітиться.

## 4. MCP-сервери

```bash
claude
```

- Дозвольте `playwright` і `azure-devops` з `.mcp.json`. Питання не було — `/exit`, `claude mcp reset-project-choices`, знову `claude`.
- `/mcp` — обидва в списку (перший запуск довший: `npx` завантажує пакети).
- Вхід в Azure DevOps: попросіть «покажи назву і стан задачі <ID>» — відкриється браузер, увійдіть акаунтом з доступом до `dev.azure.com/abp`.
- Для **dev-check.sh** (headless) вхід має бути вже виконаний хоча б раз в інтерактивному `claude` — у headless-режимі браузер для входу не відкривається.

| Симптом | Що робити |
| --- | --- |
| Вхід не проходить | `brew install azure-cli && az login`; у `.mcp.json` до аргументів `azure-devops` додати `"--authentication", "azcli"` |
| `401` / `403` | Акаунт без доступу до `abp` / `Avto.Pro` |
| MCP не віддає вміст вкладення-чек-листа | `ADO_PAT` у `.env` (Work Items — Read) — тоді `scripts/ado_attachment.py`; або збережіть xlsx у `tasks/<ID>/input/checklist.xlsx` вручну |
| Агент намагається змінити задачу | Заборонено в `.claude/settings.json` (`deny`); перевірте `/permissions` |

## 5. CodeWiki і контекст

Розділ QA (проєкт, глосарій, довідник тестових даних TD, рецепти howto, карта автотестів) — у CodeWiki `kb/QA/`. Як його створити з `qa-context/` старого репозиторію — [`codewiki-qa-section.md`](codewiki-qa-section.md). Оновлюйте CodeWiki перед роботою: `git -C ~/Desktop/ABP/avto/CodeWiki pull`.

## 6. Перший запуск

- QA: `claude` → `/qa-test <ID> seller2 es`.
- Розробник: `scripts/dev-check.sh <ID> seller2 es` — без інтерфейсу; наприкінці відкриється `report.html`, прогін закомітиться і запушиться.

## Пісочниця

Аналіз коду AvtoPro за правилами компанії — тільки в пісочниці з кодом тільки для читання. У цьому pipeline код читають `qa-agent-spec` (тексти, ключі, ендпоінти) і `qa-autotests-coverage` (diff гілки). Якщо політика вимагає — запускайте ці кроки в пісочниці (`sbx`, як у попередньому pipeline), а браузерні — на Mac. Як розділяти на практиці — питання ревʼю (`review.md`).
