<!-- MyFileInput.vue -->
<template>
  <div class="file-input-wrapper">
    <div class="input-container">
      <v-icon class="file-icon" :icon="icon"></v-icon>
      <input
        ref="fileInput"
        type="file"
        :accept="accept"
        class="hidden-input"
        @change="handleFileChange"
      />
      <v-btn
        color="primary"
        variant="outlined"
        @click="triggerFileInput"
      >
        {{ buttonText }}
      </v-btn>
    </div>

    <div v-if="selectedFile" class="file-preview">
      <span class="file-name">{{ selectedFile.name }}</span>
      <v-btn
        icon="mdi-close"
        variant="text"
        size="small"
        @click="clearFile"
      ></v-btn>
    </div>

    <div class="caption-text">{{ label }}</div>
  </div>
</template>

<script setup>
import { ref, watch } from 'vue'

const props = defineProps({
  modelValue: File,
  accept: {
    type: String,
    default: ''
  },
  buttonText: {
    type: String,
    default: '选择文件' // Revert to hardcoded default
  },
  label: {
    type: String,
    default: '支持格式：MP3/WAV/OGG' // Revert to hardcoded default
  },
  icon: {
    type: String,
    default: 'mdi-paperclip'
  }
})

const emit = defineEmits(['update:modelValue'])

const fileInput = ref(null)
const selectedFile = ref(null)

watch(() => props.modelValue, (newVal) => {
  selectedFile.value = newVal
})

const triggerFileInput = () => {
  fileInput.value.click()
}

const handleFileChange = (event) => {
  const file = event.target.files[0]
  if (file) {
    selectedFile.value = file
    emit('update:modelValue', file) // 替换原有的 'file-selected'
  }
}
const clearFile = () => {
  selectedFile.value = null
  fileInput.value.value = ''
  emit('update:modelValue', null)
}
</script>

<style scoped>
.file-input-wrapper {
  border: 1px solid rgba(0, 0, 0, 0.12);
  border-radius: 4px;
  padding: 12px;
}

.input-container {
  display: flex;
  align-items: center;
  gap: 12px;
}

.hidden-input {
  display: none;
}

.file-preview {
  margin-top: 8px;
  display: flex;
  align-items: center;
  gap: 8px;
}

.file-name {
  font-size: 0.875rem;
}

.caption-text {
  font-size: 0.75rem;
  margin-top: 4px;
}
</style>
