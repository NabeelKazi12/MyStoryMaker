"""Hook SubagentStop: deja traza de cada subagente en logs/run-<fecha>.jsonl.

El payload del evento no siempre trae el consumo de tokens; lo que si trae
siempre es la ruta de la transcripcion. De ella se derivan tokens y modelo
cuando estan disponibles, y el resto se registra como null. Un log incompleto
es util; un hook que revienta y aborta la ejecucion, no. Por eso este script
nunca falla: pase lo que pase devuelve 0.
"""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _comun import LOGS, leer_evento_hook


def uso_declarado(transcripcion: str | None) -> dict:
    """Recorre el .jsonl de la transcripcion y acumula el uso declarado."""
    if not transcripcion:
        return {}
    ruta = Path(transcripcion)
    if not ruta.exists():
        return {}

    entrada = salida = 0
    modelo = None
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
                uso = mensaje.get("usage") or {}
                if uso:
                    entrada += int(uso.get("input_tokens") or 0)
                    entrada += int(uso.get("cache_read_input_tokens") or 0)
                    entrada += int(uso.get("cache_creation_input_tokens") or 0)
                    salida += int(uso.get("output_tokens") or 0)
                    modelo = mensaje.get("model") or modelo
    except OSError:
        return {}
    return {"tokens_in": entrada, "tokens_out": salida, "modelo": modelo}


def main() -> int:
    try:
        evento = leer_evento_hook()
        ahora = datetime.now(timezone.utc)
        registro = {
            "ts": ahora.isoformat(timespec="seconds"),
            "evento": evento.get("hook_event_name", "SubagentStop"),
            "agente": (evento.get("agent_type") or evento.get("agent_name")
                       or evento.get("subagent_type")),
            "session_id": evento.get("session_id"),
            "ok": True,
        }
        registro.update(uso_declarado(evento.get("transcript_path")))
        registro.setdefault("tokens_in", None)
        registro.setdefault("tokens_out", None)
        registro["coste_usd"] = evento.get("total_cost_usd")

        LOGS.mkdir(parents=True, exist_ok=True)
        destino = LOGS / f"run-{ahora.strftime('%Y%m%d')}.jsonl"
        with open(destino, "a", encoding="utf-8", newline="\n") as fh:
            fh.write(json.dumps(registro, ensure_ascii=False) + "\n")
    except Exception:
        pass
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
