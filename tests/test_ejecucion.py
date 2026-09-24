"""Idempotencia, reanudacion, cancelacion, transiciones, senales e integridad del prompt.

Son los requisitos que el plan pedia en D5, D6, E4 y E7 y que la primera pasada dejo a
medias. Cada uno se comprueba por lo que hace, no por lo que su docstring dice.

Cubre RF-ORQ-13, RF-ORQ-14, RF-ORQ-16, RF-ORQ-17, RF-ORQ-19, RF-WRK-07 y RNF-05.
"""

from __future__ import annotations

import sqlite3

import pytest

from backend.agents.redactor import redactor
from backend.orchestrator import senales
from backend.orchestrator.ejecucion import (
    ClaveDeTarea,
    artefacto_ya_producido,
    cancelar,
    reanudar_al_arrancar,
    registrar_artefacto,
    registrar_transicion,
    resultado_obsoleto,
)
from backend.orchestrator.plan import DAG, cadena_de_escena
from backend.store.repositories import CanonVersionado
from tests.conftest import material_minimo

CLAVE = ClaveDeTarea(
    plan_id="pl-1",
    objetivo="esc-1:redaccion",
    revision_de_canon=3,
    hash_del_paquete="abc123",
    version_de_prompt="1.0.0",
    intento=1,
)


def _plan_y_tarea(conn: sqlite3.Connection) -> None:
    material_minimo(conn)
    conn.execute("INSERT INTO plan (id, objetivo) VALUES ('pl-1', 'redactar esc-1')")
    for tarea in cadena_de_escena("esc-1", "pl-1"):
        conn.execute(
            "INSERT INTO tarea (id, plan_id, tipo, rol_asignado, estado, prioridad) "
            "VALUES (?, 'pl-1', ?, ?, 'pendiente', ?)",
            (tarea.id, tarea.tipo, tarea.rol_asignado, tarea.prioridad),
        )


# --- RF-ORQ-13: idempotencia ---------------------------------------------------------


@pytest.mark.invariants
def test_reejecutar_con_la_misma_clave_devuelve_el_artefacto(conn: sqlite3.Connection) -> None:
    """Sin esto, reanudar tras una caida vuelve a pagar todo lo ya pagado."""
    assert artefacto_ya_producido(conn, CLAVE) is None

    registrar_artefacto(conn, CLAVE, "bo-1")
    assert artefacto_ya_producido(conn, CLAVE) == "bo-1"


@pytest.mark.invariants
@pytest.mark.parametrize(
    "campo,valor",
    [
        ("revision_de_canon", 4),
        ("hash_del_paquete", "otro"),
        ("version_de_prompt", "1.1.0"),
        ("intento", 2),
    ],
)
def test_cambiar_cualquier_campo_de_la_clave_la_hace_otra(
    conn: sqlite3.Connection, campo: str, valor: object
) -> None:
    """Los seis campos importan: si faltara uno, dos ejecuciones distintas se confundirian."""
    import dataclasses

    registrar_artefacto(conn, CLAVE, "bo-1")
    otra = dataclasses.replace(CLAVE, **{campo: valor})
    assert artefacto_ya_producido(conn, otra) is None


# --- RF-ORQ-19: las transiciones emiten evento --------------------------------------


@pytest.mark.invariants
def test_una_transicion_emite_su_evento(conn: sqlite3.Connection) -> None:
    """Si nadie escribe aqui, el SSE existe y no emite nada."""
    _plan_y_tarea(conn)
    registrar_transicion(conn, "esc-1:redaccion", "lista")
    registrar_transicion(conn, "esc-1:redaccion", "en_curso")

    eventos = conn.execute(
        "SELECT estado FROM tarea_evento WHERE tarea_id = 'esc-1:redaccion' ORDER BY id"
    ).fetchall()
    estado = conn.execute("SELECT estado FROM tarea WHERE id = 'esc-1:redaccion'").fetchone()

    assert [e["estado"] for e in eventos] == ["lista", "en_curso"]
    assert estado["estado"] == "en_curso"


# --- RF-ORQ-14: reanudacion ----------------------------------------------------------


@pytest.mark.invariants
def test_una_tarea_en_curso_sin_procedencia_vuelve_a_lista(conn: sqlite3.Connection) -> None:
    """La invocacion no llego a registrarse: se reintenta y suma un intento."""
    _plan_y_tarea(conn)
    conn.execute("UPDATE tarea SET estado = 'en_curso' WHERE id = 'esc-1:redaccion'")

    resultado = reanudar_al_arrancar(conn)

    assert resultado.devueltas_a_lista == ("esc-1:redaccion",)
    assert resultado.pagadas_y_perdidas == ()
    intentos = conn.execute(
        "SELECT COUNT(*) AS n FROM tarea_intento WHERE tarea_id = 'esc-1:redaccion'"
    ).fetchone()["n"]
    assert intentos == 1


@pytest.mark.invariants
def test_una_tarea_con_procedencia_y_sin_artefacto_queda_anotada(
    conn: sqlite3.Connection,
) -> None:
    """La invocacion se pago y se perdio: es la metrica que revela caidas del worker."""
    _plan_y_tarea(conn)
    conn.execute("UPDATE tarea SET estado = 'en_curso' WHERE id = 'esc-1:redaccion'")
    conn.execute(
        "INSERT INTO paquete_contexto (id, tarea_id, revision_canon, hash) "
        "VALUES ('pq-1', 'esc-1:redaccion', 0, 'abc')"
    )
    conn.execute(
        "INSERT INTO procedencia (id, agente, modelo, version_de_prompt, paquete_id, "
        "timestamp) "
        "VALUES ('pr-1', 'redactor', 'claude-haiku-4-5', '1.0.0', 'pq-1', datetime('now'))"
    )

    resultado = reanudar_al_arrancar(conn)

    assert resultado.pagadas_y_perdidas == ("esc-1:redaccion",)
    assert resultado.devueltas_a_lista == ()


@pytest.mark.invariants
def test_reanudar_no_toca_lo_que_no_quedo_a_medias(conn: sqlite3.Connection) -> None:
    _plan_y_tarea(conn)
    assert reanudar_al_arrancar(conn) == reanudar_al_arrancar(conn)
    assert reanudar_al_arrancar(conn).devueltas_a_lista == ()


# --- RF-ORQ-17: descarte por revision superada ---------------------------------------


@pytest.mark.invariants
def test_un_resultado_contra_una_revision_superada_se_descarta(
    conn: sqlite3.Connection,
) -> None:
    """Aceptarlo «porque esta bien escrito» es exactamente como entra la deriva."""
    material_minimo(conn)
    canon = CanonVersionado(conn)
    assert resultado_obsoleto(conn, "esc-1:redaccion", revision_del_paquete=0) is False

    canon.abrir_revision("otra escena canonizo mientras esta corria")
    assert resultado_obsoleto(conn, "esc-1:redaccion", revision_del_paquete=0) is True


# --- RF-ORQ-16: cancelar marca obsoleto, nunca borra ---------------------------------


@pytest.mark.invariants
def test_cancelar_alcanza_el_subarbol_y_no_borra_nada(conn: sqlite3.Connection) -> None:
    """Borrar destruiria la unica evidencia de por que se llego hasta ahi."""
    _plan_y_tarea(conn)
    conn.execute(
        "INSERT INTO borrador (id, escena_id, version, texto, estado) "
        "VALUES ('bo-1', 'esc-1', 1, 'prosa', 'propuesto')"
    )
    dag = DAG({t.id: t for t in cadena_de_escena("esc-1", "pl-1")})

    afectadas = cancelar(conn, "esc-1:redaccion", dag.subarbol_de("esc-1:redaccion"))

    assert len(afectadas) == 3
    borrador = conn.execute("SELECT obsoleto FROM borrador WHERE id = 'bo-1'").fetchone()
    assert borrador is not None, "el borrador se borro y deberia haberse marcado"
    assert borrador["obsoleto"] == 1
    canceladas = conn.execute(
        "SELECT COUNT(*) AS n FROM tarea WHERE estado = 'cancelada'"
    ).fetchone()["n"]
    assert canceladas == 3


# --- RNF-05: las senales -------------------------------------------------------------


@pytest.mark.invariants
def test_las_cinco_senales_se_leen_de_lo_ya_registrado(conn: sqlite3.Connection) -> None:
    """Se calculan de lo que el sistema escribe, no de un contador paralelo."""
    _plan_y_tarea(conn)
    conn.execute(
        "INSERT INTO tarea_intento (tarea_id, numero, clase_de_fallo, tipo_de_defecto, "
        "timestamp) "
        "VALUES ('esc-1:redaccion', 1, 'contenido', 'contradiccion', datetime('now'))"
    )
    conn.execute(
        "INSERT INTO paquete_contexto (id, tarea_id, revision_canon, hash, "
        "tokens_por_componente) "
        "VALUES ('pq-1', 'esc-1:redaccion', 0, 'abc', 'ESTATICO=2000;ARCO=4000')"
    )
    conn.execute("UPDATE tarea SET estado = 'lista', reserva = 28000")

    leidas = senales.leer(conn, descartados=1, admitidos=3)

    assert leidas.reintentos_por_tipo_de_defecto == {"contradiccion": 1}
    assert leidas.tokens_por_componente == {"ESTATICO": 2000, "ARCO": 4000}
    assert leidas.tiempo_en_cola_por_prioridad != {}
    assert leidas.deriva_entre_reserva_y_uso_real != {}
    assert leidas.proporcion_de_defectos_descartados == 0.25


@pytest.mark.invariants
def test_las_senales_tienen_resumen_legible(conn: sqlite3.Connection) -> None:
    """Una senal registrada y no observada es una senal que no existe."""
    resumen = senales.leer(conn).resumen()
    assert resumen.count("\n") == 4


# --- RF-WRK-07: prompt editado sin subir la version ----------------------------------


@pytest.mark.invariants
def test_el_prompt_vigente_coincide_con_su_manifiesto() -> None:
    redactor.verificar_integridad_del_prompt()


@pytest.mark.invariants
def test_un_prompt_editado_sin_subir_version_se_detecta(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """El hash cambia y la version no: es justo lo que rompe la reproducibilidad."""
    monkeypatch.setitem(redactor.MANIFIESTO, "1.0.0", "0" * 64)
    with pytest.raises(redactor.PromptAlterado) as error:
        redactor.verificar_integridad_del_prompt()
    assert "sin que suba la version" in str(error.value)


@pytest.mark.invariants
def test_una_version_sin_registrar_en_el_manifiesto_tambien_falla() -> None:
    with pytest.raises(redactor.PromptAlterado):
        redactor.verificar_integridad_del_prompt("9.9.9")


# --- criterio 8: los RegistroDeDecision existen --------------------------------------


@pytest.mark.invariants
def test_las_decisiones_de_la_spec_estan_registradas(conn: sqlite3.Connection) -> None:
    """Sin alternativa descartada, la decision se vuelve a discutir dentro de un mes."""
    filas = conn.execute(
        "SELECT id, alternativas, motivo FROM registro_decision ORDER BY id"
    ).fetchall()

    assert len(filas) == 13
    identificadores = {f["id"] for f in filas}
    # SPEC-003 A-03 anade dos: la ontologia del destinatario y la cronologia como vista.
    assert {"rd-d18", "rd-d19"} <= identificadores
    # SPEC-004 6.3 anade otras dos: el modo de escritura y la previa del borrador.
    assert {"rd-d20", "rd-d21"} <= identificadores
    assert "rd-predicados" in identificadores
    # D-17 no borra a R-1: la sustituye y la cita como alternativa descartada. Una
    # decision que desaparece del registro deja de poder contradecirse a la vista.
    assert {"rd-r1", "rd-d17"} <= identificadores
    for fila in filas:
        assert fila["alternativas"].strip()
        assert fila["motivo"].strip()
