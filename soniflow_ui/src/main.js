import { createApp } from 'vue'
import App from './App.vue'
import vuetify from './plugins/vuetify'
import { loadFonts } from './plugins/webfontloader'
import router from './router'
import { createI18n } from 'vue-i18n'
import messages from './locales'

loadFonts();

// 初始化 i18n，默认语言依然是中文，但它会被马上覆盖
const i18n = createI18n({
  legacy: false,
  locale: 'zh-CN',
  fallbackLocale: 'en-US',
  messages,
});

const app = createApp(App);

app.use(vuetify);
app.use(router);
app.use(i18n);

// **关键步骤 1: 启用并强化等待 API 的函数**
// 这个函数会一直等待，直到 window.pywebview.api 可用
function waitForPywebviewApi() {
  return new Promise(resolve => {
    const checkApi = () => {
      // 检查 api 对象和我们需要的 get_settings 函数是否都已准备好
      if (window.pywebview && window.pywebview.api && window.pywebview.api.get_settings) {
        console.log("pywebview API is ready.");
        resolve(window.pywebview.api);
      } else {
        // 如果还没好，请求浏览器在下一次重绘前再次检查，这比 setInterval 性能更好
        requestAnimationFrame(checkApi);
      }
    };
    checkApi();
  });
}

// **关键步骤 2: 修改 initApp 函数，先等待 API，再执行后续操作**
async function initApp() {
  try {
    // 等待 pywebview API 完全加载
    const api = await waitForPywebviewApi();
    app.config.globalProperties.$api = api;

    // 现在我们确定 api.get_settings 存在，可以安全调用
    console.log("Fetching settings from pywebview...");
    const response = await api.get_settings();
    console.log("Settings received:", response); // 打印收到的设置，方便调试

    if (response && response.success && response.settings.language) {
      const savedLanguage = response.settings.language;
      console.log(`Setting language to: ${savedLanguage}`);
      i18n.global.locale.value = savedLanguage;
    } else {
      console.log("No language setting found or request failed. Using default.");
    }

  } catch (error) {
    // 这个 catch 块现在主要处理在浏览器中直接打开（没有pywebview环境）的情况
    console.error('pywebview API not found or failed to fetch settings. Running in browser mode.', error);
    app.config.globalProperties.$api = {}; // 提供一个空的 api 对象
  } finally {
    // **关键步骤 3: 确保所有异步操作完成后再挂载应用**
    console.log("Mounting Vue app...");
    app.mount('#app');
  }
}

initApp();