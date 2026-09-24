"""Planner, editor/critic, los dos hooks y las tools con schema.

SPEC-003, fase C, pasos C-06 a C-10. Cubre RF-HAR-01, RF-HAR-04, RF-HAR-05 y RF-HAR-06.

La coordinacion entre roles vive en `orchestrator/`, no en `agents/`: por eso los hooks
se prueban contra el orquestador y los roles se prueban solos. Un rol que llamara a otro
rompería la regla de `CLAUDE.md` 4 y la puerta de limites lo cazaria.
"""

from __future__ import annotations

import sqlite3

import pytest

from backend.agents.editor.editor import SalidaDelEditor, parsear_editor
from backend.agents.planner.planner import (
    PlanDeCapitulos,
    SalidaInvalidaDelPlanner,
    parsear_plan,
)
from backend.domain.vocabularies import Severidad
from backend.orchestrator.hooks import (
    ResultadoDeHook,
    hook_de_capitulo,
    hook_de_policy,
)
from backend.worker.tools import (
    LIMITE_DE_REINTENTOS,
    EsquemaDeTool,
    LlamadaInvalida,
    ReintentosAgotados,
    ejecutar_con_reintentos,
    validar_llamada,
)
from tests.conftest import material_minimo

PLAN_BUENO = """
## capitulos
1. La casa de Gijon | ev-1 | Marta vuelve al pueblo
2. El agua fria | ev-2 | Marta se mete en el mar por primera vez

## hechos_requeridos
- he-1
- he-2
"""

EDITOR_BUENO = """
## defectos
- alta | continuidad | Marta tiene 8 anos en el capitulo 1 y 6 en el 2 | cap-2, parrafo 3
- baja | ritmo | tres escenas seguidas de dialogo sin accion | cap-2

## veredicto
rechazado
"""


# --- C-06: el planner ---------------------------------------------------------------


@pytest.mark.invariants
def test_el_plan_cubre_todos_los_capitulos_declarados_en_el_brief() -> None:
    """RF-HAR-01. Un plan que deja capitulos sin cubrir se descubre al final."""
    plan = parsear_plan(PLAN_BUENO)

    assert isinstance(plan, PlanDeCapitulos)
    assert [c.orden for c in plan.capitulos] == [1, 2]
    assert plan.capitulos[0].titulo == "La casa de Gijon"
    assert plan.capitulos[0].evento_id == "ev-1"
    assert plan.hechos_requeridos == ("he-1", "he-2")


@pytest.mark.invariants
def test_un_plan_con_ordenes_repetidos_no_valida() -> None:
    """Dos capitulos con el mismo numero hacen imposible reanudar desde checkpoint."""
    with pytest.raises(SalidaInvalidaDelPlanner) as error:
        parsear_plan(PLAN_BUENO.replace("2. El agua fria", "1. El agua fria"))

    assert "orden" in str(error.value)


@pytest.mark.invariants
def test_un_plan_sin_capitulos_no_valida() -> None:
    with pytest.raises(SalidaInvalidaDelPlanner):
        parsear_plan("## capitulos\n\n## hechos_requeridos\n- he-1")


@pytest.mark.invariants
def test_el_plan_declara_sus_hechos_requeridos() -> None:
    """Es el cuello de botella de anotacion que SPEC-001 declaro como riesgo.

    Sin hechos requeridos, la fuga epistemica se evalua sobre menos hechos de los que la
    escena usa: es F-02 de `verification.md` 11.
    """
    with pytest.raises(SalidaInvalidaDelPlanner) as error:
        parsear_plan("## capitulos\n1. Uno | ev-1 | algo\n\n## hechos_requeridos\n")

    assert "hechos_requeridos" in str(error.value)


# --- C-07: el editor/critic ---------------------------------------------------------


@pytest.mark.invariants
def test_el_editor_devuelve_defectos_con_evidencia_citable() -> None:
    """RF-HAR-01. Un defecto sin evidencia se descarta: no se puede corregir a ciegas."""
    salida = parsear_editor(EDITOR_BUENO)

    assert isinstance(salida, SalidaDelEditor)
    assert len(salida.defectos) == 2
    assert salida.defectos[0].severidad is Severidad.ALTA
    assert salida.defectos[0].evidencia == "cap-2, parrafo 3"
    assert salida.acepta is False


@pytest.mark.invariants
def test_un_defecto_sin_evidencia_se_descarta_y_se_cuenta() -> None:
    """Igual que en la capa de calidad: descartar en silencio oculta un agente que opina."""
    salida = parsear_editor(
        "## defectos\n- alta | continuidad | algo esta mal |\n\n## veredicto\nrechazado"
    )

    assert salida.defectos == ()
    assert salida.descartados_sin_evidencia == 1


@pytest.mark.invariants
def test_un_veredicto_aceptado_sin_defectos_es_valido() -> None:
    salida = parsear_editor("## defectos\n\n## veredicto\naceptado")

    assert salida.acepta is True
    assert salida.defectos == ()


# --- C-08 y C-09: los dos hooks -----------------------------------------------------


@pytest.mark.invariants
def test_el_hook_de_capitulo_corre_antes_de_aceptarlo(conn: sqlite3.Connection) -> None:
    """RF-HAR-04. El hook devuelve los defectos deterministas del capitulo."""
    material_minimo(conn)

    resultado = hook_de_capitulo(
        "palabra " * 50,
        conn=conn,
        destinatario=None,
        personajes=("Irene",),
    )

    assert isinstance(resultado, ResultadoDeHook)
    assert resultado.acepta is False
    assert any(d.tipo == "longitud_de_capitulo" for d in resultado.defectos)


@pytest.mark.invariants
def test_el_hook_de_policy_devuelve_el_capitulo_con_palabra_prohibida(
    conn: sqlite3.Connection,
) -> None:
    """RF-HAR-04 y RF-GRD-03: la politica corre sobre cada capitulo antes de aceptarlo."""
    material_minimo(conn)
    conn.execute(
        "INSERT INTO lista_prohibida (id, nivel, termino) VALUES ('lp-1', 'global', 'imbecil')"
    )

    resultado = hook_de_policy("Le llamo imbecil y se fue.", conn=conn, capitulo_id="cap-1")

    assert resultado.acepta is False
    assert resultado.motivo and "imbecil" in resultado.motivo


@pytest.mark.invariants
def test_un_capitulo_limpio_pasa_los_dos_hooks(conn: sqlite3.Connection) -> None:
    """Un hook que nunca acepta es indistinguible de uno roto."""
    material_minimo(conn)

    policy = hook_de_policy("La tarde caia sobre el puerto.", conn=conn, capitulo_id="cap-1")
    capitulo = hook_de_capitulo("palabra " * 1_000, conn=conn, destinatario=None, personajes=())

    assert policy.acepta is True
    assert capitulo.acepta is True


# --- C-10: tools con schema y reintentos con limite ---------------------------------


ESQUEMA = EsquemaDeTool(
    nombre="consultar_story_bible",
    campos_obligatorios=("clase",),
    tipos={"clase": str, "limite": int},
)


@pytest.mark.invariants
def test_una_llamada_a_tool_que_no_valida_es_fallo_de_contrato() -> None:
    """RF-HAR-05. Una tool sin schema es una llamada que nadie comprueba."""
    with pytest.raises(LlamadaInvalida) as falta:
        validar_llamada(ESQUEMA, {})
    assert "clase" in str(falta.value)

    with pytest.raises(LlamadaInvalida) as tipo:
        validar_llamada(ESQUEMA, {"clase": "personaje", "limite": "diez"})
    assert "limite" in str(tipo.value)


@pytest.mark.invariants
def test_una_llamada_valida_pasa_y_devuelve_los_argumentos() -> None:
    assert validar_llamada(ESQUEMA, {"clase": "personaje", "limite": 10}) == {
        "clase": "personaje",
        "limite": 10,
    }


@pytest.mark.invariants
def test_los_reintentos_tienen_limite_y_al_agotarlo_se_informa() -> None:
    """RF-HAR-06. Sin limite, un fallo permanente deja el sistema girando y pagando."""
    intentos: list[int] = []

    def siempre_falla() -> str:
        intentos.append(1)
        raise ConnectionError("corte de red")

    with pytest.raises(ReintentosAgotados) as error:
        ejecutar_con_reintentos(siempre_falla, nombre="consultar_story_bible")

    assert len(intentos) == LIMITE_DE_REINTENTOS
    assert "consultar_story_bible" in str(error.value)
    assert str(LIMITE_DE_REINTENTOS) in str(error.value)


@pytest.mark.invariants
def test_un_fallo_que_se_arregla_solo_no_agota_el_limite() -> None:
    """Reintentar sirve para lo transitorio; por eso el exito corta la escalera."""
    intentos: list[int] = []

    def falla_una_vez() -> str:
        intentos.append(1)
        if len(intentos) == 1:
            raise ConnectionError("corte de red")
        return "ok"

    assert ejecutar_con_reintentos(falla_una_vez, nombre="tool") == "ok"
    assert len(intentos) == 2


@pytest.mark.invariants
def test_una_llamada_invalida_no_se_reintenta() -> None:
    """Reintentar un argumento mal formado repite el mismo error y paga por ello."""
    intentos: list[int] = []

    def argumento_malo() -> str:
        intentos.append(1)
        raise LlamadaInvalida("tool", "falta el campo obligatorio «clase»")

    with pytest.raises(LlamadaInvalida):
        ejecutar_con_reintentos(argumento_malo, nombre="tool")

    assert len(intentos) == 1
