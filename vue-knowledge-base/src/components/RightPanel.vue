<template>
  <Transition name="slide-fade">
    <el-card v-if="store.selectedKnowledgeBase" class="right-panel" :key="store.selectedKnowledgeBase.id">
      <template #header>
        <div class="card-header">
          <span>知识库详情</span>
          <el-button 
            :icon="Close" 
            circle 
            @click="handleClose" 
          />
        </div>
      </template>
      
      <div class="panel-content">
        <div class="editable-header">
          <el-input 
            v-model="editableName" 
            size="large"
            placeholder="请输入知识库名称"
            @keydown.enter="handleNameSave"
            @blur="handleNameSave"
          />
        </div>

        <!-- 修复：重新组织显示逻辑 -->
        <div class="button-group" v-if="shouldShowActionButtons">
          <el-button 
            v-if="store.selectedKnowledgeBase.status === 'ready'"
            plain 
            @click="$emit('openRegenerateModal')"
          >
            再生成子知识库
          </el-button>

          <el-button 
            v-if="shouldShowParseButton"
            plain 
            @click="handleParseClick"
          >
            解析知识库
          </el-button>
          
          <el-upload
            :auto-upload="false"
            :show-file-list="false"
            @change="handleFileChange"
          >
            <el-button plain>
              {{ store.selectedKnowledgeBase.sourceFilePath ? '重新上传' : '上传文件' }}
            </el-button>
          </el-upload>
          
          <el-button type="danger" plain @click="handleDelete">删除知识库</el-button>
        </div>

        <!-- 修复：合并所有解析相关的状态显示 -->
        <div class="parsing-controls" v-if="isParsingInProgress">
          <div v-if="parsingState.stage === 'picking_model'">
            <p>请选择一个 Embedding 模型用于解析：</p>
            <p><strong>当前选中模型:</strong> {{ modelStore.selectedModel?.name || '未选择' }}</p>
            <div class="button-group">
              <el-button 
                type="primary" 
                @click="handleConfirmParsing"
                :disabled="!modelStore.selectedModel"
              >
                确定
              </el-button>
              <el-button @click="handleCancelPicking">取消</el-button>
            </div>
          </div>

          <div v-else>
            <p>正在解析知识库，请稍候...</p>
            <p v-if="parsingState.message" class="parsing-message">{{ parsingState.message }}</p>
            <el-progress :percentage="parsingState.progress" :stroke-width="15" striped />
            <div class="button-group" style="margin-top: 10px;">
              <el-button type="danger" @click="handleCancelParsing">取消解析</el-button>
            </div>
          </div>
        </div>

        <!-- 修复：显示取消状态信息 -->
        <div class="parsing-controls" v-if="parsingState.stage === 'cancelled'">
          <p><strong>解析已取消</strong></p>
          <p>知识库解析过程已被取消。您可以重新上传文件或重新开始解析。</p>
        </div>

        <!-- 修复：重新组织详情显示逻辑 -->
        <template v-if="shouldShowDetails">
          <p><strong>父知识库:</strong> {{ store.selectedKnowledgeBase.parentId ? `ID ${store.selectedKnowledgeBase.parentId}` : '无（根节点）' }}</p>
          <p><strong>子知识库数量:</strong> {{ store.selectedKnowledgeBase.childCount || 0 }}</p>

          <el-divider />

          <h4>详细数据</h4>
          <el-descriptions :column="1" border>
            <el-descriptions-item label="name">{{ store.selectedKnowledgeBase.name }}</el-descriptions-item>
            <el-descriptions-item label="description">{{ store.selectedKnowledgeBase.description }}</el-descriptions-item>
            <el-descriptions-item label="parentId">{{ store.selectedKnowledgeBase.parentId }}</el-descriptions-item>
            <el-descriptions-item label="id">{{ store.selectedKnowledgeBase.id }}</el-descriptions-item>
            <el-descriptions-item label="status">
              {{ getDisplayStatus(store.selectedKnowledgeBase.status, store.selectedKnowledgeBase.parsingState?.stage) }}
            </el-descriptions-item>
            <el-descriptions-item label="sourceFilePath">{{ store.selectedKnowledgeBase.sourceFilePath }}</el-descriptions-item>
            <el-descriptions-item label="解析状态" v-if="parsingState.stage !== 'idle'">
              {{ parsingState.stage }} ({{ parsingState.progress }}%)
            </el-descriptions-item>
          </el-descriptions>
        </template>
      </div>
    </el-card>
  </Transition>
</template>

<script setup>
import { ref, watch, computed, nextTick, onUnmounted } from 'vue'
import { useKnowledgeBaseStore } from '../stores/knowledgeBase';
import { useModelStore } from '../stores/modelStore';
import { ElNotification, ElMessageBox } from 'element-plus';
import { Close } from '@element-plus/icons-vue';

defineEmits(['openRegenerateModal']);
const store = useKnowledgeBaseStore();
const modelStore = useModelStore();

const editableName = ref('');
let originalName = '';
const isEnteringParsingMode = ref(false);
const parsingState = computed(() => store.selectedKnowledgeBase?.parsingState || { stage: 'idle', progress: 0 });
const getStatusType = (status, stage) => {
  // 优先根据解析阶段判断 (这才是正确的)
  if (stage === 'complete') return 'success';
  if (stage === 'error' || stage === 'cancelled') return 'danger';
  if (stage === 'parsing' || stage === 'pending' || stage === 'picking_model') return 'primary';
  
  // 回退
  if (status === 'ready') return 'success';
  if (status === 'processing') return 'primary';
  if (status === 'error') return 'danger';
  return 'info';
};

const getDisplayStatus = (status, stage) => {
  // 优先显示解析阶段 (这才是正确的)
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
  
  // (!! 关键修复 !!) 你缺失了下面这部分逻辑
  // 回退到状态显示
  const statusMap = {
    'ready': '就绪',
    'processing': '处理中',
    'error': '错误',
    'new': '新建'
  };
  return statusMap[status] || status;
};
// 修复：添加组件内部状态来跟踪当前显示的知识库
const currentDisplayedKbId = ref(null);

// 修复：添加标志来跟踪是否是用户主动关闭
const isUserClosing = ref(false);

// 修复：添加新的计算属性来检测解析进行中状态
const isParsingInProgress = computed(() => {
  const stage = parsingState.value.stage;
  return stage === 'picking_model' || stage === 'pending' || stage === 'loading' || 
         stage === 'chunking' || stage === 'embedding' || stage === 'parsing';
});

// 修复：简化显示逻辑
const shouldShowActionButtons = computed(() => {
  const stage = parsingState.value.stage;
  return stage === 'idle' || stage === 'complete' || stage === 'error' || stage === 'cancelled';
});

const shouldShowParseButton = computed(() => {
  const kb = store.selectedKnowledgeBase;
  const stage = parsingState.value.stage;
  return kb && kb.status !== 'ready' && kb.sourceFilePath && 
         (stage === 'idle' || stage === 'error' || stage === 'cancelled');
});

const shouldShowDetails = computed(() => {
  const stage = parsingState.value.stage;
  return stage === 'idle' || stage === 'complete' || stage === 'error' || stage === 'cancelled';
});

watch(() => store.selectedKnowledgeBase, (newKb, oldKb) => {
  console.log(`[RightPanel] watch selectedKnowledgeBase:`, {
    oldKb: oldKb ? { id: oldKb.id, name: oldKb.name, stage: oldKb.parsingState?.stage, status: oldKb.status } : null,
    newKb: newKb ? { id: newKb.id, name: newKb.name, stage: newKb.parsingState?.stage, status: newKb.status } : null,
    isEnteringParsingMode: isEnteringParsingMode.value,
    currentDisplayedKbId: currentDisplayedKbId.value,
    isUserClosing: isUserClosing.value
  });

  // 修复：如果是用户主动关闭，不进行任何恢复操作
  if (isUserClosing.value) {
    console.log(`[RightPanel] watch: User closed panel, skipping state restoration`);
    isUserClosing.value = false;
    return;
  }

  // 修复：更新当前显示的知识库ID
  if (newKb) {
    currentDisplayedKbId.value = newKb.id;
  } else {
    currentDisplayedKbId.value = null;
  }

  // 修复：防止在解析过程中selectedKnowledgeBase被重置为null
  if (oldKb && !newKb && isParsingInProgress.value) {
    console.log(`[RightPanel] watch: Preventing KB reset during parsing, restoring old KB`);
    // 保持当前选中的知识库，不进行重置
    store.setSelectedKnowledgeBase(oldKb);
    return;
  }

  if (isEnteringParsingMode.value && newKb && oldKb && newKb.id === oldKb.id) {
    console.log(`[RightPanel] watch: Same KB during parsing mode transition, skipping reset`);
    isEnteringParsingMode.value = false;
    return;
  }
  
  if (newKb && oldKb && newKb.id === oldKb.id) {
      const oldStage = oldKb.parsingState?.stage;
      const newStage = newKb.parsingState?.stage;
      console.log(`[RightPanel] watch: Same KB stage change: ${oldStage} -> ${newStage}`);
      
      if ((oldStage === 'parsing' || oldStage === 'pending' || oldStage === 'loading' || oldStage === 'chunking' || oldStage === 'embedding') && 
          (newStage === 'idle' || newStage === 'complete' || newStage === 'cancelled' || newStage === 'error')) {
          if (newStage === 'complete' && newKb.status === 'ready') {
              console.log(`[RightPanel] watch: Parsing completed successfully for KB "${newKb.name}"`);
              ElNotification({ title: '成功', message: `知识库 "${newKb.name}" 解析完成！`, type: 'success' });
          } else if (newStage === 'cancelled') {
              console.log(`[RightPanel] watch: Parsing cancelled for KB "${newKb.name}"`);
              ElNotification({ title: '已取消', message: `知识库 "${newKb.name}" 解析已取消。`, type: 'info' });
          } else {
              console.log(`[RightPanel] watch: Parsing interrupted or failed for KB "${newKb.name}"`);
              ElNotification({ title: '操作中断', message: `知识库 "${newKb.name}" 解析已取消或失败。`, type: 'warning' });
          }
      }
  }
  
  if (newKb) {
    console.log(`[RightPanel] watch: Setting up for new KB: ${newKb.name} (ID: ${newKb.id})`);
    editableName.value = newKb.name;
    originalName = newKb.name;
    // if(newKb.parsingState?.stage !== 'picking_model') {
    //   console.log(`[RightPanel] watch: Resetting selected model because stage is not picking_model`);
    //   modelStore.setSelectedModel(null);
    // }
  } else {
    console.log(`[RightPanel] watch: No KB selected, resetting model selection`);
    modelStore.setSelectedModel(null);
  }
}, { immediate: true, deep: true });

const handleClose = () => { 
  console.log(`[RightPanel] handleClose: Closing detail panel for KB ${store.selectedKnowledgeBase?.id}`);
  // 修复：设置用户主动关闭标志
  isUserClosing.value = true;
  store.setSelectedKnowledgeBase(null); 
};

// 其他函数保持不变...
const handleNameSave = async () => {
  console.log(`[RightPanel] handleNameSave: Triggered`);
  const currentKb = store.selectedKnowledgeBase;

  if (currentKb && editableName.value && editableName.value.trim() && editableName.value !== originalName) {
    console.log(`[RightPanel] handleNameSave: Name changed from "${originalName}" to "${editableName.value}", sending PUT request`);
    
    try {
      await store.updateKnowledgeBase(currentKb.id, { name: editableName.value });
      console.log(`[RightPanel] handleNameSave: Name update successful`);
      ElNotification({ title: '成功', message: '知识库名称已更新。', type: 'success' });
      originalName = editableName.value;
    } catch (err) {
      console.error(`[RightPanel] handleNameSave: Name update failed:`, err);
      ElNotification({ title: '更新失败', message: err.message || '未知错误', type: 'error' });
      editableName.value = originalName;
    }
  } else if (currentKb) {
    console.log(`[RightPanel] handleNameSave: Name did not change or was empty. Resetting input to "${originalName}"`);
    editableName.value = originalName;
  } else {
    console.log(`[RightPanel] handleNameSave: No current KB selected`);
  }
};

// 修复：重新上传文件后重置状态
const handleFileChange = async (uploadFile) => {
    console.log(`[RightPanel] handleFileChange: Triggered with file:`, uploadFile);
    if (uploadFile && uploadFile.raw) {
        ElNotification({ title: '上传中...', message: `正在上传 ${uploadFile.name}...`, type: 'info' });
        try {
            console.log(`[RightPanel] handleFileChange: Starting reupload for KB ${store.selectedKnowledgeBase.id}`);
            await store.reuploadFile(store.selectedKnowledgeBase.id, uploadFile.raw);
            console.log(`[RightPanel] handleFileChange: Reupload successful`);
            
            ElNotification({ 
                title: '成功', 
                message: '文件重新上传成功！知识库状态已重置。', 
                type: 'success' 
            });
        } catch (err) {
            console.error(`[RightPanel] handleFileChange: Reupload failed:`, err);
            ElNotification({ title: '上传失败', message: err.message, type: 'error' });
        }
    } else {
        console.log(`[RightPanel] handleFileChange: No valid file provided`);
    }
};

const handleDelete = async () => {
    console.log(`[RightPanel] handleDelete: Triggered for KB "${store.selectedKnowledgeBase.name}" (ID: ${store.selectedKnowledgeBase.id})`);
    try {
        await ElMessageBox.confirm(`确定要删除知识库 "${store.selectedKnowledgeBase.name}" 吗？此操作不可逆。`, '警告', {
            confirmButtonText: '确定删除',
            cancelButtonText: '取消',
            type: 'warning',
        });
        console.log(`[RightPanel] handleDelete: User confirmed deletion`);
        await store.deleteKnowledgeBase(store.selectedKnowledgeBase.id);
        console.log(`[RightPanel] handleDelete: Deletion successful`);
        ElNotification({ title: '已删除', message: '知识库已成功删除。', type: 'info' });
    } catch (err) {
        if (err !== 'cancel') {
            console.error(`[RightPanel] handleDelete: Deletion failed:`, err);
            ElNotification({ title: '删除失败', message: err.message, type: 'error' });
        } else {
            console.log(`[RightPanel] handleDelete: User cancelled deletion`);
        }
    }
};

const handleParseClick = async () => {
  console.log(`[RightPanel] handleParseClick: Fired for KB "${store.selectedKnowledgeBase.name}" (ID: ${store.selectedKnowledgeBase.id})`);
  
  const currentKbId = store.selectedKnowledgeBase.id;
  isEnteringParsingMode.value = true;
  console.log(`[RightPanel] handleParseClick: Set isEnteringParsingMode to true`);
  
  try {
    await store.enterParsingMode(currentKbId);
    console.log(`[RightPanel] handleParseClick: Successfully entered parsing mode`);
    
    if (!store.selectedKnowledgeBase || store.selectedKnowledgeBase.id !== currentKbId) {
      console.warn(`[RightPanel] handleParseClick: Selected knowledge base was lost, restoring...`);
      const kb = store.knowledgeBaseList.find(kb => kb.id === currentKbId);
      if (kb) {
        store.setSelectedKnowledgeBase(kb);
        console.log(`[RightPanel] handleParseClick: Restored KB selection`);
      } else {
        console.error(`[RightPanel] handleParseClick: Could not find KB with ID ${currentKbId} in list`);
      }
    }
  } catch (error) {
    console.error(`[RightPanel] handleParseClick: Error entering parsing mode:`, error);
    ElNotification({ title: '操作失败', message: '无法进入解析模式', type: 'error' });
  } finally {
    nextTick(() => {
      isEnteringParsingMode.value = false;
      console.log(`[RightPanel] handleParseClick: Set isEnteringParsingMode to false in nextTick`);
    });
  }
};

const handleConfirmParsing = async () => {
  console.log(`[RightPanel] handleConfirmParsing: Triggered`);
  try {
    // 修复：在 await 之前获取 modelId，防止 watch 提前重置
    const modelId = modelStore.selectedModel?.id;

    if (!modelId) {
        console.log(`[RightPanel] handleConfirmParsing: No model selected`);
        ElNotification({ title: '错误', message: '未选择任何模型。', type: 'error' });
        return;
    }
    console.log(`[RightPanel] handleConfirmParsing: Starting parsing with model ID: ${modelId}`);
    
    // 状态将在此处改变
    await store.startParsing(store.selectedKnowledgeBase.id, modelId);
    
    console.log(`[RightPanel] handleConfirmParsing: Parsing started successfully`);
    ElNotification({ title: '解析开始', message: '知识库正在后台解析...', type: 'info' });
    
    // 修复：在此处手动重置模型，而不是在 watch 中
    modelStore.setSelectedModel(null);
    
  } catch (err) {
    console.error(`[RightPanel] handleConfirmParsing: Parsing failed to start:`, err);
    ElNotification({ title: '解析失败', message: err.message, type: 'error' });
  }
};

const handleCancelPicking = () => {
  console.log(`[RightPanel] handleCancelPicking: Triggered, resetting parsing state to idle`);
  
  // 修复：先重置模型，再更新状态
  modelStore.setSelectedModel(null);
  
  // 这将触发 stage 改变 -> 布局切换
  store.updateKnowledgeBase(store.selectedKnowledgeBase.id, { parsingState: { stage: 'idle', progress: 0 } });
};

const handleCancelParsing = async () => {
  console.log(`[RightPanel] handleCancelParsing: Triggered for KB ${store.selectedKnowledgeBase.id}`);
  try {
    await store.cancelParsing(store.selectedKnowledgeBase.id);
    console.log(`[RightPanel] handleCancelParsing: Parsing cancelled successfully`);
    ElNotification({ title: '操作已取消', message: '解析任务已取消。', type: 'info' });
  } catch (err) {
    console.error(`[RightPanel] handleCancelParsing: Failed to cancel parsing:`, err);
    ElNotification({ title: '取消失败', message: err.message, type: 'error' });
  }
};

onUnmounted(() => {
  console.log(`[RightPanel] Component unmounted, currentDisplayedKbId: ${currentDisplayedKbId.value}`);

});


</script>

<style scoped>
.right-panel { width: 100%; height: 100%; display: flex; flex-direction: column; box-sizing: border-box; }
.right-panel :deep(.el-card__body) { flex-grow: 1; padding: 0; display: flex; flex-direction: column; min-height: 0; overflow: hidden; }
.right-panel :deep(.el-card__header) { flex-shrink: 0; }
.panel-content { flex-grow: 1; overflow-y: auto; padding: 20px; }
.card-header { display: flex; justify-content: space-between; align-items: center; }
.button-group { margin-bottom: 20px; display: flex; flex-wrap: wrap; gap: 10px; }
.editable-header { margin-bottom: 20px; }
.parsing-controls { margin-bottom: 20px; }
.parsing-message { 
  font-size: 14px; 
  color: #666; 
  margin: 8px 0; 
  font-style: italic; 
}
</style>