"""Consumidor de la cola de `Tarea`. Invoca modelos e informa; no decide.

El worker no escribe el estado de la `Tarea`, no elige la siguiente y no decide
reintentar. Lo unico que aporta al Orquestador es una descripcion precisa de su fallo,
para que pueda clasificarlo en una de las cuatro clases (D-02).

Cubre RF-WRK-01 a RF-WRK-05, RF-WRK-08 y RF-WRK-09.
"""

from __future__ import annotations

import time
import uuid
from dataclasses import dataclass

from backend.agents.redactor.redactor import (
    VERSION_DE_PROMPT,
    SalidaDelRedactor,
    SalidaInvalida,
    parsear,
)
from backend.domain.production.ejecucion import Procedencia
from backend.domain.vocabularies import ClaseDeFallo
from backend.worker.modelo import (
    MAX_TOKENS_REDACCION,
    MODELO_DEL_REDACTOR,
    ClienteDeModelo,
    clasificar_excepcion,
)


@dataclass(frozen=True)
class Informe:
    """Lo que el worker devuelve al Orquestador. Nunca un estado.

    Trae siempre `Procedencia`, tambien cuando falla: una invocacion que se pago y se
    perdio tiene que quedar anotada, porque es la metrica que revela caidas recurrentes.
    """

    tarea_id: str
    procedencia: Procedencia
    salida: SalidaDelRedactor | None = None
    clase_de_fallo: ClaseDeFallo | None = None
    detalle_del_fallo: str = ""

    @property
    def tuvo_exito(self) -> bool:
        return self.salida is not None and self.clase_de_fallo is None


@dataclass
class Worker:
    """Invoca al Redactor con los parametros de R-1 y devuelve un informe."""

    cliente: ClienteDeModelo

    def ejecutar(self, tarea_id: str, paquete_id: str, prompt: str) -> Informe:
        """Una invocacion. Sin estado propio: todo lo que sabe se lo dan y lo devuelve."""
        comienzo = time.monotonic()
        try:
            respuesta = self.cliente.invocar(prompt, max_tokens=MAX_TOKENS_REDACCION)
        except Exception as error:  # noqa: BLE001 - se clasifica, no se traga
            return Informe(
                tarea_id=tarea_id,
                procedencia=self._procedencia(
                    paquete_id,
                    0,
                    int((time.monotonic() - comienzo) * 1000),
                    clasificar_excepcion(error),
                ),
                clase_de_fallo=clasificar_excepcion(error),
                detalle_del_fallo=str(error),
            )

        latencia = int((time.monotonic() - comienzo) * 1000)
        try:
            salida = parsear(respuesta.texto)
        except SalidaInvalida as error:
            return Informe(
                tarea_id=tarea_id,
                procedencia=self._procedencia(
                    paquete_id, respuesta.coste, latencia, ClaseDeFallo.CONTRATO
                ),
                clase_de_fallo=ClaseDeFallo.CONTRATO,
                detalle_del_fallo=str(error),
            )

        if salida.contexto_insuficiente:
            # El agente se rindio en lugar de inventar. Es un resultado legitimo.
            return Informe(
                tarea_id=tarea_id,
                procedencia=self._procedencia(paquete_id, respuesta.coste, latencia, None),
                salida=salida,
            )

        return Informe(
            tarea_id=tarea_id,
            procedencia=self._procedencia(paquete_id, respuesta.coste, latencia, None),
            salida=salida,
        )

    @staticmethod
    def _procedencia(
        paquete_id: str, coste: float, latencia_ms: int, clase: ClaseDeFallo | None
    ) -> Procedencia:
        """Toda invocacion registra procedencia, incluidas las que fallan (RF-WRK-03).

        No lleva prosa: los registros referencian el id del `Borrador`. Duplicar el texto
        crearia una segunda copia que nadie invalida cuando la escena se reescribe.
        """
        return Procedencia(
            id=f"pr-{uuid.uuid4().hex[:12]}",
            agente="redactor",
            modelo=MODELO_DEL_REDACTOR,
            version_de_prompt=VERSION_DE_PROMPT,
            paquete_id=paquete_id,
            parametros_muestreo="thinking=adaptive;effort=high",
            coste=coste,
            latencia_ms=latencia_ms,
            clase_de_fallo=clase,
        )
