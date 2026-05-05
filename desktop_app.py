"""
LoL BP Assistant — 独立桌面应用（pywebview 内嵌前端）
双击 .exe 启动，零浏览器依赖。
"""
import os, sys, threading, time, logging

if getattr(sys, 'frozen', False):
    os.chdir(os.path.dirname(sys.executable))
else:
    os.chdir(os.path.dirname(os.path.abspath(__file__)))

os.makedirs('logs', exist_ok=True)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)-5s] %(name)s: %(message)s",
    datefmt="%H:%M:%S",
    filename=os.path.join('logs', 'lol-bp.log'),
    filemode='a',
)
logger = logging.getLogger(__name__)

# ── 启动 Flask ──
from app import app, start_background_threads, champ_select_state, manual_mode, manual_state, lcu_connection

HOST = "127.0.0.1"
PORT = 15000


def _manual_mode_ref():
    return manual_state


def _manual_mode_getter():
    return manual_mode


def run_flask():
    start_background_threads()
    app.run(host=HOST, port=PORT, debug=False)


threading.Thread(target=run_flask, daemon=True).start()
time.sleep(1.0)

# ── 启动 pywebview 窗口 ──
try:
    import webview

    icon_path = None
    for candidate in [
        os.path.join(os.path.dirname(os.path.abspath(__file__)), "BP.ico"),
        os.path.join(sys._MEIPASS, "BP.ico") if getattr(sys, 'frozen', False) else "",
    ]:
        if candidate and os.path.exists(candidate):
            icon_path = candidate
            break

    logger.info("启动 pywebview 窗口 (http://%s:%d)", HOST, PORT)

    window = webview.create_window(
        title="LoL BP Assistant",
        url=f"http://{HOST}:{PORT}",
        width=1280,
        height=840,
        min_size=(960, 640),
        resizable=True,
        fullscreen=False,
        text_select=True,
        confirm_close=False,
    )

    webview.start(debug=False)
    logger.info("pywebview 窗口已关闭")

except ImportError:
    logger.warning("pywebview 未安装，回退到系统浏览器")
    import webbrowser

    webbrowser.open(f"http://{HOST}:{PORT}")
    print(f"LoL BP Assistant 已启动: http://{HOST}:{PORT}")
    print("按 Ctrl+C 退出...")

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        pass

except Exception as e:
    logger.error("pywebview 启动失败: %s", e)
    import webbrowser

    webbrowser.open(f"http://{HOST}:{PORT}")
    print(f"LoL BP Assistant 已启动: http://{HOST}:{PORT}")
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        pass
