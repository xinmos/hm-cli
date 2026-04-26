from __future__ import annotations

from hermes.services.llm_config_service import LLMConfigService


class ModelCatalogService:
    def __init__(self, llm_config: LLMConfigService):
        self._llm_config = llm_config

    def list_models(self) -> list[dict[str, str | int | bool]]:
        config = self._llm_config.get_effective_config()
        models = config.custom_models or [config.model]
        return [
            {
                "id": model,
                "name": model,
                "provider": "custom" if model != config.model else config.provider,
                "context_size": 0,
                "is_available": True,
            }
            for model in models
        ]
