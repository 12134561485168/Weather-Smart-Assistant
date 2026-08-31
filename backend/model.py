from langchain_ollama import ChatOllama, OllamaEmbeddings
from langchain.chat_models import init_chat_model
import os
from functools import lru_cache


@lru_cache(maxsize=1)
def chat_model():
    return init_chat_model(
        model=os.getenv("model", "deepseek-v4-flash"),
        model_provider=os.getenv("model_provider", "openai"),
        api_key=os.getenv("model_api"),
        base_url=os.getenv("base_url"),
        streaming=True,
    )


@lru_cache(maxsize=1)
def chat_ollama_model():
    return ChatOllama(
        model=os.getenv("ollama_model", "qwen3.5:4b"),
        base_url=os.getenv("ollama_url", "http://localhost:11434"),
        reasoning=os.getenv("ollama_reasoning", "false"),
        temperature=os.getenv("ollama_temperature", "0.7"),
        num_ctx=8192,
    )


@lru_cache(maxsize=1)
def embeddings_model():

    return OllamaEmbeddings(
        model=os.getenv("embeddings_model", "qwen3-embedding:latest"),
        base_url=os.getenv("ollama_url", "http://localhost:11434"),
        dimensions=1024,
    )
