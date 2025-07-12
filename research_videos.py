import requests
import re
import json
import os
import subprocess
from urllib3.connection import HTTPConnection
from urllib.parse import quote
import yt_dlp
import asyncio
import aiohttp
import time  
import random
from configs import config_manager


# 猴子补丁修复编码
def _encode_header(value):
    if isinstance(value, str):
        return value.encode('utf-8')
    return value
HTTPConnection._encode_header = _encode_header

# Global headers (cookies will be managed dynamically)
headers = {
    "Referer": "https://www.bilibili.com/",
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/136.0.0.0 Safari/537.36 Edg/136.0.0.0",
    "Cache-Control": "max-age=300" 
}

# Global cookies_dict for requests (will be updated dynamically)
def _parse_cookie_string(cookie_string):
    """Parses a cookie string into a dictionary."""
    cookies = {}
    for cookie in cookie_string.split(';'):
        if '=' in cookie:
            name, value = cookie.split('=', 1)
            cookies[name.strip()] = value.strip()
    return cookies

# Global cookies_dict for requests (will be updated dynamically)
bilibili_cookies_str = config_manager.get('bilibiliCookies', '')
cookies_dict = _parse_cookie_string(bilibili_cookies_str)

# Global youtube_cookies string for yt_dlp (will be updated dynamically)
youtube_cookies_str = config_manager.get('youtubeCookies', '')
class BiliVideoDownloader:
     
    def __init__(self):
        self.video_url = None
        self.video_info = None
        self.output_dir = config_manager.get('defaultOutput', './output') # Use config_manager
        # Ensure the output directory exists
        os.makedirs(self.output_dir, exist_ok=True)
        self.video_page_url = None
        self.is_logged_in = True # Track login status

    def search_videos(self, keyword,page=1,per_page=20):
        # 使用B站官方搜索API
        api_url = "https://api.bilibili.com/x/web-interface/search/type"
        params = {
            "search_type": "video",
            "keyword": keyword,
            "page": page,
            "page_size": per_page  # 新增分页参数
        }
        response = requests.get(api_url, headers=headers, params=params,cookies=cookies_dict)
        if response.status_code == 200:
            data = response.json()
            videos = data.get('data', {}).get('result', [])
            total = data.get('data', {}).get('numResults', 0)  # 获取总结果数
            
            titles = []
            bvids = []
            for video in videos:
                titles.append(video.get('title'))
                bvids.append(video.get('bvid'))
            return bvids,titles,total
        else:
            print("API请求失败，状态码:", response.status_code)
            return [], [], 0
    def get_video_page_url(self, titles, bvids):
        if titles and bvids:
            print("搜索到的视频有：")
            for idx, (title, bvid) in enumerate(zip(titles, bvids), start=1):
                print(f"{idx}. {title} (BV号: {bvid})")
            
            choice = int(input("请选择想要下载的视频编号（输入数字）：")) - 1
            if 0 <= choice < len(bvids):
                return f"https://www.bilibili.com/video/{bvids[choice]}"
            else:
                print("输入的编号超出范围")
        return None

    def get_playinfo(self, url):
        try:
            headers['Referer'] = url
            response = requests.get(url, headers=headers, cookies=cookies_dict, timeout=10)
            response.raise_for_status()  # 自动触发 HTTPError
            
            findUrl = re.compile(r'<script>window\.__playinfo__=(.*?)</script>', re.S)
            video_info = re.findall(findUrl, response.text)
            if not video_info:
                print("播放信息未找到")
                return None
            
            parsed_info = json.loads(video_info[0])
            if 'data' not in parsed_info:
                print("解析的视频信息中缺少'data'字段。")
                return None
            return parsed_info
        except requests.exceptions.RequestException as e:
            print(f"请求失败: {str(e)}")
            return None
        except json.JSONDecodeError as e:
            print(f"解析视频信息JSON失败: {str(e)}")
            return None

    def download_video(self, video_info, video_title):
        sanitized_video_title = self._sanitize_filename(video_title)
        os.makedirs(self.output_dir, exist_ok=True)

        if 'data' not in video_info or 'dash' not in video_info['data']:
            return {"success": False, "error": "视频信息不完整，缺少data或dash字段。"}

        dash_data = video_info['data']['dash']
        video_filename = os.path.join(self.output_dir, f'{sanitized_video_title}.flv')
        audio_filename = os.path.join(self.output_dir, f'{sanitized_video_title}.mp3')

        video_downloaded = False
        audio_downloaded = False

        # Download video
        video_data = dash_data.get('video')
        if video_data and len(video_data) > 0:
            videoURL = video_data[0]['baseUrl']
            try:
                video_response = requests.get(videoURL, headers=headers, cookies=cookies_dict, stream=True)
                video_response.raise_for_status()
                with open(video_filename, 'wb') as f:
                    for chunk in video_response.iter_content(chunk_size=8192):
                        f.write(chunk)
                video_downloaded = True
            except requests.exceptions.RequestException as e:
                return {"success": False, "error": f"下载视频失败: {e}"}
        
        # Download audio
        audio_data = dash_data.get('audio')
        if audio_data and len(audio_data) > 0:
            audioURL = audio_data[0]['baseUrl']
            try:
                audio_response = requests.get(audioURL, headers=headers, cookies=cookies_dict, stream=True)
                audio_response.raise_for_status()
                with open(audio_filename, 'wb') as f:
                    for chunk in audio_response.iter_content(chunk_size=8192):
                        f.write(chunk)
                audio_downloaded = True
            except requests.exceptions.RequestException as e:
                return {"success": False, "error": f"下载音频失败: {e}"}

        if not video_downloaded and not audio_downloaded:
            return {"success": False, "error": "没有找到视频流和音频流信息，无法下载。"}

        if video_downloaded and audio_downloaded:
            # Merge video and audio
            output_file = os.path.join(self.output_dir, f'{sanitized_video_title}.mp4')
            command = [
                'ffmpeg', '-y', '-i', video_filename, '-i', audio_filename,
                '-c:v', 'copy', '-c:a', 'aac', '-strict', 'experimental', output_file
            ]
            try:
                subprocess.run(command, check=True, capture_output=True, encoding='utf-8')
                os.remove(video_filename) # Clean up temp files
                os.remove(audio_filename)
                return {"success": True, "message": "视频和音频合并完成。"}
            except subprocess.CalledProcessError as e:
                return {"success": False, "error": f"合并视频和音频时发生错误：{e.stderr}"}
        elif video_downloaded:
            final_video_path = os.path.join(self.output_dir, f'{sanitized_video_title}.mp4')
            os.rename(video_filename, final_video_path)
            return {"success": True, "message": "仅下载了视频。"}
        elif audio_downloaded:
            return {"success": True, "message": "仅下载了音频。"}
    async def get_api_data(self, url):
        try:
            async with aiohttp.ClientSession(headers=headers, cookies=cookies_dict) as session:
                async with session.get(url, timeout=10) as response:
                    response.raise_for_status()
                    return await response.json()
        except aiohttp.ClientError as e:
            print(f"API请求失败: {str(e)}")
            return None
        except asyncio.TimeoutError:
            print(f"API请求超时: {url}")
    async def whether_collection(self, bvid):
        # 获取视频基础信息
        print('bvid:', bvid)
        base_api = f"https://api.bilibili.com/x/web-interface/view?bvid={bvid}"
        data = await self.get_api_data(base_api)
        if data is None:
            return None
        try:
            if data.get('code') != 0 or not data.get('data'):
                print(f"获取视频信息失败: {data.get('message', '未知错误')}")
                return None

            video_data = data['data']

            # 直接检查 ugc_season 字段判断是否为合集
            ugc_season = video_data.get('ugc_season')

            if ugc_season:
                return {
                    "is_collection": True,
                    "collection_title": ugc_season.get('title'),
                    "collection_id": ugc_season.get('id'),
                    "owner_mid": video_data['owner']['mid']
                }
            else:
                return {"is_collection": False}

        except requests.exceptions.RequestException as e:
            print(f"API请求失败: {str(e)}")
            return None
        except (KeyError, TypeError) as e:
            print(f"数据结构解析错误: {str(e)}")
            return None

    def get_collection_videos(self, mid, season_id, page_num=1, page_size=50):
        """
        获取指定合集中的视频列表
        """
        api_url = "https://api.bilibili.com/x/polymer/web-space/seasons_archives_list"
        params = {
            "mid": mid,
            "season_id": season_id,
            "page_num": page_num,
            "page_size": page_size,
            "sort_reverse": "false" 
        }

        try:
            # Add Referer header as required by the API
            collection_headers = headers.copy()
            collection_headers["Referer"] = "https://www.bilibili.com/"

            print(f"get_collection_videos called with mid={mid}, season_id={season_id}")

            response = requests.get(
                api_url,
                params=params,
                headers=collection_headers,
                cookies=cookies_dict
            )
            response.raise_for_status()
            data = response.json()
            # print(f"获取合集视频列表: {data}")
            if data.get('code') == 0 and data.get('data'):
                return {"success": True, "items": data.get('data').get('archives', []), "meta": data.get('data').get('meta', {})}
            else:
                return {"success": False, "error": data.get('message', '未知错误')}

        except requests.exceptions.RequestException as e:
            print(f"API请求失败: {str(e)}")
            return {"success": False, "error": str(e)}
        except (KeyError, TypeError) as e:
            print(f"数据结构解析错误: {str(e)}")
            return {"success": False, "error": str(e)}


    def _sanitize_filename(self, filename):  
        """清理文件名中的非法字符""" 
        # 移除或替换文件名中的非法字符  
        filename = re.sub(r'[<>:"/\\|?*]', '_', filename)  
        return filename[:200]  # 限制文件名长度
        
class YoutubeDownloader:
    def __init__(self):  
        self.output_dir = config_manager.get('defaultOutput', './output') # Use config_manager
        # Ensure the output directory exists
        os.makedirs(self.output_dir, exist_ok=True)
        self.proxy = self._get_system_proxy()  
        self.ydl_opts = {  
            'format': 'bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best',  
            'outtmpl': os.path.join(self.output_dir, '%(title)s.%(ext)s'),  
            'proxy': self.proxy,  
            'http_headers': {  
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                'cookies': youtube_cookies_str
            },
            'quiet': True,  
            # 防止被检测的设置  
            'sleep_interval_requests': 1,  
            'sleep_interval': 2,  
            'retries': 10,  
            'fragment_retries': 10,  
            'extractor_retries': 3,
            # YouTube 特定设置  
            'extractor_args': {  
                'youtube': {  
                    'player_client': ['tv', 'web'],  
                    'player_skip': ['configs'],  

                }  
            }  
        }
        self.is_logged_in = True # Track login status

    def _get_system_proxy(self):
        """从环境变量获取代理配置（保留原有代码）"""
        proxy_vars = ['https_proxy', 'http_proxy', 'all_proxy']
        for var in proxy_vars + [v.upper() for v in proxy_vars]:
            if proxy := os.environ.get(var):
                if proxy.startswith('socks5://'):
                    return proxy.replace('socks5://', 'http://')
                return proxy
        return None

    def search_videos(self, keyword, page=1, per_page=20):
        """使用yt_dlp内置搜索功能，并支持分页（优化版）"""
        
        num_results_to_fetch = page * per_page
        search_query = f"ytsearch{num_results_to_fetch}:{keyword}"

        # 为搜索创建优化的、轻量级的配置
        search_opts = {
            'proxy': self.proxy,
            'quiet': True,
            'extract_flat': True,  
            'skip_download': True,
            'http_headers': self.ydl_opts.get('http_headers', {}),
            'extractor_args': self.ydl_opts.get('extractor_args', {})
        }

        for attempt in range(3):  # 最多尝试3次
            try:
                if attempt > 0:
                    delay = random.uniform(2, 5)  # 缩短重试延迟
                    print(f"等待 {delay:.1f} 秒后重试...")
                    time.sleep(delay)

                with yt_dlp.YoutubeDL(search_opts) as ydl:
                    info = ydl.extract_info(search_query, download=False)
                    if not info:
                        print("未找到相关视频")
                        return [], 0

                    entries = info.get('entries', [])
                    if not entries:
                        return [], 0
                        
                    total_results = len(entries)

                    start_index = (page - 1) * per_page
                    end_index = start_index + per_page
                    
                    paged_entries = entries[start_index:min(end_index, total_results)]

                    videos = []
                    for entry in paged_entries:
                        if not entry:
                            continue
                        video = {
                            'title': entry.get('title', '无标题'),
                            'duration': entry.get('duration'),
                            'url': entry.get('webpage_url'),
                            'id': entry.get('id'),
                            'author': entry.get('uploader', '未知'),
                        }
                        videos.append(video)
                    return videos, total_results

            except Exception as e:
                error_msg = str(e).lower()
                if '429' in error_msg or 'too many requests' in error_msg:
                    if attempt < 2:
                        print(f"遇到速率限制，第 {attempt + 1} 次重试...")
                        continue
                    else:
                        print("多次重试后仍然失败，建议稍后再试或使用代理")
                print(f"搜索失败: {str(e)}")
                return [], 0

    def check_if_playlist(self, video_url):
        """检查URL是单个视频还是播放列表"""
        check_opts = {
            'proxy': self.proxy,
            'quiet': True,
            'extract_flat': True,  # 只获取元数据，不深入解析
            'skip_download': True,
        }
        try:
            with yt_dlp.YoutubeDL(check_opts) as ydl:
                info = ydl.extract_info(video_url, download=False)
                if 'entries' in info:
                    # 这是一个播放列表
                    return True, info.get('title', 'Untitled Playlist'), info.get('webpage_url')
                else:
                    # 这是一个单独的视频
                    return False, None, None
        except Exception as e:
            print(f"检查URL时出错: {e}")
            return False, None, None

    def download_playlist(self, playlist_url):
        """下载整个播放列表的音频"""
        try:
            # 获取播放列表标题用于创建文件夹
            with yt_dlp.YoutubeDL({'proxy': self.proxy, 'quiet': True, 'extract_flat': True}) as ydl:
                info = ydl.extract_info(playlist_url, download=False)
                playlist_title = self._sanitize_filename(info.get('title', 'youtube_playlist'))

            playlist_dir = os.path.join(self.output_dir, playlist_title)
            os.makedirs(playlist_dir, exist_ok=True)
            
            print(f"播放列表将保存到: {playlist_dir}")

            playlist_opts = self.ydl_opts.copy()
            playlist_opts['outtmpl'] = os.path.join(playlist_dir, '%(title)s.%(ext)s')
            playlist_opts['quiet'] = False # 显示下载进度

            with yt_dlp.YoutubeDL(playlist_opts) as ydl:
                ydl.download([playlist_url])
            
            print(f"播放列表 '{playlist_title}' 下载完成！")
            return {"success": True, "message": f"播放列表 '{playlist_title}' 下载完成！"}

        except Exception as e:
            print(f"下载播放列表时出错: {e}")
            return {"success": False, "error": f"下载播放列表时出错: {e}"}

    def download_video(self, video_url):
        """下载视频"""
        os.makedirs(self.output_dir, exist_ok=True)
        
        try:
            with yt_dlp.YoutubeDL(self.ydl_opts) as ydl:
                ydl.download([video_url])
            print("下载完成！文件保存在:", os.path.abspath(self.output_dir))
            return {"success": True, "message": "下载完成！"}
        except Exception as e:
            error_message = f"下载失败: {str(e)}"
            if "ProxyError" in str(e):
                error_message += "\n>>> 请检查代理设置是否正确 <<<"
                error_message += "\n设置示例（在终端中运行）："
                error_message += "\nWindows:\n$env:https_proxy = 'http://127.0.0.1:1080'"
                error_message += "\nLinux/macOS:\nexport https_proxy=http://127.0.0.1:1080"
            print(error_message)
            return {"success": False, "error": error_message}


if __name__ == "__main__":
    pass # No direct execution needed for research_videos.py anymore
