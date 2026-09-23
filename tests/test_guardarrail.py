"""El guardarrail de palabras prohibidas: normalizacion, tres niveles, limite y audit log.

SPEC-003, fase B. Cubre RF-GRD-01 a RF-GRD-06 y RF-VAL-05.

Los tests de este fichero comprueban **el frontend del guardarrail**: que detecta lo que
tiene que detectar y que no detecta lo que no. Que un termino concreto deba estar vetado
es decision del cliente o de la politica global, y eso no se comprueba aqui.
"""

from __future__ import annotations

import sqlite3

import pytest

from backend.quality.guardarrail import (
    LIMITE_DE_REESCRITURAS,
    Coincidencia,
    Guardarrail,
    LimiteDeReescriturasAgotado,
    Veredicto,
    normalizar,
)
from backend.store.repositories import AuditLog, ListasProhibidas
from tests.conftest import material_minimo

# --- B-01: normalizacion -------------------------------------------------------------


@pytest.mark.invariants
@pytest.mark.parametrize(
    ("entrada", "esperado"),
    [
        ("Ricardo", "ricardo"),
        ("RICARDO", "ricardo"),
        ("Ricárdo", "ricardo"),
        ("  ricardo  ", "ricardo"),
        ("Ri-cardo", "ricardo"),
        ("Ri_car do", "ricardo"),
    ],
)
def test_normaliza_mayusculas_acentos_y_separadores(entrada: str, esperado: str) -> None:
    """Sin normalizar, esquivar el guardarrail cuesta una tilde (RF-GRD-02)."""
    assert normalizar(entrada) == esperado


@pytest.mark.invariants
def test_la_normalizacion_no_junta_palabras_distintas() -> None:
    """Un normalizador demasiado agresivo bloquea capitulos correctos.

    `casa` y `caza` suenan igual y no son lo mismo: si la normalizacion las igualara, un
    veto sobre una vetaria la otra y el guardarrail se volveria imposible de razonar.
    """
    assert normalizar("casa") != normalizar("caza")
    assert normalizar("pero") != normalizar("perro")


# --- B-02: los tres niveles ----------------------------------------------------------


def _listas(conn: sqlite3.Connection) -> ListasProhibidas:
    listas = ListasProhibidas(conn)
    listas.anadir("lp-1", nivel="global", termino="imbecil")
    listas.anadir("lp-2", nivel="novela", termino="Ricardo", ambito_id="br-1")
    listas.anadir("lp-3", nivel="cliente", termino="divorcio", ambito_id="de-1")
    return listas


@pytest.mark.invariants
@pytest.mark.parametrize(
    ("texto", "termino_esperado", "nivel_esperado"),
    [
        ("Le llamo imbecil y se fue.", "imbecil", "global"),
        ("Ricardo abrio la puerta.", "ricardo", "novela"),
        ("Hablaron del divorcio.", "divorcio", "cliente"),
    ],
)
def test_el_guardarrail_detecta_un_caso_de_cada_nivel(
    conn: sqlite3.Connection, texto: str, termino_esperado: str, nivel_esperado: str
) -> None:
    """RF-GRD-01. Un nivel que no se comprueba es un nivel que no existe."""
    _listas(conn)
    veredicto = Guardarrail(conn).revisar(texto, brief_id="br-1", destinatario_id="de-1")

    assert veredicto.limpio is False
    assert [c.termino for c in veredicto.coincidencias] == [termino_esperado]
    assert [c.nivel for c in veredicto.coincidencias] == [nivel_esperado]


@pytest.mark.invariants
@pytest.mark.parametrize("texto", ["Ricárdo abrio la puerta.", "Los Ricardos de la familia."])
def test_detecta_la_variante_con_acento_y_la_plural(
    conn: sqlite3.Connection, texto: str
) -> None:
    """RF-GRD-02. Es lo que separa un guardarrail de una busqueda de texto."""
    _listas(conn)
    veredicto = Guardarrail(conn).revisar(texto, brief_id="br-1", destinatario_id="de-1")

    assert veredicto.limpio is False
    assert veredicto.coincidencias[0].termino == "ricardo"


@pytest.mark.invariants
def test_un_termino_de_otra_novela_no_bloquea_esta(conn: sqlite3.Connection) -> None:
    """Sin ambito, una palabra vetada por un cliente vetaria las novelas de todos."""
    _listas(conn)
    veredicto = Guardarrail(conn).revisar(
        "Ricardo abrio la puerta.", brief_id="br-otra", destinatario_id="de-otro"
    )

    assert veredicto.limpio is True


@pytest.mark.invariants
def test_un_texto_limpio_pasa_sin_coincidencias(conn: sqlite3.Connection) -> None:
    """El guardarrail que bloquea todo es tan inutil como el que no bloquea nada."""
    _listas(conn)
    veredicto = Guardarrail(conn).revisar(
        "La tarde caia sobre el puerto.", brief_id="br-1", destinatario_id="de-1"
    )

    assert veredicto == Veredicto(limpio=True, coincidencias=())


# --- B-03: el limite de reescrituras -------------------------------------------------


@pytest.mark.invariants
def test_una_coincidencia_devuelve_el_capitulo_al_writer(conn: sqlite3.Connection) -> None:
    """RF-GRD-04: reescribir, no censurar. El guardarrail no edita el texto."""
    _listas(conn)
    guardarrail = Guardarrail(conn)

    veredicto = guardarrail.revisar(
        "Ricardo abrio la puerta.", brief_id="br-1", destinatario_id="de-1"
    )

    assert veredicto.reescribir is True
    assert not hasattr(veredicto, "texto_corregido")


@pytest.mark.invariants
def test_agotado_el_limite_la_generacion_se_detiene_e_informa(
    conn: sqlite3.Connection,
) -> None:
    """RF-GRD-04. Sin limite, un writer que insiste deja el sistema girando y pagando.

    La parada nombra el termino y el numero de intentos: «no se pudo generar» obliga a
    reproducir la ejecucion entera para saber que paso.
    """
    _listas(conn)
    guardarrail = Guardarrail(conn)

    for intento in range(1, LIMITE_DE_REESCRITURAS + 1):
        veredicto = guardarrail.revisar(
            "Ricardo abrio la puerta.",
            brief_id="br-1",
            destinatario_id="de-1",
            intento=intento,
        )
        assert veredicto.reescribir is True

    with pytest.raises(LimiteDeReescriturasAgotado) as error:
        guardarrail.revisar(
            "Ricardo abrio la puerta.",
            brief_id="br-1",
            destinatario_id="de-1",
            intento=LIMITE_DE_REESCRITURAS + 1,
        )

    assert "ricardo" in str(error.value)
    assert str(LIMITE_DE_REESCRITURAS) in str(error.value)


# --- B-04: el audit log --------------------------------------------------------------


@pytest.mark.invariants
def test_cada_coincidencia_deja_fila_en_el_audit_log(conn: sqlite3.Connection) -> None:
    """RF-GRD-05 y RF-GRD-06. Una decision de politica sin rastro no es auditable."""
    # El capitulo tiene que existir: la clave foranea del audit log impide registrar una
    # decision sobre un capitulo inventado, que seria un rastro que no lleva a ninguna
    # parte.
    material_minimo(conn)
    _listas(conn)
    Guardarrail(conn).revisar(
        "Ricardo llamo imbecil a su hermano.",
        brief_id="br-1",
        destinatario_id="de-1",
        capitulo_id="cap-1",
    )

    entradas = AuditLog(conn).entradas()

    assert [e.termino for e in entradas] == ["imbecil", "ricardo"]
    assert {e.decision for e in entradas} == {"devolver_al_writer"}
    assert all(e.capitulo_id == "cap-1" for e in entradas)
    assert all(e.motivo for e in entradas), "una entrada sin motivo no explica nada"


@pytest.mark.invariants
def test_un_texto_limpio_no_ensucia_el_audit_log(conn: sqlite3.Connection) -> None:
    """Un log que registra tambien lo que no paso deja de poder leerse."""
    _listas(conn)
    Guardarrail(conn).revisar("La tarde caia.", brief_id="br-1", destinatario_id="de-1")

    assert AuditLog(conn).entradas() == ()


@pytest.mark.invariants
def test_la_coincidencia_cita_el_fragmento_donde_aparece(conn: sqlite3.Connection) -> None:
    """Sin el fragmento, quien reescribe tiene que buscar la palabra a ojo."""
    _listas(conn)
    veredicto = Guardarrail(conn).revisar(
        "La tarde caia. Ricardo abrio la puerta. Nadie dijo nada.",
        brief_id="br-1",
        destinatario_id="de-1",
    )

    (coincidencia,) = veredicto.coincidencias
    assert isinstance(coincidencia, Coincidencia)
    assert "Ricardo" in coincidencia.fragmento
