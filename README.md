# Repo Analyzer

[![Python](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)
[![Built with LangGraph](https://img.shields.io/badge/built%20with-LangGraph-orange.svg)](https://github.com/langchain-ai/langgraph)
[![LLM: Claude Sonnet 4.6](https://img.shields.io/badge/LLM-Claude%20Sonnet%204.6-7c3aed.svg)](https://www.anthropic.com/claude)
[![Package manager: uv](https://img.shields.io/badge/package%20manager-uv-de5fe9.svg)](https://github.com/astral-sh/uv)

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

Граф из 5 узлов: `fetch_meta` → `plan` → 3 параллельные ветки (`analyze_code`, `find_similar`, `web_context`) → `synthesize`.

## Тесты

```bash
uv run pytest -v          # все юнит и smoke тесты с моками
uv run pytest -m live -s  # реальные API (нужны ключи)
```

## Стоимость прогона

На среднем репо (10-15 файлов): ~10-30 центов на Claude Sonnet 4.6 + бесплатные tier-ы GitHub и Tavily.
