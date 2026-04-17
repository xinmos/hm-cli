import sys
from pathlib import Path
from typing import Any

from prompt_toolkit import prompt
from prompt_toolkit.completion import WordCompleter
from prompt_toolkit.history import InMemoryHistory
from rich.console import Console, RenderableType
from rich.padding import Padding
from rich.style import Style
from rich.text import Text
from rich.theme import Theme

from hermes.app import InteractionPort
from hermes.app.bootstrap import ControlPlaneApp, bootstrap

THEME = Theme({
    "prompt": Style(color="green", bold=True),
    "banner": Style(color="cyan", bold=True),
    "info": Style(color="blue"),
    "dim": Style(color="bright_black"),
    "error": Style(color="red"),
})


class RichInteractionPort(InteractionPort):
    def __init__(self, console: Console):
        self._console = console

    def confirm(self, tool_name: str, description: str) -> bool:
        self._console.print(" " * 50, end="\r")
        self._console.print(f"[安全确认] 工具 '{tool_name}' 将要执行:", style="error")
        self._console.print(f"  {description}", style="info")

        try:
            user_input = input("是否继续? [y/N]: ").strip().lower()
            return user_input in ("y", "yes")
        except (KeyboardInterrupt, EOFError):
            self._console.print()
            return False

    def notify_tool_start(self, tool_name: str) -> None:
        self._console.print(f"[思考中... 使用 {tool_name} ]", style="dim", end="\r")

    def notify_tool_complete(self, tool_name: str, result: Any = None) -> None:
        self._console.print(" " * 50, end="\r")

    def notify_tool_error(self, tool_name: str, error: str) -> None:
        self._console.print(" " * 50, end="\r")
        self._console.print(f"[工具错误: {error}]", style="error")

    def on_context_compressed(self, original: int, compressed: int) -> None:
        self._console.print(
            f"[上下文压缩] {original} 条消息 → {compressed} 条消息",
            style="dim"
        )


class CLIAdapter:
    def __init__(self, app: ControlPlaneApp) -> None:
        self._app = app
        self._console = Console(theme=THEME)
        self._history = InMemoryHistory()
        self._current_tool: str | None = None

        # Setup interaction port
        interaction_port = RichInteractionPort(self._console)
        self._app.agent.set_interaction_port(interaction_port)

        # Build completer
        self._completer = self._create_completer()

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
        text.append(f"{self._app.settings.model_name}\n", style="info")
        text.append(f"  Tools:  ", style="dim")
        text.append(f"5\n", style="info")
        skills = self._app.skills.list_skills()
        text.append(f"  Skills: ", style="dim")
        text.append(f"{len(skills)}\n", style="info")
        return Padding(text, (0, 0, 1, 0))

    def _show_welcome(self) -> None:
        self._console.print(self._banner())
        self._console.print(self._config_info())
        self._console.print("输入 /help 查看命令或直接输入消息\n", style="dim")

    def _print_statusline(self) -> None:
        workspace = Path.cwd().name
        if workspace == "/":
            workspace = "root"

        msg_count = self._app.agent.get_message_count()
        max_msgs = self._app.settings.context_max_messages
        threshold = self._app.settings.context_threshold

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

        model = self._app.settings.model_name
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

        if msg_count > 3:
            bar_width = 8
            filled = int((pct / 100) * bar_width)
            filled = min(filled, bar_width)
            bar = "█" * filled + "░" * (bar_width - filled)
            text.append("│", style="bright_black")
            text.append(f" {bar} {pct}%", style=pct_style)

        self._console.print(text)

    def _create_completer(self) -> WordCompleter:
        commands = ["/exit", "/clear", "/reset", "/help", "/skills", "/task", "/compress", "/soul"]
        skills = self._app.skills.list_skills()
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
            self._console.print()
            return None

    def _show_help(self) -> None:
        help_text = """
[cyan]可用命令:[/]
  /exit         退出程序
  /clear        清屏
  /reset        重置对话记忆
  /skills       列出可用技能
  /task         定时任务管理 (add/list/remove)
  /compress     手动压缩上下文
  /soul         切换 Agent 身份 (list/<name>)
  /help         显示帮助

[cyan]可用技能:[/] 使用 /<skill-name> [参数] 执行"""
        self._console.print(help_text)
        self._show_available_skills()

    def _show_available_skills(self) -> None:
        skills = self._app.skills.list_skills()
        if not skills:
            self._console.print("  (暂无可用技能)", style="dim")
            return
        for skill in skills:
            cmd = skill.slash_command or f"/{skill.name}"
            desc = skill.description[:50] + "..." if len(skill.description) > 50 else skill.description
            self._console.print(f"  {cmd:<12} - {desc}", style="info")

    def _handle_command(self, cmd: str) -> bool:
        # 处理 /soul 命令
        if cmd.startswith("/soul"):
            parts = cmd.split(maxsplit=1)
            arg = parts[1] if len(parts) > 1 else ""
            self._handle_soul_command(arg)
            return True

        result = self._app.handle(cmd)

        if result["type"] == "control":
            action = result.get("action")
            if action == "exit":
                self._console.print("再见!", style="dim")
                return False
            elif action == "clear":
                self._console.clear()
                self._show_welcome()
            elif action == "reset":
                self._console.print("记忆已重置", style="dim")
            elif action == "help":
                self._show_help()
        elif result["type"] == "list_skills":
            self._show_available_skills()
        elif result["type"] == "task_management":
            self._task_cmd()
        elif result["type"] == "skill":
            response = result.get("response", [])
            for chunk in response:
                self._console.print(chunk, end="", soft_wrap=True)
            self._console.print()
        elif result["type"] == "message":
            response = result.get("response", [])
            for chunk in response:
                self._console.print(chunk, end="", soft_wrap=True)
            self._console.print()
        elif result["type"] == "compress":
            self._handle_compress()
        elif result["type"] == "error":
            self._console.print(result.get("message", "未知错误"), style="error")

        return True

    def _handle_compress(self) -> None:
        """处理 /compress 命令 - 压缩记忆"""
        if not self._app.memory:
            self._console.print("[yellow]记忆系统未启用[/yellow]")
            return

        import asyncio
        from hermes.core.memory.models import CompressionStrategy

        self._console.print("[cyan]选择压缩策略:[/]")
        self._console.print("  1. flush    - 创建检查点")
        self._console.print("  2. prune    - 裁剪低权重内容")
        self._console.print("  3. summarize- 对旧记录生成摘要")
        self._console.print("  4. segment  - 创建新的会话段")

        try:
            choice = input("选择 (1-4): ").strip()
            strategy_map = {
                "1": CompressionStrategy.FLUSH,
                "2": CompressionStrategy.PRUNE,
                "3": CompressionStrategy.SUMMARIZE,
                "4": CompressionStrategy.SEGMENT,
            }

            strategy = strategy_map.get(choice)
            if not strategy:
                self._console.print("[red]无效选择[/red]")
                return

            result = asyncio.run(self._app.memory.compress_memory(strategy))
            self._console.print(f"[green]压缩完成: {result}[/green]")

        except Exception as e:
            self._console.print(f"[red]压缩失败: {e}[/red]")

    def _handle_soul_command(self, arg: str) -> None:
        """处理 /soul 命令"""
        if not arg or arg == "list":
            # 列出可用 souls
            souls = self._app.list_available_souls()
            current = self._app.soul.name if self._app.soul else "none"
            self._console.print("[cyan]可用身份:[/]")
            for soul_name in souls:
                marker = " →" if soul_name == current else "   "
                self._console.print(f"{marker} {soul_name}")
            self._console.print(f"\n当前身份: [cyan]{current}[/]")
            self._console.print("\n使用 /soul <name> 切换身份")
        else:
            # 切换到指定 soul
            soul = self._app.load_soul(arg)
            if soul:
                self._app.set_soul(soul)
                self._console.print(f"[green]已切换身份: {soul.name}[/]")
                self._console.print(f"[dim]{soul.persona[:100]}...[/]")
            else:
                self._console.print(f"[red]未找到身份: {arg}[/]")
                self._console.print("使用 /soul list 查看可用身份")

    def _task_cmd(self) -> None:
        self._console.print("[cyan]定时任务管理:[/]")
        self._console.print("  add    - 添加任务")
        self._console.print("  list   - 列出任务")
        self._console.print("  remove - 删除任务")

        try:
            action = input("操作: ").strip().lower()
            if action == "add":
                name = input("任务名称: ").strip()
                trigger_type = input("触发类型 (cron/interval/date): ").strip()
                trigger_expr = input("触发表达式: ").strip()
                task = self._app.tasks.add_task(
                    name, trigger_type, trigger_expr, lambda: self._console.print(f"Task {name} executed")
                )
                self._console.print(f"已添加任务: {task.id}", style="info")
            elif action == "list":
                tasks = self._app.tasks.list_tasks()
                if not tasks:
                    self._console.print("没有定时任务", style="dim")
                else:
                    for t in tasks:
                        status = "启用" if t.enabled else "暂停"
                        self._console.print(f"  [{t.id}] {t.name} ({status})", style="info")
            elif action == "remove":
                task_id = input("任务ID: ").strip()
                if self._app.tasks.remove_task(task_id):
                    self._console.print(f"已删除任务: {task_id}", style="info")
                else:
                    self._console.print(f"任务不存在: {task_id}", style="error")
            else:
                self._console.print(f"未知操作: {action}", style="error")
        except Exception as e:
            self._console.print(f"操作失败: {e}", style="error")

    def run(self) -> None:
        self._show_welcome()

        prompt_text = "> "

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

            # Handle as message
            result = self._app.handle(user_input)
            if result["type"] == "message":
                response = result.get("response", [])
                for chunk in response:
                    self._console.print(chunk, end="", soft_wrap=True)
                self._console.print()


def main() -> None:
    interaction_port = RichInteractionPort(Console(theme=THEME))
    app = bootstrap(interaction_port=interaction_port)
    cli = CLIAdapter(app)
    cli.run()


if __name__ == "__main__":
    main()
