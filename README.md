# 晴雨知心 · 天气播报助手（SunnyWeather）

基于 **LangGraph + LangChain + MCP + Redis** 的智能天气播报助手。用户输入地点与时间后，系统通过 MCP 天气服务器实时获取 Open-Meteo 气象数据，由 LLM 生成结构化、有温度的生活化天气播报（穿衣 / 出行 / 健康建议），并支持 RAG 气象知识问答与多轮分支会话（重新回答、编辑、撤销）。

## 功能特性

- **实时天气播报**：通过 MCP（FastMCP，streamable-http）调用两个工具——`get_weather`（地址 + 日期区间 → Open-Meteo 当前天气与逐小时预报：温度、湿度、体感、降水概率、风况等；内部调用高德地理编码将地址解析为经纬度）与 `get_time`（北京时间，辅助时间感知）
- **智能路由**：LangGraph 三分类路由（实时查询 / 知识问答 / 无关拒绝），结合多轮上下文判断"首次查询"与"重复询问"；意图分类模型可按 `route_model` 切换云端或本地
- **RAG 知识问答**：PDF 气象资料切分后写入 Redis 向量库，结合 Ollama 嵌入模型检索作答
- **分支会话**：基于 Redis checkpointer，支持对任意一轮回答**重新回答 / 编辑 / 撤销**；问答以分支树组织，左侧（AI 侧）可翻页切换"重新回答"版本、用户侧可切换"问题版本"，两个切换轴相互独立，切换时后续消息自动跟随
- **结构化播报**：AI 以固定结构（时间 / 地点 / 概况 / 详情 / 穿衣 / 出行 / 健康 / 问题答案）返回；其中"问题答案（`result`）"作为对话正文展示在消息流中（前端支持 Markdown 渲染），其余字段由侧栏"气象播报单"面板独立渲染卡片，随分支切换自动更新
- **会话压缩**：历史对话过长时自动摘要压缩（保留最近 6 条原文与用户偏好），避免超出模型上下文

## 技术架构

| 模块 | 技术栈 | 说明 |
| --- | --- | --- |
| 前端 | Vue 3 + Vite | 对话式 UI，分支树展示，气象播报单侧栏 |
| 后端 API | FastAPI | `/answer` 接口，支持从历史检查点 fork 执行 |
| 图编排 | LangGraph + RedisSaver | 节点：input → router → weather / weather_analysis / general；历史过长时 input 节点自动摘要压缩 |
| MCP 服务器 | FastMCP (streamable-http) | 两个工具：`get_weather`（Open-Meteo 天气，地址解析内部走高德地理编码）+ `get_time`（北京时间） |
| 模型 | OpenAI 兼容 API + Ollama | 主对话与子 Agent 经 `init_chat_model` 加载（`chat_model` 可选云端/本地）；路由模型按 `route_model` 独立选择；嵌入模型走 Ollama |
| RAG | RedisVectorStore + OllamaEmbeddings | PyMuPDFLoader → 切分 → 向量化 → 相似度检索（阈值过滤） |

## 目录结构

```
project2/
├── LICENSE                    # MIT 许可证
├── .gitignore                 # Git 忽略规则
├── requirements.txt           # 后端 Python 依赖
├── backend/                   # 后端（所有 Python 服务）
│   ├── mcp.json               # MCP 客户端连接配置（端口指向 MCP 服务器）
│   ├── api.py                 # FastAPI 入口（/answer；支持 `__root__` 特殊检查点）
│   ├── node.py                # LangGraph 状态图定义与节点实现
│   ├── model.py               # 模型工厂（主对话模型 cloud/local、路由模型、embeddings）
│   ├── tool.py                # MCP 天气服务器（get_weather 天气查询 + get_time 北京时间；get_weather 内部经高德地理编码解析地址）
│   ├── rag.py                 # RAG：PDF 入库、索引删除、向量检索
│   └── rag/                   # 气象知识资料源（内置气象 PDF 及国标/科普等资料，由 rag.py 读取入库）
└── frontend/                  # Vue 3 前端
    ├── index.html
    ├── package.json           # 依赖与脚本（npm run dev）
    ├── vite.config.js         # 端口 5173，代理 /answer 到 5000
    └── src/
        ├── main.js
        ├── style.css
        ├── markdown.js        # 轻量 Markdown 渲染（对话气泡与播报卡片共用，安全转义后只注入白名单标签）
        ├── App.vue            # 分支会话主界面（含气象播报单侧栏）
        └── components/
            └── WeatherReport.vue  # 气象播报单卡片
```

## 环境要求

- Python 3.10+
- Redis（`.env` 中默认 `redis://localhost:26379`，需支持 Redis 向量检索）
- Ollama（默认 `http://localhost:11434`，需本地对话模型（如 `qwen3.5:4b`）与嵌入模型 `qwen3-embedding:latest`）
- Node.js + npm（前端构建）

## 安装

```bat
:: 1. 后端依赖
pip install -r requirements.txt

:: 2. 前端依赖（在 frontend 目录下）
cd frontend
npm install
```

## 配置

编辑 `backend/.env`，所需变量如下（`—` 表示无默认值、必填）：

| 变量 | 默认值 | 说明 |
| --- | --- | --- |
| `REDIS_URL` | `redis://localhost:26379` | Redis 地址（检查点 + 向量库共用） |
| `model` | `deepseek-v4-flash` | OpenAI 兼容主对话模型标识（播报 / 子 Agent / 知识问答） |
| `model_provider` | `openai` | 云端模型供应商 |
| `model_api` | — | 云端模型 API Key（必填） |
| `base_url` | — | OpenAI 兼容 API 地址（必填） |
| `chat_model` | `cloud` | 主对话模型来源：`cloud`=云端 `model` / `local`=本地 `ollama_model` |
| `route_model` | `cloud` | 路由意图分类模型：`cloud`=云端 `model` / `local`=本地 `ollama_model` |
| `ollama_url` | `http://localhost:11434` | Ollama 服务地址 |
| `ollama_model` | `qwen3.5:4b` | 本地对话模型（`chat_model` / `route_model` 为 `local` 时使用） |
| `embeddings_model` | `qwen3-embedding:latest` | Ollama 嵌入模型（RAG 向量化） |
| `ollama_reasoning` | `false` | 本地模型推理模式开关 |
| `ollama_temperature` | `0.7` | 本地模型采样温度 |
| `host` / `port` | `127.0.0.1` / `8000` | MCP 天气服务器监听地址与端口 |
| `amap_key` | — | 高德地图 Web 服务 Key（地理编码，必填） |

初始化 RAG（可选，需 Redis + Ollama 就绪）：

```bat
cd backend
python rag.py   # 将 rag/ 目录下的气象资料 PDF（内置气象 PDF + 国标/科普资料）写入 Redis 索引，并执行一次检索调试；add_rag_pdf(file_path=...) 可传入自定义 PDF 路径
```

## 启动

```bat
:: 1. MCP 天气服务器（backend 目录）
python tool.py

:: 2. 后端 API（backend 目录）
python -m uvicorn api:app --host 127.0.0.1 --port 5000

:: 3. 前端（frontend 目录）
npm run dev
```

> 启动前请确保 Redis 与 Ollama 已运行。前端通过 Vite 代理 `/answer` 到 `127.0.0.1:5000` 以避免跨域。
> 也可直接运行根目录 `start.bat` 一键启动三项服务（MCP 天气服务器 `8000`、后端 API `5000`、前端 `5173`）。该脚本为本地文件（已被 .gitignore 排除），需先按本机环境修改其中的 `PYTHON` 路径；`api.py` 也支持 `python api.py` 直接跑一次调试查询。

## 核心流程

```
用户提问 → input 节点（写入 HumanMessage；历史过长时先压缩为摘要）
        → router 节点（LLM 三分类，含重复询问兜底校验；路由模型按 `route_model` 可选云端或本地）
            ├── 2 实时查询 → weather 节点
            │     ├─ 初始化 MCP 客户端（mcp.json）
            │     ├─ 子 Agent（含 SummarizationMiddleware）调用工具 → 结构化 Result
            │     └─ 写入 messages 与 result
            ├── 1 知识问答 → weather_analysis 节点（RAG 检索 + 子 Agent 作答）
            └── 0 无关拒绝 → general 节点
```

检查点由 `RedisSaver` 维护（TTL 30 分钟滑动续期），`/answer` 支持传入 `checkpoint_id` 从历史检查点 fork 执行，实现前端的分支与会话回溯；特殊值 `__root__` 表示从线程最旧的初始（空）检查点继续，用于"重新回答 / 编辑第一轮"。

## API 接口

**POST `/answer`**

```json
{ "thread_id": "12", "question": "北理工明天天气如何", "checkpoint_id": null }
```

返回：

```json
{
  "result": { "time": "...", "address": "...", "summary": "...", "weather": "...", "clothing_advice": "...", "travel_tips": "...", "healthy_tips": "...", "result": "明天北京多云转晴，气温 24~32°C……" },
  "before_checkpoint_id": "提问前基准检查点",
  "after_checkpoint_id": "本次回答产生的检查点"
}
```

> `result` 类型因路由分支而异：实时天气查询返回结构化 `dict`（内含 `result` 字段，即展示在对话消息流中的"问题答案"正文，前端按 Markdown 渲染）；知识问答 / 无关拒绝 / 兜底场景返回 `str`；天气服务不可用时为 `null`。
> `checkpoint_id` 传入历史检查点 id 时从该处 fork 生成独立分支（不污染原记录）；传 `__root__` 时从线程初始空检查点重新执行；非法值返回 400。

## 效果演示

- 问：`北理工明天天气如何` → 结构化天气播报卡片（对话消息流中展示天气概括正文，左侧气象播报单同步渲染详情）
- 问：`为什么会下雪？` → RAG 知识问答
- 问：`帮我写封邮件` → 无关拒绝提示
- 多轮：`那后天呢？` → 时间维度追问，触发新的实时查询
- 分支：对任意一轮点击「重新回答 / 编辑」生成新版本，问答可分别翻页切换；点击「撤销」删除该问题及其后续

## License

[MIT](LICENSE) © SunnyWeather Contributors