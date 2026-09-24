"""Exportacion de la novela a PDF.

El PDF no es una descarga del texto: es el objeto que alguien recibe de regalo. Por eso
lleva las piezas que el alcance exige -portada tipografica, dedicatoria sola en su pagina,
indice navegable, ficha de personajes y lugares, y pagina de novedades cuando hay version
anterior- y por eso la maquetacion es de libro: serifa, parrafos corridos y medida de
lectura limitada.

La pagina de novedades solo aparece a partir de la version 2. Novedades respecto a que:
en la primera version es ruido que ocupa la primera pagina del regalo.

Cubre RF-LEC-08, y RF-PDF-01 a RF-PDF-03 de SPEC-006.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any
from xml.sax.saxutils import escape

# reportlab no publica stubs de tipos; el modulo se usa solo aqui y su frontera es
# estrecha: una funcion que recibe datos y escribe un fichero.
from reportlab.lib.colors import HexColor
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
    texto_de_dedicatoria: str = ""
    pagina_de_dedicatoria: int | None = None
    paginas: int = 0


# La portada es tipografica y una sola (SPEC-006 N-01, N-02), con los colores de la
# cubierta de la lectura (`.cubierta-libro`): quien la ve en pantalla y quien la recibe
# impresa tienen que reconocer el mismo libro. Viven aqui y no en un tema porque el PDF no
# tiene temas; lo que se imprime es siempre lo mismo.
FONDO_DE_PORTADA = HexColor("#8a5424")
ORO = HexColor("#f0d7a8")
PAPEL = HexColor("#fdf4e3")


def _pintar_portada(lienzo: Any, documento: Any) -> None:
    """El fondo de la portada, a pagina completa: lo que no cabe en un flujo de parrafos."""
    ancho, alto = documento.pagesize
    lienzo.saveState()
    lienzo.setFillColor(FONDO_DE_PORTADA)
    lienzo.rect(0, 0, ancho, alto, stroke=0, fill=1)
    lienzo.setStrokeColor(ORO)
    lienzo.setLineWidth(0.8)
    lienzo.rect(8 * mm, 8 * mm, ancho - 16 * mm, alto - 16 * mm, stroke=1, fill=0)
    lienzo.setLineWidth(0.4)
    lienzo.rect(10 * mm, 10 * mm, ancho - 20 * mm, alto - 20 * mm, stroke=1, fill=0)
    # Ornamento: dos filetes y un rombo, bajo el titulo. Times no trae «❦».
    centro, y = ancho / 2, alto * 0.42
    lienzo.line(centro - 30 * mm, y, centro - 4 * mm, y)
    lienzo.line(centro + 4 * mm, y, centro + 30 * mm, y)
    rombo = lienzo.beginPath()
    rombo.moveTo(centro, y + 2.5 * mm)
    rombo.lineTo(centro + 2.5 * mm, y)
    rombo.lineTo(centro, y - 2.5 * mm)
    rombo.lineTo(centro - 2.5 * mm, y)
    rombo.close()
    lienzo.setFillColor(ORO)
    lienzo.drawPath(rombo, stroke=0, fill=1)
    lienzo.restoreState()


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
        "antetitulo": ParagraphStyle(
            "antetitulo",
            parent=base["Normal"],
            fontName="Times-Roman",
            fontSize=8.5,
            leading=12,
            alignment=TA_CENTER,
            textColor=ORO,
        ),
        "titulo-portada": ParagraphStyle(
            "titulo-portada",
            parent=base["Title"],
            fontName="Times-Bold",
            fontSize=28,
            leading=34,
            alignment=TA_CENTER,
            textColor=PAPEL,
        ),
        "para-portada": ParagraphStyle(
            "para-portada",
            parent=base["Normal"],
            fontName="Times-Italic",
            fontSize=14,
            leading=20,
            alignment=TA_CENTER,
            textColor=ORO,
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

    # En que pagina cae la dedicatoria. Se anota al maquetarla y no se calcula: contar
    # paginas a mano es apostar a que nadie cambie lo que va antes.
    paginas_de: dict[str, int] = {}

    def al_colocar(flowable: Any) -> None:
        marca = getattr(flowable, "marca_de_pagina", None)
        if marca is not None:
            paginas_de.setdefault(marca, documento.page)

    documento.afterFlowable = al_colocar

    # --- portada (RF-PDF-01) --------------------------------------------------------
    # Sin la dedicatoria: tiene su propia pagina. Y sin «Para ...» si el titulo ya lo dice,
    # que es el titulo que compone el backend por defecto (DV-4 de SPEC-005).
    secciones.append("portada")
    para = (
        f"Para {novela.destinatario}"
        if novela.destinatario and novela.destinatario not in novela.titulo
        else ""
    )
    texto_portada = "\n".join(parte for parte in (novela.titulo, para) if parte)
    flujo += [
        Spacer(1, 32 * mm),
        Paragraph("UNA NOVELA DE MYSTORYMAKER", estilos["antetitulo"]),
        Spacer(1, 10 * mm),
        Paragraph(escape(novela.titulo), estilos["titulo-portada"]),
        Spacer(1, 24 * mm),
    ]
    if para:
        flujo.append(Paragraph(escape(para), estilos["para-portada"]))
    flujo.append(PageBreak())

    # --- dedicatoria, sola en su pagina (RF-PDF-02) --------------------------------
    dedicatoria = novela.dedicatoria.strip()
    if dedicatoria:
        secciones.append("dedicatoria")
        parrafo = Paragraph(escape(dedicatoria), estilos["dedicatoria"])
        parrafo.marca_de_pagina = "dedicatoria"
        flujo += [Spacer(1, 55 * mm), parrafo, PageBreak()]

    # --- novedades, solo si hay version anterior ---------------------------------
    cambiados = [c for c in novela.capitulos if c.cambiado]
    if novela.version > 1:
        secciones.append("novedades")
        flujo.append(Paragraph("Qué ha cambiado", estilos["capitulo"]))
        if cambiados:
            flujo += [
                Paragraph(
                    f'<a href="#{c.id}" color="#333333">'
                    f"Capítulo {c.orden}. {escape(c.titulo)}</a>",
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
                f"{capitulo.orden}. {escape(capitulo.titulo)}</a>{marca}",
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
                f'{escape(nombre)} — <a href="#{capitulo_id}" color="#333333">aparece aquí</a>',
                estilos["entrada"],
            )
        )
    if novela.lugares:
        flujo.append(Spacer(1, 6 * mm))
        flujo.append(Paragraph("Lugares", estilos["capitulo"]))
        for nombre, capitulo_id in novela.lugares:
            flujo.append(
                Paragraph(
                    f'{escape(nombre)} — <a href="#{capitulo_id}" color="#333333">'
                    "aparece aquí</a>",
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
                f'<a name="{capitulo.id}"/>{capitulo.orden}. {escape(capitulo.titulo)}',
                estilos["capitulo"],
            )
        )
        for parrafo in capitulo.texto.split("\n\n"):
            if parrafo.strip():
                flujo.append(Paragraph(escape(parrafo.strip()), estilos["prosa"]))
        flujo.append(PageBreak())

    documento.build(flujo, onFirstPage=_pintar_portada)

    return ResultadoDeExportacion(
        ruta=destino,
        secciones=tuple(secciones),
        anclas=tuple(anclas),
        texto_de_portada=texto_portada,
        texto_de_dedicatoria=dedicatoria,
        pagina_de_dedicatoria=paginas_de.get("dedicatoria"),
        paginas=documento.page,
    )
