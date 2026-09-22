"""Plano discursivo: como se selecciona, ordena y verbaliza el material diegetico.

La `Escena` es la unidad de trabajo de los agentes, y sus dos invariantes se hacen
cumplir aqui, antes de llegar a la base de datos: una escena en la que nada cambia es una
escena que sobra, y una que no narra ningun evento es exposicion disfrazada.

Cubre RF-DOM-01 en su parte discursiva, RF-DOM-04 y RF-DOM-05.
"""

from __future__ import annotations

from dataclasses import dataclass

from backend.domain.errors import exigir
from backend.domain.vocabularies import (
    EstadoDeSiembra,
    FuncionEnTrama,
    TipoDeEscena,
    TipoDeHilo,
    TipoDeSiembra,
)


@dataclass(frozen=True, kw_only=True)
class Volumen:
    """Contenedor de capitulos con su presupuesto de palabras."""

    id: str
    titulo: str
    presupuesto_palabras: int | None = None
    perfil_estilo_id: str | None = None


@dataclass(frozen=True, kw_only=True)
class Capitulo:
    """Contenedor de escenas. El presupuesto es lo que impide que un acto se coma el libro."""

    id: str
    volumen_id: str
    orden: int
    presupuesto_palabras: int | None = None


@dataclass(frozen=True, kw_only=True)
class Escena:
    """Unidad continua de narracion que produce un cambio de valor.

    `renderiza` es el puente con el plano diegetico y no puede estar vacio: sin el, la
    escena no narra nada y los verificadores causales no tienen sobre que correr.
    """

    id: str
    capitulo_id: str
    orden: int
    pov_id: str
    lugar_id: str
    momento_en_historia: int
    objetivo: str
    conflicto: str
    resultado: str
    valor_entrada: str
    valor_salida: str
    funcion_en_trama: FuncionEnTrama
    tipo: TipoDeEscena
    renderiza: tuple[str, ...]
    hilos_activos: tuple[str, ...] = ()
    hechos_requeridos: tuple[str, ...] = ()
    presupuesto_palabras: int | None = None

    def __post_init__(self) -> None:
        clase = type(self).__name__
        exigir(bool(self.id.strip()), clase, "toda escena tiene id")
        exigir(
            self.valor_entrada != self.valor_salida,
            clase,
            "valor_entrada y valor_salida son distintos",
            f"id={self.id!r}; una escena en la que nada cambia es una escena que sobra",
        )
        exigir(
            len(self.renderiza) > 0,
            clase,
            "toda escena narra al menos un EventoNarrativo",
            f"id={self.id!r}; sin aristas renderiza es exposicion disfrazada",
        )
        exigir(
            len(set(self.renderiza)) == len(self.renderiza),
            clase,
            "ninguna escena renderiza dos veces el mismo evento",
            f"id={self.id!r}",
        )


@dataclass(frozen=True, kw_only=True)
class Hilo:
    """Secuencia de escenas que desarrolla una linea de tension hasta su resolucion."""

    id: str
    tipo: TipoDeHilo
    pregunta_dramatica: str
    protagonista_id: str | None = None
    resuelto_en: str | None = None
    abandonado: bool = False

    def __post_init__(self) -> None:
        exigir(
            bool(self.pregunta_dramatica.strip()),
            type(self).__name__,
            "todo hilo tiene pregunta_dramatica declarada",
            f"id={self.id!r}",
        )

    @property
    def cerrado(self) -> bool:
        """Un hilo esta cerrado si tiene resolucion declarada o abandono declarado."""
        return self.resuelto_en is not None or self.abandonado


@dataclass(frozen=True, kw_only=True)
class ParSiembraPago:
    """Promesa narrativa con su cumplimiento: el rifle de Chejov como objeto."""

    id: str
    tipo: TipoDeSiembra
    escena_siembra: str
    estado: EstadoDeSiembra = EstadoDeSiembra.ABIERTO
    escena_pago: str | None = None
    distancia_maxima: int | None = None

    def __post_init__(self) -> None:
        clase = type(self).__name__
        exigir(
            self.estado is not EstadoDeSiembra.RESUELTO or self.escena_pago is not None,
            clase,
            "una siembra resuelta declara su escena_pago",
            f"id={self.id!r}",
        )


@dataclass(frozen=True, kw_only=True)
class PerfilDeEstilo:
    """Contrato de voz aplicable a la obra entera o a un personaje."""

    id: str
    longitud_media_frase: int | None = None
    registro: str = ""
    vocabulario_prohibido: tuple[str, ...] = ()
