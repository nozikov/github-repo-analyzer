# GitHub Repo Analyzer — Design

**Дата:** 2026-05-07
**Статус:** Draft, ожидает review
**Цель проекта:** учебный проект для освоения LangGraph через построение реально полезного агента.

## Резюме

CLI-агент на Python + LangGraph, принимает URL публичного GitHub-репозитория и выдаёт markdown-отчёт из трёх разделов: tech due-diligence для пользователя, рекомендации автору репо, идеи продуктовых надстроек поверх технологии.

Архитектура использует все ключевые фичи LangGraph: типизированный state, параллельные ветки через `Send`, conditional edges, reflection loop, structured LLM output.

## Цели и не-цели

**Цели:**

- Построить работоспособного агента, который реально полезен (не просто туториал).
- Пройти через все ключевые концепции LangGraph: state, nodes, edges (incl. conditional), tools, parallel execution через `Send`, reflection.
- Получить осязаемый артефакт (markdown-отчёт) после каждого запуска.

**Не-цели:**

- Не строим production-сервис: нет аутентификации, нет горизонтального масштабирования, нет UI кроме CLI.
- Не анализируем приватные репо (нужен только PAT, но фокус на публичных).
- Не делаем persistence/checkpoints между запусками — каждый запуск независим.
- Не покрываем огромные монорепы (>5000 файлов). На таких работает деградированный режим.
- Не пытаемся достичь детерминированных отчётов — LLM по природе недетерминирован.

## Технологический стек

- **Python 3.11+**
- **LangGraph** (последняя стабильная)
- **langchain-anthropic** для Claude Sonnet 4.6
- **httpx** + **tenacity** для GitHub REST API
- **tavily-python** для веб-поиска
- **python-dotenv** для конфигурации
- Менеджер пакетов: **uv**

**API ключи (в `.env`):**

- `ANTHROPIC_API_KEY` — Claude
- `GITHUB_TOKEN` — GitHub Personal Access Token (5000 req/h вместо 60)
- `TAVILY_API_KEY` — Tavily web search (бесплатный tier 1000 req/мес)

## Архитектура графа

```
                       (start)
                          │
                          ▼
                   ┌──────────────┐
                   │  fetch_meta  │  GitHub API: repo info, README, file tree, manifest
                   └──────┬───────┘
                          ▼
                   ┌──────────────┐
                   │     plan     │  LLM: какие файлы читать, какие запросы отправлять
                   └──────┬───────┘
                          │
                  Send fan-out (3 параллельные ветки)
                  ┌───────┼─────────────────┐
                  ▼       ▼                 ▼
           ┌──────────┐ ┌──────────────┐ ┌────────────┐
           │ analyze_ │ │ find_similar │ │ web_       │
           │ code     │ │ _repos       │ │ context    │
           └────┬─────┘ └──────┬───────┘ └─────┬──────┘
                └──────────────┼───────────────┘
                               ▼
                        ┌──────────────┐
                        │   reflect    │  LLM: достаточно ли данных, чего не хватает
                        └──────┬───────┘
                               │
                  ┌────────────┴────────────┐
                  │                         │
            (gap → re-run branch)     (ok → synthesize)
                                            │
                                            ▼
                                     ┌──────────────┐
                                     │  synthesize  │  Markdown-отчёт в файл
                                     └──────┬───────┘
                                            ▼
                                          (end)
```

**Ключевые архитектурные решения:**

- **Параллелизм через `Send`**: после `plan` три ветки (`analyze_code`, `find_similar_repos`, `web_context`) запускаются одновременно. State аккумулируется через `Annotated[list, operator.add]`.
- **Reflection-loop ограничен 1 повтором**: после максимум двух попыток сбора данных синтезируем отчёт с явной отметкой gaps. Защита от бесконечных циклов.
- **Никаких checkpoints/persistence в V1**: каждый запуск независим, отчёт пишется за один проход.

## Schema State

```python
from typing import Annotated, TypedDict
from operator import add

class RepoMeta(TypedDict):
    owner: str
    name: str
    description: str
    stars: int
    language: str
    topics: list[str]
    readme: str
    manifest: dict           # parsed package.json/pyproject.toml/etc
    file_tree: list[str]     # все пути в репо

class CodeFinding(TypedDict):
    path: str
    summary: str             # что делает файл
    quality_notes: list[str] # замечания по качеству

class SimilarRepo(TypedDict):
    full_name: str
    description: str
    stars: int
    why_similar: str
    differentiator: str

class WebSnippet(TypedDict):
    url: str
    title: str
    relevant_quote: str

class Plan(TypedDict):
    files_to_read: list[str]
    similar_repos_query: str
    web_queries: list[str]   # 2-3 запроса в Tavily

class State(TypedDict):
    repo_url: str

    meta: RepoMeta
    plan: Plan

    code_findings:  Annotated[list[CodeFinding], add]
    similar_repos:  Annotated[list[SimilarRepo], add]
    web_snippets:   Annotated[list[WebSnippet], add]

    reflection_iteration: int
    gaps: list[str]

    report_markdown: str
```

## Контракты узлов

| Узел | Читает | Пишет | Side effects |
|------|--------|-------|--------------|
| `fetch_meta` | `repo_url` | `meta` | GitHub API (3-4 calls) |
| `plan` | `meta` | `plan` | 1 LLM call (structured output) |
| `analyze_code` | `meta`, `plan.files_to_read` | `code_findings` (append) | GitHub raw + LLM на файл |
| `find_similar_repos` | `plan.similar_repos_query` | `similar_repos` (append) | GitHub Search + LLM |
| `web_context` | `plan.web_queries` | `web_snippets` (append) | Tavily + LLM фильтр |
| `reflect` | весь накопленный state | `gaps`, `reflection_iteration++` | 1 LLM call |
| `synthesize` | весь state | `report_markdown` | 1 LLM call + запись файла |

**Принцип:** каждый узел — чистая функция `State → partial State dict`. I/O изолировано в `tools/`. LLM-промпты изолированы в `prompts/`.

## Data flow по узлам

### `fetch_meta` — без LLM, чистый I/O

- `GET /repos/{owner}/{name}` → description, stars, language, topics
- `GET /repos/{owner}/{name}/readme` → README (decoded base64)
- `GET /repos/{owner}/{name}/git/trees/HEAD?recursive=1` → file_tree

Manifest парсится локально: ищется первый из `package.json`, `pyproject.toml`, `Cargo.toml`, `go.mod`, `pom.xml`, `build.gradle`. Сырой контент через GitHub raw, парсинг — стандартными библиотеками.

### `plan` — 1 LLM-вызов с structured output

Получает `meta` (включая первые ~3000 символов README и список файлов до 500 путей). LLM возвращает валидный `Plan` через `with_structured_output(Plan)`:

- 5–15 ключевых файлов для чтения (entry points, основные модули, CI/Docker)
- query для GitHub Search для похожих репозиториев
- 2–3 веб-запроса для контекста

### `analyze_code` (параллельная ветка)

Цикл по `plan.files_to_read`:

1. GET сырого содержимого через GitHub raw API.
2. Если файл > 50KB — обрезаем до 50KB.
3. LLM-вызов: "опиши, что делает файл, отметь явные проблемы качества". Returns `CodeFinding`.
4. Append в `code_findings`.

В V1 файлы читаются последовательно. Async-параллелизм — V2 при необходимости.

### `find_similar_repos` (параллельная ветка)

- `GET /search/repositories?q={query}&sort=stars&per_page=10`
- Для каждого top-10 репо короткий LLM-вызов: "сравни target и candidate, в чём похожи и чем candidate отличается".
- Сохраняем 3-5 самых релевантных как `SimilarRepo`.

### `web_context` (параллельная ветка)

Для каждого `web_query`:

1. `tavily.search(query, max_results=5)` — возвращает уже сжатые сниппеты.
2. LLM фильтрует мусор: "какие сниппеты реально полезны для анализа {target}".
3. Append в `web_snippets`.

### `reflect` — 1 LLM-вызов

Промпт: "хватит ли собранных данных для трёх разделов отчёта?"

Возвращает либо `{"sufficient": true}`, либо `{"sufficient": false, "gaps": [...], "rerun": "code|similar|web"}`.

Conditional edge:

- `sufficient=true` или `iteration >= 1` → `synthesize`
- иначе → `Send` обратно на нужную ветку с уточнённым подзапросом

### `synthesize` — финальный LLM-вызов

Собирает весь state в один промпт, просит Claude написать markdown с обязательной структурой:

```markdown
# Анализ репо {owner/name}

## 1. Tech due-diligence
- Краткое резюме что это
- Качество кода (на основе code_findings)
- Активность, экосистема (stars, манифест, similar_repos)
- Стоит ли использовать: вердикт + альтернативы

## 2. Рекомендации автору
- Конкретные улучшения кода
- Чего не хватает по сравнению с similar_repos
- Документация / DX-проблемы

## 3. Идеи поверх технологии
- Применения, которых ещё не видно в нише
- Возможные продуктовые надстройки

## Источники
{все use'd URLs}
```

Запись в `reports/{owner}-{name}-{date}.md`.

## Обработка ошибок

| Сценарий | Действие |
|----------|----------|
| GitHub 404 (репо нет/приватный) | Явный fail, `sys.exit(1)` |
| GitHub 403 rate-limit | Sleep до `X-RateLimit-Reset`, одна попытка, потом fail |
| GitHub 5xx | Retry экспобэкоффом 3 раза (`tenacity`) |
| Tavily timeout/error | Не критично — `web_snippets=[]`, продолжаем |
| LLM кривой structured output | LangChain ретраит сам; после 2 попыток — лог и пустой результат |
| Binary content в файле | Skip с пометкой |
| Огромный репо (>5000 файлов) | `file_tree` для LLM ограничен первыми 500 путями, `files_to_read` ≤ 15 |

**Принцип:** агент не падает целиком из-за частичного провала. Один источник упал → отчёт на двух остальных, gap честно отмечен в разделе "Источники / Ограничения".

## Структура проекта

```
lang-graph/
├── README.md
├── pyproject.toml
├── .env.example
├── .gitignore
│
├── src/
│   └── repo_analyzer/
│       ├── __init__.py
│       ├── __main__.py             # entry: python -m repo_analyzer <url>
│       ├── cli.py                  # argparse, парсинг URL, запуск графа
│       │
│       ├── graph.py                # построение LangGraph
│       ├── state.py                # все TypedDict
│       │
│       ├── nodes/                  # один файл = один узел
│       │   ├── fetch_meta.py
│       │   ├── plan.py
│       │   ├── analyze_code.py
│       │   ├── find_similar.py
│       │   ├── web_context.py
│       │   ├── reflect.py
│       │   └── synthesize.py
│       │
│       ├── tools/                  # I/O, изолированно
│       │   ├── github.py
│       │   └── tavily.py
│       │
│       ├── prompts/                # все LLM-промпты
│       │   ├── plan.py
│       │   ├── analyze_code.py
│       │   ├── reflect.py
│       │   └── synthesize.py
│       │
│       └── llm.py                  # singleton ChatAnthropic
│
├── tests/
│   ├── conftest.py
│   ├── test_nodes/
│   ├── test_graph_smoke.py
│   └── fixtures/
│
└── reports/                        # в .gitignore
```

**Принципы:**

- Один узел = один файл. Узел — функция `def fetch_meta(state: State) -> dict:`.
- Промпты отдельно от логики (часто меняются независимо).
- I/O изолирован в `tools/` — мокаем именно его.
- Граф собирается в `graph.py` — после прочтения этого файла понятно "как всё работает".

**Зависимости (pyproject.toml):**

```toml
dependencies = [
    "langgraph>=0.2",
    "langchain-anthropic>=0.3",
    "httpx>=0.27",
    "tavily-python>=0.5",
    "python-dotenv>=1.0",
    "tenacity>=9.0",
]

[dependency-groups]
dev = [
    "pytest>=8.0",
    "pytest-asyncio>=0.24",
    "respx>=0.21",
]
```

## Тестирование

### Уровень 1 — Unit-тесты узлов (основная масса)

Каждый узел — чистая функция. Подсовываем input-state и моки, проверяем output. Покрываем happy path + 1-2 ошибочных кейса на узел. `tools/github.py` через `respx`. `tools/tavily.py` через подмену клиента.

### Уровень 2 — Smoke-test графа

Граф собирается, прогоняется с замоканными API/LLM, проверяется что финальный `report_markdown` содержит все три обязательные секции и что параллельные ветки корректно сошлись.

### Уровень 3 — End-to-end на реальных API

Один тест с `@pytest.mark.live` на маленьком публичном репо. Запускается руками, не в обычном `pytest`. Проверяет: ключи рабочие, реальный Claude отдаёт валидный structured output, отчёт записан, время < 5 минут.

### Что не тестируем

- Содержание LLM-ответов ("Claude должен сказать, что код хорош"). Нестабильно.
- Идентичность отчётов от запуска к запуску.
- Производительность как unit-test.

### Подход к разработке

V1 — учебный проект, строгий TDD не нужен. Подход: пишем узел → 1-2 теста на критичные кейсы → следующий узел. Когда граф собран — smoke-test графа. Большую часть feedback'a даёт ручной прогон + чтение отчёта глазами.

## План развития (V2 и далее, не в скоупе V1)

- Async-параллелизм внутри `analyze_code` (asyncio.gather по файлам)
- RAG-индексирование репозитория для глубокого анализа кода
- Streamlit web UI
- Persistence через `MemorySaver` / `SqliteSaver` для возобновления прерванных запусков
- Supervisor-паттерн поверх текущей архитектуры для адаптивного выбора стратегии
