<template>
  <div class="spleeter-part-page pa-4">
    <v-card elevation="2" :title="t('app.vocalSeparation')" prepend-icon="mdi-music-note-off">
      <v-card-text>
        <v-form>
          <MyFileInput
            v-model="selectedFile"
            :label="t('spleeter.selectAudioFileButton')"
            :button-text="t('fileUpload.buttonText')"
            prepend-icon="mdi-file"
            outlined
            class="mb-4"
          ></MyFileInput>

          <v-card elevation="0" class="mb-4">
            <v-card-title class="text-h6 pa-0">{{ t('spleeter.separationModeLabel') }}</v-card-title>
            <v-card-text class="pa-0">
              <v-radio-group v-model="separationMode" row class="mt-2">
                <v-radio :label="t('spleeter.model2Stems')" value="2"></v-radio>
                <v-radio :label="t('spleeter.model4Stems')" value="4"></v-radio>
                <v-radio :label="t('spleeter.model5Stems')" value="5"></v-radio>
              </v-radio-group>
            </v-card-text>
          </v-card>

          <v-select
            v-model="outputFormat"
            :items="outputFormats"
            :label="t('spleeter.outputFormatLabel')"
            prepend-icon="mdi-format-list-bulleted-type"
            outlined
            class="mb-4"
          ></v-select>
          <v-select
            v-model="audioQuality"
            :items="audioQualities"
            :label="t('spleeter.audioQualityLabel')"
            prepend-icon="mdi-quality-high"
            outlined
            class="mb-4"
          ></v-select>

          <!-- <directory-input
            v-model="outputDirectory"
            :label="t('spleeter.outputDirectoryLabel')"
            @update:model-value="updateOutputDirectory"
            prepend-icon="mdi-folder"
            outlined
            class="mb-4"
          /> -->

          <v-btn color="primary" @click="startSeparation" :disabled="loading">
            {{ loading ? t('spleeter.processing') : t('spleeter.startSeparation') }}
          </v-btn>
        </v-form>
      </v-card-text>
    </v-card>

    <v-card v-if="outputFiles.length > 0" elevation="2" :title="t('spleeter.outputResults')" prepend-icon="mdi-folder-open" class="mt-4">
      <v-card-text>
        <v-list>
          <v-list-item v-for="file in outputFiles" :key="file.path">
            <v-list-item-content>
              <v-list-item-title>{{ file.name }}</v-list-item-title>
              <v-list-item-subtitle>
                {{ t('spleeter.fileSize') }}: {{ formatBytes(file.size) }}
              </v-list-item-subtitle>
            </v-list-item-content>
            <v-list-item-action>
              <v-btn icon @click="downloadFile(file.path)">
                <v-icon>mdi-download</v-icon>
              </v-btn>
            </v-list-item-action>
          </v-list-item>
        </v-list>
      </v-card-text>
    </v-card>

    <UserSnack
      v-for="snack in snackMessages"
      :key="snack.id"
      v-model:show="snack.show"
      :color="snack.type"
      :message="snack.message"
      :timeout="snack.timeout"
      @update:show="val => { if (!val) snackMessages = snackMessages.filter(s => s.id !== snack.id) }"
    />
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue';
import { useI18n } from 'vue-i18n';
import MyFileInput from '@/components/file_upload.vue';
import UserSnack from '@/components/user_snack.vue';

const { t } = useI18n();
const api = window.pywebview.api;

const snackMessages = ref([]);
let messageId = 0;

const selectedFile = ref(null);
const separationMode = ref('2'); // Default to 2 stems
const outputFormat = ref('mp3');
const audioQuality = ref('320k');
const outputDirectory = ref('');
const loading = ref(false);
const outputFiles = ref([]);

const outputFormats = ['mp3', 'wav', 'ogg'];
const audioQualities = ['128k', '192k', '256k', '320k'];

const showMessage = (type, message) => {
  const id = messageId++;
  snackMessages.value.push({ id, type, message, show: true });
};

const updateOutputDirectory = (newPath) => {
  outputDirectory.value = newPath;
};

const formatBytes = (bytes, decimals = 2) => {
  if (bytes === 0) return t('spleeter.unknownSize');
  const k = 1024;
  const dm = decimals < 0 ? 0 : decimals;
  const sizes = ['Bytes', 'KB', 'MB', 'GB', 'TB'];
  const i = Math.floor(Math.log(bytes) / Math.log(k));
  return parseFloat((bytes / Math.pow(k, i)).toFixed(dm)) + ' ' + sizes[i];
};

const downloadFile = (filePath) => {
  console.log('Attempting to download:', filePath);
  showMessage('info', `Downloading: ${filePath}`);
};

const startSeparation = async () => {
  if (!selectedFile.value || !selectedFile.value.name) {
    showMessage('warning', t('spleeter.selectAudioFileWarning'));
    return;
  }

  loading.value = true;
  outputFiles.value = [];
  showMessage('info', t('spleeter.uploadingFile'));

  try {
    // 1. Read the file as base64 and upload to the backend
    const file = selectedFile.value;
    const reader = new FileReader();

    const uploadResult = await new Promise((resolve, reject) => {
      reader.onload = async (e) => {
        const base64_data = e.target.result.split(',')[1]; // Get base64 string
        try {
          const result = await pywebview.api.upload_file_stream({
            name: file.name,
            type: file.type,
            size: file.size,
            base64_data: base64_data
          });
          resolve(result);
        } catch (error) {
          reject(error);
        }
      };
      reader.onerror = (error) => {
        reject(new Error('FileReader error: ' + error.target.error));
      };
      reader.readAsDataURL(file);
    });

    if (!uploadResult.success) {
      showMessage('error', t('spleeter.uploadFailed', { error: uploadResult.error }));
      return;
    }
    showMessage('success', t('spleeter.uploadSuccessAndProcessing'));

    // 2. Call process_audio with the path returned by the backend
    const separationResponse = await api.process_audio(
      parseInt(separationMode.value),
      uploadResult.path,
      outputDirectory.value,
      outputFormat.value,
      audioQuality.value
    );

    if (separationResponse.success) {
      showMessage('success', t('spleeter.audioSeparationSuccess'));
      outputFiles.value = separationResponse.output_files;
    } else {
      showMessage('error', `${t('spleeter.processingFailed', { error: separationResponse.error || t('spleeter.unknownError') })}`);
    }
  } catch (error) {
    showMessage('error', `${t('spleeter.serverConnectionFailed')}: ${error.message}`);
  } finally {
    loading.value = false;
  }
};

onMounted(async () => {
  try {
    const response = await api.get_settings();
    if (response.success) {
      outputDirectory.value = response.settings.defaultOutput || '';
    } else {
      console.error('Failed to load default output directory:', response.error);
    }
  } catch (error) {
    console.error('Error calling get_settings API:', error);
  }
});
</script>

<style scoped>
/* Add any specific styles for this page here */
</style>
