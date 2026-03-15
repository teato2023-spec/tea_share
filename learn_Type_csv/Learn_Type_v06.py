"""
암기 최적화 타이핑 연습 v6
- 기본 모드: 가리기 (전체 가리기) → 암기에 최적화
- SRS 복습 카드가 있으면 자동으로 복습 모드로 시작
- 해석/설명 항상 표시 (암기 보조)
- SRS 평가 기본 단축키: 1=다시, 2=어려움, 3=보통, 4=쉬움
- 상단 통계 바: 오늘 복습 수 / 암기 완료 수 / 전체 수
- 완료 후 정답 텍스트 자동 공개
- CSV 형식: text, description, explanation
"""

from __future__ import annotations
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from tkinter.font import Font
import csv
import json
import os
import shutil
import random
from datetime import date, timedelta

try:
    from tkinterdnd2 import TkinterDnD, DND_FILES
    HAS_DND = True
except ImportError:
    HAS_DND = False

_DEFAULT_BASE_DIR = os.path.join(os.path.expanduser("~"), "문서", "Learn Type")
_SETTINGS_PATH   = os.path.join(os.path.expanduser("~"), ".config", "learn_type", "settings_v6.json")

_SHORTCUT_ACTIONS = [
    ("prev",    "이전 문장"),
    ("next",    "다음 문장"),
    ("restart", "다시시작"),
    ("reveal",  "정답 공개/숨김"),
    ("rate_0",  "평가: 다시"),
    ("rate_1",  "평가: 어려움"),
    ("rate_2",  "평가: 보통"),
    ("rate_3",  "평가: 쉬움"),
    ("memorize","암기 완료"),
    ("mask_first", "첫글자만 보이기"),
    ("mask_full",  "전체 가리기"),
]

_DEFAULT_SHORTCUTS: dict[str, str] = {
    "rate_0": "<Key-1>",
    "rate_1": "<Key-2>",
    "rate_2": "<Key-3>",
    "rate_3": "<Key-4>",
    **{k: "" for k, _ in _SHORTCUT_ACTIONS if k not in ("rate_0","rate_1","rate_2","rate_3")}
}


def _event_to_bind(event) -> str:
    mods = []
    if event.state & 0x4: mods.append("Control")
    if event.state & 0x1: mods.append("Shift")
    if event.state & 0x8: mods.append("Alt")
    if mods:
        return "<" + "-".join(mods) + "-Key-" + event.keysym + ">"
    return "<Key-" + event.keysym + ">"


def _bind_to_display(bind_str: str) -> str:
    if not bind_str:
        return ""
    s = bind_str.strip("<>")
    parts = s.split("-")
    disp = []
    for p in parts:
        if p == "Control": disp.append("Ctrl")
        elif p == "Shift":  disp.append("Shift")
        elif p == "Alt":    disp.append("Alt")
        elif p == "Key":    continue
        else:               disp.append(p.upper() if len(p) == 1 else p)
    return "+".join(disp)


# ══════════════════════════════════════════════════════════════════════════════
class MemorizeApp:
# ══════════════════════════════════════════════════════════════════════════════

    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title("암기 연습 v6")
        self.root.geometry("1400x860")
        self.root.configure(bg="#1a1a2e")

        _s = self._load_settings()
        self.base_dir = _s.get("base_dir", _DEFAULT_BASE_DIR)
        self.srs_custom_paths: dict = _s.get("srs_custom_paths", {})
        self.shortcuts: dict = {**_DEFAULT_SHORTCUTS, **_s.get("shortcuts", {})}
        self._bound_shortcuts: list[str] = []
        os.makedirs(self.base_dir, exist_ok=True)

        # 상태
        self.current_csv: str | None = None
        self.sentence_data: list[tuple[str, str, str]] = []
        self.practice_indices: list[int] = []
        self.current_index: int = 0
        self.srs_data: dict = {}
        self.memorized_indices: set[int] = set()

        self.is_typing: bool = False
        self.completed: bool = False
        self.random_var = tk.BooleanVar(value=True)
        # 암기 최적화: 기본 모드 = 가리기
        self.typing_mode = tk.StringVar(value="가리기")
        self._mask_style: str = "full"   # 기본 전체 가리기
        self._hidden_revealed: bool = False

        self._desc_visible: bool = False
        self._explanation_visible: bool = False
        self._banner_visible: bool = False

        self._drag_source: str | None = None
        self._drag_start_y: int = 0
        self._drag_moved: bool = False

        self._setup_fonts()
        self._setup_ui()
        self._create_sentence_window()
        self._create_tree_window()
        self._setup_target_tags()
        self.load_tree()
        self._apply_shortcuts()

    # ── 헬퍼 ─────────────────────────────────────────────────────────────────

    def _cur_row(self):
        return self.sentence_data[self.practice_indices[self.current_index]] if self.practice_indices else None

    def _cur_text(self) -> str:
        row = self._cur_row(); return row[0] if row else ""

    def _cur_desc(self) -> str:
        row = self._cur_row(); return row[1] if row else ""

    def _cur_explanation(self) -> str:
        row = self._cur_row()
        return (row[2] if len(row) > 2 else "") if row else ""

    # ── 폰트 ─────────────────────────────────────────────────────────────────

    def _setup_fonts(self, size=15):
        self._font_size = size
        self.fn_strike = Font(family="Malgun Gothic", size=size, overstrike=True)
        self.fn_sm     = Font(family="Malgun Gothic", size=size)
        self.fn_bold   = Font(family="Malgun Gothic", size=size, weight="bold")
        self.fn_mono   = Font(family="Monospace", size=size)
        self.fn_mono_s = Font(family="Monospace", size=size, overstrike=True)
        self.fn_stat   = Font(family="Malgun Gothic", size=13)
        self.fn_stat_b = Font(family="Malgun Gothic", size=13, weight="bold")

    def _change_font_size(self, size_str):
        size = int(size_str)
        self._font_size = size
        for fn in [self.fn_strike, self.fn_sm, self.fn_bold, self.fn_mono, self.fn_mono_s]:
            fn.configure(size=size)

    # ── 설정 ─────────────────────────────────────────────────────────────────

    def _load_settings(self) -> dict:
        try:
            with open(_SETTINGS_PATH, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {}

    def _save_settings(self):
        os.makedirs(os.path.dirname(_SETTINGS_PATH), exist_ok=True)
        try:
            with open(_SETTINGS_PATH, "w", encoding="utf-8") as f:
                json.dump({
                    "base_dir": self.base_dir,
                    "srs_custom_paths": self.srs_custom_paths,
                    "shortcuts": self.shortcuts,
                }, f, ensure_ascii=False, indent=2)
        except Exception:
            pass

    # ── 단축키 ───────────────────────────────────────────────────────────────

    def _shortcut_fn(self, action_id: str):
        return {
            "prev":       self.prev_sentence,
            "next":       self.next_sentence,
            "restart":    self.restart_all,
            "reveal":     self._toggle_reveal,
            "memorize":   self.memorize_current,
            "rate_0":     lambda: self._rate_and_next(0),
            "rate_1":     lambda: self._rate_and_next(1),
            "rate_2":     lambda: self._rate_and_next(2),
            "rate_3":     lambda: self._rate_and_next(3),
            "mask_first": lambda: self._toggle_mask("first"),
            "mask_full":  lambda: self._toggle_mask("full"),
        }.get(action_id)

    def _apply_shortcuts(self):
        for b in self._bound_shortcuts:
            try: self.root.unbind(b)
            except Exception: pass
        self._bound_shortcuts = []
        for action_id, bind_str in self.shortcuts.items():
            if not bind_str:
                continue
            fn = self._shortcut_fn(action_id)
            if fn:
                try:
                    self.root.bind(bind_str, lambda e, f=fn: f())
                    self._bound_shortcuts.append(bind_str)
                except Exception:
                    pass

    def _open_shortcuts_window(self):
        win = tk.Toplevel(self.root)
        win.title("단축키 설정")
        win.resizable(False, False)
        win.configure(bg="#f0f2f5")
        win.transient(self.root)
        win.grab_set()

        tk.Label(win, text="  단축키 설정", bg="#2c3e50", fg="white",
                 font=self.fn_bold, pady=8, anchor="w").pack(fill=tk.X)

        body = tk.Frame(win, bg="#f0f2f5", padx=16, pady=12)
        body.pack(fill=tk.BOTH)

        tk.Label(body, text="기능",   bg="#dfe6e9", font=self.fn_bold,
                 width=18, anchor="w", padx=6, pady=4).grid(row=0, column=0, sticky="ew", padx=(0,2), pady=(0,4))
        tk.Label(body, text="단축키", bg="#dfe6e9", font=self.fn_bold,
                 width=14, anchor="w", padx=6, pady=4).grid(row=0, column=1, sticky="ew", padx=(0,2), pady=(0,4))

        key_labels: dict[str, tk.Label] = {}

        def capture(action_id: str, lbl: tk.Label):
            dlg = tk.Toplevel(win)
            dlg.title("키 입력"); dlg.configure(bg="#f0f2f5")
            dlg.transient(win); dlg.grab_set(); dlg.resizable(False, False)
            tk.Label(dlg, text="원하는 키 조합을 누르세요", bg="#f0f2f5", font=self.fn_bold, pady=12, padx=24).pack()
            cur = self.shortcuts.get(action_id, "")
            disp_var = tk.StringVar(value=_bind_to_display(cur) or "(없음)")
            captured = [cur]
            tk.Label(dlg, textvariable=disp_var, bg="#ecf0f1", font=self.fn_mono,
                     padx=20, pady=10, relief=tk.GROOVE, width=20).pack(padx=20, pady=(0,14))
            _SKIP = {"Shift_L","Shift_R","Control_L","Control_R","Alt_L","Alt_R","Super_L","Super_R"}
            def on_key(e):
                if e.keysym in _SKIP: return
                b = _event_to_bind(e); captured[0] = b; disp_var.set(_bind_to_display(b))
            dlg.bind("<KeyPress>", on_key); dlg.focus_set()
            def confirm():
                self.shortcuts[action_id] = captured[0]
                lbl.config(text=_bind_to_display(captured[0]) or "(없음)")
                dlg.destroy()
            def clear(): captured[0] = ""; disp_var.set("(없음)")
            bf = tk.Frame(dlg, bg="#f0f2f5"); bf.pack(pady=(0,14))
            _b = dict(font=self.fn_sm, relief=tk.FLAT, padx=10, pady=3, cursor="hand2")
            tk.Button(bf, text="확인",   command=confirm,      bg="#27ae60", fg="white", **_b).pack(side=tk.LEFT, padx=3)
            tk.Button(bf, text="초기화", command=clear,        bg="#e67e22", fg="white", **_b).pack(side=tk.LEFT, padx=3)
            tk.Button(bf, text="취소",   command=dlg.destroy,  bg="#bdc3c7",             **_b).pack(side=tk.LEFT, padx=3)

        for row, (action_id, label) in enumerate(_SHORTCUT_ACTIONS, start=1):
            tk.Label(body, text=label, bg="#f0f2f5", font=self.fn_sm,
                     anchor="w", padx=6).grid(row=row, column=0, sticky="ew", pady=2)
            cur = self.shortcuts.get(action_id, "")
            key_lbl = tk.Label(body, text=_bind_to_display(cur) or "(없음)",
                               bg="#ecf0f1", font=self.fn_sm, anchor="w",
                               padx=8, pady=2, relief=tk.FLAT, width=14)
            key_lbl.grid(row=row, column=1, sticky="ew", padx=(2,4), pady=2)
            key_labels[action_id] = key_lbl
            tk.Button(body, text="변경",
                      command=lambda aid=action_id, lbl=key_lbl: capture(aid, lbl),
                      font=self.fn_sm, relief=tk.FLAT, padx=8, pady=1,
                      bg="#3498db", fg="white", cursor="hand2").grid(row=row, column=2, padx=(0,0), pady=2)

        def reset_all():
            for aid in self.shortcuts:
                self.shortcuts[aid] = ""
                if aid in key_labels: key_labels[aid].config(text="(없음)")

        bf = tk.Frame(win, bg="#f0f2f5", pady=10); bf.pack()
        _b = dict(font=self.fn_sm, relief=tk.FLAT, padx=12, pady=3, cursor="hand2")
        tk.Button(bf, text="저장", command=lambda: (self._apply_shortcuts(), self._save_settings(), win.destroy()),
                  bg="#27ae60", fg="white", **_b).pack(side=tk.LEFT, padx=4)
        tk.Button(bf, text="전체 초기화", command=reset_all, bg="#e67e22", fg="white", **_b).pack(side=tk.LEFT, padx=4)
        tk.Button(bf, text="취소", command=win.destroy, bg="#bdc3c7", **_b).pack(side=tk.LEFT, padx=4)

    def _open_options_window(self):
        win = tk.Toplevel(self.root)
        win.title("옵션"); win.resizable(False, False)
        win.configure(bg="#f0f2f5"); win.transient(self.root); win.grab_set()

        body = tk.Frame(win, bg="#f0f2f5", padx=20, pady=16)
        body.pack(fill=tk.BOTH)

        tk.Label(body, text="글자 크기", bg="#f0f2f5", font=self.fn_bold).grid(row=0, column=0, sticky="w", pady=(0,6))
        size_var = tk.StringVar(value=str(self._font_size))
        om = tk.OptionMenu(body, size_var, "12","14","15","16","18","20","22","24","26","28","32",
                           command=self._change_font_size)
        om.config(font=self.fn_sm, bg="#ecf0f1", relief=tk.FLAT)
        om.grid(row=0, column=1, columnspan=2, padx=(10,0), pady=(0,6), sticky="w")

        tk.Label(body, text="기본 폴더", bg="#f0f2f5", font=self.fn_bold).grid(row=1, column=0, sticky="w", pady=(10,4))
        dir_lbl = tk.Label(body, text=self.base_dir, bg="#ecf0f1", font=self.fn_sm,
                           anchor="w", padx=6, pady=4, relief=tk.FLAT, wraplength=500)
        dir_lbl.grid(row=2, column=0, columnspan=2, sticky="ew", pady=(0,4))

        def change_dir():
            new_dir = filedialog.askdirectory(title="기본 폴더 선택", initialdir=self.base_dir, parent=win)
            if not new_dir: return
            self.base_dir = new_dir
            os.makedirs(self.base_dir, exist_ok=True)
            self._save_settings(); dir_lbl.config(text=self.base_dir); self.load_tree()

        tk.Button(body, text="폴더 변경", command=change_dir,
                  font=self.fn_sm, relief=tk.FLAT, padx=10, pady=3,
                  cursor="hand2", bg="#3498db", fg="white").grid(row=3, column=0, columnspan=2, sticky="w", pady=(0,10))

        ttk.Separator(body, orient="horizontal").grid(row=4, column=0, columnspan=3, sticky="ew", pady=(0,10))
        tk.Button(body, text="단축키 설정...", command=self._open_shortcuts_window,
                  font=self.fn_sm, relief=tk.FLAT, padx=10, pady=3,
                  bg="#8e44ad", fg="white", cursor="hand2").grid(row=5, column=0, columnspan=3, sticky="w", pady=(0,6))
        tk.Button(body, text="닫기", command=win.destroy,
                  font=self.fn_sm, relief=tk.FLAT, padx=12, pady=3,
                  cursor="hand2", bg="#bdc3c7").grid(row=6, column=0, columnspan=3, pady=(0,0))

    # ══════════════════════════════════════════════════════════════════════════
    # UI 구성
    # ══════════════════════════════════════════════════════════════════════════

    def _setup_ui(self):
        # ── 상단 통계 바 (암기 최적화 핵심) ─────────────────────────────────
        stat_bar = tk.Frame(self.root, bg="#16213e", pady=7, padx=12)
        stat_bar.pack(fill=tk.X)

        tk.Label(stat_bar, text="암기 연습", bg="#16213e", fg="#e94560",
                 font=self.fn_bold).pack(side=tk.LEFT, padx=(0, 20))

        self._stat_review_lbl = tk.Label(
            stat_bar, text="복습 0", bg="#16213e", fg="#f5a623",
            font=self.fn_stat_b, padx=8, pady=2,
            relief=tk.FLAT, cursor="hand2"
        )
        self._stat_review_lbl.pack(side=tk.LEFT, padx=4)
        self._stat_review_lbl.bind("<Button-1>", lambda e: self._switch_to_review())

        self._stat_mem_lbl = tk.Label(
            stat_bar, text="암기완료 0 / 0", bg="#16213e", fg="#2ecc71",
            font=self.fn_stat
        )
        self._stat_mem_lbl.pack(side=tk.LEFT, padx=12)

        self._stat_file_lbl = tk.Label(
            stat_bar, text="파일 없음", bg="#16213e", fg="#7f8c8d",
            font=self.fn_stat
        )
        self._stat_file_lbl.pack(side=tk.LEFT, padx=8)

        # 오른쪽 버튼
        _rb = dict(font=self.fn_stat, relief=tk.FLAT, padx=8, pady=2, cursor="hand2")
        tk.Button(stat_bar, text="옵션", command=self._open_options_window,
                  bg="#2c3e50", fg="#bdc3c7", **_rb).pack(side=tk.RIGHT, padx=2)
        tk.Button(stat_bar, text="파일 관리", command=self._open_tree_window,
                  bg="#2c3e50", fg="#bdc3c7", **_rb).pack(side=tk.RIGHT, padx=2)
        tk.Button(stat_bar, text="문장 목록", command=self._open_sentence_window,
                  bg="#2c3e50", fg="#bdc3c7", **_rb).pack(side=tk.RIGHT, padx=2)

        # ── 네비게이션 바 ─────────────────────────────────────────────────────
        nav = tk.Frame(self.root, bg="#0f3460", pady=5, padx=8)
        nav.pack(fill=tk.X)

        _nb = dict(font=self.fn_sm, relief=tk.FLAT, padx=8, pady=3, cursor="hand2", bg="#0f3460", fg="#ecf0f1")
        tk.Button(nav, text="◀ 이전", command=self.prev_sentence, **_nb).pack(side=tk.LEFT)
        self._counter_lbl = tk.Label(nav, text="0 / 0", bg="#0f3460", fg="#f5a623", font=self.fn_bold)
        self._counter_lbl.pack(side=tk.LEFT, padx=10)
        tk.Button(nav, text="다음 ▶", command=self.next_sentence, **_nb).pack(side=tk.LEFT)
        tk.Button(nav, text="다시시작", command=self.restart_all, **_nb).pack(side=tk.LEFT, padx=(8,0))

        tk.Checkbutton(
            nav, text="랜덤",
            variable=self.random_var, command=self._toggle_random,
            bg="#0f3460", fg="#ecf0f1", font=self.fn_sm, cursor="hand2",
            selectcolor="#e94560", activebackground="#0f3460", activeforeground="white"
        ).pack(side=tk.RIGHT, padx=6)

        # 모드 선택
        _MODE_COLORS = {"기본": "#3498db", "가리기": "#8e44ad", "복습": "#e67e22"}
        for mode in ["기본", "가리기", "복습"]:
            tk.Radiobutton(
                nav, text=mode, variable=self.typing_mode, value=mode,
                command=self._on_mode_change,
                bg="#0f3460", selectcolor=_MODE_COLORS[mode],
                fg="#ecf0f1", activeforeground="white",
                font=self.fn_sm, cursor="hand2",
                indicatoron=False, padx=7, pady=2,
                relief=tk.GROOVE, activebackground=_MODE_COLORS[mode],
            ).pack(side=tk.RIGHT, padx=1)

        main = tk.Frame(self.root, bg="#1a1a2e")
        main.pack(fill=tk.BOTH, expand=True)
        self._build_practice_panel(main)

    # ── 연습 패널 ────────────────────────────────────────────────────────────

    def _build_practice_panel(self, parent: tk.Frame):
        # 마스크 버튼 바
        self._mask_bar = tk.Frame(parent, bg="#1a1a2e", pady=4, padx=12)
        _mb = dict(font=self.fn_sm, relief=tk.FLAT, padx=10, pady=3, cursor="hand2")
        self._mask_btn_first = tk.Button(
            self._mask_bar, text="첫글자만 보이기",
            command=lambda: self._toggle_mask("first"), bg="#dfe6e9", fg="#2c3e50", **_mb)
        self._mask_btn_first.pack(side=tk.LEFT, padx=(0,6))
        self._mask_btn_full = tk.Button(
            self._mask_bar, text="전체 가리기",
            command=lambda: self._toggle_mask("full"), bg="#8e44ad", fg="white", **_mb)
        self._mask_btn_full.pack(side=tk.LEFT)
        tk.Label(self._mask_bar,
                 text="  ↑ 정답 공개/숨김  |  Enter = 보통으로 다음  |  1다시  2어려움  3보통  4쉬움",
                 bg="#1a1a2e", fg="#7f8c8d", font=self.fn_stat).pack(side=tk.LEFT, padx=16)
        self._mask_bar.pack(fill=tk.X)

        # 연습 문장 표시
        target_lf = tk.LabelFrame(
            parent, text=" 문장 ", font=self.fn_bold,
            bg="#1a1a2e", fg="#e94560", padx=10, pady=6
        )
        target_lf.pack(fill=tk.X, padx=12, pady=(6,2))

        self.target_display = tk.Text(
            target_lf, height=2, font=self.fn_mono,
            state=tk.DISABLED, wrap=tk.WORD,
            bg="#0d1117", fg="#e0e0e0",
            relief=tk.FLAT, cursor="arrow",
            padx=10, pady=8
        )
        self.target_display.pack(fill=tk.X)

        # ── 해석 프레임 (암기 보조 — 항상 표시) ─────────────────────────────
        self._middle = tk.Frame(parent, bg="#1a1a2e")
        self._middle.pack(fill=tk.X)

        self._desc_frame = tk.LabelFrame(
            self._middle, text=" 해석 ", font=self.fn_bold,
            bg="#0d2137", fg="#5dade2", padx=10, pady=6
        )
        _desc_row = tk.Frame(self._desc_frame, bg="#0d2137")
        _desc_row.pack(fill=tk.X)
        self._desc_lbl = tk.Label(
            _desc_row, text="",
            bg="#0d2137", fg="#85c1e9",
            font=self.fn_sm, wraplength=1100,
            anchor="w", justify="left"
        )
        self._desc_lbl.pack(side=tk.LEFT, fill=tk.X, expand=True)
        self._desc_copy_btn = tk.Button(
            _desc_row, text="복사", font=self.fn_stat,
            bg="#1a4a6e", fg="#85c1e9", relief=tk.FLAT,
            padx=8, pady=2, cursor="hand2",
            command=self._copy_desc
        )
        self._desc_copy_btn.pack(side=tk.RIGHT, padx=(6,0))

        self._explanation_frame = tk.LabelFrame(
            self._middle, text=" 설명 ", font=self.fn_bold,
            bg="#0d2a0d", fg="#58d68d", padx=10, pady=6
        )
        _expl_row = tk.Frame(self._explanation_frame, bg="#0d2a0d")
        _expl_row.pack(fill=tk.X)
        self._explanation_lbl = tk.Label(
            _expl_row, text="",
            bg="#0d2a0d", fg="#82e0aa",
            font=self.fn_sm, wraplength=1100,
            anchor="w", justify="left"
        )
        self._explanation_lbl.pack(side=tk.LEFT, fill=tk.X, expand=True)
        self._expl_copy_btn = tk.Button(
            _expl_row, text="복사", font=self.fn_stat,
            bg="#1a4a1a", fg="#82e0aa", relief=tk.FLAT,
            padx=8, pady=2, cursor="hand2",
            command=self._copy_explanation
        )
        self._expl_copy_btn.pack(side=tk.RIGHT, padx=(6,0))

        # 입력 영역
        input_lf = tk.LabelFrame(
            parent, text=" 입력 ", font=self.fn_bold,
            bg="#1a1a2e", fg="#e94560", padx=10, pady=6
        )
        input_lf.pack(fill=tk.X, padx=12, pady=(2,6))

        self.input_text = tk.Text(
            input_lf, height=2, font=self.fn_mono,
            wrap=tk.WORD, bg="#0d1117", fg="#e0e0e0",
            insertbackground="#e94560",
            padx=10, pady=8, undo=True, maxundo=-1
        )
        self.input_text.pack(fill=tk.X)
        self.input_text.bind("<KeyRelease>", self._on_key_release)
        self.input_text.bind("<Return>",     self._handle_enter)
        self.input_text.bind("<Up>",         self._handle_up)

        # ── SRS 평가 배너 ─────────────────────────────────────────────────────
        self._banner_frame = tk.Frame(parent, bg="#1e4d2b", pady=6, padx=12)

        tk.Label(self._banner_frame, text="완료!",
                 bg="#1e4d2b", fg="#2ecc71",
                 font=Font(family="Malgun Gothic", size=16, weight="bold"),
                 padx=12).pack(side=tk.LEFT)
        tk.Label(self._banner_frame,
                 text="Enter=보통  |  ",
                 bg="#1e4d2b", fg="#a9dfbf",
                 font=Font(family="Malgun Gothic", size=14)).pack(side=tk.LEFT)

        _srs_f = tk.Frame(self._banner_frame, bg="#1e4d2b")
        _srs_f.pack(side=tk.LEFT, padx=4)
        for _label, _color, _rating in [
            ("1 다시",   "#c0392b", 0),
            ("2 어려움", "#d35400", 1),
            ("3 보통",   "#2980b9", 2),
            ("4 쉬움",   "#1e8449", 3),
        ]:
            tk.Button(
                _srs_f, text=_label,
                bg=_color, fg="white",
                font=Font(family="Malgun Gothic", size=14, weight="bold"),
                relief=tk.FLAT, padx=10, pady=4, cursor="hand2",
                command=lambda r=_rating: self._rate_and_next(r)
            ).pack(side=tk.LEFT, padx=3, pady=2)

        # 하단 바
        bot = tk.Frame(parent, bg="#0f3460", pady=5, padx=8)
        bot.pack(fill=tk.X)
        tk.Button(bot, text="암기 완료", command=self.memorize_current,
                  font=self.fn_sm, relief=tk.FLAT, padx=8, pady=3,
                  cursor="hand2", bg="#1e8449", fg="white").pack(side=tk.LEFT, padx=4)
        tk.Button(bot, text="편집", command=self._edit_current_sentence,
                  font=self.fn_sm, relief=tk.FLAT, padx=8, pady=3,
                  cursor="hand2", bg="#2c3e50", fg="#bdc3c7").pack(side=tk.LEFT, padx=4)
        self._desc_visible = False
        self._explanation_visible = False
        self._banner_visible = False

    # ── 문장 목록 팝업 ───────────────────────────────────────────────────────

    def _create_sentence_window(self):
        win = tk.Toplevel(self.root)
        win.title("문장 목록")
        win.geometry("1200x780")
        win.resizable(True, True)
        win.configure(bg="#f8f9fa")
        win.transient(self.root)
        win.protocol("WM_DELETE_WINDOW", win.withdraw)
        win.withdraw()
        self._sent_win = win

        self._inline_idx: int | None = None
        self._inline_visible: bool = False

        hdr = tk.Frame(win, bg="#bdc3c7", pady=5, padx=10)
        hdr.pack(fill=tk.X)
        tk.Label(hdr, text="문장 목록", bg="#bdc3c7", font=self.fn_bold).pack(side=tk.LEFT)
        self._csv_lbl = tk.Label(hdr, text="파일 관리에서 CSV를 선택하세요",
                                 bg="#bdc3c7", fg="#555", font=self.fn_sm)
        self._csv_lbl.pack(side=tk.LEFT, padx=10)

        search_frame = tk.Frame(win, bg="#f0f2f5", pady=5, padx=6)
        search_frame.pack(fill=tk.X)
        tk.Label(search_frame, text="검색:", bg="#f0f2f5", font=self.fn_sm).pack(side=tk.LEFT)
        self._search_var = tk.StringVar()
        self._search_var.trace_add("write", lambda *_: self._apply_search())
        search_entry = tk.Entry(search_frame, textvariable=self._search_var,
                                font=self.fn_sm, relief=tk.SOLID, bd=1)
        search_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(4,4))
        tk.Button(search_frame, text="✕", command=lambda: self._search_var.set(""),
                  font=self.fn_sm, relief=tk.FLAT, padx=6, cursor="hand2", bg="#f0f2f5").pack(side=tk.LEFT)

        outer = tk.Frame(win, bg="#f8f9fa")
        outer.pack(fill=tk.BOTH, expand=True, padx=6, pady=(4,0))

        btn_col = tk.Frame(outer, bg="#f8f9fa", padx=4, pady=2)
        btn_col.pack(side=tk.RIGHT, fill=tk.Y)
        _cb = dict(font=self.fn_sm, relief=tk.FLAT, padx=10, pady=6, cursor="hand2")
        tk.Button(btn_col, text="+ 추가",    command=self.add_sentence,   bg="#27ae60", fg="white", **_cb).pack(fill=tk.X, pady=2)
        tk.Button(btn_col, text="✏ 편집",    command=self.edit_sentence,  bg="#8e44ad", fg="white", **_cb).pack(fill=tk.X, pady=2)
        tk.Button(btn_col, text="삭제",      command=self.delete_sentence, bg="#e74c3c", fg="white", **_cb).pack(fill=tk.X, pady=2)
        tk.Label(btn_col, bg="#f8f9fa").pack(fill=tk.Y, expand=True)
        tk.Button(btn_col, text="닫기",      command=win.withdraw,         bg="#7f8c8d", fg="white", **_cb).pack(fill=tk.X, pady=2)

        self._paned = ttk.PanedWindow(outer, orient=tk.HORIZONTAL)
        self._paned.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        tv_wrap = tk.Frame(self._paned, bg="#f8f9fa")
        self._paned.add(tv_wrap, weight=3)

        style = ttk.Style()
        style.configure("Sent.Treeview", font=self.fn_sm, rowheight=36)
        style.configure("Sent.Treeview.Heading", font=self.fn_bold)

        self.sent_tree = ttk.Treeview(
            tv_wrap, style="Sent.Treeview",
            columns=("check","content","srs"), show="headings", selectmode="browse"
        )
        self.sent_tree.heading("check",   text="암기")
        self.sent_tree.heading("content", text="문장")
        self.sent_tree.heading("srs",     text="난이도")
        self.sent_tree.column("check",   width=55,  minwidth=55,  stretch=False, anchor="center")
        self.sent_tree.column("content", width=520, minwidth=200, stretch=True)
        self.sent_tree.column("srs",     width=90,  minwidth=90,  stretch=False, anchor="center")
        self.sent_tree.tag_configure("normal",       foreground="#2c3e50")
        self.sent_tree.tag_configure("memorized",    foreground="#27ae60")
        self.sent_tree.tag_configure("hdr",          background="#dfe6e9", foreground="#555555", font=self.fn_bold)
        self.sent_tree.tag_configure("empty",        foreground="#aaaaaa")
        self.sent_tree.tag_configure("search_match", background="#fff3cd")
        self.sent_tree.tag_configure("drag_over",    background="#d5e8f5")

        vsb = ttk.Scrollbar(tv_wrap, orient="vertical", command=self.sent_tree.yview)
        self.sent_tree.configure(yscrollcommand=vsb.set)
        vsb.pack(side=tk.RIGHT, fill=tk.Y)
        self.sent_tree.pack(fill=tk.BOTH, expand=True)

        self.sent_tree.bind("<<TreeviewSelect>>", self._on_sentence_select)
        self.sent_tree.bind("<ButtonPress-1>",    self._drag_start)
        self.sent_tree.bind("<B1-Motion>",        self._drag_motion)
        self.sent_tree.bind("<ButtonRelease-1>",  self._drag_end)

        # 인라인 수정 패널
        self._inline_frame = tk.LabelFrame(
            self._paned, text=" 선택 문장 수정 ", font=self.fn_bold,
            bg="#fffde7", padx=4, pady=6, fg="#7d6608"
        )
        _inline_canvas = tk.Canvas(self._inline_frame, bg="#fffde7", bd=0, highlightthickness=0, width=300)
        _inline_vsb = ttk.Scrollbar(self._inline_frame, orient="vertical", command=_inline_canvas.yview)
        _inline_canvas.configure(yscrollcommand=_inline_vsb.set)
        _inline_vsb.pack(side=tk.RIGHT, fill=tk.Y)
        _inline_canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        _inner = tk.Frame(_inline_canvas, bg="#fffde7")
        _inline_cwin = _inline_canvas.create_window((0,0), window=_inner, anchor="nw")
        _inner.bind("<Configure>", lambda e: _inline_canvas.configure(scrollregion=_inline_canvas.bbox("all")))
        _inline_canvas.bind("<Configure>", lambda e: _inline_canvas.itemconfig(_inline_cwin, width=e.width))

        tk.Label(_inner, text="문장:", bg="#fffde7", font=self.fn_sm).pack(anchor="w")
        self._inline_txt = tk.Text(_inner, height=2, font=self.fn_mono, wrap=tk.WORD,
                                   padx=5, pady=3, bg="#1e2a38", fg="#e0e0e0",
                                   insertbackground="white", undo=True)
        self._inline_txt.pack(fill=tk.X, pady=(0,4))
        self._inline_txt.bind("<KeyRelease>", lambda e: self._inline_auto_h(self._inline_txt))
        tk.Label(_inner, text="해석:", bg="#fffde7", font=self.fn_sm).pack(anchor="w")
        self._inline_desc = tk.Text(_inner, height=2, font=self.fn_sm, wrap=tk.WORD,
                                    padx=5, pady=3, bg="#eaf4fb", fg="#1a5276", undo=True)
        self._inline_desc.pack(fill=tk.X, pady=(0,4))
        self._inline_desc.bind("<KeyRelease>", lambda e: self._inline_auto_h(self._inline_desc))
        tk.Label(_inner, text="설명:", bg="#fffde7", font=self.fn_sm).pack(anchor="w")
        self._inline_expl = tk.Text(_inner, height=2, font=self.fn_sm, wrap=tk.WORD,
                                    padx=5, pady=3, bg="#f0fff0", fg="#1a5226", undo=True)
        self._inline_expl.pack(fill=tk.X, pady=(0,4))
        self._inline_expl.bind("<KeyRelease>", lambda e: self._inline_auto_h(self._inline_expl))

        ibf = tk.Frame(_inner, bg="#fffde7"); ibf.pack(anchor="e", pady=(0,2))
        _ib = dict(font=self.fn_sm, relief=tk.FLAT, padx=8, pady=3, cursor="hand2")
        tk.Button(ibf, text="저장", command=self._save_inline_edit, bg="#27ae60", fg="white", **_ib).pack(side=tk.LEFT, padx=3)
        tk.Button(ibf, text="취소", command=self._hide_inline_edit, bg="#95a5a6", fg="white", **_ib).pack(side=tk.LEFT)

    def _open_sentence_window(self):
        if not self.current_csv:
            messagebox.showinfo("안내", "먼저 파일 관리에서 CSV 파일을 선택하세요.")
            return
        self._sent_win.deiconify()
        self._sent_win.lift()
        self._sent_win.focus_set()

    # ── 파일 관리 팝업 ───────────────────────────────────────────────────────

    def _create_tree_window(self):
        win = tk.Toplevel(self.root)
        win.title("파일 관리")
        win.geometry("400x680")
        win.resizable(True, True)
        win.configure(bg="#ecf0f1")
        win.transient(self.root)
        win.protocol("WM_DELETE_WINDOW", win.withdraw)
        win.withdraw()
        self._tree_win = win

        tk.Label(win, text="  폴더 / 파일", bg="#bdc3c7", font=self.fn_bold, anchor="w", pady=5).pack(fill=tk.X)

        wrap = tk.Frame(win, bg="#ecf0f1")
        wrap.pack(fill=tk.BOTH, expand=True, padx=4, pady=4)

        self.tree = ttk.Treeview(wrap, show="tree", selectmode="browse")
        vsb = ttk.Scrollbar(wrap, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=vsb.set)
        vsb.pack(side=tk.RIGHT, fill=tk.Y)
        self.tree.pack(fill=tk.BOTH, expand=True)

        style = ttk.Style()
        style.configure("Treeview", font=self.fn_sm, rowheight=36)
        self.tree.tag_configure("folder",  foreground="#e67e22")
        self.tree.tag_configure("csv",     foreground="#2980b9")
        self.tree.tag_configure("csv_srs", foreground="#27ae60")

        self.tree.bind("<<TreeviewSelect>>", self._on_tree_select)
        self.tree.bind("<Double-1>",         self._on_tree_double_click)
        self.tree.bind("<Button-3>",         self._show_tree_ctx_menu)

        self._file_drag_source: str | None = None
        self._file_drag_start_y: int = 0
        self._file_drag_moved: bool = False

        if HAS_DND:
            win.drop_target_register(DND_FILES)
            win.dnd_bind("<<Drop>>", self._on_tree_drop)

        # 버튼
        btn_f = tk.Frame(win, bg="#ecf0f1", pady=4)
        btn_f.pack()
        _bb = dict(font=self.fn_sm, relief=tk.FLAT, padx=8, pady=3, cursor="hand2")
        tk.Button(btn_f, text="폴더 추가",    command=self.create_folder,    bg="#e67e22", fg="white", **_bb).pack(side=tk.LEFT, padx=3)
        tk.Button(btn_f, text="CSV 만들기",   command=self.create_csv_file,  bg="#27ae60", fg="white", **_bb).pack(side=tk.LEFT, padx=3)
        tk.Button(btn_f, text="가져오기",     command=self.import_csv,       bg="#3498db", fg="white", **_bb).pack(side=tk.LEFT, padx=3)
        tk.Button(win,   text="닫기",         command=win.withdraw,          bg="#bdc3c7",             **_bb).pack(pady=(0,6))

    def _open_tree_window(self):
        self._tree_win.deiconify()
        self._tree_win.lift()
        self._tree_win.focus_set()

    def _on_tree_drop(self, event):
        try:
            files = self.root.tk.splitlist(event.data)
        except Exception:
            files = [event.data]
        imported = 0
        for f in files:
            f = f.strip()
            if not f.lower().endswith(".csv"):
                continue
            dest = os.path.join(self.base_dir, os.path.basename(f))
            if os.path.abspath(f) == os.path.abspath(dest):
                continue
            if os.path.exists(dest) and not messagebox.askyesno("덮어쓰기", f"'{os.path.basename(dest)}' 덮어쓸까요?", parent=self._tree_win):
                continue
            try:
                shutil.copy2(f, dest); imported += 1
            except Exception as e:
                messagebox.showerror("오류", str(e), parent=self._tree_win)
        if imported:
            self.load_tree()
            messagebox.showinfo("완료", f"{imported}개 CSV 파일을 가져왔습니다.", parent=self._tree_win)

    def _setup_target_tags(self):
        self.target_display.tag_configure("correct",     foreground="#2ecc71", font=self.fn_mono)
        self.target_display.tag_configure("wrong",       foreground="#e74c3c", font=self.fn_mono_s)
        self.target_display.tag_configure("cursor_pos",  background="#e67e22", foreground="#ffffff", font=self.fn_mono)
        self.target_display.tag_configure("pending",     foreground="#7f8c8d", font=self.fn_mono)
        self.target_display.tag_configure("mask_pending",foreground="#2e4a6e", background="#2e4a6e", font=self.fn_mono)
        self.target_display.tag_configure("mask_wrong",  foreground="#922b21", background="#922b21", font=self.fn_mono)
        self.target_display.tag_configure("mask_cursor", foreground="#ffffff", background="#e67e22", font=self.fn_mono)
        self.target_display.tag_configure("mask_hint",   foreground="#aab7c4", font=self.fn_mono)
        self.input_text.tag_configure("input_wrong",     foreground="#e74c3c", underline=True, font=self.fn_mono)

    def _auto_resize(self, widget: tk.Text, min_h: int = 2, max_h: int = 15):
        def _do():
            try:
                result = widget.count("1.0", "end", "displaylines")
                lines  = result[0] if result else min_h
                widget.configure(height=max(min_h, min(lines, max_h)))
            except Exception:
                pass
        widget.after_idle(_do)

    # ══════════════════════════════════════════════════════════════════════════
    # 파일 트리
    # ══════════════════════════════════════════════════════════════════════════

    def load_tree(self):
        self.tree.delete(*self.tree.get_children())
        self._insert_dir(self.base_dir, "")

    def _insert_dir(self, path: str, parent: str):
        try:
            entries = sorted(os.listdir(path), key=lambda x: (not os.path.isdir(os.path.join(path, x)), x.lower()))
        except PermissionError:
            return
        for name in entries:
            full = os.path.join(path, name)
            if os.path.isdir(full):
                if name in ("srs", ".srs"): continue
                node = self.tree.insert(parent, tk.END, text=f"[폴더] {name}", values=[full], tags=("folder",), open=False)
                self._insert_dir(full, node)
            elif name.lower().endswith(".csv"):
                indicator = "● " if self._has_srs(full) else ""
                self.tree.insert(parent, tk.END, text=f"{indicator}{name}", values=[full],
                                 tags=("csv_srs" if indicator else "csv",))

    def _get_selected_path(self) -> str | None:
        sel = self.tree.selection()
        return self.tree.item(sel[0])["values"][0] if sel else None

    def _get_target_dir(self) -> str:
        p = self._get_selected_path()
        if p is None: return self.base_dir
        return p if os.path.isdir(p) else os.path.dirname(p)

    def _on_tree_select(self, _e):
        p = self._get_selected_path()
        if p and os.path.isfile(p) and p.lower().endswith(".csv"):
            self._load_csv(p)

    def _on_tree_double_click(self, event):
        item = self.tree.identify_row(event.y)
        if item: self.tree.item(item, open=not self.tree.item(item, "open"))

    def _show_tree_ctx_menu(self, event):
        item = self.tree.identify_row(event.y)
        if item: self.tree.selection_set(item)
        menu = tk.Menu(self.root, tearoff=0, font=self.fn_sm)
        menu.add_command(label="폴더 추가",         command=self.create_folder)
        menu.add_command(label="CSV 새로 만들기",   command=self.create_csv_file)
        menu.add_command(label="CSV 가져오기",      command=self.import_csv)
        menu.add_separator()
        has_csv = bool(self.current_csv)
        s = tk.NORMAL if has_csv else tk.DISABLED
        menu.add_command(label="저장",              command=self._save_csv,    state=s)
        menu.add_command(label="다른 이름으로 저장", command=self.save_csv_as, state=s)
        menu.add_separator()
        menu.add_command(label="이름 변경", command=self.rename_tree_item)
        menu.add_command(label="삭제",      command=self.delete_tree_item)
        menu.tk_popup(event.x_root, event.y_root)

    # ══════════════════════════════════════════════════════════════════════════
    # 폴더 / CSV 파일 관리
    # ══════════════════════════════════════════════════════════════════════════

    def create_folder(self):
        name = self._ask_string("폴더 추가", "폴더 이름:")
        if not name: return
        try:
            os.makedirs(os.path.join(self._get_target_dir(), name), exist_ok=True)
            self.load_tree()
        except Exception as e:
            messagebox.showerror("오류", str(e))

    def create_csv_file(self):
        name = self._ask_string("CSV 만들기", "파일 이름 (.csv 자동 추가):")
        if not name: return
        if not name.lower().endswith(".csv"): name += ".csv"
        path = os.path.join(self._get_target_dir(), name)
        if os.path.exists(path):
            messagebox.showwarning("경고", "이미 같은 이름의 파일이 있습니다.")
            return
        try:
            with open(path, "w", newline="", encoding="utf-8-sig") as f:
                csv.writer(f).writerow(["text", "description", "explanation"])
            self.load_tree()
            self._load_csv(path)
        except Exception as e:
            messagebox.showerror("오류", str(e))

    def import_csv(self):
        src = filedialog.askopenfilename(
            title="가져올 CSV 선택", initialdir=self.base_dir,
            filetypes=[("CSV 파일", "*.csv"), ("모든 파일", "*.*")]
        )
        if not src: return
        dest = os.path.join(self._get_target_dir(), os.path.basename(src))
        if os.path.exists(dest) and not messagebox.askyesno("덮어쓰기", f"'{os.path.basename(dest)}' 덮어쓸까요?"):
            return
        try:
            shutil.copy2(src, dest); self.load_tree()
        except Exception as e:
            messagebox.showerror("오류", str(e))

    def rename_tree_item(self):
        path = self._get_selected_path()
        if not path: return
        old = os.path.basename(path)
        new = self._ask_string("이름 변경", "새 이름:", initialvalue=old)
        if not new or new == old: return
        new_path = os.path.join(os.path.dirname(path), new)
        try:
            os.rename(path, new_path)
            if self.current_csv == path: self.current_csv = new_path
            self.load_tree()
        except Exception as e:
            messagebox.showerror("오류", str(e))

    def delete_tree_item(self):
        path = self._get_selected_path()
        if not path:
            messagebox.showinfo("안내", "삭제할 항목을 선택하세요.")
            return
        kind = "폴더(내용 포함)" if os.path.isdir(path) else "파일"
        if not messagebox.askyesno("삭제 확인", f"{kind} '{os.path.basename(path)}' 삭제할까요?"):
            return
        try:
            shutil.rmtree(path) if os.path.isdir(path) else os.remove(path)
            if self.current_csv == path: self._clear_all()
            self.load_tree()
        except Exception as e:
            messagebox.showerror("오류", str(e))

    # ══════════════════════════════════════════════════════════════════════════
    # CSV 읽기 / 쓰기
    # ══════════════════════════════════════════════════════════════════════════

    def _load_csv(self, path: str):
        try:
            data: list[tuple[str, str, str]] = []
            with open(path, newline="", encoding="utf-8-sig") as f:
                reader = csv.reader(f)
                header = next(reader, None)
                text_col, desc_col, expl_col = 0, 1, -1
                has_desc, has_expl = False, False
                if header:
                    low = [h.strip().lower() for h in header]
                    text_col = low.index("text") if "text" in low else 0
                    for alias in ("description", "설명", "desc"):
                        if alias in low:
                            desc_col = low.index(alias); has_desc = True; break
                    for alias in ("explanation", "해석", "expl"):
                        if alias in low:
                            expl_col = low.index(alias); has_expl = True; break
                for row in reader:
                    if not row or len(row) <= text_col: continue
                    text = row[text_col].strip()
                    if not text: continue
                    desc = row[desc_col].strip() if has_desc and len(row) > desc_col else ""
                    expl = row[expl_col].strip() if has_expl and len(row) > expl_col else ""
                    data.append((text, desc, expl))

            self.current_csv = path
            self.sentence_data = data
            self.memorized_indices = set()
            self._load_srs()
            fname = os.path.basename(path)
            self._csv_lbl.config(text=fname, fg="#2c3e50")
            self._sent_win.title(f"문장 목록 — {fname}")
            self._stat_file_lbl.config(text=fname)
            self._refresh_sent_tree()
            # 암기 최적화: 복습 카드가 있으면 복습 모드로 자동 전환
            self._auto_select_mode()
            self._build_practice_indices()
            self.reset_current()
            self._update_stat_bar()
        except Exception as e:
            messagebox.showerror("오류", f"CSV 읽기 실패:\n{e}")

    def _auto_select_mode(self):
        """복습할 카드가 있으면 복습 모드, 없으면 가리기 모드로 자동 전환."""
        today = date.today().isoformat()
        review_count = sum(
            1 for i in range(len(self.sentence_data))
            if i not in self.memorized_indices
            and self._get_srs(self.sentence_data[i][0])["next_review"] <= today
        )
        if review_count > 0:
            self.typing_mode.set("복습")
        else:
            self.typing_mode.set("가리기")

    def _write_csv(self, path: str):
        with open(path, "w", newline="", encoding="utf-8-sig") as f:
            w = csv.writer(f)
            w.writerow(["text", "description", "explanation"])
            for row in self.sentence_data:
                text = row[0]
                desc = row[1] if len(row) > 1 else ""
                expl = row[2] if len(row) > 2 else ""
                w.writerow([text, desc, expl])

    def _save_csv(self):
        if not self.current_csv: return
        try:
            self._write_csv(self.current_csv)
        except Exception as e:
            messagebox.showerror("저장 오류", str(e))

    def save_csv_as(self):
        if not self.current_csv: return
        dest = filedialog.asksaveasfilename(
            title="다른 이름으로 저장",
            initialdir=os.path.dirname(self.current_csv),
            initialfile=os.path.basename(self.current_csv),
            defaultextension=".csv",
            filetypes=[("CSV 파일", "*.csv"), ("모든 파일", "*.*")],
            parent=self._tree_win
        )
        if not dest: return
        try:
            self._write_csv(dest)
            self.current_csv = dest
            self.load_tree()
            fname = os.path.basename(dest)
            self._csv_lbl.config(text=fname, fg="#2c3e50")
            self._sent_win.title(f"문장 목록 — {fname}")
            messagebox.showinfo("저장 완료", f"'{fname}' 저장했습니다.", parent=self._tree_win)
        except Exception as e:
            messagebox.showerror("저장 오류", str(e), parent=self._tree_win)

    # ══════════════════════════════════════════════════════════════════════════
    # 문장 목록 CRUD
    # ══════════════════════════════════════════════════════════════════════════

    def _srs_label(self, text: str) -> str:
        entry = self.srs_data.get(text)
        if not entry or entry.get("reps", 0) == 0: return ""
        r = entry.get("last_rating", -1)
        if r == 3:  return "쉬움"
        if r == 2:  return "보통"
        if r <= 1:  return "어려움"
        return ""

    def _refresh_sent_tree(self):
        self.sent_tree.delete(*self.sent_tree.get_children())
        self.sent_tree.insert("", tk.END, iid="hdr_active",
                              values=("","  미암기 문장",""), tags=("hdr",))
        active = [i for i in range(len(self.sentence_data)) if i not in self.memorized_indices]
        for i in active:
            text, desc, *_ = self.sentence_data[i]
            content = f"  {i+1:>3}.  {text}"
            if desc:
                short = desc if len(desc) <= 30 else desc[:27] + "…"
                content += f"   # {short}"
            self.sent_tree.insert("", tk.END, iid=f"r_{i}",
                                  values=("[ ]", content, self._srs_label(text)), tags=("normal",))
        if not active:
            self.sent_tree.insert("", tk.END, iid="empty_active",
                                  values=("","    (없음)",""), tags=("empty",))
        self.sent_tree.insert("", tk.END, iid="hdr_done",
                              values=("","  암기 완료",""), tags=("hdr",))
        done = [i for i in range(len(self.sentence_data)) if i in self.memorized_indices]
        for i in done:
            text, desc, *_ = self.sentence_data[i]
            content = f"  {i+1:>3}.  {text}"
            if desc:
                short = desc if len(desc) <= 30 else desc[:27] + "…"
                content += f"   # {short}"
            self.sent_tree.insert("", tk.END, iid=f"r_{i}",
                                  values=("[v]", content, self._srs_label(text)), tags=("memorized",))
        if not done:
            self.sent_tree.insert("", tk.END, iid="empty_done",
                                  values=("","    (없음)",""), tags=("empty",))
        self._apply_search()
        if hasattr(self, "_inline_idx") and self._inline_idx is not None:
            if self._inline_idx >= len(self.sentence_data):
                self._hide_inline_edit()

    def _on_sentence_select(self, _e):
        sel = self.sent_tree.selection()
        if not sel: return
        iid = sel[0]
        if not iid.startswith("r_"):
            self._hide_inline_edit(); return
        data_idx = int(iid[2:])
        if self.sentence_data:
            self._show_inline_edit(data_idx)
        if not self.practice_indices: return
        try:
            self.current_index = self.practice_indices.index(data_idx)
            self.reset_current()
        except ValueError:
            pass

    def _inline_auto_h(self, widget: tk.Text, min_h: int = 1, max_h: int = 6):
        def _do():
            try:
                result = widget.count("1.0", "end", "displaylines")
                lines  = result[0] if result else min_h
                widget.configure(height=max(min_h, min(lines, max_h)))
            except Exception:
                pass
        widget.after_idle(_do)

    def _show_inline_edit(self, data_idx: int):
        row = self.sentence_data[data_idx]
        text = row[0]; desc = row[1] if len(row) > 1 else ""; expl = row[2] if len(row) > 2 else ""
        self._inline_idx = data_idx
        self._inline_txt.delete("1.0", tk.END);  self._inline_txt.insert("1.0", text)
        self._inline_desc.delete("1.0", tk.END); self._inline_desc.insert("1.0", desc)
        self._inline_expl.delete("1.0", tk.END); self._inline_expl.insert("1.0", expl)
        self._inline_auto_h(self._inline_txt)
        self._inline_auto_h(self._inline_desc)
        self._inline_auto_h(self._inline_expl)
        if not self._inline_visible:
            self._paned.add(self._inline_frame, weight=1)
            self._inline_visible = True

    def _hide_inline_edit(self):
        if self._inline_visible:
            self._paned.forget(self._inline_frame)
            self._inline_visible = False
        self._inline_idx = None

    def _save_inline_edit(self):
        if self._inline_idx is None: return
        text = self._inline_txt.get("1.0", tk.END).strip()
        desc = self._inline_desc.get("1.0", tk.END).strip()
        expl = self._inline_expl.get("1.0", tk.END).strip()
        if not text:
            messagebox.showwarning("경고", "문장을 입력하세요.", parent=self._sent_win); return
        idx = self._inline_idx
        old_text = self.sentence_data[idx][0]
        self.sentence_data[idx] = (text, desc, expl)
        self._transfer_srs(old_text, text)
        self._save_csv(); self._refresh_sent_tree(); self.reset_current()
        iid = f"r_{idx}"
        if self.sent_tree.exists(iid):
            self.sent_tree.selection_set(iid); self.sent_tree.see(iid)

    def add_sentence(self):
        if not self.current_csv:
            messagebox.showinfo("안내", "먼저 파일 관리에서 CSV 파일을 선택하거나 만드세요."); return
        dlg = SentenceDialog(self.root, "문장 추가", font_size=self._font_size)
        if dlg.result:
            self.sentence_data.append(dlg.result)
            self._save_csv(); self._refresh_sent_tree()
            new_idx = len(self.sentence_data) - 1
            self._build_practice_indices()
            try: self.current_index = self.practice_indices.index(new_idx)
            except ValueError: self.current_index = 0
            self.reset_current()

    def edit_sentence(self, iid: str | None = None):
        if iid is None:
            sel = self.sent_tree.selection(); iid = sel[0] if sel else None
        if not iid or not iid.startswith("r_"):
            messagebox.showinfo("안내", "수정할 문장 항목을 선택하세요."); return
        idx = int(iid[2:])
        row = self.sentence_data[idx]
        text = row[0]; desc = row[1] if len(row) > 1 else ""; expl = row[2] if len(row) > 2 else ""
        dlg = SentenceDialog(self.root, "문장 수정", text, desc, expl, font_size=self._font_size)
        if dlg.result:
            old_text = self.sentence_data[idx][0]
            self.sentence_data[idx] = dlg.result
            self._transfer_srs(old_text, dlg.result[0])
            self._save_csv(); self._refresh_sent_tree(); self.reset_current()

    def delete_sentence(self):
        sel = self.sent_tree.selection()
        if not sel: messagebox.showinfo("안내", "삭제할 항목을 선택하세요."); return
        iid = sel[0]
        if not iid.startswith("r_"): messagebox.showinfo("안내", "삭제할 문장 항목을 선택하세요."); return
        idx = int(iid[2:])
        preview = self.sentence_data[idx][0]
        preview = preview if len(preview) <= 40 else preview[:37] + "…"
        if not messagebox.askyesno("삭제 확인", f"삭제할까요?\n\"{preview}\""): return
        self.sentence_data.pop(idx)
        self.memorized_indices = {(i-1 if i > idx else i) for i in self.memorized_indices if i != idx}
        self._save_csv(); self._refresh_sent_tree(); self._build_practice_indices()
        self.current_index = min(self.current_index, max(len(self.practice_indices)-1, 0))
        if self.practice_indices: self.reset_current()
        else: self._clear_practice_area()

    # ══════════════════════════════════════════════════════════════════════════
    # 연습 순서 / 랜덤
    # ══════════════════════════════════════════════════════════════════════════

    def _build_practice_indices(self):
        if self.typing_mode.get() == "복습":
            today = date.today().isoformat()
            indices = [
                i for i in range(len(self.sentence_data))
                if i not in self.memorized_indices
                and self._get_srs(self.sentence_data[i][0])["next_review"] <= today
            ]
        else:
            indices = [
                i for i in range(len(self.sentence_data)) if i not in self.memorized_indices
            ]

        # 난이도 미표시(미평가) 문장을 앞으로
        def _is_unrated(i: int) -> bool:
            entry = self.srs_data.get(self.sentence_data[i][0])
            return not entry or entry.get("reps", 0) == 0

        unrated = [i for i in indices if     _is_unrated(i)]
        rated   = [i for i in indices if not _is_unrated(i)]

        if self.random_var.get():
            random.shuffle(unrated)
            random.shuffle(rated)

        self.practice_indices = unrated + rated
        self.current_index = 0

    def _toggle_random(self):
        self._build_practice_indices()
        if self.practice_indices: self.reset_current()

    def _switch_to_review(self):
        """통계 바의 복습 카운터 클릭 → 복습 모드 전환."""
        self.typing_mode.set("복습")
        self._on_mode_change()

    def _update_stat_bar(self):
        """상단 통계 바 갱신."""
        total  = len(self.sentence_data)
        mem    = len(self.memorized_indices)
        today  = date.today().isoformat()
        review_due = sum(
            1 for i in range(total)
            if i not in self.memorized_indices
            and self._get_srs(self.sentence_data[i][0])["next_review"] <= today
        )
        self._stat_review_lbl.config(
            text=f"📅 복습 {review_due}",
            fg="#f5a623" if review_due > 0 else "#5d6d7e"
        )
        self._stat_mem_lbl.config(text=f"암기완료 {mem} / {total}")

    # ══════════════════════════════════════════════════════════════════════════
    # 연습 영역
    # ══════════════════════════════════════════════════════════════════════════

    def restart_all(self):
        if not self.sentence_data: return
        self._build_practice_indices()
        if self.practice_indices: self.reset_current()

    def _refresh_input_highlight(self, typed: str):
        target = self._cur_text()
        self.input_text.tag_remove("input_wrong", "1.0", tk.END)
        for i, ch in enumerate(typed):
            if i >= len(target) or ch != target[i]:
                pos = f"1.{i}"
                self.input_text.tag_add("input_wrong", pos, f"{pos}+1c")

    def reset_current(self):
        self.input_text.delete("1.0", tk.END)
        self.input_text.configure(height=2)
        self.is_typing       = False
        self.completed       = False
        self._hidden_revealed = False
        self._update_mask_buttons()
        self._hide_banner()
        self._update_counter()
        self._refresh_target("")
        # 암기 최적화: 가리기/복습 모드에서는 해석 항상 표시
        mode = self.typing_mode.get()
        if mode in ("가리기", "복습"):
            self._update_desc_display()
        else:
            self._hide_desc()
            self._hide_explanation()
        self.input_text.focus_set()

    def _clear_all(self):
        self.current_csv      = None
        self.sentence_data    = []
        self.practice_indices = []
        self.srs_data         = {}
        self._csv_lbl.config(text="파일 관리에서 CSV를 선택하세요", fg="#555")
        self._sent_win.title("문장 목록")
        self._stat_file_lbl.config(text="파일 없음")
        self._refresh_sent_tree()
        self._clear_practice_area()
        self._update_stat_bar()

    def _clear_practice_area(self):
        self.target_display.config(state=tk.NORMAL)
        self.target_display.delete("1.0", tk.END)
        self.target_display.config(state=tk.DISABLED)
        self.input_text.delete("1.0", tk.END)
        self._counter_lbl.config(text="0 / 0")
        self._hide_banner(); self._hide_desc(); self._hide_explanation()

    def _update_counter(self):
        total  = len(self.practice_indices)
        cur    = (self.current_index + 1) if total > 0 else 0
        prefix = "📅 " if self.typing_mode.get() == "복습" else ""
        self._counter_lbl.config(text=f"{prefix}{cur} / {total}")

    # ── 배너 / 설명 show·hide ─────────────────────────────────────────────────

    def _show_banner(self):
        if not self._banner_visible:
            self._banner_frame.pack(fill=tk.X, padx=12, pady=(2,2))
            self._banner_visible = True

    def _hide_banner(self):
        if self._banner_visible:
            self._banner_frame.pack_forget()
            self._banner_visible = False

    def _show_desc(self, text: str):
        self._desc_lbl.config(text=text)
        if not self._desc_visible:
            self._desc_frame.pack(fill=tk.X, padx=12, pady=(4,2))
            self._desc_visible = True

    def _hide_desc(self):
        if self._desc_visible:
            self._desc_frame.pack_forget()
            self._desc_visible = False

    def _copy_desc(self):
        text = self._desc_lbl.cget("text")
        if text:
            self.root.clipboard_clear(); self.root.clipboard_append(text)
            self._desc_copy_btn.config(text="✓ 복사됨")
            self.root.after(1500, lambda: self._desc_copy_btn.config(text="복사"))

    def _copy_explanation(self):
        text = self._explanation_lbl.cget("text")
        if text:
            self.root.clipboard_clear(); self.root.clipboard_append(text)
            self._expl_copy_btn.config(text="✓ 복사됨")
            self.root.after(1500, lambda: self._expl_copy_btn.config(text="복사"))

    def _show_explanation(self, text: str):
        self._explanation_lbl.config(text=text)
        if not self._explanation_visible:
            self._explanation_frame.pack(fill=tk.X, padx=12, pady=(2,2))
            self._explanation_visible = True

    def _hide_explanation(self):
        if self._explanation_visible:
            self._explanation_frame.pack_forget()
            self._explanation_visible = False

    def _update_desc_display(self):
        desc = self._cur_desc()
        if desc: self._show_desc(desc)
        else:    self._hide_desc()
        expl = self._cur_explanation()
        if expl: self._show_explanation(expl)
        else:    self._hide_explanation()

    # ── 연습 문장 렌더링 ──────────────────────────────────────────────────────

    def _on_mode_change(self):
        self._mask_style = "full"   # 모드 변경 시 전체 가리기로 초기화
        self._update_mask_buttons()
        mode = self.typing_mode.get()
        self._build_practice_indices()
        if not self.practice_indices:
            self._clear_practice_area()
            if mode == "복습" and self.sentence_data:
                messagebox.showinfo("복습 완료", "오늘 복습할 문장이 없습니다.\n내일 다시 확인하세요!")
            return
        self.reset_current()
        self._update_stat_bar()

    def _refresh_target(self, typed: str):
        if not self.practice_indices: return
        target = self._cur_text()
        mode   = self.typing_mode.get()

        self.target_display.config(state=tk.NORMAL)
        self.target_display.delete("1.0", tk.END)

        if mode in ("가리기", "복습"):
            def _is_word_start(text: str, i: int) -> bool:
                return (i == 0 and text[i] != " ") or (i > 0 and text[i-1] == " " and text[i] != " ")

            mask  = self._mask_style
            BLOCK = "▮"

            if mask == "full":
                for ch in target:
                    if ch == " ": self.target_display.insert(tk.END, " ")
                    else:         self.target_display.insert(tk.END, BLOCK, "mask_pending")

            elif mask == "first":
                for i, ch in enumerate(target):
                    if ch == " ": self.target_display.insert(tk.END, " "); continue
                    hint = _is_word_start(target, i)
                    if i < len(typed):
                        if typed[i] == ch: self.target_display.insert(tk.END, ch,    "correct")
                        else:              self.target_display.insert(tk.END, BLOCK,  "mask_wrong")
                    elif i == len(typed):
                        self.target_display.insert(tk.END, ch if hint else BLOCK, "mask_cursor")
                    else:
                        if hint: self.target_display.insert(tk.END, ch,    "mask_hint")
                        else:    self.target_display.insert(tk.END, BLOCK, "mask_pending")

            else:  # block
                for i, ch in enumerate(target):
                    if ch == " ": self.target_display.insert(tk.END, " "); continue
                    if i < len(typed):
                        if typed[i] == ch: self.target_display.insert(tk.END, ch,    "correct")
                        else:              self.target_display.insert(tk.END, BLOCK,  "mask_wrong")
                    elif i == len(typed):
                        self.target_display.insert(tk.END, BLOCK, "mask_cursor")
                    else:
                        self.target_display.insert(tk.END, BLOCK, "mask_pending")

        else:  # 기본
            for i, ch in enumerate(target):
                if i < len(typed):   tag = "correct" if typed[i] == ch else "wrong"
                elif i == len(typed): tag = "cursor_pos"
                else:                 tag = "pending"
                self.target_display.insert(tk.END, ch, tag)

        self.target_display.config(state=tk.DISABLED)
        self._auto_resize(self.target_display)

    # ── 입력 이벤트 ───────────────────────────────────────────────────────────

    def _handle_enter(self, _e):
        mode = self.typing_mode.get()
        if mode in ("가리기", "복습") and self.practice_indices:
            if self.completed or self._hidden_revealed:
                self._rate_and_next(2)
        elif self.completed:
            self.next_sentence()
        return "break"

    def _handle_up(self, _e):
        if self.typing_mode.get() not in ("가리기", "복습") or not self.practice_indices:
            return "break"
        if self.completed: return "break"
        self._toggle_reveal()
        return "break"

    def _toggle_reveal(self):
        """가리기 모드 정답 공개/숨김 토글 (단축키 연결용)."""
        if not self.practice_indices: return
        if self.typing_mode.get() not in ("가리기", "복습"): return
        if self.completed: return
        if self._hidden_revealed: self._hide_revealed()
        else:                     self._reveal_hidden()

    def _reveal_hidden(self):
        target = self._cur_text()
        self.target_display.config(state=tk.NORMAL)
        self.target_display.delete("1.0", tk.END)
        self.target_display.insert(tk.END, target, "pending")
        self.target_display.config(state=tk.DISABLED)
        self._hidden_revealed = True
        self._update_desc_display()

    def _hide_revealed(self):
        typed = self.input_text.get("1.0", tk.END).rstrip("\n")
        self._hidden_revealed = False
        self._refresh_target(typed)

    def _update_mask_buttons(self):
        first_active = self._mask_style == "first"
        full_active  = self._mask_style == "full"
        self._mask_btn_first.config(
            bg="#8e44ad" if first_active else "#dfe6e9",
            fg="white"   if first_active else "#2c3e50")
        self._mask_btn_full.config(
            bg="#8e44ad" if full_active  else "#dfe6e9",
            fg="white"   if full_active  else "#2c3e50")

    def _toggle_mask(self, style: str):
        self._mask_style = "block" if self._mask_style == style else style
        self._update_mask_buttons()
        typed = self.input_text.get("1.0", tk.END).rstrip("\n")
        self._refresh_target(typed)

    def _on_key_release(self, event):
        _SKIP = {"Return","Shift_L","Shift_R","Control_L","Control_R",
                 "Alt_L","Alt_R","Up","Down","Left","Right","Caps_Lock"}
        if event.keysym in _SKIP or not self.practice_indices:
            return
        typed = self.input_text.get("1.0", tk.END).rstrip("\n")
        if typed and not self.is_typing:
            self.is_typing = True
        self._refresh_target(typed)
        self._refresh_input_highlight(typed)
        self._check_completion(typed)
        self._auto_resize(self.input_text)

    def _check_completion(self, typed: str):
        if typed == self._cur_text() and not self.completed:
            self.completed = True
            mode = self.typing_mode.get()
            if mode in ("가리기", "복습"):
                self._show_banner()
            # 완료 시 정답 텍스트 공개 (암기 확인)
            self.target_display.config(state=tk.NORMAL)
            self.target_display.delete("1.0", tk.END)
            self.target_display.insert(tk.END, self._cur_text(), "correct")
            self.target_display.config(state=tk.DISABLED)
            self._update_desc_display()

    # ── 네비게이션 ────────────────────────────────────────────────────────────

    def memorize_current(self):
        if not self.practice_indices: return
        data_idx = self.practice_indices[self.current_index]
        self.memorized_indices.add(data_idx)
        self._refresh_sent_tree(); self._build_practice_indices()
        if not self.practice_indices:
            self._clear_practice_area()
            messagebox.showinfo("완료", "모든 문장을 암기 완료했습니다!")
            return
        self.current_index = min(self.current_index, len(self.practice_indices)-1)
        self.reset_current(); self._update_stat_bar()

    def next_sentence(self, _e=None):
        if not self.practice_indices: return
        if self.current_index < len(self.practice_indices) - 1:
            self.current_index += 1; self.reset_current()
        else:
            if self.typing_mode.get() == "복습":
                messagebox.showinfo("복습 완료", "오늘의 복습을 완료했습니다!")
            else:
                messagebox.showinfo("완료", "모든 문장을 완료했습니다!")

    def prev_sentence(self):
        if self.practice_indices and self.current_index > 0:
            self.current_index -= 1; self.reset_current()

    def _toggle_memorize_item(self, data_idx: int):
        if data_idx in self.memorized_indices: self.memorized_indices.discard(data_idx)
        else:                                  self.memorized_indices.add(data_idx)
        self._refresh_sent_tree(); self._build_practice_indices()
        if self.practice_indices:
            self.current_index = min(self.current_index, len(self.practice_indices)-1)
            self.reset_current()
        else:
            self._clear_practice_area()
        self._update_stat_bar()

    # ── 드래그 앤 드롭 (문장 순서 변경) ─────────────────────────────────────

    def _drag_start(self, event):
        item = self.sent_tree.identify_row(event.y)
        self._drag_source  = item if (item and item.startswith("r_")) else None
        self._drag_start_y = event.y; self._drag_moved = False

    def _drag_motion(self, event):
        if not self._drag_source: return
        if abs(event.y - self._drag_start_y) > 6: self._drag_moved = True
        if self._drag_moved:
            target = self.sent_tree.identify_row(event.y)
            for iid in self.sent_tree.get_children():
                tags = [t for t in self.sent_tree.item(iid,"tags") if t != "drag_over"]
                self.sent_tree.item(iid, tags=tags)
            if target and target != self._drag_source:
                cur_tags = list(self.sent_tree.item(target,"tags"))
                cur_tags.append("drag_over")
                self.sent_tree.item(target, tags=cur_tags)

    def _drag_end(self, event):
        if not self._drag_source: return
        for iid in self.sent_tree.get_children():
            tags = [t for t in self.sent_tree.item(iid,"tags") if t != "drag_over"]
            self.sent_tree.item(iid, tags=tags)
        target = self.sent_tree.identify_row(event.y)
        if self._drag_moved and target and target != self._drag_source:
            if target.startswith("r_"):
                from_idx = int(self._drag_source[2:]); to_idx = int(target[2:])
                from_mem = from_idx in self.memorized_indices
                to_mem   = to_idx   in self.memorized_indices
                if from_mem == to_mem: self._reorder_data(from_idx, to_idx)
        elif not self._drag_moved:
            col = self.sent_tree.identify_column(event.x)
            if col == "#1": self._toggle_memorize_item(int(self._drag_source[2:]))
        self._drag_source = None; self._drag_moved = False

    def _reorder_data(self, from_idx: int, to_idx: int):
        item = self.sentence_data.pop(from_idx)
        insert_at = to_idx - 1 if from_idx < to_idx else to_idx
        self.sentence_data.insert(insert_at, item)
        new_mem: set[int] = set()
        for idx in self.memorized_indices:
            if idx == from_idx:                           new_mem.add(insert_at)
            elif from_idx < insert_at and from_idx < idx <= insert_at: new_mem.add(idx-1)
            elif insert_at < from_idx and insert_at <= idx < from_idx: new_mem.add(idx+1)
            else:                                         new_mem.add(idx)
        self.memorized_indices = new_mem
        self._save_csv(); self._refresh_sent_tree(); self._build_practice_indices()
        if self.practice_indices: self.reset_current()

    def _edit_current_sentence(self):
        if not self.current_csv:
            messagebox.showinfo("안내", "먼저 파일 관리에서 CSV 파일을 선택하세요."); return
        if not self.practice_indices:
            messagebox.showinfo("안내", "연습할 문장이 없습니다."); return
        data_idx = self.practice_indices[self.current_index]
        row  = self.sentence_data[data_idx]
        text = row[0]; desc = row[1] if len(row)>1 else ""; expl = row[2] if len(row)>2 else ""
        dlg = SentenceDialog(self.root, "현재 문장 편집", text, desc, expl, font_size=self._font_size)
        if dlg.result:
            self._transfer_srs(text, dlg.result[0])
            self.sentence_data[data_idx] = dlg.result
            self._save_csv(); self._refresh_sent_tree(); self.reset_current()
            if self.typing_mode.get() in ("가리기", "복습"):
                self._update_desc_display()

    # ── 검색 ─────────────────────────────────────────────────────────────────

    def _apply_search(self):
        if not hasattr(self, "_search_var"): return
        query = self._search_var.get().strip().lower()
        for iid in self.sent_tree.get_children():
            if not iid.startswith("r_"): continue
            data_idx = int(iid[2:])
            text, desc, *_ = self.sentence_data[data_idx]
            is_match = bool(query) and (query in text.lower() or query in desc.lower())
            cur_tags = [t for t in self.sent_tree.item(iid,"tags") if t != "search_match"]
            if is_match: cur_tags.append("search_match")
            self.sent_tree.item(iid, tags=cur_tags)

    # ── 커스텀 입력 다이얼로그 ────────────────────────────────────────────────

    def _ask_string(self, title: str, prompt: str, initialvalue: str = "") -> str | None:
        result = [None]
        dlg = tk.Toplevel(self.root)
        dlg.title(title); dlg.resizable(False, False)
        dlg.transient(self.root); dlg.grab_set()
        dlg.configure(bg="#f0f2f5")
        tk.Label(dlg, text=prompt, bg="#f0f2f5", font=self.fn_sm, anchor="w").pack(fill=tk.X, padx=20, pady=(18,6))
        entry = tk.Entry(dlg, font=self.fn_sm, relief=tk.SOLID, bd=1)
        entry.pack(fill=tk.X, padx=20, pady=(0,14))
        entry.insert(0, initialvalue); entry.select_range(0, tk.END); entry.focus_set()
        bf = tk.Frame(dlg, bg="#f0f2f5"); bf.pack(pady=(0,16))
        _b = dict(font=self.fn_sm, relief=tk.FLAT, padx=18, pady=6, cursor="hand2")
        def ok(_e=None): result[0] = entry.get(); dlg.destroy()
        def cancel(_e=None): dlg.destroy()
        tk.Button(bf, text="확인", command=ok,     bg="#3498db", fg="white", **_b).pack(side=tk.LEFT, padx=6)
        tk.Button(bf, text="취소", command=cancel, bg="#95a5a6", fg="white", **_b).pack(side=tk.LEFT)
        dlg.bind("<Return>", ok); dlg.bind("<Escape>", cancel)
        dlg.update_idletasks(); dlg.geometry("")
        self.root.wait_window(dlg)
        return result[0]

    # ══════════════════════════════════════════════════════════════════════════
    # SRS (SM-2)
    # ══════════════════════════════════════════════════════════════════════════

    def _srs_path(self) -> str | None:
        if not self.current_csv: return None
        custom = self.srs_custom_paths.get(self.current_csv)
        if custom: return custom
        srs_dir = os.path.join(os.path.dirname(self.current_csv), "srs")
        os.makedirs(srs_dir, exist_ok=True)
        name = os.path.splitext(os.path.basename(self.current_csv))[0] + ".json"
        return os.path.join(srs_dir, name)

    def _has_srs(self, csv_path: str) -> bool:
        custom = self.srs_custom_paths.get(csv_path)
        if custom: return os.path.exists(custom)
        auto = os.path.join(os.path.dirname(csv_path), "srs",
                            os.path.splitext(os.path.basename(csv_path))[0] + ".json")
        return os.path.exists(auto)

    def _load_srs(self):
        path = self._srs_path()
        if not path: self.srs_data = {}; return
        if self.current_csv and not os.path.exists(path):
            csv_dir = os.path.dirname(self.current_csv)
            base    = os.path.splitext(os.path.basename(self.current_csv))[0]
            for old in (os.path.join(csv_dir, base+".srs.json"),
                        os.path.join(csv_dir, ".srs", base+".json")):
                if os.path.exists(old):
                    os.makedirs(os.path.dirname(path), exist_ok=True)
                    shutil.move(old, path); break
        if os.path.exists(path):
            try:
                with open(path, "r", encoding="utf-8") as f:
                    self.srs_data = json.load(f)
            except Exception:
                self.srs_data = {}
        else:
            self.srs_data = {}

    def _save_srs(self):
        path = self._srs_path()
        if not path: return
        existed = os.path.exists(path)
        try:
            with open(path, "w", encoding="utf-8") as f:
                json.dump(self.srs_data, f, ensure_ascii=False, indent=2)
        except Exception:
            pass
        if not existed: self.load_tree()

    def _transfer_srs(self, old_text: str, new_text: str):
        if old_text != new_text and old_text in self.srs_data:
            self.srs_data[new_text] = self.srs_data.pop(old_text)
            self._save_srs()

    def _get_srs(self, text: str) -> dict:
        if text not in self.srs_data:
            self.srs_data[text] = {
                "interval":    1,
                "ease_factor": 2.5,
                "next_review": date.today().isoformat(),
                "reps":        0,
            }
        return self.srs_data[text]

    def _apply_sm2(self, entry: dict, rating: int) -> dict:
        ef = entry["ease_factor"]; ivl = entry["interval"]; reps = entry["reps"]
        if rating == 0:
            ivl = 1; ef = max(1.3, ef - 0.20); reps = 0
        elif rating == 1:
            ivl = max(1, round(ivl * 1.2)); ef = max(1.3, ef - 0.15); reps += 1
        elif rating == 2:
            if reps == 0:   ivl = 1
            elif reps == 1: ivl = 3
            else:           ivl = max(1, round(ivl * ef))
            reps += 1
        else:
            if reps == 0:   ivl = 4
            elif reps == 1: ivl = 5
            else:           ivl = max(1, round(ivl * ef * 1.3))
            ef = min(3.5, ef + 0.15); reps += 1
        return {
            "interval":    ivl,
            "ease_factor": round(ef, 2),
            "next_review": (date.today() + timedelta(days=ivl)).isoformat(),
            "reps":        reps,
            "last_rating": rating,
        }

    def _rate_and_next(self, rating: int):
        if not self.practice_indices: return
        text = self._cur_text()
        self.srs_data[text] = self._apply_sm2(self._get_srs(text), rating)
        self._save_srs(); self._refresh_sent_tree(); self._update_stat_bar()
        if rating == 0: self.reset_current()
        else:           self.next_sentence()


# ══════════════════════════════════════════════════════════════════════════════
class SentenceDialog:
# ══════════════════════════════════════════════════════════════════════════════

    def __init__(self, parent: tk.Misc,
                 title: str,
                 initial_text: str = "",
                 initial_desc: str = "",
                 initial_expl: str = "",
                 font_size: int = 15):
        self.result: tuple[str, str, str] | None = None

        dlg = tk.Toplevel(parent)
        dlg.title(title); dlg.resizable(True, True)
        dlg.minsize(600, 440); dlg.transient(parent); dlg.grab_set()
        dlg.configure(bg="#f0f2f5")

        fn    = Font(family="Malgun Gothic", size=font_size)
        fn_mo = Font(family="Monospace",     size=font_size)

        scroll_outer = tk.Frame(dlg, bg="#f0f2f5")
        scroll_outer.pack(fill=tk.BOTH, expand=True)
        dlg_vsb = ttk.Scrollbar(scroll_outer, orient="vertical")
        dlg_vsb.pack(side=tk.RIGHT, fill=tk.Y)
        dlg_canvas = tk.Canvas(scroll_outer, bg="#f0f2f5", bd=0, highlightthickness=0,
                               yscrollcommand=dlg_vsb.set)
        dlg_canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        dlg_vsb.configure(command=dlg_canvas.yview)
        content = tk.Frame(dlg_canvas, bg="#f0f2f5")
        _cwin = dlg_canvas.create_window((0,0), window=content, anchor="nw")
        content.bind("<Configure>", lambda e: dlg_canvas.configure(scrollregion=dlg_canvas.bbox("all")))
        dlg_canvas.bind("<Configure>", lambda e: dlg_canvas.itemconfig(_cwin, width=e.width))

        def auto_h(widget: tk.Text, min_h: int = 2):
            def _do():
                try:
                    result = widget.count("1.0","end","displaylines")
                    lines  = result[0] if result else min_h
                    widget.configure(height=max(min_h, lines)); dlg.update_idletasks()
                except Exception: pass
            widget.after_idle(_do)

        tk.Label(content, text="문장:", bg="#f0f2f5", font=fn).pack(anchor="w", padx=14, pady=(14,2))
        txt = tk.Text(content, height=2, font=fn_mo, wrap=tk.WORD,
                      padx=6, pady=4, bg="#1e2a38", fg="#e0e0e0",
                      insertbackground="white", undo=True)
        txt.pack(fill=tk.X, padx=14)
        txt.insert("1.0", initial_text)
        txt.bind("<KeyRelease>", lambda e: auto_h(txt))
        txt.focus_set()

        tk.Label(content, text="해석 (선택):", bg="#f0f2f5", font=fn).pack(anchor="w", padx=14, pady=(10,2))
        desc_txt = tk.Text(content, height=2, font=fn, wrap=tk.WORD,
                           padx=6, pady=4, bg="#eaf4fb", fg="#1a5276", undo=True)
        desc_txt.pack(fill=tk.X, padx=14)
        desc_txt.insert("1.0", initial_desc)
        desc_txt.bind("<KeyRelease>", lambda e: auto_h(desc_txt))

        tk.Label(content, text="설명 (선택):", bg="#f0f2f5", font=fn).pack(anchor="w", padx=14, pady=(10,2))
        expl_txt = tk.Text(content, height=2, font=fn, wrap=tk.WORD,
                           padx=6, pady=4, bg="#f0fff0", fg="#1a5226", undo=True)
        expl_txt.pack(fill=tk.X, padx=14)
        expl_txt.insert("1.0", initial_expl)
        expl_txt.bind("<KeyRelease>", lambda e: auto_h(expl_txt))

        tk.Label(content, text="Ctrl+Enter: 확인  /  Esc: 취소",
                 bg="#f0f2f5", fg="#888", font=fn).pack(anchor="e", padx=14, pady=(4,8))

        def confirm(_e=None):
            val  = txt.get("1.0", tk.END).strip()
            desc = desc_txt.get("1.0", tk.END).strip()
            expl = expl_txt.get("1.0", tk.END).strip()
            if val: self.result = (val, desc, expl); dlg.destroy()
            else: messagebox.showwarning("경고", "문장을 입력하세요.", parent=dlg)

        def cancel(_e=None): dlg.destroy()

        bf = tk.Frame(dlg, bg="#f0f2f5"); bf.pack(pady=10)
        _b = dict(font=fn, relief=tk.FLAT, padx=14, pady=4, cursor="hand2")
        tk.Button(bf, text="확인", command=confirm, bg="#3498db", fg="white", **_b).pack(side=tk.LEFT, padx=6)
        tk.Button(bf, text="취소", command=cancel,  bg="#95a5a6", fg="white", **_b).pack(side=tk.LEFT)

        txt.bind("<Control-Return>", confirm)
        dlg.bind("<Escape>", cancel)

        dlg.update()
        for _w in (txt, desc_txt, expl_txt):
            try:
                _r = _w.count("1.0","end","displaylines")
                _w.configure(height=max(2, _r[0] if _r else 2))
            except Exception: pass
        dlg.update_idletasks()
        dlg.geometry("720x660")

        parent.wait_window(dlg)


# ══════════════════════════════════════════════════════════════════════════════
if __name__ == "__main__":
    root = TkinterDnD.Tk() if HAS_DND else tk.Tk()
    app = MemorizeApp(root)
    root.mainloop()
