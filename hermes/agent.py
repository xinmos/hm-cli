from langchain.agents import create_agent
from langchain_openai import ChatOpenAI
from hermes.config import Config
from hermes.tools import TOOLS


class HermesAgent:
    def __init__(self):
        # 保存工具引用
        self.tools = TOOLS
        # 初始化语言模型
        self.model = ChatOpenAI(
            api_key=Config.OPENAI_API_KEY,
            base_url=Config.OPENAI_BASE_URL,
            model=Config.MODEL_NAME
        )
        # 使用 create_agent 构建 agent，它封装了 ReAct 逻辑
        self.agent = create_agent(self.model, TOOLS)

    def run(self, user_input: str) -> str:
        """运行 Agent 并返回最终响应"""
        # 配置对话上下文
        config = {"configurable": {"thread_id": "default_thread"}}
        # 准备输入消息
        inputs = {"messages": [("user", user_input)]}

        # 执行 Agent 图，捕获所有中间步骤
        final_response = ""
        for event in self.agent.stream(inputs, config=config, stream_mode="values"):
            message = event["messages"][-1]
            if hasattr(message, "content") and message.content:
                final_response = message.content
        # 清理代理字符
        return final_response.encode("utf-8", errors="ignore").decode("utf-8")

    def run_stream(self, user_input: str):
        """运行 Agent 并流式输出响应 - 使用 stream_mode='messages' 逐 token 流式"""
        from langchain_core.messages import AIMessageChunk
        
        config = {"configurable": {"thread_id": "default_thread"}}
        inputs = {"messages": [("user", user_input)]}

        for msg, metadata in self.agent.stream(inputs, config=config, stream_mode="messages"):
            if isinstance(msg, AIMessageChunk):
                content = msg.content
                if content:
                    yield content.encode("utf-8", errors="ignore").decode("utf-8")