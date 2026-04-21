from __future__ import annotations

from hermes.app.settings import Settings


class ModelCatalogService:
    def __init__(self, settings: Settings):
        self._settings = settings

    def list_models(self) -> list[dict[str, str | int | bool]]:
        active_model = self._settings.model_name
        return [
            {
                "id": active_model,
                "name": active_model,
                "provider": "configured",
                "context_size": self._settings.context_window,
                "is_available": True,
            }
        ]
