#!/usr/bin/env python3
#
# Unit tests for aiko_chat's LLM loader (src/aiko_chat/llm.py).
#
# The langchain clients are replaced with mock factories, so these tests only
# assert that each backend is constructed with the parameters resolved from the
# explicit arguments and documented environment variables.

import sys
import types
from unittest.mock import Mock

import pytest

from aiko_chat import llm

PROVIDERS = [
    pytest.param("ollama", "OllamaLLM", "OLLAMA_MODEL", dict(base_url=None), id="ollama"),
    pytest.param("openai", "ChatOpenAI", "OPENAI_MODEL", dict(base_url=None, api_key=None), id="openai"),
]


@pytest.fixture(autouse=True)
def _clear_test_env(monkeypatch):
    """Prevent the local environment from polluting the tests."""
    for name in ("AIKO_LLM_TEMP", "OLLAMA_MODEL", "OLLAMA_HOST", "OPENAI_MODEL", "OPENAI_API_KEY", "OPENAI_BASE_URL"):
        monkeypatch.delenv(name, raising=False)


@pytest.fixture
def factories(monkeypatch):
    """Replace the optional LLM client packages with mock factories.

    llm_load() imports the modules it needs lazily, and we don't require them
    to run the tests.  Fake the imports, and return mocks instead; we'll
    then inspect them to make sure we're calling things correctly.
    """
    chat_openai = Mock(name="ChatOpenAI")
    ollama_llm = Mock(name="OllamaLLM")

    openai_error = type("OpenAIError", (Exception,), {})
    openai_module = types.ModuleType("openai")
    openai_module.OpenAIError = openai_error
    langchain_openai = types.ModuleType("langchain_openai")
    langchain_openai.ChatOpenAI = chat_openai
    langchain_ollama = types.ModuleType("langchain_ollama")
    langchain_ollama.OllamaLLM = ollama_llm

    monkeypatch.setitem(sys.modules, "openai", openai_module)
    monkeypatch.setitem(sys.modules, "langchain_openai", langchain_openai)
    monkeypatch.setitem(sys.modules, "langchain_ollama", langchain_ollama)

    return types.SimpleNamespace(ChatOpenAI=chat_openai, OllamaLLM=ollama_llm, OpenAIError=openai_error)


@pytest.mark.parametrize("provider, factory, model_env, extra_kwargs", PROVIDERS)
@pytest.mark.parametrize(
    "from_env, from_arg, expected",
    [
        pytest.param(None, None, llm.LLM_TEMPERATURE, id="default"),
        pytest.param("0.75", None, 0.75, id="env"),
        pytest.param("not-a-number", None, llm.LLM_TEMPERATURE, id="invalid-ignored"),
        pytest.param("0.75", 1.25, 1.25, id="arg-wins"),
    ],
)
def test_temperature(factories, monkeypatch, provider, factory, model_env, extra_kwargs, from_env, from_arg, expected):
    params = dict(model_name=llm.LLM_MODEL_NAME, temperature=expected, **extra_kwargs)
    if from_env is not None:
        monkeypatch.setenv("AIKO_LLM_TEMP", from_env)

    llm.llm_load(provider, llm_temp=from_arg)
    getattr(factories, factory).assert_called_once_with(**params)

@pytest.mark.parametrize("provider, factory, model_env, extra_kwargs", PROVIDERS)
@pytest.mark.parametrize(
    "from_env, from_arg, expected",
    [
        pytest.param(None, None, llm.LLM_MODEL_NAME, id="default"),
        pytest.param("from-env", None, "from-env", id="env"),
        pytest.param("from-env", "from-arg", "from-arg", id="arg-wins"),
    ],
)
def test_model_name(factories, monkeypatch, provider, factory, model_env, extra_kwargs, from_env, from_arg, expected):
    params = dict(model_name=expected, temperature=llm.LLM_TEMPERATURE, **extra_kwargs)
    if from_env is not None:
        monkeypatch.setenv(model_env, from_env)

    llm.llm_load(provider, model_name=from_arg)
    getattr(factories, factory).assert_called_once_with(**params)


def test_openai_connection_parameters(factories, monkeypatch):
    provider = "openai"
    params = dict(model_name="gpt-test", temperature=0.5, api_key="sk-test", base_url="http://openai.local/v1")

    monkeypatch.setenv("OPENAI_API_KEY", params["api_key"])
    monkeypatch.setenv("OPENAI_BASE_URL", params["base_url"])

    llm.llm_load(provider, model_name=params["model_name"], llm_temp=params["temperature"])
    factories.ChatOpenAI.assert_called_once_with(**params)


def test_ollama_connection_parameters(factories, monkeypatch):
    provider = "ollama"
    params = dict(model_name="llama-test", temperature=0.5, base_url="http://ollama.local:11434")

    monkeypatch.setenv("OLLAMA_HOST", params["base_url"])

    llm.llm_load(provider, model_name=params["model_name"], llm_temp=params["temperature"])
    factories.OllamaLLM.assert_called_once_with(**params)


def test_returns_first_working_backend(factories):
    provider_preference = ("openai", "ollama")
    model = "openai-model"

    factories.ChatOpenAI.return_value = model

    actual_result = llm.llm_load(*provider_preference)

    assert actual_result == model
    factories.ChatOpenAI.assert_called_once()
    factories.OllamaLLM.assert_not_called()


def test_falls_back_to_ollama_when_openai_fails(factories):
    provider_preference = ("openai", "ollama")
    openai_error_message = "unavailable"
    model = "ollama-model"

    factories.ChatOpenAI.side_effect = factories.OpenAIError(openai_error_message)
    factories.OllamaLLM.return_value = model

    actual_result = llm.llm_load(*provider_preference)

    assert actual_result == model
    factories.ChatOpenAI.assert_called_once()
    factories.OllamaLLM.assert_called_once()


def test_unknown_backend_raises_system_exit(factories):
    unknown_provider = "bogus"
    expected_error = "FATAL: Could not load LLM"

    with pytest.raises(SystemExit, match=expected_error):
        llm.llm_load(unknown_provider)
