# Soniflow

## Introduction

Soniflow is a comprehensive desktop application designed to streamline various audio and video processing tasks within a single software. It eliminates the need for multiple applications to obtain different audio materials, making it convenient for tasks such as voice cloning or preparing video assets. It combines functionalities for searching and downloading videos from popular platforms like Bilibili and YouTube, performing vocal and background music separation, and offering basic audio editing capabilities. The application features a user-friendly graphical interface built with Vue.js and a Python backend, making it accessible for both casual users and content creators.

## Features

Soniflow provides the following key features:

1.  **Video Search & Download**:
    *   Search for videos on Bilibili and YouTube using keywords.
    *   Download individual videos from both platforms.
    *   Support for downloading entire YouTube playlists.
    *   Ability to check Bilibili video collections.

2.  **Vocal and Background Music Separation**:
    *   Utilizes Spleeter to separate audio into different stems (e.g., vocals, accompaniment, drums, bass, piano).
    *   Supports 2-stem, 4-stem, and 5-stem separation models.
    *   Allows selection of output format and audio quality.

3.  **Audio Editing**:
    *   Load and process audio files (MP3, WAV, OGG).
    *   Generate waveform visualizations for easy editing.
    *   Perform operations like splitting audio, marking regions for deletion, and exporting processed audio.
    *   Undo/Redo functionality for audio edits.
    *   Record audio directly within the application.

4.  **Format Conversion**:
    *   Convert between various audio formats (MP3, WAV, OGG).
    *   From video files, extract audio.
    *   Convert video formats.

5.  **Application Settings**:
    *   Configure default output directories.
    *   Manage Bilibili and YouTube cookies for enhanced download capabilities.
    *   Select interface language (Simplified Chinese, English).

## Development

First of all, clone this project:

```bash
git clone https://github.com/yoruniubi/Soniflow.git
```
First, please download the pretrained_models from the releases section and place them in the same directory as Gui.py.

Next, create a folder named ffmpeg. Download the FFmpeg full build version from the following link:
Download link: https://www.gyan.dev/ffmpeg/builds/

Finally, copy all the .exe files from the downloaded bin folder into the ffmpeg folder you just created.
For the backend:

It is recommended to use Anaconda to create the virtual environment:

```bash
conda create -n Soniflow python=3.10.16
```
```bash
conda activate Soniflow
```
```bash
pip install -r requirements.txt
```

And then for the frontend:

```bash
cd ./ui_interface
npm install # Install frontend dependencies
npm run dev # For development, or npm run build for production build
```

After building the frontend (or running `npm run dev` for development), you can run the backend:

```bash
python Gui.py
```

## Usage

Once the application is running, you can navigate through the different features using the sidebar.
*   **Video Search**: Use the search tab to find and download videos.
*   **Format Convert**: Convert audio/video files to different formats.
*   **Vocal Separation**: Separate vocals from instrumental tracks.
*   **Audio Editing**: Load audio, perform edits, and export the results.
*   **Settings**: Customize application preferences.

## Quick start

Download the setup program from the release page directly.
