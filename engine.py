"""
Recommendation scoring engine.
Pure functions — no global state mutation.
"""

from champion_data import get_champion_data

cd = get_champion_data()


def _pick_id(pick):
    """Extract champion_id from int or dict."""
    if isinstance(pick, dict):
        return pick["champion_id"]
    return pick


def _pick_position(pick, cd):
    """Extract assigned position from dict, fallback to champion default role."""
    if isinstance(pick, dict) and pick.get("position"):
        return pick["position"]
    return cd.get_role(_pick_id(pick))


def build_recommendations(used_ids, my_picks, enemy_picks, my_position,
                          teammate_pool=None, top_n=12):
    """综合评分推荐引擎 — 返回 (recommendations, counter_heroes).

    enemy_picks 支持 list[int] 或 list[dict] (带 position 字段).
    teammate_pool: {champion_id: weight} 队友/自己擅长的英雄
    """
    if teammate_pool is None:
        teammate_pool = {}
    scored = []
    # 标准化 my_picks 为纯 id 列表
    my_pick_ids = [_pick_id(p) for p in my_picks]

    for ckey in cd.all_champions():
        if ckey in used_ids:
            continue

        score = 0.0
        reasons = []
        meta = cd.get_meta(ckey)

        # 1. 版本强度 (0-30)
        tier_bonus = {"S": 30, "A": 18, "B": 6, "C": -5}.get(meta.get("tier", "B"), 6)
        wr_bonus = round((meta.get("wr", 50) - 50) * 3.5, 1)
        score += tier_bonus + wr_bonus

        if meta.get("tier") == "S":
            reasons.append("版本T0")

        # 2. 位置匹配
        role = cd.get_role(ckey)
        position_match = False
        if my_position:
            pos_map = {"top": "top", "jungle": "jungle", "mid": "mid",
                       "bottom": "bot", "utility": "support", "support": "support"}
            mapped = pos_map.get(my_position.lower(), "")
            if mapped and role == mapped:
                score += 15
                position_match = True

        # 3. 协同
        syn_score, syn_names = cd.get_synergy_score(ckey, my_pick_ids)
        if syn_names:
            reasons.append(f"协同{'/'.join(syn_names)}")
        score += syn_score * 0.7

        # 4. 克制 / 被克制
        counter_score = 0
        countered_score = 0
        counter_names = []
        countered_names = []
        c_ekeys = []
        cd_ekeys = []

        for ep in enemy_picks:
            ek = _pick_id(ep)
            ek_role = _pick_position(ep, cd)
            lane_w = cd.get_lane_weight(my_position, ek_role) if my_position else 1.0

            c_s, c_ns = cd.get_counter_score(ckey, [ek])
            cd_s, cd_ns = cd.get_countered_score(ckey, [ek])

            c_s = int(c_s * lane_w)
            cd_s = int(cd_s * lane_w)

            if c_s >= 12:
                counter_score += c_s
                counter_names.extend(c_ns)
                if c_s > 0:
                    c_ekeys.append(ek)
            if cd_s >= 12:
                countered_score += cd_s
                countered_names.extend(cd_ns)
                if cd_s > 0:
                    cd_ekeys.append(ek)

        # 冲突检测
        conflict_keys = set(c_ekeys) & set(cd_ekeys)
        for ek in conflict_keys:
            # re-find the original ep for position
            ek_role = cd.get_role(ek)
            for ep in enemy_picks:
                if _pick_id(ep) == ek:
                    ek_role = _pick_position(ep, cd)
                    break
            lane_w = cd.get_lane_weight(my_position, ek_role) if my_position else 1.0
            c_s, _ = cd.get_counter_score(ckey, [ek])
            cd_s, _ = cd.get_countered_score(ckey, [ek])
            c_s = int(c_s * lane_w)
            cd_s = int(cd_s * lane_w)
            if c_s >= cd_s:
                cd_ekeys.remove(ek)
                countered_score -= cd_s
            else:
                c_ekeys.remove(ek)
                counter_score -= c_s

        # 区分对位克制和普通克制
        counter_names_direct = []
        counter_names_normal = []
        for ek in c_ekeys:
            ek_role = cd.get_role(ek)
            for ep in enemy_picks:
                if _pick_id(ep) == ek:
                    ek_role = _pick_position(ep, cd)
                    break
            lane_w = cd.get_lane_weight(my_position, ek_role) if my_position else 1.0
            en = cd.get_name(ek)
            if lane_w >= 1.0 and my_position and ek_role == my_position:
                counter_names_direct.append(en)
            else:
                counter_names_normal.append(en)

        countered_names = [cd.get_name(ek) for ek in cd_ekeys]

        if counter_names_direct:
            reasons.insert(0, f"对位克制{'/'.join(counter_names_direct)}")
            score += len(counter_names_direct) * 8
        if counter_names_normal:
            reasons.insert(0 if not counter_names_direct else 1,
                           f"克制{'/'.join(counter_names_normal)}")
        score += counter_score * 1.0

        if countered_names:
            cd_direct = [n for n in countered_names
                         if any(cd.get_role(ek) == my_position for ek in cd_ekeys
                                if cd.get_name(ek) == n and my_position)]
            cd_other = [n for n in countered_names if n not in cd_direct]
            if cd_direct:
                reasons.append(f"对位被{'/'.join(cd_direct)}克制")
                score -= len(cd_direct) * 10
            if cd_other:
                reasons.append(f"被{'/'.join(cd_other)}克制")
        score -= countered_score * 0.8

        # 6. 队友/自己熟练度加成
        if ckey in teammate_pool:
            prof_bonus = teammate_pool[ckey]
            score += prof_bonus
            reasons.append("队友擅长")

        # 7. ban率加成
        br = meta.get("br", 2)
        if br > 8:
            score += 8
        elif br > 5:
            score += 4

        # 8. 阵容平衡
        team_roles = [cd.get_role(p) for p in my_pick_ids]
        if role not in team_roles and my_position:
            score += 8

        if not reasons:
            reasons.append("稳定选择")

        scored.append({
            "champion_id": ckey,
            "name": cd.get_name(ckey),
            "image_url": cd.get_image(ckey),
            "role": role,
            "tier": meta.get("tier", "B"),
            "winrate": meta.get("wr", 50.0),
            "pickrate": meta.get("pr", 3.0),
            "banrate": meta.get("br", 2.0),
            "score": round(score, 1),
            "position_match": position_match,
            "reasons": reasons,
            "counters": counter_names,
            "countered_by": countered_names,
        })

    scored.sort(key=lambda x: (-x["score"], -x["winrate"]))

    # ── 位置覆盖保障: 确保 5 个位置都至少有 1 个推荐 ──
    POSITIONS = ["top", "jungle", "mid", "bot", "support"]
    result = scored[:top_n]
    covered = {r["role"] for r in result}
    # 找缺位并按重要性处理: 优先补 my_position
    missing = [p for p in POSITIONS if p not in covered]
    if my_position and my_position in missing:
        missing.remove(my_position)
        missing.insert(0, my_position)
    while missing:
        pos = missing.pop(0)
        best = None
        for ckey in cd.filter_by_role(pos):
            if ckey in used_ids or ckey in {r["champion_id"] for r in result}:
                continue
            meta = cd.get_meta(ckey)
            wr = meta.get("wr", 50)
            if best is None or wr > best["wr"]:
                best = {"champion_id": ckey, "wr": wr, "meta": meta}
        if best:
            meta = best["meta"]
            filler = {
                "champion_id": best["champion_id"],
                "name": cd.get_name(best["champion_id"]),
                "image_url": cd.get_image(best["champion_id"]),
                "role": pos,
                "tier": meta.get("tier", "B"),
                "winrate": meta.get("wr", 50.0),
                "pickrate": meta.get("pr", 3.0),
                "banrate": meta.get("br", 2.0),
                "score": max(0, round((meta.get("wr", 50) - 48) * 2.5, 1)),
                "position_match": my_position and pos == my_position,
                "reasons": ["对线优势"],
                "counters": [],
                "countered_by": [],
            }
            # 替换 result 中最后一个重复位置的条目，或追加
            pos_counts = {}
            for i, r in enumerate(result):
                pos_counts[r["role"]] = pos_counts.get(r["role"], 0) + 1
            replaced = False
            for i in range(len(result) - 1, -1, -1):
                old_role = result[i]["role"]
                if pos_counts.get(old_role, 0) > 1:
                    result[i] = filler
                    pos_counts[old_role] -= 1
                    replaced = True
                    break
            if not replaced and len(result) < top_n:
                result.append(filler)
    scored = result

    counter_heroes = [s for s in scored if s["counters"] and s["score"] > 30]
    for ch in counter_heroes:
        ch["score"] += 5

    scored.sort(key=lambda x: (-x["score"], -x["winrate"]))
    return scored[:top_n], counter_heroes[:6]


def build_and_store(mstate, teammate_pool=None):
    """Build recommendations from mstate and store them back into mstate."""
    if teammate_pool is None:
        teammate_pool = {}

    my_bans = mstate.get("my_team_bans", [])
    enemy_bans = mstate.get("enemy_bans", [])
    my_picks_list = mstate.get("my_team_picks", [])
    enemy_picks_list = mstate.get("enemy_picks", [])
    my_position = mstate.get("my_position", "")

    all_banned = set(my_bans + enemy_bans)
    all_picked = set([p["champion_id"] for p in my_picks_list + enemy_picks_list])
    used = all_banned | all_picked

    my_pick_ids = [p["champion_id"] for p in my_picks_list]
    enemy_pick_ids = [p["champion_id"] for p in enemy_picks_list]
    enemy_picks_with_pos = [{"champion_id": p["champion_id"], "position": p.get("position", "")}
                            for p in enemy_picks_list]

    recs, counters = build_recommendations(
        used, my_pick_ids, enemy_picks_with_pos, my_position, teammate_pool
    )
    mstate["recommendations"] = recs
    mstate["counter_heroes"] = [{
        "champion_id": c["champion_id"],
        "name": c["name"],
        "image_url": c["image_url"],
        "role": c["role"],
        "counters": c["counters"],
    } for c in counters]

    # Ban 推荐 — 基于预选 + 熟练度
    my_prepicks_list = mstate.get("my_prepicks", [])
    enemy_prepicks_list = mstate.get("enemy_prepicks", [])
    ban_recs = build_ban_recommendations(
        used, my_prepicks_list, enemy_prepicks_list, my_position, teammate_pool
    )
    mstate["ban_recommendations"] = ban_recs

    # 阵容识别
    mstate["my_composition"] = analyze_composition(my_pick_ids)
    mstate["enemy_composition"] = analyze_composition(enemy_pick_ids)


# ── Ban 推荐 ──────────────────────────────────────────────────────────────────

def build_ban_recommendations(used_ids, my_prepicks, enemy_prepicks, my_position,
                               teammate_pool=None, top_n=6):
    """
    Ban 推荐评分引擎 — 基于队友和敌方预选英雄 (championPickIntent)。
    5 维度：meta威胁 → 敌方体系补全 → 克制我方 → 角色填补 → 队友擅长惩罚
    """
    if teammate_pool is None:
        teammate_pool = {}
    scored = []

    for ckey in cd.all_champions():
        if ckey in used_ids:
            continue

        score = 0.0
        reasons = []
        meta = cd.get_meta(ckey)

        # 1. Meta 威胁 (0-25)
        tier = meta.get("tier", "B")
        if tier == "S":
            score += 25
            reasons.append("版本S级威胁")
        elif tier == "A":
            score += 15
            reasons.append("版本强势")

        wr = meta.get("wr", 50)
        if wr > 52:
            score += round((wr - 52) * 1.5, 1)
        br = meta.get("br", 2)
        if br > 8:
            score += 8

        # 2. 敌方预选体系补全 — 禁与敌方预选强协同的英雄 (+22/条)
        champ_arches = set(cd.get_archetypes(ckey))
        for ek in enemy_prepicks:
            ek_arches = set(cd.get_archetypes(ek))
            best_syn = 0
            for a1 in champ_arches:
                for a2 in ek_arches:
                    pair = "+".join(sorted([a1, a2]))
                    s = cd.synergy_rules.get(pair, 0)
                    best_syn = max(best_syn, s)
            if best_syn > 0.4:
                score += 22
                reasons.append(f"与敌方预选{cd.get_name(ek)}强协同")

        # 3. 克制我方预选 — 禁克制我方预选的英雄 (+20/条)
        for mk in my_prepicks:
            countered_s, countered_ns = cd.get_countered_score(mk, [ckey])
            if countered_s >= 12:
                score += 20
                reasons.append(f"克制我方预选{cd.get_name(mk)}")

        # 4. 角色填补 — 敌方预选缺少的角色 (+12)
        enemy_roles = {cd.get_role(p) for p in enemy_prepicks}
        c_role = cd.get_role(ckey)
        if c_role not in enemy_roles:
            score += 12

        # 5. 队友擅长惩罚 — 队友/自己熟练的英雄降低 ban 优先级 (-15)
        if ckey in teammate_pool:
            score -= 15
            reasons.append("队友擅长(慎ban)")

        if not reasons:
            reasons.append("综合威胁")

        scored.append({
            "champion_id": ckey,
            "name": cd.get_name(ckey),
            "image_url": cd.get_image(ckey),
            "role": c_role,
            "tier": tier,
            "winrate": meta.get("wr", 50.0),
            "score": round(score, 1),
            "reasons": reasons,
        })

    scored.sort(key=lambda x: -x["score"])
    return scored[:top_n]


# ── 阵容类型识别 ──────────────────────────────────────────────────────────────

COMPOSITION_PATTERNS = {
    "dive": {
        "name": "冲阵强开",
        "icon": "🏃",
        "tags": {"engage": 3, "dive": 3, "burst": 2, "teamfight-aoe": 2,
                 "mobility": 1, "assassin": 1, "tank": 1},
        "anti": {"poke": -2, "disengage": -2},
    },
    "poke": {
        "name": "拉扯消耗",
        "icon": "🏹",
        "tags": {"poke": 3, "siege": 3, "disengage": 2, "zone-control": 1,
                 "utility-adc": 1},
        "anti": {"engage": -2, "dive": -2},
    },
    "protect": {
        "name": "保排输出",
        "icon": "🛡️",
        "tags": {"peel": 3, "hypercarry-enabler": 3, "utility": 2,
                 "hypercarry": 2, "tank": 1, "dps": 1},
        "anti": {"split-push": -1},
    },
    "split": {
        "name": "分带牵制",
        "icon": "⚔️",
        "tags": {"split-push": 3, "duel": 2, "mobility": 2, "sustain": 1,
                 "bruiser": 1},
        "anti": {"teamfight-aoe": -2, "engage": -2},
    },
    "pick": {
        "name": "抓单击杀",
        "icon": "🔪",
        "tags": {"pick": 3, "burst": 2, "assassin": 2, "mobility": 1,
                 "control-mage": 1},
        "anti": {"peel": -2, "tank": -1},
    },
    "wombo": {
        "name": "团战连控",
        "icon": "💥",
        "tags": {"teamfight-aoe": 3, "engage": 3, "zone-control": 2,
                 "burst": 1, "tank": 1},
        "anti": {"split-push": -2, "disengage": -2},
    },
}


def analyze_composition(pick_ids):
    """
    分析阵容类型。
    输入: champion key 列表
    返回: {type, name, icon, archetypes, score}
    如果 pick 少于 2 个，返回 type='unformed'
    """
    if len(pick_ids) < 2:
        return {"type": "unformed", "name": "阵容未成形", "icon": "",
                "archetypes": [], "score": 0}

    # 汇总所有原型标签
    tag_counts = {}
    all_arches = []
    for pk in pick_ids:
        arches = cd.get_archetypes(pk)
        all_arches.extend(arches)
        for a in arches:
            tag_counts[a] = tag_counts.get(a, 0) + 1

    # 对每种阵容类型打分
    results = []
    for comp_type, pattern in COMPOSITION_PATTERNS.items():
        score = 0
        for tag, weight in pattern["tags"].items():
            count = tag_counts.get(tag, 0)
            score += count * weight
        for anti_tag, penalty in pattern["anti"].items():
            count = tag_counts.get(anti_tag, 0)
            score += count * penalty
        results.append((comp_type, score))

    results.sort(key=lambda x: -x[1])
    best_type, best_score = results[0]

    # 阈值: 如果最高分 < 5，判定为均衡
    if best_score < 5:
        return {
            "type": "balanced", "name": "均衡阵容", "icon": "⚖️",
            "archetypes": sorted(set(all_arches)), "score": best_score,
        }

    pattern = COMPOSITION_PATTERNS[best_type]
    return {
        "type": best_type,
        "name": pattern["name"],
        "icon": pattern["icon"],
        "archetypes": sorted(set(all_arches)),
        "score": best_score,
    }


def manual_build(manual_state):
    """Build recommendations from manual state.

    manual_state picks are list[dict]: {champion_id, position}
    """
    my_picks_raw = manual_state.get("my_picks", [])
    enemy_picks_raw = manual_state.get("enemy_picks", [])
    # Normalize to dict form
    my_picks = [_pick_id(p) for p in my_picks_raw]
    enemy_picks_with_pos = [
        {"champion_id": _pick_id(p), "position": p.get("position", "") if isinstance(p, dict) else ""}
        for p in enemy_picks_raw
    ]
    all_banned = set(manual_state.get("my_bans", []) + manual_state.get("enemy_bans", []))
    all_picked = set(my_picks + [_pick_id(p) for p in enemy_picks_raw])
    used = all_banned | all_picked
    recs, counters = build_recommendations(
        used, my_picks, enemy_picks_with_pos,
        manual_state.get("my_position", "")
    )
    return recs, counters

