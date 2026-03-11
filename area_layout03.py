"""
area_layout.py – 캔버스 안에 도형을 배치하고 면적 비율을 균등 분배하는 프로그램
"""
import copy
import json
import math
import os
import random
import tkinter as tk
from tkinter import ttk, colorchooser, messagebox, filedialog, simpledialog

# ──────────────────────────────────────────────
# 색상 테마
# ──────────────────────────────────────────────
C = {
    "bg":        "#1e1e2e",
    "panel":     "#2a2a3e",
    "card":      "#313147",
    "border":    "#44446a",
    "accent":    "#7c6af7",
    "accent2":   "#56cfb2",
    "fg":        "#cdd6f4",
    "fg2":       "#a6adc8",
    "fg3":       "#6c7086",
    "red":       "#f38ba8",
    "yellow":    "#f9e2af",
    "canvas_bg": "#242436",
}

SHAPE_TYPES = ["원", "정사각형", "직사각형", "정삼각형", "타원", "정육각형"]
# 세로가 가로와 독립적으로 입력되는 도형
DUAL_DIM_TYPES = {"직사각형", "타원"}

DEFAULT_COLORS = [
    "#7c6af7", "#56cfb2", "#f38ba8", "#f9e2af",
    "#89dceb", "#a6e3a1", "#fab387", "#cba6f7",
]


# ──────────────────────────────────────────────
# 헬퍼: 픽셀 치수 → dims dict (draw_shape 용)
# ──────────────────────────────────────────────
def dims_from_wh(shape_type: str, w_px: float, h_px: float) -> dict:
    if w_px <= 0:
        return {"w": 0, "h": 0}
    if shape_type == "원":
        r = w_px / 2
        return {"r": r, "w": w_px, "h": w_px}
    elif shape_type == "정사각형":
        return {"s": w_px, "w": w_px, "h": w_px}
    elif shape_type == "직사각형":
        return {"w": w_px, "h": h_px}
    elif shape_type == "정삼각형":
        h = w_px * math.sqrt(3) / 2
        return {"a": w_px, "w": w_px, "h": h}
    elif shape_type == "타원":
        rx, ry = w_px / 2, h_px / 2
        return {"rx": rx, "ry": ry, "w": w_px, "h": h_px}
    elif shape_type == "정육각형":
        a = w_px / 2
        h = w_px * math.sqrt(3) / 2
        return {"a": a, "w": w_px, "h": h}
    return {"w": w_px, "h": h_px}


# ──────────────────────────────────────────────
# 헬퍼: 점이 도형 내부인지 확인
# ──────────────────────────────────────────────
def _ray_cast(pts, px, py):
    """Ray casting: 점 (px,py)가 다각형 pts 안에 있는지"""
    inside = False
    n = len(pts)
    j = n - 1
    for i in range(n):
        xi, yi = pts[i]
        xj, yj = pts[j]
        if ((yi > py) != (yj > py)) and (px < (xj - xi) * (py - yi) / (yj - yi) + xi):
            inside = not inside
        j = i
    return inside


def point_in_shape(shape_type: str, cx: float, cy: float,
                   w_px: float, h_px: float, px: float, py: float) -> bool:
    dx, dy = px - cx, py - cy
    if shape_type == "원":
        r = w_px / 2
        return dx * dx + dy * dy <= r * r
    elif shape_type == "정사각형":
        h = w_px / 2
        return abs(dx) <= h and abs(dy) <= h
    elif shape_type == "직사각형":
        return abs(dx) <= w_px / 2 and abs(dy) <= h_px / 2
    elif shape_type == "정삼각형":
        a = w_px
        h = a * math.sqrt(3) / 2
        pts = [(0, -h * 2 / 3), (-a / 2, h / 3), (a / 2, h / 3)]
        return _ray_cast(pts, dx, dy)
    elif shape_type == "타원":
        rx, ry = w_px / 2, h_px / 2
        if rx <= 0 or ry <= 0:
            return False
        return (dx / rx) ** 2 + (dy / ry) ** 2 <= 1
    elif shape_type == "정육각형":
        a = w_px / 2
        pts = [(a * math.cos(math.pi / 6 + i * math.pi / 3),
                a * math.sin(math.pi / 6 + i * math.pi / 3)) for i in range(6)]
        return _ray_cast(pts, dx, dy)
    return False


# ──────────────────────────────────────────────
# 헬퍼: Monte Carlo 가시 면적 추정
# ──────────────────────────────────────────────
def compute_visible_areas(shapes, canvas_w: float, canvas_h: float,
                          n_samples: int = 8000):
    """
    Monte Carlo로 두 가지 면적을 동시 추정 (샘플 좌표는 항상 캔버스 내부).

    visible  : 캔버스 내에서 실제로 보이는 면적 (겹침 제외 + 캔버스 경계 클리핑)
    clipped  : 캔버스 내 총 면적 (겹침 포함,   캔버스 경계 클리핑만 적용)

    z-order: shapes 리스트 뒤쪽이 최상단.
    반환: (visible_dict, clipped_dict)  ← 각각 {uid: 면적(px²)}
    """
    vis_cnt  = {s.uid: 0 for s in shapes}
    clip_cnt = {s.uid: 0 for s in shapes}
    for _ in range(n_samples):
        x = random.random() * canvas_w
        y = random.random() * canvas_h
        top_found = False
        for s in reversed(shapes):        # 위(나중 그려진) 도형부터
            scx = s.cx_ratio * canvas_w
            scy = s.cy_ratio * canvas_h
            if point_in_shape(s.shape_type, scx, scy, s.w_px, s.h_px, x, y):
                clip_cnt[s.uid] += 1      # 겹침 관계없이 캔버스 내 면적
                if not top_found:
                    vis_cnt[s.uid] += 1   # 최상단 도형만 가시 면적으로 인정
                    top_found = True
                # break 하지 않음 → 아래 도형들의 clipped 면적도 계속 누적
    canvas_area = canvas_w * canvas_h
    visible = {uid: cnt / n_samples * canvas_area for uid, cnt in vis_cnt.items()}
    clipped = {uid: cnt / n_samples * canvas_area for uid, cnt in clip_cnt.items()}
    return visible, clipped


# ──────────────────────────────────────────────
# 헬퍼: 픽셀 치수 → 면적 (px²)
# ──────────────────────────────────────────────
def shape_area(shape_type: str, w_px: float, h_px: float) -> float:
    if w_px <= 0:
        return 0.0
    if shape_type == "원":
        return math.pi * (w_px / 2) ** 2
    elif shape_type == "정사각형":
        return w_px * w_px
    elif shape_type == "직사각형":
        return w_px * (h_px if h_px > 0 else w_px)
    elif shape_type == "정삼각형":
        return (math.sqrt(3) / 4) * w_px * w_px
    elif shape_type == "타원":
        return math.pi * (w_px / 2) * (h_px / 2) if h_px > 0 else math.pi * (w_px / 2) ** 2
    elif shape_type == "정육각형":
        a = w_px / 2
        return (3 * math.sqrt(3) / 2) * a * a
    return 0.0


# ──────────────────────────────────────────────
# 헬퍼: 목표 면적에서 w_px 역산 (h/w 비율 유지)
# ──────────────────────────────────────────────
def w_from_area(shape_type: str, target_area: float, hw_ratio: float = 1.0) -> float:
    """target_area(px²)와 h/w 비율로부터 w_px를 계산"""
    if target_area <= 0:
        return 0.0
    if shape_type == "원":
        return 2 * math.sqrt(target_area / math.pi)
    elif shape_type == "정사각형":
        return math.sqrt(target_area)
    elif shape_type == "직사각형":
        # area = w * h = w * (hw_ratio * w)  →  w = √(area/hw_ratio)
        return math.sqrt(target_area / hw_ratio) if hw_ratio > 0 else math.sqrt(target_area)
    elif shape_type == "정삼각형":
        return math.sqrt(4 * target_area / math.sqrt(3))
    elif shape_type == "타원":
        # area = π*(w/2)*(h/2) = π*(w/2)*(hw_ratio*w/2)  →  w = 2*√(area/(π*hw_ratio))
        return 2 * math.sqrt(target_area / (math.pi * hw_ratio)) if hw_ratio > 0 else 2 * math.sqrt(target_area / math.pi)
    elif shape_type == "정육각형":
        # area = (3√3/2)*(w/2)²  →  w = 2*√(2*area/(3√3))
        return 2 * math.sqrt(2 * target_area / (3 * math.sqrt(3)))
    return math.sqrt(target_area)


# ──────────────────────────────────────────────
# 도형 그리기
# ──────────────────────────────────────────────
def draw_shape(canvas: tk.Canvas, shape_type: str, cx: float, cy: float,
               dims: dict, fill: str, outline: str = "", width: int = 1, tags=()):
    if shape_type == "원":
        r = dims.get("r", 0)
        return canvas.create_oval(cx - r, cy - r, cx + r, cy + r,
                                  fill=fill, outline=outline, width=width, tags=tags)
    elif shape_type == "정사각형":
        s = dims.get("s", 0) / 2
        return canvas.create_rectangle(cx - s, cy - s, cx + s, cy + s,
                                       fill=fill, outline=outline, width=width, tags=tags)
    elif shape_type == "직사각형":
        hw = dims.get("w", 0) / 2
        hh = dims.get("h", 0) / 2
        return canvas.create_rectangle(cx - hw, cy - hh, cx + hw, cy + hh,
                                       fill=fill, outline=outline, width=width, tags=tags)
    elif shape_type == "정삼각형":
        a = dims.get("a", 0)
        h = dims.get("h", 0)
        y_top = cy - h * 2 / 3
        y_bot = cy + h / 3
        pts = [cx, y_top, cx - a / 2, y_bot, cx + a / 2, y_bot]
        return canvas.create_polygon(pts, fill=fill, outline=outline, width=width, tags=tags)
    elif shape_type == "타원":
        rx = dims.get("rx", 0)
        ry = dims.get("ry", 0)
        return canvas.create_oval(cx - rx, cy - ry, cx + rx, cy + ry,
                                  fill=fill, outline=outline, width=width, tags=tags)
    elif shape_type == "정육각형":
        a = dims.get("a", 0)
        pts = []
        for i in range(6):
            angle = math.pi / 6 + i * math.pi / 3
            pts += [cx + a * math.cos(angle), cy + a * math.sin(angle)]
        return canvas.create_polygon(pts, fill=fill, outline=outline, width=width, tags=tags)
    return None


# ──────────────────────────────────────────────
# 도형 데이터 클래스
# ──────────────────────────────────────────────
class Shape:
    _id_counter = 0

    def __init__(self, shape_type="원", w_px=100.0, h_px=100.0,
                 color="#7c6af7", cx_ratio=0.5, cy_ratio=0.5, label=""):
        Shape._id_counter += 1
        self.uid = Shape._id_counter
        self.shape_type = shape_type
        self.w_px = w_px          # 가로 픽셀 (주 치수)
        self.h_px = h_px          # 세로 픽셀 (직사각형·타원만 독립)
        self.color = color
        self.cx_ratio = cx_ratio  # 0~1 (캔버스 너비 대비 중심)
        self.cy_ratio = cy_ratio  # 0~1 (캔버스 높이 대비 중심)
        self.label = label or shape_type
        self.canvas_id = None
        self.locked = False


# ──────────────────────────────────────────────
# 줄자 데이터 클래스
# ──────────────────────────────────────────────
class Ruler:
    """캔버스 위에 표시되는 줄자 (캔버스 픽셀 좌표 기준)"""
    _id_counter = 0

    _default_colors = ["#f9e2af", "#89dceb", "#a6e3a1", "#fab387",
                       "#f38ba8", "#cba6f7", "#56cfb2", "#7c6af7"]

    def __init__(self, x1: float = 0, y1: float = 0,
                 x2: float = 100, y2: float = 100, color: str = ""):
        Ruler._id_counter += 1
        self.uid = Ruler._id_counter
        self.x1, self.y1 = float(x1), float(y1)
        self.x2, self.y2 = float(x2), float(y2)
        idx = (self.uid - 1) % len(Ruler._default_colors)
        self.color = color or Ruler._default_colors[idx]


# ──────────────────────────────────────────────
# 도형 추가/편집 다이얼로그
# ──────────────────────────────────────────────
class ShapeDialog:
    def __init__(self, parent, initial: Shape = None, unit: str = "px", dpi: float = 96.0):
        self.result: Shape = None
        self._color  = initial.color if initial else DEFAULT_COLORS[0]
        self._unit   = unit
        self._dpi    = dpi

        dlg = tk.Toplevel(parent)
        dlg.title("도형 편집" if initial else "도형 추가")
        dlg.configure(bg=C["panel"])
        dlg.resizable(False, False)
        dlg.grab_set()
        self._dlg = dlg

        pad = {"padx": 8, "pady": 4}

        # ── 도형 유형
        ttk.Label(dlg, text="도형 유형", background=C["panel"],
                  foreground=C["fg2"]).grid(row=0, column=0, sticky="w", **pad)
        self._type_var = tk.StringVar(value=initial.shape_type if initial else "원")
        type_cb = ttk.Combobox(dlg, textvariable=self._type_var,
                               values=SHAPE_TYPES, state="readonly", width=14)
        type_cb.grid(row=0, column=1, sticky="ew", **pad)
        type_cb.bind("<<ComboboxSelected>>", self._on_type_change)

        # ── 이름(레이블)
        ttk.Label(dlg, text="이름", background=C["panel"],
                  foreground=C["fg2"]).grid(row=1, column=0, sticky="w", **pad)
        self._label_var = tk.StringVar(value=initial.label if initial else "")
        ttk.Entry(dlg, textvariable=self._label_var, width=16).grid(
            row=1, column=1, sticky="ew", **pad)

        # ── 가로 / 세로
        sfx = unit
        def _disp(v_px):
            v = v_px * 25.4 / dpi if unit == "mm" else v_px
            return f"{v:.2f}" if unit == "mm" else f"{v:.1f}"

        ttk.Label(dlg, text=f"가로 ({sfx})", background=C["panel"],
                  foreground=C["fg2"]).grid(row=2, column=0, sticky="w", **pad)
        self._w_var = tk.StringVar(value=_disp(initial.w_px) if initial else "100")
        self._w_entry = ttk.Entry(dlg, textvariable=self._w_var, width=12)
        self._w_entry.grid(row=2, column=1, sticky="w", **pad)
        self._w_preview = tk.Label(dlg, text="", bg=C["panel"],
                                   fg=C["accent2"], font=("Consolas", 9))
        self._w_preview.grid(row=2, column=2, sticky="w", padx=(0, 6))

        # ── 세로 — 직사각형·타원만 활성
        self._h_lbl = ttk.Label(dlg, text=f"세로 ({sfx})", background=C["panel"],
                                 foreground=C["fg2"])
        self._h_lbl.grid(row=3, column=0, sticky="w", **pad)
        self._h_var = tk.StringVar(value=_disp(initial.h_px) if initial else "100")
        self._h_entry = ttk.Entry(dlg, textvariable=self._h_var, width=12)
        self._h_entry.grid(row=3, column=1, sticky="w", **pad)
        self._h_preview = tk.Label(dlg, text="", bg=C["panel"],
                                   fg=C["accent2"], font=("Consolas", 9))
        self._h_preview.grid(row=3, column=2, sticky="w", padx=(0, 6))

        # 수식 힌트
        tk.Label(dlg, text="수식 가능: 100+50, 300/3, sqrt(200)",
                 bg=C["panel"], fg=C["fg3"], font=("맑은 고딕", 8)
                 ).grid(row=4, column=0, columnspan=3, sticky="w", padx=8, pady=(0, 4))

        # 수식 바인딩
        for var, entry, preview in [
            (self._w_var, self._w_entry, self._w_preview),
            (self._h_var, self._h_entry, self._h_preview),
        ]:
            var.trace_add("write",
                lambda *_, v=var, p=preview: self._preview_expr(v, p))
            entry.bind("<Return>",   lambda e, v=var, p=preview: self._eval_expr(v, p))
            entry.bind("<FocusOut>", lambda e, v=var, p=preview: self._eval_expr(v, p))

        # ── 색상
        ttk.Label(dlg, text="색상", background=C["panel"],
                  foreground=C["fg2"]).grid(row=5, column=0, sticky="w", **pad)
        color_row = tk.Frame(dlg, bg=C["panel"])
        color_row.grid(row=5, column=1, sticky="w", **pad)
        self._color_patch = tk.Label(color_row, bg=self._color, width=4,
                                     relief="solid", cursor="hand2")
        self._color_patch.pack(side="left", padx=(0, 6))
        self._hex_var = tk.StringVar(value=self._color)
        self._hex_entry = ttk.Entry(color_row, textvariable=self._hex_var,
                                    width=10, font=("Consolas", 10))
        self._hex_entry.pack(side="left")
        self._hex_entry.bind("<Return>",   self._apply_hex)
        self._hex_entry.bind("<FocusOut>", self._apply_hex)
        self._hex_var.trace_add("write", self._on_hex_type)
        self._color_patch.bind("<Button-1>", self._pick_color)

        # ── 확인 / 취소
        btn_row = tk.Frame(dlg, bg=C["panel"])
        btn_row.grid(row=6, column=0, columnspan=3, pady=10)
        ttk.Button(btn_row, text="확인", command=lambda: self._ok(dlg)).pack(side="left", padx=6)
        ttk.Button(btn_row, text="취소", command=dlg.destroy).pack(side="left", padx=6)

        self._on_type_change()
        dlg.wait_window()

    def _on_type_change(self, *_):
        t = self._type_var.get()
        state = "normal" if t in DUAL_DIM_TYPES else "disabled"
        self._h_entry.config(state=state)

    # ── 인라인 수식 계산 ──────────────────────
    @staticmethod
    def _safe_eval(expr: str):
        """수식 문자열을 안전하게 계산. 실패하면 None 반환."""
        import math as _m
        _allowed = {k: getattr(_m, k) for k in dir(_m) if not k.startswith("_")}
        try:
            result = eval(expr.strip(), {"__builtins__": {}}, _allowed)
            return float(result)
        except Exception:
            return None

    def _preview_expr(self, var: tk.StringVar, preview_lbl: tk.Label):
        """입력 중 실시간 미리보기 — 수식이면 결과 표시, 단순 숫자면 숨김."""
        expr = var.get()
        # 연산자가 없으면 미리보기 숨김
        if not any(op in expr for op in ("+", "-", "*", "/", "(", "sqrt", "pi")):
            preview_lbl.config(text="")
            return
        result = self._safe_eval(expr)
        if result is not None and result > 0:
            preview_lbl.config(text=f"= {result:.2f}", fg=C["accent2"])
        else:
            preview_lbl.config(text="오류", fg=C["red"])

    def _eval_expr(self, var: tk.StringVar, preview_lbl: tk.Label):
        """Enter/FocusOut 시 수식을 계산해 결과값으로 치환."""
        expr = var.get()
        result = self._safe_eval(expr)
        if result is not None and result > 0:
            var.set(f"{result:.4g}")
            preview_lbl.config(text="")

    def _pick_color(self, *_):
        c = colorchooser.askcolor(color=self._color, title="색상 선택", parent=self._dlg)
        if c and c[1]:
            self._color = c[1].upper()
            self._hex_var.set(self._color)
            self._color_patch.config(bg=self._color)

    def _on_hex_type(self, *_):
        """입력 중 실시간으로 패치 미리보기."""
        val = self._hex_var.get().strip()
        if not val.startswith("#"):
            val = "#" + val
        try:
            self._color_patch.winfo_rgb(val)  # 유효성 검사
            self._color_patch.config(bg=val)
        except Exception:
            pass  # 잘못된 HEX는 무시

    def _apply_hex(self, *_):
        """Enter / FocusOut 시 최종 적용."""
        val = self._hex_var.get().strip()
        if not val.startswith("#"):
            val = "#" + val
        # 3자리 → 6자리 확장
        if len(val) == 4:
            val = "#" + "".join(c * 2 for c in val[1:])
        try:
            self._color_patch.winfo_rgb(val)
            self._color = val.upper()
            self._hex_var.set(self._color)
            self._color_patch.config(bg=self._color)
        except Exception:
            # 잘못된 값이면 이전 색으로 복구
            self._hex_var.set(self._color)
            self._color_patch.config(bg=self._color)

    def _ok(self, dlg):
        if not self._label_var.get().strip():
            messagebox.showwarning("알림", "이름을 추가하세요.", parent=dlg)
            return
        w_val = self._safe_eval(self._w_var.get())
        h_val = self._safe_eval(self._h_var.get())
        if w_val is None or h_val is None:
            messagebox.showerror("오류", "숫자 또는 수식을 올바르게 입력하세요.", parent=dlg)
            return
        if w_val <= 0 or h_val <= 0:
            messagebox.showerror("오류", "크기는 0보다 커야 합니다.", parent=dlg)
            return

        # 단위 → px 변환
        if self._unit == "mm":
            w = w_val * self._dpi / 25.4
            h = h_val * self._dpi / 25.4
        else:
            w, h = w_val, h_val

        t = self._type_var.get()
        if t not in DUAL_DIM_TYPES:
            h = w

        s = Shape(
            shape_type=t,
            w_px=w,
            h_px=h,
            color=self._color,
            label=self._label_var.get().strip(),
        )
        self.result = s
        dlg.destroy()


# ──────────────────────────────────────────────
# 메인 애플리케이션
# ──────────────────────────────────────────────
class AreaLayoutApp:
    CANVAS_W = 480
    CANVAS_H = 360

    def __init__(self, root: tk.Tk):
        self.root = root
        root.title("면적 균등 배치")
        root.configure(bg=C["bg"])
        root.minsize(920, 560)

        self.shapes: list[Shape] = []
        self._sel_idx: int = -1
        self._drag_uid: int = -1
        self._drag_ox = self._drag_oy = 0
        self._updating = False
        self._unit = "px"   # "px" 또는 "mm"
        self._dpi  = 96.0
        self._vis_job = None   # 가시 면적 계산 디바운스 job id
        self._undo_stack = []           # undo 스택 (최대 50)
        self._dirty = False             # 미저장 변경사항 여부
        self._current_file = None       # 현재 열린 파일 경로
        self._tree_drag_src = -1        # treeview 드래그 소스 인덱스
        self._tree_drag_moved = False   # 드래그 중 실제 이동 발생 여부
        self.rulers: list = []              # Ruler 객체 목록
        self._sel_ruler_idx: int = -1       # 선택된 줄자 인덱스
        self._ruler_mode: bool = False      # 줄자 표시/상호작용 모드
        self._ruler_drawing: bool = False   # 새 줄자 그리기 진행 중
        self._ruler_drag_state = None       # None | {'uid', 'part':'p1'/'p2'}
        self._ruler_items: list = []        # 캔버스 줄자 아이템 IDs
        self._zoom: float = 1.0             # 미리보기 줌 배율
        self._grid_on: bool = True          # 격자 표시 여부
        self._grid_cols: int = 12           # 격자 열 수
        self._grid_rows: int = 12           # 격자 행 수

        self._apply_styles()
        self._build_ui()
        root.bind("<Control-z>", self._undo)
        root.bind("<Control-Z>", self._undo)
        for _key in ("<Left>", "<Right>", "<Up>", "<Down>",
                     "<Shift-Left>", "<Shift-Right>",
                     "<Shift-Up>", "<Shift-Down>"):
            root.bind(_key, self._on_arrow_key)
        self._redraw()

    # ── 스타일 ────────────────────────────────
    def _apply_styles(self):
        s = ttk.Style()
        s.theme_use("clam")
        bg, fg, bd = C["panel"], C["fg"], C["border"]
        s.configure("TFrame", background=bg)
        s.configure("TLabel", background=bg, foreground=fg)
        s.configure("TLabelframe", background=bg, foreground=fg, bordercolor=bd)
        s.configure("TLabelframe.Label", background=bg, foreground=C["accent"])
        s.configure("TButton", background=C["card"], foreground=fg,
                    bordercolor=bd, focuscolor=C["accent"], padding=(6, 3))
        s.map("TButton",
              background=[("active", C["accent"]), ("pressed", C["accent2"])],
              foreground=[("active", C["bg"])])
        s.configure("Accent.TButton", background=C["card"], foreground=fg,
                    bordercolor=bd, focuscolor=C["accent"], padding=(6, 3))
        s.map("Accent.TButton",
              background=[("active", C["accent"]), ("pressed", C["accent2"])],
              foreground=[("active", C["bg"])])
        s.configure("TCombobox", fieldbackground=C["bg"], background=C["bg"],
                    foreground=fg, arrowcolor=fg,
                    selectbackground=C["accent"], selectforeground=fg)
        s.map("TCombobox",
              fieldbackground=[("readonly", C["bg"]),
                               ("disabled", C["panel"]),
                               ("focus",    C["card"]),
                               ("active",   C["card"])],
              background=    [("readonly", C["bg"]),
                               ("disabled", C["panel"]),
                               ("active",   C["card"])],
              foreground=    [("disabled", C["fg3"]),
                               ("readonly", fg)],
              arrowcolor=    [("disabled", C["fg3"])])
        s.configure("TEntry", fieldbackground=C["card"], foreground=fg,
                    insertcolor=fg, bordercolor=bd,
                    selectbackground=C["accent"], selectforeground=fg)
        s.map("TEntry",
              fieldbackground=[("disabled", C["panel"]),
                               ("readonly", C["bg"]),
                               ("focus",    C["card"])],
              foreground=    [("disabled", C["fg3"])],
              bordercolor=   [("focus",    C["accent"])])
        s.configure("TScrollbar", background=C["card"], troughcolor=C["bg"],
                    bordercolor=C["bg"], arrowcolor=fg)
        s.configure("Treeview", background=C["card"], foreground=fg,
                    fieldbackground=C["card"], bordercolor=bd, rowheight=24)
        s.configure("Treeview.Heading", background=C["panel"],
                    foreground=C["accent2"], bordercolor=bd)
        s.map("Treeview", background=[("selected", C["accent"])],
              foreground=[("selected", C["fg"])])
        s.configure("TScale", background=bg, troughcolor=C["card"],
                    sliderthickness=14, sliderrelief="flat")
        # Combobox 드롭다운 팝업 목록 색 (option_add로만 변경 가능)
        self.root.option_add("*TCombobox*Listbox.background", C["bg"])
        self.root.option_add("*TCombobox*Listbox.foreground", fg)
        self.root.option_add("*TCombobox*Listbox.selectBackground", C["accent"])
        self.root.option_add("*TCombobox*Listbox.selectForeground", C["fg"])
        # 일반 tk.Entry / Spinbox 흰색 배경 제거
        self.root.option_add("*Entry.background",       C["card"])
        self.root.option_add("*Entry.foreground",       fg)
        self.root.option_add("*Entry.insertBackground", fg)
        self.root.option_add("*Entry.selectBackground", C["accent"])
        self.root.option_add("*Entry.selectForeground", fg)
        self.root.option_add("*Entry.relief",           "flat")
        self.root.option_add("*Spinbox.background",     C["card"])
        self.root.option_add("*Spinbox.foreground",     fg)
        self.root.option_add("*Spinbox.relief",         "flat")

    # ── UI 빌드 ───────────────────────────────
    def _build_ui(self):
        root = self.root

        # 상단 툴바
        tb = tk.Frame(root, bg=C["panel"], height=40)
        tb.pack(fill="x", side="top")
        tk.Label(tb, text="  면적 균등 배치", bg=C["panel"], fg=C["fg"],
                 font=("맑은 고딕", 12, "bold")).pack(side="left", padx=8, pady=6)
        ttk.Button(tb, text="도형 추가", style="Accent.TButton",
                   command=self._add_shape).pack(side="left", padx=4, pady=6)

        tk.Label(tb, text="캔버스:", bg=C["panel"], fg=C["fg2"]).pack(side="left", padx=(16, 2))
        self._cv_w_var = tk.StringVar(value=str(self.CANVAS_W))
        self._cv_h_var = tk.StringVar(value=str(self.CANVAS_H))
        ttk.Entry(tb, textvariable=self._cv_w_var, width=6).pack(side="left")
        tk.Label(tb, text="×", bg=C["panel"], fg=C["fg2"]).pack(side="left", padx=2)
        ttk.Entry(tb, textvariable=self._cv_h_var, width=6).pack(side="left")
        ttk.Button(tb, text="적용", command=self._apply_canvas_size).pack(side="left", padx=4)

        # 단위 선택
        tk.Label(tb, text="단위:", bg=C["panel"], fg=C["accent2"]).pack(side="left", padx=(16, 2))
        self._unit_var = tk.StringVar(value="px")
        unit_cb = ttk.Combobox(tb, textvariable=self._unit_var,
                               values=["px", "mm"], state="readonly", width=4)
        unit_cb.pack(side="left")
        unit_cb.bind("<<ComboboxSelected>>", self._on_unit_change)

        tk.Label(tb, text="DPI:", bg=C["panel"], fg=C["fg2"]).pack(side="left", padx=(8, 2))
        self._dpi_var = tk.StringVar(value="96")
        self._dpi_entry = ttk.Entry(tb, textvariable=self._dpi_var, width=5, state="disabled")
        self._dpi_entry.pack(side="left")
        self._dpi_entry.bind("<Return>", self._on_unit_change)
        self._dpi_entry.bind("<FocusOut>", self._on_unit_change)

        # 파일 메뉴 버튼 (툴바 우측)
        tk.Frame(tb, bg=C["border"], width=1).pack(side="left", fill="y", padx=(16, 8), pady=4)
        file_menu = tk.Menu(
            tb, tearoff=0,
            bg=C["bg"], fg=C["fg"],
            activebackground=C["accent"], activeforeground=C["bg"],
            disabledforeground=C["fg3"],
            selectcolor=C["accent2"],
            relief="flat", borderwidth=1,
            font=("맑은 고딕", 10))
        file_menu.add_command(label="저장",          command=self._save_canvas)
        file_menu.add_command(label="불러오기",       command=self._load_canvas)
        file_menu.add_separator()
        file_menu.add_command(label="SVG 불러오기",  command=self._import_svg)
        file_menu.add_separator()
        file_menu.add_command(label="이름바꾸기",     command=self._rename_canvas)
        file_menu.add_command(label="삭제",          command=self._delete_canvas)
        file_menu.add_separator()
        file_menu.add_command(label="초기화",         command=self._reset_canvas)

        def _show_file_menu():
            w = file_btn.winfo_rootx()
            h = file_btn.winfo_rooty() + file_btn.winfo_height()
            file_menu.tk_popup(w, h)

        file_btn = ttk.Button(tb, text="파일 ▾", command=_show_file_menu)
        file_btn.pack(side="left", padx=2, pady=6)

        # 메인 영역
        main = tk.Frame(root, bg=C["bg"])
        main.pack(fill="both", expand=True, padx=8, pady=8)

        # 좌측 패널 (PanedWindow로 도형목록/줄자목록 1:1 분할)
        left = tk.Frame(main, bg=C["panel"])
        left.pack(side="left", fill="y", padx=(0, 6))

        self._paned_left = tk.PanedWindow(left, orient="vertical",
                                          bg=C["border"], sashwidth=5,
                                          sashrelief="flat", bd=0,
                                          handlesize=0)
        self._paned_left.pack(fill="both", expand=True)

        # ── 위쪽 칸: 도형 목록
        shape_pane = ttk.LabelFrame(self._paned_left, text="도형 목록", padding=4)
        self._paned_left.add(shape_pane, stretch="always", minsize=80)

        tree_frame = tk.Frame(shape_pane, bg=C["panel"])
        tree_frame.pack(fill="both", expand=True)

        cols = ("이름", "유형", "가로", "면적%", "잠금")
        self._tree = ttk.Treeview(tree_frame, columns=cols, show="headings",
                                  height=8, selectmode="browse")
        for col, w in zip(cols, (72, 60, 60, 52, 44)):
            self._tree.heading(col, text=col)
            self._tree.column(col, width=w, anchor="center")
        self._tree.pack(fill="both", expand=True, side="left")
        sb = ttk.Scrollbar(tree_frame, orient="vertical", command=self._tree.yview)
        sb.pack(side="left", fill="y")
        self._tree.configure(yscrollcommand=sb.set)
        self._tree.bind("<<TreeviewSelect>>", self._on_tree_select)
        self._tree.bind("<ButtonPress-1>", self._tree_press)
        self._tree.bind("<B1-Motion>", self._tree_motion)
        self._tree.bind("<ButtonRelease-1>", self._tree_release)

        # 편집/삭제 버튼 — 도형목록 바로 아래, 줄자목록 위
        shape_btn_row = tk.Frame(shape_pane, bg=C["panel"])
        shape_btn_row.pack(fill="x", pady=(4, 0))
        ttk.Button(shape_btn_row, text="편집", command=self._edit_shape).pack(
            side="left", expand=True, fill="x", padx=2)
        ttk.Button(shape_btn_row, text="복제", command=self._duplicate_shape).pack(
            side="left", expand=True, fill="x", padx=2)
        ttk.Button(shape_btn_row, text="삭제", command=self._del_shape).pack(
            side="left", expand=True, fill="x", padx=2)

        # ── 아래쪽 칸: 줄자 목록
        ruler_pane = ttk.LabelFrame(self._paned_left, text="줄자 목록", padding=4)
        self._paned_left.add(ruler_pane, stretch="always", minsize=80)

        ruler_cols = ("번호", "거리")
        self._ruler_tree = ttk.Treeview(ruler_pane, columns=ruler_cols,
                                        show="headings", height=4,
                                        selectmode="browse")
        for col, w in zip(ruler_cols, (36, 110)):
            self._ruler_tree.heading(col, text=col)
            self._ruler_tree.column(col, width=w, anchor="center")
        self._ruler_tree.pack(fill="both", expand=True)
        self._ruler_tree.bind("<<TreeviewSelect>>", self._on_ruler_select)

        ruler_btn_row = tk.Frame(ruler_pane, bg=C["panel"])
        ruler_btn_row.pack(fill="x", pady=(4, 0))
        self._ruler_add_btn = ttk.Button(ruler_btn_row, text="줄자 추가",
                                         command=self._start_add_ruler)
        self._ruler_add_btn.pack(side="left", expand=True, fill="x", padx=2)
        ttk.Button(ruler_btn_row, text="줄자 삭제",
                   command=self._del_ruler).pack(side="left", expand=True,
                                                 fill="x", padx=2)
        ttk.Button(ruler_btn_row, text="색상",
                   command=self._pick_ruler_color).pack(side="left", expand=True,
                                                        fill="x", padx=2)

        # 1:1 비율 초기 설정 (렌더링 후)
        self.root.after(80, self._equalize_left_panes)

        # 중앙: 캔버스 미리보기
        center = ttk.LabelFrame(main, text="미리보기", padding=6)
        center.pack(side="left", fill="both", expand=True, padx=(0, 6))

        # 스크롤 가능한 캔버스 컨테이너
        cv_outer = tk.Frame(center, bg=C["bg"])
        cv_outer.pack(fill="both", expand=True)
        cv_hscroll = ttk.Scrollbar(cv_outer, orient="horizontal")
        cv_hscroll.pack(side="bottom", fill="x")
        cv_vscroll = ttk.Scrollbar(cv_outer, orient="vertical")
        cv_vscroll.pack(side="right", fill="y")
        self._cv = tk.Canvas(cv_outer, bg=C["canvas_bg"],
                             width=self.CANVAS_W, height=self.CANVAS_H,
                             highlightthickness=1, highlightbackground=C["border"],
                             cursor="crosshair",
                             xscrollcommand=cv_hscroll.set,
                             yscrollcommand=cv_vscroll.set)
        self._cv.pack(expand=True)
        cv_hscroll.config(command=self._cv.xview)
        cv_vscroll.config(command=self._cv.yview)
        self._cv.bind("<ButtonPress-1>", self._on_press)
        self._cv.bind("<B1-Motion>", self._on_drag)
        self._cv.bind("<ButtonRelease-1>", self._on_release)
        # 스크롤 휠로 줌
        self._cv.bind("<Control-MouseWheel>", self._on_zoom_wheel)
        self._cv.bind("<Control-Button-4>", self._on_zoom_wheel)
        self._cv.bind("<Control-Button-5>", self._on_zoom_wheel)

        # 하단 1행: 센터맞춤, 줄자, 거리
        cv_btns = tk.Frame(center, bg=C["panel"])
        cv_btns.pack(fill="x", pady=(4, 0))
        ttk.Button(cv_btns, text="센터 맞춤",
                   command=self._center_shape).pack(side="left", padx=4, pady=3)
        self._ruler_btn = ttk.Button(cv_btns, text="줄자 ON",
                                     command=self._toggle_ruler)
        self._ruler_btn.pack(side="left", padx=4, pady=3)
        self._ruler_lbl = tk.Label(cv_btns, text="", bg=C["panel"],
                                   fg=C["yellow"], font=("Consolas", 10))
        self._ruler_lbl.pack(side="left", padx=6)

        # 하단 2행: 격자 + 줌
        cv_btns2 = tk.Frame(center, bg=C["panel"])
        cv_btns2.pack(fill="x")
        self._grid_btn = ttk.Button(cv_btns2, text="격자 ON",
                                    style="Accent.TButton",
                                    command=self._toggle_grid)
        self._grid_btn.pack(side="left", padx=4, pady=3)
        tk.Label(cv_btns2, text="열×행:", bg=C["panel"],
                 fg=C["fg2"]).pack(side="left", padx=(6, 2))
        self._grid_cols_var = tk.StringVar(value="12")
        ttk.Entry(cv_btns2, textvariable=self._grid_cols_var,
                  width=3).pack(side="left")
        tk.Label(cv_btns2, text="×", bg=C["panel"],
                 fg=C["fg2"]).pack(side="left", padx=2)
        self._grid_rows_var = tk.StringVar(value="12")
        ttk.Entry(cv_btns2, textvariable=self._grid_rows_var,
                  width=3).pack(side="left")
        ttk.Button(cv_btns2, text="적용",
                   command=self._apply_grid_settings).pack(side="left", padx=4)

        tk.Label(cv_btns2, text="줌:", bg=C["panel"],
                 fg=C["fg2"]).pack(side="left", padx=(12, 2))
        ttk.Button(cv_btns2, text="−",
                   command=self._zoom_out).pack(side="left", padx=2, pady=3)
        self._zoom_lbl = tk.Label(cv_btns2, text="100%", bg=C["panel"],
                                  fg=C["fg"], font=("Consolas", 10), width=5)
        self._zoom_lbl.pack(side="left")
        ttk.Button(cv_btns2, text="+",
                   command=self._zoom_in).pack(side="left", padx=2, pady=3)
        ttk.Button(cv_btns2, text="1:1",
                   command=self._zoom_reset).pack(side="left", padx=4)

        # 우측: 선택 도형 정보
        right = ttk.LabelFrame(main, text="선택 도형 정보", padding=10)
        right.pack(side="left", fill="y")

        def _lbl(row, text):
            tk.Label(right, text=text + ":", bg=C["panel"], fg=C["fg2"],
                     font=("맑은 고딕", 9)).grid(row=row, column=0, sticky="w", pady=2)

        def _val_lbl(row, key):
            lbl = tk.Label(right, text="—", bg=C["panel"], fg=C["fg"],
                           font=("Consolas", 10), width=12, anchor="w")
            lbl.grid(row=row, column=1, sticky="w", padx=(4, 0))
            return lbl

        self._info: dict = {}
        self._info_row_lbls: dict = {}  # 단위 변경 시 텍스트를 갱신할 행 레이블

        # 읽기 전용 필드
        static_fields = [("이름", "label"), ("유형", "shape_type"),
                         ("가로 (px)", "w"), ("세로 (px)", "h"),
                         ("비율 (W:H)", "ratio"),
                         ("면적 %", "pct"), ("가시 면적 %", "vis_pct"),
                         ("균등 대비", "eq_ratio"), ("색상", "color")]
        for i, (txt, key) in enumerate(static_fields):
            lbl_w = tk.Label(right, text=txt + ":", bg=C["panel"], fg=C["fg2"],
                             font=("맑은 고딕", 9))
            lbl_w.grid(row=i, column=0, sticky="w", pady=2)
            if key in ("w", "h"):
                self._info_row_lbls[key] = lbl_w
            self._info[key] = _val_lbl(i, key)

        color_row_r = 8  # 색상 행 번호 (ratio 추가로 +1)
        self._info_patch = tk.Label(right, bg=C["panel"], width=3, height=1,
                                    relief="solid", bd=1)
        self._info_patch.grid(row=color_row_r, column=2, sticky="w", padx=4)

        # 편집 가능 필드: 중심 X / Y
        sep_row = 9  # static_fields 9개 → separator는 row 9
        ttk.Separator(right, orient="horizontal").grid(
            row=sep_row, column=0, columnspan=3, sticky="ew", pady=6)

        self._info_row_lbls["cx"] = tk.Label(right, text="중심 X (px):", bg=C["panel"],
                                              fg=C["fg2"], font=("맑은 고딕", 9))
        self._info_row_lbls["cx"].grid(row=sep_row + 1, column=0, sticky="w", pady=2)
        self._cx_var = tk.StringVar(value="—")
        self._cx_entry = ttk.Entry(right, textvariable=self._cx_var, width=10)
        self._cx_entry.grid(row=sep_row + 1, column=1, sticky="w", padx=(4, 0))
        self._cx_entry.bind("<Return>", self._apply_pos)
        self._cx_entry.bind("<FocusOut>", self._apply_pos)

        self._info_row_lbls["cy"] = tk.Label(right, text="중심 Y (px):", bg=C["panel"],
                                              fg=C["fg2"], font=("맑은 고딕", 9))
        self._info_row_lbls["cy"].grid(row=sep_row + 2, column=0, sticky="w", pady=2)
        self._cy_var = tk.StringVar(value="—")
        self._cy_entry = ttk.Entry(right, textvariable=self._cy_var, width=10)
        self._cy_entry.grid(row=sep_row + 2, column=1, sticky="w", padx=(4, 0))
        self._cy_entry.bind("<Return>", self._apply_pos)
        self._cy_entry.bind("<FocusOut>", self._apply_pos)

        # 크기 조절 슬라이더 (w_px)
        ttk.Separator(right, orient="horizontal").grid(
            row=sep_row + 3, column=0, columnspan=3, sticky="ew", pady=6)
        self._size_scale_lbl = tk.Label(right, text="크기 조절 (가로 px):", bg=C["panel"],
                                        fg=C["fg2"], font=("맑은 고딕", 9))
        self._size_scale_lbl.grid(row=sep_row + 4, column=0, columnspan=3, sticky="w")
        self._size_scale = ttk.Scale(right, from_=4, to=max(self.CANVAS_W, self.CANVAS_H),
                                     orient="horizontal", length=160,
                                     command=self._on_scale)
        self._size_scale.grid(row=sep_row + 5, column=0, columnspan=3, sticky="ew")
        # 정밀 입력 행: [−] [entry] [단위] [+]
        size_row = tk.Frame(right, bg=C["panel"])
        size_row.grid(row=sep_row + 6, column=0, columnspan=3, sticky="w", pady=(2, 0))
        ttk.Button(size_row, text="−", width=2,
                   command=lambda: self._step_size(-1)).pack(side="left", padx=(0, 2))
        self._size_var = tk.StringVar(value="—")
        self._size_entry = ttk.Entry(size_row, textvariable=self._size_var,
                                     width=8, font=("Consolas", 10))
        self._size_entry.pack(side="left")
        self._size_entry.bind("<Return>", self._apply_size)
        self._size_entry.bind("<FocusOut>", self._apply_size)
        self._size_unit_lbl = tk.Label(size_row, text="px", bg=C["panel"],
                                       fg=C["fg2"], font=("Consolas", 10))
        self._size_unit_lbl.pack(side="left", padx=(3, 4))
        ttk.Button(size_row, text="+", width=2,
                   command=lambda: self._step_size(1)).pack(side="left")

        # 전체 면적 합계
        ttk.Separator(right, orient="horizontal").grid(
            row=sep_row + 7, column=0, columnspan=3, sticky="ew", pady=6)
        tk.Label(right, text="전체 면적 합계:", bg=C["panel"], fg=C["fg2"],
                 font=("맑은 고딕", 9)).grid(row=sep_row + 8, column=0, columnspan=3,
                                             sticky="w")
        self._total_lbl = tk.Label(right, text="0.0 %", bg=C["panel"], fg=C["accent2"],
                                   font=("맑은 고딕", 11, "bold"))
        self._total_lbl.grid(row=sep_row + 9, column=0, columnspan=3, sticky="w")

    # ── 단위 변환 헬퍼 ────────────────────────
    def _to_px(self, v: float) -> float:
        """현재 단위 → px"""
        return v * self._dpi / 25.4 if self._unit == "mm" else v

    def _from_px(self, v: float) -> float:
        """px → 현재 단위"""
        return v * 25.4 / self._dpi if self._unit == "mm" else v

    def _fmt(self, v_px: float, dec: int = 2) -> str:
        return f"{self._from_px(v_px):.{dec}f}"

    def _unit_sfx(self) -> str:
        return self._unit

    def _on_unit_change(self, *_):
        u = self._unit_var.get()
        self._unit = u
        # DPI 읽기
        try:
            self._dpi = max(1.0, float(self._dpi_var.get()))
        except ValueError:
            self._dpi = 96.0
        # DPI 입력 활성/비활성
        self._dpi_entry.config(state="normal" if u == "mm" else "disabled")
        sfx = u
        # 정보 패널 레이블 갱신
        self._info_row_lbls["w"].config(text=f"가로 ({sfx}):")
        self._info_row_lbls["h"].config(text=f"세로 ({sfx}):")
        self._info_row_lbls["cx"].config(text=f"중심 X ({sfx}):")
        self._info_row_lbls["cy"].config(text=f"중심 Y ({sfx}):")
        self._size_scale_lbl.config(text=f"크기 조절 (가로 {sfx}):")
        self._size_unit_lbl.config(text=sfx)
        # 트리 헤더 갱신
        self._tree.heading("가로", text=f"가로({sfx})")
        # 캔버스 사이즈 입력란 갱신
        dec = 1 if u == "mm" else 0
        self._cv_w_var.set(f"{self._from_px(self.CANVAS_W):.{dec}f}")
        self._cv_h_var.set(f"{self._from_px(self.CANVAS_H):.{dec}f}")
        # 선택 도형 정보 갱신
        self._refresh_tree()
        self._refresh_ruler_tree()
        if 0 <= self._sel_idx < len(self.shapes):
            self._update_info(self.shapes[self._sel_idx])

    # ── 캔버스 크기 적용 ──────────────────────
    def _apply_canvas_size(self):
        try:
            w = self._to_px(float(self._cv_w_var.get()))
            h = self._to_px(float(self._cv_h_var.get()))
        except ValueError:
            messagebox.showerror("오류", "캔버스 크기를 올바르게 입력하세요.")
            return
        w = max(100, min(int(round(w)), 4000))
        h = max(100, min(int(round(h)), 4000))
        self.CANVAS_W = w
        self.CANVAS_H = h
        self._cv.config(width=w, height=h)
        self._size_scale.config(to=max(w, h))
        self._mark_dirty()
        self._redraw()

    # ── 도형 추가 / 편집 / 삭제 ───────────────
    def _add_shape(self):
        dlg = ShapeDialog(self.root, unit=self._unit, dpi=self._dpi)
        if dlg.result:
            self._save_undo()
            s = dlg.result
            if s.color == DEFAULT_COLORS[0] and self.shapes:
                s.color = DEFAULT_COLORS[len(self.shapes) % len(DEFAULT_COLORS)]
            s.cx_ratio = 0.5
            s.cy_ratio = 0.5
            self.shapes.append(s)
            self._redraw()

    def _edit_shape(self):
        idx = self._sel_idx
        if idx < 0 or idx >= len(self.shapes):
            return
        dlg = ShapeDialog(self.root, initial=self.shapes[idx], unit=self._unit, dpi=self._dpi)
        if dlg.result:
            self._save_undo()
            s = dlg.result
            orig = self.shapes[idx]
            orig.shape_type = s.shape_type
            orig.w_px = s.w_px
            orig.h_px = s.h_px
            orig.color = s.color
            orig.label = s.label
            self._redraw()
            self._update_info(orig)

    def _duplicate_shape(self):
        idx = self._sel_idx
        if idx < 0 or idx >= len(self.shapes):
            return
        self._save_undo()
        orig = self.shapes[idx]
        dup = copy.copy(orig)
        Shape._id_counter += 1
        dup.uid = Shape._id_counter
        dup.label = orig.label + "_copy"
        dup.canvas_id = None
        # 약간 오프셋해서 겹치지 않게 배치
        dup.cx_ratio = min(1.0, orig.cx_ratio + 0.03)
        dup.cy_ratio = min(1.0, orig.cy_ratio + 0.03)
        self.shapes.insert(idx + 1, dup)
        self._sel_idx = idx + 1
        self._redraw()
        self._update_info(dup)

    def _del_shape(self):
        idx = self._sel_idx
        if idx < 0 or idx >= len(self.shapes):
            return
        self._save_undo()
        self.shapes.pop(idx)
        self._sel_idx = -1
        self._redraw()
        self._clear_info()

    # ── Undo ──────────────────────────────────
    def _save_undo(self):
        """현재 shapes 상태를 undo 스택에 저장 (최대 50개)"""
        self._undo_stack.append(copy.deepcopy(self.shapes))
        if len(self._undo_stack) > 50:
            self._undo_stack.pop(0)
        self._mark_dirty()

    def _mark_dirty(self):
        self._dirty = True
        name = os.path.basename(self._current_file) if self._current_file else "새 파일"
        self.root.title(f"면적 균등 배치 — {name} *")

    def _clear_dirty(self):
        self._dirty = False
        name = os.path.basename(self._current_file) if self._current_file else "새 파일"
        self.root.title(f"면적 균등 배치 — {name}")

    def _undo(self, event=None):
        if not self._undo_stack:
            return
        self.shapes = self._undo_stack.pop()
        self._sel_idx = -1
        self._drag_uid = -1
        self._redraw()
        self._clear_info()

    # ── 균등 분배 ─────────────────────────────
    def _equalize(self):
        if not self.shapes:
            return
        total_area = sum(shape_area(s.shape_type, s.w_px, s.h_px) for s in self.shapes)
        target = total_area / len(self.shapes)
        for s in self.shapes:
            hw = s.h_px / s.w_px if s.w_px > 0 else 1.0
            new_w = w_from_area(s.shape_type, target, hw)
            new_h = new_w * hw if s.shape_type in DUAL_DIM_TYPES else new_w
            s.w_px = new_w
            s.h_px = new_h
        self._redraw()
        if 0 <= self._sel_idx < len(self.shapes):
            self._update_info(self.shapes[self._sel_idx])

    # ── 겹침 제외 균등 분배 ───────────────────
    def _equalize_visible(self):
        """
        겹치는 영역을 제외한 실제 가시 면적이 균등해지도록 도형 크기를 반복 조정.
        Monte Carlo 샘플링으로 각 도형의 가시 면적을 추정한 뒤,
        면적 비율의 제곱근으로 w_px을 스케일링 → 최대 12회 반복.
        """
        if len(self.shapes) < 2:
            self._equalize()
            return

        MAX_ITER = 12
        SAMPLES  = 8000
        TOL      = 0.02   # 오차 허용 2%

        for _ in range(MAX_ITER):
            visible, _ = compute_visible_areas(
                self.shapes, self.CANVAS_W, self.CANVAS_H, SAMPLES)
            total_v = sum(visible.values())
            if total_v <= 0:
                break
            target = total_v / len(self.shapes)

            converged = True
            for s in self.shapes:
                current = visible.get(s.uid, 0)
                if current <= 0:
                    # 완전히 가려진 도형은 조금 키워 줌
                    s.w_px *= 1.2
                    if s.shape_type in DUAL_DIM_TYPES:
                        s.h_px *= 1.2
                    converged = False
                    continue
                ratio = target / current
                if abs(ratio - 1.0) > TOL:
                    converged = False
                scale = math.sqrt(ratio)
                hw = s.h_px / s.w_px if s.w_px > 0 else 1.0
                s.w_px *= scale
                s.h_px = s.w_px * hw if s.shape_type in DUAL_DIM_TYPES else s.w_px
            if converged:
                break

        self._redraw()
        if 0 <= self._sel_idx < len(self.shapes):
            self._update_info(self.shapes[self._sel_idx])

    # ── 자동 격자 배치 ────────────────────────
    def _auto_layout(self):
        n = len(self.shapes)
        if n == 0:
            return
        cols = math.ceil(math.sqrt(n))
        rows = math.ceil(n / cols)
        for i, s in enumerate(self.shapes):
            s.cx_ratio = (i % cols + 0.5) / cols
            s.cy_ratio = (i // cols + 0.5) / rows
        self._redraw()

    # ── 캔버스 그리기 ─────────────────────────
    def _redraw(self):
        self._cv.delete("all")
        z = self._zoom
        cw, ch = self.CANVAS_W, self.CANVAS_H
        cw_z, ch_z = cw * z, ch * z

        # 캔버스 위젯 크기 및 스크롤 영역 갱신
        w_i, h_i = max(1, int(cw_z)), max(1, int(ch_z))
        self._cv.config(width=w_i, height=h_i,
                        scrollregion=(0, 0, w_i, h_i))

        # 도형 그리기 (줌 좌표 사용)
        canvas_area = cw * ch
        for s in self.shapes:
            dims = dims_from_wh(s.shape_type, s.w_px * z, s.h_px * z)
            cx_z = s.cx_ratio * cw_z
            cy_z = s.cy_ratio * ch_z
            tag = f"shape_{s.uid}"
            oid = draw_shape(self._cv, s.shape_type, cx_z, cy_z, dims,
                             fill=s.color, outline=C["fg2"], width=1, tags=(tag,))
            s.canvas_id = oid
            self._cv.create_text(cx_z, cy_z, text=s.label, fill=C["fg"],
                                 font=("맑은 고딕", 8), tags=(tag + "_lbl",))
            # 센터 포인트
            CP = 4
            self._cv.create_line(cx_z - CP, cy_z, cx_z + CP, cy_z,
                                 fill=C["accent2"], width=1, tags=(tag + "_cp",))
            self._cv.create_line(cx_z, cy_z - CP, cx_z, cy_z + CP,
                                 fill=C["accent2"], width=1, tags=(tag + "_cp",))
            self._cv.create_oval(cx_z - 2, cy_z - 2, cx_z + 2, cy_z + 2,
                                 fill=C["accent2"], outline="", tags=(tag + "_cp",))

        # 격자 — 도형 위에 그리기
        if self._grid_on:
            gc = max(1, self._grid_cols)
            gr = max(1, self._grid_rows)
            for i in range(gc + 1):
                x = i * cw_z / gc
                self._cv.create_line(x, 0, x, ch_z,
                                     fill=C["border"], width=1, tags=("grid",))
            for j in range(gr + 1):
                y = j * ch_z / gr
                self._cv.create_line(0, y, cw_z, y,
                                     fill=C["border"], width=1, tags=("grid",))

        # 합계 표시
        total_pct = sum(
            shape_area(s.shape_type, s.w_px, s.h_px) / canvas_area * 100
            for s in self.shapes
        ) if canvas_area > 0 else 0
        color = C["accent2"] if abs(total_pct - 100) < 0.5 else (
            C["yellow"] if total_pct < 100 else C["red"])
        self._total_lbl.config(text=f"{total_pct:.1f} %", fg=color)

        self._refresh_tree()
        # 줄자를 shapes+격자 위에 재그리기
        self._draw_all_rulers()

    # ── Treeview ──────────────────────────────
    def _refresh_tree(self):
        canvas_area = self.CANVAS_W * self.CANVAS_H
        for item in self._tree.get_children():
            self._tree.delete(item)
        dec = 1 if self._unit == "mm" else 0
        for i, s in enumerate(self.shapes):
            pct = shape_area(s.shape_type, s.w_px, s.h_px) / canvas_area * 100
            w_disp = self._from_px(s.w_px)
            self._tree.insert("", "end", iid=str(i),
                               values=(s.label, s.shape_type,
                                       f"{w_disp:.{dec}f}", f"{pct:.1f}%",
                                       "🔒" if s.locked else ""))
        if 0 <= self._sel_idx < len(self.shapes):
            self._updating = True
            self._tree.selection_set(str(self._sel_idx))
            self._updating = False

    # ── Treeview 드래그 재정렬 ────────────────
    def _tree_press(self, event):
        col = self._tree.identify_column(event.x)
        item = self._tree.identify_row(event.y)
        if item and col == "#5":  # 잠금 열 클릭 → 토글
            idx = int(item)
            if 0 <= idx < len(self.shapes):
                self.shapes[idx].locked = not self.shapes[idx].locked
                self._refresh_tree()
            self._tree_drag_src = -1
            return
        if item:
            self._tree_drag_src = int(item)
            self._tree_drag_moved = False
        else:
            self._tree_drag_src = -1

    def _tree_motion(self, event):
        if self._tree_drag_src < 0:
            return
        target = self._tree.identify_row(event.y)
        if not target:
            return
        dst = int(target)
        if dst == self._tree_drag_src:
            return
        if not self._tree_drag_moved:
            self._save_undo()
            self._tree_drag_moved = True
        src = self._tree_drag_src
        if 0 <= src < len(self.shapes) and 0 <= dst < len(self.shapes):
            self.shapes.insert(dst, self.shapes.pop(src))
            # 선택 인덱스 갱신
            if self._sel_idx == src:
                self._sel_idx = dst
            elif src < self._sel_idx <= dst:
                self._sel_idx -= 1
            elif dst <= self._sel_idx < src:
                self._sel_idx += 1
            self._tree_drag_src = dst
            self._redraw()

    def _tree_release(self, event):
        self._tree_drag_src = -1
        self._tree_drag_moved = False

    def _on_tree_select(self, *_):
        if self._updating:
            return
        sel = self._tree.selection()
        if not sel:
            return
        idx = int(sel[0])
        self._sel_idx = idx
        if 0 <= idx < len(self.shapes):
            s = self.shapes[idx]
            self._update_info(s)
            self._updating = True
            self._size_scale.set(s.w_px)
            self._updating = False

    # ── W:H 비율 문자열 ───────────────────────
    @staticmethod
    def _wh_ratio_str(w: float, h: float) -> str:
        if w <= 0 or h <= 0:
            return "—"
        # 소수점 1자리 정밀도로 정수화 후 GCD 약분
        wi = round(w * 10)
        hi = round(h * 10)
        g = math.gcd(wi, hi)
        rw, rh = wi // g, hi // g
        # 숫자가 너무 크면 소수 형태로
        if max(rw, rh) > 99:
            if w >= h:
                return f"{w / h:.2f} : 1"
            else:
                return f"1 : {h / w:.2f}"
        return f"{rw} : {rh}"

    # ── 정보 패널 ─────────────────────────────
    def _update_info(self, s: Shape):
        cw, ch = self.CANVAS_W, self.CANVAS_H
        canvas_area = cw * ch
        dims = dims_from_wh(s.shape_type, s.w_px, s.h_px)
        pct = shape_area(s.shape_type, s.w_px, s.h_px) / canvas_area * 100

        sfx = self._unit_sfx()
        dec = 2 if sfx == "mm" else 1
        self._info["label"].config(text=s.label[:14])
        self._info["shape_type"].config(text=s.shape_type)
        self._info["w"].config(text=f"{self._from_px(dims.get('w', 0)):.{dec}f} {sfx}")
        self._info["h"].config(text=f"{self._from_px(dims.get('h', 0)):.{dec}f} {sfx}")
        self._info["ratio"].config(text=self._wh_ratio_str(dims.get('w', 0), dims.get('h', 0)))
        self._info["pct"].config(text=f"{pct:.2f} %")
        self._info["color"].config(text=s.color)
        try:
            self._info_patch.config(bg=s.color)
        except Exception:
            pass
        # 중심 X/Y 입력란 업데이트 (포커스 없을 때만)
        if self.root.focus_get() not in (self._cx_entry, self._cy_entry):
            self._cx_var.set(f"{self._from_px(s.cx_ratio * cw):.{dec}f}")
            self._cy_var.set(f"{self._from_px(s.cy_ratio * ch):.{dec}f}")
        if self.root.focus_get() is not self._size_entry:
            self._size_var.set(f"{self._from_px(s.w_px):.{dec}f}")
        self._size_unit_lbl.config(text=sfx)
        # 가시 면적: 드래그 중이 아닐 때 300 ms 디바운스로 계산
        if self._vis_job is not None:
            self.root.after_cancel(self._vis_job)
        if self._drag_uid >= 0:
            # 드래그 중에는 표시 유지 (재계산 안 함)
            return
        self._info["vis_pct"].config(text="계산 중...", fg=C["fg3"])
        self._info["eq_ratio"].config(text="계산 중...", fg=C["fg3"])
        self._vis_job = self.root.after(300, lambda uid=s.uid: self._compute_vis_for(uid))

    def _compute_vis_for(self, uid: int):
        """
        Monte Carlo로 선택 도형의 면적을 계산해 정보 패널을 갱신.
          - 면적 %   : 캔버스 내 총 면적 (겹침 포함, 캔버스 밖 제외)
          - 가시 면적 %: 실제로 보이는 면적 (겹침 + 캔버스 경계 모두 제외)
        """
        self._vis_job = None
        if not (0 <= self._sel_idx < len(self.shapes)):
            return
        if self.shapes[self._sel_idx].uid != uid:
            return
        visible, clipped = compute_visible_areas(
            self.shapes, self.CANVAS_W, self.CANVAS_H, n_samples=4000)
        canvas_area = self.CANVAS_W * self.CANVAS_H
        if canvas_area <= 0:
            return
        clip_pct = clipped.get(uid, 0) / canvas_area * 100
        vis_pct  = visible.get(uid, 0)  / canvas_area * 100
        # 면적 % → 캔버스-클리핑된 값으로 덮어쓰기
        self._info["pct"].config(text=f"{clip_pct:.2f} %")
        self._info["vis_pct"].config(
            text=f"{vis_pct:.2f} %",
            fg=C["accent2"] if vis_pct > 0 else C["red"])
        n = len(self.shapes)
        if n > 0 and vis_pct > 0:
            eq_pct = 100.0 / n
            ratio = vis_pct / eq_pct
            color = (C["accent2"] if abs(ratio - 1.0) < 0.1
                     else C["yellow"] if ratio < 1.0 else C["red"])
            self._info["eq_ratio"].config(
                text=f"×{ratio:.2f}  (균등 {eq_pct:.1f}%)",
                fg=color)
        else:
            self._info["eq_ratio"].config(text="—", fg=C["fg"])

    def _clear_info(self):
        if self._vis_job is not None:
            self.root.after_cancel(self._vis_job)
            self._vis_job = None
        for lbl in self._info.values():
            lbl.config(text="—", fg=C["fg"])
        self._cx_var.set("—")
        self._cy_var.set("—")
        self._size_var.set("—")

    # ── 중심 X/Y 입력 적용 ────────────────────
    def _apply_pos(self, event=None):
        if self._updating:
            return
        idx = self._sel_idx
        if idx < 0 or idx >= len(self.shapes):
            return
        cw, ch = self.CANVAS_W, self.CANVAS_H
        try:
            cx = self._to_px(float(self._cx_var.get()))
            cy = self._to_px(float(self._cy_var.get()))
        except ValueError:
            return
        s = self.shapes[idx]
        self._save_undo()
        s.cx_ratio = max(0.0, min(1.0, cx / cw))
        s.cy_ratio = max(0.0, min(1.0, cy / ch))
        self._redraw()
        self._update_info(s)

    # ── 크기 직접 입력 ────────────────────────
    def _apply_size(self, event=None):
        idx = self._sel_idx
        if idx < 0 or idx >= len(self.shapes):
            return
        try:
            val = float(self._size_var.get())
        except ValueError:
            return
        new_w = max(1.0, self._to_px(val))
        s = self.shapes[idx]
        self._save_undo()
        if s.shape_type in DUAL_DIM_TYPES and s.w_px > 0:
            s.h_px = s.h_px * new_w / s.w_px
        s.w_px = new_w
        self._updating = True
        self._size_scale.set(new_w)
        self._updating = False
        self._redraw()
        self._update_info(s)

    def _step_size(self, delta):
        """±1 (현재 단위) 씩 크기 조절."""
        idx = self._sel_idx
        if idx < 0 or idx >= len(self.shapes):
            return
        s = self.shapes[idx]
        step_px = self._to_px(1.0)
        new_w = max(1.0, s.w_px + delta * step_px)
        self._save_undo()
        if s.shape_type in DUAL_DIM_TYPES and s.w_px > 0:
            s.h_px = s.h_px * new_w / s.w_px
        s.w_px = new_w
        self._updating = True
        self._size_scale.set(new_w)
        self._updating = False
        self._redraw()
        self._update_info(s)

    # ── 크기 슬라이더 ─────────────────────────
    def _on_scale(self, val):
        if self._updating:
            return
        idx = self._sel_idx
        if idx < 0 or idx >= len(self.shapes):
            return
        new_w = float(val)   # 슬라이더는 항상 px 기준
        s = self.shapes[idx]
        if s.shape_type in DUAL_DIM_TYPES and s.w_px > 0:
            s.h_px = s.h_px * new_w / s.w_px
        s.w_px = new_w
        dec = 2 if self._unit == "mm" else 1
        self._size_var.set(f"{self._from_px(new_w):.{dec}f}")
        self._redraw()
        self._update_info(s)

    # ── 마우스 드래그 이동 ────────────────────
    def _on_press(self, event):
        z = self._zoom
        lx, ly = event.x / z, event.y / z   # 논리 좌표

        if self._ruler_mode:
            hit = self._ruler_handle_at(lx, ly)
            if hit:
                r, part = hit
                for i, ruler in enumerate(self.rulers):
                    if ruler.uid == r.uid:
                        self._sel_ruler_idx = i
                        self._updating = True
                        self._ruler_tree.selection_set(str(i))
                        self._updating = False
                        break
                self._ruler_drag_state = {'uid': r.uid, 'part': part}
            elif self._ruler_drawing:
                new_r = Ruler(lx, ly, lx, ly)
                self.rulers.append(new_r)
                self._sel_ruler_idx = len(self.rulers) - 1
                self._ruler_drag_state = {'uid': new_r.uid, 'part': 'p2'}
                self._ruler_drawing = False
                self._ruler_add_btn.config(style="TButton", text="줄자 추가")
                self._refresh_ruler_tree()
                self._draw_all_rulers()
            else:
                self._ruler_drag_state = None
            return

        # 캔버스 클릭 → 도형 선택 및 드래그 시작
        cw, ch = self.CANVAS_W, self.CANVAS_H
        hit_uid = -1
        for s in reversed(self.shapes):   # 위에 그려진 도형 우선
            if point_in_shape(s.shape_type,
                              s.cx_ratio * cw, s.cy_ratio * ch,
                              s.w_px, s.h_px, lx, ly):
                hit_uid = s.uid
                break

        if hit_uid >= 0:
            hit_idx = next((i for i, s in enumerate(self.shapes)
                            if s.uid == hit_uid), -1)
            if hit_idx >= 0:
                self._sel_idx = hit_idx
                self._updating = True
                self._tree.selection_set(str(hit_idx))
                self._updating = False
                s = self.shapes[hit_idx]
                self._update_info(s)
                self._updating = True
                self._size_scale.set(s.w_px)
                self._updating = False
                self._save_undo()
                self._drag_uid = -1 if s.locked else hit_uid
                self._drag_ox, self._drag_oy = lx, ly
        else:
            self._drag_uid = -1

    def _on_drag(self, event):
        z = self._zoom
        lx, ly = event.x / z, event.y / z

        if self._ruler_mode:
            if self._ruler_drag_state is None:
                return
            uid  = self._ruler_drag_state['uid']
            part = self._ruler_drag_state['part']
            r = next((r for r in self.rulers if r.uid == uid), None)
            if r:
                lx, ly = self._snap_ruler_point(lx, ly)
                if part == 'p1':
                    r.x1, r.y1 = lx, ly
                else:
                    r.x2, r.y2 = lx, ly
                self._draw_all_rulers()
                self._refresh_ruler_tree()
            return

        if self._drag_uid < 0:
            return
        cw, ch = self.CANVAS_W, self.CANVAS_H
        dx = (lx - self._drag_ox) / cw
        dy = (ly - self._drag_oy) / ch
        for s in self.shapes:
            if s.uid == self._drag_uid:
                s.cx_ratio = max(0.0, min(1.0, s.cx_ratio + dx))
                s.cy_ratio = max(0.0, min(1.0, s.cy_ratio + dy))
                self._drag_ox, self._drag_oy = lx, ly
                self._update_info(s)
                self._redraw()
                break

    def _on_release(self, event):
        z = self._zoom
        lx, ly = event.x / z, event.y / z

        if self._ruler_mode:
            if self._ruler_drag_state is not None:
                uid  = self._ruler_drag_state['uid']
                part = self._ruler_drag_state['part']
                r = next((r for r in self.rulers if r.uid == uid), None)
                if r:
                    lx, ly = self._snap_ruler_point(lx, ly)
                    if part == 'p1':
                        r.x1, r.y1 = lx, ly
                    else:
                        r.x2, r.y2 = lx, ly
                    dist_px = math.hypot(r.x2 - r.x1, r.y2 - r.y1)
                    sfx = self._unit_sfx()
                    dec = 2 if sfx == "mm" else 1
                    self._ruler_lbl.config(
                        text=f"선택 줄자: {self._from_px(dist_px):.{dec}f} {sfx}")
                    self._draw_all_rulers()
                    self._refresh_ruler_tree()
            self._ruler_drag_state = None
            return

        self._drag_uid = -1
        if 0 <= self._sel_idx < len(self.shapes):
            self._update_info(self.shapes[self._sel_idx])

    # ── 방향키 이동 ───────────────────────────
    def _on_arrow_key(self, event):
        # Entry 위젯에 포커스가 있으면 무시
        focused = self.root.focus_get()
        if isinstance(focused, (ttk.Entry, tk.Entry)):
            return
        idx = self._sel_idx
        if idx < 0 or idx >= len(self.shapes):
            return
        step = 5 if (event.state & 0x1) else 1   # Shift 여부
        cw, ch = self.CANVAS_W, self.CANVAS_H
        s = self.shapes[idx]
        dx = dy = 0
        sym = event.keysym
        if   sym in ("Left",  "KP_Left"):  dx = -step
        elif sym in ("Right", "KP_Right"): dx =  step
        elif sym in ("Up",    "KP_Up"):    dy = -step
        elif sym in ("Down",  "KP_Down"):  dy =  step
        if dx == 0 and dy == 0:
            return
        self._save_undo()
        s.cx_ratio = max(0.0, min(1.0, s.cx_ratio + dx / cw))
        s.cy_ratio = max(0.0, min(1.0, s.cy_ratio + dy / ch))
        self._redraw()
        self._update_info(s)
        return "break"   # 다른 위젯으로 이벤트 전파 차단

    # ── PanedWindow 1:1 초기 비율 설정 ────────
    def _equalize_left_panes(self):
        h = self._paned_left.winfo_height()
        if h > 20:
            self._paned_left.sash_place(0, 0, h // 2)

    # ── 파일 저장 / 불러오기 / 삭제 / 이름바꾸기 ──
    _SAVE_DIR = os.path.expanduser("~/project")

    def _canvas_to_dict(self):
        return {
            "canvas_w": self.CANVAS_W,
            "canvas_h": self.CANVAS_H,
            "unit": self._unit,
            "dpi": self._dpi,
            "shapes": [
                {"shape_type": s.shape_type, "w_px": s.w_px, "h_px": s.h_px,
                 "color": s.color, "cx_ratio": s.cx_ratio, "cy_ratio": s.cy_ratio,
                 "label": s.label, "locked": s.locked}
                for s in self.shapes
            ],
            "rulers": [
                {"x1": r.x1, "y1": r.y1, "x2": r.x2, "y2": r.y2, "color": r.color}
                for r in self.rulers
            ],
        }

    def _dict_to_canvas(self, data):
        self.CANVAS_W = data.get("canvas_w", self.CANVAS_W)
        self.CANVAS_H = data.get("canvas_h", self.CANVAS_H)
        self._unit = data.get("unit", "px")
        self._unit_var.set(self._unit)
        self._dpi = float(data.get("dpi", 96.0))
        self._dpi_var.set(str(int(self._dpi)))
        self.shapes = []
        for sd in data.get("shapes", []):
            s = Shape(shape_type=sd["shape_type"], w_px=sd["w_px"], h_px=sd["h_px"],
                      color=sd["color"], cx_ratio=sd["cx_ratio"],
                      cy_ratio=sd["cy_ratio"], label=sd["label"])
            s.locked = sd.get("locked", False)
            self.shapes.append(s)
        self.rulers = []
        for rd in data.get("rulers", []):
            self.rulers.append(Ruler(rd["x1"], rd["y1"], rd["x2"], rd["y2"],
                                     rd.get("color", "")))
        self._sel_idx = -1
        self._cv_w_var.set(str(self.CANVAS_W))
        self._cv_h_var.set(str(self.CANVAS_H))
        self._cv.config(width=self.CANVAS_W, height=self.CANVAS_H)
        self._size_scale.config(to=max(self.CANVAS_W, self.CANVAS_H))
        self._on_unit_change()
        self._redraw()
        self._refresh_tree()
        self._refresh_ruler_tree()

    # ── SVG 불러오기 ──────────────────────────
    def _import_svg(self):
        import xml.etree.ElementTree as ET

        path = filedialog.askopenfilename(
            title="SVG 불러오기",
            filetypes=[("SVG 파일", "*.svg"), ("모든 파일", "*.*")],
            initialdir=self._SAVE_DIR)
        if not path:
            return

        try:
            tree = ET.parse(path)
        except Exception as e:
            messagebox.showerror("SVG 파싱 오류", str(e))
            return

        root_el = tree.getroot()
        ns = {"svg": "http://www.w3.org/2000/svg"}
        # 네임스페이스 없이도 동작하도록 태그 정규화
        def strip_ns(tag):
            return tag.split("}")[-1] if "}" in tag else tag

        # viewBox 또는 width/height 로 SVG 좌표계 파악
        vb = root_el.get("viewBox") or root_el.get("viewbox")
        if vb:
            parts = vb.replace(",", " ").split()
            svg_x0, svg_y0 = float(parts[0]), float(parts[1])
            svg_w,  svg_h  = float(parts[2]), float(parts[3])
        else:
            svg_w = float(root_el.get("width",  self.CANVAS_W) or self.CANVAS_W)
            svg_h = float(root_el.get("height", self.CANVAS_H) or self.CANVAS_H)
            svg_x0, svg_y0 = 0.0, 0.0

        if svg_w <= 0 or svg_h <= 0:
            messagebox.showerror("SVG 오류", "SVG 크기를 파악할 수 없습니다.")
            return

        def svg_to_ratio(x, y):
            """SVG 절대 좌표 → 캔버스 비율 (0~1)"""
            return (x - svg_x0) / svg_w, (y - svg_y0) / svg_h

        def parse_color(val):
            if not val or val in ("none", "transparent"):
                return None
            if val.startswith("#") and len(val) in (4, 7):
                if len(val) == 4:
                    val = "#" + "".join(c*2 for c in val[1:])
                return val
            # rgb(r,g,b) 형태
            if val.startswith("rgb"):
                nums = [int(x.strip()) for x in val[4:-1].split(",")]
                return "#{:02x}{:02x}{:02x}".format(*nums)
            return DEFAULT_COLORS[0]

        def apply_group_transform(el, parent_tx=0.0, parent_ty=0.0, parent_sx=1.0, parent_sy=1.0):
            """<g transform="translate/scale"> 처리 — 단순 translate/scale만 지원."""
            t = el.get("transform", "")
            tx, ty, sx, sy = parent_tx, parent_ty, parent_sx, parent_sy
            if "translate" in t:
                vals = t[t.index("(")+1 : t.index(")")].replace(",", " ").split()
                tx += float(vals[0]) * parent_sx
                ty += float(vals[1] if len(vals) > 1 else "0") * parent_sy
            if "scale" in t:
                vals = t[t.index("(")+1 : t.index(")")].replace(",", " ").split()
                sx *= float(vals[0])
                sy *= float(vals[1] if len(vals) > 1 else vals[0])
            return tx, ty, sx, sy

        added = 0
        color_idx = len(self.shapes) % len(DEFAULT_COLORS)

        def process_elements(parent_el, tx=0.0, ty=0.0, sx=1.0, sy=1.0):
            nonlocal added, color_idx
            for el in parent_el:
                tag = strip_ns(el.tag)
                if tag == "g":
                    ntx, nty, nsx, nsy = apply_group_transform(el, tx, ty, sx, sy)
                    process_elements(el, ntx, nty, nsx, nsy)
                    continue

                fill = parse_color(el.get("fill") or el.get("style", "").split("fill:")[-1].split(";")[0].strip() if "fill:" in el.get("style", "") else None)
                color = fill or DEFAULT_COLORS[color_idx % len(DEFAULT_COLORS)]

                shape_type = None
                cx_r = cy_r = 0.5
                w_px = h_px = 50.0

                if tag == "circle":
                    r  = float(el.get("r", 50)) * sx
                    cx = float(el.get("cx", svg_w / 2)) * sx + tx
                    cy = float(el.get("cy", svg_h / 2)) * sy + ty
                    cx_r, cy_r = svg_to_ratio(cx, cy)
                    w_px = h_px = r * 2 / svg_w * self.CANVAS_W
                    shape_type = "원"

                elif tag == "ellipse":
                    rx = float(el.get("rx", 50)) * sx
                    ry = float(el.get("ry", 30)) * sy
                    cx = float(el.get("cx", svg_w / 2)) * sx + tx
                    cy = float(el.get("cy", svg_h / 2)) * sy + ty
                    cx_r, cy_r = svg_to_ratio(cx, cy)
                    w_px = rx * 2 / svg_w * self.CANVAS_W
                    h_px = ry * 2 / svg_h * self.CANVAS_H
                    shape_type = "원" if abs(rx - ry) < 1 else "타원"

                elif tag == "rect":
                    rw = float(el.get("width",  100)) * sx
                    rh = float(el.get("height", 100)) * sy
                    x  = float(el.get("x", 0)) * sx + tx
                    y  = float(el.get("y", 0)) * sy + ty
                    cx = x + rw / 2
                    cy = y + rh / 2
                    cx_r, cy_r = svg_to_ratio(cx, cy)
                    w_px = rw / svg_w * self.CANVAS_W
                    h_px = rh / svg_h * self.CANVAS_H
                    shape_type = "정사각형" if abs(rw - rh) < 1 else "직사각형"

                elif tag == "polygon":
                    pts_raw = el.get("points", "").replace(",", " ").split()
                    coords = [float(v) for v in pts_raw]
                    pts = [(coords[i]*sx + tx, coords[i+1]*sy + ty)
                           for i in range(0, len(coords)-1, 2)]
                    if len(pts) < 3:
                        continue
                    cx = sum(p[0] for p in pts) / len(pts)
                    cy = sum(p[1] for p in pts) / len(pts)
                    cx_r, cy_r = svg_to_ratio(cx, cy)
                    xs = [p[0] for p in pts]
                    ys = [p[1] for p in pts]
                    w_px = (max(xs) - min(xs)) / svg_w * self.CANVAS_W
                    h_px = (max(ys) - min(ys)) / svg_h * self.CANVAS_H
                    if len(pts) == 3:
                        shape_type = "정삼각형"
                    elif len(pts) == 6:
                        shape_type = "정육각형"
                    else:
                        shape_type = "직사각형"  # 근사

                if shape_type is None:
                    continue

                # 비율 범위 클리핑
                cx_r = max(0.0, min(1.0, cx_r))
                cy_r = max(0.0, min(1.0, cy_r))
                w_px = max(4.0, w_px)
                h_px = max(4.0, h_px)

                label = el.get("id") or el.get("inkscape:label") or f"{shape_type}{added+1}"
                s = Shape(shape_type=shape_type, w_px=w_px, h_px=h_px,
                          color=color, cx_ratio=cx_r, cy_ratio=cy_r, label=label)
                self.shapes.append(s)
                added += 1
                color_idx += 1

        process_elements(root_el)

        if added == 0:
            messagebox.showwarning("SVG 불러오기",
                "지원되는 도형을 찾지 못했습니다.\n"
                "(circle, ellipse, rect, polygon 지원)")
            return

        self._mark_dirty()
        self._redraw()
        self._refresh_tree()
        messagebox.showinfo("SVG 불러오기 완료",
            f"{added}개 도형을 불러왔습니다.\n\n"
            "지원 태그: circle, ellipse, rect, polygon\n"
            "미지원: path, text, image")

    def _check_dirty(self) -> bool:
        """미저장 변경사항 있으면 저장 여부 확인. 진행해도 되면 True 반환."""
        if not self._dirty:
            return True
        answer = messagebox.askyesnocancel(
            "저장하지 않은 변경사항",
            "저장하지 않은 변경사항이 있습니다.\n저장하시겠습니까?")
        if answer is None:      # 취소
            return False
        if answer:              # 예 → 저장 후 진행
            self._save_canvas()
            return not self._dirty  # 저장 대화상자를 취소하면 dirty가 남아 있음
        return True             # 아니오 → 저장 없이 진행

    def _reset_canvas(self):
        if not self._check_dirty():
            return
        self.shapes = []
        self.rulers = []
        self._sel_idx = -1
        self._sel_ruler_idx = -1
        self._undo_stack = []
        self._ruler_drag_state = None
        self.CANVAS_W = 800
        self.CANVAS_H = 600
        self._unit = "px"
        self._dpi = 96.0
        self._unit_var.set("px")
        self._dpi_var.set("96")
        self._cv_w_var.set("800")
        self._cv_h_var.set("600")
        self._cv.config(width=800, height=600)
        self._size_scale.config(to=max(800, 600))
        self._current_file = None
        self._on_unit_change()
        self._redraw()
        self._refresh_tree()
        self._refresh_ruler_tree()
        self._clear_dirty()

    def _save_canvas(self):
        path = filedialog.asksaveasfilename(
            title="캔버스 저장", defaultextension=".json",
            filetypes=[("JSON 파일", "*.json"), ("모든 파일", "*.*")],
            initialdir=self._SAVE_DIR)
        if not path:
            return
        with open(path, "w", encoding="utf-8") as f:
            json.dump(self._canvas_to_dict(), f, ensure_ascii=False, indent=2)
        self._current_file = path
        self._clear_dirty()
        messagebox.showinfo("저장 완료", f"저장됨:\n{os.path.basename(path)}")

    def _load_canvas(self):
        if not self._check_dirty():
            return
        path = filedialog.askopenfilename(
            title="캔버스 불러오기",
            filetypes=[("JSON 파일", "*.json"), ("모든 파일", "*.*")],
            initialdir=self._SAVE_DIR)
        if not path:
            return
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            self._dict_to_canvas(data)
            self._current_file = path
            self._clear_dirty()
        except Exception as e:
            messagebox.showerror("불러오기 실패", str(e))

    def _delete_canvas(self):
        path = filedialog.askopenfilename(
            title="삭제할 파일 선택",
            filetypes=[("JSON 파일", "*.json"), ("모든 파일", "*.*")],
            initialdir=self._SAVE_DIR)
        if not path:
            return
        if messagebox.askyesno("삭제 확인",
                               f"'{os.path.basename(path)}'\n을(를) 삭제할까요?"):
            os.remove(path)
            messagebox.showinfo("삭제 완료", "파일이 삭제되었습니다.")

    def _rename_canvas(self):
        path = filedialog.askopenfilename(
            title="이름 바꿀 파일 선택",
            filetypes=[("JSON 파일", "*.json"), ("모든 파일", "*.*")],
            initialdir=self._SAVE_DIR)
        if not path:
            return
        old_name = os.path.splitext(os.path.basename(path))[0]
        new_name = simpledialog.askstring("이름 바꾸기", "새 파일 이름:",
                                          initialvalue=old_name, parent=self.root)
        if not new_name or new_name == old_name:
            return
        new_path = os.path.join(os.path.dirname(path), new_name + ".json")
        if os.path.exists(new_path):
            messagebox.showerror("오류", f"'{new_name}.json' 이(가) 이미 존재합니다.")
            return
        os.rename(path, new_path)
        messagebox.showinfo("완료", f"'{old_name}' → '{new_name}'")

    # ── 센터 맞춤 ─────────────────────────────
    def _center_shape(self):
        idx = self._sel_idx
        if idx < 0 or idx >= len(self.shapes):
            return
        self._save_undo()
        s = self.shapes[idx]
        s.cx_ratio = 0.5
        s.cy_ratio = 0.5
        self._redraw()
        self._update_info(s)

    # ── 줄자 색상 ─────────────────────────────
    def _pick_ruler_color(self):
        idx = self._sel_ruler_idx
        if idx < 0 or idx >= len(self.rulers):
            return
        r = self.rulers[idx]
        c = colorchooser.askcolor(color=r.color, title="줄자 색상",
                                  parent=self.root)
        if c and c[1]:
            r.color = c[1]
            self._refresh_ruler_tree()
            self._draw_all_rulers()

    # ── 줄자 ──────────────────────────────────
    def _toggle_ruler(self):
        self._ruler_mode = not self._ruler_mode
        self._ruler_drawing = False
        self._ruler_drag_state = None
        if self._ruler_mode:
            self._ruler_btn.config(style="Accent.TButton", text="줄자 OFF")
            self._cv.config(cursor="tcross")
        else:
            self._ruler_btn.config(style="TButton", text="줄자 ON")
            self._cv.config(cursor="crosshair")
            self._ruler_add_btn.config(style="TButton", text="줄자 추가")
            self._ruler_lbl.config(text="")
        self._draw_all_rulers()

    def _start_add_ruler(self):
        """줄자 추가 버튼: 줄자 모드 활성화 후 그리기 대기"""
        if not self._ruler_mode:
            self._ruler_mode = True
            self._ruler_btn.config(style="Accent.TButton", text="줄자 OFF")
            self._cv.config(cursor="tcross")
            self._draw_all_rulers()
        self._ruler_drawing = True
        self._ruler_add_btn.config(style="Accent.TButton", text="클릭 후 드래그")

    def _del_ruler(self):
        idx = self._sel_ruler_idx
        if idx < 0 or idx >= len(self.rulers):
            return
        self.rulers.pop(idx)
        self._sel_ruler_idx = -1
        self._ruler_drag_state = None
        self._ruler_lbl.config(text="")
        self._mark_dirty()
        self._refresh_ruler_tree()
        self._draw_all_rulers()

    def _ruler_handle_at(self, x: float, y: float):
        """(x,y) 근처 핸들이 있으면 (Ruler, 'p1'/'p2') 반환, 없으면 None"""
        HIT_R = 10
        for r in reversed(self.rulers):
            if math.hypot(x - r.x1, y - r.y1) <= HIT_R:
                return r, 'p1'
            if math.hypot(x - r.x2, y - r.y2) <= HIT_R:
                return r, 'p2'
        return None

    def _refresh_ruler_tree(self):
        for item in self._ruler_tree.get_children():
            self._ruler_tree.delete(item)
        sfx = self._unit_sfx()
        dec = 2 if sfx == "mm" else 1
        for i, r in enumerate(self.rulers):
            dist_px = math.hypot(r.x2 - r.x1, r.y2 - r.y1)
            tag = f"rc_{r.uid}"
            self._ruler_tree.tag_configure(tag, foreground=r.color)
            self._ruler_tree.insert("", "end", iid=str(i), tags=(tag,),
                                    values=(i + 1,
                                            f"{self._from_px(dist_px):.{dec}f} {sfx}"))
        if 0 <= self._sel_ruler_idx < len(self.rulers):
            self._updating = True
            self._ruler_tree.selection_set(str(self._sel_ruler_idx))
            self._updating = False

    def _on_ruler_select(self, *_):
        if self._updating:
            return
        sel = self._ruler_tree.selection()
        if not sel:
            return
        self._sel_ruler_idx = int(sel[0])
        self._draw_all_rulers()
        # 선택 줄자 거리 표시
        r = self.rulers[self._sel_ruler_idx]
        dist_px = math.hypot(r.x2 - r.x1, r.y2 - r.y1)
        sfx = self._unit_sfx()
        dec = 2 if sfx == "mm" else 1
        self._ruler_lbl.config(
            text=f"선택 줄자: {self._from_px(dist_px):.{dec}f} {sfx}")

    # ── 줄자 스냅 ─────────────────────────────
    SNAP_DIST = 14  # 논리 픽셀

    def _shape_snap_points(self, s):
        """도형의 스냅 가능 포인트 목록 반환 (논리 좌표)."""
        cw, ch = self.CANVAS_W, self.CANVAS_H
        cx, cy = s.cx_ratio * cw, s.cy_ratio * ch
        w, h = s.w_px, s.h_px
        pts = [(cx, cy)]  # 센터는 항상 포함
        st = s.shape_type
        if st == "원":
            r = w / 2
            pts += [(cx + r, cy), (cx - r, cy), (cx, cy - r), (cx, cy + r)]
        elif st == "정사각형":
            hw = w / 2
            pts += [(cx - hw, cy - hw), (cx + hw, cy - hw),
                    (cx - hw, cy + hw), (cx + hw, cy + hw),
                    (cx, cy - hw), (cx, cy + hw), (cx - hw, cy), (cx + hw, cy)]
        elif st == "직사각형":
            hw, hh = w / 2, h / 2
            pts += [(cx - hw, cy - hh), (cx + hw, cy - hh),
                    (cx - hw, cy + hh), (cx + hw, cy + hh),
                    (cx, cy - hh), (cx, cy + hh), (cx - hw, cy), (cx + hw, cy)]
        elif st == "정삼각형":
            th = w * math.sqrt(3) / 2
            pts += [(cx, cy - th * 2 / 3),
                    (cx - w / 2, cy + th / 3),
                    (cx + w / 2, cy + th / 3)]
        elif st == "타원":
            rx, ry = w / 2, h / 2
            pts += [(cx + rx, cy), (cx - rx, cy), (cx, cy - ry), (cx, cy + ry)]
        elif st == "정육각형":
            r = w / 2
            for i in range(6):
                a = math.pi / 6 + i * math.pi / 3
                pts.append((cx + r * math.cos(a), cy + r * math.sin(a)))
        return pts

    def _snap_ruler_point(self, lx, ly):
        """가장 가까운 스냅 포인트 반환. 없으면 (lx, ly) 그대로."""
        best_d = self.SNAP_DIST
        best_pt = None
        for s in self.shapes:
            for px, py in self._shape_snap_points(s):
                d = math.hypot(lx - px, ly - py)
                if d < best_d:
                    best_d = d
                    best_pt = (px, py)
        return best_pt if best_pt else (lx, ly)

    def _draw_all_rulers(self):
        """모든 줄자를 도형 위에 그린다 (기존 항목 삭제 후 재생성)."""
        for item in self._ruler_items:
            self._cv.delete(item)
        self._ruler_items = []

        if not self._ruler_mode:
            return

        z = self._zoom
        HANDLE_R = 6
        TICK = 8

        for idx, r in enumerate(self.rulers):
            is_sel = (idx == self._sel_ruler_idx)
            LC = r.color
            lw = 3 if is_sel else 2
            # 논리 좌표 → 줌 좌표
            x1z, y1z = r.x1 * z, r.y1 * z
            x2z, y2z = r.x2 * z, r.y2 * z
            dist_px = math.hypot(r.x2 - r.x1, r.y2 - r.y1)

            line = self._cv.create_line(x1z, y1z, x2z, y2z,
                                        fill=LC, width=lw,
                                        arrow=tk.BOTH, arrowshape=(8, 10, 4))
            self._ruler_items.append(line)

            if dist_px >= 1:
                nx = -(r.y2 - r.y1) / dist_px
                ny =  (r.x2 - r.x1) / dist_px

                # 틱 마크
                for px, py in ((x1z, y1z), (x2z, y2z)):
                    t = self._cv.create_line(px + nx * TICK, py + ny * TICK,
                                             px - nx * TICK, py - ny * TICK,
                                             fill=LC, width=lw)
                    self._ruler_items.append(t)

                # 거리 레이블
                sfx = self._unit_sfx()
                dec = 2 if sfx == "mm" else 1
                label_text = f"{self._from_px(dist_px):.{dec}f} {sfx}"
                mx, my = (x1z + x2z) / 2, (y1z + y2z) / 2
                lbx = mx + nx * 18
                lby = my + ny * 18
                bg = self._cv.create_rectangle(lbx - 34, lby - 10,
                                               lbx + 34, lby + 10,
                                               fill=C["panel"],
                                               outline=LC, width=1)
                self._ruler_items.append(bg)
                txt = self._cv.create_text(lbx, lby, text=label_text,
                                           fill=LC,
                                           font=("맑은 고딕", 9, "bold"))
                self._ruler_items.append(txt)

            # 핸들 (드래그 포인트)
            for hx, hy in ((x1z, y1z), (x2z, y2z)):
                h = self._cv.create_oval(hx - HANDLE_R, hy - HANDLE_R,
                                         hx + HANDLE_R, hy + HANDLE_R,
                                         fill=LC if is_sel else C["panel"],
                                         outline=LC, width=2)
                self._ruler_items.append(h)

        # 모든 줄자 아이템을 최상단으로 올리기
        for item in self._ruler_items:
            self._cv.tag_raise(item)

    # ── 줌 ────────────────────────────────────
    def _zoom_in(self):
        self._zoom = min(4.0, round(self._zoom + 0.25, 2))
        self._zoom_lbl.config(text=f"{int(self._zoom * 100)}%")
        self._redraw()

    def _zoom_out(self):
        self._zoom = max(0.25, round(self._zoom - 0.25, 2))
        self._zoom_lbl.config(text=f"{int(self._zoom * 100)}%")
        self._redraw()

    def _zoom_reset(self):
        self._zoom = 1.0
        self._zoom_lbl.config(text="100%")
        self._redraw()

    def _on_zoom_wheel(self, event):
        if event.num == 4 or (hasattr(event, 'delta') and event.delta > 0):
            self._zoom_in()
        else:
            self._zoom_out()

    # ── 격자 ──────────────────────────────────
    def _toggle_grid(self):
        self._grid_on = not self._grid_on
        if self._grid_on:
            self._grid_btn.config(style="Accent.TButton", text="격자 ON")
        else:
            self._grid_btn.config(style="TButton", text="격자 OFF")
        self._redraw()

    def _apply_grid_settings(self):
        try:
            self._grid_cols = max(1, int(self._grid_cols_var.get()))
            self._grid_rows = max(1, int(self._grid_rows_var.get()))
        except ValueError:
            pass
        self._redraw()


# ──────────────────────────────────────────────
# 진입점
# ──────────────────────────────────────────────
if __name__ == "__main__":
    root = tk.Tk()
    app = AreaLayoutApp(root)
    root.mainloop()
