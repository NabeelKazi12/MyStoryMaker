"""Validadores deterministas de la personalizacion.

Son los tres que convierten «esta novela es un regalo para Marta» en algo comprobable:
que el nombre este escrito como en la story bible, que el capitulo mida lo que tiene que
medir, y que cada elemento obligatorio haya llegado a algun capitulo.

Los tres son deterministas, dan el mismo resultado sobre la misma entrada y por eso
**bloquean** (`architecture.md` 7.1). Lo que ninguno comprueba es si el capitulo esta
bien escrito: un texto puede nombrar bien a todos, medir lo que toca y traer todos los
recuerdos, y ser ilegible. Eso lo cobra el juez con rubrica, que penaliza y no bloquea.

Cubre RF-VAL-02, RF-VAL-03, RF-VAL-04 y RF-VAL-09.
"""

from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from enum import Enum

from backend.domain.production.ejecucion import Defecto
from backend.domain.spec.encargo import Destinatario
from backend.domain.vocabularies import Severidad
from backend.quality.guardarrail import normalizar
from backend.store.repositories import UsoDeHechos

# Rango de palabras por capitulo. Es un presupuesto declarado de diseno, no una medida:
# `architecture.md` 4.2 fija el techo de salida en 4.000 tokens, que caen alrededor de
# estas cifras. El brief puede estrecharlo, nunca ensancharlo sin spec.
RANGO_DE_CAPITULO: tuple[int, int] = (800, 3_000)

PALABRAS = re.compile(r"\w+", re.UNICODE)


class PuntoDeEjecucion(Enum):
    """Donde corre un validador. Es lo que decide que pasa cuando falla.

    Un fallo en el hook devuelve el capitulo al writer; uno en la puerta impide publicar
    la version. Sin declararlo, un validador que falla no se sabe a quien interrumpe.
    """

    HOOK_DE_CAPITULO = "hook_de_capitulo"
    HOOK_DE_POLICY = "hook_de_policy"
    ROL_EDITOR = "rol_editor"
    PUERTA_DE_PUBLICACION = "puerta_de_publicacion"


@dataclass(frozen=True)
class Validador:
    """Una fila del registro: como se llama, cuando corre y que requisito cobra."""

    nombre: str
    punto: PuntoDeEjecucion
    requisito: str
    descripcion: str
    bloquea: bool = True


def _defecto(tipo: str, severidad: Severidad, regla: str, evidencia: str) -> Defecto:
    return Defecto(
        id=f"{tipo}:{abs(hash(evidencia)) % 10**10}",
        tipo=tipo,
        severidad=severidad,
        regla_violada=regla,
        evidencia=evidencia,
    )


# --- RF-VAL-02: los nombres, escritos como en la story bible -------------------------


def nombres_exactos(
    texto: str, *, destinatario: Destinatario, personajes: Sequence[str] = ()
) -> list[Defecto]:
    """Detecta nombres **casi** correctos: los que normalizan igual y se escriben distinto.

    No exige que el nombre aparezca: que el destinatario salga en algun capitulo lo cobra
    RF-VAL-04. Exigirlo tambien aqui haria fallar los capitulos que legitimamente no lo
    nombran, y dos validadores respondiendo a la misma pregunta dejan sin decidir cual
    manda.
    """
    defectos: list[Defecto] = []
    esperados = ((destinatario.nombre, "nombre_del_destinatario"),) + tuple(
        (nombre, "nombre_de_personaje") for nombre in personajes
    )

    for palabra in PALABRAS.findall(texto):
        for canonico, tipo in esperados:
            if palabra == canonico:
                continue
            if _casi_igual(palabra, canonico):
                defectos.append(
                    _defecto(
                        tipo,
                        Severidad.CRITICA,
                        "los nombres se escriben exactamente como en la story bible",
                        f"el texto escribe «{palabra}» donde la story bible dice «{canonico}»",
                    )
                )
    return defectos


def _casi_igual(palabra: str, canonico: str) -> bool:
    """Una variante del mismo nombre: normaliza igual, o difiere en una sola letra.

    La distancia de uno es lo que atrapa `Marte` por `Marta` y `Irenne` por `Irene`, que
    son los errores que de verdad comete un modelo. Una distancia mayor empezaria a
    marcar nombres distintos como si fueran el mismo.
    """
    if normalizar(palabra) == normalizar(canonico):
        return palabra.lower() != canonico.lower()
    return _distancia_uno(normalizar(palabra), normalizar(canonico))


def _distancia_uno(a: str, b: str) -> bool:
    """Cierto si `a` y `b` difieren en una sustitucion, insercion o borrado."""
    if abs(len(a) - len(b)) > 1 or a == b:
        return False
    if len(a) == len(b):
        return sum(x != y for x, y in zip(a, b, strict=True)) == 1
    corto, largo = (a, b) if len(a) < len(b) else (b, a)
    for i in range(len(largo)):
        if corto == largo[:i] + largo[i + 1 :]:
            return True
    return False


# --- RF-VAL-03: la longitud del capitulo ---------------------------------------------


def longitud_de_capitulo(
    texto: str, *, rango: tuple[int, int] = RANGO_DE_CAPITULO
) -> list[Defecto]:
    """Los dos extremos importan: uno corto no cuenta nada y uno largo cansa."""
    minimo, maximo = rango
    palabras = len(PALABRAS.findall(texto))
    if minimo <= palabras <= maximo:
        return []
    return [
        _defecto(
            "longitud_de_capitulo",
            Severidad.MEDIA,
            "cada capitulo mide dentro del rango declarado",
            f"el capitulo tiene {palabras} palabras, fuera del rango {minimo}-{maximo}",
        )
    ]


# --- RF-VAL-04: los elementos obligatorios llegan a algun capitulo -------------------


def elementos_obligatorios_presentes(
    destinatario: Destinatario,
    *,
    usos: UsoDeHechos,
    hechos_por_elemento: Mapping[str, str],
) -> list[Defecto]:
    """Comprueba contra la tabla de hechos, no leyendo la prosa.

    Buscar el texto del recuerdo dentro del capitulo daria por bueno cualquier parafraseo
    y por malo cualquier integracion elegante, que es justo lo contrario de lo que el
    alcance pide -que la personalizacion no se note forzada-.

    Un elemento obligatorio sin hecho asociado **no** se da por bueno: sin hecho no hay
    nada que comprobar, y llamar a eso «sin defectos» convertiria la ausencia de
    evidencia en evidencia favorable (`architecture.md` 1, principio 8).
    """
    defectos: list[Defecto] = []

    for elemento in destinatario.elementos_obligatorios:
        hecho_id = hechos_por_elemento.get(elemento.id)
        if hecho_id is None:
            defectos.append(
                _defecto(
                    "elemento_personalizado_sin_hecho",
                    Severidad.ALTA,
                    "todo elemento obligatorio esta atado a un hecho comprobable",
                    f"el elemento {elemento.id} ({elemento.tipo.value}) no tiene hecho "
                    f"asociado: no hay nada que comprobar en los capitulos",
                )
            )
            continue

        if not usos.capitulos_de(hecho_id):
            defectos.append(
                _defecto(
                    "elemento_personalizado_ausente",
                    Severidad.ALTA,
                    "cada elemento obligatorio aparece en al menos un capitulo",
                    f"el elemento {elemento.id} ({elemento.tipo.value}) esta atado al "
                    f"hecho {hecho_id}, que no se usa en ningun capitulo",
                )
            )

    return defectos


# --- RF-VAL-09: el registro ----------------------------------------------------------

VALIDADORES: tuple[Validador, ...] = (
    Validador(
        nombre="guardarrail_palabras_prohibidas",
        punto=PuntoDeEjecucion.HOOK_DE_POLICY,
        requisito="RF-VAL-05",
        descripcion="ningun termino vetado, en ninguno de los tres niveles, en el capitulo",
    ),
    Validador(
        nombre="nombres_exactos",
        punto=PuntoDeEjecucion.HOOK_DE_CAPITULO,
        requisito="RF-VAL-02",
        descripcion="los nombres se escriben exactamente como en la story bible",
    ),
    Validador(
        nombre="longitud_de_capitulo",
        punto=PuntoDeEjecucion.HOOK_DE_CAPITULO,
        requisito="RF-VAL-03",
        descripcion="cada capitulo mide dentro del rango declarado",
    ),
    Validador(
        nombre="elementos_obligatorios_presentes",
        punto=PuntoDeEjecucion.PUERTA_DE_PUBLICACION,
        requisito="RF-VAL-04",
        descripcion="cada elemento personalizado obligatorio llega a algun capitulo",
    ),
)
