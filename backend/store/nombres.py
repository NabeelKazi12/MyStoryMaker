"""Los textos de una novela que llevan nombres, para cambiar uno en todos a la vez.

El nombre de un personaje vive copiado en el canon, el esqueleto, los resumenes, el
encargo y la prosa. Este modulo sabe donde esta cada copia y la reescribe con la
sustitucion que le pasen; no decide cual ni si se puede (eso es `orchestrator/renombrar`).

Todo va acotado a **una** novela: la base guarda varias, y un cambio de nombre en la de
Marta no puede tocar un «Luis» de la de Ana.

Cubre RF-NOM-10 y RF-NOM-11.
"""

from __future__ import annotations

import sqlite3
from collections.abc import Callable
from dataclasses import dataclass

_CAPITULOS = "SELECT id FROM capitulo WHERE volumen_id = :v"
_ESCENAS = f"SELECT id FROM escena WHERE capitulo_id IN ({_CAPITULOS})"
_PERSONAJES = f"""
    SELECT p.id FROM personaje p JOIN escena e ON e.pov_id = p.id
    WHERE e.id IN ({_ESCENAS})
    UNION
    SELECT ep.entidad_id FROM evento_participante ep
    JOIN escena_evento se ON se.evento_id = ep.evento_id
    WHERE se.escena_id IN ({_ESCENAS})
"""


@dataclass(frozen=True)
class TextoCambiado:
    """Una fila del canon cuyo texto cambio, para registrarla como evento `renombrar`."""

    tabla: str
    fila_id: str
    antes: str
    despues: str


@dataclass(frozen=True)
class ProsaCambiada:
    escena_id: str
    capitulo_id: str
    borrador_id: str


@dataclass(frozen=True)
class TextosDeLaNovela:
    conn: sqlite3.Connection

    def personajes(self, volumen_id: str) -> dict[str, str]:
        """Los personajes que salen en la novela, por id, con su nombre canonico.

        Salir es lo mismo que para la ficha de la lectura: ser POV de una escena o
        participar en un evento que una escena renderiza.
        """
        filas = self.conn.execute(
            f"SELECT id, nombre_canonico FROM personaje WHERE id IN ({_PERSONAJES})",
            {"v": volumen_id},
        ).fetchall()
        return {fila["id"]: fila["nombre_canonico"] for fila in filas}

    def destinataria(self, volumen_id: str) -> str | None:
        fila = self.conn.execute(
            "SELECT d.nombre FROM destinatario d JOIN volumen v ON v.brief_id = d.brief_id "
            "WHERE v.id = ? LIMIT 1",
            (volumen_id,),
        ).fetchone()
        return None if fila is None else str(fila["nombre"])

    def sustituir(
        self, volumen_id: str, personaje_id: str, aplicar: Callable[[str], str]
    ) -> tuple[tuple[TextoCambiado, ...], tuple[ProsaCambiada, ...]]:
        """Reescribe cada copia del nombre en la novela. No abre ni cierra transaccion.

        Devuelve las filas de canon cambiadas y las escenas cuya prosa cambio. La prosa no
        se sobrescribe: cada escena tocada recibe un borrador nuevo y el anterior queda
        obsoleto, conservado.
        """
        canon: list[TextoCambiado] = []
        nombre = self.conn.execute(
            "SELECT nombre_canonico FROM personaje WHERE id = ?", (personaje_id,)
        ).fetchone()["nombre_canonico"]
        nuevo = aplicar(nombre)
        self.conn.execute(
            "UPDATE personaje SET nombre_canonico = ? WHERE id = ?", (nuevo, personaje_id)
        )
        canon.append(TextoCambiado("personaje", personaje_id, nombre, nuevo))

        hechos = self.conn.execute(
            f"""
            SELECT id, objeto FROM hecho
            WHERE sujeto_id IN ({_PERSONAJES})
               OR id IN (SELECT hecho_id FROM hecho_capitulo
                         WHERE capitulo_id IN ({_CAPITULOS}))
            """,
            {"v": volumen_id},
        ).fetchall()
        for hecho in hechos:
            despues = aplicar(hecho["objeto"])
            if despues != hecho["objeto"]:
                self.conn.execute(
                    "UPDATE hecho SET objeto = ? WHERE id = ?", (despues, hecho["id"])
                )
                canon.append(TextoCambiado("hecho", hecho["id"], hecho["objeto"], despues))

        self._columnas(
            "personaje_declarado",
            ("nombre",),
            "brief_id = (SELECT brief_id FROM volumen WHERE id = :v)",
            volumen_id,
            aplicar,
        )
        self._columnas(
            "evento",
            ("descripcion",),
            f"id IN (SELECT evento_id FROM escena_evento WHERE escena_id IN ({_ESCENAS}))",
            volumen_id,
            aplicar,
        )
        self._columnas(
            "escena",
            ("objetivo", "conflicto", "resultado"),
            f"id IN ({_ESCENAS})",
            volumen_id,
            aplicar,
        )
        self._columnas("capitulo", ("titulo",), f"id IN ({_CAPITULOS})", volumen_id, aplicar)
        self._columnas(
            "resumen_capitulo",
            ("texto",),
            f"capitulo_id IN ({_CAPITULOS})",
            volumen_id,
            aplicar,
            clave="capitulo_id",
        )
        return tuple(canon), self._prosa(volumen_id, aplicar)

    # --- piezas ----------------------------------------------------------------------

    def _columnas(
        self,
        tabla: str,
        columnas: tuple[str, ...],
        donde: str,
        volumen_id: str,
        aplicar: Callable[[str], str],
        *,
        clave: str = "id",
    ) -> None:
        filas = self.conn.execute(
            f"SELECT {clave} AS clave, {', '.join(columnas)} FROM {tabla} WHERE {donde}",
            {"v": volumen_id},
        ).fetchall()
        for fila in filas:
            nuevos = {c: aplicar(fila[c]) if fila[c] else fila[c] for c in columnas}
            if any(nuevos[c] != fila[c] for c in columnas):
                asignacion = ", ".join(f"{c} = :{c}" for c in columnas)
                self.conn.execute(
                    f"UPDATE {tabla} SET {asignacion} WHERE {clave} = :clave",
                    {**nuevos, "clave": fila["clave"]},
                )

    def _prosa(
        self, volumen_id: str, aplicar: Callable[[str], str]
    ) -> tuple[ProsaCambiada, ...]:
        """El ultimo borrador no obsoleto de cada escena: el que sirve la lectura."""
        filas = self.conn.execute(
            f"""
            SELECT b.id, b.escena_id, b.version, b.texto, b.estado, b.procedencia_id,
                   e.capitulo_id
            FROM borrador b JOIN escena e ON e.id = b.escena_id
            WHERE b.obsoleto = 0 AND e.id IN ({_ESCENAS})
              AND b.version = (SELECT MAX(version) FROM borrador
                               WHERE escena_id = b.escena_id AND obsoleto = 0)
            ORDER BY e.capitulo_id, e.orden
            """,
            {"v": volumen_id},
        ).fetchall()
        cambiadas: list[ProsaCambiada] = []
        for fila in filas:
            texto = aplicar(fila["texto"])
            if texto == fila["texto"]:
                continue
            version = (
                int(
                    self.conn.execute(
                        "SELECT MAX(version) FROM borrador WHERE escena_id = ?",
                        (fila["escena_id"],),
                    ).fetchone()[0]
                )
                + 1
            )
            borrador_id = f"bo-{fila['escena_id']}-v{version}"
            self.conn.execute("UPDATE borrador SET obsoleto = 1 WHERE id = ?", (fila["id"],))
            self.conn.execute(
                "INSERT INTO borrador (id, escena_id, version, texto, estado, "
                "recuento_palabras, procedencia_id) VALUES (?, ?, ?, ?, ?, ?, ?)",
                (
                    borrador_id,
                    fila["escena_id"],
                    version,
                    texto,
                    fila["estado"],
                    len(texto.split()),
                    fila["procedencia_id"],
                ),
            )
            cambiadas.append(ProsaCambiada(fila["escena_id"], fila["capitulo_id"], borrador_id))
        return tuple(cambiadas)
