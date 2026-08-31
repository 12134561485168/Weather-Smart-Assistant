from langgraph.graph import StateGraph, START, END
from node import get_graph
import os
from dotenv import load_dotenv
load_dotenv()  # 加载 .env 文件中的环境变量

if __name__ == '__main__':
    graph = get_graph()
    config = {"configurable": {"thread_id": "test0"}}
    
    # for chunk, _metadata in graph.stream({"question": "北理工明天天气如何"}, stream_mode="messages"):
    #     # print(f"type of chunk:{type(chunk)}")  # 调试时可打开
    #     print(chunk)
    #     print(chunk.additional_kwargs.get('reasoning_content',''),end='')

    for chunk,_ in graph.stream({"question": "北理工明天天气如何"},config,stream_mode='messages'):
        if chunk.content!='':
            print(chunk.content,end='')
        else:
            try:
                # print(chunk.tool_call_chunks[-1].get('args',''),end='')
                print(chunk.additional_kwargs.get('reasoning_content',''),end='')
            except:
                pass

    # graph.invoke({"question": "北理工明天天气如何"},config)
    saved_state = graph.get_state(config)
    print(f"保存的状态: {saved_state.config['configurable']['checkpoint_id']}")
    # print(f"结果: {saved_state.values['result']}")
    print(f"过程：{list(reversed([i for i in graph.get_state_history(config)]))}")
    print(f"下一个节点: {saved_state.next}\n")