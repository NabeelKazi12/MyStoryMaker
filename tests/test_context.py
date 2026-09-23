"""Ensamblado del paquete: orden, recuento, filtros, recorte y hash.

Cubre RF-CTX-01 a RF-CTX-08.
"""

from __future__ import annotations

import pytest

from backend.context.ensamblado import (
    Ensamblador,
    bloque_de_arco,
    bloqueada_por_presupuesto,
)
from backend.context.filtros import (
    AlcanceDeRelevancia,
    FiltroEpistemico,
    FiltroEstructural,
    FiltroTemporal,
)
from backend.context.presupuesto import (
    INTOCABLES,
    MAXIMO_DE_ENTRADA,
    ORDEN_DE_RECORTE,
    TECHO_DE_SALIDA_REDACCION,
    TECHO_DEL_SISTEMA,
    Componente,
    PresupuestoExcedido,
    PresupuestoFueraDeRango,
    contar_tokens,
)
from backend.domain.diegetic.canon import Hecho
from backend.domain.production.ejecucion import Defecto
from backend.domain.vocabularies import Severidad

ORDEN_DE_EVENTO = {"ev-1": 10, "ev-2": 20, "ev-3": 30}


def _ensamblador(presupuesto: int = 24_000) -> Ensamblador:
    return Ensamblador(revision_canon=3, version_de_prompt="1.0.0", presupuesto=presupuesto)


def _completo(ens: Ensamblador, tamano: int = 20) -> Ensamblador:
    for componente in Componente:
        if componente is Componente.DEFECTOS_ABIERTOS:
            continue
        ens.poner(componente, f"{componente.name} " + "palabra " * tamano)
    return ens


# --- RF-CTX-01: el orden de componentes es parte del contrato ------------------------


@pytest.mark.invariants
def test_el_paquete_sale_en_el_orden_del_contrato_de_rol() -> None:
    """Estatico, estado del mundo, continuidad, arco, voz, epistemico, promesas, instruccion."""
    ens = _ensamblador()
    # Se ponen en desorden a proposito: el orden de llamada no debe influir.
    for componente in reversed(list(Componente)):
        if componente is Componente.DEFECTOS_ABIERTOS:
            continue
        ens.poner(componente, componente.name)

    paquete, texto = ens.ensamblar("tar-1", "pq-1")

    assert [nombre for nombre, _ in paquete.tokens_por_componente] == [
        "ESTATICO",
        "ESTADO_DEL_MUNDO",
        "CONTINUIDAD",
        "ARCO",
        "VOZ",
        "EPISTEMICO",
        "PROMESAS",
        "INSTRUCCION",
    ]
    assert texto.index("ESTATICO") < texto.index("INSTRUCCION")


@pytest.mark.invariants
def test_los_defectos_abiertos_van_al_final() -> None:
    """Es lo unico que cambia entre intentos, y por eso es lo ultimo del paquete."""
    ens = _completo(_ensamblador())
    ens.con_defectos(
        [
            Defecto(
                id="d-1",
                tipo="contradiccion_de_hechos",
                severidad=Severidad.CRITICA,
                regla_violada="intervalos solapados",
                evidencia="h-1 y h-2 solapan",
            )
        ]
    )
    paquete, texto = ens.ensamblar("tar-1", "pq-1")

    assert paquete.tokens_por_componente[-1][0] == "DEFECTOS_ABIERTOS"
    assert texto.rstrip().endswith("h-1 y h-2 solapan")


# --- RF-CTX-02: se cuenta antes de invocar y se guarda el recuento real --------------


@pytest.mark.invariants
def test_el_recuento_guardado_coincide_con_lo_contado() -> None:
    ens = _completo(_ensamblador())
    paquete, texto = ens.ensamblar("tar-1", "pq-1")

    por_componente = dict(paquete.tokens_por_componente)
    assert por_componente["ESTATICO"] == contar_tokens("ESTATICO " + "palabra " * 20)
    assert paquete.tokens_totales == sum(por_componente.values())


# --- RF-CTX-03 y RF-CTX-04: recorte en orden fijo, intocables intactos ---------------


@pytest.mark.invariants
def test_el_recorte_sigue_el_orden_fijo() -> None:
    """Se sueltan primero los niveles mas lejanos: arco, luego promesas, luego continuidad."""
    ens = _completo(_ensamblador(presupuesto=280), tamano=40)
    antes = {c: b.tokens for c, b in ens._bloques.items()}
    paquete, _ = ens.ensamblar("tar-1", "pq-1")
    despues = dict(paquete.tokens_por_componente)

    # El primero del orden de recorte pierde tokens antes que el ultimo.
    primero, ultimo = ORDEN_DE_RECORTE[0], ORDEN_DE_RECORTE[-1]
    perdido_primero = antes[primero] - despues.get(primero.name, 0)
    perdido_ultimo = antes[ultimo] - despues.get(ultimo.name, 0)
    assert perdido_primero >= perdido_ultimo


@pytest.mark.invariants
def test_los_tres_intocables_no_se_recortan_nunca() -> None:
    """Truncar la instruccion es perder el encargo; recortar lo epistemico produce fugas."""
    ens = _completo(_ensamblador(presupuesto=280), tamano=40)
    antes = {c: b.tokens for c, b in ens._bloques.items()}
    paquete, _ = ens.ensamblar("tar-1", "pq-1")
    despues = dict(paquete.tokens_por_componente)

    for componente in INTOCABLES:
        if componente in antes:
            assert despues.get(componente.name) == antes[componente]


@pytest.mark.invariants
def test_un_paquete_que_no_cabe_no_se_trunca_sino_que_bloquea() -> None:
    """Es el caso previsto: Tarea a bloqueada con falta, nunca truncar por la cola."""
    ens = _ensamblador(presupuesto=10)
    ens.poner(Componente.ESTATICO, "palabra " * 200)
    ens.poner(Componente.INSTRUCCION, "palabra " * 200)

    with pytest.raises(PresupuestoExcedido) as error:
        ens.ensamblar("tar-1", "pq-1")

    falta = bloqueada_por_presupuesto(error.value)
    assert any("excede su presupuesto" in f for f in falta)
    assert any("filtro estructural" in f for f in falta)
    assert any("no subir el presupuesto" in f for f in falta)


# --- RF-CTX-08: el paquete de redaccion no supera su techo ---------------------------


@pytest.mark.invariants
def test_el_paquete_de_redaccion_no_supera_25000_tokens() -> None:
    ens = _completo(_ensamblador(), tamano=500)
    paquete, _ = ens.ensamblar("tar-1", "pq-1")
    assert paquete.tokens_totales <= 25_000


# --- RF-CTX-05: el filtro temporal actua antes que el epistemico ---------------------


def _hecho(
    identificador: str, desde: str, hasta: str | None = None, sujeto: str = "per-1"
) -> Hecho:
    return Hecho(
        id=identificador,
        sujeto_id=sujeto,
        predicado="ubicacion",
        objeto="el puerto",
        valido_desde=desde,
        valido_hasta=hasta,
    )


@pytest.mark.invariants
def test_un_hecho_invalidado_antes_del_momento_no_entra() -> None:
    """Un hecho invalidado en el capitulo 8 no aparece al escribir el 12."""
    filtro = FiltroTemporal(momento=25, orden_de_evento=ORDEN_DE_EVENTO)
    vigentes = filtro.aplicar([_hecho("h-1", "ev-1", "ev-2"), _hecho("h-2", "ev-2")])

    assert [h.id for h in vigentes] == ["h-2"]


@pytest.mark.invariants
def test_un_hecho_posterior_al_momento_tampoco_entra() -> None:
    filtro = FiltroTemporal(momento=15, orden_de_evento=ORDEN_DE_EVENTO)
    assert filtro.aplicar([_hecho("h-3", "ev-3")]) == ()


@pytest.mark.invariants
def test_el_orden_de_los_filtros_es_temporal_luego_epistemico() -> None:
    """Aplicar el epistemico antes decidiria que existe en funcion de quien mira."""
    alcance = AlcanceDeRelevancia(
        temporal=FiltroTemporal(momento=25, orden_de_evento=ORDEN_DE_EVENTO),
        epistemico=FiltroEpistemico(),
        estructural=FiltroEstructural(entidades_presentes=frozenset({"per-1"})),
    )
    resultado = alcance.aplicar(
        [
            _hecho("h-1", "ev-1", "ev-2"),
            _hecho("h-2", "ev-2"),
            _hecho("h-3", "ev-2", sujeto="per-9"),
        ]
    )
    # h-1 lo descarta el temporal; h-3, el estructural.
    assert [h.id for h in resultado] == ["h-2"]


@pytest.mark.invariants
def test_el_filtro_epistemico_existe_y_en_v1_no_filtra() -> None:
    """Su punto de insercion esta puesto, aunque la fase 2 aun no exista (S-9)."""
    hechos = [_hecho("h-1", "ev-1")]
    assert FiltroEpistemico().aplicar(hechos) == tuple(hechos)

    with pytest.raises(NotImplementedError) as error:
        FiltroEpistemico(activo=True).aplicar(hechos)
    assert "fase 2" in str(error.value)


# --- RF-CTX-06: hash estable y ligado a la revision ----------------------------------


@pytest.mark.invariants
def test_mismo_canon_y_misma_escena_dan_el_mismo_hash() -> None:
    uno, _ = _completo(_ensamblador()).ensamblar("tar-1", "pq-1")
    otro, _ = _completo(_ensamblador()).ensamblar("tar-1", "pq-2")
    assert uno.hash == otro.hash


@pytest.mark.invariants
def test_otra_revision_de_canon_da_otro_hash() -> None:
    """Dos paquetes de igual texto sobre canones distintos no son intercambiables."""
    uno, _ = _completo(_ensamblador()).ensamblar("tar-1", "pq-1")
    otra_revision = Ensamblador(revision_canon=4, version_de_prompt="1.0.0")
    otro, _ = _completo(otra_revision).ensamblar("tar-1", "pq-1")
    assert uno.hash != otro.hash


@pytest.mark.invariants
def test_otra_version_de_prompt_da_otro_hash() -> None:
    """Editar un prompt sin subir la version se detecta: el hash cambia y la version no."""
    uno, _ = _completo(_ensamblador()).ensamblar("tar-1", "pq-1")
    otra = Ensamblador(revision_canon=3, version_de_prompt="1.1.0")
    otro, _ = _completo(otra).ensamblar("tar-1", "pq-1")
    assert uno.hash != otro.hash


# --- RF-CTX-07: nada se acumula entre intentos ---------------------------------------


@pytest.mark.invariants
def test_el_paquete_del_intento_2_no_contiene_el_borrador_rechazado() -> None:
    """Reinyectarlo invita a reproducirlo: el intento 2 vuelve a escribir, no parchea."""
    prosa_rechazada = "La niebla cerraba el puerto como una mano sucia."

    intento_1 = _completo(_ensamblador())
    _, texto_1 = intento_1.ensamblar("tar-1", "pq-1")

    intento_2 = _completo(_ensamblador())
    intento_2.con_defectos(
        [
            Defecto(
                id="d-1",
                tipo="contradiccion_de_hechos",
                severidad=Severidad.CRITICA,
                regla_violada="intervalos solapados",
                evidencia="h-1 y h-2 solapan",
            )
        ]
    )
    _, texto_2 = intento_2.ensamblar("tar-1", "pq-2")

    assert prosa_rechazada not in texto_1
    assert prosa_rechazada not in texto_2
    # Lo unico que cambia entre intentos es la cola.
    assert texto_2.startswith(texto_1[: len(texto_1) // 2])


@pytest.mark.invariants
def test_el_paquete_no_crece_con_la_longitud_del_libro() -> None:
    """El de la escena 3 y el de la escena 40 miden lo mismo, o es un bug."""
    escena_3, _ = _completo(_ensamblador(), tamano=30).ensamblar("tar-3", "pq-3")
    escena_40, _ = _completo(_ensamblador(), tamano=30).ensamblar("tar-40", "pq-40")
    assert escena_3.tokens_totales == escena_40.tokens_totales


# --- RF-CTX-08: el techo de 100.000 es un limite, no un valor por defecto -------------


@pytest.mark.invariants
def test_un_presupuesto_por_encima_del_maximo_de_entrada_no_se_acepta() -> None:
    """RF-CTX-08. Sin esto, el tope de 25.000 es el valor por defecto de un parametro.

    Quien llama podria pedir un paquete de 500.000 y el ensamblador lo serviria: el techo
    del sistema dejaria de ser un techo sin que nadie lo hubiera derogado.
    """
    with pytest.raises(PresupuestoFueraDeRango) as error:
        Ensamblador(
            revision_canon=3,
            version_de_prompt="1.0.0",
            presupuesto=MAXIMO_DE_ENTRADA + 1,
        )

    assert str(MAXIMO_DE_ENTRADA) in str(error.value)


@pytest.mark.invariants
def test_ninguna_invocacion_de_redaccion_puede_agotar_el_techo_del_sistema() -> None:
    """Entrada maxima mas techo de salida tiene que caber, y con sitio para otra tarea."""
    reserva_maxima = MAXIMO_DE_ENTRADA + TECHO_DE_SALIDA_REDACCION

    assert reserva_maxima <= TECHO_DEL_SISTEMA
    # El caso normal de `architecture.md` 4.2: tres redacciones y un juicio en vuelo.
    assert 3 * reserva_maxima + 9_000 <= TECHO_DEL_SISTEMA


# --- SPEC-003 A-06: los resumenes entran al paquete, la prosa no ---------------------


@pytest.mark.invariants
def test_el_arco_se_compone_de_resumenes_y_nunca_de_prosa_literal() -> None:
    """RF-BIB-03. El componente de arco es la piramide, y la piramide son resumenes.

    Que el bloque se construya aqui y no en cada llamador es lo que impide que alguien
    «solo por esta vez» meta el texto del capitulo anterior: el paquete dejaria de medir
    lo mismo en el capitulo 3 y en el 40.
    """
    bloque = bloque_de_arco(
        (
            ("ca-1", "Marta aprende a nadar."),
            ("ca-2", "Marta vuelve al pueblo y discute con su hermana."),
        )
    )

    assert "ca-1" in bloque
    assert "Marta aprende a nadar." in bloque
    assert bloque.index("ca-1") < bloque.index("ca-2"), "el orden de lectura se conserva"


@pytest.mark.invariants
def test_sin_capitulos_anteriores_el_arco_queda_vacio_y_no_ocupa_presupuesto() -> None:
    """El primer capitulo no tiene arco. Un encabezado vacio gastaria tokens por nada."""
    assert bloque_de_arco(()) == ""
