"""`AlcanceDeRelevancia`: que entra en un paquete y que se queda fuera.

Tres dimensiones combinadas, y **el orden importa**: el temporal actua antes que el
epistemico. Primero se determina que es verdad en ese momento, y solo despues que de eso
conoce el POV. Aplicar el epistemico antes seria mas barato y estaria mal: decidiria que
existe en funcion de quien mira (`architecture.md` 4.4).

Cubre RF-CTX-05.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from backend.domain.diegetic.canon import Hecho


@dataclass(frozen=True)
class FiltroTemporal:
    """Solo los hechos vigentes en el momento de historia de la escena.

    Un hecho invalidado en el capitulo 8 no debe aparecer al escribir el 12: si aparece,
    el redactor escribe sobre un mundo que ya no existe y nadie lo detecta hasta la
    relectura.
    """

    momento: int
    orden_de_evento: dict[str, int]

    def aplicar(self, hechos: Sequence[Hecho]) -> tuple[Hecho, ...]:
        return tuple(h for h in hechos if self._vigente(h))

    def _vigente(self, hecho: Hecho) -> bool:
        desde = self.orden_de_evento.get(hecho.valido_desde)
        if desde is None or desde > self.momento:
            return False
        if hecho.valido_hasta is None:
            return True
        hasta = self.orden_de_evento.get(hecho.valido_hasta)
        return hasta is None or hasta > self.momento


@dataclass(frozen=True)
class FiltroEpistemico:
    """En POV limitado, solo lo que el narrador puede conocer.

    **En v1 no filtra nada.** `EstadoDeConocimiento` entra en la fase 2
    (`architecture.md` 13), asi que este filtro existe con su punto de insercion explicito
    y deja pasar todo. Es el supuesto S-9 de la spec: su ausencia produce falsos negativos
    —fugas que nadie detecta— y no falsos positivos.

    El punto de insercion esta aqui y no implicito en el orden de las llamadas para que,
    cuando llegue la fase 2, no haya que discutir donde va: ya esta puesto, y el test de
    RF-CTX-05 lo fija.
    """

    activo: bool = False

    def aplicar(self, hechos: Sequence[Hecho]) -> tuple[Hecho, ...]:
        if not self.activo:
            return tuple(hechos)
        raise NotImplementedError(
            "FiltroEpistemico: el filtrado por EstadoDeConocimiento entra en la fase 2 "
            "de architecture.md 13. Activarlo antes daria una falsa sensacion de que las "
            "fugas epistemicas se estan comprobando."
        )


@dataclass(frozen=True)
class FiltroEstructural:
    """Hilos activos, entidades presentes o mencionadas, motivos del acto en curso.

    Es el filtro que se apiesta cuando un paquete no cabe: subir el presupuesto esconderia
    que este filtro esta mal acotado (`architecture.md` 4.1).
    """

    entidades_presentes: frozenset[str]

    def aplicar(self, hechos: Sequence[Hecho]) -> tuple[Hecho, ...]:
        return tuple(h for h in hechos if h.sujeto_id in self.entidades_presentes)


@dataclass(frozen=True)
class AlcanceDeRelevancia:
    """Los tres filtros combinados, en el orden que fija la arquitectura."""

    temporal: FiltroTemporal
    epistemico: FiltroEpistemico
    estructural: FiltroEstructural

    def aplicar(self, hechos: Sequence[Hecho]) -> tuple[Hecho, ...]:
        """Temporal, luego epistemico, luego estructural. El orden no es negociable."""
        vigentes = self.temporal.aplicar(hechos)
        conocidos = self.epistemico.aplicar(vigentes)
        return self.estructural.aplicar(conocidos)
