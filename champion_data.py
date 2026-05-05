"""
英雄数据管理模块
- 从 Data Dragon API 获取英雄名称、头像、角色
- 内置最新版本 tier/胜率数据
- 基于角色标签的协同/克制关系
"""

import json
import os
import sys
import time
import requests

import logging

logger = logging.getLogger(__name__)

if getattr(sys, 'frozen', False):
    DATA_DIR = os.path.join(sys._MEIPASS, "data")
else:
    DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")
CHAMPION_CACHE = os.path.join(DATA_DIR, "champion_data.json")
META_CACHE = os.path.join(DATA_DIR, "champion_meta.json")

# ── 版本胜率 & tier 数据 (16.9 版本) ──────────────────────────────────────────
# 基于 lolalytics / u.gg 全球数据，按 Riot champion key 索引
# tier: S/A/B/C, wr: 胜率%, pr: 出场率%, br: ban率%
META_DATA = {
    266: {"tier":"B","wr":49.2,"pr":5.1,"br":3.2},   # 亚托克斯
    103: {"tier":"A","wr":51.8,"pr":7.3,"br":4.1},   # 阿狸
    84:  {"tier":"A","wr":50.9,"pr":8.5,"br":6.8},   # 阿卡丽
    166: {"tier":"A","wr":51.2,"pr":4.8,"br":3.5},   # 阿克尚
    12:  {"tier":"B","wr":50.1,"pr":3.2,"br":1.5},   # 阿利斯塔
    32:  {"tier":"A","wr":52.0,"pr":4.5,"br":2.1},   # 阿木木
    34:  {"tier":"A","wr":51.2,"pr":6.8,"br":3.2},   # 艾尼维亚
    1:   {"tier":"A","wr":51.5,"pr":5.2,"br":2.8},   # 安妮
    22:  {"tier":"A","wr":51.3,"pr":8.2,"br":2.5},   # 艾希
    268: {"tier":"B","wr":49.5,"pr":3.1,"br":1.8},   # 阿兹尔
    432: {"tier":"A","wr":51.0,"pr":4.2,"br":2.2},   # 巴德
    53:  {"tier":"S","wr":52.1,"pr":9.5,"br":5.8},   # 布里茨
    63:  {"tier":"A","wr":51.2,"pr":7.1,"br":4.5},   # 布兰德
    201: {"tier":"B","wr":50.0,"pr":3.5,"br":2.1},   # 布隆
    51:  {"tier":"A","wr":51.4,"pr":9.1,"br":3.8},   # 凯特琳
    69:  {"tier":"A","wr":52.0,"pr":5.5,"br":3.1},   # 卡西奥佩娅
    31:  {"tier":"B","wr":49.8,"pr":3.2,"br":1.5},   # 科加斯
    42:  {"tier":"B","wr":49.2,"pr":4.5,"br":1.8},   # 库奇
    122: {"tier":"S","wr":52.8,"pr":7.2,"br":6.5},   # 德莱厄斯
    131: {"tier":"A","wr":50.8,"pr":6.8,"br":4.2},   # 黛安娜
    119: {"tier":"A","wr":50.5,"pr":5.8,"br":3.5},   # 德莱文
    36:  {"tier":"B","wr":50.2,"pr":3.8,"br":2.1},   # 蒙多
    245: {"tier":"A","wr":51.2,"pr":5.5,"br":3.8},   # 艾克
    60:  {"tier":"B","wr":49.5,"pr":4.2,"br":2.5},   # 伊莉丝
    81:  {"tier":"A","wr":51.0,"pr":9.2,"br":3.5},   # 伊泽瑞尔
    9:   {"tier":"B","wr":49.8,"pr":3.5,"br":2.8},   # 费德提克
    114: {"tier":"A","wr":50.8,"pr":6.5,"br":4.5},   # 菲奥娜
    105: {"tier":"A","wr":50.5,"pr":6.2,"br":4.8},   # 菲兹
    3:   {"tier":"B","wr":49.5,"pr":3.2,"br":1.5},   # 加里奥
    41:  {"tier":"S","wr":52.5,"pr":8.5,"br":5.5},   # 普朗克
    86:  {"tier":"A","wr":51.8,"pr":7.8,"br":3.5},   # 盖伦
    150: {"tier":"B","wr":49.0,"pr":4.5,"br":2.1},   # 纳尔
    79:  {"tier":"B","wr":50.1,"pr":5.2,"br":3.1},   # 古拉加斯
    104: {"tier":"A","wr":51.5,"pr":6.8,"br":5.2},   # 格雷福斯
    120: {"tier":"S","wr":52.5,"pr":7.2,"br":6.1},   # 赫卡里姆
    420: {"tier":"B","wr":49.8,"pr":3.5,"br":2.2},   # 艾翁
    39:  {"tier":"A","wr":51.0,"pr":5.5,"br":3.5},   # 艾瑞莉娅
    40:  {"tier":"A","wr":52.2,"pr":5.8,"br":2.5},   # 迦娜
    59:  {"tier":"A","wr":51.5,"pr":7.5,"br":4.5},   # 嘉文四世
    24:  {"tier":"S","wr":52.5,"pr":8.2,"br":6.8},   # 贾克斯
    126: {"tier":"A","wr":51.0,"pr":6.5,"br":3.8},   # 杰斯
    202: {"tier":"A","wr":51.8,"pr":7.8,"br":4.2},   # 烬
    115: {"tier":"S","wr":52.3,"pr":9.8,"br":5.5},   # 金克丝
    222: {"tier":"S","wr":52.3,"pr":9.8,"br":5.5},   # 金克丝（重复key保留兼容）
    10:  {"tier":"B","wr":50.2,"pr":4.2,"br":2.8},   # 迦娜(索尔)
    55:  {"tier":"B","wr":50.5,"pr":5.5,"br":4.2},   # 卡特琳娜
    89:  {"tier":"S","wr":52.0,"pr":8.5,"br":4.5},   # 蕾欧娜
    64:  {"tier":"A","wr":50.2,"pr":9.5,"br":7.2},   # 李青
    127: {"tier":"B","wr":49.5,"pr":4.8,"br":3.5},   # 丽桑卓
    99:  {"tier":"A","wr":51.2,"pr":8.5,"br":3.8},   # 拉克丝
    54:  {"tier":"A","wr":51.8,"pr":6.5,"br":3.2},   # 墨菲特
    90:  {"tier":"A","wr":52.0,"pr":5.8,"br":3.5},   # 玛尔扎哈
    57:  {"tier":"B","wr":50.0,"pr":4.5,"br":2.5},   # 茂凯
    11:  {"tier":"A","wr":50.5,"pr":6.8,"br":4.2},   # 易
    21:  {"tier":"B","wr":50.8,"pr":7.2,"br":3.5},   # 厄运小姐
    82:  {"tier":"A","wr":51.5,"pr":7.8,"br":4.5},   # 莫德凯撒
    25:  {"tier":"A","wr":50.8,"pr":6.2,"br":5.2},   # 莫甘娜
    267: {"tier":"B","wr":50.2,"pr":5.5,"br":3.1},   # 娜美
    75:  {"tier":"B","wr":49.8,"pr":4.2,"br":2.8},   # 内瑟斯
    111: {"tier":"S","wr":51.8,"pr":8.2,"br":5.5},   # 诺提勒斯
    76:  {"tier":"B","wr":49.5,"pr":4.5,"br":2.5},   # 奈德丽
    56:  {"tier":"B","wr":49.2,"pr":4.8,"br":3.2},   # 魔腾
    20:  {"tier":"A","wr":50.8,"pr":5.2,"br":2.8},   # 努努
    2:   {"tier":"B","wr":49.5,"pr":3.5,"br":1.8},   # 奥拉夫
    61:  {"tier":"A","wr":51.2,"pr":6.5,"br":3.2},   # 奥莉安娜
    80:  {"tier":"B","wr":50.1,"pr":5.5,"br":3.8},   # 潘森
    78:  {"tier":"B","wr":49.8,"pr":4.2,"br":2.1},   # 波比
    133: {"tier":"A","wr":50.8,"pr":6.8,"br":4.5},   # 奎因
    33:  {"tier":"B","wr":50.2,"pr":4.5,"br":2.5},   # 兰博
    58:  {"tier":"S","wr":52.5,"pr":7.8,"br":5.5},   # 雷克顿
    107: {"tier":"B","wr":49.8,"pr":5.5,"br":3.2},   # 雷恩加尔
    92:  {"tier":"A","wr":51.0,"pr":6.5,"br":4.2},   # 锐雯
    68:  {"tier":"B","wr":49.5,"pr":3.5,"br":2.1},   # 兰博(鲁尔)
    13:  {"tier":"B","wr":50.0,"pr":3.2,"br":1.5},   # 瑞兹
    113: {"tier":"A","wr":51.5,"pr":5.8,"br":3.5},   # 瑟庄妮
    35:  {"tier":"B","wr":50.2,"pr":4.8,"br":2.8},   # 萨科
    98:  {"tier":"A","wr":51.2,"pr":6.5,"br":3.8},   # 慎
    102: {"tier":"B","wr":49.8,"pr":3.5,"br":2.1},   # 希瓦娜
    27:  {"tier":"B","wr":50.0,"pr":4.2,"br":2.5},   # 辛吉德
    14:  {"tier":"B","wr":49.5,"pr":3.2,"br":1.8},   # 赛恩
    72:  {"tier":"B","wr":49.2,"pr":3.5,"br":2.1},   # 希维尔
    37:  {"tier":"A","wr":52.5,"pr":6.8,"br":3.5},   # 索拉卡
    16:  {"tier":"B","wr":50.2,"pr":4.5,"br":2.5},   # 索娜(娑娜)
    50:  {"tier":"A","wr":51.8,"pr":7.5,"br":5.2},   # 斯维因
    91:  {"tier":"A","wr":51.5,"pr":5.8,"br":3.5},   # 泰隆
    44:  {"tier":"B","wr":50.0,"pr":3.8,"br":1.5},   # 塔里克
    17:  {"tier":"B","wr":49.8,"pr":4.2,"br":2.8},   # 提莫
    412: {"tier":"S","wr":51.2,"pr":9.2,"br":5.5},   # 锤石
    23:  {"tier":"A","wr":51.5,"pr":5.8,"br":2.5},   # 崔丝塔娜
    48:  {"tier":"B","wr":49.5,"pr":3.8,"br":2.1},   # 特朗德尔
    77:  {"tier":"B","wr":49.8,"pr":4.5,"br":2.5},   # 乌迪尔
    6:   {"tier":"B","wr":50.0,"pr":3.2,"br":1.8},   # 厄加特
    67:  {"tier":"A","wr":50.8,"pr":7.5,"br":3.5},   # 薇恩
    45:  {"tier":"B","wr":49.5,"pr":3.5,"br":2.1},   # 维迦
    161: {"tier":"A","wr":51.5,"pr":5.8,"br":3.5},   # 维克兹
    112: {"tier":"A","wr":51.0,"pr":6.2,"br":4.5},   # 薇古丝
    8:   {"tier":"B","wr":50.5,"pr":5.5,"br":3.2},   # 弗拉基米尔
    106: {"tier":"A","wr":51.8,"pr":6.8,"br":4.5},   # 沃利贝尔
    19:  {"tier":"A","wr":52.0,"pr":6.5,"br":4.2},   # 沃里克
    62:  {"tier":"A","wr":51.2,"pr":7.2,"br":5.8},   # 孙悟空
    101: {"tier":"A","wr":51.5,"pr":6.5,"br":4.5},   # 泽拉斯
    5:   {"tier":"A","wr":51.8,"pr":6.2,"br":3.5},   # 赵信
    157: {"tier":"S","wr":52.5,"pr":8.5,"br":6.5},   # 亚索
    83:  {"tier":"B","wr":49.8,"pr":4.5,"br":2.8},   # 约里克
    154: {"tier":"B","wr":49.5,"pr":4.2,"br":2.5},   # 扎克
    238: {"tier":"A","wr":50.5,"pr":6.8,"br":5.5},   # 劫
    26:  {"tier":"B","wr":50.0,"pr":3.8,"br":2.1},   # 基兰
    142: {"tier":"A","wr":51.0,"pr":5.5,"br":3.8},   # 佐伊
    236: {"tier":"S","wr":52.2,"pr":9.2,"br":5.8},   # 卢锡安
    117: {"tier":"A","wr":52.0,"pr":6.8,"br":3.2},   # 璐璐
    43:  {"tier":"B","wr":50.2,"pr":4.5,"br":2.5},   # 卡尔玛
    203: {"tier":"B","wr":49.8,"pr":3.5,"br":1.5},   # 千珏
    223: {"tier":"A","wr":51.2,"pr":5.8,"br":3.5},   # 塔姆
    164: {"tier":"A","wr":51.5,"pr":7.2,"br":5.5},   # 卡蜜尔
    141: {"tier":"S","wr":52.8,"pr":8.5,"br":6.8},   # 凯隐
    240: {"tier":"A","wr":51.2,"pr":6.5,"br":4.2},   # 永恩
    145: {"tier":"A","wr":51.8,"pr":8.5,"br":5.5},   # 凯莎
    235: {"tier":"A","wr":51.0,"pr":7.8,"br":4.5},   # 赛娜
    234: {"tier":"A","wr":51.5,"pr":6.5,"br":4.2},   # 佛耶戈
    147: {"tier":"A","wr":50.8,"pr":5.5,"br":3.5},   # 格温
    200: {"tier":"B","wr":49.5,"pr":4.2,"br":2.5},   # 卑尔维斯
    221: {"tier":"B","wr":50.0,"pr":5.5,"br":3.8},   # 泽丽
    233: {"tier":"A","wr":51.2,"pr":6.8,"br":4.5},   # 芮尔
    360: {"tier":"A","wr":51.8,"pr":6.2,"br":3.5},   # 斯莫德
    901: {"tier":"B","wr":50.2,"pr":5.8,"br":3.2},   # 蔚(奥德)
    427: {"tier":"A","wr":51.5,"pr":6.5,"br":4.5},   # 安娜(米利欧)
}

# ── 角色标签映射 ──────────────────────────────────────────────────────────────
# 将 Data Dragon tags 映射到标准5位置
TAG_TO_ROLE = {
    "Fighter": "top",
    "Tank": "top",
    "Mage": "mid",
    "Assassin": "mid",
    "Marksman": "bot",
    "Support": "support",
}

# 多标签英雄的精细化角色映射（Riot champion key → role）
# Data Dragon 的 tags 不够精确，手动指定位置
MANUAL_ROLE = {
    266: "top",     # Aatrox
    103: "mid",     # Ahri
    84: "mid",      # Akali
    166: "mid",     # Akshan
    12: "support",  # Alistar
    32: "jungle",   # Amumu
    34: "mid",      # Anivia
    1: "mid",       # Annie
    22: "bot",      # Ashe
    268: "mid",     # Azir
    432: "support", # Bard
    53: "support",  # Blitzcrank
    63: "support",  # Brand (support为主)
    201: "support", # Braum
    51: "bot",      # Caitlyn
    69: "mid",      # Cassiopeia
    31: "top",      # Cho'Gath
    42: "mid",      # Corki
    122: "top",     # Darius
    131: "jungle",  # Diana
    119: "bot",     # Draven
    36: "top",      # Dr. Mundo
    245: "jungle",  # Ekko
    60: "jungle",   # Elise
    81: "bot",      # Ezreal
    9: "jungle",    # Fiddlesticks
    114: "top",     # Fiora
    105: "mid",     # Fizz
    3: "mid",       # Galio
    41: "top",      # Gangplank
    86: "top",      # Garen
    150: "top",     # Gnar
    79: "top",      # Gragas
    104: "jungle",  # Graves
    120: "jungle",  # Hecarim
    420: "jungle",  # Ivern
    39: "top",      # Irelia
    40: "support",  # Janna
    59: "jungle",   # Jarvan IV
    24: "top",      # Jax
    126: "top",     # Jayce
    202: "bot",     # Jhin
    115: "bot",     # Jinx
    222: "bot",     # Jinx dup
    10: "mid",      # Kayle
    55: "mid",      # Katarina
    89: "support",  # Leona
    64: "jungle",   # Lee Sin
    127: "mid",     # Lissandra
    99: "support",  # Lux
    54: "top",      # Malphite
    90: "mid",      # Malzahar
    57: "top",      # Maokai
    11: "jungle",   # Master Yi
    21: "bot",      # Miss Fortune
    82: "top",      # Mordekaiser
    25: "support",  # Morgana
    267: "support", # Nami
    75: "top",      # Nasus
    111: "support", # Nautilus
    76: "jungle",   # Nidalee
    56: "jungle",   # Nocturne
    20: "jungle",   # Nunu
    2: "top",       # Olaf
    61: "mid",      # Orianna
    80: "top",      # Pantheon
    78: "top",      # Poppy
    133: "top",     # Quinn
    33: "top",      # Rumble
    58: "top",      # Renekton
    107: "jungle",  # Rengar
    92: "top",      # Riven
    68: "mid",      # Ryze
    13: "mid",      # Ryze old
    113: "jungle",  # Sejuani
    35: "jungle",   # Shaco
    98: "top",      # Shen
    102: "jungle",  # Shyvana
    27: "top",      # Singed
    14: "top",      # Sion
    72: "bot",      # Sivir
    37: "support",  # Soraka
    16: "support",  # Sona
    50: "support",  # Swain
    91: "mid",      # Talon
    44: "support",  # Taric
    17: "top",      # Teemo
    412: "support", # Thresh
    23: "bot",      # Tristana
    48: "top",      # Trundle
    77: "jungle",   # Udyr
    6: "top",       # Urgot
    67: "bot",      # Vayne
    45: "mid",      # Veigar
    161: "support", # Vel'Koz
    112: "mid",     # Vex
    8: "mid",       # Vladimir
    106: "top",     # Volibear
    19: "jungle",   # Warwick
    62: "jungle",   # Wukong
    101: "mid",     # Xerath
    5: "jungle",    # Xin Zhao
    157: "mid",     # Yasuo
    83: "top",      # Yorick
    154: "jungle",  # Zac
    238: "mid",     # Zed
    26: "mid",      # Zilean
    142: "mid",     # Zoe
    236: "bot",     # Lucian
    117: "support", # Lulu
    43: "support",  # Karma
    203: "jungle",  # Kindred
    223: "top",     # Tahm Kench
    164: "top",     # Camille
    141: "jungle",  # Kayn
    240: "top",     # Yone
    145: "bot",     # Kai'Sa
    235: "support", # Senna
    234: "jungle",  # Viego
    147: "top",     # Gwen
    200: "jungle",  # Bel'Veth
    221: "bot",     # Zeri
    233: "support", # Rell
    360: "bot",     # Smolder
    427: "support", # Milio
}

# ── 标签克制矩阵（覆盖全部英雄）────────────────────────────────────────────
# 我的标签 → 敌方标签 → 加成值
TAG_COUNTER_MATRIX = {
    ("Assassin", "Marksman"): 25,
    ("Assassin", "Mage"): 20,
    ("Assassin", "Support"): 15,
    ("Tank", "Assassin"): 25,
    ("Tank", "Fighter"): 15,
    ("Tank", "Mage"): 15,
    ("Mage", "Fighter"): 20,
    ("Mage", "Tank"): 15,
    ("Mage", "Assassin"): 10,
    ("Marksman", "Tank"): 22,
    ("Marksman", "Fighter"): 15,
    ("Marksman", "Assassin"): 10,
    ("Fighter", "Tank"): 20,
    ("Fighter", "Assassin"): 18,
    ("Fighter", "Marksman"): 18,
    ("Fighter", "Mage"): 15,
    ("Support", "Assassin"): 22,
    ("Support", "Fighter"): 15,
    ("Support", "Mage"): 10,
}

# 热门英雄的精细协同/克制（覆盖关键对局）
SPECIFIC_RELATIONS = {
    157: {"synergy": [54,32,89,111,53], "counters": [22,51,81,21,202], "countered_by": [24,58,122,92,55]},
    238: {"synergy": [64,59,254], "counters": [22,51,99,67,81], "countered_by": [127,90,54,3,25]},
    64:  {"synergy": [238,157,92,84], "counters": [120,5,76,56], "countered_by": [19,32,35,24]},
    115: {"synergy": [89,111,412,53,117], "counters": [119,67,236,22], "countered_by": [238,11,105,84]},
    51:  {"synergy": [40,99,117,267], "counters": [22,202,236,81], "countered_by": [119,24,120,55]},
    81:  {"synergy": [37,89,40,412], "counters": [119,67,202,51], "countered_by": [22,51,53,157]},
    67:  {"synergy": [412,117,40,89], "counters": [54,33,82,122], "countered_by": [119,51,22,115]},
    412: {"synergy": [115,22,51,67,202,222], "counters": [37,89,53,111], "countered_by": [40,117,37,267]},
    53:  {"synergy": [22,51,115,119,202], "counters": [412,89,99,25], "countered_by": [117,37,40,267]},
    89:  {"synergy": [115,119,202,22,145], "counters": [37,117,53], "countered_by": [117,40,37,412]},
    117: {"synergy": [67,81,115,51], "counters": [89,111,105,240], "countered_by": [53,412,53]},
    24:  {"synergy": [64,59,254,141], "counters": [86,58,157,240], "countered_by": [54,33,82,114]},
    86:  {"synergy": [254,59,64,89], "counters": [24,420,11,157], "countered_by": [67,126,58,114]},
    92:  {"synergy": [254,64,59,238], "counters": [24,86,157,240], "countered_by": [54,33,58,122]},
    114: {"synergy": [64,59,254,122], "counters": [58,86,420,122], "countered_by": [54,33,24,92]},
    58:  {"synergy": [59,254,64,114], "counters": [24,11,92,240], "countered_by": [114,67,86,82]},
    54:  {"synergy": [157,202,67,238], "counters": [114,67,92,119], "countered_by": [24,58,82,114]},
    120: {"synergy": [32,61,89,111], "counters": [64,5,76,56], "countered_by": [19,254,24,59]},
    59:  {"synergy": [238,92,58,157], "counters": [120,121,76,56], "countered_by": [19,254,64,24]},
    22:  {"synergy": [412,89,53,117], "counters": [202,81,67,236], "countered_by": [119,24,120,238]},
    119: {"synergy": [89,111,53,412], "counters": [81,67,22,202], "countered_by": [51,115,202,54]},
    84:  {"synergy": [64,113,59,157], "counters": [22,51,99,67], "countered_by": [3,127,90,54]},
    55:  {"synergy": [59,254,64,157], "counters": [22,51,69,99], "countered_by": [3,25,90,54]},
    131: {"synergy": [157,64,254,240], "counters": [22,51,69,67], "countered_by": [3,25,82,54]},
    141: {"synergy": [89,32,111,54], "counters": [64,120,254,19], "countered_by": [19,24,64,58]},
    240: {"synergy": [157,54,32,89], "counters": [22,51,67,81], "countered_by": [24,58,114,92]},
    145: {"synergy": [89,111,412,53], "counters": [81,67,202,22], "countered_by": [51,115,119,24]},
    236: {"synergy": [89,40,412,111], "counters": [81,22,67,202], "countered_by": [51,115,202,24]},
    5:   {"synergy": [89,32,111,59], "counters": [64,120,254,76], "countered_by": [19,24,64,58]},
    11:  {"synergy": [89,32,40,53], "counters": [22,51,99,67], "countered_by": [24,58,19,54]},
    122: {"synergy": [59,254,64,92], "counters": [86,157,420,240], "countered_by": [67,114,24,82]},
    62:  {"synergy": [157,59,64,238], "counters": [22,51,81,67], "countered_by": [24,58,86,122]},
    234: {"synergy": [89,32,111,54], "counters": [64,120,19,254], "countered_by": [24,58,64,92]},
    164: {"synergy": [64,59,254,141], "counters": [86,157,92,240], "countered_by": [24,58,114,122]},
    147: {"synergy": [59,254,64,157], "counters": [86,157,82,122], "countered_by": [24,58,92,114]},
}

# ── 协同关系（基于角色）────────────────────────────────────────────────────
ROLE_SYNERGY = {
    ("bot", "support"): 22, ("support", "bot"): 22,
    ("top", "jungle"): 18, ("jungle", "top"): 18,
    ("mid", "jungle"): 18, ("jungle", "mid"): 18,
    ("top", "mid"): 12, ("mid", "top"): 12,
    ("jungle", "support"): 10, ("support", "jungle"): 10,
}


class ChampionData:
    """英雄数据管理器"""

    def __init__(self):
        self.champions = {}       # key → {name, tags, image_url, role}
        self.id_to_key = {}       # data dragon id → champion key
        self.key_to_id = {}       # champion key → data dragon id
        self.version = ""
        self._load_or_fetch()
        self._load_archetypes()

    def _load_archetypes(self):
        """加载原型(archetype)数据用于协同和克制计算"""
        import os
        archetype_file = os.path.join(DATA_DIR, "champion_archetypes.json")
        self.champion_archetypes = {}
        self.synergy_rules = {}
        self.anti_synergy_rules = {}
        try:
            if os.path.exists(archetype_file):
                with open(archetype_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                self.champion_archetypes = data.get("archetypes", {})
                self.synergy_rules = data.get("synergy_rules", {})
                self.anti_synergy_rules = data.get("anti_synergy_rules", {})
        except Exception:
            pass

    def get_archetypes(self, champion_key):
        """获取英雄的原型列表，如 ['engage', 'tank', 'pick']"""
        dd_id = self.id_to_key.get(champion_key, "")
        return self.champion_archetypes.get(dd_id, [])


    def _load_or_fetch(self):
        os.makedirs(DATA_DIR, exist_ok=True)

        # 尝试加载缓存
        if os.path.exists(CHAMPION_CACHE):
            with open(CHAMPION_CACHE, "r", encoding="utf-8") as f:
                cache = json.load(f)
            # 检查缓存是否在24小时内
            if time.time() - cache.get("cached_at", 0) < 86400:
                self._parse_dd_data(cache)
                logger.info("从缓存加载 %d 个英雄 (版本 %s)", len(self.champions), self.version)
                return

        # 从 API 获取
        self._fetch_from_api()

    def _fetch_from_api(self):
        try:
            versions = requests.get(DD_VERSION_URL, timeout=10).json()
            self.version = versions[0]
        except Exception:
            self.version = "16.9.1"

        try:
            url = f"https://ddragon.leagueoflegends.com/cdn/{self.version}/data/zh_CN/champion.json"
            data = requests.get(url, timeout=15).json()
            data["cached_at"] = time.time()
            with open(CHAMPION_CACHE, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False)
            self._parse_dd_data(data)
            logger.info("从 API 获取 %d 个英雄 (版本 %s)", len(self.champions), self.version)
        except Exception as e:
            logger.error("Data Dragon 获取失败: %s", e)
            # 尝试用旧缓存
            if os.path.exists(CHAMPION_CACHE):
                with open(CHAMPION_CACHE, "r", encoding="utf-8") as f:
                    self._parse_dd_data(json.load(f))
                logger.warning("回退到缓存 (%d 个英雄)", len(self.champions))

    def _parse_dd_data(self, data):
        self.version = data.get("version", self.version)
        dd_data = data.get("data", {})
        self.champions.clear()
        self.id_to_key.clear()
        self.key_to_id.clear()

        for dd_id, info in dd_data.items():
            key = int(info["key"])
            name = info["name"]
            tags = info["tags"]
            image_url = f"https://ddragon.leagueoflegends.com/cdn/{self.version}/img/champion/{dd_id}.png"

            # 确定角色
            role = MANUAL_ROLE.get(key)
            if not role:
                # 根据 tags 自动推断
                for tag in tags:
                    if tag in TAG_TO_ROLE:
                        role = TAG_TO_ROLE[tag]
                        break
                if not role:
                    role = "unknown"

            self.champions[key] = {
                "name": name,
                "dd_id": dd_id,
                "tags": tags,
                "image_url": image_url,
                "role": role,
            }
            self.id_to_key[key] = dd_id
            self.key_to_id[dd_id] = key

    def get_name(self, champion_key):
        """根据 key 获取英雄中文名"""
        c = self.champions.get(champion_key)
        return c["name"] if c else f"英雄#{champion_key}"

    def get_image(self, champion_key):
        """根据 key 获取英雄头像 URL"""
        c = self.champions.get(champion_key)
        return c["image_url"] if c else ""

    def get_role(self, champion_key):
        """根据 key 获取位置"""
        c = self.champions.get(champion_key)
        return c["role"] if c else "unknown"

    def get_tags(self, champion_key):
        """根据 key 获取标签列表"""
        c = self.champions.get(champion_key)
        return c["tags"] if c else []

    def get_tier(self, champion_key):
        """获取版本 tier（优先实时数据）"""
        from meta_fetcher import get_live_meta
        live = get_live_meta(champion_key)
        return live.get("tier", META_DATA.get(champion_key, {}).get("tier", "B"))

    def get_winrate(self, champion_key):
        """获取胜率（优先实时数据）"""
        from meta_fetcher import get_live_meta
        live = get_live_meta(champion_key)
        return live.get("wr", META_DATA.get(champion_key, {}).get("wr", 50.0))

    def get_pickrate(self, champion_key):
        """获取出场率（优先实时数据）"""
        from meta_fetcher import get_live_meta
        live = get_live_meta(champion_key)
        return live.get("pr", META_DATA.get(champion_key, {}).get("pr", 3.0))

    def get_banrate(self, champion_key):
        """获取 ban 率（优先实时数据）"""
        from meta_fetcher import get_live_meta
        live = get_live_meta(champion_key)
        return live.get("br", META_DATA.get(champion_key, {}).get("br", 2.0))

    def get_meta(self, champion_key):
        """获取完整 meta 数据（优先实时数据）"""
        from meta_fetcher import get_live_meta
        live = get_live_meta(champion_key)
        if live:
            return live
        return META_DATA.get(champion_key, {"tier":"B","wr":50.0,"pr":3.0,"br":2.0})

    def all_champions(self):
        """返回所有英雄 key 列表"""
        return list(self.champions.keys())

    def filter_by_role(self, role):
        """按位置筛选英雄"""
        if role == "all":
            return list(self.champions.keys())
        return [k for k, v in self.champions.items() if v["role"] == role]

    # ── 分路临近度 ─────────────────────────────────────────────────────
    LANE_PROXIMITY = {
        ("top","top"):1.5,("jungle","jungle"):1.5,("mid","mid"):1.5,
        ("bot","bot"):1.5,("support","support"):1.5,
        ("jungle","top"):0.9,("jungle","mid"):0.9,("jungle","bot"):0.8,("jungle","support"):0.7,
        ("top","jungle"):0.8,("mid","jungle"):0.8,("bot","jungle"):0.7,("support","jungle"):0.7,
        ("mid","top"):0.7,("mid","bot"):0.6,("mid","support"):0.5,
        ("top","mid"):0.6,("bot","mid"):0.5,("support","mid"):0.5,
        ("support","top"):0.4,("support","bot"):1.0,("bot","support"):1.0,
        ("top","bot"):0.3,("top","support"):0.3,("bot","top"):0.3,
    }

    def get_lane_weight(self, my_position, enemy_role):
        """计算我对敌方英雄的对位权重"""
        if not my_position or not enemy_role:
            return 1.0
        mp = my_position.lower().replace("utility","support").replace("bottom","bot")
        ep = enemy_role.lower().replace("utility","support").replace("bottom","bot")
        return self.LANE_PROXIMITY.get((mp, ep), 0.5)

    def _calc_archetype_synergy(self, arches1, arches2):
        """计算两套原型之间的协同分（-0.3 ~ 0.9）"""
        if not arches1 or not arches2:
            return 0.1
        best = 0.1
        for a1 in arches1:
            for a2 in arches2:
                pair = "+".join(sorted([a1, a2]))
                if pair in self.synergy_rules:
                    best = max(best, self.synergy_rules[pair])
                elif pair in self.anti_synergy_rules:
                    best = min(best, self.anti_synergy_rules[pair])
        return best

    def get_synergy_score(self, champ_key, teammate_keys):
        """计算与己方阵容的协同分（基于原型+精确数据），返回 (score, [协同英雄名])"""
        score = 0
        syn_names = []
        my_role = self.get_role(champ_key)
        my_arches = self.get_archetypes(champ_key)
        team_roles = set()

        # 精确协同（手动标注的热门组合）
        spec = SPECIFIC_RELATIONS.get(champ_key, {})
        spec_syn = spec.get("synergy", [])
        for t_key in teammate_keys:
            if t_key in spec_syn:
                score += 22
                syn_names.append(self.get_name(t_key))
            # 原型协同
            t_arches = self.get_archetypes(t_key)
            arch_syn = self._calc_archetype_synergy(my_arches, t_arches)
            if arch_syn > 0.3:
                score += int(arch_syn * 25)
                if t_key not in spec_syn:
                    syn_names.append(self.get_name(t_key))
            # 角色协同
            t_role = self.get_role(t_key)
            score += ROLE_SYNERGY.get((my_role, t_role), 4)
            team_roles.add(t_role)

        # 阵容平衡: 重复角色扣分，填补空位加分
        if my_role in team_roles:
            score -= 10  # 重复角色
        else:
            score += 12  # 填补空位

        return score, syn_names

    def get_counter_score(self, champ_key, enemy_keys):
        """计算对敌方阵容的克制分（基于原型+标签+精确数据），返回 (score, [被克制的敌方英雄名])"""
        score = 0
        counter_names = []
        my_tags = set(self.get_tags(champ_key))
        my_arches = set(self.get_archetypes(champ_key))

        spec = SPECIFIC_RELATIONS.get(champ_key, {})
        spec_counters = spec.get("counters", [])
        for e_key in enemy_keys:
            # 精确克制
            if e_key in spec_counters:
                score += 25
                counter_names.append(self.get_name(e_key))
                continue
            # 标签克制
            e_tags = set(self.get_tags(e_key))
            best_tag = 0
            for mt in my_tags:
                for et in e_tags:
                    best_tag = max(best_tag, TAG_COUNTER_MATRIX.get((mt, et), 0))
            # 原型克制（assassin克制marksman等可以在这里扩展）
            e_arches = set(self.get_archetypes(e_key))
            # 简化: "assassin"/"dive" 克制 "marksman"/"hypercarry"/"control-mage"
            counter_arches = {"assassin", "dive", "engage", "pick"}
            vulnerable_arches = {"marksman", "hypercarry", "control-mage", "poke"}
            if my_arches & counter_arches and e_arches & vulnerable_arches:
                best_tag = max(best_tag, 18)
            if best_tag >= 12:
                score += best_tag
                counter_names.append(self.get_name(e_key))

        return score, counter_names

    def get_countered_score(self, champ_key, enemy_keys):
        """计算被敌方克制的惩罚分，返回 (score, [克制我的敌方英雄名])"""
        score = 0
        countered_names = []
        my_tags = set(self.get_tags(champ_key))
        my_arches = set(self.get_archetypes(champ_key))

        spec = SPECIFIC_RELATIONS.get(champ_key, {})
        spec_countered = spec.get("countered_by", [])
        for e_key in enemy_keys:
            if e_key in spec_countered:
                score += 22
                countered_names.append(self.get_name(e_key))
                continue
            e_tags = set(self.get_tags(e_key))
            best = 0
            for et in e_tags:
                for mt in my_tags:
                    best = max(best, TAG_COUNTER_MATRIX.get((et, mt), 0))
            # 原型被克制
            e_arches = set(self.get_archetypes(e_key))
            counter_arches = {"assassin", "dive", "engage", "pick"}
            vulnerable_arches = {"marksman", "hypercarry", "control-mage", "poke"}
            if e_arches & counter_arches and my_arches & vulnerable_arches:
                best = max(best, 18)
            if best >= 12:
                score += best
                countered_names.append(self.get_name(e_key))

        return score, countered_names


# 单例
_champion_data_instance = None

def get_champion_data():
    global _champion_data_instance
    if _champion_data_instance is None:
        _champion_data_instance = ChampionData()
    return _champion_data_instance
