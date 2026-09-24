"""Los personajes declarados de cada encargo (SPEC-011).

Capa de especificacion, no canon: aqui vive lo que quien encarga dijo de los personajes,
y la apertura lo lee para cobrarlo. Se reemplaza entera —no fila a fila— porque el orden
es parte del dato: la destinataria va primera y los demas en el orden en que se dijeron.
"""

from __future__ import annotations

import sqlite3
from collections.abc import Sequence
from dataclasses import dataclass

from backend.domain.spec.encargo import PersonajeDeclarado
from backend.domain.vocabularies import Relevancia


@dataclass(frozen=True)
class PersonajesDeclarados:
    conn: sqlite3.Connection

    def de_brief(self, brief_id: str) -> tuple[PersonajeDeclarado, ...]:
        filas = self.conn.execute(
            "SELECT id, nombre, papel, relacion, descripcion, es_destinatario "
            "FROM personaje_declarado WHERE brief_id = ? ORDER BY orden",
            (brief_id,),
        ).fetchall()
        return tuple(
            PersonajeDeclarado(
                id=f["id"],
                nombre=f["nombre"],
                papel=Relevancia(f["papel"]),
                relacion=f["relacion"],
                descripcion=f["descripcion"],
                es_destinatario=bool(f["es_destinatario"]),
            )
            for f in filas
        )

    def reemplazar(self, brief_id: str, personajes: Sequence[PersonajeDeclarado]) -> None:
        self.conn.execute("DELETE FROM personaje_declarado WHERE brief_id = ?", (brief_id,))
        for orden, personaje in enumerate(personajes, start=1):
            self.conn.execute(
                "INSERT INTO personaje_declarado (id, brief_id, orden, nombre, papel, "
                "relacion, descripcion, es_destinatario) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    f"{brief_id}-personaje-{orden}",
                    brief_id,
                    orden,
                    personaje.nombre.strip(),
                    personaje.papel.value,
                    personaje.relacion.strip(),
                    personaje.descripcion.strip(),
                    1 if personaje.es_destinatario else 0,
                ),
            )
