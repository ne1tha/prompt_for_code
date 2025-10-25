<template>
  <Transition name="slide-fade">
    <el-card v-if="props.visible" class="action-panel">
      <template #header>
        <div class="card-header">
          <span>配置新模型</span>
          <el-button 
            :icon="Close" 
            circle 
            @click="handleClose" 
          />
        </div>
      </template>
      
      <div class="panel-content">
        <el-form :model="form" label-position="top">
          <el-form-item label="模型名称" required>
            <el-input v-model="form.name" placeholder="例如：OpenAI - gpt-3.5-turbo" />
          </el-form-item>
          <el-form-item label="模型类型" required>
            <el-select v-model="form.model_type" placeholder="请选择模型类型" style="width: 100%;">
              <el-option label="Embedding (词嵌入)" value="embedding" />
              <el-option label="Generative (生成式)" value="generative" />
            </el-select>
          </el-form-item>
          
          <el-form-item 
            v-if="form.model_type === 'embedding'" 
            label="模型维度 (Dimensions)" 
            required
          >
            <el-input-number v-model="form.dimensions" :min="0" placeholder="0表示不设置维度，使用对应平台默认维度，请确认是否支持。" style="width: 100%;" />
          </el-form-item>
          
          <el-form-item label="API 密钥 (API Key)">
            <el-input v-model="form.api_key" placeholder="请输入您的 API 密钥（可选）" show-password />
          </el-form-item>
          
          <el-form-item label="端点 URL (Endpoint URL)" required>
            <el-input v-model="form.endpoint_url" placeholder="例如：https://api.openai.com/v1/chat/completions 或 BAAI/bge-small-en-v1.5" />
          </el-form-item>
          
        </el-form>
      </div>
      
      <div class="panel-footer">
        <div class="footer-buttons">
          <el-button @click="handleClose">取消</el-button>
          <el-button 
            type="primary" 
            @click="handleSubmit"
            :disabled="!form.name.trim() || !form.endpoint_url.trim()"
          >
            确认配置
          </el-button>
        </div>
      </div>

    </el-card>
  </Transition>
</template>

<script setup>
import { ref, watch } from 'vue';
import { useModelStore } from '../stores/modelStore';
import { ElNotification } from 'element-plus';
import { Close } from '@element-plus/icons-vue';

const props = defineProps({
  visible: Boolean
});
const emit = defineEmits(['close']);
const store = useModelStore();

// (关键修复) 添加 dimensions
const getInitialForm = () => ({
  name: '',
  model_type: 'generative',
  api_key: '',
  endpoint_url: '',
  dimensions: null, // (新增)
});

const form = ref(getInitialForm());

watch(() => store.selectedModel, (newModel) => {
    if (props.visible && newModel) {
        handleClose(); 
    }
});

watch(() => props.visible, (newVal) => {
    if (newVal) {
        resetState();
    }
});

const handleClose = () => {
    emit('close');
};

const handleSubmit = async () => {
  // 基础校验
  if (!form.value.name || !form.value.endpoint_url) {
    ElNotification({
      title: '错误',
      message: '模型名称和端点 URL 是必填项。',
      type: 'error',
    });
    return;
  }
  
  // (关键修复) 维度校验
  if (form.value.model_type === 'embedding' && (!form.value.dimensions && form.value.dimensions < 0)) {
     ElNotification({
      title: '错误',
      message: 'Embedding 模型必须指定大于等于 0 的维度。',
      type: 'error',
    });
    return;
  }
  
  try {
    // (关键修复) 提交包含 dimensions 的 payload
    await store.addModel({
      name: form.value.name,
      model_type: form.value.model_type,
      api_key: form.value.api_key || null,
      endpoint_url: form.value.endpoint_url,
      dimensions: form.value.dimensions // (新增)
    });
    
    ElNotification({
      title: '成功',
      message: '新模型配置成功！',
      type: 'success',
    });
    emit('close');
  } catch (err) {
    ElNotification({
      title: '创建失败',
      message: err.message || '无法连接到服务器。',
      type: 'error',
    });
  }
};
const resetState = () => {
    form.value = getInitialForm();
};
</script>

<style scoped>
/* 样式保持不变 */
.action-panel { width: 100%; height: 100%; display: flex; flex-direction: column; box-sizing: border-box; }
.card-header { display: flex; justify-content: space-between; align-items: center; }
.action-panel :deep(.el-card__body) { padding: 0; flex-grow: 1; display: flex; flex-direction: column; min-height: 0; min-width: 0; }
.panel-content { flex-grow: 1; overflow-y: auto; padding: 20px; box-sizing: border-box; }
.panel-footer { flex-shrink: 0; border-top: 1px solid var(--el-card-border-color, #ebeef5); padding: 10px 20px; }
.footer-buttons { display: flex; justify-content: flex-end; }
.slide-fade-enter-active { transition: all 0.3s ease-out; }
.slide-fade-leave-active { transition: all 0.3s cubic-bezier(1, 0.5, 0.8, 1); }
.slide-fade-enter-from, .slide-fade-leave-to { transform: translateX(20px); opacity: 0; }
</style>