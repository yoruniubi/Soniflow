from moviepy import *
from pydub import AudioSegment
import os
from configs import config_manager

# --- 功能1：从视频提取音频 ---
def extract_audio_from_video(video_path: str, output_audio_path: str):
    if not os.path.exists(video_path):
        print(f"错误：视频文件不存在于 '{video_path}'")
        return
    video_clip = None
    try:
        print(f"正在加载视频: {video_path}...")
        video_clip = VideoFileClip(video_path)
        audio_clip = video_clip.audio
        print(f"正在写入音频到: {output_audio_path}...")
        audio_clip.write_audiofile(output_audio_path)
        print("✅ 提取音频成功！\n")
    except Exception as e:
        print(f"❌ 处理失败：{e}\n")
    finally:
        if video_clip:
            video_clip.close()
            del video_clip # Explicitly delete to release resources
        if 'audio_clip' in locals() and audio_clip:
            audio_clip.close()
            del audio_clip # Explicitly delete to release resources

# --- 功能2：转换音频格式 ---
def convert_audio_format(input_audio_path: str, output_audio_path: str):
    if not os.path.exists(input_audio_path):
        print(f"错误：音频文件不存在于 '{input_audio_path}'")
        return
    try:
        print(f"正在加载音频: {input_audio_path}...")
        audio = AudioSegment.from_file(input_audio_path)
        output_format = output_audio_path.split('.')[-1]
        print(f"正在导出为 '{output_format}' 格式到: {output_audio_path}...")
        audio.export(output_audio_path, format=output_format, bitrate="192k") # for mp3, you can set bitrate
        print("✅ 格式转换成功！\n")
    except Exception as e:
        print(f"❌ 处理失败：{e}\n")

# --- 功能3：转换视频格式 ---
def convert_video_format(input_video_path: str, output_video_path: str):
    if not os.path.exists(input_video_path):
        print(f"错误：视频文件不存在于 '{input_video_path}'")
        return
    video_clip = None
    try:
        print(f"正在加载视频: {input_video_path}...")
        video_clip = VideoFileClip(input_video_path)
        output_format = output_video_path.split('.')[-1]
        print(f"正在导出为 '{output_format}' 格式到: {output_video_path}...")
        video_clip.write_videofile(output_video_path, codec='libx264', audio_codec='aac') # Default codecs, can be made configurable
        print("✅ 视频格式转换成功！\n")
    except Exception as e:
        print(f"❌ 处理失败：{e}\n")
    finally:
        if video_clip:
            video_clip.close()
            del video_clip # Explicitly delete to release resources

# --- 主程序入口 ---
if __name__ == "__main__":

    output_dir = config_manager.get_output_dir()
    os.makedirs(output_dir, exist_ok=True)

    input_video = "./audio/【tuki.】晩餐歌【Music Video】.mp4" 
    extracted_audio = os.path.join(output_dir, "extracted_audio.mp3")
    
    # 确保你有一个名为 my_video.mp4 的文件，或者换成你自己的文件名
    if os.path.exists(input_video):
        extract_audio_from_video(input_video, extracted_audio)
    else:
        print(f"示例跳过：请在脚本同目录下放置一个名为 '{input_video}' 的视频文件。\n")

    input_audio = extracted_audio # 使用上一步提取的音频
    converted_audio = os.path.join(output_dir, "converted_audio.wav")

    # 确保上一步成功生成了文件
    if os.path.exists(input_audio):
        convert_audio_format(input_audio, converted_audio)
    else:
        print(f"示例跳过：找不到输入音频文件 '{input_audio}'。\n")
        
    input_audio_wav = converted_audio # 使用上一步转换的音频
    converted_audio_flac = os.path.join(output_dir, "final_audio.flac")
    
    if os.path.exists(input_audio_wav):
         convert_audio_format(input_audio_wav, converted_audio_flac)
    else:
        print(f"示例跳过：找不到输入音频文件 '{input_audio_wav}'。\n")
    
    # 视频到视频转换示例
    input_video_mp4 = "./audio/tuki.『晩餐歌』Official Music Video.mp4"
    converted_video_avi = os.path.join(output_dir, "converted_video.avi")
    if os.path.exists(input_video_mp4):
        convert_video_format(input_video_mp4, converted_video_avi)
    else:
        print(f"示例跳过：找不到输入视频文件 '{input_video_mp4}'。\n")
