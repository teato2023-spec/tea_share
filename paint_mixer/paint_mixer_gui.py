"""
CMY 기반 유화 물감 혼합 시스템 + 이미지 색상 추출기 - Tkinter GUI
"""

import os
import sys
import ctypes
import tkinter as tk
from tkinter import ttk, messagebox, filedialog

try:
    from tkinterdnd2 import TkinterDnD, DND_FILES
    DND_AVAILABLE = True
except ImportError:
    DND_AVAILABLE = False

# Linux X11 BadWindow 에러 억제 (tkinterdnd2 드래그 후 발생)
if sys.platform.startswith("linux") and DND_AVAILABLE:
    try:
        _xlib = ctypes.cdll.LoadLibrary("libX11.so.6")
        _ERR_FUNC = ctypes.CFUNCTYPE(ctypes.c_int, ctypes.c_void_p, ctypes.c_void_p)
        _x_err_cb = _ERR_FUNC(lambda d, e: 0)   # 변수에 저장해야 GC 방지
        _xlib.XSetErrorHandler(_x_err_cb)
    except Exception:
        pass

try:
    from PIL import Image, ImageTk
    PIL_AVAILABLE = True
except ImportError:
    PIL_AVAILABLE = False

from paint_mixer_cmy import PaintMixer


# ──────────────────────────────────────────────────────────────────────────────
# 유틸리티
# ──────────────────────────────────────────────────────────────────────────────

def rgb_to_hsl(r, g, b):
    r, g, b = r / 255, g / 255, b / 255
    mx, mn = max(r, g, b), min(r, g, b)
    l = (mx + mn) / 2
    if mx == mn:
        return 0, 0, int(l * 100)
    d = mx - mn
    s = d / (2 - mx - mn) if l > 0.5 else d / (mx + mn)
    if mx == r:
        h = (g - b) / d + (6 if g < b else 0)
    elif mx == g:
        h = (b - r) / d + 2
    else:
        h = (r - g) / d + 4
    return int(h / 6 * 360), int(s * 100), int(l * 100)


# ──────────────────────────────────────────────────────────────────────────────
# 이미지 색상 추출기 (팝업 창)
# ──────────────────────────────────────────────────────────────────────────────

class ImageColorPicker(tk.Toplevel):
    """이미지를 불러와 마우스 클릭으로 색상을 추출하는 팝업 창"""

    IMAGE_EXTS = (
        ("이미지 파일", "*.png *.jpg *.jpeg *.gif *.bmp *.webp *.tiff *.tif *.avif"),
        ("모든 파일", "*.*"),
    )

    def __init__(self, parent, callback=None, initial_colors=None, close_callback=None):
        super().__init__(parent)
        self.title("이미지 색상 추출기")
        self.geometry("800x800")
        self.configure(bg="#1e1e2e")
        self.callback = callback          # fn(hex_color) — 색상 선택 후 호출
        self.close_callback = close_callback  # fn(color_list) — 창 닫힐 때 호출
        self.img = None
        self.base_scale = 1.0   # 이미지를 캔버스에 맞추는 초기 배율
        self.zoom = 1.0         # 사용자 확대/축소 배율
        self.offset_x = 0       # 캔버스 내 이미지 X 오프셋
        self.offset_y = 0       # 캔버스 내 이미지 Y 오프셋
        self.photo = None
        self.current_hex = None
        self.color_list = list(initial_colors) if initial_colors else []
        self._drag_start = None
        self._drag_offset_start = (0, 0)
        self._dragging = False

        self._build_ui()
        if self.color_list:
            self._refresh_list_ui()
        self.protocol("WM_DELETE_WINDOW", self._do_close)

    def _build_ui(self):
        # 상단 툴바
        toolbar = tk.Frame(self, bg="#181825")
        toolbar.pack(fill=tk.X)
        tk.Button(
            toolbar, text="이미지 열기...", command=self._open_image,
            bg="#313244", fg="#cdd6f4", relief="flat", padx=10, pady=4,
        ).pack(side=tk.LEFT, padx=6, pady=4)
        tk.Button(
            toolbar, text="맞춤", command=self._zoom_fit,
            bg="#313244", fg="#cdd6f4", relief="flat", padx=6, pady=4,
        ).pack(side=tk.LEFT, padx=2, pady=4)
        tk.Button(
            toolbar, text="1:1", command=self._zoom_reset,
            bg="#313244", fg="#cdd6f4", relief="flat", padx=6, pady=4,
        ).pack(side=tk.LEFT, padx=2, pady=4)
        self._zoom_var = tk.StringVar(value="100%")
        tk.Label(
            toolbar, textvariable=self._zoom_var,
            bg="#181825", fg="#a6adc8", font=("Courier New", 9), width=6,
        ).pack(side=tk.LEFT, padx=4)
        dnd_hint = "  드래그로 파일 추가  |" if DND_AVAILABLE else ""
        tk.Label(
            toolbar, text=f"{dnd_hint}  클릭: 색상 추출  |  드래그: 이동  |  휠: 확대/축소  |  ESC: 닫기",
            bg="#181825", fg="#585b70", font=("Arial", 8),
        ).pack(side=tk.LEFT, padx=4)

        # 메인 영역
        main = tk.Frame(self, bg="#1e1e2e")
        main.pack(fill=tk.BOTH, expand=True)

        # 이미지 캔버스
        self.canvas = tk.Canvas(main, bg="#11111b", cursor="crosshair",
                                highlightthickness=0)
        self.canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self.canvas.bind("<ButtonPress-1>", self._on_pan_start)
        self.canvas.bind("<B1-Motion>", self._on_pan_move)
        self.canvas.bind("<ButtonRelease-1>", self._on_pan_end)
        self.canvas.bind("<MouseWheel>", self._on_wheel)   # Windows / macOS
        self.canvas.bind("<Button-4>", self._on_wheel)     # Linux 휠 위
        self.canvas.bind("<Button-5>", self._on_wheel)     # Linux 휠 아래

        if DND_AVAILABLE:
            self.canvas.drop_target_register(DND_FILES)
            self.canvas.dnd_bind('<<Drop>>', self._on_drop)
            self.canvas.dnd_bind('<<DragEnter>>', self._on_drag_enter)
            self.canvas.dnd_bind('<<DragLeave>>', self._on_drag_leave)

        self._draw_drop_hint()

        # 오른쪽 패널
        right = tk.Frame(main, width=230, bg="#181825")
        right.pack(side=tk.RIGHT, fill=tk.Y)
        right.pack_propagate(False)

        # ── 색상 정보 ──
        tk.Label(right, text="색상 정보", font=("Arial", 11, "bold"),
                 bg="#181825", fg="#cdd6f4").pack(pady=(10, 4))

        self.preview = tk.Canvas(right, width=190, height=60, bg="#000",
                                 highlightthickness=1,
                                 highlightbackground="#45475a")
        self.preview.pack(pady=(0, 6))

        self.hex_var = tk.StringVar(value="#------")
        self.rgb_var = tk.StringVar(value="RGB(-, -, -)")
        self.hsl_var = tk.StringVar(value="HSL(-, -, -)")
        self.pos_var = tk.StringVar(value="위치: (-, -)")

        tk.Label(right, textvariable=self.hex_var,
                 font=("Courier New", 13, "bold"),
                 bg="#181825", fg="#cdd6f4").pack()
        tk.Label(right, textvariable=self.rgb_var,
                 font=("Courier New", 9),
                 bg="#181825", fg="#a6adc8").pack(pady=1)
        tk.Label(right, textvariable=self.hsl_var,
                 font=("Courier New", 9),
                 bg="#181825", fg="#a6adc8").pack()
        tk.Label(right, textvariable=self.pos_var,
                 font=("Courier New", 8),
                 bg="#181825", fg="#585b70").pack(pady=(4, 0))

        # ── 버튼 행 ──
        btn_row = tk.Frame(right, bg="#181825")
        btn_row.pack(fill=tk.X, padx=6, pady=6)

        self.add_btn = tk.Button(
            btn_row, text="목록에 추가",
            font=("Arial", 9), bg="#40a02b", fg="white",
            activebackground="#2d7920", relief="flat",
            padx=6, pady=4, command=self._add_to_list, state=tk.DISABLED,
        )
        self.add_btn.pack(side=tk.LEFT, expand=True, fill=tk.X, padx=(0, 2))

        self.copy_btn = tk.Button(
            btn_row, text="HEX 복사",
            font=("Arial", 9), bg="#313244", fg="#cdd6f4",
            activebackground="#45475a", relief="flat",
            padx=6, pady=4, command=self._copy_hex, state=tk.DISABLED,
        )
        self.copy_btn.pack(side=tk.LEFT, expand=True, fill=tk.X, padx=(2, 0))

        # ── 구분선 ──
        tk.Frame(right, height=1, bg="#45475a").pack(fill=tk.X, padx=6, pady=4)

        # ── 추출 목록 헤더 ──
        hdr = tk.Frame(right, bg="#181825")
        hdr.pack(fill=tk.X, padx=6)
        self.list_count_var = tk.StringVar(value="추출 목록 (0)")
        tk.Label(hdr, textvariable=self.list_count_var,
                 font=("Arial", 9, "bold"), bg="#181825", fg="#cdd6f4").pack(side=tk.LEFT)
        tk.Button(hdr, text="불러오기", command=self._load_colors,
                  font=("Arial", 8), bg="#313244", fg="#cdd6f4",
                  activebackground="#45475a", relief="flat",
                  padx=5, pady=2).pack(side=tk.RIGHT)

        # ── 스와치 스크롤 영역 ──
        swatch_outer = tk.Frame(right, bg="#181825")
        swatch_outer.pack(fill=tk.BOTH, expand=True, padx=6, pady=(2, 0))

        self._swatch_canvas = tk.Canvas(swatch_outer, bg="#11111b", highlightthickness=0)
        swatch_sb = tk.Scrollbar(swatch_outer, orient=tk.VERTICAL,
                                 command=self._swatch_canvas.yview)
        self._swatch_canvas.configure(yscrollcommand=swatch_sb.set)

        self._swatch_frame = tk.Frame(self._swatch_canvas, bg="#11111b")
        self._swatch_win = self._swatch_canvas.create_window(
            (0, 0), window=self._swatch_frame, anchor=tk.NW)

        self._swatch_frame.bind("<Configure>", lambda e: self._swatch_canvas.configure(
            scrollregion=self._swatch_canvas.bbox("all")))
        self._swatch_canvas.bind("<Configure>", lambda e: self._swatch_canvas.itemconfig(
            self._swatch_win, width=e.width))

        self._swatch_canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        swatch_sb.pack(side=tk.RIGHT, fill=tk.Y)

        # ── 저장 / 삭제 버튼 ──
        save_row = tk.Frame(right, bg="#181825")
        save_row.pack(fill=tk.X, padx=6, pady=6)
        tk.Button(
            save_row, text="파일 저장...", command=self._save_colors,
            font=("Arial", 9), bg="#1e66f5", fg="white",
            activebackground="#2469d6", relief="flat", padx=6, pady=4,
        ).pack(side=tk.LEFT, expand=True, fill=tk.X, padx=(0, 2))
        tk.Button(
            save_row, text="전체 삭제", command=self._clear_list,
            font=("Arial", 9), bg="#313244", fg="#cdd6f4",
            activebackground="#45475a", relief="flat", padx=6, pady=4,
        ).pack(side=tk.LEFT, expand=True, fill=tk.X, padx=(2, 0))

        self.bind("<q>", lambda _: self._do_close())
        self.bind("<Escape>", lambda _: self._do_close())

    def _do_close(self):
        """창 닫기 — 색상 목록을 상위에 전달한 뒤 소멸"""
        if self.close_callback:
            self.close_callback(list(self.color_list))
        self.destroy()

    def _draw_drop_hint(self):
        """이미지가 없을 때 캔버스에 안내 문구 표시"""
        self.canvas.delete("hint")
        if self.img is not None:
            return
        w = self.canvas.winfo_width() or 400
        h = self.canvas.winfo_height() or 400
        cx, cy = w // 2, h // 2
        self.canvas.create_text(
            cx, cy - 16, text="이미지를 여기에 드래그하거나",
            fill="#585b70", font=("Arial", 13), tags="hint",
        )
        self.canvas.create_text(
            cx, cy + 16, text="위 버튼으로 파일을 열어주세요",
            fill="#585b70", font=("Arial", 13), tags="hint",
        )

    def _on_drag_enter(self, event):
        self.canvas.config(bg="#1e2040")

    def _on_drag_leave(self, event):
        self.canvas.config(bg="#11111b")

    def _on_drop(self, event):
        self.canvas.config(bg="#11111b")
        raw = event.data.strip()
        # tkinterdnd2는 경로를 '{path}' 또는 공백 구분으로 반환
        if raw.startswith('{'):
            path = raw[1:raw.index('}')]
        else:
            path = raw.split()[0]
        self.after_idle(self._load_image, path)

    def _open_image(self):
        path = filedialog.askopenfilename(
            title="이미지 파일 선택",
            filetypes=self.IMAGE_EXTS,
            parent=self,
        )
        if not path:
            return
        self._load_image(path)

    def _load_image(self, path):
        try:
            self.img = Image.open(path).convert("RGB")
        except Exception as e:
            messagebox.showerror("오류", f"이미지를 열 수 없습니다:\n{e}", parent=self)
            return
        self.title(f"이미지 색상 추출기 — {os.path.basename(path)}")
        self._fit_and_draw()

    def _fit_and_draw(self):
        self.update_idletasks()
        cw = max(self.canvas.winfo_width(), 400)
        ch = max(self.canvas.winfo_height(), 400)
        self.base_scale = min(cw / self.img.width, ch / self.img.height, 1.0)
        self.zoom = 1.0
        dw = int(self.img.width * self.base_scale)
        dh = int(self.img.height * self.base_scale)
        self.offset_x = (cw - dw) // 2
        self.offset_y = (ch - dh) // 2
        self._redraw()

    def _redraw(self):
        """현재 zoom/offset 으로 이미지를 다시 그린다."""
        if self.img is None:
            return
        scale = self.base_scale * self.zoom
        dw = max(1, int(self.img.width * scale))
        dh = max(1, int(self.img.height * scale))
        disp = self.img.resize((dw, dh), Image.LANCZOS)
        self.photo = ImageTk.PhotoImage(disp)
        self.canvas.delete("all")
        self.canvas.create_image(self.offset_x, self.offset_y,
                                 anchor=tk.NW, image=self.photo)
        self._zoom_var.set(f"{scale * 100:.0f}%")

    def _on_wheel(self, event):
        if self.img is None:
            return
        if event.num == 4 or event.delta > 0:
            factor = 1.15
        else:
            factor = 1 / 1.15
        new_zoom = max(0.05, min(20.0, self.zoom * factor))
        factor = new_zoom / self.zoom
        # 마우스 커서 위치 기준으로 확대/축소
        self.offset_x = int(event.x - (event.x - self.offset_x) * factor)
        self.offset_y = int(event.y - (event.y - self.offset_y) * factor)
        self.zoom = new_zoom
        self._redraw()

    def _zoom_fit(self):
        """이미지를 캔버스에 맞게 되돌린다."""
        if self.img is None:
            return
        self._fit_and_draw()

    def _zoom_reset(self):
        """1:1 원본 크기로 되돌린다."""
        if self.img is None:
            return
        cw = max(self.canvas.winfo_width(), 400)
        ch = max(self.canvas.winfo_height(), 400)
        self.zoom = 1.0 / self.base_scale  # base_scale * zoom = 1.0
        dw = int(self.img.width * self.base_scale * self.zoom)
        dh = int(self.img.height * self.base_scale * self.zoom)
        self.offset_x = (cw - dw) // 2
        self.offset_y = (ch - dh) // 2
        self._redraw()

    def _on_pan_start(self, event):
        self._drag_start = (event.x, event.y)
        self._drag_offset_start = (self.offset_x, self.offset_y)
        self._dragging = False

    def _on_pan_move(self, event):
        if self._drag_start is None:
            return
        dx = event.x - self._drag_start[0]
        dy = event.y - self._drag_start[1]
        if abs(dx) > 4 or abs(dy) > 4:
            self._dragging = True
        if self._dragging:
            self.offset_x = self._drag_offset_start[0] + dx
            self.offset_y = self._drag_offset_start[1] + dy
            self._redraw()

    def _on_pan_end(self, event):
        if not self._dragging:
            self._on_click(event)
        self._drag_start = None
        self._dragging = False

    def _on_click(self, event):
        if self.img is None:
            return
        scale = self.base_scale * self.zoom
        px = int((event.x - self.offset_x) / scale)
        py = int((event.y - self.offset_y) / scale)
        # 이미지 영역 밖 클릭 무시
        if not (0 <= px < self.img.width and 0 <= py < self.img.height):
            return
        r, g, b = self.img.getpixel((px, py))
        hx = f"#{r:02X}{g:02X}{b:02X}"
        h, s, l = rgb_to_hsl(r, g, b)

        self.current_hex = hx
        self.hex_var.set(hx)
        self.rgb_var.set(f"RGB({r}, {g}, {b})")
        self.hsl_var.set(f"HSL({h}°, {s}%, {l}%)")
        self.pos_var.set(f"위치: ({px}, {py})")

        # 색상 미리보기
        self.preview.config(bg=hx)
        fg = "#fff" if (r * 299 + g * 587 + b * 114) / 1000 < 128 else "#000"
        self.preview.delete("all")
        self.preview.create_text(80, 35, text=hx,
                                 font=("Courier New", 13, "bold"), fill=fg)

        # 십자선 (캔버스 좌표)
        cx, cy = event.x, event.y
        self.canvas.delete("cross")
        for col, dash in [("white", ()), ("black", (4, 2))]:
            self.canvas.create_line(cx - 12, cy, cx + 12, cy,
                                    fill=col, width=1, dash=dash, tags="cross")
            self.canvas.create_line(cx, cy - 12, cx, cy + 12,
                                    fill=col, width=1, dash=dash, tags="cross")

        # 버튼 활성화 + 클립보드 자동 복사
        self.add_btn.config(state=tk.NORMAL)
        self.copy_btn.config(state=tk.NORMAL)
        self.clipboard_clear()
        self.clipboard_append(hx)

    def _add_to_list(self):
        """현재 선택 색을 추출 목록에 추가"""
        if not self.current_hex:
            return
        hx = self.current_hex
        r, g, b = int(hx[1:3], 16), int(hx[3:5], 16), int(hx[5:7], 16)
        h, s, l = rgb_to_hsl(r, g, b)
        self.color_list.append({"hex": hx, "r": r, "g": g, "b": b,
                                 "h": h, "s": s, "l": l})
        self._refresh_list_ui()

    def _refresh_list_ui(self):
        """스와치 목록 UI를 color_list 에 맞게 다시 그린다"""
        for w in self._swatch_frame.winfo_children():
            w.destroy()
        for i, item in enumerate(self.color_list):
            hx = item["hex"]
            row = tk.Frame(self._swatch_frame, bg="#11111b", cursor="hand2")
            row.pack(fill=tk.X, padx=2, pady=1)

            swatch = tk.Canvas(row, width=22, height=22, bg=hx,
                               highlightthickness=1, highlightbackground="#45475a")
            swatch.pack(side=tk.LEFT, padx=(4, 4), pady=2)

            lbl = tk.Label(row, text=hx, font=("Courier New", 10),
                           bg="#11111b", fg="#cdd6f4")
            lbl.pack(side=tk.LEFT)

            del_btn = tk.Button(row, text="×", font=("Arial", 9),
                                bg="#11111b", fg="#585b70",
                                activebackground="#313244", relief="flat", padx=2,
                                command=lambda idx=i: self._remove_from_list(idx))
            del_btn.pack(side=tk.RIGHT, padx=2)

            # 클릭 → 메인 GUI에 색 지정
            for widget in (row, swatch, lbl):
                widget.bind("<Button-1>", lambda e, h=hx: self._apply_color(h))

            # hover 효과
            def _enter(e, r=row, s=swatch, l=lbl):
                r.config(bg="#1e1e2e"); s.config(highlightbackground="#89b4fa")
                l.config(bg="#1e1e2e")
            def _leave(e, r=row, s=swatch, l=lbl):
                r.config(bg="#11111b"); s.config(highlightbackground="#45475a")
                l.config(bg="#11111b")
            for widget in (row, swatch, lbl):
                widget.bind("<Enter>", _enter)
                widget.bind("<Leave>", _leave)

        self.list_count_var.set(f"추출 목록 ({len(self.color_list)})")

    def _remove_from_list(self, idx):
        if 0 <= idx < len(self.color_list):
            self.color_list.pop(idx)
            self._refresh_list_ui()

    def _apply_color(self, hex_color):
        """목록의 색을 선택 — 색상 정보 업데이트 + 메인 GUI에 전달"""
        self.current_hex = hex_color
        r, g, b = int(hex_color[1:3], 16), int(hex_color[3:5], 16), int(hex_color[5:7], 16)
        h, s, l = rgb_to_hsl(r, g, b)
        self.hex_var.set(hex_color)
        self.rgb_var.set(f"RGB({r}, {g}, {b})")
        self.hsl_var.set(f"HSL({h}°, {s}%, {l}%)")
        self.pos_var.set("목록에서 선택")
        self.preview.config(bg=hex_color)
        fg = "#fff" if (r * 299 + g * 587 + b * 114) / 1000 < 128 else "#000"
        self.preview.delete("all")
        self.preview.create_text(95, 30, text=hex_color,
                                 font=("Courier New", 12, "bold"), fill=fg)
        self.add_btn.config(state=tk.NORMAL)
        self.copy_btn.config(state=tk.NORMAL)
        if self.callback:
            self.callback(hex_color)

    def _load_colors(self):
        """저장된 색상 파일 불러오기"""
        path = filedialog.askopenfilename(
            parent=self,
            title="색상 목록 불러오기",
            filetypes=[
                ("JSON 파일", "*.json"),
                ("CSV 파일", "*.csv"),
                ("텍스트 파일", "*.txt"),
                ("모든 파일", "*.*"),
            ],
        )
        if not path:
            return
        ext = os.path.splitext(path)[1].lower()
        try:
            loaded = []
            if ext == ".json":
                import json
                with open(path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                for item in data:
                    hx = item.get("hex", "")
                    if len(hx) == 7 and hx.startswith("#"):
                        r = item.get("r", int(hx[1:3], 16))
                        g = item.get("g", int(hx[3:5], 16))
                        b = item.get("b", int(hx[5:7], 16))
                        h, s, l = rgb_to_hsl(r, g, b)
                        loaded.append({"hex": hx, "r": r, "g": g, "b": b,
                                       "h": item.get("h", h), "s": item.get("s", s),
                                       "l": item.get("l", l)})
            elif ext == ".csv":
                with open(path, "r", encoding="utf-8") as f:
                    lines = f.readlines()
                for line in lines[1:]:   # 헤더 스킵
                    parts = line.strip().split(",")
                    if parts and len(parts[0]) == 7 and parts[0].startswith("#"):
                        hx = parts[0]
                        r = int(parts[1]) if len(parts) > 1 else int(hx[1:3], 16)
                        g = int(parts[2]) if len(parts) > 2 else int(hx[3:5], 16)
                        b = int(parts[3]) if len(parts) > 3 else int(hx[5:7], 16)
                        h, s, l = rgb_to_hsl(r, g, b)
                        h = int(parts[4]) if len(parts) > 4 else h
                        s = int(parts[5]) if len(parts) > 5 else s
                        l = int(parts[6]) if len(parts) > 6 else l
                        loaded.append({"hex": hx, "r": r, "g": g, "b": b,
                                       "h": h, "s": s, "l": l})
            else:  # txt
                with open(path, "r", encoding="utf-8") as f:
                    for line in f:
                        hx = line.strip()
                        if len(hx) == 7 and hx.startswith("#"):
                            r, g, b = int(hx[1:3], 16), int(hx[3:5], 16), int(hx[5:7], 16)
                            h, s, l = rgb_to_hsl(r, g, b)
                            loaded.append({"hex": hx, "r": r, "g": g, "b": b,
                                           "h": h, "s": s, "l": l})
            if not loaded:
                messagebox.showwarning("알림", "불러올 색상이 없습니다.", parent=self)
                return
            if self.color_list:
                choice = messagebox.askyesnocancel(
                    "불러오기 방식 선택",
                    f"{len(loaded)}개 색상을 불러옵니다.\n\n"
                    "예  → 기존 목록에 추가\n"
                    "아니오 → 기존 목록을 교체",
                    parent=self,
                )
                if choice is None:    # 취소
                    return
                if not choice:        # 아니오 → 교체
                    self.color_list.clear()
            self.color_list.extend(loaded)
            self._refresh_list_ui()
            messagebox.showinfo("완료", f"{len(loaded)}개 색상을 불러왔습니다.", parent=self)
        except Exception as e:
            messagebox.showerror("오류", f"불러오기 실패:\n{e}", parent=self)

    def _clear_list(self):
        if not self.color_list:
            return
        if messagebox.askyesno("확인", "목록을 모두 삭제하시겠습니까?", parent=self):
            self.color_list.clear()
            self._refresh_list_ui()

    def _save_colors(self):
        """추출 목록을 파일로 저장"""
        if not self.color_list:
            messagebox.showinfo("알림", "저장할 색이 없습니다.", parent=self)
            return
        path = filedialog.asksaveasfilename(
            parent=self,
            title="색상 목록 저장",
            defaultextension=".json",
            filetypes=[
                ("JSON 파일", "*.json"),
                ("CSV 파일", "*.csv"),
                ("텍스트 파일", "*.txt"),
            ],
        )
        if not path:
            return
        ext = os.path.splitext(path)[1].lower()
        try:
            if ext == ".json":
                import json
                with open(path, "w", encoding="utf-8") as f:
                    json.dump(self.color_list, f, ensure_ascii=False, indent=2)
            elif ext == ".csv":
                with open(path, "w", encoding="utf-8") as f:
                    f.write("hex,r,g,b,h,s,l\n")
                    for item in self.color_list:
                        f.write(f"{item['hex']},{item['r']},{item['g']},{item['b']},"
                                f"{item['h']},{item['s']},{item['l']}\n")
            else:
                with open(path, "w", encoding="utf-8") as f:
                    for item in self.color_list:
                        f.write(f"{item['hex']}\n")
            messagebox.showinfo("저장 완료",
                                f"{len(self.color_list)}개 색상을 저장했습니다.",
                                parent=self)
        except Exception as e:
            messagebox.showerror("오류", f"저장 실패:\n{e}", parent=self)

    def add_color(self, hex_color: str):
        """외부(메인 GUI)에서 색을 추출 목록에 직접 추가"""
        hx = hex_color.strip().upper()
        if len(hx) != 7 or not hx.startswith('#'):
            return
        r, g, b = int(hx[1:3], 16), int(hx[3:5], 16), int(hx[5:7], 16)
        h, s, l = rgb_to_hsl(r, g, b)
        self.color_list.append({"hex": hx, "r": r, "g": g, "b": b,
                                 "h": h, "s": s, "l": l})
        self._refresh_list_ui()
        # 추가된 항목이 보이도록 스크롤을 아래로
        self._swatch_canvas.update_idletasks()
        self._swatch_canvas.yview_moveto(1.0)
        # 창을 앞으로 가져오기
        self.lift()

    def _copy_hex(self):
        if self.current_hex:
            self.clipboard_clear()
            self.clipboard_append(self.current_hex)
            self.copy_btn.config(text="✓ 복사됨!")
            self.after(1500, lambda: self.copy_btn.config(text="HEX 복사"))


# ──────────────────────────────────────────────────────────────────────────────
# 메인 GUI
# ──────────────────────────────────────────────────────────────────────────────

class PaintMixerGUI:
    """Tkinter 기반 GUI"""

    def __init__(self, root):
        self.root = root
        self.root.title("유화 물감 혼합 시스템 (CMY 기반)")
        self.root.geometry("900x780")

        self.mixer = PaintMixer()
        self._updating = False
        self._color_picker = None        # ImageColorPicker 인스턴스 참조
        self._picker_color_list = []     # 추출기가 닫혀도 유지되는 색상 목록

        self.create_widgets()

    def create_widgets(self):
        """GUI 위젯 생성"""
        frame = ttk.Frame(self.root, padding="10")
        frame.pack(fill=tk.BOTH, expand=True)

        # ── Hex 색 입력 ──
        ttk.Label(frame, text="색 입력 (Hex):", font=("Arial", 10, "bold")).grid(
            row=0, column=0, sticky=tk.W
        )
        self.entry_analysis_color = ttk.Entry(frame, width=20)
        self.entry_analysis_color.insert(0, "#0066CC")
        self.entry_analysis_color.grid(row=0, column=1, padx=5)
        self.entry_analysis_color.bind("<Return>", self.on_hex_entry_change)
        self.entry_analysis_color.bind("<FocusOut>", self.on_hex_entry_change)

        ttk.Button(frame, text="이미지에서...",
                   command=self.open_image_color_picker).grid(row=0, column=2, padx=5)

        ttk.Button(frame, text="추출기에 추가",
                   command=self.send_color_to_picker).grid(row=0, column=3, padx=5)

        # ── CMYKW 색 선택기 ──
        cmyk_frame = ttk.LabelFrame(frame, text="CMYKW 색 선택기", padding="10")
        cmyk_frame.grid(row=1, column=0, columnspan=4, sticky=tk.EW, pady=10)

        self.cmyk_vars = {}
        self.cmyk_labels = {}

        channels = [
            ("C (Cyan)",    "C"),
            ("M (Magenta)", "M"),
            ("Y (Yellow)",  "Y"),
            ("K (Black)",   "K"),
            ("W (White)",   "W"),
        ]
        for i, (label_text, key) in enumerate(channels):
            ttk.Label(cmyk_frame, text=label_text, width=14, anchor=tk.W).grid(
                row=i, column=0, sticky=tk.W, pady=3
            )
            var = tk.IntVar(value=0)
            self.cmyk_vars[key] = var
            ttk.Scale(
                cmyk_frame, from_=0, to=100, orient=tk.HORIZONTAL,
                variable=var, command=lambda _v, k=key: self.on_cmyk_change()
            ).grid(row=i, column=1, sticky=tk.EW, padx=5)
            lbl = ttk.Label(cmyk_frame, text="  0%", width=5)
            lbl.grid(row=i, column=2)
            self.cmyk_labels[key] = lbl
        cmyk_frame.columnconfigure(1, weight=1)

        # ── 현재 색 미리보기 ──
        self.canvas_preview = tk.Canvas(frame, height=50, bg="white",
                                        relief=tk.SUNKEN)
        self.canvas_preview.grid(row=2, column=0, columnspan=4,
                                 sticky=tk.EW, pady=5)

        # ── 분석 버튼 ──
        ttk.Button(frame, text="분석",
                   command=self.on_analyze_click).grid(
            row=3, column=0, columnspan=4, sticky=tk.EW, pady=8
        )

        # ── 중간 회색 혼합 미리보기 ──
        mix_frame = ttk.LabelFrame(
            frame, text="중간 회색(#808080)을 만들기 위해 섞어야 할 색", padding="8"
        )
        mix_frame.grid(row=4, column=0, columnspan=4, sticky=tk.EW, pady=5)

        self.canvas_mix_src = tk.Canvas(mix_frame, width=120, height=60,
                                        bg="#CCCCCC", relief=tk.SUNKEN)
        self.canvas_mix_src.grid(row=0, column=0, padx=4)
        self.label_mix_src = ttk.Label(mix_frame, text="?", font=("Arial", 9))
        self.label_mix_src.grid(row=1, column=0)

        ttk.Label(mix_frame, text="+", font=("Arial", 18, "bold")).grid(
            row=0, column=1, padx=6
        )

        self.canvas_mix_color = tk.Canvas(mix_frame, width=120, height=60,
                                          bg="#CCCCCC", relief=tk.SUNKEN)
        self.canvas_mix_color.grid(row=0, column=2, padx=4)
        self.label_mix_color = ttk.Label(mix_frame, text="?", font=("Arial", 9))
        self.label_mix_color.grid(row=1, column=2)

        ttk.Label(mix_frame, text="=", font=("Arial", 18, "bold")).grid(
            row=0, column=3, padx=6
        )

        self.canvas_mix_result = tk.Canvas(mix_frame, width=120, height=60,
                                           bg="#CCCCCC", relief=tk.SUNKEN)
        self.canvas_mix_result.grid(row=0, column=4, padx=4)
        self.label_mix_result = ttk.Label(mix_frame, text="?", font=("Arial", 9))
        self.label_mix_result.grid(row=1, column=4)

        # ── 결과 텍스트 ──
        self.text_analysis_result = tk.Text(frame, height=16, width=60)
        self.text_analysis_result.grid(row=5, column=0, columnspan=4,
                                       sticky=tk.NSEW)

        frame.rowconfigure(5, weight=1)
        frame.columnconfigure(1, weight=1)

        self.sync_hex_to_cmykw("#0066CC")

    # ── 변환 함수 ──

    def cmykw_to_hex(self, c, m, y, k, w):
        """CMYKW (0-100) → Hex 변환"""
        r_base = 255 * (1 - c / 100) * (1 - k / 100)
        g_base = 255 * (1 - m / 100) * (1 - k / 100)
        b_base = 255 * (1 - y / 100) * (1 - k / 100)
        w_ratio = w / 100
        r = r_base + (255 - r_base) * w_ratio
        g = g_base + (255 - g_base) * w_ratio
        b = b_base + (255 - b_base) * w_ratio
        return (
            f"#{max(0, min(255, int(r))):02X}"
            f"{max(0, min(255, int(g))):02X}"
            f"{max(0, min(255, int(b))):02X}"
        )

    def hex_to_cmykw(self, hex_color):
        """Hex → CMYKW (0-100) 변환"""
        hex_color = hex_color.lstrip('#')
        if len(hex_color) != 6:
            return 0, 0, 0, 0, 0
        r = int(hex_color[0:2], 16) / 255
        g = int(hex_color[2:4], 16) / 255
        b = int(hex_color[4:6], 16) / 255
        w = min(r, g, b)
        w_pct = round(w * 100)
        if w >= 1.0:
            return 0, 0, 0, 0, 100
        scale = 1 - w
        r_base = (r - w) / scale
        g_base = (g - w) / scale
        b_base = (b - w) / scale
        k = 1 - max(r_base, g_base, b_base)
        if k >= 1.0:
            return 0, 0, 0, 100, w_pct
        c  = (1 - r_base - k) / (1 - k)
        m  = (1 - g_base - k) / (1 - k)
        yv = (1 - b_base - k) / (1 - k)
        return round(c * 100), round(m * 100), round(yv * 100), round(k * 100), w_pct

    def calc_midgray_mix(self, hex_color):
        """
        주어진 색과 50:50으로 섞었을 때 중간 회색(#808080)에 가장 가까운
        색을 계산한다.

        공식: (A + B) / 2 = 128  →  B = 256 - A  (0~255 클램핑)
        클램핑이 발생하면 실제 결과 색이 완전한 회색이 아닐 수 있으므로
        실제 결과 색도 함께 반환한다.
        """
        h = hex_color.lstrip('#')
        r_a = int(h[0:2], 16)
        g_a = int(h[2:4], 16)
        b_a = int(h[4:6], 16)

        r_b = max(0, min(255, 256 - r_a))
        g_b = max(0, min(255, 256 - g_a))
        b_b = max(0, min(255, 256 - b_a))

        mix_hex = f"#{r_b:02X}{g_b:02X}{b_b:02X}"

        r_res = (r_a + r_b) // 2
        g_res = (g_a + g_b) // 2
        b_res = (b_a + b_b) // 2
        result_hex = f"#{r_res:02X}{g_res:02X}{b_res:02X}"

        return mix_hex, result_hex

    # ── 동기화 ──

    def on_cmyk_change(self):
        """CMYKW 슬라이더 변경 → Hex 입력 및 미리보기 업데이트"""
        if self._updating:
            return
        self._updating = True
        c = self.cmyk_vars["C"].get()
        m = self.cmyk_vars["M"].get()
        y = self.cmyk_vars["Y"].get()
        k = self.cmyk_vars["K"].get()
        w = self.cmyk_vars["W"].get()
        for key, val in [("C", c), ("M", m), ("Y", y), ("K", k), ("W", w)]:
            self.cmyk_labels[key].config(text=f"{val:3d}%")
        hex_color = self.cmykw_to_hex(c, m, y, k, w)
        self.entry_analysis_color.delete(0, tk.END)
        self.entry_analysis_color.insert(0, hex_color)
        self.canvas_preview.config(bg=hex_color)
        self._updating = False

    def on_hex_entry_change(self, event=None):
        """Hex 입력 변경 → CMYKW 슬라이더 동기화"""
        if self._updating:
            return
        hex_color = self.entry_analysis_color.get().strip()
        if len(hex_color) == 7 and hex_color.startswith('#'):
            try:
                self.sync_hex_to_cmykw(hex_color)
            except Exception:
                pass

    def sync_hex_to_cmykw(self, hex_color):
        """Hex 값으로 CMYKW 슬라이더 및 미리보기 동기화"""
        self._updating = True
        c, m, y, k, w = self.hex_to_cmykw(hex_color)
        self.cmyk_vars["C"].set(c)
        self.cmyk_vars["M"].set(m)
        self.cmyk_vars["Y"].set(y)
        self.cmyk_vars["K"].set(k)
        self.cmyk_vars["W"].set(w)
        for key, val in [("C", c), ("M", m), ("Y", y), ("K", k), ("W", w)]:
            self.cmyk_labels[key].config(text=f"{val:3d}%")
        self.canvas_preview.config(bg=hex_color)
        self._updating = False

    # ── 이벤트 핸들러 ──

    def open_image_color_picker(self):
        """이미지 색상 추출기 팝업 열기 (이미 열려있으면 앞으로 가져오기)"""
        if not PIL_AVAILABLE:
            messagebox.showerror(
                "라이브러리 없음",
                "Pillow가 설치되지 않았습니다.\n\n"
                "설치 명령:\n"
                "  pip install pillow\n"
                "또는\n"
                "  sudo apt install python3-pil python3-pil.imagetk",
            )
            return

        # 이미 열려있으면 앞으로 가져오기만 함
        if self._color_picker is not None:
            self._color_picker.lift()
            self._color_picker.focus_force()
            return

        def on_color_picked(hex_color):
            self.entry_analysis_color.delete(0, tk.END)
            self.entry_analysis_color.insert(0, hex_color)
            self.sync_hex_to_cmykw(hex_color)

        def on_picker_close(saved_list):
            # 창이 닫힐 때 목록을 메인 GUI에 보존
            self._picker_color_list = saved_list
            self._color_picker = None

        picker = ImageColorPicker(
            self.root,
            callback=on_color_picked,
            initial_colors=self._picker_color_list,
            close_callback=on_picker_close,
        )
        self._color_picker = picker

    def send_color_to_picker(self):
        """현재 Hex 색을 이미지 색상 추출기의 추출 목록에 추가"""
        hex_color = self.entry_analysis_color.get().strip()
        if len(hex_color) != 7 or not hex_color.startswith('#'):
            messagebox.showwarning("알림", "올바른 Hex 색상을 입력해 주세요.\n예: #FF6B9D")
            return
        # 추출기가 닫혀있으면 먼저 열기
        if self._color_picker is None:
            self.open_image_color_picker()
        # 열린 추출기에 색 추가
        if self._color_picker is not None:
            self._color_picker.add_color(hex_color)

    def on_analyze_click(self):
        """색 분석 버튼 클릭"""
        color_hex = self.entry_analysis_color.get().strip()

        try:
            self.canvas_preview.config(bg=color_hex)

            result = self.mixer.analyze_color(color_hex)

            c = self.cmyk_vars["C"].get()
            m = self.cmyk_vars["M"].get()
            y = self.cmyk_vars["Y"].get()
            k = self.cmyk_vars["K"].get()
            w = self.cmyk_vars["W"].get()

            # ── 중간 회색 혼합 계산 ──
            mix_hex, result_mix_hex = self.calc_midgray_mix(color_hex)
            mc, mm, my, mk, mw = self.hex_to_cmykw(mix_hex)

            # 스와치 업데이트
            self.canvas_mix_src.config(bg=color_hex)
            self.label_mix_src.config(text=color_hex)
            self.canvas_mix_color.config(bg=mix_hex)
            self.label_mix_color.config(text=mix_hex)
            self.canvas_mix_result.config(bg=result_mix_hex)
            self.label_mix_result.config(text=result_mix_hex)

            # ── 텍스트 결과 ──
            self.text_analysis_result.delete(1.0, tk.END)

            output  = "[분석 색]\n"
            output += f"  Hex:   {result['hex']}\n"
            output += f"  RGB:   R={result['rgb']['r']},  G={result['rgb']['g']},  B={result['rgb']['b']}\n"
            output += f"  CMYKW: C={c}%,  M={m}%,  Y={y}%,  K={k}%,  W={w}%\n"
            output += f"  CMY:   C={result['cmy']['c']:.3f},  M={result['cmy']['m']:.3f},  Y={result['cmy']['y']:.3f}\n"
            output += f"  Kubelka-Munk:  K={result['kubelka_munk']['k']:.3f},  S={result['kubelka_munk']['s']:.3f}\n"
            output += f"  무채색: {result['characteristics']['is_neutral']}  "
            output += f"주색상: {result['characteristics']['dominant_channel']}  "
            output += f"채도: {result['characteristics']['saturation']:.3f}\n"

            output += f"\n{'─'*50}\n"
            output += "[중간 회색(#808080)을 만들기 위해 섞어야 할 색]\n"
            output += f"  Hex:   {mix_hex}\n"

            mix_result_data = self.mixer.analyze_color(mix_hex)
            output += f"  RGB:   R={mix_result_data['rgb']['r']},  G={mix_result_data['rgb']['g']},  B={mix_result_data['rgb']['b']}\n"
            output += f"  CMYKW: C={mc}%,  M={mm}%,  Y={my}%,  K={mk}%,  W={mw}%\n"
            output += f"  CMY:   C={mix_result_data['cmy']['c']:.3f},  M={mix_result_data['cmy']['m']:.3f},  Y={mix_result_data['cmy']['y']:.3f}\n"
            output += f"  Kubelka-Munk:  K={mix_result_data['kubelka_munk']['k']:.3f},  S={mix_result_data['kubelka_munk']['s']:.3f}\n"

            output += "\n[50:50 혼합 결과]\n"
            output += f"  결과 색 Hex: {result_mix_hex}\n"

            h = result_mix_hex.lstrip('#')
            rr, gr, br = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
            diff = ((rr - 128)**2 + (gr - 128)**2 + (br - 128)**2) ** 0.5
            output += f"  목표 #808080과의 오차: {diff:.1f}\n"
            if diff < 5:
                output += "  → 완벽한 중간 회색입니다.\n"
            else:
                output += "  → 채널 클램핑으로 인해 완전한 회색이 아닐 수 있습니다.\n"

            self.text_analysis_result.insert(tk.END, output)

        except Exception as e:
            messagebox.showerror("오류", f"오류 발생: {str(e)}")


def main():
    if DND_AVAILABLE:
        root = TkinterDnD.Tk()
    else:
        root = tk.Tk()
    app = PaintMixerGUI(root)
    root.mainloop()


if __name__ == "__main__":
    main()
