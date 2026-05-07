import os
from unittest.mock import patch

from repo_analyzer import llm as llm_module


def test_get_chat_model_returns_claude_sonnet():
    with patch.dict(os.environ, {"ANTHROPIC_API_KEY": "sk-test"}):
        llm_module._cached = None  # reset singleton
        model = llm_module.get_chat_model()
    assert "claude-sonnet-4-6" in model.model


def test_get_chat_model_is_singleton():
    with patch.dict(os.environ, {"ANTHROPIC_API_KEY": "sk-test"}):
        llm_module._cached = None
        a = llm_module.get_chat_model()
        b = llm_module.get_chat_model()
    assert a is b
