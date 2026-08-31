from fastapi import FastAPI
from pydantic import BaseModel
from typing_extensions import TypedDict
from dotenv import load_dotenv

load_dotenv()  # 加载 .env 文件中的环境变量


class Question(TypedDict):
    thread_id: str
    question: str


a = Question()
print(a.get("question"))
a["1"] = 1
print(a)
