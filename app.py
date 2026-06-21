import tkinter as tk
from tkinter import font

class Calculator:
    def __init__(self, root):
        self.root = root
        self.root.title("计算器")
        self.root.resizable(False, False)
        self.root.geometry("280x380")
        self.root.configure(bg="#f0f0f0")

        self.expression = ""
        self.current = ""
        self.result_shown = False

        # 字体
        display_font = font.Font(family="Segoe UI", size=22, weight="bold")
        btn_font = font.Font(family="Segoe UI", size=14)

        # 显示屏
        display_frame = tk.Frame(root, bg="#f0f0f0")
        display_frame.pack(pady=(15, 10))

        self.display_var = tk.StringVar(value="0")
        self.display = tk.Label(
            display_frame, textvariable=self.display_var, font=display_font,
            anchor="e", fg="#333", bg="white", width=14, height=2,
            relief="flat", padx=10
        )
        self.display.pack()

        # 按钮布局
        btn_frame = tk.Frame(root, bg="#f0f0f0")
        btn_frame.pack(padx=10, pady=(0, 10))

        buttons = [
            ("7", 0, 0), ("8", 0, 1), ("9", 0, 2), ("/", 0, 3),
            ("4", 1, 0), ("5", 1, 1), ("6", 1, 2), ("x", 1, 3),
            ("1", 2, 0), ("2", 2, 1), ("3", 2, 2), ("-", 2, 3),
            ("0", 3, 0), (".", 3, 1), ("C", 3, 2), ("=", 3, 3),
            ("CE", 4, 0), ("+", 4, 1),
        ]
        # 合并 CE 和 + 占两列：CE 占(4,0-1), +占(4,2-3)

        for text, row, col in buttons:
            if text in ("=", "C", "CE"):
                bg = "#ff9800"
                fg = "white"
                active_bg = "#e68900"
            elif text in ("+", "-", "x", "/"):
                bg = "#e0e0e0"
                fg = "#333"
                active_bg = "#ccc"
            else:
                bg = "#fafafa"
                fg = "#333"
                active_bg = "#e8e8e8"

            btn = tk.Button(
                btn_frame, text=text, font=btn_font,
                width=4, height=1, bg=bg, fg=fg,
                activebackground=active_bg, relief="raised", bd=1,
                command=lambda t=text: self.on_button(t)
            )
            btn.grid(row=row, column=col, padx=2, pady=2, sticky="nsew")
            # 设置每个格子等宽
            btn_frame.grid_columnconfigure(col, weight=1)

        # 合并 CE 占两列 (col 0-1), + 占两列 (col 2-3)
        for widget in btn_frame.grid_slaves():
            if widget.cget("text") == "CE":
                widget.grid_configure(column=0, columnspan=2, sticky="ew")
            if widget.cget("text") == "+":
                widget.grid_configure(column=2, columnspan=2, sticky="ew")
                btn_frame.grid_columnconfigure(2, weight=1)

        # 键盘绑定
        self.root.bind("<Key>", self.on_keypress)

    def on_button(self, text):
        if text == "C":
            self.current = self.current[:-1]
        elif text == "CE":
            self.current = ""
            self.expression = ""
        elif text == "=":
            try:
                expr = self.expression + self.current
                expr = expr.replace("x", "*")
                result = eval(expr)
                # 去掉 .0
                if isinstance(result, float) and result == int(result):
                    result = int(result)
                self.expression = str(result)
                self.current = ""
                self.result_shown = True
            except Exception:
                self.expression = ""
                self.current = "错误"
                self.result_shown = True
        elif text in ("+", "-", "x", "/"):
            if self.result_shown:
                self.current = ""
                self.result_shown = False
            self.expression += self.current + text
            self.current = ""
        elif text == ".":
            if "." not in self.current:
                self.current += text
        else:  # 数字
            if self.result_shown:
                self.expression = ""
                self.current = ""
                self.result_shown = False
            self.current += text

        self.update_display()

    def on_keypress(self, event):
        key_map = {
            "0": "0", "1": "1", "2": "2", "3": "3", "4": "4",
            "5": "5", "6": "6", "7": "7", "8": "8", "9": "9",
            ".": ".", "+": "+", "-": "-", "*": "x", "/": "/",
            "Return": "=", "Escape": "CE", "BackSpace": "C"
        }
        if event.char in key_map:
            self.on_button(key_map[event.char])
        elif event.keysym in key_map:
            self.on_button(key_map[event.keysym])

    def update_display(self):
        display_text = self.expression + self.current
        if not display_text:
            display_text = "0"
        self.display_var.set(display_text)


if __name__ == "__main__":
    root = tk.Tk()
    Calculator(root)
    root.mainloop()
