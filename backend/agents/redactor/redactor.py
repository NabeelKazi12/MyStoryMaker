"""Contrato del Redactor: que se le pide y que forma tiene lo que devuelve.

La salida se valida contra este esquema antes de que nada la toque. `dispatch` concentra
el riesgo: es la frontera donde el texto de un modelo se convierte en objeto tipado, y
todo lo que pase de ahi sin validar contamina el canon.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

VERSION_DE_PROMPT = "1.0.0"
PROMPTS = Path(__file__).parent / "prompts"


def prompt_vigente() -> str:
    """El prompt de la version declarada. Editarlo sin subir la version rompe el replay."""
    return (PROMPTS / f"v{VERSION_DE_PROMPT}.md").read_text(encoding="utf-8")


@dataclass(frozen=True)
class SalidaDelRedactor:
    """Prosa mas el bloque declarado. Es el contrato comun de `AGENTS.md` 3."""

    prosa: str
    hechos_nuevos_detectados: tuple[tuple[str, str, str], ...] = ()
    eventos_narrados: tuple[str, ...] = ()
    siembras_tocadas: tuple[str, ...] = ()
    contexto_insuficiente: bool = False
    falta: tuple[str, ...] = ()

    @property
    def recuento_palabras(self) -> int:
        return len(self.prosa.split())

    @property
    def declaracion_vacia(self) -> bool:
        """Si el bloque de hechos llego vacio. No es un defecto: es evidencia ausente."""
        return not self.hechos_nuevos_detectados


class SalidaInvalida(Exception):
    """La salida no valida contra el esquema del rol. Es fallo de contrato (D-06)."""

    def __init__(self, motivo: str) -> None:
        super().__init__(f"SalidaDelRedactor: {motivo}")


def parsear(texto: str) -> SalidaDelRedactor:
    """Convierte la respuesta del modelo en un objeto tipado, o falla.

    Si el agente se rinde, devuelve `resultado: null` con su `falta`: no inventa. El
    Orquestador reconstruye el paquete o replanifica (RF-WRK-05).
    """
    if not texto.strip():
        raise SalidaInvalida("la respuesta llego vacia")

    if "contexto_insuficiente" in texto.lower():
        falta = tuple(
            linea.strip("- ").strip()
            for linea in _seccion(texto, "falta").splitlines()
            if linea.strip()
        )
        if not falta:
            raise SalidaInvalida("declara contexto_insuficiente sin enumerar que le falta")
        return SalidaDelRedactor(prosa="", contexto_insuficiente=True, falta=falta)

    prosa = _seccion(texto, "prosa").strip()
    if not prosa:
        raise SalidaInvalida("no trae prosa y tampoco declara contexto_insuficiente")

    return SalidaDelRedactor(
        prosa=prosa,
        hechos_nuevos_detectados=_hechos(_seccion(texto, "hechos_nuevos_detectados")),
        eventos_narrados=_lista(_seccion(texto, "eventos_narrados")),
        siembras_tocadas=_lista(_seccion(texto, "siembras_tocadas")),
    )


def _seccion(texto: str, nombre: str) -> str:
    patron = re.compile(rf"^##\s*{nombre}\s*$(.*?)(?=^##\s|\Z)", re.M | re.S | re.I)
    coincidencia = patron.search(texto)
    return coincidencia.group(1) if coincidencia else ""


def _lista(bloque: str) -> tuple[str, ...]:
    return tuple(linea.strip("- ").strip() for linea in bloque.splitlines() if linea.strip())


def _hechos(bloque: str) -> tuple[tuple[str, str, str], ...]:
    declarados: list[tuple[str, str, str]] = []
    for linea in bloque.splitlines():
        partes = [p.strip() for p in linea.strip("- ").split("|")]
        if len(partes) == 3 and all(partes):
            declarados.append((partes[0], partes[1], partes[2]))
    return tuple(declarados)
