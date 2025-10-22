# ===================================================================
# ==              知识智能平台 - 应用启动脚本 (v1.0)             ==
# ===================================================================
#
# 使用方法:
#   1. 确保您已经成功运行过 .\setup.ps1。
#   2. 手动激活您偏好的 Python 环境 (例如 Conda)。
#   3. 在 PowerShell 终端中，运行 .\run-app.ps1
#

# --- 欢迎信息 ---
Write-Host "🚀 正在启动 FastAPI 应用..." -ForegroundColor Cyan

# --- 前置检查 ---
if (-not (Get-Command python -ErrorAction SilentlyContinue)) {
    Write-Host "❌ 错误: 找不到 'python' 命令。" -ForegroundColor Red
    Write-Host "   请在运行此脚本前，手动激活您的 Python 环境。"
    Read-Host "按任意键退出..."
    exit 1
}

# --- 启动 FastAPI 应用 ---
Write-Host "   服务器运行于 http://127.0.0.1:8000 (按 CTRL+C 停止)"

# 使用 --reload-dir 参数明确告诉 uvicorn 只监视 'app' 文件夹。
python -m uvicorn app.main:app --reload --reload-dir ./app

# 服务器停止后的清理信息
Write-Host ""
Write-Host "✅ FastAPI 应用已停止。" -ForegroundColor Green
Write-Host "   提示: Qdrant 数据库仍在后台运行。"
Write-Host "   如需停止数据库，请运行 .\stop-dev.ps1"
