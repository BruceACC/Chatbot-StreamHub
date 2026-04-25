"""
config_panel.py
Channel + spam mode configuration panel.
"""

import customtkinter as ctk
from core.spam_engine import SpamConfig, SpamMode

C_PANEL   = "#16161e"
C_SURFACE = "#1e1e2a"
C_ACCENT  = "#53fc18"
C_TEXT    = "#e0e0e0"
C_MUTED   = "#888"
C_BORDER  = "#2a2a38"

MODES = ["Simultáneo", "Diferido", "Por Grupos"]
MODE_MAP = {
    "Simultáneo": SpamMode.SIMULTANEOUS,
    "Diferido":     SpamMode.DEFERRED,
    "Por Grupos":      SpamMode.GROUPED,
}
MODE_DESC = {
    "Simultáneo": "Todos los bots envían al mismo tiempo",
    "Diferido":     "Los bots envían con retraso aleatorio entre mínimo y máximo",
    "Por Grupos":      "Los bots se agrupan y envían con retraso aleatorio por grupo",
}

CHAT_TARGETS = ["kick.com canal", "kick.com popout chat"]
CHAT_TARGET_MAP = {
    "kick.com canal": "channel",
    "kick.com popout chat": "popout",
}


class ConfigPanel(ctk.CTkFrame):
    def __init__(self, parent, **kwargs):
        super().__init__(parent, corner_radius=12, **kwargs)
        self._build()

    def _build(self):
        # Section label
        ctk.CTkLabel(
            self, text="Configuración de Spam",
            font=ctk.CTkFont("Segoe UI", 14, "bold"),
            text_color="#e0e0e0"
        ).pack(anchor="w", padx=14, pady=(12, 6))

        # ── Channel Row ───────────────────────────────────────────
        row = ctk.CTkFrame(self, fg_color="transparent")
        row.pack(fill="x", padx=12, pady=(0, 8))
        row.columnconfigure(1, weight=1)

        ctk.CTkLabel(
            row, text="Canal :", font=ctk.CTkFont("Segoe UI", 12),
            text_color=C_MUTED, width=70, anchor="e"
        ).grid(row=0, column=0, sticky="e")

        prefix = ctk.CTkLabel(
            row, text="kick.com/",
            font=ctk.CTkFont("Segoe UI", 12),
            text_color=C_MUTED
        )
        prefix.grid(row=0, column=1, sticky="w", padx=(6, 0))

        self._channel_var = ctk.StringVar()
        self._channel_entry = ctk.CTkEntry(
            row,
            textvariable=self._channel_var,
            placeholder_text="ej. xqc",
            fg_color=C_SURFACE, border_color=C_BORDER,
            text_color=C_TEXT, height=34, width=180,
        )
        self._channel_entry.grid(row=0, column=2, padx=(2, 0), sticky="w")

        # ── Mode Row ─────────────────────────────────────────────
        row2 = ctk.CTkFrame(self, fg_color="transparent")
        row2.pack(fill="x", padx=12, pady=(0, 4))
        row2.columnconfigure(1, weight=1)

        ctk.CTkLabel(
            row2, text="Modo Spam :", font=ctk.CTkFont("Segoe UI", 12),
            text_color=C_MUTED, width=80, anchor="e"
        ).grid(row=0, column=0, sticky="e")

        self._mode_var = ctk.StringVar(value="Simultáneo")
        self._mode_menu = ctk.CTkOptionMenu(
            row2,
            values=MODES,
            variable=self._mode_var,
            fg_color=C_SURFACE,
            button_color="#2a2a3a",
            button_hover_color="#3a3a50",
            dropdown_fg_color=C_SURFACE,
            text_color=C_TEXT,
            width=180,
            height=34,
            command=self._on_mode_change,
        )
        self._mode_menu.grid(row=0, column=1, padx=6, sticky="w")

        # ── Chat Target Row ───────────────────────────────────────
        row_target = ctk.CTkFrame(self, fg_color="transparent")
        row_target.pack(fill="x", padx=12, pady=(0, 4))
        row_target.columnconfigure(1, weight=1)

        ctk.CTkLabel(
            row_target, text="Destino Chat :", font=ctk.CTkFont("Segoe UI", 12),
            text_color=C_MUTED, width=80, anchor="e"
        ).grid(row=0, column=0, sticky="e")

        self._chat_target_var = ctk.StringVar(value="kick.com popout chat")
        self._chat_target_menu = ctk.CTkOptionMenu(
            row_target,
            values=CHAT_TARGETS,
            variable=self._chat_target_var,
            fg_color=C_SURFACE,
            button_color="#2a2a3a",
            button_hover_color="#3a3a50",
            dropdown_fg_color=C_SURFACE,
            text_color=C_TEXT,
            width=220,
            height=34,
        )
        self._chat_target_menu.grid(row=0, column=1, padx=6, sticky="w")

        # Mode description
        self._mode_desc_lbl = ctk.CTkLabel(
            self, text=MODE_DESC["Simultáneo"],
            font=ctk.CTkFont("Segoe UI", 11, slant="italic"),
            text_color="#a0a0a0"
        )
        self._mode_desc_lbl.pack(anchor="w", padx=100, pady=(2, 6))

        # ── Delay + Group Row ────────────────────────────────────
        self._extra_row = ctk.CTkFrame(self, fg_color="transparent")
        self._extra_row.pack(fill="x", padx=12, pady=(0, 4))

        ctk.CTkLabel(
            self._extra_row, text="Retraso (s) :",
            font=ctk.CTkFont("Segoe UI", 12),
            text_color=C_MUTED, width=80, anchor="e"
        ).grid(row=0, column=0, sticky="e")

        self._delay_min_var = ctk.StringVar(value="40")
        self._delay_min_entry = ctk.CTkEntry(
            self._extra_row, textvariable=self._delay_min_var,
            fg_color=C_SURFACE, border_color=C_BORDER,
            text_color=C_TEXT, height=34, width=70,
        )
        self._delay_min_entry.grid(row=0, column=1, padx=(6, 2), sticky="w")

        self._delay_sep_lbl = ctk.CTkLabel(
            self._extra_row,
            text="a",
            font=ctk.CTkFont("Segoe UI", 12),
            text_color=C_MUTED,
        )
        self._delay_sep_lbl.grid(row=0, column=2, padx=(2, 2), sticky="w")

        self._delay_max_var = ctk.StringVar(value="120")
        self._delay_max_entry = ctk.CTkEntry(
            self._extra_row, textvariable=self._delay_max_var,
            fg_color=C_SURFACE, border_color=C_BORDER,
            text_color=C_TEXT, height=34, width=70,
        )
        self._delay_max_entry.grid(row=0, column=3, padx=(2, 6), sticky="w")

        self._group_lbl = ctk.CTkLabel(
            self._extra_row, text="Tamaño Grupo :",
            font=ctk.CTkFont("Segoe UI", 12),
            text_color=C_MUTED, anchor="e"
        )
        self._group_lbl.grid(row=0, column=4, sticky="e", padx=(12, 2))

        self._group_var = ctk.StringVar(value="2")
        self._group_entry = ctk.CTkEntry(
            self._extra_row, textvariable=self._group_var,
            fg_color=C_SURFACE, border_color=C_BORDER,
            text_color=C_TEXT, height=34, width=60,
        )
        self._group_entry.grid(row=0, column=5, padx=4, sticky="w")

        # ── Random + Loop Row ────────────────────────────────────
        opts_row = ctk.CTkFrame(self, fg_color="transparent")
        opts_row.pack(fill="x", padx=16, pady=(4, 12))

        self._random_var = ctk.BooleanVar(value=False)
        ctk.CTkCheckBox(
            opts_row,
            text="Mensaje aleatorio por bot",
            variable=self._random_var,
            font=ctk.CTkFont("Segoe UI", 12, "bold"),
            text_color=C_TEXT,
            fg_color=C_ACCENT,
            hover_color="#3acc10",
            checkmark_color="#000",
        ).pack(side="left", padx=(0, 20))

        self._loop_var = ctk.BooleanVar(value=True)
        ctk.CTkCheckBox(
            opts_row,
            text="Repetir infinitamente",
            variable=self._loop_var,
            font=ctk.CTkFont("Segoe UI", 12, "bold"),
            text_color=C_TEXT,
            fg_color=C_ACCENT,
            hover_color="#3acc10",
            checkmark_color="#000",
        ).pack(side="left")

        self._on_mode_change("Simultáneo")

    def _on_mode_change(self, mode: str):
        self._mode_desc_lbl.configure(text=MODE_DESC.get(mode, ""))
        show_group = mode == "Por Grupos"
        show_delay = mode in ("Diferido", "Por Grupos", "Simultáneo")

        # Group controls visibility
        if show_group:
            self._group_lbl.grid()
            self._group_entry.grid()
        else:
            self._group_lbl.grid_remove()
            self._group_entry.grid_remove()

    def get_channel(self) -> str:
        return self._channel_var.get().strip().lstrip("/")

    def get_chat_target(self) -> str:
        selected = self._chat_target_var.get()
        return CHAT_TARGET_MAP.get(selected, "popout")

    def get_spam_config(self) -> SpamConfig:
        mode_str = self._mode_var.get()
        mode = MODE_MAP.get(mode_str, SpamMode.SIMULTANEOUS)
        try:
            delay_min = float(self._delay_min_var.get())
        except ValueError:
            delay_min = 3.0
        try:
            delay_max = float(self._delay_max_var.get())
        except ValueError:
            delay_max = 5.0
        try:
            group_size = int(self._group_var.get())
        except ValueError:
            group_size = 2

        delay_min = max(0.5, delay_min)
        delay_max = max(0.5, delay_max)
        low = min(delay_min, delay_max)
        high = max(delay_min, delay_max)

        return SpamConfig(
            mode=mode,
            delay=high,
            delay_min=low,
            delay_max=high,
            group_size=max(1, group_size),
            random_messages=self._random_var.get(),
            loop=self._loop_var.get(),
        )
