# Repo Analyzer

Учебный LangGraph-агент: принимает URL публичного GitHub-репозитория и выдаёт markdown-отчёт из трёх секций — tech due-diligence, советы автору, идеи продуктов поверх технологии.

## Установка

```bash
uv sync
cp .env.example .env
# открой .env и впиши три ключа
```

## Запуск

```bash
uv run python -m repo_analyzer https://github.com/tiangolo/typer
```

Отчёт пишется в `reports/<owner>-<repo>-<date>.md` и одновременно печатается в stdout.

## Архитектура

См. `docs/superpowers/specs/2026-05-07-github-repo-analyzer-design.md`.

Граф из 7 узлов: `fetch_meta` → `plan` → 3 параллельные ветки (`analyze_code`, `find_similar`, `web_context`) → `reflect` → (loop or) `synthesize`.

## Тесты

```bash
uv run pytest -v          # все юнит и smoke тесты с моками
uv run pytest -m live -s  # реальные API (нужны ключи)
```

## Стоимость прогона

На среднем репо (10-15 файлов): ~10-30 центов на Claude Sonnet 4.6 + бесплатные tier-ы GitHub и Tavily.
