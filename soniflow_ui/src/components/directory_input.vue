<template>
  <v-text-field
    :model-value="modelValue"
    :label="label"
    readonly
    density="compact"
    variant="outlined"
    append-inner-icon="mdi-folder-open"
    @click:append-inner="openDirectoryDialog"
  ></v-text-field>

  <v-dialog v-model="dialog" max-width="600px">
    <v-card>
      <v-card-title class="text-h6">{{ t('directoryInput.selectDirectory') }}</v-card-title>
      <v-card-text>
        <v-list dense>
          <v-list-item @click="goUpDirectory" :disabled="!canGoUp">
            <v-list-item-icon>
              <v-icon>mdi-arrow-up-bold-box-outline</v-icon>
            </v-list-item-icon>
            <v-list-item-title>..</v-list-item-title>
          </v-list-item>
          <v-list-item
            v-for="item in currentDirectoryItems"
            :key="item.path"
            @click="selectItem(item)"
          >
            <v-list-item-icon>
              <v-icon>{{ item.is_dir ? 'mdi-folder' : 'mdi-file' }}</v-icon>
            </v-list-item-icon>
            <v-list-item-title>{{ item.name }}</v-list-item-title>
          </v-list-item>
        </v-list>
        <v-alert v-if="error" type="error" dense dismissible class="mt-4">{{ error }}</v-alert>
      </v-card-text>
      <v-card-actions>
        <v-spacer></v-spacer>
        <v-btn color="blue-darken-1" text @click="dialog = false">{{ t('directoryInput.cancel') }}</v-btn>
        <v-btn color="blue-darken-1" text @click="selectCurrentDirectory">{{ t('directoryInput.select') }}</v-btn>
      </v-card-actions>
    </v-card>
  </v-dialog>
</template>

<script setup>
import { ref, onMounted, watch } from 'vue';
import { useI18n } from 'vue-i18n';

const props = defineProps({
  modelValue: String,
  label: String,
});

const emit = defineEmits(['update:modelValue']);

const { t } = useI18n();

const dialog = ref(false);
const currentPath = ref('');
const currentDirectoryItems = ref([]);
const error = ref(null);
const canGoUp = ref(false);

const openDirectoryDialog = async () => {
  dialog.value = true;
  error.value = null;
  if (!currentPath.value) {
    // Try to get current working directory from backend if not set
    try {
      const response = await pywebview.api.get_cwd();
      if (response.success) {
        currentPath.value = response.path;
      } else {
        console.error(t('directoryInput.failedToLoadDirectory', { error: response.error }));
        currentPath.value = ''; // Fallback to empty, will load user home
      }
    } catch (e) {
      console.error(t('directoryInput.errorAccessingDirectory', { message: e.message }));
      currentPath.value = ''; // Fallback to empty
    }
  }
  await listDirectory(currentPath.value);
};

const listDirectory = async (path) => {
  try {
    const response = await pywebview.api.list_directory(path);
    if (response.success) {
      currentPath.value = response.path;
      currentDirectoryItems.value = response.items.filter(item => item.is_dir); // Only show directories
      error.value = null;

      // Determine if "go up" is possible
      const effectivePathSeparator = pywebview.api.path_separator || '/'; // Use '/' as a fallback
      if (effectivePathSeparator === '/') { // Unix-like paths
        canGoUp.value = response.path !== '/';
      } else { // Windows paths
        // Check if the path is a root drive (e.g., "C:\")
        const isRootDrive = /^[A-Za-z]:\\?$/.test(response.path);
        canGoUp.value = !isRootDrive;
      }
    } else {
      error.value = `${t('directoryInput.failedToLoadDirectory', { error: response.error })}`;
      currentDirectoryItems.value = [];
      canGoUp.value = false;
    }
  } catch (e) {
    error.value = `${t('directoryInput.errorAccessingDirectory', { message: e.message })}`;
    currentDirectoryItems.value = [];
    canGoUp.value = false;
  }
};

const selectItem = async (item) => {
  if (item.is_dir) {
    await listDirectory(item.path);
  } else {
    error.value = t('directoryInput.selectFolderOnly');
  }
};

const goUpDirectory = async () => {
  if (currentPath.value) { // Removed api.path_separator check here, as it's handled by effectivePathSeparator
    const effectivePathSeparator = pywebview.api.path_separator || '/'; // Use '/' as a fallback
    let parentPath;
    if (effectivePathSeparator === '/') { // Unix-like paths
      parentPath = currentPath.value.substring(0, currentPath.value.lastIndexOf('/')) || '/';
    } else { // Windows paths
      const lastSeparatorIndex = currentPath.value.lastIndexOf(effectivePathSeparator);
      if (lastSeparatorIndex > -1) {
        parentPath = currentPath.value.substring(0, lastSeparatorIndex);
      } else {
        parentPath = currentPath.value; // Fallback, should be handled by canGoUp
      }

      // Special handling for Windows drive roots (e.g., "C:" should become "C:\")
      if (parentPath.match(/^[A-Za-z]:$/)) {
        parentPath += effectivePathSeparator;
      }
    }
    await listDirectory(parentPath);
  }
};

const selectCurrentDirectory = () => {
  emit('update:modelValue', currentPath.value);
  dialog.value = false;
};

// Initialize with modelValue if provided
onMounted(() => {
  if (props.modelValue) {
    currentPath.value = props.modelValue;
  }
});

// Watch for external changes to modelValue
watch(() => props.modelValue, (newValue) => {
  if (newValue !== currentPath.value) {
    currentPath.value = newValue;
  }
});
</script>

<style scoped>
.v-list-item-icon {
  margin-right: 16px;
}
</style>
