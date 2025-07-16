# spleeter_part.py
import os
import sys
import json
import tempfile
# 确保 utils.py 中的 resource_path 函数是正确的
from utils import resource_path

def _get_spleeter_model_path_for_separator(stems: int):
    """
    智能获取Spleeter模型路径。
    - 在打包环境下，返回一个包含模型绝对路径的临时JSON配置文件路径。
    - 在开发环境下，返回Spleeter的内置模型字符串（如 'spleeter:2stems'）。
    """
    # 1. 判断是否为打包环境
    is_bundled = hasattr(sys, '_MEIPASS')

    if is_bundled:
        # --- 打包环境下的逻辑 ---
        print("[Spleeter Subprocess] Running in BUNDLED mode. Patching model path...")
        try:
            # a. 找到我们打包的原始JSON配置文件
            config_filename = f'{stems}stems.json'
            original_config_path = resource_path(os.path.join('spleeter', 'resources', config_filename))
            if not os.path.exists(original_config_path):
                raise FileNotFoundError(f"Bundled config not found: {original_config_path}")

            with open(original_config_path, 'r', encoding='utf-8') as f:
                config = json.load(f)

            # b. 计算打包的预训练模型的绝对路径
            model_name_from_config = config['model_dir'] # e.g., "2stems"
            absolute_model_path = resource_path(os.path.join('pretrained_models', model_name_from_config))
            if not os.path.isdir(absolute_model_path):
                raise FileNotFoundError(f"Bundled model directory not found: {absolute_model_path}")

            # c. 修改配置，并写入临时文件
            config['model_dir'] = absolute_model_path
            
            with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.json', encoding='utf-8') as tmp:
                json.dump(config, tmp, indent=4)
                temp_config_path = tmp.name
            
            print(f"[Spleeter Subprocess] Patched config saved to: {temp_config_path}")
            return temp_config_path

        except Exception as e:
            print(f"ERROR: Failed to patch Spleeter config in bundled mode: {e}")
            # 在打包模式下如果失败，这是致命错误，直接抛出异常
            raise
    else:
        # --- 开发环境下的逻辑 ---
        model_string = f'spleeter:{stems}stems'
        print(f"[Spleeter Subprocess] Running in DEVELOPMENT mode. Using default model: '{model_string}'")
        # 直接返回Spleeter的内置模型字符串
        return model_string


class SpleeterPart:
    def __init__(self):
        self.separator = None
        self.temp_config_path = None # 用于追踪临时文件，以便后续清理

    def _get_separator(self, stems):
        # 无论是否已有separator，都根据stems重新获取或确认
        from spleeter.separator import Separator

        # 获取模型路径或字符串
        model_path_or_string = _get_spleeter_model_path_for_separator(stems)

        # 如果返回的是一个临时文件路径（打包模式），我们就记录下来以便清理
        if os.path.exists(model_path_or_string) and model_path_or_string.endswith('.json'):
            # 如果之前有旧的临时文件，先清理掉
            if self.temp_config_path and self.temp_config_path != model_path_or_string:
                self._cleanup_temp_config()
            self.temp_config_path = model_path_or_string
        
        # 使用路径或字符串来初始化 Separator
        # 这里的 model_path_or_string 可能是 'spleeter:2stems' 或一个临时文件的路径
        self.separator = Separator(model_path_or_string)
        
        print("[Spleeter Subprocess] Spleeter Separator initialized successfully.")
        return self.separator
        
    def _cleanup_temp_config(self):
        """清理临时配置文件"""
        if self.temp_config_path and os.path.exists(self.temp_config_path):
            try:
                os.remove(self.temp_config_path)
                print(f"[Spleeter Subprocess] Cleaned up temporary config file: {self.temp_config_path}")
            except Exception as e:
                print(f"[Spleeter Subprocess] Warning: Failed to clean up temp config file: {e}")
            finally:
                self.temp_config_path = None # 清理后重置

    def _process(self, stems, input_file, output_dir, codec, bitrate):
        """统一处理方法"""
        try:
            separator = self._get_separator(stems)
            separator.separate_to_file(
                input_file,
                output_dir,
                codec=codec,
                bitrate=bitrate,
                filename_format='{filename}/{instrument}.{codec}'
            )
            print("[Spleeter Subprocess] Separation completed.")
        finally:
            # 每次处理完都清理资源，确保下次调用可以重新初始化
            self.release()

    def spleeter_2stems(self, *args):
        self._process(2, *args)

    def spleeter_4stems(self, *args):
        self._process(4, *args)

    def spleeter_5stems(self, *args):
        self._process(5, *args)

    def release(self):
        """释放所有资源"""
        self._cleanup_temp_config()
        if self.separator:
            self.separator = None
            # 可选：建议Python进行垃圾回收
            import gc
            gc.collect()
            print("[Spleeter Subprocess] Separator object and resources released.")