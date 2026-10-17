# -*- mode: python ; coding: utf-8 -*-


a = Analysis(
    ['app.py'],
    pathex=[],
    binaries=[],
    datas=[('icon.png', '.'), ('avatar.png', '.'), ('assets', 'assets'), ('project', 'project'), ('plugins', 'plugins'), ('translation_guidelines','translation_guidelines')],
    hiddenimports=['tiktoken_ext.openai_public', 'tiktoken_ext'],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=['torch','onnx','onnxruntime','librosa','soundfile'],
    noarchive=False,
    optimize=0,
)
# These are complete, independently built runtimes. Add them after Analysis so
# PyInstaller does not scan their DLLs again and copy another CUDA runtime into
# the main executable's _internal directory. Keep each backend's DLLs together.
for runtime_dir in ('llama', 'crispasr', 'separate', 'ffmpeg', 'translate'):
    a.datas += Tree(runtime_dir, prefix=runtime_dir, typecode='DATA')

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='VoiceTransl',
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
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='VoiceTransl',
)
