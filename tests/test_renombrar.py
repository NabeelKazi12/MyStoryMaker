"""Cambiar el nombre de un personaje y que quede en toda la novela.

SPEC-013. Cubre RF-NOM-01 a RF-NOM-15 y RF-LEC-29.

La propiedad que sostiene la spec: tras renombrar, ningun texto de la novela -canon,
esqueleto, resumenes, prosa- lleva el nombre viejo, y nada de lo que habia se ha perdido.
Un nombre cambiado en la ficha y no en los resumenes es canon fantasma: el capitulo
siguiente vuelve a llamarlo como antes.
"""

from __future__ import annotations

import json
import re
import shutil
import sqlite3
from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from backend.api import main
from backend.domain.diegetic.nombres import SustitucionDeNombre
from backend.domain.vocabularies import ModoDeEscritura
from backend.orchestrator.aprobacion import aprobar
from backend.orchestrator.escritura import encolar_escritura, paquete_de_escena
from backend.orchestrator.renombrar import (
    NombreInvalido,
    PersonajeAjeno,
    RenombradoCerrado,
    renombrar,
)
from backend.store import database
from backend.store.escritura import TextoDeLaNovela
from backend.store.repositories import CanonVersionado, VersionesDeNovela
from tests.test_escritura import _escribir, _novela
from tests.test_personajes import HERMANO

# --- A-1: la sustitucion pura (RF-NOM-07 a RF-NOM-09) --------------------------------


@pytest.mark.invariants
def test_sustituye_el_nombre_completo_y_en_mayusculas() -> None:
    regla = SustitucionDeNombre("Luis Ortega", "Pablo Ruiz")

    assert (
        regla.aplicar("Luis Ortega entro. —¡LUIS ORTEGA!") == "Pablo Ruiz entro. —¡PABLO RUIZ!"
    )


@pytest.mark.invariants
def test_sustituye_cada_parte_si_tienen_las_mismas_palabras() -> None:
    regla = SustitucionDeNombre("Luis Ortega", "Pablo Ruiz")

    assert regla.aplicar("Luis miro a Ortega.") == "Pablo miro a Ruiz."


@pytest.mark.invariants
def test_con_distinto_numero_de_palabras_solo_la_primera() -> None:
    regla = SustitucionDeNombre("Luis Ortega", "Pablo")

    assert regla.aplicar("Luis Ortega, Luis y Ortega.") == "Pablo, Pablo y Ortega."


@pytest.mark.invariants
def test_no_sustituye_dentro_de_otra_palabra() -> None:
    regla = SustitucionDeNombre("Ana", "Lucía")

    assert regla.aplicar("Ana y Anabel, en Santana.") == "Lucía y Anabel, en Santana."


@pytest.mark.invariants
def test_no_sustituye_una_parte_de_otro_personaje() -> None:
    regla = SustitucionDeNombre("Luis Ortega", "Pablo Ruiz", otros=("Marta Ortega",))

    assert regla.aplicar("Luis Ortega, Luis y Ortega.") == "Pablo Ruiz, Pablo y Ortega."


@pytest.mark.invariants
def test_una_particula_en_minuscula_no_se_sustituye_suelta() -> None:
    regla = SustitucionDeNombre("María de la Luz", "Elena de la Mar")

    assert regla.aplicar("María de la Luz vino de la sierra con Luz.") == (
        "Elena de la Mar vino de la sierra con Mar."
    )


@pytest.mark.invariants
def test_una_sola_pasada_aunque_el_nuevo_contenga_el_viejo() -> None:
    regla = SustitucionDeNombre("Ana", "Ana María")

    assert regla.aplicar("Ana llego.") == "Ana María llego."


@pytest.mark.invariants
def test_con_acentos_casa_como_palabra() -> None:
    regla = SustitucionDeNombre("Íñigo", "Óscar")

    assert regla.aplicar("Íñigo y Íñigoberto.") == "Óscar y Íñigoberto."


# --- A-2: el canon registra el cambio de nombre (RF-NOM-12) --------------------------


@pytest.mark.invariants
def test_migracion_0009_admite_renombrar(conn: sqlite3.Connection) -> None:
    revision = CanonVersionado(conn).abrir_revision("prueba")
    conn.execute(
        "INSERT INTO canon_cambio (revision, tabla, fila_id, operacion, datos) "
        "VALUES (?, 'personaje', 'per-1', 'renombrar', '{}')",
        (revision,),
    )
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute(
            "INSERT INTO canon_cambio (revision, tabla, fila_id, operacion, datos) "
            "VALUES (?, 'personaje', 'per-1', 'inventada', '')",
            (revision,),
        )
    registradas = {f["id"] for f in conn.execute("SELECT id FROM registro_decision").fetchall()}
    assert "rd-d26" in registradas


@pytest.mark.invariants
def test_renombrar_un_hecho_no_lo_saca_del_canon(conn: sqlite3.Connection) -> None:
    """Un evento `renombrar` cambia el texto del hecho, no su vigencia."""
    canon = CanonVersionado(conn)
    primera = canon.abrir_revision("alta")
    conn.execute(
        "INSERT INTO canon_cambio (revision, tabla, fila_id, operacion, datos) "
        "VALUES (?, 'hecho', 'he-1', 'insertar', 'ev-1')",
        (primera,),
    )
    segunda = canon.registrar_renombrado(
        canon.abrir_revision("renombrar"), "hecho", "he-1", "confia en Luis", "confia en Pablo"
    )

    assert canon.hechos_vigentes_en(segunda) == frozenset({"he-1"})


# --- B: renombrar en una novela escrita (RF-NOM-02 a RF-NOM-15) ----------------------

PALABRA_LUIS = re.compile(r"(?<!\w)Luis(?!\w)")


def _novela_con_luis(conn: sqlite3.Connection) -> tuple[str, str]:
    """Una muestra escrita en demostracion con Luis de secundario. Devuelve novela y Luis."""
    volumen_id = _novela(conn, personajes=[HERMANO])
    _escribir(conn, volumen_id)
    fila = conn.execute("SELECT id FROM personaje WHERE nombre_canonico = 'Luis'").fetchone()
    return volumen_id, str(fila["id"])


def _textos_de_la_novela(conn: sqlite3.Connection, volumen_id: str) -> list[str]:
    """Todo texto de RF-NOM-10 de esa novela, con la prosa que sirve la lectura."""
    capitulos = "SELECT id FROM capitulo WHERE volumen_id = :v"
    escenas = f"SELECT id FROM escena WHERE capitulo_id IN ({capitulos})"
    consultas = [
        f"SELECT titulo FROM capitulo WHERE id IN ({capitulos})",
        f"SELECT objetivo || conflicto || resultado FROM escena WHERE id IN ({escenas})",
        f"SELECT texto FROM resumen_capitulo WHERE capitulo_id IN ({capitulos})",
        "SELECT ev.descripcion FROM evento ev JOIN escena_evento se ON se.evento_id = ev.id "
        f"WHERE se.escena_id IN ({escenas})",
        "SELECT nombre FROM personaje_declarado pd JOIN volumen v ON v.brief_id = pd.brief_id "
        "WHERE v.id = :v",
        "SELECT objeto FROM hecho",
        f"SELECT texto FROM borrador WHERE obsoleto = 0 AND escena_id IN ({escenas})",
    ]
    return [
        str(fila[0] or "")
        for consulta in consultas
        for fila in conn.execute(consulta, {"v": volumen_id}).fetchall()
    ]


@pytest.mark.invariants
def test_un_nombre_vacio_o_largo_no_vale(conn: sqlite3.Connection) -> None:
    """RF-NOM-02."""
    volumen_id, luis = _novela_con_luis(conn)

    for malo in ("   ", "a" * 81):
        with pytest.raises(NombreInvalido):
            renombrar(conn, volumen_id, luis, malo)


@pytest.mark.invariants
def test_el_mismo_nombre_o_el_de_otro_no_vale(conn: sqlite3.Connection) -> None:
    """RF-NOM-03: la destinataria se llama Marta, y «márta» es Marta."""
    volumen_id, luis = _novela_con_luis(conn)

    with pytest.raises(NombreInvalido, match="Luis"):
        renombrar(conn, volumen_id, luis, "luís")
    with pytest.raises(NombreInvalido, match="Marta"):
        renombrar(conn, volumen_id, luis, "márta")


@pytest.mark.invariants
def test_un_personaje_ajeno_no_se_encuentra(conn: sqlite3.Connection) -> None:
    """RF-NOM-04."""
    volumen_id, _ = _novela_con_luis(conn)

    with pytest.raises(PersonajeAjeno):
        renombrar(conn, volumen_id, "per-de-otra-novela", "Pablo")


@pytest.mark.invariants
def test_la_destinataria_no_se_renombra(conn: sqlite3.Connection) -> None:
    """RF-NOM-05."""
    volumen_id, _ = _novela_con_luis(conn)
    marta = conn.execute("SELECT id FROM personaje WHERE nombre_canonico = 'Marta'").fetchone()

    with pytest.raises(RenombradoCerrado, match="destinataria"):
        renombrar(conn, volumen_id, marta["id"], "Lucía")


@pytest.mark.invariants
def test_aprobada_o_escribiendo_no_se_renombra(conn: sqlite3.Connection) -> None:
    """RF-NOM-06."""
    volumen_id, luis = _novela_con_luis(conn)
    aprobar(conn, volumen_id)
    with pytest.raises(RenombradoCerrado, match="aprobada"):
        renombrar(conn, volumen_id, luis, "Pablo")

    otra = _novela(conn, nombre="Ana", personajes=[HERMANO])
    encolar_escritura(conn, otra, ModoDeEscritura.DEMOSTRACION)
    with pytest.raises(RenombradoCerrado, match="termine"):
        renombrar(conn, otra, "per-cualquiera", "Pablo")


@pytest.mark.invariants
def test_tras_renombrar_ningun_texto_de_la_novela_lleva_el_nombre_viejo(
    conn: sqlite3.Connection,
) -> None:
    """RF-NOM-10: ni la ficha, ni el esqueleto, ni los resumenes, ni la prosa."""
    volumen_id, luis = _novela_con_luis(conn)
    assert any(PALABRA_LUIS.search(t) for t in _textos_de_la_novela(conn, volumen_id))

    hecho = renombrar(conn, volumen_id, luis, "Pablo")

    assert (hecho.anterior, hecho.nuevo) == ("Luis", "Pablo")
    assert not any(PALABRA_LUIS.search(t) for t in _textos_de_la_novela(conn, volumen_id))
    ficha = {
        p["nombre_canonico"] for p in main.lectura_de_novela(volumen_id, conn)["personajes"]
    }
    assert "Pablo" in ficha and "Luis" not in ficha
    prosa = " ".join(
        e.texto for c in TextoDeLaNovela(conn).por_capitulos(volumen_id) for e in c.escenas
    )
    assert "Pablo" in prosa


@pytest.mark.invariants
def test_el_borrador_anterior_se_conserva_obsoleto(conn: sqlite3.Connection) -> None:
    """RF-NOM-11: la prosa de antes no se sobrescribe."""
    volumen_id, luis = _novela_con_luis(conn)
    antes = {
        f["id"]: (f["escena_id"], f["version"], f["estado"], f["procedencia_id"], f["texto"])
        for f in conn.execute("SELECT * FROM borrador WHERE obsoleto = 0").fetchall()
    }

    renombrar(conn, volumen_id, luis, "Pablo")

    for borrador_id, (escena_id, version, estado, procedencia, texto) in antes.items():
        viejo = conn.execute("SELECT * FROM borrador WHERE id = ?", (borrador_id,)).fetchone()
        assert viejo["texto"] == texto
        if not PALABRA_LUIS.search(texto):
            assert viejo["obsoleto"] == 0
            continue
        assert viejo["obsoleto"] == 1
        nuevo = conn.execute(
            "SELECT * FROM borrador WHERE escena_id = ? AND obsoleto = 0", (escena_id,)
        ).fetchone()
        assert nuevo["version"] == version + 1
        assert (nuevo["estado"], nuevo["procedencia_id"]) == (estado, procedencia)
        assert nuevo["texto"] == PALABRA_LUIS.sub("Pablo", texto)


@pytest.mark.invariants
def test_renombrar_abre_una_revision_con_eventos_renombrar(conn: sqlite3.Connection) -> None:
    """RF-NOM-12."""
    volumen_id, luis = _novela_con_luis(conn)
    anterior = CanonVersionado(conn).revision_actual()

    hecho = renombrar(conn, volumen_id, luis, "Pablo")

    assert hecho.revision == anterior + 1
    evento = conn.execute(
        "SELECT datos FROM canon_cambio WHERE revision = ? AND tabla = 'personaje' "
        "AND fila_id = ? AND operacion = 'renombrar'",
        (hecho.revision, luis),
    ).fetchone()
    assert json.loads(evento["datos"]) == {"antes": "Luis", "despues": "Pablo"}


@pytest.mark.invariants
def test_la_version_nueva_marca_solo_los_capitulos_tocados(conn: sqlite3.Connection) -> None:
    """RF-NOM-13."""
    volumen_id, luis = _novela_con_luis(conn)
    con_luis = {
        f["capitulo_id"]
        for f in conn.execute(
            "SELECT e.capitulo_id, b.texto FROM borrador b JOIN escena e ON e.id = b.escena_id "
            "WHERE b.obsoleto = 0"
        ).fetchall()
        if PALABRA_LUIS.search(f["texto"])
    }

    hecho = renombrar(conn, volumen_id, luis, "Pablo")

    versiones = VersionesDeNovela(conn)
    assert hecho.version_id is not None
    assert set(versiones.capitulos_cambiados(hecho.version_id)) == con_luis
    assert {c.id for c in hecho.capitulos} == con_luis
    todos = conn.execute(
        "SELECT COUNT(*) FROM capitulo WHERE volumen_id = ?", (volumen_id,)
    ).fetchone()[0]
    assert len(versiones.capitulos_de(hecho.version_id)) == todos
    motivo = conn.execute(
        "SELECT motivo FROM version_novela WHERE id = ?", (hecho.version_id,)
    ).fetchone()["motivo"]
    assert motivo == "«Luis» pasa a llamarse «Pablo»"


@pytest.mark.invariants
def test_sin_prosa_no_se_publica_version(conn: sqlite3.Connection) -> None:
    """RF-NOM-13: si la prosa no lo nombra, cambia el canon y nada mas."""
    volumen_id, luis = _novela_con_luis(conn)
    conn.execute("UPDATE borrador SET texto = 'Nadie dijo nada.' WHERE obsoleto = 0")
    publicadas = len(VersionesDeNovela(conn).historial(volumen_id))

    hecho = renombrar(conn, volumen_id, luis, "Pablo")

    assert hecho.version_id is None and hecho.capitulos == ()
    assert len(VersionesDeNovela(conn).historial(volumen_id)) == publicadas


@pytest.mark.invariants
def test_un_fallo_a_mitad_no_deja_nada_cambiado(
    conn: sqlite3.Connection, monkeypatch: pytest.MonkeyPatch
) -> None:
    """RF-NOM-10: o cambia todo o nada."""
    volumen_id, luis = _novela_con_luis(conn)
    conn.commit()
    antes = _textos_de_la_novela(conn, volumen_id)

    def publicar_que_falla(*_: object, **__: object) -> str:
        raise RuntimeError("fallo a mitad")

    monkeypatch.setattr(VersionesDeNovela, "publicar", publicar_que_falla)
    with pytest.raises(RuntimeError):
        renombrar(conn, volumen_id, luis, "Pablo")

    assert _textos_de_la_novela(conn, volumen_id) == antes
    assert conn.execute("SELECT COUNT(*) FROM borrador WHERE obsoleto = 1").fetchone()[0] == 0


@pytest.mark.invariants
def test_renombrar_queda_en_audit_log(conn: sqlite3.Connection) -> None:
    """RF-NOM-14."""
    volumen_id, luis = _novela_con_luis(conn)

    renombrar(conn, volumen_id, luis, "Pablo")

    fila = conn.execute(
        "SELECT motivo FROM audit_log WHERE decision = 'renombrar_personaje'"
    ).fetchone()
    assert luis in fila["motivo"] and "Luis" in fila["motivo"] and "Pablo" in fila["motivo"]


@pytest.mark.invariants
def test_el_paquete_siguiente_no_lleva_el_nombre_viejo(conn: sqlite3.Connection) -> None:
    """RF-NOM-15: lo que se escriba despues no puede recuperar el nombre viejo."""
    volumen_id, luis = _novela_con_luis(conn)

    hecho = renombrar(conn, volumen_id, luis, "Pablo")

    escenas = conn.execute(
        "SELECT e.id FROM escena e JOIN capitulo c ON c.id = e.capitulo_id "
        "WHERE c.volumen_id = ?",
        (volumen_id,),
    ).fetchall()
    for escena in escenas:
        _, texto = paquete_de_escena(conn, escena["id"], hecho.revision).ensamblar("t", "p")
        assert not PALABRA_LUIS.search(texto), escena["id"]


# --- C-1: la ruta y la ficha (RF-NOM-01, RF-LEC-29) ----------------------------------


@pytest.fixture
def escrita(base_plantilla: Path, tmp_path: Path) -> Iterator[tuple[TestClient, str, str]]:
    """Una muestra escrita en una base propia, y un cliente HTTP contra ella."""
    ruta = tmp_path / "canon.db"
    shutil.copy(base_plantilla, ruta)
    with database.conexion(ruta) as conn:
        volumen_id, luis = _novela_con_luis(conn)

    def conexion_de_prueba() -> Iterator[object]:
        with database.conexion(ruta) as conn:
            yield conn

    main.app.dependency_overrides[main.obtener_conexion] = conexion_de_prueba
    try:
        yield TestClient(main.app), volumen_id, luis
    finally:
        main.app.dependency_overrides.clear()


@pytest.mark.invariants
def test_renombrar_por_la_ruta_responde_los_capitulos_cambiados(
    escrita: tuple[TestClient, str, str],
) -> None:
    cliente, volumen_id, luis = escrita

    respuesta = cliente.put(
        f"/novelas/{volumen_id}/personajes/{luis}/nombre", json={"nombre": " Pablo "}
    )

    assert respuesta.status_code == 200, respuesta.text
    cuerpo = respuesta.json()
    assert (cuerpo["anterior"], cuerpo["nuevo"]) == ("Luis", "Pablo")
    assert cuerpo["version_id"] is not None and cuerpo["revision"] > 0
    ordenes = [c["orden"] for c in cuerpo["capitulos"]]
    assert ordenes and ordenes == sorted(ordenes)
    ficha = cliente.get(f"/novelas/{volumen_id}/lectura").json()["personajes"]
    assert "Pablo" in {p["nombre_canonico"] for p in ficha}


@pytest.mark.invariants
def test_la_ruta_traduce_cada_rechazo_a_su_codigo(escrita: tuple[TestClient, str, str]) -> None:
    """RF-NOM-02 a RF-NOM-05, por HTTP."""
    cliente, volumen_id, luis = escrita
    ruta = f"/novelas/{volumen_id}/personajes/{{}}/nombre"
    marta = next(
        p["id"]
        for p in cliente.get(f"/novelas/{volumen_id}/lectura").json()["personajes"]
        if p["nombre_canonico"] == "Marta"
    )

    assert cliente.put(ruta.format(luis), json={"nombre": "Marta"}).status_code == 422
    assert cliente.put(ruta.format(luis), json={"nombre": ""}).status_code == 422
    assert cliente.put(ruta.format("per-nadie"), json={"nombre": "Pablo"}).status_code == 404
    assert cliente.put(ruta.format(marta), json={"nombre": "Lucía"}).status_code == 409
    assert (
        cliente.put(
            f"/novelas/no-existe/personajes/{luis}/nombre", json={"nombre": "Pablo"}
        ).status_code
        == 404
    )


@pytest.mark.invariants
def test_la_lectura_dice_quien_es_la_destinataria(escrita: tuple[TestClient, str, str]) -> None:
    """RF-LEC-29: el frontend no lo deduce del nombre."""
    cliente, volumen_id, _ = escrita

    ficha = cliente.get(f"/novelas/{volumen_id}/lectura").json()["personajes"]

    assert {p["nombre_canonico"]: p["es_destinatario"] for p in ficha} == {
        "Marta": True,
        "Luis": False,
    }
