# KickBot

KickBot es una app de escritorio para automatizar mensajes en el chat de Kick.com con multiples cuentas. Incluye modo de envio programado, respuestas con IA via Ollama y transcripcion de audio con Whisper (opcional), ademas de captura HLS para vision (opcional).

## Caracteristicas
- Multi-cuenta con sesiones persistentes (cada cuenta usa su propio contexto de navegador).
- Modos de envio: simultaneo, diferido o por grupos.
- Editor de mensajes por linea con envio secuencial o aleatorio.
- Integracion con Ollama (local o en red) para generar respuestas.
- Transcripcion en vivo con faster-whisper (CUDA si existe, CPU si no).
- Captura HLS para adjuntar imagen a prompts de IA (vision).
- Soporte de proxies y probador masivo.

## Requisitos
- Windows (el script build.bat esta pensado para Windows).
- Python 3.x (recomendado 3.10+).
- Acceso a internet para instalar dependencias y Playwright.
- (Opcional) Ollama instalado y ejecutandose.
- (Opcional) Dispositivo de entrada de audio (microfono o VB-Cable).

## Instalacion (desde cero)
1) Crear entorno virtual:

```bat
py -m venv venv
venv\Scripts\activate
```

2) Instalar dependencias:

```bat
py -m pip install -r requirements.txt
```

3) Instalar Chromium para Playwright:

```bat
py -m playwright install chromium
```

## Ejecutar la app

```bat
py main.py
```

## Uso basico
1) Abre la app.
2) En "Gestion de Cuentas" escribe un usuario y pulsa "+ Conectar Navegador".
3) Se abrira una ventana de navegador para iniciar sesion en Kick. Cierra cuando termine.
4) Repite para cada cuenta.
5) En "Configuracion de Spam" escribe el canal (sin https://), elige modo y retrasos.
6) En "Panel de Mensajes" escribe una frase por linea.
7) Pulsa "Iniciar Todo".

## IA con Ollama (opcional)
- Instala Ollama y ejecuta el servidor.
- En la app elige "Local" o "Red" y el modelo.
- Escribe un prompt y pulsa "Responder IA".
- El texto generado se copia al editor de mensajes.

Modelos sugeridos (ejemplo):
- `gemma4:e4b` (por defecto en el proyecto)

Si Ollama no corre en `http://127.0.0.1:11434`, define:
- `OLLAMA_HOST` (URL completa)
- `OLLAMA_MODE` = `local` o `remote`
- `OLLAMA_TIMEOUT_SECONDS` (30-600)

## Transcripcion con Whisper (opcional)
- Selecciona el dispositivo de entrada (por ejemplo "CABLE Output" de VB-Cable).
- Elige el modelo Whisper.
- Pulsa "Iniciar Transcrip.".
- La transcripcion se agrega al prompt de IA en ciclos cuando los bots estan corriendo.

Nota: el primer uso descarga el modelo, puede tardar y consumir espacio.

## Vision HLS (opcional)
La captura de imagen usa URLs definidas en `core/hls_capture.py`:

```
HLS_STREAM_URLS = [
  "http://...",
]
```

Actualiza esas URLs si tu stream no coincide. Si falla, la app sigue funcionando pero no adjunta imagen.

## Proxies (opcional)
Formatos soportados:
- `ip:puerto`
- `ip:puerto:usuario:clave`
- `http://usuario:clave@ip:puerto`

Usa "Probar Proxies" para validar conectividad.

## Build a ejecutable
Opcion rapida:

```bat
build.bat
```

Salida esperada:
- `dist\kickbot\kickbot.exe`

## Datos y seguridad
- Cuentas guardadas en `sessions/accounts.json`.
- Sesiones del navegador en `sessions/<cuenta>/state.json`.
- Configuracion UI en `sessions/ui_settings.json`.

No compartas estas carpetas si contienen sesiones activas.

## Solucion de problemas
- Error Playwright o navegador no encontrado: vuelve a ejecutar `py -m playwright install chromium`.
- No encuentra el chat input: prueba "kick.com popout chat" en la configuracion.
- Ollama no responde: confirma que el servicio esta activo y la URL es correcta.
- Whisper no detecta audio: refresca dispositivos y selecciona el correcto.

## Nota de uso
Este proyecto automatiza acciones en Kick.com. Usa la app de forma responsable y respetando las reglas de la plataforma.
