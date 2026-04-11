from typing import Callable, Optional

from langchain.agents import create_agent
from langchain_core.messages import AIMessageChunk, HumanMessage, ToolMessage
from langchain_openai import ChatOpenAI

from hermes.config import Config
from hermes.context import ContextCompressor
from hermes.tools import TOOLS


class HermesAgent:
    def __init__(self, enable_compression: bool = True):
        self.tools = TOOLS
        self.model = ChatOpenAI(
            api_key=Config.OPENAI_API_KEY,
            base_url=Config.OPENAI_BASE_URL,
            model=Config.MODEL_NAME
        )
        self.agent = create_agent(self.model, TOOLS)
        self._messages = []
        self._tool_callback: Optional[Callable[[str, dict], None]] = None
        self._confirm_callback: Optional[Callable[[str, str], bool]] = None
        self._compression_callback: Optional[Callable[[int, int], None]] = None

        # 初始化上下文压缩器
        if enable_compression and Config.CONTEXT_COMPRESSION:
            self._compressor = ContextCompressor(
                model=self.model,
                max_messages=Config.CONTEXT_MAX_MESSAGES,
                compression_threshold=Config.CONTEXT_THRESHOLD,
            )
        else:
            self._compressor = None

    def set_tool_callback(self, callback: Callable[[str, dict], None]) -> None:
        """设置工具调用事件回调

        callback 接收:
            - event_type: "start" | "complete" | "error"
            - data: {"tool_name": str, "result": Any, "error": str}
        """
        self._tool_callback = callback

    def set_confirm_callback(self, callback: Callable[[str, str], bool]) -> None:
        """设置危险命令确认回调

        callback 接收:
            - tool_name: 工具名称
            - command: 要执行的命令/操作描述
        返回: bool - True 表示用户确认执行，False 表示取消
        """
        self._confirm_callback = callback

    def _notify_tool(self, event_type: str, tool_name: str, result: any = None, error: str = None):
        if self._tool_callback:
            self._tool_callback(event_type, {
                "tool_name": tool_name,
                "result": result,
                "error": error
            })

    def run(self, user_input: str) -> str:
        config = {"configurable": {"thread_id": "default_thread"}}
        inputs = {"messages": [("user", user_input)]}

        final_response = ""
        for event in self.agent.stream(inputs, config=config, stream_mode="values"):
            message = event["messages"][-1]

            if hasattr(message, "tool_calls") and message.tool_calls:
                for tool_call in message.tool_calls:
                    self._notify_tool("start", tool_call.get("name", "unknown"))

            if isinstance(message, ToolMessage):
                self._notify_tool("complete", message.name, result=message.content)

            if hasattr(message, "content") and message.content:
                final_response = message.content

        return final_response.encode("utf-8", errors="ignore").decode("utf-8")

    def set_compression_callback(self, callback: Callable[[int, int], None]) -> None:
        """设置上下文压缩回调

        callback 接收:
            - original_count: 压缩前的消息数
            - compressed_count: 压缩后的消息数
        """
        self._compression_callback = callback

    def _maybe_compress(self) -> None:
        """根据条件自动压缩上下文"""
        if self._compressor and self._compressor.should_compress(self._messages):
            original = len(self._messages)
            self._messages = self._compressor.smart_compress(self._messages)
            compressed = len(self._messages)
            if self._compression_callback and original > compressed:
                self._compression_callback(original, compressed)

    def compress_context(self) -> dict:
        """手动触发上下文压缩"""
        if not self._compressor:
            return {"error": "Compression disabled"}
        original = len(self._messages)
        self._messages = self._compressor.smart_compress(self._messages)
        compressed = len(self._messages)
        return {
            "original": original,
            "compressed": compressed,
            "reduced": original - compressed,
        }

    def run_stream(self, user_input: str):
        self._messages.append(HumanMessage(content=user_input))

        # 自动压缩上下文
        self._maybe_compress()

        config = {"configurable": {"thread_id": "default_thread"}}
        inputs = {"messages": self._messages}

        full_response = ""
        current_tool = None

        for msg, metadata in self.agent.stream(inputs, config=config, stream_mode="messages"):
            if hasattr(msg, "tool_calls") and msg.tool_calls:
                for tool_call in msg.tool_calls:
                    tool_name = tool_call.get("name", "unknown")
                    current_tool = tool_name
                    self._notify_tool("start", tool_name)

            if isinstance(msg, ToolMessage):
                self._notify_tool("complete", msg.name, result=msg.content)
                current_tool = None

            if isinstance(msg, AIMessageChunk):
                content = msg.content
                if content:
                    full_response += content
                    yield content.encode("utf-8", errors="ignore").decode("utf-8")

        if full_response:
            self._messages.append(AIMessageChunk(content=full_response))

    def reset(self) -> None:
        self._messages.clear()
