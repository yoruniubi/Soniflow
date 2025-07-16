<template>
  <v-text-field
    :model-value="modelValue"
    :label="label"
    readonly
    density="compact"
    variant="outlined"
    append-inner-icon="mdi-folder-open"
    @click:append-inner="openDirectoryDialog"
    append-outer-icon="mdi-folder-search-outline"
    @click:append-outer="openNativeDirectoryDialog"
  ></v-text-field>

  <v-dialog v-model="dialog" max-width="800px" persistent>
    <v-card>
      <v-card-title class="d-flex align-center pa-4">
        <span class="text-h6">{{ t('directoryInput.selectDirectory') }}</span>
        <v-spacer></v-spacer>
        <v-select
          :items="availableDrives"
          :model-value="currentDrive"
          @update:model-value="onDriveChange"
          :label="t('r')"
          density="compact"
          hide-details
          variant="outlined"
          style="max-width: 150px;"
          class="ml-4"
        ></v-select>
      </v-card-title>
      
      <v-divider></v-divider>
      <v-card-subtitle class="pa-3 bg-grey-lighten-4 text-truncate">
        {{ currentPath }}
      </v-card-subtitle>
      
      <v-card-text style="height: 400px; overflow-y: auto;">
        <div v-if="loading" class="d-flex justify-center align-center fill-height">
          <v-progress-circular indeterminate color="primary"></v-progress-circular>
        </div>
        
        <v-list v-else dense nav>
          <v-list-item @click="goUpDirectory" :disabled="!canGoUp">
            <template v-slot:prepend><v-icon>mdi-arrow-up-bold-box-outline</v-icon></template>
            <v-list-item-title class="font-weight-bold">{{ t('directoryInput.goUp') }}</v-list-item-title>
          </v-list-item>

          <v-list-item
            v-for="item in currentDirectoryItems"
            :key="item.path"
            @click="selectItem(item)"
          >
            <template v-slot:prepend>
              <v-icon :color="item.is_dir ? 'amber' : 'grey-lighten-1'">
                {{ item.is_dir ? 'mdi-folder' : 'mdi-file-outline' }}
              </v-icon>
            </template>
            <v-list-item-title>{{ item.name }}</v-list-item-title>
          </v-list-item>
        </v-list>
        
        <v-alert v-if="error" type="error" dense class="mt-4">{{ error }}</v-alert>
      </v-card-text>
      
      <v-divider></v-divider>
      <v-card-actions class="pa-3">
        <v-spacer></v-spacer>
        <v-btn text @click="dialog = false">{{ t('directoryInput.cancel') }}</v-btn>
        <v-btn color="primary" variant="flat" @click="selectCurrentDirectory">{{ t('directoryInput.select') }}</v-btn>
      </v-card-actions>
    </v-card>
  </v-dialog>
</template>

<script setup>
import { ref, computed, watch } from 'vue';
import { useI18n } from 'vue-i18n';

const props = defineProps({ modelValue: String, label: String });
const emit = defineEmits(['update:modelValue']);

const { t } = useI18n();

const dialog = ref(false);
const loading = ref(false);
const currentPath = ref('');
const currentDirectoryItems = ref([]);
const error = ref(null);
const canGoUp = ref(false);
const availableDrives = ref([]);

const currentDrive = computed(() => {
  if (!currentPath.value) return null;
  // 后端返回的盘符应为 'C:\\', 'D:\\' 等格式
  const drive = availableDrives.value.find(d => currentPath.value.startsWith(d));
  return drive || (currentPath.value === '/' ? '/' : null);
});


const openNativeDirectoryDialog = async () => { /* ... 保持不变 ... */ };

const openDirectoryDialog = async () => {
  dialog.value = true;
  error.value = null;
  loading.value = true;

  try {
    // 总是先获取最新的盘符列表
    const driveResponse = await pywebview.api.get_drives();
    if (driveResponse.success) {
      availableDrives.value = driveResponse.drives;
    }

    // 确定初始路径：优先使用props传来的值，其次是CWD，最后是第一个盘符
    let initialPath = props.modelValue;
    if (!initialPath) {
      const cwdResponse = await pywebview.api.get_cwd();
      initialPath = cwdResponse.success ? cwdResponse.path : availableDrives.value[0];
    }
    
    await listDirectory(initialPath);

  } catch (e) {
    error.value = t('directoryInput.failedToInitialize', { message: e.message });
    console.error(e);
  } finally {
    loading.value = false;
  }
};

const listDirectory = async (path) => {
  if (!path) return;
  loading.value = true;
  error.value = null;
  try {
    const response = await pywebview.api.list_directory(path);
    if (response.success) {
      currentPath.value = response.path;
      currentDirectoryItems.value = response.items.filter(item => item.is_dir);
      
      // 让后端判断是否可以返回上一级
      const parentResponse = await pywebview.api.get_parent_directory(response.path);
      canGoUp.value = parentResponse.success && parentResponse.path !== response.path;
      } else {
        error.value = response.error;
      }
  } catch (e) {
    error.value = t('directoryInput.errorAccessingDirectory', { message: e.message });
  } finally {
    loading.value = false;
  }
};

const selectItem = (item) => {
  if (item.is_dir) listDirectory(item.path);
};

const goUpDirectory = async () => {
  if (!canGoUp.value) return;
  const response = await pywebview.api.get_parent_directory(currentPath.value);
  if (response.success) listDirectory(response.path);
};

// **核心修改 2: onDriveChange 只负责导航**
const onDriveChange = (newDrive) => {
  // 不再需要 watch(selectedDrive)，因为 v-select 的 model-value 绑定到了
  // `currentDrive` (计算属性)，而我们通过 @update:model-value 直接处理切换事件。
  if (newDrive && newDrive !== currentDrive.value) {
    listDirectory(newDrive);
  }
};

const selectCurrentDirectory = () => {
  emit('update:modelValue', currentPath.value);
  dialog.value = false;
};

// **核心修改 3: 移除 watch(selectedDrive)**
// 这个监听器是导致状态混乱的根源，现在不再需要它。
watch(() => props.modelValue, (newValue) => {
  if (newValue && newValue !== currentPath.value) {
    // 当外部路径变化时，也应该刷新当前视图
    listDirectory(newValue);
  }
});

</script>

<style scoped>
.v-list-item-icon {
  margin-right: 16px;
}
</style>
