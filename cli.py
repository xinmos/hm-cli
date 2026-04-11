#!/usr/bin/env python
from rich.console import Console, RenderableType
from rich.padding import Padding
from rich.style import Style
from rich.text import Text
from rich.theme import Theme
import sys
from prompt_toolkit import prompt
from prompt_toolkit.history import InMemoryHistory
from hermes.agent import HermesAgent
from hermes.config import Config


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
        }
    
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
        self.console.print("记忆已重置", style="dim")
        return True
    
    def _help(self) -> bool:
        """显示帮助"""
        help_text = """
[cyan]可用命令:[/]
  /exit  退出程序
  /clear        清屏
  /reset        重置对话记忆
  /help         显示帮助
        """
        self.console.print(help_text)
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
    
    def _think_stream(self, message: str) -> str:
        """调用 agent 思考并流式输出"""
        full_response = ""
        
        try:
            # 流式输出：使用 Rich Console 直接输出（更稳定）
            for chunk in self.agent.run_stream(message):
                full_response += chunk
                self.console.print(chunk, end="", soft_wrap=True)
            
            self.console.print()  # 换行
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
            
            response = self._think_stream(user_input)


def main() -> None:
    """入口函数"""
    cli = HermesCLI()
    cli.run()


if __name__ == "__main__":
    main()