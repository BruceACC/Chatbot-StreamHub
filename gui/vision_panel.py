"""
vision_panel.py
Standalone Vision HLS panel with cycle and capture status.
"""

import customtkinter as ctk

C_SURFACE = "#1e1e2a"
C_ACCENT = "#53fc18"
C_TEXT = "#e0e0e0"
C_MUTED = "#888"
C_BORDER = "#2a2a38"

VISION_TITLE = "Vision HLS"


class VisionPanel(ctk.CTkFrame):
    def __init__(self, parent, **kwargs):
        super().__init__(parent, corner_radius=12, **kwargs)
        self._build()

    def _build(self):
        ctk.CTkLabel(
            self,
            text=VISION_TITLE,
            font=ctk.CTkFont("Segoe UI", 14, "bold"),
            text_color=C_ACCENT,
        ).pack(anchor="w", padx=14, pady=(12, 6))

        body = ctk.CTkFrame(
            self,
            fg_color=C_SURFACE,
            corner_radius=10,
            border_width=1,
            border_color=C_BORDER,
        )
        body.pack(fill="both", expand=True, padx=12, pady=(0, 12))

        self._cycle_lbl = ctk.CTkLabel(
            body,
            text="T=--.-s | T/2=--.-s | T-5=--.-s",
            font=ctk.CTkFont("Segoe UI", 11, "bold"),
            text_color=C_TEXT,
            justify="left",
            wraplength=300,
        )
        self._cycle_lbl.pack(anchor="w", padx=12, pady=(10, 6))

        self._cycle_info_lbl = ctk.CTkLabel(
            body,
            text="Ciclo IA: inactivo",
            font=ctk.CTkFont("Segoe UI", 10, "bold"),
            text_color="#9fb6ff",
            justify="left",
            wraplength=300,
        )
        self._cycle_info_lbl.pack(anchor="w", padx=12, pady=(0, 6))

        self._capture_lbl = ctk.CTkLabel(
            body,
            text="Captura HLS: pendiente",
            font=ctk.CTkFont("Segoe UI", 10, "bold"),
            text_color=C_MUTED,
            justify="left",
            wraplength=300,
        )
        self._capture_lbl.pack(anchor="w", padx=12, pady=(0, 10))

    def set_cycle(self, cycle_index: int, t_s: float, t_half_s: float, t_minus_5_s: float):
        self._cycle_lbl.configure(
            text=f"T={t_s:.1f}s | T/2={t_half_s:.1f}s | T-5={t_minus_5_s:.1f}s"
        )
        self._cycle_info_lbl.configure(
            text=(
                f"Ciclo IA -> T={t_s:.1f}s (envio chat) | "
                f"T/2={t_half_s:.1f}s (captura) | "
                f"T-5={t_minus_5_s:.1f}s (respuesta IA)"
            )
        )
        self._capture_lbl.configure(text="Captura HLS: pendiente", text_color=C_MUTED)

    def set_cycle_info(self, text: str):
        self._cycle_info_lbl.configure(text=text)

    def set_capture_result(self, result: dict):
        success = bool(result.get("success"))
        if success:
            self._capture_lbl.configure(text="Captura HLS: OK", text_color=C_ACCENT)
        else:
            self._capture_lbl.configure(text="Captura HLS: FAIL", text_color="#ff6666")

    def reset(self):
        self._cycle_lbl.configure(text="T=--.-s | T/2=--.-s | T-5=--.-s")
        self._cycle_info_lbl.configure(text="Ciclo IA: inactivo")
        self._capture_lbl.configure(text="Captura HLS: pendiente", text_color=C_MUTED)
