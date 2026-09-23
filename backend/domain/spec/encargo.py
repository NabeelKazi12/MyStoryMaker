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

from dataclasses import dataclass

from backend.domain.errors import exigir
from backend.domain.vocabularies import TipoDeElementoPersonalizado


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
