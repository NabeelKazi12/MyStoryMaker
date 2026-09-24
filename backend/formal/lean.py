"""Generacion del fichero Lean con la cronologia de la novela.

El fichero se **genera** desde SQLite y no se escribe a mano. Si se pudiera editar, Lean
verificaria la historia que el fichero cuenta y no la que la novela tiene, que es una
forma elegante de no verificar nada.

Este modulo no demuestra nada: prepara los datos. Los invariantes viven en
`lean/MyStoryMaker/Cronologia.lean` y los comprueba `lake build`. Lo que si hace aqui es
`incoherencias_detectables`, que existe por un motivo concreto: poder **enseñar** el caso
de RF-LEAN-05 sin depender de que el toolchain de Lean este instalado, y poder sembrar
incoherencias en los briefs de evaluacion sabiendo cuales son.

Cubre RF-LEAN-01.
"""

from __future__ import annotations

from dataclasses import dataclass

from backend.store.repositories import StoryBible

# Donde vive el proyecto Lean, relativo a la raiz del repositorio.
RAIZ_LEAN = "lean"

CABECERA = """-- generado por backend/formal/lean.py desde la story bible en SQLite.
-- NO EDITAR A MANO: se regenera en cada verificacion, y un cambio aqui no cambia la
-- novela, solo hace que Lean verifique una historia distinta de la que se lee.

namespace MyStoryMaker

structure Evento where
  evento_id : String
  momento : Int
  lugar_id : String
  personajes : List String
  deriving Repr

structure Personaje where
  personaje_id : String
  anio_de_nacimiento : Int
  deriving Repr
"""


@dataclass(frozen=True)
class Incoherencia:
    """Algo que la cronologia afirma y que no puede ser cierto."""

    tipo: str
    detalle: str


def generar_cronologia_lean(biblia: StoryBible) -> str:
    """Escribe la cronologia como datos de Lean, en orden estable.

    El orden importa: dos generaciones seguidas tienen que dar el mismo fichero, o el
    diff deja de significar nada y nadie sabe si la historia cambio o solo el orden.
    """
    filas = sorted(biblia.cronologia(), key=lambda f: (f.momento or 0, f.evento_id))
    personajes = sorted(
        (p for p in biblia.personajes() if p.anio_de_nacimiento is not None),
        key=lambda p: p.id,
    )

    eventos = "\n".join(
        f"  {{ evento_id := {fila.evento_id!r}, momento := {fila.momento}, "
        f"lugar_id := {(fila.lugar_id or '')!r}, "
        f"personajes := [{', '.join(repr(p) for p in fila.personajes)}] }},"
        for fila in filas
    ).replace("'", '"')

    nacimientos = "\n".join(
        f"  {{ personaje_id := {p.id!r}, anio_de_nacimiento := {p.anio_de_nacimiento} }},"
        for p in personajes
    ).replace("'", '"')

    return (
        f"{CABECERA}\n"
        f"def eventos : List Evento := [\n{eventos}\n]\n\n"
        f"def personajes : List Personaje := [\n{nacimientos}\n]\n\n"
        f"end MyStoryMaker\n"
    )


def incoherencias_detectables(biblia: StoryBible) -> tuple[Incoherencia, ...]:
    """Las incoherencias que los invariantes de Lean encontrarian, calculadas en Python.

    No sustituye a Lean y no pretende hacerlo: Lean demuestra sobre toda la cronologia y
    esto comprueba la concreta. Existe para dos cosas que si son de Python: sembrar
    incoherencias a proposito en los briefs de evaluacion, y poder enseñar el caso de
    RF-LEAN-05 aunque el toolchain no este instalado en la maquina de quien revisa.
    """
    problemas: list[Incoherencia] = []
    nacimientos = {
        p.id: p.anio_de_nacimiento
        for p in biblia.personajes()
        if p.anio_de_nacimiento is not None
    }
    filas = biblia.cronologia()

    for fila in filas:
        for personaje_id in fila.personajes:
            nacimiento = nacimientos.get(personaje_id)
            if nacimiento is None or fila.momento is None:
                continue
            if fila.momento - nacimiento < 0:
                problemas.append(
                    Incoherencia(
                        tipo="edad_negativa",
                        detalle=(
                            f"{personaje_id} participa en {fila.evento_id} en "
                            f"{fila.momento} y nace en {nacimiento}: tendria "
                            f"{fila.momento - nacimiento} anos"
                        ),
                    )
                )

    por_personaje: dict[tuple[str, int], set[str]] = {}
    for fila in filas:
        if fila.momento is None or not fila.lugar_id:
            continue
        for personaje_id in fila.personajes:
            por_personaje.setdefault((personaje_id, fila.momento), set()).add(fila.lugar_id)

    for (personaje_id, momento), lugares in sorted(por_personaje.items()):
        if len(lugares) > 1:
            problemas.append(
                Incoherencia(
                    tipo="ubicuidad",
                    detalle=(
                        f"{personaje_id} esta en {sorted(lugares)} a la vez en el "
                        f"momento {momento}"
                    ),
                )
            )

    return tuple(problemas)
