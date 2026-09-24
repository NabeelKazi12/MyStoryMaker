"""Capa de especificacion: el contrato del encargo.

Es lo que la capa de calidad usa como referencia para medir. `Restriccion` y
`PoliticaDeContenido` quedan fuera del alcance de v1 (SPEC-001, 2.3).

Desde SPEC-003 el encargo tiene dos mitades: el `Brief`, que dice que novela se escribe, y
el `Destinatario`, que dice para quien. La segunda es la que convierte una novela generica
en un regalo, y la unica que hace verificable la personalizacion: sin nombre no hay nada
que comparar contra la story bible, y sin elemento obligatorio no hay nada que buscar en
los capitulos.

Cubre la parte de especificacion de RF-DOM-01 y los requisitos RF-CFG-01 y RF-CFG-07.
"""

from __future__ import annotations

import unicodedata
from dataclasses import dataclass

from backend.domain.errors import exigir
from backend.domain.vocabularies import Relevancia, TipoDeElementoPersonalizado

# Limites de un personaje declarado (SPEC-011 RF-PER-01 y RF-PER-03). Doce en total, la
# persona destinataria incluida: un regalo con mas personajes que capitulos no se lee.
LARGO_MAXIMO_DEL_NOMBRE = 80
LARGO_MAXIMO_DE_LA_RELACION = 120
LARGO_MAXIMO_DE_LA_DESCRIPCION = 500
MAXIMO_DE_PERSONAJES = 12
RELACION_DE_LA_DESTINATARIA = "a quien va dedicada"


@dataclass(frozen=True, kw_only=True)
class Brief:
    """El encargo. Sin contrato no hay nada que medir.

    `promesa_al_lector` es el compromiso implicito del genero, y su incumplimiento es el
    fallo de calidad mas grave y menos detectable frase a frase; por eso no es opcional.
    """

    id: str
    genero: str
    premisa: str
    promesa_al_lector: str
    extension_objetivo: int
    tabues: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        clase = type(self).__name__
        exigir(bool(self.premisa.strip()), clase, "todo brief tiene premisa", f"id={self.id!r}")
        exigir(
            bool(self.promesa_al_lector.strip()),
            clase,
            "todo brief declara su promesa_al_lector",
            f"id={self.id!r}; es lo que la puerta Volumen cerrado cobra al final",
        )
        exigir(
            self.extension_objetivo > 0,
            clase,
            "la extension objetivo es un numero de palabras positivo",
            f"id={self.id!r}; recibida {self.extension_objetivo}",
        )


@dataclass(frozen=True, kw_only=True)
class ElementoPersonalizado:
    """Algo del destinatario que la novela tiene que llevar dentro.

    `obligatorio` no es un adorno: es lo que separa lo que el validador de RF-VAL-04
    exige encontrar en algun capitulo de lo que solo enriquece si cabe. Marcarlo todo
    como obligatorio convierte el validador en un bloqueo permanente; no marcar nada lo
    convierte en decorativo.
    """

    id: str
    tipo: TipoDeElementoPersonalizado
    contenido: str
    obligatorio: bool = True

    def __post_init__(self) -> None:
        clase = type(self).__name__
        exigir(bool(self.id.strip()), clase, "todo elemento personalizado tiene id")
        exigir(
            bool(self.contenido.strip()),
            clase,
            "todo elemento personalizado tiene contenido no vacio",
            f"id={self.id!r}; un elemento vacio no se puede buscar en ningun capitulo",
        )


@dataclass(frozen=True, kw_only=True)
class Destinatario:
    """Para quien se escribe la novela.

    La edad se guarda porque es una de las dos patas de la contradiccion que RF-CFG-04
    obliga a detectar -edad frente a genero o tono-, y porque sin ella esa deteccion no
    tiene con que chocar.
    """

    id: str
    nombre: str
    edad: int
    rasgos: tuple[str, ...] = ()
    elementos: tuple[ElementoPersonalizado, ...] = ()
    dedicatoria: str = ""

    def __post_init__(self) -> None:
        clase = type(self).__name__
        exigir(bool(self.id.strip()), clase, "todo destinatario tiene id")
        exigir(
            bool(self.nombre.strip()),
            clase,
            "todo destinatario tiene nombre no vacio",
            f"id={self.id!r}; es lo que RF-VAL-02 compara contra la story bible",
        )
        exigir(
            self.edad > 0,
            clase,
            "la edad del destinatario es un numero de anos positivo",
            f"id={self.id!r}; recibida {self.edad}",
        )
        exigir(
            bool(self.elementos_obligatorios),
            clase,
            "todo destinatario aporta al menos un elemento personalizado obligatorio",
            f"id={self.id!r}; sin el, la personalizacion no es verificable (RF-VAL-04)",
        )

    @property
    def elementos_obligatorios(self) -> tuple[ElementoPersonalizado, ...]:
        """Los que RF-VAL-04 exige encontrar en al menos un capitulo."""
        return tuple(e for e in self.elementos if e.obligatorio)


def clave_de_nombre(nombre: str) -> str:
    """El nombre tal como se compara: sin espacios sobrantes, mayusculas ni acentos.

    «Luis» y «luís» son la misma persona para quien encarga, y lo tienen que ser tambien
    para la apertura: un Planner que escribe «Lucia» donde se declaro «Lucía» no se ha
    dejado a nadie fuera (SPEC-011 RF-PER-03, RF-PER-06).
    """
    descompuesto = unicodedata.normalize("NFKD", " ".join(nombre.split()))
    return "".join(c for c in descompuesto if not unicodedata.combining(c)).casefold()


@dataclass(frozen=True, kw_only=True)
class PersonajeDeclarado:
    """Alguien que quien encarga quiere ver en la novela, dicho antes de escribirla.

    Vive en la capa de especificacion, no en el canon: declarar es encargar. Entra en el
    canon por la apertura, que tiene que proponerlo con su nombre y su papel o ve el plan
    rechazado entero (SPEC-011, D-25). Lo que no se declara —deseo, necesidad, arco— lo
    completa el Planner.
    """

    id: str
    nombre: str
    papel: Relevancia
    relacion: str = ""
    descripcion: str = ""
    es_destinatario: bool = False

    def __post_init__(self) -> None:
        clase = type(self).__name__
        nombre = self.nombre.strip()
        exigir(bool(nombre), clase, "todo personaje declarado tiene nombre", f"id={self.id!r}")
        exigir(
            len(nombre) <= LARGO_MAXIMO_DEL_NOMBRE,
            clase,
            f"el nombre tiene como mucho {LARGO_MAXIMO_DEL_NOMBRE} caracteres",
            f"«{nombre[:20]}…» tiene {len(nombre)}",
        )
        exigir(
            len(self.relacion.strip()) <= LARGO_MAXIMO_DE_LA_RELACION,
            clase,
            f"la relacion tiene como mucho {LARGO_MAXIMO_DE_LA_RELACION} caracteres",
            f"la de «{nombre}» tiene {len(self.relacion.strip())}",
        )
        exigir(
            len(self.descripcion.strip()) <= LARGO_MAXIMO_DE_LA_DESCRIPCION,
            clase,
            f"la descripcion tiene como mucho {LARGO_MAXIMO_DE_LA_DESCRIPCION} caracteres",
            f"la de «{nombre}» tiene {len(self.descripcion.strip())}",
        )
        exigir(
            not self.es_destinatario or self.papel is Relevancia.PROTAGONICO,
            clase,
            "la persona destinataria es protagonista de su novela",
            f"«{nombre}» llega como {self.papel.value}",
        )
