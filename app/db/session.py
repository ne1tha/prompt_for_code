from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, DeclarativeBase
from app.core.config import settings

# 创建 SQLAlchemy engine
# 'pool_pre_ping=True' 检查连接是否仍然存在
engine = create_engine(
    settings.SQLALCHEMY_DATABASE_URI,
    pool_pre_ping=True
)

# 创建一个 SessionLocal 类，用于生成新的数据库会话
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# 创建一个 Base 类，我们的 ORM 模型将继承它
class Base(DeclarativeBase):
    pass

# (未来) 在这里导入所有模型，以便 Base 能够“看到”它们
from app.models.model import Model
from app.models.knowledgebase import KnowledgeBase

def init_db():
    """
    (可选) 在应用启动时创建所有数据库表
    在开发中很有用
    """
    # 注意：在生产环境中，您可能希望使用 Alembic 来管理迁移
    Base.metadata.create_all(bind=engine)