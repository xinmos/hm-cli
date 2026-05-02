from __future__ import annotations

from dataclasses import dataclass, replace
from pathlib import Path
import sys

_project_root = Path(__file__).parent.parent.parent.parent
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))

from hermes.app import InteractionPort
from hermes.app.bootstrap import ControlPlaneApp, ControlPlaneRuntime, assemble_control_plane
from hermes.app.settings import Settings
from hermes.infra.persistence.json_chat_store import JsonChatStore
from hermes.services import ChatService, LLMConfigService, ModelCatalogService, ProjectService


@dataclass(frozen=True)
class WebServiceContainer:
    settings: Settings
    chat_service: ChatService
    llm_config: LLMConfigService
    model_catalog: ModelCatalogService
    project_service: ProjectService

    def create_control_plane(
        self,
        interaction_port: InteractionPort | None = None,
        model_name: str | None = None,
    ) -> tuple[ControlPlaneApp, ControlPlaneRuntime]:
        config = self.llm_config.get_effective_config()
        if model_name:
            config = replace(config, model=model_name)
        settings = self.settings.with_llm_config(config)
        return assemble_control_plane(
            settings=settings,
            interaction_port=interaction_port,
        )


def build_web_services() -> WebServiceContainer:
    settings = Settings.from_env_and_args()
    llm_config = LLMConfigService(settings)
    chat_store = JsonChatStore(settings.workdir / ".hermes" / "web")
    return WebServiceContainer(
        settings=settings,
        chat_service=ChatService(chat_store),
        llm_config=llm_config,
        model_catalog=ModelCatalogService(llm_config),
        project_service=ProjectService(settings),
    )
