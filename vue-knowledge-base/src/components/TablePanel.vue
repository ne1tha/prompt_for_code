<template>
  <el-card class="table-card">
    <template #header>
      <Transition name="fade-header">
        <div class="card-header" v-if="props.headerMode !== 'none'">
          
          <el-button 
            v-if="props.headerMode === 'full'" 
            type="primary" 
            @click="handleCreateKnowledgeBase">创建知识库</el-button>
          
          <el-input 
            v-model="store.searchTerm" 
            placeholder="按名称搜索..." 
            :prefix-icon="Search"
            :style="{ 'flex-grow': props.headerMode === 'search' ? 1 : 0 }"
          />

        </div>
      </Transition>
    </template>
    <el-table 
      ref="tableRef"
      :data="tableData" 
      highlight-current-row 
      @current-change="handleRowClick" 
      @selection-change="handleSelectionChange"
      height="100%"
    >
      <el-table-column v-if="props.activeMenu === 'prompt'" type="selection" width="55" />
      <el-table-column prop="id" label="ID" width="80" />
      <el-table-column label="Name" show-overflow-tooltip>
          <template #default="scope"><span :style="{ 'padding-left': (scope.row.level || 0) * 20 + 'px' }">{{ scope.row.name }}</span></template>
      </el-table-column>
      
      <el-table-column v-if="props.headerMode === 'full'" label="Status" width="140">
        <template #default="scope">
          <div class="status-container">
            <el-tag :type="getStatusType(scope.row.status, scope.row.parsingState?.stage)" disable-transitions>
              {{ getDisplayStatus(scope.row.status, scope.row.parsingState?.stage) }}
            </el-tag>
            <div v-if="scope.row.parsingState?.progress > 0" class="progress-text">
              {{ scope.row.parsingState.progress }}%
            </div>
          </div>
        </template>
      </el-table-column>
      
      <el-table-column prop="updatedAt" label="Updated" width="180">
            <template #default="scope">{{ formatDateTime(scope.row.updatedAt) }}</template>
      </el-table-column>

      <!-- 新增解析阶段列 -->
      <el-table-column v-if="props.headerMode === 'full'" label="解析阶段" width="140">
        <template #default="scope">
          <el-tag :type="getStageType(scope.row.parsingState?.stage)" size="small">
            {{ getStageDisplayName(scope.row.parsingState?.stage) }}
          </el-tag>
        </template>
      </el-table-column>
    </el-table>
  </el-card>
</template>

<script setup>
// 核心修复1：导入 ref 和 watch
import { computed, ref, watch, nextTick } from 'vue';  // 确保导入了 nextTick
import { useKnowledgeBaseStore } from '../stores/knowledgeBase';
import { Search } from '@element-plus/icons-vue';

const props = defineProps({
  activeMenu: String,
  headerMode: { type: String, default: 'full' },
  isPickingParentKb: { type: Boolean, default: false },
  headerDisabled: { type: Boolean, default: false }
});

const store = useKnowledgeBaseStore();
// 核心修复2：创建对 el-table 的引用
const tableRef = ref(null);

const tableData = computed(() => {
  let list;
  if (props.headerMode === 'full') {
    // 过滤掉知识库图谱
    list = store.filteredKnowledgeBaseList.filter(item => item.kbType !== 'l2b_graph');
  } else {
    // (!! 修改 !!) Prompt 模式也使用 filteredList，并过滤掉知识库图谱
    list = store.filteredKnowledgeBaseList.filter(item => item.kbType !== 'l2b_graph'); 
    if (props.activeMenu === 'prompt') {
      list = list.filter(item => item.status === 'ready');
    }
  }

  
  const finalSortedList = [];
  const addedIds = new Set();
  const itemsById = new Map(list.map(item => [item.id, item]));
  
  // 找到所有在当前列表中的根节点
  const rootsInList = list.filter(item => !item.parentId || !itemsById.has(item.parentId));
  
  function addNode(node, level) {
     if (!node || addedIds.has(node.id)) return;
     
     const nodeWithLevel = { ...node, level: level };
     finalSortedList.push(nodeWithLevel);
     addedIds.add(node.id);
     
     // 找到所有在当前列表中的子节点
     const children = list.filter(child => child.parentId === node.id);
     children.forEach(child => addNode(child, level + 1));
  }
  
  rootsInList.forEach(root => addNode(root, 0));
  
  // 添加可能因父节点被过滤掉而遗留的 "孤儿"
  list.forEach(item => {
    if(!addedIds.has(item.id)) {
      finalSortedList.push({ ...item, level: 0 }); // 视为 0 级
      addedIds.add(item.id);
    }
  });

  return finalSortedList;
});

const emit = defineEmits(['create-kb', 'parse-kb', 'kb-picked']);
const isHandlingClick = ref(false);
// 核心修复3：监听 store 中的选中项变化
watch(() => store.selectedKnowledgeBase, (newSelection) => {
  console.log(`[TablePanel] Selected KB changed:`, newSelection ? `ID ${newSelection.id}` : 'null');
  // (!! 关键修复 1 !!) 
  // 如果是 handleRowClick 正在处理，则 watch 必须 "跳过"
  if (isHandlingClick.value) {
    console.log(`[TablePanel WATCH] Skipping: handleRowClick is active.`);
    return;
  }
  
  // 当外部（如详情页关闭）将选中项清空时
  if (newSelection === null && tableRef.value) {
    // 主动调用 el-table 的方法，清除其内部的高亮状态
    tableRef.value.setCurrentRow(null);
  } else if (newSelection && tableRef.value) {
    // 当有新的选中项时，确保表格高亮正确
    const row = tableData.value.find(row => row.id === newSelection.id);
    if (row) {
      nextTick(() => {
        tableRef.value.setCurrentRow(row);
      });
    }
  }
}, { deep: true });

const handleRowClick = (row) => {
  console.log(`[TablePanel CLICK] Row clicked:`, row ? `ID ${row.id}` : 'null');
  
  const currentRowId = row ? row.id : null;
  const storeRowId = store.selectedKnowledgeBase ? store.selectedKnowledgeBase.id : null;
  
  // (!! 关键修复 1 !!) 
  // 仍然保留冗余检查
  if (currentRowId === storeRowId) {
     console.log(`[TablePanel CLICK] Event for ${currentRowId} is redundant, skipping.`);
     return;
  }

  // (!! 关键修复 1 !!) 
  // 激活 "click lock"
  isHandlingClick.value = true;
  console.log(`[TablePanel CLICK] Lock engaged (isHandlingClick = true).`);

  if (props.isPickingParentKb) {
    if (row) {
      console.log(`[TablePanel CLICK] Picking Parent: Setting store to ID ${row.id}`);
      store.setSelectedKnowledgeBase(row);
      emit('kb-picked');
    } else {
      console.log(`[TablePanel CLICK] Picking Parent: Setting store to null`);
      store.setSelectedKnowledgeBase(null);
    }
  } else if (props.activeMenu === 'database') {
    if (!row) {
      console.log(`[TablePanel CLICK] Database: Setting store to null`);
      store.setSelectedKnowledgeBase(null);
    } else {
      const latestRow = store.knowledgeBaseList.find(item => item.id === row.id) || row;
      console.log(`[TablePanel CLICK] Database: Setting store to ID ${latestRow.id}`);
      store.setSelectedKnowledgeBase(latestRow);
    }
  } else {
     console.log(`[TablePanel CLICK] Click in non-database, non-picking mode. Ignored.`);
  }

  // (!! 关键修复 1 !!) 
  // 在下一个 "tick" 释放 "click lock"
  nextTick(() => {
    isHandlingClick.value = false;
    console.log(`[TablePanel CLICK] Lock released (isHandlingClick = false).`);
  });
};

// 更新状态类型判断，考虑解析阶段
const getStatusType = (status, stage) => {
  // 优先根据解析阶段判断
  if (stage === 'complete') return 'success';
  if (stage === 'error' || stage === 'cancelled') return 'danger';
  if (stage === 'parsing' || stage === 'pending' || stage === 'picking_model') return 'primary';
  
  // 如果没有解析阶段信息，回退到状态判断
  if (status === 'ready') return 'success';
  if (status === 'processing') return 'primary';
  if (status === 'error') return 'danger';
  return 'info';
};

// 获取显示的状态文本
const getDisplayStatus = (status, stage) => {
  // 优先显示解析阶段
  if (stage) {
    const stageMap = {
      'idle': '空闲',
      'picking_model': '选择模型中',
      'pending': '等待解析',
      'parsing': '解析中',
      'complete': '已完成',
      'error': '错误',
      'cancelled': '已取消'
    };
    return stageMap[stage] || stage;
  }
  
  // 回退到状态显示
  const statusMap = {
    'ready': '就绪',
    'processing': '处理中',
    'error': '错误',
    'new': '新建'
  };
  return statusMap[status] || status;
};

// 获取解析阶段的显示类型
const getStageType = (stage) => {
  if (stage === 'complete') return 'success';
  if (stage === 'error' || stage === 'cancelled') return 'danger';
  if (stage === 'parsing' || stage === 'pending' || stage === 'picking_model') return 'primary';
  return 'info';
};

// 获取解析阶段的显示名称
const getStageDisplayName = (stage) => {
  const stageMap = {
    'idle': '空闲',
    'picking_model': '选择模型',
    'pending': '等待中',
    'parsing': '解析中',
    'complete': '完成',
    'error': '错误',
    'cancelled': '已取消'
  };
  return stageMap[stage] || stage || '未知';
};

// 格式化日期时间显示
const formatDateTime = (dateString) => {
  if (!dateString) return '-';
  
  try {
    // 创建日期对象
    const date = new Date(dateString);
    
    // 检查日期是否有效
    if (isNaN(date.getTime())) {
      console.warn('Invalid date string:', dateString);
      return '-';
    }
    
    // 使用本地时区显示，确保格式正确
    const options = {
      year: 'numeric',
      month: '2-digit',
      day: '2-digit',
      hour: '2-digit',
      minute: '2-digit',
      second: '2-digit',
      hour12: false,
      timeZone: 'Asia/Shanghai' // 明确指定中国时区
    };
    
    return date.toLocaleString('zh-CN', options);
  } catch (error) {
    console.error('Error formatting date:', error, dateString);
    return '-';
  }
};

const handleCreateKnowledgeBase = () => { emit('create-kb'); };


// (!! 新增 !!) 用于父子联动的状态
let internalSelection = [];

// (!! 新增 !!) 监听来自 Store 的变化'
watch(() => store.promptSelection, (storeSelection) => {
   // 如果 Store 的选择与表格内部的选择不一致
   if (props.activeMenu === 'prompt' && JSON.stringify(storeSelection.map(s=>s.id)) !== JSON.stringify(internalSelection.map(s=>s.id))) {
       console.log("External selection change detected, updating table.");
       if (tableRef.value) {
         tableRef.value.clearSelection();
         storeSelection.forEach(row => {
             const rowInTable = tableData.value.find(item => item.id === row.id);
             if (rowInTable) {
               tableRef.value.toggleRowSelection(rowInTable, true);
             }
         });
       }
       internalSelection = [...storeSelection];
   }
}, { deep: true });

// (!! 新增 !!) 表格多选变化处理器
const handleSelectionChange = (selection) => {
  // 只在 prompt 模式下启用此逻辑
  if (props.activeMenu !== 'prompt') return;

  const oldSelection = internalSelection;
  internalSelection = selection; // 更新内部状态

  const allRows = tableData.value;
  let finalSelection = [...selection];

  // 检查是否新增了选择
  const newlySelected = selection.filter(row => !oldSelection.includes(row));
  if (newlySelected.length > 0) {
     const row = newlySelected[0]; // 假设一次只点一个
     if (row.level === 0) { // 如果选中的是父节点
        const children = allRows.filter(r => r.parentId === row.id);
        children.forEach(child => {
          if (!finalSelection.includes(child)) {
            finalSelection.push(child);
            if (tableRef.value) tableRef.value.toggleRowSelection(child, true);
          }
        });
     }
  }
  
  // 检查是否取消了选择
  const newlyDeselected = oldSelection.filter(row => !selection.includes(row));
  if (newlyDeselected.length > 0) {
    const row = newlyDeselected[0]; // 假设一次只点一个
    if (row.level === 0) { // 如果取消的是父节点
      const children = allRows.filter(r => r.parentId === row.id);
      children.forEach(child => {
         const index = finalSelection.findIndex(item => item.id === child.id);
         if (index > -1) {
           finalSelection.splice(index, 1);
           if (tableRef.value) tableRef.value.toggleRowSelection(child, false);
         }
      });
    }
  }

  // 将最终结果同步回 Store
  store.setPromptSelection(finalSelection);
};
</script>

<style scoped>
.table-card {
  width: 100%; height: 100%; display: flex; flex-direction: column; box-sizing: border-box;
}
.table-card :deep(.el-card__body) {
  flex-grow: 1; overflow: hidden; padding: 0;
}
.table-card :deep(.el-card__header) {
  min-height: 32px;
  flex-shrink: 0;
}
.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 10px;
}
.fade-header-enter-active,
.fade-header-leave-active {
  transition: opacity 0.3s ease;
}
.fade-header-enter-from,
.fade-header-leave-to {
  opacity: 0;
}
.status-container {
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  gap: 2px;
}
.progress-text {
  font-size: 12px;
  color: #666;
}
</style>