"""Semaforo de credito, cola por prioridad y timeouts.

Lo que hay que acotar es la **ocupacion simultanea**, no la tasa: un cubo de fichas
dejaria pasar tres tareas grandes a la vez si el cubo esta lleno (D-14). Por eso es un
semaforo con reserva y liberacion.

La fuga que hay que evitar: toda ruta de salida libera la reserva. Una reserva no liberada
es credito perdido para siempre, y el sistema se va parando sin ningun error visible, que
es el modo de fallo mas dificil de diagnosticar de este apartado.

Cubre RF-ORQ-08 a RF-ORQ-12 y RNF-04.
"""

from __future__ import annotations

import heapq
import itertools
from dataclasses import dataclass, field

from backend.context.presupuesto import TECHO_DEL_SISTEMA

# Valores de partida de R-5. Se calibran con `Procedencia.latencia`.
TIMEOUT_POR_INVOCACION_S = 10 * 60
TIMEOUT_POR_TAREA_S = 30 * 60
TIMEOUT_POR_PLAN_S = 8 * 60 * 60

# Paralelismo por defecto. Con concurrencia 1 el control de tokens se reduce a comprobar
# el presupuesto del paquete, pero el mecanismo existe desde el primer dia (RNF-04).
PARALELISMO_POR_DEFECTO = 1


class ReservaImposible(Exception):
    """Una reserva mayor que el credito total. No se encola: no cabe ni vacio (D-15)."""

    def __init__(self, reserva: int, credito: int) -> None:
        super().__init__(
            f"Semaforo: error de planificacion, ninguna tarea puede exceder el techo. "
            f"Pide {reserva} tokens sobre un credito total de {credito}."
        )


@dataclass(order=True)
class _EnCola:
    """Entrada de la cola. Ordena por prioridad efectiva y, a igualdad, por llegada."""

    prioridad_efectiva: int
    secuencia: int
    tarea_id: str = field(compare=False)
    reserva: int = field(compare=False)
    prioridad_original: int = field(compare=False)
    esperas: int = field(default=0, compare=False)


@dataclass
class Semaforo:
    """Credito con reserva y liberacion.

    El credito se concede antes de invocar y se libera en **toda** ruta de salida: exito,
    fallo, timeout y cancelacion. No hay una sola ruta que se salte la liberacion, y eso
    es lo que comprueba la prueba de propiedades.
    """

    credito_total: int = TECHO_DEL_SISTEMA
    umbral_de_envejecimiento: int = 3
    en_vuelo: int = 0
    _reservas: dict[str, int] = field(default_factory=dict)
    _cola: list[_EnCola] = field(default_factory=list)
    _secuencia: itertools.count[int] = field(default_factory=itertools.count)

    # --- reserva y liberacion --------------------------------------------------------

    def admitir(self, tarea_id: str, reserva: int, prioridad: int) -> bool:
        """Concede la reserva o encola. Devuelve si la tarea puede invocar ya.

        Todo se encola; lo unico que se rechaza es lo que no cabe ni en un sistema vacio.
        """
        if reserva > self.credito_total:
            raise ReservaImposible(reserva, self.credito_total)

        if self.en_vuelo + reserva <= self.credito_total:
            self.en_vuelo += reserva
            self._reservas[tarea_id] = reserva
            return True

        heapq.heappush(
            self._cola,
            _EnCola(
                prioridad_efectiva=prioridad,
                secuencia=next(self._secuencia),
                tarea_id=tarea_id,
                reserva=reserva,
                prioridad_original=prioridad,
            ),
        )
        return False

    def liberar(self, tarea_id: str) -> int:
        """Devuelve el credito de una tarea. Idempotente a proposito.

        Que liberar dos veces no reste dos veces importa: la alternativa es que un camino
        de salida poco frecuente descuadre el contador y nadie lo note hasta que el
        sistema se para.
        """
        reserva = self._reservas.pop(tarea_id, 0)
        self.en_vuelo -= reserva
        return reserva

    def conciliar(self, tarea_id: str, uso_real: int) -> int:
        """Desviacion entre lo reservado y lo que `Procedencia` registro (RF-ORQ-09)."""
        return uso_real - self._reservas.get(tarea_id, 0)

    # --- cola ------------------------------------------------------------------------

    def drenar(self) -> list[str]:
        """Admite de la cola todo lo que quepa ahora, envejeciendo lo que espera.

        Sin envejecimiento la prioridad estricta mata de hambre a P2 y P3 en cualquier
        sesion larga, y la inanicion no se ve: el sistema parece sano y simplemente hay
        trabajo que nunca corre.
        """
        admitidas: list[str] = []
        rechazadas: list[_EnCola] = []

        while self._cola:
            entrada = heapq.heappop(self._cola)
            if self.en_vuelo + entrada.reserva <= self.credito_total:
                self.en_vuelo += entrada.reserva
                self._reservas[entrada.tarea_id] = entrada.reserva
                admitidas.append(entrada.tarea_id)
            else:
                entrada.esperas += 1
                if entrada.esperas >= self.umbral_de_envejecimiento:
                    entrada.prioridad_efectiva = max(0, entrada.prioridad_efectiva - 1)
                    entrada.esperas = 0
                rechazadas.append(entrada)

        for entrada in rechazadas:
            heapq.heappush(self._cola, entrada)
        return admitidas

    @property
    def en_cola(self) -> tuple[str, ...]:
        return tuple(e.tarea_id for e in sorted(self._cola))

    def prioridad_efectiva_de(self, tarea_id: str) -> int | None:
        for entrada in self._cola:
            if entrada.tarea_id == tarea_id:
                return entrada.prioridad_efectiva
        return None


@dataclass(frozen=True)
class Timeouts:
    """Tres niveles. Un vencimiento cuenta como fallo de contrato (D-07).

    Los valores son los de R-5, holgados a proposito: cancelar no cancela el coste, asi
    que un vencimiento falso es una invocacion pagada y perdida.
    """

    por_invocacion_s: int = TIMEOUT_POR_INVOCACION_S
    por_tarea_s: int = TIMEOUT_POR_TAREA_S
    por_plan_s: int = TIMEOUT_POR_PLAN_S

    def vencido(self, nivel: str, transcurrido_s: float) -> bool:
        limites = {
            "invocacion": self.por_invocacion_s,
            "tarea": self.por_tarea_s,
            "plan": self.por_plan_s,
        }
        if nivel not in limites:
            raise ValueError(
                f"Timeouts: nivel desconocido {nivel!r}; hay invocacion, tarea y plan"
            )
        return transcurrido_s > limites[nivel]
