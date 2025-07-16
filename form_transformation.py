import os
import sys
from utils import get_ffmpeg_path, get_ffprobe_path
from configs import config_manager

# --- 全局标志，防止重复初始化 ---
_FFMPEG_INITIALIZED = False

def initialize_ffmpeg():
    """
    一个健壮的初始化函数，用于配置ffmpeg和ffprobe的路径。
    它会设置pydub, moviepy, 并修改当前进程的PATH环境变量。
    
    【【这几行代码就加在这里】】
    """
    global _FFMPEG_INITIALIZED
    if _FFMPEG_INITIALIZED:
        return

    print("--- Initializing FFmpeg and ffprobe paths ---")
    
    ffmpeg_path = get_ffmpeg_path()
    ffprobe_path = get_ffprobe_path()
    
    # 1. 检查路径是否存在
    if not os.path.exists(ffmpeg_path) or not os.path.exists(ffprobe_path):
        print("WARNING: ffmpeg or ffprobe not found in bundled directory.")
        _FFMPEG_INITIALIZED = True
        return
        
    # 2. 将ffmpeg所在目录添加到PATH环境变量的最前面
    #    这是最可靠的方式，能让pydub和其它库自动找到ffprobe
    ffmpeg_dir = os.path.dirname(ffmpeg_path)
    if ffmpeg_dir not in os.environ['PATH']:
        os.environ['PATH'] = ffmpeg_dir + os.pathsep + os.environ['PATH']
        print(f"INFO: Added '{ffmpeg_dir}' to PATH.")

    # 3. 为MoviePy设置环境变量
    os.environ["FFMPEG_BINARY"] = ffmpeg_path
    print(f"INFO: Environment variable 'FFMPEG_BINARY' set for MoviePy: {ffmpeg_path}")

    # 4. 为Pydub显式设置converter路径
    #    虽然添加到PATH后pydub通常能自己找到，但显式设置更保险
    from pydub import AudioSegment
    AudioSegment.converter = ffmpeg_path
    print(f"INFO: Pydub's converter path explicitly set to: {ffmpeg_path}")
    
    # ffprobe现在会从我们修改过的PATH中被找到，无需其他设置
    
    _FFMPEG_INITIALIZED = True
    print("--- FFmpeg and ffprobe initialization finished. ---")


# --- 在模块加载时就执行初始化，确保全局生效 ---
initialize_ffmpeg()


from moviepy import VideoFileClip
from pydub import AudioSegment


# 你的功能函数保持不变，无需修改
def extract_audio_from_video(video_path: str, output_audio_path: str):
    """
    功能 1: 从视频文件中提取音频。
    """
    if not os.path.exists(video_path):
        print(f"ERROR: Video file not found at '{video_path}'")
        return
    
    video_clip = None
    audio_clip = None
    try:
        print(f"\n[Extracting Audio] Loading video: {video_path}...")
        video_clip = VideoFileClip(video_path)
        audio_clip = video_clip.audio
        
        print(f"[Extracting Audio] Writing audio to: {output_audio_path}...")
        audio_clip.write_audiofile(output_audio_path, logger=None)
        
        print("SUCCESS: Audio extracted successfully!")
    except Exception as e:
        print(f"ERROR: Audio extraction failed: {e}")
    finally:
        if audio_clip:
            audio_clip.close()
        if video_clip:
            video_clip.close()

def convert_audio_format(input_audio_path: str, output_audio_path: str):
    """
    功能 2: 转换音频文件的格式。
    """
    if not os.path.exists(input_audio_path):
        print(f"ERROR: Audio file not found at '{input_audio_path}'")
        return
    
    try:
        print(f"\n[Converting Audio] Loading audio: {input_audio_path}...")
        audio = AudioSegment.from_file(input_audio_path)
        
        output_format = os.path.splitext(output_audio_path)[1][1:].lower()
        print(f"[Converting Audio] Exporting as '{output_format}' to: {output_audio_path}...")
        
        audio.export(output_audio_path, format=output_format, bitrate="192k")
        print("SUCCESS: Audio format converted successfully!")
    except Exception as e:
        print(f"ERROR: Audio conversion failed: {e}")

def convert_video_format(input_video_path: str, output_video_path: str):
    """
    功能 3: 转换视频文件的格式。
    """
    if not os.path.exists(input_video_path):
        print(f"ERROR: Video file not found at '{input_video_path}'")
        return
        
    video_clip = None
    try:
        print(f"\n[Converting Video] Loading video: {input_video_path}...")
        video_clip = VideoFileClip(input_video_path)
        
        print(f"[Converting Video] Exporting to: {output_video_path}...")
        video_clip.write_videofile(output_video_path, codec='libx264', audio_codec='aac', logger=None)
        
        print("SUCCESS: Video format converted successfully!")
    except Exception as e:
        print(f"ERROR: Video conversion failed: {e}")
    finally:
        if video_clip:
            video_clip.close()

if __name__ == "__main__":
    print("\n--- Running form_transformation.py as a standalone script for testing ---")

    output_dir = config_manager.get('defaultOutput', './output_test')
    os.makedirs(output_dir, exist_ok=True)
    print(f"Test output will be saved to: {output_dir}")

    input_video = "./audio/【tuki.】晩餐歌【Music Video】.mp4" 
    extracted_audio = os.path.join(output_dir, "extracted_audio.mp3")
    if os.path.exists(input_video):
        extract_audio_from_video(input_video, extracted_audio)
    else:
        print(f"\nSKIP: Test video not found at '{input_video}'.")

    input_audio = extracted_audio
    converted_audio = os.path.join(output_dir, "converted_audio.wav")
    if os.path.exists(input_audio):
        convert_audio_format(input_audio, converted_audio)
    else:
        print(f"\nSKIP: Input audio for conversion not found at '{input_audio}'.")
        
    input_video_for_conversion = "./audio/【tuki.】晩餐歌【Music Video】.mp4"
    converted_video_avi = os.path.join(output_dir, "converted_video.avi")
    if os.path.exists(input_video_for_conversion):
        convert_video_format(input_video_for_conversion, converted_video_avi)
    else:
        print(f"\nSKIP: Input video for conversion not found at '{input_video_for_conversion}'.")
    
    print("\n--- Standalone script test finished ---")