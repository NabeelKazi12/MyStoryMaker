"""Orquestacion: DAG, maquina de estados, escalera, semaforo, permisos y canonizacion.

Cubre RF-ORQ-01 a RF-ORQ-24 y RF-CAN-01 a RF-CAN-06.
"""

from __future__ import annotations

import dataclasses
import sqlite3

import pytest

from backend.domain.diegetic.canon import Hecho
from backend.domain.production.ejecucion import Tarea
from backend.domain.vocabularies import ClaseDeFallo, EstadoDeTarea
from backend.orchestrator import permisos
from backend.orchestrator.admision import (
    PARALELISMO_POR_DEFECTO,
    ReservaImposible,
    Semaforo,
    Timeouts,
)
from backend.orchestrator.canonize import Canonizador
from backend.orchestrator.estados import (
    MAXIMO_DE_INTENTOS,
    TERMINALES,
    TRANSICIONES,
    Accion,
    PoliticaDeTransporte,
    TransicionInvalida,
    alcanzables,
    clasificar,
    siguiente_accion,
    transicionar,
)
from backend.orchestrator.plan import DAG, PlanCiclico, cadena_de_escena, reconciliar
from backend.store.repositories import CanonVersionado, UsoDeHechos
from tests.conftest import material_minimo

ORDEN = {"ev-1": 10, "ev-2": 20, "ev-3": 30}


def _tarea(identificador: str, **kwargs: object) -> Tarea:
    base: dict[str, object] = {
        "plan_id": "pl-1",
        "tipo": "redaccion",
        "rol_asignado": "redactor",
    }
    return Tarea(id=identificador, **{**base, **kwargs})  # type: ignore[arg-type]


# --- RF-ORQ-01: el plan es un DAG y un ciclo lo rechaza entero -----------------------


@pytest.mark.invariants
def test_un_plan_ciclico_se_rechaza_entero() -> None:
    """No se rompe el ciclo por heuristica: eso elegiria por el planificador en silencio."""
    with pytest.raises(PlanCiclico) as error:
        DAG(
            {
                "a": _tarea("a", depende_de=("c",)),
                "b": _tarea("b", depende_de=("a",)),
                "c": _tarea("c", depende_de=("b",)),
            }
        )
    assert "->" in str(error.value)


@pytest.mark.invariants
def test_un_dag_valido_se_construye() -> None:
    dag = DAG({t.id: t for t in cadena_de_escena("esc-1", "pl-1")})
    assert len(dag.tareas) == 3


# --- RF-ORQ-02: solo se lista con todas las dependencias aceptadas -------------------


@pytest.mark.invariants
def test_una_tarea_se_lista_solo_con_sus_dependencias_aceptadas() -> None:
    tareas = {t.id: t for t in cadena_de_escena("esc-1", "pl-1")}
    dag = DAG(tareas)
    assert dag.listas() == ("esc-1:redaccion",)

    tareas["esc-1:redaccion"] = dataclasses.replace(
        tareas["esc-1:redaccion"], estado=EstadoDeTarea.ACEPTADA
    )
    assert DAG(tareas).listas() == ("esc-1:verificacion",)


@pytest.mark.invariants
def test_la_reconciliacion_es_determinista() -> None:
    """Dos pasadas sobre el mismo estado deciden lo mismo: no hay modelo en el camino."""
    dag = DAG({t.id: t for t in cadena_de_escena("esc-1", "pl-1")})
    assert reconciliar(dag) == reconciliar(dag)


# --- RF-ORQ-22: la cadena de una escena es secuencial en el DAG ----------------------


@pytest.mark.invariants
def test_la_cadena_de_una_escena_queda_encadenada_aunque_la_concurrencia_sea_1() -> None:
    """La regla vive en el plan, no en un parametro que alguien pueda subir."""
    assert PARALELISMO_POR_DEFECTO == 1
    redaccion, verificacion, canonizacion = cadena_de_escena("esc-1", "pl-1")

    assert verificacion.depende_de == (redaccion.id,)
    assert canonizacion.depende_de == (verificacion.id,)
    assert canonizacion.prioridad == 0  # P0: bloquea todo su subarbol


@pytest.mark.invariants
def test_cancelar_alcanza_todo_el_subarbol() -> None:
    dag = DAG({t.id: t for t in cadena_de_escena("esc-1", "pl-1")})
    assert dag.subarbol_de("esc-1:redaccion") == {"esc-1:verificacion", "esc-1:canonizacion"}


# --- RF-ORQ-04: la maquina de estados no admite caminos que no tiene ----------------


@pytest.mark.invariants
def test_una_transicion_fuera_del_vocabulario_falla() -> None:
    with pytest.raises(TransicionInvalida):
        transicionar(_tarea("t-1"), EstadoDeTarea.ACEPTADA)


@pytest.mark.invariants
def test_todo_camino_de_la_maquina_termina() -> None:
    """Comprobacion de modelos: desde cualquier estado se alcanza un terminal."""
    for estado in EstadoDeTarea:
        if estado in TERMINALES:
            continue
        assert alcanzables(estado) & TERMINALES, f"{estado.value} no alcanza ningun terminal"


@pytest.mark.invariants
def test_los_terminales_no_tienen_salida() -> None:
    for terminal in TERMINALES:
        assert TRANSICIONES[terminal] == frozenset()


# --- RF-ORQ-07 y RF-ORQ-24: clasificacion e historial tipificado --------------------


@pytest.mark.invariants
def test_solo_contrato_y_contenido_suman_intento_narrativo() -> None:
    """Un corte de red no consume el presupuesto de reescrituras de una escena."""
    tarea = _tarea("t-1")
    for clase in (ClaseDeFallo.TRANSPORTE, ClaseDeFallo.PRESUPUESTO):
        tarea = clasificar(tarea, clase)
    assert tarea.intentos_narrativos == 0
    assert tarea.intentos_de_infraestructura == 2

    tarea = clasificar(tarea, ClaseDeFallo.CONTENIDO, "pov")
    assert tarea.intentos_narrativos == 1


@pytest.mark.invariants
def test_los_reintentos_de_transporte_no_los_hace_el_worker() -> None:
    """R-2: una sola capa. Dos capas multiplican y descuadran la contabilidad de coste."""
    politica = PoliticaDeTransporte()
    assert politica.max_reintentos == 3
    assert politica.consume_intento_narrativo() is False


# --- RF-ORQ-05 y RF-ORQ-06: la escalera y su atajo ----------------------------------


@pytest.mark.invariants
def test_la_escalera_recorre_sus_cuatro_peldanos_con_defectos_distintos() -> None:
    tarea = _tarea("t-1")
    esperado = [
        Accion.REESCRIBIR,
        Accion.REESCRIBIR_CON_MAS_CONTEXTO,
        Accion.REPLANIFICAR,
        Accion.ESCALAR,
    ]
    for paso, tipo in enumerate(("pov", "contradiccion", "ngramas", "presupuesto")):
        tarea = clasificar(tarea, ClaseDeFallo.CONTENIDO, tipo)
        assert siguiente_accion(tarea) == esperado[paso]
    assert tarea.intentos_narrativos == MAXIMO_DE_INTENTOS


@pytest.mark.invariants
def test_dos_defectos_iguales_saltan_directamente_a_replanificacion() -> None:
    """Repetir la misma operacion esperando otro resultado es el fallo mas caro."""
    tarea = _tarea("t-1")
    tarea = clasificar(tarea, ClaseDeFallo.CONTENIDO, "contradiccion")
    tarea = clasificar(tarea, ClaseDeFallo.CONTENIDO, "contradiccion")
    assert siguiente_accion(tarea) == Accion.REPLANIFICAR


# --- RF-ORQ-08 a RF-ORQ-11: el semaforo ---------------------------------------------


@pytest.mark.invariants
def test_el_credito_vuelve_al_inicial_en_toda_ruta_de_salida() -> None:
    """Exito, fallo, timeout y cancelacion: ninguna ruta se salta la liberacion."""
    semaforo = Semaforo()
    for i, _ruta in enumerate(("exito", "fallo", "timeout", "cancelacion")):
        semaforo.admitir(f"t-{i}", 28_000, prioridad=1)
        semaforo.liberar(f"t-{i}")
    assert semaforo.en_vuelo == 0


@pytest.mark.invariants
def test_liberar_dos_veces_no_descuadra_el_contador() -> None:
    """Un contador que se descuadra para el sistema sin producir ningun error visible."""
    semaforo = Semaforo()
    semaforo.admitir("t-1", 28_000, prioridad=1)
    semaforo.liberar("t-1")
    semaforo.liberar("t-1")
    assert semaforo.en_vuelo == 0


@pytest.mark.invariants
def test_tres_redacciones_y_un_juicio_caben_en_el_techo() -> None:
    """El caso normal de `architecture.md` 4.2: 3 x 28.000 + 9.000 = 93.000."""
    semaforo = Semaforo()
    for i in range(3):
        assert semaforo.admitir(f"red-{i}", 28_000, prioridad=1) is True
    assert semaforo.admitir("juicio", 9_000, prioridad=2) is True
    assert semaforo.en_vuelo == 93_000


@pytest.mark.invariants
def test_lo_que_no_cabe_ahora_se_encola_y_entra_al_liberar() -> None:
    semaforo = Semaforo()
    semaforo.admitir("grande", 90_000, prioridad=1)
    assert semaforo.admitir("otra", 28_000, prioridad=1) is False
    assert semaforo.en_cola == ("otra",)

    semaforo.liberar("grande")
    assert semaforo.drenar() == ["otra"]


@pytest.mark.invariants
def test_una_reserva_mayor_que_el_credito_se_rechaza_sin_encolar() -> None:
    """No cabe ni en un sistema vacio: es error de planificacion, no de saturacion."""
    with pytest.raises(ReservaImposible):
        Semaforo().admitir("imposible", 120_000, prioridad=1)


@pytest.mark.invariants
def test_una_tarea_que_espera_sube_de_clase() -> None:
    """Sin envejecimiento la prioridad estricta mata de hambre a P2 y P3."""
    semaforo = Semaforo(umbral_de_envejecimiento=2)
    semaforo.admitir("grande", 95_000, prioridad=1)
    semaforo.admitir("pequena", 28_000, prioridad=3)

    inicial = semaforo.prioridad_efectiva_de("pequena")
    for _ in range(2):
        semaforo.drenar()
    assert semaforo.prioridad_efectiva_de("pequena") < inicial


# --- RF-ORQ-12: los tres timeouts ---------------------------------------------------


@pytest.mark.invariants
def test_los_tres_niveles_de_timeout_tienen_valor_y_orden() -> None:
    t = Timeouts()
    assert t.por_invocacion_s < t.por_tarea_s < t.por_plan_s
    assert t.vencido("invocacion", t.por_invocacion_s + 1) is True
    assert t.vencido("tarea", 60) is False


@pytest.mark.invariants
def test_un_timeout_de_tarea_cubre_sus_reintentos() -> None:
    """30 minutos queda por debajo de los 40 que daria el reloj real de R-2."""
    t = Timeouts()
    reloj_real_del_sdk = t.por_invocacion_s * (PoliticaDeTransporte().max_reintentos + 1)
    assert t.por_tarea_s < reloj_real_del_sdk


# --- RF-ORQ-15: la matriz de permisos ------------------------------------------------


@pytest.mark.invariants
def test_un_rol_no_puede_escribir_una_clase_ajena() -> None:
    with pytest.raises(permisos.PermisoDenegado):
        permisos.exigir_permiso("redactor", "Hecho")
    permisos.exigir_permiso("redactor", "Borrador")


@pytest.mark.invariants
def test_solo_el_canonizador_escribe_canon() -> None:
    assert permisos.ESCRIBEN_CANON == {"canonizador"}
    assert permisos.puede_escribir_canon("redactor") is False


@pytest.mark.invariants
def test_ningun_rol_genera_y_valida_a_la_vez() -> None:
    """«Quien genera no valida», expresado como consulta sobre la matriz."""
    assert permisos.roles_que_generan_y_validan() == frozenset()


# --- RF-CAN-01 a RF-CAN-06: canonizacion --------------------------------------------


def _hecho(identificador: str, objeto: str, desde: str, hasta: str | None = None) -> Hecho:
    return Hecho(
        id=identificador,
        sujeto_id="per-1",
        predicado="ubicacion",
        objeto=objeto,
        valido_desde=desde,
        valido_hasta=hasta,
    )


@pytest.mark.invariants
def test_un_hecho_compatible_se_promueve_y_sube_la_revision(conn: sqlite3.Connection) -> None:
    material_minimo(conn)
    resultado = Canonizador(conn).canonizar(
        "bo-1", [_hecho("h-1", "el puerto", "ev-1")], [], ORDEN
    )

    assert resultado.promovidos == ("h-1",)
    assert resultado.revision == 1
    assert CanonVersionado(conn).hechos_vigentes_en(1) == {"h-1"}


@pytest.mark.invariants
def test_un_duplicado_exacto_no_se_inserta(conn: sqlite3.Connection) -> None:
    material_minimo(conn)
    vigente = _hecho("h-1", "el puerto", "ev-1")
    resultado = Canonizador(conn).canonizar("bo-1", [vigente], [vigente], ORDEN)

    assert resultado.duplicados == ("h-1",)
    assert resultado.promovidos == ()
    assert resultado.canon_cambio is False


@pytest.mark.invariants
def test_una_sucesion_legitima_cierra_el_intervalo_anterior(conn: sqlite3.Connection) -> None:
    """El personaje se mudo: se cierra el anterior y se inserta el nuevo."""
    material_minimo(conn)
    anterior = _hecho("h-1", "el puerto", "ev-1")
    nuevo = _hecho("h-2", "el faro", "ev-2")

    resultado = Canonizador(conn).canonizar("bo-1", [nuevo], [anterior], ORDEN)

    assert resultado.intervalos_cerrados == ("h-1",)
    assert resultado.promovidos == ("h-2",)
    assert resultado.defectos == ()


@pytest.mark.invariants
def test_una_contradiccion_genera_defecto_y_no_toca_el_canon(conn: sqlite3.Connection) -> None:
    """El paso que protege el canon: nunca se sobrescribe."""
    material_minimo(conn)
    # Dos hechos vigentes del mismo sujeto y predicado: no hay sucesion que deducir.
    vigentes = [_hecho("h-1", "el puerto", "ev-2"), _hecho("h-0", "la playa", "ev-2")]
    nuevo = _hecho("h-2", "el faro", "ev-1")

    antes = CanonVersionado(conn).revision_actual()
    resultado = Canonizador(conn).canonizar("bo-1", [nuevo], vigentes, ORDEN)

    assert resultado.defectos != ()
    assert resultado.promovidos == ()
    assert CanonVersionado(conn).revision_actual() == antes
    assert all(d.extraccion_evaluada == "hechos_nuevos_detectados" for d in resultado.defectos)


@pytest.mark.invariants
def test_la_cascada_es_parte_del_cierre(conn: sqlite3.Connection) -> None:
    """No es un trabajo posterior opcional: sin ella entra canon fantasma."""
    material_minimo(conn)
    conn.execute(
        "INSERT INTO paquete_contexto (id, tarea_id, revision_canon, hash) "
        "VALUES ('pq-1', 'esc-1:redaccion', 0, 'abc')"
    )
    resultado = Canonizador(conn).canonizar(
        "bo-1", [_hecho("h-1", "el puerto", "ev-1")], [], ORDEN, escena_id="esc-1"
    )
    assert resultado.unidades_invalidadas == ("pq-1",)


# --- SPEC-003 A-05: canonizar anota en que capitulo se usa cada hecho ----------------


@pytest.mark.invariants
def test_canonizar_registra_el_uso_del_hecho_en_su_capitulo(conn: sqlite3.Connection) -> None:
    """RF-BIB-01. Sin esto, cambiar un hecho obliga a regenerar la novela entera.

    El capitulo no se deduce del hecho: se lo da quien canoniza, porque es quien sabe en
    que escena se acepto el borrador. Deducirlo del canon devolveria capitulos que no lo
    narran (F-09 de `verification.md` 11) y la regeneracion tocaria de mas.
    """
    material_minimo(conn)
    resultado = Canonizador(conn).canonizar(
        "bo-1", [_hecho("h-1", "el puerto", "ev-1")], [], ORDEN, capitulo_id="cap-1"
    )

    assert resultado.promovidos == ("h-1",)
    assert UsoDeHechos(conn).capitulos_de("h-1") == ("cap-1",)


@pytest.mark.invariants
def test_un_hecho_que_no_se_promueve_no_registra_uso(conn: sqlite3.Connection) -> None:
    """Un duplicado no aporta nada al capitulo: anotarlo ensancharia la regeneracion."""
    material_minimo(conn)
    vigente = _hecho("h-1", "el puerto", "ev-1")
    Canonizador(conn).canonizar("bo-1", [vigente], [vigente], ORDEN, capitulo_id="cap-1")

    assert UsoDeHechos(conn).capitulos_de("h-1") == ()


@pytest.mark.invariants
def test_canonizar_sin_capitulo_sigue_funcionando_y_no_registra_nada(
    conn: sqlite3.Connection,
) -> None:
    """La canonizacion de SPEC-001 no se rompe: el capitulo es opcional y su ausencia
    significa «no se de que capitulo viene», no «viene de todos»."""
    material_minimo(conn)
    resultado = Canonizador(conn).canonizar(
        "bo-1", [_hecho("h-1", "el puerto", "ev-1")], [], ORDEN
    )

    assert resultado.promovidos == ("h-1",)
    assert UsoDeHechos(conn).capitulos_de("h-1") == ()
