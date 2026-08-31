# 晴雨知心 · 天气播报助手（SunnyWeather）

基于 **LangGraph + LangChain + MCP + Redis** 的智能天气播报助手。用户输入地点与时间后，系统通过 MCP 天气服务器实时获取 Open-Meteo 气象数据，由 LLM 生成结构化、有温度的生活化天气播报（穿衣 / 出行 / 健康建议），并支持 RAG 气象知识问答与多轮分支会话（重新回答、编辑、撤销）。

## 功能特性

- **实时天气播报**：通过 MCP（FastMCP，streamable-http）调用天气工具，获取当前天气与逐小时预报（温度、湿度、体感、降水概率、风况等）
- **智能路由**：LangGraph 三分类路由（实时查询 / 知识问答 / 无关拒绝），结合多轮上下文判断"首次查询"与"重复询问"
- **RAG 知识问答**：PDF 气象资料切分后写入 Redis 向量库，结合 Ollama 嵌入模型检索作答
- **分支会话**：基于 Redis checkpointer，支持对任意一轮回答**重新回答 / 编辑 / 撤销**，问答以分支树形式组织，可自由切换版本
- **结构化播报**：AI 以固定结构（时间 / 地点 / 概况 / 详情 / 穿衣 / 出行 / 健康）返回，前端"气象播报单"面板独立渲染卡片

## 技术架构

| 模块 | 技术栈 | 说明 |
| --- | --- | --- |
| 前端 | Vue 3 + Vite | 对话式 UI，分支树展示，气象播报单侧栏 |
| 后端 API | FastAPI | `/answer`、`/revoke` 两个接口，与 LangGraph 图交互 |
| 图编排 | LangGraph + RedisSaver | 节点：input → router → weather / weather_analysis / general |
| MCP 服务器 | FastMCP (streamable-http) | 天气工具（Open-Meteo）+ 地理编码（高德地图） |
| 模型 | OpenAI 兼容 API + Ollama | 主对话与子 Agent 经 `init_chat_model` 加载；本地 Qwen 小模型做意图分类、嵌入模型走 Ollama |
| RAG | RedisVectorStore + OllamaEmbeddings | PDF → 切分 → 向量化 → 相似度检索 |

## 目录结构

```
project2/
├── LICENSE                    # MIT 许可证
├── .gitignore                 # Git 忽略规则
├── requirements.txt           # 后端 Python 依赖
├── start.bat                  # 一键启动（MCP 天气服务器 + 后端 API + 前端）
├── backend/                   # 后端（所有 Python 服务）
│   ├── .env                   # 环境变量（模型、密钥、Redis、Ollama 配置）
│   ├── mcp.json               # MCP 客户端连接配置（端口指向 MCP 服务器）
│   ├── api.py                 # FastAPI 入口（/answer、/revoke）
│   ├── node.py                # LangGraph 状态图定义与节点实现
│   ├── model.py               # 模型工厂（主对话模型 / Ollama 小模型 / embeddings）
│   ├── tool.py                # MCP 天气服务器（天气查询 + 高德地理编码）
│   ├── rag.py                 # RAG：PDF 入库、索引删除、向量检索
│   ├── test.py                # 图调用调试脚本
│   └── rag/9787502958572_L.pdf# 气象知识资料源
└── frontend/                  # Vue 3 前端
    ├── index.html
    ├── package.json           # 依赖与脚本（npm run dev）
    ├── vite.config.js         # 端口 5173，代理 /answer、/revoke 到 5000
    └── src/
        ├── main.js
        ├── style.css
        ├── App.vue            # 分支会话主界面
        └── components/WeatherReport.vue  # 气象播报单卡片
```

## 环境要求

- Python 3.10+
- Redis（`.env` 中默认 `redis://localhost:26379`，另支持 Redis Stack 向量检索）
- Ollama（默认 `http://localhost:11434`，需对话模型如 `qwen3.5:9b` 与嵌入模型如 `qwen3-embedding:latest`）
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

编辑 `backend/.env`：

| 变量 | 说明 |
| --- | --- |
| `REDIS_URL` | Redis 地址（检查点 + 向量库共用） |
| `model` / `model_provider` / `model_api` / `base_url` | OpenAI 兼容主对话模型配置 |
| `ollama_url` / `ollama_model` / `embeddings_model` | 本地 Ollama 推理与嵌入模型 |
| `ollama_reasoning` / `ollama_temperature` | Ollama 小模型的推理模式与采样温度（可选） |
| `amap_key` | 高德地图 Web 服务 Key（地理编码） |

> 注意：`.env` 含密钥，请勿提交到版本库。

初始化 RAG（可选，需 Redis + Ollama 就绪）：

```bat
cd backend
python rag.py   # 默认执行 get_retriever 调试；初始化索引请打开 add_rag_pdf() 注释（缺省写入内置气象 PDF，也可传自定义 PDF 路径）
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

> 启动前请确保 Redis 与 Ollama 已运行。前端通过 Vite 代理 `/answer`、`/revoke` 到 `127.0.0.1:5000` 以避免跨域。
> 也可直接运行根目录 `start.bat` 一键启动三项服务（MCP 天气服务器 `8000`、后端 API `5000`、前端 `5173`）。

## 核心流程

```
用户提问 → input 节点（写入 HumanMessage）
        → router 节点（LLM 三分类，含重复询问兜底校验）
            ├── 2 实时查询 → weather 节点
            │     ├─ 初始化 MCP 客户端（mcp.json）
            │     ├─ 子 Agent 调用天气工具 → 结构化 Result
            │     └─ 写入 messages 与 result
            ├── 1 知识问答 → weather_analysis 节点（RAG 检索 + 子 Agent 作答）
            └── 0 无关拒绝 → general 节点
```

检查点由 `RedisSaver` 维护（TTL 30 分钟滑动续期），`/answer` 支持传入 `checkpoint_id` 从历史检查点 fork 执行，实现前端的分支与会话回溯。

## API 接口

**POST `/answer`**

```json
{ "thread_id": "12", "question": "北理工明天天气如何", "checkpoint_id": null }
```

返回：

```json
{
  "result": { "time": "...", "address": "...", "summary": "...", "weather": "...", "clothing_advice": "...", "travel_tips": "...", "healthy_tips": "..." },
  "before_checkpoint_id": "提问前基准检查点",
  "after_checkpoint_id": "本次回答产生的检查点"
}
```

> `result` 类型因路由分支而异：实时天气查询返回结构化 `dict`；知识问答 / 无关拒绝 / 兜底场景返回 `str`；天气服务不可用时为 `null`。

**POST `/revoke`** — 撤销某轮回答（回溯到指定检查点；不传 `checkpoint_id` 则清空整个线程）

```json
{ "thread_id": "12", "checkpoint_id": "xxx" }
```

## 效果演示

- 问：`北理工明天天气如何` → 结构化天气播报卡片
- 问：`为什么会下雪？` → RAG 知识问答
- 问：`帮我写封邮件` → 无关拒绝提示
- 多轮：`那后天呢？` → 时间维度追问，触发新的实时查询

## License

[MIT](LICENSE) © SunnyWeather Contributors