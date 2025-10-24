<template>
  <Transition name="fade">
    <el-card v-if="props.visible" class="action-panel">
      <template #header>
        <div class="card-header">
          <span>再生成知识库 - {{ panelModeTitle }}</span>
          <el-button 
            type="primary" 
            :icon="Close" 
            circle 
            @click="handleClose" 
          />
        </div>
      </template>
      
      <div class="panel-content">
        <el-alert 
          v-if="panelMode !== 'config'" 
          title="点击表格行进行选择，完成后请点击下方按钮返回配置。" 
          type="info" 
          show-icon 
          style="margin-bottom: 20px;" 
          :closable="false"
        />

        <div v-if="panelMode === 'config'" class="config-content config-content-styled">
          <p>父知识库：<strong>{{ parentKb?.name || '未选择' }}</strong></p>
          <p>生成模型 (LLM)：<strong>{{ genModel?.name || '未选择' }}</strong></p>
          <p>嵌入模型 (Embedding)：<strong>{{ embedModel?.name || '未选择' }}</strong></p>

          <div class="button-group">
            <el-button @click="setPanelMode('model-picking')">选择生成模型</el-button>
            
            <el-button @click="setPanelMode('embedding-model-picking')">选择嵌入模型</el-button>
            
            <el-button 
              v-if="!isGraphReady"
              type="primary" 
              plain
              @click="handleGenerateGraph"
              :disabled="!genModel || isGraphGenerating"
              :loading="isGraphGenerating"
            >
              {{ isGraphGenerating ? '正在生成图谱...' : '生成知识图谱' }}
            </el-button>
          </div>

          <el-form :model="form" label-position="top" class="panel-form">
            <el-form-item label="知识图谱 (L2b) 状态">
              <div v-if="isGraphReady" class="status-text-success">
                <el-icon><CircleCheckFilled /></el-icon>
                已就绪
                <!-- 新增：显示文件路径 -->
                <div v-if="graphFilePath" class="file-path-info">
                  <small>文件路径: {{ truncatedGraphFilePath }}</small>
                </div>
              </div>
              <div v-else-if="isGraphGenerating" class="status-text-processing">
                <el-icon class="is-loading"><Loading /></el-icon>
                正在生成... 
                ({{ childGraphKb?.parsingState?.progress || 0 }}%)
              </div>
              <div v-else class="status-text-info">
                <el-icon><InfoFilled /></el-icon>
                此知识库尚未生成知识图谱。
              </div>
            </el-form-item>
            <el-form-item label="摘要知识库 (L2a) 名称" required>
              <el-input v-model="form.newName" placeholder="请输入 L2a 摘要知识库的名称" />
            </el-form-item>
          </el-form>
        </div>
      </div>
      
      <div class="panel-footer">
        <div v-if="panelMode !== 'config'" class="footer-buttons">
            <el-button @click="setPanelMode('config')">返回配置</el-button>
        </div>
        
        <div v-if="panelMode === 'config'" class="footer-buttons">
          <el-button @click="handleClose">取消</el-button>
          
          <el-button 
            type="primary" 
            @click="handleSubmit" 
            :disabled="!parentKb || !genModel || !embedModel || isLoadingSummary || isGraphGenerating"
            :loading="isLoadingSummary"
          >
            {{ isLoadingSummary ? '正在生成摘要...' : '确认生成摘要 (L2a)' }}
          </el-button>
        </div>
      </div>

    </el-card>
  </Transition>
</template>

<script setup>
import { ref, watch, computed } from 'vue';
import { useKnowledgeBaseStore } from '../stores/knowledgeBase';
import { useModelStore } from '../stores/modelStore'; 
import { ElNotification } from 'element-plus';
import { Close } from '@element-plus/icons-vue';

const PANEL_MODE = {
    CONFIG: 'config',
    MODEL_PICKING: 'model-picking',
    EMBEDDING_MODEL_PICKING: 'embedding-model-picking' 
};
const props = defineProps({
  visible: Boolean
});
const emit = defineEmits(['close', 'panel-mode-change']); 
const kbStore = useKnowledgeBaseStore();
const modelStore = useModelStore();
const panelMode = ref(PANEL_MODE.CONFIG); 
const parentKb = ref(null); 
const genModel = ref(null); 
const panelModeTitle = computed(() => {
    if (panelMode.value === PANEL_MODE.MODEL_PICKING) return '选择生成模型';
    if (panelMode.value === PANEL_MODE.EMBEDDING_MODEL_PICKING) return '选择嵌入模型'; // (!! 新增 !!)
    return '配置';
});
const form = ref({
  newName: '', // (!! 修改 !!) 我们将用这个作为 L2a 摘要的新名称
});
const embedModel = ref(null); // (!! 新增 !!) 存储嵌入模型
const isLoadingGraph = ref(false); // (!! 新增 !!) 知识图谱生成状态
const isLoadingSummary = ref(false);

// 检查子知识图谱状态
const childGraphKb = computed(() => {
  if (!parentKb.value) return null;
  return kbStore.knowledgeBaseList.find(kb => 
    kb.parentId === parentKb.value.id && kb.kbType === 'l2b_graph'
  );
});

// 知识图谱是否就绪
const isGraphReady = computed(() => {
  return childGraphKb.value && childGraphKb.value.status === 'ready';
});

// 知识图谱是否正在生成
const isGraphGenerating = computed(() => {
  // 检查我们自己的加载状态，或 store 中的状态
  return isLoadingGraph.value || (childGraphKb.value && childGraphKb.value.status === 'processing');
});
watch([childGraphKb, isGraphReady, isGraphGenerating], ([newChild, newReady, newGenerating]) => {
  console.log(`[RegeneratePanel] 知识图谱状态变化:`, {
    childGraphKb: newChild ? { 
      id: newChild.id, 
      name: newChild.name, 
      status: newChild.status,
      kbType: newChild.kbType,
      parentId: newChild.parentId
    } : null,
    isGraphReady: newReady,
    isGraphGenerating: newGenerating,
    parentKbId: parentKb.value?.id
  });
}, { deep: true });

watch(() => modelStore.selectedModel, (newModel) => {
    if (panelMode.value === PANEL_MODE.MODEL_PICKING && newModel) {
        panelMode.value = PANEL_MODE.CONFIG; 
        genModel.value = newModel;
    }
    // (!! 新增 !!) 处理嵌入模型的选择
    if (panelMode.value === PANEL_MODE.EMBEDDING_MODEL_PICKING && newModel) {
        panelMode.value = PANEL_MODE.CONFIG;
        embedModel.value = newModel;
    }
});

// (!! 修改 !!) watch props.visible
watch(() => props.visible, (newVal) => {
    if (newVal) {
        parentKb.value = kbStore.selectedKnowledgeBase; 
        genModel.value = null; 
        embedModel.value = null; // (!! 新增 !!)
        isLoadingGraph.value = false; // (!! 新增 !!)
        isLoadingSummary.value = false; // (!! 新增 !!)
        // (!! 修改 !!) 自动填充摘要名称
        form.value.newName = parentKb.value ? `${parentKb.value.name} - AI 摘要` : '';
        setPanelMode(PANEL_MODE.CONFIG);
    } else {
        modelStore.setSelectedModel(null);
    }
});

const setPanelMode = (mode) => {
    panelMode.value = mode;
    modelStore.setSelectedModel(null);
    emit('panel-mode-change', mode);
};

const handleClose = () => {

    console.log(`[RegenPanel] handleClose called. Emitting 'close'. Parent KB ID ${parentKb.value?.id} *remains selected* in kbStore.`);
    setPanelMode(PANEL_MODE.CONFIG);
    emit('close');
};

const graphFilePath = computed(() => {
  if (!childGraphKb.value) return null;
  return childGraphKb.value.sourceFilePath || childGraphKb.value.filePath;
});

const truncatedGraphFilePath = computed(() => {
  if (!graphFilePath.value) return null;
  
  const uploadsIndex = graphFilePath.value.indexOf('uploads/');
  if (uploadsIndex !== -1) {
    return graphFilePath.value.substring(uploadsIndex);
  }
  
  // 如果没有找到 uploads/，返回原路径（或者可以返回最后一部分）
  return graphFilePath.value.split('/').slice(-2).join('/'); // 返回最后两级路径
});
const handleSubmit = async () => {
  const parent = parentKb.value;
  const model = genModel.value; 
  const embed = embedModel.value; // (!! 新增 !!)

  // (!! 修改 !!) 检查所有三个依赖项 (Req 4)
  if (!parent || !model || !embed) {
      ElNotification({ title: '错误', message: '请选择父知识库、生成模型和嵌入模型！', type: 'error' });
      return;
  }
  
  if (!form.value.newName.trim()) {
      ElNotification({ title: '错误', message: '请输入新知识库的名称！', type: 'error' });
      return;
  }

  isLoadingSummary.value = true;
  try {
    // (!! 修改 !!) 调用新的 generateSummary action
    const newL2aKb = await kbStore.generateSummary(
      parent.id, 
      model.id, 
      embed.id
    );
    
    // (!! 新增 !!) 手动更新 L2a 知识库的名称
    if (newL2aKb && newL2aKb.id) {
      await kbStore.updateKnowledgeBase(newL2aKb.id, { name: form.value.newName.trim() });
    }
    
    ElNotification({ title: '成功', message: '摘要子知识库生成任务已开始！', type: 'success' });
    handleClose(); // (Req 5) 关闭面板，App.vue 会自动显示 RightPanel
    
  } catch (err) {
    ElNotification({ title: '生成失败', message: err.message, type: 'error' });
  } finally {
    isLoadingSummary.value = false;
  }
};

const handleGenerateGraph = async () => {
  if (!parentKb.value || !genModel.value) {
    ElNotification({ title: '错误', message: '请先选择父知识库和生成模型！', type: 'error' });
    return;
  }
  
  console.log(`[RegeneratePanel] 开始生成知识图谱:`, {
    parentKbId: parentKb.value.id,
    parentKbName: parentKb.value.name,
    modelId: genModel.value.id,
    modelName: genModel.value.name
  });
  
  isLoadingGraph.value = true;
  try {
    // 调用 store action
    await kbStore.generateGraph(parentKb.value.id, genModel.value.id);
    
    console.log(`[RegeneratePanel] 知识图谱生成请求成功`);
    ElNotification({ title: '成功', message: '知识图谱生成任务已开始！', type: 'success' });
    
    // 立即检查状态更新
    setTimeout(() => {
      console.log(`[RegeneratePanel] 生成后状态检查:`, {
        childGraphKb: childGraphKb.value,
        isGraphReady: isGraphReady.value,
        isGraphGenerating: isGraphGenerating.value
      });
    }, 1000);
    
  } catch (err) {
    console.error(`[RegeneratePanel] 知识图谱生成失败:`, err);
    ElNotification({ title: '生成失败', message: err.message, type: 'error' });
  } finally {
    isLoadingGraph.value = false;
  }
};
</script>

<style scoped>
.action-panel {
  width: 100%;
  height: 100%;
  display: flex;
  flex-direction: column;
  box-sizing: border-box; 
}
.card-header {
  display: flex;
  justify-content: space-between; 
  align-items: center;
}
.action-panel :deep(.el-card__header) {
  flex-shrink: 0; 
}
.action-panel :deep(.el-card__body) {
  flex-grow: 1; 
  padding: 0; 
  display: flex;
  flex-direction: column;
  min-height: 0; 
  overflow: hidden; /* <-- 关键修复 */
}
.panel-content {
  flex-grow: 1; 
  overflow-y: auto; 
  padding: 20px; 
}
.panel-footer {
  flex-shrink: 0; 
  border-top: 1px solid var(--el-card-border-color, #ebeef5);
  padding: 10px 20px;
}
.footer-buttons {
  display: flex;
  justify-content: flex-end; 
}
.button-group {
  margin-bottom: 20px;
  display: flex;
  gap: 10px;
}
.file-path-info {
  margin-top: 4px;
  color: var(--el-text-color-secondary);
  font-size: 12px;
  padding-left: 20px;
}
.config-content-styled {
  border: 1px solid var(--el-card-border-color, #ebeef5);
  padding: 15px 20px 5px; /* 底部padding小一点，因为form有margin */
  border-radius: 4px;
}

.config-content-styled p {
  margin: 0 0 12px 0;
  font-size: 14px;
}
.config-content-styled p strong {
  color: var(--el-text-color-primary);
}

.status-text-success,
.status-text-processing,
.status-text-info {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 14px;
}
.status-text-success { color: var(--el-color-success); }
.status-text-processing { color: var(--el-color-primary); }
.status-text-info { color: var(--el-color-info); }
</style>
