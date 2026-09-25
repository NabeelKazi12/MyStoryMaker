"""Versiones de la novela y regeneracion selectiva por hecho cambiado.

SPEC-003, fase E, pasos E-06 y E-07. Cubre RF-LEC-05, RF-LEC-06 y RF-LEC-07.

La propiedad que sostiene los tres: cambiar un hecho toca **solo** los capitulos que lo
usan, y la version anterior sigue ahi. Regenerar de mas cuesta invocaciones; regenerar de
menos deja la novela incoherente; sobrescribir la anterior pierde lo unico que permite
comparar.
"""

from __future__ import annotations

import sqlite3

import pytest

from backend.orchestrator.regeneracion import (
    CambioDelLector,
    capitulos_afectados,
    publicar_version,
)
from backend.store.repositories import UsoDeHechos, VersionesDeNovela
from tests.conftest import material_minimo


def _dos_capitulos(conn: sqlite3.Connection) -> None:
    material_minimo(conn)
    conn.execute(
        "INSERT OR IGNORE INTO capitulo (id, volumen_id, orden) VALUES ('cap-2', 'vol-1', 2)"
    )
    usos = UsoDeHechos(conn)
    usos.registrar("he-perro", "cap-1")
    usos.registrar("he-perro", "cap-2")
    usos.registrar("he-casa", "cap-1")
    conn.commit()


@pytest.mark.invariants
def test_cambiar_un_hecho_regenera_solo_los_capitulos_que_lo_usan(
    conn: sqlite3.Connection,
) -> None:
    """RF-LEC-05. «El perro se llama Nala» no obliga a reescribir la novela entera."""
    _dos_capitulos(conn)

    afectados = capitulos_afectados(
        CambioDelLector(hecho_id="he-perro", descripcion="el perro se llama Nala"),
        usos=UsoDeHechos(conn),
    )

    assert afectados == ("cap-1", "cap-2")


@pytest.mark.invariants
def test_un_hecho_que_solo_usa_un_capitulo_no_arrastra_a_los_demas(
    conn: sqlite3.Connection,
) -> None:
    _dos_capitulos(conn)

    afectados = capitulos_afectados(
        CambioDelLector(hecho_id="he-casa", descripcion="la casa era azul"),
        usos=UsoDeHechos(conn),
    )

    assert afectados == ("cap-1",)


@pytest.mark.invariants
def test_un_hecho_que_no_usa_nadie_no_regenera_nada_y_se_dice(
    conn: sqlite3.Connection,
) -> None:
    """Devolver «toda la novela» ante un hecho sin uso seria el peor de los dos errores."""
    _dos_capitulos(conn)

    afectados = capitulos_afectados(
        CambioDelLector(hecho_id="he-inexistente", descripcion="nada"),
        usos=UsoDeHechos(conn),
    )

    assert afectados == ()


@pytest.mark.invariants
def test_un_cambio_sobre_un_personaje_toca_los_capitulos_de_sus_hechos(
    conn: sqlite3.Connection,
) -> None:
    """La ficha ancla el cambio a un personaje, no a un hecho.

    Tratar el id del personaje como id de hecho no encuentra nada en `hecho_capitulo` y
    responde «no se regenera nada» a cualquier cambio de nombre. Los capitulos salen de
    los hechos cuyo sujeto es el personaje, que siguen siendo usos declarados.
    """
    _dos_capitulos(conn)
    conn.executemany(
        "INSERT INTO hecho (id, sujeto_id, predicado, objeto, valido_desde) "
        "VALUES (?, 'per-1', ?, ?, 'ev-1')",
        [("he-irene-perro", "posee", "un perro"), ("he-irene-casa", "ubicacion", "el puerto")],
    )
    usos = UsoDeHechos(conn)
    usos.registrar("he-irene-perro", "cap-2")
    usos.registrar("he-irene-casa", "cap-1")
    usos.registrar("he-irene-casa", "cap-2")

    afectados = capitulos_afectados(
        CambioDelLector(entidad_id="per-1", descripcion="se llama Lucia"),
        usos=usos,
    )

    assert afectados == ("cap-1", "cap-2")


@pytest.mark.invariants
def test_un_personaje_sin_hechos_usados_no_regenera_nada(
    conn: sqlite3.Connection,
) -> None:
    _dos_capitulos(conn)

    afectados = capitulos_afectados(
        CambioDelLector(entidad_id="pe-nadie", descripcion="nada"),
        usos=UsoDeHechos(conn),
    )

    assert afectados == ()


@pytest.mark.invariants
def test_la_primera_version_no_tiene_anterior_y_las_demas_si(
    conn: sqlite3.Connection,
) -> None:
    """RF-LEC-07: las versiones se encadenan, no se sobrescriben."""
    _dos_capitulos(conn)
    versiones = VersionesDeNovela(conn)

    primera = publicar_version(
        conn, volumen_id="vol-1", capitulos=("cap-1", "cap-2"), cambiados=(), motivo="inicial"
    )
    segunda = publicar_version(
        conn,
        volumen_id="vol-1",
        capitulos=("cap-1", "cap-2"),
        cambiados=("cap-2",),
        motivo="el perro se llama Nala",
    )

    assert versiones.numero_de(primera) == 1
    assert versiones.numero_de(segunda) == 2
    assert versiones.anterior_de(segunda) == primera
    assert versiones.anterior_de(primera) is None


@pytest.mark.invariants
def test_la_version_anterior_sigue_legible_tras_regenerar(conn: sqlite3.Connection) -> None:
    """Es el invariante que TLA+ verifica como VersionAnteriorSeConserva."""
    _dos_capitulos(conn)
    primera = publicar_version(
        conn, volumen_id="vol-1", capitulos=("cap-1", "cap-2"), cambiados=(), motivo="inicial"
    )
    publicar_version(
        conn, volumen_id="vol-1", capitulos=("cap-1", "cap-2"), cambiados=("cap-2",), motivo="x"
    )

    versiones = VersionesDeNovela(conn)

    assert versiones.capitulos_de(primera) == ("cap-1", "cap-2")
    assert len(versiones.historial("vol-1")) == 2


@pytest.mark.invariants
def test_la_version_marca_que_capitulos_cambiaron(conn: sqlite3.Connection) -> None:
    """RF-LEC-06. Sin la marca, el lector tiene que releer la novela para saber que cambio."""
    _dos_capitulos(conn)
    publicar_version(
        conn, volumen_id="vol-1", capitulos=("cap-1", "cap-2"), cambiados=(), motivo="inicial"
    )
    segunda = publicar_version(
        conn, volumen_id="vol-1", capitulos=("cap-1", "cap-2"), cambiados=("cap-2",), motivo="x"
    )

    assert VersionesDeNovela(conn).capitulos_cambiados(segunda) == ("cap-2",)
