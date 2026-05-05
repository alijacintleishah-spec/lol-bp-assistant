"""
LoL BP Assistant — 原生 tkinter UI
高性能版本：Canvas 绘制卡片，仅重建可见 tab，异步头像。
"""

import os, sys, json, hashlib, threading, time, math, urllib.request, tkinter as tk
from tkinter import ttk
from io import BytesIO
from PIL import Image, ImageTk, ImageDraw

import logging; logger = logging.getLogger(__name__)

from champion_data import get_champion_data
from engine import build_and_store, build_ban_recommendations, analyze_composition, manual_build

cd = get_champion_data()

POS_LABELS = {"top": "上单", "jungle": "打野", "mid": "中单", "bot": "下路", "support": "辅助"}
TIER_COLORS = {"S": "#845ec2", "A": "#2c73d2", "B": "#008e9b", "C": "#666666"}
ROLE_COLORS = {"top": "#0089ba", "jungle": "#008f7a", "mid": "#845ec2",
               "bot": "#2c73d2", "support": "#0081cf"}

# ── 配色 ──
CK = {
    "bg":      "#080c14",
    "bg2":     "#0e131c",
    "bg3":     "#141c28",
    "card":    "#101722",
    "border":  "#1a2736",
    "border2": "#243040",
    "text":    "#d0d8e4",
    "dim":     "#607088",
    "muted":   "#3d4d60",
    "a1": "#845ec2", "a2": "#2c73d2", "a3": "#0081cf",
    "a4": "#0089ba", "a5": "#008e9b", "a6": "#008f7a",
    "red": "#d94a5a", "green": "#2ea86a", "gold": "#d4a853",
}

HEADER_H = 50
CARD_H = 64
CARD_GAP = 2
PICK_IMG = 52
ALL_IMG = 36
PAD_X = 16

# ── 图片系统 ──
IMG_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "img_cache")
os.makedirs(IMG_DIR, exist_ok=True)
_photo_cache: dict[str, ImageTk.PhotoImage] = {}
_fetching: set[str] = set()


def _download(url: str) -> Image.Image | None:
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "LoLBP/1.0"})
        with urllib.request.urlopen(req, timeout=10) as r:
            return Image.open(BytesIO(r.read()))
    except Exception:
        return None


def _process_avatar(pil: Image.Image, size: int) -> Image.Image:
    pil = pil.resize((size, size), Image.LANCZOS).convert("RGBA")
    mask = Image.new("L", (size, size), 0)
    ImageDraw.Draw(mask).ellipse((0, 0, size, size), fill=255)
    pil.putalpha(mask)
    return pil


def get_photo(ckey: int, size: int) -> ImageTk.PhotoImage | None:
    return _photo_cache.get(f"{ckey}_{size}")


def start_async_load(root: tk.Tk, keys: list[int], size: int, on_done_cb):
    """后台下载+处理图片，完成后主线程回调 on_done_cb(ckey, photo)"""
    todo = []
    for ck in keys:
        ck_str = f"{ck}_{size}"
        if ck_str in _photo_cache or ck_str in _fetching:
            continue
        _fetching.add(ck_str)
        cache_path = os.path.join(IMG_DIR, f"{ck}_{size}.png")
        todo.append((ck, cache_path, size))

    if not todo:
        return

    def _worker():
        for ck, cp, sz in todo:
            try:
                if not os.path.exists(cp):
                    url = cd.get_image(ck)
                    if not url:
                        _fetching.discard(f"{ck}_{sz}"); continue
                    raw = _download(url)
                    if raw is None:
                        _fetching.discard(f"{ck}_{sz}"); continue
                    _process_avatar(raw, sz).save(cp, "PNG")
                root.after(0, _on_ready, ck, cp, sz)
            except Exception:
                _fetching.discard(f"{ck}_{sz}")

    def _on_ready(ck, cp, sz):
        try:
            pil = Image.open(cp)
            photo = ImageTk.PhotoImage(pil)
            _photo_cache[f"{ck}_{sz}"] = photo
            on_done_cb(ck, photo, sz)
        except Exception:
            pass
        finally:
            _fetching.discard(f"{ck}_{sz}")

    threading.Thread(target=_worker, daemon=True).start()


# ═══════════════════════════════════════════════════════════════════════════════
#  Canvas 卡片渲染器 — 零子 widget，纯 Canvas 绘制
# ═══════════════════════════════════════════════════════════════════════════════
class CanvasCardList:
    """在 Canvas 上绘制卡片列表，无子 widget 开销。"""

    def __init__(self, canvas: tk.Canvas, bg: str = CK["bg"]):
        self.cv = canvas
        self.bg = bg
        self.items: list[dict] = []        # 每张卡片对应的 canvas item ids
        self._v_scroll = 0.0
        self._total_h = 0
        self._on_click = None
        self.cv.bind("<Button-1>", self._click)
        self.cv.bind("<MouseWheel>", self._wheel)

    def set_on_click(self, cb):
        self._on_click = cb

    def clear(self):
        self.cv.delete("all")
        self.items.clear()
        self._total_h = 0

    def _wheel(self, event):
        self.cv.yview_scroll(int(-1 * (event.delta / 120)), "units")

    def _click(self, event):
        if not self._on_click:
            return
        x, y = self.cv.canvasx(event.x), self.cv.canvasy(event.y)
        scroll_top = self.cv.canvasy(0)
        for i, card in enumerate(self.items):
            y0 = card["y0"]
            y1 = card["y1"]
            if y0 <= y + scroll_top <= y1:
                self._on_click(i, card.get("data"))
                return

    def _y(self, idx: int) -> int:
        return idx * (CARD_H + CARD_GAP)

    def _draw_pick_card(self, idx: int, item: dict, my_pos: str):
        """绘制 Pick/Ban 推荐卡片"""
        x0, y0 = PAD_X, self._y(idx)
        w = self.cv.winfo_width() - PAD_X * 2
        if w < 200:
            w = 600
        x1, y1 = x0 + w, y0 + CARD_H

        cid = item.get("champion_id", 0)
        name = item.get("name", "")
        tier = item.get("tier", "B")
        role = item.get("role", "")
        score = item.get("score", 0)
        wr = item.get("winrate", 50)
        reasons = item.get("reasons", [])
        is_top = idx == 0
        pos_match = item.get("position_match", False)

        border_c = CK["a1"] if is_top else CK["border"]
        fill_c = CK["card"]

        ids = {}

        # 背景
        ids["bg"] = self.cv.create_rectangle(x0, y0, x1, y1, fill=fill_c, outline=border_c, width=1)

        cx = x0 + 12  # cursor

        # ── 排名 ──
        rank_c = CK["a1"] if idx == 0 else (CK["a3"] if idx < 3 else CK["dim"])
        ids["rank"] = self.cv.create_text(cx + 14, y0 + CARD_H // 2,
                                           text=f"#{idx + 1}", fill=rank_c,
                                           font=("Segoe UI", 12, "bold"), anchor="w")
        cx += 42

        # ── 头像（占位圆 + 图片） ──
        img_cy = y0 + CARD_H // 2
        role_c = ROLE_COLORS.get(role, CK["dim"])
        ids["avatar_bg"] = self.cv.create_oval(cx, img_cy - PICK_IMG // 2,
                                                cx + PICK_IMG, img_cy + PICK_IMG // 2,
                                                fill=role_c, outline="", width=0)
        ids["avatar_text"] = self.cv.create_text(cx + PICK_IMG // 2, img_cy,
                                                  text=name[0] if name else "?",
                                                  fill="white", font=("Segoe UI", 18, "bold"))
        ids["avatar_img"] = None  # placeholder for when image loads
        ids["_avatar_cx"] = cx
        ids["_avatar_cy"] = img_cy
        ids["_avatar_size"] = PICK_IMG

        # 已缓存则直接显示
        photo = get_photo(cid, PICK_IMG)
        if photo:
            ids["avatar_img"] = self.cv.create_image(cx + PICK_IMG // 2, img_cy, image=photo)
            self.cv.itemconfigure(ids["avatar_bg"], state="hidden")
            self.cv.itemconfigure(ids["avatar_text"], state="hidden")

        cx += PICK_IMG + 14

        # ── 名称 + 标签 ──
        tc = TIER_COLORS.get(tier, "#666")
        txt = name
        txt += f"  {tier}"
        txt += f"  [{POS_LABELS.get(role, role)}]"
        if pos_match:
            txt += "  ✓对位"
        ids["title"] = self.cv.create_text(cx, y0 + 18, text=txt, fill=CK["text"],
                                            font=("Segoe UI", 13, "bold"), anchor="w")
        # tier/role 着色（分开画）
        tw = len(name) * 10 + 4
        ids["tier_tag"] = self.cv.create_text(cx + tw, y0 + 18, text=tier, fill=tc,
                                                font=("Segoe UI", 10, "bold"), anchor="w")
        tw += 24
        ids["role_tag"] = self.cv.create_text(cx + tw, y0 + 18,
                                               text=POS_LABELS.get(role, role), fill=CK["dim"],
                                               font=("Segoe UI", 9), anchor="w")

        # ── Reasons ──
        if reasons:
            rtext = " · ".join(reasons[:4])
            # 根据内容着色
            if "对位克制" in rtext:
                rc = CK["a6"]
            elif "克制" in rtext:
                rc = CK["green"]
            elif "被" in rtext:
                rc = CK["red"]
            elif "T0" in rtext or "版本" in rtext:
                rc = CK["a1"]
            elif "协同" in rtext or "对线" in rtext:
                rc = "#6cd4a0"
            else:
                rc = CK["dim"]
            ids["reasons"] = self.cv.create_text(cx, y0 + 40, text=rtext, fill=rc,
                                                  font=("Segoe UI", 9), anchor="w")

        # ── 分数（右对齐） ──
        if score >= 35:
            sc = CK["a1"]
        elif score >= 20:
            sc = CK["a3"]
        elif score >= 0:
            sc = CK["dim"]
        else:
            sc = CK["red"]
        ids["score"] = self.cv.create_text(x1 - 16, y0 + 22, text=f"+{score:.0f}",
                                            fill=sc, font=("Segoe UI", 15, "bold"), anchor="e")
        wr_c = CK["green"] if wr >= 52 else (CK["red"] if wr < 48 else CK["dim"])
        ids["wr"] = self.cv.create_text(x1 - 16, y0 + 44, text=f"WR {wr:.1f}%",
                                         fill=wr_c, font=("Segoe UI", 9), anchor="e")

        data = {
            "champion_id": cid, "name": name, "role": role,
            "img_cx": ids["_avatar_cx"], "img_cy": ids["_avatar_cy"],
            "img_size": PICK_IMG,
            "avatar_bg_id": ids["avatar_bg"], "avatar_text_id": ids["avatar_text"],
            "avatar_img_id_key": "avatar_img",
        }
        self.items.append({"y0": y0, "y1": y1, "ids": ids, "data": data})

    def _draw_all_row(self, idx: int, item: dict):
        """绘制全部英雄列表行（轻量）"""
        x0, y0 = 8, self._y(idx)
        w = self.cv.winfo_width() - 16
        if w < 200:
            w = 600
        x1, y1 = x0 + w, y0 + CARD_H

        cid = item["key"]
        name = item["name"]
        tier = item["tier"]
        role = item["role"]
        wr = item["wr"]
        banned = item.get("banned", False)
        picked = item.get("picked", False)
        available = item.get("available", True)

        bg_c = "#1a1015" if banned else ("#101820" if picked else CK["card"])
        border_c = CK["accent"] if item.get("_selected") else CK["border"]
        fg_n = CK["text"] if available else CK["muted"]

        ids = {}
        ids["bg"] = self.cv.create_rectangle(x0, y0, x1, y1, fill=bg_c, outline=border_c, width=1)

        img_cy = y0 + CARD_H // 2
        role_c = ROLE_COLORS.get(role, CK["dim"])
        ids["avatar_bg"] = self.cv.create_oval(x0 + 12, img_cy - ALL_IMG // 2,
                                                x0 + 12 + ALL_IMG, img_cy + ALL_IMG // 2,
                                                fill=role_c, outline="", width=0)
        ids["avatar_text"] = self.cv.create_text(x0 + 12 + ALL_IMG // 2, img_cy,
                                                  text=name[0] if name else "?",
                                                  fill="white", font=("Segoe UI", 12, "bold"))
        ids["avatar_img"] = None
        ids["_avatar_cx"] = x0 + 12
        ids["_avatar_cy"] = img_cy
        ids["_avatar_size"] = ALL_IMG

        photo = get_photo(cid, ALL_IMG)
        if photo:
            ids["avatar_img"] = self.cv.create_image(x0 + 12 + ALL_IMG // 2, img_cy, image=photo)
            self.cv.itemconfigure(ids["avatar_bg"], state="hidden")
            self.cv.itemconfigure(ids["avatar_text"], state="hidden")

        cx = x0 + 12 + ALL_IMG + 12
        tc = TIER_COLORS.get(tier, "#666")
        ids["name_lbl"] = self.cv.create_text(cx, img_cy, text=name, fill=fg_n,
                                               font=("Segoe UI", 11, "bold"), anchor="w")
        cx += len(name) * 10 + 10
        ids["role_lbl"] = self.cv.create_text(cx, img_cy, text=POS_LABELS.get(role, role),
                                               fill=CK["dim"], font=("Segoe UI", 9), anchor="w")
        cx += 44
        ids["tier_lbl"] = self.cv.create_text(cx, img_cy, text=tier, fill=tc,
                                               font=("Segoe UI", 9, "bold"), anchor="w")
        cx += 24
        ids["wr_lbl"] = self.cv.create_text(cx, img_cy, text=f"WR {wr:.1f}%",
                                             fill=CK["dim"], font=("Segoe UI", 9), anchor="w")

        status = "已Ban" if banned else ("已选" if picked else "")
        if status:
            st_c = CK["red"] if banned else CK["a3"]
            ids["status_lbl"] = self.cv.create_text(x1 - 14, img_cy, text=status, fill=st_c,
                                                     font=("Segoe UI", 9), anchor="e")

        data = {
            "champion_id": cid, "name": name, "role": role,
            "img_cx": ids["_avatar_cx"], "img_cy": ids["_avatar_cy"],
            "img_size": ALL_IMG,
            "avatar_bg_id": ids["avatar_bg"], "avatar_text_id": ids["avatar_text"],
            "avatar_img_id_key": "avatar_img",
        }
        self.items.append({"y0": y0, "y1": y1, "ids": ids, "data": data})

    def finalize(self):
        """设 Canvas 滚动区"""
        self._total_h = len(self.items) * (CARD_H + CARD_GAP)
        self.cv.configure(scrollregion=(0, 0, self.cv.winfo_width(), self._total_h + 10))

    def update_avatar(self, ckey: int, photo: ImageTk.PhotoImage, size: int):
        """图片加载完，更新 Canvas 中的头像"""
        for card in self.items:
            d = card.get("data", {})
            if d.get("champion_id") == ckey and d.get("img_size") == size:
                cx = d["img_cx"] + size // 2
                cy = d["img_cy"]
                ids = card["ids"]
                # 创建图片
                img_id = self.cv.create_image(cx, cy, image=photo)
                ids["avatar_img"] = img_id
                # 隐藏占位
                self.cv.itemconfigure(ids["avatar_bg"], state="hidden")
                self.cv.itemconfigure(ids["avatar_text"], state="hidden")
                # 提升图片层级
                self.cv.tag_raise(img_id)
                return


# ═══════════════════════════════════════════════════════════════════════════════
#  Main App
# ═══════════════════════════════════════════════════════════════════════════════
class LoLBPUI:
    def __init__(self, root, state_ref, manual_ref, lcu_conn_ref):
        self.root = root
        self.state_ref = state_ref
        self.manual_ref_cb = manual_ref
        self.lcu_conn_ref = lcu_conn_ref
        self.manual_mode = False
        self.selected_champ = None
        self._filter_pos = "all"
        self._last_state_hash = ""
        self._refresh_busy = False
        self._active_tab = "pick"
        self._img_refs: list = []

        self.root.title("LoL BP Assistant")
        self.root.geometry("1240x820")
        self.root.configure(bg=CK["bg"])
        self.root.minsize(920, 620)

        try:
            if getattr(sys, 'frozen', False):
                ip = os.path.join(sys._MEIPASS, "BP.ico")
            else:
                ip = os.path.join(os.path.dirname(os.path.abspath(__file__)), "BP.ico")
            if os.path.exists(ip):
                self.root.iconbitmap(ip)
        except Exception:
            pass

        self._setup_styles()
        self._build_topbar()
        self._build_layout()
        self._start_timer_refresh()
        self._start_data_refresh()

    # ── Styles ──
    def _setup_styles(self):
        s = ttk.Style()
        s.theme_use("clam")
        s.configure(".", background=CK["bg"], foreground=CK["text"], font=("Segoe UI", 10))
        s.configure("TNotebook", background=CK["bg"], borderwidth=0)
        s.configure("TNotebook.Tab", background=CK["bg2"], foreground=CK["dim"],
                    padding=[14, 5], font=("Segoe UI", 10))
        s.map("TNotebook.Tab", background=[("selected", CK["bg3"])],
              foreground=[("selected", CK["a4"])])
        s.configure("Custom.Vertical.TScrollbar", background=CK["bg3"],
                    troughcolor=CK["bg"], bordercolor=CK["bg"], arrowcolor=CK["dim"],
                    arrowsize=14, gripcount=0)
        s.map("Custom.Vertical.TScrollbar",
              background=[("active", CK["border2"]), ("!disabled", CK["bg3"])])

    # ── Topbar ──
    def _build_topbar(self):
        top = tk.Frame(self.root, bg=CK["bg2"], height=HEADER_H)
        top.pack(fill="x"); top.pack_propagate(False)
        inn = tk.Frame(top, bg=CK["bg2"])
        inn.pack(fill="both", expand=True, padx=18, pady=6)

        tk.Label(inn, text="◆ LoL BP Assistant", fg=CK["a5"], bg=CK["bg2"],
                 font=("Segoe UI", 14, "bold")).pack(side="left")

        mf = tk.Frame(inn, bg=CK["bg2"]); mf.pack(side="right", padx=(8, 0))
        self.auto_btn = tk.Button(mf, text="自动模式", bg=CK["bg3"], fg=CK["a4"],
                                   font=("Segoe UI", 9), relief="flat", padx=12, pady=3, bd=0,
                                   activebackground=CK["bg3"], activeforeground=CK["a4"],
                                   command=self._toggle_mode, cursor="hand2")
        self.auto_btn.pack(side="left", padx=3)
        self.manual_btn = tk.Button(mf, text="手动模式", bg=CK["bg2"], fg=CK["dim"],
                                     font=("Segoe UI", 9), relief="flat", padx=12, pady=3, bd=0,
                                     activebackground=CK["bg3"], activeforeground=CK["text"],
                                     command=self._toggle_mode, cursor="hand2")
        self.manual_btn.pack(side="left", padx=3)

        self.timer_label = tk.Label(inn, text="", font=("Segoe UI", 17, "bold"),
                                     fg=CK["a5"], bg=CK["bg2"])
        self.timer_label.pack(side="right", padx=(18, 0))
        self.status_label = tk.Label(inn, text="○ 未连接", fg=CK["dim"], bg=CK["bg2"],
                                      font=("Segoe UI", 9))
        self.status_label.pack(side="right", padx=(14, 0))

    # ── Layout ──
    def _build_layout(self):
        panes = tk.PanedWindow(self.root, orient="horizontal", bg=CK["bg"],
                               sashwidth=1, sashrelief="flat")
        panes.pack(fill="both", expand=True)

        left = tk.Frame(panes, bg=CK["bg"]); panes.add(left, width=900)

        self.notebook = ttk.Notebook(left)
        self.notebook.pack(fill="both", expand=True, padx=(14, 8), pady=10)
        self.notebook.bind("<<NotebookTabChanged>>", self._on_tab_changed)

        self.pick_tab = tk.Frame(self.notebook, bg=CK["bg"])
        self.ban_tab = tk.Frame(self.notebook, bg=CK["bg"])
        self.all_tab = tk.Frame(self.notebook, bg=CK["bg"])
        self.notebook.add(self.pick_tab, text="⚔ Pick 推荐")
        self.notebook.add(self.ban_tab, text="⛔ Ban 推荐")
        self.notebook.add(self.all_tab, text="📋 全部英雄")

        # 每个 tab 各有一个 Canvas
        self._card_lists: dict[str, CanvasCardList] = {}
        self._canvas_widgets: dict[str, tk.Canvas] = {}
        for tab, key in [(self.pick_tab, "pick"), (self.ban_tab, "ban"), (self.all_tab, "all")]:
            self._build_canvas_tab(tab, key)

        # 右侧栏
        right = tk.Frame(panes, bg=CK["bg2"]); panes.add(right, width=320)
        self._build_sidebar(right)

    def _build_canvas_tab(self, parent, key: str):
        ff = tk.Frame(parent, bg=CK["bg"])
        ff.pack(fill="x", padx=12, pady=(8, 2))
        tk.Label(ff, text="位置", fg=CK["dim"], bg=CK["bg"],
                 font=("Segoe UI", 9)).pack(side="left", padx=(0, 8))

        self._pos_btns = getattr(self, '_pos_btns', {})
        for pk in ["all", "top", "jungle", "mid", "bot", "support"]:
            lb = "全部" if pk == "all" else POS_LABELS.get(pk, pk)
            btn = tk.Button(ff, text=lb, bg=CK["bg2"], fg=CK["dim"], font=("Segoe UI", 9),
                           relief="flat", padx=10, pady=2, bd=0,
                           activebackground=CK["bg3"], activeforeground=CK["text"],
                           command=lambda p=pk: self._set_filter(p), cursor="hand2")
            btn.pack(side="left", padx=2)
            self._pos_btns[pk] = btn
        self._pos_btns["all"].configure(bg=CK["bg3"], fg=CK["a4"])

        container = tk.Frame(parent, bg=CK["bg"])
        container.pack(fill="both", expand=True, padx=12, pady=4)

        canvas = tk.Canvas(container, bg=CK["bg"], highlightthickness=0, bd=0)
        scrollbar = ttk.Scrollbar(container, orient="vertical", command=canvas.yview,
                                   style="Custom.Vertical.TScrollbar")
        canvas.configure(yscrollcommand=scrollbar.set)
        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        self._canvas_widgets[key] = canvas
        self._card_lists[key] = CanvasCardList(canvas, CK["bg"])

    def _on_tab_changed(self, event=None):
        sel = self.notebook.select()
        idx = self.notebook.index(sel)
        self._active_tab = {0: "pick", 1: "ban", 2: "all"}.get(idx, "pick")
        # 切换时立即重建当前 tab（可能已过期）
        self._last_state_hash = ""
        self._smart_refresh()

    # ── Sidebar ──
    def _build_sidebar(self, parent):
        sf = tk.Frame(parent, bg=CK["bg2"])
        sf.pack(fill="both", expand=True, padx=10, pady=10)

        for team, dc in [("我方", "#4da0cc"), ("敌方", "#d94a5a")]:
            row = tk.Frame(sf, bg=CK["bg2"]); row.pack(fill="x", pady=(8, 2))
            tk.Label(row, text="●", fg=dc, bg=CK["bg2"], font=("Segoe UI", 9)).pack(side="left", padx=(0, 4))
            tk.Label(row, text=team, fg=CK["text"], bg=CK["bg2"], font=("Segoe UI", 10, "bold")).pack(side="left")

        self.my_ban_frame = tk.Frame(sf, bg=CK["bg2"]); self.my_ban_frame.pack(fill="x", pady=(2, 0))
        self.my_pick_list = tk.Frame(sf, bg=CK["bg2"]); self.my_pick_list.pack(fill="x", pady=(2, 0))
        self.my_prepick_frame = tk.Frame(sf, bg=CK["bg2"]); self.my_prepick_frame.pack(fill="x", pady=(2, 0))
        tk.Frame(sf, height=1, bg=CK["border"]).pack(fill="x", pady=10)
        self.enemy_ban_frame = tk.Frame(sf, bg=CK["bg2"]); self.enemy_ban_frame.pack(fill="x", pady=(2, 0))
        self.enemy_pick_list = tk.Frame(sf, bg=CK["bg2"]); self.enemy_pick_list.pack(fill="x", pady=(2, 0))
        self.enemy_prepick_frame = tk.Frame(sf, bg=CK["bg2"]); self.enemy_prepick_frame.pack(fill="x", pady=(2, 0))
        tk.Frame(sf, height=1, bg=CK["border"]).pack(fill="x", pady=10)
        self.my_comp_label = tk.Label(sf, text="", font=("Segoe UI", 10, "bold"),
                                       fg=CK["dim"], bg=CK["bg2"]); self.my_comp_label.pack(anchor="w", pady=2)
        self.enemy_comp_label = tk.Label(sf, text="", font=("Segoe UI", 10, "bold"),
                                          fg=CK["dim"], bg=CK["bg2"]); self.enemy_comp_label.pack(anchor="w", pady=2)
        self._sep3 = tk.Frame(sf, height=1, bg=CK["border"]); self._sep3.pack(fill="x", pady=10)

        self.manual_frame = tk.Frame(sf, bg=CK["bg2"])
        tk.Label(self.manual_frame, text="── 手动操作 ──", fg=CK["dim"], bg=CK["bg2"],
                 font=("Segoe UI", 9)).pack(anchor="w", pady=(0, 6))
        self.search_var = tk.StringVar()
        self.search_entry = tk.Entry(self.manual_frame, textvariable=self.search_var,
                                      bg=CK["bg3"], fg=CK["text"], insertbackground=CK["text"],
                                      font=("Segoe UI", 10), relief="flat", bd=0)
        self.search_entry.pack(fill="x", ipady=5, padx=1)
        self.search_entry.insert(0, "搜索英雄...")
        self.search_entry.bind("<FocusIn>", lambda e: self.search_entry.delete(0, "end"))
        self.search_var.trace_add("write", lambda *a: self._on_search_type())

        self.search_results = tk.Listbox(self.manual_frame, bg=CK["bg"], fg=CK["text"],
                                          font=("Segoe UI", 10), relief="flat", height=5, bd=0,
                                          selectbackground=CK["bg3"], selectforeground=CK["a4"],
                                          highlightthickness=0)
        self.search_results.pack(fill="x", pady=5)
        self.search_results.bind("<<ListboxSelect>>", self._on_search_select)

        br = tk.Frame(self.manual_frame, bg=CK["bg2"]); br.pack(fill="x", pady=3)
        for txt, cmd, fgc in [("我方 Ban","my_ban",CK["red"]),("敌方 Ban","enemy_ban",CK["red"]),
                               ("我方 Pick","my_pick",CK["green"]),("敌方 Pick","enemy_pick",CK["green"])]:
            tk.Button(br, text=txt, bg=CK["bg3"], fg=fgc, font=("Segoe UI", 9), relief="flat",
                      padx=7, pady=3, bd=0, activebackground=CK["border2"], activeforeground=fgc,
                      command=lambda t=cmd: self._manual_action(t), cursor="hand2").pack(side="left", padx=2)

        pr = tk.Frame(self.manual_frame, bg=CK["bg2"]); pr.pack(fill="x", pady=3)
        tk.Label(pr, text="位置", fg=CK["dim"], bg=CK["bg2"], font=("Segoe UI", 9)).pack(side="left")
        self.pos_var = tk.StringVar(value="")
        ttk.OptionMenu(pr, self.pos_var, "", "top", "jungle", "mid", "bot", "support").pack(side="left", padx=6)
        tk.Button(self.manual_frame, text="重置", bg=CK["bg3"], fg=CK["dim"], font=("Segoe UI", 9),
                  relief="flat", padx=16, pady=3, bd=0, activebackground=CK["border2"],
                  activeforeground=CK["text"], command=self._manual_reset, cursor="hand2").pack(pady=6)

    # ═══════════════════════════ Scheduler ═══════════════════════════
    def _start_timer_refresh(self):
        def _tick():
            if self.manual_mode:
                self.timer_label.configure(text="")
            else:
                r = self.state_ref.get("timer", {}).get("remaining_sec", 0)
                if r > 0:
                    m, s = divmod(int(r), 60)
                    self.timer_label.configure(text=f"{m}:{s:02d}",
                                                fg=CK["red"] if r < 10 else CK["a5"])
                else:
                    self.timer_label.configure(text="")
            self._timer_job = self.root.after(1000, _tick)
        self._timer_job = self.root.after(1000, _tick)

    def _start_data_refresh(self):
        def _tick():
            if not self._refresh_busy:
                try:
                    self._smart_refresh()
                except Exception:
                    pass
            self._data_job = self.root.after(2000, _tick)
        self._data_job = self.root.after(500, _tick)

    # ═══════════════════════════ State hash ═══════════════════════════
    def _state_hash(self):
        if self.manual_mode:
            ms = self.manual_ref_cb()
            raw = json.dumps({"b": sorted(ms.get("my_bans",[]) + ms.get("enemy_bans",[])),
                "p": sorted([p["champion_id"] for p in ms.get("my_picks",[]) + ms.get("enemy_picks",[])]),
                "pp": sorted(ms.get("my_prepicks",[]) + ms.get("enemy_prepicks",[])),
                "po": ms.get("my_position","")}, sort_keys=True)
        else:
            s = self.state_ref
            raw = json.dumps({"cs": s.get("in_champ_select"), "cn": s.get("connected"),
                "b": sorted(s.get("my_team_bans",[]) + s.get("enemy_bans",[])),
                "p": sorted([p.get("champion_id",p) if isinstance(p,dict) else p
                    for p in s.get("my_team_picks",[]) + s.get("enemy_picks",[])]),
                "pp": sorted(s.get("my_prepicks",[]) + s.get("enemy_prepicks",[])),
                "po": s.get("my_position",""),
                "r": [r.get("champion_id") for r in s.get("recommendations",[])],
                "br": [r.get("champion_id") for r in s.get("ban_recommendations",[])]}, sort_keys=True)
        return hashlib.md5(raw.encode()).hexdigest()

    def _smart_refresh(self):
        h = self._state_hash()
        if h == self._last_state_hash:
            return
        self._last_state_hash = h
        self._refresh_busy = True
        try:
            self._rebuild_visible()
        finally:
            self._refresh_busy = False

    def _rebuild_visible(self):
        """仅重建当前可见 tab"""
        if self.manual_mode:
            self.status_label.configure(text="● 手动模式", fg=CK["a1"])
            self._rebuild_manual_tab(self._active_tab)
        else:
            s = self.state_ref
            if s.get("in_champ_select"):
                self.status_label.configure(text="● 选人中", fg=CK["a3"])
            elif s.get("connected"):
                self.status_label.configure(text="● 已连接", fg=CK["green"])
            else:
                self.status_label.configure(text="○ 未连接", fg=CK["dim"])
            self._rebuild_auto_tab(self._active_tab)

        # 侧边栏始终刷新（轻量）
        if self.manual_mode:
            ms = self.manual_ref_cb()
            my_pick_ids = [p["champion_id"] for p in ms.get("my_picks", [])]
            enemy_pick_ids = [p["champion_id"] for p in ms.get("enemy_picks", [])]
            ss = {"my_team_bans": ms.get("my_bans", []), "enemy_bans": ms.get("enemy_bans", []),
                  "my_team_picks": ms.get("my_picks", []), "enemy_picks": ms.get("enemy_picks", []),
                  "my_prepicks": ms.get("my_prepicks", []), "enemy_prepicks": ms.get("enemy_prepicks", []),
                  "my_position": ms.get("my_position", ""),
                  "my_composition": analyze_composition(my_pick_ids),
                  "enemy_composition": analyze_composition(enemy_pick_ids)}
        else:
            ss = self.state_ref
        self._refresh_sidebar(ss)

    def _rebuild_auto_tab(self, key: str):
        state = self.state_ref
        pos = state.get("my_position", "")

        if key == "pick":
            self._draw_pick_cards(state.get("recommendations", []), pos)
        elif key == "ban":
            self._draw_ban_cards(state.get("ban_recommendations", []), pos)
        elif key == "all":
            self._draw_all_rows(state)

    def _rebuild_manual_tab(self, key: str):
        ms = self.manual_ref_cb()
        my_bans = ms.get("my_bans", []); enemy_bans = ms.get("enemy_bans", [])
        my_picks = ms.get("my_picks", []); enemy_picks = ms.get("enemy_picks", [])
        my_pick_ids = [p["champion_id"] for p in my_picks]
        enemy_pick_ids = [p["champion_id"] for p in enemy_picks]
        used = set(my_bans + enemy_bans + my_pick_ids + enemy_pick_ids)
        pos = ms.get("my_position", "")

        recs, _ = manual_build(ms)
        ban_recs = build_ban_recommendations(used, ms.get("my_prepicks", my_pick_ids),
                                              ms.get("enemy_prepicks", enemy_pick_ids), pos)

        if key == "pick":
            self._draw_pick_cards(recs, pos)
        elif key == "ban":
            self._draw_ban_cards(ban_recs, pos)
        elif key == "all":
            self._draw_all_rows_manual(my_bans, enemy_bans, my_picks, enemy_picks)

    # ═══════════════════════════ Canvas drawing ═══════════════════════════
    def _draw_pick_cards(self, items, my_pos):
        cl = self._card_lists["pick"]
        cl.clear()
        filtered = [it for it in items if self._filter_pos == "all" or it.get("role") == self._filter_pos]
        if not filtered:
            cl.cv.create_text(400, 60, text="暂无推荐数据", fill=CK["dim"], font=("Segoe UI", 11))
        else:
            for i, item in enumerate(filtered):
                cl._draw_pick_card(i, item, my_pos)
        cl.finalize()

        # 异步加载头像
        keys = [it.get("champion_id", 0) for it in filtered]
        if keys:
            start_async_load(self.root, keys, PICK_IMG, lambda ck, ph, sz: self._on_avatar(ck, ph, "pick"))

    def _draw_ban_cards(self, items, my_pos):
        cl = self._card_lists["ban"]
        cl.clear()
        filtered = [it for it in items if self._filter_pos == "all" or it.get("role") == self._filter_pos]
        if not filtered:
            cl.cv.create_text(400, 60, text="暂无推荐数据", fill=CK["dim"], font=("Segoe UI", 11))
        else:
            for i, item in enumerate(filtered):
                cl._draw_pick_card(i, item, my_pos)
        cl.finalize()
        keys = [it.get("champion_id", 0) for it in filtered]
        if keys:
            start_async_load(self.root, keys, PICK_IMG, lambda ck, ph, sz: self._on_avatar(ck, ph, "ban"))

    def _draw_all_rows(self, state):
        cl = self._card_lists["all"]
        cl.clear()

        all_banned = set(state.get("my_team_bans", []) + state.get("enemy_bans", []))
        all_picked = set()
        for p in state.get("my_team_picks", []) + state.get("enemy_picks", []):
            all_picked.add(p.get("champion_id", p) if isinstance(p, dict) else p)
        used = all_banned | all_picked

        champs = []
        for key in cd.all_champions():
            if self._filter_pos != "all" and cd.get_role(key) != self._filter_pos:
                continue
            meta = cd.get_meta(key)
            champs.append({"key": key, "name": cd.get_name(key), "role": cd.get_role(key),
                "tier": meta.get("tier", "B"), "wr": meta.get("wr", 50),
                "banned": key in all_banned, "picked": key in all_picked, "available": key not in used})
        champs.sort(key=lambda x: (0 if x["available"] else 1,
                                    {"S":0,"A":1,"B":2}.get(x["tier"],2), -x["wr"]))

        for i, item in enumerate(champs[:60]):
            cl._draw_all_row(i, item)
        cl.finalize()

        keys = [c["key"] for c in champs[:60]]
        if keys:
            start_async_load(self.root, keys, ALL_IMG, lambda ck, ph, sz: self._on_avatar(ck, ph, "all"))

    def _draw_all_rows_manual(self, my_bans, enemy_bans, my_picks, enemy_picks):
        cl = self._card_lists["all"]
        cl.clear()

        used = set(my_bans + enemy_bans + [p["champion_id"] for p in my_picks + enemy_picks])
        champs = []
        for key in cd.all_champions():
            if self._filter_pos != "all" and cd.get_role(key) != self._filter_pos:
                continue
            meta = cd.get_meta(key)
            champs.append({"key": key, "name": cd.get_name(key), "role": cd.get_role(key),
                "tier": meta.get("tier", "B"), "wr": meta.get("wr", 50),
                "banned": key in my_bans or key in enemy_bans,
                "picked": key in [p["champion_id"] for p in my_picks + enemy_picks],
                "available": key not in used,
                "_selected": key == self.selected_champ})
        champs.sort(key=lambda x: (0 if x["available"] else 1,
                                    {"S":0,"A":1,"B":2}.get(x["tier"],2), -x["wr"]))

        for i, item in enumerate(champs[:60]):
            cl._draw_all_row(i, item)
        cl.finalize()

        keys = [c["key"] for c in champs[:60]]
        if keys:
            start_async_load(self.root, keys, ALL_IMG, lambda ck, ph, sz: self._on_avatar(ck, ph, "all"))

    def _on_avatar(self, ckey: int, photo: ImageTk.PhotoImage, tab: str):
        """头像异步加载完成回调"""
        self._img_refs.append(photo)
        cl = self._card_lists.get(tab)
        if cl:
            cl.update_avatar(ckey, photo, PICK_IMG if tab in ("pick", "ban") else ALL_IMG)

    # ═══════════════════════════ Filter / Mode ═══════════════════════════
    def _set_filter(self, pos):
        self._filter_pos = pos
        for k, btn in self._pos_btns.items():
            btn.configure(bg=CK["bg3"] if k == pos else CK["bg2"],
                          fg=CK["a4"] if k == pos else CK["dim"])
        self._last_state_hash = ""
        self._smart_refresh()

    def _toggle_mode(self):
        self.manual_mode = not self.manual_mode
        if self.manual_mode:
            ms = self.manual_ref_cb(); ms.clear()
            ms.update({"my_bans": [], "enemy_bans": [], "my_picks": [],
                        "enemy_picks": [], "my_prepicks": [], "enemy_prepicks": [], "my_position": ""})
            self.auto_btn.configure(bg=CK["bg2"], fg=CK["dim"])
            self.manual_btn.configure(bg=CK["bg3"], fg=CK["a4"])
            self.manual_frame.pack(fill="x", before=self._sep3)
        else:
            self.auto_btn.configure(bg=CK["bg3"], fg=CK["a4"])
            self.manual_btn.configure(bg=CK["bg2"], fg=CK["dim"])
            self.manual_frame.pack_forget()
        self._last_state_hash = ""
        self._smart_refresh()

    # ═══════════════════════════ Search / Manual ═══════════════════════════
    def _on_search_type(self):
        q = self.search_var.get().strip(); self.search_results.delete(0, "end")
        if len(q) < 1: return
        results = []
        for key in cd.all_champions():
            n = cd.get_name(key); r = cd.get_role(key)
            if q.lower() in n.lower() or q.lower() in r.lower():
                results.append((key, n, r, cd.get_tier(key)))
        results.sort(key=lambda x: ({"S":0,"A":1,"B":2,"C":3}.get(x[3],2), x[1]))
        for key, n, r, t in results[:15]:
            self.search_results.insert("end", f"  {n}  [{POS_LABELS.get(r,r)}]  {t}")

    def _on_search_select(self, event=None):
        sel = self.search_results.curselection()
        if sel:
            text = self.search_results.get(sel[0])
            name = text.strip().split("[")[0].strip()
            for key in cd.all_champions():
                if cd.get_name(key) == name: self.selected_champ = key; break

    def _manual_action(self, action):
        if not self.selected_champ: return
        ms = self.manual_ref_cb(); key = self.selected_champ
        pos = self.pos_var.get() or cd.get_role(key)
        if action == "my_ban":
            if key not in ms["my_bans"] and len(ms["my_bans"]) < 5: ms["my_bans"].append(key)
        elif action == "enemy_ban":
            if key not in ms["enemy_bans"] and len(ms["enemy_bans"]) < 5: ms["enemy_bans"].append(key)
        elif action == "my_pick":
            if key not in [p["champion_id"] for p in ms["my_picks"]]:
                ms["my_picks"].append({"champion_id": key, "position": pos})
        elif action == "enemy_pick":
            if key not in [p["champion_id"] for p in ms["enemy_picks"]]:
                ms["enemy_picks"].append({"champion_id": key, "position": pos})
        self._last_state_hash = ""; self._smart_refresh()

    def _manual_reset(self):
        ms = self.manual_ref_cb(); ms.clear()
        ms.update({"my_bans": [], "enemy_bans": [], "my_picks": [],
                    "enemy_picks": [], "my_prepicks": [], "enemy_prepicks": [], "my_position": ""})
        self.selected_champ = None
        self._last_state_hash = ""; self._smart_refresh()

    # ═══════════════════════════ Sidebar ═══════════════════════════
    def _refresh_sidebar(self, state):
        for frame in [self.my_ban_frame, self.my_pick_list, self.my_prepick_frame,
                      self.enemy_ban_frame, self.enemy_pick_list, self.enemy_prepick_frame]:
            for w in frame.winfo_children(): w.destroy()

        for key in state.get("my_team_bans", []):
            tk.Label(self.my_ban_frame, text=cd.get_name(key), bg="#2a1015", fg=CK["red"],
                     font=("Segoe UI", 9, "overstrike"), padx=7, pady=2).pack(side="left", padx=2, pady=1)
        for key in state.get("enemy_bans", []):
            tk.Label(self.enemy_ban_frame, text=cd.get_name(key), bg="#2a1015", fg=CK["red"],
                     font=("Segoe UI", 9, "overstrike"), padx=7, pady=2).pack(side="left", padx=2, pady=1)

        for p in state.get("my_team_picks", []):
            if isinstance(p, dict): k, po = p["champion_id"], p.get("position", "")
            else: k, po = p, ""
            r = f" {POS_LABELS.get(po,'')}" if po else ""
            tk.Label(self.my_pick_list, text=f"{cd.get_name(k)}{r}", bg=CK["card"], fg=CK["text"],
                     font=("Segoe UI", 9), padx=8, pady=3).pack(anchor="w", pady=2, padx=2, fill="x")
        for p in state.get("enemy_picks", []):
            if isinstance(p, dict): k, po = p["champion_id"], p.get("position", "")
            else: k, po = p, ""
            r = f" {POS_LABELS.get(po,'')}" if po else ""
            tk.Label(self.enemy_pick_list, text=f"{cd.get_name(k)}{r}", bg=CK["card"], fg=CK["text"],
                     font=("Segoe UI", 9), padx=8, pady=3).pack(anchor="w", pady=2, padx=2, fill="x")

        for key in state.get("my_prepicks", []):
            tk.Label(self.my_prepick_frame, text=f"✦ {cd.get_name(key)}", bg="#182018", fg=CK["gold"],
                     font=("Segoe UI", 9), padx=7, pady=2).pack(side="left", padx=2, pady=1)
        for key in state.get("enemy_prepicks", []):
            tk.Label(self.enemy_prepick_frame, text=f"✦ {cd.get_name(key)}", bg="#182018", fg=CK["gold"],
                     font=("Segoe UI", 9), padx=7, pady=2).pack(side="left", padx=2, pady=1)

        myc = state.get("my_composition", {}); enc = state.get("enemy_composition", {})
        self.my_comp_label.configure(text=f"我方: {myc.get('icon','')} {myc.get('name','')}" if myc else "")
        self.enemy_comp_label.configure(text=f"敌方: {enc.get('icon','')} {enc.get('name','')}" if enc else "")


def launch_native_ui(state_ref, manual_ref, lcu_conn_ref):
    root = tk.Tk()
    LoLBPUI(root, state_ref, manual_ref, lcu_conn_ref)
    root.mainloop()
