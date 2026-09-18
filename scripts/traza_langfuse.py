"""Hook de observabilidad: convierte los eventos de Claude Code en spans de Langfuse.

Un unico script atiende todos los eventos y despacha por `hook_event_name`. Es
deliberado: el arbol de la traza —la sesion como tronco, cada herramienta y cada
subagente como rama— solo sale bien si un mismo sitio decide las claves de los
spans, y partirlo en cuatro scripts obligaria a repetir esa decision cuatro veces.

El arbol que se ve en Langfuse:

    sesion (agent)                     <- SessionStart, se cierra en Stop/SessionEnd
      +- Read, Grep, Bash... (tool)    <- PostToolUse, con su duracion real
      +- escritor (generation)         <- lo emite registrar_coste.py, no este script

La rama del subagente no sale de aqui a proposito. Claude Code **no dispara
Pre/PostToolUse para la herramienta `Task`**: el unico evento de un subagente es
SubagentStop, y quien lo atiende es `registrar_coste.py`, que ademas es el que
sabe leer su transcripcion. Intentar cerrar el span desde el PostToolUse del Task
dejaba los subagentes con duracion cero, porque ese evento no llega nunca.

Como todos los hooks, este nunca falla: pase lo que pase devuelve 0. Una traza
perdida es un incordio; un hook que revienta detiene la produccion de la novela.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import langfuse_cliente as lf
from _comun import leer_evento_hook

# Herramientas que no generan span aqui. 'Task' lo emite registrar_coste.py
# desde SubagentStop, que es el unico evento que Claude Code dispara para un
# subagente: no hay Pre/PostToolUse de 'Task' con los que contar.
IGNORADAS = {"TodoWrite", "Task"}


# -------------------------------------------------------------------- estado

def clave_herramienta(evento: dict) -> str:
    """Identifica una llamada concreta para casar PreToolUse con PostToolUse."""
    import hashlib
    entrada = json.dumps(evento.get("tool_input") or {}, sort_keys=True, ensure_ascii=False, default=str)
    return f"{evento.get('tool_name')}|{hashlib.sha1(entrada.encode()).hexdigest()[:12]}"


# ---------------------------------------------------------------- span raiz

def nombre_de_traza(prompt: str | None) -> str:
    """El primer prompt da nombre a la traza: '/novela capitulo 1' se lee solo."""
    if not prompt:
        return "sesion de MyStoryMaker"
    primera = prompt.strip().splitlines()[0].strip()
    return (primera[:80] or "sesion de MyStoryMaker")


def capitulo_de(prompt: str | None) -> str | None:
    import re
    if not prompt:
        return None
    m = re.search(r"capitulo\s+(\d+)", prompt, re.IGNORECASE)
    return m.group(1) if m else None


def span_raiz(sid: str, estado: dict, fin_ns: int | None = None, salida=None) -> list[dict]:
    """El tronco. Se emite al empezar y se reemite al cerrar con la duracion real.

    Reemitir la misma clave no es gratis: Langfuse guarda las dos filas y solo las
    colapsa despues, cuando su almacen fusiona por (traza, span). Mientras tanto
    las metricas suman ambas. Aqui compensa igualmente —el span raiz no lleva
    tokens, asi que lo unico que se duplica un rato es su duracion— pero no sirve
    como via para corregir un span que si los lleve: para eso hay que emitirlo
    bien la primera vez.
    """
    cfg = lf.config()
    if cfg is None:
        return []
    inicio = int(estado.get("inicio_ns") or lf.ahora_ns())
    nombre = estado.get("nombre_traza") or "sesion de MyStoryMaker"
    attrs = lf.atributos_traza(nombre, sid, cfg,
                               etiquetas=["mystorymaker", "claude-code", "orquestador"],
                               metadatos={"cwd": estado.get("cwd"),
                                          "origen": estado.get("origen"),
                                          "capitulo": estado.get("capitulo")})
    if estado.get("prompt"):
        attrs["langfuse.observation.input"] = estado["prompt"]
    if salida:
        attrs["langfuse.observation.output"] = lf.recortar(salida)
    return [lf.span(sid, "raiz", nombre, inicio, fin_ns or lf.ahora_ns(),
                    tipo="agent", padre=None, atributos=attrs)]


def ultimo_mensaje(transcripcion: str | None) -> str | None:
    """Ultimo texto del asistente en la transcripcion: es la salida de la sesion."""
    if not transcripcion:
        return None
    ruta = Path(transcripcion)
    if not ruta.exists():
        return None
    salida = None
    try:
        with open(ruta, encoding="utf-8") as fh:
            for linea in fh:
                linea = linea.strip()
                if not linea:
                    continue
                try:
                    registro = json.loads(linea)
                except json.JSONDecodeError:
                    continue
                mensaje = registro.get("message") or {}
                if mensaje.get("role") != "assistant":
                    continue
                contenido = mensaje.get("content")
                if isinstance(contenido, str):
                    salida = contenido
                elif isinstance(contenido, list):
                    textos = [b.get("text") for b in contenido
                              if isinstance(b, dict) and b.get("type") == "text" and b.get("text")]
                    if textos:
                        salida = "\n".join(textos)
    except OSError:
        return None
    return salida


# ------------------------------------------------------------------ eventos

def en_inicio(evento: dict, estado: dict) -> list[dict]:
    sid = evento.get("session_id") or "desconocida"
    estado.clear()
    estado.update({
        "session_id": sid,
        "inicio_ns": lf.ahora_ns(),
        "cwd": evento.get("cwd"),
        "origen": evento.get("source"),
        "nombre_traza": "sesion de MyStoryMaker",
        "herramientas": {},
        "subagentes": [],
        "contadores": {},
    })
    lf.guardar_sesion(sid, estado["inicio_ns"], estado["nombre_traza"])
    return span_raiz(sid, estado)


def en_prompt(evento: dict, estado: dict) -> list[dict]:
    sid = evento.get("session_id") or estado.get("session_id") or "desconocida"
    prompt = evento.get("prompt")
    # Solo el primer prompt bautiza la traza: los siguientes son la conversacion,
    # no el trabajo, y renombrar a mitad dejaria la sesion irreconocible.
    if not estado.get("prompt"):
        estado["prompt"] = lf.recortar(prompt)
        estado["nombre_traza"] = nombre_de_traza(prompt)
        estado["capitulo"] = capitulo_de(prompt)
        estado.setdefault("inicio_ns", lf.ahora_ns())
        estado["session_id"] = sid
        lf.guardar_sesion(sid, estado["inicio_ns"], estado["nombre_traza"])
        return span_raiz(sid, estado)
    return []


def en_pre_herramienta(evento: dict, estado: dict) -> list[dict]:
    estado.setdefault("herramientas", {})[clave_herramienta(evento)] = lf.ahora_ns()
    return []


def nivel_de(respuesta) -> tuple[str, str | None]:
    """Traduce la respuesta de la herramienta a nivel y mensaje de estado."""
    if isinstance(respuesta, dict):
        if respuesta.get("success") is False or respuesta.get("is_error"):
            return "ERROR", lf.recortar(respuesta.get("error") or respuesta, 300)
    if isinstance(respuesta, str) and respuesta.strip().lower().startswith("error"):
        return "ERROR", lf.recortar(respuesta, 300)
    return "DEFAULT", None


def en_post_herramienta(evento: dict, estado: dict) -> list[dict]:
    herramienta = evento.get("tool_name") or "herramienta"
    if herramienta in IGNORADAS or not lf.trazar_herramientas():
        return []
    sid = evento.get("session_id") or estado.get("session_id") or "desconocida"
    clave_llamada = clave_herramienta(evento)
    inicio = estado.get("herramientas", {}).pop(clave_llamada, None) or lf.ahora_ns()
    nivel, mensaje = nivel_de(evento.get("tool_response"))

    clave = f"herramienta:{clave_llamada}:{estado.get('n_herramientas', 0)}"
    estado["n_herramientas"] = estado.get("n_herramientas", 0) + 1
    attrs = {
        "langfuse.observation.input": lf.recortar(evento.get("tool_input")),
        "langfuse.observation.output": lf.recortar(evento.get("tool_response")),
        "langfuse.observation.level": nivel,
        "langfuse.observation.metadata.herramienta": herramienta,
    }
    if mensaje:
        attrs["langfuse.observation.status_message"] = mensaje
    return [lf.span(sid, clave, herramienta, inicio, lf.ahora_ns(), tipo="tool", atributos=attrs)]


def en_cierre(evento: dict, estado: dict) -> list[dict]:
    sid = evento.get("session_id") or estado.get("session_id") or "desconocida"
    salida = ultimo_mensaje(evento.get("transcript_path"))
    return span_raiz(sid, estado, fin_ns=lf.ahora_ns(), salida=salida)


DESPACHO = {
    "SessionStart": en_inicio,
    "UserPromptSubmit": en_prompt,
    "PreToolUse": en_pre_herramienta,
    "PostToolUse": en_post_herramienta,
    "Stop": en_cierre,
    "SessionEnd": en_cierre,
}

# Eventos tras los cuales conviene que la traza este ya arriba.
VACIAR_EN = {"Stop", "SessionEnd", "SubagentStop"}


def main() -> int:
    try:
        if not lf.activo():
            return 0
        evento = leer_evento_hook()
        nombre = evento.get("hook_event_name") or ""
        manejador = DESPACHO.get(nombre)
        if manejador is None:
            return 0
        estado = lf.leer_estado()
        spans = manejador(evento, estado) or []
        lf.escribir_estado(estado)
        lf.encolar(spans, vaciar_ahora=nombre in VACIAR_EN)
    except Exception:
        pass
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
