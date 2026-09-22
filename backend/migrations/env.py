"""Entorno de Alembic.

La URL sale de `backend.store.database`, para que el fichero de la base sea el mismo que
usa el resto del sistema y no haya dos verdades sobre donde vive el canon.
"""

from __future__ import annotations

from alembic import context
from sqlalchemy import create_engine

from backend.store.database import url_de_la_base

config = context.config


def run_migrations_offline() -> None:
    """Genera el SQL sin conectarse."""
    context.configure(url=url_de_la_base(), literal_binds=True)
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Aplica las migraciones contra el fichero real."""
    engine = create_engine(url_de_la_base())
    with engine.connect() as connection:
        # Las mismas garantias que exige RF-STO-01 en cualquier conexion.
        connection.exec_driver_sql("PRAGMA journal_mode=WAL")
        connection.exec_driver_sql("PRAGMA foreign_keys=ON")
        context.configure(connection=connection)
        with context.begin_transaction():
            context.run_migrations()
        # SQLAlchemy 2.0 descarta la transaccion al cerrar la conexion si nadie la
        # confirma. Sin este commit, `alembic upgrade head` termina con codigo 0 y la
        # base se queda sin el sello de version ni las filas sembradas: el DDL sobrevive
        # solo porque SQLite lo autoconfirma, y el fallo no da la cara hasta mucho despues.
        connection.commit()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
