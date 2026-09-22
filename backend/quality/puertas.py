"""Puertas: donde una dimension adquiere autoridad para parar la linea.

Una dimension sin puerta no bloquea nada, por determinista que sea su verificador
(`verification.md` 6). Aqui estan las cuatro que v1 implementa, con lo que cobra cada una
y, sobre todo, con lo que **no** puede cobrar.

La regla que ordena todo el modulo es el principio 8 de `architecture.md` 1: la ausencia
de evidencia nunca se convierte en evidencia favorable. Un invariante que v1 no implementa
sale como evidencia ausente, jamas como superado, y una puerta con evidencia ausente no
esta limpia: esta incompleta.

Cubre RF-QUA-11 a RF-QUA-14, RF-QUA-18 y RF-QUA-20.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum

from backend.domain.production.ejecucion import Defecto
from backend.domain.vocabularies import Severidad


class Politica(Enum):
    """Si la puerta puede parar la linea o solo avisar."""

    BLOQUEANTE = "bloqueante"
    ADVERTENCIA = "advertencia"


# Invariantes bloqueantes que v1 no implementa. Salen como evidencia ausente en toda
# puerta que los cobraria (RF-QUA-14): declararlos es lo que impide darlos por buenos.
AUSENTES_EN_V1: dict[str, tuple[str, ...]] = {
    "escena_limpia": (
        "fuga_epistemica",
        "disciplina_de_pov",
        "violacion_de_regla_del_mundo",
    ),
    "outline_aprobado": (
        "conformidad_estructural",
        "restricciones_y_politicas_de_contenido",
    ),
    "capitulo_cerrado": (
        "fuga_epistemica",
        "disciplina_de_pov",
    ),
    "volumen_cerrado": ("promesa_al_lector",),
}


@dataclass(frozen=True)
class ResultadoDePuerta:
    """Lo que una puerta devuelve. Nunca un booleano suelto.

    Un booleano no distingue «limpia» de «no encontre nada porque no mire», y esa
    distincion es justo la que el principio 8 exige conservar.
    """

    fase: str
    politica: Politica
    defectos: tuple[Defecto, ...]
    evidencia_ausente: tuple[str, ...]

    @property
    def bloqueantes(self) -> tuple[Defecto, ...]:
        return tuple(d for d in self.defectos if d.severidad is Severidad.CRITICA)

    @property
    def superada(self) -> bool:
        """Solo una puerta sin defectos criticos y sin evidencia ausente esta superada.

        Una puerta de advertencia nunca para la linea, pero tampoco miente sobre lo que
        no ha podido comprobar.
        """
        if self.politica is Politica.ADVERTENCIA:
            return True
        return not self.bloqueantes and not self.evidencia_ausente

    @property
    def detiene_el_avance(self) -> bool:
        """Si el Orquestador puede pasar de fase."""
        return self.politica is Politica.BLOQUEANTE and not self.superada

    def explicacion(self) -> str:
        """Por que no se supero, en una linea legible en el panel de defectos."""
        if self.superada:
            return f"{self.fase}: superada"
        partes = []
        if self.bloqueantes:
            partes.append(f"{len(self.bloqueantes)} defecto(s) critico(s)")
        if self.evidencia_ausente:
            partes.append(f"evidencia ausente: {', '.join(self.evidencia_ausente)}")
        return f"{self.fase}: " + "; ".join(partes)


@dataclass
class Puerta:
    """Una fase con su politica y lo que cobra."""

    fase: str
    politica: Politica
    ausentes: tuple[str, ...] = field(default_factory=tuple)

    def evaluar(
        self, defectos: list[Defecto], *, extracciones_vacias: tuple[str, ...] = ()
    ) -> ResultadoDePuerta:
        """Evalua la puerta sobre los defectos recogidos.

        `extracciones_vacias` son los bloques declarados que llegaron vacios. No son un
        defecto —no hay nada que senalar— pero tampoco son una escena limpia: es F-01 de
        `verification.md` 11, y sale como evidencia ausente (RF-QUA-20).
        """
        ausente = tuple(sorted(set(self.ausentes) | set(extracciones_vacias)))
        return ResultadoDePuerta(
            fase=self.fase,
            politica=self.politica,
            defectos=tuple(defectos),
            evidencia_ausente=ausente,
        )


def outline_aprobado() -> Puerta:
    """Antes de redactar. Cobra lo que v1 puede cobrar del alcance de contrato."""
    return Puerta("outline_aprobado", Politica.BLOQUEANTE, AUSENTES_EN_V1["outline_aprobado"])


def escena_limpia() -> Puerta:
    """Antes de aceptar un borrador. Los invariantes bloqueantes que v1 implementa."""
    return Puerta("escena_limpia", Politica.BLOQUEANTE, AUSENTES_EN_V1["escena_limpia"])


def capitulo_cerrado() -> Puerta:
    """Fin de capitulo. Las dimensiones de escena reejecutadas sobre el capitulo cerrado."""
    return Puerta("capitulo_cerrado", Politica.BLOQUEANTE, AUSENTES_EN_V1["capitulo_cerrado"])


def volumen_cerrado() -> Puerta:
    """Final. Siembras, hilos, preguntas dramaticas y arcos."""
    return Puerta("volumen_cerrado", Politica.BLOQUEANTE, AUSENTES_EN_V1["volumen_cerrado"])
