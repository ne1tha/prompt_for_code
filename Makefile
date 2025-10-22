# ===================================================================
# ==     知识智能平台 - 通用跨平台任务运行文件 (Makefile) v2.2     ==
# ===================================================================
#
# 该版本会自动使用系统默认的 `python3` 命令，兼容 Python 3.10+。
#
# 使用方法 (在 Linux, macOS, 或 Windows 的 Git Bash 中):
#   - make run          : [推荐] 自动安装依赖并启动所有服务
#   - make stop         : 停止并清理数据库
#   - make logs         : 查看数据库日志
#   - make clean        : (危险) 删除虚拟环境
#
SHELL := /bin/bash
# --- 变量定义 ---
# 使用通用的 python3 命令, 它会自动匹配您系统中的默认 Python 3 版本 (例如 3.10)
PYTHON_CMD := python3
VENV_DIR := venv
PYTHON := $(VENV_DIR)/bin/python
PIP := $(VENV_DIR)/bin/pip

# --- 核心命令 ---

.PHONY: run stop setup install logs clean help

# 'run' 
run: $(PIP) | $(PYTHON)
	@echo "🔵 正在开启docker"
	docker-compose up -d
	@echo "🔵 正在启动 FastAPI 应用..."
	@echo "⚠️  请注意: 此脚本不会自动设置代理。"
	@echo "   如有需要，请在终端中手动设置 (例: export HTTP_PROXY=...)"
	@echo "   服务器运行于 http://127.0.0.1:8000 (按 CTRL+C 停止)"
	@# 激活 venv 并运行 uvicorn
	@uvicorn app.main:app --reload --reload-exclude "uploads"


setup: $(PIP)
	@echo "🔵 正在安装/更新项目依赖于虚拟环境..."
	@source $(VENV_DIR)/bin/activate && $(PIP) install -r requirements.txt
	@echo "🔵 正在后台启动 Qdrant 数据库..."
	

# 这个目标用来创建虚拟环境，只有在 venv/bin/pip 文件不存在时才会执行
$(PIP):
	@echo "🔵 虚拟环境不存在, 正在创建 'venv'..."
	$(PYTHON_CMD) -m venv $(VENV_DIR)

# --- 辅助命令 ---

stop:
	@echo "🔴 正在停止并清理 Qdrant 数据库..."
	docker-compose down

logs:
	@echo "🔎 正在追踪 Qdrant 数据库日志 (按 CTRL+C 退出)..."
	docker-compose logs -f qdrant

clean:
	@echo "🔥 正在删除 Python 虚拟环境..."
	rm -rf $(VENV_DIR)

help:
	@echo "✅ 自定义命令已加载:"
	@echo "--------------------------------------------------"
	@echo "  make run          -> [推荐] 自动安装依赖并启动所有服务"
	@echo "  make stop         -> 停止并清理数据库"
	@echo "  make logs         -> 查看数据库实时日志"
	@echo "  make clean        -> (危险) 删除虚拟环境"
	@echo "--------------------------------------------------"

# 将 help 设置为默认目标
.DEFAULT_GOAL := help

