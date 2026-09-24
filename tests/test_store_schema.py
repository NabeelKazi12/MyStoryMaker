"""La migracion inicial deja la base utilizable, y toda conexion trae sus garantias.

Cubre RF-STO-01, RF-STO-02, RF-STO-03, RF-STO-09 y RF-STO-10.
"""

from __future__ import annotations

import sqlite3
import subprocess
import sys
from collections.abc import Iterator
from pathlib import Path

import pytest

from backend.store import database

RAIZ = Path(__file__).resolve().parent.parent


@pytest.fixture(scope="module")
def base_migrada(tmp_path_factory: pytest.TempPathFactory) -> Iterator[Path]:
    """Base vacia, migracion, esquema esperado. Es el recorrido de RF-STO-02."""
    destino = tmp_path_factory.mktemp("canon") / "canon.db"
    resultado = subprocess.run(
        [sys.executable, "-m", "alembic", "upgrade", "head"],
        cwd=RAIZ,
        env={**_entorno(), "MYSTORYMAKER_DB": str(destino)},
        capture_output=True,
        text=True,
    )
    assert resultado.returncode == 0, resultado.stderr
    yield destino


def _entorno() -> dict[str, str]:
    import os

    return dict(os.environ)


def _conexion(ruta: Path) -> sqlite3.Connection:
    return database.abrir(ruta)


# --- RF-STO-02: la migracion crea el esquema, no el arranque ------------------------


@pytest.mark.invariants
def test_la_migracion_sella_su_version(base_migrada: Path) -> None:
    """Un `upgrade head` que termina con codigo 0 y sin sellar no ha migrado nada.

    Es el fallo que costo encontrar la primera vez: el DDL sobrevivia porque SQLite lo
    autoconfirma, mientras el sello y las filas sembradas se perdian al cerrar.
    """
    with _conexion(base_migrada) as conn:
        sellada = conn.execute("SELECT version_num FROM alembic_version").fetchall()
    # La cabeza avanza con cada migracion encadenada; hoy es 0004 (SPEC-004, fase A).
    assert [fila[0] for fila in sellada] == ["0004"]


@pytest.mark.invariants
def test_estan_las_tablas_del_modelo_de_datos(base_migrada: Path) -> None:
    """Las tablas de SPEC-001 5.1 y 5.2, una por una."""
    esperadas = {
        "brief",
        "volumen",
        "capitulo",
        "escena",
        "personaje",
        "lugar",
        "evento",
        "hecho",
        "predicado",
        "hilo",
        "siembra_pago",
        "perfil_estilo",
        "escena_evento",
        "escena_hilo",
        "evento_participante",
        "evento_causa",
        "canon_revision",
        "canon_cambio",
        "borrador",
        "hecho_detectado",
        "defecto",
        "plan",
        "tarea",
        "tarea_intento",
        "tarea_dependencia",
        "tarea_evento",
        "puerta",
        "paquete_contexto",
        "procedencia",
        "registro_decision",
    }
    with _conexion(base_migrada) as conn:
        presentes = {
            fila[0]
            for fila in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")
        }
    assert esperadas <= presentes, f"faltan tablas: {sorted(esperadas - presentes)}"


@pytest.mark.invariants
def test_estan_los_indices_obligatorios(base_migrada: Path) -> None:
    """RF-STO-03: las validaciones mas frecuentes del sistema no pueden ir a barrido."""
    with _conexion(base_migrada) as conn:
        indices = {
            fila[0]
            for fila in conn.execute("SELECT name FROM sqlite_master WHERE type='index'")
        }
    assert "ix_hecho_sujeto_predicado" in indices
    assert "ix_evento_posicion_en_historia" in indices


# --- RF-STO-10: el catalogo no nace vacio -------------------------------------------


@pytest.mark.invariants
def test_el_catalogo_de_predicados_viene_sembrado(base_migrada: Path) -> None:
    """Con el catalogo vacio, RF-STO-07 rechazaria toda canonizacion y el bucle no cierra."""
    with _conexion(base_migrada) as conn:
        filas = dict(conn.execute("SELECT nombre, exclusividad FROM predicado").fetchall())

    assert len(filas) == 9
    for dimension in ("salud", "ubicacion", "lealtad", "emocion", "recursos", "reputacion"):
        assert filas[dimension] == "funcional"
    assert filas["posee"] == "multivalor"


@pytest.mark.invariants
def test_un_predicado_no_catalogado_se_rechaza(base_migrada: Path) -> None:
    """RF-STO-07, en el esquema: la clave foranea lo impide antes que ningun verificador."""
    with _conexion(base_migrada) as conn:
        conn.execute(
            "INSERT INTO evento (id, descripcion, posicion_en_historia, tipo) "
            "VALUES ('ev-1', 'la carta cambia de manos', 10, 'accion')"
        )
        with pytest.raises(sqlite3.IntegrityError):
            conn.execute(
                "INSERT INTO hecho (id, sujeto_id, predicado, objeto, valido_desde) "
                "VALUES ('h-1', 'per-1', 'predicado_inventado', 'x', 'ev-1')"
            )
        conn.rollback()


# --- RF-STO-01: toda conexion trae sus PRAGMA ---------------------------------------


@pytest.mark.invariants
def test_toda_conexion_lleva_wal_y_claves_foraneas(base_migrada: Path) -> None:
    """Si los PRAGMA se ponen en un solo sitio, no hay forma de olvidarlos en el segundo."""
    with _conexion(base_migrada) as conn:
        assert conn.execute("PRAGMA journal_mode").fetchone()[0].lower() == "wal"
        assert conn.execute("PRAGMA foreign_keys").fetchone()[0] == 1


# --- RF-STO-09: el canon no admite prosa --------------------------------------------


@pytest.mark.invariants
def test_solo_borrador_tiene_texto_largo(base_migrada: Path) -> None:
    """El canon es estructura consultable; la prosa vive en una sola tabla."""
    tablas_de_canon = (
        "brief",
        "volumen",
        "capitulo",
        "escena",
        "personaje",
        "lugar",
        "evento",
        "hecho",
        "predicado",
        "hilo",
        "siembra_pago",
        "perfil_estilo",
    )
    with _conexion(base_migrada) as conn:
        for tabla in tablas_de_canon:
            columnas = {fila[1] for fila in conn.execute(f"PRAGMA table_info({tabla})")}
            assert "texto" not in columnas, f"{tabla} admite prosa y no deberia"

        columnas_borrador = {fila[1] for fila in conn.execute("PRAGMA table_info(borrador)")}
    assert "texto" in columnas_borrador


# --- invariantes que el esquema tambien cobra ----------------------------------------


@pytest.mark.invariants
def test_el_esquema_rechaza_escena_sin_cambio_de_valor(base_migrada: Path) -> None:
    """RF-DOM-04 tambien en la base: una escritura directa no puede esquivar el dominio."""
    with _conexion(base_migrada) as conn:
        _material_minimo(conn)
        with pytest.raises(sqlite3.IntegrityError):
            conn.execute(
                "INSERT INTO escena (id, capitulo_id, orden, pov_id, lugar_id, "
                "momento_en_historia, objetivo, conflicto, resultado, valor_entrada, "
                "valor_salida, funcion_en_trama, tipo) VALUES "
                "('esc-x', 'cap-1', 9, 'per-1', 'lug-1', 10, 'o', 'c', 'r', "
                "'igual', 'igual', 'giro', 'accion')"
            )
        conn.rollback()


@pytest.mark.invariants
def test_el_esquema_admite_un_solo_borrador_aceptado_por_escena(base_migrada: Path) -> None:
    """RF-QUA-05 tiene aqui su red de seguridad: un indice unico parcial."""
    with _conexion(base_migrada) as conn:
        _material_minimo(conn)
        conn.execute(
            "INSERT INTO borrador (id, escena_id, version, texto, estado) "
            "VALUES ('bo-1', 'esc-1', 1, 'prosa', 'aceptado')"
        )
        with pytest.raises(sqlite3.IntegrityError):
            conn.execute(
                "INSERT INTO borrador (id, escena_id, version, texto, estado) "
                "VALUES ('bo-2', 'esc-1', 2, 'otra prosa', 'aceptado')"
            )
        conn.rollback()


def _material_minimo(conn: sqlite3.Connection) -> None:
    """Un capitulo, un personaje, un lugar y una escena validos sobre los que probar."""
    conn.execute("INSERT OR IGNORE INTO volumen (id, titulo) VALUES ('vol-1', 'Uno')")
    conn.execute(
        "INSERT OR IGNORE INTO capitulo (id, volumen_id, orden) VALUES ('cap-1', 'vol-1', 1)"
    )
    conn.execute(
        "INSERT OR IGNORE INTO personaje (id, nombre_canonico) VALUES ('per-1', 'Irene')"
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


# --- SPEC-003 A-03: las siete tablas de la memoria del regalo ------------------------

TABLAS_DE_0002 = (
    "destinatario",
    "elemento_personalizado",
    "hecho_capitulo",
    "resumen_capitulo",
    "checkpoint_capitulo",
    "lista_prohibida",
    "audit_log",
    "version_novela",
    "version_capitulo",
)


@pytest.mark.invariants
def test_migracion_0002_crea_las_tablas_de_la_memoria_del_regalo(base_migrada: Path) -> None:
    """Sin ellas, cinco de las siete areas del alcance no tienen donde escribir."""
    with sqlite3.connect(base_migrada) as conn:
        presentes = {
            fila[0]
            for fila in conn.execute("SELECT name FROM sqlite_master WHERE type = 'table'")
        }

    assert set(TABLAS_DE_0002) <= presentes


@pytest.mark.invariants
def test_la_cronologia_es_una_vista_y_no_una_copia(base_migrada: Path) -> None:
    """Una cronologia duplicada diverge del canon en cuanto alguien edita un evento.

    Se comprueba que `evento_cronologia` existe como vista, no como tabla: si algun dia
    alguien la convierte en tabla, este test lo dice antes de que las dos copias empiecen
    a discrepar en silencio.
    """
    with sqlite3.connect(base_migrada) as conn:
        fila = conn.execute(
            "SELECT type FROM sqlite_master WHERE name = 'evento_cronologia'"
        ).fetchone()

    assert fila is not None, "la cronologia de RF-BIB-02 no existe"
    assert fila[0] == "view"


@pytest.mark.invariants
def test_un_hecho_registra_los_capitulos_en_que_se_usa(base_migrada: Path) -> None:
    """RF-BIB-01. Es la precondicion de la regeneracion selectiva de RF-LEC-05.

    Sin saber que capitulos usan un hecho, cambiar ese hecho obliga a regenerar la novela
    entera, que es justo lo que el alcance pide no hacer.
    """
    with sqlite3.connect(base_migrada) as conn:
        columnas = {fila[1] for fila in conn.execute("PRAGMA table_info(hecho_capitulo)")}
        claves = [fila for fila in conn.execute("PRAGMA foreign_key_list(hecho_capitulo)")]

    assert {"hecho_id", "capitulo_id"} <= columnas
    # Solo el capitulo tiene clave foranea: la identidad de un hecho vive en el canon
    # versionado (`canon_cambio`), no en una fila de `hecho`, asi que exigirla haria
    # fallar toda canonizacion.
    assert {fila[2] for fila in claves} == {"capitulo"}


@pytest.mark.invariants
def test_las_listas_prohibidas_tienen_sus_tres_niveles(base_migrada: Path) -> None:
    """RF-GRD-01: global, por novela y las que declara el cliente en la entrevista."""
    with sqlite3.connect(base_migrada) as conn:
        conn.execute(
            "INSERT INTO lista_prohibida (id, nivel, termino) VALUES ('lp-1', 'global', 'x')"
        )
        with pytest.raises(sqlite3.IntegrityError):
            conn.execute(
                "INSERT INTO lista_prohibida (id, nivel, termino) "
                "VALUES ('lp-2', 'inventado', 'y')"
            )
        conn.rollback()


@pytest.mark.invariants
def test_una_version_de_novela_conserva_la_anterior(base_migrada: Path) -> None:
    """RF-LEC-07. La version anterior no se sobrescribe: se encadena."""
    with sqlite3.connect(base_migrada) as conn:
        columnas = {fila[1] for fila in conn.execute("PRAGMA table_info(version_novela)")}
        cambiados = {fila[1] for fila in conn.execute("PRAGMA table_info(version_capitulo)")}

    assert {"numero", "anterior_id", "publicada_en"} <= columnas
    assert {"version_id", "capitulo_id", "cambiado"} <= cambiados


@pytest.mark.invariants
def test_un_volumen_sabe_de_que_brief_es(base_migrada: Path) -> None:
    """Sin esta columna, «quién es el destinatario de esta novela» no tiene respuesta.

    La consulta acababa adivinándolo por parecido del título, que es la clase de atajo
    que funciona en la demo y falla con dos novelas parecidas.
    """
    with sqlite3.connect(base_migrada) as conn:
        columnas = {fila[1] for fila in conn.execute("PRAGMA table_info(volumen)")}
        claves = {fila[2] for fila in conn.execute("PRAGMA foreign_key_list(volumen)")}

    assert "brief_id" in columnas
    assert "brief" in claves


def test_una_conexion_se_puede_cerrar_desde_otro_hilo(tmp_path: Path) -> None:
    """H-1 de SPEC-005: FastAPI abre la conexion en un hilo y la cierra en otro."""
    import threading

    conexion = database.abrir(tmp_path / "hilos.db")
    fallos: list[BaseException] = []

    def usar_y_cerrar() -> None:
        try:
            conexion.execute("SELECT 1").fetchone()
            conexion.commit()
            conexion.close()
        except BaseException as error:  # noqa: BLE001 - se comprueba abajo
            fallos.append(error)

    hilo = threading.Thread(target=usar_y_cerrar)
    hilo.start()
    hilo.join()
    assert fallos == []
