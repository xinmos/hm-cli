from pathlib import Path
from typing import Any

from hermes.app.ports import (
    AgentBackend,
    InteractionPort,
    SchedulerDriver,
    SkillRepository,
    TaskStore,
    ToolCatalog,
)
from hermes.app.settings import Settings
from hermes.core.agent import AgentSession
from hermes.infra.langchain.backend import LangChainOpenAIBackend
from hermes.infra.langchain.tools import LangChainToolCatalog
from hermes.infra.persistence.file_skill_repo import FileSkillRepository
from hermes.infra.persistence.json_task_store import JsonTaskStore
from hermes.infra.scheduler.apscheduler_driver import APSchedulerDriver
from hermes.services.skill_service import SkillService
from hermes.services.task_service import TaskService


class ControlPlaneApp:
    def __init__(
        self,
        settings: Settings,
        agent_session: AgentSession,
        skill_service: SkillService,
        task_service: TaskService,
        interaction_port: InteractionPort | None = None,
    ):
        self.settings = settings
        self.agent = agent_session
        self.skills = skill_service
        self.tasks = task_service
        self.interaction = interaction_port

    def handle(self, command: str, args: str = "") -> Any:
        if command.startswith("/"):
            return self._handle_slash_command(command, args)
        return self._handle_message(command)

    def _handle_slash_command(self, cmd: str, args: str) -> dict[str, Any]:
        skill = self.skills.get_by_slash_command(cmd)
        if skill:
            full_prompt = self._build_skill_prompt(skill.instructions, args)
            return {"type": "skill", "skill": skill.name, "response": list(self.agent.run_stream(full_prompt))}

        if cmd == "/exit":
            return {"type": "control", "action": "exit"}
        elif cmd == "/clear":
            return {"type": "control", "action": "clear"}
        elif cmd == "/reset":
            self.agent.reset()
            return {"type": "control", "action": "reset"}
        elif cmd == "/help":
            return {"type": "control", "action": "help"}
        elif cmd == "/skills":
            return {"type": "list_skills", "skills": self.skills.list_skills()}
        elif cmd == "/task":
            return {"type": "task_management"}
        elif cmd == "/compress":
            return {"type": "compress"}
        else:
            return {"type": "error", "message": f"Unknown command: {cmd}"}

    def _handle_message(self, message: str) -> dict[str, Any]:
        response_chunks = list(self.agent.run_stream(message))
        return {"type": "message", "response": "".join(response_chunks)}

    def _build_skill_prompt(self, instructions: str, args: str) -> str:
        if "$ARGUMENTS" in instructions and args:
            return instructions.replace("$ARGUMENTS", args)
        elif args:
            return f"{instructions}\n\n用户输入: {args}"
        return instructions


def bootstrap(
    env_file: Path | None = None,
    interaction_port: InteractionPort | None = None,
) -> ControlPlaneApp:
    settings = Settings.from_env_and_args(env_file=env_file)

    skill_repo: SkillRepository = FileSkillRepository(settings.workdir)
    task_store: TaskStore = JsonTaskStore(settings.tasks_path)

    skill_service = SkillService(skill_repo)

    agent_backend: AgentBackend = LangChainOpenAIBackend(
        api_key=settings.openai_api_key,
        base_url=settings.openai_base_url,
        model_name=settings.model_name,
        temperature=settings.temperature,
    )

    tool_catalog: ToolCatalog = LangChainToolCatalog(
        settings=settings,
        skill_repository=skill_repo,
        interaction_port=interaction_port,
    )

    agent_session = AgentSession(
        backend=agent_backend,
        system_prompt=_build_system_prompt(skill_repo),
        interaction_port=interaction_port,
    )
    agent_session.set_tools(tool_catalog.get_tools())

    scheduler_driver: SchedulerDriver = APSchedulerDriver()
    scheduler_driver.start()

    task_service = TaskService(task_store, scheduler_driver)
    task_service.load_persistent_tasks()

    return ControlPlaneApp(
        settings=settings,
        agent_session=agent_session,
        skill_service=skill_service,
        task_service=task_service,
        interaction_port=interaction_port,
    )


def _build_system_prompt(skill_repo: SkillRepository) -> str:
    prompt_path = Path(__file__).parent.parent / "prompts" / "system.md"
    base_prompt = ""
    if prompt_path.exists():
        base_prompt = prompt_path.read_text(encoding="utf-8")

    skills = skill_repo.list_skills()
    if not skills:
        return base_prompt

    skill_section = "\n\n## 可用技能\n\n"
    for skill in skills:
        skill_section += f"- {skill.name}: {skill.description}\n"

    skill_section += "\n当需要使用某个 skill 时，先调用 `load_skill` 工具获取完整指令。"

    return base_prompt + skill_section
