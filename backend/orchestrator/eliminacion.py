"""Eliminar una novela: se retira con fecha, y sus filas se quedan.

Vive en `orchestrator/` porque sus precondiciones son las de otros dos modulos de aqui:
la aprobacion vigente (SPEC-007) y el progreso de la escritura (SPEC-004). Una novela
aprobada se reabre antes; una que se esta escribiendo, se espera (SPEC-009 N-03).

Retirar solo escribe `volumen.eliminada_en` y una linea en `audit_log`. Ninguna otra fila
se borra ni se toca (RF-ELI-07): es lo que distingue retirar de borrar (D-23).

Cubre RF-ELI-01 a RF-ELI-04, RF-ELI-07 y RF-ELI-08.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass

from backend.orchestrator.aprobacion import vigente
from backend.orchestrator.escritura import progreso
from backend.store.database import Conexion
from backend.store.repositories import AuditLog

# Los estados en los que el worker todavia tiene trabajo con la novela.
EN_CURSO = ("abriendo", "escribiendo")


class NovelaInexistente(LookupError):
    """No existe, o ya esta retirada: para la API son lo mismo (RF-ELI-04)."""


class EliminacionRechazada(Exception):
    """No se retira, y se dice por que."""


@dataclass(frozen=True)
class NovelaRetirada:
    volumen_id: str
    titulo: str
    eliminada_en: str


def exigir_viva(conn: Conexion, volumen_id: str) -> None:
    """`NovelaInexistente` si el volumen no existe o esta retirado.

    Lo usan todas las rutas con `{volumen_id}`: una novela retirada no existe para la API
    (RF-ELI-05), y el mensaje es el mismo que el de un volumen que nunca existio.
    """
    fila = conn.execute(
        "SELECT eliminada_en FROM volumen WHERE id = ?", (volumen_id,)
    ).fetchone()
    if fila is None or fila["eliminada_en"] is not None:
        raise NovelaInexistente(f"no existe el volumen {volumen_id}")


def eliminar(conn: Conexion, volumen_id: str) -> NovelaRetirada:
    exigir_viva(conn, volumen_id)
    if vigente(conn, volumen_id) is not None:
        raise EliminacionRechazada("La novela está aprobada; reábrela antes de eliminarla")
    estado = progreso(conn, volumen_id)
    if estado.estado in EN_CURSO:
        raise EliminacionRechazada(
            f"la escritura sigue en marcha («{estado.estado}»): {estado.detalle} "
            "Espera a que termine o se detenga para eliminar la novela"
        )

    conn.execute(
        "UPDATE volumen SET eliminada_en = datetime('now') WHERE id = ?", (volumen_id,)
    )
    fila = conn.execute(
        "SELECT titulo, eliminada_en FROM volumen WHERE id = ?", (volumen_id,)
    ).fetchone()
    AuditLog(conn).registrar(
        f"al-{uuid.uuid4().hex[:12]}",
        decision="eliminar_novela",
        motivo=f"{volumen_id} «{fila['titulo']}» retirada; sus filas se conservan",
        ambito="eliminacion",
    )
    return NovelaRetirada(
        volumen_id=volumen_id, titulo=fila["titulo"], eliminada_en=fila["eliminada_en"]
    )
