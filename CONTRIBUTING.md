# Contributing

Спасибо за интерес к проекту. Это учебный репозиторий, и любая помощь приветствуется — от опечатки в README до новой ноды в графе.

## Установка локального окружения

```bash
git clone https://github.com/nozikov/github-repo-analyzer.git
cd github-repo-analyzer
uv sync
cp .env.example .env
# открой .env и впиши три ключа: ANTHROPIC_API_KEY, GITHUB_TOKEN, TAVILY_API_KEY
```

Минимальный Python — 3.11. Менеджер пакетов — [uv](https://github.com/astral-sh/uv).

## Тесты

```bash
uv run pytest -v          # все юнит и smoke тесты с моками — быстро, без API-ключей
uv run pytest -m live -s  # реальные API — медленно, требует ключи в .env
```

Live-тест по умолчанию скипается через `addopts = "-m 'not live'"` в `pyproject.toml`. Запускать его нужно вручную — он совершает реальные вызовы к Claude, GitHub и Tavily.

CI (GitHub Actions) прогоняет юнит-тесты на Python 3.11 и 3.12 на каждый push и PR. Live-тесты в CI не запускаются.

## Где менять что

Вся логика — в `src/repo_analyzer/`. Структура и контракты узлов описаны в [docs/architecture.md](docs/architecture.md).

| Хочешь изменить | Смотри сюда |
|---|---|
| Текст промпта (например, как формулируется due-diligence) | `src/repo_analyzer/prompts/<node>.py` |
| Логику узла | `src/repo_analyzer/nodes/<node>.py` |
| Топологию графа (порядок, новые рёбра) | `src/repo_analyzer/graph.py` |
| Модель данных | `src/repo_analyzer/state.py` |
| Обращение к GitHub/Tavily | `src/repo_analyzer/tools/` |
| LLM-провайдера или модель | `src/repo_analyzer/llm.py` |

Принцип: узел — чистая функция `State → partial State`. I/O мокаются через моки `tools/`, LLM — через подмену `get_chat_model`. Подробности в существующих тестах в `tests/test_nodes/`.

## Как открыть PR

1. Форкни репозиторий и создай ветку с осмысленным именем (`feat/...`, `fix/...`, `docs/...`).
2. Сделай изменения. Если меняешь поведение — добавь или поправь тест.
3. Прогони `uv run pytest -v` локально — должно быть зелено.
4. Открой PR в `main`. CI запустится автоматически.
5. Merge возможен только при зелёном CI на обеих версиях Python (защищённая ветка).

## Стиль коммитов

Conventional Commits: `feat:`, `fix:`, `docs:`, `refactor:`, `chore:`, `test:`, `ci:`. Сообщение в одну строку, императив, без точки в конце. Например:

```
feat: add Context7 lookup in analyze_code
fix: handle 403 rate-limit with sleep
```

История проекта в `git log` — хороший референс.

## Идеи и обсуждения

Конкретные баги — issues. Идеи фич — issues с лейблом `discussion` или просто открытый PR с черновиком. Список запланированных направлений в секции [Roadmap](docs/architecture.md#roadmap-v2-и-далее) архитектурного документа.
