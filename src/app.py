from __future__ import annotations

import csv
import tkinter as tk
from tkinter import messagebox, ttk, filedialog
from typing import Dict, Optional

from db import add_raw_type, authenticate, get_coeffs, get_raw_types, init_db, update_coeffs
from model_core import sweep_CB

try:
    from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
    from matplotlib.figure import Figure

    HAS_MPL = True
except Exception:
    HAS_MPL = False


class App(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title("Reactor Model")
        self.geometry("1100x700")
        self.minsize(900, 600)

        init_db()

        self.current_user_role: Optional[str] = None
        self.login_frame: Optional[tk.Frame] = None
        self.main_frame: Optional[tk.Frame] = None

        # для отчёта
        self.last_results: list[dict] = []
        self.last_params: Dict[str, float] = {}
        self.save_report_button: Optional[ttk.Button] = None

        self.show_login()

    # ---------- auth ----------
    def show_login(self) -> None:
        if self.main_frame:
            self.main_frame.destroy()

        frame = tk.Frame(self, padx=20, pady=20)
        frame.pack(expand=True)

        tk.Label(frame, text="Логин").grid(row=0, column=0, sticky="e", pady=5)
        tk.Label(frame, text="Пароль").grid(row=1, column=0, sticky="e", pady=5)

        self.username_var = tk.StringVar()
        self.password_var = tk.StringVar()

        tk.Entry(frame, textvariable=self.username_var, width=22).grid(row=0, column=1, padx=8)
        tk.Entry(frame, textvariable=self.password_var, show="*", width=22).grid(row=1, column=1, padx=8)

        ttk.Button(frame, text="Войти", command=self.do_login).grid(
            row=2, column=0, columnspan=2, pady=12
        )

        self.login_frame = frame

    def do_login(self) -> None:
        user = authenticate(self.username_var.get().strip(), self.password_var.get())
        if not user:
            messagebox.showerror("Ошибка", "Неверный логин/пароль")
            return

        self.current_user_role = user["role"]
        self.show_main()

    # ---------- main UI ----------
    def show_main(self) -> None:
        if self.login_frame:
            self.login_frame.destroy()

        frame = tk.Frame(self)
        frame.pack(fill="both", expand=True)

        top = tk.Frame(frame)
        top.pack(fill="x")
        ttk.Button(top, text="Выйти", command=self.logout).pack(side="right", padx=10, pady=5)

        notebook = ttk.Notebook(frame)
        notebook.pack(fill="both", expand=True)

        research_tab = tk.Frame(notebook)
        notebook.add(research_tab, text="Исследование")
        self.build_research_tab(research_tab)

        if self.current_user_role == "admin":
            admin_tab = tk.Frame(notebook)
            notebook.add(admin_tab, text="Администрирование")
            self.build_admin_tab(admin_tab)

        self.main_frame = frame

    def logout(self) -> None:
        if self.main_frame:
            self.main_frame.destroy()
        self.current_user_role = None
        self.last_results = []
        self.last_params = {}
        self.save_report_button = None
        self.show_login()

    # ---------- research tab ----------
    def build_research_tab(self, parent: tk.Frame) -> None:
        left = tk.Frame(parent, padx=10, pady=10)
        left.pack(side="left", fill="y")

        right = tk.Frame(parent, padx=10, pady=10)
        right.pack(side="right", fill="both", expand=True)

        tk.Label(left, text="Тип сырья:").grid(row=0, column=0, sticky="w")
        self.raw_type_var = tk.StringVar()
        self.raw_type_id_by_name: Dict[str, int] = {}

        raw_types = get_raw_types()
        names = [rt["name"] for rt in raw_types]
        self.raw_type_id_by_name = {rt["name"]: rt["id"] for rt in raw_types}

        self.raw_combo = ttk.Combobox(left, textvariable=self.raw_type_var, values=names, state="readonly")
        if names:
            self.raw_combo.current(0)
        self.raw_combo.grid(row=0, column=1, padx=5, pady=5, sticky="ew")

        self.param_vars: Dict[str, tk.StringVar] = {}
        params = [
            ("k1", 1), ("k2", 2), ("Vr", 3),
            ("Q_min", 4), ("Q_max", 5), ("dQ", 6),
            ("CAin_min", 7), ("CAin_max", 8), ("dCAin", 9),
        ]
        for name, row in params:
            tk.Label(left, text=f"{name}:").grid(row=row, column=0, sticky="e")
            var = tk.StringVar()
            tk.Entry(left, textvariable=var, width=10).grid(row=row, column=1, padx=5, pady=2, sticky="w")
            self.param_vars[name] = var

        ttk.Button(left, text="Загрузить из БД", command=self.load_params_from_db).grid(
            row=10, column=0, columnspan=2, pady=(8, 4), sticky="ew"
        )
        ttk.Button(left, text="Рассчитать", command=self.run_calculation).grid(
            row=11, column=0, columnspan=2, pady=4, sticky="ew"
        )

        # кнопка отчёта
        self.save_report_button = ttk.Button(
            left,
            text="Сохранить отчёт…",
            command=self.save_report,
            state="disabled",
        )
        self.save_report_button.grid(row=12, column=0, columnspan=2, pady=4, sticky="ew")

        columns = ("Q", "CA_in", "CB")
        self.tree = ttk.Treeview(right, columns=columns, show="headings", height=18)
        for col in columns:
            self.tree.heading(col, text=col)
            self.tree.column(col, width=120, anchor="center")
        self.tree.pack(fill="both", expand=True)

        if HAS_MPL:
            self.fig = Figure(figsize=(6, 3))
            self.ax = self.fig.add_subplot(111)
            self.canvas = FigureCanvasTkAgg(self.fig, master=right)
            self.canvas.get_tk_widget().pack(fill="x", pady=10)

        self.load_params_from_db()

    def load_params_from_db(self) -> None:
        name = self.raw_type_var.get()
        if not name:
            return

        raw_id = self.raw_type_id_by_name[name]
        coeffs = get_coeffs(raw_id)
        if not coeffs:
            messagebox.showerror("Ошибка", "Нет коэффициентов для выбранного типа сырья")
            return

        for key in self.param_vars:
            self.param_vars[key].set(str(coeffs[key]))

    def _read_float(self, key: str) -> float:
        try:
            return float(self.param_vars[key].get())
        except ValueError as e:
            raise ValueError(f"Некорректное значение {key}") from e

    def run_calculation(self) -> None:
        try:
            k1 = self._read_float("k1")
            k2 = self._read_float("k2")
            Vr = self._read_float("Vr")
            Q_min = self._read_float("Q_min")
            Q_max = self._read_float("Q_max")
            dQ = self._read_float("dQ")
            CAin_min = self._read_float("CAin_min")
            CAin_max = self._read_float("CAin_max")
            dCAin = self._read_float("dCAin")
        except ValueError as e:
            messagebox.showerror("Ошибка", str(e))
            return

        if dQ <= 0 or dCAin <= 0:
            messagebox.showerror("Ошибка", "Шаги dQ и dCAin должны быть > 0")
            return

        results = sweep_CB(k1, k2, Vr, Q_min, Q_max, dQ, CAin_min, CAin_max, dCAin)

        # запоминаем для отчёта
        self.last_results = results
        self.last_params = {
            "raw_type": self.raw_type_var.get(),
            "k1": k1, "k2": k2, "Vr": Vr,
            "Q_min": Q_min, "Q_max": Q_max, "dQ": dQ,
            "CAin_min": CAin_min, "CAin_max": CAin_max, "dCAin": dCAin,
        }
        if self.save_report_button:
            self.save_report_button.config(state="normal")

        self.tree.delete(*self.tree.get_children())
        for r in results:
            self.tree.insert(
                "", "end",
                values=(
                    f"{r['Q']:.3f}",
                    f"{r['CA_in']:.3f}",
                    f"{r['CB']:.6f}",
                ),
            )

        if HAS_MPL and results:
            self.ax.clear()
            ca0 = results[0]["CA_in"]
            xs = [r["Q"] for r in results if abs(r["CA_in"] - ca0) < 1e-9]
            ys = [r["CB"] for r in results if abs(r["CA_in"] - ca0) < 1e-9]
            self.ax.plot(xs, ys)
            self.ax.set_xlabel("Q, л/мин")
            self.ax.set_ylabel("CB, моль/л")
            self.ax.set_title(f"CB(Q) при CA_in={ca0:g}")
            self.canvas.draw()

        messagebox.showinfo("Готово", f"Расчёт выполнен, точек: {len(results)}")

    def save_report(self) -> None:
        if not self.last_results:
            messagebox.showwarning("Отчёт", "Нет данных для отчёта. Сначала выполните расчёт.")
            return

        filename = filedialog.asksaveasfilename(
            defaultextension=".csv",
            filetypes=[("CSV файлы", "*.csv"), ("Все файлы", "*.*")],
            title="Сохранить отчёт",
        )
        if not filename:
            return

        try:
            with open(filename, "w", newline="", encoding="utf-8-sig") as f:
                writer = csv.writer(f, delimiter=";")
                p = self.last_params

                writer.writerow(["Отчёт по расчёту реактора (вариант 8)"])
                writer.writerow([])
                writer.writerow(["Тип сырья", p.get("raw_type", "")])
                writer.writerow(["Vr, л", p["Vr"]])
                writer.writerow(["k1, 1/мин", p["k1"]])
                writer.writerow(["k2, 1/мин", p["k2"]])
                writer.writerow(["Q_min, л/мин", p["Q_min"]])
                writer.writerow(["Q_max, л/мин", p["Q_max"]])
                writer.writerow(["dQ, л/мин", p["dQ"]])
                writer.writerow(["CAin_min, моль/л", p["CAin_min"]])
                writer.writerow(["CAin_max, моль/л", p["CAin_max"]])
                writer.writerow(["dCAin, моль/л", p["dCAin"]])
                writer.writerow([])
                writer.writerow(["Q, л/мин", "CA_in, моль/л", "CB, моль/л"])

                for r in self.last_results:
                    writer.writerow([
                        f"{r['Q']:.2f}",
                        f"{r['CA_in']:.3f}",
                        f"{r['CB']:.4f}",
                    ])

            messagebox.showinfo("Отчёт", f"Отчёт сохранён:\n{filename}")
        except Exception as e:
            messagebox.showerror("Ошибка", f"Не удалось сохранить отчёт:\n{e}")

    # ---------- admin tab ----------
    def build_admin_tab(self, parent: tk.Frame) -> None:
        left = tk.Frame(parent, padx=10, pady=10)
        left.pack(side="left", fill="y")

        right = tk.Frame(parent, padx=10, pady=10)
        right.pack(side="right", fill="both", expand=True)

        tk.Label(left, text="Типы сырья:").pack(anchor="w")
        self.raw_listbox = tk.Listbox(left, height=12)
        self.raw_listbox.pack(fill="y")
        self.raw_listbox.bind("<<ListboxSelect>>", self.on_raw_select)

        ttk.Button(left, text="Обновить список", command=self.reload_raw_list).pack(fill="x", pady=(8, 4))
        ttk.Button(left, text="Добавить тип", command=self.add_raw_type_dialog).pack(fill="x")

        self.admin_param_vars: Dict[str, tk.StringVar] = {}
        params = [
            ("k1", 0), ("k2", 1), ("Vr", 2),
            ("Q_min", 3), ("Q_max", 4), ("dQ", 5),
            ("CAin_min", 6), ("CAin_max", 7), ("dCAin", 8),
        ]
        for name, row in params:
            tk.Label(right, text=f"{name}:").grid(row=row, column=0, sticky="e", pady=2)
            var = tk.StringVar()
            tk.Entry(right, textvariable=var, width=12).grid(row=row, column=1, sticky="w", padx=5, pady=2)
            self.admin_param_vars[name] = var

        ttk.Button(right, text="Сохранить параметры", command=self.save_admin_params).grid(
            row=9, column=0, columnspan=2, pady=10, sticky="ew"
        )

        self.reload_raw_list()

    def reload_raw_list(self) -> None:
        self.raw_types_admin = get_raw_types()
        self.raw_listbox.delete(0, tk.END)
        for rt in self.raw_types_admin:
            self.raw_listbox.insert(tk.END, rt["name"])

        if self.raw_types_admin:
            self.raw_listbox.selection_set(0)
            self.on_raw_select(None)

    def on_raw_select(self, event) -> None:
        if not self.raw_listbox.curselection():
            return
        idx = int(self.raw_listbox.curselection()[0])
        raw_id = self.raw_types_admin[idx]["id"]
        coeffs = get_coeffs(raw_id)
        if not coeffs:
            for k in self.admin_param_vars:
                self.admin_param_vars[k].set("")
            return

        for k in self.admin_param_vars:
            self.admin_param_vars[k].set(str(coeffs[k]))

    def save_admin_params(self) -> None:
        if not self.raw_listbox.curselection():
            return
        idx = int(self.raw_listbox.curselection()[0])
        raw_id = self.raw_types_admin[idx]["id"]

        try:
            coeffs = {k: float(v.get()) for k, v in self.admin_param_vars.items()}
        except ValueError:
            messagebox.showerror("Ошибка", "Проверьте корректность числовых параметров")
            return

        update_coeffs(raw_id, coeffs)
        messagebox.showinfo("Готово", "Параметры обновлены")

    def add_raw_type_dialog(self) -> None:
        win = tk.Toplevel(self)
        win.title("Добавить тип сырья")
        win.resizable(False, False)

        name_var = tk.StringVar()

        tk.Label(win, text="Название:").grid(row=0, column=0, padx=10, pady=10, sticky="e")
        tk.Entry(win, textvariable=name_var, width=25).grid(row=0, column=1, padx=10, pady=10)

        def on_ok():
            name = name_var.get().strip()
            if not name:
                messagebox.showwarning("Ошибка", "Введите название")
                return
            try:
                add_raw_type(name)
            except Exception:
                messagebox.showerror("Ошибка", "Такой тип уже существует")
                return
            self.reload_raw_list()
            win.destroy()

        ttk.Button(win, text="OK", command=on_ok).grid(row=1, column=0, columnspan=2, pady=10)


if __name__ == "__main__":
    App().mainloop()
