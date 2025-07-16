<script setup>
import { watch } from 'vue'
import { markRaw } from 'vue'
import { shallowReactive } from 'vue'
import { ref, reactive } from 'vue'
import BiliIcon from '@/components/BiliIcon.vue'
import UserSnack from '@/components/user_snack.vue'
import { useI18n } from 'vue-i18n'

const { t } = useI18n()

const search_text = ref('')
const search_results = reactive([])
const selected_video = ref(null)
const platform = ref('bilibili') // 当前选中的平台
const loading = ref(false)
const error = ref(null)
const showPreviewDialog = ref(false); // 初始为关闭状态
const collectionVideos = ref([]); // 存储合集中的视频列表
const collectionTitle = ref(''); // 存储合集标题
const currentCollectionIndex = ref(-1); // 当前播放视频在合集中的索引
const currentPage = ref(1);
const totalPages = ref(1)
const itemsPerPage = 10 // 每页数量
// 引入自定义消息提示框
const snackMessages = ref([])
// the progress bar
const downloadingVideos = ref({})
let messageId = 0
const showMessage = (type, message, timeout = 3000) => {
  const id = messageId++
  snackMessages.value.push({ id, type, message, show: true, timeout })
}

// Function to fetch collection info
const fetchCollectionInfo = async (video) => {
  try {
    const result = await pywebview.api.whether_collection(video.bvid || video.id);
    if (!result) {
      return false;
    }
    return result.is_collection || false;
  } catch (err) {
    console.error('Failed to fetch collection info:', err);
    return false;
  }
};

// 平台选项配置
const platforms = shallowReactive({
  bilibili: {
    label: 'Bilibili',
    color: 'blue',
    icon: markRaw(BiliIcon) 
  },
  youtube: {
    label: 'YouTube',
    color: 'red',
    icon: 'mdi-youtube'
  }
})

const search_videos = async () => {
  if (!search_text.value.trim()) return
  
  loading.value = true
  error.value = null
  currentPage.value = 1 // 重置到第一页
  
  try {
    const result = await pywebview.api.search_videos(
      search_text.value.trim(),  // keyword 参数
      platform.value,             // platform 参数
      currentPage.value,
      itemsPerPage
    )
    // 搜索时就直接调用show_collection_info，获取collectionVideos
    
    // 统一不同平台的数据格式
    search_results.splice(0, search_results.length, ...await Promise.all(result.items.map(async item => {
      const is_collection = await fetchCollectionInfo({ bvid: item.bvid || item.id });
      console.log('is_collection:', is_collection);
      
      // Call show_collection_info for each video
      // await show_collection_info({ bvid: item.bvid || item.id });

      return {
        id: item.bvid || item.id,
        title: item.title,
        author: item.owner?.name || item.author || item.channel || '未知作者', // 适配B站字段
        cover: item.pic || item.cover || 'default_cover.jpg',
        duration: item.duration || 'N/A',
        url: item.url,
        platform: platform.value,
        is_collection: !!is_collection // Ensure is_collection is a boolean
      };
    })));
    totalPages.value = result.total_pages;
  } catch (err) {
    error.value = t('search.searchFailed', { error: err.message })
    console.error('搜索失败:', err)
    showMessage('error', t('search.searchFailed', { error: err.message }), 5000)
  } finally {
    loading.value = false
  }
}
// 添加翻页方法
const changePage = async (newPage) => {
  if (newPage < 1 || newPage > totalPages.value) return
  
  loading.value = true // Set loading to true
  error.value = null // Clear previous errors
  currentPage.value = newPage
  try {
    const result = await pywebview.api.search_videos(
      search_text.value.trim(),
      platform.value,
      currentPage.value,
      itemsPerPage
    )
    
    search_results.splice(0, search_results.length, ...await Promise.all(result.items.map(async item => {
      const is_collection = await fetchCollectionInfo({ url: item.url });
      return {
        id: item.bvid || item.id,
        title: item.title,
        author: item.owner?.name || item.author || item.channel || '未知作者', // 适配B站字段
        cover: item.pic || item.cover || item.thumbnail || 'default_cover.jpg',
        duration: item.duration || 'N/A',
        url: item.url,
        platform: platform.value,
        is_collection: !!is_collection
      };
    })));
  } catch (err) {
    error.value = t('search.paginationFailed', { error: err.message })
    console.error('翻页失败:', err)
    showMessage('error', t('search.paginationFailed', { error: err.message }), 5000)
  } finally {
    loading.value = false // Set loading to false
  }
}

const preview_video = async (video) => {
  try {
    let data = {};
    selected_video.value = { ...video }; // Set selected video early for context

    if (video.platform === 'bilibili') {
      const result = await pywebview.api.get_video_preview(video.id);
      if (result.error) {
        showMessage('error', result.error);
        return;
      }
      data = {
        ...video,
        ...result,
        embed_url: result.embed_url || `/proxy_video?url=${encodeURIComponent(result.direct_url)}`,
      };
    } else if (video.platform === 'youtube') {
      const youtube_video_id_match = video.url.match(/(?:https?:\/\/)?(?:www\.)?(?:youtube\.com|youtu\.be)\/(?:watch\?v=|embed\/|v\/|)([\w-]{11})/);
      let youtube_embed_url = null;
      if (youtube_video_id_match && youtube_video_id_match[1]) {
        youtube_embed_url = `https://www.youtube.com/embed/${youtube_video_id_match[1]}?autoplay=1`;
      }
      data = { ...video, embed_url: youtube_embed_url };
    } else {
      showMessage('warning', '该平台暂不支持预览。');
      return;
    }

    selected_video.value = { ...data };

    // Reset collection info before fetching
    collectionVideos.value = [];
    collectionTitle.value = '';
    currentCollectionIndex.value = -1;

    if (video.is_collection) {
      if (video.platform === 'bilibili') {
        // Bilibili collection logic remains the same
        const collectionCheckResult = await pywebview.api.whether_collection(video.id);
        if (collectionCheckResult?.is_collection) {
          const collectionResult = await pywebview.api.get_collection_videos(collectionCheckResult.owner_mid, collectionCheckResult.collection_id);
          if (collectionResult?.success) {
            collectionVideos.value = collectionResult.items;
            collectionTitle.value = collectionResult.meta?.name || t('search.collection');
            currentCollectionIndex.value = collectionVideos.value.findIndex(item => item.bvid === video.id);
          } else {
            showMessage('error', t('search.bilibiliCollectionFailed', { error: collectionResult?.error }));
          }
        }
      } else if (video.platform === 'youtube') {
        // YouTube playlist logic
        const playlist_info = await pywebview.api.check_if_playlist(video.url);
        if (playlist_info && playlist_info[0]) { // is_playlist is true
          collectionTitle.value = playlist_info[1]; // playlist_title
          // For YouTube, we don't have a list of videos in the preview,
          // so we can't show a list. We just need the title for the download dialog.
          // We can set a flag to show the playlist download button.
          selected_video.value.is_playlist = true;
          selected_video.value.playlist_title = playlist_info[1];
          selected_video.value.playlist_url = playlist_info[2];
        }
      }
    }
    
    showPreviewDialog.value = true;

  } catch (err) {
    console.error('预览失败:', err);
    showMessage('error', t('search.previewError'));
  }
};

const format_time = (seconds) => {
  if (typeof seconds !== 'number' || isNaN(seconds)) {
    return 'N/A';
  }
  const minutes = Math.floor(seconds / 60);
  const remainingSeconds = Math.floor(seconds % 60);
  return `${minutes}:${remainingSeconds < 10 ? '0' : ''}${remainingSeconds}`;
};


const download_youtube_playlist = async (playlist_url, playlist_title) => {
  const id = `playlist_${Date.now()}`;
  try {
    downloadingVideos.value[id] = {
      status: 'downloading',
      title: playlist_title,
      platform: 'youtube'
    };
    showMessage('info', t('search.downloadingPlaylist', { title: playlist_title }));
    
    const result = await pywebview.api.download_playlist(playlist_url);

    if (result && result.success) {
      downloadingVideos.value[id].status = 'success';
      showMessage('success', t('search.playlistDownloadComplete', { title: playlist_title }));
    } else {
      downloadingVideos.value[id].status = 'error';
      showMessage('error', t('search.playlistDownloadFailed', { error: result?.error || err.message }));
    }
  } catch (err) {
    downloadingVideos.value[id].status = 'error';
    showMessage('error', t('search.playlistDownloadFailed', { error: err.message }));
  } finally {
    setTimeout(() => {
      delete downloadingVideos.value[id];
    }, 3000);
  }
};

const download_video = async (video) => {
  const id = video.id || video.url;
  try {
    downloadingVideos.value[id] = {
      status: 'downloading',
      title: video.title,
      platform: video.platform
    };
    
    showMessage('info', t('search.downloadingVideo', { platform: platforms[video.platform].label }));
    
    let result;
    if (video.platform === 'bilibili') {
      result = await pywebview.api.download_video(video.id, video.title);
    } else {
      result = await pywebview.api.download_youtube_video(video.url, video.title);
    }
    
    if (result && result.success) {
      downloadingVideos.value[id].status = 'success';
      showMessage('success', t('search.videoDownloadComplete', { title: video.title }));
    } else {
      downloadingVideos.value[id].status = 'error';
      const errorMsg = result?.error || t('search.unknownError');
      showMessage('error', t('search.downloadFailed', { error: errorMsg }));
    }
  } catch (err) {
    downloadingVideos.value[id].status = 'error';
    showMessage('error', t('search.downloadFailed', { error: err.message }));
  } finally {
    setTimeout(() => {
      delete downloadingVideos.value[id];
    }, 3000);
  }
};
watch(showPreviewDialog, (newVal) => {
  if (!newVal) {
    selected_video.value = null
  }
})

</script>

<template>
  <div class="search-container">

    <!-- 搜索框 -->
    <v-text-field
      v-model="search_text"
      :label="t('search.searchLabel', { platform: platforms[platform].label })"
      :placeholder="t('search.searchPlaceholder')"
      type="search"
      @keyup.enter="search_videos"
      :loading="loading"
    >
      <template #append>
        <v-btn
          icon="mdi-magnify"
          color="primary"
          variant="text"
          @click="search_videos"
        />
      </template>
    </v-text-field>
    <!-- 平台切换 -->
    <div class="platform-switch mb-4">
      <span class="select-platform">
        {{ t('search.selectPlatform') }}:
      </span>
      <v-radio-group 
      v-model="platform" 
      mandatory 
      inline
      class="platform-radio-group"
    >
      <!-- 确保每个 v-radio 使用正确的样式 -->
      <v-radio
        v-for="(config, key) in platforms"
        :key="key"
        :value="key"
        :color="config.color"
        density="compact" 
      >
        <template #label>
          <component 
            :is="config.icon"
            v-if="typeof config.icon !== 'string'"
            :size="20"
            :color="config.color"
          />
          <v-icon
            v-else
            :icon="config.icon"
            :color="config.color"
          />
          {{ config.label }}
        </template>
      </v-radio>
    </v-radio-group>
    </div>
    <!-- 错误提示 -->
    <v-alert v-if="error" type="error" density="compact" class="mt-2">
      {{ error }}
    </v-alert>
  </div>

  <!-- 搜索结果 -->
  <div class="search-results" style="position: relative;">
    <v-overlay
      :model-value="loading"
      class="align-center justify-center"
      contained
      persistent
    >
      <v-progress-circular
        indeterminate
        size="64"
        color="primary"
      ></v-progress-circular>
    </v-overlay>

    <v-row v-if="search_results.length">
      <v-col
        v-for="(video, index) in search_results"
        :key="index"
        cols="12"
        md="6"
        lg="4"
      >
      
        <v-card @click="preview_video(video)">
          <v-img
          :src="video.cover || 'default_cover.jpg'"
          height="200"
          cover
          gradient="to bottom, rgba(0,0,0,0), rgba(0,0,0,0.7)"
        >
            <!-- <v-chip
              v-if="video.platform === 'youtube'"
              color="red"
              small
              class="ma-2"
            >
              <v-icon small>mdi-youtube</v-icon> -->
            <!-- </v-chip> -->
            
            <div class="duration-chip">
              {{ format_time(video.duration) }}
            </div>
          </v-img>

          <v-card-title class="text-subtitle-1">
            {{ video.title }}
          </v-card-title>
          
          <v-card-subtitle>
            <div class="d-flex align-center">
            <component 
              :is="platforms[video.platform].icon"
              v-if="typeof platforms[video.platform].icon !== 'string'"
              :size="20"
              :color="platforms[video.platform].color"
            />
            <v-icon
              v-else
              :icon="platforms[video.platform]?.icon || 'mdi-help-circle'"
              small
              :color="platforms[video.platform].color"
            />
            <span class="ml-1">{{ video.author }}</span>
          </div>
          </v-card-subtitle>

          <v-card-actions
           style="min-height: 20px;"
          </v-card-actions>
        </v-card>
      </v-col>
    </v-row>

    <!-- 预览弹窗 -->
    <v-dialog v-model="showPreviewDialog" max-width="1000">
      <v-card v-if="selected_video">
        <v-card-title class="d-flex align-center">
          <div class="d-flex align-center flex-shrink-1 overflow-hidden">
            <span class="text-truncate">{{ selected_video.title }}</span>
            <v-chip class="ml-2 flex-shrink-1" :color="platforms[selected_video.platform].color" small>
              <component
                :is="platforms[selected_video.platform].icon"
                v-if="typeof platforms[selected_video.platform].icon !== 'string'"
                :size="16"
                :color="platforms[selected_video.platform].color"
              />
              <v-icon
                v-else
                :icon="platforms[selected_video.platform]?.icon || 'mdi-help-circle'"
                small
                :color="platforms[selected_video.platform].color"
              />
              {{ selected_video.author }}
            </v-chip>
          </div>
          <v-spacer></v-spacer>
          <v-btn icon @click="showPreviewDialog = false">
            <v-icon>mdi-close</v-icon>
          </v-btn>
        </v-card-title>
        
        <v-row>
          <!-- Left column for video preview and download button -->
          <v-col :cols="selected_video && collectionVideos.length > 0 && selected_video.is_collection === true ? 8 : 12">
            <v-progress-linear
              v-if="!selected_video.embed_url"
              indeterminate
              color="primary"
            ></v-progress-linear>

            <iframe
              v-if="selected_video.embed_url"
              :src="selected_video.embed_url"
              frameborder="0"
              allowfullscreen
              style="width:100%;height:400px"
            ></iframe>

            <!-- Download button moved here, below the iframe -->
            <div
              v-if="selected_video.embed_url"
              class="d-flex mt-4 justify-center download-buttons-container"
            >
              <v-btn
                color="primary"
                variant="tonal"
                @click.stop="download_video(selected_video)"
                :disabled="downloadingVideos[selected_video.id]?.status === 'downloading'"
              >
                <template v-if="downloadingVideos[selected_video.id]?.status === 'downloading'">
                  <v-progress-circular
                    indeterminate
                    size="20"
                    width="2"
                    :color="platforms[selected_video.platform].color"
                    class="mr-2"
                  />
                  {{ t('search.downloading') }}
                </template>
                <template v-else>
                  {{ t('search.downloadVideo') }}
                  <v-icon end>mdi-download</v-icon>
                </template>
              </v-btn>
              
              <!-- YouTube Playlist Download Button -->
              <v-btn
                v-if="selected_video.platform === 'youtube' && selected_video.is_playlist"
                color="red"
                variant="tonal"
                class="ml-4"
                @click.stop="download_youtube_playlist(selected_video.playlist_url, selected_video.playlist_title)"
                :disabled="downloadingVideos[`playlist_${selected_video.playlist_url}`]?.status === 'downloading'"
              >
                <template v-if="downloadingVideos[`playlist_${selected_video.playlist_url}`]?.status === 'downloading'">
                   <v-progress-circular indeterminate size="20" width="2" class="mr-2" />
                  {{ t('search.downloading') }}
                </template>
                <template v-else>
                  {{ t('search.downloadPlaylist') }}
                  <v-icon end>mdi-playlist-music</v-icon>
                </template>
              </v-btn>
            </div>
            <div class="d-flex flex-column"> 
              
            </div>
          </v-col>

          <!-- Right column for video collection list -->
          <v-col cols="4" v-if="selected_video && collectionVideos.length > 0 && selected_video.is_collection === true">
            <v-card-title>
              {{ t('search.videoCollection') }} ({{ currentCollectionIndex !== -1 ? currentCollectionIndex + 1 : '-' }}/{{ collectionVideos.length }})
            </v-card-title>
            <v-list dense style="max-height: 400px; overflow-y: auto;">
              <v-list-item
                v-for="(video, index) in collectionVideos"
                :key="video.bvid || video.aid || index"
                :class="{ 'selected-collection-item': (video.bvid || video.id) === (selected_video.bvid || selected_video.id) }"
                @click="preview_video({ id: video.bvid || video.id, url: `https://www.bilibili.com/video/${video.bvid}`, title: video.title, author: video.owner?.name, platform: 'bilibili', is_collection: true })"
              >
                <v-list-item-content>
                  <v-list-item-title>{{ index + 1 }}. {{ video.title }}</v-list-item-title>
                  <v-list-item-subtitle>{{ t('search.duration') }}: {{ format_time(video.duration) }}</v-list-item-subtitle>
                </v-list-item-content>
              </v-list-item>
            </v-list>
          </v-col>
        </v-row>
        <!-- <v-card-title v-if="selected_video">
          <p>collectionVideos.length: {{ collectionVideos.length }}</p>
          <p>video.is_collection: {{ selected_video.is_collection }}</p>
        </v-card-title> -->
      </v-card>
    </v-dialog>

  </div>
  <!-- 分页 -->
  <v-pagination
  v-if="totalPages > 1"
  v-model="currentPage"
  :length="totalPages"
  :total-visible="7"
  density="compact"
  color="primary"
  @update:modelValue="changePage"
  class="mt-4"
/>

  <!-- 消息提示框 -->
  <UserSnack
    v-for="snack in snackMessages"
    :key="snack.id"
    v-model:show="snack.show"
    :color="snack.type"
    :message="snack.message"
    :timeout="snack.timeout"
    @update:show="val => { if (!val) snackMessages = snackMessages.filter(s => s.id !== snack.id) }"
  />
</template>

<style scoped>

.duration-chip {
  position: absolute;
  bottom: 8px;
  right: 8px;
  background: rgba(0,0,0,0.7);
  color: white;
  padding: 2px 8px;
  border-radius: 4px;
  font-size: 0.8rem;
}

.search-container {
  max-width: 800px;
  margin: 20px auto;
  padding: 0 16px;
}

.search-results {
  padding: 20px;
  max-width: 1400px;
  margin: 0 auto;
}

.v-card {
  transition: transform 0.2s;
  height: 100%;
  
  &:hover {
    transform: translateY(-5px);
    box-shadow: 0 4px 12px rgba(0,0,0,0.2);
  }
}
/* 调整样式 */
.platform-switch {
  display: flex;
  align-items: center;
  gap: 16px; /* 增加间距 */
}

.select-platform {
  font-weight: bold;
  flex-shrink: 0; /* 防止文字被挤压 */
}

/* 调整单选按钮组内部间距 */
.platform-radio-group {
  /* 使用 flexbox layout, and set the spacing between child elements */
  display: flex;
  gap: 24px; /* Increase spacing between radio buttons */
}

/* Remove the right margin of a single v-radio, because the parent's gap has already handled the spacing */
.platform-radio-group :deep(.v-radio) {
  margin-right: 24px !important;
}
.v-pagination {
  justify-content: center;
}

.v-pagination__item {
  box-shadow: none !important;
}

.v-pagination__item--is-active {
  background: rgba(var(--v-theme-primary), 0.1);
}
.v-btn--disabled {
  opacity: 0.7;
}

.selected-collection-item {
  background-color: rgba(var(--v-theme-primary), 0.1);
}

.v-list-item-title {
  font-size: 0.825rem !important; /* Adjusted font size */
}

.v-list-item-subtitle {
  font-size: 0.825rem !important; /* Adjusted font size */
}

.download-buttons-container {
  padding: 16px; /* Add some padding around the buttons */
  gap: 16px; /* Space between buttons */
}
</style>
