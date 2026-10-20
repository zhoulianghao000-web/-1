# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller 打包配置：单文件 exe（--windowed，不签名）。

产物：dist/SidebarIM.exe
用法：python -m PyInstaller packaging/build.spec --noconfirm --clean

说明：
- 入口 desktop/app.py，后端以静态/隐藏 import 方式打进同一个 exe（uvicorn 跑守护线程）
- pathex 让 `import server` / `import config` 等后端模块能被解析到
- excludes 掉 wxauto（只在用户显式切 wxauto 适配器时才需要，本机微信 4.x 用不上）
- console=False：无控制台窗口；日志落到 exe 同目录 logs/app.log
"""
import os

from PyInstaller.utils.hooks import collect_submodules

# spec 里的相对路径是相对 spec 文件所在目录解析的，这里统一用绝对路径
ROOT = os.path.abspath(os.path.join(SPECPATH, '..'))

hidden = [
    # 后端本体（其余依赖由 PyInstaller 顺着 server.py 自动分析）
    'server',
    'config',
    'db',
    'schemas',
    'services',
    'services.ai',
    'services.docker',
    'adapters',
    'adapters.base',
    'adapters.mock_adapter',
    'adapters.qq_adapter',
    'adapters.wxauto_adapter',
    # uvicorn 的运行时后端都是动态导入，必须显式列出
    'uvicorn',
    'uvicorn.lifespan.on',
    'uvicorn.loops.auto',
    'uvicorn.protocols.http.auto',
    'uvicorn.protocols.http.httptools_impl',
    'uvicorn.protocols.http.h11_impl',
    'uvicorn.protocols.websockets.auto',
    'uvicorn.protocols.websockets.websockets_impl',
    'uvicorn.protocols.websockets.wsproto_impl',
    # UI
    'PySide6.QtWebSockets',
    'PySide6.QtNetwork',
    # win32
    'win32clipboard',
    'win32gui',
    'win32api',
    'win32con',
    'win32process',
    'win32com.client',
    'pythoncom',
    # 其它
    'httpx',
    'dotenv',
    'anyio._backends._asyncio',
] + collect_submodules('starlette')

a = Analysis(
    [os.path.join(ROOT, 'desktop', 'app.py')],
    pathex=[ROOT, os.path.join(ROOT, 'backend'), os.path.join(ROOT, 'desktop')],
    binaries=[],
    datas=[],
    hiddenimports=hidden,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=['tkinter', 'wxauto', 'pytest', 'numpy', 'PIL'],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='SidebarIM',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,  # 不签名
    entitlements_file=None,
    icon=None,
)
