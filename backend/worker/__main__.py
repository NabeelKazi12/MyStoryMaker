"""Punto de entrada del worker: `uv run python -m backend.worker`.

Consume la cola de `Tarea` e invoca modelos. No arranca sin un cliente real, y el cliente
real no existe hasta confirmar el modelo de R-1 contra la API de modelos.
"""

from __future__ import annotations

import sys

from backend.worker.modelo import construir_cliente_real


def main() -> int:
    try:
        construir_cliente_real()
    except NotImplementedError as error:
        print(f"worker: no se puede arrancar todavia.\n{error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
