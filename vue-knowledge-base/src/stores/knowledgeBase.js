import { defineStore } from 'pinia'
import { ref, computed } from 'vue'

// 假设你的 FastAPI 根路径是 /api/v1
const API_BASE_URL = '/api/v1'
const POLLING_INTERVAL = 3000 // 轮询间隔，3000ms

// 用于存储轮询定时器
const activePollers = ref({});
// (修正) 这是一个健壮的响应处理程序
async function handleResponse(response) {
  if (response.ok) {
    const text = await response.text();
    return text ? JSON.parse(text) : null;
  }
  let errorMsg = `HTTP Error ${response.status}: ${response.statusText}`;
  try {
    const errData = await response.json();
    errorMsg = errData.detail || JSON.stringify(errData);
  } catch (e) { /* 响应体不是 JSON */ }
  throw new Error(errorMsg);
}

export const useKnowledgeBaseStore = defineStore('knowledgeBase', () => {
  // --- State ---
  const knowledgeBaseList = ref([]);
  const selectedKnowledgeBase = ref(null);
  const searchTerm = ref('');
  const promptSelection = ref([]);

  const promptSelectedModel = ref(null); // (新增) 选中的模型
  const promptModeTable = ref('kb'); // (新增) 'kb' 或 'model'
  
  // 新增: 加载和错误状态
  const isLoading = ref(false);
  const error = ref(null);

  // --- Getters (Computed) ---
  const filteredKnowledgeBaseList = computed(() => {
    // ... (保持不变)
    if (!searchTerm.value) {
      return knowledgeBaseList.value;
    }
    return knowledgeBaseList.value.filter(item =>
      item.name.toLowerCase().includes(searchTerm.value.toLowerCase())
    );
  });

  const readyKnowledgeBaseList = computed(() => {
    // ... (保持不变)
    return knowledgeBaseList.value.filter(item => item.status === 'ready');
  });

  // --- Actions ---

  /**
   * (修复) 停止轮询时清理状态
   */
  function _stopPolling(id) {
    if (activePollers.value[id]) {
      console.log(`[Polling] Stopping poller for KB ${id}`);
      clearInterval(activePollers.value[id]);
      delete activePollers.value[id];
    }
  }


  /**
   * (新增) 从后端获取所有知识库
   */
async function fetchKnowledgeBases() {
  isLoading.value = true;
  error.value = null;
  try {
    const response = await fetch(`${API_BASE_URL}/knowledgebases`);
    const items = await handleResponse(response);
    
    // 修复：处理时间戳时区转换
    const processedItems = items.map(item => {
      if (item.updatedAt) {
        const backendDate = new Date(item.updatedAt);
        
        // 检查是否是 US 时区
        const isLikelyUSTimezone = backendDate.getTimezoneOffset() > 240;
        
        if (isLikelyUSTimezone) {
          const localDate = new Date(backendDate.getTime() + (backendDate.getTimezoneOffset() * 60000));
          return {
            ...item,
            updatedAt: localDate.toISOString()
          };
        }
      }
      return item;
    });
    
    processedItems.forEach(item => {
      if (item.status === 'processing' || 
          (item.parsingState && 
           (item.parsingState.stage === 'parsing' || 
            item.parsingState.stage === 'pending' || 
            item.parsingState.stage === 'picking_model'))) {
        _pollParsingStatus(item.id);
      }
    });
    
    knowledgeBaseList.value = processedItems;

  } catch (err) {
    error.value = err.message;
  } finally {
    isLoading.value = false;
  }
}

function _updateKBState(updatedItem) {
  console.log("----- DEBUG: _updateKBState called -----");
  console.log("Received updatedItem:", JSON.stringify(updatedItem, null, 2));
  console.log("Current selectedKnowledgeBase:", selectedKnowledgeBase.value?.id);
  
  const index = knowledgeBaseList.value.findIndex(i => i.id === updatedItem.id);
  if (index !== -1) {
    console.log(`Found item at index ${index}, updating list.`);
    
    // 修复：正确处理后端返回的时间戳
    if (updatedItem.updatedAt) {
      // 后端返回的时间戳可能是 UTC 或美国时区，我们需要转换为本地时间
      const backendDate = new Date(updatedItem.updatedAt);
      
      // 检查时间戳是否看起来像美国时区（比 UTC 晚 4-8 小时）
      const isLikelyUSTimezone = backendDate.getTimezoneOffset() > 240; // 大于 4 小时时差
      
      if (isLikelyUSTimezone) {
        console.log(`Detected US timezone for KB ${updatedItem.id}, converting to local time`);
        // 如果是美国时区，转换为本地时间
        const localDate = new Date(backendDate.getTime() + (backendDate.getTimezoneOffset() * 60000));
        knowledgeBaseList.value[index] = {
          ...updatedItem,
          updatedAt: localDate.toISOString()
        };
      } else {
        // 如果已经是 UTC 或本地时间，直接使用
        knowledgeBaseList.value[index] = updatedItem;
      }
    } else {
      // 如果后端没有返回更新时间，使用当前本地时间
      knowledgeBaseList.value[index] = {
        ...updatedItem,
        updatedAt: new Date().toISOString()
      };
    }
  }
  
  // 修复：只有当 selectedKnowledgeBase 存在且 ID 匹配时才更新
  // 防止在用户离开详情页后错误地更新 selectedKnowledgeBase
  if (selectedKnowledgeBase.value && selectedKnowledgeBase.value.id === updatedItem.id) {
    console.log("Updating selectedKnowledgeBase with ID:", updatedItem.id);
    
    // 使用处理后的数据更新 selectedKnowledgeBase
    const updatedItemInList = knowledgeBaseList.value.find(item => item.id === updatedItem.id);
    if (updatedItemInList) {
      selectedKnowledgeBase.value = { ...updatedItemInList };
    } else {
      selectedKnowledgeBase.value = { ...updatedItem };
    }
  } else {
    console.log("Not updating selectedKnowledgeBase - either null or ID mismatch");
    console.log("Current selected ID:", selectedKnowledgeBase.value?.id, "Updated item ID:", updatedItem.id);
  }
  
  console.log("---------------------------------------");
}

/**
 * (修复) 改进轮询函数，防止状态不一致
 */
async function _pollParsingStatus(id) {
  if (activePollers.value[id]) return;
  
  console.log(`[Polling] Starting poll for KB ${id}`);
  
  activePollers.value[id] = setInterval(async () => {
    try {
      const response = await fetch(`${API_BASE_URL}/knowledgebases/${id}`);
      const item = await handleResponse(response);
      
      if (item) {
        console.log(`[Polling] Received update for KB ${id}, selected KB:`, selectedKnowledgeBase.value?.id);
        
        // 处理时间戳时区转换
        if (item.updatedAt) {
          const backendDate = new Date(item.updatedAt);
          const isLikelyUSTimezone = backendDate.getTimezoneOffset() > 240;
          
          if (isLikelyUSTimezone) {
            const localDate = new Date(backendDate.getTime() + (backendDate.getTimezoneOffset() * 60000));
            item.updatedAt = localDate.toISOString();
          }
        }
        
        _updateKBState(item);
        
        // 扩展停止轮询的条件
        const shouldStop = item.status === 'ready' || item.status === 'error' || 
            (item.parsingState && 
             (item.parsingState.stage === 'complete' || 
              item.parsingState.stage === 'error' || 
              item.parsingState.stage === 'cancelled'));
              
        if (shouldStop) {
          console.log(`[Polling] Stopping poll for KB ${id} due to completion state`);
          _stopPolling(id);
        }
      } else {
        console.log(`[Polling] No item received for KB ${id}, stopping poll`);
        _stopPolling(id);
      }
    } catch (err) {
      console.error(`[Polling] Error polling KB ${id}:`, err);
      _stopPolling(id);
    }
  }, POLLING_INTERVAL);
}

  // 修复：改进开始解析函数，确保状态一致性
  async function startParsing(id, embeddingModelId) {
    error.value = null;
    try {
      // 先保存当前选中的知识库
      const currentSelected = selectedKnowledgeBase.value;
      
      console.log(`[StartParsing] Starting parsing for KB ${id}, current selected:`, currentSelected?.id);
      
      const response = await fetch(`${API_BASE_URL}/knowledgebases/${id}/parse`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ embedding_model_id: embeddingModelId }) 
      });
      
      if (!response.ok) throw new Error('Failed to start parsing');

      const updatedKB = await response.json();
      
      // 处理时间戳时区转换
      if (updatedKB.updatedAt) {
        const backendDate = new Date(updatedKB.updatedAt);
        const isLikelyUSTimezone = backendDate.getTimezoneOffset() > 240;
        
        if (isLikelyUSTimezone) {
          const localDate = new Date(backendDate.getTime() + (backendDate.getTimezoneOffset() * 60000));
          updatedKB.updatedAt = localDate.toISOString();
        }
      }
      
      _updateKBState(updatedKB);

      // 扩展轮询条件
      if (updatedKB.status === 'processing' || 
          (updatedKB.parsingState && 
          (updatedKB.parsingState.stage === 'parsing' || 
            updatedKB.parsingState.stage === 'pending'))) {
        _pollParsingStatus(id);
      }
      
      // 确保选中的知识库保持不变（如果用户还在查看同一个知识库）
      if (currentSelected && currentSelected.id === id) {
        console.log(`[StartParsing] Maintaining selection for KB ${id}`);
        const updatedItem = knowledgeBaseList.value.find(item => item.id === id) || updatedKB;
        setSelectedKnowledgeBase(updatedItem);
      }
      
    } catch (err) {
      error.value = err.message;
      throw err;
    }
  }
  // 1. (修改) 进入解析模式 - 添加时间戳更新
  function enterParsingMode(id) {
    const item = knowledgeBaseList.value.find(i => i.id === id);
    if (item) {
      const updatedItem = { 
        ...item, 
        parsingState: { stage: 'picking_model', progress: 0 },
        updatedAt: new Date().toISOString() // 添加时间戳更新
      };
      _updateKBState(updatedItem);
    }
  }

  // 2. (重构) 开始解析 - *真正*的 API 调用
  async function startParsing(id, embeddingModelId) {
    error.value = null;
    try {
      // 假设 API 接收 embedding_model_id
      const response = await fetch(`${API_BASE_URL}/knowledgebases/${id}/parse`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ embedding_model_id: embeddingModelId }) 
      });
      if (!response.ok) throw new Error('Failed to start parsing');

      const updatedKB = await response.json();
      _updateKBState(updatedKB);

      // 扩展轮询条件
      if (updatedKB.status === 'processing' || 
          (updatedKB.parsingState && 
           (updatedKB.parsingState.stage === 'parsing' || 
            updatedKB.parsingState.stage === 'pending'))) {
        _pollParsingStatus(id);
      }
    } catch (err) {
      error.value = err.message;
      throw err;
    }
  }

  // 3. (重构) 取消解析
  async function cancelParsing(id) {
    error.value = null;
    // 立即停止轮询
    _stopPolling(id);
    
    try {
      const response = await fetch(`${API_BASE_URL}/knowledgebases/${id}/cancel`, {
        method: 'POST',
      });
      if (!response.ok) throw new Error('Failed to cancel parsing');

      const updatedKB = await response.json();
      _updateKBState(updatedKB);

    } catch (err) {
      error.value = err.message;
      throw err;
    }
  }
  


  // (修改) 删除知识库
  async function deleteKnowledgeBase(id) {
    error.value = null;
    _stopPolling(id);
    try {
      const response = await fetch(`${API_BASE_URL}/knowledgebases/${id}`, {
        method: 'DELETE',
      });
      await handleResponse(response);
      
      knowledgeBaseList.value = knowledgeBaseList.value.filter(i => i.id !== id);
      if (selectedKnowledgeBase.value && selectedKnowledgeBase.value.id === id) {
          selectedKnowledgeBase.value = null;
      }
    } catch (err) {
      error.value = err.message;
      throw err; // (修改) 抛出错误以便 UI 捕获
    }
  }
  
async function createKnowledgeBase(newItem) {
  error.value = null;
  try {
    const response = await fetch(`${API_BASE_URL}/knowledgebases`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(newItem),
    });
    if (!response.ok) {
      const errData = await response.json();
      throw new Error(errData.detail || 'Failed to create knowledge base');
    }
    
    const createdKB = await response.json();
    
    // 处理时间戳时区转换
    if (createdKB.updatedAt) {
      const backendDate = new Date(createdKB.updatedAt);
      const isLikelyUSTimezone = backendDate.getTimezoneOffset() > 240;
      
      if (isLikelyUSTimezone) {
        const localDate = new Date(backendDate.getTime() + (backendDate.getTimezoneOffset() * 60000));
        createdKB.updatedAt = localDate.toISOString();
      }
    }
    
    knowledgeBaseList.value.push(createdKB);
    
    // 扩展轮询条件
    if (createdKB.status === 'processing' || 
        (createdKB.parsingState && 
         (createdKB.parsingState.stage === 'parsing' || 
          createdKB.parsingState.stage === 'pending' || 
          createdKB.parsingState.stage === 'picking_model'))) {
      _pollParsingStatus(createdKB.id);
    }
    
    return createdKB;
    
  } catch (err) {
    error.value = err.message;
    throw err;
  }
}

async function updateKnowledgeBase(id, payload) {
  error.value = null;
  try {
    const response = await fetch(`${API_BASE_URL}/knowledgebases/${id}`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload) 
    });
    if (!response.ok) {
      const errData = await response.json();
      throw new Error(errData.detail || 'Failed to update knowledge base');
    }
    
    const updatedKB = await response.json();
    
    // 处理时间戳时区转换
    if (updatedKB.updatedAt) {
      const backendDate = new Date(updatedKB.updatedAt);
      const isLikelyUSTimezone = backendDate.getTimezoneOffset() > 240;
      
      if (isLikelyUSTimezone) {
        const localDate = new Date(backendDate.getTime() + (backendDate.getTimezoneOffset() * 60000));
        updatedKB.updatedAt = localDate.toISOString();
      }
    }
    
    _updateKBState(updatedKB);
  } catch (err) {
    error.value = err.message;
    throw err;
  }
}

async function reuploadFile(id, file) {
  error.value = null;
  try {
    const formData = new FormData();
    formData.append("file", file);
    const response = await fetch(`${API_BASE_URL}/knowledgebases/${id}/upload`, {
      method: 'POST',
      body: formData,
    });
    const updatedKB = await handleResponse(response);

    console.log("----- DEBUG: reuploadFile received -----");
    console.log("Parsed updatedKB from response:", JSON.stringify(updatedKB, null, 2));
    
    // 处理时间戳时区转换
    if (updatedKB.updatedAt) {
      const backendDate = new Date(updatedKB.updatedAt);
      const isLikelyUSTimezone = backendDate.getTimezoneOffset() > 240;
      
      if (isLikelyUSTimezone) {
        const localDate = new Date(backendDate.getTime() + (backendDate.getTimezoneOffset() * 60000));
        updatedKB.updatedAt = localDate.toISOString();
      }
    }
    
    console.log("Status after reupload:", updatedKB.status);
    console.log("Parsing state after reupload:", updatedKB.parsingState);
    console.log("UpdatedAt after reupload:", updatedKB.updatedAt);
    console.log("---------------------------------------");

    _updateKBState(updatedKB);
    
    // 重新开始轮询状态（如果需要）
    if (updatedKB.status === 'processing' || 
        (updatedKB.parsingState && 
         (updatedKB.parsingState.stage === 'parsing' || 
          updatedKB.parsingState.stage === 'pending' || 
          updatedKB.parsingState.stage === 'picking_model'))) {
      _pollParsingStatus(id);
    }
    
    return updatedKB;
  } catch (err) { 
    error.value = err.message;
    throw err;
  }
  }

  // 修复：改进设置选中知识库函数
  function setSelectedKnowledgeBase(item) {
    console.log(`[setSelectedKnowledgeBase] Setting selected KB to:`, item ? `ID ${item.id}` : 'null');
    
    // 如果设置为 null，确保停止所有轮询（可选，根据需求）
    // if (!item) {
    //   console.log(`[setSelectedKnowledgeBase] Clearing selection, stopping all polls`);
    //   Object.keys(activePollers.value).forEach(id => _stopPolling(id));
    // }
    
    selectedKnowledgeBase.value = item;
  }
    
  function setPromptSelection(selection) {
    promptSelection.value = selection;
  }
  function setPromptSelectedModel(model) {
    promptSelectedModel.value = model;
  }
  function setPromptModeTable(mode) { // 'kb' or 'model'
    promptModeTable.value = mode;
  }


async function generateSummary(kbId, generationModelId, embeddingModelId) {
    error.value = null;
    try {
      const response = await fetch(`${API_BASE_URL}/knowledgebases/${kbId}/generate-summary`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ // 匹配 API (schemas/knowledgebase.py)
          generation_model_id: generationModelId,
          embedding_model_id: embeddingModelId
        }) 
      });

      // 使用您已有的健壮的响应处理器
      const newL2aKb = await handleResponse(response);
      
      // (!! 关键 !!) 后端返回了新创建的 L2a 知识库对象
      // 我们需要将这个新对象添加到列表中
      
      // (复制 createKnowledgeBase 中的时间戳处理逻辑)
      if (newL2aKb.updatedAt) {
        const backendDate = new Date(newL2aKb.updatedAt);
        const isLikelyUSTimezone = backendDate.getTimezoneOffset() > 240;
        if (isLikelyUSTimezone) {
          const localDate = new Date(backendDate.getTime() + (backendDate.getTimezoneOffset() * 60000));
          newL2aKb.updatedAt = localDate.toISOString();
        }
      }
      
      knowledgeBaseList.value.push(newL2aKb); // 添加到列表

      // (!! 关键 !!) L2a 摘要需要摄取，所以后端返回 "processing"
      // 我们需要像 createKnowledgeBase 一样为这个*新*ID启动轮询
      if (newL2aKb.status === 'processing' || 
          (newL2aKb.parsingState && 
           (newL2aKb.parsingState.stage === 'parsing' || 
            newL2aKb.parsingState.stage === 'pending' || 
            newL2aKb.parsingState.stage === 'picking_model'))) {
        _pollParsingStatus(newL2aKb.id); //
      }
      
      return newL2aKb; // 返回新创建的对象

    } catch (err) {
      error.value = err.message;
      throw err;
    }
  }

  /**
   * (!! 新增 !!) 调用 L2b 知识图谱生成 API
   */
  async function generateGraph(kbId, generationModelId) {
    error.value = null;
    try {
      const response = await fetch(`${API_BASE_URL}/knowledgebases/${kbId}/generate-graph`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ // 匹配 API (schemas/knowledgebase.py)
          generation_model_id: generationModelId
        }) 
      });

      const newL2bKb = await handleResponse(response);
      
      // (!! 关键 !!) 后端返回了新创建的 L2b 知识库对象
      
      // (复制 createKnowledgeBase 中的时间戳处理逻辑)
      if (newL2bKb.updatedAt) {
        const backendDate = new Date(newL2bKb.updatedAt);
        const isLikelyUSTimezone = backendDate.getTimezoneOffset() > 240;
        if (isLikelyUSTimezone) {
          const localDate = new Date(backendDate.getTime() + (backendDate.getTimezoneOffset() * 60000));
          newL2bKb.updatedAt = localDate.toISOString();
        }
      }
      console.log('[DEBUG generateGraph] 收到并即将推入列表的对象:', JSON.stringify(newL2bKb, null, 2));
      
      knowledgeBaseList.value.push(newL2bKb); // 添加到列表

      // (!! 注意 !!) L2b 生成是同步的，*不*需要轮询
      
      return newL2bKb; // 返回新创建的对象

    } catch (err) {
      error.value = err.message;
      throw err;
    }
  }


  return {
    // --- State ---
    knowledgeBaseList, 
    selectedKnowledgeBase, 
    searchTerm, 
    promptSelection,
    promptSelectedModel,      // 新增
    promptModeTable,          // 新增
    isLoading, 
    error,
    
    // --- Getters ---
    filteredKnowledgeBaseList, 
    readyKnowledgeBaseList,
    
    // --- Actions ---
    fetchKnowledgeBases,
    setSelectedKnowledgeBase, 
    setPromptSelection, 
    setPromptSelectedModel,    // 确保存在
    setPromptModeTable,        // 确保存在
    updateKnowledgeBase, 
    enterParsingMode, 
    startParsing, 
    cancelParsing,
    createKnowledgeBase, 
    deleteKnowledgeBase,
    _updateKBState,
    reuploadFile,
    generateSummary,
    generateGraph
  }
})