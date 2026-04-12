import sys
from pathlib import Path

from prompt_toolkit import prompt
from prompt_toolkit.completion import WordCompleter
from prompt_toolkit.history import InMemoryHistory
from rich.console import Console, RenderableType
from rich.padding import Padding
from rich.style import Style
from rich.text import Text
from rich.theme import Theme

from hermes.agents import HermesAgent
from hermes.config import Config
from hermes.scheduler import TaskScheduler
from hermes.skills import get_registry
from hermes.tools.confirm import set_confirm_callback


THEME = Theme({
    "prompt": Style(color="green", bold=True),
    "banner": Style(color="cyan", bold=True),
    "info": Style(color="blue"),
    "dim": Style(color="bright_black"),
    "error": Style(color="red"),
})


class HermesCLI:
    def __init__(self) -> None:
        self.console = Console(theme=THEME)
        self.agent = HermesAgent()
        self.commands: dict[str, callable] = {
            "/exit": self._exit,
            "/clear": self._clear,
            "/reset": self._reset,
            "/help": self._help,
            "/skills": self._skill_cmd,
            "/task": self._task_cmd,
            "/compress": self._compress_cmd,
        }
        self._skill_registry = get_registry()
        self._load_default_skills()
        self._scheduler = TaskScheduler()
        self._scheduler.start()
        self._current_tool: str | None = None

        self.agent.set_system_prompt(self._build_system_prompt())
        self.agent.set_tool_callback(self._on_tool_event)
        set_confirm_callback(self._confirm_operation)
        self.agent.set_compression_callback(self._on_context_compressed)
        self._completer = self._create_completer()
    
    def _build_system_prompt(self) -> str:
        prompt_path = Path(__file__).parent / "hermes" / "prompts" / "system.md"
        base_prompt = ""
        if prompt_path.exists():
            base_prompt = prompt_path.read_text(encoding="utf-8")

        skills = self._skill_registry.list_skills()
        if not skills:
            return base_prompt

        skill_section = "\n\n## 可用技能\n\n"
        for skill in skills:
            cmd = skill.slash_command or f"{skill.name}"
            skill_section += f"- {cmd}: {skill.description}\n"

        return base_prompt + skill_section

    def _banner(self) -> RenderableType:
        banner_ascii = """
╔═══════════════════════════════════════════════════╗
║                                                   ║
║   ██╗  ██╗███████╗██████╗ ███╗   ███╗███████╗    ║
║   ██║  ██║██╔════╝██╔══██╗████╗ ████║██╔════╝    ║
║   ███████║█████╗  ██████╔╝██╔████╔██║███████╗    ║
║   ██╔══██║██╔══╝  ██╔══██╗██║╚██╔╝██║╚════██║    ║
║   ██║  ██║███████╗██║  ██║██║ ╚═╝ ██║███████║    ║
║   ╚═╝  ╚═╝╚══════╝╚═╝  ╚═╝╚═╝     ╚═╝╚══════╝    ║
║                                                   ║
║              [      AI 助理       ]              ║
╚═══════════════════════════════════════════════════╝"""
        return Text(banner_ascii, style="cyan bold")

    def _config_info(self) -> RenderableType:
        text = Text()
        text.append(f"  Model:  ", style="dim")
        text.append(f"{Config.MODEL_NAME}\n", style="info")
        text.append(f"  Tools:  ", style="dim")
        text.append(f"{len(self.agent.tools)}\n", style="info")
        skills = self._skill_registry.list_skills()
        text.append(f"  Skills: ", style="dim")
        text.append(f"{len(skills)}\n", style="info")
        return Padding(text, (0, 0, 1, 0))
    
    
    def _show_welcome(self) -> None:
        self.console.print(self._banner())
        self.console.print(self._config_info())
        self.console.print("输入 /help 查看命令或直接输入消息\n", style="dim")
    
    def _clear(self) -> bool:
        self.console.clear()
        self._show_welcome()
        return True
    
    def _reset(self) -> bool:
        self.agent.reset()
        self.console.print("记忆已重置", style="dim")
        return True
    
    def _help(self) -> bool:
        help_text = """
[cyan]可用命令:[/]
  /exit         退出程序
  /clear        清屏
  /reset        重置对话记忆
  /skills        列出可用技能
  /task         定时任务管理 (add/list/remove)
  /compress     手动压缩上下文
  /help         显示帮助

[cyan]可用技能:[/] 使用 /<skill-name> [参数] 执行"""
        self.console.print(help_text)
        self._show_available_skills()
        return True
    
    def _load_default_skills(self) -> None:
        loaded = []

        builtin_dirs = [
            Config.WORKDIR / ".hermes" / "skills",
            Config.WORKDIR / "hermes" / "skills",
        ]
        for skills_dir in builtin_dirs:
            if skills_dir.exists():
                for subdir in skills_dir.iterdir():
                    if subdir.is_dir():
                        skill_md = subdir / "SKILL.md"
                        if skill_md.exists():
                            try:
                                skill = self._skill_registry.load_from_file(str(skill_md))
                                loaded.append(skill)
                            except Exception as e:
                                self.console.print(f"加载技能失败 {skill_md}: {e}", style="error")
                try:
                    batch = self._skill_registry.load_from_directory(str(skills_dir))
                    loaded.extend(batch)
                except Exception as e:
                    self.console.print(f"加载技能目录失败 {skills_dir}: {e}", style="error")

        user_skills_dir = Config.WORKDIR / "skills"
        if user_skills_dir.exists():
            try:
                batch = self._skill_registry.load_from_directory(str(user_skills_dir))
                loaded.extend(batch)
            except Exception as e:
                self.console.print(f"加载用户技能失败 {user_skills_dir}: {e}", style="error")

    def _show_available_skills(self) -> None:
        skills = self._skill_registry.list_skills()
        if not skills:
            self.console.print("  (暂无可用技能)", style="dim")
            return
        for skill in skills:
            cmd = skill.slash_command or f"/{skill.name}"
            desc = skill.description[:50] + "..." if len(skill.description) > 50 else skill.description
            self.console.print(f"  {cmd:<12} - {desc}", style="info")

    def _skill_cmd(self) -> bool:
        self.console.print("[cyan]可用技能:[/]")
        self._show_available_skills()
        self.console.print("\n使用方式: /<skill-name> [参数]", style="dim")
        return True

    def _run_skill(self, skill, args: str = "") -> bool:
        if "$ARGUMENTS" in skill.instructions and args:
            full_prompt = skill.instructions.replace("$ARGUMENTS", args)
        elif args:
            full_prompt = f"{skill.instructions}\n\n用户输入: {args}"
        else:
            full_prompt = skill.instructions

        self._think_stream(full_prompt)
        return True

    def _exit(self) -> bool:
        self.console.print("再见!", style="dim")
        return False
    
    def _handle_command(self, cmd: str) -> bool:
        cmd_lower = cmd.lower().strip()

        if cmd_lower in self.commands:
            return self.commands[cmd_lower]()

        parts = cmd.split(None, 1)
        slash_cmd = parts[0].lower()
        args = parts[1] if len(parts) > 1 else ""

        if self._skill_registry.is_slash_command(slash_cmd):
            skill = self._skill_registry.get_by_slash_command(slash_cmd)
            if skill:
                return self._run_skill(skill, args)

        self.console.print(f"未知命令: {cmd}", style="error")
        return True
    
    def _print_statusline(self) -> None:
        workspace = Path.cwd().name
        if workspace == "/":
            workspace = "root"

        msg_count = len(self.agent._messages)
        max_msgs = Config.CONTEXT_MAX_MESSAGES
        threshold = Config.CONTEXT_THRESHOLD

        pct = min(100, int((msg_count / max_msgs) * 100)) if max_msgs > 0 else 0
        if pct < 50:
            pct_style = "green"
        elif pct < 80:
            pct_style = "yellow"
        else:
            pct_style = "red"

        if msg_count > threshold:
            ctx_style = "yellow" if msg_count < max_msgs else "red"
        else:
            ctx_style = "bright_black"

        model = Config.MODEL_NAME
        if len(model) > 18:
            model = model[:15] + "..."

        text = Text()
        text.append(" Hermes ", style="bold cyan")
        text.append("│", style="bright_black")
        text.append(f" {workspace} ", style="white")
        text.append("│", style="bright_black")
        text.append(f" {msg_count}/{max_msgs} ", style=ctx_style)
        text.append("│", style="bright_black")
        text.append(f" {model} ", style="magenta")

        # Add progress bar if context is growing
        if msg_count > 3:
            bar_width = 8
            filled = int((pct / 100) * bar_width)
            filled = min(filled, bar_width)
            bar = "█" * filled + "░" * (bar_width - filled)
            text.append("│", style="bright_black")
            text.append(f" {bar} {pct}%", style=pct_style)

        self.console.print(text)

    def _create_completer(self) -> WordCompleter:
        commands = list(self.commands.keys())
        skills = self._skill_registry.list_skills()
        for skill in skills:
            if skill.slash_command:
                commands.append(skill.slash_command)
        return WordCompleter(commands, sentence=True, match_middle=True)

    def _ask(self, prompt_text: str) -> str | None:
        try:
            self._print_statusline()
            result = prompt(prompt_text, history=self._history, completer=self._completer)
            sys.stdout.write("\n")
            sys.stdout.flush()
            return result
        except (KeyboardInterrupt, EOFError):
            self.console.print()
            return None
    
    def _on_tool_event(self, event_type: str, data: dict) -> None:
        tool_name = data.get("tool_name", "unknown")
        
        if event_type == "start":
            self._current_tool = tool_name
            self.console.print(f"[思考中... 使用 {tool_name} ]", style="dim", end="\r")
        elif event_type == "complete":
            self._current_tool = None
            self.console.print(" " * 50, end="\r")
        elif event_type == "error":
            self._current_tool = None
            error = data.get("error", "未知错误")
            self.console.print(f"[工具错误: {error}]", style="error")

    def _confirm_operation(self, tool_name: str, description: str) -> bool:
        self.console.print(" " * 50, end="\r")

        self.console.print(f"[安全确认] 工具 '{tool_name}' 将要执行:", style="error")
        self.console.print(f"  {description}", style="info")

        try:
            user_input = input("是否继续? [y/N]: ").strip().lower()
            return user_input in ("y", "yes")
        except (KeyboardInterrupt, EOFError):
            self.console.print()
            return False

    def _on_context_compressed(self, original: int, compressed: int) -> None:
        self.console.print(
            f"[上下文压缩] {original} 条消息 → {compressed} 条消息",
            style="dim"
        )

    def _task_cmd(self) -> bool:
        self.console.print("[cyan]定时任务管理:[/]")
        self.console.print("  add    - 添加任务")
        self.console.print("  list   - 列出任务")
        self.console.print("  remove - 删除任务")

        try:
            action = input("操作: ").strip().lower()
            if action == "add":
                name = input("任务名称: ").strip()
                trigger_type = input("触发类型 (cron/interval/date): ").strip()
                trigger_expr = input("触发表达式: ").strip()
                action_name = input("执行动作: ").strip()
                task = self._scheduler.add_task(name, trigger_type, trigger_expr, action_name)
                self.console.print(f"已添加任务: {task.id}", style="info")
            elif action == "list":
                tasks = self._scheduler.list_tasks()
                if not tasks:
                    self.console.print("没有定时任务", style="dim")
                else:
                    for t in tasks:
                        status = "启用" if t.enabled else "暂停"
                        self.console.print(f"  [{t.id}] {t.name} ({status})", style="info")
            elif action == "remove":
                task_id = input("任务ID: ").strip()
                if self._scheduler.remove_task(task_id):
                    self.console.print(f"已删除任务: {task_id}", style="info")
                else:
                    self.console.print(f"任务不存在: {task_id}", style="error")
            else:
                self.console.print(f"未知操作: {action}", style="error")
        except Exception as e:
            self.console.print(f"操作失败: {e}", style="error")
        return True

    def _compress_cmd(self) -> bool:
        result = self.agent.compress_context()
        if "error" in result:
            self.console.print(f"压缩失败: {result['error']}", style="error")
        else:
            self.console.print(
                f"已压缩: {result['original']} → {result['compressed']} "
                f"(减少 {result['reduced']} 条)",
                style="info"
            )
        return True

    def _think_stream(self, message: str) -> str:
        full_response = ""
        
        try:
            for chunk in self.agent.run_stream(message):
                if self._current_tool:
                    self.console.print(" " * 50, end="\r")
                    self._current_tool = None
                    
                full_response += chunk
                self.console.print(chunk, end="", soft_wrap=True)
            
            self.console.print()
            return full_response
        except Exception as e:
            return f"出错了: {e}"
    
    def run(self) -> None:
        self._show_welcome()
        
        prompt_text = "> "
        self._history = InMemoryHistory()
        
        while True:
            user_input = self._ask(prompt_text)
            if user_input is None:
                break
            
            user_input = user_input.strip()
            if not user_input:
                continue
            
            if user_input.startswith("/"):
                if not self._handle_command(user_input):
                    break
                continue
            
            self._think_stream(user_input)


def main() -> None:
    cli = HermesCLI()
    cli.run()


if __name__ == "__main__":
    main()