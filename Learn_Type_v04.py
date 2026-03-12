"""
타이핑 연습 프로그램 v4
- 좌측   : 폴더/CSV 파일 트리 (생성·삭제·가져오기·이름변경)
- 우측 상단: 문장 목록 + CRUD (추가·수정·삭제, 설명 포함)
- 우측 하단: 타이핑 연습 (오타 취소선·설명 표시·랜덤·복습 모드)
- CSV 형식: text, description 두 열
- SRS(Anki): 완료 후 난이도 평가 → .srs.json 에 복습 일정 자동 관리
"""

from __future__ import annotations
import tkinter as tk
from tkinter import ttk, filedialog, messagebox, simpledialog
from tkinter.font import Font
import csv
import time
import random
import os
import shutil
import json
from datetime import date, timedelta

try:
    from tkinterdnd2 import TkinterDnD, DND_FILES
    HAS_DND = True
except ImportError:
    HAS_DND = False

# ── 기본 저장 경로 ────────────────────────────────────────────────────────────
BASE_DIR = os.path.join(os.path.expanduser("~"), "문서", "Learn Type")


# ══════════════════════════════════════════════════════════════════════════════
class TypingPractice:
# ══════════════════════════════════════════════════════════════════════════════

    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title("TH")
        self.root.geometry("1650x930")
        self.root.configure(bg="#f0f2f5")

        os.makedirs(BASE_DIR, exist_ok=True)

        # ── 상태 변수 ──────────────────────────────────────────────────────
        self.current_csv: str | None = None
        # 각 항목: (타이핑 텍스트, 설명)
        self.sentence_data: list[tuple[str, str, str]] = []
        # 연습 순서 (sentence_data 의 인덱스 목록, 랜덤 시 섞임)
        self.practice_indices: list[int] = []
        self.current_index: int = 0

        self.srs_data: dict = {}

        self.start_time: float | None = None
        self.is_typing: bool = False
        self.completed: bool = False
        self.random_var = tk.BooleanVar(value=True)
        self.typing_mode = tk.StringVar(value="기본")
        self._hidden_revealed: bool = False
        self.memorized_indices: set[int] = set()
        self._drag_source: str | None = None
        self._drag_start_y: int = 0
        self._drag_moved: bool = False

        self._desc_visible: bool = False
        self._explanation_visible: bool = False
        self._banner_visible: bool = False

        self._setup_fonts()
        self._setup_ui()
        self._create_sentence_window()   # 문장 목록 팝업 미리 생성 (숨김 상태)
        self._create_tree_window()       # 파일 관리 팝업 미리 생성 (숨김 상태)
        self._setup_target_tags()
        self.load_tree()

    # ── 현재 항목 헬퍼 ───────────────────────────────────────────────────────

    def _cur_text(self) -> str:
        if not self.practice_indices:
            return ""
        return self.sentence_data[self.practice_indices[self.current_index]][0]

    def _cur_desc(self) -> str:
        if not self.practice_indices:
            return ""
        return self.sentence_data[self.practice_indices[self.current_index]][1]

    def _cur_explanation(self) -> str:
        if not self.practice_indices:
            return ""
        row = self.sentence_data[self.practice_indices[self.current_index]]
        return row[2] if len(row) > 2 else ""

    # ── 폰트 ─────────────────────────────────────────────────────────────────

    def _setup_fonts(self):
        self.fn_main   = Font(family="Malgun Gothic", size=22)
        self.fn_strike = Font(family="Malgun Gothic", size=22, overstrike=True)
        self.fn_sm     = Font(family="Malgun Gothic", size=22)
        self.fn_bold   = Font(family="Malgun Gothic", size=22, weight="bold")
        self.fn_title  = Font(family="Malgun Gothic", size=22, weight="bold")
        self.fn_desc   = Font(family="Malgun Gothic", size=22)
        self.fn_mono    = Font(family="Monospace", size=22)
        self.fn_mono_s  = Font(family="Monospace", size=22, overstrike=True)
        self.fn_mono_sm = Font(family="Monospace", size=22)

    # ── UI 구성 ───────────────────────────────────────────────────────────────

    def _setup_ui(self):
        top = tk.Frame(self.root, bg="#2c3e50", pady=9)
        top.pack(fill=tk.X)
        tk.Label(
            top, text="  Learn_Type  ",
            bg="#2c3e50", fg="white", font=self.fn_title
        ).pack(side=tk.LEFT, padx=14)

        main = tk.Frame(self.root, bg="#f0f2f5")
        main.pack(fill=tk.BOTH, expand=True)
        self._build_practice_panel(main)

    # ── 연습 패널 ────────────────────────────────────────────────────────────

    def _build_practice_panel(self, parent: tk.Frame):
        # 네비게이션 바
        nav = tk.Frame(parent, bg="#ecf0f1", pady=5, padx=8)
        nav.pack(fill=tk.X)
        _nb = dict(font=self.fn_sm, relief=tk.FLAT, padx=8, pady=3,
                   cursor="hand2", bg="#ecf0f1")
        tk.Button(nav, text="< 이전",      command=self.prev_sentence, **_nb).pack(side=tk.LEFT)
        self._counter_lbl = tk.Label(nav, text="0 / 0", bg="#ecf0f1", font=self.fn_sm)
        self._counter_lbl.pack(side=tk.LEFT, padx=8)
        tk.Button(nav, text="다음 >",      command=self.next_sentence, **_nb).pack(side=tk.LEFT)
        tk.Button(nav, text="다시시작",  command=self.restart_all, **_nb).pack(side=tk.LEFT, padx=4)
        tk.Button(nav, text="문장 목록", command=self._open_sentence_window, **_nb).pack(side=tk.LEFT, padx=4)
        tk.Button(nav, text="파일 관리", command=self._open_tree_window,     **_nb).pack(side=tk.LEFT, padx=4)
        tk.Button(
            nav, text="암기 완료", command=self.memorize_current,
            font=self.fn_sm, relief=tk.FLAT, padx=8, pady=3,
            cursor="hand2", bg="#27ae60", fg="white"
        ).pack(side=tk.LEFT, padx=4)
        # RIGHT 쪽은 먼저 pack 한 것이 더 오른쪽에 붙음
        self._stats_lbl = tk.Label(
            nav, text="타수: —  |  시간: —",
            bg="#ecf0f1", fg="#555", font=self.fn_sm
        )
        self._stats_lbl.pack(side=tk.RIGHT, padx=8)
        tk.Checkbutton(
            nav, text="랜덤",
            variable=self.random_var, command=self._toggle_random,
            bg="#ecf0f1", font=self.fn_sm, cursor="hand2",
            activebackground="#ecf0f1"
        ).pack(side=tk.RIGHT, padx=4)

        # ── 타이핑 모드 선택 ─────────────────────────────────────────────
        tk.Label(nav, text="모드:", bg="#ecf0f1", font=self.fn_sm).pack(side=tk.RIGHT, padx=(8, 2))
        _MODE_COLORS = {"기본": "#3498db", "가리기": "#8e44ad", "복습": "#e67e22"}
        for mode in ["기본", "가리기", "복습"]:
            tk.Radiobutton(
                nav, text=mode, variable=self.typing_mode, value=mode,
                command=self._on_mode_change,
                bg="#ecf0f1", selectcolor=_MODE_COLORS[mode],
                fg="#2c3e50", activeforeground="white",
                font=self.fn_sm, cursor="hand2",
                indicatoron=False, padx=7, pady=2,
                relief=tk.GROOVE, activebackground=_MODE_COLORS[mode],
            ).pack(side=tk.RIGHT, padx=1)

        # 연습 문장
        self._target_frame = tk.LabelFrame(
            parent, text=" 연습 문장 ", font=self.fn_bold,
            bg="#f0f2f5", padx=10, pady=8
        )
        self._target_frame.pack(fill=tk.X, padx=12, pady=(8, 2))

        self.target_display = tk.Text(
            self._target_frame, height=2, font=self.fn_mono,
            state=tk.DISABLED, wrap=tk.WORD,
            bg="#1e2a38", fg="#e0e0e0",
            relief=tk.FLAT, cursor="arrow",
            padx=8, pady=6
        )
        self.target_display.pack(fill=tk.X)

        # ── 미들 컨테이너: 설명 + 완료 배너 ─────────────────────────────────
        self._middle = tk.Frame(parent, bg="#f0f2f5")
        self._middle.pack(fill=tk.X)

        # 해석 프레임 (내부, 기본 숨김)
        self._desc_frame = tk.LabelFrame(
            self._middle, text=" 해석 ", font=self.fn_bold,
            bg="#eaf4fb", padx=10, pady=6, fg="#1a6898"
        )
        self._desc_lbl = tk.Label(
            self._desc_frame, text="",
            bg="#eaf4fb", fg="#1a5276",
            font=self.fn_desc, wraplength=1200,
            anchor="w", justify="left"
        )
        self._desc_lbl.pack(fill=tk.X)

        # 설명 프레임 (별도, 기본 숨김)
        self._explanation_frame = tk.LabelFrame(
            self._middle, text=" 설명 ", font=self.fn_bold,
            bg="#f0fff0", padx=10, pady=6, fg="#1a7a3a"
        )
        self._explanation_lbl = tk.Label(
            self._explanation_frame, text="",
            bg="#f0fff0", fg="#1a5226",
            font=self.fn_desc, wraplength=1200,
            anchor="w", justify="left"
        )
        self._explanation_lbl.pack(fill=tk.X)

        # 완료 배너 (SRS 평가 버튼 포함, 기본 숨김)
        self._banner_frame = tk.Frame(self._middle, bg="#27ae60")

        tk.Label(
            self._banner_frame, text="완료!",
            bg="#27ae60", fg="white",
            font=Font(family="Malgun Gothic", size=22, weight="bold"),
            padx=12, pady=5
        ).pack(side=tk.LEFT)

        tk.Label(
            self._banner_frame, text="Enter = 보통",
            bg="#27ae60", fg="#d5f5e3",
            font=Font(family="Malgun Gothic", size=22),
            padx=10
        ).pack(side=tk.RIGHT)

        _srs_f = tk.Frame(self._banner_frame, bg="#27ae60")
        _srs_f.pack(side=tk.LEFT, padx=4)
        for _label, _color, _rating in [
            ("다시",   "#e74c3c", 0),
            ("어려움", "#e67e22", 1),
            ("보통",   "#3498db", 2),
            ("쉬움",   "#2ecc71", 3),
        ]:
            tk.Button(
                _srs_f, text=_label,
                bg=_color, fg="white",
                font=Font(family="Malgun Gothic", size=22, weight="bold"),
                relief=tk.FLAT, padx=10, pady=3, cursor="hand2",
                command=lambda r=_rating: self._rate_and_next(r)
            ).pack(side=tk.LEFT, padx=2, pady=3)

        # 입력 영역 (target_display 와 같은 방식으로 fill=X, 자동 높이)
        self._input_frame = tk.LabelFrame(
            parent, text=" 입력 ", font=self.fn_bold,
            bg="#f0f2f5", padx=10, pady=8
        )
        self._input_frame.pack(fill=tk.X, padx=12, pady=(0, 8))

        self.input_text = tk.Text(
            self._input_frame, height=2, font=self.fn_mono,
            wrap=tk.WORD, bg="#fffef7", padx=8, pady=6,
            undo=True, maxundo=-1
        )
        self.input_text.pack(fill=tk.X)
        self.input_text.bind("<KeyRelease>", self._on_key_release)
        self.input_text.bind("<Return>",     self._handle_enter)

    # ── 문장 목록 팝업 창 ────────────────────────────────────────────────────

    def _create_sentence_window(self):
        """문장 목록 팝업을 미리 생성해 숨겨 둔다 (위젯 참조 유지용)."""
        win = tk.Toplevel(self.root)
        win.title("문장 목록")
        win.geometry("1020x840")
        win.resizable(True, True)
        win.configure(bg="#f8f9fa")
        win.protocol("WM_DELETE_WINDOW", win.withdraw)
        win.withdraw()
        self._sent_win = win

        self._inline_idx: int | None = None
        self._inline_visible: bool = False

        # 헤더
        hdr = tk.Frame(win, bg="#bdc3c7", pady=5, padx=10)
        hdr.pack(fill=tk.X)
        tk.Label(hdr, text="문장 목록", bg="#bdc3c7", font=self.fn_bold).pack(side=tk.LEFT)
        self._csv_lbl = tk.Label(
            hdr, text="파일 관리에서 CSV를 선택하세요",
            bg="#bdc3c7", fg="#555", font=self.fn_sm
        )
        self._csv_lbl.pack(side=tk.LEFT, padx=10)

        # 검색 바
        search_frame = tk.Frame(win, bg="#f0f2f5", pady=5, padx=6)
        search_frame.pack(fill=tk.X)
        tk.Label(search_frame, text="검색:", bg="#f0f2f5", font=self.fn_sm).pack(side=tk.LEFT)
        self._search_var = tk.StringVar()
        self._search_var.trace_add("write", lambda *_: self._apply_search())
        search_entry = tk.Entry(
            search_frame, textvariable=self._search_var,
            font=self.fn_sm, relief=tk.SOLID, bd=1
        )
        search_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(4, 4))
        tk.Button(
            search_frame, text="✕", command=lambda: self._search_var.set(""),
            font=self.fn_sm, relief=tk.FLAT, padx=6, cursor="hand2", bg="#f0f2f5"
        ).pack(side=tk.LEFT)

        # ── 트리뷰 + 우측 버튼 컬럼 ─────────────────────────────────────────
        outer = tk.Frame(win, bg="#f8f9fa")
        outer.pack(fill=tk.BOTH, expand=True, padx=6, pady=(4, 0))

        # 우측 버튼 컬럼 (RIGHT 먼저 pack 해야 treeview 보다 오른쪽에 위치)
        btn_col = tk.Frame(outer, bg="#f8f9fa", padx=4, pady=2)
        btn_col.pack(side=tk.RIGHT, fill=tk.Y)
        _cb = dict(font=self.fn_sm, relief=tk.FLAT, padx=10, pady=6, cursor="hand2")
        tk.Button(btn_col, text="+ 추가", command=self.add_sentence,
                  bg="#27ae60", fg="white", **_cb).pack(fill=tk.X, pady=2)
        tk.Button(btn_col, text="삭제", command=self.delete_sentence,
                  bg="#e74c3c", fg="white", **_cb).pack(fill=tk.X, pady=2)
        tk.Label(btn_col, bg="#f8f9fa").pack(fill=tk.Y, expand=True)  # spacer
        tk.Button(btn_col, text="✕ 닫기", command=win.withdraw,
                  bg="#7f8c8d", fg="white", **_cb).pack(fill=tk.X, pady=2)

        # 트리뷰 (좌측, 나머지 공간 모두 사용)
        tv_wrap = tk.Frame(outer, bg="#f8f9fa")
        tv_wrap.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        style = ttk.Style()
        style.configure("Sent.Treeview", font=self.fn_sm, rowheight=38)
        style.configure("Sent.Treeview.Heading", font=self.fn_bold)

        self.sent_tree = ttk.Treeview(
            tv_wrap, style="Sent.Treeview",
            columns=("check", "content"), show="headings",
            selectmode="browse"
        )
        self.sent_tree.heading("check",   text="암기")
        self.sent_tree.heading("content", text="문장")
        self.sent_tree.column("check",   width=55,  minwidth=55,  stretch=False, anchor="center")
        self.sent_tree.column("content", width=580, minwidth=200, stretch=True)

        self.sent_tree.tag_configure("normal",       foreground="#2c3e50")
        self.sent_tree.tag_configure("memorized",    foreground="#27ae60")
        self.sent_tree.tag_configure("hdr",          background="#dfe6e9",
                                     foreground="#555555", font=self.fn_bold)
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
        self.sent_tree.bind("<Double-1>",         self._on_sent_double_click)

        tk.Label(
            win, text="☑ 클릭으로 암기 토글  |  행을 드래그하여 같은 섹션 내 순서 변경  |  행 클릭 시 하단 수정 패널 표시",
            bg="#f8f9fa", fg="#95a5a6", font=Font(family="Malgun Gothic", size=22), pady=2
        ).pack(fill=tk.X, padx=8)

        # ── 인라인 수정 패널 (기본 숨김, 클릭 시 표시) ──────────────────────
        self._inline_frame = tk.LabelFrame(
            win, text=" ✎ 선택 문장 수정 ", font=self.fn_bold,
            bg="#fffde7", padx=8, pady=6, fg="#7d6608"
        )
        # (pack 은 _show_inline_edit 에서 호출)

        tk.Label(self._inline_frame, text="문장:", bg="#fffde7",
                 font=self.fn_sm).pack(anchor="w")
        self._inline_txt = tk.Text(
            self._inline_frame, height=2, font=self.fn_mono_sm, wrap=tk.WORD,
            padx=5, pady=3, bg="#1e2a38", fg="#e0e0e0",
            insertbackground="white", undo=True
        )
        self._inline_txt.pack(fill=tk.X, pady=(0, 4))
        self._inline_txt.bind(
            "<KeyRelease>", lambda e: self._inline_auto_h(self._inline_txt))

        tk.Label(self._inline_frame, text="해석:", bg="#fffde7",
                 font=self.fn_sm).pack(anchor="w")
        self._inline_desc = tk.Text(
            self._inline_frame, height=2, font=self.fn_sm, wrap=tk.WORD,
            padx=5, pady=3, bg="#eaf4fb", fg="#1a5276", undo=True
        )
        self._inline_desc.pack(fill=tk.X, pady=(0, 4))
        self._inline_desc.bind(
            "<KeyRelease>", lambda e: self._inline_auto_h(self._inline_desc))

        tk.Label(self._inline_frame, text="설명:", bg="#fffde7",
                 font=self.fn_sm).pack(anchor="w")
        self._inline_expl = tk.Text(
            self._inline_frame, height=2, font=self.fn_sm, wrap=tk.WORD,
            padx=5, pady=3, bg="#f0fff0", fg="#1a5226", undo=True
        )
        self._inline_expl.pack(fill=tk.X, pady=(0, 4))
        self._inline_expl.bind(
            "<KeyRelease>", lambda e: self._inline_auto_h(self._inline_expl))

        ibf = tk.Frame(self._inline_frame, bg="#fffde7")
        ibf.pack(anchor="e", pady=(0, 2))
        _ib = dict(font=self.fn_sm, relief=tk.FLAT, padx=8, pady=3, cursor="hand2")
        tk.Button(ibf, text="💾 저장", command=self._save_inline_edit,
                  bg="#27ae60", fg="white", **_ib).pack(side=tk.LEFT, padx=3)
        tk.Button(ibf, text="✕ 취소", command=self._hide_inline_edit,
                  bg="#95a5a6", fg="white", **_ib).pack(side=tk.LEFT)


    def _open_sentence_window(self):
        """문장 목록 팝업을 열거나 앞으로 가져온다."""
        if not self.current_csv:
            messagebox.showinfo("안내", "먼저 파일 관리에서 CSV 파일을 선택하세요.")
            return
        self._sent_win.deiconify()
        self._sent_win.lift()
        self._sent_win.focus_set()

    # ── 파일 관리 팝업 창 ────────────────────────────────────────────────────

    def _create_tree_window(self):
        """파일/폴더 트리 팝업을 미리 생성해 숨겨 둔다."""
        win = tk.Toplevel(self.root)
        win.title("파일 관리")
        win.geometry("450x720")
        win.resizable(True, True)
        win.configure(bg="#ecf0f1")
        win.protocol("WM_DELETE_WINDOW", win.withdraw)
        win.withdraw()
        self._tree_win = win

        tk.Label(
            win, text="  폴더 / 파일",
            bg="#bdc3c7", font=self.fn_bold, anchor="w", pady=5
        ).pack(fill=tk.X)

        wrap = tk.Frame(win, bg="#ecf0f1")
        wrap.pack(fill=tk.BOTH, expand=True, padx=4, pady=4)

        self.tree = ttk.Treeview(wrap, show="tree", selectmode="browse")
        vsb = ttk.Scrollbar(wrap, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=vsb.set)
        vsb.pack(side=tk.RIGHT, fill=tk.Y)
        self.tree.pack(fill=tk.BOTH, expand=True)

        style = ttk.Style()
        style.configure("Treeview", font=self.fn_sm, rowheight=38)
        self.tree.tag_configure("folder", foreground="#e67e22")
        self.tree.tag_configure("csv",    foreground="#2980b9")

        self.tree.tag_configure("drag_over", background="#d5e8f5")

        self.tree.bind("<<TreeviewSelect>>", self._on_tree_select)
        self.tree.bind("<Double-1>",          self._on_tree_double_click)
        self.tree.bind("<Button-3>",          self._show_tree_ctx_menu)
        self.tree.bind("<ButtonPress-1>",     self._file_drag_start)
        self.tree.bind("<B1-Motion>",         self._file_drag_motion)
        self.tree.bind("<ButtonRelease-1>",   self._file_drag_end)

        self._file_drag_source: str | None = None
        self._file_drag_start_y: int = 0
        self._file_drag_moved: bool = False

        tk.Label(
            win, text="우클릭으로 폴더·파일 관리  |  CSV를 드래그하여 폴더 이동",
            bg="#ecf0f1", fg="#95a5a6", font=Font(family="Malgun Gothic", size=22),
            pady=4
        ).pack(fill=tk.X, padx=6)

        # 드래그 앤 드롭 힌트 레이블
        _dnd_text = (
            "📂  CSV 파일을 여기에 드래그하여 가져오기"
            if HAS_DND else
            "💡  우클릭 → CSV 가져오기 로 파일 추가"
        )
        self._drop_hint = tk.Label(
            win, text=_dnd_text,
            bg="#ecf0f1", fg="#95a5a6",
            font=Font(family="Malgun Gothic", size=9),
            pady=6, relief=tk.GROOVE, bd=1
        )
        self._drop_hint.pack(fill=tk.X, padx=4, pady=(0, 4))

        if HAS_DND:
            win.drop_target_register(DND_FILES)
            win.dnd_bind('<<Drop>>',      self._on_tree_drop)
            win.dnd_bind('<<DragEnter>>', self._on_drag_enter)
            win.dnd_bind('<<DragLeave>>', self._on_drag_leave)

        tk.Button(
            win, text="✕ 닫기", command=win.withdraw,
            font=self.fn_sm, relief=tk.FLAT, padx=8, pady=3,
            cursor="hand2", bg="#bdc3c7"
        ).pack(pady=(0, 6))

    def _open_tree_window(self):
        """파일 관리 팝업을 열거나 앞으로 가져온다."""
        self._tree_win.deiconify()
        self._tree_win.lift()
        self._tree_win.focus_set()

    def _on_drag_enter(self, _event):
        """CSV 파일이 파일 관리 창 위에 드래그될 때 시각 피드백."""
        self._drop_hint.config(
            bg="#d5e8f5", fg="#2980b9",
            text="📂  여기에 놓으면 CSV를 가져옵니다!"
        )

    def _on_drag_leave(self, _event):
        """드래그가 파일 관리 창을 벗어날 때 원래 상태로 복원."""
        self._drop_hint.config(
            bg="#ecf0f1", fg="#95a5a6",
            text="📂  CSV 파일을 여기에 드래그하여 가져오기"
        )

    def _on_tree_drop(self, event):
        """파일 관리 창에 CSV 파일을 드롭했을 때 처리."""
        self._on_drag_leave(None)
        try:
            files = self.root.tk.splitlist(event.data)
        except Exception:
            files = [event.data]

        imported = 0
        for f in files:
            f = f.strip()
            if not f.lower().endswith(".csv"):
                continue
            dest_dir = self._get_target_dir()
            dest = os.path.join(dest_dir, os.path.basename(f))
            if os.path.abspath(f) == os.path.abspath(dest):
                continue
            if os.path.exists(dest) and not messagebox.askyesno(
                "덮어쓰기",
                f"'{os.path.basename(dest)}'이 이미 있습니다. 덮어쓸까요?",
                parent=self._tree_win
            ):
                continue
            try:
                shutil.copy2(f, dest)
                imported += 1
            except Exception as e:
                messagebox.showerror("오류", str(e), parent=self._tree_win)

        if imported:
            self.load_tree()
            messagebox.showinfo(
                "완료", f"{imported}개 CSV 파일을 가져왔습니다.",
                parent=self._tree_win
            )

    def _setup_target_tags(self):
        # 다크 배경 기준 색상
        self.target_display.tag_configure(
            "correct",    foreground="#2ecc71", font=self.fn_mono)
        self.target_display.tag_configure(
            "wrong",      foreground="#e74c3c", font=self.fn_mono_s)
        self.target_display.tag_configure(
            "cursor_pos", background="#2980b9", foreground="#ffffff", font=self.fn_mono)
        self.target_display.tag_configure(
            "pending",    foreground="#bdc3c7", font=self.fn_mono)

    # ── 텍스트 위젯 자동 높이 조절 ───────────────────────────────────────────

    def _auto_resize(self, widget: tk.Text, min_h: int = 2, max_h: int = 15):
        """display lines 기준으로 Text 위젯 높이를 내용에 맞게 조절한다.
        after_idle 로 예약해 위젯 레이아웃이 확정된 후 실행된다."""
        def _do():
            try:
                result = widget.count("1.0", "end", "displaylines")
                lines  = result[0] if result else min_h
                widget.configure(height=max(min_h, min(lines, max_h)))
            except Exception:
                pass
        widget.after_idle(_do)

    # ══════════════════════════════════════════════════════════════════════════
    # 파일 시스템 트리
    # ══════════════════════════════════════════════════════════════════════════

    def load_tree(self):
        self.tree.delete(*self.tree.get_children())
        self._insert_dir(BASE_DIR, "")

    def _insert_dir(self, path: str, parent: str):
        try:
            entries = sorted(
                os.listdir(path),
                key=lambda x: (not os.path.isdir(os.path.join(path, x)), x.lower())
            )
        except PermissionError:
            return
        for name in entries:
            full = os.path.join(path, name)
            if os.path.isdir(full):
                node = self.tree.insert(
                    parent, tk.END,
                    text=f"📁 {name}", values=[full],
                    tags=("folder",), open=False
                )
                self._insert_dir(full, node)
            elif name.lower().endswith(".csv"):
                self.tree.insert(
                    parent, tk.END,
                    text=f"📄 {name}", values=[full],
                    tags=("csv",)
                )

    def _get_selected_path(self) -> str | None:
        sel = self.tree.selection()
        return self.tree.item(sel[0])["values"][0] if sel else None

    def _get_target_dir(self) -> str:
        p = self._get_selected_path()
        if p is None:
            return BASE_DIR
        return p if os.path.isdir(p) else os.path.dirname(p)

    def _on_tree_select(self, _e):
        p = self._get_selected_path()
        if p and os.path.isfile(p) and p.lower().endswith(".csv"):
            self._load_csv(p)

    def _on_tree_double_click(self, event):
        item = self.tree.identify_row(event.y)
        if item:
            self.tree.item(item, open=not self.tree.item(item, "open"))

    # ── 파일 트리 내부 드래그&드롭 ────────────────────────────────────────────

    def _file_drag_start(self, event):
        item = self.tree.identify_row(event.y)
        tags = self.tree.item(item, "tags") if item else ()
        # CSV 파일만 드래그 가능
        self._file_drag_source = item if (item and "csv" in tags) else None
        self._file_drag_start_y = event.y
        self._file_drag_moved = False

    def _file_drag_motion(self, event):
        if not self._file_drag_source:
            return
        if abs(event.y - self._file_drag_start_y) > 6:
            self._file_drag_moved = True
        if not self._file_drag_moved:
            return
        # 전체 하이라이트 제거 후 현재 대상만 강조
        for iid in self.tree.get_children(""):
            self._file_tree_clear_drag_highlight(iid)
        target = self.tree.identify_row(event.y)
        if target and target != self._file_drag_source:
            tags = list(self.tree.item(target, "tags"))
            if "drag_over" not in tags:
                tags.append("drag_over")
                self.tree.item(target, tags=tags)

    def _file_tree_clear_drag_highlight(self, iid: str):
        tags = [t for t in self.tree.item(iid, "tags") if t != "drag_over"]
        self.tree.item(iid, tags=tags)
        for child in self.tree.get_children(iid):
            self._file_tree_clear_drag_highlight(child)

    def _file_drag_end(self, event):
        if not self._file_drag_source:
            return

        # 하이라이트 전체 제거
        for iid in self.tree.get_children(""):
            self._file_tree_clear_drag_highlight(iid)

        if not self._file_drag_moved:
            self._file_drag_source = None
            self._file_drag_moved = False
            return

        target = self.tree.identify_row(event.y)
        src_item = self._file_drag_source
        self._file_drag_source = None
        self._file_drag_moved = False

        if not target or target == src_item:
            return

        src_path = self.tree.item(src_item, "values")[0]
        target_path = self.tree.item(target, "values")[0]
        target_tags = self.tree.item(target, "tags")

        # 드롭 위치: 폴더면 그 안, CSV면 같은 폴더
        if "folder" in target_tags:
            dest_dir = target_path
        else:
            dest_dir = os.path.dirname(target_path)

        # 이미 같은 폴더면 취소
        if os.path.dirname(src_path) == dest_dir:
            return

        dest_path = os.path.join(dest_dir, os.path.basename(src_path))
        if os.path.exists(dest_path) and not messagebox.askyesno(
            "덮어쓰기",
            f"'{os.path.basename(dest_path)}'이 이미 있습니다. 덮어쓸까요?",
            parent=self._tree_win
        ):
            return

        try:
            shutil.move(src_path, dest_path)
            if self.current_csv == src_path:
                self.current_csv = dest_path
            self.load_tree()
        except Exception as e:
            messagebox.showerror("오류", f"이동 실패:\n{e}", parent=self._tree_win)

    def _show_tree_ctx_menu(self, event):
        item = self.tree.identify_row(event.y)
        if item:
            self.tree.selection_set(item)
        menu = tk.Menu(self.root, tearoff=0, font=self.fn_sm)
        menu.add_command(label="📁 폴더 추가",       command=self.create_folder)
        menu.add_command(label="📄 CSV 새로 만들기", command=self.create_csv_file)
        menu.add_command(label="📥 CSV 가져오기",    command=self.import_csv)
        menu.add_separator()
        # 현재 로드된 CSV가 있을 때만 저장 활성화
        has_csv = bool(self.current_csv)
        save_state = tk.NORMAL if has_csv else tk.DISABLED
        menu.add_command(label="💾 저장",              command=self._save_selected_csv,
                         state=save_state)
        menu.add_command(label="💾 다른 이름으로 저장", command=self.save_csv_as,
                         state=save_state)
        menu.add_separator()
        menu.add_command(label="✎ 이름 변경",        command=self.rename_tree_item)
        menu.add_command(label="🗑 삭제",            command=self.delete_tree_item)
        menu.tk_popup(event.x_root, event.y_root)

    # ══════════════════════════════════════════════════════════════════════════
    # 폴더 / CSV 파일 관리
    # ══════════════════════════════════════════════════════════════════════════

    def create_folder(self):
        name = simpledialog.askstring("폴더 추가", "폴더 이름:", parent=self.root)
        if not name:
            return
        try:
            os.makedirs(os.path.join(self._get_target_dir(), name), exist_ok=True)
            self.load_tree()
        except Exception as e:
            messagebox.showerror("오류", str(e))

    def create_csv_file(self):
        name = simpledialog.askstring(
            "CSV 만들기", "파일 이름 (.csv 자동 추가):", parent=self.root
        )
        if not name:
            return
        if not name.lower().endswith(".csv"):
            name += ".csv"
        path = os.path.join(self._get_target_dir(), name)
        if os.path.exists(path):
            messagebox.showwarning("경고", "이미 같은 이름의 파일이 있습니다.")
            return
        try:
            with open(path, "w", newline="", encoding="utf-8-sig") as f:
                csv.writer(f).writerow(["text", "description"])
            self.load_tree()
            self._load_csv(path)
        except Exception as e:
            messagebox.showerror("오류", str(e))

    def import_csv(self):
        """CSV 파일 가져오기 (USB 드라이브 자동 감지 포함)."""
        initial_dir = self._pick_import_dir()
        if initial_dir is None:
            return  # 취소

        src = filedialog.askopenfilename(
            title="가져올 CSV 선택",
            initialdir=initial_dir,
            filetypes=[("CSV 파일", "*.csv"), ("모든 파일", "*.*")]
        )
        if not src:
            return
        dest = os.path.join(self._get_target_dir(), os.path.basename(src))
        if os.path.exists(dest) and not messagebox.askyesno(
            "덮어쓰기", f"'{os.path.basename(dest)}'이 이미 있습니다. 덮어쓸까요?"
        ):
            return
        try:
            shutil.copy2(src, dest)
            self.load_tree()
        except Exception as e:
            messagebox.showerror("오류", str(e))

    def _detect_usb_drives(self) -> list[tuple[str, str]]:
        """마운트된 USB/외부 드라이브 목록 반환: [(표시이름, 경로), ...]"""
        import getpass
        username = getpass.getuser()
        # Ubuntu/Debian → /media/user/, Fedora/Arch → /run/media/user/, 수동 → /mnt/
        bases = [
            f"/media/{username}",
            f"/run/media/{username}",
            "/media",
            "/mnt",
        ]
        drives: list[tuple[str, str]] = []
        seen: set[str] = set()
        for base in bases:
            if not os.path.isdir(base):
                continue
            try:
                for name in sorted(os.listdir(base)):
                    full = os.path.join(base, name)
                    if os.path.isdir(full) and os.path.ismount(full) and full not in seen:
                        drives.append((name, full))
                        seen.add(full)
            except (PermissionError, OSError):
                pass
        return drives

    def _pick_import_dir(self) -> str | None:
        """가져오기 시작 경로 선택 다이얼로그.
        USB 드라이브가 없으면 바로 홈 디렉토리 반환.
        드라이브가 있으면 선택 UI 표시 후 선택된 경로 반환 (취소 시 None).
        """
        drives = self._detect_usb_drives()
        if not drives:
            return os.path.expanduser("~")

        chosen   = [os.path.expanduser("~")]
        cancelled = [False]

        dlg = tk.Toplevel(self.root)
        dlg.title("가져오기 위치 선택")
        dlg.resizable(False, False)
        dlg.grab_set()
        dlg.configure(bg="#f0f2f5")

        fn      = Font(family="Malgun Gothic", size=22)
        fn_bold = Font(family="Malgun Gothic", size=22, weight="bold")
        fn_sm   = Font(family="Malgun Gothic", size=22)

        tk.Label(
            dlg, text="CSV를 가져올 위치를 선택하세요",
            bg="#2c3e50", fg="white", font=fn_bold, pady=8
        ).pack(fill=tk.X)

        body = tk.Frame(dlg, bg="#f0f2f5", padx=16, pady=10)
        body.pack(fill=tk.BOTH)

        var = tk.StringVar(value=drives[0][1])   # 첫 번째 USB 드라이브를 기본 선택

        # USB 드라이브 목록
        tk.Label(body, text="💾  USB / 외부 드라이브",
                 bg="#f0f2f5", fg="#2980b9", font=fn_bold,
                 anchor="w").pack(fill=tk.X, pady=(0, 4))

        for name, path in drives:
            info = ""
            try:
                st = os.statvfs(path)
                total_gb = st.f_blocks * st.f_frsize / (1024 ** 3)
                free_gb  = st.f_bavail * st.f_frsize / (1024 ** 3)
                info = f"  (여유 {free_gb:.1f} / 전체 {total_gb:.1f} GB)"
            except OSError:
                pass
            tk.Radiobutton(
                body,
                text=f"  {name}{info}",
                variable=var, value=path,
                bg="#f0f2f5", fg="#2c3e50", font=fn,
                activebackground="#f0f2f5", anchor="w"
            ).pack(fill=tk.X, padx=8, pady=2)

        ttk.Separator(body, orient="horizontal").pack(fill=tk.X, pady=8)

        # 홈 디렉토리 선택
        tk.Radiobutton(
            body,
            text=f"🏠  홈 디렉토리  ({os.path.expanduser('~')})",
            variable=var, value="__home__",
            bg="#f0f2f5", fg="#2c3e50", font=fn,
            activebackground="#f0f2f5", anchor="w"
        ).pack(fill=tk.X, padx=8, pady=2)

        tk.Label(
            body,
            text="선택 후 파일 탐색기에서 CSV 파일을 고르세요",
            bg="#f0f2f5", fg="#7f8c8d", font=fn_sm
        ).pack(anchor="w", padx=8, pady=(6, 0))

        # 버튼
        bf = tk.Frame(dlg, bg="#f0f2f5", pady=10)
        bf.pack()
        _b = dict(font=fn, relief=tk.FLAT, padx=14, pady=4, cursor="hand2")

        def ok(_e=None):
            v = var.get()
            chosen[0] = os.path.expanduser("~") if v == "__home__" else v
            dlg.destroy()

        def cancel(_e=None):
            cancelled[0] = True
            dlg.destroy()

        tk.Button(bf, text="파일 탐색기 열기", command=ok,
                  bg="#3498db", fg="white", **_b).pack(side=tk.LEFT, padx=6)
        tk.Button(bf, text="취소", command=cancel,
                  bg="#95a5a6", fg="white", **_b).pack(side=tk.LEFT)

        dlg.bind("<Return>", ok)
        dlg.bind("<Escape>", cancel)
        dlg.update_idletasks()
        dlg.geometry("")   # 내용에 맞게 크기 자동 조절
        self.root.wait_window(dlg)

        return None if cancelled[0] else chosen[0]

    def rename_tree_item(self):
        path = self._get_selected_path()
        if not path:
            return
        old = os.path.basename(path)
        new = simpledialog.askstring("이름 변경", "새 이름:", initialvalue=old, parent=self.root)
        if not new or new == old:
            return
        new_path = os.path.join(os.path.dirname(path), new)
        try:
            os.rename(path, new_path)
            if self.current_csv == path:
                self.current_csv = new_path
            self.load_tree()
        except Exception as e:
            messagebox.showerror("오류", str(e))

    def delete_tree_item(self):
        path = self._get_selected_path()
        if not path:
            messagebox.showinfo("안내", "삭제할 항목을 선택하세요.")
            return
        kind = "폴더(내용 포함)" if os.path.isdir(path) else "파일"
        if not messagebox.askyesno("삭제 확인",
                                   f"{kind} '{os.path.basename(path)}'을 삭제할까요?"):
            return
        try:
            shutil.rmtree(path) if os.path.isdir(path) else os.remove(path)
            if self.current_csv == path:
                self._clear_all()
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
                            desc_col = low.index(alias)
                            has_desc = True
                            break
                    for alias in ("explanation", "해석", "expl"):
                        if alias in low:
                            expl_col = low.index(alias)
                            has_expl = True
                            break

                for row in reader:
                    if not row or len(row) <= text_col:
                        continue
                    text = row[text_col].strip()
                    if not text:
                        continue
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
            self._refresh_sent_tree()
            self._build_practice_indices()
            self._load_sentence()

        except Exception as e:
            messagebox.showerror("오류", f"CSV 읽기 실패:\n{e}")

    def _save_csv(self):
        if not self.current_csv:
            return
        try:
            with open(self.current_csv, "w", newline="", encoding="utf-8-sig") as f:
                w = csv.writer(f)
                w.writerow(["text", "description", "explanation"])
                for row in self.sentence_data:
                    text = row[0]
                    desc = row[1] if len(row) > 1 else ""
                    expl = row[2] if len(row) > 2 else ""
                    w.writerow([text, desc, expl])
        except Exception as e:
            messagebox.showerror("저장 오류", str(e))

    def _save_selected_csv(self):
        """현재 로드된 CSV를 같은 위치에 저장한다."""
        if not self.current_csv:
            return
        self._save_csv()
        fname = os.path.basename(self.current_csv)
        messagebox.showinfo("저장 완료", f"'{fname}' 파일을 저장했습니다.",
                            parent=self._tree_win)

    def save_csv_as(self):
        """저장 위치를 직접 선택해서 CSV를 저장한다."""
        if not self.current_csv:
            return
        dest = filedialog.asksaveasfilename(
            title="다른 이름으로 저장",
            initialdir=os.path.dirname(self.current_csv),
            initialfile=os.path.basename(self.current_csv),
            defaultextension=".csv",
            filetypes=[("CSV 파일", "*.csv"), ("모든 파일", "*.*")],
            parent=self._tree_win
        )
        if not dest:
            return
        try:
            with open(dest, "w", newline="", encoding="utf-8-sig") as f:
                w = csv.writer(f)
                w.writerow(["text", "description", "explanation"])
                for row in self.sentence_data:
                    text = row[0]
                    desc = row[1] if len(row) > 1 else ""
                    expl = row[2] if len(row) > 2 else ""
                    w.writerow([text, desc, expl])
            self.current_csv = dest
            self.load_tree()
            fname = os.path.basename(dest)
            self._csv_lbl.config(text=fname, fg="#2c3e50")
            self._sent_win.title(f"문장 목록 — {fname}")
            messagebox.showinfo("저장 완료", f"'{fname}' 파일을 저장했습니다.",
                                parent=self._tree_win)
        except Exception as e:
            messagebox.showerror("저장 오류", str(e), parent=self._tree_win)

    # ══════════════════════════════════════════════════════════════════════════
    # 문장 목록 CRUD
    # ══════════════════════════════════════════════════════════════════════════

    def _refresh_sent_tree(self):
        self.sent_tree.delete(*self.sent_tree.get_children())

        # ── 미암기 섹션 ──────────────────────────────────────────────────────
        self.sent_tree.insert("", tk.END, iid="hdr_active",
                              values=("", "  📝  미암기 문장"), tags=("hdr",))
        active = [i for i in range(len(self.sentence_data))
                  if i not in self.memorized_indices]
        for i in active:
            text, desc, *_ = self.sentence_data[i]
            content = f"  {i+1:>3}.  {text}"
            if desc:
                short = desc if len(desc) <= 30 else desc[:27] + "…"
                content += f"   # {short}"
            self.sent_tree.insert("", tk.END, iid=f"r_{i}",
                                  values=("☐", content), tags=("normal",))
        if not active:
            self.sent_tree.insert("", tk.END, iid="empty_active",
                                  values=("", "    (없음)"), tags=("empty",))

        # ── 암기 완료 섹션 ───────────────────────────────────────────────────
        self.sent_tree.insert("", tk.END, iid="hdr_done",
                              values=("", "  ✅  암기 완료"), tags=("hdr",))
        done = [i for i in range(len(self.sentence_data))
                if i in self.memorized_indices]
        for i in done:
            text, desc, *_ = self.sentence_data[i]
            content = f"  {i+1:>3}.  {text}"
            if desc:
                short = desc if len(desc) <= 30 else desc[:27] + "…"
                content += f"   # {short}"
            self.sent_tree.insert("", tk.END, iid=f"r_{i}",
                                  values=("☑", content), tags=("memorized",))
        if not done:
            self.sent_tree.insert("", tk.END, iid="empty_done",
                                  values=("", "    (없음)"), tags=("empty",))

        # 검색 하이라이트 재적용
        self._apply_search()
        # 인라인 수정 패널: 인덱스가 범위 밖이면 숨김
        if hasattr(self, '_inline_idx') and self._inline_idx is not None:
            if self._inline_idx >= len(self.sentence_data):
                self._hide_inline_edit()

    def _on_sentence_select(self, _e):
        sel = self.sent_tree.selection()
        if not sel:
            return
        iid = sel[0]
        if not iid.startswith("r_"):
            self._hide_inline_edit()
            return
        data_idx = int(iid[2:])
        # 인라인 수정 패널 갱신
        if self.sentence_data:
            self._show_inline_edit(data_idx)
        # 연습 화면 이동
        if not self.practice_indices:
            return
        try:
            self.current_index = self.practice_indices.index(data_idx)
            self._load_sentence()
        except ValueError:
            pass  # 암기 완료 항목은 연습 목록에 없으므로 무시

    def _on_sent_double_click(self, event):
        pass  # 더블클릭 동작 없음

    # ── 인라인 수정 패널 ──────────────────────────────────────────────────────

    def _inline_auto_h(self, widget: tk.Text, min_h: int = 1, max_h: int = 6):
        """인라인 패널 텍스트 위젯 높이를 내용에 맞게 자동 조절."""
        def _do():
            try:
                result = widget.count("1.0", "end", "displaylines")
                lines  = result[0] if result else min_h
                widget.configure(height=max(min_h, min(lines, max_h)))
            except Exception:
                pass
        widget.after_idle(_do)

    def _show_inline_edit(self, data_idx: int):
        """인라인 수정 패널에 선택 문장을 채우고 표시한다."""
        row = self.sentence_data[data_idx]
        text = row[0]; desc = row[1] if len(row) > 1 else ""; expl = row[2] if len(row) > 2 else ""
        self._inline_idx = data_idx
        self._inline_txt.delete("1.0", tk.END)
        self._inline_txt.insert("1.0", text)
        self._inline_desc.delete("1.0", tk.END)
        self._inline_desc.insert("1.0", desc)
        self._inline_expl.delete("1.0", tk.END)
        self._inline_expl.insert("1.0", expl)
        self._inline_auto_h(self._inline_txt)
        self._inline_auto_h(self._inline_desc)
        self._inline_auto_h(self._inline_expl)
        if not self._inline_visible:
            self._inline_frame.pack(fill=tk.X, padx=6, pady=(4, 4))
            self._inline_visible = True

    def _hide_inline_edit(self):
        """인라인 수정 패널을 숨긴다."""
        if self._inline_visible:
            self._inline_frame.pack_forget()
            self._inline_visible = False
        self._inline_idx = None

    def _save_inline_edit(self):
        """인라인 패널에서 수정한 내용을 저장한다."""
        if self._inline_idx is None:
            return
        text = self._inline_txt.get("1.0", tk.END).strip()
        desc = self._inline_desc.get("1.0", tk.END).strip()
        expl = self._inline_expl.get("1.0", tk.END).strip()
        if not text:
            messagebox.showwarning("경고", "문장을 입력하세요.", parent=self._sent_win)
            return
        idx = self._inline_idx
        self.sentence_data[idx] = (text, desc, expl)
        self._save_csv()
        self._refresh_sent_tree()
        self._load_sentence()
        # 저장 후 해당 행 재선택
        iid = f"r_{idx}"
        if self.sent_tree.exists(iid):
            self.sent_tree.selection_set(iid)
            self.sent_tree.see(iid)

    def add_sentence(self):
        if not self.current_csv:
            messagebox.showinfo("안내", "먼저 파일 관리에서 CSV 파일을 선택하거나 만드세요.")
            return
        dlg = SentenceDialog(self.root, "문장 / 명령어 추가")
        if dlg.result:
            self.sentence_data.append(dlg.result)
            self._save_csv()
            self._refresh_sent_tree()
            new_data_idx = len(self.sentence_data) - 1
            self._build_practice_indices()
            try:
                self.current_index = self.practice_indices.index(new_data_idx)
            except ValueError:
                self.current_index = 0
            self._load_sentence()

    def edit_sentence(self, iid: str | None = None):
        if iid is None:
            sel = self.sent_tree.selection()
            iid = sel[0] if sel else None
        if not iid or not iid.startswith("r_"):
            messagebox.showinfo("안내", "수정할 문장 항목을 선택하세요.")
            return
        idx = int(iid[2:])
        row = self.sentence_data[idx]
        text = row[0]; desc = row[1] if len(row) > 1 else ""; expl = row[2] if len(row) > 2 else ""
        dlg = SentenceDialog(self.root, "문장 / 명령어 수정", text, desc, expl)
        if dlg.result:
            self.sentence_data[idx] = dlg.result
            self._save_csv()
            self._refresh_sent_tree()
            self._load_sentence()

    def delete_sentence(self):
        sel = self.sent_tree.selection()
        if not sel:
            messagebox.showinfo("안내", "삭제할 항목을 선택하세요.")
            return
        iid = sel[0]
        if not iid.startswith("r_"):
            messagebox.showinfo("안내", "삭제할 문장 항목을 선택하세요.")
            return
        idx = int(iid[2:])
        preview = self.sentence_data[idx][0]
        preview = preview if len(preview) <= 40 else preview[:37] + "…"
        if not messagebox.askyesno("삭제 확인", f"삭제할까요?\n\"{preview}\""):
            return
        self.sentence_data.pop(idx)
        # 삭제된 인덱스보다 큰 memorized_indices 를 한 칸씩 앞으로 당김
        self.memorized_indices = {
            (i - 1 if i > idx else i) for i in self.memorized_indices if i != idx
        }
        self._save_csv()
        self._refresh_sent_tree()
        self._build_practice_indices()
        self.current_index = min(
            self.current_index, max(len(self.practice_indices) - 1, 0)
        )
        if self.practice_indices:
            self._load_sentence()
        else:
            self._clear_practice_area()

    # ══════════════════════════════════════════════════════════════════════════
    # 연습 순서 / 랜덤
    # ══════════════════════════════════════════════════════════════════════════

    def _build_practice_indices(self):
        if self.typing_mode.get() == "복습":
            today = date.today().isoformat()
            self.practice_indices = [
                i for i in range(len(self.sentence_data))
                if i not in self.memorized_indices
                and self._get_srs(self.sentence_data[i][0])["next_review"] <= today
            ]
        else:
            self.practice_indices = [
                i for i in range(len(self.sentence_data))
                if i not in self.memorized_indices
            ]
        if self.random_var.get():
            random.shuffle(self.practice_indices)
        self.current_index = 0

    def _toggle_random(self):
        self._build_practice_indices()
        if self.practice_indices:
            self._load_sentence()

    # ══════════════════════════════════════════════════════════════════════════
    # 연습 영역
    # ══════════════════════════════════════════════════════════════════════════

    def _load_sentence(self):
        self.reset_current()

    def restart_all(self):
        """연습 순서를 처음부터 재생성하고 첫 번째 문장으로 이동한다."""
        if not self.sentence_data:
            return
        self._build_practice_indices()
        if self.practice_indices:
            self._load_sentence()

    def reset_current(self):
        self.input_text.delete("1.0", tk.END)
        self.input_text.configure(height=2)   # 입력란 높이 초기화
        self.start_time      = None
        self.is_typing       = False
        self.completed       = False
        self._hidden_revealed = False
        self._hide_banner()
        self._stats_lbl.config(text="타수: —  |  시간: —")
        self._update_counter()
        self._refresh_target("")   # target_display 도 내부에서 _auto_resize 호출
        # 가리기 모드: 다음 문장에도 설명을 계속 표시
        if self.typing_mode.get() == "가리기":
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
        self._refresh_sent_tree()
        self._clear_practice_area()

    def _clear_practice_area(self):
        self.target_display.config(state=tk.NORMAL)
        self.target_display.delete("1.0", tk.END)
        self.target_display.config(state=tk.DISABLED)
        self.input_text.delete("1.0", tk.END)
        self._counter_lbl.config(text="0 / 0")
        self._stats_lbl.config(text="타수: —  |  시간: —")
        self._hide_banner()
        self._hide_desc()
        self._hide_explanation()

    def _update_counter(self):
        total  = len(self.practice_indices)
        cur    = (self.current_index + 1) if total > 0 else 0
        prefix = "📅 " if self.typing_mode.get() == "복습" else ""
        self._counter_lbl.config(text=f"{prefix}{cur} / {total}")

    # ── 배너 / 설명 show·hide ─────────────────────────────────────────────────

    def _show_banner(self):
        if not self._banner_visible:
            self._banner_frame.pack(fill=tk.X, padx=12, pady=(2, 4))
            self._banner_visible = True

    def _hide_banner(self):
        if self._banner_visible:
            self._banner_frame.pack_forget()
            self._banner_visible = False

    def _show_desc(self, text: str):
        self._desc_lbl.config(text=text)
        if not self._desc_visible:
            self._desc_frame.pack(fill=tk.X, padx=12, pady=(4, 2))
            self._desc_visible = True

    def _hide_desc(self):
        if self._desc_visible:
            self._desc_frame.pack_forget()
            self._desc_visible = False

    def _show_explanation(self, text: str):
        self._explanation_lbl.config(text=text)
        if not self._explanation_visible:
            self._explanation_frame.pack(fill=tk.X, padx=12, pady=(2, 2))
            self._explanation_visible = True

    def _hide_explanation(self):
        if self._explanation_visible:
            self._explanation_frame.pack_forget()
            self._explanation_visible = False

    def _update_desc_display(self):
        desc = self._cur_desc()
        if desc:
            self._show_desc(desc)
        else:
            self._hide_desc()
        expl = self._cur_explanation()
        if expl:
            self._show_explanation(expl)
        else:
            self._hide_explanation()

    # ── 연습 문장 렌더링 ──────────────────────────────────────────────────────

    def _on_mode_change(self):
        """타이핑 모드 변경 시 연습 화면 갱신."""
        self._build_practice_indices()
        if not self.practice_indices:
            self._clear_practice_area()
            if self.typing_mode.get() == "복습" and self.sentence_data:
                messagebox.showinfo("복습 완료", "오늘 복습할 문장이 없습니다. 🎉\n내일 다시 확인하세요!")
            return
        self._load_sentence()
        typed = self.input_text.get("1.0", tk.END).rstrip("\n")
        self._refresh_target(typed)
        if self.typing_mode.get() in ("가리기", "복습"):
            self._update_desc_display()
        elif not self.completed:
            self._hide_desc()
            self._hide_explanation()

    def _refresh_target(self, typed: str):
        if not self.practice_indices:
            return
        target = self._cur_text()
        mode = self.typing_mode.get()

        self.target_display.config(state=tk.NORMAL)
        self.target_display.delete("1.0", tk.END)

        if mode == "가리기":
            # 목표 문장을 블록으로 숨김; 맞은 글자만 완료 후 공개
            for i, ch in enumerate(target):
                if i < len(typed):
                    if typed[i] == ch:
                        self.target_display.insert(tk.END, ch, "correct")
                    else:
                        self.target_display.insert(tk.END, "░", "wrong")
                elif i == len(typed):
                    self.target_display.insert(tk.END, "░", "cursor_pos")
                else:
                    self.target_display.insert(tk.END, "░", "pending")

        else:  # 기본
            for i, ch in enumerate(target):
                if i < len(typed):
                    tag = "correct" if typed[i] == ch else "wrong"
                elif i == len(typed):
                    tag = "cursor_pos"
                else:
                    tag = "pending"
                self.target_display.insert(tk.END, ch, tag)

        self.target_display.config(state=tk.DISABLED)
        self._auto_resize(self.target_display)

    # ── 입력 이벤트 ───────────────────────────────────────────────────────────

    def _handle_enter(self, _e):
        if self.typing_mode.get() == "가리기" and self.practice_indices:
            if self.completed or self._hidden_revealed:
                self._rate_and_next(2)   # 보통
            else:
                self._reveal_hidden()
        elif self.completed:
            self._rate_and_next(2)       # 보통
        return "break"

    def _reveal_hidden(self):
        """가리기 모드에서 목표 문장을 강제로 공개한다."""
        target = self._cur_text()
        self.target_display.config(state=tk.NORMAL)
        self.target_display.delete("1.0", tk.END)
        self.target_display.insert(tk.END, target, "pending")
        self.target_display.config(state=tk.DISABLED)
        self._hidden_revealed = True
        self._update_desc_display()

    def _on_key_release(self, event):
        _SKIP = {
            "Return", "Shift_L", "Shift_R", "Control_L", "Control_R",
            "Alt_L", "Alt_R", "Up", "Down", "Left", "Right", "Caps_Lock",
        }
        if event.keysym in _SKIP or not self.practice_indices:
            return

        typed = self.input_text.get("1.0", tk.END).rstrip("\n")

        if typed and not self.is_typing:
            self.start_time = time.time()
            self.is_typing  = True

        self._refresh_target(typed)
        self._update_stats(typed)
        self._check_completion(typed)
        self._auto_resize(self.input_text)

    def _check_completion(self, typed: str):
        if typed == self._cur_text() and not self.completed:
            self.completed = True
            self._show_banner()
            self._update_desc_display()
            if self.typing_mode.get() == "가리기":
                self._refresh_target(typed)

    def _update_stats(self, typed: str):
        if not typed or not self.start_time:
            return
        target  = self._cur_text()
        correct = sum(1 for a, b in zip(typed, target) if a == b)
        acc     = correct / len(typed) * 100
        elapsed = time.time() - self.start_time
        cpm     = len(typed) / elapsed * 60 if elapsed > 0 else 0
        self._stats_lbl.config(
            text=f"타수: {cpm:.0f} CPM  |  시간: {elapsed:.1f}초"
        )

    # ── 네비게이션 ────────────────────────────────────────────────────────────

    def memorize_current(self):
        if not self.practice_indices:
            return
        data_idx = self.practice_indices[self.current_index]
        self.memorized_indices.add(data_idx)
        self._refresh_sent_tree()
        self._build_practice_indices()
        if not self.practice_indices:
            self._clear_practice_area()
            messagebox.showinfo("완료", "모든 문장을 암기 완료했습니다! 🎉")
            return
        self.current_index = min(self.current_index, len(self.practice_indices) - 1)
        self._load_sentence()

    def next_sentence(self, _e=None):
        if not self.practice_indices:
            return
        if self.current_index < len(self.practice_indices) - 1:
            self.current_index += 1
            self._load_sentence()
        else:
            if self.typing_mode.get() == "복습":
                messagebox.showinfo("복습 완료", "오늘의 복습을 완료했습니다! 🎉")
            else:
                messagebox.showinfo("완료", "모든 문장을 완료했습니다! 🎉")

    def prev_sentence(self):
        if self.practice_indices and self.current_index > 0:
            self.current_index -= 1
            self._load_sentence()

    # ── 암기 토글 (체크박스 클릭) ────────────────────────────────────────────

    def _toggle_memorize_item(self, data_idx: int):
        if data_idx in self.memorized_indices:
            self.memorized_indices.discard(data_idx)
        else:
            self.memorized_indices.add(data_idx)
        self._refresh_sent_tree()
        self._build_practice_indices()
        if self.practice_indices:
            self.current_index = min(self.current_index, len(self.practice_indices) - 1)
            self._load_sentence()
        else:
            self._clear_practice_area()

    # ── 드래그 앤 드롭 ───────────────────────────────────────────────────────

    def _drag_start(self, event):
        item = self.sent_tree.identify_row(event.y)
        # 헤더·빈칸 행은 드래그 불가
        self._drag_source  = item if (item and item.startswith("r_")) else None
        self._drag_start_y = event.y
        self._drag_moved   = False

    def _drag_motion(self, event):
        if not self._drag_source:
            return
        if abs(event.y - self._drag_start_y) > 6:
            self._drag_moved = True
        if self._drag_moved:
            # 드롭 대상 행을 시각적으로 강조
            target = self.sent_tree.identify_row(event.y)
            for iid in self.sent_tree.get_children():
                cur_tags = list(self.sent_tree.item(iid, "tags"))
                cur_tags = [t for t in cur_tags if t != "drag_over"]
                self.sent_tree.item(iid, tags=cur_tags)
            if target and target != self._drag_source:
                cur_tags = list(self.sent_tree.item(target, "tags"))
                cur_tags.append("drag_over")
                self.sent_tree.item(target, tags=cur_tags)

    def _drag_end(self, event):
        if not self._drag_source:
            return
        # 강조 제거
        for iid in self.sent_tree.get_children():
            cur_tags = [t for t in self.sent_tree.item(iid, "tags") if t != "drag_over"]
            self.sent_tree.item(iid, tags=cur_tags)

        target = self.sent_tree.identify_row(event.y)

        if self._drag_moved and target and target != self._drag_source:
            if target.startswith("r_"):
                from_idx = int(self._drag_source[2:])
                to_idx   = int(target[2:])
                # 같은 섹션(미암기↔미암기 또는 암기↔암기) 내에서만 허용
                from_mem = from_idx in self.memorized_indices
                to_mem   = to_idx   in self.memorized_indices
                if from_mem == to_mem:
                    self._reorder_data(from_idx, to_idx)
        elif not self._drag_moved:
            # 클릭 → 체크 컬럼이면 토글
            col = self.sent_tree.identify_column(event.x)
            if col == "#1":
                self._toggle_memorize_item(int(self._drag_source[2:]))

        self._drag_source = None
        self._drag_moved  = False

    def _reorder_data(self, from_idx: int, to_idx: int):
        """sentence_data[from_idx]를 to_idx 위치로 이동하고 인덱스 재맵핑."""
        item = self.sentence_data.pop(from_idx)
        insert_at = to_idx - 1 if from_idx < to_idx else to_idx
        self.sentence_data.insert(insert_at, item)

        new_mem: set[int] = set()
        for idx in self.memorized_indices:
            if idx == from_idx:
                new_mem.add(insert_at)
            elif from_idx < insert_at and from_idx < idx <= insert_at:
                new_mem.add(idx - 1)
            elif insert_at < from_idx and insert_at <= idx < from_idx:
                new_mem.add(idx + 1)
            else:
                new_mem.add(idx)
        self.memorized_indices = new_mem

        self._save_csv()
        self._refresh_sent_tree()
        self._build_practice_indices()
        if self.practice_indices:
            self._load_sentence()

    # ── 검색 ─────────────────────────────────────────────────────────────────

    # ══════════════════════════════════════════════════════════════════════════
    # SRS (Anki SM-2) 메서드
    # ══════════════════════════════════════════════════════════════════════════

    def _srs_path(self) -> str | None:
        """현재 CSV 에 대응하는 .srs.json 경로."""
        if not self.current_csv:
            return None
        return os.path.splitext(self.current_csv)[0] + ".srs.json"

    def _load_srs(self):
        """SRS JSON 파일 로드. 없으면 빈 dict."""
        path = self._srs_path()
        if path and os.path.exists(path):
            try:
                with open(path, "r", encoding="utf-8") as f:
                    self.srs_data = json.load(f)
            except Exception:
                self.srs_data = {}
        else:
            self.srs_data = {}

    def _save_srs(self):
        """SRS 데이터를 JSON 파일에 저장."""
        path = self._srs_path()
        if not path:
            return
        try:
            with open(path, "w", encoding="utf-8") as f:
                json.dump(self.srs_data, f, ensure_ascii=False, indent=2)
        except Exception:
            pass

    def _get_srs(self, text: str) -> dict:
        """문장의 SRS 항목 반환. 없으면 기본값 생성."""
        if text not in self.srs_data:
            self.srs_data[text] = {
                "interval":    1,
                "ease_factor": 2.5,
                "next_review": date.today().isoformat(),
                "reps":        0,
            }
        return self.srs_data[text]

    def _apply_sm2(self, entry: dict, rating: int) -> dict:
        """SM-2 알고리즘으로 다음 복습 일정 계산.
        rating: 0=다시, 1=어려움, 2=보통, 3=쉬움
        """
        ef   = entry["ease_factor"]
        ivl  = entry["interval"]
        reps = entry["reps"]

        if rating == 0:        # 다시
            ivl  = 1
            ef   = max(1.3, ef - 0.20)
            reps = 0
        elif rating == 1:      # 어려움
            ivl  = max(1, round(ivl * 1.2))
            ef   = max(1.3, ef - 0.15)
            reps += 1
        elif rating == 2:      # 보통
            if reps == 0:   ivl = 1
            elif reps == 1: ivl = 3
            else:           ivl = max(1, round(ivl * ef))
            reps += 1
        else:                  # 쉬움
            if reps == 0:   ivl = 4
            elif reps == 1: ivl = 5
            else:           ivl = max(1, round(ivl * ef * 1.3))
            ef   = min(3.5, ef + 0.15)
            reps += 1

        return {
            "interval":    ivl,
            "ease_factor": round(ef, 2),
            "next_review": (date.today() + timedelta(days=ivl)).isoformat(),
            "reps":        reps,
        }

    def _rate_and_next(self, rating: int):
        """SRS 평가 후 다음 문장으로 이동."""
        if not self.practice_indices:
            return
        text = self._cur_text()
        self.srs_data[text] = self._apply_sm2(self._get_srs(text), rating)
        self._save_srs()
        self.next_sentence()

    # ══════════════════════════════════════════════════════════════════════════

    def _apply_search(self):
        """검색어와 일치하는 행을 노란색으로 하이라이트."""
        if not hasattr(self, "_search_var"):
            return
        query = self._search_var.get().strip().lower()
        for iid in self.sent_tree.get_children():
            if not iid.startswith("r_"):
                continue
            data_idx = int(iid[2:])
            text, desc, *_ = self.sentence_data[data_idx]
            is_match = bool(query) and (
                query in text.lower() or query in desc.lower()
            )
            cur_tags = [t for t in self.sent_tree.item(iid, "tags")
                        if t != "search_match"]
            if is_match:
                cur_tags.append("search_match")
            self.sent_tree.item(iid, tags=cur_tags)


# ══════════════════════════════════════════════════════════════════════════════
class SentenceDialog:
    """문장/명령어 + 설명 추가·수정 다이얼로그
    - 마우스로 창 크기 조절 가능
    - 입력란이 글자 수에 따라 자동으로 높이 조절
    """
# ══════════════════════════════════════════════════════════════════════════════

    def __init__(self, parent: tk.Misc,
                 title: str,
                 initial_text: str = "",
                 initial_desc: str = "",
                 initial_expl: str = ""):
        self.result: tuple[str, str, str] | None = None

        dlg = tk.Toplevel(parent)
        dlg.title(title)
        dlg.resizable(True, True)          # ← 마우스로 크기 조절 가능
        dlg.minsize(630, 480)              # 최소 크기
        dlg.grab_set()
        dlg.configure(bg="#f0f2f5")

        fn    = Font(family="Malgun Gothic", size=22)
        fn_sm = Font(family="Malgun Gothic", size=22)
        fn_mo = Font(family="Monospace",     size=22)

        # ── 글자 수에 따라 입력란 높이 자동 조절 ──────────────────────────
        def auto_h(widget: tk.Text, min_h: int = 2, max_h: int = 12):
            def _do():
                try:
                    result = widget.count("1.0", "end", "displaylines")
                    lines  = result[0] if result else min_h
                    widget.configure(height=max(min_h, min(lines, max_h)))
                    dlg.update_idletasks()
                except Exception:
                    pass
            widget.after_idle(_do)

        # 명령어/문장 입력
        tk.Label(dlg, text="명령어 / 문장:", bg="#f0f2f5", font=fn).pack(
            anchor="w", padx=14, pady=(14, 2)
        )
        txt = tk.Text(dlg, height=2, font=fn_mo, wrap=tk.WORD,
                      padx=6, pady=4, bg="#1e2a38", fg="#e0e0e0",
                      insertbackground="white", undo=True)
        txt.pack(fill=tk.BOTH, expand=True, padx=14)
        txt.insert("1.0", initial_text)
        txt.bind("<KeyRelease>", lambda e: auto_h(txt))
        txt.focus_set()

        # 해석 입력
        tk.Label(dlg, text="해석 (선택 사항):", bg="#f0f2f5", font=fn).pack(
            anchor="w", padx=14, pady=(10, 2)
        )
        desc_txt = tk.Text(dlg, height=2, font=fn, wrap=tk.WORD,
                           padx=6, pady=4, bg="#eaf4fb", fg="#1a5276", undo=True)
        desc_txt.pack(fill=tk.BOTH, expand=True, padx=14)
        desc_txt.insert("1.0", initial_desc)
        desc_txt.bind("<KeyRelease>", lambda e: auto_h(desc_txt))

        # 설명 입력
        tk.Label(dlg, text="설명 (선택 사항):", bg="#f0f2f5", font=fn).pack(
            anchor="w", padx=14, pady=(10, 2)
        )
        expl_txt = tk.Text(dlg, height=2, font=fn, wrap=tk.WORD,
                           padx=6, pady=4, bg="#f0fff0", fg="#1a5226", undo=True)
        expl_txt.pack(fill=tk.BOTH, expand=True, padx=14)
        expl_txt.insert("1.0", initial_expl)
        expl_txt.bind("<KeyRelease>", lambda e: auto_h(expl_txt))

        tk.Label(dlg, text="Ctrl+Enter: 확인  /  Esc: 취소",
                 bg="#f0f2f5", fg="#888", font=fn_sm).pack(anchor="e", padx=14, pady=2)

        def confirm(_e=None):
            val  = txt.get("1.0", tk.END).strip()
            desc = desc_txt.get("1.0", tk.END).strip()
            expl = expl_txt.get("1.0", tk.END).strip()
            if val:
                self.result = (val, desc, expl)
                dlg.destroy()
            else:
                messagebox.showwarning("경고", "명령어/문장을 입력하세요.", parent=dlg)

        def cancel(_e=None):
            dlg.destroy()

        bf = tk.Frame(dlg, bg="#f0f2f5")
        bf.pack(pady=10)
        _b = dict(font=fn, relief=tk.FLAT, padx=14, pady=4, cursor="hand2")
        tk.Button(bf, text="확인", command=confirm,
                  bg="#3498db", fg="white", **_b).pack(side=tk.LEFT, padx=6)
        tk.Button(bf, text="취소", command=cancel,
                  bg="#95a5a6", fg="white", **_b).pack(side=tk.LEFT)

        txt.bind("<Control-Return>", confirm)
        dlg.bind("<Escape>", cancel)

        # 초기 내용에 맞게 높이 조절 후 창 크기 자동 결정
        auto_h(txt)
        auto_h(desc_txt)
        auto_h(expl_txt)
        dlg.update_idletasks()
        dlg.geometry("")   # 내용에 맞게 초기 크기 자동 결정

        parent.wait_window(dlg)  # type: ignore[arg-type]


# ══════════════════════════════════════════════════════════════════════════════
if __name__ == "__main__":
    root = TkinterDnD.Tk() if HAS_DND else tk.Tk()
    app = TypingPractice(root)
    root.mainloop()
