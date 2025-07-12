# spleeter_part.py
class spleeter_part():
    def __init__(self):
        self.separator = None

    def _get_separator(self, stems):
        """延迟加载模型"""
        if self.separator is None:
            from spleeter.separator import Separator  # 延迟导入
            self.separator = Separator(f'spleeter:{stems}stems')
        return self.separator

    def spleeter_2stems(self, *args):
        self._process(2, *args)

    def spleeter_4stems(self, *args):
        self._process(4, *args)

    def spleeter_5stems(self, *args):
        self._process(5, *args)

    def _process(self, stems, input_file, output_dir, codec, bitrate):
        """统一处理方法"""
        separator = self._get_separator(stems)
        separator.separate_to_file(
            input_file,
            output_dir,
            codec=codec,
            bitrate=bitrate,
            filename_format='{filename}/{instrument}.{codec}'
        )

    def release(self):
        """显式释放资源"""
        if self.separator:
            self.separator = None
        # 清理TensorFlow资源
        # import tensorflow as tf
        # tf.keras.backend.clear_session()
