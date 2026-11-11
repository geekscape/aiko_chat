# Adapted from: https://github.com/0xDEC0DE/aiko_services/blob/issue/67/src/aiko_services/examples/llm/elements.py

import contextlib
import os

LLM_MODEL_NAME = "gemma4:latest"  # e4b
LLM_TEMPERATURE = 0.0


# --------------------------------------------------------------------------- #


def llm_load(*llm_types, model_name=None, llm_temp=None):
    if llm_temp is None:
        llm_temp = LLM_TEMPERATURE
        if "AIKO_LLM_TEMP" in os.environ:
            with contextlib.suppress(ValueError):
                llm_temp = float(os.environ["AIKO_LLM_TEMP"])

    for llm_type in llm_types:
        try:
            if llm_type == "openai":
                from openai import OpenAIError
                from langchain_openai import ChatOpenAI

                OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY")
                OPENAI_BASE_URL = os.environ.get("OPENAI_BASE_URL")
                with contextlib.suppress(OpenAIError):
                    return ChatOpenAI(
                        model_name=model_name or os.environ.get("OPENAI_MODEL", LLM_MODEL_NAME),
                        temperature=llm_temp,
                        base_url=OPENAI_BASE_URL,
                        api_key=OPENAI_API_KEY,
                    )
            elif llm_type == "ollama":
                from langchain_ollama import OllamaLLM

                OLLAMA_HOST = os.environ.get("OLLAMA_HOST")
                return OllamaLLM(
                    model_name=model_name or os.environ.get("OLLAMA_MODEL", LLM_MODEL_NAME),
                    temperature=llm_temp,
                    base_url=OLLAMA_HOST,
                )
            else:
                raise ImportError("Unknown model")
        except ImportError:
            continue

    raise SystemExit(f"FATAL: Could not load LLM, tried: {llm_types}")
