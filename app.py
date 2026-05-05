"""
LoL 排位赛 BP 辅助工具 - 主程序
Flask 路由 + 状态管理 + LCU 自动检测
"""

import json
import os
import threading
import time
import logging
import webbrowser
import requests
import urllib3
from flask import Flask, jsonify, render_template, request
from flask_cors import CORS

from champion_data import get_champion_data
from meta_fetcher import update_meta_if_needed, META_LIVE_CACHE
from lcu import poll_lcu, fetch_teammate_mastery
from engine import build_and_store, build_ban_recommendations, analyze_composition, manual_build

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# PyInstaller 兼容：指定模板路径
import sys as _sys
_TEMPLATE_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'templates')
if getattr(_sys, 'frozen', False):
    _TEMPLATE_DIR = os.path.join(_sys._MEIPASS, 'templates')

# ── 日志 ─────────────────────────────────────────────────────────────────────────
import sys as _sys
_is_console = _sys.stdout and hasattr(_sys.stdout, 'isatty') and _sys.stdout.isatty()
LOG_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'logs')
os.makedirs(LOG_DIR, exist_ok=True)
if _is_console:
    logging.basicConfig(level=logging.DEBUG, format="%(asctime)s [%(levelname)-5s] %(name)s: %(message)s", datefmt="%H:%M:%S")
else:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)-5s] %(name)s: %(message)s", datefmt="%H:%M:%S",
                        filename=os.path.join(LOG_DIR, 'lol-bp.log'), filemode='a')
logger = logging.getLogger(__name__)

VERSION = "2.2.0"

# ── 全局状态 ───────────────────────────────────────────────────────────────────
champ_select_state = {
    "connected": False,
    "in_champ_select": False,
    "gameflow_phase": "",
    "my_team_bans": [],
    "enemy_bans": [],
    "my_team_picks": [],
    "enemy_picks": [],
    "my_prepicks": [],
    "enemy_prepicks": [],
    "my_position": "",
    "phase": "BAN_PICK",
    "recommendations": [],
    "timer": {"phase": "idle", "total_sec": 0, "remaining_sec": 0},
    "action_seq": [],
    "next_action": None,
}

lcu_connection = {"headers": {}, "base_url": "", "active": False}

manual_mode = False
manual_state = {
    "my_bans": [],
    "enemy_bans": [],
    "my_picks": [],
    "enemy_picks": [],
    "my_prepicks": [],
    "enemy_prepicks": [],
    "my_position": "",
}

cd = get_champion_data()


# ── LCU 回调 ──────────────────────────────────────────────────────────────────
def _on_session_parsed(parsed_state, raw_session=None):
    teammate_pool = {}
    if lcu_connection.get("active"):
        teammate_pool = fetch_teammate_mastery(
            lcu_connection["headers"], lcu_connection["base_url"], raw_session
        )
    build_and_store(champ_select_state, teammate_pool)


# ── 手动模式推荐 ────────────────────────────────────────────────────────────────
def manual_build_recommendations():
    return manual_build(manual_state)


# ── Flask 应用 ────────────────────────────────────────────────────────────────
app = Flask(__name__, template_folder=_TEMPLATE_DIR)
CORS(app)


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/state")
def api_state():
    if manual_mode:
        recs, counters = manual_build_recommendations()
        my_bans = manual_state["my_bans"]
        enemy_bans = manual_state["enemy_bans"]
        my_pick_entries = manual_state["my_picks"]
        enemy_pick_entries = manual_state["enemy_picks"]
        my_pick_ids = [p["champion_id"] for p in my_pick_entries]
        enemy_pick_ids = [p["champion_id"] for p in enemy_pick_entries]
        used = set(my_bans + enemy_bans + my_pick_ids + enemy_pick_ids)

        ban_recs = build_ban_recommendations(
            used, manual_state.get("my_prepicks", my_pick_ids), manual_state.get("enemy_prepicks", enemy_pick_ids),
            manual_state["my_position"]
        )
        my_comp = analyze_composition(my_pick_ids)
        enemy_comp = analyze_composition(enemy_pick_ids)

        return jsonify({
            "connected": True,
            "in_champ_select": True,
            "my_team_bans": my_bans,
            "enemy_bans": enemy_bans,
            "my_team_picks": my_pick_entries,
            "enemy_picks": enemy_pick_entries,
            "my_position": manual_state["my_position"],
            "phase": "BAN_PICK",
            "recommendations": recs,
            "counter_heroes": [{
                "champion_id": c["champion_id"],
                "name": c["name"],
                "image_url": c["image_url"],
                "role": c["role"],
                "counters": c["counters"],
            } for c in counters],
            "ban_recommendations": ban_recs,
            "my_composition": my_comp,
            "enemy_composition": enemy_comp,
            "timer": {"phase": "manual", "total_sec": 0, "remaining_sec": 0},
            "action_seq": [],
            "next_action": None,
            "manual_mode": True,
        })
    state = dict(champ_select_state)
    state["manual_mode"] = False
    return jsonify(state)


@app.route("/api/champions")
def api_champions():
    result = {}
    for key in cd.all_champions():
        result[str(key)] = {
            "name": cd.get_name(key),
            "image_url": cd.get_image(key),
            "role": cd.get_role(key),
            "tier": cd.get_tier(key),
            "winrate": cd.get_winrate(key),
            "pickrate": cd.get_pickrate(key),
            "banrate": cd.get_banrate(key),
            "tags": cd.get_tags(key),
        }
    return jsonify(result)


@app.route("/api/meta")
def api_meta():
    meta_list = []
    for key in cd.all_champions():
        m = cd.get_meta(key)
        meta_list.append({
            "key": key,
            "name": cd.get_name(key),
            "role": cd.get_role(key),
            "tier": m.get("tier", "B"),
            "winrate": m.get("wr", 50.0),
            "pickrate": m.get("pr", 3.0),
            "banrate": m.get("br", 2.0),
        })
    tier_order = {"S": 0, "A": 1, "B": 2, "C": 3}
    meta_list.sort(key=lambda x: (tier_order.get(x["tier"], 2), -x["winrate"]))
    return jsonify(meta_list)


# ── 手动模式 API ────────────────────────────────────────────────────────────────
@app.route("/api/manual/start", methods=["POST"])
def manual_start():
    global manual_mode
    manual_mode = True
    return jsonify({"ok": True, "manual_mode": True})


@app.route("/api/manual/stop", methods=["POST"])
def manual_stop():
    global manual_mode
    manual_mode = False
    return jsonify({"ok": True, "manual_mode": False})


@app.route("/api/manual/state", methods=["GET"])
def manual_get_state():
    return jsonify(manual_state)


@app.route("/api/manual/reset", methods=["POST"])
def manual_reset():
    global manual_state
    manual_state = {"my_bans": [], "enemy_bans": [], "my_picks": [], "enemy_picks": [], "my_position": ""}
    return jsonify({"ok": True, "state": manual_state})


@app.route("/api/manual/set-position", methods=["POST"])
def manual_set_position():
    data = request.json
    manual_state["my_position"] = data.get("position", "")
    return jsonify({"ok": True})


@app.route("/api/manual/add-ban", methods=["POST"])
def manual_add_ban():
    data = request.json
    team = data.get("team", "enemy")
    champion_key = data.get("champion_key")
    if not champion_key:
        return jsonify({"ok": False, "error": "missing champion_key"}), 400
    if team == "my":
        if champion_key not in manual_state["my_bans"]:
            manual_state["my_bans"].append(champion_key)
        if len(manual_state["my_bans"]) > 5:
            manual_state["my_bans"] = manual_state["my_bans"][:5]
    else:
        if champion_key not in manual_state["enemy_bans"]:
            manual_state["enemy_bans"].append(champion_key)
        if len(manual_state["enemy_bans"]) > 5:
            manual_state["enemy_bans"] = manual_state["enemy_bans"][:5]
    return jsonify({"ok": True, "state": manual_state})


@app.route("/api/manual/add-pick", methods=["POST"])
def manual_add_pick():
    data = request.json
    team = data.get("team", "enemy")
    champion_key = data.get("champion_key")
    position = data.get("position", "")
    if not position:
        position = cd.get_role(champion_key)
    if not champion_key:
        return jsonify({"ok": False, "error": "missing champion_key"}), 400
    pick_entry = {"champion_id": champion_key, "position": position}
    if team == "my":
        if champion_key not in [p["champion_id"] for p in manual_state["my_picks"]]:
            manual_state["my_picks"].append(pick_entry)
    else:
        if champion_key not in [p["champion_id"] for p in manual_state["enemy_picks"]]:
            manual_state["enemy_picks"].append(pick_entry)
    return jsonify({"ok": True, "state": manual_state})


@app.route("/api/manual/remove-ban", methods=["POST"])
def manual_remove_ban():
    data = request.json
    team = data.get("team", "enemy")
    champion_key = data.get("champion_key")
    if team == "my":
        manual_state["my_bans"] = [b for b in manual_state["my_bans"] if b != champion_key]
    else:
        manual_state["enemy_bans"] = [b for b in manual_state["enemy_bans"] if b != champion_key]
    return jsonify({"ok": True})


@app.route("/api/manual/remove-pick", methods=["POST"])
def manual_remove_pick():
    data = request.json
    team = data.get("team", "enemy")
    champion_key = data.get("champion_key")
    if team == "my":
        manual_state["my_picks"] = [p for p in manual_state["my_picks"] if p["champion_id"] != champion_key]
    else:
        manual_state["enemy_picks"] = [p for p in manual_state["enemy_picks"] if p["champion_id"] != champion_key]
    return jsonify({"ok": True})


@app.route("/api/diagnose")
def api_diagnose():
    import os, psutil
    result = {
        "connected": champ_select_state.get("connected", False),
        "in_champ_select": champ_select_state.get("in_champ_select", False),
        "gameflow_phase": champ_select_state.get("gameflow_phase", ""),
        "manual_mode": manual_mode,
    }
    lcu_procs = []
    for proc in psutil.process_iter(["name", "cmdline", "exe"]):
        try:
            name = (proc.info["name"] or "").lower()
            if name in ("leagueclientux.exe", "leagueclient.exe",
                        "league of legends.exe", "riotclientservices.exe"):
                cmd = " ".join(proc.info["cmdline"] or [])
                lcu_procs.append({
                    "name": name,
                    "exe": proc.info.get("exe", ""),
                    "has_port": "--app-port=" in cmd or "--riotclient-app-port=" in cmd,
                })
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            pass
    result["lcu_processes_found"] = len(lcu_procs)
    result["lcu_processes"] = lcu_procs[:5]

    lockfiles_found = []
    for lf in ["C:/Program Files/League of Legends/lockfile",
               "C:/Riot Games/League of Legends/lockfile",
               "D:/WeGame/英雄联盟/lockfile"]:
        if os.path.exists(lf):
            lockfiles_found.append(lf)
    result["lockfiles_found"] = lockfiles_found

    if lcu_connection.get("active") and lcu_connection.get("headers"):
        try:
            r = requests.get(
                f"{lcu_connection['base_url']}/lol-gameflow/v1/gameflow-phase",
                headers=lcu_connection["headers"],
                verify=False, timeout=3
            )
            result["lcu_api_test"] = {
                "ok": r.status_code == 200,
                "status": r.status_code,
                "phase": r.text.strip().strip('"') if r.status_code == 200 else None,
            }
        except Exception as e:
            result["lcu_api_test"] = {"ok": False, "error": str(e)}

    return jsonify(result)


@app.route("/api/search")
def api_search():
    q = request.args.get("q", "").lower().strip()
    if not q or len(q) < 1:
        return jsonify([])
    results = []
    for key in cd.all_champions():
        name = cd.get_name(key)
        role = cd.get_role(key)
        if q in name.lower() or q in role.lower():
            results.append({
                "key": key,
                "name": name,
                "image_url": cd.get_image(key),
                "role": role,
                "tier": cd.get_tier(key),
            })
    results.sort(key=lambda x: ({"S": 0, "A": 1, "B": 2, "C": 3}.get(x["tier"], 2), x["name"]))
    return jsonify(results[:20])


@app.route("/api/available")
def api_available():
    if manual_mode:
        all_banned = set(manual_state["my_bans"] + manual_state["enemy_bans"])
        all_picked = set([p["champion_id"] for p in manual_state["my_picks"] + manual_state["enemy_picks"]])
    else:
        all_banned = set(champ_select_state.get("my_team_bans", []) +
                          champ_select_state.get("enemy_bans", []))
        all_picked = set([p["champion_id"] for p in
                          champ_select_state.get("my_team_picks", []) +
                          champ_select_state.get("enemy_picks", [])])
    used = all_banned | all_picked
    champions = []
    for key in cd.all_champions():
        meta = cd.get_meta(key)
        champions.append({
            "key": key,
            "name": cd.get_name(key),
            "image_url": cd.get_image(key),
            "role": cd.get_role(key),
            "tier": meta.get("tier", "B"),
            "winrate": meta.get("wr", 50.0),
            "banned": key in all_banned,
            "picked": key in all_picked,
            "available": key not in used,
        })
    tier_order = {"S": 0, "A": 1, "B": 2, "C": 3}
    champions.sort(key=lambda x: (
        0 if x["available"] else 1,
        tier_order.get(x["tier"], 2),
        -x["winrate"]
    ))
    return jsonify(champions)


@app.route("/api/meta/status")
def api_meta_status():
    import os
    if os.path.exists(META_LIVE_CACHE):
        try:
            with open(META_LIVE_CACHE, "r", encoding="utf-8") as f:
                cached = json.load(f)
            age_hours = (time.time() - cached.get("cached_at", 0)) / 3600
            return jsonify({
                "source": "live",
                "version": cached.get("version", "unknown"),
                "age_hours": round(age_hours, 1),
                "champions_count": len(cached.get("meta", {})),
            })
        except Exception:
            pass
    return jsonify({"source": "builtin", "version": cd.version, "age_hours": None})


@app.route("/api/meta/refresh", methods=["POST"])
def api_meta_refresh():
    global cd
    updated, msg = update_meta_if_needed(cd, force=True)
    if updated:
        return jsonify({"ok": True, "message": msg, "champions_updated": len(updated)})
    return jsonify({"ok": False, "message": msg})


@app.route("/api/version")
def api_version():
    return jsonify({"version": VERSION})


# ── 后台线程 ──────────────────────────────────────────────────────────────────
_threads_started = False


def start_background_threads():
    global _threads_started
    if _threads_started:
        return
    _threads_started = True

    update_meta_if_needed(cd, force=False)

    def _manual_mode_getter():
        return manual_mode

    t = threading.Thread(
        target=poll_lcu,
        args=(champ_select_state, lcu_connection, _manual_mode_getter, _on_session_parsed),
        daemon=True,
    )
    t.start()
    logger.info("LCU 后台轮询已启动")


if __name__ == "__main__":
    updated_meta, meta_msg = update_meta_if_needed(cd, force=False)
    logger.info("启动 LoL BP Assistant %s", VERSION)
    logger.info("已加载 %d 个英雄 (Data Dragon %s)", len(cd.champions), cd.version)
    logger.info("Meta数据: %s", meta_msg)

    start_background_threads()

    print()
    print("=" * 55)
    print(f"  LoL BP Assistant  {VERSION}")
    print("=" * 55)
    print(f"  打开浏览器访问: http://localhost:5000")
    print("  自动检测 LoL 客户端并读取选英雄数据")
    print("=" * 55)

    # 启动后自动打开浏览器
    def _open_browser():
        time.sleep(0.5)
        webbrowser.open("http://localhost:5000")
    threading.Thread(target=_open_browser, daemon=True).start()

    app.run(host="0.0.0.0", port=5000, debug=False)
