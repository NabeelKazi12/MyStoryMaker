"""Validadores deterministas de la personalizacion: nombres, longitud y elementos.

SPEC-003, fase B. Cubre RF-VAL-02, RF-VAL-03, RF-VAL-04 y RF-VAL-09.

Los tres son deterministas y por eso bloquean. Lo que **no** comprueban, y conviene tener
a la vista: ninguno dice si el capitulo esta bien escrito. Un capitulo puede nombrar
correctamente a todos los personajes, medir lo que toca y traer todos los recuerdos, y
ser ilegible. Eso lo cobra el juez con rubrica de la fase C, que penaliza y no bloquea.
"""

from __future__ import annotations

import sqlite3

import pytest

from backend.domain.spec.encargo import Destinatario, ElementoPersonalizado
from backend.domain.vocabularies import Severidad, TipoDeElementoPersonalizado
from backend.quality.personalizacion import (
    RANGO_DE_CAPITULO,
    VALIDADORES,
    PuntoDeEjecucion,
    elementos_obligatorios_presentes,
    longitud_de_capitulo,
    nombres_exactos,
)
from backend.store.repositories import UsoDeHechos
from tests.conftest import material_minimo

MARTA = Destinatario(
    id="de-1",
    nombre="Marta",
    edad=34,
    elementos=(
        ElementoPersonalizado(
            id="ep-1",
            tipo=TipoDeElementoPersonalizado.RECUERDO,
            contenido="el verano en que aprendio a nadar",
        ),
        ElementoPersonalizado(
            id="ep-2",
            tipo=TipoDeElementoPersonalizado.RASGO,
            contenido="nunca llega tarde",
            obligatorio=False,
        ),
    ),
)


# --- B-05: los nombres se escriben como en la story bible ---------------------------


@pytest.mark.invariants
def test_un_nombre_que_no_coincide_con_la_story_bible_es_defecto() -> None:
    """RF-VAL-02. Una novela de regalo que escribe mal el nombre deja de ser un regalo."""
    defectos = nombres_exactos(
        "Marte abrio la puerta y sonrio.", destinatario=MARTA, personajes=("Irene",)
    )

    assert [d.tipo for d in defectos] == ["nombre_del_destinatario"]
    assert defectos[0].severidad is Severidad.CRITICA
    assert "Marta" in defectos[0].evidencia


@pytest.mark.invariants
def test_el_nombre_escrito_igual_no_produce_defecto() -> None:
    defectos = nombres_exactos(
        "Marta abrio la puerta.", destinatario=MARTA, personajes=("Irene",)
    )
    assert defectos == []


@pytest.mark.invariants
def test_un_personaje_del_canon_escrito_de_otra_forma_es_defecto() -> None:
    """Vale para cualquier personaje, no solo para el destinatario."""
    defectos = nombres_exactos(
        "Marta hablo con Irenne toda la tarde.", destinatario=MARTA, personajes=("Irene",)
    )

    assert [d.tipo for d in defectos] == ["nombre_de_personaje"]
    assert "Irene" in defectos[0].evidencia


@pytest.mark.invariants
def test_un_nombre_ausente_no_es_defecto_de_este_validador() -> None:
    """Que el destinatario aparezca en **algun** capitulo lo cobra RF-VAL-04.

    Exigirlo tambien aqui haria fallar todos los capitulos que legitimamente no lo
    nombran, y dos validadores respondiendo a la misma pregunta dejan sin decidir cual
    manda.
    """
    assert nombres_exactos("La tarde caia.", destinatario=MARTA, personajes=("Irene",)) == []


# --- B-06: la longitud del capitulo -------------------------------------------------


@pytest.mark.invariants
@pytest.mark.parametrize("palabras", [RANGO_DE_CAPITULO[0] - 1, RANGO_DE_CAPITULO[1] + 1])
def test_un_capitulo_fuera_de_rango_es_defecto(palabras: int) -> None:
    """RF-VAL-03. Los dos extremos importan: uno corto no cuenta nada, uno largo cansa."""
    defectos = longitud_de_capitulo("palabra " * palabras)

    assert [d.tipo for d in defectos] == ["longitud_de_capitulo"]
    assert str(palabras) in defectos[0].evidencia


@pytest.mark.invariants
def test_un_capitulo_dentro_del_rango_no_produce_defecto() -> None:
    medio = (RANGO_DE_CAPITULO[0] + RANGO_DE_CAPITULO[1]) // 2
    assert longitud_de_capitulo("palabra " * medio) == []


@pytest.mark.invariants
def test_el_rango_se_puede_estrechar_por_brief_sin_tocar_el_validador() -> None:
    """La extension la declara el brief; el validador solo la cobra."""
    assert longitud_de_capitulo("palabra " * 100, rango=(50, 150)) == []
    assert longitud_de_capitulo("palabra " * 100, rango=(200, 300)) != []


# --- B-07: los elementos obligatorios aparecen en algun capitulo ---------------------


@pytest.mark.invariants
def test_un_elemento_obligatorio_ausente_de_todos_los_capitulos_es_defecto(
    conn: sqlite3.Connection,
) -> None:
    """RF-VAL-04. Se comprueba contra la tabla de hechos, no leyendo la prosa.

    Buscar el texto del recuerdo dentro del capitulo daria por bueno cualquier parafraseo
    y por malo cualquier integracion elegante. Lo que se comprueba es que el hecho que
    representa ese elemento quedo usado en algun capitulo.
    """
    material_minimo(conn)

    defectos = elementos_obligatorios_presentes(
        MARTA, usos=UsoDeHechos(conn), hechos_por_elemento={"ep-1": "he-recuerdo"}
    )

    assert [d.tipo for d in defectos] == ["elemento_personalizado_ausente"]
    assert "ep-1" in defectos[0].evidencia


@pytest.mark.invariants
def test_un_elemento_obligatorio_usado_en_un_capitulo_no_produce_defecto(
    conn: sqlite3.Connection,
) -> None:
    material_minimo(conn)
    usos = UsoDeHechos(conn)
    usos.registrar("he-recuerdo", "cap-1")

    defectos = elementos_obligatorios_presentes(
        MARTA, usos=usos, hechos_por_elemento={"ep-1": "he-recuerdo"}
    )

    assert defectos == []


@pytest.mark.invariants
def test_un_elemento_opcional_ausente_no_bloquea(conn: sqlite3.Connection) -> None:
    """Marcarlo todo como obligatorio convierte el validador en un bloqueo permanente."""
    material_minimo(conn)

    defectos = elementos_obligatorios_presentes(
        MARTA,
        usos=UsoDeHechos(conn),
        hechos_por_elemento={"ep-1": "he-recuerdo", "ep-2": "he-rasgo"},
    )

    assert [d.evidencia.count("ep-2") for d in defectos] == [0]


@pytest.mark.invariants
def test_un_elemento_sin_hecho_asociado_se_declara_y_no_se_da_por_bueno(
    conn: sqlite3.Connection,
) -> None:
    """Si nadie ato el elemento a un hecho, no hay nada que comprobar.

    Devolver «sin defectos» seria convertir la ausencia de evidencia en evidencia
    favorable, que es lo que el principio 8 de `architecture.md` 1 prohibe.
    """
    material_minimo(conn)

    defectos = elementos_obligatorios_presentes(
        MARTA, usos=UsoDeHechos(conn), hechos_por_elemento={}
    )

    assert [d.tipo for d in defectos] == ["elemento_personalizado_sin_hecho"]


# --- B-08: el registro de validadores -----------------------------------------------


@pytest.mark.invariants
def test_cada_validador_declara_nombre_y_punto_de_ejecucion() -> None:
    """RF-VAL-09. Un validador sin punto declarado no se sabe cuando corre.

    Es la columna que el alcance pide y la que decide si un fallo devuelve el capitulo al
    writer o impide publicar la version.
    """
    assert VALIDADORES, "el registro no puede estar vacio"

    for validador in VALIDADORES:
        assert validador.nombre
        assert isinstance(validador.punto, PuntoDeEjecucion)
        assert validador.requisito.startswith("RF-")
        assert validador.bloquea is True, "los deterministas bloquean; el juez no"


@pytest.mark.invariants
def test_los_nombres_de_los_validadores_no_se_repiten() -> None:
    """Dos validadores con el mismo nombre hacen ilegible el score en Langfuse."""
    nombres = [v.nombre for v in VALIDADORES]
    assert len(nombres) == len(set(nombres))
