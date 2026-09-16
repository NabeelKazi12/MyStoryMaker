"""Hook PreToolUse: INV-09 - ningun subagente escribe en memory/.

La garantia no descansa en el prompt sino en la topologia: memory/ solo se
modifica a traves de scripts/consolidar.py, que se invoca con Bash, y ningun
subagente tiene Bash entre sus herramientas (SPECS 2.4). Este hook cierra la
via directa: cualquier Write, Edit o NotebookEdit sobre memory/ se deniega,
venga de donde venga. Tambien protege config/capitulos.json, que es del autor.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _comun import CONFIG, MEMORIA, bajo, leer_evento_hook, ruta_afectada


def denegar(motivo: str) -> None:
    salida = {
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "deny",
            "permissionDecisionReason": motivo,
        }
    }
    print(json.dumps(salida, ensure_ascii=False))
    sys.exit(0)


def main() -> int:
    evento = leer_evento_hook()
    ruta = ruta_afectada(evento)
    if ruta is None:
        return 0

    if bajo(ruta, MEMORIA):
        denegar(
            "INV-09 - memory/ no se edita a mano. La memoria es de escritura exclusiva del "
            "orquestador y solo al consolidar un capitulo aprobado por D1. Usa "
            "`python scripts/consolidar.py --capitulo N --iteracion K`, que escribe de forma "
            "atomica e incrementa 'version'."
        )

    if Path(ruta).name == CONFIG.name and bajo(ruta, CONFIG.parent):
        denegar(
            "config/capitulos.json pertenece al autor (SPECS 11). El numero de capitulos y su "
            "extension no los decide ningun agente. Si el plan necesita cambiar, propon el "
            "cambio al autor y que lo edite el."
        )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
