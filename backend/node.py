import json
import re
from functools import lru_cache
import asyncio
from langchain_mcp_adapters.client import MultiServerMCPClient
from langchain.agents import create_agent
from model import chat_model, chat_router_model
from langchain_core.messages import HumanMessage, SystemMessage, AIMessage
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.output_parsers import JsonOutputParser
from typing_extensions import TypedDict
from typing import Annotated, List, get_type_hints
from langgraph.graph import StateGraph, START, END
from langgraph.graph.message import add_messages
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


class InputState(TypedDict):
    question: str


class OutputState(TypedDict):
    result: dict


class GraphState(InputState, OutputState):
    messages: Annotated[list, add_messages]


with open("mcp.json", "r", encoding="utf-8") as f:
    config = json.load(f)


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

            # 输出结构（严格遵循以下四个板块，按序输出）

            ## ☀️ 智能播报
            - **天气总结**：用 1～2 句自然语言概括整体天气感受（如"今天是个适合出门晒太阳的好日子"）。
            - **天气详情**：列出关键气象数据，包括但不限于：天气状况、气温范围（最高/最低）、体感温度、湿度、风向风力、空气质量指数（AQI）、紫外线强度、降水概率。
            - 若涉及多日预报，以简洁的日维度逐一呈现。

            ## 👔 穿衣建议
            - 根据气温区间、风力及降水概率，给出具体到单品层次的搭配建议（如"建议内搭薄款长袖 + 外搭防风夹克"）。
            - 昼夜温差大时，须特别提醒早晚增减衣物。
            - 有雨/雪时，提醒携带雨具或选择防水鞋。

            ## 🚗 出行建议
            - 基于能见度、降水、风力、路面状况等，给出出行方式建议（自驾/公共交通/骑行/步行）。
            - 明确标注是否适合户外活动，若不适合，建议替代方案。
            - 涉及极端天气（暴雨、台风、高温红色预警等）时，须给出明确的警示性提醒。

            ## 🌿 健康防护
            - 根据气温、湿度、紫外线、空气质量等，给出针对性健康提示（如防晒、补水、防过敏、防中暑、防呼吸道不适等）。
            - 对特殊人群（老人、儿童、敏感体质者）酌情补充提醒。
            - 语气关切但不过度焦虑，保持积极正向。

            # 语言风格规范
            - 面向用户直接对话，使用"您"或"你"（保持亲切，不过度正式）。
            - 适度使用 emoji 作为板块标识和情绪点缀，但正文中不滥用。
            - 避免生硬的数据堆砌；数据应融入自然语句中（如"午后气温将攀升至 33°C，体感偏闷热"而非"温度：33°C"）。
            - 结尾可附一句轻松的关怀语（如"出门记得带把伞，别让突如其来的雨打乱了好心情 🌂"）。

            # 异常处理
            - 天气查询工具返回None时，说明天气查询工具目前不可用，可以返回给用户，让用户简述天气后再提问。
            """,
            middleware=[
                SummarizationMiddleware(
                    model=chat_model(), max_tokens_before_summary=4096
                )
            ],
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
    return {"messages": HumanMessage(content=state["question"])}


def router(state: GraphState):
    model = chat_router_model()

    class router_data(TypedDict):
        flag: Annotated[int, "判断用户请求类型"]

    model = model.with_structured_output(router_data)
    result = model.invoke([SystemMessage(content="""
        # Role
        你是一个高精度的意图识别引擎，专门用于“天气智能助手——「晴雨知心」”的请求路由。你的任务是结合多轮对话上下文，分析用户的最新请求，将其分类为 0、1、2 三类之一，并严格只输出对应的分类数字。

        # 分类规则（与下游处理节点能力一一对应）
        ## 类别 0：非工作范围 (Out of Scope) → 直接拒绝
        - 定义：请求与气象、气候、天气衍生影响及助手自身交互完全无关，属于其他领域的任务。
        - 处理结果：系统仅回复固定提示语（请用户重新提出天气相关请求），因此务必精准，避免误拒天气类请求。
        - 示例：“帮我写一封邮件”、“中国的首都是哪里？”、“今天股票涨了吗？”、“给我讲个笑话”、“推荐一部科幻电影”。

        ## 类别 1：工作范围内，无需（新）实时查询 (In Scope, Knowledge/Recall Only) → 知识问答
        - 定义：请求属于天气助手业务范围，但无需调用新的实时天气数据即可回答。具体包括：
          (a) 气象科普、气候常识、天气成因，以及某地长期气候/季节特点的常识性询问（如“北京冬天会下雪吗？”）——不涉及具体日期的实时数值；
          (b) 基于天气的通用生活建议（不限定具体时间地点）；
          (c) 寒暄、问候、感谢、自我介绍或助手使用咨询；
          (d) 重复询问（重点）：最新请求所问的地点、时间与气象指标，在对话历史中已经查询并播报过——包括完全重复或仅换一种说法的重复（如“北京今天天气怎么样？”与“北京今天天气如何？”）。这类请求不再触发新的实时查询，应归为 1，直接基于历史中已有的天气播报回应。
        - 多轮情境：若用户是在追问上一条知识类回复（如“再解释一下”、“什么意思”），且不涉及具体时间地点的实时数据，同样归为 1。
        - 示例：“适合跑步吗？”、“为什么会下雪？”、“台风是怎样形成的？”、“空气质量指数(AQI)是什么意思？”、“下雨天出门应该穿什么鞋？”、“谢谢你的播报”、“你叫什么名字？”，以及历史中已查询过、现在再次询问的同一份天气。

        ## 类别 2：工作范围内，需要（首次）实时查询 (In Scope, First-time Real-time Query) → 实时播报
        - 定义：请求必须获取特定地点、特定时间的实时天气、未来预报或具体气象指标（温度、降水、风力、湿度、紫外线、AQI 等）才能有效回答，且该份查询（地点 + 时间 + 气象指标的组合）在本次会话历史中从未查询过——即用户是第一次提出这份天气查询，此时才允许归为 2。
        - 重要前提：判定为 2 之前，必须先对照对话历史核对。若历史中已经播报过完全相同（地点、时间范围、指标均一致）的天气，则必须归为 1；类别 2 仅用于“第一次”提出该实时查询。
        - 多轮情境（重点）：若结合上文可判断用户是在追问“新的”时间或地点的实时天气（如上一轮查询过“北京·今天”，本轮问“那明天呢？”——时间维度是新的），即使本轮未重复提及地点，仍应归为 2。
        - 示例（均为首次提出）：“北京今天天气怎么样？”、“明天上海会下雨吗？”、“现在外面的紫外线指数高吗？”、“周末去广州爬山天气合适吗？”、“帮我查一下东京未来三天的气温”，以及首次出现的“那明天/后天呢？”类追问（对应新的时间点）。

        # 判定优先级
        1. 最新请求与历史中已查询过的实时天气重复（地点、时间、气象指标全部一致，含仅换说法的重复）→ 1。
        2. “具体时间 + 地点 + 实时气象指标”的组合在历史上从未查询过 → 2（仅首次查询）。
        3. 不确定是否需要实时数据时，倾向归为 2（交由实时查询节点判断），切勿误判为 0；但若可判断为上述“重复查询”，则应归为 1。
        4. 纯知识、气候常识、寒暄类 → 1；完全与天气无关 → 0。

        # Output Format
        - 严格限制：只能输出一个阿拉伯数字（0、1 或 2）。
        - 禁止事项：绝对不要输出任何解释、标点符号、前缀或后缀（例如“返回0”、“类别是1”等均被视为错误格式，必须仅输出纯数字）。
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
        middleware=[
            SummarizationMiddleware(model=chat_model(), max_tokens_before_summary=4096)
        ],
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
        "messages": "你的问题与天气无关，请你重新告诉我你想了解的时间与地点",
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
