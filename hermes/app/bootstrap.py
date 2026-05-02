from __future__ import annotations

import asyncio
import threading
from pathlib import Path
from typing import Any

from hermes.app.ports import (
    AgentBackend,
    InteractionPort,
    Message,
    SchedulerDriver,
    SkillRepository,
    TaskStore,
    ToolCatalog,
)
from hermes.app.settings import Settings
from hermes.core.agent import AgentSession
from hermes.core.memory.memory_manager import MemoryManager
from hermes.core.memory.models import MemoryConfig
from hermes.core.soul import SoulIdentity, SoulLoader
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
        soul_loader: SoulLoader,
        soul: SoulIdentity | None = None,
        interaction_port: InteractionPort | None = None,
        memory_manager: MemoryManager | None = None,
        base_system_prompt: str | None = None,
    ):
        self.settings = settings
        self.agent = agent_session
        self.skills = skill_service
        self.tasks = task_service
        self.soul_loader = soul_loader
        self.soul = soul
        self.interaction = interaction_port
        self.memory = memory_manager
        self._base_system_prompt = base_system_prompt or _build_system_prompt_base(settings, skill_repo=None)

    def set_soul(self, soul: SoulIdentity) -> None:
        self.soul = soul
        combined_prompt = self._build_full_system_prompt()
        self.agent.set_system_prompt(combined_prompt)

    def list_available_souls(self) -> list[str]:
        return self.soul_loader.list_souls()

    def load_soul(self, name: str) -> SoulIdentity | None:
        return self.soul_loader.load(name)

    def _build_full_system_prompt(self) -> str:
        if self.soul:
            soul_prompt = self.soul.to_system_prompt()
            return f"{self._base_system_prompt}\n\n---\n\n{soul_prompt}"
        return self._base_system_prompt

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
        return {"type": "message", "response": self._run_with_memory(message)}

    def _build_skill_prompt(self, instructions: str, args: str) -> str:
        if "$ARGUMENTS" in instructions and args:
            return instructions.replace("$ARGUMENTS", args)
        elif args:
            return f"{instructions}\n\n用户输入: {args}"
        return instructions

    def _run_with_memory(self, user_input: str):
        memory_context = ""
        if self.memory:
            try:
                context = _run_coroutine_sync(
                    self.memory.retrieve_relevant_context(
                        query=user_input,
                        max_tokens=2000,
                    )
                )
                if not context.is_empty():
                    memory_context = context.formatted_text
                    if self.interaction:
                        self.interaction.notify_tool_start("memory")
                        self.interaction.notify_tool_complete("memory")
            except Exception:
                pass

        messages = self.agent.get_messages()
        if memory_context and messages:
            enhanced_messages = []
            for msg in messages:
                enhanced_messages.append(msg)
                if msg.role == "system" and len(enhanced_messages) == 1:
                    enhanced_messages.append(
                        Message(role="system", content=f"[相关记忆]\n{memory_context}")
                    )
            messages = enhanced_messages

        full_response = ""
        for chunk in self.agent.run_stream_with_messages(user_input, messages):
            full_response += chunk
            yield chunk

        if self.memory:
            try:
                _run_coroutine_sync(
                    self.memory.process_interaction(
                        user_input=user_input,
                        agent_response=full_response,
                    )
                )
            except Exception:
                # 记忆保存失败不影响主流程
                pass


class ControlPlaneRuntime:
    def __init__(
        self,
        scheduler_driver: SchedulerDriver,
        task_service: TaskService,
        *,
        load_persistent_tasks: bool = True,
    ):
        self._scheduler_driver = scheduler_driver
        self._task_service = task_service
        self._load_persistent_tasks = load_persistent_tasks
        self._started = False

    def start(self) -> None:
        if self._started:
            return
        self._scheduler_driver.start()
        if self._load_persistent_tasks:
            self._task_service.load_persistent_tasks()
        self._started = True

    def stop(self) -> None:
        if not self._started:
            return
        self._scheduler_driver.shutdown()
        self._started = False


def assemble_control_plane(
    env_file: Path | None = None,
    settings: Settings | None = None,
    interaction_port: InteractionPort | None = None,
    soul_name: str | None = None,
) -> tuple[ControlPlaneApp, ControlPlaneRuntime]:
    if settings is None:
        settings = Settings.from_env_and_args(env_file=env_file)

    skill_repo: SkillRepository = FileSkillRepository(
        settings.workdir,
        llm_wiki_path=settings.llm_wiki_path,
    )
    task_store: TaskStore = JsonTaskStore(settings.tasks_path)

    skill_service = SkillService(skill_repo)

    souls_dir = settings.workdir / ".hermes" / "souls"
    soul_loader = SoulLoader(souls_dir)

    current_soul: SoulIdentity | None = None
    if soul_name:
        current_soul = soul_loader.load(soul_name)
    if not current_soul:
        current_soul = soul_loader.load("default")

    agent_backend: AgentBackend = LangChainOpenAIBackend(
        api_key=settings.openai_api_key,
        base_url=settings.openai_base_url,
        model_name=settings.model_name,
        temperature=settings.temperature,
        max_tokens=settings.max_tokens,
        timeout=settings.timeout,
        max_retries=settings.max_retries,
        top_p=settings.top_p,
        streaming=settings.streaming,
    )

    tool_catalog: ToolCatalog = LangChainToolCatalog(
        settings=settings,
        skill_repository=skill_repo,
        interaction_port=interaction_port,
    )

    base_prompt = _build_system_prompt_base(settings, skill_repo)
    full_system_prompt = base_prompt
    if current_soul:
        soul_prompt = current_soul.to_system_prompt()
        full_system_prompt = f"{base_prompt}\n\n---\n\n{soul_prompt}"

    agent_session = AgentSession(
        backend=agent_backend,
        system_prompt=full_system_prompt,
        interaction_port=interaction_port,
    )
    agent_session.set_tools(tool_catalog.get_tools())

    scheduler_driver: SchedulerDriver = APSchedulerDriver()
    task_service = TaskService(task_store, scheduler_driver)

    # 初始化记忆系统
    memory_config = MemoryConfig(
        db_path=str(settings.workdir / ".hermes" / "memory.db"),
        importance_threshold=3,
        max_working_messages=50,
    )
    memory_manager = MemoryManager(config=memory_config)

    app = ControlPlaneApp(
        settings=settings,
        agent_session=agent_session,
        skill_service=skill_service,
        task_service=task_service,
        soul_loader=soul_loader,
        soul=current_soul,
        interaction_port=interaction_port,
        memory_manager=memory_manager,
        base_system_prompt=base_prompt,
    )
    runtime = ControlPlaneRuntime(
        scheduler_driver=scheduler_driver,
        task_service=task_service,
    )
    return app, runtime


def bootstrap(
    env_file: Path | None = None,
    interaction_port: InteractionPort | None = None,
    soul_name: str | None = None,
) -> ControlPlaneApp:
    app, runtime = assemble_control_plane(
        env_file=env_file,
        interaction_port=interaction_port,
        soul_name=soul_name,
    )
    runtime.start()
    return app


def _build_system_prompt_base(settings: Settings | None, skill_repo: SkillRepository | None) -> str:
    prompt_path = Path(__file__).parent.parent / "prompts" / "system.md"
    base_prompt = ""
    if prompt_path.exists():
        base_prompt = prompt_path.read_text(encoding="utf-8")

    if settings is not None:
        base_prompt += (
            "\n\n## 项目设置\n"
            f"- llm-wiki 知识库路径: `{settings.llm_wiki_path}`\n"
            "- 当用户说“通过知识库回答”、“基于知识库回答”、“根据知识库”或类似表达时，"
            "先调用 `load_skill(\"llm-wiki\")` 获取完整指令；如果目录未初始化，按 skill 指令初始化，"
            "然后基于该知识库读取、检索并回答。"
        )

    if skill_repo is None:
        return base_prompt

    skills = skill_repo.list_skills()
    if not skills:
        return base_prompt

    skill_section = "\n## 可用技能\n"
    for skill in skills:
        skill_section += f"- {skill.name}: {skill.description}\n"

    return base_prompt + skill_section


def _run_coroutine_sync(coroutine: Any) -> Any:
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(coroutine)

    result: dict[str, Any] = {}
    error: dict[str, Exception] = {}

    def runner() -> None:
        try:
            result["value"] = asyncio.run(coroutine)
        except Exception as exc:  # pragma: no cover - defensive bridge for async callers
            error["value"] = exc

    thread = threading.Thread(target=runner, daemon=True)
    thread.start()
    thread.join()

    if "value" in error:
        raise error["value"]
    return result.get("value")
