"""
ollama_client.py
Minimal client for local Ollama HTTP API.
"""

import json
import os
import re
import urllib.error
import urllib.request


DEFAULT_OLLAMA_URL = os.getenv("OLLAMA_HOST", "http://127.0.0.1:11434")
EMOTE_TOKEN_RE = re.compile(r"\[emote:\d+:[^\]]+\]")


EMOTE_GUIDE = """
Usa estos emotes de Kick cuando aporten a la reaccion y sin forzar.
Formato exacto permitido: [emote:ID:NOMBRE]

Asombro sorpresa wow:
[emote:37233:PogU] [emote:37229:OOOO] [emote:39261:kkHuh]

Risa vacilon meme:
[emote:37226:KEKW] [emote:37227:LULW] [emote:37225:KEKLEO] [emote:37243:gachiGASM] [emote:37215:AYAYA]

Aprobacion apoyo felicitacion:
[emote:37218:Clap] [emote:37232:PeepoClap] [emote:4147873:YouTried] [emote:28633:SenpaiWhoo] [emote:37221:EZ] [emote:37237:TriKool] [emote:4148085:SUSSY]

Baile musica energia:
[emote:4147884:vibePls] [emote:5380973:shoulderRoll] [emote:4055796:ODAJAM] [emote:37245:peepoDJ] [emote:39260:DanceDance]
[emote:4147914:duckPls] [emote:4148144:catblobDance] [emote:39265:EDMusiC] [emote:39251:beeBobble] [emote:3753119:asmonSmash]

Duda sospecha confusion:
[emote:37244:modCheck] [emote:305040:Kappa] [emote:37239:WeSmart] [emote:39275:peepoShy] 

Enamorado:
[emote:37240:WeirdChamp]

Tristeza presion frustracion:
[emote:4148081:Sadge] [emote:4148128:mericCat] [emote:37236:ThisIsFine] [emote:39254:CaptFail] [emote:5273247:highCortisol] [emote:5273243:lowCortisol]

Reaccion fuerte caos toxicidad meme:
[emote:4147896:TOXIC] [emote:37246:peepoRiot] [emote:37230:POLICE] [emote:39272:LetMeIn] [emote:4147909:coffinPls] [emote:4147814:OuttaPocket]

Cariño respeto fe presencia:
[emote:39402:Flowie] [emote:4147900:catKISS] [emote:37234:Prayge] [emote:37248:ratJAM] [emote:4147902:KEKBye] [emote:3645849:TRUEING]

Enojo:
[emote:37228:NODDERS] [emote:3645850:EDDIE] 

locuaz:
[emote:37217:Bwop] 

Mateado:
[emote:39273:MuteD]

Muerto Fallecera:
[emote:4147909:coffinPls] 

Atraso Retraso Tarde:
[emote:4147869:SaltT]

Otros de estilo chat del canal:
[emote:37228:NODDERS] [emote:37217:Bwop] [emote:39273:MuteD] [emote:4147909:coffinPls] [emote:3645850:EDDIE] [emote:4147869:SaltT]
""".strip()


def _is_emoji_char(ch: str) -> bool:
    cp = ord(ch)
    return (
        0x1F300 <= cp <= 0x1FAFF
        or 0x1F1E6 <= cp <= 0x1F1FF
        or 0x2600 <= cp <= 0x27BF
        or cp in (0x200D, 0xFE0F)
    )


def truncate_chat_text_ignoring_emotes(text: str, max_chars: int) -> str:
    """Trim text by counting only regular chars; emojis and [emote:*] are free."""
    safe_max = max(1, min(500, int(max_chars)))
    non_emote_count = 0
    out: list[str] = []
    i = 0
    while i < len(text):
        token_match = EMOTE_TOKEN_RE.match(text, i)
        if token_match:
            out.append(token_match.group(0))
            i = token_match.end()
            continue

        ch = text[i]
        if _is_emoji_char(ch):
            out.append(ch)
            i += 1
            continue

        if non_emote_count < safe_max:
            out.append(ch)
            non_emote_count += 1
        i += 1

    return "".join(out).strip()


def strip_unicode_emojis(text: str) -> str:
    """Remove unicode emojis while preserving regular text and Kick emote tokens."""
    if not text:
        return ""

    out: list[str] = []
    i = 0
    while i < len(text):
        token_match = EMOTE_TOKEN_RE.match(text, i)
        if token_match:
            out.append(token_match.group(0))
            i = token_match.end()
            continue

        ch = text[i]
        if not _is_emoji_char(ch):
            out.append(ch)
        i += 1

    return "".join(out)


def generate_ollama_response(
    prompt: str,
    model: str = "llama3",
    max_chars: int = 500,
    emote_only: bool = False,
    image_base64: str | None = None,
) -> str:
    if not prompt.strip():
        raise ValueError("El prompt de IA no puede estar vacio.")

    system_context = """Eres un espectador real viendo un stream en vivo.
Responde siempre en español, aunque el usuario escriba en inglés, francés, portugués u otro idioma.
Habla con estilo peruano achorado pero de buena onda: usa jerga peruana natural (por ejemplo: causa, mano, broder, paja, al toque, palta), con energía y calle, sin sonar forzado.
Responde de forma casual, natural y corta como lo haría una persona mirando la transmisión.
- Sé espontáneo y auténtico
- Responde en una línea o dos máximo
- Usa tono conversacional, picante y divertido, pero sin insultar ni faltar el respeto
- Reacciona emocionalmente si es apropiado
- No uses formateo especial ni asteriscos
- No uses emojis unicode como caritas o iconos
- Usa puntuación simple y texto fácil de enviar en chat
- Parece que estás chateando mientras ves el stream
- Usa emotes de Kick en formato [emote:ID:NOMBRE] cuando ayuden a expresar la reacción
- Usa entre 0 y 2 emotes por mensaje, sin repetir el mismo emote dos veces seguidas
- A veces puedes responder solo con emotes de Kick"""

    if emote_only:
        system_context = (
            f"{system_context}\n"
            "- Responde SOLO con emotes de Kick\n"
            "- No escribas palabras normales\n"
            "- Usa de 1 a 3 emotes en formato [emote:ID:NOMBRE]"
        )

    system_context = f"{system_context}\n\nGuia de emotes del canal:\n{EMOTE_GUIDE}"

    payload = {
        "model": model,
        "prompt": prompt,
        "stream": False,
        "system": system_context,
        "options": {
            "num_predict": 90,
            "temperature": 0.7,
        },
    }

    if image_base64:
        payload["images"] = [image_base64]

    endpoint = f"{DEFAULT_OLLAMA_URL.rstrip('/')}/api/generate"
    req = urllib.request.Request(
        endpoint,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )

    try:
        with urllib.request.urlopen(req, timeout=120) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        details = e.read().decode("utf-8", errors="ignore")
        raise RuntimeError(f"HTTP {e.code} de Ollama: {details}") from e
    except urllib.error.URLError as e:
        raise RuntimeError(
            "No se pudo conectar con Ollama. Verifica que Ollama este iniciado."
        ) from e

    answer = data.get("response", "").strip()
    if not answer:
        raise RuntimeError("Ollama no devolvio contenido.")

    answer = strip_unicode_emojis(answer)
    return truncate_chat_text_ignoring_emotes(answer, max_chars)
