import ctypes
import importlib.util
import os
import subprocess
import sys


def _show_startup_error(message: str) -> None:
    ctypes.windll.user32.MessageBoxW(None, message, "Моя музыка", 0x10)


def _check_dependencies() -> bool:
    required_modules = ("tkinter", "webbrowser", "music_library")
    missing = [
        name for name in required_modules if importlib.util.find_spec(name) is None
    ]
    if missing:
        _show_startup_error(
            "Не найдены необходимые компоненты: "
            + ", ".join(missing)
            + ". Переустановите приложение или Python с поддержкой Tcl/Tk."
        )
        return False
    return True


if not _check_dependencies():
    sys.exit(1)

if len(sys.argv) >= 3 and sys.argv[1] == "--webview":
    if importlib.util.find_spec("webview") is None:
        _show_startup_error(
            "Не найден встроенный браузер pywebview. "
            "Пересоберите приложение командой build_exe.bat."
        )
        sys.exit(1)
    from webview_window import run_browser_window

    run_browser_window(sys.argv[2])
    sys.exit(0)

import tkinter as tk
from tkinter import ttk

from music_library import UnsupportedMusicLink, parse_music_link


BACKGROUND = "#10131b"
CARD = "#191e29"
ACCENT = "#8b7cff"
TEXT = "#f4f5fb"
MUTED = "#a3a9ba"
ERROR = "#ff8585"


class MusicLibraryApp:
    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.root.title("Моя музыка")
        self.root.configure(bg=BACKGROUND)
        self.root.resizable(False, False)
        self.root.geometry("520x410")
        self._center_window()

        self.link = ""
        self.service_name = ""
        self.error_message = tk.StringVar()
        self._configure_styles()
        self._show_link_form()

    def _center_window(self) -> None:
        self.root.update_idletasks()
        width, height = 520, 410
        x = (self.root.winfo_screenwidth() - width) // 2
        y = (self.root.winfo_screenheight() - height) // 2
        self.root.geometry(f"{width}x{height}+{x}+{y}")

    def _configure_styles(self) -> None:
        style = ttk.Style(self.root)
        style.theme_use("clam")
        style.configure(
            "Music.TEntry",
            fieldbackground="#222836",
            foreground=TEXT,
            insertcolor=TEXT,
            bordercolor="#353c4d",
            lightcolor="#353c4d",
            darkcolor="#353c4d",
            padding=12,
        )
        style.configure(
            "Accent.TButton",
            background=ACCENT,
            foreground="#ffffff",
            borderwidth=0,
            padding=(16, 12),
            font=("Segoe UI Semibold", 10),
        )
        style.map(
            "Accent.TButton",
            background=[("active", "#7769e8"), ("disabled", "#514c79")],
        )
        style.configure(
            "Secondary.TButton",
            background=CARD,
            foreground=TEXT,
            borderwidth=0,
            padding=(14, 10),
            font=("Segoe UI", 9),
        )
        style.map("Secondary.TButton", background=[("active", "#252c3a")])

    def _new_page(self) -> tk.Frame:
        for child in self.root.winfo_children():
            child.destroy()
        page = tk.Frame(self.root, bg=BACKGROUND, padx=38, pady=32)
        page.pack(fill="both", expand=True)
        tk.Label(
            page,
            text="♫  MY MUSIC",
            bg=BACKGROUND,
            fg=ACCENT,
            font=("Segoe UI Semibold", 10),
        ).pack(anchor="w")
        return page

    def _show_link_form(self) -> None:
        self.error_message.set("")
        page = self._new_page()
        tk.Label(
            page,
            text="Где ваша музыка?",
            bg=BACKGROUND,
            fg=TEXT,
            font=("Segoe UI Semibold", 22),
        ).pack(anchor="w", pady=(26, 8))
        tk.Label(
            page,
            text="Вставьте ссылку на плейлист, альбом, профиль или трек.",
            bg=BACKGROUND,
            fg=MUTED,
            font=("Segoe UI", 10),
            wraplength=430,
            justify="left",
        ).pack(anchor="w", pady=(0, 20))

        self.link_entry = ttk.Entry(page, style="Music.TEntry", font=("Segoe UI", 10))
        self.link_entry.pack(fill="x")
        self.link_entry.bind("<Return>", lambda _event: self._connect())
        self.link_entry.focus_set()

        tk.Label(
            page,
            text="SoundCloud  ·  Яндекс Музыка  ·  Spotify\nYouTube  ·  YouTube Music",
            bg=BACKGROUND,
            fg=MUTED,
            font=("Segoe UI", 9),
        ).pack(anchor="w", pady=(12, 20))
        ttk.Button(
            page,
            text="Продолжить",
            style="Accent.TButton",
            command=self._connect,
        ).pack(fill="x")
        tk.Label(
            page,
            textvariable=self.error_message,
            bg=BACKGROUND,
            fg=ERROR,
            font=("Segoe UI", 9),
            wraplength=430,
            justify="left",
        ).pack(anchor="w", pady=(12, 0))
        tk.Label(
            page,
            text="Откройте ссылку во встроенном окне проигрывателя.",
            bg=BACKGROUND,
            fg=MUTED,
            font=("Segoe UI", 9),
        ).pack(anchor="w", side="bottom", pady=(16, 0))

    def _connect(self) -> None:
        try:
            service, link = parse_music_link(self.link_entry.get())
        except UnsupportedMusicLink as error:
            self.error_message.set(str(error))
            return

        self.link = link
        self.service_name = service.name
        self._show_library()

    def _show_library(self) -> None:
        self.error_message.set("")
        page = self._new_page()
        tk.Label(
            page,
            text="Ваша музыка",
            bg=BACKGROUND,
            fg=TEXT,
            font=("Segoe UI Semibold", 22),
        ).pack(anchor="w", pady=(26, 8))
        tk.Label(
            page,
            text="Сервис подключён",
            bg=BACKGROUND,
            fg=MUTED,
            font=("Segoe UI", 10),
        ).pack(anchor="w", pady=(0, 22))

        card = tk.Frame(page, bg=CARD, padx=18, pady=16)
        card.pack(fill="x")
        tk.Label(
            card,
            text=self.service_name,
            bg=CARD,
            fg=ACCENT,
            font=("Segoe UI Semibold", 11),
        ).pack(anchor="w")
        tk.Label(
            card,
            text=self.link,
            bg=CARD,
            fg=TEXT,
            font=("Segoe UI", 9),
            wraplength=390,
            justify="left",
        ).pack(anchor="w", pady=(8, 0))

        tk.Label(
            page,
            text="Откройте ссылку в сервисе, чтобы увидеть библиотеку "
            "и включить доступную вам музыку.",
            bg=BACKGROUND,
            fg=MUTED,
            font=("Segoe UI", 9),
            wraplength=430,
            justify="left",
        ).pack(anchor="w", pady=(18, 20))
        ttk.Button(
            page,
            text="Открыть в окне проигрывателя",
            style="Accent.TButton",
            command=self._open_link,
        ).pack(fill="x")
        ttk.Button(
            page,
            text="Изменить ссылку",
            style="Secondary.TButton",
            command=self._show_link_form,
        ).pack(fill="x", pady=(10, 0))
        tk.Label(
            page,
            textvariable=self.error_message,
            bg=BACKGROUND,
            fg=ERROR,
            font=("Segoe UI", 9),
            wraplength=430,
            justify="left",
        ).pack(anchor="w", pady=(10, 0))

    def _open_link(self) -> None:
        try:
            if getattr(sys, "frozen", False):
                command = [sys.executable, "--webview", self.link]
            else:
                command = [
                    sys.executable,
                    os.path.abspath(__file__),
                    "--webview",
                    self.link,
                ]
            subprocess.Popen(command)
        except OSError as error:
            self.error_message.set(
                f"Не удалось запустить окно проигрывателя: {error}"
            )


def main() -> None:
    try:
        root = tk.Tk()
    except tk.TclError as error:
        _show_startup_error(
            "Не удалось запустить графический интерфейс Tcl/Tk.\n\n"
            f"Проверьте установку Python или переустановите приложение.\n\n{error}"
        )
        sys.exit(1)
    MusicLibraryApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
