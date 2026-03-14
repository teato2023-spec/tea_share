#!/usr/bin/env python3
"""이미지 색상 추출기 - Neovim 연동용"""
import sys
import os

try:
    import tkinter as tk
    from PIL import Image, ImageTk
except ImportError as e:
    missing = "tkinter" if "tkinter" in str(e) else "Pillow"
    print(f"ERROR: {missing} 가 없습니다.")
    print("설치: sudo apt install python3-tk python3-pil python3-pil.imagetk")
    sys.exit(1)


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


def main():
    if len(sys.argv) < 2:
        print("사용법: python3 color_picker.py <이미지_파일>")
        sys.exit(1)

    image_path = sys.argv[1]
    if not os.path.exists(image_path):
        print(f"ERROR: 파일 없음: {image_path}")
        sys.exit(1)

    try:
        img = Image.open(image_path).convert("RGB")
    except Exception as e:
        print(f"ERROR: 이미지를 열 수 없습니다: {e}")
        sys.exit(1)

    root = tk.Tk()
    root.title(f"색상 추출기 — {os.path.basename(image_path)}")
    root.configure(bg="#1e1e2e")

    # 화면에 맞게 이미지 크기 조정
    sw = root.winfo_screenwidth() - 300
    sh = root.winfo_screenheight() - 160
    scale = min(sw / img.width, sh / img.height, 1.0)
    dw, dh = int(img.width * scale), int(img.height * scale)
    disp = img.resize((dw, dh), Image.LANCZOS)
    photo = ImageTk.PhotoImage(disp)

    # ── 레이아웃 ──────────────────────────────────────────
    left = tk.Frame(root, bg="#1e1e2e")
    left.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

    right = tk.Frame(root, width=220, bg="#181825")
    right.pack(side=tk.RIGHT, fill=tk.Y)
    right.pack_propagate(False)

    # 캔버스
    canvas = tk.Canvas(left, width=dw, height=dh,
                        bg="#000", cursor="crosshair", highlightthickness=0)
    canvas.pack()
    canvas.create_image(0, 0, anchor=tk.NW, image=photo)

    # ── 오른쪽 패널 ───────────────────────────────────────
    tk.Label(right, text="색상 추출기", font=("Arial", 13, "bold"),
             bg="#181825", fg="#cdd6f4").pack(pady=(16, 8))

    preview = tk.Canvas(right, width=160, height=70,
                         bg="#000000", highlightthickness=1,
                         highlightbackground="#45475a")
    preview.pack(pady=(0, 8))

    hex_var = tk.StringVar(value="#------")
    rgb_var = tk.StringVar(value="RGB(-, -, -)")
    hsl_var = tk.StringVar(value="HSL(-, -, -)")
    pos_var = tk.StringVar(value="위치: (-, -)")

    tk.Label(right, textvariable=hex_var, font=("Courier New", 15, "bold"),
             bg="#181825", fg="#cdd6f4").pack()
    tk.Label(right, textvariable=rgb_var, font=("Courier New", 10),
             bg="#181825", fg="#a6adc8").pack(pady=2)
    tk.Label(right, textvariable=hsl_var, font=("Courier New", 10),
             bg="#181825", fg="#a6adc8").pack()
    tk.Label(right, textvariable=pos_var, font=("Courier New", 9),
             bg="#181825", fg="#585b70").pack(pady=(6, 0))

    copy_btn = tk.Button(right, text="HEX 복사",
                          font=("Arial", 10), bg="#313244", fg="#cdd6f4",
                          activebackground="#45475a", relief="flat",
                          padx=12, pady=6)
    copy_btn.pack(pady=10, ipadx=4)

    tk.Label(right, text="클릭 → 색상 추출\n자동으로 클립보드 복사\n\nQ / ESC → 종료",
             font=("Arial", 8), bg="#181825", fg="#585b70",
             justify=tk.LEFT).pack(pady=(4, 0), padx=10, anchor=tk.W)

    # ── 이벤트 ────────────────────────────────────────────
    current_hex = ["#000000"]

    def do_copy():
        root.clipboard_clear()
        root.clipboard_append(current_hex[0])
        copy_btn.config(text="✓ 복사됨!")
        root.after(1500, lambda: copy_btn.config(text="HEX 복사"))

    copy_btn.config(command=do_copy)

    def on_click(event):
        cx, cy = event.x, event.y
        px = max(0, min(int(cx / scale), img.width - 1))
        py = max(0, min(int(cy / scale), img.height - 1))
        r, g, b = img.getpixel((px, py))
        hx = f"#{r:02X}{g:02X}{b:02X}"
        h, s, l = rgb_to_hsl(r, g, b)

        current_hex[0] = hx
        hex_var.set(hx)
        rgb_var.set(f"RGB({r}, {g}, {b})")
        hsl_var.set(f"HSL({h}°, {s}%, {l}%)")
        pos_var.set(f"위치: ({px}, {py})")
        preview.config(bg=hx)

        # 텍스트 대비색
        fg = "#ffffff" if (r * 299 + g * 587 + b * 114) / 1000 < 128 else "#000000"
        preview.delete("all")
        preview.create_text(80, 35, text=hx, font=("Courier New", 14, "bold"),
                            fill=fg)

        # 십자선
        canvas.delete("cross")
        for dx, dy, col in [(0,0,"white"), (0,0,"black")]:
            kw = {"tags": "cross", "width": 1}
            canvas.create_line(cx-12, cy, cx+12, cy, fill=col,
                               dash=(4,2) if col=="black" else (), **kw)
            canvas.create_line(cx, cy-12, cx, cy+12, fill=col,
                               dash=(4,2) if col=="black" else (), **kw)

        # 클립보드 자동 복사
        root.clipboard_clear()
        root.clipboard_append(hx)
        print(f"PICKED: {hx} | RGB({r},{g},{b}) | HSL({h},{s}%,{l}%) | pos({px},{py})",
              flush=True)

    canvas.bind("<Button-1>", on_click)
    root.bind("<q>", lambda _: root.destroy())
    root.bind("<Escape>", lambda _: root.destroy())

    root.mainloop()


if __name__ == "__main__":
    main()
