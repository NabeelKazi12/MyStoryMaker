"""Plano de produccion: quien hizo que, con que entrada y con que resultado.

Es lo que hace el sistema depurable. `Procedencia` enlaza cada artefacto con el
`PaqueteDeContexto` exacto que recibio el agente, que es lo que convierte un fallo de
coherencia en algo reproducible.

El recuento de intentos es un historial tipificado, no dos contadores: las cuatro clases
de fallo de `architecture.md` 6.5 no caben en dos enteros (SPEC-001, 9.2 R-3).

Cubre RF-DOM-02 y la parte de produccion de RF-DOM-01.
"""

from __future__ import annotations

from dataclasses import dataclass

from backend.domain.errors import exigir
from backend.domain.vocabularies import (
    ClaseDeFallo,
    EstadoDeBorrador,
    EstadoDeTarea,
    Severidad,
)


@dataclass(frozen=True, kw_only=True)
class Procedencia:
    """Como se genero un artefacto. Sin esto, un fallo de coherencia no es depurable."""

    id: str
    agente: str
    modelo: str
    version_de_prompt: str
    paquete_id: str
    parametros_muestreo: str = ""
    coste: float = 0.0
    latencia_ms: int = 0
    clase_de_fallo: ClaseDeFallo | None = None
    # Los que devolvio el cliente del modelo. `None` cuando no hubo respuesta -la llamada
    # no llego a salir o fallo antes de contestar- y en las filas de antes de SPEC-012.
    tokens_entrada: int | None = None
    tokens_salida: int | None = None


@dataclass(frozen=True, kw_only=True)
class PaqueteDeContexto:
    """Registro de lo que se inyecto a un agente en una llamada.

    `tokens_por_componente` es la metrica que dice si la compresion se degrada a lo largo
    del libro; guardarla no es opcional (`architecture.md` 4.4).
    """

    id: str
    tarea_id: str
    revision_canon: int
    hash: str
    tokens_por_componente: tuple[tuple[str, int], ...] = ()

    def __post_init__(self) -> None:
        clase = type(self).__name__
        exigir(bool(self.hash.strip()), clase, "todo paquete lleva hash", f"id={self.id!r}")
        exigir(
            self.revision_canon >= 0,
            clase,
            "todo paquete referencia la revision de canon con la que se construyo",
            f"id={self.id!r}",
        )

    @property
    def tokens_totales(self) -> int:
        """Suma real contada antes de invocar, no una estimacion."""
        return sum(tokens for _, tokens in self.tokens_por_componente)


@dataclass(frozen=True, kw_only=True)
class Intento:
    """Una entrada del historial tipificado de una `Tarea`.

    Sustituye a los dos contadores: de aqui salen por agregacion tanto los intentos
    narrativos como los de infraestructura, y tambien la condicion de RF-ORQ-06.
    """

    numero: int
    clase_de_fallo: ClaseDeFallo | None = None
    tipo_de_defecto: str | None = None

    @property
    def suma_intento_narrativo(self) -> bool:
        """Solo contrato y contenido consumen intentos narrativos (D-06)."""
        return self.clase_de_fallo in (ClaseDeFallo.CONTRATO, ClaseDeFallo.CONTENIDO)


@dataclass(frozen=True, kw_only=True)
class Tarea:
    """Unidad de trabajo asignable."""

    id: str
    plan_id: str
    tipo: str
    rol_asignado: str
    estado: EstadoDeTarea = EstadoDeTarea.PENDIENTE
    prioridad: int = 1
    depende_de: tuple[str, ...] = ()
    historial: tuple[Intento, ...] = ()
    techo_de_salida: int = 0
    reserva: int = 0
    paquete_id: str | None = None
    falta: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        clase = type(self).__name__
        exigir(
            0 <= self.prioridad <= 3,
            clase,
            "la prioridad es una de las cuatro clases P0 a P3",
            f"id={self.id!r}; recibida {self.prioridad}",
        )
        exigir(
            self.id not in self.depende_de,
            clase,
            "ninguna tarea depende de si misma",
            f"id={self.id!r}",
        )

    @property
    def intentos_narrativos(self) -> int:
        """Cuantas veces se ha reescrito por un fallo de contenido o de contrato."""
        return sum(1 for intento in self.historial if intento.suma_intento_narrativo)

    @property
    def intentos_de_infraestructura(self) -> int:
        """Cuantas veces fallo por transporte o por presupuesto, que no consumen escalera."""
        return sum(
            1
            for intento in self.historial
            if intento.clase_de_fallo is not None and not intento.suma_intento_narrativo
        )

    @property
    def repite_tipo_de_defecto(self) -> bool:
        """Dos intentos consecutivos con el mismo tipo de defecto saltan a replanificacion."""
        tipos = [i.tipo_de_defecto for i in self.historial if i.tipo_de_defecto is not None]
        return len(tipos) >= 2 and tipos[-1] == tipos[-2]


@dataclass(frozen=True, kw_only=True)
class Plan:
    """Arbol de tareas con dependencias que produce un artefacto de nivel superior."""

    id: str
    objetivo: str
    techo_de_coste: float | None = None


@dataclass(frozen=True, kw_only=True)
class Borrador:
    """Version concreta de la prosa de una escena. Unica tabla con texto largo."""

    id: str
    escena_id: str
    version: int
    texto: str
    estado: EstadoDeBorrador = EstadoDeBorrador.PROPUESTO
    procedencia_id: str | None = None
    hechos_nuevos_detectados: tuple[str, ...] = ()
    eventos_narrados: tuple[str, ...] = ()
    siembras_tocadas: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        exigir(
            self.version >= 1,
            type(self).__name__,
            "la version de un borrador empieza en 1",
            f"id={self.id!r}; recibida {self.version}",
        )

    @property
    def recuento_palabras(self) -> int:
        """Derivado del texto, nunca declarado a mano."""
        return len(self.texto.split())


@dataclass(frozen=True, kw_only=True)
class Defecto:
    """Incoherencia detectada, con la evidencia que la sostiene.

    Un defecto sin evidencia se descarta antes de llegar al Orquestador, y el descarte se
    cuenta: la proporcion descartada delata a un agente que opina en vez de comprobar.
    """

    id: str
    tipo: str
    severidad: Severidad
    regla_violada: str
    evidencia: str
    borrador_id: str | None = None
    span: str | None = None
    extraccion_evaluada: str | None = None

    @property
    def tiene_evidencia(self) -> bool:
        """Sin evidencia citable, el defecto no llega al Orquestador."""
        return bool(self.evidencia.strip())


@dataclass(frozen=True, kw_only=True)
class RegistroDeDecision:
    """Decision tomada, con su alternativa descartada y su motivo. Es inmutable."""

    id: str
    decision: str
    motivo: str
    alternativas_consideradas: tuple[str, ...] = ()
    ambito: str = ""
    reversible: bool = True

    def __post_init__(self) -> None:
        clase = type(self).__name__
        exigir(
            bool(self.motivo.strip()),
            clase,
            "todo registro de decision lleva motivo",
            f"id={self.id!r}",
        )
        exigir(
            len(self.alternativas_consideradas) > 0,
            clase,
            "todo registro de decision nombra al menos una alternativa descartada",
            f"id={self.id!r}; sin ella la decision se vuelve a discutir",
        )
