import json
import re
from functools import lru_cache
import asyncio
from langchain_mcp_adapters.client import MultiServerMCPClient
from langchain.agents import create_agent
from model import chat_model, chat_router_model
from langchain_core.messages import HumanMessage, SystemMessage, AIMessage,RemoveMessage
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.output_parsers import JsonOutputParser
from typing_extensions import TypedDict
from typing import Annotated, List, get_type_hints
from langgraph.graph import StateGraph, START, END
from langgraph.graph.message import add_messages, REMOVE_ALL_MESSAGES
from langgraph._internal._constants import CONFIG_KEY_CHECKPOINTER
from langchain.agents.structured_output import ToolStrategy
from langgraph.checkpoint.redis import RedisSaver
from langchain.agents.middleware import SummarizationMiddleware
import os
from rag import get_retriever


class Result(TypedDict):
    time: Annotated[str, "时间"]
    address: Annotated[str, "地点"]
    summary: Annotated[str, "天气情况的概况"]
    weather: Annotated[str, "天气的详情"]
    clothing_advice: Annotated[str, "穿衣建议"]
    travel_tips: Annotated[str, "出行建议"]
    healthy_tips: Annotated[str, "健康防护"]
    result: Annotated[str, "问题结果"]


class InputState(TypedDict):
    question: str


class OutputState(TypedDict):
    result: dict|str


class GraphState(InputState, OutputState):
    messages: Annotated[list, add_messages]


with open("mcp.json", "r", encoding="utf-8") as f:
    config = json.load(f)


@lru_cache(maxsize=1)
def get_mcp_client() -> MultiServerMCPClient:
    """获取缓存的 MCP 客户端，避免每次天气查询都重复握手建立连接。"""
    return MultiServerMCPClient(connections=config)


def weather(state: GraphState):
    async def _run_async_logic():
        client = MultiServerMCPClient(connections=config)
        tools = await client.get_tools()
        agent = create_agent(
            chat_model(),
            tools=tools,
            system_prompt="""
            # 角色定义
            你是一位专业且富有温度的天气智能助手——「晴雨知心」。你的核心职责是：基于用户指定的时间（若未指定，则默认当前时间），将天气数据转化为自然、温暖、实用的生活化播报。

            # 核心原则
            1. **时间感知**：始终以用户明确提及的时间点为分析基准；若用户未提及时间，则以当前实际时间为基准。
            2. **数据完整**：在调用天气工具时，必须确保覆盖用户所需的全部时间段（如"这周""未来三天"），不得遗漏任何一天、任何一小时。
            3. **温度表达**：语言应像一位贴心的朋友在提醒对方，避免机械罗列数据；善用比喻、生活化表达和适度共情。
            4. **实用导向**：所有建议必须与当前具体天气数据紧密关联，杜绝泛泛而谈。

            # 输出结构（严格映射到结构化结果各字段，按序填充）
            # 字段对应：summary=天气总结，weather=天气详情，clothing_advice=穿衣建议，travel_tips=出行建议，healthy_tips=健康防护，result=问题答案；time/address 按查询结果填写
            # 排版规范：天气详情、穿衣、出行、健康等长文本一律用 "- " 要点列表逐条呈现（前端会把 "- " 自动渲染为圆点列表）；字段内容中不要写"**天气总结**：""**天气详情**："这类字段名标题

            ## ☀️ 智能播报（对应 summary 与 weather 两个字段）
            - **summary（天气总结）**：只用 1～2 句自然语言概括整体天气感受（如"今天是个适合出门晒太阳的好日子"），不要罗列数据，也不要出现"天气总结"等字眼。
            - **weather（天气详情）**：只写天气详情，逐条以 "- " 开头的要点列表呈现，不得包含天气总结内容，也不得加"**天气详情**：""**天气总结**："等标题；条目须覆盖：天气状况、气温范围（最高/最低）、体感温度、湿度、风向风力、空气质量指数（AQI）、紫外线强度、降水概率。
            - 若涉及多日预报，在 weather 中按日维度逐条列出。

            ## 👔 穿衣建议（clothing_advice）
            - 根据气温区间、风力及降水概率，给出具体到单品层次的搭配建议（如"建议内搭薄款长袖 + 外搭防风夹克"），以 "- " 要点列表呈现。
            - 昼夜温差大时，须特别提醒早晚增减衣物。
            - 有雨/雪时，提醒携带雨具或选择防水鞋。

            ## 🚗 出行建议（travel_tips）
            - 基于能见度、降水、风力、路面状况等，给出出行方式建议（自驾/公共交通/骑行/步行），以 "- " 要点列出。
            - 明确标注是否适合户外活动，若不适合，建议替代方案。
            - 涉及极端天气（暴雨、台风、高温红色预警等）时，须给出明确的警示性提醒。

            ## 🌿 健康防护（healthy_tips）
            - 根据气温、湿度、紫外线、空气质量等，给出针对性健康提示（如防晒、补水、防过敏、防中暑、防呼吸道不适等），以 "- " 要点列出。
            - 对特殊人群（老人、儿童、敏感体质者）酌情补充提醒。
            - 语气关切但不过度焦虑，保持积极正向。

            ## 问题答案（写入 result 字段）
            - `result` 字段是本轮回答的正文，会在对话消息流中直接展示给用户，必须用自然、完整、可直接阅读的口吻撰写。
            - 纯天气查询（用户除天气外未提出其他问题）时：`result` 必须概括本轮的天气情况，用 1～2 句把查询到的天气要点口语化复述给用户（如"明天北京多云转晴，气温 24~32°C，午间体感偏闷热，早晚出门记得加件薄外套"），让用户不看面板也能知道天气核心结论。
            - 严禁出现"无其他问题需要额外回答""已按当前时间完成播报"等元话语/程序化口吻；也不要写"详见左侧面板 / 见气象播报单"等依赖界面元素的表述。
            - 若用户除天气外还提出其他问题（如穿衣、出行、健康、闲聊等）：先在各对应板块给出详细内容，再于 `result` 中一并给出简明完整的答复，务必覆盖用户的所有问题点，不得遗漏。

            # 语言风格规范
            - 面向用户直接对话，使用"您"或"你"（保持亲切，不过度正式）。
            - 适度使用 emoji 作为板块标识和情绪点缀，但正文中不滥用。
            - 避免生硬的数据堆砌；数据应融入自然语句中（如"午后气温将攀升至 33°C，体感偏闷热"而非"温度：33°C"）。
            - 结尾可附一句轻松的关怀语（如"出门记得带把伞，别让突如其来的雨打乱了好心情 🌂"）。

            # 异常处理
            - 天气查询工具返回None时，说明天气查询工具目前不可用，可以返回给用户，让用户简述天气后再提问。
            """,
            response_format=Result,
        )
        length = len(state["messages"])
        response = await agent.ainvoke(
            {"messages": state["messages"]},
            # 防止继承父图的 RedisSaver（同步 saver 不支持异步 agent 的
            # aget_tuple），子 agent 使用独立无 checkpointer 的会话
            {"configurable": {CONFIG_KEY_CHECKPOINTER: None}},
        )
        return response["messages"][length:], response["structured_response"]

    try:
        messages, result = asyncio.run(_run_async_logic())
        if result == None:
            result = messages[-1].content
        return {"messages": messages, "result": result}
    except:
        return None


def input(state: GraphState):
    # 历史消息过长时，先用 chat_model 压缩为摘要，避免超出模型上下文
    history = state.get("messages") or []
    total_chars = sum(
        len(m.content if isinstance(m.content, str) else str(m.content or ""))
        for m in history
    )
    # 粗略估算 token（约 1 token ≈ 4 字符）；阈值由环境变量控制，
    # 默认 4096，参考本地模型的 num_ctx 或云端模型上下文按需调整
    threshold_tokens = int(os.getenv("SUMMARY_THRESHOLD_TOKENS", "4096"))
    if total_chars // 4 > threshold_tokens:
        # 最近 6 条消息保留原文，更早的历史才做摘要
        older, newest = history[:-6], history[-6:]
        update = [RemoveMessage(id=REMOVE_ALL_MESSAGES)]  # 清空旧历史后整体替换
        if older:
            summary = chat_model().invoke(
                [
                    SystemMessage(
                        content="你是一个对话压缩助手。请将以下对话历史压缩为一份简洁摘要，便于后续继续对话。\n"
                        "具体要求：\n"
                        "1. 天气查询结果：只保留最近两次查询的时间、地点与天气结果，更早的查询结果可省略或一笔带过；\n"
                        "2. 用户偏好（如关注的气象指标、语言偏好等）与未完成的需求：全部保留，不得遗漏；\n"
                        "3. 寒暄、客套、重复内容等无关信息可省略。"
                    ),
                    *older,
                ]
            )
            update.append(
                SystemMessage(content=f"【以下为之前对话的摘要】\n{summary.content}")
            )
        update.extend(newest)
        update.append(HumanMessage(content=state["question"]))
        return {"messages": update}
    return {"messages": HumanMessage(content=state["question"])}


def router(state: GraphState):
    model = chat_router_model()

    class router_data(TypedDict):
        flag: Annotated[int, "判断用户请求类型"]

    model = model.with_structured_output(router_data)
    result = model.invoke([SystemMessage(content="""
        # Role
        你是天气智能助手「晴雨知心」的意图识别引擎。结合多轮对话上下文，把用户最新请求归类为 0、1、2 之一，只输出对应数字。

        # 分类规则（按优先级从高到低判定）
        ## 类别 0：超出工作范围（Out of Scope）
        与天气、气候、天气衍生影响及助手交互完全无关的请求，如写邮件、问首都、聊股票、讲笑话、推荐电影等。

        ## 类别 2：需要实时查询，且历史中未查过（First-time Real-time Query）
        必须获取特定地点 + 特定时间 + 实时气象指标才能回答，且该组合在本次会话历史中从未查询播报过。
        - 注意先核对历史：若地点、时间、指标与已播报过的完全一致（含换说法重复），则归 1，不得归 2。
        - 多轮追问"新"信息算首次：如上轮查过"北京·今天"，本轮"那明天呢？"（时间维度变新）→ 归 2。

        ## 类别 1：其余情况（Knowledge/Recall Only）
        - 气象科普、气候常识、长期气候特点、基于天气的通用生活建议；
        - 寒暄、问候、感谢、自我介绍、使用咨询；
        - 重复询问历史中已播报过的同一份天气；
        - 追问上一条知识类回复（如"再解释一下"），不涉及新的实时数据。

        # 判定参考
        1. 不确定是否需要实时数据时，倾向归 2（交给实时查询节点判断），切勿误判为 0；
        2. 能判断为"重复查询已播报天气"时，必须归 1。

        # Output Format
        只输出一个阿拉伯数字（0/1/2），禁止输出任何解释、标点、前后缀。
        """)] + state["messages"])

    # 解析分类结果（兼容结构化输出 dict 与纯字符串两种形态）
    if isinstance(result, str):
        match = re.search(r"[012]", result)
        flag = int(match.group()) if match else 2
    else:
        try:
            flag = int(result.get("flag", 2))
        except (TypeError, ValueError):
            flag = 2

    return flag


def weather_analysis(state: GraphState):
    retriever = get_retriever(state["messages"][-1].content)
    agent = create_agent(
        chat_model(),
        system_prompt=f"""
        # 角色定义
        你是一位专业且富有温度的天气智能助手——「晴雨知心」。你当前处于【知识问答模式】：负责解答气象科普、气候常识、基于天气的通用生活建议，以及与用户进行日常寒暄。

        # 参考知识（针对当前问题的检索资料）
        【{retriever}】
        以上为根据用户问题检索到的气象类资料。请优先据此作答；若资料为空或与问题无关，请基于自身专业知识回答，不得编造。

        # 回答原则
        1. **知识准确**：讲解气象原理、天气成因（如"为什么会下雪"）时，应结合检索资料，用通俗易懂、生活化的语言解释清楚。
        2. **重复询问（历史已有播报）**：若用户是在重复询问本段对话中已经播报过的同一份天气（相同地点 + 时间，问法一致或类似），请直接从对话历史中已有的天气播报内容复述或概括回应，不要再引导用户重新提供时间地点，也不要编造新数值。
        3. **不虚构实时数据**：若用户询问的是历史中从未播报过的特定时间+地点的实时天气，你当前没有实时查询能力，请勿编造数值，应礼貌说明并引导用户提供具体的时间与地点后再实时查询。
        4. **生活建议落地**：针对穿衣、出行、健康等通用问题，结合相关天气常识给出具体、可执行的建议。
        5. **寒暄得体**：面对问候、感谢、自我介绍等，回复亲切简洁，并自然引导用户说出想查询的时间与地点。
        6. **诚实作答**：资料与自身知识均无法覆盖时，坦然说明不确定，绝不臆造。

        # 语言风格
        - 以自然、温暖的口吻直接对话，无需按固定板块输出。
        - 礼貌用语 + 适度生活化比喻，可用少量 emoji 点缀，避免数据堆砌。
        """,
    )
    length = len(state["messages"])
    response = agent.invoke(
        {"messages": state["messages"]},
        # 防止继承父图的 RedisSaver（同步 saver 不支持异步 agent 的
        # aget_tuple），子 agent 使用独立无 checkpointer 的会话
        {"configurable": {CONFIG_KEY_CHECKPOINTER: None}},
    )
    return {
        "messages": response["messages"][length:],
        "result": response["messages"][-1].content,
    }


def general(state: GraphState):
    return {
        "messages": [RemoveMessage(id=state["messages"][-1].id)],
        "result": "你的问题与天气无关，请你重新告诉我你想了解的时间与地点",
    }


@lru_cache(maxsize=1)
def get_graph():
    graph = StateGraph(GraphState, input_schema=InputState, output_schema=OutputState)
    graph.add_node("weather", weather)
    graph.add_node("input", input)
    graph.add_node("general", general)
    graph.add_node("weather_analysis", weather_analysis)
    graph.add_edge(START, "input")
    graph.add_conditional_edges(
        "input", router, {2: "weather", 0: "general", 1: "weather_analysis"}
    )
    graph.add_edge("general", END)
    graph.add_edge("weather", END)
    graph.add_edge("weather_analysis", END)
    checkpointer = RedisSaver(
        os.getenv("REDIS_URL"),
        ttl={
            "default_ttl": 30,  # TTL 时长（分钟）
            "refresh_on_read": True,  # 读取时刷新 TTL（滑动续期）
        },
    )
    checkpointer.setup()

    return graph.compile(checkpointer=checkpointer)
