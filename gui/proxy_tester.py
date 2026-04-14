"""
proxy_tester.py
A Toplevel window to bulk test proxies.
"""

import customtkinter as ctk
import threading
import urllib.request
import time

C_BG       = "#0f0f14"
C_PANEL    = "#16161e"
C_SURFACE  = "#1e1e2a"
C_ACCENT   = "#53fc18"
C_TEXT     = "#e0e0e0"
C_MUTED    = "#888"
C_RED      = "#ff4444"
C_BORDER   = "#2a2a38"

class ProxyTesterWindow(ctk.CTkToplevel):
    def __init__(self, parent):
        super().__init__(parent)
        self.title("Probador Masivo de Proxies")
        self.geometry("750x550")
        
        # Keep window on top so it isn't lost behind main window
        self.attributes("-topmost", True)
        self.configure(fg_color=C_BG)
        
        self._testing = False
        self._build()
        
    def _build(self):
        self.grid_columnconfigure(0, weight=1)
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(1, weight=1)
        
        # Headers
        ctk.CTkLabel(
            self, text="1. Pega tus Proxies (uno por línea)", 
            font=ctk.CTkFont("Segoe UI", 12, "bold"), text_color=C_TEXT
        ).grid(row=0, column=0, pady=(15, 5), padx=10, sticky="w")
        
        ctk.CTkLabel(
            self, text="2. Resultados", 
            font=ctk.CTkFont("Segoe UI", 12, "bold"), text_color=C_TEXT
        ).grid(row=0, column=1, pady=(15, 5), padx=10, sticky="w")
        
        # Input Box
        self.input_box = ctk.CTkTextbox(
            self, fg_color=C_SURFACE, border_color=C_BORDER, 
            border_width=1, text_color=C_TEXT, font=ctk.CTkFont("Consolas", 12)
        )
        self.input_box.grid(row=1, column=0, sticky="nsew", padx=10, pady=5)
        self.input_box.insert("end", "127.0.0.1:8080\nip:puerto:usuario:clave\nhttp://usuario:clave@ip:puerto")
        
        # Results Box
        self.results_box = ctk.CTkTextbox(
            self, state="disabled", fg_color=C_SURFACE, border_color=C_BORDER, 
            border_width=1, text_color="#b0ffb0", font=ctk.CTkFont("Consolas", 11)
        )
        self.results_box.grid(row=1, column=1, sticky="nsew", padx=10, pady=5)
        
        # Bottom Controls
        btn_frame = ctk.CTkFrame(self, fg_color="transparent")
        btn_frame.grid(row=2, column=0, columnspan=2, pady=(10, 15))
        
        self.test_btn = ctk.CTkButton(
            btn_frame, text="▶ Empezar Prueba", 
            font=ctk.CTkFont("Segoe UI", 12, "bold"),
            command=self._start_testing, 
            fg_color=C_ACCENT, hover_color="#3acc10", text_color="#000"
        )
        self.test_btn.pack(side="left", padx=10)
        
        ctk.CTkLabel(
            btn_frame, 
            text="* Verifica conectividad contra api.ipify.org (10s límite).",
            font=ctk.CTkFont("Segoe UI", 10), text_color=C_MUTED
        ).pack(side="left", padx=10)

    def log(self, text: str, is_error: bool = False):
        self.results_box.configure(state="normal")
        self.results_box.insert("end", text + "\n")
        self.results_box.see("end")
        self.results_box.configure(state="disabled")

    def _start_testing(self):
        if self._testing: return
        
        raw_text = self.input_box.get("1.0", "end")
        proxies = [p.strip() for p in raw_text.splitlines() if p.strip()]
        
        # Filter out the placeholder
        proxies = [p for p in proxies if p not in ["127.0.0.1:8080", "ip:puerto:usuario:clave", "http://usuario:clave@ip:puerto"]]
        
        if not proxies: 
            self.log("⚠ No hay proxies válidos para probar.")
            return
            
        self._testing = True
        self.test_btn.configure(state="disabled", text="Probando...")
        self.results_box.configure(state="normal")
        self.results_box.delete("1.0", "end")
        self.results_box.configure(state="disabled")
        
        threading.Thread(target=self._run_tests, args=(proxies,), daemon=True).start()

    def _to_url(self, p: str) -> str:
        if p.startswith("http"): return p
        parts = p.split(":")
        if len(parts) == 2:
            return f"http://{parts[0]}:{parts[1]}"
        if len(parts) == 4:
            return f"http://{parts[2]}:{parts[3]}@{parts[0]}:{parts[1]}"
        return f"http://{p}"

    def _run_tests(self, proxies: list[str]):
        self.after(0, self.log, f"Empezando prueba para {len(proxies)} proxy(s)...\n" + "-"*40)
        
        for p in proxies:
            if not self._testing:
                break
                
            proxy_url = self._to_url(p)
            try:
                # Setup custom opener with proxy
                proxy_handler = urllib.request.ProxyHandler({'http': proxy_url, 'https': proxy_url})
                opener = urllib.request.build_opener(proxy_handler)
                
                req = urllib.request.Request("https://api.ipify.org?format=json", headers={
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
                })
                
                t0 = time.time()
                with opener.open(req, timeout=10) as response:
                    # Parse assuming response text resembles {"ip":"..."} or plain text IP
                    body = response.read().decode('utf-8').strip()
                    ip_seen = body.split('"ip":"')[-1].split('"')[0] if "ip" in body else body
                    ms = int((time.time() - t0) * 1000)
                    
                    self.after(0, self.log, f"✅ FUNCIONA ({ms}ms) | IP: {ip_seen}")
                    self.after(0, self.log, f"   Proxy: {p}\n")
            except Exception as e:
                # Capture short error (e.g. timeout, connection refused)
                err_msg = str(e).split(':')[-1].strip() if str(e) else type(e).__name__
                self.after(0, self.log, f"❌ ERROR | {err_msg}")
                self.after(0, self.log, f"   Proxy: {p}\n")
                
        self.after(0, self._finish_testing)
        
    def _finish_testing(self):
        self._testing = False
        self.after(0, self.log, "-"*40 + "\nPruebas completadas.")
        self.test_btn.configure(state="normal", text="▶ Empezar Prueba")
