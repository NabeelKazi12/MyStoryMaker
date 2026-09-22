"""Corpus de casos sembrados (bloque A9 del alcance de SPEC-001).

Un par por verificador: un caso con el defecto conocido **de esa sola dimension** y el
mismo caso con la dimension intacta. Los dos miembros del par se construyen a partir del
mismo material, para que la unica diferencia entre ellos sea el defecto sembrado: si
difirieran en algo mas, un fallo no diria cual de las dos cosas lo causo.

Es el material sobre el que corren las dos filas de `verification.md` 7 que miden si los
verificadores detectan y si no inventan defectos.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Any

from backend.domain.diegetic.canon import Hecho, Personaje
from backend.domain.discursive.relato import Escena, Hilo, PerfilDeEstilo
from backend.domain.vocabularies import (
    FuncionEnTrama,
    Relevancia,
    TipoDeEscena,
    TipoDeHilo,
)


@dataclass(frozen=True)
class CasoSembrado:
    """Un par: el material con el defecto y el mismo material sin el."""

    dimension: str
    con_defecto: Any
    intacto: Any
    descripcion: str


# --- material de referencia -----------------------------------------------------------

ORDEN_DE_EVENTO = {"ev-1": 10, "ev-2": 20, "ev-3": 30, "ev-4": 40}

ESCENA = Escena(
    id="esc-1",
    capitulo_id="cap-1",
    orden=1,
    pov_id="per-1",
    lugar_id="lug-1",
    momento_en_historia=10,
    objetivo="recuperar la carta",
    conflicto="el guardia no se mueve",
    resultado="la consigue pero la ven",
    valor_entrada="seguro",
    valor_salida="expuesto",
    funcion_en_trama=FuncionEnTrama.COMPLICACION,
    tipo=TipoDeEscena.ACCION,
    renderiza=("ev-1", "ev-2"),
)

PERFIL = PerfilDeEstilo(id="pe-1", registro="sobrio", vocabulario_prohibido=("palpable",))

HILO_PRINCIPAL = Hilo(
    id="hil-1", tipo=TipoDeHilo.PRINCIPAL, pregunta_dramatica="¿recupera la carta?"
)


def _hecho(identificador: str, objeto: str, desde: str, hasta: str | None = None) -> Hecho:
    return Hecho(
        id=identificador,
        sujeto_id="per-1",
        predicado="ubicacion",
        objeto=objeto,
        valido_desde=desde,
        valido_hasta=hasta,
    )


# --- los pares ------------------------------------------------------------------------

CONTRADICCION = CasoSembrado(
    dimension="contradiccion_de_hechos",
    # Dos ubicaciones distintas del mismo personaje, vigentes a la vez.
    con_defecto=[_hecho("h-1", "el puerto", "ev-1"), _hecho("h-2", "el faro", "ev-2")],
    # El mismo par, pero el primero cierra antes de que el segundo abra.
    intacto=[_hecho("h-1", "el puerto", "ev-1", "ev-2"), _hecho("h-2", "el faro", "ev-2")],
    descripcion="dos hechos funcionales del mismo sujeto con intervalos solapados",
)

ESCENA_SIN_EVENTO = CasoSembrado(
    dimension="escena_con_evento",
    con_defecto=("ev-1",),  # el borrador solo narra uno de los dos prometidos
    intacto=("ev-1", "ev-2"),
    descripcion="el borrador no narra un evento que la escena declaro renderizar",
)

DERIVA_DE_NOMBRES = CasoSembrado(
    dimension="deriva_de_nombres",
    con_defecto="Irene miro la carta. Tobias no dijo nada y salio al patio.",
    intacto="Irene miro la carta. El guardia no dijo nada y salio al patio.",
    descripcion="un nombre propio que no corresponde a ninguna entidad ni alias",
)

REPETICION = CasoSembrado(
    dimension="repeticion_de_ngramas",
    con_defecto="La niebla cerraba el puerto como una mano.",
    intacto="El viento arranco las amarras sin aviso.",
    descripcion="un tetragrama con contenido que ya aparecia en un capitulo anterior",
)
CAPITULO_ANTERIOR = "La niebla cerraba el puerto como una mano sucia."

VOCABULARIO_PROHIBIDO = CasoSembrado(
    dimension="vocabulario_prohibido",
    con_defecto="El silencio era palpable en la sala mientras todos esperaban.",
    intacto="El silencio pesaba en la sala mientras todos esperaban.",
    descripcion="una palabra del vocabulario_prohibido del PerfilDeEstilo",
)

HILO_INACTIVO = CasoSembrado(
    dimension="hilo_inactivo",
    # El hilo principal no avanza en cinco escenas seguidas; su limite son tres.
    con_defecto={
        "esc-1": {"hil-1"},
        "esc-2": set(),
        "esc-3": set(),
        "esc-4": set(),
        "esc-5": set(),
        "esc-6": set(),
    },
    intacto={
        "esc-1": {"hil-1"},
        "esc-2": set(),
        "esc-3": set(),
        "esc-4": {"hil-1"},
        "esc-5": set(),
        "esc-6": {"hil-1"},
    },
    descripcion="un hilo principal inactivo mas escenas de las que su tipo tolera",
)

PROTAGONICO_SIN_HILO = CasoSembrado(
    dimension="protagonico_sin_hilo",
    con_defecto={},
    intacto={"per-1": 1},
    descripcion="un protagonico que no aparece en ningun hilo",
)
PROTAGONICA = Personaje(
    id="per-1",
    nombre_canonico="Irene",
    relevancia=Relevancia.PROTAGONICO,
    necesidad_interna="dejar de cargar con la culpa de su hermano",
)


def _sembrar(instancia: Any, **campos: Any) -> Any:
    """Corrompe una instancia inmutable saltandose su validacion.

    Hace falta precisamente porque el dominio hace su trabajo: `replace` volveria a pasar
    por `__post_init__` y el caso sembrado no llegaria a existir. Un caso sembrado es un
    artefacto deliberadamente corrupto, del tipo que solo puede aparecer por un fallo de
    codigo o por una escritura que esquive el dominio, y el verificador es la segunda red
    que lo atrapa.
    """
    copia = replace(instancia)
    for nombre, valor in campos.items():
        object.__setattr__(copia, nombre, valor)
    return copia


HILO_SIN_PREGUNTA = CasoSembrado(
    dimension="hilo_sin_pregunta_dramatica",
    con_defecto=_sembrar(HILO_PRINCIPAL, pregunta_dramatica="   "),
    intacto=HILO_PRINCIPAL,
    descripcion="un hilo sin pregunta dramatica declarada",
)


TODOS = (
    CONTRADICCION,
    ESCENA_SIN_EVENTO,
    DERIVA_DE_NOMBRES,
    REPETICION,
    VOCABULARIO_PROHIBIDO,
    HILO_INACTIVO,
    PROTAGONICO_SIN_HILO,
    HILO_SIN_PREGUNTA,
)
