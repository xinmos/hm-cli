import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

class Config:
    # LLM 配置
    OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "sk-no-key-required")
    OPENAI_BASE_URL = os.getenv("OPENAI_BASE_URL", "http://192.168.1.7:8081/v1")
    MODEL_NAME = os.getenv("MODEL_NAME", "llama-model")

    # 可选参数
    TEMPERATURE = float(os.getenv("TEMPERATURE", "0.7"))
    MAX_TOKENS = int(os.getenv("MAX_TOKENS", "2048"))

    # 运行时配置（从环境变量读取，支持用户自定义）
    WORKDIR = Path(os.getenv("HERMES_WORKDIR", ".")).resolve()
    MAX_OUTPUT_SIZE = int(os.getenv("HERMES_MAX_OUTPUT", "50000"))  # 50KB
    MAX_OUTPUT_LINES = int(os.getenv("HERMES_MAX_LINES", "500"))
    COMMAND_TIMEOUT = int(os.getenv("HERMES_TIMEOUT", "120"))  # 秒
    STRICT_SANDBOX = os.getenv("HERMES_STRICT", "true").lower() == "true"