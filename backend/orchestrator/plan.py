"""El `Plan` como DAG persistido y el bucle de reconciliacion.

El plan se materializa antes de ejecutar nada; el bucle compara el estado deseado —el
DAG— con el estado real —la tabla de `Tarea`— y emite las transiciones que faltan. El
paso siguiente depende de verificaciones deterministas, no de la valoracion de un modelo:
un router con un modelo decidiendo convertiria el control de flujo en salida no
determinista, y ese modelo acabaria juzgando trabajo propio (D-01).

Cubre RF-ORQ-01, RF-ORQ-02, RF-ORQ-21 y RF-ORQ-22.
"""

from __future__ import annotations

from dataclasses import dataclass

from backend.domain.production.ejecucion import Tarea
from backend.domain.vocabularies import EstadoDeTarea


class PlanCiclico(Exception):
    """El DAG no lo es. Se rechaza el plan entero; no se rompe el ciclo por heuristica."""

    def __init__(self, ciclo: tuple[str, ...]) -> None:
        self.ciclo = ciclo
        super().__init__(
            f"Plan: el grafo de dependencias tiene un ciclo y no es un DAG. "
            f"Ciclo: {' -> '.join(ciclo)}. Se rechaza el plan entero: romperlo por "
            f"heuristica elegiria por el planificador sin que nadie lo sepa."
        )


@dataclass
class DAG:
    """Las tareas de un plan con sus dependencias."""

    tareas: dict[str, Tarea]

    def __post_init__(self) -> None:
        self._exigir_aciclico()

    def _exigir_aciclico(self) -> None:
        estado: dict[str, int] = {}
        camino: list[str] = []

        def visitar(nodo: str) -> None:
            estado[nodo] = 1
            camino.append(nodo)
            for dependencia in self.tareas[nodo].depende_de if nodo in self.tareas else ():
                if dependencia not in self.tareas:
                    continue
                if estado.get(dependencia) == 1:
                    inicio = camino.index(dependencia)
                    raise PlanCiclico(tuple(camino[inicio:]) + (dependencia,))
                if estado.get(dependencia, 0) == 0:
                    visitar(dependencia)
            camino.pop()
            estado[nodo] = 2

        for nodo in self.tareas:
            if estado.get(nodo, 0) == 0:
                visitar(nodo)

    def listas(self) -> tuple[str, ...]:
        """Tareas que pueden pasar a `lista`.

        Una `Tarea` pasa a lista cuando, y solo cuando, todas sus `depende_de` estan
        `aceptada`. Ningun otro criterio la desbloquea: si un plan necesita adelantar
        trabajo sobre una dependencia sin aceptar, el plan esta mal descompuesto.
        """
        return tuple(
            identificador
            for identificador, tarea in sorted(self.tareas.items())
            if tarea.estado is EstadoDeTarea.PENDIENTE and self._dependencias_aceptadas(tarea)
        )

    def _dependencias_aceptadas(self, tarea: Tarea) -> bool:
        return all(
            self.tareas[d].estado is EstadoDeTarea.ACEPTADA
            for d in tarea.depende_de
            if d in self.tareas
        )

    def subarbol_de(self, tarea_id: str) -> frozenset[str]:
        """Todo lo que depende de una tarea, directa o indirectamente.

        Cancelar una tarea cancela su subarbol: los artefactos ya producidos se marcan
        obsoletos, nunca se borran (RF-ORQ-16).
        """
        dependientes: set[str] = set()
        pendientes = [tarea_id]
        while pendientes:
            actual = pendientes.pop()
            for identificador, tarea in self.tareas.items():
                if actual in tarea.depende_de and identificador not in dependientes:
                    dependientes.add(identificador)
                    pendientes.append(identificador)
        return frozenset(dependientes)


@dataclass(frozen=True)
class Reconciliacion:
    """Lo que el bucle decide en una pasada. Determinista por construccion."""

    a_listar: tuple[str, ...]
    bloqueadas: tuple[str, ...]


def reconciliar(dag: DAG) -> Reconciliacion:
    """Una pasada del bucle: compara el DAG con la tabla y dice que falta mover."""
    bloqueadas = tuple(
        identificador
        for identificador, tarea in sorted(dag.tareas.items())
        if tarea.estado is EstadoDeTarea.BLOQUEADA
    )
    return Reconciliacion(a_listar=dag.listas(), bloqueadas=bloqueadas)


def cadena_de_escena(escena_id: str, plan_id: str) -> tuple[Tarea, ...]:
    """La cadena secuencial de una escena, expresada en el DAG y no en la configuracion.

    Redaccion, verificacion y canonizacion de una misma escena son secuenciales por
    construccion, porque cada paso consume la salida del anterior (D-05). Con concurrencia
    1 la regla se cumpliria de todas formas, pero entonces viviria en un parametro en vez
    de en el plan, y dejaria de cumplirse el dia que alguien suba el paralelismo.
    """
    redaccion = Tarea(
        id=f"{escena_id}:redaccion",
        plan_id=plan_id,
        tipo="redaccion",
        rol_asignado="redactor",
        prioridad=1,
    )
    verificacion = Tarea(
        id=f"{escena_id}:verificacion",
        plan_id=plan_id,
        tipo="verificacion",
        rol_asignado="guardian_de_continuidad",
        prioridad=1,
        depende_de=(redaccion.id,),
    )
    canonizacion = Tarea(
        id=f"{escena_id}:canonizacion",
        plan_id=plan_id,
        tipo="canonizacion",
        rol_asignado="canonizador",
        prioridad=0,  # P0: una canonizacion pendiente bloquea todo su subarbol
        depende_de=(verificacion.id,),
    )
    return (redaccion, verificacion, canonizacion)
