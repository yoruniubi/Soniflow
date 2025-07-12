<script setup>
import { ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'; // Import useI18n
import UserSnack from '@/components/user_snack.vue'
import MyFileInput from '@/components/file_upload.vue' // Assuming file_upload.vue is still MyFileInput

const { t } = useI18n(); // Initialize useI18n

const snackMessages = ref([])
const whether_video = ref(false)
const showFormatSelect = ref(false)
const inputFile = ref(null)
const outputFormat = ref('')
const isConverting = ref(false) // New state for conversion status
let messageId = 0;

const showMessage = (type, message) => {
  const id = messageId++;
  snackMessages.value.push({ id, type, message, show: true });
};
const audioFormatOptions = ['MP3', 'WAV', 'OGG'];
const videoFormatOptions = ['MP4', 'AVI', 'MKV'];
const allFormatOptions = [...audioFormatOptions, ...videoFormatOptions];

watch(inputFile, (newValue) => {
  checkFileType(newValue);
});

const convertFile = async () => {
  if (!inputFile.value || !inputFile.value.name) {
    showMessage('warning', t('formatConvert.selectInputFileWarning'));
    return;
  }
  if (!outputFormat.value) {
    showMessage('warning', t('formatConvert.selectOutputFormatWarning'));
    return;
  }

  isConverting.value = true; // Set converting state to true

  try {
    // 1. Read the file as base64 and upload to the backend
    showMessage('info', t('formatConvert.uploadingFile'));
    
    const file = inputFile.value;
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
      showMessage('error', t('formatConvert.fileUploadFailed', { error: uploadResult.error }));
      return;
    }
    showMessage('success', t('formatConvert.fileUploadSuccessAndConverting'));

    // 2. Call form_transformation with the path returned by the backend
    const result = await pywebview.api.form_transformation(
      { path: uploadResult.path }, // Pass the full path returned by the backend
      outputFormat.value
    );

    if (result.success) {
      showMessage('success', result.message);
    } else {
      showMessage('error', `${t('formatConvert.conversionFailed', { error: result.error || t('formatConvert.unknownError') })}`);
    }
  } catch (error) {
    showMessage('error', `${t('formatConvert.unknownError')}: ${error.message}`);
  } finally {
    isConverting.value = false; // Reset converting state
  }
};

const checkFileType = (file) => {
  if (file && file.name) {
    const name = file.name;
    whether_video.value = name.toLowerCase().endsWith('.mp4') || name.toLowerCase().endsWith('.avi') || name.toLowerCase().endsWith('.mkv');
    showFormatSelect.value = true;
    outputFormat.value = whether_video.value ? videoFormatOptions[0] : audioFormatOptions[0]; // Default to first video or audio format
  } else {
    whether_video.value = false;
    showFormatSelect.value = false;
    outputFormat.value = '';
  }
}

</script>
<template>
  <div class="format-convert-page pa-4">
    <v-card elevation="2" :title="t('formatConvert.title')" prepend-icon="mdi-swap-horizontal">
      <v-card-text>
        <v-form>
          <MyFileInput
            v-model="inputFile"
            :label="t('formatConvert.inputFileLabel')"
            :button-text="t('fileUpload.buttonText')"
            prepend-icon="mdi-file"
            outlined
            class="mb-4"
          ></MyFileInput>

          <v-select
            v-if="showFormatSelect"
            v-model="outputFormat"
            :items="whether_video ? allFormatOptions : audioFormatOptions"
            :label="whether_video ? t('formatConvert.outputFormatVideoLabel') : t('formatConvert.outputFormatAudioLabel')"
            :prepend-icon="whether_video ? 'mdi-video' : 'mdi-format-list-bulleted-type'"
            outlined
            class="mb-4"
          ></v-select>
          <v-btn color="primary" @click="convertFile" :disabled="isConverting">
            {{ isConverting ? t('formatConvert.processing') : t('formatConvert.convertButton') }}
          </v-btn>
        </v-form>
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
<style scoped>
/* Add any specific styles for this page here */
</style>
