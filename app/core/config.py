from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    # .env 文件路径
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding='utf-8')

    # Qdrant
    QDRANT_HOST: str = "localhost"
    QDRANT_PORT: int = 6333

    # PostgreSQL
    POSTGRES_SERVER: str
    POSTGRES_PORT: int
    POSTGRES_USER: str
    POSTGRES_PASSWORD: str
    POSTGRES_DB: str

    @property
    def SQLALCHEMY_DATABASE_URI(self) -> str:
        """ 构造异步 PostgreSQL 连接字符串 """
        # 注意: 我们将使用 'postgresql+asyncpg'，但 psycopg2 (psycopg) 也可以
        # 为了与 psycopg2-binary 库兼容，我们使用 'postgresql+psycopg'
        # 你的 requirements.txt 应该有 psycopg2-binary
        return (
            f"postgresql+psycopg://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}@"
            f"{self.POSTGRES_SERVER}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"
        )

# 创建一个全局可用的配置实例
settings = Settings()