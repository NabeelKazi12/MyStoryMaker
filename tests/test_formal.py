"""El generador del fichero Lean y la correspondencia con la especificacion TLA+.

SPEC-003, fase F. Cubre RF-LEAN-01, RF-LEAN-02, RF-TLA-01 y RF-TLA-05.

Lo que se comprueba aqui es la **generacion**, no la demostracion: que el fichero Lean
refleje la cronologia que hay en SQLite. Que los invariantes se cumplan lo dice `lake
build`, y eso corre en la tuberia, no en la suite de Python.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from backend.formal.lean import (
    RAIZ_LEAN,
    generar_cronologia_lean,
    incoherencias_detectables,
)
from backend.store.repositories import StoryBible

RAIZ = Path(__file__).resolve().parent.parent


def _cronologia(conn: sqlite3.Connection) -> None:
    conn.executescript(
        """
        INSERT INTO lugar (id, nombre_canonico) VALUES ('lu-1', 'Gijon');
        INSERT INTO lugar (id, nombre_canonico) VALUES ('lu-2', 'Madrid');
        INSERT INTO personaje (id, nombre_canonico, anio_de_nacimiento)
            VALUES ('pe-1', 'Marta', 1990);
        INSERT INTO evento (id, descripcion, posicion_en_historia, tipo, momento, lugar_id)
            VALUES ('ev-1', 'aprende a nadar', 10, 'accion', 1998, 'lu-1');
        INSERT INTO evento (id, descripcion, posicion_en_historia, tipo, momento, lugar_id)
            VALUES ('ev-2', 'se muda', 20, 'accion', 2008, 'lu-2');
        INSERT INTO evento_participante (evento_id, entidad_id, rol_en_evento)
            VALUES ('ev-1', 'pe-1', 'agente');
        INSERT INTO evento_participante (evento_id, entidad_id, rol_en_evento)
            VALUES ('ev-2', 'pe-1', 'agente');
        """
    )
    conn.commit()


@pytest.mark.invariants
def test_el_fichero_lean_refleja_la_cronologia_de_sqlite(conn: sqlite3.Connection) -> None:
    """RF-LEAN-01. El fichero se **genera**: escrito a mano dejaria de ser verificacion.

    Si alguien pudiera editarlo, Lean verificaria la historia que el fichero cuenta y no
    la que la novela tiene, que es una forma elegante de no verificar nada.
    """
    _cronologia(conn)

    lean = generar_cronologia_lean(StoryBible(conn))

    assert "def eventos : List Evento" in lean
    assert 'evento_id := "ev-1"' in lean
    assert "momento := 1998" in lean
    assert 'personaje_id := "pe-1"' in lean
    assert "anio_de_nacimiento := 1990" in lean
    assert "-- generado" in lean.splitlines()[0].lower() or "generado" in lean[:400]


@pytest.mark.invariants
def test_un_evento_sin_momento_no_entra_en_el_fichero(conn: sqlite3.Connection) -> None:
    """Lo que no esta fechado no se puede verificar, y no se le inventa una fecha."""
    _cronologia(conn)
    conn.execute(
        "INSERT INTO evento (id, descripcion, posicion_en_historia, tipo) "
        "VALUES ('ev-3', 'sin fecha', 30, 'accion')"
    )
    conn.commit()

    lean = generar_cronologia_lean(StoryBible(conn))

    assert '"ev-3"' not in lean


@pytest.mark.invariants
def test_la_generacion_es_reproducible(conn: sqlite3.Connection) -> None:
    """Dos generaciones seguidas dan el mismo fichero, o el diff deja de significar nada."""
    _cronologia(conn)
    biblia = StoryBible(conn)

    assert generar_cronologia_lean(biblia) == generar_cronologia_lean(biblia)


@pytest.mark.invariants
def test_la_edad_negativa_se_puede_detectar_en_los_datos(conn: sqlite3.Connection) -> None:
    """El caso que RF-LEAN-05 pide demostrar, sembrado en los datos.

    Es la incoherencia que ningun validador anterior detecta: el guardarrail no mira
    fechas, la longitud no mira fechas, el juez con rubrica lee prosa y un personaje que
    aparece doce anos antes de nacer se lee perfectamente.
    """
    _cronologia(conn)
    conn.execute("UPDATE personaje SET anio_de_nacimiento = 2010 WHERE id = 'pe-1'")
    conn.commit()

    problemas = incoherencias_detectables(StoryBible(conn))

    assert any(p.tipo == "edad_negativa" for p in problemas)
    assert any("ev-1" in p.detalle for p in problemas)


@pytest.mark.invariants
def test_un_personaje_en_dos_lugares_el_mismo_momento_se_detecta(
    conn: sqlite3.Connection,
) -> None:
    """El tercer invariante de la lista de RF-LEAN-02."""
    _cronologia(conn)
    conn.execute("UPDATE evento SET momento = 1998 WHERE id = 'ev-2'")
    conn.commit()

    problemas = incoherencias_detectables(StoryBible(conn))

    assert any(p.tipo == "ubicuidad" for p in problemas)


@pytest.mark.invariants
def test_una_cronologia_sana_no_produce_incoherencias(conn: sqlite3.Connection) -> None:
    """Un detector que siempre encuentra algo es indistinguible de uno roto."""
    _cronologia(conn)
    assert incoherencias_detectables(StoryBible(conn)) == ()


@pytest.mark.invariants
def test_el_proyecto_lean_existe_y_declara_sus_invariantes() -> None:
    """RF-LEAN-02: los invariantes viven en Lean, no en el generador de Python."""
    cronologia = RAIZ / RAIZ_LEAN / "MyStoryMaker" / "Cronologia.lean"
    assert cronologia.exists(), "falta el fichero de invariantes de Lean"

    texto = cronologia.read_text(encoding="utf-8")
    assert "orden_temporal" in texto
    assert "edad_no_negativa" in texto
    assert "theorem" in texto or "def" in texto


@pytest.mark.invariants
def test_la_especificacion_tla_existe_con_sus_invariantes_y_su_configuracion() -> None:
    """RF-TLA-01 a RF-TLA-04. Una especificacion sin `.cfg` no la ejecuta nadie."""
    spec = RAIZ / "tla" / "Generacion.tla"
    cfg = RAIZ / "tla" / "Generacion.cfg"

    assert spec.exists() and cfg.exists()

    texto = spec.read_text(encoding="utf-8")
    for invariante in (
        "NoPublicarSinValidar",
        "CheckpointNoDuplicaNiPierde",
        "VersionAnteriorSeConserva",
        "ReintentosAcotados",
    ):
        assert invariante in texto, f"falta el invariante {invariante}"
    assert "Termina" in texto, "falta la propiedad de liveness"

    configuracion = cfg.read_text(encoding="utf-8")
    assert "INVARIANT" in configuracion and "PROPERTY" in configuracion
    assert "5" in configuracion, "el modelo pequeno declarado es de 5 capitulos"
