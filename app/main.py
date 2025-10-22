from fastapi import FastAPI
from app.core.lifespan import lifespan
from app.api.router import api_router
from fastapi.middleware.cors import CORSMiddleware # (新增) 1. 导入中间件

# 1. 创建 FastAPI 主应用实例
app = FastAPI(
    title="知识智能平台 API",
    description="基于混合RAG架构的知识智能平台",
    version="1.0.0",
    lifespan=lifespan
)

# (新增) 2. 定义允许的来源
origins = [
    "http://localhost:5173", # 您的 Vue 前端地址
    "http://localhost",
]

# (新增) 3. 将 CORS 中间件添加到应用
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins, # 允许列表中的来源
    allow_credentials=True,
    allow_methods=["*"], # 允许所有方法 (GET, POST, PUT, DELETE etc.)
    allow_headers=["*"], # 允许所有请求头
)

# 4. 包含 API 总路由
app.include_router(api_router, prefix="/api/v1")

# (可选) 添加一个根路径重定向到文档
@app.get("/", include_in_schema=False)
async def redirect_to_docs():
    from fastapi.responses import RedirectResponse
    return RedirectResponse(url="/docs")