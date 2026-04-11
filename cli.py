import sys

from prompt_toolkit import prompt
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


# 自定义主题
THEME = Theme({
    "prompt": Style(color="green", bold=True),
    "banner": Style(color="cyan", bold=True),
    "info": Style(color="blue"),
    "dim": Style(color="bright_black"),
    "error": Style(color="red"),
})


class HermesCLI:
    """Hermes Code CLI 主类"""

    def __init__(self) -> None:
        self.console = Console(theme=THEME)
        self.agent = HermesAgent()
        self.commands: dict[str, callable] = {
            "/exit": self._exit,
            "/clear": self._clear,
            "/reset": self._reset,
            "/help": self._help,
            "/skill": self._skill_cmd,
            "/task": self._task_cmd,
            "/compress": self._compress_cmd,
        }
        self._skill_registry = get_registry()
        self._load_default_skills()
        self._scheduler = TaskScheduler()
        self._scheduler.start()
        self._current_tool: str | None = None

        # 注册工具状态回调
        self.agent.set_tool_callback(self._on_tool_event)
        # 注册危险操作确认回调
        set_confirm_callback(self._confirm_operation)
        # 注册上下文压缩回调
        self.agent.set_compression_callback(self._on_context_compressed)
    
    def _banner(self) -> RenderableType:
        """生成优美的 ASCII banner"""
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
║              [ AI Coding Assistant ]              ║
╚═══════════════════════════════════════════════════╝"""
        return Text(banner_ascii, style="cyan bold")
    
    def _config_info(self) -> RenderableType:
        """显示配置信息"""
        text = Text()
        text.append(f"  Model:  ", style="dim")
        text.append(f"{Config.MODEL_NAME}\n", style="info")
        text.append(f"  Tools:  ", style="dim")
        text.append(f"{len(self.agent.tools)}\n", style="info")
        return Padding(text, (0, 0, 1, 0))
    
    def _show_welcome(self) -> None:
        """显示欢迎界面"""
        self.console.print(self._banner())
        self.console.print(self._config_info())
        self.console.print("输入 /help 查看命令或直接输入消息\n", style="dim")
    
    def _clear(self) -> bool:
        """清屏并显示 banner"""
        self.console.clear()
        self._show_welcome()
        return True
    
    def _reset(self) -> bool:
        """重置对话记忆"""
        self.agent.reset()
        self.console.print("记忆已重置", style="dim")
        return True
    
    def _help(self) -> bool:
        """显示帮助"""
        help_text = """
[cyan]可用命令:[/]
  /exit         退出程序
  /clear        清屏
  /reset        重置对话记忆
  /skill        技能管理 (load/list/unload)
  /task         定时任务管理 (add/list/remove)
  /compress     手动压缩上下文
  /help         显示帮助
        """
        self.console.print(help_text)
        return True
    
    def _load_default_skills(self) -> None:
        skills_dir = Config.WORKDIR / ".hermes" / "skills"
        if skills_dir.exists():
            loaded = self._skill_registry.load_from_directory(str(skills_dir))
            if loaded:
                names = [s.name for s in loaded]
                self.console.print(f"已加载技能: {', '.join(names)}", style="dim")

    def _skill_cmd(self) -> bool:
        """技能管理命令 - 输入 /skill load <path> 或 /skill list"""
        self.console.print("[cyan]技能管理:[/]")
        self.console.print("  /skill load <路径>  - 加载技能文件")
        self.console.print("  /skill list         - 列出已加载技能")
        self.console.print("  /skill unload <名>  - 卸载技能")

        try:
            action = input("操作 (load/list/unload): ").strip().lower()
            if action == "load":
                path = input("技能文件路径: ").strip()
                skill = self._skill_registry.load_from_file(path)
                self.console.print(f"已加载技能: {skill.name}", style="info")
            elif action == "list":
                skills = self._skill_registry.list_skills()
                if not skills:
                    self.console.print("没有已加载的技能", style="dim")
                else:
                    for s in skills:
                        self.console.print(f"  - {s.name}: {s.description}", style="info")
            elif action == "unload":
                name = input("技能名称: ").strip()
                if self._skill_registry.unregister(name):
                    self.console.print(f"已卸载技能: {name}", style="info")
                else:
                    self.console.print(f"技能不存在: {name}", style="error")
            else:
                self.console.print(f"未知操作: {action}", style="error")
        except Exception as e:
            self.console.print(f"操作失败: {e}", style="error")
        return True

    def _exit(self) -> bool:
        """退出程序"""
        self.console.print("再见!", style="dim")
        return False
    
    def _handle_command(self, cmd: str) -> bool:
        """处理斜杠命令"""
        handler = self.commands.get(cmd.lower().strip())
        if handler:
            return handler()
        self.console.print(f"未知命令: {cmd}", style="error")
        return True
    
    def _ask(self, prompt_text: str) -> str | None:
        """获取用户输入 - 支持方向键和历史记录"""
        try:
            result = prompt(prompt_text, history=self._history)
            # 强制在输入后换新行，确保后续输出不会覆盖输入
            sys.stdout.write("\n")
            sys.stdout.flush()
            return result
        except (KeyboardInterrupt, EOFError):
            self.console.print()
            return None
    
    def _on_tool_event(self, event_type: str, data: dict) -> None:
        """处理工具调用事件"""
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
        """询问用户确认危险操作"""
        # 清除思考状态行
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
        """处理上下文压缩事件"""
        self.console.print(
            f"[上下文压缩] {original} 条消息 → {compressed} 条消息",
            style="dim"
        )

    def _task_cmd(self) -> bool:
        """定时任务管理命令"""
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
        """手动触发上下文压缩"""
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
        """调用 agent 思考并流式输出"""
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
        """运行 CLI 主循环"""
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
    """入口函数"""
    cli = HermesCLI()
    cli.run()


if __name__ == "__main__":
    main()