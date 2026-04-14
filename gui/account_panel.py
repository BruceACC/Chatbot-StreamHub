"""
account_panel.py
Left panel: shows account list with status indicators and add/delete controls.
"""

import customtkinter as ctk
import threading
from gui.proxy_tester import ProxyTesterWindow

C_BG       = "#0f0f14"
C_PANEL    = "#16161e"
C_SURFACE  = "#1e1e2a"
C_ACCENT   = "#53fc18"
C_TEXT     = "#e0e0e0"
C_MUTED    = "#888"
C_RED      = "#ff4444"
C_BORDER   = "#2a2a38"

STATUS_COLORS = {
    "idle":       "#888",
    "listo ✓":     "#53fc18",
    "iniciando…": "#f0a500",
    "listo":      "#53fc18",
    "enviando":    "#00aaff",
    "error":      "#ff4444",
    "detenido":    "#555",
}


class AccountCard(ctk.CTkFrame):
    def __init__(self, parent, name: str, status: str, on_delete: callable, **kwargs):
        super().__init__(parent, fg_color=C_SURFACE, corner_radius=8, **kwargs)
        self.name = name

        self.columnconfigure(1, weight=1)

        # Status dot
        self.dot = ctk.CTkLabel(self, text="●", font=ctk.CTkFont(size=14),
                                 text_color=STATUS_COLORS.get(status, C_MUTED))
        self.dot.grid(row=0, column=0, padx=(10, 6), pady=10)

        # Name
        self.name_lbl = ctk.CTkLabel(
            self, text=name,
            font=ctk.CTkFont("Segoe UI", 13, "bold"),
            text_color=C_TEXT, anchor="w"
        )
        self.name_lbl.grid(row=0, column=1, sticky="ew", pady=10)

        # Status text
        self.status_lbl = ctk.CTkLabel(
            self, text=status,
            font=ctk.CTkFont("Segoe UI", 10),
            text_color=STATUS_COLORS.get(status, C_MUTED)
        )
        self.status_lbl.grid(row=1, column=1, sticky="w", pady=(0, 8))

        # Delete button
        del_btn = ctk.CTkButton(
            self, text="✕", width=28, height=28,
            fg_color="#2a1a1a", hover_color="#3d1a1a",
            text_color=C_RED, corner_radius=6,
            command=lambda: on_delete(name)
        )
        del_btn.grid(row=0, column=2, padx=(0, 8), pady=10, rowspan=2)

    def update_status(self, status: str):
        color = STATUS_COLORS.get(status, C_MUTED)
        self.dot.configure(text_color=color)
        self.status_lbl.configure(text=status, text_color=color)


class AccountPanel(ctk.CTkFrame):
    def __init__(self, parent, on_add: callable, on_delete: callable, **kwargs):
        super().__init__(parent, corner_radius=12, **kwargs)
        self._on_add = on_add
        self._on_delete = on_delete
        self._cards: dict[str, AccountCard] = {}
        self._build()

    def _build(self):
        # Title
        header = ctk.CTkFrame(self, fg_color="transparent")
        header.pack(fill="x", padx=12, pady=(12, 8))

        ctk.CTkLabel(
            header, text="Gestión de Cuentas",
            font=ctk.CTkFont("Segoe UI", 14, "bold"),
            text_color=C_TEXT
        ).pack(side="left")

        # Scrollable list area
        self._list_frame = ctk.CTkScrollableFrame(
            self, fg_color="transparent", corner_radius=0
        )
        self._list_frame.pack(fill="both", expand=True, padx=8, pady=(0, 8))

        # Add Account section
        add_frame = ctk.CTkFrame(self, fg_color="#1a1a24", corner_radius=10)
        add_frame.pack(fill="x", padx=8, pady=(0, 12))

        ctk.CTkLabel(
            add_frame, text="Añadir Cuenta",
            font=ctk.CTkFont("Segoe UI", 12, "bold"),
            text_color=C_MUTED
        ).pack(anchor="w", padx=10, pady=(10, 4))

        self._name_entry = ctk.CTkEntry(
            add_frame,
            placeholder_text="Nombre de usuario...",
            fg_color=C_SURFACE,
            border_color=C_BORDER,
            text_color=C_TEXT,
            height=34,
        )
        self._name_entry.pack(fill="x", padx=10, pady=(0, 6))
        self._name_entry.bind("<Return>", lambda e: self._do_add())

        self._proxy_entry = ctk.CTkEntry(
            add_frame,
            placeholder_text="Proxy (opt) ip:puerto:usu:pass",
            fg_color=C_SURFACE,
            border_color=C_BORDER,
            text_color=C_TEXT,
            height=34,
        )
        self._proxy_entry.pack(fill="x", padx=10, pady=(0, 10))
        self._proxy_entry.bind("<Return>", lambda e: self._do_add())

        add_btn = ctk.CTkButton(
            add_frame,
            text="+ Conectar Navegador",
            fg_color=C_ACCENT,
            hover_color="#3acc10",
            text_color="#000",
            font=ctk.CTkFont("Segoe UI", 12, "bold"),
            height=36,
            corner_radius=8,
            command=self._do_add,
        )
        add_btn.pack(fill="x", padx=10, pady=(0, 6))

        test_btn = ctk.CTkButton(
            add_frame,
            text="🛠 Probar Proxies...",
            fg_color="#2a2a3a",
            hover_color="#3a3a4a",
            text_color="#ccc",
            font=ctk.CTkFont("Segoe UI", 11, "bold"),
            height=32,
            corner_radius=6,
            command=self._open_tester,
        )
        test_btn.pack(fill="x", padx=10, pady=(0, 10))

    def _open_tester(self):
        # Only open if it doesn't exist or was destroyed
        if not hasattr(self, '_tester_window') or not self._tester_window.winfo_exists():
            self._tester_window = ProxyTesterWindow(self.winfo_toplevel())
        self._tester_window.focus()

    def _do_add(self):
        name = self._name_entry.get().strip()
        proxy = self._proxy_entry.get().strip()
        if name:
            self._name_entry.delete(0, "end")
            self._proxy_entry.delete(0, "end")
            self._on_add(name, proxy)

    def set_accounts(self, accounts: list[dict]):
        # Clear existing cards
        for w in self._list_frame.winfo_children():
            w.destroy()
        self._cards = {}

        if not accounts:
            ctk.CTkLabel(
                self._list_frame,
                text="Aún no hay cuentas.\nHaz clic abajo para añadir una.",
                font=ctk.CTkFont("Segoe UI", 12),
                text_color=C_MUTED,
                justify="center"
            ).pack(expand=True, pady=30)
            return

        for acc in accounts:
            name = acc["name"]
            status = acc.get("status", "idle")
            card = AccountCard(
                self._list_frame, name, status,
                on_delete=self._on_delete,
            )
            card.pack(fill="x", pady=4)
            self._cards[name] = card

    def set_status(self, name: str, status: str):
        if name in self._cards:
            self._cards[name].update_status(status)
