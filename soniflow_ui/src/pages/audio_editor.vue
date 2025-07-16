<script setup>
import { ref, onMounted, onBeforeUnmount, watch, computed, nextTick } from 'vue'
import UserSnack from '@/components/user_snack.vue'
import Recorder from 'js-audio-recorder';
import { useI18n } from 'vue-i18n';
// 新增状态
const currentPath = ref('')
const initialCwd = ref(''); // Store the initial current working directory
const loadedAudioPath = ref(null) // Store the path of the currently loaded audio file
const fileList = ref([])
const audioInfo = ref({ duration: 0 })
const zoomLevel = ref(50)
const isSplitMode = ref(false)
const originalAudioUrl = ref('')
const isPlaying = ref(false)
const currentTime = ref(0)
const totalDuration = ref(0)
const audioExtensions = ['mp3', 'wav', 'flac', 'aac', 'ogg', 'm4a']
// const playheadHoverVisible = ref(false)
const barWidth = 1 // Width of each bar in the waveform
const mainWaveformData = ref([]); // New reactive variable to store main waveform data
const barSpacing = 1 // Space between bars in the waveform
const waveformDisplayRef = ref(null) // Reference to the waveform display area
const split_line_time = ref([]) // 用于存储剪切线时间,因为可能不止一个
const deleted_regions = ref([]) // 用于存储标记删除的区域
const isDraggingOverWaveform = ref(false) // 新增：用于波形区域拖拽效果

// Frontend history for undo/redo of split lines and deleted regions
const frontendHistory = ref([{ split_line_time: [], deleted_regions: [] }]); // Stores snapshots of { split_line_time, deleted_regions }
const frontendHistoryPointer = ref(0); // Points to the current state in history

const { t } = useI18n(); // Initialize i18n

let messageId = 0
const snackMessages = ref([])
const showMessage = (type, message, timeout = 3000) => {
  const id = messageId++
  snackMessages.value.push({ id, type, message, show: true, timeout })
}
// 获取文件扩展名
const getExtension = (filename) => {
  const parts = filename.split('.')
  return parts.length > 1 ? parts.pop().toLowerCase() : ''
}

// 检查是否为音频文件
const isAudioFile = (filename) => {
  const ext = getExtension(filename)
  return audioExtensions.includes(ext)
}

// 处理播放头悬停
// const handlePlayheadHover = () => {
//   playheadHoverVisible.value = true
// }


// HTML5 Audio Element
let audio = null
let waveformCanvas = null // Keep canvas ref for the main waveform section
let waveformCtx = null // Keep context for the main waveform section
const waveformCanvasRef = ref(null) // Keep canvas ref for the main waveform section

// 获取目录列表
const fetchDirectory = async (path = null) => {
  try {
    const result = await pywebview.api.list_directory(path)
    if (result.success) {
      currentPath.value = result.path
      fileList.value = result.items
    }
  } catch (e) {
    console.error('API调用失败:', e);
    showMessage('error', t('audioEditor.fetchDirectoryFailed', { message: e.message }));
  }
}

// 回退到上一级目录
const goBack = async () => {
  try {
    const result = await pywebview.api.get_parent_directory(currentPath.value);
    if (result.success) {
      await fetchDirectory(result.path);
      console.log('回退到上一级目录:', result.path);
    } else {
      console.error('Failed to get parent directory from backend:', result.error);
      showMessage('error', t('audioEditor.goBackFailed', { message: result.error }));
    }
  } catch (e) {
    console.error('Error calling get_parent_directory API:', e);
    showMessage('error', t('audioEditor.goBackError', { message: e.message }));
  }
};

// 当前拖拽的文件
const draggedFile = ref(null)

// 处理文件拖拽开始
const handleDragStart = (e, file) => {
  draggedFile.value = file
  e.dataTransfer.setData('text/plain', file.name)
}

// 处理波形区域拖拽进入
const handleWaveformDragEnter = (e) => {
  e.preventDefault();
  isDraggingOverWaveform.value = true;
}

// 处理波形区域拖拽离开
const handleWaveformDragLeave = (e) => {
  e.preventDefault();
  // Check if the drag is leaving the element entirely, not just entering a child
  if (e.relatedTarget && e.currentTarget.contains(e.relatedTarget)) {
    return;
  }
  isDraggingOverWaveform.value = false;
}

// 处理波形区域文件拖拽放下
const handleWaveformDrop = async (e) => {
  e.preventDefault();
  isDraggingOverWaveform.value = false; // Reset drag state

  if (!draggedFile.value) {
    showMessage('warning', t('audioEditor.noFileDragged'));
    return;
  }

  if (!isAudioFile(draggedFile.value.name)) {
    showMessage('warning', t('audioEditor.dragAudioFile'));
    draggedFile.value = null; // Clear dragged file if not audio
    return;
  }

  console.log('在波形区域放下文件:', draggedFile.value.name);

  // Load the audio file into the main editor, same as double-click
  await handleFileAction('load', draggedFile.value);

  draggedFile.value = null; // Clear dragged file after drop
}

// 时间轴缩放计算
const timeToPixel = computed(() => {
  const minMinPxPerSec = 10 // Adjusted for more granular zoom
  const maxMinPxPerSec = 500 // Adjusted for more granular zoom
  const calculatedValue = (zoomLevel.value / 100) * (maxMinPxPerSec - minMinPxPerSec) + minMinPxPerSec;
  console.log('timeToPixel computed:', calculatedValue, 'from zoomLevel:', zoomLevel.value);
  return calculatedValue;
})

// 计算波形画布的宽度
const waveformCanvasWidth = computed(() => {
  // Ensure totalDuration is a number and greater than 0
  if (typeof totalDuration.value !== 'number' || totalDuration.value <= 0) {
    console.log('waveformCanvasWidth computed: totalDuration is not valid, returning 0');
    return 0; // Or a default minimum width
  }
  const calculatedWidth = totalDuration.value * timeToPixel.value;
  console.log('waveformCanvasWidth computed:', calculatedWidth, 'from totalDuration:', totalDuration.value, 'and timeToPixel:', timeToPixel.value);
  return calculatedWidth;
});

// 监听 zoomLevel 和 totalDuration 变化，重新绘制波形
watch([zoomLevel, totalDuration], async ([newZoomLevel, newTotalDuration], [oldZoomLevel, oldTotalDuration]) => {
  console.log('watch triggered: zoomLevel changed from', oldZoomLevel, 'to', newZoomLevel, 'totalDuration changed from', oldTotalDuration, 'to', newTotalDuration);
  // Only generate waveform if audio is loaded and duration is valid
  if (isAudioLoadedAndReady.value) {
    await generateAndDrawWaveform();
  } else {
    console.warn('Watch: Audio not loaded/ready, skipping waveform generation.');
  }
}, { immediate: false }); 

onMounted(async () => {
  // Fetch initial directory listing using backend's get_default_output_directory
  try {
    const defaultOutputDirResult = await pywebview.api.get_default_output_directory();
    if (defaultOutputDirResult.success) {
      initialCwd.value = defaultOutputDirResult.path; // Store the initial CWD
      fetchDirectory(defaultOutputDirResult.path);
      console.log('Initial default output directory fetched from backend:', defaultOutputDirResult.path);
    } else {
      console.error('Failed to get default output directory from backend:', defaultOutputDirResult.error);
      // Fallback to current working directory if getting default output fails
      const cwdResult = await pywebview.api.get_cwd();
      if (cwdResult.success) {
        initialCwd.value = cwdResult.path;
        fetchDirectory(cwdResult.path);
        console.log('Fallback to current working directory:', cwdResult.path);
      } else {
        console.error('Failed to get current working directory from backend:', cwdResult.error);
        fetchDirectory('/'); // Fallback to root if all else fails
      }
    }
  } catch (e) {
    console.error('Error calling backend API for initial directory:', e);
    fetchDirectory('/'); // Fallback to root on API call error
  }

  // Add global keydown listener for spacebar
  window.addEventListener('keydown', handleSpaceKey);

  // Watch for the waveform canvas ref to be available and initialize
  watch(waveformCanvasRef, (newCanvas) => {
    if (newCanvas) {
      waveformCanvas = newCanvas;
      waveformCtx = newCanvas.getContext('2d');
      console.log('Main waveform canvas and context initialized via watch.');

      // Initial draw if audio is already loaded (e.g., on page reload with audio state preserved)
      if (isAudioLoadedAndReady.value) {
          generateAndDrawWaveform(); // Attempt to draw if audio is ready
      }
    } else {
        console.warn('waveformCanvasRef is null or undefined in watch.');
        waveformCanvas = null;
        waveformCtx = null;
    }
  }, { immediate: true }); // Run immediately if the ref is already available

});

onBeforeUnmount(() => {
  if (audio) {
    audio.pause()
    audio = null
  }
  window.removeEventListener('keydown', handleSpaceKey)
})

// Saves the current frontend state (split lines, deleted regions) to history
const saveFrontendState = () => {
  // Remove any "future" states if we're not at the end of history
  if (frontendHistoryPointer.value < frontendHistory.value.length - 1) {
    frontendHistory.value = frontendHistory.value.slice(0, frontendHistoryPointer.value + 1);
  }
  // Add the current state
  const newState = {
    split_line_time: [...split_line_time.value], // Deep copy
    deleted_regions: [...deleted_regions.value] // Deep copy
  };
  frontendHistory.value.push(newState);
  frontendHistoryPointer.value = frontendHistory.value.length - 1;
  console.log('Frontend state saved. History length:', frontendHistory.value.length, 'Pointer:', frontendHistoryPointer.value, 'New State:', newState);
};

// Applies a historical frontend state
const applyFrontendState = (state) => {
  split_line_time.value = [...state.split_line_time];
  deleted_regions.value = [...state.deleted_regions];
  console.log('Frontend state applied. Split lines:', split_line_time.value, 'Deleted regions:', deleted_regions.value);
};

// 更新撤销/重做/剪贴板状态
const updateAudioState = async () => {
  try {
    const result = await pywebview.api.get_audio_history_state()
    if (result.success) {
      backendCanUndo.value = result.state.can_undo;
      backendCanRedo.value = result.state.can_redo;
      copyData.value = result.state.has_clipboard;
      console.log('音频历史状态更新 (Backend):', result.state);
      console.log('backendCanUndo:', backendCanUndo.value, 'backendCanRedo:', backendCanRedo.value, 'copyData:', copyData.value);
    } else {
      console.error('获取音频历史状态失败:', result.error);
      showMessage('error', t('audioEditor.getAudioHistoryFailed', { error: result.error }));
    }
  } catch (error) {
    console.error('调用后端获取历史状态时发生错误:', error);
    showMessage('error', t('audioEditor.getAudioHistoryError', { message: error.message }));
  }
}

// 加载新音频到播放器
const loadAudioToPlayer = async (url) => {
  console.log('loadAudioToPlayer called with URL:', url); // Log the URL
  if (!audio || !url) return;
  audio.src = url;
  
  // Wait for metadata to load before setting duration and generating waveform
  await new Promise((resolve, reject) => {
    audio.onloadedmetadata = () => {
      // Check if audio.duration is a finite number. If not, rely on the duration
      // potentially provided by the backend load_audio call.
      if (Number.isFinite(audio.duration) && audio.duration > 0) {
        totalDuration.value = audio.duration;
        console.log('loadedmetadata fired, totalDuration:', totalDuration.value);
      } else {
        console.warn('loadedmetadata fired, audio.duration is not finite:', audio.duration, '. Keeping backend duration:', totalDuration.value);
        // Keep the totalDuration value set by the backend load_audio call
      }
      resolve();
    };
    audio.onerror = (e) => {
      console.error('Audio loading error:', e);
      reject(new Error('Failed to load audio metadata'));
    };
    audio.load(); // Load the new audio source
  });

  // After loading and setting duration, update audio state.
  // Waveform generation will be triggered by the watch on totalDuration.
  await updateAudioState(); // Update state after loading new audio
};
// 生成并绘制波形
const generateAndDrawWaveform = async () => {
  console.log('generateAndDrawWaveform called');
  // Add check for canvas context
  if (!waveformCtx || !waveformCanvasRef.value) {
      console.warn('generateAndDrawWaveform: Canvas context or ref not ready. Skipping generation.');
      // Optionally, you could try to initialize here again, or wait and retry
      // For now, let's just skip and rely on the watch/next call
      return;
  }

  try {
    const targetBarCount = Math.floor(waveformCanvasWidth.value / (barWidth + barSpacing));
    console.log('generateAndDrawWaveform: targetBarCount', targetBarCount);

    // Add check for valid targetBarCount
    if (!Number.isFinite(targetBarCount) || targetBarCount <= 0) {
      console.warn('generateAndDrawWaveform: targetBarCount is not a valid positive number:', targetBarCount, '. Skipping waveform generation.');
      clearWaveform(); // Clear any previous waveform
      return; // Exit the function
    }

    const result = await pywebview.api.generate_waveform(loadedAudioPath.value, targetBarCount); // Corrected function name and added file path
    if (result.success) {
      console.log('generateAndDrawWaveform: Received waveform data (length):', result.data ? result.data.length : 'null/undefined');
      console.log('generateAndDrawWaveform: Received waveform duration:', result.duration);
      mainWaveformData.value = result.data; // Store the received data
      drawWaveform(result.data, result.duration);
    } else {
      console.error('generateAndDrawWaveform: Backend waveform generation failed:', result.error);
      // showMessage('error', t('audioEditor.generateWaveformFailed', { error: result.error })); // Re-enable if needed
      clearWaveform();
    }
  } catch (error) {
    console.error('generateAndDrawWaveform: Error calling backend API:', error);
    // showMessage('error', t('audioEditor.generateWaveformError', { message: error.message })); // Re-enable if needed
    clearWaveform();
  }
};

// 绘制波形图
const drawWaveform = (data) => {
  console.log('drawWaveform called.');
  console.log('drawWaveform state:', {
    waveformCtx: !!waveformCtx, // Check if context exists
    waveformCanvasRefValue: !!waveformCanvasRef.value, // Check if ref value exists
    waveformCanvasWidthValue: waveformCanvasWidth.value // Check computed width
  });

  if (!waveformCtx || !waveformCanvasRef.value || !waveformCanvasWidth.value) {
    console.log('drawWaveform: Canvas context, ref, or width not ready. Skipping draw.');
    return;
  }

  const canvas = waveformCanvasRef.value;
  const width = waveformCanvasWidth.value; 
  const height = canvas.height; // Use fixed height from canvas attribute

  console.log('drawWaveform: Drawing with width', width, 'and height', height);
  console.log('drawWaveform: Data length:', data ? data.length : 'null/undefined');

  // Set canvas dimensions for drawing
  canvas.width = width;
  canvas.height = height;

  waveformCtx.clearRect(0, 0, width, height);
  waveformCtx.fillStyle = '#61afef'; // Wave color

  const center = height / 2;
  const scale = height / 2;

  const barWidth = 2; // Width of each bar
  const barSpacing = 1; // Space between bars
  const totalBarWidth = barWidth + barSpacing;

  // Calculate how many bars can fit into the *dynamic* width
  const numBarsToDraw = Math.floor(width / totalBarWidth);
  console.log('drawWaveform: numBarsToDraw:', numBarsToDraw);

  if (!data || data.length === 0) {
    console.warn('drawWaveform: No data to draw or data is empty.');
    // Optionally draw a placeholder or clear the canvas if no data
    waveformCtx.clearRect(0, 0, width, height);
    return;
  }

  // Calculate step size to sample data points from the audio data
  // This ensures that the entire audio duration is represented across the dynamic width
  const step = Math.max(1, Math.floor(data.length / numBarsToDraw));
  console.log('drawWaveform: step for data sampling:', step);

  for (let i = 0; i < numBarsToDraw; i++) {
    const x = i * totalBarWidth;
    const dataIndex = i * step;
    
    if (dataIndex < data.length) {
      const chunk = data.slice(dataIndex, dataIndex + step);
      const peakValue = Math.max(...chunk.map(Math.abs));

      const barHeight = peakValue * scale;
      waveformCtx.fillRect(x, center - barHeight, barWidth, barHeight * 2);
    } else {
      // If we run out of data, draw a small line to indicate empty space
      waveformCtx.fillRect(x, center - 1, barWidth, 2);
    }
  }
};

// 清除波形图
const clearWaveform = () => {
  if (waveformCtx && waveformCanvas) {
    waveformCtx.clearRect(0, 0, waveformCanvas.width, waveformCanvas.height)
  }
}

// 处理剪切点击
const handleSplitClick = () => {
  if (!isAudioLoadedAndReady.value) {
    console.warn('音频未加载或未准备好，无法进入剪切模式。');
    showMessage('warning', t('audioEditor.audioNotLoadedForSplit'));
    return
  }
  isSplitMode.value = !isSplitMode.value
  console.log(t('audioEditor.debugSplitMode'), isSplitMode.value ? t('audioEditor.splitModeEnabled') : t('audioEditor.splitModeDisabled'))
}

// 处理文件操作
const handleFileAction = async (action, file) => {
  switch (action) {
    case 'load':
      try {
        // 先加载音频到后端处理器
        const loadResult = await pywebview.api.load_audio(file.path)
        if (loadResult.success) {
          audioInfo.value = loadResult.info
          totalDuration.value = loadResult.duration // 关键：先设置时长

          // Set loadedAudioPath here
          loadedAudioPath.value = file.path; // <--- Add this line

          // 再获取URL并加载到播放器
          const result = await pywebview.api.get_local_file_url(file.path)
          if (result.success) {
            originalAudioUrl.value = result.url
            // Ensure audio object is created before loading
            if (!audio) {
              audio = new Audio();
              // Add event listeners for playback updates
              audio.ontimeupdate = () => {
                currentTime.value = audio.currentTime;
              };
              audio.onplay = () => {
                isPlaying.value = true;
              };
              audio.onpause = () => {
                isPlaying.value = false;
              };
              audio.onended = () => {
                isPlaying.value = false;
                currentTime.value = 0; // Reset to start on end
              };
            }
            await loadAudioToPlayer(result.url) // 此时totalDuration已有效
          }
        }
      } catch (error) {
        console.error('加载失败:', error)
        showMessage('error', t('audioEditor.loadFailed', { message: error.message }))
      }
      break
  }
}

// 新增状态
const hoverTime = ref(0)
const hoverPosition = ref(0)
const hoverTimeVisible = ref(false)

// 处理波形区域鼠标移动
const handleWaveformMouseMove = (event) => {
  if (!waveformDisplayRef.value) return // Need waveformDisplayRef for scrollLeft and getBoundingClientRect
  
  const displayElement = waveformDisplayRef.value;
  const displayRect = displayElement.getBoundingClientRect();
  const currentScrollLeft = displayElement.scrollLeft;

  // Get the left padding of the waveform display container
  const displayStyle = getComputedStyle(displayElement);
  const displayPaddingLeft = parseFloat(displayStyle.paddingLeft);

  // Calculate mouse position relative to waveform-display's content area
  const mouseXRelativeToDisplay = event.clientX - displayRect.left;
  const mouseXRelativeToDisplayContent = mouseXRelativeToDisplay - displayPaddingLeft;

  // Calculate hover position relative to the absolute start of the waveform content
  const hoverPositionAbsolute = mouseXRelativeToDisplayContent + currentScrollLeft;

  // Ensure hoverPositionAbsolute is not negative
  hoverPosition.value = Math.max(0, hoverPositionAbsolute);
  hoverTime.value = hoverPosition.value / timeToPixel.value;
  hoverTimeVisible.value = true

  // Auto-scroll waveform display area
  const displayWidth = displayElement.clientWidth; // This is the width of the content box
  
  // If the hover line is outside the current visible scroll area, or too close to the edge, scroll
  const scrollPadding = displayWidth * 0.2; // Keep hover line at least 20% from edges

  // The hoverPosition.value is relative to the start of the full waveform content.
  // The visible area starts at currentScrollLeft and ends at currentScrollLeft + displayWidth.
  // We need to check if hoverPosition.value is within [currentScrollLeft + scrollPadding, currentScrollLeft + displayWidth - scrollPadding].

  if (hoverPosition.value < currentScrollLeft + scrollPadding) {
    // Scroll left to bring it into view, keeping padding
    displayElement.scrollLeft = Math.max(0, hoverPosition.value - scrollPadding);
  } else if (hoverPosition.value > currentScrollLeft + displayWidth - scrollPadding) {
    // Scroll right to bring it into view, keeping padding
    displayElement.scrollLeft = Math.min(waveformCanvasWidth.value - displayWidth, hoverPosition.value - (displayWidth - scrollPadding));
  }
}

// 处理鼠标离开波形区域
const handleWaveformMouseLeave = () => {
  hoverTimeVisible.value = false
}

const add_split_line = (time) => {
  if (!isAudioLoadedAndReady.value) {
    console.warn('音频未加载或未准备好，无法添加分割线。');
    showMessage('warning', t('audioEditor.audioNotLoadedForSplit'));
    return
  }
  // 直接利用前端逻辑在点击位置添加分割线
  split_line_time.value.push(time)
  split_line_time.value.sort((a, b) => a - b) // 保持时间线有序
  saveFrontendState(); // Save state after modification

  console.log(t('audioEditor.debugAddSplitLine'), time, t('audioEditor.debugCurrentSplitLines'), split_line_time.value)
}
// 处理波形区域点击
const handleWaveformClick = async (event) => {
  if (!isAudioLoadedAndReady.value) return

  const rect = waveformCanvasRef.value.getBoundingClientRect()
  const offsetX = event.clientX - rect.left
  const clickedTime = offsetX / timeToPixel.value

  // Ensure it's a left click for this handler
  if (event.button !== 0) return; 

  if (isSplitMode.value) {
    
    console.log(t('audioEditor.debugClickTimeSplit'), clickedTime)
    // 先不调用后端函数，先在剪切位置放置剪切线
    add_split_line(clickedTime)
    // isSplitMode.value = false // Exit split mode after adding the line - Removed to allow multiple splits
  } else {
    // If not in split mode, jump to the clicked time
    currentTime.value = clickedTime
    console.log(t('audioEditor.debugJumpToTime'), currentTime.value)
    if (audio) {
      audio.currentTime = currentTime.value
      if (isPlaying.value) {
        audio.pause()
      }
    }
  }
}
// 处理右键删除波形
const delete_waveform = async (event) => { 
  if (!isAudioLoadedAndReady.value) return
  const rect = event.currentTarget.getBoundingClientRect()
  const offsetXRelativeToRulerContainer = event.clientX - rect.left
  
  // Get the left padding of the ruler container
  const rulerContainerStyle = getComputedStyle(event.currentTarget);
  const rulerPaddingLeft = parseFloat(rulerContainerStyle.paddingLeft);

  // Calculate the offset relative to the start of the ruler *content*
  const offsetXRelativeToRulerContent = offsetXRelativeToRulerContainer - rulerPaddingLeft;

  // Add the scrollLeft of the waveform-display to get the absolute position
  const absoluteRulerHoverX = offsetXRelativeToRulerContent + waveformDisplayRef.value.scrollLeft;

  rulerHoverPosition.value = absoluteRulerHoverX; // This should be the absolute position
  rulerHoverTime.value = absoluteRulerHoverX / timeToPixel.value;
  // Find the split line immediately before or at the current time
  const start_time = split_line_time.value
    .filter(time => time <= rulerHoverTime.value)
    .reduce((latest, current) => Math.max(latest, current), 0); // Default to 0 if no split line before
    console.log(t('audioEditor.debugCurrentTime'), rulerHoverTime.value, t('audioEditor.debugStartTime'), start_time, t('audioEditor.debugSplitLines'), split_line_time.value)

  // Find the split line immediately after the current time
  const end_time = split_line_time.value
    .filter(time => time > rulerHoverTime.value)
    .reduce((earliest, current) => Math.min(earliest, current), totalDuration.value); // Default to totalDuration if no split line after
  console.log(t('audioEditor.debugCurrentTime'), rulerHoverTime.value, t('audioEditor.debugEndTime'), end_time, t('audioEditor.debugSplitLines'), split_line_time.value)
  // Check if a valid selection exists
  if (start_time === end_time) {
    console.warn('没有选区，无法执行删除操作。请先选择一个区域。')
    showMessage('warning', t('audioEditor.noSelectionToDelete'));
    return
  }
  if (event.button !== 2) { // Right click
    console.warn('请使用右键点击波形区域进行删除操作。')
    showMessage('warning', t('audioEditor.useRightClickToDelete'));
    return
  }
  // Check if a region with these exact start/end times already exists
  const existingIndex = deleted_regions.value.findIndex(
    (region) => region.start === start_time && region.end === end_time
  );

  if (existingIndex !== -1) {
    // Region exists, so remove it (deselect)
    deleted_regions.value.splice(existingIndex, 1);
    showMessage('info', t('audioEditor.regionRemoved', { start: formatTime(start_time), end: formatTime(end_time) }));
    console.log('取消标记区域:', { start: start_time, end: end_time }, t('audioEditor.debugCurrentDeletedRegion'), deleted_regions.value);
  } else {
    // Region does not exist, so add it (select/mark for deletion)
    deleted_regions.value.push({ start: start_time, end: end_time });
    showMessage('info', t('audioEditor.regionMarkedForDeletion', { start: formatTime(start_time), end: formatTime(end_time) }));
    console.log(t('audioEditor.debugMarkedDeletedRegion'), { start: start_time, end: end_time }, t('audioEditor.debugCurrentDeletedRegion'), deleted_regions.value);
  }
  saveFrontendState(); // Save state after modification
}

// 更新格式化时间方法，支持毫秒级显示
const formatTime = (seconds) => {
  const minutes = Math.floor(seconds / 60)
  const remainingSeconds = Math.floor(seconds % 60)
  const milliseconds = Math.floor((seconds * 1000) % 1000).toString().padStart(3, '0').substring(0, 2)
  
  return `${minutes}:${remainingSeconds < 10 ? '0' : ''}${remainingSeconds}.${milliseconds}`
}
// 新增标尺悬停状态
const rulerHoverTime = ref(0)
const rulerHoverPosition = ref(0)
const rulerHoverTimeVisible = ref(false)

// 处理标尺鼠标移动
const handleRulerMouseMove = (event) => {
  if (!waveformDisplayRef.value) return; // Need waveformDisplayRef for scrollLeft

  const rect = event.currentTarget.getBoundingClientRect()
  const offsetXRelativeToRulerContainer = event.clientX - rect.left
  
  // Add the scrollLeft of the waveform-display to get the absolute position
  const absoluteRulerHoverX = offsetXRelativeToRulerContainer + waveformDisplayRef.value.scrollLeft;

  rulerHoverPosition.value = absoluteRulerHoverX; // This should be the absolute position
  rulerHoverTime.value = absoluteRulerHoverX / timeToPixel.value;
  console.log(t('audioEditor.debugRulerHoverTime'), rulerHoverTime.value)
  rulerHoverTimeVisible.value = true;
}

// 处理标尺鼠标离开
const handleRulerMouseLeave = () => {
  rulerHoverTimeVisible.value = false
}
// 复制选区
// const handleCopySelection = async () => {
//   if (!isAudioLoadedAndReady.value) return
  
//   const start = Math.min(selectionStart.value, selectionEnd.value)
//   const end = Math.max(selectionStart.value, selectionEnd.value)
  
//   console.log('已复制选区:', { start, end })
//   try {
//     const result = await pywebview.api.copy_audio_selection(start, end)
//     if (result.success) {
//       showMessage('success', '选区已复制到剪贴板');
//       await updateAudioState() // Update state after operation
//     } else {
//       console.error('后端复制选区失败:', result.error);
//       showMessage('error', `复制选区失败: ${result.error}`);
//     }
//   } catch (error) {
//     console.error('调用后端复制选区时发生错误:', error);
//     showMessage('error', `复制选区时发生错误: ${error.message}`);
//   }
// }
// 鼠标左键点击参考线跳转
const handleRulerClick = (event) => {
  if (!isAudioLoadedAndReady.value) return
  if (event.button === 0) { // Left click
    currentTime.value = rulerHoverTime.value
    console.log(t('audioEditor.debugJumpToTime'), currentTime.value)
    if (audio) {
      audio.currentTime = currentTime.value
      if (isPlaying.value) { 
        audio.pause()
      }
    }
  }
}
// 粘贴选区
// const handlePasteSelection = async () => {
//   if (!isAudioLoadedAndReady.value) return
  
//   console.log('粘贴到当前时间:', currentTime.value)
//   try {
//     const result = await pywebview.api.paste_audio_selection(currentTime.value)
//     if (result.success) {
//       const newAudioUrlResult = await pywebview.api.get_current_audio_url()
//       if (newAudioUrlResult.success) {
//         await loadAudioToPlayer(newAudioUrlResult.url)
//         audioInfo.value = result.info // Update audio info from backend
//         // Clear frontend visual markers as the underlying audio state has changed
//         split_line_time.value = []
//         deleted_regions.value = []
//         await updateAudioState() // Update state after operation
//       } else {
//         console.error('获取更新音频URL失败:', newAudioUrlResult.error);
//         showMessage('error', `撤销后加载音频失败: ${newAudioUrlResult.error}`);
//       }
//     } else {
//       console.error('后端撤销操作失败:', result.error);
//       showMessage('error', `撤销操作失败: ${result.error}`);
//     }
//   } catch (error) {
//     console.error('调用后端撤销操作时发生错误:', error);
//     showMessage('error', `撤销操作时发生错误: ${error.message}`);
//   }
// }

// 撤销操作
const handleUndo = async () => {
  console.log(t('audioEditor.debugExecuteUndo'), t('audioEditor.debugCurrentHistory'), frontendHistory.value, t('audioEditor.debugPointer'), frontendHistoryPointer.value);
  try {
    // First, try to undo a frontend action
    if (frontendHistoryPointer.value > 0) {
      frontendHistoryPointer.value--;
      const prevState = frontendHistory.value[frontendHistoryPointer.value];
      applyFrontendState(prevState);
      showMessage('info', t('audioEditor.frontendUndoSuccess'));
      console.log(t('audioEditor.debugUndoFrontendPointer'), frontendHistoryPointer.value, 'Applied State:', prevState);
      return; // Exit if frontend action was undone
    }

    // If no frontend actions to undo, try backend undo
    if (backendCanUndo.value) {
      const result = await pywebview.api.undo_audio();
      if (result.success) {
        const newAudioUrlResult = await pywebview.api.get_current_audio_url();
        if (newAudioUrlResult.success) {
          await loadAudioToPlayer(newAudioUrlResult.url);
          audioInfo.value = result.info; // Update audio info from backend
          // Clear frontend history as backend state changed
          frontendHistory.value = [{ split_line_time: [], deleted_regions: [] }]; // Reset to initial empty state
          frontendHistoryPointer.value = 0; // Reset pointer
          await updateAudioState(); // Update backend state flags
          showMessage('info', t('audioEditor.backendUndoSuccess'));
          console.log('撤销后端操作，前端历史已重置.');
        } else {
          console.error('获取更新音频URL失败:', newAudioUrlResult.error);
          showMessage('error', t('audioEditor.loadAudioAfterUndoFailed', { error: newAudioUrlResult.error }));
        }
      } else {
        console.error('后端撤销操作失败:', result.error);
        showMessage('error', t('audioEditor.backendUndoFailed', { error: result.error }));
      }
    } else {
      showMessage('warning', t('audioEditor.noMoreUndo'));
    }
  } catch (error) {
    console.error('调用撤销操作时发生错误:', error);
    showMessage('error', t('audioEditor.undoError', { message: error.message }));
  }
};

// 重做操作
const handleRedo = async () => {
  console.log(t('audioEditor.debugExecuteRedo'), t('audioEditor.debugCurrentHistory'), frontendHistory.value, t('audioEditor.debugPointer'), frontendHistoryPointer.value);
  try {
    // First, try to redo a frontend action
    if (frontendHistoryPointer.value < frontendHistory.value.length - 1) {
      frontendHistoryPointer.value++;
      const nextState = frontendHistory.value[frontendHistoryPointer.value];
      applyFrontendState(nextState);
      showMessage('info', t('audioEditor.frontendRedoSuccess'));
      console.log(t('audioEditor.debugRedoFrontendPointer'), frontendHistoryPointer.value, 'Applied State:', nextState);
      return; // Exit if frontend action was redone
    }

    // If no frontend actions to redo, try backend redo
    if (backendCanRedo.value) {
      const result = await pywebview.api.redo_audio();
      if (result.success) {
        const newAudioUrlResult = await pywebview.api.get_current_audio_url();
        if (newAudioUrlResult.success) {
          loadedAudioPath.value = newAudioUrlResult.path; // Update the loaded path
          await loadAudioToPlayer(newAudioUrlResult.url);
          audioInfo.value = result.info; // Update audio info from backend
          // Clear frontend history as backend state changed
          frontendHistory.value = [{ split_line_time: [], deleted_regions: [] }]; // Reset to initial empty state
          frontendHistoryPointer.value = 0; // Reset pointer
          await updateAudioState(); // Update backend state flags
          showMessage('info', t('audioEditor.backendRedoSuccess'));
          console.log('重做后端操作，前端历史已重置.');
        } else {
          console.error('获取更新音频URL失败:', newAudioUrlResult.error);
          showMessage('error', t('audioEditor.loadAudioAfterRedoFailed', { error: newAudioUrlResult.error }));
        }
      } else {
        console.error('后端重做操作失败:', result.error);
        showMessage('error', t('audioEditor.backendRedoFailed', { error: result.error }));
      }
    } else {
      showMessage('warning', t('audioEditor.noMoreRedo'));
    }
  } catch (error) {
    console.error('调用重做操作时发生错误:', error);
    showMessage('error', t('audioEditor.redoError', { message: error.message }));
  }
};

// 导出音频
const handleExport = async () => {
  console.log(t('audioEditor.debugExecuteExport'))
  console.log(t('audioEditor.debugExportSplitLines'), split_line_time.value)
  console.log(t('audioEditor.debugExportDeletedRegions'), deleted_regions.value)

  try {
    const result = await pywebview.api.process_and_export_audio(split_line_time.value, deleted_regions.value)
    if (result.success) {
      showMessage('success', t('audioEditor.exportSuccess', { path: result.path }));
      // 清空分割线和删除区域
      split_line_time.value = []
      deleted_regions.value = []
    } else {
      console.error('后端处理和导出音频失败:', result.error);
      showMessage('error', t('audioEditor.exportFailed', { error: result.error }));
    }
  }
  catch (error) {
    console.error('调用后端处理和导出音频时发生错误:', error);
    showMessage('error', t('audioEditor.exportError', { message: error.message }));
  }
}

// 处理音频片段拖拽
const handleClipDrag = (e, clip) => {
  e.dataTransfer.setData('clip/id', clip.id)
}

// 处理片段在音轨内移动
// 播放/暂停控制
const togglePlayPause = () => {
  if (audio) {
    if (isPlaying.value) {
      audio.pause()
    } else {
      audio.play()
    }
  }
}

const handleSpaceKey = (event) => {
  if (event.code === 'Space') {
    event.preventDefault()
    togglePlayPause()
  }
}

// 处理鼠标滚轮事件进行缩放 (Placeholder for custom waveform)
const handleMouseWheel = (event) => {
  event.preventDefault()
  const zoomAmount = event.deltaY > 0 ? -5 : 5 // Zoom out for positive deltaY (scroll down), zoom in for negative
  zoomLevel.value = Math.max(0, Math.min(100, zoomLevel.value + zoomAmount))
}

// 新增处理颜色
const getFileColor = (file) => {
  if (file.is_dir) return '#c678dd'
  return isAudioFile(file.name) ? '#61afef' : '#5c6370'
}

// 计算是否音频已加载
const isAudioLoadedAndReady = computed(() => {
  // Audio is considered loaded and ready if we have a path and a valid duration
  const loaded = loadedAudioPath.value !== null && totalDuration.value > 0;
  console.log('isAudioLoadedAndReady computed:', loaded, 'loadedAudioPath:', loadedAudioPath.value, 'totalDuration:', totalDuration.value);
  return loaded;
})

// Placeholder for canUndo/canRedo, will depend on backend state
const backendCanUndo = ref(false) // Tracks backend undo state
const backendCanRedo = ref(false) // Tracks backend redo state
const copyData = ref(false) // Will be true if backend indicates something is copied

// Computed properties for combined undo/redo state
const canUndo = computed(() => {
  return frontendHistoryPointer.value > 0 || backendCanUndo.value;
});

const canRedo = computed(() => {
  return frontendHistoryPointer.value < frontendHistory.value.length - 1 || backendCanRedo.value;
});

// Recording state
const isRecording = ref(false);
let recorder = null; // Declare recorder here

// Record audio function
const recordAudio = async () => {
  if (isRecording.value) {
    // Stop recording
    if (recorder) { // Check if recorder exists
      try {
        // Stop the existing recorder instance
        recorder.stop();
        showMessage('success', t('audioEditor.recordedComplete'));
        // Get the recorded audio data as a Blob
        const audioBlob = recorder.getWAVBlob();
        console.log('Recorded audio Blob size:', audioBlob.size, 'bytes'); // Added for debugging
        // Check if the result is a Blob
        if (!(audioBlob instanceof Blob)) {
          console.error('recorder.getWAVBlob() did not return a Blob');
          showMessage('error', t('audioEditor.recordStopFailedNoAudio'));
          isRecording.value = false; // Ensure state is false on error
          return; // Exit if no blob
        }

        // Existing saving logic adapted for the new blob
        const reader = new FileReader();
        reader.onloadend = async () => {
          const base64data = reader.result.split(',')[1]; // Get base64 string
          const fileName = `recorded_audio_${Date.now()}.wav`; // Generate a filename
          try {
            // Send base64 data and filename to backend to save as a file
            const saveResult = await pywebview.api.save_recorded_audio({
              base64_data: base64data,
              file_name: fileName
            });
            if (saveResult.success) {
              const loadResult = await pywebview.api.load_audio(saveResult.path);
              if (loadResult.success) {
                audioInfo.value = loadResult.info;
                totalDuration.value = loadResult.duration;

                // Get URL and load into player
                const result = await pywebview.api.get_local_file_url(saveResult.path);
                if (result.success) {
                  originalAudioUrl.value = result.url;
                  if (!audio) {
                    audio = new Audio();
                    audio.ontimeupdate = () => { currentTime.value = audio.currentTime; };
                    audio.onplay = () => { isPlaying.value = true; };
                    audio.onpause = () => { isPlaying.value = false; };
                    audio.onended = () => { isPlaying.value = false; currentTime.value = 0; };
                  }
                  await loadAudioToPlayer(result.url); // totalDuration is now valid

                  // Only set state to false and show success message if everything above succeeded
                  isRecording.value = false;
                  showMessage('info', t('audioEditor.recordStopSuccess'));
                } else {
                  console.error('获取更新音频URL失败:', newAudioUrlResult.error);
                  showMessage('error', t('audioEditor.getUpdatedAudioUrlFailed', { error: result.error }));
                  isRecording.value = false; // Ensure state is false on error
                }
              } else {
                console.error('加载录制音频失败:', loadResult.error);
                showMessage('error', t('audioEditor.loadRecordedAudioFailed', { error: loadResult.error }));
                isRecording.value = false; // Ensure state is false on error
              }
            } else {
              console.error('保存录制音频失败:', saveResult.error);
              showMessage('error', t('audioEditor.saveRecordedAudioFailed', { error: saveResult.error }));
              isRecording.value = false; // Ensure state is false on error
            }
          } catch (error) {
            console.error('调用后端保存录制音频时发生错误:', error);
            showMessage('error', t('audioEditor.callBackendSaveRecordedAudioError', { message: error.message }));
            isRecording.value = false; // Ensure state is false on error
          }
        };
        reader.readAsDataURL(audioBlob); // Read the Blob returned by recorder.stop()

      } catch (error) {
         console.error('停止录制失败:', error);
         showMessage('error', t('audioEditor.recordStopFailed', { message: error.message }));
         isRecording.value = false; // Ensure state is false on error
      } finally {
        recorder = null; // Clear recorder instance regardless of success/failure
      }
    } else {
       // If recorder was somehow null when trying to stop
       console.warn('Attempted to stop recording, but recorder instance was null.');
       showMessage('warning', t('audioEditor.recordStateAbnormalReset'));
       isRecording.value = false; // Ensure state is false
       recorder = null; // Ensure recorder is null
    }
  } else {
    // Start recording
    try {
      const options = {
        // Recorder options, adjust as needed
        sampleRate: 44100,
        numChannels: 2, // Changed from 1 to 2
        sampleBits: 16, 
      };
      recorder = new Recorder(options);
      // Assuming start() is async and returns a Promise
      await recorder.start();
   
      isRecording.value = true;
      showMessage('info', t('audioEditor.startRecording'));
    } catch (error) {
      console.error('启动录制失败:', error);
      showMessage('error', t('audioEditor.startRecordingFailed', { message: error.message }));
      isRecording.value = false; // Ensure state is false if start fails
    }
  }
};
</script>

<template>
  <div class="editor-container">
    <!-- 左侧文件面板 - 固定不动 -->
    <div class="file-panel">
      <div class="path-bar">
        <v-btn icon @click="goBack" :disabled="currentPath === initialCwd">
          <v-icon>mdi-arrow-left</v-icon>
        </v-btn>
        <span class="path-text">{{ currentPath }}</span>
      </div>

      <div class="file-list">
        <div v-for="item in fileList"
             :key="item.path"
             class="file-item"
             @dblclick="item.is_dir ? fetchDirectory(item.path) : handleFileAction('load', item)"
             @dragstart="e => handleDragStart(e, item)"
             draggable="true"
             :class="{ 'is-dragging': draggedFile && draggedFile.path === item.path }">
           <v-icon :color="getFileColor(item)">
            {{
              item.is_dir
                ? 'mdi-folder'
                : isAudioFile(item.name)
                  ? 'mdi-music'
                  : 'mdi-file'
            }}
          </v-icon>
          <span class="file-name">{{ item.name }}</span>
          <!-- <span class="size">{{ formatSize(item.size) }}</span> -->
        </div>
      </div>
    </div>

    <!-- 右侧编辑面板 -->
    <div class="editor-panel">
      <!-- 主波形显示 (用于剪切选择) -->
      <div class="main-waveform-section">
        <h3><v-icon left>mdi-waveform</v-icon>{{ t('audioEditor.currentLoadedWaveform') }}</h3>
        <div class="waveform-controls">
          <v-btn icon @click="togglePlayPause" @keydown.space="togglePlayPause" tabindex="0">
            <v-icon>{{ isPlaying ? 'mdi-pause' : 'mdi-play' }}</v-icon>
          </v-btn>
          <span class="time-display">{{ formatTime(currentTime) }} / {{ formatTime(totalDuration) }}</span>
          <v-slider
            v-model="zoomLevel"
            :min="0"
            :max="100"
            :step="1"
            append-icon="mdi-magnify-plus-outline"
            prepend-icon="mdi-magnify-minus-outline"
            thumb-label="always"
            class="zoom-slider"
            hide-details
          ></v-slider>
          <v-tooltip :text="t('audioEditor.recordAudio')">
          <template v-slot:activator="{ props }">
            <v-btn v-bind="props" class="ma-2" @click="recordAudio" color="secondary" :icon="isRecording ? 'mdi-stop' : 'mdi-microphone'" variant="text">
            </v-btn>
          </template>
        </v-tooltip>
        <v-tooltip :text="t('audioEditor.undo')">
          <template v-slot:activator="{ props }">
            <v-btn v-bind="props" class="ma-2" @click="handleUndo" :disabled="!canUndo" color="secondary" icon="mdi-undo" variant="text">
            </v-btn>
          </template>
        </v-tooltip>
        
        <v-tooltip :text="t('audioEditor.redo')">
          <template v-slot:activator="{ props }">
            <v-btn v-bind="props" class="ma-2" @click="handleRedo" :disabled="!canRedo" color="secondary" icon="mdi-redo" variant="text">
            </v-btn>
          </template>
        </v-tooltip>
    
        <!-- <v-tooltip :text="t('audioEditor.copySelection')">
          <template v-slot:activator="{ props }">
            <v-btn v-bind="props" class="ma-2" @click="handleCopySelection" :disabled="!isAudioLoadedAndReady" color="secondary" icon="mdi-content-copy" variant="text">
            </v-btn>
          </template>
        </v-tooltip>
        
        <v-tooltip :text="t('audioEditor.pasteSelection')">
          <template v-slot:activator="{ props }">
            <v-btn v-bind="props" class="ma-2" @click="handlePasteSelection" :disabled="!copyData" color="secondary" icon="mdi-content-paste" variant="text">
            </v-btn>
          </template>
        </v-tooltip> -->
        <v-tooltip :text="isSplitMode ? t('audioEditor.exitSplitMode') : t('audioEditor.splitAudio')">
          <template v-slot:activator="{ props }">
            <v-btn v-bind="props" class="ma-2" @click="handleSplitClick" :color="isSplitMode ? 'warning' : 'secondary'" icon="mdi-content-cut" variant="text">
            </v-btn>
          </template>
        </v-tooltip>

        <v-tooltip :text="t('audioEditor.exportAudio')">
          <template v-slot:activator="{ props }">
            <v-btn v-bind="props" class="ma-2" @click="handleExport" color="secondary" icon="mdi-export" variant="text">
            </v-btn>
          </template>
        </v-tooltip>
        </div>
        <!-- 时间轴标尺 -->
        <div class="time-ruler-container"
          @mousemove="handleRulerMouseMove"
          @mouseleave="handleRulerMouseLeave"
          @click="handleRulerClick"
          v-if="totalDuration > 0">
          <div class="time-ruler" :style="{ width: `${waveformCanvasWidth}px` }">
            <div
              v-for="t in Math.ceil(totalDuration)"
              :key="t"
              class="time-marker"
              :style="{ left: `${(t - 1) * timeToPixel}px` }"
            ></div>
            <div v-if="rulerHoverTimeVisible" class="ruler-hover-time" :style="{ left: `${rulerHoverPosition}px` }">
              {{ formatTime(rulerHoverTime) }}
            </div>
          </div>
        </div>
        <div id="waveform" class="waveform-display"
            @wheel.prevent="handleMouseWheel"
            @mousemove="handleWaveformMouseMove"
            @mouseleave="handleWaveformMouseLeave"
            @click="handleWaveformClick"
            @contextmenu.prevent="delete_waveform"
            @dragover.prevent
            @dragenter.prevent="handleWaveformDragEnter"
            @dragleave.prevent="handleWaveformDragLeave"
            @drop="handleWaveformDrop"
            ref="waveformDisplayRef"
            :class="{ 'is-dragging-over-waveform': isDraggingOverWaveform }"
        >
          <canvas ref="waveformCanvasRef" id="waveformCanvas"></canvas>
        <!-- 在波形显示区域添加悬停线和时间 -->
          <div v-if="hoverTimeVisible" class="hover-line" :style="{ left: `${hoverPosition}px` }" ></div>
          <div v-if="hoverTimeVisible" class="waveform-hover-time" :style="{ left: `${hoverPosition}px` }">
            {{ formatTime(hoverTime) }}
          </div>

          <!-- 播放头 -->
          <div v-if="isAudioLoadedAndReady" class="playhead" :style="{ left: `${currentTime * timeToPixel}px` }">
            <div class="playhead-time">{{ formatTime(currentTime) }}</div>
          </div>

          <!-- 音频分割线 -->
          <div v-for="(time, index) in split_line_time" :key="`split-line-${index}`"
               class="split-line" :style="{ left: `${time * timeToPixel}px` }">
            <div class="split-line-handle"></div>
          </div>

          <!-- 标记删除区域的视觉覆盖层 -->
          <div v-for="(region, index) in deleted_regions" :key="`deleted-region-${index}`"
               class="deleted-region-overlay"
               :style="{ left: `${region.start * timeToPixel}px`, width: `${(region.end - region.start) * timeToPixel}px` }">
          </div>
        </div>
      </div>
    </div>
  </div>
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
.editor-container {
  display: flex;
  height: 100vh;
  background-color: #1a1d24; /* 更深的背景色 */
  color: #abb2bf;
}

/* 新增或修改的样式 */
.waveform-controls {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-bottom: 10px;
}

.time-display {
  font-size: 1rem;
  color: #e6c07b;
}

/* Waveform Canvas Container */
#waveform {
  width: 100%; /* This will be the visible window */
  height: 120px;
  background: #282c34;
  border-radius: 4px;
  margin-bottom: 10px;
  position: relative;
  overflow-x: auto; /* Enable horizontal scrolling */
  overflow-y: hidden;
  display: flex; /* To contain the canvas */
  align-items: center;
  transition: border-color 0.3s ease; /* Add transition for visual feedback */
}

/* 新增拖拽悬停样式 */
.waveform-display.is-dragging-over-waveform {
  border: 2px dashed #61afef; /* Highlight with a dashed border */
}

#waveformCanvas {
  /* The canvas itself will have its width set dynamically by Vue binding */
  height: 100%;
  display: block;
  /* Do not set width: 100% here, as it will stretch the canvas to the parent's width,
     instead of allowing it to be its calculated dynamic width. */
}

.waveform-display .waveform-bar {
  display: none;
}

.selection-overlay {
  display: none; /* WaveSurfer Regions Plugin handles this */
}

:deep(.ws-cursor) {
  background-color: #e6c07b !important; /* 播放头颜色 */
}

:deep(.ws-timeline) {
  color: #abb2bf !important;
}

:deep(.ws-minimap) {
  background-color: #1e222a !important;
}

:deep(.ws-minimap-wave) {
  background-color: #61afef !important;
}

:deep(.ws-minimap-progress) {
  background-color: #c678dd !important;
}

.waveform-display .waveform-bar {
  display: none;
}

.selection-overlay {
  display: none; /* WaveSurfer Regions Plugin handles this */
}

.file-panel {
  width: 280px;
  background: #1e222a;
  border-right: 1px solid #2c313a;
  padding: 16px;
  overflow-y: auto;
  flex-shrink: 0; /* 防止被压缩 */
}

.path-bar {
  display: flex;
  align-items: center;
  margin-bottom: 16px;
  padding: 8px;
  background: #282c34;
  border-radius: 4px;
}

.path-text {
  margin-left: 10px;
  font-size: 0.9rem;
  color: #61afef;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.file-list {
  margin-top: 12px;
}

.file-item {
  padding: 10px;
  display: grid;
  grid-template-columns: 24px 1fr auto;
  align-items: center;
  cursor: pointer;
  border-radius: 4px;
  transition: all 0.2s;
  margin-bottom: 6px;
}

.file-item:hover {
  background: rgba(97, 175, 239, 0.15);
}

/* Ensure disabled back button is visible */
.path-bar .v-btn[disabled] {
  opacity: 0.3 !important; /* Make it semi-transparent */
  pointer-events: none; /* Prevent clicks */
}

.file-item.is-dragging {
  background: rgba(198, 120, 221, 0.3);
  transform: scale(0.98);
  box-shadow: 0 0 8px rgba(198, 120, 221, 0.5);
}

.file-name {
  margin-left: 8px;
  font-size: 0.9rem;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.size {
  color: #5c6370;
  font-size: 0.8em;
  margin-left: 8px;
}

.editor-panel {
  flex: 1;
  display: flex;
  flex-direction: column;
  padding: 16px;
  overflow: hidden;
}

.toolbar {
  display: flex;
  gap: 16px;
  margin-bottom: 16px;
  align-items: center;
  padding: 10px;
  background: #1e222a;
  border-radius: 4px;
}


.zoom-slider {
  max-width: 200px;
  margin-left: 10px;
}

.time-ruler-container {
  overflow-x: hidden; 
  margin-bottom: 10px;
  border-bottom: 1px solid #2c313a;
  padding-bottom: 5px;
  background: #1e222a;
  border-radius: 4px;
  padding: 0 10px;
}

.time-ruler {
  display: flex;
  height: 30px;
  position: relative;
}

.time-marker {
  position: absolute;
  height: 100%;
  /* border-left: 1px solid #3e4451; */ /* Removed vertical line */
  font-size: 0.8em;
  color: #abb2bf;
  padding-left: 6px;
  top: 0;
  display: flex;
  align-items: center;
}

.tracks-container {
  flex-grow: 1;
  overflow-y: auto;
  margin-bottom: 20px;
  border: 1px solid #2c313a;
  border-radius: 4px;
  background-color: #1e222a;
  padding: 10px;
}

.audio-track {
  display: flex; /* Added for internal layout */
  background-color: #262b30; /* From test.vue */
  border-bottom: 1px solid #1a1e23; /* From test.vue */
  position: relative;
  min-height: 120px;
  margin-bottom: 10px;
  border-radius: 4px;
  /* Removed padding and box-shadow */
}

.audio-track:last-child {
  border-bottom: none;
}

.track-info-panel { /* Renamed from track-header */
  display: flex;
  flex-direction: column; /* Stack items vertically */
  align-items: center;
  gap: 8px; /* Adjusted gap */
  min-width: 78px; /* From test.vue .track-operations */
  background-color: #3B424A; /* From test.vue */
  border-right: 1px solid #2a2f35; /* From test.vue */
  padding: 10px 5px; /* Adjusted padding */
  color: #c678dd;
  flex-shrink: 0; /* Prevent shrinking */
}

.track-mixer-panel { /* New panel for sliders */
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 5px;
  min-width: 120px; /* Adjusted width for sliders */
  background-color: #3B424A; /* From test.vue */
  border-right: 1px solid #2a2f35; /* From test.vue */
  padding: 10px 5px;
  flex-shrink: 0;
}

.track-icon {
  margin-right: 5px;
}

.track-name {
  font-weight: 600;
  font-size: 0.95rem;
  text-align: center; /* Center the text within the span */
  width: 100%; /* Ensure it takes full width to center effectively */
}

.volume-slider, .pan-slider {
  max-width: 150px;
}

.track-clips {
  flex: 1; /* Allow it to grow and take available space */
  position: relative;
  overflow: auto; /* Enable scrolling if content overflows */
  background-color: #0C0E0F; /* From test.vue */
  background-image:   
    linear-gradient(90deg, #3C444C 0px, transparent 2px),  
    linear-gradient(0deg, #3C444C 0px, transparent 1px),  
    linear-gradient(90deg, #262B30 0px, transparent 1px),  
    linear-gradient(0deg, #262B30 0px, transparent 1px);  
  background-size:   
    128px 100%, /* Coarse grid: every 4 beats */  
    100% 32px,  
    32px 100%,  /* Fine grid: every beat */  
    100% 8px;
  border-radius: 4px;
  padding: 5px;
}

.audio-clip {
  position: absolute;
  top: 2px; /* From test.vue */
  height: 28px; /* From test.vue */
  background: linear-gradient(to bottom, #4a9eff 0%, #2d7dd2 100%); /* From test.vue */
  border: 1px solid #1a5490; /* From test.vue */
  border-radius: 3px; /* From test.vue */
  overflow: hidden;
  color: white;
  cursor: move;
  box-shadow: 0 2px 4px rgba(0,0,0,0.2); /* Adjusted for consistency */
  transition: transform 0.1s;
  user-select: none; /* From test.vue */
}

.audio-clip:hover {
  transform: translateY(-1px);
  box-shadow: 0 4px 8px rgba(0,0,0,0.4);
}


.clip-name {
  padding: 2px 6px; /* From test.vue */
  color: white;
  font-size: 10px; /* From test.vue */
  font-weight: bold; /* From test.vue */
  text-shadow: 1px 1px 1px rgba(0, 0, 0, 0.5); /* From test.vue */
  overflow: hidden;
  white-space: nowrap;
  text-overflow: ellipsis;
  position: static; /* Changed to static as padding handles positioning */
  max-width: 100%; /* Allow full width */
}

.clip-handle {
  position: absolute;
  top: 0;
  height: 100%;
  width: 4px; /* Slightly thinner */
  background: rgba(255,255,255,0.2); /* More subtle */
  cursor: col-resize;
}

.clip-handle.left {
  left: 0;
  border-top-left-radius: 4px;
  border-bottom-left-radius: 4px;
}

.clip-handle.right {
  right: 0;
  border-top-right-radius: 4px;
  border-bottom-right-radius: 4px;
}

.add-track {
  margin-top: 15px;
}

.main-waveform-section {
  padding: 15px;
  border: 1px solid #2c313a;
  border-radius: 4px;
  background-color: #1e222a;
}

.main-waveform-section h3 {
  margin-bottom: 12px;
  color: #e6c07b;
  display: flex;
  align-items: center;
  font-size: 1.1rem;
}

.waveform-controls {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-bottom: 10px;
}

.time-display {
  font-size: 1rem;
  color: #e6c07b;
}

/* WaveSurfer 容器样式 */
#waveform {
  width: 100%;
  height: 120px; /* 与原波形显示高度一致 */
  background: #282c34;
  border-radius: 4px;
  margin-bottom: 10px;
  position: relative; /* 确保内部元素定位正确 */
}

/* 覆盖 WaveSurfer 默认样式以匹配主题 */
:deep(.ws-wavesurfer) {
  background: #282c34 !important;
  border-radius: 4px;
}

:deep(.ws-region) {
  background-color: rgba(97, 175, 239, 0.25) !important;
  border: 2px solid #61afef !important;
  border-radius: 2px;
}

:deep(.ws-cursor) {
  background-color: #e6c07b !important; /* 播放头颜色 */
}

:deep(.ws-timeline) {
  color: #abb2bf !important;
}

:deep(.ws-minimap) {
  background-color: #1e222a !important;
}

:deep(.ws-minimap-wave) {
  background-color: #61afef !important;
}

:deep(.ws-minimap-progress) {
  background-color: #c678dd !important;
}

/* 移除旧的波形条样式，因为WaveSurfer会生成自己的 */
.waveform-display .waveform-bar {
  display: none;
}

.selection-overlay {
  display: none; /* WaveSurfer Regions Plugin handles this */
}

.selection-controls {
  display: flex;
  gap: 20px;
}
.zoom-slider {
  position: relative;
  width: 200px;
}
/* 悬停参考线 */
.hover-line {
  position: absolute;
  top: 0; /* Position relative to the top of the waveform container */
  bottom: 0;
  width: 1px;
  background: rgba(230, 192, 123, 0.7);
  pointer-events: none;
  z-index: 15;
  transform: translateX(-50%);
}

/* 波形悬停时间显示 */
.waveform-hover-time {
  position: absolute;
  top: 5px; /* Position relative to the top of the waveform container */
  transform: translateX(-50%);
  background: rgba(30, 34, 42, 0.85);
  color: #e6c07b; /* Use a distinct color, e.g., the playhead color */
  padding: 2px 8px;
  border-radius: 4px;
  font-size: 0.8rem;
  pointer-events: none;
  z-index: 20; /* Ensure it's above the hover line */
  white-space: nowrap;
  box-shadow: 0 2px 4px rgba(0, 0, 0, 0.3);
}

/* 悬停参考线 */
.hover-line {
  position: absolute;
  top: 0;
  bottom: 0;
  width: 1px;
  background: rgba(230, 192, 123, 0.7);
  pointer-events: none;
  z-index: 15;
  transform: translateX(-50%);
}

/* 确保波形容器有相对定位 */
.waveform-display {
  position: relative;
}
/* 标尺悬停时间 */
.ruler-hover-time {
  position: absolute;
  /* Position relative to the top of the waveform-display area */
  top: 5px; /* Adjust as needed to position it visually */
  transform: translateX(-50%);
  background: rgba(30, 34, 42, 0.85);
  color: #61afef;
  padding: 2px 8px;
  border-radius: 4px;
  font-size: 0.8rem;
  pointer-events: none;
  z-index: 20;
  white-space: nowrap;
  box-shadow: 0 2px 4px rgba(0, 0, 0, 0.3);
}
/* 播放头样式 */
.playhead {
  position: absolute;
  top: 0;
  bottom: 0;
  width: 2px;
  background: #e6c07b;
  z-index: 25;
  pointer-events: none;
}

.playhead::after {
  content: '';
  position: absolute;
  top: 0;
  left: -4px;
  width: 10px;
  height: 10px;
  background: #e6c07b;
  border-radius: 50%;
}

/* 播放头时间显示 */
.playhead-time {
  position: absolute;
  top: -25px;
  left: 50%;
  transform: translateX(-50%);
  background: rgba(30, 34, 42, 0.85);
  color: #e6c07b;
  padding: 2px 8px;
  border-radius: 4px;
  font-size: 0.8rem;
  pointer-events: none;
  z-index: 30;
  white-space: nowrap;
  box-shadow: 0 2px 4px rgba(0, 0, 0, 0.3);
}

/* 分割线样式 */
.split-line {
  position: absolute;
  top: 0;
  bottom: 0;
  width: 2px; /* 线的宽度 */
  background-color: #e06c75; /* 线的颜色，例如红色 */
  z-index: 18; /* 确保在波形之上，但在播放头之下 */
  pointer-events: none; /* 不响应鼠标事件 */
  transform: translateX(-50%); /* 使线居中于其left位置 */
}

.split-line-handle {
  position: absolute;
  top: 0;
  left: -4px; /* 使手柄居中于线 */
  width: 10px;
  height: 10px;
  background-color: #e06c75; /* 手柄颜色 */
  border-radius: 50%;
  pointer-events: all; /* 允许手柄响应鼠标事件 */
  cursor: grab;
}

/* 删除区域覆盖层样式 */
.deleted-region-overlay {
  position: absolute;
  top: 0;
  height: 100%;
  background-color: rgba(255, 0, 0, 0.3); /* 半透明红色 */
  z-index: 17; /* 在波形之上，分割线之下 */
  pointer-events: none; /* 不响应鼠标事件 */
  border-left: 1px dashed #ff0000;
  border-right: 1px dashed #ff0000;
}
</style>
