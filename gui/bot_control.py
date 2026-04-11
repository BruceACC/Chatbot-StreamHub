"""
bot_control.py
Right panel: Start/Stop controls + live log.
"""

import customtkinter as ctk
from datetime import datetime

C_SURFACE = "#1e1e2a"
C_ACCENT  = "#53fc18"
C_RED     = "#ff4444"
C_TEXT    = "#e0e0e0"
C_MUTED   = "#888"
C_BORDER  = "#2a2a38"

MAX_LOG_LINES = 200


class BotControl(ctk.CTkFrame):
    def __init__(self, parent, on_start: callable, on_stop: callable, **kwargs):
        super().__init__(parent, corner_radius=12, **kwargs)
        self._on_start = on_start
        self._on_stop = on_stop
        self._running = False
        self._build()

    def _build(self):
        # Title
        ctk.CTkLabel(
            self, text="Control Central",
            font=ctk.CTkFont("Segoe UI", 14, "bold"),
            text_color="#e0e0e0"
        ).pack(anchor="w", padx=14, pady=(12, 8))

        # Start / Stop buttons
        btn_frame = ctk.CTkFrame(self, fg_color="transparent")
        btn_frame.pack(fill="x", padx=12, pady=(0, 8))
        btn_frame.columnconfigure(0, weight=1)
        btn_frame.columnconfigure(1, weight=1)

        self._start_btn = ctk.CTkButton(
            btn_frame,
            text="▶  Iniciar Todo",
            font=ctk.CTkFont("Segoe UI", 13, "bold"),
            fg_color=C_ACCENT,
            hover_color="#3acc10",
            text_color="#000",
            height=42,
            corner_radius=10,
            command=self._do_start,
        )
        self._start_btn.grid(row=0, column=0, sticky="ew", padx=(0, 4))

        self._stop_btn = ctk.CTkButton(
            btn_frame,
            text="■  Detener Todo",
            font=ctk.CTkFont("Segoe UI", 13, "bold"),
            fg_color="#2a0a0a",
            hover_color="#400a0a",
            text_color=C_RED,
            height=42,
            corner_radius=10,
            state="disabled",
            command=self._do_stop,
        )
        self._stop_btn.grid(row=0, column=1, sticky="ew", padx=(4, 0))

        # Status indicator
        self._status_lbl = ctk.CTkLabel(
            self, text="● Inactivo",
            font=ctk.CTkFont("Segoe UI", 12, "bold"),
            text_color=C_MUTED,
        )
        self._status_lbl.pack(anchor="w", padx=14, pady=(0, 8))

        # Divider label
        ctk.CTkLabel(
            self, text="Registro de Actividad",
            font=ctk.CTkFont("Segoe UI", 12, "bold"),
            text_color=C_MUTED
        ).pack(anchor="w", padx=14, pady=(0, 4))

        # Log area
        self._log_box = ctk.CTkTextbox(
            self,
            fg_color=C_SURFACE,
            border_color=C_BORDER,
            border_width=1,
            text_color="#b0ffb0",
            font=ctk.CTkFont("Consolas", 11),
            state="disabled",
            corner_radius=8,
        )
        self._log_box.pack(fill="both", expand=True, padx=12, pady=(0, 8))

        # Clear log
        ctk.CTkButton(
            self, text="Limpiar Registro",
            width=110, height=28,
            fg_color=C_SURFACE, hover_color="#25253a",
            text_color=C_MUTED, corner_radius=6, font=ctk.CTkFont("Segoe UI", 11, "bold"),
            command=self._clear_log,
        ).pack(anchor="e", padx=12, pady=(0, 12))

    def _do_start(self):
        self._on_start()

    def _do_stop(self):
        self._on_stop()

    def set_running(self, running: bool):
        self._running = running
        if running:
            self._start_btn.configure(state="disabled")
            self._stop_btn.configure(state="normal")
            self._status_lbl.configure(text="● En Ejecución", text_color=C_ACCENT)
        else:
            self._start_btn.configure(state="normal")
            self._stop_btn.configure(state="disabled")
            self._status_lbl.configure(text="● Inactivo", text_color=C_MUTED)

    def log(self, message: str):
        """Append a timestamped line to the log box."""
        ts = datetime.now().strftime("%H:%M:%S")
        line = f"[{ts}] {message}\n"

        self._log_box.configure(state="normal")

        # Trim old lines if too many
        content = self._log_box.get("1.0", "end-1c")
        lines = content.splitlines()
        if len(lines) >= MAX_LOG_LINES:
            self._log_box.delete("1.0", f"{len(lines) - MAX_LOG_LINES + 1}.0")

        self._log_box.insert("end", line)
        self._log_box.see("end")
        self._log_box.configure(state="disabled")

    def _clear_log(self):
        self._log_box.configure(state="normal")
        self._log_box.delete("1.0", "end")
        self._log_box.configure(state="disabled")
