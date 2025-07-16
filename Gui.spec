# -*- mode: python ; coding: utf-8 -*-
import os 
import spleeter 

a = Analysis(
    ['Gui.py'],
    pathex=['.'],
    binaries=[
    ('./ffmpeg/ffmpeg.exe','ffmpeg'),
    ('./ffmpeg/ffprobe.exe','ffmpeg'),
    ('./ffmpeg/ffplay.exe','ffmpeg'),
    ],
    datas=[
        (os.path.join(spleeter.__path__[0], 'resources'), 'spleeter/resources'),
        ('./configs','configs'),
        ('./pretrained_models', 'pretrained_models'),
        ('./soniflow_ui/dist', 'soniflow_ui/dist'),
        ('./configs/user_config.json', 'configs'),
        ('logo.png', '.'),
    ],
    hiddenimports=[
        'spleeter.model.functions.unet', # Spleeter 使用的核心模型架构
        'spleeter.model.functions.separate',
        'tensorflow.python.framework.dtypes', # 经常被遗漏的依赖
        'tensorflow.python.ops.gen_logging_ops', # 同上
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='soniflow',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon = './icon.ico',
)
coll = COLLECT(
    exe,
    a.binaries, 
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='Soniflow',
)

