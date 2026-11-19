# Розділ QA у CodeWiki

Контекст проєкту для QA і агента живе в CodeWiki (гілка `docs/wiki-kb-pilot`), розділ `kb/QA/`, — щоб його бачила вся команда, а не тільки цей репозиторій.

## Структура

```
kb/QA/
├── README.md           що тут і як оновлюється
├── PROJECT.md          площадки, ролі, стенди, інтеграції, severity / priority
├── glossary.md         терміни, синоніми, назви в UI за площадками
├── test-data.md        довідник тестових даних: записи TD-xxx
├── autotests-map.md    карта автотестів AvtoProAutomation
├── domain/             бізнес-правила за сутностями (замовлення, доставка, оплата…)
└── howto/              рецепти: як отримати стан даних («Агенту можна: так / ні»)
    └── README.md
```

## Перенесення з попереднього pipeline (`qaPipeline/qa-context/`)

| Було | Стало | Що змінити |
| --- | --- | --- |
| `PROJECT.md`, `glossary.md`, `domain/`, `howto/` | ті самі шляхи в `kb/QA/` | посилання `qa-context/…` → `kb/QA/…` |
| `test-data.md` | `kb/QA/test-data.md` | кожному запису — ID `TD-xxx` (на них посилаються кейси і `data.md`) |
| `sources.md` | `kb/QA/README.md` § Джерела | — |
| `open-questions.md` | не переносити | відкриті питання — в задачах |
| `autotests-map.md` (якщо є) | `kb/QA/autotests-map.md` | — |

Паролів і персональних даних у CodeWiki немає — тільки назви змінних `.env`.

## Перенесення правок (`context-outbox/` → CodeWiki)

Pipeline для CodeWiki — тільки читання; підтверджені правки складаються в `context-outbox/`. Переносить людина:

```bash
cd ~/Desktop/ABP/avto/CodeWiki
git pull
git switch -c qa-kb/<YYYY-MM-DD>-<тема>
rsync -a ~/Desktop/ABP/avto/qa-agent-pipeline/context-outbox/kb/QA/ CodeWiki/kb/QA/
git diff                      # перегляд
git commit -am "kb/QA: <що додано>"
git push -u origin HEAD       # PR у docs/wiki-kb-pilot
```

Після злиття — у `context-outbox/CHANGES.md` стан «перенесено, PR …» і очистити перенесені файли з `context-outbox/kb/`.

## Перевірити до старту

- `CodeWiki/AUTOUPDATE.md` — чи автооновлення вікі не перезаписує `kb/QA/` (розділ ведеться людьми). Якщо перезаписує — виключити `kb/QA/` з автооновлення або вести розділ в іншому місці.
- Хто ревʼюїть PR у `kb/QA/`.
