from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from node import get_graph

from dotenv import load_dotenv

load_dotenv()  # 加载 .env 文件中的环境变量

# 语义标记：从线程最旧的初始（空）检查点继续，用于「重新回答/撤销第一轮」
ROOT_MARKER = "__root__"


class Question(BaseModel):
    thread_id: str
    question: str | None = None  # 可选字段
    checkpoint_id: str | None = (
        None  # 可选：从指定历史检查点分支继续（重新回答/选择续接点）
    )


app = FastAPI()


def _history(graph, thread_id: str):
    """线程内全部检查点（最新在前）。"""
    return list(graph.get_state_history({"configurable": {"thread_id": thread_id}}))


def _resolve_cid(graph, thread_id: str, checkpoint_id: str) -> str | None:
    """把请求中的 checkpoint_id 解析为线程内真实存在的检查点 id。

    - "__root__"：取最旧（初始空状态）检查点；线程无历史时返回 None
    - 其他值：必须真实存在于历史中，否则抛 400（防止误删 / 误回滚）
    """
    history = _history(graph, thread_id)
    if checkpoint_id == ROOT_MARKER:
        return history[-1].config["configurable"]["checkpoint_id"] if history else None
    existing = {s.config["configurable"]["checkpoint_id"] for s in history}
    if checkpoint_id not in existing:
        raise HTTPException(400, "checkpoint_id 不存在或已过期")
    return checkpoint_id


@app.post("/answer")
def answer(question: Question):
    graph = get_graph()
    thread_id = "user_" + question.thread_id
    cfg = {"configurable": {"thread_id": thread_id}}

    # 指定 checkpoint_id 时，从该历史检查点 fork 执行，生成独立分支（不污染原记录）
    if question.checkpoint_id:
        cid = _resolve_cid(graph, thread_id, question.checkpoint_id)
        if cid:
            cfg["configurable"]["checkpoint_id"] = cid

    before_cid = graph.get_state(cfg).config["configurable"].get("checkpoint_id")
    result = graph.invoke({"question": question.question}, cfg)
    after_cid = (
        graph.get_state({"configurable": {"thread_id": thread_id}})
        .config["configurable"]
        .get("checkpoint_id")
    )
    return {
        "result": result["result"],
        "before_checkpoint_id": before_cid,  # 该问题提问前（重新回答 / 撤销的基准）
        "after_checkpoint_id": after_cid,  # 该回答产生的检查点（后续分支的基准）
    }


class Revoke(BaseModel):
    checkpoint_id: str | None = None  # 不传则清空整个线程
    thread_id: str


@app.post("/revoke")
def revoke_checkpoint(revoke: Revoke):
    graph = get_graph()
    checkpointer = graph.checkpointer  # RedisSaver
    thread_id = "user_" + revoke.thread_id

    # 未指定 checkpoint_id：删除整个线程（回退到最初）
    if not revoke.checkpoint_id:
        checkpointer.delete_thread(thread_id)
        return {"success": True}

    target = _resolve_cid(graph, thread_id, revoke.checkpoint_id)
    if target is None:  # 空线程，等价于清空
        checkpointer.delete_thread(thread_id)
        return {"success": True}

    snapshots = _history(graph, thread_id)
    by_id = {s.config["configurable"]["checkpoint_id"]: s for s in snapshots}

    # 保留 target 及其祖先链（即回退到的状态），其余检查点（含其它分支）全部删除
    keep, cur, guard = set(), target, 0
    while cur in by_id and guard <= len(by_id):
        keep.add(cur)
        parent = getattr(by_id[cur], "parent_config", None)
        cur = parent["configurable"]["checkpoint_id"] if parent else None
        guard += 1

    for cid in by_id:
        if cid not in keep:
            checkpointer.delete(thread_id, cid)
    return {"success": True}


# 仅直接运行 python api.py 时才执行调试查询
# uvicorn 导入模块时会运行在已有事件循环内，不能在模块顶层调用图（其中 weather 节点用 asyncio.run）
if __name__ == "__main__":
    print(answer(Question(question="北理明天天气如何", thread_id="12")))
