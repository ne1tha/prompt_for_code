# ===================================================================
# ==            知识智能平台 - 开发环境设置脚本 (v1.0)           ==
# ===================================================================
#
# 使用方法:
#   1. 手动激活您偏好的 Python 环境 (例如 Conda)。
#   2. 在 PowerShell 终端中，运行 .\setup.ps1
#
# 功能:
#   - 安装/更新 requirements.txt 中定义的 Python 依赖。
#   - 启动 Docker Compose 中定义的所有服务 (Qdrant)。
#

# --- 欢迎信息 ---
Write-Host "🚀 正在初始化开发环境..." -ForegroundColor Cyan
Write-Host "--------------------------------------------------"

# --- 前置检查 ---
if (-not (Get-Command pip -ErrorAction SilentlyContinue)) {
    Write-Host "❌ 错误: 找不到 'pip' 命令。" -ForegroundColor Red
    Write-Host "   请在运行此脚本前，手动激活您的 Python 环境。"
    Read-Host "按任意键退出..."
    exit 1
}

# --- 步骤 1: 安装 Python 依赖 ---
Write-Host "🔵 [1/2] 正在安装/更新项目依赖..." -ForegroundColor White
pip install -r requirements_for_windows.txt
if ($LASTEXITCODE -ne 0) {
    Write-Host "❌ 依赖安装失败，请检查错误信息。" -ForegroundColor Red
    Read-Host "按任意键退出..."
    exit 1
}
Write-Host "✅ 依赖安装完成。" -ForegroundColor Green
Write-Host ""

# --- 步骤 2: 启动 Docker 服务 ---
Write-Host "🔵 [2/2] 正在后台启动 Qdrant 数据库..." -ForegroundColor White
docker-compose up -d
if ($LASTEXITCODE -ne 0) {
    Write-Host "❌ Docker 服务启动失败，请检查 Docker 是否正在运行。" -ForegroundColor Red
    Read-Host "按任意键退出..."
    exit 1
}
Write-Host "✅ Qdrant 数据库已在后台运行。" -ForegroundColor Green
Write-Host ""

# --- 完成信息 ---
Write-Host "✅ 开发环境设置完成。现在您可以运行 .\run.ps1 来启动应用了。" -ForegroundColor Green
Read-Host "按任意键退出..."
