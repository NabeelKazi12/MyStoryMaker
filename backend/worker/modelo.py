"""Cliente de modelo. Aqui, y solo aqui, viven las llamadas al proveedor.

`api/` no lo alcanza por ninguna ruta: encola una `Tarea` y lee estado. El trabajo ocurre
aqui (`architecture.md` 2.3, regla 5).

La invocacion esta detras de un protocolo a proposito. No es una abstraccion gratuita:
sin ella el bucle de E7 no se podria ejecutar ni probar sin credenciales, y el sistema
solo se sabria roto la primera vez que alguien pagara por descubrirlo.

Cubre RF-WRK-01 a RF-WRK-05 y RF-WRK-09.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol

from backend.context.presupuesto import TECHO_DE_SALIDA_REDACCION
from backend.domain.vocabularies import ClaseDeFallo

# R-1. El identificador sale de una tabla de referencia que este entorno no ha podido
# contrastar contra la API de modelos: hay que confirmarlo antes de invocar de verdad.
MODELO_DEL_REDACTOR = "claude-opus-5"

# El techo de salida es el de `architecture.md` 4.2, no uno mayor: con 8.000 la reserva
# subiria a 32.000 y tres escenas concurrentes mas un juicio pasarian de 100.000.
MAX_TOKENS_REDACCION = TECHO_DE_SALIDA_REDACCION

# Opus 5 corre pensamiento adaptativo por defecto y rechaza `budget_tokens` con un 400.
PENSAMIENTO = "adaptive"
ESFUERZO = "high"


class FalloDeInvocacion(Exception):
    """Un fallo que el worker describe con precision suficiente para clasificarlo.

    Un worker que solo sabe decir «ha fallado» obliga al Orquestador a tratar todo fallo
    como el peor caso (D-02).
    """

    def __init__(self, clase: ClaseDeFallo, detalle: str) -> None:
        self.clase = clase
        self.detalle = detalle
        super().__init__(f"Invocacion fallida [{clase.value}]: {detalle}")


@dataclass(frozen=True)
class Respuesta:
    """Lo que devuelve una invocacion, con lo que hace falta para la `Procedencia`."""

    texto: str
    tokens_entrada: int
    tokens_salida: int
    modelo: str
    truncada: bool = False
    coste: float = 0.0
    latencia_ms: int = 0


class ClienteDeModelo(Protocol):
    """Lo minimo que el worker necesita de un proveedor."""

    def invocar(self, prompt: str, *, max_tokens: int) -> Respuesta: ...


@dataclass
class ClienteFalso:
    """Cliente determinista para pruebas y para el bucle de E7 sin credenciales.

    No simula calidad literaria: simula el **contrato**. Devuelve lo que se le programa,
    y eso basta para comprobar que el orquestador clasifica, reintenta, canoniza y
    escala como debe.
    """

    respuestas: list[Respuesta | Exception] = field(default_factory=list)
    invocaciones: list[str] = field(default_factory=list)

    def invocar(self, prompt: str, *, max_tokens: int) -> Respuesta:
        self.invocaciones.append(prompt)
        if not self.respuestas:
            raise FalloDeInvocacion(ClaseDeFallo.TRANSPORTE, "sin respuestas programadas")
        siguiente = self.respuestas.pop(0)
        if isinstance(siguiente, Exception):
            raise siguiente
        if siguiente.tokens_salida > max_tokens:
            # Alcanzar el techo trunca la salida, y eso es fallo de contrato, no una
            # invitacion a ampliar el techo (`architecture.md` 6.6).
            raise FalloDeInvocacion(
                ClaseDeFallo.CONTRATO,
                f"salida truncada al alcanzar max_tokens={max_tokens}",
            )
        return siguiente


def clasificar_excepcion(error: Exception) -> ClaseDeFallo:
    """Traduce un fallo en una de las cuatro clases de D-06.

    Es lo que permite que un corte de red no consuma el presupuesto de reescrituras de
    una escena.
    """
    if isinstance(error, FalloDeInvocacion):
        return error.clase
    if isinstance(error, TimeoutError):
        # Un vencimiento cuenta como fallo de contrato (D-07).
        return ClaseDeFallo.CONTRATO
    if isinstance(error, (ConnectionError, OSError)):
        return ClaseDeFallo.TRANSPORTE
    return ClaseDeFallo.CONTRATO


def construir_cliente_real() -> ClienteDeModelo:
    """El cliente del proveedor, con los reintentos de transporte del SDK (R-2).

    No se construye en import time: sin credenciales, importar este modulo debe seguir
    funcionando para que la suite corra.
    """
    raise NotImplementedError(
        "Cliente real no cableado. Antes de habilitarlo hay que confirmar el modelo de "
        "R-1 contra la API de modelos, que este entorno no puede consultar: es la "
        "salvedad declarada en SPEC-001 9.2 y la marcha atras de E2 en el plan."
    )
