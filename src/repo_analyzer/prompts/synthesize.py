PROMPT = """You are writing a final analysis report for repo {owner}/{name}.

DATA COLLECTED:

Description: {description}
Language: {language}
Stars: {stars}
README excerpt:
{readme}

Code findings:
{code_findings}

Similar repos:
{similar_repos}

Web context:
{web_snippets}

Known data gaps (be honest about these):
{gaps}

Write a markdown report in Russian with EXACTLY this structure:

# Анализ репо {owner}/{name}

## 1. Tech due-diligence
- Краткое резюме что это
- Качество кода
- Активность и экосистема
- Стоит ли использовать: вердикт + альтернативы

## 2. Рекомендации автору
- Конкретные улучшения кода
- Чего не хватает по сравнению с похожими проектами
- Документация / DX-проблемы

## 3. Идеи поверх технологии
- Применения, которых ещё не видно в нише
- Возможные продуктовые надстройки

## Источники и ограничения
- Все упомянутые URL
- Что не удалось собрать (data gaps)

Be concrete and specific. Cite paths and URLs. No hedging fluff. If gaps exist, list them in the last section.
"""
