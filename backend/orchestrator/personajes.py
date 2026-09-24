"""Leer y reemplazar los personajes declarados de una novela, antes de escribirla.

Vive en `orchestrator/` porque junta tres cosas de sitios distintos: la validacion del
Entrevistador —la misma que en la entrevista, para que las dos digan lo mismo—, el
progreso de la escritura y la aprobacion. `api/` solo traduce el resultado a HTTP.

Se edita solo mientras la escritura esta `sin_empezar`: despues, los personajes ya estan
en el canon y en la prosa, y cambiarlos es un cambio del lector (SPEC-011 N-01).

Cubre RF-PER-08 a RF-PER-10.
"""

from __future__ import annotations

import uuid

from backend.agents.entrevistador.entrevistador import Contradiccion, leer_personajes
from backend.domain.spec.encargo import PersonajeDeclarado
from backend.orchestrator.aprobacion import vigente
from backend.orchestrator.escritura import progreso
from backend.store.database import Conexion
from backend.store.personajes import PersonajesDeclarados
from backend.store.repositories import AuditLog

YA_EMPEZADA = "La escritura ya ha empezado: los personajes están en la novela; pide un cambio"
APROBADA = "La novela está aprobada; reábrela para cambiarla"


class PersonajesInvalidos(ValueError):
    """La lista no vale, y se dice que personaje falla y por que."""

    def __init__(self, problemas: tuple[Contradiccion, ...]) -> None:
        super().__init__("; ".join(p.detalle for p in problemas))
        self.problemas = problemas


class PersonajesCerrados(Exception):
    """La novela ya no admite cambios en sus personajes declarados."""


def leer(conn: Conexion, volumen_id: str) -> tuple[PersonajeDeclarado, ...]:
    return PersonajesDeclarados(conn).de_brief(_brief_de(conn, volumen_id))


def reemplazar(
    conn: Conexion, volumen_id: str, crudos: object
) -> tuple[PersonajeDeclarado, ...]:
    """Guarda la lista nueva si la escritura no ha empezado y la lista vale."""
    if vigente(conn, volumen_id) is not None:
        raise PersonajesCerrados(APROBADA)
    if progreso(conn, volumen_id).estado != "sin_empezar":
        raise PersonajesCerrados(YA_EMPEZADA)

    brief_id = _brief_de(conn, volumen_id)
    destinataria = conn.execute(
        "SELECT nombre FROM destinatario WHERE brief_id = ? LIMIT 1", (brief_id,)
    ).fetchone()
    nuevos, problemas = leer_personajes(
        "" if destinataria is None else destinataria["nombre"], crudos, prefijo=brief_id
    )
    if problemas:
        raise PersonajesInvalidos(problemas)

    repositorio = PersonajesDeclarados(conn)
    anteriores = repositorio.de_brief(brief_id)
    repositorio.reemplazar(brief_id, nuevos)
    AuditLog(conn).registrar(
        f"al-{uuid.uuid4().hex[:12]}",
        decision="editar_personajes",
        motivo=f"{volumen_id}: {_resumen(anteriores)} -> {_resumen(nuevos)}",
        ambito="personajes",
    )
    return repositorio.de_brief(brief_id)


def _brief_de(conn: Conexion, volumen_id: str) -> str:
    fila = conn.execute("SELECT brief_id FROM volumen WHERE id = ?", (volumen_id,)).fetchone()
    return "" if fila is None or fila["brief_id"] is None else str(fila["brief_id"])


def _resumen(personajes: tuple[PersonajeDeclarado, ...]) -> str:
    return "[" + ", ".join(f"{p.nombre} ({p.papel.value})" for p in personajes) + "]"
