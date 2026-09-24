"""Exportacion de la novela a PDF, con indice, ficha, portada y novedades.

SPEC-003, fase E, paso E-08. Cubre RF-LEC-08.

Lo que se comprueba es que el PDF **contiene** lo que el alcance exige y que los enlaces
internos existen. Que se lea bien es inspeccion humana: un PDF valido puede ser ilegible.
"""

from __future__ import annotations

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
def test_la_dedicatoria_del_destinatario_aparece_en_la_portada(tmp_path: Path) -> None:
    """RF-LEC-03: es lo que convierte el PDF en un regalo y no en una descarga."""
    resultado = exportar_pdf(NOVELA, tmp_path / "novela.pdf")

    assert NOVELA.dedicatoria in resultado.texto_de_portada
    assert "Marta" in resultado.texto_de_portada
