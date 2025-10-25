# 知识智能平台 (Knowledge Intelligence Platform)

这是一个全栈 Web 应用程序，旨在实现智能化的源代码分析和知识管理。该平台允许用户上传代码库（作为单独文件或 `.zip`/`.rar` 压缩包），将其处理为可查询的知识库，并生成高层次的 AI 驱动的代码洞察。

### 重要：
此应用目前为测试版本，存在以下问题：
- 前端界面不完善（作者不是前端大手子）
- 后端功能也会有一些隐藏漏洞（作者还没有搭CI大规模测试）
- 目前还在完善，随时欢迎pr

## 核心功能

  * **知识库管理:** 支持上传代码文件、`.zip` 或 `.rar` 压缩包作为知识库（KB）的来源。
  * **模型管理:** 提供统一界面，用于配置和管理多种 AI 模型，包括嵌入（Embedding）模型和生成（Generative）模型（例如，支持本地 Ollama 和远程 API）。
  * **异步摄取管道 (L1):**
      * 一个强大的后台处理任务，负责解压文件、智能分割代码（能识别 Python, Java, JavaScript 等）。
      * 使用选定的嵌入模型（包括动态维度发现）生成向量。
      * 将向量和元数据存入 Qdrant 向量数据库。
  * **RAG 检索:**
      * 提供 "Prompt" 界面，用于通过检索增强生成 (RAG) 与您的代码库进行“聊天”。
  * **AI 驱动的代码分析 (L2):**
      * **L2a (AI 摘要):** 自动生成代码库的高级 Markdown 摘要。对于大型项目，它会智能地使用 RAG 来获取上下文，以生成准确的总结。
      * **L2b (知识图谱):** 对源代码进行深度分析，提取类继承、函数调用等结构化关系，并将其保存为知识图谱 (JSON 格式)。
  * **动态前端:**
      * 采用 Vue 3 和 Pinia 构建的响应式前端。
      * 通过 API 轮询，为知识库解析等长时间运行的任务提供实时的进度更新和状态反馈。

## 架构概览

本项目采用前后端分离的现代分层架构，确保了高度的可维护性和可扩展性。

### 技术栈

  * **后端:**
      * **框架:** FastAPI。
      * **架构:** 分层架构 (API 接口层, Services 业务逻辑层, CRUD 数据访问层, Schemas 数据模式层)。
      * **数据库:**
          * **关系型 (PostgreSQL):** 存储知识库、模型和用户的元数据。
          * **向量 (Qdrant):** 存储代码块的向量嵌入，用于 RAG 检索。
  * **前端:**
      * **框架:** Vue 3 (Composition API)。
      * **状态管理:** Pinia (`knowledgeBase.js`, `modelStore.js`)。
      * **UI 库:** Element Plus。

### 核心数据流

1.  **上传 (L0):** 用户通过 Vue 前端上传一个 `.zip` 压缩包。文件被保存到服务器，并在 PostgreSQL 中创建一条知识库 (KB) 记录。
2.  **解析 (L1):** 用户在前端选择一个“嵌入模型”并点击“解析”。
      * `kb_service.py` 验证模型，准备 Qdrant 集合，并启动一个后台任务 `run_ingestion_pipeline`。
      * `ingestion_pipeline.py` 开始执行：解压 `.zip` 包，遍历所有代码文件，使用 `CodeSplitter` 进行智能切分，调用嵌入模型 API 生成向量，最后将向量和元数据批量上传到 Qdrant。
      * 同时，`knowledgeBase.js` (Pinia) 开始轮询该 KB 的状态，在前端实时显示进度条。
3.  **分析 (L2):** L1 任务完成后 (状态变为 `ready`)，用户可以生成 L2 知识：
      * **L2a (摘要):** `generation_service.py` 被调用。它首先对 L1 数据执行 RAG 检索（`_perform_rag_retrieval`）以收集相关代码块，然后将这些代码块连同 Prompt 一起发送给一个生成模型，最后将返回的 Markdown 摘要保存为新的 L2a 知识库。
      * **L2b (图谱):** `kg_service.py` 被调用。它会重新读取（或解压）L1 的 *原始* 文件，逐个文件发送给 LLM 进行三元组（如函数调用、类继承）提取，最后将所有三元组汇总并保存为一个 `.json` 知识图谱文件。
4.  **查询 (RAG):** 用户在 "Prompt" 界面 提问。
      * `rag_service.py` 接收到请求，使用 L1 知识库关联的嵌入模型将问题向量化。
      * `rag_service.py` 在 Qdrant 中搜索最相关的代码块。
      * `rag_service.py` 将代码块和原始问题组合成一个 Metaprompt，发送给生成模型，并将最终答案返回给前端。


### 依赖环境

  * Python 3.10+
  * Node.js (用于前端)
  * docker

### 启动 

1.  安装 Python 依赖:
    ```bash
    make setup
    ```
2.  运行后端
    ```bash
    make run
    ```
3.  运行前端
    ```bash
    cd ./vue-knowledge-base && npm run dev
    ```

## API 概览

后端 API 遵循 RESTful 规范，并定义在 `app/api/endpoints/` 中。主要端点包括：

  * `/api/v1/knowledgebases`: 知识库的
    CRUD。
  * `/api/v1/knowledgebases/{id}/upload`: 重新上传文件。
  * `/api/v1/knowledgebases/{id}/parse`: 启动 L1 解析任务。
  * `/api/v1/knowledgebases/{id}/cancel`: 取消 L1 解析任务。
  * `/api/v1/knowledgebases/{id}/generate-summary`: 启动 L2a 摘要生成。
  * `/api/v1/knowledgebases/{id}/generate-graph`: 启动 L2b 图谱生成。
  * `/api/v1/models`: 模型管理的 CRUD。
  * `/api/v1/rag/query`: (推断) 执行完整的 RAG 查询。
  * `/api/v1/rag/retrieve`: (推断) 仅检索上下文。

更详细的架构设计，请参阅 `前端架构书.md` 和 `后端架构书.md`。
