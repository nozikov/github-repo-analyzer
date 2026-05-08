# Repo Analyzer

[![Tests](https://github.com/nozikov/github-repo-analyzer/actions/workflows/test.yml/badge.svg)](https://github.com/nozikov/github-repo-analyzer/actions/workflows/test.yml)
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

## Как работает

Граф из 5 узлов. Три параллельные ветки сливаются в финальный синтезатор:

```mermaid
flowchart TD
    Start([URL]) --> fetch_meta[fetch_meta]
    fetch_meta -->|GitHub API| plan[plan]
    plan -->|fan-out| analyze_code[analyze_code]
    plan -->|fan-out| find_similar[find_similar]
    plan -->|fan-out| web_context[web_context]
    analyze_code --> synthesize[synthesize]
    find_similar --> synthesize
    web_context --> synthesize
    synthesize --> End([report.md])

    classDef io fill:#e0f2fe,stroke:#0284c7
    classDef llm fill:#fef3c7,stroke:#d97706
    class fetch_meta io
    class plan,analyze_code,find_similar,web_context,synthesize llm
```

- **`fetch_meta`** — тянет метаданные репо, README и file_tree из GitHub API.
- **`plan`** — Claude решает, какие файлы читать, какой запрос на похожие репо отправить и какие веб-запросы.
- **`analyze_code` / `find_similar` / `web_context`** — три ветки идут одновременно, каждая собирает свой кусок контекста.
- **`synthesize`** — собирает всё в финальный markdown с тремя секциями.

Полное описание архитектуры, контракты узлов, обработка ошибок и roadmap — в [docs/architecture.md](docs/architecture.md).

## Тесты

```bash
uv run pytest -v          # все юнит и smoke тесты с моками
uv run pytest -m live -s  # реальные API (нужны ключи)
```

CI прогоняет юнит-тесты на Python 3.11 и 3.12 на каждый push и PR.

## Стоимость прогона

На среднем репо (10-15 файлов): ~10-30 центов на Claude Sonnet 4.6 + бесплатные tier-ы GitHub и Tavily.

## Contributing

См. [CONTRIBUTING.md](CONTRIBUTING.md). Issues и PR приветствуются.

## Лицензия

[MIT](LICENSE)
