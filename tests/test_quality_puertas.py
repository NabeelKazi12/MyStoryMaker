"""Las puertas bloquean lo que deben y no dan por superado lo que no han mirado.

Cubre RF-QUA-11 a RF-QUA-14, RF-QUA-18 y RF-QUA-20.
"""

from __future__ import annotations

import pytest

from backend.domain.production.ejecucion import Defecto
from backend.domain.vocabularies import Severidad
from backend.quality import puertas


def _defecto(severidad: Severidad = Severidad.CRITICA) -> Defecto:
    return Defecto(
        id="d-1",
        tipo="contradiccion_de_hechos",
        severidad=severidad,
        regla_violada="intervalos solapados",
        evidencia="h-1 y h-2 solapan en ev-4",
        extraccion_evaluada="hechos_nuevos_detectados",
    )


# --- RF-QUA-14: la ausencia de evidencia nunca es evidencia favorable ----------------


@pytest.mark.invariants
@pytest.mark.parametrize(
    "constructor",
    [
        puertas.escena_limpia,
        puertas.capitulo_cerrado,
        puertas.volumen_cerrado,
        puertas.outline_aprobado,
    ],
    ids=["escena_limpia", "capitulo_cerrado", "volumen_cerrado", "outline_aprobado"],
)
def test_una_puerta_sin_defectos_no_esta_superada_si_le_falta_evidencia(
    constructor: object,
) -> None:
    """Es el principio 8: no encontrar nada porque no se ha mirado no es estar limpio."""
    resultado = constructor().evaluar([])  # type: ignore[operator]

    assert resultado.defectos == ()
    assert resultado.evidencia_ausente != ()
    assert resultado.superada is False
    assert resultado.detiene_el_avance is True


@pytest.mark.invariants
def test_escena_limpia_declara_los_tres_invariantes_que_v1_no_implementa() -> None:
    """Fuga epistemica, disciplina de POV y regla del mundo: ausentes, no superados."""
    resultado = puertas.escena_limpia().evaluar([])

    assert set(resultado.evidencia_ausente) == {
        "fuga_epistemica",
        "disciplina_de_pov",
        "violacion_de_regla_del_mundo",
    }
    assert "evidencia ausente" in resultado.explicacion()


@pytest.mark.invariants
def test_ningun_invariante_ausente_aparece_como_superado() -> None:
    """La comprobacion que exige RF-QUA-14, dicha al reves."""
    for constructor in (puertas.escena_limpia, puertas.volumen_cerrado):
        resultado = constructor().evaluar([])
        for ausente in resultado.evidencia_ausente:
            assert ausente not in resultado.explicacion().split("evidencia ausente")[0]


# --- RF-QUA-11 a RF-QUA-13: la puerta bloquea con defectos criticos ------------------


@pytest.mark.invariants
def test_un_defecto_critico_detiene_el_avance() -> None:
    resultado = puertas.escena_limpia().evaluar([_defecto()])

    assert resultado.bloqueantes != ()
    assert resultado.detiene_el_avance is True
    assert "1 defecto(s) critico(s)" in resultado.explicacion()


@pytest.mark.invariants
def test_un_defecto_no_critico_no_bloquea_por_si_solo() -> None:
    """Solo lo critico para la linea; lo demas penaliza y queda anotado."""
    resultado = puertas.escena_limpia().evaluar([_defecto(Severidad.BAJA)])

    assert resultado.bloqueantes == ()
    # Sigue sin superarse, pero por la evidencia ausente de v1, no por ese defecto.
    assert resultado.evidencia_ausente != ()


@pytest.mark.invariants
def test_una_puerta_sin_ausencias_y_sin_criticos_se_supera() -> None:
    """El caso limpio de verdad: nada ausente y nada critico."""
    puerta = puertas.Puerta("prueba", puertas.Politica.BLOQUEANTE, ausentes=())
    resultado = puerta.evaluar([_defecto(Severidad.MEDIA)])

    assert resultado.superada is True
    assert resultado.detiene_el_avance is False
    assert resultado.explicacion() == "prueba: superada"


# --- RF-QUA-20: el bloque declarado vacio no pasa en silencio ------------------------


@pytest.mark.invariants
def test_un_bloque_de_extraccion_vacio_no_da_una_escena_limpia() -> None:
    """F-01: si el Redactor no declara ningun hecho, no hay nada que contradecir.

    Sin esto, la escena pasaria la puerta precisamente porque el verificador no tuvo
    entrada sobre la que correr, que es la definicion de fallo silencioso.
    """
    puerta = puertas.Puerta("escena_limpia", puertas.Politica.BLOQUEANTE, ausentes=())
    resultado = puerta.evaluar([], extracciones_vacias=("hechos_nuevos_detectados",))

    assert resultado.defectos == ()
    assert "hechos_nuevos_detectados" in resultado.evidencia_ausente
    assert resultado.superada is False


# --- politica de advertencia ---------------------------------------------------------


@pytest.mark.invariants
def test_una_puerta_de_advertencia_nunca_detiene_el_avance() -> None:
    """Acto cerrado es de grado: un acto con la curva algo plana sigue siendo un acto."""
    puerta = puertas.Puerta("acto_cerrado", puertas.Politica.ADVERTENCIA, ausentes=("curva",))
    resultado = puerta.evaluar([_defecto()])

    assert resultado.bloqueantes != ()
    assert resultado.detiene_el_avance is False
