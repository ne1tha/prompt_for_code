<template>
  <Transition name="slide-fade">
    <el-card v-if="store.selectedModel" class="detail-panel">
      <div class="card-header">
        <span>模型详情</span>
        <el-button :icon="Close" circle @click="handleClose" />
      </div>

      <el-form :model="editableModel" label-position="top" class="detail-form">
        <el-form-item label="模型名称">
          <el-input v-model="editableModel.name" />
        </el-form-item>
        <el-form-item label="模型类型">
          <el-select v-model="editableModel.model_type" style="width: 100%;">
            <el-option label="Embedding (词嵌入)" value="embedding" />
            <el-option label="Generative (生成式)" value="generative" />
          </el-select>
        </el-form-item>
        
        <el-form-item 
            v-if="editableModel.model_type === 'embedding'" 
            label="模型维度 (Dimensions)" 
            required
          >
            <el-input-number v-model="editableModel.dimensions" :min="0" placeholder="例如: 384, 768" style="width: 100%;" />
        </el-form-item>
        
        <el-form-item label="API Key">
          <el-input v-model="editableModel.api_key" type="password" show-password />
        </el-form-item>
        <el-form-item label="Endpoint URL">
          <el-input v-model="editableModel.endpoint_url" />
        </el-form-item>
      </el-form>

      <div class="footer-actions">
        <el-button type="danger" plain @click="handleDelete">删除模型</el-button>
        <el-button type="primary" @click="handleSave">保存更改</el-button>
      </div>
    </el-card>
  </Transition>
</template>

<script setup>
import { ref, watch } from 'vue';
import { useModelStore } from '../stores/modelStore';
import { Close } from '@element-plus/icons-vue';
import { ElNotification, ElMessageBox } from 'element-plus';

const store = useModelStore();
const editableModel = ref(null);

watch(() => store.selectedModel, (newModel) => { 
  if (newModel) { 
    // (修正) 确保所有字段都被正确复制
    editableModel.value = { 
      id: newModel.id,
      name: newModel.name,
      model_type: newModel.model_type,
      api_key: newModel.api_key,
      endpoint_url: newModel.endpoint_url,
      dimensions: newModel.dimensions === null ? 0 : newModel.dimensions
    }; 
  } else { 
    editableModel.value = null; 
  } 
}, { deep: true, immediate: true });

const handleClose = () => { store.setSelectedModel(null); };

const handleSave = async () => { 
  try {
    // (修复 3) 校验逻辑改为: 必须是数字且不能小于0
    if (editableModel.value.model_type === 'embedding' && (editableModel.value.dimensions === null || editableModel.value.dimensions < 0)) {
       ElNotification({
        title: '错误',
        message: 'Embedding 模型必须指定大于等于 0 的维度。',
        type: 'error',
      });
      return;
    }
    
    // (修复 4) 如果 UI 上是 0, 发送给后端 null
    const payload = { ...editableModel.value };
    if (payload.model_type === 'embedding' && payload.dimensions === 0) {
      payload.dimensions = null;
    }

    await store.updateModel(payload); // 发送 payload
    ElNotification({ title: '成功', message: '模型信息已保存。', type: 'success' });
  } catch (err) {
    ElNotification({ title: '保存失败', message: err.message || '未知错误', type: 'error' });
  }
};

// ... (handleDelete 保持不变) ...
const handleDelete = async () => { 
  try {
    await ElMessageBox.confirm(`确定要删除模型 "${editableModel.value.name}" 吗？`, '警告', { 
      confirmButtonText: '确定删除', 
      cancelButtonText: '取消', 
      type: 'warning', 
    });
    await store.deleteModel(editableModel.value.id);
    ElNotification({ title: '已删除', message: '模型已成功删除。', type: 'info' });
  } catch (err) {
    if (err !== 'cancel') {
      ElNotification({ title: '删除失败', message: err.message || '未知错误', type: 'error' });
    }
  } 
};
</script>

<style scoped>
/* 样式保持不变 */
.detail-panel { width: 100%; height: 100%; display: flex; flex-direction: column; box-sizing: border-box; }
.detail-panel :deep(.el-card__body) { flex-grow: 1; display: flex; flex-direction: column; padding: 0; min-height: 0; overflow: hidden; }
.card-header { flex-shrink: 0; padding: 18px 20px; border-bottom: 1px solid var(--el-card-border-color, #ebeef5); }
.detail-form { flex-grow: 1; overflow-y: auto; padding: 20px; }
.footer-actions { flex-shrink: 0; padding: 10px 20px; border-top: 1px solid var(--el-card-border-color, #ebeef5); }
.card-header, .footer-actions { display: flex; justify-content: space-between; align-items: center; }
</style>