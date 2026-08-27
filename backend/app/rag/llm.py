from abc import ABC, abstractmethod

from app.config import get_settings


class LLMProvider(ABC):
    @abstractmethod
    def generate(self, prompt: str) -> str:
        ...


class OllamaProvider(LLMProvider):
    """Free, local LLM via Ollama. Default provider -- no API key required."""

    def __init__(self, base_url: str, model: str):
        self._base_url = base_url
        self._model = model

    def generate(self, prompt: str) -> str:
        import httpx

        response = httpx.post(
            f"{self._base_url}/api/generate",
            json={"model": self._model, "prompt": prompt, "stream": False},
            timeout=60.0,
        )
        response.raise_for_status()
        return response.json()["response"]


class OpenAIProvider(LLMProvider):
    """Stub for future use -- swap in via LLM_PROVIDER=openai once API
    credits are available."""

    def __init__(self, api_key: str, model: str = "gpt-4o-mini"):
        self._api_key = api_key
        self._model = model

    def generate(self, prompt: str) -> str:
        from openai import OpenAI

        client = OpenAI(api_key=self._api_key)
        response = client.chat.completions.create(
            model=self._model,
            messages=[{"role": "user", "content": prompt}],
        )
        return response.choices[0].message.content


def get_llm_provider() -> LLMProvider:
    settings = get_settings()
    if settings.llm_provider == "openai":
        return OpenAIProvider(settings.openai_api_key)
    return OllamaProvider(settings.ollama_base_url, settings.ollama_model)
