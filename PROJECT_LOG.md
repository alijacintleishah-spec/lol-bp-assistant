# LoL BP Assistant — 项目日志

> 最后更新: 2026-05-05
> 当前版本: v1.1

---

## 项目概述

League of Legends 排位赛 BP 辅助工具。自动连接游戏客户端读取实时选英雄数据（或使用手动模式），综合 **版本强度、位置匹配、阵容协同、对位克制、分路加权** 等维度，给出实时 Pick/Ban 推荐和阵容类型分析。

**核心原则**：只读数据，不自动操作游戏（不违反 Riot 服务条款）。

---

## 项目目录

```
D:\lolbp\
├── lol-bp-assistant/          ← 主项目
│   ├── app.py                   Flask 路由 + API + 启动入口
│   ├── engine.py                Pick/Ban 推荐引擎 + 阵容识别
│   ├── champion_data.py         英雄数据 + 原型系统 (172 英雄 / 30 原型)
│   ├── lcu.py                   LCU 连接 (WebSocket + REST 双通道)
│   ├── meta_fetcher.py          OP.GG 实时胜率/tier 获取
│   ├── native_ui.py             原生 tkinter 桌面 UI (Canvas 渲染)
│   ├── lcu_diag.py              LCU 诊断工具
│   ├── desktop_app.py           桌面版启动入口 (tkinter 窗口)
│   ├── build_exe.py             PyInstaller 打包脚本
│   ├── launch.pyw               无终端启动器
│   ├── BP.ico                   应用图标
│   ├── BP.png                   图标源文件
│   ├── PROJECT_LOG.md           ← 本文件
│   ├── README.md                使用说明
│   ├── CHANGELOG.md             版本变更日志
│   ├── data/                    数据文件
│   │   ├── champion_data.json       Data Dragon 缓存
│   │   ├── champion_archetypes.json 172 英雄原型标签 + 协同规则
│   │   ├── champion_meta_live.json  OP.GG 实时胜率缓存
│   │   └── img_cache/              头像图片缓存 (PNG)
│   ├── dist/                    打包产物
│   │   └── LoL_BP_Assistant.exe    自包含可执行文件
│   ├── templates/               前端
│   │   └── index.html               Web UI 界面
│   └── logs/                    运行日志
│       └── lol-bp.log
│
├── ai-draft-assistant/         ← 已归档（hackathon 原型）
├── build-your-own-x-master/    ← 学习方法论参考
└── .claude/                    ← Claude Code 内部文件
```

---

## 技术架构

```
浏览器 http://localhost:5000  (可选, Web UI)
        │
        ▼
┌─ app.py ─── Flask 路由 + 状态管理 + 启动 ────────────┐
│  /api/state       BP 实时状态                          │
│  /api/champions   完整英雄数据                         │
│  /api/meta        版本胜率/tier                        │
│  /api/search      英雄搜索                             │
│  /api/manual/*    手动模式操作                         │
│  /api/diagnose    诊断 LCU 连接                        │
│  /api/available   英雄可用状态                         │
└──────────────────────────────────────────────────────┘
         │           │            │
         ▼           ▼            ▼
┌────────────┐ ┌──────────┐ ┌──────────────┐
│ engine.py  │ │  lcu.py  │ │ meta_fetcher │
│ Pick推荐   │ │ WebSocket│ │ OP.GG 数据   │
│ Ban 推荐   │ │ + REST   │ │ 获取/缓存    │
│ 阵容识别   │ │ 双通道    │ │              │
└────────────┘ └──────────┘ └──────────────┘
         │            │
         ▼            ▼
┌─────────────────────────────────────────┐
│  champion_data.py                       │
│  172 英雄 · 30 原型 · 协同/克制矩阵     │
└─────────────────────────────────────────┘
         │
         ▼
┌─────────────────────────────────────────┐
│  native_ui.py  (桌面 UI)                │
│  Canvas 卡片渲染 · 异步头像 · 手动模式  │
└─────────────────────────────────────────┘
         │
         ▼
┌─ desktop_app.py ─────────────────────────┐
│  Flask 线程 + tkinter 窗口 (默认入口)     │
└─────────────────────────────────────────┘
```

### LCU 检测流程

```
进程扫描 (所有 LCU 进程 + lockfile + wmic)
        │
        ▼
  收集候选 (port, token)
        │
        ▼
  逐个测试 /lol-summoner/v1/current-summoner
        │
   ┌────┴────┐
   ▼         ▼
 200 OK    其他
 游戏客户端  启动器
   │         │
   ▼         ▼
 WebSocket  轮询等待
 + REST      游戏客户端
 双通道      启动
```

---

## 文件清单

| 文件 | 职责 |
|------|------|
| `app.py` | Flask 路由、状态管理、启动入口、9 个 API 端点 |
| `engine.py` | Pick 推荐 (7维) + Ban 推荐 (4维，基于预选) + 阵容识别 (7种) |
| `champion_data.py` | 172 英雄数据、30 原型标签、协同/克制矩阵、分路加权 |
| `lcu.py` | LCU 进程检测、WebSocket 监听 + REST 轮询双通道、session 解析 |
| `meta_fetcher.py` | OP.GG MCP API 实时胜率/tier 获取与缓存 |
| `native_ui.py` | 原生 tkinter 桌面 UI — Canvas 卡片渲染、异步头像加载、手动模式 |
| `desktop_app.py` | 桌面版启动入口，启动 Flask + 打开 tkinter 窗口 |
| `lcu_diag.py` | LCU 全面诊断工具 |
| `build_exe.py` | PyInstaller 打包脚本，输出自包含 exe |
| `templates/index.html` | Web 前端 UI（暗色 LoL 主题）|
| `data/champion_archetypes.json` | 172 英雄 → 30 种原型标签 + 协同/冲突规则 |
| `data/img_cache/` | 英雄头像 PNG 缓存目录 |

---

## 推荐引擎详解

### Pick 推荐（7 维度）

| # | 维度 | 权重 | 说明 |
|---|------|------|------|
| 1 | 版本强度 | S=+30, A=+18, B=+6 | 基于 OP.GG 实时 tier |
| 2 | 胜率加成 | (wr-50)×3.5 | 高于 50% 按比例加分 |
| 3 | 位置匹配 | +15 | 与你的分配位置一致 |
| 4 | 阵容协同 | syn×0.7 | 原型 + 精确 + 角色三重协同 |
| 5 | 对位克制 | 分路权重×基础分 | 对位×1.5, 打野×0.7-0.9, 远端×0.3 |
| 6 | 被克制惩罚 | -8~-10/项 | 被敌方阵容 counter 风险 |
| 7 | Ban率/阵容平衡 | +4~8 | 高 ban 率加分, 补位加分 |

### Ban 推荐（4 维度 — 基于预选）

| # | 维度 | 分值 |
|---|------|------|
| 1 | 版本 Meta 威胁 | S=+25, A=+15 |
| 2 | 敌方预选体系补全 | +22/条（拆对方协同）|
| 3 | 克制我方预选 | +20/条（禁我方 counter）|
| 4 | 角色填补 | +12（对方空缺位置的强势英雄）|

### 阵容类型识别（7 种）

冲阵强开 / 拉扯消耗 / 保排输出 / 分带牵制 / 抓单击杀 / 团战连控 / 均衡阵容

---

## 数据系统

- **英雄名称/头像/角色**: Riot Data Dragon API（官方，24h 缓存）
- **版本胜率/tier**: OP.GG MCP API（24h 缓存）
- **协同/克制**: 原型驱动 + 38 热门英雄精确关系 + 标签矩阵（19 条）
- **172 英雄 → 30 种原型标签**（assassin, burst, dive, engage, poke, split-push 等）

---

## 启动方式

```bash
cd D:\lolbp\lol-bp-assistant

# 桌面窗口（推荐，零浏览器依赖）
python desktop_app.py

# Web 界面（浏览器访问 http://localhost:5000）
python app.py

# 诊断工具
python lcu_diag.py     # 全面检查 LCU 连接状态
```

分享给他人只需发送 `dist/LoL_BP_Assistant.exe`（24MB，自包含，双击运行）。

---

## 开发日志

### 2026-05-05 (v2.2 — bp2.2)

**前端完全重设计 — LoL 客户端风格**

完全推翻 `templates/index.html`，改为模仿 LoL 客户端 BP 界面的三栏布局：

**布局**
- **1:2:1 比例**：左 25% 蓝方队伍面板 + 中 50% 英雄推荐列表 + 右 25% 红方队伍面板
- 上方 ban 行：5 个方形 ban 位 × 双方，中间 BANS 分隔
- 两侧队伍面板：5 行竖排，每行含六边形头像(66px)、淡黄色分路标签、白色英雄名
- 中部推荐列表：排名 → 六边形头像(50px) → 英雄名+分路 → 菱形Tier水晶 → 位置标签 → WR → 原因标签 → 评分条 → 分数

**视觉**
- Hextech 暗黑主题：`#010A14` 深空背景 + `#C89B3C` 符文金 + `#0AC8FF` 魔法蓝辉
- 英雄头像统一六边形 `clip-path: polygon()` 裁剪
- Tier 标识改为菱形水晶（旋转 45°），S/A/B 渐变配色
- 原因标签色彩编码：绿=克制、红=被克制、蓝=协同、金=版本、紫=Ban
- 金色角标镶边（面板四角 L 形线条）
- 符文分隔线（`◇—— 标题 ——◇`）
- Cinzel 衬线字体（标题，近似 LoL Beaufort）+ Inter 无衬线（正文）

**背景**
- 新增加载背景图 `static/2379016.webp`，35% 透明度 + 半透明暗色蒙层保证文字辨识度

**文字尺寸（放大 1.5~2×）**
- 两侧分路标签: 14px 淡黄 `#F0E6A0` / 英雄名: 19px 纯白 `#FFFFFF`
- 中间英雄名: 17px 纯白 / 分路副标题: 13px 淡黄
- 中间分数: 24px 金色 / WR: 18px / 原因标签: 12px
- Tier 水晶: 28px / 列表头像: 50px

**桌面入口**
- `desktop_app.py` 改为 pywebview 内嵌窗口（保留浏览器 fallback）
- 新增 `requirements.txt` 依赖清单
- `build_exe.py` 更新适配 pywebview + static 文件夹

**功能保留**
- 推荐 / 禁用 / 全部英雄 三 Tab 切换
- 上单/打野/中单/下路/辅助 五位置筛选
- 手动模式：搜索 → 选中 → 我方Ban/Pick、敌方Ban/Pick + 位置选择 + 重置
- 克制专区：自动展示克制敌方阵容的英雄（绿色高亮）
- 预选展示、阵容类型识别、BP 计时器、Meta 数据更新
- LCU 自动检测 + WebSocket 实时推荐（后端 API 零改动）

### 2026-05-04 (v1.0 — bp1.0)

**核心修复：LCU 自动检测**

WeGame 国服客户端的 LCU API 与国际版完全不同——标准 `lol-*` 端点全部 404。经过全面诊断后彻底重写了检测方案：

- **WebSocket 主通道**：连接 `wss://127.0.0.1:{port}/`，订阅 `OnJsonApiEvent` 实时监听 champ-select session 创建/更新/删除事件。这是 Blitz.gg、Porofessor 等专业工具的标准做法。
- **REST 兜底**：每 1.5s 轮询 `/lol-champ-select/v1/session`，用 `_has_players()` 校验 session 数据有效性（过滤大厅空 session）。
- **gameflow phase 监控**：轮询 `/lol-gameflow/v1/gameflow-phase` 获取当前阶段，状态变化时记录日志。
- **智能进程检测**：改进 `find_lcu_process()`，收集所有候选端口后用 `/lol-summoner/v1/current-summoner` 测试，优先返回游戏客户端端口（而非启动器端口）。解决了 WeGame 启动器和游戏客户端同端口被误判的问题。

**Ban 推荐改为基于预选**
- `parse_session()` 提取双方 `championPickIntent`（预选/悬停英雄）作为 `my_prepicks` / `enemy_prepicks`
- `build_ban_recommendations()` 改为基于预选评分（而非已选英雄），贴合实际排位流程
- 前端侧边栏新增"预选"行，金色标签展示

**项目精简**
- 删除所有非核心文件（tkinter 面板、桌面版、打包、配置系统、自动更新、队友熟练度等）
- 移除 `champion_data.py` 和 `meta_fetcher.py` 对 `config`/`logging_config` 的依赖
- 内联所有硬编码配置值

**前端修复**
- 克制专区去重：只显示未在推荐列表中的克制英雄
- 预选展示：侧边栏双方各新增"预选"行

**工具**
- 新增 `lcu_diag.py`：LCU 全面诊断脚本

### 2026-05-05 (v1.1 — bp1.1)

**原生桌面 UI 替代浏览器方案**

彻底移除对 Chrome/Edge 浏览器的依赖，改为 Python 内置 tkinter 实现的独立桌面窗口：
- 新增 `native_ui.py`：基于 Canvas 的高性能卡片列表渲染（零子 widget 嵌套，`create_rectangle`/`create_text` 直接绘制）
- 重写 `desktop_app.py`：不再通过 subprocess 启动浏览器，改为调用 `native_ui.launch_native_ui()`
- `build_exe.py` 新增 `--icon=BP.ico`，exe 文件带自定义图标
- 新增 `BP.ico`：从 BP.png 转换的多尺寸图标（16~256px）

**异步头像加载**
- `AvatarLoader` 类：后台线程下载 Data Dragon 头像 → PIL 圆形裁切 → 存盘缓存 → 主线程 `create_image` 替换 Canvas 占位圆
- 首次打开秒显角色色圆+首字母占位，头像逐张弹入
- 缓存目录 `data/img_cache/`，二次启动全部瞬间加载

**UI 配色重设**
- 全界面配色改为指定色系：`#845ec2` `#2c73d2` `#0081cf` `#0089ba` `#008e9b` `#008f7a`
- 自定义 ttk Scrollbar 样式（窄条深槽）
- 背景暗色 `#080c14`，卡片 `#101722`

**性能优化（三轮迭代）**
1. 状态指纹跳过：MD5 对比当前和上次渲染的 bans/picks/recs，不变则完全不重绘
2. 计时器独立 1s 刷新（仅改一个 Label），数据轮询降至 2s
3. 仅重建当前可见 tab（`NotebookTabChanged` 事件跟踪）
4. Canvas 替代 Frame 嵌套：widget 数从 ~600 降至 ~50，无 layout 重算开销

**终端窗口闪烁修复**
- `lcu.py`: `subprocess.run(wmic)` 添加 `creationflags=CREATE_NO_WINDOW`
- `desktop_app.py`: `subprocess.Popen` 启动浏览器添加 `CREATE_NO_WINDOW`
- `launch.pyw`: 同上

### 2026-05-05 (v1.1 修复版)

**修复数据刷新混乱**

- `_state_hash()` 移除 `r`（推荐ID列表）和 `br`（ban推荐ID列表）——推荐数据是引擎每次重算的派生结果，不应参与状态变化检测
- 新增 `_sidebar_hash()`：侧边栏只在 picks/bans/prepicks/position 实际变化时才重建，不再每 2 秒拆了重建
- 所有重置点（`_set_filter`、`_toggle_mode`、`_manual_action`、`_manual_reset`、`_on_tab_changed`）同步重置 `_last_sidebar_hash`

### 历史版本

- v1.0 (2026-05-04): LCU 自动检测重写、Ban 推荐基于预选、项目精简

---

## 待开发

- [ ] 比赛模式 BP（Ban1→Pick1→Ban2→Pick2 双阶段）
- [ ] 英雄技能 counter 关系（硬控克突进等）
- [ ] 对局历史记录保存
- [ ] 敌方分路推测
