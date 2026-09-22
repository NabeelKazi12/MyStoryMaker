"""Invariantes del dominio, comprobados antes de llegar a la base de datos.

Cubre RF-DOM-04, RF-DOM-05, RF-DOM-06, RF-DOM-07 y RF-DOM-08.
"""

from __future__ import annotations

import dataclasses

import pytest

from backend.domain.diegetic.canon import (
    Entidad,
    EventoNarrativo,
    Hecho,
    Lugar,
    Personaje,
)
from backend.domain.discursive.relato import Escena, Hilo, ParSiembraPago
from backend.domain.errors import ErrorDeDominio
from backend.domain.production.ejecucion import (
    Borrador,
    Defecto,
    Intento,
    PaqueteDeContexto,
    RegistroDeDecision,
    Tarea,
)
from backend.domain.spec.encargo import Brief
from backend.domain.vocabularies import (
    ClaseDeFallo,
    EstadoDeSiembra,
    FuncionEnTrama,
    Relevancia,
    Severidad,
    TipoDeEscena,
    TipoDeEvento,
    TipoDeHilo,
    TipoDeSiembra,
)

# --- material minimo valido, para que cada test solo rompa lo que quiere romper -------

ESCENA_VALIDA = {
    "id": "esc-1",
    "capitulo_id": "cap-1",
    "orden": 1,
    "pov_id": "per-1",
    "lugar_id": "lug-1",
    "momento_en_historia": 10,
    "objetivo": "recuperar la carta",
    "conflicto": "el guardia no se mueve",
    "resultado": "la consigue pero la ven",
    "valor_entrada": "seguro",
    "valor_salida": "expuesto",
    "funcion_en_trama": FuncionEnTrama.COMPLICACION,
    "tipo": TipoDeEscena.ACCION,
    "renderiza": ("ev-1",),
}


def test_escena_valida_se_construye() -> None:
    """El material de referencia es valido: si no, los demas tests no prueban nada."""
    assert Escena(**ESCENA_VALIDA).id == "esc-1"


# --- RF-DOM-04 y RF-DOM-05 -----------------------------------------------------------


@pytest.mark.invariants
def test_escena_con_valor_entrada_igual_a_salida_falla() -> None:
    """Una escena en la que nada cambia es una escena que sobra."""
    with pytest.raises(ErrorDeDominio) as error:
        Escena(**{**ESCENA_VALIDA, "valor_salida": ESCENA_VALIDA["valor_entrada"]})

    assert error.value.clase == "Escena"
    assert "valor_entrada" in error.value.invariante


@pytest.mark.invariants
def test_escena_sin_evento_renderizado_falla() -> None:
    """Sin aristas renderiza no hay puente con el plano diegetico."""
    with pytest.raises(ErrorDeDominio) as error:
        Escena(**{**ESCENA_VALIDA, "renderiza": ()})

    assert error.value.clase == "Escena"
    assert "al menos un EventoNarrativo" in error.value.invariante


# --- RF-DOM-06 -----------------------------------------------------------------------


@pytest.mark.invariants
def test_hecho_exige_valido_desde() -> None:
    """Ningun hecho es atemporal: la vigencia se ancla a un evento, no a una fecha."""
    with pytest.raises(ErrorDeDominio) as error:
        Hecho(
            id="h-1", sujeto_id="per-1", predicado="ubicacion", objeto="puerto", valido_desde=""
        )

    assert error.value.clase == "Hecho"
    assert "valido_desde" in error.value.invariante


@pytest.mark.invariants
def test_hecho_sin_valido_hasta_esta_vigente() -> None:
    """Nulo significa vigente, no significa desconocido."""
    hecho = Hecho(
        id="h-1", sujeto_id="per-1", predicado="ubicacion", objeto="puerto", valido_desde="ev-1"
    )
    assert hecho.vigente is True
    assert dataclasses.replace(hecho, valido_hasta="ev-9").vigente is False


@pytest.mark.invariants
def test_hecho_no_abre_y_cierra_en_el_mismo_evento() -> None:
    """Un intervalo de longitud cero no es un intervalo."""
    with pytest.raises(ErrorDeDominio):
        Hecho(
            id="h-1",
            sujeto_id="per-1",
            predicado="ubicacion",
            objeto="puerto",
            valido_desde="ev-1",
            valido_hasta="ev-1",
        )


# --- RF-DOM-07 -----------------------------------------------------------------------


@pytest.mark.invariants
@pytest.mark.parametrize(
    "clase", [Entidad, Personaje, Lugar], ids=["Entidad", "Personaje", "Lugar"]
)
def test_ninguna_entidad_expone_dimensiones_variables(clase: type) -> None:
    """Ubicacion, lealtad, salud, posesion y emocion son Hecho, no campos de la entidad."""
    prohibidos = {
        "ubicacion",
        "lealtad",
        "salud",
        "posesion",
        "poseedor",
        "emocion",
        "estado_emocional",
        "recursos",
        "reputacion",
        "conoce",
    }
    campos = {f.name for f in dataclasses.fields(clase)}
    assert not (campos & prohibidos), (
        f"{clase.__name__} expone dimensiones variables como atributo estatico: "
        f"{sorted(campos & prohibidos)}"
    )


@pytest.mark.invariants
def test_protagonico_sin_necesidad_interna_falla() -> None:
    """El invariante de Personaje de definitions.md, en su mitad comprobable aqui."""
    with pytest.raises(ErrorDeDominio) as error:
        Personaje(
            id="per-1",
            nombre_canonico="Irene",
            relevancia=Relevancia.PROTAGONICO,
            necesidad_interna="  ",
        )

    assert "necesidad_interna" in error.value.invariante


# --- RF-DOM-08 -----------------------------------------------------------------------


@pytest.mark.invariants
def test_los_mensajes_nombran_clase_e_invariante() -> None:
    """CLAUDE.md 5.3: el mensaje va en espanol y nombra la clase y el invariante violado."""
    with pytest.raises(ErrorDeDominio) as error:
        Escena(**{**ESCENA_VALIDA, "renderiza": ()})

    mensaje = str(error.value)
    assert mensaje.startswith("Escena: ")
    assert "id='esc-1'" in mensaje


# --- resto del nucleo ----------------------------------------------------------------


@pytest.mark.invariants
def test_evento_no_se_causa_a_si_mismo() -> None:
    """El ciclo mas corto posible del grafo causal se corta en el dominio."""
    with pytest.raises(ErrorDeDominio):
        EventoNarrativo(
            id="ev-1",
            descripcion="la carta cambia de manos",
            posicion_en_historia=10,
            tipo=TipoDeEvento.ACCION,
            causa=("ev-1",),
        )


@pytest.mark.invariants
def test_hilo_exige_pregunta_dramatica() -> None:
    """Lo cobra la puerta Outline aprobado, pero se rechaza ya al construir."""
    with pytest.raises(ErrorDeDominio):
        Hilo(id="hil-1", tipo=TipoDeHilo.PRINCIPAL, pregunta_dramatica="   ")


@pytest.mark.invariants
def test_hilo_cerrado_por_resolucion_o_por_abandono() -> None:
    abierto = Hilo(id="hil-1", tipo=TipoDeHilo.PRINCIPAL, pregunta_dramatica="¿vuelve?")
    assert abierto.cerrado is False
    assert dataclasses.replace(abierto, resuelto_en="esc-9").cerrado is True
    assert dataclasses.replace(abierto, abandonado=True).cerrado is True


@pytest.mark.invariants
def test_siembra_resuelta_declara_su_pago() -> None:
    with pytest.raises(ErrorDeDominio):
        ParSiembraPago(
            id="sp-1",
            tipo=TipoDeSiembra.OBJETO,
            escena_siembra="esc-1",
            estado=EstadoDeSiembra.RESUELTO,
        )


@pytest.mark.invariants
def test_registro_de_decision_exige_alternativa_descartada() -> None:
    """Sin alternativa descartada, la decision se vuelve a discutir dentro de un mes."""
    with pytest.raises(ErrorDeDominio):
        RegistroDeDecision(id="rd-1", decision="usar SQLite", motivo="volumen pequeno")


@pytest.mark.invariants
def test_brief_exige_promesa_al_lector() -> None:
    with pytest.raises(ErrorDeDominio):
        Brief(
            id="br-1",
            genero="misterio",
            premisa="una carta que no deberia existir",
            promesa_al_lector="",
            extension_objetivo=120_000,
        )


@pytest.mark.invariants
def test_paquete_de_contexto_exige_hash() -> None:
    """Sin hash no se puede reproducir una generacion pasada."""
    with pytest.raises(ErrorDeDominio):
        PaqueteDeContexto(id="pq-1", tarea_id="tar-1", revision_canon=3, hash="")


# --- historial tipificado de intentos (R-3) ------------------------------------------


@pytest.mark.invariants
def test_solo_contrato_y_contenido_suman_intento_narrativo() -> None:
    """Un corte de red no debe consumir el presupuesto de reescrituras de una escena."""
    tarea = Tarea(
        id="tar-1",
        plan_id="pl-1",
        tipo="redaccion",
        rol_asignado="redactor",
        historial=(
            Intento(numero=1, clase_de_fallo=ClaseDeFallo.TRANSPORTE),
            Intento(
                numero=2, clase_de_fallo=ClaseDeFallo.CONTENIDO, tipo_de_defecto="contradiccion"
            ),
            Intento(numero=3, clase_de_fallo=ClaseDeFallo.PRESUPUESTO),
            Intento(numero=4, clase_de_fallo=ClaseDeFallo.CONTRATO, tipo_de_defecto="esquema"),
        ),
    )
    assert tarea.intentos_narrativos == 2
    assert tarea.intentos_de_infraestructura == 2


@pytest.mark.invariants
def test_dos_defectos_consecutivos_del_mismo_tipo_se_detectan() -> None:
    """Es la condicion que manda replanificar en lugar de reescribir otra vez."""
    base = {"plan_id": "pl-1", "tipo": "redaccion", "rol_asignado": "redactor"}
    distintos = Tarea(
        id="tar-1",
        **base,
        historial=(
            Intento(numero=1, clase_de_fallo=ClaseDeFallo.CONTENIDO, tipo_de_defecto="pov"),
            Intento(
                numero=2, clase_de_fallo=ClaseDeFallo.CONTENIDO, tipo_de_defecto="contradiccion"
            ),
        ),
    )
    iguales = Tarea(
        id="tar-2",
        **base,
        historial=(
            Intento(
                numero=1, clase_de_fallo=ClaseDeFallo.CONTENIDO, tipo_de_defecto="contradiccion"
            ),
            Intento(
                numero=2, clase_de_fallo=ClaseDeFallo.CONTENIDO, tipo_de_defecto="contradiccion"
            ),
        ),
    )
    assert distintos.repite_tipo_de_defecto is False
    assert iguales.repite_tipo_de_defecto is True


@pytest.mark.invariants
def test_defecto_sin_evidencia_se_reconoce() -> None:
    """La proporcion descartada delata a un agente que opina en vez de comprobar."""
    sin = Defecto(
        id="df-1",
        tipo="contradiccion",
        severidad=Severidad.CRITICA,
        regla_violada="intervalos solapados",
        evidencia="   ",
    )
    assert sin.tiene_evidencia is False
    assert (
        dataclasses.replace(sin, evidencia="h-1 y h-2 solapan en ev-4").tiene_evidencia is True
    )


@pytest.mark.invariants
def test_recuento_de_palabras_es_derivado() -> None:
    """Se calcula del texto: un recuento declarado a mano miente en cuanto se edita."""
    borrador = Borrador(id="bo-1", escena_id="esc-1", version=1, texto="tres palabras aqui")
    assert borrador.recuento_palabras == 3
