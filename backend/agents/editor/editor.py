"""Contrato del Editor/critic: lee lo escrito y devuelve defectos con evidencia.

Es el rol que **no** escribe. Su unica salida son defectos, y un defecto sin evidencia
citable se descarta y se cuenta, igual que en la capa de calidad: descartarlo en silencio
oculta a un agente que opina en vez de comprobar (`verification.md` 11, F-03).

Quien genera no valida (`AGENTS.md` 1): por eso el editor nunca es el mismo rol que
escribio el capitulo.

Cubre RF-HAR-01.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from backend.domain.production.ejecucion import Defecto
from backend.domain.vocabularies import Severidad

VERSION_DE_PROMPT = "1.0.0"
PROMPTS = Path(__file__).parent / "prompts"


@dataclass(frozen=True)
class SalidaDelEditor:
    """Los defectos encontrados, y si el capitulo se acepta."""

    defectos: tuple[Defecto, ...]
    acepta: bool
    descartados_sin_evidencia: int = 0


def parsear_editor(texto: str) -> SalidaDelEditor:
    """Convierte la critica en defectos tipados, descartando lo que no trae evidencia."""
    defectos: list[Defecto] = []
    descartados = 0

    for numero, linea in enumerate(_seccion(texto, "defectos").splitlines(), start=1):
        if not linea.strip():
            continue
        partes = [parte.strip() for parte in linea.strip("- ").split("|")]
        if len(partes) < 4:
            descartados += 1
            continue
        severidad, tipo, regla, evidencia = partes[0], partes[1], partes[2], partes[3]
        if not evidencia:
            descartados += 1
            continue
        defectos.append(
            Defecto(
                id=f"editor-{numero}",
                tipo=tipo,
                severidad=Severidad(severidad.lower()),
                regla_violada=regla,
                evidencia=evidencia,
            )
        )

    veredicto = _seccion(texto, "veredicto").strip().lower()
    return SalidaDelEditor(
        defectos=tuple(defectos),
        acepta=veredicto.startswith("aceptado"),
        descartados_sin_evidencia=descartados,
    )


def _seccion(texto: str, nombre: str) -> str:
    patron = re.compile(rf"^##\s*{nombre}\s*$(.*?)(?=^##\s|\Z)", re.M | re.S | re.I)
    coincidencia = patron.search(texto)
    return coincidencia.group(1) if coincidencia else ""


def prompt_vigente() -> str:
    return (PROMPTS / f"v{VERSION_DE_PROMPT}.md").read_text(encoding="utf-8")
