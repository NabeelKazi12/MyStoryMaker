"""Cambiar el nombre de un personaje en toda la novela.

Vive en `orchestrator/` porque junta cosas de sitios distintos: la sustitucion del
dominio, los textos de la novela del store, el canon versionado, las versiones de la
novela, la aprobacion y el progreso de la escritura. `api/` solo traduce a HTTP.

Es una sustitucion exacta, sin modelo (D-26): se paga en milisegundos y no reescribe nada
que nadie pidiera cambiar. Todo ocurre en un `SAVEPOINT`: o cambia todo o nada, porque un
nombre cambiado en la prosa y no en los resumenes es canon fantasma.

Cubre RF-NOM-02 a RF-NOM-14.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass

from backend.domain.diegetic.nombres import SustitucionDeNombre
from backend.domain.spec.encargo import LARGO_MAXIMO_DEL_NOMBRE, clave_de_nombre
from backend.orchestrator.aprobacion import vigente
from backend.orchestrator.escritura import progreso
from backend.store.database import Conexion
from backend.store.nombres import TextosDeLaNovela
from backend.store.repositories import AuditLog, CanonVersionado, VersionesDeNovela

APROBADA = "La novela está aprobada; reábrela para cambiarla"
ESCRIBIENDO = (
    "Espera a que termine la escritura: una escena en curso volvería con el nombre viejo"
)
DESTINATARIA = (
    "Es la persona destinataria: su nombre viene del encargo y está en la dedicatoria; "
    "no se cambia desde aquí"
)


class NombreInvalido(ValueError):
    """El nombre nuevo no vale, y se dice por que."""


class PersonajeAjeno(LookupError):
    """El personaje no sale en esta novela."""


class RenombradoCerrado(Exception):
    """La novela, o ese personaje, no admite ahora un cambio de nombre."""


@dataclass(frozen=True)
class CapituloCambiado:
    id: str
    orden: int


@dataclass(frozen=True)
class Renombrado:
    """Lo que el cambio hizo, para responderlo y para que quede auditable."""

    personaje_id: str
    anterior: str
    nuevo: str
    revision: int
    version_id: str | None
    capitulos: tuple[CapituloCambiado, ...]


def renombrar(conn: Conexion, volumen_id: str, personaje_id: str, nombre: str) -> Renombrado:
    """Cambia el nombre si se puede y lo lleva a cada texto de la novela."""
    if vigente(conn, volumen_id) is not None:
        raise RenombradoCerrado(APROBADA)
    if progreso(conn, volumen_id).en_curso:
        raise RenombradoCerrado(ESCRIBIENDO)

    textos = TextosDeLaNovela(conn)
    personajes = textos.personajes(volumen_id)
    if personaje_id not in personajes:
        raise PersonajeAjeno(f"El personaje {personaje_id} no sale en esta novela")
    anterior = personajes[personaje_id]
    destinataria = textos.destinataria(volumen_id)
    if destinataria is not None and clave_de_nombre(destinataria) == clave_de_nombre(anterior):
        raise RenombradoCerrado(DESTINATARIA)

    nuevo = " ".join(nombre.split())
    _exigir_nombre(nuevo, anterior, [n for i, n in personajes.items() if i != personaje_id])

    otros = tuple(n for i, n in personajes.items() if i != personaje_id)
    regla = SustitucionDeNombre(anterior, nuevo, otros=otros)

    conn.execute("SAVEPOINT renombrar")
    try:
        canon, prosa = textos.sustituir(volumen_id, personaje_id, regla.aplicar)

        versionado = CanonVersionado(conn)
        revision = versionado.abrir_revision(f"renombrar {personaje_id}: {anterior} -> {nuevo}")
        for cambio in canon:
            versionado.registrar_renombrado(
                revision, cambio.tabla, cambio.fila_id, cambio.antes, cambio.despues
            )

        capitulos = _capitulos_cambiados(conn, {p.capitulo_id for p in prosa})
        version_id = _publicar(conn, volumen_id, capitulos, anterior, nuevo) if prosa else None

        AuditLog(conn).registrar(
            f"al-{uuid.uuid4().hex[:12]}",
            decision="renombrar_personaje",
            motivo=f"{volumen_id}: {personaje_id} «{anterior}» -> «{nuevo}», "
            f"{len(prosa)} escena(s) reescrita(s)",
            ambito="personajes",
        )
    except BaseException:
        conn.execute("ROLLBACK TO SAVEPOINT renombrar")
        conn.execute("RELEASE SAVEPOINT renombrar")
        raise
    conn.execute("RELEASE SAVEPOINT renombrar")

    return Renombrado(
        personaje_id=personaje_id,
        anterior=anterior,
        nuevo=nuevo,
        revision=revision,
        version_id=version_id,
        capitulos=capitulos,
    )


def _exigir_nombre(nuevo: str, anterior: str, otros: list[str]) -> None:
    if not nuevo or len(nuevo) > LARGO_MAXIMO_DEL_NOMBRE:
        raise NombreInvalido(
            "Personaje: el nombre nuevo tiene que tener entre 1 y "
            f"{LARGO_MAXIMO_DEL_NOMBRE} caracteres"
        )
    clave = clave_de_nombre(nuevo)
    if clave == clave_de_nombre(anterior):
        raise NombreInvalido(f"Personaje: ya se llama «{anterior}»")
    for otro in otros:
        if clave == clave_de_nombre(otro):
            raise NombreInvalido(f"Personaje: «{otro}» ya es otro personaje de la novela")


def _capitulos_cambiados(conn: Conexion, ids: set[str]) -> tuple[CapituloCambiado, ...]:
    if not ids:
        return ()
    marcas = ", ".join("?" for _ in ids)
    filas = conn.execute(
        f"SELECT id, orden FROM capitulo WHERE id IN ({marcas}) ORDER BY orden", tuple(ids)
    ).fetchall()
    return tuple(CapituloCambiado(fila["id"], int(fila["orden"])) for fila in filas)


def _publicar(
    conn: Conexion,
    volumen_id: str,
    cambiados: tuple[CapituloCambiado, ...],
    anterior: str,
    nuevo: str,
) -> str:
    todos = tuple(
        fila["id"]
        for fila in conn.execute(
            "SELECT id FROM capitulo WHERE volumen_id = ? ORDER BY orden", (volumen_id,)
        ).fetchall()
    )
    return VersionesDeNovela(conn).publicar(
        f"ver-{uuid.uuid4().hex[:12]}",
        volumen_id=volumen_id,
        capitulos=todos,
        cambiados=tuple(c.id for c in cambiados),
        motivo=f"«{anterior}» pasa a llamarse «{nuevo}»",
    )
