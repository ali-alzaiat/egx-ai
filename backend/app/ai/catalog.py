"""Curated model list (R49 A5): Claude, OpenAI and Gemini models that support tool calling.

Each entry must exist in LiteLLM 1.105.1's ``model_cost`` map with ``mode == "chat"``,
``supports_function_calling`` and a token price; a test asserts it. The list is code on
purpose: a new model is added here on purpose, never picked up from a provider listing.
"""

from dataclasses import dataclass

PROVIDERS = ("anthropic", "openai", "gemini")

PROVIDER_LABELS = {
    "anthropic": "Anthropic (Claude)",
    "openai": "OpenAI",
    "gemini": "Google Gemini",
}

#: Environment settings that hold each provider's fallback key.
ENV_KEY_SETTING = {
    "anthropic": "ANTHROPIC_API_KEY",
    "openai": "OPENAI_API_KEY",
    "gemini": "GEMINI_API_KEY",
}


@dataclass(frozen=True)
class CatalogModel:
    id: str
    label: str
    provider: str
    #: The vendor's own web search can be switched on through LiteLLM ``web_search_options``
    #: (R50 B3). Only entries LiteLLM 1.105.1 can search with are true; a test asserts it.
    web_search: bool = False

    @property
    def litellm_model(self) -> str:
        """The model string handed to LiteLLM (always provider-prefixed)."""
        return f"{self.provider}/{self.id}"

    @property
    def cost_key(self) -> str:
        """The key of this model in LiteLLM's ``model_cost`` map."""
        return f"gemini/{self.id}" if self.provider == "gemini" else self.id


# Order matters: the first available model becomes the default when none is saved.
CATALOG: tuple[CatalogModel, ...] = (
    CatalogModel("claude-sonnet-5-5", "Claude Sonnet 5.5", "anthropic", web_search=True),
    CatalogModel("claude-opus-5-5", "Claude Opus 5.5", "anthropic", web_search=True),
    # claude-haiku-5-5 is not in LiteLLM 1.105.1's cost map; haiku 4.5 is the newest Haiku there.
    CatalogModel("claude-haiku-4-5", "Claude Haiku 4.5", "anthropic"),
    CatalogModel("gpt-5.5", "GPT-5.5", "openai"),
    CatalogModel("gpt-5.4-mini", "GPT-5.4 mini", "openai"),
    CatalogModel("gemini-3.1-pro-preview", "Gemini 3.1 Pro (preview)", "gemini", web_search=True),
    CatalogModel("gemini-3.5-flash-lite", "Gemini 3.5 Flash-Lite", "gemini", web_search=True),
)

_BY_ID = {m.id: m for m in CATALOG}

#: The cheapest model of each provider, used for the one-token key check.
KEY_TEST_MODEL = {
    "anthropic": "claude-haiku-4-5",
    "openai": "gpt-5.4-mini",
    "gemini": "gemini-3.5-flash-lite",
}


def get_model(model_id: str) -> CatalogModel | None:
    return _BY_ID.get(model_id)


def models_for(provider: str) -> list[CatalogModel]:
    return [m for m in CATALOG if m.provider == provider]
