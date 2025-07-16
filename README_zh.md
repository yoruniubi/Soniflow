# Soniflow (中文版)

## 介绍

Soniflow 是一款功能全面的桌面应用程序，旨在将各种音频和视频处理任务整合到同一个软件中，方便用户获取不同音频素材，无需打开多个软件，可用于语音克隆或作为视频素材。它集成了从 Bilibili 和 YouTube 等流行平台搜索和下载视频的功能，支持人声与背景音乐分离，并提供基本的音频编辑能力。该应用程序拥有一个基于 Vue.js 构建的用户友好型图形界面和 Python 后端，使其对普通用户和内容创作者都易于使用。

## 功能特性

Soniflow 提供以下主要功能：

1.  **视频搜索与下载**:
    *   通过关键词在 Bilibili 和 YouTube 上搜索视频。
    *   从这两个平台下载单个视频。
    *   支持下载整个 YouTube 播放列表。
    *   能够查看 Bilibili 视频合集。

2.  **人声与背景音乐分离**:
    *   利用 Spleeter 将音频分离成不同音轨（例如，人声、伴奏、鼓、贝斯、钢琴）。
    *   支持 2-stem、4-stem 和 5-stem 分离模型。
    *   允许选择输出格式和音频质量。

3.  **音频编辑**:
    *   加载和处理音频文件（MP3、WAV、OGG）。
    *   生成波形可视化，便于编辑。
    *   执行音频分割、标记删除区域和导出处理后的音频等操作。
    *   支持音频编辑的撤销/重做功能。
    *   直接在应用程序内录制音频。

4.  **格式转换**:
    *   在各种音频格式（MP3、WAV、OGG）之间进行转换。
    *   从视频文件中提取音频。
    *   转换视频格式。

5.  **应用设置**:
    *   配置默认输出目录。
    *   管理 Bilibili 和 YouTube 的 Cookies，以增强下载能力。
    *   选择界面语言（简体中文、英文）。

## 开发环境搭建
首先，克隆本项目：

```bash
git clone https://github.com/yoruniubi/Soniflow.git
```

然后，请先从release中下载pretrained_models，放到和Gui.py同一级目录下，然后再创建一个叫做ffmpeg的文件夹，下载ffmpeg full build 版本
并且将bin文件里面的所有exe文件复制到ffmpeg文件夹下
下载链接：https://www.gyan.dev/ffmpeg/builds/

后端部分：

建议使用 Anaconda 创建虚拟环境：

```bash
conda create -n Soniflow python=3.10.16
```
```bash
conda activate Soniflow
```
```bash
pip install -r requirements.txt
```

前端部分：

```bash
cd ./ui_interface
npm install # 安装前端依赖
npm run dev # 用于开发模式，或 npm run build 用于生产构建
```

在前端构建完成后（或在开发模式下运行 `npm run dev`），即可运行后端：

```bash
python Gui.py
```

## 使用说明

应用程序启动后，您可以通过侧边栏导航到不同的功能：
*   **视频搜索**: 使用搜索选项卡查找和下载视频。
*   **格式转换**: 将音频/视频文件转换为不同的格式。
*   **人声分离**: 将人声从伴奏中分离出来。
*   **音频编辑**: 加载音频，执行编辑，并导出结果。
*   **设置**: 自定义应用程序偏好。
