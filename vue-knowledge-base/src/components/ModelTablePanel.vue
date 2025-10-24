<template>
  <el-card class="table-card">
    <template #header v-if="!props.isPickingGenModel && !props.isPickingEmbeddingModel"> 
      <div class="card-header">
        <el-button type="primary" @click="handleCreateModelClick">配置新模型</el-button>
        <el-input v-model="store.searchTerm" placeholder="按名称搜索..." :prefix-icon="Search"/>
      </div>
    </template>
    <el-table 
      ref="tableRef"
      :data="tableData" 
      highlight-current-row 
      @current-change="handleRowClick" 
      height="100%"
    >
      <el-table-column prop="name" label="模型名称" />
      <el-table-column prop="model_type" label="类型" width="120" />
    </el-table>
  </el-card>
</template>

<script setup>
import { computed, ref, watch } from 'vue';
import { useModelStore } from '../stores/modelStore';
import { useKnowledgeBaseStore } from '../stores/knowledgeBase';
import { Search } from '@element-plus/icons-vue';

const store = useModelStore();
const tableRef = ref(null);
const kbStore = useKnowledgeBaseStore();

// 核心修改 2: 添加新 prop
const props = defineProps({
  isPickingGenModel: {
    type: Boolean,
    default: false
  },
  isPickingEmbeddingModel: {
    type: Boolean,
    default: false
  },
  isPickingForPrompt: {
    type: Boolean,
    default: false
  },
  isForRegeneratePanel: { 
    type: Boolean,
    default: false
  }
});

const tableData = computed(() => {
  const list = store.filteredModelList;

  // (!! 修正 !!)
  // 如果是为 "再生成" 选择生成模型，或者为 "Prompt" 模式选择模型
  if (props.isPickingGenModel) {
    return list.filter(model => model.model_type === 'generative');
  }

  // 如果是为解析选择模型
  if (props.isPickingEmbeddingModel || props.isPickingForPrompt) {
    return list.filter(model => model.model_type === 'embedding');
  }
  return list;
});

const emit = defineEmits(['create-model', 'model-picked']);

watch(() => store.selectedModel, (newSelection) => {
  if (newSelection === null && tableRef.value) {
    tableRef.value.setCurrentRow(null);
  }
});

const handleRowClick = (model) => {
  store.setSelectedModel(model);


  if (props.isForRegeneratePanel && model) {
    emit('model-picked'); 
  }
  
  // 3. (保持不变) 如果是为 Prompt 模式选择
  if (props.isPickingForPrompt && model) {
    kbStore.setPromptSelectedModel(model); 
    kbStore.setPromptModeTable('hidden');     
  }

};
const handleCreateModelClick = () => {
  emit('create-model');
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
  flex-shrink: 0;
}
.card-header {
  display: flex;
  justify-content: flex-start;
  align-items: center;
  gap: 10px;
}
</style>