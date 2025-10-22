import time
import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI
from qdrant_client import QdrantClient
from qdrant_client.http.models import Distance, VectorParams
from app.core.config import settings
from app.db.session import init_db
from app.services.kb_service import UPLOADS_DIR


# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# 全局客户端实例，将在 lifespan 中初始化
qdrant_db = None

@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    FastAPI 启动和关闭事件处理器
    """
    # --- 应用启动 ---
    logger.info("FastAPI 应用启动...")

    # 1. (迁移) 初始化 Qdrant 连接
    global qdrant_db
    qdrant_db = QdrantClient(host=settings.QDRANT_HOST, port=settings.QDRANT_PORT)

    max_retries = 5
    retry_wait = 2
    for attempt in range(max_retries):
        try:
            # 检查 Qdrant 服务是否就绪
            qdrant_db.get_collections()
            logger.info("Qdrant 连接成功!")
            
            # (迁移) 检查并创建 'test_collection'
            try:
                qdrant_db.recreate_collection(
                    collection_name="test_collection",
                    vectors_config=VectorParams(size=384, distance=Distance.COSINE), # 假设使用 BGE-small 的 384 维
                )
                logger.info("'test_collection' 已创建或已存在。")
            except Exception as e:
                logger.warning(f"无法创建 'test_collection' (可能已存在且配置不同): {e}")

            break # 连接成功，退出重试
        except Exception as e:
            logger.warning(f"无法连接到 Qdrant (尝试 {attempt+1}/{max_retries}): {e}")
            if attempt + 1 == max_retries:
                logger.error("Qdrant 连接失败，已达最大重试次数。")
                # 您可以在此处引发异常以停止应用启动
                raise
            time.sleep(retry_wait)

    # 2. (新增) 初始化关系型数据库 (创建表)
    try:
        init_db()
        logger.info("关系型数据库表已初始化。")
    except Exception as e:
        logger.error(f"关系型数据库初始化失败: {e}")
        raise
#    而不是在文件被导入时运行，从而避免了重载循环
    try:
        UPLOADS_DIR.mkdir(exist_ok=True)
        logger.info(f"上传目录 '{UPLOADS_DIR}' 已创建或已存在。")
    except Exception as e:
        logger.error(f"创建上传目录失败: {e}")
        raise

    yield# 应用在此处运行

    # --- 应用关闭 ---
    logger.info("FastAPI 应用关闭...")
    # (如果需要，可以在此关闭连接池等)
    qdrant_db.close()
    logger.info("Qdrant 连接已关闭。")


def get_qdrant_client():
    """ 依赖项，用于在 API 端点中获取 Qdrant 客户端 """
    global qdrant_db
    return qdrant_db