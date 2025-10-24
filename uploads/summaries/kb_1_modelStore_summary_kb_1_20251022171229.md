# `kb_1_modelStore.js` 模块总结

## 1. 主要目的
该文件定义了一个基于 Pinia 的状态管理 Store（`useModelStore`），用于集中管理与“模型”相关的应用状态和业务逻辑。其主要职责包括：
- 从后端 API 获取、添加、更新和删除模型数据。
- 维护本地模型列表、选中模型、搜索条件和加载/错误状态。
- 提供过滤后的模型列表以支持前端搜索功能。

## 2. 关键组件

### 函数
- **`handleResponse(response)`**  
  一个通用的响应处理函数，用于解析 API 响应并统一处理成功或失败情况，抛出包含详细信息的错误。

- **`fetchModels()`**  
  获取所有模型数据，并更新 `modelList`。

- **`addModel(newModel)`**  
  向服务器提交新模型，成功后将其加入 `modelList`。

- **`updateModel(updatedModel)`**  
  更新指定模型，同步更新本地列表和当前选中模型（如匹配）。

- **`deleteModel(id)`**  
  删除指定 ID 的模型，并从 `modelList` 中移除，若被删除的是当前选中模型则清空 `selectedModel`。

- **`setSelectedModel(model)`**  
  设置当前选中的模型。

### 状态属性（Reactive）
- `modelList`: 存储所有模型的数组。
- `selectedModel`: 当前选中的模型对象。
- `searchTerm`: 用户输入的搜索关键词。
- `isLoading`: 标识请求是否正在进行。
- `error`: 存储最近发生的错误消息。

### 计算属性
- **`filteredModelList`**  
  根据 `searchTerm` 对 `modelList` 进行名称模糊匹配过滤的结果。

## 3. 组件交互关系
- 所有 CRUD 操作函数（`fetchModels`, `addModel`, `updateModel`, `deleteModel`）均调用 `handleResponse` 来处理 HTTP 响应结果，确保错误能被捕获并传递给 UI 层。
- 状态变更通过直接修改 `ref` 实现，由 Vue 自动触发视图更新。
- `filteredModelList` 依赖 `modelList` 和 `searchTerm`，实现响应式过滤。
- 外部组件可通过 `useModelStore()` 使用该 Store 提供的状态和方法，实现跨组件共享模型数据。