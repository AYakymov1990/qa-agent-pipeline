# Вихідні правки контексту для CodeWiki

Pipeline **не пише** в CodeWiki напряму: CodeWiki — частина репозиторію AvtoPro, а він для pipeline тільки для читання.

Підтверджені QA правки контексту (`qa-context-update`, `qa-context-intake`) складаються сюди:

```
context-outbox/
├── CHANGES.md          що змінено, навіщо, джерело, хто підтвердив — по датах
└── kb/QA/...           нові версії файлів розділу QA, той самий шлях, що в CodeWiki
```

Поки правки не перенесені, скіли читають спершу `context-outbox/kb/QA/`, потім `$CODEWIKI_PATH/kb/QA/`.

Як перенести — `docs/codewiki-qa-section.md` § «Перенесення правок». Після злиття в CodeWiki — очистити перенесене (рядок у `CHANGES.md` → «перенесено, PR …»).
