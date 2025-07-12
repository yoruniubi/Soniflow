<template>
  <div class="setting-page pa-4">
    <v-card elevation="2" :title="t('settings.title')" prepend-icon="mdi-cog">
      <v-card-text>
        <v-form>
          <v-card elevation="0" class="mb-4">
            <!-- <v-card-title class="text-h6 pa-0">General Settings</v-card-title> -->
            <v-card-text class="pa-0">
              <v-select
                v-model="selectedLanguage"
                :items="languages"
                item-title="text"
                item-value="value"
                :label="t('settings.interfaceLanguage')"
                outlined
                class="mb-4"
                @update:model-value="changeLanguage"
              ></v-select>

              <directory-input
                v-model="defaultOutputDirectory"
                :label="t('settings.defaultOutput')"
                @update:model-value="updateDefaultOutput"
                outlined
                class="mb-4"
              />
            </v-card-text>
          </v-card>

          <v-card elevation="0" class="mb-4">
            <!-- <v-card-title class="text-h6 pa-0">Cookies</v-card-title> -->
            <v-card-text class="pa-0">
              <v-textarea
                v-model="bilibiliCookies"
                :label="t('settings.bilicookies')"
                rows="2"
                outlined
                clearable
                class="mb-4"
                @update:model-value="saveSettings"
                placeholder="e.g., SESSDATA=your_data; DedeUserID=your_id;"
                density="compact"
                persistent-placeholder
              ></v-textarea>
              <v-textarea
                v-model="youtubeCookies"
                :label="t('settings.youtubecookies')"
                rows="2"
                outlined
                clearable
                class="mb-4"
                @update:model-value="saveSettings"
                placeholder="e.g., YSC=your_data; PREF=your_pref;"
                density="compact"
                persistent-placeholder
              ></v-textarea>
            </v-card-text>
          </v-card>
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

<script setup>
import { ref, onMounted } from 'vue';
import { useI18n } from 'vue-i18n';
import DirectoryInput from '@/components/directory_input.vue';
import UserSnack from '@/components/user_snack.vue'; // Import UserSnack

const { t, locale } = useI18n();
const api = window.pywebview.api;

const snackMessages = ref([]);
let messageId = 0;

const defaultOutputDirectory = ref('');
const bilibiliCookies = ref('');
const youtubeCookies = ref('');
const autoUpdate = ref(false);
const selectedLanguage = ref('zh-CN'); // Default to Chinese

const loading = ref(false);

const languages = [
  { text: '简体中文', value: 'zh-CN' },
  { text: 'English', value: 'en-US' },
];

const showMessage = (type, message) => {
  const id = messageId++;
  snackMessages.value.push({ id, type, message, show: true, timeout: 3000 });
};

const loadSettings = async () => {
  try {
    const response = await api.get_settings();
    if (response.success) {
      const settings = response.settings;
      defaultOutputDirectory.value = settings.defaultOutput || '';
      bilibiliCookies.value = settings.bilibiliCookies || '';
      youtubeCookies.value = settings.youtubeCookies || '';
      autoUpdate.value = settings.autoUpdate || false;
      selectedLanguage.value = settings.language || 'zh-CN';
    } else {
      showMessage('error', `Failed to load settings: ${response.error}`);
    }
  } catch (error) {
    showMessage('error', `Error loading settings: ${error.message}`);
  }
};

const saveSettings = async () => {
  loading.value = true;
  try {
    const settingsToSave = {
      defaultOutput: defaultOutputDirectory.value,
      bilibiliCookies: bilibiliCookies.value,
      youtubeCookies: youtubeCookies.value,
      autoUpdate: autoUpdate.value,
      language: selectedLanguage.value,
    };
    const response = await api.save_app_settings(settingsToSave);
    if (response.success) {
      showMessage('success', t('settings.saveSuccess'));
    } else {
      showMessage('error', `${t('settings.saveFailed')}: ${response.error}`);
    }
  } catch (error) {
    showMessage('error', `${t('settings.saveFailed')}: ${error.message}`);
  } finally {
    loading.value = false;
  }
};

const changeLanguage = (newLang) => {
  locale.value = newLang;
  // Save language immediately
  saveSettings();
};

const updateDefaultOutput = (newPath) => {
  defaultOutputDirectory.value = newPath;
  saveSettings(); // Save settings when directory changes
};

onMounted(() => {
  loadSettings();
});
</script>

<style scoped>
/* Add any specific styles for this page here */
</style>
