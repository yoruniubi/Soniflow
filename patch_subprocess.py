# patch_subprocess.py
import subprocess
import sys

# 这个补丁只应该在 Windows 系统上应用
if sys.platform == 'win32':
    # 定义一个新的 Popen 类，它继承自原始的 Popen
    class NoWindowPopen(subprocess.Popen):
        def __init__(self, *args, **kwargs):
            # 创建一个 STARTUPINFO 结构体
            startupinfo = subprocess.STARTUPINFO()
            
            # 设置标志，为子进程创建一个新的、隐藏的控制台
            startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
            # startupinfo.dwFlags |= subprocess.CREATE_NEW_CONSOLE 
            # 隐藏这个窗口
            startupinfo.wShowWindow = subprocess.SW_HIDE

            # 将修改后的 startupinfo 传递给 Popen 的构造函数
            kwargs["startupinfo"] = startupinfo
            
            # 调用原始 Popen 的 __init__ 方法
            super().__init__(*args, **kwargs)

    subprocess.Popen = NoWindowPopen