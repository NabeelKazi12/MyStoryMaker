"""Tools del harness: schema validado y reintentos con limite.

Dos reglas, y las dos existen por la misma razon -que un fallo no se convierta en gasto
sin final-:

1. **Toda llamada valida contra su schema antes de ejecutarse.** Una tool sin schema es
   una llamada que nadie comprueba, y su error aparece dentro del modelo, no aqui.
2. **Los reintentos son para lo transitorio.** Un corte de red se reintenta; un argumento
   mal formado, no: repetirlo produce exactamente el mismo error y lo paga otra vez.

Cubre RF-HAR-05 y RF-HAR-06.
"""

from __future__ import annotations

import time
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from typing import Any

# Tres, el mismo numero que la escalera de transporte de `architecture.md` 6.3.
LIMITE_DE_REINTENTOS = 3
ESPERA_BASE = 0.01


class LlamadaInvalida(Exception):
    """Los argumentos no validan contra el schema de la tool. Fallo de contrato (D-06).

    No se reintenta: los mismos argumentos producen el mismo error.
    """

    def __init__(self, tool: str, motivo: str) -> None:
        self.tool = tool
        super().__init__(f"Tool {tool}: {motivo}")


class ReintentosAgotados(RuntimeError):
    """Se agotaron los reintentos de una tool y sigue fallando."""

    def __init__(self, tool: str, intentos: int, ultimo: Exception) -> None:
        super().__init__(
            f"Tool {tool}: agotados los {intentos} reintentos. Ultimo fallo: {ultimo}. "
            f"Se detiene en lugar de seguir reintentando: un fallo permanente reintentado "
            f"es gasto sin final."
        )


@dataclass(frozen=True)
class EsquemaDeTool:
    """El contrato de una tool: como se llama, que exige y de que tipo."""

    nombre: str
    campos_obligatorios: tuple[str, ...] = ()
    tipos: Mapping[str, type] = field(default_factory=dict)


def validar_llamada(esquema: EsquemaDeTool, argumentos: Mapping[str, Any]) -> dict[str, Any]:
    """Comprueba obligatorios y tipos. Devuelve los argumentos si valen."""
    for campo in esquema.campos_obligatorios:
        if campo not in argumentos:
            raise LlamadaInvalida(esquema.nombre, f"falta el campo obligatorio «{campo}»")

    for campo, tipo in esquema.tipos.items():
        if campo in argumentos and not isinstance(argumentos[campo], tipo):
            raise LlamadaInvalida(
                esquema.nombre,
                f"el campo «{campo}» tiene que ser {tipo.__name__} y llego "
                f"{type(argumentos[campo]).__name__}",
            )

    return dict(argumentos)


def ejecutar_con_reintentos[T](
    accion: Callable[[], T], *, nombre: str, limite: int = LIMITE_DE_REINTENTOS
) -> T:
    """Ejecuta la tool reintentando solo lo transitorio, con retroceso exponencial."""
    ultimo: Exception | None = None
    for intento in range(1, limite + 1):
        try:
            return accion()
        except LlamadaInvalida:
            # Un argumento mal formado no mejora al repetirlo.
            raise
        except (ConnectionError, TimeoutError, OSError) as error:
            ultimo = error
            if intento < limite:
                time.sleep(ESPERA_BASE * (2 ** (intento - 1)))

    assert ultimo is not None
    raise ReintentosAgotados(nombre, limite, ultimo)
