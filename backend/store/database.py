"""Acceso a SQLite. Unico punto del sistema que abre una conexion.

Toda conexion lleva `journal_mode=WAL` y `foreign_keys=ON`, sin excepcion: sin WAL las
lecturas bloquean al escritor, y sin claves foraneas el canon admite huerfanos que
ningun verificador busca porque da por hecho que no existen (`architecture.md` 3.1).

Cubre RF-STO-01 y RF-STO-04.
"""

from __future__ import annotations

import os
import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

# Una novela por proceso, una sola persona autora (supuesto S-1).
VARIABLE_DE_ENTORNO = "MYSTORYMAKER_DB"
RUTA_POR_DEFECTO = Path("mystorymaker.db")


def ruta_de_la_base(explicita: str | os.PathLike[str] | None = None) -> Path:
    """Ruta del fichero SQLite: la explicita, la del entorno o la de por defecto."""
    if explicita is not None:
        return Path(explicita)
    del_entorno = os.environ.get(VARIABLE_DE_ENTORNO)
    return Path(del_entorno) if del_entorno else RUTA_POR_DEFECTO


def url_de_la_base(explicita: str | os.PathLike[str] | None = None) -> str:
    """La misma ruta en la forma que Alembic espera."""
    return f"sqlite:///{ruta_de_la_base(explicita)}"


def abrir(explicita: str | os.PathLike[str] | None = None) -> sqlite3.Connection:
    """Abre una conexion ya configurada.

    Ninguna otra funcion del sistema debe llamar a `sqlite3.connect`: si los PRAGMA se
    ponen en un solo sitio, no hay forma de olvidarlos en el segundo.
    """
    conexion = sqlite3.connect(ruta_de_la_base(explicita))
    conexion.row_factory = sqlite3.Row
    conexion.execute("PRAGMA journal_mode=WAL")
    conexion.execute("PRAGMA foreign_keys=ON")
    return conexion


@contextmanager
def conexion(explicita: str | os.PathLike[str] | None = None) -> Iterator[sqlite3.Connection]:
    """Conexion con cierre garantizado y transaccion explicita.

    El artefacto y la transicion de estado que lo acompana se escriben dentro del mismo
    `with`: separarlos produce borradores huerfanos y tareas que parecen pendientes con
    el trabajo ya hecho (RF-STO-06).
    """
    conn = abrir(explicita)
    try:
        yield conn
        conn.commit()
    except BaseException:
        conn.rollback()
        raise
    finally:
        conn.close()
