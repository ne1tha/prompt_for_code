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

        <div v-if="panelMode === 'config'" class="config-content">
          <p>父知识库：{{ parentKb?.name || '未选择' }}</p>
          <p>生成模型：{{ genModel?.name || '未选择' }}</p>

          <div class="button-group">
            <el-button @click="setPanelMode('kb-picking')">选择父知识库</el-button>
            <el-button @click="setPanelMode('model-picking')">选择生成模型</el-button>
          </div>

          <el-form :model="form" label-position="top" class="panel-form">
            <el-form-item label="新知识库名称" required>
              <el-input v-model="form.newName" placeholder="请输入新知识库名称" />
            </el-form-item>
            <el-form-item label="再生成配置（JSON格式）">
              <el-input v-model="form.options" type="textarea" :rows="4" placeholder='{\n  "method": "extract",\n  "params": {}\n}' />
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
            :disabled="!parentKb || !genModel"
          >
            确认生成
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
    KB_PICKING: 'kb-picking',
    MODEL_PICKING: 'model-picking'
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
    if (panelMode.value === PANEL_MODE.KB_PICKING) return '选择父知识库';
    if (panelMode.value === PANEL_MODE.MODEL_PICKING) return '选择生成模型';
    return '配置';
});
const form = ref({
  newName: '',
  options: '{\n  "method": "extract",\n  "params": {}\n}',
});
watch(() => kbStore.selectedKnowledgeBase, (newKb) => {
    if (panelMode.value === PANEL_MODE.KB_PICKING && newKb) {
        panelMode.value = PANEL_MODE.CONFIG; 
        parentKb.value = newKb;
    }
});
watch(() => modelStore.selectedModel, (newModel) => {
    if (panelMode.value === PANEL_MODE.MODEL_PICKING && newModel) {
        panelMode.value = PANEL_MODE.CONFIG; 
        genModel.value = newModel;
    }
});
watch(() => props.visible, (newVal) => {
    if (newVal) {
        parentKb.value = kbStore.selectedKnowledgeBase; 
        genModel.value = null; 
        form.value.newName = '';
        form.value.options = '{\n  "method": "extract",\n  "params": {}\n}';
        setPanelMode(PANEL_MODE.CONFIG);
    } else {
        kbStore.setSelectedKnowledgeBase(null);
        modelStore.setSelectedModel(null);
    }
});
const setPanelMode = (mode) => {
    panelMode.value = mode;
    kbStore.setSelectedKnowledgeBase(null);
    modelStore.setSelectedModel(null);
    emit('panel-mode-change', mode);
};
const handleClose = () => {
    setPanelMode(PANEL_MODE.CONFIG);
    emit('close');
};
const handleSubmit = () => {
  const parent = parentKb.value;
  const model = genModel.value; 
  if (!parent || !model) {
      ElNotification({ title: '错误', message: '请先选择父知识库和生成模型！', type: 'error' });
      return;
  }
  kbStore.regenerateKnowledgeBase(parent.id, form.value.newName, form.value.options);
  ElNotification({ title: '成功', message: '子知识库生成成功！', type: 'success' });
  handleClose(); 
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
</style>
