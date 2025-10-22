import { defineStore } from 'pinia'
import { ref, computed } from 'vue'

const API_BASE_URL = '/api/v1'

// (新增) 健壮的响应处理程序
async function handleResponse(response) {
  if (response.ok) {
    const text = await response.text();
    return text ? JSON.parse(text) : null;
  }
  let errorMsg = `HTTP Error ${response.status}: ${response.statusText}`;
  try {
    const errData = await response.json();
    errorMsg = errData.detail || JSON.stringify(errData);
  } catch (e) { /* 响应体不是 JSON */ }
  throw new Error(errorMsg);
}

export const useModelStore = defineStore('model', () => {
  const modelList = ref([]);
  const selectedModel = ref(null);
  const searchTerm = ref('');
  const isLoading = ref(false);
  const error = ref(null);

  const filteredModelList = computed(() => {
    if (!searchTerm.value) {
      return modelList.value;
    }
    return modelList.value.filter(model =>
      model.name.toLowerCase().includes(searchTerm.value.toLowerCase())
    );
  });

  async function fetchModels() {
    isLoading.value = true;
    error.value = null;
    try {
      const response = await fetch(`${API_BASE_URL}/models`);
      modelList.value = await handleResponse(response);
    } catch (err) {
      error.value = err.message;
    } finally {
      isLoading.value = false;
    }
  }

  function setSelectedModel(model) {
    selectedModel.value = model;
  }

  async function deleteModel(id) {
    error.value = null;
    try {
      const response = await fetch(`${API_BASE_URL}/models/${id}`, {
        method: 'DELETE',
      });
      await handleResponse(response); // 会处理 204 No Content
      
      modelList.value = modelList.value.filter(model => model.id !== id);
      if (selectedModel.value && selectedModel.value.id === id) {
        selectedModel.value = null;
      }
    } catch (err) {
      error.value = err.message;
      throw err; // (关键) 重新抛出错误，以便 UI catch
    }
  }

  async function updateModel(updatedModel) {
    error.value = null;
    try {
      const response = await fetch(`${API_BASE_URL}/models/${updatedModel.id}`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(updatedModel),
      });
      const modelFromServer = await handleResponse(response);

      // (修正) 更新本地 state
      const index = modelList.value.findIndex(model => model.id === modelFromServer.id);
      if (index !== -1) {
        modelList.value[index] = modelFromServer;
      }
      if (selectedModel.value && selectedModel.value.id === modelFromServer.id) {
        selectedModel.value = modelFromServer;
      }
    } catch (err) {
      error.value = err.message;
      throw err; // (关键) 重新抛出错误
    }
  }
  
  async function addModel(newModel) {
    error.value = null;
    try {
      const response = await fetch(`${API_BASE_URL}/models`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(newModel),
      });
      const addedModel = await handleResponse(response);
      
      modelList.value.push(addedModel);
    } catch (err) {
      error.value = err.message;
      throw err; // (关键) 重新抛出错误
    }
  }

  return {
    modelList, selectedModel, searchTerm,
    isLoading, error,
    filteredModelList,
    fetchModels,
    setSelectedModel, deleteModel, updateModel, addModel
  }
})