"""
PyInstaller 打包脚本
运行: python build_exe.py
生成: dist/LoL_BP_Assistant.exe
"""
import PyInstaller.__main__
import os, sys

os.chdir(os.path.dirname(os.path.abspath(__file__)))

PyInstaller.__main__.run([
    'desktop_app.py',
    '--name=LoL_BP_Assistant',
    '--onefile',
    '--windowed',
    '--noconsole',
    '--add-data=templates;templates',
    '--add-data=data;data',
    '--add-data=static;static',
    '--add-data=BP.ico;.',
    '--add-data=logs;logs',
    '--hidden-import=flask',
    '--hidden-import=flask_cors',
    '--hidden-import=engine',
    '--hidden-import=champion_data',
    '--hidden-import=lcu',
    '--hidden-import=meta_fetcher',
    '--hidden-import=psutil',
    '--hidden-import=requests',
    '--hidden-import=urllib3',
    '--hidden-import=websocket',
    '--hidden-import=webview',
    '--hidden-import=webview.platforms.edgechromium',
    '--hidden-import=webview.platforms.cef',
    '--hidden-import=webview.platforms.winforms',
    '--hidden-import=clr',
    '--hidden-import=json',
    '--hidden-import=logging',
    '--hidden-import=threading',
    '--hidden-import=asyncio',
    '--hidden-import=hashlib',
    '--hidden-import=re',
    '--collect-all=webview',
    '--icon=BP.ico',
    '--clean',
])
print("\nBuild complete: dist/LoL_BP_Assistant.exe")
