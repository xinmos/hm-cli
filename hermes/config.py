import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    # OpenAI 官方配置（已注释，如需使用请取消注释）
    # OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
    # OPENAI_BASE_URL = os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1")
    # MODEL_NAME = os.getenv("MODEL_NAME", "gpt-4o")

    # llama.cpp 本地服务配置
    OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "sk-no-key-required")
    OPENAI_BASE_URL = os.getenv("OPENAI_BASE_URL", "http://192.168.1.7:8081/v1")
    MODEL_NAME = os.getenv("MODEL_NAME", "llama-model")

    # 可选参数
    TEMPERATURE = float(os.getenv("TEMPERATURE", "0.7"))
    MAX_TOKENS = int(os.getenv("MAX_TOKENS", "2048"))