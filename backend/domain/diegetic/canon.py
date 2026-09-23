"""Plano diegetico: lo que es verdad en el mundo y cuando.

Las clases son inmutables a proposito. El canon cambia por canonizacion, no mutando un
objeto en memoria: un `Hecho` no se edita, se cierra su intervalo y se inserta otro
(`architecture.md` 3.3).

Nada aqui importa de ningun otro paquete, ni de FastAPI ni de Pydantic
(`architecture.md` 2.3, regla 1), y ningun atributo estatico describe una dimension
variable: eso es un `Hecho` (`CLAUDE.md` 3.2).

Cubre RF-DOM-01 en su parte diegetica, RF-DOM-06 y RF-DOM-07.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass, field

from backend.domain.errors import exigir
from backend.domain.vocabularies import (
    EstatusOntologico,
    ExclusividadDePredicado,
    Relevancia,
    RolEnEvento,
    TipoDeArco,
    TipoDeEvento,
    VisibilidadDeEvento,
)


@dataclass(frozen=True, kw_only=True)
class Entidad:
    """Cualquier cosa a la que el relato pueda referirse de forma persistente."""

    id: str
    nombre_canonico: str
    alias: tuple[str, ...] = ()
    estatus_ontologico: EstatusOntologico = EstatusOntologico.REAL
    relevancia: Relevancia = Relevancia.SECUNDARIO

    def __post_init__(self) -> None:
        clase = type(self).__name__
        exigir(bool(self.id.strip()), clase, "toda entidad tiene id")
        exigir(
            bool(self.nombre_canonico.strip()),
            clase,
            "toda entidad tiene nombre_canonico no vacio",
            f"id={self.id!r}",
        )

    @property
    def nombres(self) -> frozenset[str]:
        """Nombre canonico y alias declarados. Es lo que la deriva de nombres compara."""
        return frozenset({self.nombre_canonico, *self.alias})


@dataclass(frozen=True, kw_only=True)
class Personaje(Entidad):
    """Entidad con agencia, capaz de querer, saber y actuar."""

    deseo_externo: str = ""
    necesidad_interna: str = ""
    creencia_falsa: str = ""
    arco_tipo: TipoDeArco | None = None
    anio_de_nacimiento: int | None = None

    def __post_init__(self) -> None:
        super().__post_init__()
        # El invariante de definitions.md exige ademas un Hilo asociado, que no se puede
        # comprobar desde aqui porque vive en el plano discursivo: lo cobra RF-QUA-17.
        exigir(
            self.relevancia is not Relevancia.PROTAGONICO
            or bool(self.necesidad_interna.strip()),
            type(self).__name__,
            "todo personaje protagonico tiene necesidad_interna no vacia",
            f"id={self.id!r}",
        )

    def edad_en(self, momento: int) -> int | None:
        """Edad en un momento de la historia, o `None` si no se declaro nacimiento.

        Se deriva y no se guarda: una edad almacenada miente en cuanto el evento cambia
        de momento. Tampoco se corrige si sale negativa, porque una edad negativa **es**
        la incoherencia que el validador formal tiene que encontrar; taparla aqui dejaria
        a Lean sin nada que detectar (RF-LEAN-02).
        """
        if self.anio_de_nacimiento is None:
            return None
        return momento - self.anio_de_nacimiento


@dataclass(frozen=True, kw_only=True)
class Lugar(Entidad):
    """Entidad espacial donde pueden situarse escenas y eventos."""

    atmosfera_sensorial: str = ""
    contenido_en: str | None = None


@dataclass(frozen=True, kw_only=True)
class Participacion:
    """Una entidad dentro de un evento, con el papel que juega en el."""

    entidad_id: str
    rol: RolEnEvento


@dataclass(frozen=True, kw_only=True)
class EventoNarrativo:
    """Ocurrencia atomica y fechable en tiempo de historia que cambia el estado del mundo.

    Es la clase pivote del plano: toda vigencia se ancla a un evento, nunca a una fecha.
    """

    id: str
    descripcion: str
    posicion_en_historia: int
    tipo: TipoDeEvento
    visibilidad: VisibilidadDeEvento = VisibilidadDeEvento.PUBLICO
    momento: int | None = None
    lugar_id: str | None = None
    participantes: tuple[Participacion, ...] = ()
    causa: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        clase = type(self).__name__
        exigir(bool(self.id.strip()), clase, "todo evento tiene id")
        exigir(
            self.id not in self.causa,
            clase,
            "ningun evento se causa a si mismo: el grafo causal es aciclico",
            f"id={self.id!r}",
        )


@dataclass(frozen=True, kw_only=True)
class Hecho:
    """Proposicion sobre el mundo verdadera durante un intervalo delimitado por eventos.

    `valido_hasta` a `None` significa vigente. El intervalo se delimita con eventos y
    nunca con fechas: los atributos estaticos son el origen de la deriva de canon.
    """

    id: str
    sujeto_id: str
    predicado: str
    objeto: str
    valido_desde: str
    valido_hasta: str | None = None
    certeza: str = "cierto"
    establecido_en: str | None = None
    es_publico: bool = True

    def __post_init__(self) -> None:
        clase = type(self).__name__
        exigir(bool(self.id.strip()), clase, "todo hecho tiene id")
        exigir(
            bool(self.valido_desde.strip()),
            clase,
            "todo hecho tiene valido_desde apuntando a un EventoNarrativo",
            f"id={self.id!r}; ningun hecho es atemporal (CLAUDE.md 3.2)",
        )
        exigir(
            bool(self.predicado.strip()),
            clase,
            "todo hecho tiene predicado",
            f"id={self.id!r}",
        )
        exigir(
            self.valido_hasta != self.valido_desde,
            clase,
            "un intervalo no se abre y se cierra en el mismo evento",
            f"id={self.id!r}; valido_desde={self.valido_desde!r}",
        )

    @property
    def vigente(self) -> bool:
        """Un hecho sin `valido_hasta` sigue siendo verdad."""
        return self.valido_hasta is None


@dataclass(frozen=True, kw_only=True)
class Predicado:
    """Entrada del catalogo de predicados, con su exclusividad declarada.

    Lo introduce SPEC-001 9.2 R-7: sin saber que predicados son mutuamente excluyentes,
    «contradiccion de hechos» no es un predicado ejecutable.
    """

    nombre: str
    exclusividad: ExclusividadDePredicado
    descripcion: str = ""

    def __post_init__(self) -> None:
        exigir(
            bool(self.nombre.strip()),
            type(self).__name__,
            "todo predicado del catalogo tiene nombre",
        )


@dataclass(frozen=True, kw_only=True)
class LineaTemporal:
    """Ordenacion completa de eventos en tiempo de historia.

    v1 asume una sola linea sin `ramas[]` (SPEC-001, supuesto S-11).
    """

    id: str
    eventos_ordenados: tuple[str, ...] = field(default_factory=tuple)


@dataclass(frozen=True, kw_only=True)
class EventoDeCronologia:
    """Una fila de la cronologia: evento, momento, lugar y quien estaba.

    Es una **proyeccion** del canon, no una segunda copia. Se construye con
    `cronologia_de` y nadie la persiste aparte: una cronologia declarada a mano diverge
    del canon en cuanto alguien edita un evento, y entonces el validador formal estaria
    verificando una historia que ya no es la que se lee.

    Cubre RF-BIB-02 y es la entrada de RF-LEAN-01.
    """

    evento_id: str
    momento: int | None
    lugar_id: str | None = None
    personajes: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        clase = type(self).__name__
        exigir(
            self.momento is not None,
            clase,
            "toda fila de la cronologia tiene momento",
            f"evento_id={self.evento_id!r}; sin momento no se puede ordenar ni fechar, "
            f"y los dos invariantes de RF-LEAN-02 comparan momentos",
        )


def cronologia_de(eventos: Iterable[EventoNarrativo]) -> tuple[EventoDeCronologia, ...]:
    """Proyecta los eventos fechados como cronologia, ordenados por momento.

    Los eventos sin momento **se quedan fuera** en lugar de recibir uno inventado. Lo que
    falta se cuenta con `sin_momento`, que es lo que permite decir «la cronologia cubre 18
    de 20 eventos» en vez de dar por completa una historia a medio fechar.
    """
    filas = [
        EventoDeCronologia(
            evento_id=evento.id,
            momento=evento.momento,
            lugar_id=evento.lugar_id,
            personajes=tuple(p.entidad_id for p in evento.participantes),
        )
        for evento in eventos
        if evento.momento is not None
    ]
    return tuple(sorted(filas, key=lambda f: (f.momento or 0, f.evento_id)))


def sin_momento(eventos: Iterable[EventoNarrativo]) -> tuple[str, ...]:
    """Los eventos que no entran en la cronologia, para poder declarar el hueco."""
    return tuple(evento.id for evento in eventos if evento.momento is None)
