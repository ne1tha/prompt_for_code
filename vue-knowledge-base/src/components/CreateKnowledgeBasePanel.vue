<template>
  <Transition name="fade">
    <el-card v-if="props.visible" class="action-panel">
      <template #header>
        <div class="card-header">
          <span>创建知识库 - {{ panelModeTitle }}</span>
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
          title="点击表格行进行选择，完成后将自动返回配置。" 
          type="info" 
          show-icon 
          style="margin-bottom: 20px;" 
          :closable="false"
        />

        <div v-if="panelMode === 'config'" class="config-content">
          <el-form :model="form" label-position="top" class="panel-form">
            <el-form-item label="知识库名称" required>
              <el-input v-model="form.name" placeholder="请输入知识库名称" />
            </el-form-item>
            <el-form-item label="知识库描述">
              <el-input v-model="form.description" type="textarea" :rows="2" placeholder="请输入描述（可选）" />
            </el-form-item>
            
            <el-form-item label="父知识库（可选）">
              <div class="parent-kb-selector">
                <span>当前选择: <strong>{{ parentKb?.name || '无' }}</strong></span>
                <div class="button-group">
                  <el-button @click="setPanelMode('kb-picking')">选择父知识库</el-button>
                  <el-button v-if="parentKb" @click="clearParentSelection" type="danger">清除选择</el-button>
                </div>
              </div>
            </el-form-item>

            <el-form-item label="上传文件或压缩包" required>
              <el-upload 
                action="#" 
                :auto-upload="false" 
                v-model:file-list="form.files"
                :limit="1"
                :on-exceed="handleFileExceed"
                :on-change="handleFileChange"
              >
                <el-button type="primary">点击上传</el-button>
              </el-upload>
            </el-form-item>
          </el-form>
        </div>
      </div>
      
      <div class="panel-footer">
        <div v-if="panelMode === 'config'" class="footer-buttons">
          <el-button @click="handleClose">取消</el-button>
          <el-button 
            type="primary" 
            @click="handleSubmit"
            :disabled="!form.name.trim() || form.files.length === 0 || isLoading"
            :loading="isLoading"
          >
            {{ isLoading ? '正在提交...' : '提交创建' }}
          </el-button>
        </div>
      </div>

    </el-card>
  </Transition>
</template>

<script setup>
import { ref, watch, computed } from 'vue';
import { useKnowledgeBaseStore } from '../stores/knowledgeBase';
import { ElNotification, genFileId } from 'element-plus';
import { Close } from '@element-plus/icons-vue';

const props = defineProps({
  visible: Boolean
});
const emit = defineEmits(['close', 'panel-mode-change']);
const PANEL_MODE = {
    CONFIG: 'config',
    KB_PICKING: 'kb-picking',
};
const store = useKnowledgeBaseStore();
const panelMode = ref(PANEL_MODE.CONFIG);
const parentKb = ref(null); 
const isLoading = ref(false); // (新增)
const form = ref({
  name: '',
  description: '',
  parentId: null,
  files: [],
});
const panelModeTitle = computed(() => {
    return panelMode.value === PANEL_MODE.KB_PICKING ? '选择父知识库' : '配置';
});
// ... (panelModeTitle, watch store.selectedKnowledgeBase, watch props.visible 保持不变) ...
watch(() => store.selectedKnowledgeBase, (newKb) => {
    if (panelMode.value === PANEL_MODE.KB_PICKING && newKb) {
        parentKb.value = newKb;
        form.value.parentId = newKb.id;
        setPanelMode(PANEL_MODE.CONFIG); 
        return;
    } else if (panelMode.value === PANEL_MODE.CONFIG && newKb) {
        parentKb.value = null;
        form.value.parentId = null;
        handleClose(); 
    }
});
watch(() => props.visible, (newVal) => {
    if (newVal) {
        resetState();
    }
});
const setPanelMode = (mode) => {
    console.log(`[CreatePanel] Setting panel mode to: ${mode}`);
    panelMode.value = mode;
    
    // (!! 关键修复 2 !!) 
    // 确保只在 *进入* picking 模式时才清空 selection
    if (mode !== PANEL_MODE.CONFIG) {
        console.log(`[CreatePanel] Entering picking mode, setting store selection to null.`);
        store.setSelectedKnowledgeBase(null); 
    }
    emit('panel-mode-change', mode); 
};
const clearParentSelection = () => {
    parentKb.value = null;
    form.value.parentId = null;
};
const handleClose = () => {
    emit('close');
};
// (新增) 处理文件列表
const handleFileExceed = (files) => {
  const file = files[0];
  file.uid = genFileId();
  form.value.files = [file];
};
const handleFileChange = (file) => {
  form.value.files = [file];
};

// (修改) 完整的 handleSubmit 逻辑
const handleSubmit = async () => {
  if (!form.value.name.trim() || form.value.files.length === 0) {
    ElNotification({
      title: '错误',
      message: '知识库名称和文件是必填项。',
      type: 'error',
    });
    return;
  }

  isLoading.value = true;
  let createdKB = null;

  try {
    // --- 第 1 步: 创建知识库条目 ---
    createdKB = await store.createKnowledgeBase({
        name: form.value.name,
        description: form.value.description,
        parentId: form.value.parentId, // 后端 schema 尚不支持
    });

    // --- 第 2 步: 上传文件 ---
    const fileObject = form.value.files[0];
    const fileToUpload = fileObject.raw ? fileObject.raw : fileObject;
    if (!createdKB || !createdKB.id || !fileToUpload) {
      throw new Error("知识库条目创建失败或文件丢失。");
    }
    
    const formData = new FormData();
    formData.append("file", fileToUpload);

    const uploadResponse = await fetch(
      // 对应 `POST /api/v1/knowledgebases/{id}/upload`
      `/api/v1/knowledgebases/${createdKB.id}/upload`, 
      {
        method: 'POST',
        body: formData,
      }
    );

    if (!uploadResponse.ok) {
      const errData = await uploadResponse.json();
      throw new Error(errData.detail || "文件上传失败。");
    }
    
    // (可选) 上传成功后，更新 store 中的那一项
    const updatedKB = await uploadResponse.json();
    store._updateKBState(updatedKB); // (需要将 _updateKBState 暴露在 store 中)

    ElNotification({
      title: '成功',
      message: '知识库创建成功，文件已上传！',
      type: 'success',
    });
    emit('close');

  } catch (err) {
    ElNotification({
      title: '创建失败',
      message: err.message,
      type: 'error',
    });
    
    // (回滚) 如果文件上传失败，但 KB 条目创建成功了，最好删除它
    if (createdKB && createdKB.id) {
        try {
            await store.deleteKnowledgeBase(createdKB.id);
            ElNotification({
                title: '回滚',
                message: '由于文件上传失败，已自动删除知识库条目。',
                type: 'warning',
            });
        } catch (deleteErr) {
            ElNotification({
                title: '回滚失败',
                message: '请手动删除已创建的知识库条目。',
                type: 'error',
            });
        }
    }
  } finally {
    isLoading.value = false;
  }
};

const resetState = () => {
    panelMode.value = PANEL_MODE.CONFIG;
    parentKb.value = null;
    isLoading.value = false; // (新增)
    form.value = {
        name: '',
        description: '',
        parentId: null,
        files: [],
    };
    emit('panel-mode-change', 'config'); 
};
</script>

<style scoped>
/* 样式保持不变 */
.action-panel {
  width: 100%; height: 100%; display: flex; flex-direction: column; box-sizing: border-box; 
}
.card-header {
  display: flex; justify-content: space-between; align-items: center;
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
  flex-shrink: 0; border-top: 1px solid var(--el-card-border-color, #ebeef5); padding: 10px 20px;
}
.footer-buttons {
  display: flex; justify-content: flex-end;
}
.parent-kb-selector {
    display: flex;
    flex-direction: column;
    align-items: flex-start;
    gap: 8px;
}
.button-group {
    display: flex;
    gap: 10px;
}
.fade-enter-active,
.fade-leave-active {
  transition: opacity 0.3s ease;
}
.fade-enter-from,
.fade-leave-to {
  opacity: 0;
}
</style>