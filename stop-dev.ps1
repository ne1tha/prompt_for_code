# ===================================================================
# ==         知识智能平台 - 一键停止开发环境脚本 (v1.0)         ==
# ===================================================================
#
# 使用方法:
#   在 PowerShell 终端中，运行 .\stop-dev.ps1
#
# 功能:
#   1. 使用 Docker Compose 停止并移除 Qdrant 容器。
#   2. 释放所有占用的系统资源（端口、CPU、内存）。
#

Write-Host "🔴 正在停止并清理所有开发服务..." -ForegroundColor Red

# 使用 docker-compose down 命令来停止并移除容器和网络
# 这能确保所有资源都被干净地释放
docker-compose down

Write-Host "✅ 所有服务已成功停止。您的开发环境已清理干净。" -ForegroundColor Green
Read-Host "按任意键退出..."
