<script setup>
import { ref, computed } from 'vue' // Import computed and onMounted
import { useI18n } from 'vue-i18n'

const { t } = useI18n()

// onMounted(async () => {
//   // if (window.pywebview && window.pywebview.api && window.pywebview.api.get_settings) {
//     try {
//       const response = await pywebview.api.get_settings();
//       if (response.success) {
//         const savedLanguage = response.settings.language || 'zh-CN';
//         locale.value = savedLanguage;
//       }
//     } catch (error) {
//       console.error('Failed to fetch settings in App.vue:', error);
//     }
//   });


const isDrawerOpen = ref(true)
const primary = ref('000000')
const appVersion = '1.0.0' // Define app version here

const items = computed(() => [ // Make items a computed property
  { text: t('app.videoSearch'), icon: 'mdi-magnify', route: '/' },
  { text: t('app.formatConvert'), icon: 'mdi-swap-horizontal', route: '/format_convert' },
  { text: t('app.vocalSeparation'), icon: 'mdi-music-note-off', route: '/spleeter_part' },
  { text: t('app.audioEditing'), icon: 'mdi-pencil', route: '/audio_editor' },
  { text: t('app.settings'), icon: 'mdi-cog', route: '/setting_page' },
  // { text: t('app.test'), icon: 'mdi-test-tube', route: '/test' },
]);
</script>

<template>
  <v-app>
    <v-app-bar color="primary">
      <v-app-bar-nav-icon @click="isDrawerOpen = !isDrawerOpen"></v-app-bar-nav-icon>
      <v-app-bar-title>Soniflow</v-app-bar-title>
    </v-app-bar>

    <v-navigation-drawer
      v-model="isDrawerOpen"
      :permanent="isDrawerOpen"
      :temporary="false"
      app
      color="grey-lighten-3"
      width="240"
    >
      <v-list density="compact" nav>
        <v-list-subheader>{{ t('app.navigationHeader') }}</v-list-subheader>

        <v-list-item
          v-for="(item, i) in items"
          :key="i"
          :value="item"
          color="primary"
          :to="item.route"
          :base-color="primary"
        >
          <template v-slot:prepend>
            <v-icon :icon="item.icon"></v-icon>
          </template>

          <v-list-item-title v-text="item.text"></v-list-item-title>
        </v-list-item>
      </v-list>

      <template v-slot:append>
        <div class="pa-2 text-caption text-grey">
          {{ t('app.currentVersion', { version: appVersion }) }}
        </div>
      </template>
    </v-navigation-drawer>

    <v-main>
      <router-view />
    </v-main>
  </v-app>
</template>

<style>
.v-navigation-drawer__content {
  display: flex;
  flex-direction: column;
  justify-content: space-between;
}
.v-list-subheader__text {
  font-weight: bold;
  color: #151515;
  gap: 0.5rem;
}
.v-list-item--active {
  background-color: rgba(25, 118, 210, 0.15);
  border-right: 3px solid #1976d2;
}
.v-list-item{
  box-shadow: #151515;
}
</style>
