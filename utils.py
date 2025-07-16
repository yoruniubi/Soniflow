import sys
import os

def resource_path(relative_path):
    """
    获取资源的绝对路径，兼容开发环境与PyInstaller打包后的环境。
    这是解决开发/生产环境路径问题的核心。
    """
    try:
        # 在打包后的生产环境中运行，_MEIPASS是解压后的临时目录
        base_path = sys._MEIPASS
    except Exception:
        # 在开发环境中，使用 __file__ 获取当前脚本文件所在的目录作为基准路径
        base_path = os.path.dirname(os.path.abspath(__file__))
    
    # 拼接路径并返回一个标准化的路径 (处理不同操作系统的路径分隔符)
    return os.path.normpath(os.path.join(base_path, relative_path))


def get_ffmpeg_path():
    """
    获取ffmpeg可执行文件的绝对路径。
    假定 ffmpeg 位于项目根目录下的 'ffmpeg' 文件夹中。
    """
    # 区分不同操作系统的可执行文件名
    ffmpeg_executable = "ffmpeg.exe" if sys.platform == "win32" else "ffmpeg"
    
    # 直接在基准路径下寻找 'ffmpeg' 文件夹
    return resource_path(os.path.join("ffmpeg", ffmpeg_executable))


def get_ffprobe_path():
    """
    获取ffprobe可执行文件的绝对路径。
    假定 ffprobe 位于项目根目录下的 'ffmpeg' 文件夹中。
    """
    # 区分不同操作系统的可执行文件名
    ffprobe_executable = "ffprobe.exe" if sys.platform == "win32" else "ffprobe"
    
    # 直接在基准路径下寻找 'ffmpeg' 文件夹
    return resource_path(os.path.join("ffmpeg", ffprobe_executable))


# --- 用于测试的示例 ---
if __name__ == '__main__':
    print("--- Testing utils.py with './ffmpeg' directory structure ---")
    
    print(f"Current Script Directory (based on __file__): {os.path.dirname(os.path.abspath(__file__))}")
    print(f"Base path calculated by resource_path(''): {resource_path('')}")
    print("-" * 20)
    
    ffmpeg_p = get_ffmpeg_path()
    ffprobe_p = get_ffprobe_path()
    
    print(f"Calculated FFmpeg path: {ffmpeg_p}")
    print(f"Does it exist? {'Yes' if os.path.exists(ffmpeg_p) else 'No, please check your directory structure!'}")
    print("-" * 20)
    
    print(f"Calculated ffprobe path: {ffprobe_p}")
    print(f"Does it exist? {'Yes' if os.path.exists(ffprobe_p) else 'No, please check your directory structure!'}")
    print("-" * 20)
    
    # 测试其他资源
    spleeter_config_path = resource_path(os.path.join('spleeter', 'resources', '2stems.json'))
    print(f"Calculated Spleeter config path: {spleeter_config_path}")
    print(f"Does it exist? {'Yes' if os.path.exists(spleeter_config_path) else 'No, please check your directory structure!'}")