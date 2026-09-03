# 晴雨知心 · 天气播报助手（SunnyWeather）

基于 **LangGraph + LangChain + MCP + Redis** 的智能天气播报助手。用户以自然语言输入地点与时间，系统经 MCP 天气服务器实时获取 Open-Meteo 气象数据，由 LLM 生成结构化的生活化天气播报（穿衣 / 出行 / 健康建议），并支持 RAG 气象知识问答与多轮分支会话（重新回答、编辑、撤销）。

## 功能特性

- **实时天气播报**：MCP（FastMCP，streamable-http）暴露 `get_weather`（地址 → 高德地理编码 → Open-Meteo 逐小时预报）与 `get_time`（北京时间）两个工具
- **智能路由**：LangGraph 三分类路由（实时查询 / 知识问答 / 无关拒绝），结合多轮上下文区分"首次查询"与"重复询问"
- **RAG 知识问答**：PyMuPDF 切分气象资料 → Qwen3-Embedding 向量化 → Redis VectorStore 语义检索作答
- **分支会话**：RedisSaver 持久化检查点，支持任意一轮**重新回答 / 编辑 / 撤销**；问题版本与回答版本两条切换轴彼此独立，切换时后续消息自动跟随
- **结构化播报**：固定结构（时间 / 地点 / 概况 / 详情 / 穿衣 / 出行 / 健康）返回，"问题答案"作为对话正文按 Markdown 渲染，其余字段由侧栏"气象播报单"独立渲染卡片
- **会话压缩**：历史过长时自动摘要压缩（保留最近 6 条原文与用户偏好），避免超出模型上下文

## 效果演示

**实时天气播报** —— 问“北理工明天天气如何”，对话流展示天气概括正文，左侧气象播报单同步渲染天气详情、穿衣、出行、健康卡片。

![实时天气播报](docs/images/demo-1-weather.png)

**多轮追问** —— 追问"那后天呢？"，识别为时间维度新查询，播报单自动更新。

![多轮追问](docs/images/demo-2-multiturn.png)

**分支会话** —— 对任一轮点击"重新回答 / 编辑"生成新版本，可独立翻页切换（如 1/2 ↔ 2/2），后续消息自动跟随；"撤销"删除该问题及其分支。

![分支会话](docs/images/demo-3-branch.png)

**RAG 知识问答** —— "为什么会下雪？"走 RAG 检索气象资料作答。

![RAG 知识问答](docs/images/demo-4-rag.png)

## 技术架构

| 模块 | 技术栈 | 说明 |
| --- | --- | --- |
| 前端 | Vue 3 + Vite | 对话式 UI，分支树展示，气象播报单侧栏 |
| 后端 API | FastAPI | `/answer` 接口，支持从历史检查点 fork 执行 |
| 图编排 | LangGraph + RedisSaver | input → router → weather / weather_analysis / general；历史过长时自动摘要压缩 |
| MCP 服务器 | FastMCP (streamable-http) | `get_weather`（Open-Meteo + 高德地理编码）+ `get_time` |
| 模型 | OpenAI 兼容 API + Ollama | 主对话与子 Agent 经 `init_chat_model` 加载；路由模型独立选择；嵌入走 Ollama |
| RAG | RedisVectorStore + OllamaEmbeddings | 切分 → 向量化 → 相似度检索（阈值过滤） |

## 目录结构

```
project2/
├── backend/                   # 后端（所有 Python 服务）
│   ├── mcp.json               # MCP 客户端连接配置
│   ├── api.py                 # FastAPI 入口（/answer；支持 __root__ 特殊检查点）
│   ├── node.py                # LangGraph 状态图定义与节点实现
│   ├── model.py               # 模型工厂（主对话 cloud/local、路由模型、embeddings）
│   ├── tool.py                # MCP 天气服务器（get_weather + get_time）
│   ├── rag.py                 # RAG：PDF 入库、索引删除、向量检索
│   └── rag/                   # 气象知识资料源（内置 PDF）
├── frontend/                  # Vue 3 前端
│   └── src/
│       ├── App.vue            # 分支会话主界面（含气象播报单侧栏）
│       ├── markdown.js        # 轻量安全 Markdown 渲染
│       └── components/WeatherReport.vue  # 气象播报单卡片
└── docs/images/               # 效果演示截图
```

## 环境要求

Python 3.10+、Redis（默认 `redis://localhost:26379`，需支持向量检索）、Ollama（对话模型 + 嵌入模型）、Node.js + npm。

## 快速开始

```bat
:: 1. 后端依赖
pip install -r requirements.txt

:: 2. 前端依赖（frontend 目录下）
cd frontend && npm install

:: 3. 初始化 RAG（可选，需 Redis + Ollama 就绪；将 rag/ 下气象 PDF 写入索引并调试检索）
cd backend && python rag.py

:: 4. 启动三项服务
cd backend && python tool.py                                   :: MCP 天气服务器 :8000
cd backend && python -m uvicorn api:app --host 127.0.0.1 --port 5000   :: 后端 API
cd frontend && npm run dev                                    :: 前端 :5173
```

> 也可运行根目录 `start.bat` 一键启动（本地脚本，需按本机环境修改 `PYTHON` 路径）；`api.py` 支持 `python api.py` 直接跑一次调试查询。

### 配置（`backend/.env`）

| 变量 | 默认值 | 说明 |
| --- | --- | --- |
| `REDIS_URL` | `redis://localhost:26379` | Redis 地址（检查点 + 向量库共用） |
| `model` / `model_provider` / `model_api` / `base_url` | `deepseek-v4-flash` / `openai` | OpenAI 兼容主对话模型及凭证（`model_api`、`base_url` 必填） |
| `chat_model` | `cloud` | 主对话模型来源：`cloud`=云端 / `local`=Ollama |
| `route_model` | `cloud` | 路由意图分类模型来源（同 `chat_model`） |
| `ollama_url` / `ollama_model` | `http://localhost:11434` / `qwen3.5:4b` | Ollama 服务与本地对话模型 |
| `embeddings_model` | `qwen3-embedding:latest` | RAG 嵌入模型（Ollama） |
| `ollama_reasoning` / `ollama_temperature` | `false` / `0.7` | 本地模型推理开关与温度 |
| `host` / `port` | `127.0.0.1` / `8000` | MCP 天气服务器监听地址与端口 |
| `amap_key` | — | 高德 Web 服务 Key（地理编码，必填） |

## 核心流程

```
用户提问 → input（写入 HumanMessage；历史过长先摘要压缩）
        → router（LLM 三分类）
            ├── 2 实时查询 → weather（MCP 子 Agent 调用工具 → 结构化 Result）
            ├── 1 知识问答 → weather_analysis（RAG 检索 + 子 Agent 作答）
            └── 0 无关拒绝 → general
```

`RedisSaver` 维护检查点（TTL 30 分钟滑动续期）；`/answer` 传入 `checkpoint_id` 可从历史检查点 fork 执行（前端分支回溯），`__root__` 表示从线程初始空检查点继续，用于"重新回答 / 编辑第一轮"。

## API 接口

**POST `/answer`**

```json
{ "thread_id": "12", "question": "北理工明天天气如何", "checkpoint_id": null }
```

```json
{
  "result": { "time": "...", "address": "...", "summary": "...", "weather": "...", "clothing_advice": "...", "travel_tips": "...", "healthy_tips": "...", "result": "明天北京多云转晴……" },
  "before_checkpoint_id": "提问前基准检查点",
  "after_checkpoint_id": "本次回答产生的检查点"
}
```

> `result` 类型因路由分支而异：实时查询返回结构化 `dict`（其 `result` 字段为对话正文，前端按 Markdown 渲染）；知识问答 / 无关拒绝 / 兜底返回 `str`；天气服务不可用时为 `null`。`checkpoint_id` 非法返回 400。

## License

[MIT](LICENSE) © SunnyWeather Contributors