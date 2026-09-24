"""Exportacion de la novela a PDF.

El PDF no es una descarga del texto: es el objeto que alguien recibe de regalo. Por eso
lleva las cuatro piezas que el alcance exige -portada con dedicatoria, indice navegable,
ficha de personajes y lugares, y pagina de novedades cuando hay version anterior- y por
eso la maquetacion es de libro: serifa, parrafos corridos y medida de lectura limitada.

La pagina de novedades solo aparece a partir de la version 2. Novedades respecto a que:
en la primera version es ruido que ocupa la primera pagina del regalo.

Cubre RF-LEC-08.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

# reportlab no publica stubs de tipos; el modulo se usa solo aqui y su frontera es
# estrecha: una funcion que recibe datos y escribe un fichero.
from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY
from reportlab.lib.pagesizes import A5
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import (
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
)


@dataclass(frozen=True)
class CapituloParaPDF:
    """Un capitulo listo para maquetar."""

    id: str
    orden: int
    titulo: str
    texto: str
    cambiado: bool = False


@dataclass(frozen=True)
class NovelaParaPDF:
    """Todo lo que el PDF necesita, ya leido de la story bible."""

    titulo: str
    dedicatoria: str
    destinatario: str
    personajes: tuple[tuple[str, str], ...]
    lugares: tuple[tuple[str, str], ...]
    capitulos: tuple[CapituloParaPDF, ...]
    version: int = 1


@dataclass
class ResultadoDeExportacion:
    """Que se escribio, para poder comprobarlo sin abrir el PDF a ojo."""

    ruta: Path
    secciones: tuple[str, ...] = ()
    anclas: tuple[str, ...] = ()
    texto_de_portada: str = ""
    paginas: int = 0


def _estilos() -> dict[str, ParagraphStyle]:
    base = getSampleStyleSheet()
    return {
        "titulo": ParagraphStyle(
            "titulo",
            parent=base["Title"],
            fontName="Times-Bold",
            fontSize=26,
            leading=32,
            alignment=TA_CENTER,
        ),
        "dedicatoria": ParagraphStyle(
            "dedicatoria",
            parent=base["Normal"],
            fontName="Times-Italic",
            fontSize=13,
            leading=20,
            alignment=TA_CENTER,
        ),
        "capitulo": ParagraphStyle(
            "capitulo",
            parent=base["Heading1"],
            fontName="Times-Bold",
            fontSize=17,
            leading=22,
            spaceAfter=10 * mm,
        ),
        # Medida de lectura limitada y sangria francesa: es prosa, no un volcado.
        "prosa": ParagraphStyle(
            "prosa",
            parent=base["Normal"],
            fontName="Times-Roman",
            fontSize=11.5,
            leading=17,
            alignment=TA_JUSTIFY,
            firstLineIndent=5 * mm,
            spaceAfter=0,
        ),
        "entrada": ParagraphStyle(
            "entrada",
            parent=base["Normal"],
            fontName="Times-Roman",
            fontSize=11,
            leading=16,
        ),
    }


def exportar_pdf(novela: NovelaParaPDF, destino: Path) -> ResultadoDeExportacion:
    """Escribe el PDF y devuelve lo que contiene, para poder comprobarlo."""
    if not novela.capitulos:
        raise ValueError(
            "No se exporta un PDF sin ningun capitulo: seria un fichero que parece una "
            "novela y no lo es."
        )

    estilos = _estilos()
    documento = SimpleDocTemplate(
        str(destino),
        pagesize=A5,
        leftMargin=18 * mm,
        rightMargin=18 * mm,
        topMargin=20 * mm,
        bottomMargin=20 * mm,
        title=novela.titulo,
        author="MyStoryMaker",
    )

    flujo: list[object] = []
    secciones: list[str] = []
    anclas: list[str] = []

    # --- portada -----------------------------------------------------------------
    secciones.append("portada")
    texto_portada = f"{novela.titulo}\n{novela.dedicatoria}\nPara {novela.destinatario}"
    flujo += [
        Spacer(1, 30 * mm),
        Paragraph(novela.titulo, estilos["titulo"]),
        Spacer(1, 18 * mm),
        Paragraph(novela.dedicatoria, estilos["dedicatoria"]),
        Spacer(1, 6 * mm),
        Paragraph(f"Para {novela.destinatario}", estilos["dedicatoria"]),
        PageBreak(),
    ]

    # --- novedades, solo si hay version anterior ---------------------------------
    cambiados = [c for c in novela.capitulos if c.cambiado]
    if novela.version > 1:
        secciones.append("novedades")
        flujo.append(Paragraph("Qué ha cambiado", estilos["capitulo"]))
        if cambiados:
            flujo += [
                Paragraph(
                    f'<a href="#{c.id}" color="#333333">Capítulo {c.orden}. {c.titulo}</a>',
                    estilos["entrada"],
                )
                for c in cambiados
            ]
        else:
            flujo.append(
                Paragraph("Ningún capítulo cambió en esta versión.", estilos["entrada"])
            )
        flujo.append(PageBreak())

    # --- indice ------------------------------------------------------------------
    secciones.append("indice")
    flujo.append(Paragraph("Índice", estilos["capitulo"]))
    for capitulo in sorted(novela.capitulos, key=lambda c: c.orden):
        marca = " ·nuevo·" if capitulo.cambiado and novela.version > 1 else ""
        flujo.append(
            Paragraph(
                f'<a href="#{capitulo.id}" color="#333333">'
                f"{capitulo.orden}. {capitulo.titulo}</a>{marca}",
                estilos["entrada"],
            )
        )
    flujo.append(PageBreak())

    # --- ficha de personajes y lugares -------------------------------------------
    secciones.append("ficha")
    anclas.append("ficha")
    flujo.append(Paragraph('<a name="ficha"/>Quién es quién', estilos["capitulo"]))
    for nombre, capitulo_id in novela.personajes:
        flujo.append(
            Paragraph(
                f'{nombre} — <a href="#{capitulo_id}" color="#333333">aparece aquí</a>',
                estilos["entrada"],
            )
        )
    if novela.lugares:
        flujo.append(Spacer(1, 6 * mm))
        flujo.append(Paragraph("Lugares", estilos["capitulo"]))
        for nombre, capitulo_id in novela.lugares:
            flujo.append(
                Paragraph(
                    f'{nombre} — <a href="#{capitulo_id}" color="#333333">aparece aquí</a>',
                    estilos["entrada"],
                )
            )
    flujo.append(PageBreak())

    # --- capitulos ---------------------------------------------------------------
    secciones.append("capitulos")
    for capitulo in sorted(novela.capitulos, key=lambda c: c.orden):
        anclas.append(capitulo.id)
        flujo.append(
            Paragraph(
                f'<a name="{capitulo.id}"/>{capitulo.orden}. {capitulo.titulo}',
                estilos["capitulo"],
            )
        )
        for parrafo in capitulo.texto.split("\n\n"):
            if parrafo.strip():
                flujo.append(Paragraph(parrafo.strip(), estilos["prosa"]))
        flujo.append(PageBreak())

    documento.build(flujo)

    return ResultadoDeExportacion(
        ruta=destino,
        secciones=tuple(secciones),
        anclas=tuple(anclas),
        texto_de_portada=texto_portada,
        paginas=documento.page,
    )
