from __future__ import annotations

from src.config import settings
from src.llm.base import BaseLLMAdapter
from src.llm.mock_adapter import MockLLMAdapter
from src.llm.openai_adapter import OpenAIRealLLMAdapter
from src.llm.real_adapter import RealLLMAdapter


def create_llm_adapter() -> BaseLLMAdapter:
    backend = settings.llm_backend.lower()

    if backend == "mock":
        return MockLLMAdapter()

    if backend == "real":
        provider = settings.llm_provider.lower()

        if provider == "openai":
            if not settings.llm_api_key:
                raise ValueError(
                    "AGENTOPS_LLM_API_KEY is required when "
                    "AGENTOPS_LLM_BACKEND=real and provider=openai."
                )
            return OpenAIRealLLMAdapter(
                model=settings.llm_model,
                api_key=settings.llm_api_key,
                timeout_s=settings.llm_timeout_s,
            )

        return RealLLMAdapter(
            provider=settings.llm_provider,
            model=settings.llm_model,
            api_key=settings.llm_api_key,
            timeout_s=settings.llm_timeout_s,
        )

    raise ValueError(
        f"Unsupported LLM backend: {settings.llm_backend}. "
        "Expected 'mock' or 'real'."
    )
