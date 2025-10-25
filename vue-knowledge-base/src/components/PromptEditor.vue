<template>
  <div class="prompt-editor">
    <!-- 查询输入区域 -->
    <div class="query-section">
      <el-input 
        v-model="mainContent" 
        type="textarea" 
        :rows="4"
        placeholder="请输入您的问题或提示词..." 
        class="query-input"
        :disabled="isGenerating"
      />
      <div class="query-actions">
        <el-button 
          @click="handleSelectKBClick"
          :disabled="isGenerating"
        >
           {{ store.promptModeTable === 'kb' ? '关闭知识库选择' : '选择知识库' }}
        </el-button>
        <el-button 
          @click="handleSelectModelClick"
          :disabled="isGenerating"
        >
          选择模型
        </el-button>

          <!-- 修复三: 新增控制右侧面板显示的按钮 -->
        <el-button
            @click="toggleContextPanel"
            :disabled="retrievedContexts.length === 0"
        >
            {{ isContextPanelVisible ? '隐藏相关信息' : '显示相关信息' }}
        </el-button>
          
        <el-button 
            type="primary" 
            :disabled="isGenerateDisabled"
            :loading="isGenerating"
            @click="handleGenerate"
        >
            {{ isGenerating ? '检索中...' : '检索增强' }}
        </el-button>
      </div>
    </div>


    <!-- 配置信息显示 -->
    <div class="config-display">
      
       <div class="config-item">
        <span class="label">当前模型:</span>
        <el-tag v-if="selectedModel" type="success" size="small">
          {{ selectedModel.name }}
        </el-tag>
        <span v-else class="no-kb">未选择模型</span>
      </div>

      <div class="config-item">
        <span class="label">知识库:</span>
        <div class="kb-tags">
          <el-tag 
            v-for="kb in selectedKBs" 
            :key="kb.id" 
            size="small"
            class="kb-tag"
          >
            {{ kb.name }}
          </el-tag>
          <span v-if="selectedKBs.length === 0" class="no-kb">未选择知识库</span>
        </div>
      </div>
    </div>

    <!-- 修复二: 主内容区改为左右布局 -->
    <div 
      class="main-content-area"
      :class="{ 'visible': isContextPanelVisible && retrievedContexts.length > 0 }"
    >
      <!-- 左侧: 生成结果区域 -->
      <div class="result-panel">
        <div class="result-section">
          <div class="generated-content">
            <div class="result-header">
              <h4>增强后的提示词:</h4>
              <el-button 
                size="small" 
                @click="handleCopyAnswer"
                :disabled="!generatedContent"
              >
                复制
              </el-button>
            </div>
            <div class="answer-content">
              {{ generatedContent || "请点击'检索增强'按钮获取增强提示词" }}
            </div>
          </div>
        </div>
      </div>

      <!-- 右侧: 检索上下文显示 -->
      <div 
        class="context-panel"
        :class="{ 'visible': isContextPanelVisible && retrievedContexts.length > 0 }"
      >
        <div class="context-section">
          <div class="section-header">
            <h4>检索到的相关内容 ({{ retrievedContexts.length }}条)</h4>
            <el-tag type="info">阈值: {{ (similarityThreshold * 100).toFixed(0) }}%</el-tag>
          </div>
          
          <div class="context-list">
            <div 
              v-for="(context, index) in retrievedContexts" 
              :key="index" 
              class="context-item"
              :class="{ 'high-score': context.score > 0.8, 'medium-score': context.score > 0.6 }"
            >
              <div class="context-header">
                <div class="context-meta">
                  <el-tag size="small">KB{{ context.source_kb_id }}</el-tag>
                  <span class="score">相似度: {{ (context.score * 100).toFixed(1) }}%</span>
                </div>
                <el-button 
                  size="small" 
                  text 
                  @click="toggleContextExpand(index)"
                >
                  {{ expandedContexts[index] ? '收起' : '展开' }}
                </el-button>
              </div>
              
              <div 
                class="context-text"
                :class="{ 'expanded': expandedContexts[index] }"
              >
                {{ context.text }}
              </div>
              
              <div class="file-path">
                <el-icon><Document /></el-icon>
                {{ context.file_path }}
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- 历史记录对话框 -->
    <el-dialog
      v-model="showHistory"
      title="生成历史"
      width="60%"
    >
      <div class="history-list">
        <el-empty description="暂无历史记录" />
      </div>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, watch } from 'vue';
import { useKnowledgeBaseStore } from '../stores/knowledgeBase';
import { ElMessage } from 'element-plus';
import { Document } from '@element-plus/icons-vue';

const store = useKnowledgeBaseStore();

// 响应式数据
const mainContent = ref('');
const generatedContent = ref('');
const isGenerating = ref(false);
const retrievedContexts = ref([]);
const expandedContexts = ref({});
const showHistory = ref(false);
const similarityThreshold = ref(0.3);
const isContextPanelVisible = ref(true); // 右侧面板是否可见

// 从 Store 获取状态
const selectedModel = computed(() => store.promptSelectedModel);
const selectedKBs = computed(() => store.promptSelection);

const isGenerateDisabled = computed(() => {
  return selectedKBs.value.length === 0 || 
         !mainContent.value.trim() ||
         isGenerating.value;
});

const handleSelectKBClick = () => {
  if (store.promptModeTable === 'kb') {
    // 如果当前显示知识库表，则关闭它
    store.setPromptModeTable('hidden');
  } else {
    // 否则打开知识库表
    store.setPromptModeTable('kb');
  }
};

const handleSelectModelClick = () => {
  store.setPromptModeTable('model');
};

const toggleContextPanel = () => {
  isContextPanelVisible.value = !isContextPanelVisible.value;
};

const toggleContextExpand = (index) => {
  expandedContexts.value[index] = !expandedContexts.value[index];
};

const handleCopyAnswer = async () => {
  if (!generatedContent.value) return;
  try {
    await navigator.clipboard.writeText(generatedContent.value);
    ElMessage.success('增强提示词已复制到剪贴板');
  } catch (err) {
    console.error('复制失败:', err);
    ElMessage.error('复制失败');
  }
};

const handleGenerate = async () => {
  if (isGenerateDisabled.value) return;
  store.setPromptModeTable('hidden');
  isGenerating.value = true;
  generatedContent.value = '';
  retrievedContexts.value = [];
  expandedContexts.value = {};
  
  try {
    console.log("开始调用 RAG 检索 API...");
    const ragRequest = {
      query: mainContent.value.trim(),
      knowledgebase_ids: selectedKBs.value.map(kb => kb.id),
      top_k: 5
    };
    
    console.log("RAG 请求参数:", ragRequest);
    generatedContent.value = "正在检索相关知识库...";
    
    const response = await fetch('/api/v1/rag/retrieve', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(ragRequest)
    });
    
    if (!response.ok) {
      const errorData = await response.json().catch(() => ({}));
      throw new Error(errorData.detail || `请求失败: ${response.status} ${response.statusText}`);
    }
    
    const ragResponse = await response.json();
    console.log("RAG 响应:", ragResponse);

    generatedContent.value = ragResponse.enhanced_prompt;
    retrievedContexts.value = ragResponse.retrieved_contexts || [];
    
    // 如果检索到内容，自动显示右侧面板
    if (retrievedContexts.value.length > 0) {
      isContextPanelVisible.value = true;
    }
    
    ElMessage.success('检索增强完成！');
    
  } catch (error) {
    console.error('RAG 检索失败:', error);
    generatedContent.value = `检索失败: ${error.message}`;
    ElMessage.error(`检索失败: ${error.message}`);
  } finally {
    isGenerating.value = false;
  }
};

watch(mainContent, (newValue) => {
  if (newValue && generatedContent.value && !isGenerating.value) {
    generatedContent.value = "";
    retrievedContexts.value = [];
    expandedContexts.value = {};
  }
});

onMounted(() => {
  console.log(`[PromptEditor MOUNTED] RAG检索功能已加载`);
});
</script>

<style scoped>
.prompt-editor {
  width: 100%;
  height: 100%;
  display: flex;
  flex-direction: column;
  gap: 16px;
  background-color: var(--el-bg-color);
  padding: 20px;
  border-radius: 4px;
  border: 1px solid var(--el-border-color-light);
  box-sizing: border-box;
}

.query-section {
  display: flex;
  flex-direction: column;
  gap: 12px;
  flex-shrink: 0;
}
.query-input :deep(.el-textarea__inner) {
  font-size: 14px;
  line-height: 1.5;
}

/* 按钮组样式 - 添加间隙和布局 */
.query-actions {
  display: flex;
  gap: 10px;
  justify-content: flex-start;
  flex-wrap: wrap;
}

.query-actions {
  display: flex;
  gap: 10px;
  justify-content: flex-end;
}

/* 配置显示 */
.config-display {
  display: flex;
  gap: 20px;
  padding: 12px;
  background-color: var(--el-fill-color-light);
  border-radius: 4px;
  flex-wrap: wrap;
  flex-shrink: 0;
}

.config-item { display: flex; align-items: center; gap: 8px; }
.config-item .label { font-size: 14px; color: var(--el-text-color-secondary); }
.config-item .hint { font-size: 12px; color: var(--el-text-color-placeholder); }
.kb-tags { display: flex; gap: 6px; flex-wrap: wrap; }
.kb-tag { max-width: 120px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.no-kb { font-size: 14px; color: var(--el-text-color-placeholder); }

/* 主内容区: 左右布局容器 */
.main-content-area {
  flex: 1;
  display: flex;
  gap: 16px;
  overflow: hidden;
  min-height: 0;
}

/* 左侧面板: 结果 */
.result-panel {
  flex: 1 1 auto;
  min-width: 0;
  display: flex;
  flex-direction: column;
}

.result-section {
  width: 100%;
  height: 100%;
  display: flex;
  flex-direction: column;
}

.generated-content {
  flex: 1;
  display: flex;
  flex-direction: column;
  min-height: 0;
}

.result-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 12px;
  flex-shrink: 0;
}

.result-header h4 { margin: 0; color: var(--el-text-color-primary); }

.answer-content {
  flex: 1;
  padding: 16px;
  background-color: var(--el-fill-color-light);
  border-radius: 4px;
  line-height: 1.6;
  white-space: pre-wrap;
  overflow-y: auto;
}

/* 右侧面板: 上下文 */
.context-panel {
  flex: 0 0 0;
  opacity: 0;
  overflow: hidden;
  visibility: hidden;
  border-left: 1px solid var(--el-border-color-light);
  transition: flex-basis 0.4s ease-in-out, opacity 0.3s ease-in-out, visibility 0.4s;
}
.context-panel.visible {
  flex-basis: 40%;
  opacity: 1;
  visibility: visible;
  padding-left: 16px;
}

.context-section {
  height: 100%;
  display: flex;
  flex-direction: column;
}

.section-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 12px;
  flex-shrink: 0;
}

.section-header h4 { margin: 0; color: var(--el-text-color-primary); }

/* 上下文列表: 垂直布局 */
.context-list {
  flex: 1;
  display: flex;
  flex-direction: column; /* 改为垂直排列 */
  gap: 12px;
  overflow-y: auto; /* 垂直滚动 */
  overflow-x: hidden;
  min-height: 0;
  padding-right: 8px; /* 为滚动条留出空间 */
}

.context-item {
  background-color: var(--el-fill-color-light);
  border-radius: 4px;
  padding: 12px;
  border-left: 4px solid var(--el-border-color);
  transition: background-color 0.3s ease;
  display: flex;
  flex-direction: column;
  flex-shrink: 0; /* 防止项目被压缩 */
}

.context-item:hover {
  background-color: var(--el-fill-color);
}

.context-item.high-score { border-left-color: var(--el-color-success); }
.context-item.medium-score { border-left-color: var(--el-color-warning); }

.context-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 8px;
}

.context-meta { display: flex; align-items: center; gap: 8px; }
.score { font-size: 12px; color: var(--el-text-color-secondary); }

.context-text {
  line-height: 1.6;
  color: var(--el-text-color-primary);
  overflow: hidden;
  display: -webkit-box;
  -webkit-line-clamp: 3; 
  -webkit-box-orient: vertical;
  word-break: break-all;
}

.context-text.expanded {
  -webkit-line-clamp: unset;
}

.file-path {
  margin-top: 8px;
  font-size: 12px;
  color: var(--el-text-color-secondary);
  display: flex;
  align-items: center;
  gap: 4px;
  word-break: break-all;
}

/* 历史记录 */
.history-list {
  min-height: 200px;
}
</style>