"""La biblioteca: todas las novelas, con lo que hace falta para elegir cual abrir.

Vive en `orchestrator/` porque no calcula nada propio: junta el progreso de SPEC-004 y la
aprobacion de SPEC-007, que ya viven aqui, con la portada y las versiones del almacen. Si
la biblioteca calculara su propio estado, acabaria diciendo «escrita» de una novela que
la lectura da por detenida (SPEC-008 RF-CON-05).

Es de solo lectura: no encola, no escribe y no registra nada (RF-BIB-04).

Cubre RF-BIB-01 a RF-BIB-03.
"""

from __future__ import annotations

from dataclasses import dataclass

from backend.orchestrator.aprobacion import vigente
from backend.orchestrator.escritura import progreso
from backend.store.database import Conexion
from backend.store.escritura import TextoDeLaNovela
from backend.store.repositories import Aprobacion


@dataclass(frozen=True)
class NovelaDeBiblioteca:
    volumen_id: str
    titulo: str
    destinatario: str
    estado: str
    detalle: str
    capitulos: int
    palabras: int
    ultima_version_en: str | None
    aprobacion: Aprobacion | None


def biblioteca(conn: Conexion) -> tuple[NovelaDeBiblioteca, ...]:
    """Todas las novelas, de la creada mas recientemente a la mas antigua.

    El orden es el de insercion (`rowid`): `volumen` no tiene fecha de creacion y anadirla
    exigiria una migracion que SPEC-008 N-04 descarta.
    """
    filas = conn.execute(
        """
        SELECT v.id, v.titulo,
               COALESCE((SELECT d.nombre FROM destinatario d
                          WHERE d.brief_id = v.brief_id LIMIT 1), '') AS destinatario,
               (SELECT COUNT(*) FROM capitulo c WHERE c.volumen_id = v.id) AS capitulos,
               (SELECT MAX(publicada_en) FROM version_novela n
                 WHERE n.volumen_id = v.id) AS ultima_version_en
        FROM volumen v
        -- Una novela retirada no se lista (SPEC-009 RF-ELI-06).
        WHERE v.eliminada_en IS NULL
        ORDER BY v.rowid DESC
        """
    ).fetchall()
    texto = TextoDeLaNovela(conn)
    novelas = []
    for fila in filas:
        estado = progreso(conn, fila["id"])
        novelas.append(
            NovelaDeBiblioteca(
                volumen_id=fila["id"],
                titulo=fila["titulo"],
                destinatario=fila["destinatario"],
                estado=estado.estado,
                detalle=estado.detalle,
                capitulos=int(fila["capitulos"]),
                palabras=sum(c.palabras for c in texto.por_capitulos(fila["id"])),
                ultima_version_en=fila["ultima_version_en"],
                aprobacion=vigente(conn, fila["id"]),
            )
        )
    return tuple(novelas)
