import tkinter as tk
from tkinter import ttk

class Calculator:
    def __init__(self, root):
        self.root = root
        self.root.title("计算器")
        self.root.resizable(False, False)
        self.root.attributes('-alpha', 1.0)

        # State
        self.current_input = "0"
        self.operator = None
        self.first_operand = None
        self.waiting_for_second = False
        self.expression = ""

        # Entry display
        self.display_var = tk.StringVar(value="0")
        self.display = ttk.Entry(
            root, textvariable=self.display_var,
            font=("Consolas", 20), justify="right",
            state="readonly"
        )
        self.display.grid(row=0, column=0, columnspan=4, sticky="nsew", padx=2, pady=2)

        # Button definitions: (text, row, col, colspan)
        buttons = [
            ("7", 1, 0, 1), ("8", 1, 1, 1), ("9", 1, 2, 1), ("/", 1, 3, 1),
            ("4", 2, 0, 1), ("5", 2, 1, 1), ("6", 2, 2, 1), ("*", 2, 3, 1),
            ("1", 3, 0, 1), ("2", 3, 1, 1), ("3", 3, 2, 1), ("-", 3, 3, 1),
            ("0", 4, 0, 1), (".", 4, 1, 1), ("C", 4, 2, 1), ("=", 4, 3, 1),
            ("CE", 5, 0, 1), ("+", 5, 1, 3),
        ]

        for (text, row, col, colspan) in buttons:
            btn = tk.Button(
                root, text=text, font=("Consolas", 14),
                command=lambda t=text: self.on_button_click(t),
                relief="raised", bd=1
            )
            btn.grid(row=row, column=col, columnspan=colspan, sticky="nsew", padx=1, pady=1)

        # Grid weights for resizing
        for i in range(6):
            root.grid_rowconfigure(i, weight=1)
        for i in range(4):
            root.grid_columnconfigure(i, weight=1)

        # Keyboard bindings
        root.bind("<Key>", self.on_key_press)

    def on_button_click(self, char):
        if char.isdigit() or char == ".":
            self.input_digit(char)
        elif char in ("+", "-", "*", "/"):
            self.input_operator(char)
        elif char == "=":
            self.calculate_result()
        elif char == "C":
            self.clear_all()
        elif char == "CE":
            self.clear_entry()

    def on_key_press(self, event):
        key = event.char
        if key in "0123456789.":
            self.input_digit(key)
        elif key in "+-*/":
            self.input_operator(key)
        elif key == "\r" or key == "=":
            self.calculate_result()
        elif key == "\x08":  # Backspace
            self.backspace()
        elif key == "\x1b":  # Escape
            self.clear_all()

    def input_digit(self, char):
        if self.waiting_for_second:
            self.current_input = char if char != "." else "0."
            self.waiting_for_second = False
        else:
            if char == ".":
                if "." in self.current_input:
                    return
                self.current_input += "."
            else:
                if self.current_input == "0" and char == "0":
                    return
                if self.current_input == "0" and char != ".":
                    self.current_input = char
                else:
                    self.current_input += char
        self.update_display()

    def input_operator(self, op):
        if self.first_operand is not None and not self.waiting_for_second:
            self.calculate_result()
        self.first_operand = float(self.current_input)
        self.operator = op
        self.waiting_for_second = True
        self.update_display()

    def calculate_result(self):
        if self.operator is None or self.first_operand is None:
            return
        second_operand = float(self.current_input)

        if self.operator == "/" and second_operand == 0:
            self.display_var.set("除数不能为零")
            self.current_input = "0"
            self.first_operand = None
            self.operator = None
            self.waiting_for_second = False
            return

        operations = {
            "+": lambda a, b: a + b,
            "-": lambda a, b: a - b,
            "*": lambda a, b: a * b,
            "/": lambda a, b: a / b,
        }

        result = operations[self.operator](self.first_operand, second_operand)

        # Format: remove .0 if integer
        if result == int(result):
            self.current_input = str(int(result))
        else:
            self.current_input = str(result)

        self.first_operand = result
        self.operator = None
        self.waiting_for_second = True
        self.update_display()

    def clear_all(self):
        self.current_input = "0"
        self.first_operand = None
        self.operator = None
        self.waiting_for_second = False
        self.update_display()

    def clear_entry(self):
        self.current_input = "0"
        self.update_display()

    def backspace(self):
        if self.waiting_for_second:
            return
        if len(self.current_input) > 1:
            self.current_input = self.current_input[:-1]
            if self.current_input == "" or self.current_input == "-":
                self.current_input = "0"
        else:
            self.current_input = "0"
        self.update_display()

    def update_display(self):
        self.display_var.set(self.current_input)


if __name__ == "__main__":
    root = tk.Tk()
    Calculator(root)
    root.mainloop()
