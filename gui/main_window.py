"""
main_window.py
Main application window for KickBot.
Three-column layout: Accounts | Config+Messages | Status Log
"""

import customtkinter as ctk
import threading
import logging
import random
import time

from core.session_manager import load_accounts, add_account, delete_account, has_session
from core.bot_worker import BotWorker
from core.spam_engine import SpamEngine, SpamConfig, SpamMode
from core.browser_manager import shutdown_shared_browser_manager
from core.hls_capture import capture_hls_snapshot
from core.message_pool import MessagePool
from core.ollama_client import generate_ollama_response, truncate_chat_text_ignoring_emotes
from core.audio_transcriber import LiveAudioTranscriber
from gui.account_panel import AccountPanel
from gui.config_panel import ConfigPanel
from gui.vision_panel import VisionPanel
from gui.message_editor import MessageEditor
from gui.bot_control import BotControl

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
)
logger = logging.getLogger(__name__)

ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")

# Brand colors
C_BG       = "#0f0f14"
C_PANEL    = "#16161e"
C_SURFACE  = "#1e1e2a"
C_ACCENT   = "#53fc18"   # Kick green
C_ACCENT2  = "#7B5EA7"
C_TEXT     = "#e0e0e0"
C_MUTED    = "#888"
C_RED      = "#ff4444"
C_BORDER   = "#2a2a38"


class MainWindow(ctk.CTk):
    def __init__(self):
        super().__init__()

        self.title("KickBot — Bot de Chat Multicuentas")
        self.geometry("1200x720")
        self.minsize(900, 600)
        self.configure(fg_color=C_BG)

        self._workers: dict[str, BotWorker] = {}
        self._pool = MessagePool()
        self._engine = SpamEngine()
        self._engine.on_log = self._on_engine_log
        self._engine_running = False
        self._transcriber: LiveAudioTranscriber | None = None
        self._stt_clear_job_id = None
        self._stt_clear_ms = 2 * 60 * 1000
        self._auto_ai_job_id = None
        self._auto_ai_capture_job_id = None
        self._auto_ai_cycle_end_job_id = None
        self._auto_ai_delay_s = 120.0
        self._auto_ai_delay_min_s = 40.0
        self._auto_ai_delay_max_s = 120.0
        self._auto_ai_cycle_index = 0
        self._auto_ai_cycle_t_s = 0.0
        self._ai_request_inflight = False
        self._ai_request_started_at = 0.0
        self._ai_request_timeout_s = 180.0
        self._auto_ai_empty_logged = False
        self._auto_ai_busy_logged = False
        self._capture_inflight = False
        self._latest_capture_image_b64 = ""
        self._poll_status_job_id = None

        self._build_ui()
        self._refresh_accounts()
        self.protocol("WM_DELETE_WINDOW", self._on_close)

    def _build_ui(self):
        # ── Header ────────────────────────────────────────────────
        header = ctk.CTkFrame(self, fg_color=C_PANEL, height=56, corner_radius=0)
        header.pack(fill="x", side="top")

        logo_lbl = ctk.CTkLabel(
            header,
            text="⚡ KickBot",
            font=ctk.CTkFont("Segoe UI", 22, "bold"),
            text_color=C_ACCENT,
        )
        logo_lbl.pack(side="left", padx=20)

        sub_lbl = ctk.CTkLabel(
            header,
            text="Automatización de Chat",
            font=ctk.CTkFont("Segoe UI", 12),
            text_color=C_MUTED,
        )
        sub_lbl.pack(side="left", padx=4)

        # ── Main Content ──────────────────────────────────────────
        content = ctk.CTkFrame(self, fg_color=C_BG, corner_radius=0)
        content.pack(fill="both", expand=True, padx=0, pady=0)
        content.columnconfigure(0, weight=0, minsize=230)
        content.columnconfigure(1, weight=1)
        content.columnconfigure(2, weight=0, minsize=300)
        content.rowconfigure(0, weight=1)

        # Left: Accounts
        self.account_panel = AccountPanel(
            content,
            on_add=self._on_add_account,
            on_delete=self._on_delete_account,
            fg_color=C_PANEL,
        )
        self.account_panel.grid(row=0, column=0, sticky="nsew", padx=(8, 4), pady=8)

        # Center: Config + Message Editor
        center = ctk.CTkFrame(content, fg_color=C_BG, corner_radius=0)
        center.grid(row=0, column=1, sticky="nsew", padx=4, pady=8)
        center.rowconfigure(0, weight=0)
        center.rowconfigure(1, weight=1)
        center.columnconfigure(0, weight=1)

        top_row = ctk.CTkFrame(center, fg_color=C_BG, corner_radius=0)
        top_row.grid(row=0, column=0, sticky="ew", pady=(0, 6))
        top_row.columnconfigure(0, weight=1)
        top_row.columnconfigure(1, weight=0)

        self.config_panel = ConfigPanel(top_row, fg_color=C_PANEL)
        self.config_panel.grid(row=0, column=0, sticky="ew", padx=(0, 6))

        self.vision_panel = VisionPanel(top_row, fg_color=C_PANEL, width=350)
        self.vision_panel.grid(row=0, column=1, sticky="ns")
        self.vision_panel.grid_propagate(False)

        self.message_editor = MessageEditor(
            center,
            fg_color=C_PANEL,
            on_change=self._on_message_changed,
            on_ai_request=self._on_ai_request,
            on_stt_toggle=self._on_stt_toggle,
            on_stt_refresh_devices=self._refresh_stt_devices,
        )
        self.message_editor.grid(row=1, column=0, sticky="nsew")

        # Right: Bot Control + Status Log
        self.bot_control = BotControl(
            content,
            on_start=self._on_start,
            on_stop=self._on_stop,
            fg_color=C_PANEL,
        )
        self.bot_control.grid(row=0, column=2, sticky="nsew", padx=(4, 8), pady=8)

        self.bot_control.set_on_refresh(self._on_refresh_config)

        self._refresh_stt_devices()

    def _get_target_ai_response_count(self) -> int:
        cfg = self.config_panel.get_spam_config()

        if self._workers:
            account_count = len(self._workers)
        else:
            account_count = len(load_accounts())

        account_count = max(1, account_count)

        if cfg.mode == SpamMode.SIMULTANEOUS:
            return account_count
        if cfg.mode == SpamMode.DEFERRED:
            return 1
        if cfg.mode == SpamMode.GROUPED:
            return max(1, min(account_count, int(cfg.group_size)))
        return account_count

    def _on_message_changed(self, text: str):
        self._pool.set_text(text)

    def _on_ai_request(
        self,
        prompt: str,
        model: str,
        image_base64: str | None = None,
        response_count_override: int | None = None,
    ):
        self._ai_request_inflight = True
        self._ai_request_started_at = time.monotonic()
        default_count = self._get_target_ai_response_count()
        response_count = max(1, int(response_count_override)) if response_count_override is not None else default_count
        max_chars = self.message_editor.get_ai_max_chars()

        self.bot_control.log(f"🤖 Consultando IA ({model})...")
        if response_count > 1:
            self.bot_control.log(
                f"🤖 Generando {response_count} respuestas (una por cuenta, max {max_chars})."
            )
        thread = threading.Thread(
            target=self._ask_ollama_thread,
            args=(prompt, model, response_count, max_chars, image_base64),
            daemon=True,
        )
        thread.start()

    def _ask_ollama_thread(
        self,
        prompt: str,
        model: str,
        response_count: int = 1,
        max_chars: int = 500,
        image_base64: str | None = None,
    ):
        try:
            answers: list[str] = []
            total = max(1, int(response_count))
            for idx in range(total):
                if total > 1:
                    variant_prompt = (
                        f"{prompt}\n\n"
                        f"Genera una variante distinta de chat para la cuenta #{idx + 1} de {total}. "
                        "Debe ser diferente a las otras variantes, natural y breve."
                    )
                else:
                    variant_prompt = prompt

                emote_only = random.random() < 0.30
                answer = generate_ollama_response(
                    variant_prompt,
                    model=model,
                    max_chars=max_chars,
                    emote_only=emote_only,
                    image_base64=image_base64,
                )
                answers.append(truncate_chat_text_ignoring_emotes(answer, max_chars))

            self.after(0, lambda: self._on_ai_success(answers, model, max_chars))
        except Exception as e:
            self.after(0, lambda: self._on_ai_error(str(e)))

    def _on_ai_success(self, answers: list[str], model: str, max_chars: int):
        safe_answers = [self._format_ai_message(a, max_chars=max_chars) for a in answers if a and a.strip()]
        if not safe_answers:
            self._on_ai_error("La IA no devolvio contenido util.")
            return

        self.message_editor.clear_messages()
        for answer in safe_answers:
            self.message_editor.append_message(answer)
        self.message_editor.clear_ai_input()
        if len(safe_answers) == 1:
            self.bot_control.log(f"🤖 Respuesta recibida de {model}.")
        else:
            self.bot_control.log(f"🤖 {len(safe_answers)} respuestas recibidas de {model}.")
        self.message_editor.set_ai_busy(False)
        self._ai_request_inflight = False
        self._ai_request_started_at = 0.0
        self._auto_ai_busy_logged = False

    def _on_ai_error(self, error: str):
        self.bot_control.log(f"⚠ Error IA: {error}")
        self.message_editor.set_ai_busy(False)
        self._ai_request_inflight = False
        self._ai_request_started_at = 0.0
        self._auto_ai_busy_logged = False

    def _on_stt_toggle(self, should_start: bool, device_hint: str, model_size: str):
        if should_start:
            self._start_transcriber(device_hint, model_size)
        else:
            self._stop_transcriber()

    def _refresh_stt_devices(self):
        try:
            devices = LiveAudioTranscriber.list_input_devices()
            self.message_editor.set_stt_devices(devices)
            if hasattr(self, "bot_control"):
                self.bot_control.log(f"[Whisper] Entradas detectadas: {len(devices)}")
        except Exception as e:
            if hasattr(self, "bot_control"):
                self.bot_control.log(f"⚠ Error listando entradas de audio: {e}")

    def _start_transcriber(self, device_hint: str, model_size: str):
        try:
            if self._transcriber is None:
                self._transcriber = LiveAudioTranscriber(model_size=model_size, language="es")
            else:
                self._transcriber.model_size = model_size

            self._transcriber.start(
                device_hint=device_hint,
                on_text=self._on_transcribed_text,
                on_log=lambda msg: self.after(0, lambda: self.bot_control.log(f"[Whisper] {msg}")),
            )
            self.message_editor.set_stt_running(True)
            self._schedule_stt_ai_input_clear()
            self.bot_control.log("[Whisper] Transcripcion iniciada.")
            if self._engine_running:
                self._schedule_auto_ai_request_range(self._auto_ai_delay_min_s, self._auto_ai_delay_max_s)
        except Exception as e:
            self.bot_control.log(f"⚠ Error al iniciar transcripcion: {e}")
            self.message_editor.set_stt_running(False)

    def _stop_transcriber(self):
        self._cancel_stt_ai_input_clear()
        self._cancel_auto_ai_request()
        if self._transcriber is not None:
            self._transcriber.stop()
        self.message_editor.set_stt_running(False)
        self.message_editor.clear_cycle_timing()
        self.vision_panel.reset()
        self.bot_control.log("[Whisper] Transcripcion detenida.")

    def _schedule_auto_ai_request(self, delay_s: float):
        self._schedule_auto_ai_request_range(delay_s, delay_s)

    def _schedule_auto_ai_request_range(self, delay_min_s: float, delay_max_s: float):
        self._cancel_auto_ai_request()
        low = max(0.5, min(float(delay_min_s), float(delay_max_s)))
        high = max(0.5, max(float(delay_min_s), float(delay_max_s)))
        self._auto_ai_delay_min_s = low
        self._auto_ai_delay_max_s = high
        self._auto_ai_cycle_index = 0
        self._start_auto_ai_cycle()

    def _cancel_auto_ai_request(self):
        for job_id_attr in ("_auto_ai_job_id", "_auto_ai_capture_job_id", "_auto_ai_cycle_end_job_id"):
            job_id = getattr(self, job_id_attr, None)
            if job_id is None:
                continue
            try:
                self.after_cancel(job_id)
            except Exception:
                pass
            setattr(self, job_id_attr, None)

    def _pick_auto_ai_cycle_delay(self, low: float, high: float) -> float:
        if abs(high - low) < 1e-9:
            return low

        low_i = int(low)
        high_i = int(high)
        if abs(low - low_i) < 1e-9 and abs(high - high_i) < 1e-9:
            return float(random.randint(low_i, high_i))
        return random.uniform(low, high)

    def _start_auto_ai_cycle(self):
        if not self._engine_running or not self.message_editor.is_stt_running():
            return

        t_s = self._pick_auto_ai_cycle_delay(self._auto_ai_delay_min_s, self._auto_ai_delay_max_s)
        t_half_s = t_s / 2.0
        t_minus_5_s = max(0.5, t_s - 5.0)

        self._auto_ai_cycle_index += 1
        self._auto_ai_cycle_t_s = t_s
        self._auto_ai_delay_s = t_s

        self.vision_panel.set_cycle(self._auto_ai_cycle_index, t_s, t_half_s, t_minus_5_s)
        self.message_editor.set_cycle_timing(t_s, t_half_s, t_minus_5_s)
        self.bot_control.log(
            f"[Vision HLS] Ciclo #{self._auto_ai_cycle_index}: T={t_s:.1f}s | T/2={t_half_s:.1f}s | T-5={t_minus_5_s:.1f}s"
        )

        self._auto_ai_capture_job_id = self.after(int(t_half_s * 1000), self._auto_ai_capture_tick)
        self._auto_ai_job_id = self.after(int(t_minus_5_s * 1000), self._auto_ai_request_tick)
        self._auto_ai_cycle_end_job_id = self.after(int(t_s * 1000), self._auto_ai_cycle_end_tick)

    def _auto_ai_cycle_end_tick(self):
        self._auto_ai_cycle_end_job_id = None
        if not self._engine_running or not self.message_editor.is_stt_running():
            return
        self._start_auto_ai_cycle()

    def _auto_ai_capture_tick(self):
        self._auto_ai_capture_job_id = None
        if not self._engine_running or not self.message_editor.is_stt_running():
            return
        if self._capture_inflight:
            return

        self._capture_inflight = True
        cycle_index = self._auto_ai_cycle_index
        self.bot_control.log(f"[Vision HLS] Captura en T/2 del ciclo #{cycle_index}...")

        thread = threading.Thread(target=self._capture_hls_snapshot_thread, args=(cycle_index,), daemon=True)
        thread.start()

    def _capture_hls_snapshot_thread(self, cycle_index: int):
        try:
            result = capture_hls_snapshot()
        except Exception as exc:
            result = {
                "success": False,
                "image_base64": "",
                "url_used": "",
                "results": [{"url": "(global)", "ok": False, "detail": str(exc)}],
            }
        self.after(0, lambda: self._on_capture_hls_done(cycle_index, result))

    def _on_capture_hls_done(self, cycle_index: int, result: dict):
        self._capture_inflight = False

        if result.get("success"):
            self._latest_capture_image_b64 = str(result.get("image_base64") or "")
            img_size = len(self._latest_capture_image_b64) if self._latest_capture_image_b64 else 0
            self.bot_control.log(
                f"[Vision HLS] Captura OK en ciclo #{cycle_index} ({result.get('url_used', '')} - {img_size} bytes imagen base64)."
            )
        else:
            self._latest_capture_image_b64 = ""
            self.bot_control.log(f"[Vision HLS] Captura FALLIDA en ciclo #{cycle_index}.")

        self.vision_panel.set_capture_result(result)

    def _auto_ai_request_tick(self):
        self._auto_ai_job_id = None
        if not self._engine_running or not self.message_editor.is_stt_running():
            return

        self.message_editor.set_cycle_info(
            f"Ciclo IA -> T-5 alcanzado: la IA responde ahora (T={self._auto_ai_cycle_t_s:.1f}s)."
        )

        prompt = self.message_editor.get_ai_input()
        if not prompt:
            if not self._auto_ai_empty_logged:
                self.bot_control.log("[Auto IA] Ciclo omitido: el campo de IA esta vacio.")
                self._auto_ai_empty_logged = True
            return

        if self._ai_request_inflight and self._ai_request_started_at > 0:
            elapsed = time.monotonic() - self._ai_request_started_at
            if elapsed > self._ai_request_timeout_s:
                self.bot_control.log(
                    f"⚠ [Auto IA] Solicitud previa atascada por {elapsed:.0f}s; se libera el bloqueo para reintentar."
                )
                self._ai_request_inflight = False
                self._ai_request_started_at = 0.0
                self._auto_ai_busy_logged = False

        if self._ai_request_inflight:
            if not self._auto_ai_busy_logged:
                self.bot_control.log("[Auto IA] Esperando respuesta de IA anterior...")
                self._auto_ai_busy_logged = True
            return

        self._auto_ai_empty_logged = False
        self._auto_ai_busy_logged = False
        model = self.message_editor.get_ai_model()
        
        has_image = bool(self._latest_capture_image_b64 and len(self._latest_capture_image_b64) > 100)
        if has_image:
            self.bot_control.log(f"[Vision HLS] Enviando a IA: transcripcion ({len(prompt)} chars) + imagen ({len(self._latest_capture_image_b64)} bytes).")
        else:
            self.bot_control.log(f"[Vision HLS] Enviando a IA: transcripcion ({len(prompt)} chars) SOLO (sin imagen).")
        
        self._on_ai_request(prompt, model, image_base64=self._latest_capture_image_b64 or None)

    def _schedule_stt_ai_input_clear(self):
        self._cancel_stt_ai_input_clear()
        self._stt_clear_job_id = self.after(self._stt_clear_ms, self._clear_ai_input_while_stt)

    def _cancel_stt_ai_input_clear(self):
        if self._stt_clear_job_id is None:
            return
        try:
            self.after_cancel(self._stt_clear_job_id)
        except Exception:
            pass
        self._stt_clear_job_id = None

    def _clear_ai_input_while_stt(self):
        self.message_editor.clear_ai_input()
        self._stt_clear_job_id = self.after(self._stt_clear_ms, self._clear_ai_input_while_stt)

    def _on_transcribed_text(self, text: str):
        channel_name = self.config_panel.get_channel().strip()
        source = channel_name if channel_name else "Canal"

        line = f"[{source}] {text}"
        self.after(0, lambda: self.message_editor.append_ai_input(line))
        self.after(0, lambda: self.bot_control.log(f"[Whisper] {line}"))

    def _ask_ollama_for_transcribed(self, prompt: str, model: str, source: str):
        try:
            max_chars = self.message_editor.get_ai_max_chars()
            emote_only = random.random() < 0.25
            answer = generate_ollama_response(
                prompt,
                model=model,
                max_chars=max_chars,
                emote_only=emote_only,
                image_base64=self._latest_capture_image_b64 or None,
            )
            self.after(0, lambda: self._on_auto_streaming_response(answer, model, source, prompt, max_chars))
        except Exception as e:
            self.after(0, lambda: self.bot_control.log(f"⚠ Error IA automática: {e}"))

    def _on_auto_streaming_response(self, answer: str, model: str, source: str, original_prompt: str, max_chars: int):
        self.message_editor.clear_messages()
        self.message_editor.append_message(self._format_ai_message(answer, max_chars=max_chars))
        self.bot_control.log(f"[Whisper] ✓ Respuesta de {model}.")

    def _format_ai_message(self, answer: str, max_chars: int | None = None) -> str:
        cleaned = (answer or "").strip()
        if not cleaned:
            return ""

        prefix = self.message_editor.get_ai_prefix().strip()
        if prefix:
            cleaned = f"{prefix} {cleaned}".strip()

        safe_max = max_chars if max_chars is not None else self.message_editor.get_ai_max_chars()
        return truncate_chat_text_ignoring_emotes(cleaned, safe_max)

    # ── Account Management ─────────────────────────────────────────

    def _refresh_accounts(self):
        accounts = load_accounts()
        self.account_panel.set_accounts(accounts)

    def _on_add_account(self, name: str, proxy: str = ""):
        if not name.strip():
            return

        self.account_panel.set_status(name, "iniciando…")
        add_account(
            name.strip(),
            proxy=proxy if proxy else None,
            on_done=self._on_account_done,
            on_error=self._on_account_error,
        )

    def _on_account_done(self, name: str):
        self.after(0, self._refresh_accounts)
        self.after(0, lambda: self.account_panel.set_status(name, "listo ✓"))
        self.after(0, lambda: self.bot_control.log(f"✔ Cuenta '{name}' agregada."))

    def _on_account_error(self, name: str, error: str):
        self.after(0, lambda: self.account_panel.set_status(name, f"error"))
        self.after(0, lambda: self.bot_control.log(f"✘ {name}: {error}"))

    def _on_delete_account(self, name: str):
        # Stop worker if running
        if name in self._workers:
            self._workers[name].stop()
            del self._workers[name]
        delete_account(name)
        self._refresh_accounts()
        self.bot_control.log(f"🗑 Cuenta '{name}' ha sido eliminada.")

    # ── Bot Start / Stop ──────────────────────────────────────────

    def _on_start(self):
        channel = self.config_panel.get_channel()
        chat_target = self.config_panel.get_chat_target()
        if not channel.strip():
            self.bot_control.log("⚠ Escribe primero el nombre del canal de Kick.")
            return

        text = self.message_editor.get_text()
        if not text.strip():
            self.bot_control.log("⚠ Escribe al menos un mensaje para enviar.")
            return

        self._pool.set_text(text)

        accounts = load_accounts()
        if not accounts:
            self.bot_control.log("⚠ No hay cuentas conectadas. Añade cuentas primero.")
            return

        # Stop existing workers
        self._stop_workers()

        # Create workers
        self._workers = {}
        for i, acc in enumerate(accounts):
            name = acc["name"]
            if not has_session(name):
                self.bot_control.log(f"⚠ Sin sesión para '{name}', saltando cuenta.")
                continue
            worker = BotWorker(name, i, on_log=self._on_worker_log)
            self._workers[name] = worker
            worker.start(channel.strip(), chat_target=chat_target)
            self.account_panel.set_status(name, "iniciando…")

        if not self._workers:
            self.bot_control.log("⚠ Ningún bot está listo para correr.")
            return

        # Configure and start engine
        cfg = self.config_panel.get_spam_config()
        self._engine.configure(list(self._workers.values()), self._pool, cfg)
        self._engine.start()
        self._engine_running = True
        self._auto_ai_delay_min_s = cfg.delay_min
        self._auto_ai_delay_max_s = cfg.delay_max
        self._auto_ai_delay_s = cfg.delay_max

        self.bot_control.set_running(True)
        self.bot_control.log(
            f"▶ {len(self._workers)} bots activados → #{channel}  "
            f"[{cfg.mode} | retraso={cfg.delay_min:.1f}s-{cfg.delay_max:.1f}s | chat={chat_target}]"
        )

        if self.message_editor.is_stt_running():
            self._schedule_auto_ai_request_range(cfg.delay_min, cfg.delay_max)

        # Poll worker statuses
        self._poll_statuses()

    def _on_stop(self):
        self._engine.stop()
        self._cancel_auto_ai_request()
        self._cancel_poll_statuses()
        self._stop_workers()
        self._engine_running = False
        self._latest_capture_image_b64 = ""
        self.message_editor.clear_cycle_timing()
        self.vision_panel.reset()
        self.bot_control.set_running(False)
        self.bot_control.log("■ Bots detenidos satisfactoriamente.")
        for name in load_accounts():
            self.account_panel.set_status(name["name"], "idle")

    def _on_refresh_config(self):
        """Refresh config without stopping engine."""
        if not self._engine_running:
            self.bot_control.log("⚠ Los bots no están en ejecución.")
            return

        cfg = self.config_panel.get_spam_config()
        self._engine.reconfigure(cfg)
        self.bot_control.log(
            f"✓ Configuracion refrescada: [{cfg.mode} | retraso={cfg.delay_min:.1f}s-{cfg.delay_max:.1f}s]"
        )
        self._auto_ai_delay_min_s = cfg.delay_min
        self._auto_ai_delay_max_s = cfg.delay_max
        if self.message_editor.is_stt_running():
            self._schedule_auto_ai_request_range(cfg.delay_min, cfg.delay_max)

    def _stop_workers(self):
        for worker in self._workers.values():
            worker.stop()
        self._workers = {}

    def _poll_statuses(self):
        if not self._engine_running:
            self._poll_status_job_id = None
            return
        for name, worker in self._workers.items():
            self.account_panel.set_status(name, worker.status)
        self._poll_status_job_id = self.after(1000, self._poll_statuses)
    
    def _cancel_poll_statuses(self):
        if self._poll_status_job_id is not None:
            try:
                self.after_cancel(self._poll_status_job_id)
            except Exception:
                pass
            self._poll_status_job_id = None

    # ── Logging ────────────────────────────────────────────────────

    def _on_worker_log(self, account_name: str, msg: str):
        self.after(0, lambda: self.bot_control.log(f"[{account_name}] {msg}"))

    def _on_engine_log(self, source: str, msg: str):
        self.after(0, lambda: self.bot_control.log(f"[Engine] {msg}"))

    def _on_close(self):
        try:
            self._on_stop()
        finally:
            try:
                self._stop_transcriber()
            finally:
                shutdown_shared_browser_manager()
                self.destroy()
