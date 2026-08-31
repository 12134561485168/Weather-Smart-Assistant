from langchain_community.document_loaders import PyMuPDFLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_redis import RedisConfig, RedisVectorStore
import redis
from model import embeddings_model
import os
from dotenv import load_dotenv
load_dotenv()  # 加载 .env 文件中的环境变量


def add_rag_pdf(file_path=r"rag\9787502958572_L.pdf"):
    """加载 PDF 并分块写入 Redis 向量库。

    file_path 缺省时使用项目内置的气象资料 PDF。
    """
    # load() 为 BaseLoader 统一接口，返回 List[Document]
    documents = PyMuPDFLoader(
        file_path=file_path,
        mode="page",  # plain 纯文本；layout 按版面
    ).load()

    text_splitter = RecursiveCharacterTextSplitter(
        chunk_size=500, chunk_overlap=50, length_function=len
    )

    # 直接对 Document 列表分割，返回更小的 Document 列表（需保留 metadata）
    splitter_documents = text_splitter.split_documents(documents)

    embeddings = embeddings_model()

    # 用新库 langchain_redis 批量写入并建索引（默认字段 embedding/text，键前缀 weather）
    re = RedisVectorStore.from_documents(
        documents=[splitter_documents[0]],
        embedding=embeddings,
        config=RedisConfig(
            index_name="weather",
            redis_url=os.getenv("REDIS_URL"),
        ),
    )
    for i in splitter_documents[1:]:
        re.add_documents([i])

def del_rag(index_name):
    # 直接通过 redis 客户端删除索引及关联文档
    client = redis.from_url(os.getenv("REDIS_URL"))
    client.ft(index_name).dropindex(delete_documents=True)


def get_retriever(question):
    embeddings = embeddings_model()
    config = RedisConfig(
        index_name="weather",
        redis_url=os.getenv("REDIS_URL"),
    )

    vector_store = RedisVectorStore(embeddings, config=config)
    results = vector_store.similarity_search_with_score(question,5)
    result = ''
    for i,j in results:
        if j >0.5:
            result += i.page_content
    return result

if __name__ == "__main__":
    # del_rag("weather")
    # add_rag_pdf()
    print(get_retriever('重大气象灾害之后要注意什么'))