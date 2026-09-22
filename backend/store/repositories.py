"""Repositorios tipados sobre SQLite.

El grafo del dominio se modela relacionalmente y las consultas transitivas se resuelven
con CTEs recursivas dentro de este paquete, no reconstruyendo el grafo en memoria: traerse
todas las aristas para recorrerlas en Python convierte una consulta de indice en un
barrido completo, y deja de funcionar justo cuando el libro crece (`architecture.md` 3.1).

El canon versionado no se copia entero por revision: se guardan eventos de cambio y se
reconstruye. Una copia por revision no escala a 40 capitulos.

Cubre RF-STO-05, RF-STO-07 y RF-STO-08.
"""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass

from backend.domain.diegetic.canon import Hecho, Predicado
from backend.domain.errors import ErrorDeDominio
from backend.domain.vocabularies import ExclusividadDePredicado


@dataclass(frozen=True)
class CatalogoDePredicados:
    """Lectura del catalogo que hace ejecutable la contradiccion de hechos."""

    conn: sqlite3.Connection

    def todos(self) -> tuple[Predicado, ...]:
        filas = self.conn.execute(
            "SELECT nombre, exclusividad, descripcion FROM predicado ORDER BY nombre"
        ).fetchall()
        return tuple(
            Predicado(
                nombre=fila["nombre"],
                exclusividad=ExclusividadDePredicado(fila["exclusividad"]),
                descripcion=fila["descripcion"],
            )
            for fila in filas
        )

    def exclusividad_de(self, nombre: str) -> ExclusividadDePredicado:
        """Exclusividad declarada de un predicado. Uno no catalogado es un error.

        Se rechaza aqui y no al insertar para que el mensaje diga que hay que catalogarlo,
        en vez de dejar que aflore como una violacion de clave foranea.
        """
        fila = self.conn.execute(
            "SELECT exclusividad FROM predicado WHERE nombre = ?", (nombre,)
        ).fetchone()
        if fila is None:
            raise ErrorDeDominio(
                "Predicado",
                "todo predicado usado por un Hecho esta en el catalogo",
                f"nombre={nombre!r}; anadirlo exige un RegistroDeDecision y una migracion",
            )
        return ExclusividadDePredicado(fila["exclusividad"])

    def es_funcional(self, nombre: str) -> bool:
        """Un predicado funcional admite a lo sumo un valor vigente por sujeto."""
        return self.exclusividad_de(nombre) is ExclusividadDePredicado.FUNCIONAL


@dataclass(frozen=True)
class GrafoCausal:
    """Consultas transitivas sobre `evento_causa`, resueltas con CTE recursiva."""

    conn: sqlite3.Connection

    def alcanzables_desde(self, evento_id: str) -> frozenset[str]:
        """Todos los eventos que un evento causa, directa o indirectamente."""
        filas = self.conn.execute(
            """
            WITH RECURSIVE alcanzable(id) AS (
                SELECT efecto_id FROM evento_causa WHERE causa_id = ?
                UNION
                SELECT ec.efecto_id
                FROM evento_causa ec
                JOIN alcanzable a ON ec.causa_id = a.id
            )
            SELECT id FROM alcanzable
            """,
            (evento_id,),
        ).fetchall()
        return frozenset(fila["id"] for fila in filas)

    def ciclos(self) -> tuple[str, ...]:
        """Eventos que se alcanzan a si mismos. Un grafo causal con ciclos no es causal."""
        filas = self.conn.execute(
            """
            WITH RECURSIVE alcanzable(origen, id) AS (
                SELECT causa_id, efecto_id FROM evento_causa
                UNION
                SELECT a.origen, ec.efecto_id
                FROM evento_causa ec
                JOIN alcanzable a ON ec.causa_id = a.id
            )
            SELECT DISTINCT origen FROM alcanzable WHERE origen = id ORDER BY origen
            """
        ).fetchall()
        return tuple(fila["origen"] for fila in filas)

    def precedencias_violadas(self) -> tuple[tuple[str, str], ...]:
        """Pares (causa, efecto) en los que la causa no precede al efecto en la historia.

        Es el invariante 2 de `definitions.md`: si A causa B, A precede a B en tiempo de
        historia. Se comprueba sobre las aristas directas; los ciclos los cubre `ciclos`.
        """
        filas = self.conn.execute(
            """
            SELECT ec.causa_id, ec.efecto_id
            FROM evento_causa ec
            JOIN evento causa ON causa.id = ec.causa_id
            JOIN evento efecto ON efecto.id = ec.efecto_id
            WHERE causa.posicion_en_historia >= efecto.posicion_en_historia
            ORDER BY ec.causa_id, ec.efecto_id
            """
        ).fetchall()
        return tuple((fila["causa_id"], fila["efecto_id"]) for fila in filas)


@dataclass(frozen=True)
class CanonVersionado:
    """Revisiones del canon reconstruidas desde eventos de cambio.

    Cada canonizacion escribe sus cambios y sube la revision. Reconstruir la revision N
    es plegar los cambios de 0 a N, no leer una copia guardada.
    """

    conn: sqlite3.Connection

    def revision_actual(self) -> int:
        fila = self.conn.execute("SELECT MAX(revision) AS r FROM canon_revision").fetchone()
        return int(fila["r"] or 0)

    def abrir_revision(self, motivo: str = "") -> int:
        """Incrementa la revision. Solo la canonizacion deberia llamar a esto."""
        siguiente = self.revision_actual() + 1
        self.conn.execute(
            "INSERT INTO canon_revision (revision, creada_en, motivo) "
            "VALUES (?, datetime('now'), ?)",
            (siguiente, motivo),
        )
        return siguiente

    def registrar_insercion(self, revision: int, hecho: Hecho) -> None:
        """Deja constancia de que un hecho entro en el canon en esa revision."""
        self.conn.execute(
            "INSERT INTO canon_cambio (revision, tabla, fila_id, operacion, datos) "
            "VALUES (?, 'hecho', ?, 'insertar', ?)",
            (revision, hecho.id, hecho.valido_desde),
        )

    def registrar_cierre(self, revision: int, hecho_id: str, valido_hasta: str) -> None:
        """Deja constancia de que un intervalo se cerro en esa revision."""
        self.conn.execute(
            "INSERT INTO canon_cambio (revision, tabla, fila_id, operacion, datos) "
            "VALUES (?, 'hecho', ?, 'cerrar_intervalo', ?)",
            (revision, hecho_id, valido_hasta),
        )

    def hechos_vigentes_en(self, revision: int) -> frozenset[str]:
        """Que hechos estaban vigentes en la revision N.

        Responde a «que era verdad en el capitulo 12» sin guardar una copia del canon por
        capitulo, que es lo que RF-STO-05 exige.
        """
        filas = self.conn.execute(
            """
            SELECT fila_id, operacion
            FROM canon_cambio
            WHERE tabla = 'hecho' AND revision <= ?
            ORDER BY id
            """,
            (revision,),
        ).fetchall()

        vigentes: set[str] = set()
        for fila in filas:
            if fila["operacion"] == "insertar":
                vigentes.add(fila["fila_id"])
            else:
                vigentes.discard(fila["fila_id"])
        return frozenset(vigentes)
