"""Maquina de estados de `Tarea` y escalera de reintentos.

Las transiciones las escribe **solo** el Orquestador. El worker informa del resultado y no
decide el estado: una unica autoridad sobre la maquina es lo que permite comprobarla por
modelos y lo que evita dos escritores sobre SQLite (D-02).

Cubre RF-ORQ-02 a RF-ORQ-07, RF-ORQ-23 y RF-ORQ-24.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from backend.domain.production.ejecucion import Intento, Tarea
from backend.domain.vocabularies import ClaseDeFallo, EstadoDeTarea

# Transiciones legitimas. Lo que no esta aqui no ocurre: el vocabulario es cerrado y la
# maquina tambien (`AGENTS.md` 7.1).
TRANSICIONES: dict[EstadoDeTarea, frozenset[EstadoDeTarea]] = {
    EstadoDeTarea.PENDIENTE: frozenset({EstadoDeTarea.LISTA, EstadoDeTarea.CANCELADA}),
    EstadoDeTarea.LISTA: frozenset(
        {EstadoDeTarea.EN_CURSO, EstadoDeTarea.BLOQUEADA, EstadoDeTarea.CANCELADA}
    ),
    EstadoDeTarea.EN_CURSO: frozenset(
        {
            EstadoDeTarea.EN_VERIFICACION,
            EstadoDeTarea.FALLIDA,
            EstadoDeTarea.BLOQUEADA,
            EstadoDeTarea.LISTA,
            EstadoDeTarea.CANCELADA,
        }
    ),
    EstadoDeTarea.EN_VERIFICACION: frozenset(
        {EstadoDeTarea.ACEPTADA, EstadoDeTarea.RECHAZADA, EstadoDeTarea.ESCALADA}
    ),
    EstadoDeTarea.RECHAZADA: frozenset({EstadoDeTarea.LISTA, EstadoDeTarea.ESCALADA}),
    EstadoDeTarea.FALLIDA: frozenset({EstadoDeTarea.LISTA, EstadoDeTarea.ESCALADA}),
    EstadoDeTarea.BLOQUEADA: frozenset({EstadoDeTarea.LISTA, EstadoDeTarea.CANCELADA}),
    EstadoDeTarea.ESCALADA: frozenset({EstadoDeTarea.ACEPTADA, EstadoDeTarea.LISTA}),
    # Terminales: todo camino de la maquina acaba en uno de estos dos.
    EstadoDeTarea.ACEPTADA: frozenset(),
    EstadoDeTarea.CANCELADA: frozenset(),
}

TERMINALES = frozenset({EstadoDeTarea.ACEPTADA, EstadoDeTarea.CANCELADA})

MAXIMO_DE_INTENTOS = 4


class TransicionInvalida(Exception):
    """Alguien intento mover una tarea por un camino que la maquina no tiene."""

    def __init__(self, desde: EstadoDeTarea, hasta: EstadoDeTarea) -> None:
        super().__init__(
            f"Tarea: transicion no permitida por la maquina de estados. "
            f"De {desde.value} a {hasta.value}; permitidas: "
            f"{', '.join(sorted(e.value for e in TRANSICIONES[desde])) or 'ninguna'}"
        )


class Accion(Enum):
    """Que hacer con una tarea que no supero la verificacion (`architecture.md` 6.3)."""

    REESCRIBIR = "reescritura con los defectos como instruccion"
    REESCRIBIR_CON_MAS_CONTEXTO = "reescritura con contexto ampliado"
    REPLANIFICAR = "replanificacion de la escena"
    ESCALAR = "escalado a humano"


def transicionar(tarea: Tarea, hasta: EstadoDeTarea) -> Tarea:
    """Mueve la tarea, o falla ruidosamente si el camino no existe."""
    import dataclasses

    if hasta not in TRANSICIONES[tarea.estado]:
        raise TransicionInvalida(tarea.estado, hasta)
    return dataclasses.replace(tarea, estado=hasta)


def clasificar(tarea: Tarea, clase: ClaseDeFallo, tipo_de_defecto: str | None = None) -> Tarea:
    """Anota un intento en el historial tipificado.

    No incrementa dos contadores: guarda el suceso con su clase, y los contadores salen
    por agregacion. Mezclar las cuatro clases en un solo contador hace que un corte de red
    consuma el presupuesto de reescrituras de una escena y la mande a escalado sin que
    nadie haya leido nunca una prosa mala (D-06).
    """
    import dataclasses

    intento = Intento(
        numero=len(tarea.historial) + 1,
        clase_de_fallo=clase,
        tipo_de_defecto=tipo_de_defecto,
    )
    return dataclasses.replace(tarea, historial=(*tarea.historial, intento))


def siguiente_accion(tarea: Tarea) -> Accion:
    """La escalera de `architecture.md` 6.3, con su atajo.

    Si dos intentos consecutivos producen el mismo tipo de defecto, el problema no es la
    redaccion: se replanifica en lugar de reintentar. Repetir la misma operacion esperando
    un resultado distinto es el modo de fallo mas caro de estos sistemas.
    """
    if tarea.repite_tipo_de_defecto:
        return Accion.REPLANIFICAR

    narrativos = tarea.intentos_narrativos
    if narrativos <= 1:
        return Accion.REESCRIBIR
    if narrativos == 2:
        return Accion.REESCRIBIR_CON_MAS_CONTEXTO
    if narrativos == 3:
        return Accion.REPLANIFICAR
    return Accion.ESCALAR


@dataclass(frozen=True)
class PoliticaDeTransporte:
    """Los reintentos de transporte los hace el cliente del SDK, no el worker (R-2).

    Esta clase existe para dejar el numero en un sitio y para que quede escrito por que no
    hay una escalera propia: dos capas de reintento multiplican, y tres por tres son nueve
    llamadas pagadas por un corte de red. Tambien destrozan la contabilidad de coste, que
    es lo que RF-ORQ-09 concilia.
    """

    max_reintentos: int = 3

    def consume_intento_narrativo(self) -> bool:
        return False


def alcanzables(desde: EstadoDeTarea) -> frozenset[EstadoDeTarea]:
    """Cierre transitivo de la maquina. Lo usa la comprobacion de modelos."""
    vistos: set[EstadoDeTarea] = set()
    pendientes = [desde]
    while pendientes:
        actual = pendientes.pop()
        for siguiente in TRANSICIONES[actual]:
            if siguiente not in vistos:
                vistos.add(siguiente)
                pendientes.append(siguiente)
    return frozenset(vistos)
