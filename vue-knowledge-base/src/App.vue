<template>
  <el-container class="main-layout">
    <el-aside width="200px">
      <el-menu :default-active="activeMenu" @select="handleMenuSelect">
        <el-menu-item index="database"><el-icon>
            <Menu />
          </el-icon><span>Database</span></el-menu-item>
        <el-menu-item index="prompt"><el-icon>
            <Promotion />
          </el-icon><span>Prompt</span></el-menu-item>
        <el-menu-item index="model"><el-icon>
            <Setting />
          </el-icon><span>Model</span></el-menu-item>
      </el-menu>
      <div class="avatar-footer">
        <el-avatar>{{ currentUser.fullName[0] }}</el-avatar>
        <div class="user-info">
          <span>{{ currentUser.fullName }}</span><small>{{ currentUser.email }}</small>
        </div>
      </div>
    </el-aside>

    <el-main>
      <div class="content-body" :class="{
        'is-prompt-mode': activeMenu === 'prompt',
        'is-model-mode': activeMenu === 'model',
        'detail-is-open': isDetailPanelOpen,
        'create-panel-is-open': isCreatePanelVisible || isCreateModelPanelVisible,
        'regenerate-panel-is-open': isRegeneratePanelVisible,
        'is-picking-mode': (isRegeneratePanelVisible && regeneratePanelMode !== 'config') || (isCreatePanelVisible && createPanelMode !== 'config'),
        'is-parsing-picking-mode': isPickingForParsing,
        'prompt-table-is-open': activeMenu === 'prompt' && (store.promptModeTable === 'kb' || store.promptModeTable === 'model')
      }">

        <div class="create-panel-wrapper">
          <CreateKnowledgeBasePanel 
            :visible="isCreatePanelVisible" 
            @close="handleCreateKnowledgeBaseClose"
            @panel-mode-change="handleCreatePanelModeChange" />
          <CreateModelPanel
            :visible="isCreateModelPanelVisible"
            @close="isCreateModelPanelVisible = false"
          />
        </div>

        <div class="composition-panel-wrapper">
          <PromptEditor />
        </div>

        <div class="main-panel-wrapper" :class="{ 'show-model-table': isModelTableVisible }">
          <div class="table-wrapper-knowledge">
            <TablePanel 
              :active-menu="activeMenu"
              :header-mode="knowledgeBaseHeaderMode" 
              :is-picking-parent-kb="createPanelMode === 'kb-picking' || regeneratePanelMode === 'kb-picking'"
              @create-kb="handleCreateKnowledgeBase" 
              @parse-kb="handleParse"
              @kb-picked="handleKbPicked"
            />
          </div>
          
          <div class="table-wrapper-model">
            <ModelTablePanel 
              :is-picking-gen-model="isPickingForRegenGenModel"
              :is-picking-embedding-model="isPickingForParsing || isPickingForRegenEmbedding"
              :is-for-regenerate-panel="isPickingForRegenGenModel || isPickingForRegenEmbedding"
              :is-picking-for-prompt="activeMenu === 'prompt' && store.promptModeTable === 'model'"
              @create-model="handleCreateModel"
              @model-picked="handleRegeneratePanelModeChange('config')"
            />
          </div>
        </div>

        <div class="detail-panel-wrapper">
          <RightPanel @openRegenerateModal="handleOpenRegenerate" @analysisDatabase="handleParse" />
          <ModelDetailPanel />
        </div>

        <div class="regenerate-panel-wrapper">
          <RegenerateKnowledgeBasePanel 
            :visible="isRegeneratePanelVisible" 
            @close="isRegeneratePanelVisible = false"
            @panel-mode-change="handleRegeneratePanelModeChange" 
          />
        </div>

      </div>
    </el-main>
  </el-container>

</template>

<script setup>
import { ref, computed, watch, onMounted } from 'vue';
import { useKnowledgeBaseStore } from './stores/knowledgeBase';
import { useModelStore } from './stores/modelStore';
import { Menu, Promotion, Setting } from '@element-plus/icons-vue';
import RightPanel from './components/RightPanel.vue';
import TablePanel from './components/TablePanel.vue';
import ModelTablePanel from './components/ModelTablePanel.vue';
import CreateModelPanel from './components/CreateModelPanel.vue';
import CreateKnowledgeBasePanel from './components/CreateKnowledgeBasePanel.vue';
import RegenerateKnowledgeBasePanel from './components/RegenerateKnowledgeBasePanel.vue';
import ModelDetailPanel from './components/ModelDetailPanel.vue';
import PromptEditor from './components/PromptEditor.vue';

const store = useKnowledgeBaseStore();
const modelStore = useModelStore();
const activeMenu = ref('database');
const isCreatePanelVisible = ref(false);
const isRegeneratePanelVisible = ref(false);
const isCreateModelPanelVisible = ref(false);
const regeneratePanelMode = ref('config');
const currentUser = { fullName: 'Current User', email: 'user@example.com' };
const createPanelMode = ref('config');

onMounted(() => {
  console.log("App component mounted. Fetching initial data...");
  // 调用 action 从后端获取初始数据
  store.fetchKnowledgeBases()
    .catch(err => {
      console.error("Failed to fetch knowledge bases on mount:", err);
      // 可以在这里添加用户提示，例如 ElNotification
    });
  modelStore.fetchModels()
    .catch(err => {
      console.error("Failed to fetch models on mount:", err);
      // 添加用户提示
    });
});
// (!! 关键修复 !!) 使用 ref 存储上一个选中的 ID
const previousSelectedKbId = ref(null);

watch(() => store.selectedKnowledgeBase, (newKb) => {
  const currentSelectedKbId = newKb?.id ?? null;
  const oldKbId = previousSelectedKbId.value;


}, { deep: true }); // deep: true 仍然需要，以便能检测到 deselection (newKb变成null)

const isPickingForParsing = computed(() => {
  // 直接检查当前选中项的状态
  return store.selectedKnowledgeBase?.parsingState?.stage === 'picking_model';
});
const isPickingForRegenGenModel = computed(() => {
  return isRegeneratePanelVisible.value && regeneratePanelMode.value === 'model-picking';
});

const isPickingForRegenEmbedding = computed(() => {
  return isRegeneratePanelVisible.value && regeneratePanelMode.value === 'embedding-model-picking';
});

const handleCreatePanelModeChange = (mode) => {
    createPanelMode.value = mode;
    if (mode !== 'config') {
        store.setSelectedKnowledgeBase(null);
        modelStore.setSelectedModel(null);
    }
};

const handleCreateKnowledgeBaseClose = () => {
  if (isCreatePanelVisible.value === true) {
    isCreatePanelVisible.value = false;
    createPanelMode.value = 'config';
  }
};

const isDetailPanelOpen = computed(() => {
  if (isCreatePanelVisible.value) {
    console.log(`[App COMPUTED isDetailPanelOpen] BLOCKED: CreatePanel is visible.`);
    return false;
  }
  
  const kbSelected = !!store.selectedKnowledgeBase;
  const modelSelected = !!modelStore.selectedModel;
  
  if (isRegeneratePanelVisible.value) {
    console.log(`[App COMPUTED isDetailPanelOpen] BLOCKED: RegeneratePanel is visible.`);
    return false; 
  }
  if(isPickingForParsing.value) {
    console.log(`[App COMPUTED isDetailPanelOpen] BLOCKED: Picking for Parsing.`);
    return false; 
  }
  if (activeMenu.value === 'prompt') {
    console.log(`[App COMPUTED isDetailPanelOpen] BLOCKED: Active menu is prompt.`);
    return false;
  }
  const result = kbSelected || modelSelected;
  console.log(`[App COMPUTED isDetailPanelOpen] Result: ${result} (kb: ${kbSelected}, model: ${modelSelected})`);
  return result;
});


const isModelTableVisible = computed(() => {
    // (!! 新增调试 !!)
    console.log(`[App COMPUTED isModelTableVisible] Checking:
      - activeMenu.value: ${activeMenu.value}
      - promptModeTable: ${store.promptModeTable}
      - isPickingForRegenGenModel: ${isPickingForRegenGenModel.value}
      - isPickingForRegenEmbedding: ${isPickingForRegenEmbedding.value} 
      - isPickingForParsing: ${isPickingForParsing.value}`);

    if (activeMenu.value === 'model') return true;
    if (activeMenu.value === 'prompt' && store.promptModeTable === 'model') return true;
    if (isPickingForRegenGenModel.value) return true; // “再生成”选择“生成”模型

    // (!! 关键修复 !!) 添加下面这一行
    if (isPickingForRegenEmbedding.value) return true; // “再生成”选择“嵌入”模型

    if (isPickingForParsing.value) return true; // “详情页”选择“嵌入”模型

    return false;
});

const knowledgeBaseHeaderMode = computed(() => {
  const isPicking = (isRegeneratePanelVisible.value && regeneratePanelMode.value !== 'config') ||
                      (isCreatePanelVisible.value && createPanelMode.value !== 'config');
    if (activeMenu.value === 'prompt' || isPicking) return 'search';
    return 'full';
});


const handleMenuSelect = (index) => {
  activeMenu.value = index;
  store.setSelectedKnowledgeBase(null); // 清除选择会触发 watcher
  modelStore.setSelectedModel(null);
  isCreatePanelVisible.value = false;
  isCreateModelPanelVisible.value = false;
  isRegeneratePanelVisible.value = false;
  regeneratePanelMode.value = 'config';
  createPanelMode.value = 'config';
  if (index === 'prompt') {
    store.setPromptModeTable('hidden');
    store.setPromptSelectedModel(null);
    store.setPromptSelection([]); // 清空多选
  }
};

const handleCreateKnowledgeBase = () => {
  store.setSelectedKnowledgeBase(null); // 清除选择会触发 watcher
  modelStore.setSelectedModel(null);
  isRegeneratePanelVisible.value = false;
  isCreateModelPanelVisible.value = false;
  isCreatePanelVisible.value = true;
};

const handleCreateModel = () => {
  store.setSelectedKnowledgeBase(null); // 清除选择会触发 watcher
  modelStore.setSelectedModel(null);
  isRegeneratePanelVisible.value = false;
  isCreatePanelVisible.value = false;
  isCreateModelPanelVisible.value = true;
};

const handleOpenRegenerate = () => {
  // store.setSelectedKnowledgeBase(null); // 打开再生时可能不需要清除 KB 选择
  modelStore.setSelectedModel(null);
  isCreatePanelVisible.value = false;
  isCreateModelPanelVisible.value = false;
  isRegeneratePanelVisible.value = true;
  handleRegeneratePanelModeChange('config');
};

const handleRegeneratePanelModeChange = (mode) => {
    regeneratePanelMode.value = mode;
    if (mode !== 'config') {
        // store.setSelectedKnowledgeBase(null); // 进入 picking 时可能不需要清除 KB
        modelStore.setSelectedModel(null);
    }
};

const handleKbPicked = () => {
  if (createPanelMode.value === 'kb-picking') handleCreatePanelModeChange('config');
  if (regeneratePanelMode.value === 'kb-picking') handleRegeneratePanelModeChange('config');
}

// 这个 handleParse 似乎没用到，可以考虑删除
const handleParse = () => { console.log('Parse KB triggered from App.vue'); };

watch(() => store.knowledgeBaseList, (newList) => {
  console.log(`[App] 知识库列表更新:`, newList.map(kb => ({
    id: kb.id,
    name: kb.name,
    type: kb.kbType,
    status: kb.status,
    parentId: kb.parentId,
    parsingStage: kb.parsingState?.stage
  })));
}, { deep: true });

// 添加选中的知识库变化调试
watch(() => store.selectedKnowledgeBase, (newKb, oldKb) => {
  console.log(`[App] 选中的知识库变化:`, {
    oldKb: oldKb ? { id: oldKb.id, name: oldKb.name } : null,
    newKb: newKb ? { 
      id: newKb.id, 
      name: newKb.name,
      type: newKb.kbType,
      status: newKb.status,
      parsingStage: newKb.parsingState?.stage
    } : null
  });
}, { deep: true });

</script>
<style>
/* --- 全局与基础样式 --- */
body,
#app {
  height: 100vh;
  margin: 0;
}

.main-layout {
  height: 100%;
}

.el-aside {
  display: flex;
  flex-direction: column;
  border-right: 1px solid #e6e6e6;
}

.el-menu {
  flex-grow: 1;
  border-right: none;
}

.avatar-footer {
  padding: 20px;
  border-top: 1px solid #e6e6e6;
  display: flex;
  align-items: center;
}

.avatar-footer .user-info {
  margin-left: 10px;
  display: flex;
  flex-direction: column;
}

/* --- 核心布局容器 --- */
.el-main {
  padding: 20px;
  display: flex;
  flex-direction: column;
  box-sizing: border-box;
  overflow: hidden;
}

.content-body {
  display: flex;
  gap: 20px;
  flex-grow: 1;
  width: 100%;
  min-width: 0;
  overflow: hidden;
}

/* --- Panel 基础与子元素填充样式 --- */
.create-panel-wrapper,
.composition-panel-wrapper,
.main-panel-wrapper,
.detail-panel-wrapper,
.regenerate-panel-wrapper {
  transition: flex-basis 0.4s ease-in-out, opacity 0.3s ease-in-out;
  flex-shrink: 1;
  flex-grow: 1;
  min-width: 0;
  min-height: 0; 
  overflow: hidden;
  height: 100%;
  display: flex;
  flex-direction: column;
  position: relative; /* <-- 这是关键修复！ */
}


.create-panel-wrapper > * ,
.composition-panel-wrapper > *,
.main-panel-wrapper > *,
.detail-panel-wrapper > *,
.regenerate-panel-wrapper > * {
  flex: 1; 
  min-width: 0; 
  min-height: 0;
}

/* --- 动态布局规则 --- */

/* 默认布局: 只显示主面板 */
.main-panel-wrapper {
  flex-basis: 100%;
  opacity: 1;
}
.create-panel-wrapper,
.composition-panel-wrapper,
.detail-panel-wrapper,
.regenerate-panel-wrapper {
  flex-basis: 0;
  opacity: 0;
}

/* 状态1: 详情页打开 (主面板/详情面板) */
.detail-is-open {
  & .main-panel-wrapper {
    flex-basis: calc(60% - 10px);
  }
  & .detail-panel-wrapper {
    flex-basis: calc(40% - 10px);
    opacity: 1;
  }
}

.is-prompt-mode {
  /* (!! 修正 !!) 默认状态：PromptEditor 占 100% */
  & .composition-panel-wrapper {
    flex-basis: 100%;
    opacity: 1;
  }
  & .main-panel-wrapper {
    flex-basis: 0;
    opacity: 0; /* 确保它默认不占空间 */
  }
  
  /* (!! 移除 !!) 下面这个规则不再需要，因为它与默认状态冲突 */
  /* & > *:not(.composition-panel-wrapper):not(.main-panel-wrapper) {
    flex-basis: 0;
    opacity: 0;
  } */
}
/* (!! 新增 !!) Prompt 模式下，当表格需要打开时的 70/30 布局 */
.is-prompt-mode.prompt-table-is-open {
  & .composition-panel-wrapper {
    flex-basis: calc(60% - 10px);
  }
  & .main-panel-wrapper {
    flex-basis: calc(40% - 10px);
    opacity: 1; /* 确保 main-panel 可见 */
  }
}
/* 状态3: 创建面板打开 (创建面板/主面板) */
.create-panel-is-open {
  & .create-panel-wrapper {
    flex-basis: calc(50% - 10px);
    opacity: 1;
  }
  & .main-panel-wrapper {
    flex-basis: calc(50% - 10px);
  }
  & > *:not(.create-panel-wrapper):not(.main-panel-wrapper) {
    flex-basis: 0;
    opacity: 0;
  }
}

/* 状态4: 再生成面板打开 (多种子状态) */
.regenerate-panel-is-open {
  & .composition-panel-wrapper,
  & .create-panel-wrapper {
    flex-basis: 0;
    opacity: 0;
  }

  &:not(.is-picking-mode):not(.detail-is-open) {
    & .main-panel-wrapper {
      flex-basis: calc(50% - 10px);
    }
    & .regenerate-panel-wrapper {
      flex-basis: calc(50% - 10px);
      opacity: 1;
    }
    & .detail-panel-wrapper { 
      flex-basis: 0;
      opacity: 0;
    }
  }
}

/* 状态5: Picking 模式 (主面板/再生成面板) */
.is-picking-mode {
  & .main-panel-wrapper {
    flex-basis: calc(60% - 10px);
  }
  & .regenerate-panel-wrapper {
    flex-basis: calc(40% - 10px);
    opacity: 1;
  }
  & > *:not(.main-panel-wrapper):not(.regenerate-panel-wrapper):not(.create-panel-wrapper) {
    flex-basis: 0;
    opacity: 0;
  }
}

/* 解析时选择模型的特定布局 */
.is-parsing-picking-mode.detail-is-open {
  & .main-panel-wrapper {
    flex-basis: calc(60% - 10px);
  }
  & .detail-panel-wrapper {
    flex-basis: calc(40% - 10px);
  }
}


/* --- Main Panel 内部表格切换 --- */

.main-panel-wrapper .table-wrapper-knowledge,
.main-panel-wrapper .table-wrapper-model {
  overflow: hidden;
  flex-shrink: 1;
  transition: flex-basis 0.4s ease-in-out,
              opacity 0.2s ease-in-out;
}

.main-panel-wrapper .table-wrapper-knowledge {
  flex-basis: 100%;
  opacity: 1;
  transition-delay: 0s, 0.1s;
}

.main-panel-wrapper .table-wrapper-model {
  flex-basis: 0;
  opacity: 0;
  transition-delay: 0s, 0s;
}

.main-panel-wrapper.show-model-table .table-wrapper-knowledge {
  flex-basis: 0;
  opacity: 0;
  transition-delay: 0s, 0s;
}

.main-panel-wrapper.show-model-table .table-wrapper-model {
  flex-basis: 100%;
  opacity: 1;
  transition-delay: 0s, 0.1s;
}

.main-panel-wrapper {
    display: flex;
    flex-direction: row;
}

.slide-fade-enter-active {
  transition: all 0.3s ease-out;
}
.slide-fade-leave-active {
  transition: all 0.3s cubic-bezier(1, 0.5, 0.8, 1);
}
.slide-fade-enter-from,
.slide-fade-leave-to {
  transform: translateX(20px);
  opacity: 0;
}
</style>

