"""Worker, contrato del Redactor y el bucle completo de 3.2.

El bucle es el criterio de aceptacion 1 de la spec. Corre con un cliente de modelo falso
—no hay credenciales en este entorno— y eso es suficiente para lo que comprueba: que el
orquestador clasifica, verifica, canoniza, reintenta y escala como debe. Lo que el cliente
falso no prueba es la calidad de la prosa, que no es lo que un test puede decidir.

Cubre RF-WRK-01 a RF-WRK-09 y los criterios 1, 2 y 3 del apartado 10.
"""

from __future__ import annotations

import sqlite3

import pytest

from backend.agents.redactor.redactor import (
    VERSION_DE_PROMPT,
    SalidaInvalida,
    parsear,
    prompt_vigente,
)
from backend.context.ensamblado import Ensamblador
from backend.context.presupuesto import Componente
from backend.domain.diegetic.canon import Hecho
from backend.domain.production.ejecucion import Tarea
from backend.domain.vocabularies import ClaseDeFallo, EstadoDeTarea
from backend.orchestrator.admision import Semaforo
from backend.orchestrator.canonize import Canonizador
from backend.orchestrator.estados import Accion, clasificar, siguiente_accion, transicionar
from backend.orchestrator.plan import DAG, cadena_de_escena
from backend.quality import puertas
from backend.store.repositories import CanonVersionado
from backend.worker.modelo import (
    MAX_TOKENS_REDACCION,
    MODELO_DEL_REDACTOR,
    ClienteFalso,
    FalloDeInvocacion,
    Respuesta,
    construir_cliente_real,
)
from backend.worker.worker import Worker
from tests.conftest import material_minimo

ORDEN = {"ev-1": 10, "ev-2": 20}

RESPUESTA_BUENA = """
## prosa
Irene empujo la puerta y el olor a sal entro con ella.

## hechos_nuevos_detectados
- per-1 | ubicacion | el puerto

## eventos_narrados
- ev-1

## siembras_tocadas
"""

RESPUESTA_SIN_HECHOS = """
## prosa
Irene empujo la puerta y no dijo nada.

## eventos_narrados
- ev-1
"""

RESPUESTA_RENDIDA = """
contexto_insuficiente

## falta
- el nombre canonico del guardia
- si la carta ya se habia mencionado
"""


def _worker(*respuestas: object) -> Worker:
    return Worker(cliente=ClienteFalso(respuestas=list(respuestas)))  # type: ignore[arg-type]


def _respuesta(texto: str) -> Respuesta:
    return Respuesta(
        texto=texto, tokens_entrada=24_000, tokens_salida=900, modelo=MODELO_DEL_REDACTOR
    )


# --- RF-WRK-06 y RF-WRK-09: el contrato del rol --------------------------------------


@pytest.mark.invariants
def test_el_prompt_vigente_existe_y_esta_versionado() -> None:
    assert VERSION_DE_PROMPT == "1.0.0"
    assert "Redactor" in prompt_vigente()


@pytest.mark.invariants
def test_el_max_tokens_es_el_techo_declarado_y_no_uno_mayor() -> None:
    """Con 8.000 la reserva subiria a 32.000 y el caso normal pasaria de 100.000."""
    assert MAX_TOKENS_REDACCION == 4_000
    assert 3 * (24_000 + MAX_TOKENS_REDACCION) + 9_000 <= 100_000


@pytest.mark.invariants
def test_la_salida_valida_se_convierte_en_objeto_tipado() -> None:
    salida = parsear(RESPUESTA_BUENA)
    assert salida.hechos_nuevos_detectados == (("per-1", "ubicacion", "el puerto"),)
    assert salida.eventos_narrados == ("ev-1",)
    assert salida.declaracion_vacia is False


@pytest.mark.invariants
def test_una_salida_vacia_o_sin_prosa_es_fallo_de_contrato() -> None:
    for texto in ("", "   ", "## eventos_narrados\n- ev-1"):
        with pytest.raises(SalidaInvalida):
            parsear(texto)


# --- RF-WRK-05: el agente se rinde en lugar de inventar ------------------------------


@pytest.mark.invariants
def test_contexto_insuficiente_devuelve_su_falta_y_no_prosa() -> None:
    salida = parsear(RESPUESTA_RENDIDA)
    assert salida.contexto_insuficiente is True
    assert salida.prosa == ""
    assert len(salida.falta) == 2


@pytest.mark.invariants
def test_rendirse_sin_decir_que_falta_es_fallo_de_contrato() -> None:
    with pytest.raises(SalidaInvalida):
        parsear("contexto_insuficiente")


# --- RF-WRK-01 a RF-WRK-03: el worker informa, no decide -----------------------------


@pytest.mark.invariants
def test_el_worker_devuelve_procedencia_tambien_cuando_falla() -> None:
    """Una invocacion que se pago y se perdio queda anotada."""
    informe = _worker(FalloDeInvocacion(ClaseDeFallo.TRANSPORTE, "corte de red")).ejecutar(
        "tar-1", "pq-1", "prompt"
    )

    assert informe.tuvo_exito is False
    assert informe.clase_de_fallo is ClaseDeFallo.TRANSPORTE
    assert informe.procedencia.paquete_id == "pq-1"
    assert informe.procedencia.modelo == MODELO_DEL_REDACTOR


@pytest.mark.invariants
def test_el_worker_no_devuelve_ningun_estado_de_tarea() -> None:
    """Las transiciones las escribe solo el Orquestador."""
    informe = _worker(_respuesta(RESPUESTA_BUENA)).ejecutar("tar-1", "pq-1", "prompt")
    assert not hasattr(informe, "estado")
    assert informe.tuvo_exito is True


@pytest.mark.invariants
def test_ningun_registro_de_ejecucion_contiene_prosa() -> None:
    """Los registros referencian el id del Borrador; duplicar el texto crea una copia
    que nadie invalida cuando la escena se reescribe."""
    informe = _worker(_respuesta(RESPUESTA_BUENA)).ejecutar("tar-1", "pq-1", "prompt")
    serializada = str(informe.procedencia)
    assert "Irene" not in serializada


@pytest.mark.invariants
def test_una_salida_truncada_al_techo_es_fallo_de_contrato() -> None:
    """Alcanzar max_tokens no es una invitacion a ampliar el techo."""
    larga = Respuesta(
        texto=RESPUESTA_BUENA,
        tokens_entrada=24_000,
        tokens_salida=99_000,
        modelo=MODELO_DEL_REDACTOR,
    )
    informe = _worker(larga).ejecutar("tar-1", "pq-1", "prompt")
    assert informe.clase_de_fallo is ClaseDeFallo.CONTRATO


@pytest.mark.invariants
def test_el_cliente_real_no_arranca_sin_confirmar_el_modelo() -> None:
    """La salvedad de R-1, hecha codigo: no se invoca a ciegas."""
    with pytest.raises(NotImplementedError) as error:
        construir_cliente_real()
    assert "R-1" in str(error.value)


# --- criterio 1: el bucle completo ---------------------------------------------------


def _paquete(ensamblador: Ensamblador) -> tuple[str, str]:
    ensamblador.poner(Componente.ESTATICO, "premisa y contrato de estilo")
    ensamblador.poner(Componente.ESTADO_DEL_MUNDO, "per-1 esta en el puerto")
    ensamblador.poner(Componente.EPISTEMICO, "el POV sabe donde esta la carta")
    ensamblador.poner(Componente.INSTRUCCION, "escribe la escena esc-1")
    paquete, texto = ensamblador.ensamblar("esc-1:redaccion", "pq-1")
    return paquete.id, texto


@pytest.mark.invariants
def test_el_bucle_completo_acepta_y_canoniza(conn: sqlite3.Connection) -> None:
    """Criterio 1: de alta de canon a Borrador aceptado y canonizado, con revision + 1."""
    material_minimo(conn)
    semaforo = Semaforo()
    dag = DAG({t.id: t for t in cadena_de_escena("esc-1", "pl-1")})
    assert dag.listas() == ("esc-1:redaccion",)

    tarea = dag.tareas["esc-1:redaccion"]
    tarea = transicionar(tarea, EstadoDeTarea.LISTA)

    assert semaforo.admitir(tarea.id, 28_000, tarea.prioridad) is True
    paquete_id, prompt = _paquete(Ensamblador(revision_canon=0, version_de_prompt="1.0.0"))

    informe = _worker(_respuesta(RESPUESTA_BUENA)).ejecutar(tarea.id, paquete_id, prompt)
    semaforo.liberar(tarea.id)
    assert semaforo.en_vuelo == 0

    assert informe.tuvo_exito and informe.salida is not None
    tarea = transicionar(tarea, EstadoDeTarea.EN_CURSO)
    tarea = transicionar(tarea, EstadoDeTarea.EN_VERIFICACION)

    resultado = puertas.Puerta("escena_limpia", puertas.Politica.BLOQUEANTE).evaluar([])
    assert resultado.superada is True

    tarea = transicionar(tarea, EstadoDeTarea.ACEPTADA)
    hechos = [
        Hecho(id="h-1", sujeto_id=s, predicado=p, objeto=o, valido_desde="ev-1")
        for s, p, o in informe.salida.hechos_nuevos_detectados
    ]
    canon = Canonizador(conn).canonizar("bo-1", hechos, [], ORDEN, escena_id="esc-1")

    assert tarea.estado is EstadoDeTarea.ACEPTADA
    assert canon.revision == 1
    assert CanonVersionado(conn).hechos_vigentes_en(1) == {"h-1"}


@pytest.mark.invariants
def test_una_declaracion_vacia_no_da_una_escena_limpia() -> None:
    """F-01 en el bucle: sin hechos declarados no hay nada que contradecir,
    y eso no es limpio."""
    informe = _worker(_respuesta(RESPUESTA_SIN_HECHOS)).ejecutar("tar-1", "pq-1", "prompt")
    assert informe.salida is not None and informe.salida.declaracion_vacia is True

    vacias = ("hechos_nuevos_detectados",) if informe.salida.declaracion_vacia else ()
    resultado = puertas.Puerta("escena_limpia", puertas.Politica.BLOQUEANTE).evaluar(
        [], extracciones_vacias=vacias
    )
    assert resultado.superada is False
    assert "hechos_nuevos_detectados" in resultado.evidencia_ausente


# --- criterios 2 y 3: los dos caminos de la escalera ---------------------------------


def _tarea() -> Tarea:
    return Tarea(id="tar-1", plan_id="pl-1", tipo="redaccion", rol_asignado="redactor")


@pytest.mark.invariants
def test_defecto_repetido_replanifica_en_el_segundo_intento() -> None:
    """Criterio 2: RF-ORQ-06 impide que este caso recorra la escalera entera."""
    tarea = _tarea()
    tarea = clasificar(tarea, ClaseDeFallo.CONTENIDO, "contradiccion")
    assert siguiente_accion(tarea) == Accion.REESCRIBIR
    tarea = clasificar(tarea, ClaseDeFallo.CONTENIDO, "contradiccion")
    assert siguiente_accion(tarea) == Accion.REPLANIFICAR


@pytest.mark.invariants
def test_defectos_distintos_escalan_en_el_cuarto_intento() -> None:
    """Criterio 3: el otro camino, que por eso se comprueba por separado."""
    tarea = _tarea()
    for tipo in ("pov", "contradiccion", "ngramas", "presupuesto"):
        tarea = clasificar(tarea, ClaseDeFallo.CONTENIDO, tipo)
    assert siguiente_accion(tarea) == Accion.ESCALAR
    assert tarea.intentos_narrativos == 4


@pytest.mark.invariants
def test_un_corte_de_red_no_gasta_la_escalera() -> None:
    """Cuatro cortes de red no mandan una escena a escalado sin que nadie lea la prosa."""
    tarea = _tarea()
    for _ in range(4):
        tarea = clasificar(tarea, ClaseDeFallo.TRANSPORTE)
    assert tarea.intentos_narrativos == 0
    assert siguiente_accion(tarea) == Accion.REESCRIBIR
