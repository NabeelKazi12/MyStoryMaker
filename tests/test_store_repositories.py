"""Repositorios: grafo causal por CTE, catalogo de predicados y canon versionado.

Cubre RF-STO-05, RF-STO-07 y RF-STO-08.
"""

from __future__ import annotations

import sqlite3
import subprocess
import sys
from collections.abc import Iterator
from pathlib import Path

import pytest

from backend.domain.diegetic.canon import Hecho
from backend.domain.errors import ErrorDeDominio
from backend.store import database
from backend.store.repositories import (
    CanonVersionado,
    CatalogoDePredicados,
    CheckpointDeCapitulos,
    GrafoCausal,
    ResumenesDeCapitulo,
    StoryBible,
    UsoDeHechos,
)

RAIZ = Path(__file__).resolve().parent.parent


@pytest.fixture
def conn(tmp_path: Path) -> Iterator[sqlite3.Connection]:
    """Una base migrada por test: los repositorios escriben y no deben contaminarse."""
    import os

    destino = tmp_path / "canon.db"
    resultado = subprocess.run(
        [sys.executable, "-m", "alembic", "upgrade", "head"],
        cwd=RAIZ,
        env={**os.environ, "MYSTORYMAKER_DB": str(destino)},
        capture_output=True,
        text=True,
    )
    assert resultado.returncode == 0, resultado.stderr
    conexion = database.abrir(destino)
    try:
        yield conexion
    finally:
        conexion.close()


def _eventos(conn: sqlite3.Connection, *, posiciones: dict[str, int]) -> None:
    for id_evento, posicion in posiciones.items():
        conn.execute(
            "INSERT INTO evento (id, descripcion, posicion_en_historia, tipo) "
            "VALUES (?, ?, ?, 'accion')",
            (id_evento, f"evento {id_evento}", posicion),
        )


def _causa(conn: sqlite3.Connection, *pares: tuple[str, str]) -> None:
    conn.executemany("INSERT INTO evento_causa (causa_id, efecto_id) VALUES (?, ?)", pares)


# --- RF-STO-08: consultas transitivas con CTE recursiva ------------------------------


@pytest.mark.invariants
def test_alcanzables_recorre_el_grafo_en_profundidad(conn: sqlite3.Connection) -> None:
    """Una cadena de cinco saltos se resuelve en una consulta, no en cinco viajes."""
    _eventos(conn, posiciones={f"ev-{i}": i * 10 for i in range(1, 7)})
    _causa(conn, ("ev-1", "ev-2"), ("ev-2", "ev-3"), ("ev-3", "ev-4"), ("ev-4", "ev-5"))

    assert GrafoCausal(conn).alcanzables_desde("ev-1") == {"ev-2", "ev-3", "ev-4", "ev-5"}
    assert GrafoCausal(conn).alcanzables_desde("ev-6") == frozenset()


@pytest.mark.invariants
def test_detecta_un_ciclo_indirecto(conn: sqlite3.Connection) -> None:
    """El ciclo corto lo corta el dominio; el largo solo se ve recorriendo el grafo."""
    _eventos(conn, posiciones={"ev-1": 10, "ev-2": 20, "ev-3": 30})
    _causa(conn, ("ev-1", "ev-2"), ("ev-2", "ev-3"), ("ev-3", "ev-1"))

    assert set(GrafoCausal(conn).ciclos()) == {"ev-1", "ev-2", "ev-3"}


@pytest.mark.invariants
def test_un_grafo_aciclico_no_reporta_ciclos(conn: sqlite3.Connection) -> None:
    """Que no invente: es la mitad de la comprobacion que exige verification.md 7."""
    _eventos(conn, posiciones={"ev-1": 10, "ev-2": 20, "ev-3": 30})
    _causa(conn, ("ev-1", "ev-2"), ("ev-1", "ev-3"), ("ev-2", "ev-3"))

    assert GrafoCausal(conn).ciclos() == ()


@pytest.mark.invariants
def test_detecta_causa_posterior_a_su_efecto(conn: sqlite3.Connection) -> None:
    """Si A causa B, A precede a B en tiempo de historia."""
    _eventos(conn, posiciones={"ev-1": 50, "ev-2": 20})
    _causa(conn, ("ev-1", "ev-2"))

    assert GrafoCausal(conn).precedencias_violadas() == (("ev-1", "ev-2"),)


@pytest.mark.invariants
def test_no_reporta_precedencias_correctas(conn: sqlite3.Connection) -> None:
    _eventos(conn, posiciones={"ev-1": 10, "ev-2": 20})
    _causa(conn, ("ev-1", "ev-2"))

    assert GrafoCausal(conn).precedencias_violadas() == ()


# --- RF-STO-07: catalogo de predicados ----------------------------------------------


@pytest.mark.invariants
def test_el_catalogo_declara_la_exclusividad(conn: sqlite3.Connection) -> None:
    catalogo = CatalogoDePredicados(conn)

    assert catalogo.es_funcional("ubicacion") is True
    assert catalogo.es_funcional("posee") is False
    assert len(catalogo.todos()) == 9


@pytest.mark.invariants
def test_un_predicado_no_catalogado_da_error_de_dominio(conn: sqlite3.Connection) -> None:
    """El mensaje dice que hay que catalogarlo, no que fallo una clave foranea."""
    with pytest.raises(ErrorDeDominio) as error:
        CatalogoDePredicados(conn).exclusividad_de("predicado_inventado")

    assert error.value.clase == "Predicado"
    assert "RegistroDeDecision" in str(error.value)


# --- RF-STO-05: canon reconstruido desde eventos de cambio ---------------------------


@pytest.mark.invariants
def test_reconstruye_la_revision_n_sin_copiar_el_canon(conn: sqlite3.Connection) -> None:
    """«Que era verdad en el capitulo 12» se responde plegando cambios, no leyendo copias."""
    canon = CanonVersionado(conn)
    _eventos(conn, posiciones={"ev-1": 10, "ev-2": 20})

    hecho_uno = Hecho(
        id="h-1", sujeto_id="per-1", predicado="ubicacion", objeto="puerto", valido_desde="ev-1"
    )
    hecho_dos = Hecho(
        id="h-2", sujeto_id="per-1", predicado="ubicacion", objeto="faro", valido_desde="ev-2"
    )

    rev1 = canon.abrir_revision("primera canonizacion")
    canon.registrar_insercion(rev1, hecho_uno)

    rev2 = canon.abrir_revision("el personaje se muda")
    canon.registrar_cierre(rev2, "h-1", "ev-2")
    canon.registrar_insercion(rev2, hecho_dos)

    assert canon.revision_actual() == 2
    assert canon.hechos_vigentes_en(0) == frozenset()
    assert canon.hechos_vigentes_en(1) == {"h-1"}
    assert canon.hechos_vigentes_en(2) == {"h-2"}


@pytest.mark.invariants
def test_la_revision_solo_avanza(conn: sqlite3.Connection) -> None:
    """El canon se versiona; lo que deja de estar vigente conserva su intervalo."""
    canon = CanonVersionado(conn)
    primera = canon.abrir_revision()
    segunda = canon.abrir_revision()

    assert (primera, segunda) == (1, 2)
    assert canon.revision_actual() == 2


# --- SPEC-003 A-04 y A-05: la story bible consultable y el uso por capitulo ----------


def _canon_minimo(conn: sqlite3.Connection) -> None:
    """Un brief, un volumen, dos capitulos, un personaje, un lugar, un evento y un hecho."""
    conn.executescript(
        """
        INSERT INTO brief (id, genero, premisa, promesa_al_lector, extension_objetivo)
            VALUES ('br-1', 'memoria', 'una vida', 'emocionar', 30000);
        INSERT INTO volumen (id, titulo) VALUES ('vo-1', 'Marta');
        INSERT INTO capitulo (id, volumen_id, orden) VALUES ('ca-1', 'vo-1', 1);
        INSERT INTO capitulo (id, volumen_id, orden) VALUES ('ca-2', 'vo-1', 2);
        INSERT INTO lugar (id, nombre_canonico) VALUES ('lu-1', 'Gijon');
        INSERT INTO personaje (id, nombre_canonico, anio_de_nacimiento)
            VALUES ('pe-1', 'Marta', 1990);
        INSERT INTO evento (id, descripcion, posicion_en_historia, tipo, momento, lugar_id)
            VALUES ('ev-1', 'aprende a nadar', 10, 'accion', 1998, 'lu-1');
        INSERT INTO evento_participante (evento_id, entidad_id, rol_en_evento)
            VALUES ('ev-1', 'pe-1', 'agente');
        INSERT INTO hecho (id, sujeto_id, predicado, objeto, valido_desde)
            VALUES ('he-1', 'pe-1', 'ubicacion', 'Gijon', 'ev-1');
        """
    )
    conn.commit()


@pytest.mark.invariants
def test_la_story_bible_se_consulta_por_personaje_lugar_hecho_y_cronologia(
    conn: sqlite3.Connection,
) -> None:
    """RF-BIB-05. Es lo que la ficha de la lectura y el generador de Lean van a leer."""
    _canon_minimo(conn)
    biblia = StoryBible(conn)

    assert [p.nombre_canonico for p in biblia.personajes()] == ["Marta"]
    assert [lugar.nombre_canonico for lugar in biblia.lugares()] == ["Gijon"]
    assert [h.id for h in biblia.hechos()] == ["he-1"]

    (fila,) = biblia.cronologia()
    assert fila.evento_id == "ev-1"
    assert fila.momento == 1998
    assert fila.lugar_id == "lu-1"
    assert fila.personajes == ("pe-1",)


@pytest.mark.invariants
def test_un_hecho_usado_en_dos_capitulos_los_lista_ambos(conn: sqlite3.Connection) -> None:
    """RF-BIB-01, y la precondicion de la regeneracion selectiva de RF-LEC-05."""
    _canon_minimo(conn)
    usos = UsoDeHechos(conn)

    usos.registrar("he-1", "ca-1")
    usos.registrar("he-1", "ca-2")
    usos.registrar("he-1", "ca-1")  # idempotente: registrar dos veces no duplica

    assert usos.capitulos_de("he-1") == ("ca-1", "ca-2")
    assert usos.hechos_de("ca-2") == ("he-1",)


@pytest.mark.invariants
def test_un_hecho_sin_uso_declarado_no_arrastra_ningun_capitulo(
    conn: sqlite3.Connection,
) -> None:
    """Un hecho vigente que ninguna escena narra existe: es F-09 de verification.md 11.

    Devolver capitulos que no lo usan haria que cambiarlo regenerase de mas, que es lo
    contrario de lo que RF-LEC-05 pide.
    """
    _canon_minimo(conn)
    assert UsoDeHechos(conn).capitulos_de("he-1") == ()


# --- SPEC-003 A-06 y A-07: resumenes por capitulo y checkpoint ----------------------


@pytest.mark.invariants
def test_el_contexto_del_capitulo_n_trae_resumenes_y_no_prosa_literal(
    conn: sqlite3.Connection,
) -> None:
    """RF-BIB-03. Es lo que mantiene el paquete de tamano constante en el capitulo 40.

    Si el capitulo 3 entrara con su prosa, el paquete crecería con el libro y la
    reproducibilidad del `hash` dejaria de significar nada (`architecture.md` 4.4).
    """
    _canon_minimo(conn)
    resumenes = ResumenesDeCapitulo(conn)
    resumenes.guardar("ca-1", "Marta aprende a nadar y pierde el miedo.", revision_canon=1)

    anteriores = resumenes.anteriores_a("ca-2")

    assert [r.capitulo_id for r in anteriores] == ["ca-1"]
    assert anteriores[0].texto.startswith("Marta aprende")
    assert anteriores[0].tokens > 0
    # El capitulo propio no entra en su propio contexto.
    assert resumenes.anteriores_a("ca-1") == ()


@pytest.mark.invariants
def test_guardar_dos_veces_el_resumen_de_un_capitulo_lo_sustituye(
    conn: sqlite3.Connection,
) -> None:
    """Un capitulo regenerado tiene un resumen nuevo, no dos resumenes contradictorios."""
    _canon_minimo(conn)
    resumenes = ResumenesDeCapitulo(conn)
    resumenes.guardar("ca-1", "primera version", revision_canon=1)
    resumenes.guardar("ca-1", "segunda version", revision_canon=2)

    (unico,) = resumenes.anteriores_a("ca-2")
    assert unico.texto == "segunda version"
    assert unico.revision_canon == 2


@pytest.mark.invariants
def test_reanudar_desde_checkpoint_no_duplica_ni_pierde_capitulos(
    conn: sqlite3.Connection,
) -> None:
    """RF-BIB-04, y el invariante de seguridad que TLA+ verificara en F-05.

    Los dos fallos que importan son simetricos: reanudar rehaciendo el ultimo capitulo
    duplica trabajo y paga dos veces la invocacion; reanudar saltandoselo deja un hueco
    que nadie nota hasta leer la novela entera.
    """
    _canon_minimo(conn)
    checkpoint = CheckpointDeCapitulos(conn)

    assert checkpoint.completados() == ()
    assert checkpoint.siguiente(("ca-1", "ca-2")) == "ca-1"

    checkpoint.marcar_completado("ca-1", orden=1)

    assert checkpoint.completados() == ("ca-1",)
    assert checkpoint.siguiente(("ca-1", "ca-2")) == "ca-2"

    # Marcarlo dos veces no lo duplica ni retrocede: la reanudacion es idempotente.
    checkpoint.marcar_completado("ca-1", orden=1)
    assert checkpoint.completados() == ("ca-1",)

    checkpoint.marcar_completado("ca-2", orden=2)
    assert checkpoint.siguiente(("ca-1", "ca-2")) is None
