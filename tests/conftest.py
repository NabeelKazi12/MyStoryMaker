"""Material compartido por los tests que necesitan una base migrada.

La migracion se ejecuta una vez por sesion sobre una base plantilla y cada test recibe
una copia: migrar en cada test costaba siete segundos por fichero y el tiempo de la suite
es lo que decide si alguien la ejecuta antes de cada commit.
"""

from __future__ import annotations

import os
import shutil
import sqlite3
import subprocess
import sys
from collections.abc import Iterator
from pathlib import Path

import pytest

from backend.store import database

RAIZ = Path(__file__).resolve().parent.parent


@pytest.fixture(scope="session")
def base_plantilla(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """Una base migrada, creada una sola vez, de la que todas las demas se copian."""
    destino = tmp_path_factory.mktemp("plantilla") / "canon.db"
    resultado = subprocess.run(
        [sys.executable, "-m", "alembic", "upgrade", "head"],
        cwd=RAIZ,
        env={**os.environ, "MYSTORYMAKER_DB": str(destino)},
        capture_output=True,
        text=True,
    )
    assert resultado.returncode == 0, resultado.stderr
    return destino


@pytest.fixture
def conn(base_plantilla: Path, tmp_path: Path) -> Iterator[sqlite3.Connection]:
    """Conexion a una copia limpia de la base migrada."""
    copia = tmp_path / "canon.db"
    shutil.copy(base_plantilla, copia)
    conexion = database.abrir(copia)
    try:
        yield conexion
    finally:
        conexion.close()


def material_minimo(conn: sqlite3.Connection) -> None:
    """Un volumen, un capitulo, un personaje, un lugar y una escena validos."""
    conn.execute("INSERT OR IGNORE INTO volumen (id, titulo) VALUES ('vol-1', 'Uno')")
    conn.execute(
        "INSERT OR IGNORE INTO capitulo (id, volumen_id, orden) VALUES ('cap-1', 'vol-1', 1)"
    )
    conn.execute(
        "INSERT OR IGNORE INTO personaje (id, nombre_canonico, relevancia, necesidad_interna) "
        "VALUES ('per-1', 'Irene', 'protagonico', 'dejar de cargar con la culpa')"
    )
    conn.execute(
        "INSERT OR IGNORE INTO lugar (id, nombre_canonico) VALUES ('lug-1', 'El puerto')"
    )
    conn.execute(
        "INSERT OR IGNORE INTO escena (id, capitulo_id, orden, pov_id, lugar_id, "
        "momento_en_historia, objetivo, conflicto, resultado, valor_entrada, valor_salida, "
        "funcion_en_trama, tipo) VALUES ('esc-1', 'cap-1', 1, 'per-1', 'lug-1', 10, "
        "'recuperar la carta', 'el guardia', 'la consigue', 'seguro', 'expuesto', "
        "'complicacion', 'accion')"
    )
