import multiprocessing
import sys
from PIL import Image
from pystray import Icon, Menu, MenuItem
import os
import webview
import logging
import time
import base64
import ctypes
from editor import AudioProcessor
import aiohttp
import time 
import asyncio
import threading
from flask import Flask, send_from_directory
from flask_cors import CORS 
from pydub import AudioSegment
import shutil
from form_transformation import extract_audio_from_video, convert_audio_format, convert_video_format
from http.server import SimpleHTTPRequestHandler, HTTPServer
from configs import config_manager
from pathlib import Path # Added for UPLOADS_DIR
# Removed: from concurrent.futures import ThreadPoolExecutor
if sys.platform == 'win32':
    # Windows深色模式常量
    DWMWA_USE_IMMERSIVE_DARK_MODE = 20
# Configure logging
logging.basicConfig(level=logging.DEBUG, 
                    format='%(asctime)s - %(levelname)s - %(message)s',
                    handlers=[logging.StreamHandler()])
# from spleeter_part import spleeter_part
from research_videos import BiliVideoDownloader, YoutubeDownloader
if sys.platform == 'darwin':
    ctx = multiprocessing.get_context('spawn')
    Process = ctx.Process
    Queue = ctx.Queue
else:
    Process = multiprocessing.Process
    Queue = multiprocessing.Queue

# Define UPLOADS_DIR globally
UPLOADS_DIR = Path(__file__).parent / "uploads"
UPLOADS_DIR.mkdir(parents=True, exist_ok=True) # Ensure the directory exists

webview_process = None

# 新建flask服务器
app_flask = Flask(__name__)
app_flask.config['UPLOAD_FOLDER'] = os.path.join(os.path.dirname(__file__), 'uploads')
# 设置静态文件路由
@app_flask.route('/audio/<path:filename>')
def get_audio(filename):
    return send_from_directory(app_flask.config['UPLOAD_FOLDER'], filename)
CORS(app_flask)
def run_flask_app():
    app_flask.run(host='0.0.0.0', port=5000, threaded=True)

class Api:
    def __init__(self):
        self.Bili_downloader = BiliVideoDownloader()
        self.youtube_downloader = YoutubeDownloader()
        # self.spl = spleeter_part()
        self.upload_dir = os.path.join(os.path.dirname(__file__), 'uploads')
        if not os.path.exists(self.upload_dir):
            os.makedirs(self.upload_dir)
        self.preview_cache = {}
        # 用于追踪spl进程
        self.spl_process = None
        self.spl_queue = Queue()  # 新增进程通信队列
        # 新增黑暗模式追踪
        self.dark_mode = False
        # 初始化音频处理器
        self.audio_processor = AudioProcessor()
        self.temp_audio_dir = os.path.join(os.path.dirname(__file__), 'temp_audio')
        os.makedirs(self.temp_audio_dir, exist_ok=True)
        logging.info("Api class initialized.")
        self.path_separator = os.sep # Expose path separator for frontend

        # Load initial settings using ConfigManager
        self.default_output_dir = config_manager.get('defaultOutput', os.path.join(os.getcwd(), 'output'))
        logging.info(f"Initial default output directory: {self.default_output_dir}")
    
    def get_settings(self):
        """API to get current application settings."""
        try:
            # Return the current config from ConfigManager
            return {"success": True, "settings": config_manager.config}
        except Exception as e:
            logging.error(f"Failed to get settings: {str(e)}", exc_info=True)
            return {"success": False, "error": str(e)}

    def save_app_settings(self, settings_data):
        """API to save application settings."""
        try:
            # Update settings using ConfigManager
            for key, value in settings_data.items():
                config_manager.set(key, value)
            
            # Update the internal default_output_dir immediately
            self.default_output_dir = config_manager.get('defaultOutput', os.path.join(os.getcwd(), 'output'))
            logging.info(f"Settings saved. New default output directory: {self.default_output_dir}")
            return {"success": True}
        except Exception as e:
            logging.error(f"Failed to save settings: {str(e)}", exc_info=True)
            return {"success": False, "error": str(e)}

    def get_current_audio_url(self):
        """
        导出当前处理器的音频到临时文件并返回其URL
        """
        try:
            if not self.audio_processor.audio:
                return {"success": False, "error": "没有加载音频"}
            
            temp_filename = f"current_audio_{int(time.time())}.mp3"
            temp_path = os.path.join(self.temp_audio_dir, temp_filename)
            
            self.audio_processor.export(temp_path)
            
            # 返回由Flask服务器提供的URL
            url_filename = temp_filename.replace('\\', '/')
            return {'success': True, 'url': f'http://localhost:5000/audio/{url_filename}'}
        except Exception as e:
            logging.error(f"获取当前音频URL失败: {str(e)}", exc_info=True)
            return {"success": False, "error": str(e)}

    def list_directory(self, path=None):
        try:
            path = path or os.path.expanduser("~")
            items = []
            for item in os.listdir(path):
                full_path = os.path.join(path, item)
                items.append({
                    "name": item,
                    "path": full_path,
                    "is_dir": os.path.isdir(full_path),
                    "size": os.path.getsize(full_path) if not os.path.isdir(full_path) else 0
                })
            return {"success": True, "path": path, "items": items}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def save_recorded_audio(self, data):
        try:
            base64_data = data.get('base64_data')
            file_name = data.get('file_name')
            frontend_duration = data.get('duration', 0)  # 获取前端传递的时长

            # 确保上传目录存在
            os.makedirs(self.upload_dir, exist_ok=True)
            save_path = os.path.join(self.upload_dir, file_name)
            
            # 保存文件
            file_bytes = base64.b64decode(base64_data)
            with open(save_path, 'wb') as f:
                f.write(file_bytes)

            # 使用前端提供的时长（如果有效）
            duration = frontend_duration if frontend_duration > 0 else 0
            
            # 如果前端没提供时长，尝试用pydub获取
            if duration <= 0:
                try:
                    from pydub import AudioSegment
                    audio = AudioSegment.from_file(save_path)
                    duration = len(audio) / 1000.0  # 毫秒转秒
                except Exception as e:
                    logging.error(f"Pydub failed to read audio file {save_path}: {e}", exc_info=True)
                    duration = 0
            
                
            return {
                "success": True,
                "path": save_path,
                "name": file_name,
                "duration": duration
            }
        except Exception as e:
            return {"success": False, "error": str(e)}

    def upload_file_stream(self, file_object):
        """
        Receives a File object from the frontend and saves it to the uploads directory.
        This function will now block until the file is saved.
        """
        try:
            logging.debug(f"Received file_object type: {type(file_object)}")
            if not isinstance(file_object, dict):
                raise TypeError("Expected file_object to be a dictionary.")
            
            logging.debug(f"Received file_object keys: {file_object.keys()}")
            
            file_name = file_object.get('name')
            base64_data = file_object.get('base64_data')

            if not file_name:
                raise ValueError("File name not found in file_object.")
            if not base64_data:
                raise ValueError("Base64 data not found in file_object.")

            save_path = UPLOADS_DIR / file_name
            
            # Decode base64 data and write to file
            file_bytes = base64.b64decode(base64_data)
            with open(save_path, 'wb') as f:
                f.write(file_bytes)
            
            print(f"File saved successfully to: {save_path}")
            return {"success": True, "path": str(save_path), "name": file_name}
        except Exception as e:
            print(f"Error saving file: {e}")
            return {"success": False, "error": str(e)}

    # _write_file_chunks is no longer needed as we write the whole file at once from base64
    # def _write_file_chunks(self, file_stream, save_path):
    #     """Helper function to write file chunks (blocking I/O)."""
    #     with open(save_path, 'wb') as f:
    #         while True:
    #             chunk = file_stream.read(4096) # Read 4KB chunks
    #             if not chunk:
    #                 break
    #             f.write(chunk)

    def generate_waveform(self, file_path, resolution=800): # Adjusted default resolution to match editor.py
        """生成波形数据"""
        try:
            # Use the updated generate_waveform that loads from path directly
            waveform = self.audio_processor.generate_waveform(audio_path=file_path, width=resolution)
            if "error" in waveform:
                 return {"success": False, "error": waveform["error"]}
            return {
                "success": True,
                "data": waveform["waveform"],
                "duration": waveform["duration"]
            }
        except Exception as e:
            logging.error(f"生成波形失败: {str(e)}", exc_info=True)
            return {"success": False, "error": str(e)}
    def get_audio_url(self, filename):
        """获取正确的音频文件 URL"""
        # 确保文件名是安全的
        safe_filename = os.path.basename(filename)
        audio_path = os.path.join(self.upload_dir, safe_filename)
        
        # 检查文件是否存在
        if not os.path.exists(audio_path):
            return {'success': False, 'error': '文件不存在'}
        
        # 返回相对路径（前端会通过代理访问）
        return {'success': True, 'url': f'/audio/{safe_filename}'}
    def get_local_file_url(self, file_path):
        """获取本地文件的正确 URL（由 Flask 服务器提供）"""
        try:
            # Get absolute and normalized paths for both source and upload directory
            source_abs_path = os.path.normpath(os.path.abspath(file_path))
            upload_abs_dir = os.path.normpath(os.path.abspath(self.upload_dir))

            # Get the target path within the upload directory
            target_abs_path = os.path.join(upload_abs_dir, os.path.basename(source_abs_path))
            target_abs_path = os.path.normpath(target_abs_path)

            # Check if the source file is the same as the target file in the upload directory
            # Use os.path.samefile for a robust check across different path representations
            is_same_file = False
            logging.debug(f"Comparing source: {source_abs_path} (exists: {os.path.exists(source_abs_path)})")
            logging.debug(f"Comparing target: {target_abs_path} (exists: {os.path.exists(target_abs_path)})")
            try:
                # Check if both paths exist before calling samefile
                if os.path.exists(source_abs_path) and os.path.exists(target_abs_path):
                     is_same_file = os.path.samefile(source_abs_path, target_abs_path)
                # If target_abs_path doesn't exist, they can't be the same file, is_same_file remains False
            except Exception as e:
                # Handle other potential exceptions from os.path.samefile
                logging.warning(f"Error checking if files are the same using os.path.samefile: {e}")
                is_same_file = False # Assume not the same file on error

            final_file_path_to_use = target_abs_path # Assume the file should end up here

            if not is_same_file:
                logging.info(f"File {source_abs_path} is not the same as target {target_abs_path}. Copying.")
                # 复制文件
                shutil.copy2(source_abs_path, target_abs_path)
                logging.info(f"File copied to {final_file_path_to_use}")
            else:
                logging.info(f"File {source_abs_path} is already the same as target {target_abs_path}. Skipping copy.")
                # final_file_path_to_use is already set to target_abs_path

            # Check if the final file exists at the expected location
            if not os.path.exists(final_file_path_to_use):
                logging.error(f"File does not exist at final path: {final_file_path_to_use}")
                return {'success': False, 'error': '文件不存在'}

            filename = os.path.basename(final_file_path_to_use)

            # 返回URL
            url_filename = filename.replace('\\', '/')
            return {'success': True, 'url': f'http://localhost:5000/audio/{url_filename}'}

        except Exception as e:
            logging.exception(f"获取本地文件URL失败: {str(e)}")
            return {'success': False, 'error': str(e)}
    # 音频处理功能
    def load_audio(self, file_path):
        try:
            self.audio_processor.load_from_file(file_path)
            logging.debug(f"加载音频成功: {file_path}")
            return {"success": True, "info": self.audio_processor.get_current_info()}
        except Exception as e:
            return {"success": False, "error": str(e)}

    # def clip_audio(self, start, end):
    #     try:
    #         self.audio_processor.clip(start, end)
    #         return {"success": True, "info": self.audio_processor.get_current_info()}
    #     except Exception as e:
    #         return {"success": False, "error": str(e)}

    def export_audio(self, output_path):
        try:
            self.audio_processor.export(output_path)
            return {"success": True, "path": output_path}
        except Exception as e:
            return {"success": False, "error": str(e)}

    # def copy_audio_selection(self, start, end):
    #     """
    #     复制选定区域的音频到剪贴板
    #     """
    #     try:
    #         self.audio_processor.copy_selection(start, end)
    #         return {"success": True, "state": self.audio_processor.get_history_state()}
    #     except Exception as e:
    #         logging.error(f"复制音频选区失败: {str(e)}", exc_info=True)
    #         return {"success": False, "error": str(e)}

    # def paste_audio_selection(self, target_time):
    #     """
    #     将剪贴板中的音频粘贴到指定时间点
    #     """
    #     try:
    #         self.audio_processor.paste_selection(target_time)
    #         return {"success": True, "info": self.audio_processor.get_current_info(), "state": self.audio_processor.get_history_state()}
    #     except Exception as e:
    #         logging.error(f"粘贴音频选区失败: {str(e)}", exc_info=True)
    #         return {"success": False, "error": str(e)}

    def undo_audio(self):
        """
        撤销音频操作
        """
        try:
            success = self.audio_processor.undo()
            if success:
                return {"success": True, "info": self.audio_processor.get_current_info(), "state": self.audio_processor.get_history_state()}
            else:
                return {"success": False, "error": "无法撤销"}
        except Exception as e:
            logging.error(f"撤销音频操作失败: {str(e)}", exc_info=True)
            return {"success": False, "error": str(e)}

    def redo_audio(self):
        """
        重做音频操作
        """
        try:
            success = self.audio_processor.redo()
            if success:
                return {"success": True, "info": self.audio_processor.get_current_info(), "state": self.audio_processor.get_history_state()}
            else:
                return {"success": False, "error": "无法重做"}
        except Exception as e:
            logging.error(f"重做音频操作失败: {str(e)}", exc_info=True)
            return {"success": False, "error": str(e)}

    
    def get_audio_history_state(self):
        """
        获取音频历史状态（可撤销/重做，是否有剪贴板内容）
        """
        try:
            state = self.audio_processor.get_history_state()
            return {"success": True, "state": state}
        except Exception as e:
            logging.error(f"获取音频历史状态失败: {str(e)}", exc_info=True)
            return {"success": False, "error": str(e)}


    def process_and_export_audio(self, split_times, deleted_regions, output_filename=None):
        """
        根据分割线和删除区域处理音频并导出
        :param split_times: 分割时间点列表 (秒)
        :param deleted_regions: 删除区域列表 [{start: 秒, end: 秒}]
        :param output_filename: 导出文件名 (可选)。如果未提供，将打开保存文件对话框。
        :return: 成功/失败状态和导出路径
        """
        try:
            if not self.audio_processor.audio:
                logging.warning("没有加载音频，无法处理和导出。")
                return {"success": False, "error": "没有加载音频"}

            final_output_path = output_filename
            # Open save file dialog if output_filename is not provided or is an empty string
            if not final_output_path:
                dialog_result = self.open_save_file_dialog(default_filename="processed_audio.mp3")
                if dialog_result["success"]:
                    final_output_path = dialog_result["path"]
                    logging.debug(f"process_and_export_audio: final_output_path after dialog = '{final_output_path}'")
                else:
                    return {"success": False, "error": dialog_result["error"]}

            output_dir = os.path.dirname(final_output_path)
            if not output_dir: # If output_dir is empty, it means the file is in the current directory
                output_dir = os.getcwd()
            
            # Ensure the output directory exists for the chosen path
            os.makedirs(output_dir, exist_ok=True)

            # Store current state before processing for history
            self.audio_processor._add_to_history() # Add current state before modification

            original_audio = self.audio_processor.audio # Work on the current audio state

            # 1. Combine all significant time points
            time_points = [0] + split_times + [original_audio.duration_seconds]
            
            # Add start and end points of deleted regions
            for region in deleted_regions:
                time_points.append(region['start'])
                time_points.append(region['end'])

            # Sort and remove duplicates
            time_points = sorted(list(set(time_points)))
            
            logging.debug(f"处理时间点: {time_points}")
            logging.debug(f"删除区域: {deleted_regions}")

            processed_audio = AudioSegment.empty()

            # 2. Iterate through segments defined by time points
            for i in range(len(time_points) - 1):
                start_time = time_points[i]
                end_time = time_points[i+1]

                # Convert to milliseconds
                start_ms = int(start_time * 1000)
                end_ms = int(end_time * 1000)

                # Check if this segment overlaps with any deleted region
                is_deleted = False
                for region in deleted_regions:
                    region_start_ms = int(region['start'] * 1000)
                    region_end_ms = int(region['end'] * 1000)
                    
                    # Check for overlap: max(seg_start, reg_start) < min(seg_end, reg_end)
                    if max(start_ms, region_start_ms) < min(end_ms, region_end_ms):
                        is_deleted = True
                        logging.debug(f"Segment [{start_time:.2f}s - {end_time:.2f}s] overlaps with deleted region [{region['start']:.2f}s - {region['end']:.2f}s]. Skipping.")
                        break # No need to check other deleted regions for this segment

                # If the segment is not deleted, append it to the processed audio
                if not is_deleted:
                    segment = original_audio[start_ms:end_ms]
                    processed_audio += segment
                    logging.debug(f"Segment [{start_time:.2f}s - {end_time:.2f}s] kept.")

            # 3. Update the audio processor's current audio
            self.audio_processor.audio = processed_audio
            self.audio_processor._update_original_info() # Update info based on new audio
            logging.debug(f"Attempting to export to: {final_output_path}")
            self.audio_processor.export(final_output_path)

            logging.info(f"音频处理和导出成功: {final_output_path}")
            return {
                "success": True,
                "path": final_output_path,
                "info": self.audio_processor.get_current_info(), # Return info of the processed audio
                "state": self.audio_processor.get_history_state() # Return updated history state
            }

        except Exception as e:
            logging.error(f"音频处理和导出失败: {str(e)}", exc_info=True)
            return {"success": False, "error": str(e)}

    def search_videos(self, keyword, platform, page=1, per_page=20):
        # Run the asynchronous search function
        return asyncio.run(self._search_videos_sync(keyword, platform, page, per_page))
    
    async def _search_videos_sync(self, keyword, platform, page=1, per_page=20):
        start_time = time.time()
        if platform == 'bilibili':
            logging.debug(f"Searching videos with keyword: {keyword}")
            # Bili_downloader.search_videos is still synchronous, so run it in a thread pool
            loop = asyncio.get_running_loop()
            bvids, titles, total = await loop.run_in_executor(
                None, self.Bili_downloader.search_videos, keyword, page, per_page
            )
            
            # Prepare tasks for fetching video info and cover images concurrently
            video_info_tasks = [self._get_video_info(bvid) for bvid in bvids]
            video_infos = await asyncio.gather(*video_info_tasks)
            
            image_proxy_tasks = []
            for video_info in video_infos:
                if video_info and video_info.get('pic'):
                    image_proxy_tasks.append(self.get_image_proxy(video_info['pic']))
                else:
                    image_proxy_tasks.append(asyncio.sleep(0, result='')) # Placeholder for missing pic or failed video_info

            cover_datas = await asyncio.gather(*image_proxy_tasks)

            results = []
            for idx, bvid in enumerate(bvids):
                video_info = video_infos[idx]
                cover_data = cover_datas[idx]
                
                results.append({
                    'bvid': bvid,
                    'title': video_info.get('title', titles[idx]) if video_info else titles[idx],
                    'url': f"https://www.bilibili.com/video/{bvid}",
                    'pic': f"data:image/jpeg;base64,{cover_data}" if cover_data else '',
                    'author': video_info.get('owner', {}).get('name', '未知UP主') if video_info else '未知UP主',
                    'duration': video_info.get('duration', '未知时长') if video_info else '未知时长',
                })
            # logging.debug(f"Search results: {results}")
            print(
                f"搜索耗时: {time.time() - start_time:.2f}s | "
                f"关键词: {keyword} | 平台: {platform} | 页数: {page}"
            )
            total_pages = min((total + per_page - 1) // per_page, 15)
            return {
                'items': results,
                'total_pages': total_pages
            }
        elif platform == 'youtube':
            start_time = time.time()
            logging.debug(f"Searching YouTube videos with keyword: {keyword}")
            loop = asyncio.get_running_loop()
            # 使用线程池执行同步的搜索方法，并传递分页参数
            videos, total_results = await loop.run_in_executor(
                None, 
                self.youtube_downloader.search_videos, 
                keyword,
                page,
                per_page
            )
            results = []
            for video in videos:
                results.append({
                    'bvid': video['id'],
                    'title': video['title'],
                    'url': f"https://www.youtube.com/watch?v={video['id']}",
                    'pic':f"https://img.youtube.com/vi/{video['id']}/mqdefault.jpg",
                    'author': video.get('author', '未知UP主'),
                    'duration': video.get('duration', '未知时长'),
                })
            print(
                f"搜索耗时: {time.time() - start_time:.2f}s | "
                f"关键词: {keyword} | 平台: {platform} | 页数: {page}"
            )
            logging.debug(f"YouTube search results: {results}")
            # yt-dlp does not provide the total number of search results,
            # so we cannot calculate the exact number of pages.
            # We will return a fixed number of pages and let the frontend handle empty results.
            total_pages = 10
            return {
                'items': results,
                'total_pages': total_pages
            }
    async def _get_video_preview_async(self, bvid):
        try:
            if bvid not in self.preview_cache:
                loop = asyncio.get_running_loop()
                # Bili_downloader.get_playinfo is synchronous, run in executor
                video_info = await loop.run_in_executor(
                    None, self.Bili_downloader.get_playinfo, f"https://www.bilibili.com/video/{bvid}"
                )
                
                if not video_info or 'data' not in video_info:
                    return {'error': '无法获取视频信息'}

                # 提取视频流直链（示例逻辑，需根据B站API实际返回调整）
                dash = video_info['data'].get('dash', {})
                video_urls = [
                    video.get('baseUrl') 
                    for video in dash.get('video', []) 
                    if video.get('baseUrl')
                ]
                # 选择第一个可用视频地址（可能需鉴权）
                direct_url = video_urls[0] if video_urls else ''

                # 获取元数据 (now an async call)
                detail_info = await self._get_video_info(bvid)
                # logging.debug(f"获取视频预览信息: {detail_info}")
                
                self.preview_cache[bvid] = {
                    'title': detail_info.get('title', '无标题'),
                    'direct_url': direct_url,  # 直接播放的URL
                    'author': detail_info.get('owner', {}).get('name', '未知UP主'),
                    'cover': detail_info.get('pic', ''),
                    'embed_url': f"https://player.bilibili.com/player.html?bvid={bvid}"
                }
            return self.preview_cache[bvid]
        except Exception as e:
            logging.exception(f"获取预览失败: {str(e)}")
            return {'error': '解析视频地址失败'}

    def get_video_preview(self, bvid):
        return asyncio.run(self._get_video_preview_async(bvid))

    def download_video(self, bvid, title):
        """同步方法：下载B站视频"""
        async def _download_task():
            try:
                # 获取视频信息
                video_info = await self._get_video_info(bvid)
                if not video_info:
                    logging.error(f"无法获取视频信息: {bvid}")
                    return
                    
                # 获取播放信息
                loop = asyncio.get_running_loop()
                play_info = await loop.run_in_executor(
                    None, 
                    self.Bili_downloader.get_playinfo, 
                    f"https://www.bilibili.com/video/{bvid}"
                )
                
                if play_info:
                    # 下载视频
                    await loop.run_in_executor(
                        None, 
                        self.Bili_downloader.download_video, 
                        play_info, 
                        title
                    )
                    return {"success": True,"title": title}
                return {"success": False, "error": "无法获取播放信息"}
            except Exception as e:
                logging.exception(f"下载失败: {str(e)}")
                return {"success": False, "error": str(e)}

        # 在事件循环中运行异步任务
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                # 如果事件循环已在运行，创建新任务
                task = loop.create_task(_download_task())
                return {"status": "started", "bvid": bvid}
            else:
                # 直接运行异步任务
                result = loop.run_until_complete(_download_task())
                return result
        except RuntimeError as e:
            # 处理没有事件循环的情况
            result = asyncio.run(_download_task())
            return result
    def download_youtube_video(self, video_url,video_title):
        """异步下载YouTube视频"""
        async def _download_task():
            try:
                loop = asyncio.get_running_loop()
                await loop.run_in_executor(
                    None, 
                    self.youtube_downloader.download_video, 
                    video_url
                )
                return {"success": True,"title":video_title}
            except Exception as e:
                logging.exception(f"YouTube下载失败: {str(e)}")
                return {"success": False, "error": str(e)}
        
        # 在事件循环中运行异步任务
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                loop.create_task(_download_task())
                return {"status": "started", "video_url": video_url}
            else:
                result = loop.run_until_complete(_download_task())
                return result
        except RuntimeError:
            result = asyncio.run(_download_task())
            return result

    def check_if_playlist(self, url):
        """检查YouTube链接是否为播放列表"""
        try:
            # This is a synchronous method in the backend, so no async/await needed here.
            is_playlist, title, playlist_url = self.youtube_downloader.check_if_playlist(url)
            return is_playlist, title, playlist_url
        except Exception as e:
            logging.error(f"检查播放列表失败: {e}", exc_info=True)
            return False, None, None

    def download_playlist(self, playlist_url):
        """异步下载YouTube播放列表"""
        async def _download_task():
            try:
                loop = asyncio.get_running_loop()
                await loop.run_in_executor(
                    None,
                    self.youtube_downloader.download_playlist,
                    playlist_url
                )
                return {"success": True}
            except Exception as e:
                logging.exception(f"YouTube播放列表下载失败: {str(e)}")
                return {"success": False, "error": str(e)}

        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                loop.create_task(_download_task())
                return {"status": "started", "playlist_url": playlist_url}
            else:
                result = loop.run_until_complete(_download_task())
                return result
        except RuntimeError:
            result = asyncio.run(_download_task())
            return result
            
    def get_collection_videos(self, mid, season_id):
        data = self.Bili_downloader.get_collection_videos(mid, season_id, page_num=1, page_size=50)
        if not data or not data.get('success'):
            return {'success': False, 'error': data.get('error', '无法获取收藏夹视频信息')}
        results = []
        for video in data.get('items', []):
            results.append({
                'bvid': video.get('bvid'),
                'title': video.get('title'),
                'cover': video.get('cover'),
                'duration': video.get('duration'),
                'author': video.get('author')
            })
    
        return {'success': True, 'items': results}
        
    async def _get_image_proxy_sync(self, url):
        try:
            headers = {
                'Referer': 'https://www.bilibili.com/',
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
            }
            async with aiohttp.ClientSession(headers=headers) as session:
                async with session.get(url, timeout=10) as response:
                    response.raise_for_status()
                    content = await response.read()
                    return base64.b64encode(content).decode('utf-8')
        except aiohttp.ClientError as e:
            logging.error(f"图片代理失败: {str(e)}")
            return None
        except asyncio.TimeoutError:
            logging.error(f"图片代理超时: {url}")
            return None

    def get_image_proxy(self, url):
        # This function is now a simple wrapper for the async function
        return self._get_image_proxy_sync(url)
    def process_audio(self, number, input_filename, output_directory, codec, bitrate):
        """使用子进程处理音频"""
        try:
            # 验证输入参数
            if number not in [2, 4, 5]:
                raise ValueError("无效的分离模型类型")

            # 构建完整输入路径
            input_path = os.path.join(self.upload_dir, input_filename)
            if not os.path.exists(input_path):
                raise FileNotFoundError("音频文件不存在")

            # 创建并启动子进程
            self.spl_process = Process(
                target=self._run_spleeter_in_subprocess,
                args=(number, input_path, output_directory, codec, bitrate)
            )
            self.spl_process.start()
            self.spl_process.join()  # 等待子进程完成

            # 获取处理结果
            if not self.spl_queue.empty():
                result = self.spl_queue.get()
                if result.get('error'):
                    raise Exception(result['error'])

                # Extract output files from result
                output_files = []
                output_dir = result.get('output_dir')
                if output_dir:
                    stems = self._get_output_stems(number)
                    for stem in stems:
                        file_path = os.path.join(output_dir, f"{stem}.{codec}")
                        if os.path.exists(file_path):
                            output_files.append({
                                "name": f"{stem}.{codec}",
                                "path": file_path,
                                "size": os.path.getsize(file_path)
                            })

                return {
                    "success": True,
                    "output_files": output_files
                }

        except Exception as e:
            logging.error(f"音频处理失败: {str(e)}", exc_info=True)
            return {
                "success": False,
                "error": str(e),
                "error_type": type(e).__name__
            }
        finally:
            # 确保清理进程
            if self.spl_process and self.spl_process.is_alive():
                self.spl_process.terminate()
            self.spl_process = None
    def _run_spleeter_in_subprocess(self, number, input_path, output_dir, codec, bitrate):
        """子进程执行函数"""
        try:
            from spleeter_part import spleeter_part  # 在子进程内导入
            start_time = time.time()

            # 初始化新的spleeter实例
            spl = spleeter_part()
            
            # 根据类型调用处理
            if number == 2:
                spl.spleeter_2stems(input_path, output_dir, codec, bitrate)
            elif number == 4:
                spl.spleeter_4stems(input_path, output_dir, codec, bitrate)
            elif number == 5:
                spl.spleeter_5stems(input_path, output_dir, codec, bitrate)

            # 强制释放资源
            spl.release()
            # del spl

            # 返回结果到队列
            self.spl_queue.put({
                "success": True,
                "processing_time": round(time.time() - start_time, 1)
            })
            
        except Exception as e:
            self.spl_queue.put({
                "success": False,
                "error": str(e),
                "error_type": type(e).__name__
            })
        finally:
            # 子进程自动退出时会释放所有资源
            import gc
            gc.collect()
    def _get_output_stems(self, number):
        """获取输出音轨描述"""
        stems_map = {
            2: ["人声", "伴奏"],
            4: ["人声", "鼓", "贝斯", "其他"],
            5: ["人声", "鼓", "贝斯", "钢琴", "其他"]
        }
        return stems_map.get(number, [])
        
    async def _get_video_info_sync(self, bvid):
        url = f"https://api.bilibili.com/x/web-interface/view?bvid={bvid}"
        data = await self.Bili_downloader.get_api_data(url)
        return data.get('data', {}) if data else {}

    def _get_video_info(self, bvid):
        # This function is now a simple wrapper for the async function
        return self._get_video_info_sync(bvid)

    def _format_number(self, num):
        if num > 10000:
            return f"{round(num/10000, 1)}万"
        return str(num)
    def whether_collection(self, bvid):
        return asyncio.run(self.Bili_downloader.whether_collection(bvid))
    
    def get_cwd(self):
        """获取当前工作目录"""
        try:
            return {"success": True, "path": os.getcwd()}
        except Exception as e:
            logging.error(f"Failed to get current working directory: {str(e)}", exc_info=True)
            return {"success": False, "error": str(e)}

    def open_save_file_dialog(self, default_filename="output.mp3"):
        """打开系统保存文件对话框"""
        logging.debug("Attempting to open save file dialog.")
        try:
            if not webview.windows:
                logging.error("No webview windows found. Cannot open file dialog.")
                return {"success": False, "error": "No webview window available."}

            file_types = ('Audio Files (*.mp3;*.wav;*.flac)', 'All files (*.*)')
            logging.debug(f"Calling create_file_dialog with default_filename: {default_filename}")
            result = webview.windows[0].create_file_dialog(
                webview.SAVE_DIALOG,          
                directory=os.getcwd(),       
                allow_multiple=False,         
                file_types=file_types,       
                save_filename=default_filename 
            )
            logging.debug(f"create_file_dialog returned: {result}")
            logging.debug(f"open_save_file_dialog: type(result) = {type(result)}")

            if result and len(result) > 0:
                # If result is a string (which seems to be the case based on logs), use it directly.
                # If it's a list (standard behavior), result[0] is correct.
                # We'll assume it's a string if it's not a list, or if it's a list of length 1.
                if isinstance(result, list):
                    selected_path = result[0]
                else: # Assume it's a string if not a list
                    selected_path = result
                logging.debug(f"open_save_file_dialog: selected_path = '{selected_path}'")
                
                # Normalize path to handle potential inconsistencies from webview
                normalized_path = os.path.normpath(selected_path)
                logging.debug(f"open_save_file_dialog: normalized_path = '{normalized_path}'")
                
                # Special handling for Windows drive letters returned without a trailing slash or colon
                if sys.platform == 'win32' and len(normalized_path) == 1 and normalized_path.isalpha():
                    # If it's a single letter, assume it's a drive letter and append ':\'
                    normalized_path = normalized_path.upper() + ":\\"
                    logging.info(f"Detected single letter drive '{selected_path}', converted to '{normalized_path}'")
                elif sys.platform == 'win32' and len(normalized_path) == 2 and normalized_path[1] == ':' and normalized_path[0].isalpha():
                    # If it's "E:", ensure it has a trailing slash for os.path.join to treat it as root
                    normalized_path = normalized_path.upper() + "\\"
                    logging.info(f"Detected drive letter '{selected_path}', converted to '{normalized_path}'")
                
                base_name, file_extension = os.path.splitext(normalized_path)
                logging.debug(f"open_save_file_dialog: base_name = '{base_name}', file_extension = '{file_extension}'")

                # Determine if the selected path is a directory or a file without an extension
                # The condition `not file_extension` means the user typed a filename without an extension
                # or selected a directory that doesn't have a typical file extension.
                is_directory_or_no_extension = os.path.isdir(normalized_path) or \
                                               (sys.platform == 'win32' and normalized_path.endswith(':\\')) or \
                                               not file_extension
                logging.debug(f"open_save_file_dialog: is_directory_or_no_extension = {is_directory_or_no_extension}")

                if is_directory_or_no_extension:
                    final_path = os.path.join(normalized_path, default_filename)
                    logging.info(f"Selected path '{selected_path}' (processed to '{normalized_path}') was a directory/drive/no-extension, appending default filename. Final path: {final_path}")
                else:
                    final_path = normalized_path # Use normalized path if it's a valid file path
                    logging.info(f"File dialog successful, path: {final_path}")
                
                logging.debug(f"open_save_file_dialog: final_path returned = '{final_path}'")
                return {"success": True, "path": final_path}
            else:
                logging.warning("No file selected or dialog cancelled.")
                return {"success": False, "error": "No file selected or dialog cancelled."}
        except Exception as e:
            logging.error(f"Error opening save file dialog: {str(e)}", exc_info=True)
            return {"success": False, "error": str(e)}
    def form_transformation(self, file_data, output_format): # Renamed file_name to file_data for clarity
        try:
            # Use the full path directly from file_data
            input_path = file_data['path']

            # Determine output_path
            base_name = os.path.splitext(os.path.basename(input_path))[0] # Use input_path for base_name
            output_filename = f"{base_name}_converted.{output_format.lower()}"
            
            # Use config_manager to get the output directory
            output_dir = config_manager.get('defaultOutput', os.path.join(os.getcwd(), 'output'))
            os.makedirs(output_dir, exist_ok=True) # Ensure the output directory exists
            
            output_path = os.path.join(output_dir, output_filename)

            # Check if the input file exists
            if not os.path.exists(input_path):
                return {"success": False, "error": f"输入文件不存在: {input_path}"}

            # Determine if it's an audio or video conversion
            is_video = input_path.lower().endswith(('.mp4', '.avi', '.mkv'))
            is_audio_output = output_format.lower() in ['mp3', 'wav', 'ogg']

            if is_video and is_audio_output:
                # Video to audio conversion
                extract_audio_from_video(input_path, output_path)
                if not os.path.exists(output_path):
                    return {"success": False, "error": "视频提取音频失败"}
                return {"success": True, "message": f"视频已成功提取音频并转换为 {output_format.upper()}", "path": output_path}
            elif not is_video and is_audio_output:
                # Audio to audio conversion
                convert_audio_format(input_path, output_path)
                return {"success": True, "message": f"音频已成功转换为 {output_format.upper()}", "path": output_path}
            elif is_video and not is_audio_output:
                # Video to video conversion
                convert_video_format(input_path, output_path)
                return {"success": True, "message": f"视频已成功转换为 {output_format.upper()}", "path": output_path}
            else:
                return {"success": False, "error": "不支持的转换类型"}

        except Exception as e:
            logging.error(f"格式转换失败: {str(e)}", exc_info=True)
            return {"success": False, "error": f"转换失败: {str(e)}"}


    # def editor(self):
    #     while True:
    #         message = self.get_message()
    #         print(f"Received message: {message}")

# 判断是否为生产环境
def whether_production():
    # if hasattr(sys, '_MEIPASS'):
        # 打包环境下，返回本地服务器的URL
        # return 'http://localhost:8000/'
    # else:
    #     # 开发环境下，返回Vite服务器的URL
        return 'http://localhost:3000/'
def resource_path(relative_path):
    """ 动态获取资源的绝对路径，兼容开发环境与PyInstaller打包后的环境 """
    if hasattr(sys, '_MEIPASS'):
        # 打包后，资源位于临时目录 sys._MEIPASS 下
        base_path = sys._MEIPASS
    else:
        # 开发时，使用当前目录的相对路径
        base_path = os.path.abspath(".")
    
    # 拼接路径并标准化（处理路径分隔符）
    return os.path.normpath(os.path.join(base_path, relative_path))

def run_server(port=8000, directory='./ui_interface/dist'):
    """启动一个更健壮的静态文件服务器，不使用 os.chdir()"""
    
    # 确保目录是绝对路径
    directory = os.path.abspath(directory)
    
    class Handler(SimpleHTTPRequestHandler):
        def __init__(self, *args, **kwargs):
            # 在初始化时就指定目录
            super().__init__(*args, directory=directory, **kwargs)

    try:
        httpd = HTTPServer(('localhost', port), Handler)
        logging.info(f"静态文件服务器已启动，服务于目录: {directory}，访问地址: http://localhost:{port}")
        httpd.serve_forever()
    except Exception as e:
        logging.error(f"启动静态文件服务器失败: {e}", exc_info=True)


def run_webview():
    logging.debug("Starting webview")
    from urllib3.connection import HTTPConnection
    def _encode_header(value):
        return value.encode('utf-8') if isinstance(value, str) else value
    HTTPConnection._encode_header = _encode_header
    
    api = Api()
    real_url = whether_production()
    
    logging.info(f"Webview 将要加载的 URL: {real_url}")
    
    webview.create_window(
        title='Soniflow',
        url=real_url,  # <-- 只使用 URL
        width=800,
        height=600,
        resizable=True,
        js_api=api,
        frameless=False,
        localization=False,
    )
    
    logging.info("Webview 窗口已创建，正在启动事件循环...")
    webview.start(debug=True)
    logging.info("Webview 事件循环已退出。")


def start_webview_process():
    global webview_process
    logging.info("准备启动 webview 进程...")
    webview_process = Process(target=run_webview)
    webview_process.start()
    logging.info("Webview 进程已启动。")


def on_open():
    global webview_process
    if not webview_process or not webview_process.is_alive():
        logging.info("Webview 进程不存在或已关闭，重新启动。")
        start_webview_process()
    else:
        logging.info("Webview 进程已在运行。")


def on_exit():
    logging.info("收到退出信号，正在停止图标...")
    icon.stop()


if __name__ == '__main__':
    # 增加日志记录，帮助调试
    logging.info("应用程序启动...")
    
    is_dev_mode = whether_production().startswith('http://localhost:3000')
    logging.info(f"是否为开发模式: {is_dev_mode}")

    if not is_dev_mode:
        dist_path = resource_path('ui_interface/dist')
        logging.info(f"生产模式，前端文件路径: {dist_path}")
        
        if not os.path.isdir(dist_path):
            logging.error(f"错误: 找不到前端构建目录 {dist_path}")
            logging.error("请确保您已经在 'ui_interface' 目录下运行了 'npm run build'")
            sys.exit(1)

        server_thread = threading.Thread(target=run_server, args=(8000, dist_path))
        server_thread.daemon = True
        server_thread.start()
        logging.info("静态文件服务器线程已启动。")
        time.sleep(1) # 等待服务器线程初始化
    
    # Flask 服务器始终需要启动
    flask_thread = threading.Thread(target=run_flask_app)
    flask_thread.daemon = True
    flask_thread.start()
    logging.info("Flask API 服务器线程已启动。")

    # 启动主应用窗口
    start_webview_process()

    # 创建系统托盘图标
    try:
        image = Image.open(resource_path('logo.png'))
        menu = Menu(MenuItem('打开', on_open), MenuItem('退出', on_exit))
        icon = Icon('Soniflow', image, menu=menu)
        logging.info("系统托盘图标已创建，正在运行...")
        icon.run()
    except Exception as e:
        logging.error(f"创建或运行系统托盘图标失败: {e}", exc_info=True)

    # 退出时清理
    logging.info("应用程序正在退出，终止 webview 进程...")
    if webview_process and webview_process.is_alive():
        webview_process.terminate()
        webview_process.join(timeout=2) # 等待进程终止
    logging.info("应用程序已退出。")
