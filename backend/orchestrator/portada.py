"""Editar el titulo y la dedicatoria de una novela ya encargada.

Vive en `orchestrator/` por lo mismo que `encargo.py`: coordina una regla de calidad -el
guardarrail- con el almacen, y `api/` solo traduce el resultado a HTTP.

Cambia como se presenta la novela y nada de lo que cuenta: ni prosa, ni canon, ni tareas,
ni versiones. Por eso no publica version nueva (SPEC-006 N-04).

Cubre RF-POR-01 a RF-POR-07.
"""

from __future__ import annotations

import dataclasses
import uuid

from backend.quality.guardarrail import Guardarrail
from backend.store.database import Conexion
from backend.store.escritura import Portada, Portadas
from backend.store.repositories import AuditLog

LARGO_MAXIMO_DEL_TITULO = 120
LARGO_MAXIMO_DE_LA_DEDICATORIA = 500


class NovelaSinPortada(LookupError):
    """La novela que se quiere editar no existe."""


class PortadaInvalida(ValueError):
    """Lo pedido no se puede guardar, y se dice por que."""


def editar_portada(
    conn: Conexion,
    volumen_id: str,
    *,
    titulo: str | None = None,
    dedicatoria: str | None = None,
) -> Portada:
    """Guarda lo que se pide, o no guarda nada y dice que falla."""
    if titulo is None and dedicatoria is None:
        raise PortadaInvalida("hay que enviar el titulo, la dedicatoria o los dos")

    actual = Portadas(conn).de(volumen_id)
    if actual is None:
        raise NovelaSinPortada(f"no existe el volumen {volumen_id}")

    nueva = dataclasses.replace(
        actual,
        titulo=actual.titulo if titulo is None else titulo.strip(),
        dedicatoria=actual.dedicatoria if dedicatoria is None else dedicatoria.strip(),
    )
    _exigir_limites(nueva)
    _exigir_sin_vetados(conn, nueva, cambiados=(titulo, dedicatoria))

    Portadas(conn).guardar(nueva)
    AuditLog(conn).registrar(
        f"al-{uuid.uuid4().hex[:12]}",
        decision="editar_portada",
        motivo=(
            f"titulo «{actual.titulo}» -> «{nueva.titulo}»; "
            f"dedicatoria «{actual.dedicatoria}» -> «{nueva.dedicatoria}»"
        ),
        ambito="portada",
    )
    return nueva


def _exigir_limites(portada: Portada) -> None:
    if not portada.titulo:
        raise PortadaInvalida("el titulo no puede quedar vacio")
    if len(portada.titulo) > LARGO_MAXIMO_DEL_TITULO:
        raise PortadaInvalida(
            f"el titulo tiene {len(portada.titulo)} caracteres y el maximo es "
            f"{LARGO_MAXIMO_DEL_TITULO}"
        )
    if len(portada.dedicatoria) > LARGO_MAXIMO_DE_LA_DEDICATORIA:
        raise PortadaInvalida(
            f"la dedicatoria tiene {len(portada.dedicatoria)} caracteres y el maximo es "
            f"{LARGO_MAXIMO_DE_LA_DEDICATORIA}"
        )


def _exigir_sin_vetados(
    conn: Conexion, portada: Portada, *, cambiados: tuple[str | None, str | None]
) -> None:
    """El guardarrail sobre lo que se esta cambiando, con las mismas listas que la prosa."""
    textos = [
        texto
        for texto, enviado in (
            (portada.titulo, cambiados[0]),
            (portada.dedicatoria, cambiados[1]),
        )
        if enviado is not None and texto
    ]
    guardarrail = Guardarrail(conn)
    terminos = sorted(
        {
            coincidencia.termino
            for texto in textos
            for coincidencia in guardarrail.coincidencias(
                texto, brief_id=portada.brief_id, destinatario_id=portada.destinatario_id
            )
        }
    )
    if terminos:
        raise PortadaInvalida(f"hay terminos vetados: {', '.join(terminos)}")
