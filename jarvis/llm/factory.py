from __future__ import annotations

from ..state import UserState
from .base import LLM


def create_llm(user: UserState) -> LLM:
    provider = user.provider

    if provider == "anthropic":
        if not user.anthropic_api_key:
            raise RuntimeError("Anthropic API 키가 설정되지 않았습니다.")
        from .anthropic_provider import AnthropicLLM

        return AnthropicLLM(api_key=user.anthropic_api_key, model=user.anthropic_model)

    if provider == "openai":
        if not user.openai_api_key:
            raise RuntimeError("OpenAI API 키가 설정되지 않았습니다.")
        from .openai_provider import OpenAILLM

        return OpenAILLM(api_key=user.openai_api_key, model=user.openai_model)

    if provider == "ollama":
        from .ollama_provider import OllamaLLM

        return OllamaLLM(host=user.ollama_host, model=user.ollama_model)

    if provider == "gemini":
        if not user.gemini_api_key:
            raise RuntimeError("Gemini API 키가 설정되지 않았습니다.")
        from .gemini_provider import GeminiLLM

        return GeminiLLM(api_key=user.gemini_api_key, model=user.gemini_model)

    raise ValueError(f"알 수 없는 provider: {provider}")
