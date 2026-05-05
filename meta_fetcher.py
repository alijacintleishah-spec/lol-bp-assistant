"""
Meta 数据自动更新模块
从 OP.GG MCP API 获取实时胜率/tier 数据
检测 Data Dragon 版本变化自动触发更新
"""

import json
import os
import re
import sys
import time
import requests

import logging

logger = logging.getLogger(__name__)

META_CACHE_HOURS = 24

if getattr(sys, 'frozen', False):
    DATA_DIR = os.path.join(sys._MEIPASS, "data")
else:
    DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")
META_LIVE_CACHE = os.path.join(DATA_DIR, "champion_meta_live.json")

# OP.GG 位置名 → 标准位置名
POSITION_MAP = {"top": "top", "mid": "mid", "jungle": "jungle", "adc": "bot", "support": "support"}

# OP.GG tier → 标准 tier
TIER_MAP = {1: "S", 2: "A", 3: "B", 4: "C", 5: "C"}


DD_VERSION_URL = "https://ddragon.leagueoflegends.com/api/versions.json"
OPGG_MCP_URL = "https://mcp-api.op.gg/mcp"


def get_latest_dd_version():
    """获取最新的 Data Dragon 版本"""
    try:
        r = requests.get(DD_VERSION_URL, timeout=10)
        return r.json()[0]
    except Exception:
        return None


def fetch_opgg_meta():
    """从 OP.GG MCP 获取所有位置的 meta 数据"""
    # 初始化 MCP 会话
    try:
        init_payload = {
            "jsonrpc": "2.0", "id": 0, "method": "initialize",
            "params": {"protocolVersion": "2024-11-05", "capabilities": {},
                       "clientInfo": {"name": "lol-bp", "version": "2.0"}}
        }
        r = requests.post(OPGG_MCP_URL, json=init_payload,
                          headers={"Content-Type": "application/json"}, timeout=10)
        if r.status_code != 200:
            return None

        # 调用 meta API
        call_payload = {
            "jsonrpc": "2.0", "id": 2, "method": "tools/call",
            "params": {"name": "lol_list_lane_meta_champions", "arguments": {}}
        }
        r2 = requests.post(OPGG_MCP_URL, json=call_payload,
                           headers={"Content-Type": "application/json"}, timeout=20)
        if r2.status_code != 200:
            return None

        data = r2.json()
        content = data.get("result", {}).get("content", [])
        if not content:
            return None

        text = "".join([c["text"] for c in content if c["type"] == "text"])
        return parse_opgg_response(text)

    except Exception as e:
        logger.error("OP.GG fetch failed: %s", e)
        return None


def parse_opgg_response(text):
    """解析 OP.GG 返回的 meta 数据文本"""
    # 格式: Position("ChampionName",is_rip,play,win,kill,win_rate,pick_rate,role_rate,ban_rate,kda,tier,rank,rank_prev,rank_prev_patch)
    # 解析每个位置的 champion 数据
    result = {}

    for pos_key in ["Top", "Mid", "Jungle", "Adc", "Support"]:
        # 匹配该位置的所有条目
        # 模式: Pos("Name",bool,num,num,num,num,num,num,num,num,num,num,num,num)
        pattern = rf'{pos_key}\("([^"]+)",(true|false),(\d+),(\d+),(\d+),([\d.]+),([\d.]+),([\d.]+),([\d.]+),([\d.]+),(\d+),(\d+),(\d+),(\d+)\)'
        matches = re.findall(pattern, text)

        role = POSITION_MAP.get(pos_key.lower(), "unknown")

        for m in matches:
            name = m[0]
            # is_rip = m[1] == "true"
            # play = int(m[2])
            # win = int(m[3])
            # kill = int(m[4])
            win_rate = float(m[5])
            pick_rate = float(m[6])
            # role_rate = float(m[7])
            ban_rate = float(m[8])
            # kda = float(m[9])
            tier_raw = int(m[10])
            rank = int(m[11])
            # rank_prev = int(m[12])
            # rank_prev_patch = int(m[13])

            tier = TIER_MAP.get(tier_raw, "B")

            result[name] = {
                "role": role,
                "tier": tier,
                "winrate": round(win_rate * 100, 1),
                "pickrate": round(pick_rate * 100, 1),
                "banrate": round(ban_rate * 100, 1),
                "rank": rank,
            }

    return result if result else None


def merge_meta_with_champions(champion_data, opgg_meta):
    """
    将 OP.GG meta 数据合并到 champion 数据结构中
    返回: {champion_key: {tier, wr, pr, br, role}}
    """
    merged = {}

    # 构建 name → key 的映射
    name_to_keys = {}
    for key, info in champion_data.champions.items():
        name_lower = info["name"].lower().strip()
        if name_lower not in name_to_keys:
            name_to_keys[name_lower] = []
        name_to_keys[name_lower].append(key)

    # 构建 OP.GG name → key 的精确映射
    opgg_name_to_key = {}
    for opgg_name, meta in opgg_meta.items():
        name_lower = opgg_name.lower().strip()
        if name_lower in name_to_keys:
            # 找到匹配
            for key in name_to_keys[name_lower]:
                # 检查角色是否匹配
                cd_role = champion_data.get_role(key)
                if cd_role == meta["role"] or meta["role"] in ["bot"] and cd_role == "bot":
                    opgg_name_to_key[key] = meta
                    break
            else:
                # 角色不匹配，仍用第一个key
                opgg_name_to_key[name_to_keys[name_lower][0]] = meta

    # 合并
    for key in champion_data.all_champions():
        if key in opgg_name_to_key:
            m = opgg_name_to_key[key]
            merged[key] = {
                "tier": m["tier"],
                "wr": m["winrate"],
                "pr": m["pickrate"],
                "br": m["banrate"],
            }
        else:
            # 没有 OP.GG 数据，使用内置默认值
            from champion_data import META_DATA
            builtin = META_DATA.get(key, {"tier": "B", "wr": 50.0, "pr": 3.0, "br": 2.0})
            merged[key] = {
                "tier": builtin.get("tier", "B"),
                "wr": builtin.get("wr", 50.0),
                "pr": builtin.get("pr", 3.0),
                "br": builtin.get("br", 2.0),
            }

    return merged


def update_meta_if_needed(champion_data, force=False):
    """
    检查是否需要更新 meta 数据，如果需要则从 OP.GG 获取
    返回: (updated_meta_dict or None, status_message)
    """
    os.makedirs(DATA_DIR, exist_ok=True)

    latest_version = get_latest_dd_version()
    if not latest_version:
        return None, "无法获取最新版本号"

    # 检查缓存
    cached_meta = None
    cache_version = None
    if os.path.exists(META_LIVE_CACHE):
        try:
            with open(META_LIVE_CACHE, "r", encoding="utf-8") as f:
                cached = json.load(f)
            cached_meta = cached.get("meta", {})
            cache_version = cached.get("version", "")
            cache_time = cached.get("cached_at", 0)
        except Exception:
            pass

    # 判断是否需要更新
    needs_update = force
    if not needs_update:
        if cache_version != latest_version:
            needs_update = True
        elif time.time() - cached.get("cached_at", 0) > META_CACHE_HOURS * 3600:
            needs_update = True
        elif not cached_meta:
            needs_update = True

    if not needs_update:
        return cached_meta, f"数据已是最新 (版本 {cache_version})"

    # 需要更新
    logger.info("检测到版本变化或缓存过期，从 OP.GG 获取最新数据...")
    opgg_meta = fetch_opgg_meta()

    if not opgg_meta:
        if cached_meta:
            return cached_meta, "OP.GG 获取失败，使用缓存数据"
        return None, "OP.GG 获取失败，无缓存可用"

    merged = merge_meta_with_champions(champion_data, opgg_meta)

    # 缓存到文件
    cache_data = {
        "version": latest_version,
        "cached_at": time.time(),
        "meta": merged,
    }
    with open(META_LIVE_CACHE, "w", encoding="utf-8") as f:
        json.dump(cache_data, f, ensure_ascii=False)

    logger.info("已更新 %d 个英雄的 meta 数据 (版本 %s)", len(merged), latest_version)
    return merged, f"已更新到版本 {latest_version}"


def get_live_meta(champion_key):
    """获取单个英雄的实时 meta 数据（优先使用 OP.GG 数据）"""
    if os.path.exists(META_LIVE_CACHE):
        try:
            with open(META_LIVE_CACHE, "r", encoding="utf-8") as f:
                cached = json.load(f)
            meta = cached.get("meta", {})
            key_str = str(champion_key)
            if key_str in meta:
                return meta[key_str]
        except Exception:
            pass

    # 回退到内置数据
    from champion_data import META_DATA
    builtin = META_DATA.get(champion_key, {"tier": "B", "wr": 50.0, "pr": 3.0, "br": 2.0})
    return builtin
