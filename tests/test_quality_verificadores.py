"""Los verificadores detectan lo que deben y no inventan lo que no hay.

Cada dimension se prueba con el par del corpus: el caso con el defecto conocido y el
mismo caso intacto. Es el reparto de `verification.md` 7, filas «que los verificadores
detectan» y «que no inventan defectos».

Cubre RF-QUA-01 a RF-QUA-09, RF-QUA-16, RF-QUA-17, RF-QUA-21, RF-QUA-22, RF-QUA-10 y
RF-QUA-19.
"""

from __future__ import annotations

import sqlite3
from dataclasses import replace

import pytest

from backend.domain.production.ejecucion import Defecto
from backend.domain.vocabularies import Severidad
from backend.quality import verificadores as v
from backend.quality.defectos import ColaDeDefectos
from backend.store.repositories import CatalogoDePredicados, ConsultasDeCalidad, GrafoCausal
from tests import corpus
from tests.conftest import material_minimo

# --- RF-QUA-01: contradiccion de hechos ----------------------------------------------


@pytest.mark.invariants
def test_detecta_contradiccion_de_hechos(conn: sqlite3.Connection) -> None:
    defectos = v.contradiccion_de_hechos(
        corpus.CONTRADICCION.con_defecto, CatalogoDePredicados(conn), corpus.ORDEN_DE_EVENTO
    )
    assert len(defectos) == 1
    assert defectos[0].severidad is Severidad.CRITICA
    assert defectos[0].extraccion_evaluada == "hechos_nuevos_detectados"


@pytest.mark.invariants
def test_no_inventa_contradiccion_cuando_los_intervalos_no_solapan(
    conn: sqlite3.Connection,
) -> None:
    assert (
        v.contradiccion_de_hechos(
            corpus.CONTRADICCION.intacto, CatalogoDePredicados(conn), corpus.ORDEN_DE_EVENTO
        )
        == []
    )


@pytest.mark.invariants
def test_un_predicado_multivalor_no_se_contradice(conn: sqlite3.Connection) -> None:
    """Un personaje esta en un sitio, pero posee varios objetos a la vez.

    Es lo que aporta el catalogo: sin la distincion, este caso seria un falso positivo.
    """
    from backend.domain.diegetic.canon import Hecho

    hechos = [
        Hecho(
            id="h-1",
            sujeto_id="per-1",
            predicado="posee",
            objeto="la carta",
            valido_desde="ev-1",
        ),
        Hecho(
            id="h-2",
            sujeto_id="per-1",
            predicado="posee",
            objeto="un cuchillo",
            valido_desde="ev-2",
        ),
    ]
    assert (
        v.contradiccion_de_hechos(hechos, CatalogoDePredicados(conn), corpus.ORDEN_DE_EVENTO)
        == []
    )


# --- RF-QUA-02 y RF-QUA-03: grafo causal ---------------------------------------------


@pytest.mark.invariants
def test_detecta_ciclo_causal(conn: sqlite3.Connection) -> None:
    _eventos(conn, {"ev-1": 10, "ev-2": 20, "ev-3": 30})
    _causa(conn, ("ev-1", "ev-2"), ("ev-2", "ev-3"), ("ev-3", "ev-1"))
    assert len(v.ciclos_causales(GrafoCausal(conn))) == 3


@pytest.mark.invariants
def test_no_inventa_ciclos_en_un_dag(conn: sqlite3.Connection) -> None:
    _eventos(conn, {"ev-1": 10, "ev-2": 20, "ev-3": 30})
    _causa(conn, ("ev-1", "ev-2"), ("ev-2", "ev-3"))
    assert v.ciclos_causales(GrafoCausal(conn)) == []


@pytest.mark.invariants
def test_detecta_causa_que_no_precede(conn: sqlite3.Connection) -> None:
    _eventos(conn, {"ev-1": 50, "ev-2": 20})
    _causa(conn, ("ev-1", "ev-2"))
    defectos = v.precedencia_causal(GrafoCausal(conn))
    assert len(defectos) == 1 and defectos[0].severidad is Severidad.CRITICA


@pytest.mark.invariants
def test_no_inventa_precedencias(conn: sqlite3.Connection) -> None:
    _eventos(conn, {"ev-1": 10, "ev-2": 20})
    _causa(conn, ("ev-1", "ev-2"))
    assert v.precedencia_causal(GrafoCausal(conn)) == []


# --- RF-QUA-04: escena con cambio de valor y con evento ------------------------------


@pytest.mark.invariants
def test_detecta_evento_prometido_y_no_narrado() -> None:
    defectos = v.escena_con_cambio_y_evento(corpus.ESCENA, corpus.ESCENA_SIN_EVENTO.con_defecto)
    assert len(defectos) == 1
    assert defectos[0].extraccion_evaluada == "eventos_narrados"


@pytest.mark.invariants
def test_no_inventa_cuando_lo_narrado_coincide() -> None:
    assert v.escena_con_cambio_y_evento(corpus.ESCENA, corpus.ESCENA_SIN_EVENTO.intacto) == []


# --- RF-QUA-05: borrador unico aceptado ----------------------------------------------


@pytest.mark.invariants
def test_no_inventa_borradores_duplicados(conn: sqlite3.Connection) -> None:
    material_minimo(conn)
    conn.execute(
        "INSERT INTO borrador (id, escena_id, version, texto, estado) "
        "VALUES ('bo-1', 'esc-1', 1, 'prosa', 'aceptado')"
    )
    assert (
        v.borrador_unico_aceptado(ConsultasDeCalidad(conn).borradores_aceptados_duplicados())
        == []
    )


# --- RF-QUA-08: deriva de nombres ----------------------------------------------------


@pytest.mark.invariants
def test_detecta_nombre_no_declarado() -> None:
    defectos = v.deriva_de_nombres(corpus.DERIVA_DE_NOMBRES.con_defecto, {"Irene"})
    assert [d.evidencia.split("«")[1].split("»")[0] for d in defectos] == ["Tobias"]


@pytest.mark.invariants
def test_no_inventa_nombres_cuando_todos_estan_declarados() -> None:
    assert v.deriva_de_nombres(corpus.DERIVA_DE_NOMBRES.intacto, {"Irene"}) == []


# --- RF-QUA-09: repeticion de n-gramas -----------------------------------------------


@pytest.mark.invariants
def test_detecta_tetragrama_repetido() -> None:
    defectos = v.repeticion_de_ngramas(
        corpus.REPETICION.con_defecto, [corpus.CAPITULO_ANTERIOR]
    )
    assert defectos and all(d.severidad is Severidad.MEDIA for d in defectos)


@pytest.mark.invariants
def test_no_inventa_repeticion_en_texto_nuevo() -> None:
    assert v.repeticion_de_ngramas(corpus.REPETICION.intacto, [corpus.CAPITULO_ANTERIOR]) == []


# --- RF-QUA-16 y RF-QUA-17: alcance de contrato --------------------------------------


@pytest.mark.invariants
def test_detecta_hilo_sin_pregunta_dramatica() -> None:
    assert len(v.hilos_con_pregunta_dramatica([corpus.HILO_SIN_PREGUNTA.con_defecto])) == 1


@pytest.mark.invariants
def test_no_inventa_hilos_sin_pregunta() -> None:
    assert v.hilos_con_pregunta_dramatica([corpus.HILO_SIN_PREGUNTA.intacto]) == []


@pytest.mark.invariants
def test_detecta_protagonico_sin_hilo() -> None:
    defectos = v.protagonicos_con_hilo_y_necesidad(
        [corpus.PROTAGONICA], corpus.PROTAGONICO_SIN_HILO.con_defecto
    )
    assert len(defectos) == 1 and defectos[0].severidad is Severidad.CRITICA


@pytest.mark.invariants
def test_no_inventa_protagonicos_sin_hilo() -> None:
    assert (
        v.protagonicos_con_hilo_y_necesidad(
            [corpus.PROTAGONICA], corpus.PROTAGONICO_SIN_HILO.intacto
        )
        == []
    )


# --- RF-QUA-21: diversidad lexica y vocabulario prohibido ----------------------------


@pytest.mark.invariants
def test_detecta_vocabulario_prohibido() -> None:
    defectos = v.diversidad_lexica(corpus.VOCABULARIO_PROHIBIDO.con_defecto, corpus.PERFIL)
    assert [d.tipo for d in defectos] == ["vocabulario_prohibido"]


@pytest.mark.invariants
def test_no_inventa_vocabulario_prohibido() -> None:
    defectos = v.diversidad_lexica(corpus.VOCABULARIO_PROHIBIDO.intacto, corpus.PERFIL)
    assert [d for d in defectos if d.tipo == "vocabulario_prohibido"] == []


# --- RF-QUA-22: hilos inactivos ------------------------------------------------------


@pytest.mark.invariants
def test_detecta_hilo_principal_inactivo() -> None:
    escenas = [f"esc-{i}" for i in range(1, 7)]
    defectos = v.hilos_inactivos(
        [corpus.HILO_PRINCIPAL], escenas, corpus.HILO_INACTIVO.con_defecto
    )
    assert len(defectos) == 1 and "5 escenas" in defectos[0].evidencia


@pytest.mark.invariants
def test_no_inventa_inactividad_cuando_el_hilo_avanza() -> None:
    escenas = [f"esc-{i}" for i in range(1, 7)]
    assert (
        v.hilos_inactivos([corpus.HILO_PRINCIPAL], escenas, corpus.HILO_INACTIVO.intacto) == []
    )


# --- RF-QUA-10 y RF-QUA-19: la forma del defecto -------------------------------------


@pytest.mark.invariants
def test_un_defecto_sin_evidencia_se_descarta_y_se_cuenta() -> None:
    cola = ColaDeDefectos()
    admitido = cola.ofrecer(
        Defecto(
            id="d-1",
            tipo="ciclo_causal",
            severidad=Severidad.CRITICA,
            regla_violada="el grafo es aciclico",
            evidencia="   ",
        )
    )
    assert admitido is False
    assert cola.descartados_por_tipo == {"ciclo_causal": 1}
    assert cola.proporcion_descartada == 1.0


@pytest.mark.invariants
def test_un_defecto_de_dimension_E_sin_bloque_declarado_se_descarta() -> None:
    """Sin decir contra que declaracion se evaluo, F-01 no es depurable."""
    base = Defecto(
        id="d-1",
        tipo="contradiccion_de_hechos",
        severidad=Severidad.CRITICA,
        regla_violada="intervalos solapados",
        evidencia="h-1 y h-2 solapan",
    )
    cola = ColaDeDefectos()
    assert cola.ofrecer(base) is False
    assert cola.ofrecer(replace(base, extraccion_evaluada="hechos_nuevos_detectados")) is True


@pytest.mark.invariants
def test_los_verificadores_producen_defectos_admisibles(conn: sqlite3.Connection) -> None:
    """Todo lo que emiten los verificadores pasa la cola: si no, nunca llegaria a una puerta."""
    cola = ColaDeDefectos()
    emitidos = v.contradiccion_de_hechos(
        corpus.CONTRADICCION.con_defecto, CatalogoDePredicados(conn), corpus.ORDEN_DE_EVENTO
    ) + v.deriva_de_nombres(corpus.DERIVA_DE_NOMBRES.con_defecto, {"Irene"})

    assert emitidos
    assert all(cola.ofrecer(d) for d in emitidos)
    assert cola.total_descartados == 0


# --- utilidades ----------------------------------------------------------------------


def _eventos(conn: sqlite3.Connection, posiciones: dict[str, int]) -> None:
    for identificador, posicion in posiciones.items():
        conn.execute(
            "INSERT INTO evento (id, descripcion, posicion_en_historia, tipo) "
            "VALUES (?, ?, ?, 'accion')",
            (identificador, f"evento {identificador}", posicion),
        )


def _causa(conn: sqlite3.Connection, *pares: tuple[str, str]) -> None:
    conn.executemany("INSERT INTO evento_causa (causa_id, efecto_id) VALUES (?, ?)", pares)
