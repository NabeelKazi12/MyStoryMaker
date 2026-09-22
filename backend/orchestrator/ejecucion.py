"""Idempotencia, reanudacion, cancelacion y registro de transiciones.

Lo que este modulo protege es el dinero y la trazabilidad. El estado de ejecucion vive en
SQLite y el proceso del worker no guarda nada: copiar el fichero es copiar el estado, y de
ahi salen la reanudacion y la reproducibilidad (D-04).

Cubre RF-ORQ-13, RF-ORQ-14, RF-ORQ-16, RF-ORQ-17 y RF-ORQ-19.
"""

from __future__ import annotations

from dataclasses import dataclass

from backend.store.database import Conexion


@dataclass(frozen=True)
class ClaveDeTarea:
    """Los seis campos que identifican una ejecucion (`architecture.md` 6.4).

    Dos ejecuciones son la misma cuando coinciden en los seis. No es un identificador
    inventado: si faltara la revision de canon, dos invocaciones contra canones distintos
    se confundirian y el *replay* devolveria un artefacto que nunca se genero con ese
    contexto.
    """

    plan_id: str
    objetivo: str
    revision_de_canon: int
    hash_del_paquete: str
    version_de_prompt: str
    intento: int

    def como_fila(self) -> tuple[str, str, int, str, str, int]:
        return (
            self.plan_id,
            self.objetivo,
            self.revision_de_canon,
            self.hash_del_paquete,
            self.version_de_prompt,
            self.intento,
        )


def artefacto_ya_producido(conn: Conexion, clave: ClaveDeTarea) -> str | None:
    """El artefacto de una ejecucion anterior con la misma clave, si lo hay.

    Devolverlo en lugar de invocar es lo que convierte un reintento del proceso en algo
    gratis. Sin esto, reanudar tras una caida vuelve a pagar todo lo ya pagado.
    """
    fila = conn.execute(
        "SELECT artefacto_id FROM artefacto_de_tarea WHERE plan_id = ? AND objetivo = ? "
        "AND revision_de_canon = ? AND hash_del_paquete = ? AND version_de_prompt = ? "
        "AND intento = ?",
        clave.como_fila(),
    ).fetchone()
    return fila["artefacto_id"] if fila else None


def registrar_artefacto(conn: Conexion, clave: ClaveDeTarea, artefacto_id: str) -> None:
    """Deja la clave apuntando a lo producido, para que la proxima no vuelva a invocar."""
    conn.execute(
        "INSERT OR IGNORE INTO artefacto_de_tarea (plan_id, objetivo, revision_de_canon, "
        "hash_del_paquete, version_de_prompt, intento, artefacto_id, creado_en) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, datetime('now'))",
        (*clave.como_fila(), artefacto_id),
    )


def registrar_transicion(conn: Conexion, tarea_id: str, estado: str) -> None:
    """Emite el evento de una transicion. Es el origen del SSE de RF-API-04.

    Si nadie escribe aqui, el endpoint de eventos existe y no emite nada: el frontend se
    queda mirando un flujo vacio y lo interpreta como «no ha empezado». Por eso la
    transicion y su evento se escriben juntos.
    """
    conn.execute(
        "INSERT INTO tarea_evento (tarea_id, estado, timestamp) VALUES (?, ?, datetime('now'))",
        (tarea_id, estado),
    )
    conn.execute("UPDATE tarea SET estado = ? WHERE id = ?", (estado, tarea_id))


@dataclass(frozen=True)
class Reanudacion:
    """Lo que el arranque encontro y que hizo con ello."""

    devueltas_a_lista: tuple[str, ...]
    pagadas_y_perdidas: tuple[str, ...]


def reanudar_al_arrancar(conn: Conexion) -> Reanudacion:
    """Recupera las tareas que quedaron a medias cuando el proceso cayo.

    Dos casos, y la diferencia importa. Si quedo `en_curso` **sin** `Procedencia`, la
    invocacion no llego a registrarse: vuelve a `lista` y suma un intento. Si la
    `Procedencia` esta y el artefacto no, la invocacion **se pago y se perdio**, y eso
    queda anotado porque es la metrica que revela caidas recurrentes del worker
    (`AGENTS.md` 7.4).
    """
    filas = conn.execute(
        """
        SELECT t.id, (
            SELECT COUNT(*) FROM procedencia p
            JOIN paquete_contexto pq ON pq.id = p.paquete_id
            WHERE pq.tarea_id = t.id
        ) AS procedencias
        FROM tarea t WHERE t.estado = 'en_curso' ORDER BY t.id
        """
    ).fetchall()

    a_lista: list[str] = []
    perdidas: list[str] = []
    for fila in filas:
        if fila["procedencias"] == 0:
            a_lista.append(fila["id"])
        else:
            perdidas.append(fila["id"])
        registrar_transicion(conn, fila["id"], "lista")
        conn.execute(
            "INSERT OR IGNORE INTO tarea_intento (tarea_id, numero, clase_de_fallo, "
            "tipo_de_defecto, timestamp) SELECT ?, COALESCE(MAX(numero), 0) + 1, "
            "'transporte', 'proceso caido', datetime('now') FROM tarea_intento "
            "WHERE tarea_id = ?",
            (fila["id"], fila["id"]),
        )

    return Reanudacion(devueltas_a_lista=tuple(a_lista), pagadas_y_perdidas=tuple(perdidas))


def resultado_obsoleto(conn: Conexion, tarea_id: str, revision_del_paquete: int) -> bool:
    """Si el canon cambio bajo una tarea `en_curso`, su resultado se descarta.

    Aceptarlo «porque esta bien escrito» es exactamente como entra la deriva: la prosa se
    genero contra un mundo que ya no es el vigente.
    """
    fila = conn.execute("SELECT MAX(revision) AS r FROM canon_revision").fetchone()
    return int(fila["r"] or 0) > revision_del_paquete


def cancelar(conn: Conexion, tarea_id: str, subarbol: frozenset[str]) -> tuple[str, ...]:
    """Cancela la tarea y su subarbol. Marca obsoleto lo producido; **no borra nada**.

    Borrar destruiria la unica evidencia de por que se llego hasta ahi. Un artefacto
    obsoleto sigue siendo consultable y sigue contando en las senales.
    """
    afectadas = tuple(sorted({tarea_id, *subarbol}))
    for identificador in afectadas:
        registrar_transicion(conn, identificador, "cancelada")
        conn.execute(
            "UPDATE borrador SET obsoleto = 1 WHERE escena_id = ?",
            (identificador.split(":")[0],),
        )
    return afectadas
