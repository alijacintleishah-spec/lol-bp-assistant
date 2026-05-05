"""
LoL BP Assistant — 桌面版 (无终端)
"""
import subprocess, sys, os
os.chdir(os.path.dirname(os.path.abspath(__file__)))
subprocess.Popen([sys.executable, "desktop_app.py"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, creationflags=subprocess.CREATE_NO_WINDOW)
