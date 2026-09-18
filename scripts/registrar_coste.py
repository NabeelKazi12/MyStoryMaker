"""Hook SubagentStop: mide lo que costo un subagente y lo deja en el log y en Langfuse.

El payload del evento no trae el consumo, y su `transcript_path` apunta a la
transcripcion del **orquestador**, no a la del subagente. Sumar esa era el fallo
original de este hook: atribuia a cada subagente el gasto acumulado de la sesion
padre, con lo que el Revisor siempre parecia mas caro que el Escritor solo por
correr despues, y los totales no significaban nada.

La transcripcion del subagente esta en `<sesion>/subagents/agent-*.jsonl`, y la
que acaba de cerrarse es la ultima modificada. De ahi salen las cuatro cosas que
importan: los tokens, el modelo, cuando empezo y cuando acabo. Con eso el span de
Langfuse lleva consumo real y duracion real.

Este hook tambien emite el span, en vez de dejarselo al PostToolUse del `Task`:
Claude Code no dispara Pre/PostToolUse para `Task` —usa este evento en su lugar—,
asi que esperar a ese cierre dejaba los spans sin duracion.

Como todos los hooks del harness, este nunca falla: pase lo que pase devuelve 0.
"""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import langfuse_cliente as lf
from _comun import LOGS, leer_evento_hook

# Margen entre el cierre del subagente y la ultima escritura de su transcripcion.
# Si la candidata es mas vieja que esto, no es de este subagente.
MARGEN_SEGUNDOS = 300

NODOS = {"investigacion": "N1", "escaleta": "N2", "escritor": "N3", "revisor": "N4"}


def a_ns(marca: str | None) -> int | None:
    """ISO-8601 de la transcripcion a nanosegundos epoch."""
    if not marca:
        return None
    try:
        return int(datetime.fromisoformat(marca.replace("Z", "+00:00")).timestamp() * 1_000_000_000)
    except ValueError:
        return None


def transcripcion_subagente(transcripcion_padre: str | None) -> Path | None:
    """Localiza la transcripcion del subagente que acaba de terminar.

    Claude Code no dice cual es, pero las guarda en un directorio propio junto a
    la del padre y la que acaba de cerrarse es la ultima escrita. Se exige ademas
    que sea reciente: si la mas nueva tiene media hora, es de otra tanda y vale
    mas no atribuir nada que atribuir lo que no es.
    """
    if not transcripcion_padre:
        return None
    try:
        padre = Path(transcripcion_padre)
        directorio = padre.with_suffix("") / "subagents"
        if not directorio.is_dir():
            return None
        candidatas = sorted(directorio.glob("*.jsonl"), key=lambda p: p.stat().st_mtime, reverse=True)
        if not candidatas:
            return None
        reciente = candidatas[0]
        edad = datetime.now(timezone.utc).timestamp() - reciente.stat().st_mtime
        return reciente if edad <= MARGEN_SEGUNDOS else None
    except OSError:
        return None


def leer_transcripcion(ruta: Path) -> dict:
    """Consumo, modelo, margenes de tiempo, peticion y resultado del subagente."""
    # Los cuatro tramos se cuentan por separado porque no valen lo mismo: leer de
    # cache cuesta la decima parte que la entrada fresca y escribirla un 25% mas.
    # Sumarlos en un solo numero, como se hacia antes, inflaba el coste a la mitad.
    fresca = cache_escrita = cache_leida = salida = 0
    modelo = None
    primera = ultima = None
    peticion = resultado = None
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

                marca = registro.get("timestamp")
                if marca:
                    primera = primera or marca
                    ultima = marca

                mensaje = registro.get("message") or {}
                uso = mensaje.get("usage") or {}
                if uso:
                    fresca += int(uso.get("input_tokens") or 0)
                    cache_escrita += int(uso.get("cache_creation_input_tokens") or 0)
                    cache_leida += int(uso.get("cache_read_input_tokens") or 0)
                    salida += int(uso.get("output_tokens") or 0)
                    modelo = mensaje.get("model") or modelo

                texto = texto_de(mensaje)
                if not texto:
                    continue
                if mensaje.get("role") == "user" and peticion is None:
                    peticion = texto          # el encargo con el que se lanzo
                elif mensaje.get("role") == "assistant":
                    resultado = texto         # lo ultimo que dijo es lo que devuelve
    except OSError:
        return {}
    return {
        "tokens_in": fresca + cache_escrita + cache_leida,   # total, para el log
        "tokens_out": salida,
        "entrada_fresca": fresca,
        "cache_escrita": cache_escrita,
        "cache_leida": cache_leida,
        "modelo": modelo,
        "inicio_ns": a_ns(primera), "fin_ns": a_ns(ultima),
        "peticion": peticion, "resultado": resultado,
    }


def texto_de(mensaje: dict) -> str | None:
    contenido = mensaje.get("content")
    if isinstance(contenido, str):
        return contenido or None
    if isinstance(contenido, list):
        partes = [b.get("text") for b in contenido
                  if isinstance(b, dict) and b.get("type") == "text" and b.get("text")]
        return "\n".join(partes) or None
    return None


def uso_de_la_sesion(transcripcion: str | None) -> dict:
    """Ultimo recurso: el gasto de la sesion padre, marcado como lo que es.

    No es el consumo del subagente y no debe presentarse como tal, pero saber que
    la sesion iba por 900.000 tokens es mejor que no saber nada.
    """
    if not transcripcion:
        return {}
    ruta = Path(transcripcion)
    if not ruta.exists():
        return {}
    datos = leer_transcripcion(ruta)
    if not datos:
        return {}
    return {"tokens_in": datos.get("tokens_in"), "tokens_out": datos.get("tokens_out"),
            "modelo": datos.get("modelo"), "fuente": "sesion"}


def main() -> int:
    try:
        evento = leer_evento_hook()
        ahora = datetime.now(timezone.utc)
        agente = (evento.get("agent_type") or evento.get("agent_name")
                  or evento.get("subagent_type"))
        registro = {
            "ts": ahora.isoformat(timespec="seconds"),
            "evento": evento.get("hook_event_name", "SubagentStop"),
            "agente": agente,
            "session_id": evento.get("session_id"),
            "ok": True,
        }

        propia = transcripcion_subagente(evento.get("transcript_path"))
        datos = leer_transcripcion(propia) if propia else {}
        if datos.get("tokens_in") or datos.get("tokens_out"):
            registro.update({"tokens_in": datos["tokens_in"], "tokens_out": datos["tokens_out"],
                             "modelo": datos.get("modelo"), "fuente": "subagente"})
        else:
            datos = {}
            registro.update(uso_de_la_sesion(evento.get("transcript_path")))
        registro.setdefault("tokens_in", None)
        registro.setdefault("tokens_out", None)
        registro.setdefault("fuente", "desconocida")
        registro["coste_usd"] = evento.get("total_cost_usd")

        LOGS.mkdir(parents=True, exist_ok=True)
        destino = LOGS / f"run-{ahora.strftime('%Y%m%d')}.jsonl"
        with open(destino, "a", encoding="utf-8", newline="\n") as fh:
            fh.write(json.dumps(registro, ensure_ascii=False) + "\n")

        emitir_span(evento, registro, datos)
    except Exception:
        pass
    return 0


def emitir_span(evento: dict, registro: dict, datos: dict) -> None:
    """Publica el subagente como una generacion colgada de la sesion."""
    if not lf.activo():
        return
    try:
        sid = evento.get("session_id") or "desconocida"
        agente = registro.get("agente") or "subagente"
        estado = lf.leer_estado()
        n = estado.setdefault("contadores", {}).get(agente, 0)
        estado["contadores"][agente] = n + 1
        lf.escribir_estado(estado)

        fin = datos.get("fin_ns") or lf.ahora_ns()
        inicio = datos.get("inicio_ns") or fin
        atributos = {
            "langfuse.observation.metadata.subagente": agente,
            "langfuse.observation.metadata.nodo": NODOS.get(agente),
            "langfuse.observation.metadata.fuente_consumo": registro.get("fuente"),
        }
        if datos:
            # Desglosado: Langfuse aplica a cada tramo su precio. Con todo metido
            # en 'input' el coste sale la mitad de caro de lo que es en realidad.
            atributos["langfuse.observation.usage_details"] = json.dumps({
                "input": datos.get("entrada_fresca", 0),
                "cache_creation_input_tokens": datos.get("cache_escrita", 0),
                "cache_read_input_tokens": datos.get("cache_leida", 0),
                "output": datos.get("tokens_out", 0),
            })
        elif registro.get("tokens_in") is not None or registro.get("tokens_out") is not None:
            atributos["langfuse.observation.usage_details"] = json.dumps(
                {"input": int(registro.get("tokens_in") or 0),
                 "output": int(registro.get("tokens_out") or 0)})
        if registro.get("modelo"):
            atributos["langfuse.observation.model.name"] = registro["modelo"]
        if registro.get("coste_usd") is not None:
            atributos["langfuse.observation.cost_details"] = json.dumps(
                {"total": registro["coste_usd"]})
        if datos.get("peticion"):
            atributos["langfuse.observation.input"] = lf.recortar(datos["peticion"])
        if datos.get("resultado"):
            atributos["langfuse.observation.output"] = lf.recortar(datos["resultado"])
        if registro.get("fuente") != "subagente":
            atributos["langfuse.observation.level"] = "WARNING"
            atributos["langfuse.observation.status_message"] = (
                "No se ha encontrado la transcripcion del subagente: el consumo que "
                "figura es el de la sesion completa, no el de este agente.")

        lf.encolar([lf.span(sid, f"subagente:{agente}:{n}", agente, inicio, fin,
                            tipo="generation", atributos=atributos)], vaciar_ahora=True)
    except Exception:
        return


if __name__ == "__main__":
    raise SystemExit(main())
