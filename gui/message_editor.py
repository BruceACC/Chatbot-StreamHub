"""
message_editor.py
Center-bottom panel: multiline text area where each line is one message.
"""

import customtkinter as ctk

from core.app_settings import load_settings, save_settings
from core.ollama_client import DEFAULT_OLLAMA_URL, LOCAL_OLLAMA_URL, REMOTE_OLLAMA_URL

C_PANEL   = "#16161e"
C_SURFACE = "#1e1e2a"
C_ACCENT  = "#53fc18"
C_TEXT    = "#e0e0e0"
C_MUTED   = "#e0e0e0"
C_BORDER  = "#2a2a38"
MSG_BOX_BASE_HEIGHT = 10


class MessageEditor(ctk.CTkFrame):
    def __init__(
        self,
        parent,
        on_change: callable = None,
        on_ai_request: callable = None,
        on_stt_toggle: callable = None,
        on_stt_refresh_devices: callable = None,
        **kwargs,
    ):
        super().__init__(parent, corner_radius=12, **kwargs)
        self.on_change = on_change
        self.on_ai_request = on_ai_request
        self.on_stt_toggle = on_stt_toggle
        self.on_stt_refresh_devices = on_stt_refresh_devices
        self._build()

    def _build(self):
        # Header row
        header = ctk.CTkFrame(self, fg_color="transparent")
        header.pack(fill="x", padx=14, pady=(12, 4))

        ctk.CTkLabel(
            header, text="Panel de Mensajes",
            font=ctk.CTkFont("Segoe UI", 14, "bold"),
            text_color="#e0e0e0"
        ).pack(side="left")

        self._line_count_lbl = ctk.CTkLabel(
            header, text="0 mensajes",
            font=ctk.CTkFont("Segoe UI", 11, "bold"),
            text_color=C_MUTED
        )
        self._line_count_lbl.pack(side="right")

        # Hint
        ctk.CTkLabel(
            self,
            text="Cada línea = 1 mensaje distinto  •  Se envían de arriba abajo o al azar",
            font=ctk.CTkFont("Segoe UI", 11, slant="italic"),
            text_color=C_MUTED
        ).pack(anchor="w", padx=14, pady=(0, 6))

        # Whisper transcription controls (compact and visible)
        stt_box = ctk.CTkFrame(self, fg_color="#191924", corner_radius=10)
        stt_box.pack(fill="x", padx=12, pady=(0, 8))
        stt_box.columnconfigure(1, weight=1)
        stt_box.columnconfigure(3, weight=0)

        ctk.CTkLabel(
            stt_box,
            text="Transcribir audio (Whisper)",
            font=ctk.CTkFont("Segoe UI", 11, "bold"),
            text_color=C_MUTED,
        ).grid(row=0, column=0, columnspan=5, sticky="w", padx=10, pady=(8, 4))

        ctk.CTkLabel(
            stt_box,
            text="Entrada:",
            font=ctk.CTkFont("Segoe UI", 11, "bold"),
            text_color=C_MUTED,
        ).grid(row=1, column=0, sticky="w", padx=(10, 6), pady=(0, 8))

        self._stt_device_combo = ctk.CTkComboBox(
            stt_box,
            height=30,
            corner_radius=6,
            fg_color=C_SURFACE,
            border_color=C_BORDER,
            text_color=C_TEXT,
            values=["CABLE Output"],
        )
        self._stt_device_combo.grid(row=1, column=1, sticky="ew", padx=(0, 8), pady=(0, 8))
        self._stt_device_combo.set("CABLE Output")

        self._stt_refresh_btn = ctk.CTkButton(
            stt_box,
            text="Refrescar",
            width=90,
            height=30,
            fg_color=C_SURFACE,
            hover_color="#25253a",
            text_color=C_TEXT,
            corner_radius=6,
            font=ctk.CTkFont("Segoe UI", 11, "bold"),
            command=self._refresh_stt_devices,
        )
        self._stt_refresh_btn.grid(row=1, column=2, sticky="w", padx=(0, 8), pady=(0, 8))

        self._stt_model_entry = ctk.CTkEntry(
            stt_box,
            width=72,
            height=30,
            corner_radius=6,
            fg_color=C_SURFACE,
            border_color=C_BORDER,
            text_color=C_TEXT,
        )
        self._stt_model_entry.grid(row=1, column=3, sticky="e", padx=(0, 8), pady=(0, 8))
        self._stt_model_entry.insert(0, "medium")

        self._stt_btn = ctk.CTkButton(
            stt_box,
            text="Iniciar Transcrip.",
            width=140,
            height=30,
            fg_color="#256c2c",
            hover_color="#1e5523",
            text_color="#eaffea",
            corner_radius=6,
            font=ctk.CTkFont("Segoe UI", 11, "bold"),
            command=self._toggle_stt,
        )
        self._stt_btn.grid(row=1, column=4, sticky="e", padx=(0, 10), pady=(0, 8))

        self._save_txt_btn = ctk.CTkButton(
            stt_box,
            text="Guardar TXT",
            width=110,
            height=28,
            fg_color=C_SURFACE,
            hover_color="#25253a",
            text_color=C_TEXT,
            corner_radius=6,
            font=ctk.CTkFont("Segoe UI", 11, "bold"),
            command=self._save_transcript,
        )
        self._save_txt_btn.grid(row=2, column=0, sticky="w", padx=(10, 0), pady=(0, 10))

        txt_tools_row = ctk.CTkFrame(stt_box, fg_color="transparent")
        txt_tools_row.grid(row=2, column=1, columnspan=4, sticky="w", padx=(8, 0), pady=(0, 10))

        ctk.CTkButton(
            txt_tools_row,
            text="📄 Cargar desde .txt",
            width=150,
            height=28,
            fg_color=C_SURFACE,
            hover_color="#25253a",
            text_color=C_TEXT,
            corner_radius=6,
            font=ctk.CTkFont("Segoe UI", 11, "bold"),
            command=self._load_file,
        ).pack(side="left", padx=(0, 6))

        ctk.CTkButton(
            txt_tools_row,
            text="🗑 Limpiar",
            width=94,
            height=28,
            fg_color="#2a1a1a",
            hover_color="#3d1a1a",
            text_color="#ff6666",
            corner_radius=6,
            font=ctk.CTkFont("Segoe UI", 11, "bold"),
            command=self._clear,
        ).pack(side="left", padx=(0, 10))

        ctk.CTkLabel(
            txt_tools_row,
            text="Prefijo:",
            font=ctk.CTkFont("Segoe UI", 11, "bold"),
            text_color=C_MUTED,
        ).pack(side="left", padx=(0, 6))

        self._prefix_entry = ctk.CTkEntry(
            txt_tools_row,
            width=82,
            height=28,
            corner_radius=6,
            fg_color=C_SURFACE,
            border_color=C_BORDER,
            text_color=C_TEXT,
            placeholder_text="!tts",
        )
        self._prefix_entry.pack(side="left", padx=(0, 10))
     #   self._prefix_entry.insert(0, "")

        ctk.CTkLabel(
            txt_tools_row,
            text="Max:",
            font=ctk.CTkFont("Segoe UI", 11, "bold"),
            text_color=C_MUTED,
        ).pack(side="left", padx=(0, 6))

        self._max_chars_entry = ctk.CTkEntry(
            txt_tools_row,
            width=35,
            height=28,
            corner_radius=6,
            fg_color=C_SURFACE,
            border_color=C_BORDER,
            text_color=C_TEXT,
            placeholder_text="60",
        )
        self._max_chars_entry.pack(side="left")
        self._max_chars_entry.insert(0, "60")

        # Text area
        self._textbox = ctk.CTkTextbox(
            self,
            height=MSG_BOX_BASE_HEIGHT,
            fg_color=C_SURFACE,
            border_color=C_BORDER,
            border_width=1,
            text_color=C_TEXT,
            font=ctk.CTkFont("Consolas", 13),
            wrap="none",
            corner_radius=8,
        )
        self._textbox.pack(fill="both", expand=True, padx=12, pady=(0, 6))
        self._textbox.bind("<KeyRelease>", self._update_count)
        self._textbox.bind("<FocusIn>", self._update_textbox_placeholder)
        self._textbox.bind("<FocusOut>", self._update_textbox_placeholder)

        self._textbox_placeholder = ctk.CTkLabel(
            self,
            text="Las respuestas se muestran aqui...",
            font=ctk.CTkFont("Segoe UI", 12, slant="italic"),
            text_color=C_MUTED,
            fg_color=C_SURFACE,
        )
        self._textbox_placeholder.place(in_=self._textbox, x=12, y=10, anchor="nw")

        # AI row
        ai_row = ctk.CTkFrame(self, fg_color="transparent")
        ai_row.pack(fill="x", padx=12, pady=(0, 12))
        ai_row.columnconfigure(2, weight=1)

        ctk.CTkLabel(
            ai_row,
            text="Modelo:",
            font=ctk.CTkFont("Segoe UI", 11, "bold"),
            text_color=C_MUTED,
        ).grid(row=0, column=0, sticky="w", padx=(0, 6), pady=(0, 6))

        self._model_entry = ctk.CTkEntry(
            ai_row,
            width=120,
            height=30,
            corner_radius=6,
            fg_color=C_SURFACE,
            border_color=C_BORDER,
            text_color=C_TEXT,
        )
        self._model_entry.grid(row=0, column=1, sticky="w", pady=(0, 6))
        self._model_entry.insert(0, "qwen2.5vl:7b-q4_K_M")

        ollama_row = ctk.CTkFrame(self, fg_color="transparent")
        ollama_row.pack(fill="x", padx=12, pady=(0, 8))

        ctk.CTkLabel(
            ollama_row,
            text="Ollama:",
            font=ctk.CTkFont("Segoe UI", 11, "bold"),
            text_color=C_MUTED,
        ).pack(side="left", padx=(0, 8))

        self._ollama_mode_var = ctk.StringVar(value=self._default_ollama_mode())

        ctk.CTkRadioButton(
            ollama_row,
            text="Local",
            value="local",
            variable=self._ollama_mode_var,
            fg_color=C_ACCENT,
            hover_color="#3acc10",
            text_color=C_TEXT,
            command=self._save_ollama_url,
        ).pack(side="left", padx=(0, 10))

        ctk.CTkRadioButton(
            ollama_row,
            text="Red",
            value="red",
            variable=self._ollama_mode_var,
            fg_color=C_ACCENT,
            hover_color="#3acc10",
            text_color=C_TEXT,
            command=self._save_ollama_url,
        ).pack(side="left")

        ctk.CTkLabel(
            ollama_row,
            text="Selecciona dónde corre la IA",
            font=ctk.CTkFont("Segoe UI", 10),
            text_color=C_MUTED,
        ).pack(side="right")

        self._ai_input = ctk.CTkEntry(
            ai_row,
            height=34,
            corner_radius=8,
            placeholder_text="Escribe aquí para que la IA responda...",
            fg_color=C_SURFACE,
            border_color=C_BORDER,
            text_color=C_TEXT,
        )
        self._ai_input.grid(row=0, column=2, sticky="ew", padx=(12, 8), pady=(0, 6))
        self._ai_input.bind("<Return>", self._ask_ai)

        self._ask_ai_btn = ctk.CTkButton(
            ai_row,
            text="Responder IA",
            width=120,
            height=34,
            fg_color=C_ACCENT,
            hover_color="#3acc10",
            text_color="#000",
            corner_radius=8,
            font=ctk.CTkFont("Segoe UI", 12, "bold"),
            command=self._ask_ai,
        )
        self._ask_ai_btn.grid(row=0, column=3, sticky="e", pady=(0, 6))

        self._stt_running = False
        self._update_textbox_placeholder()

    def _ask_ai(self, event=None):
        prompt = self._ai_input.get().strip()
        if not prompt or not self.on_ai_request:
            return
        model = self._model_entry.get().strip() or "llama3"
        self.set_ai_busy(True)
        self.on_ai_request(prompt, model)

    def _toggle_stt(self):
        if not self.on_stt_toggle:
            return
        if self._stt_running:
            self.on_stt_toggle(False, "", "")
            return
        device_hint = self._stt_device_combo.get().strip() or "CABLE Output"
        model_size = self._stt_model_entry.get().strip() or "medium"
        self.on_stt_toggle(True, device_hint, model_size)

    def _refresh_stt_devices(self):
        if not self.on_stt_refresh_devices:
            return
        self.on_stt_refresh_devices()

    def _save_transcript(self):
        from tkinter import filedialog

        content = self.get_text().strip()
        if not content:
            return

        path = filedialog.asksaveasfilename(
            title="Guardar transcripcion",
            defaultextension=".txt",
            filetypes=[("Text files", "*.txt"), ("Todos los archivos", "*.*")],
        )
        if not path:
            return
        try:
            with open(path, "w", encoding="utf-8") as f:
                f.write(content)
        except Exception:
            pass

    def _update_count(self, event=None):
        text = self._textbox.get("1.0", "end-1c")
        lines = [l for l in text.splitlines() if l.strip()]
        self._line_count_lbl.configure(
            text=f"{len(lines)} mensaje{'s' if len(lines) != 1 else ''}"
        )
        self._update_textbox_placeholder()
        if self.on_change:
            self.on_change(text)

    def _update_textbox_placeholder(self, event=None):
        has_text = bool(self._textbox.get("1.0", "end-1c").strip())
        if has_text:
            self._textbox_placeholder.place_forget()
            return
        self._textbox_placeholder.place(in_=self._textbox, x=12, y=10, anchor="nw")

    def _clear(self):
        self._textbox.delete("1.0", "end")
        self._update_count()

    def clear_messages(self):
        self._clear()

    def _load_file(self):
        from tkinter import filedialog
        path = filedialog.askopenfilename(
            title="Seleccionar archivo de mensajes",
            filetypes=[("Text files", "*.txt"), ("Todos los archivos", "*.*")]
        )
        if path:
            try:
                with open(path, "r", encoding="utf-8") as f:
                    content = f.read()
                self._textbox.delete("1.0", "end")
                self._textbox.insert("1.0", content)
                self._update_count()
            except Exception as e:
                pass

    def get_text(self) -> str:
        return self._textbox.get("1.0", "end-1c")

    def append_message(self, text: str):
        if not text.strip():
            return
        current = self.get_text().strip()
        joined = f"{current}\n{text}" if current else text
        self._textbox.delete("1.0", "end")
        self._textbox.insert("1.0", joined)
        self._update_count()

    def set_ai_busy(self, busy: bool):
        self._ask_ai_btn.configure(state="disabled" if busy else "normal")

    def clear_ai_input(self):
        self._ai_input.delete(0, "end")

    def get_ai_input(self) -> str:
        return self._ai_input.get().strip()

    def append_ai_input(self, text: str):
        cleaned = (text or "").strip()
        if not cleaned:
            return

        current = self._ai_input.get().strip()
        joined = f"{current} {cleaned}".strip() if current else cleaned
        self._ai_input.delete(0, "end")
        self._ai_input.insert(0, joined)

    def set_stt_running(self, running: bool):
        self._stt_running = running
        if running:
            self._stt_btn.configure(text="Detener Transcrip.", fg_color="#6b2525", hover_color="#552020")
            self._stt_device_combo.configure(state="disabled")
            self._stt_model_entry.configure(state="disabled")
            self._stt_refresh_btn.configure(state="disabled")
        else:
            self._stt_btn.configure(text="Iniciar Transcrip.", fg_color="#256c2c", hover_color="#1e5523")
            self._stt_device_combo.configure(state="normal")
            self._stt_model_entry.configure(state="normal")
            self._stt_refresh_btn.configure(state="normal")

    def set_stt_devices(self, devices: list[str]):
        values = devices if devices else ["CABLE Output"]
        self._stt_device_combo.configure(values=values)
        current = self._stt_device_combo.get().strip()
        if current in values:
            self._stt_device_combo.set(current)
            return

        cable_match = next((d for d in values if "cable output" in d.lower()), None)
        self._stt_device_combo.set(cable_match or values[0])

    def is_stt_running(self) -> bool:
        return self._stt_running

    def get_ai_model(self) -> str:
        return self._model_entry.get().strip() or "qwen2.5vl:7b-q4_K_M"

    def get_ollama_url(self) -> str:
        if self._ollama_mode_var.get() == "red":
            return REMOTE_OLLAMA_URL
        return LOCAL_OLLAMA_URL

    def get_ollama_mode(self) -> str:
        return self._ollama_mode_var.get().strip() or "local"

    def _load_ollama_mode(self) -> str:
        settings = load_settings()
        saved_mode = str(settings.get("ollama_mode", "")).strip().lower()
        if saved_mode in ("local", "red"):
            return saved_mode

        saved_url = str(settings.get("ollama_url", "")).strip().rstrip("/")
        if saved_url == REMOTE_OLLAMA_URL:
            return "red"
        if saved_url == LOCAL_OLLAMA_URL:
            return "local"

        if saved_url:
            return "red"

        normalized = DEFAULT_OLLAMA_URL.rstrip("/")
        if normalized == REMOTE_OLLAMA_URL:
            return "red"
        return "local"

    def _default_ollama_mode(self) -> str:
        return self._load_ollama_mode()

    def _save_ollama_url(self):
        try:
            save_settings(
                {
                    "ollama_mode": self.get_ollama_mode(),
                    "ollama_url": self.get_ollama_url(),
                }
            )
        except Exception:
            pass

    def get_ai_prefix(self) -> str:
        return self._prefix_entry.get().strip()

    def get_ai_max_chars(self) -> int:
        raw = self._max_chars_entry.get().strip()
        try:
            value = int(raw)
        except ValueError:
            value = 60
        return max(1, min(500, value))

