"""Observabilidad: trazas por novela, spans por rol y tool, coste y scores.

SPEC-003, fase D. Cubre RF-OBS-01 a RF-OBS-05.

Todo corre contra un cliente doble. Es deliberado y es la propiedad que decide si esta
fase esta bien construida: si la suite necesitara Langfuse en marcha, el observador seria
punto unico de fallo y una novela dejaria de escribirse porque esta caido el que mira.
"""

from __future__ import annotations

import pytest

from backend.observability.trazas import (
    ClienteDeObservabilidad,
    ClienteFalsoDeObservabilidad,
    ClienteNulo,
    Observador,
    Score,
    Uso,
)


@pytest.fixture
def doble() -> ClienteFalsoDeObservabilidad:
    return ClienteFalsoDeObservabilidad()


# --- RF-OBS-01: una traza por novela, agrupada por sesion ---------------------------


@pytest.mark.invariants
def test_una_generacion_produce_una_traza_con_su_sesion(
    doble: ClienteFalsoDeObservabilidad,
) -> None:
    """La sesion agrupa entrevista, generacion y regeneraciones de la misma novela."""
    observador = Observador(cliente=doble, sesion="novela-marta")

    with observador.traza("generacion", metadatos={"brief_id": "br-1"}):
        pass

    (traza,) = doble.trazas
    assert traza.nombre == "generacion"
    assert traza.sesion == "novela-marta"
    assert traza.metadatos["brief_id"] == "br-1"
    assert traza.terminada is True


@pytest.mark.invariants
def test_una_regeneracion_posterior_cae_en_la_misma_sesion(
    doble: ClienteFalsoDeObservabilidad,
) -> None:
    """Dos trazas de la misma novela tienen que poder leerse juntas."""
    observador = Observador(cliente=doble, sesion="novela-marta")

    with observador.traza("entrevista"):
        pass
    with observador.traza("regeneracion", metadatos={"motivo": "el perro se llama Nala"}):
        pass

    assert {t.sesion for t in doble.trazas} == {"novela-marta"}
    assert [t.nombre for t in doble.trazas] == ["entrevista", "regeneracion"]


# --- RF-OBS-02: un span por rol y por tool ------------------------------------------


@pytest.mark.invariants
def test_cada_rol_y_cada_tool_aparece_como_span_nombrado(
    doble: ClienteFalsoDeObservabilidad,
) -> None:
    """Un span sin nombre identificable obliga a adivinar quien gasto que."""
    observador = Observador(cliente=doble, sesion="novela-marta")

    with observador.traza("generacion"):
        with observador.span("rol:redactor", tipo="rol", version_de_prompt="1.0.0"):
            pass
        with observador.span("tool:consultar_story_bible", tipo="tool"):
            pass

    assert [s.nombre for s in doble.spans] == [
        "rol:redactor",
        "tool:consultar_story_bible",
    ]
    assert [s.tipo for s in doble.spans] == ["rol", "tool"]
    assert all(s.traza_id for s in doble.spans), "un span sin traza no se puede agrupar"


@pytest.mark.invariants
def test_un_span_registra_su_latencia(doble: ClienteFalsoDeObservabilidad) -> None:
    observador = Observador(cliente=doble, sesion="s")

    with (
        observador.traza("generacion"),
        observador.span("rol:redactor", tipo="rol", version_de_prompt="1.0.0"),
    ):
        pass

    assert doble.spans[0].latencia_ms >= 0


@pytest.mark.invariants
def test_un_span_que_falla_queda_registrado_como_fallido(
    doble: ClienteFalsoDeObservabilidad,
) -> None:
    """Una traza que solo registra lo que salio bien miente por omision."""
    observador = Observador(cliente=doble, sesion="s")

    with pytest.raises(ValueError):  # noqa: PT012 - el fallo es lo que se comprueba
        with (
            observador.traza("generacion"),
            observador.span("rol:redactor", tipo="rol", version_de_prompt="1.0.0"),
        ):
            raise ValueError("el modelo devolvio basura")

    assert doble.spans[0].error is not None
    assert "basura" in doble.spans[0].error


# --- RF-OBS-03: tokens, coste y latencia por llamada, capitulo y novela -------------


@pytest.mark.invariants
def test_el_coste_por_novela_es_la_suma_de_sus_llamadas(
    doble: ClienteFalsoDeObservabilidad,
) -> None:
    """Sin agregacion, «cuanto costo esta novela» se responde a mano con una hoja."""
    observador = Observador(cliente=doble, sesion="novela-marta")

    with observador.traza("generacion"):
        with observador.span("rol:redactor", tipo="rol", version_de_prompt="1.0.0") as span:
            span.registrar_uso(Uso(tokens_entrada=24_000, tokens_salida=3_500, coste=0.041))
        with observador.span("rol:editor", tipo="rol", version_de_prompt="1.0.0") as span:
            span.registrar_uso(Uso(tokens_entrada=8_000, tokens_salida=1_000, coste=0.013))

    assert doble.coste_total() == pytest.approx(0.054)
    assert doble.tokens_totales() == (32_000, 4_500)


@pytest.mark.invariants
def test_el_uso_se_puede_leer_por_capitulo(doble: ClienteFalsoDeObservabilidad) -> None:
    observador = Observador(cliente=doble, sesion="novela-marta")

    with observador.traza("generacion"):
        with observador.span(
            "rol:redactor", tipo="rol", capitulo_id="cap-1", version_de_prompt="1.0.0"
        ) as span:
            span.registrar_uso(Uso(tokens_entrada=1_000, tokens_salida=500, coste=0.01))
        with observador.span(
            "rol:redactor", tipo="rol", capitulo_id="cap-2", version_de_prompt="1.0.0"
        ) as span:
            span.registrar_uso(Uso(tokens_entrada=2_000, tokens_salida=700, coste=0.02))

    assert doble.coste_de_capitulo("cap-2") == pytest.approx(0.02)


# --- RF-OBS-04: los scores de los validadores ---------------------------------------


@pytest.mark.invariants
def test_cada_validador_envia_su_score_a_su_traza(
    doble: ClienteFalsoDeObservabilidad,
) -> None:
    """Un validador que corre y no deja score es un validador que nadie puede auditar."""
    observador = Observador(cliente=doble, sesion="novela-marta")

    with observador.traza("generacion"):
        observador.score(Score(nombre="longitud_de_capitulo", valor=1.0))
        observador.score(
            Score(nombre="guardarrail_palabras_prohibidas", valor=0.0, comentario="ricardo")
        )

    assert [s.nombre for s in doble.scores] == [
        "longitud_de_capitulo",
        "guardarrail_palabras_prohibidas",
    ]
    assert all(s.traza_id for s in doble.scores)
    assert doble.scores[1].comentario == "ricardo"


@pytest.mark.invariants
def test_un_score_fuera_de_traza_no_se_pierde_en_silencio(
    doble: ClienteFalsoDeObservabilidad,
) -> None:
    """Perderlo en silencio haria que un validador pareciera no haber corrido."""
    observador = Observador(cliente=doble, sesion="novela-marta")

    with pytest.raises(RuntimeError) as error:
        observador.score(Score(nombre="suelto", valor=1.0))

    assert "traza" in str(error.value)


# --- RF-OBS-05: los prompts van versionados -----------------------------------------


@pytest.mark.invariants
def test_la_traza_registra_la_version_de_prompt_usada(
    doble: ClienteFalsoDeObservabilidad,
) -> None:
    """Sin la version, la iteracion de tuning no puede decir que produjo cada resultado."""
    observador = Observador(cliente=doble, sesion="novela-marta")

    with observador.traza("generacion"):
        with observador.span("rol:redactor", tipo="rol", version_de_prompt="1.0.0"):
            pass

    assert doble.spans[0].version_de_prompt == "1.0.0"


@pytest.mark.invariants
def test_un_span_de_rol_sin_version_de_prompt_se_rechaza(
    doble: ClienteFalsoDeObservabilidad,
) -> None:
    """Un rol siempre corre con un prompt; no declararlo rompe la reproducibilidad.

    Las tools no lo llevan, porque no tienen prompt: por eso la exigencia es por tipo y
    no general.
    """
    observador = Observador(cliente=doble, sesion="s")

    with observador.traza("generacion"):
        with pytest.raises(ValueError) as error:
            with observador.span("rol:redactor", tipo="rol", version_de_prompt=""):
                pass

    assert "version_de_prompt" in str(error.value)


# --- La propiedad que sostiene la fase: la suite corre sin red ----------------------


@pytest.mark.invariants
def test_con_el_observador_nulo_todo_sigue_funcionando() -> None:
    """RF-OBS y S-02. Si Langfuse esta caido, la novela se escribe igual.

    Lo contrario -que una generacion falle porque el observador no responde- convierte la
    observabilidad en punto unico de fallo, que es exactamente lo que no debe ser.
    """
    observador = Observador(cliente=ClienteNulo(), sesion="sin-red")

    with observador.traza("generacion"):
        with observador.span("rol:redactor", tipo="rol", version_de_prompt="1.0.0") as span:
            span.registrar_uso(Uso(tokens_entrada=1, tokens_salida=1, coste=0.0))
        observador.score(Score(nombre="cualquiera", valor=1.0))


@pytest.mark.invariants
def test_el_cliente_falso_cumple_el_protocolo() -> None:
    """Si el doble se desviara del protocolo, la suite verde no diria nada del real."""
    assert isinstance(ClienteFalsoDeObservabilidad(), ClienteDeObservabilidad)
    assert isinstance(ClienteNulo(), ClienteDeObservabilidad)
