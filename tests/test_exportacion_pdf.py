"""Exportacion de la novela a PDF, con indice, ficha, portada y novedades.

SPEC-003, fase E, paso E-08. Cubre RF-LEC-08, y RF-PDF-01 a RF-PDF-03 de SPEC-006.

Lo que se comprueba es que el PDF **contiene** lo que el alcance exige y que los enlaces
internos existen. Que se lea bien es inspeccion humana: un PDF valido puede ser ilegible.
"""

from __future__ import annotations

import dataclasses
from pathlib import Path

import pytest

from backend.export.pdf import CapituloParaPDF, NovelaParaPDF, exportar_pdf

NOVELA = NovelaParaPDF(
    titulo="El verano en que aprendiste a nadar",
    dedicatoria="Para Marta, que siempre vuelve al mar.",
    destinatario="Marta",
    personajes=(("Marta", "cap-1"), ("Clara", "cap-2")),
    lugares=(("Gijon", "cap-1"),),
    capitulos=(
        CapituloParaPDF(id="cap-1", orden=1, titulo="La casa", texto="La tarde caia."),
        CapituloParaPDF(
            id="cap-2",
            orden=2,
            titulo="El agua",
            texto="El agua estaba fria.",
            cambiado=True,
        ),
    ),
    version=2,
)


@pytest.mark.invariants
def test_el_pdf_trae_indice_ficha_portada_y_novedades_con_enlaces(tmp_path: Path) -> None:
    """RF-LEC-08. Las cuatro piezas del alcance, en un fichero que abre."""
    destino = tmp_path / "novela.pdf"

    resultado = exportar_pdf(NOVELA, destino)

    assert destino.exists() and destino.stat().st_size > 1_000
    assert destino.read_bytes().startswith(b"%PDF-")
    assert resultado.secciones == (
        "portada",
        "dedicatoria",
        "novedades",
        "indice",
        "ficha",
        "capitulos",
    )
    # Los destinos internos de los enlaces: uno por capitulo, mas la ficha.
    assert set(resultado.anclas) >= {"cap-1", "cap-2", "ficha"}


@pytest.mark.invariants
def test_la_primera_version_no_lleva_pagina_de_novedades(tmp_path: Path) -> None:
    """Novedades respecto a que. Una pagina de novedades en la version 1 es ruido."""
    primera = NovelaParaPDF(
        titulo=NOVELA.titulo,
        dedicatoria=NOVELA.dedicatoria,
        destinatario=NOVELA.destinatario,
        personajes=NOVELA.personajes,
        lugares=NOVELA.lugares,
        capitulos=tuple(
            CapituloParaPDF(id=c.id, orden=c.orden, titulo=c.titulo, texto=c.texto)
            for c in NOVELA.capitulos
        ),
        version=1,
    )

    resultado = exportar_pdf(primera, tmp_path / "v1.pdf")

    assert "novedades" not in resultado.secciones


@pytest.mark.invariants
def test_una_novela_sin_capitulos_no_produce_pdf(tmp_path: Path) -> None:
    """Un PDF de cero capitulos es un fichero que parece una novela y no lo es."""
    vacia = NovelaParaPDF(
        titulo="x",
        dedicatoria="",
        destinatario="Marta",
        personajes=(),
        lugares=(),
        capitulos=(),
        version=1,
    )

    with pytest.raises(ValueError) as error:
        exportar_pdf(vacia, tmp_path / "vacia.pdf")

    assert "capitulo" in str(error.value)


@pytest.mark.invariants
def test_la_portada_lleva_titulo_y_destinatario_y_no_la_dedicatoria(tmp_path: Path) -> None:
    """RF-PDF-01. La portada es la portada; la dedicatoria tiene su propia pagina."""
    resultado = exportar_pdf(NOVELA, tmp_path / "novela.pdf")

    assert NOVELA.titulo in resultado.texto_de_portada
    assert "Para Marta" in resultado.texto_de_portada
    assert NOVELA.dedicatoria not in resultado.texto_de_portada


@pytest.mark.invariants
def test_la_dedicatoria_va_sola_en_la_segunda_pagina(tmp_path: Path) -> None:
    """RF-PDF-02: es lo que convierte el PDF en un regalo y no en una descarga."""
    resultado = exportar_pdf(NOVELA, tmp_path / "novela.pdf")

    assert resultado.pagina_de_dedicatoria == 2
    assert resultado.texto_de_dedicatoria == NOVELA.dedicatoria


@pytest.mark.invariants
def test_sin_dedicatoria_no_hay_pagina_de_dedicatoria(tmp_path: Path) -> None:
    """RF-PDF-02 y RF-PDF-03: sin ella, el indice sigue a la portada."""
    sin = dataclasses.replace(NOVELA, dedicatoria="  ", version=1)

    resultado = exportar_pdf(sin, tmp_path / "sin.pdf")

    assert resultado.secciones == ("portada", "indice", "ficha", "capitulos")
    assert resultado.pagina_de_dedicatoria is None


@pytest.mark.invariants
def test_la_portada_no_repite_el_destinatario_si_el_titulo_ya_lo_nombra(
    tmp_path: Path,
) -> None:
    """Como DV-4 de SPEC-005: «Para Marta» bajo «Para Marta» es eco."""
    resultado = exportar_pdf(
        dataclasses.replace(NOVELA, titulo="Para Marta"), tmp_path / "eco.pdf"
    )
    assert resultado.texto_de_portada.count("Para Marta") == 1


@pytest.mark.invariants
def test_un_titulo_con_marcado_no_rompe_el_pdf(tmp_path: Path) -> None:
    """Reportlab lee `<` y `&` como marcado; un titulo editado a mano puede traerlos."""
    raro = dataclasses.replace(NOVELA, titulo="Tú & yo <siempre>", dedicatoria="A & B")
    assert exportar_pdf(raro, tmp_path / "raro.pdf").paginas > 0
