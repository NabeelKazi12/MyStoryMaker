"""Consumidor de la cola de `Tarea`. Invoca modelos e informa; no decide.

El worker no escribe el estado de la `Tarea`, no elige la siguiente y no decide
reintentar. Lo unico que aporta al Orquestador es una descripcion precisa de su fallo,
para que pueda clasificarlo en una de las cuatro clases (D-02).

Cubre RF-WRK-01 a RF-WRK-05, RF-WRK-08 y RF-WRK-09.
"""

from __future__ import annotations

import dataclasses
import time
import uuid
from dataclasses import dataclass

from backend.agents.redactor.redactor import (
    VERSION_DE_PROMPT,
    SalidaDelRedactor,
    SalidaInvalida,
    parsear,
)
from backend.context.presupuesto import MAXIMO_DE_ENTRADA, contar_tokens
from backend.domain.production.ejecucion import Procedencia
from backend.domain.vocabularies import ClaseDeFallo
from backend.worker.modelo import (
    MAX_TOKENS_REDACCION,
    ClienteDeModelo,
    clasificar_excepcion,
)


@dataclass(frozen=True)
class InformeCrudo:
    """Una invocacion pagada, con su texto sin interpretar.

    Existe para que los dos roles que invocan modelos -Redactor y Planner- compartan el
    pago, el recuento y la procedencia sin compartir el contrato de salida. Cada uno
    valida el suyo, que es lo que impide que un objeto acabe decidiendo que esquema
    aplicar segun una cadena.
    """

    tarea_id: str
    procedencia: Procedencia
    texto: str = ""
    clase_de_fallo: ClaseDeFallo | None = None
    detalle_del_fallo: str = ""

    @property
    def tuvo_exito(self) -> bool:
        return self.clase_de_fallo is None


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
    """Invoca a un rol con los parametros de R-1 y devuelve un informe.

    `agente` es de quien se registra la `Procedencia`. No es cosmetico: sin el, la apertura
    del canon quedaria anotada como si la hubiera escrito el Redactor, y la pregunta
    «quien propuso este lugar» dejaria de tener respuesta.

    El parseo de la salida **no** ocurre aqui cuando el rol no es el Redactor: este worker
    conoce un unico contrato, y quien invoca a otro rol parsea con el suyo. Mezclar los dos
    aqui pondria a un solo objeto a decidir que contrato aplica segun una cadena.
    """

    cliente: ClienteDeModelo
    agente: str = "redactor"

    def invocar(self, tarea_id: str, paquete_id: str, prompt: str) -> InformeCrudo:
        """Una invocacion, sin interpretar la respuesta.

        Es lo que comparten todos los roles: contar el paquete, pagar la llamada y anotar
        la procedencia. Lo que cada rol hace con el texto es cosa suya, y por eso no pasa
        por aqui.
        """
        comienzo = time.monotonic()

        tokens_de_entrada = contar_tokens(prompt)
        if tokens_de_entrada > MAXIMO_DE_ENTRADA:
            # Se para antes de pagar la llamada. Un paquete que no cabe es fallo de
            # presupuesto, no de contenido: no consume intentos narrativos (D-06).
            detalle = (
                f"el prompt ocupa {tokens_de_entrada} tokens sobre el maximo de entrada "
                f"de {MAXIMO_DE_ENTRADA} (RF-CTX-08); no se envia"
            )
            return InformeCrudo(
                tarea_id=tarea_id,
                procedencia=self._procedencia(
                    paquete_id,
                    0,
                    int((time.monotonic() - comienzo) * 1000),
                    ClaseDeFallo.PRESUPUESTO,
                ),
                clase_de_fallo=ClaseDeFallo.PRESUPUESTO,
                detalle_del_fallo=detalle,
            )

        try:
            respuesta = self.cliente.invocar(prompt, max_tokens=MAX_TOKENS_REDACCION)
        except Exception as error:  # noqa: BLE001 - se clasifica, no se traga
            return InformeCrudo(
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

        return InformeCrudo(
            tarea_id=tarea_id,
            procedencia=self._procedencia(
                paquete_id,
                respuesta.coste,
                int((time.monotonic() - comienzo) * 1000),
                None,
            ),
            texto=respuesta.texto,
        )

    def ejecutar(self, tarea_id: str, paquete_id: str, prompt: str) -> Informe:
        """Una invocacion del Redactor, con su salida ya validada contra el esquema."""
        crudo = self.invocar(tarea_id, paquete_id, prompt)
        if crudo.clase_de_fallo is not None:
            return Informe(
                tarea_id=crudo.tarea_id,
                procedencia=crudo.procedencia,
                clase_de_fallo=crudo.clase_de_fallo,
                detalle_del_fallo=crudo.detalle_del_fallo,
            )

        try:
            salida = parsear(crudo.texto)
        except SalidaInvalida as error:
            return Informe(
                tarea_id=crudo.tarea_id,
                procedencia=dataclasses.replace(
                    crudo.procedencia, clase_de_fallo=ClaseDeFallo.CONTRATO
                ),
                clase_de_fallo=ClaseDeFallo.CONTRATO,
                detalle_del_fallo=str(error),
            )

        # Si el agente se rindio, `salida.contexto_insuficiente` lo dice y trae su `falta`.
        # Es un resultado legitimo, no un fallo: el Orquestador reconstruye el paquete o
        # replanifica (RF-WRK-05).
        return Informe(
            tarea_id=crudo.tarea_id, procedencia=crudo.procedencia, salida=salida
        )

    def _procedencia(
        self, paquete_id: str, coste: float, latencia_ms: int, clase: ClaseDeFallo | None
    ) -> Procedencia:
        """Toda invocacion registra procedencia, incluidas las que fallan (RF-WRK-03).

        No lleva prosa: los registros referencian el id del `Borrador`. Duplicar el texto
        crearia una segunda copia que nadie invalida cuando la escena se reescribe.

        El modelo sale del cliente y no de una constante: es lo que hace que una
        invocacion de demostracion quede reconocible para siempre en la misma columna en
        la que se mira siempre cual respondio (RF-MOD-03).
        """
        return Procedencia(
            id=f"pr-{uuid.uuid4().hex[:12]}",
            agente=self.agente,
            modelo=self.cliente.modelo,
            version_de_prompt=VERSION_DE_PROMPT,
            paquete_id=paquete_id,
            parametros_muestreo="thinking=adaptive;effort=high",
            coste=coste,
            latencia_ms=latencia_ms,
            clase_de_fallo=clase,
        )
