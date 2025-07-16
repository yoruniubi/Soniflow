from pydub import AudioSegment
from pydub.playback import play
import librosa
import numpy as np
import os 
import logging
# logging.basicConfig(level=logging.DEBUG, 
#                     format='%(asctime)s - %(levelname)s - %(message)s',
#                     handlers=[logging.StreamHandler()])
class AudioProcessor:
    def __init__(self, input_path=None):
        """
        初始化音频处理器
        :param input_path: 可选，可直接加载音频文件路径
        """
        self.audio = AudioSegment.empty()  # 初始化为空音频
        self.original_info = {}
        self.history = []  # 存储音频操作历史
        self.history_index = -1
        self.clipboard = None # 剪贴板

        if input_path:
            self.load_from_file(input_path)

    def _add_to_history(self):
        """将当前音频状态添加到历史记录"""
        if self.audio:
            # 如果当前不是最新状态，则截断历史
            if self.history_index < len(self.history) - 1:
                self.history = self.history[:self.history_index + 1]
            self.history.append(self.audio[:]) # 存储深拷贝
            self.history_index = len(self.history) - 1
            # 限制历史记录大小，例如10步
            if len(self.history) > 10:
                self.history.pop(0)
                self.history_index -= 1

    def _restore_from_history(self):
        """从历史记录恢复音频状态"""
        if 0 <= self.history_index < len(self.history):
            self.audio = self.history[self.history_index][:]
            self._update_original_info()
            return True
        return False

    def undo(self):
        """撤销上一步操作"""
        if self.history_index > 0:
            self.history_index -= 1
            return self._restore_from_history()
        return False

    def redo(self):
        """重做下一步操作"""
        if self.history_index < len(self.history) - 1:
            self.history_index += 1
            return self._restore_from_history()
        return False

    def load_from_file(self, input_path):
        """
        从文件加载音频
        :param input_path: 音频文件路径
        """
        try:
            self.audio = AudioSegment.from_file(input_path)
            self._update_original_info()
            self._add_to_history() # 加载时也加入历史
            print(f"已加载音频成功: {input_path} | 时长: {self.original_info['duration']}秒 | 采样率: {self.original_info['frame_rate']}Hz")
            return self
        except Exception as e:
            print(f"加载音频失败: {input_path} - {e}")
            raise # Re-raise the exception after logging

    def _update_original_info(self):
        """更新音频元信息"""
        if self.audio:
            self.original_info = {
                'duration': len(self.audio) / 1000,
                'frame_rate': self.audio.frame_rate,
                'channels': self.audio.channels,
                'sample_width': self.audio.sample_width
            }
    # def adjust_volume(self, dB_change):
    #     """
    #     调整音量
    #     :param dB_change: 音量变化值（分贝）
    #     """
    #     self._check_loaded()
    #     self.audio = self.audio + dB_change
    #     self._update_original_info()
    #     self._add_to_history(a
    #     return self

    # def add_fade(self, fade_in_sec=2, fade_out_sec=2):
    #     """
    #     添加淡入淡出效果
    #     :param fade_in_sec: 淡入时长（秒）
    #     :param fade_out_sec: 淡出时长（秒）
    #     """
    #     self._check_loaded()
    #     self.audio = self.audio.fade_in(int(fade_in_sec * 1000))
    #     self.audio = self.audio.fade_out(int(fade_out_sec * 1000))
    #     self._update_original_info()
    #     self._add_to_history()
    #     return self

    def split(self, split_time_sec):
        """
        在指定时间点将音频分割成两部分
        :param split_time_sec: 分割时间点（秒）
        :return: 包含两个AudioSegment对象的元组 (part1, part2)
        """
        self._check_loaded()
        split_time_ms = int(split_time_sec * 1000)
        if split_time_ms < 0 or split_time_ms > len(self.audio):
            raise ValueError("分割时间点超出音频范围")

        part1 = self.audio[:split_time_ms]
        part2 = self.audio[split_time_ms:]
        self.audio = part1 # For split, we keep the first part as current audio
        self._update_original_info()
        self._add_to_history()
        print(f"音频已在 {split_time_sec} 秒处分割")
        return part1, part2 # Return both parts, but only part1 is current

    def copy_selection(self, start_sec, end_sec):
        """
        复制选定区域的音频到剪贴板
        :param start_sec: 开始时间（秒）
        :param end_sec: 结束时间（秒）
        """
        self._check_loaded()
        start_ms = int(start_sec * 1000)
        end_ms = int(end_sec * 1000)
        self.clipboard = self.audio[start_ms:end_ms][:]
        print(f"已复制选区: {start_sec}-{end_sec}秒")
        return self

    def paste_selection(self, target_sec):
        """
        将剪贴板中的音频粘贴到指定时间点
        :param target_sec: 粘贴目标时间（秒）
        """
        self._check_loaded()
        if not self.clipboard:
            raise ValueError("剪贴板为空，无法粘贴")

        target_ms = int(target_sec * 1000)
        
        # 分割当前音频
        before = self.audio[:target_ms]
        after = self.audio[target_ms:]
        
        # 拼接音频
        self.audio = before + self.clipboard + after
        self._update_original_info()
        self._add_to_history()
        print(f"已粘贴音频到: {target_sec}秒")
        return self

    def open_file_explorer(self, path):
        """打开文件资源管理器到指定路径"""
        # 确保路径存在
        if not os.path.exists(path):
            os.makedirs(path, exist_ok=True)
        
        # 跨平台打开文件资源管理器
        if os.name == 'nt':  # Windows
            os.startfile(path)
        elif os.name == 'posix':  # macOS, Linux
            if sys.platform == 'darwin':
                subprocess.run(['open', path])
            else:
                subprocess.run(['xdg-open', path])
        else:
            print(f"无法在您的系统上打开文件资源管理器: {sys.platform}")
    def export(self, output_path, format="mp3", bitrate="192k"):
        """
        导出音频文件并在导出后打开所在文件夹
        """
        self._check_loaded()
        
        # 确保输出目录存在
        output_dir = os.path.dirname(output_path)
        if output_dir and not os.path.exists(output_dir):
            os.makedirs(output_dir, exist_ok=True)
        
        # 导出音频文件
        # pydub export handles format and bitrate
        self.audio.export(output_path, format=format, bitrate=bitrate)
        print(f"文件已导出至: {output_path} (格式: {format}, 比特率: {bitrate})")
        
        # 打开文件所在目录
        if os.path.exists(output_path):
            # Get the directory of the exported file
            export_dir = os.path.dirname(output_path)
            # If output_path is just a filename in the current directory, export_dir will be empty.
            # In that case, use the current working directory.
            if not export_dir:
                export_dir = "."
            self.open_file_explorer(export_dir)
        else:
            print("警告: 文件导出成功但无法定位")
        
        return self

    def play(self):
        """播放当前音频（需要安装simpleaudio）"""
        self._check_loaded()
        play(self.audio)
        return self

    def _check_loaded(self):
        """检查音频是否已加载"""
        if not self.audio:
            raise ValueError("未加载音频！请先使用load_from_file()方法加载")
    
    def get_history_state(self):
        """获取历史记录状态，用于前端判断撤销/重做按钮状态"""
        return {
            'can_undo': self.history_index > 0,
            'can_redo': self.history_index < len(self.history) - 1,
            'has_clipboard': self.clipboard is not None
        }

    # 添加可视化支持
    def generate_waveform(self, audio_path, width=800):
        """
        使用 pydub 加载音频，然后使用 librosa 生成波形数据。
        这个方法在打包后的无控制台环境下更健壮。

        :param audio_path: 音频文件路径
        :param width: 波形图宽度（像素点数）
        :return: 包含波形数据和时长的字典
        """
        try:
            logging.info(f"开始生成波形，使用pydub加载: {audio_path}")
            
            # 步骤 1: 使用我们已经配置好的 pydub 来加载文件，这会正确处理 ffmpeg
            audio_segment = AudioSegment.from_file_using_temporary_files(audio_path)
            
            # 获取采样率和通道数
            sr = audio_segment.frame_rate
            channels = audio_segment.channels
            
            logging.debug(f"Pydub加载成功. 采样率: {sr}, 通道数: {channels}")

            # 步骤 2: 从 pydub 获取原始样本数据，并转换为 numpy 数组
            # get_array_of_samples() 返回一个 array.array 对象
            samples_array = audio_segment.get_array_of_samples()
            
            # 将其转换为 numpy 数组
            y = np.array(samples_array).astype(np.float32)

            # 步骤 3: 如果是立体声，转换为单声道
            if channels == 2:
                # pydub 的样本是交错的 [L, R, L, R, ...]
                # 我们需要将其重塑为 (n_samples, 2) 然后取平均
                y = y.reshape((-1, 2)).mean(axis=1)

            # 步骤 4: 标准化样本数据到 [-1.0, 1.0] 范围，这是 librosa 的标准输入格式
            # audio_segment.sample_width 是字节数 (1, 2, 4) -> 对应 8, 16, 32 bit
            # 2**(bits - 1) 是有符号整数的最大值
            max_val = 2**(audio_segment.sample_width * 8 - 1)
            y /= max_val
            
            logging.debug(f"已将样本转换为标准化的单声道 numpy 数组. 样本数: {len(y)}")

            # 步骤 5: 使用 librosa 进行后续处理（主要是下采样以匹配宽度）
            # 注意：此时的 y 已经是 librosa 喜欢的格式了，无需再次 normalize
            step = max(1, len(y) // width)
            waveform_data = []
            for i in range(0, len(y), step):
                chunk = y[i:i+step]
                if len(chunk) > 0:
                    waveform_data.append(float(np.mean(np.abs(chunk))))
                else:
                    waveform_data.append(0.0)

            # 计算时长
            duration = audio_segment.duration_seconds

            logging.info(f"成功生成波形数据: {len(waveform_data)} 点, 时长: {duration} 秒")
            
            return {
                "waveform": waveform_data,
                "duration": float(duration)
            }
        except Exception as e:
            logging.error(f"生成波形失败: {e}", exc_info=True) # 使用 exc_info=True 记录更详细的堆栈信息
            return {
                "waveform": [],
                "duration": 0.0,
                "error": f"加载音频元数据失败: {e}" # 返回更具体的错误信息
            }

    def get_current_info(self):
        """
        获取当前音频信息
        :return: 字典包含时长/采样率/通道数/采样宽度
        """
        self._check_loaded()
        return {
            'duration': round(len(self.audio) / 1000.0, 2),
            'frame_rate': self.audio.frame_rate,
            'channels': self.audio.channels,
            'sample_width': self.audio.sample_width
        }

# 使用示例
if __name__ == "__main__":
    # 创建处理器并加载音频
    processor = AudioProcessor("test.mp3")
    
    # 处理流程（支持链式调用）
    (processor
     .clip(30, 60)          # 剪切30-60秒
     .adjust_volume(6)      # 提升6分贝
     .add_fade(2, 2)        # 添加2秒淡入淡出
     .export("output.mp3")  # 导出文件
     # .play()               # 可试听
    )
    
    # 查看处理后的音频信息
    print("处理后信息:", processor.get_current_info())
