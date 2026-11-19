# QA agent pipeline AvtoPro

Агентне тестування задач AvtoPro за чек-листом з PBI — для QA і розробників.

> **Стан: базова структура для ревʼю.** Не привʼязана до задачі; наступний етап — прогін на реальній задачі. Відкриті питання — [`docs/review.md`](docs/review.md).

## Як це працює

```
Аналіз PBI (окремий процес)  →  чек-лист .xlsx вкладено в PBI
                                         │
                     ┌───────────────────┴───────────────────┐
              /qa-test <ID>                          /dev-check <ID>
              тестувальник                           розробник
                     │                                       │
   ado-fetch → checklist-import → маршрут S/M/L → відбір → дані → кейси
                     │                                       │
   розвідка, покроковий прогін з апрувом      автоматичний прогін, без питань
   баги, правка автотестів                    вердикт ✅ / ❌ / ⚠️
                     │                                       │
                     └── «Прогон N» у копії чек-листа, report.html, коміт ──┘
```

| | QA-режим `/qa-test` | Dev-режим `/dev-check` |
| --- | --- | --- |
| Що перевіряє | Усе, що може агент: P1–P3, з допущеннями Q-xx | Основний функціонал: «агент», P1 → P2, без допущень, без граничних (P3), без регресу, тільки з даними |
| Участь людини | Підтвердження класифікації, перегляд кейсів, розвідка, апрув вердиктів | Немає — одна команда |
| Результат | Звіт, «Прогон N», чернетки багів, оновлені автотести | Вердикт «Готово до тесту ✅ / Не готово ❌ / ⚠️», звіт, «Прогон N» |

Детально — [`docs/how-it-works.md`](docs/how-it-works.md). Вимоги до чек-листа — [`docs/checklist-format.md`](docs/checklist-format.md).

## Швидкий старт

1. Встановлення і доступи — [`docs/setup.md`](docs/setup.md) (Claude Code, Node, Python venv, `.env`, Azure DevOps MCP, CodeWiki).
2. Перевірка скриптів без мережі: `tests/selftest.sh`.
3. QA: у Claude Code в корені репозиторію — `/qa-test 129469 seller2 es`.
4. Розробник: `scripts/dev-check.sh 129469 seller2 es` (або `/dev-check …` у Claude Code).

## Структура

```
.claude/skills/          скіли pipeline (нижче)
.claude/settings.json    дозволи: Azure DevOps — тільки читання; allowlist для headless-запуску
.mcp.json                Playwright MCP, Azure DevOps MCP
pipeline.config.json     стенди, формат чек-листа, правила класифікації і відбору, маршрути
scripts/                 checklist.py (імпорт / відбір / результати), dev-check.sh, commit-run.sh, ado_attachment.py
tasks/<ID>/              артефакти задачі; прогони — tasks/<ID>/runs/<дата>-<qa|dev>-<хто>/ (комітяться)
context-outbox/          підтверджені правки контексту для розділу QA у CodeWiki
examples/, tests/        синтетичний чек-лист і самоперевірка
docs/                    встановлення, як працює, формат чек-листа, CodeWiki, ревʼю
```

| Скіл | Режим | Що робить |
| --- | --- | --- |
| `qa-test` | QA | Точка входу QA-режиму, маршрут S / M / L |
| `dev-check` | Dev | Точка входу dev-режиму, вердикт |
| `qa-ado-fetch` | обидва | Задача, коментарі, вкладений чек-лист з Azure DevOps (читання) |
| `qa-checklist-import` | обидва | Розбір xlsx і класифікація: агент / вручну / API / автотести |
| `qa-test-data` | обидва | Дані для кожної перевірки з довідника TD і рецептів howto |
| `qa-agent-spec` | обидва | Специфікація і кейси для агента |
| `qa-agent-recon` | QA | Розвідка інтерфейсу перед прогоном |
| `qa-agent-run` | обидва | Прогін через Playwright MCP, звіт, «Прогон N», метрики, HTML |
| `qa-bug-report` | QA | Чернетки багів для ручного заведення |
| `qa-autotests-coverage` | QA | Що з регресу покривають автотести, які тести зламаються |
| `qa-autotests-update` | QA | Правка автотестів у гілці `autotests/<ID>` за стандартами проєкту автотестів |
| `qa-context-update`, `qa-context-intake` | QA | Поповнення розділу QA у CodeWiki через `context-outbox/` |

## Безпека — коротко

Тільки тестові стенди (`<site>.seller<N>.vus.us`) і тестові користувачі; Azure DevOps — тільки читання; код AvtoPro, CodeWiki, автотести — тільки читання (крім гілки `autotests/<ID>`); секрети — тільки в `.env`. Повністю — [`CLAUDE.md`](CLAUDE.md).
