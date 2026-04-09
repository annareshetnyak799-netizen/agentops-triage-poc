from src.config import settings
from src.llm.factory import create_llm_adapter
from src.llm.mock_adapter import MockLLMAdapter
from src.llm.openai_adapter import OpenAIRealLLMAdapter


def test_llm_factory_returns_mock_adapter_by_default() -> None:
    adapter = create_llm_adapter()
    assert isinstance(adapter, MockLLMAdapter)


def test_openai_adapter_class_is_available() -> None:
    assert OpenAIRealLLMAdapter is not None
    assert settings is not None

