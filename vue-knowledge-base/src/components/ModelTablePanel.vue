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
  }
});

// 核心修改 3: 更新 tableData 的过滤逻辑
const tableData = computed(() => {
  const list = store.filteredModelList;
  if (props.isPickingGenModel) {
    // 假设 'Generative' 模型对应 model_type == 'generative' (全小写)
    return list.filter(model => model.model_type === 'generative');
  }
  // 如果是为解析选择模型，则只显示 Embedding 类型
  if (props.isPickingEmbeddingModel) {
    // (修正) 使用 model_type 和 'embedding' (全小写)
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
  // 当处于 picking 模式时，点击模型后，不应自动返回
  // RightPanel 会监听 selectedModel 的变化
  store.setSelectedModel(model);

  if (props.isPickingGenModel && model) {
    emit('model-picked');
  }
  if (props.isPickingForPrompt && model) {
    kbStore.setPromptSelectedModel(model); // 1. 在 Prompt Store 中设置模型
    kbStore.setPromptModeTable('kb');      // 2. 自动切换回 KB 选择视图
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