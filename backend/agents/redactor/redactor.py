"""Contrato del Redactor: que se le pide y que forma tiene lo que devuelve.

La salida se valida contra este esquema antes de que nada la toque. `dispatch` concentra
el riesgo: es la frontera donde el texto de un modelo se convierte en objeto tipado, y
todo lo que pase de ahi sin validar contamina el canon.
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from pathlib import Path

VERSION_DE_PROMPT = "1.1.0"
PROMPTS = Path(__file__).parent / "prompts"


# Hash del fichero de cada version publicada. Editar un prompt sin subir la version rompe
# la reproducibilidad de todo lo generado antes, y se detecta porque el hash cambia y la
# version no (RF-WRK-07). Al publicar una version nueva se anade su linea aqui.
MANIFIESTO = {
    "1.0.0": "b096e2e19ccbd60d811819307e677a8ca6089d4ea1ac85c70006d23d6675ea78",
    # v1.1.0 no cambia el esquema: lo escribe. La v1.0.0 nunca decia que la prosa va bajo
    # `## prosa`, y un modelo real que no lo adivinaba fallaba el contrato siempre.
    "1.1.0": "8cc8ab20c126173278804019a6d520454f0f80ee2b003ee312779dc706f7999c",
}


class PromptAlterado(Exception):
    """El fichero de prompt no coincide con el hash de su version declarada."""

    def __init__(self, version: str, esperado: str, encontrado: str) -> None:
        super().__init__(
            f"Prompt del Redactor v{version}: el fichero ha cambiado sin que suba la "
            f"version. Esperado {esperado[:12]}..., encontrado {encontrado[:12]}.... "
            f"Incrementa la version en lugar de editar en sitio: si no, todo lo generado "
            f"antes deja de ser reproducible y nada lo avisa."
        )


def hash_del_prompt(version: str = "") -> str:
    """Hash del fichero de prompt de una version."""
    objetivo = version or VERSION_DE_PROMPT
    return hashlib.sha256((PROMPTS / f"v{objetivo}.md").read_bytes()).hexdigest()


def verificar_integridad_del_prompt(version: str = "") -> None:
    """Falla si el fichero cambio sin que subiera la version. Corre en integracion continua."""
    objetivo = version or VERSION_DE_PROMPT
    esperado = MANIFIESTO.get(objetivo)
    if esperado is None:
        # Se comprueba antes de leer el fichero: una version que nadie registro puede no
        # existir siquiera, y el error util es «no esta en el manifiesto», no un
        # FileNotFoundError que obliga a ir a mirar por que.
        raise PromptAlterado(objetivo, "sin registrar en el manifiesto", "desconocido")
    encontrado = hash_del_prompt(objetivo)
    if encontrado != esperado:
        raise PromptAlterado(objetivo, esperado, encontrado)


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

    # Las vallas de codigo no son contenido: quitarlas no cambia lo que el rol escribio.
    texto = "\n".join(
        linea for linea in texto.splitlines() if not linea.strip().startswith("```")
    )

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
