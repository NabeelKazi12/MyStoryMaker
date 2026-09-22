"""Capa de especificacion: el contrato del encargo.

Es lo que la capa de calidad usa como referencia para medir. `Restriccion` y
`PoliticaDeContenido` quedan fuera del alcance de v1 (SPEC-001, 2.3), asi que aqui solo
esta el `Brief`.

Cubre la parte de especificacion de RF-DOM-01.
"""

from __future__ import annotations

from dataclasses import dataclass

from backend.domain.errors import exigir


@dataclass(frozen=True, kw_only=True)
class Brief:
    """El encargo. Sin contrato no hay nada que medir.

    `promesa_al_lector` es el compromiso implicito del genero, y su incumplimiento es el
    fallo de calidad mas grave y menos detectable frase a frase; por eso no es opcional.
    """

    id: str
    genero: str
    premisa: str
    promesa_al_lector: str
    extension_objetivo: int
    tabues: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        clase = type(self).__name__
        exigir(bool(self.premisa.strip()), clase, "todo brief tiene premisa", f"id={self.id!r}")
        exigir(
            bool(self.promesa_al_lector.strip()),
            clase,
            "todo brief declara su promesa_al_lector",
            f"id={self.id!r}; es lo que la puerta Volumen cerrado cobra al final",
        )
        exigir(
            self.extension_objetivo > 0,
            clase,
            "la extension objetivo es un numero de palabras positivo",
            f"id={self.id!r}; recibida {self.extension_objetivo}",
        )
