"""Trazas, spans y scores: lo que el sistema deja ver de si mismo.

La fuente de verdad sigue siendo SQLite -`Procedencia`, `Puerta`, `Tarea`-, y esto es la
**vista**: lo que permite mirar una ejecucion sin reconstruirla a mano. De esa decision
(SPEC-003 S-02) salen las tres propiedades de este modulo:

1. **El cliente esta detras de un protocolo.** Langfuse se enchufa implementandolo, y la
   suite corre contra un doble. Si la suite necesitara Langfuse en marcha, el observador
   seria punto unico de fallo.
2. **`ClienteNulo` es un cliente de pleno derecho.** Con el observador apagado la novela
   se escribe igual: que una generacion falle porque el que mira esta caido es
   exactamente lo que no debe pasar.
3. **Nadie que juzgue importa este paquete.** `domain/`, `quality/` y `agents/` no lo
   conocen, y `test_import_boundaries` lo hace cumplir. Un juez que sabe que esta siendo
   observado es un juez distinto.

Cubre RF-OBS-01 a RF-OBS-05.
"""

from __future__ import annotations

import time
import uuid
from collections.abc import Iterator, Mapping
from contextlib import contextmanager
from dataclasses import dataclass, field
from typing import Protocol, runtime_checkable


@dataclass(frozen=True)
class Uso:
    """Lo que costo una llamada. Se registra por span y se agrega por capitulo y novela."""

    tokens_entrada: int
    tokens_salida: int
    coste: float = 0.0


@dataclass(frozen=True)
class Score:
    """El resultado de un validador, asociado a la traza donde corrio.

    `valor` en 0-1 a proposito: un score booleano no distingue «fallo por poco» de «fallo
    del todo», y los deterministas simplemente usan los extremos.
    """

    nombre: str
    valor: float
    comentario: str = ""


@dataclass
class Traza:
    """Una ejecucion completa: una generacion, una entrevista, una regeneracion."""

    id: str
    nombre: str
    sesion: str
    metadatos: Mapping[str, str] = field(default_factory=dict)
    terminada: bool = False


@dataclass
class Span:
    """Un tramo dentro de una traza: un rol o una llamada a tool."""

    id: str
    traza_id: str
    nombre: str
    tipo: str
    capitulo_id: str | None = None
    version_de_prompt: str | None = None
    latencia_ms: int = 0
    uso: Uso | None = None
    error: str | None = None

    def registrar_uso(self, uso: Uso) -> None:
        """Anota lo que consumio este tramo."""
        self.uso = uso


@dataclass
class ScoreRegistrado:
    """Un score ya asociado a su traza."""

    nombre: str
    valor: float
    traza_id: str
    comentario: str = ""


@runtime_checkable
class ClienteDeObservabilidad(Protocol):
    """Lo minimo que el sistema necesita de un backend de observabilidad."""

    def abrir_traza(self, traza: Traza) -> None: ...

    def cerrar_traza(self, traza: Traza) -> None: ...

    def registrar_span(self, span: Span) -> None: ...

    def registrar_score(self, score: ScoreRegistrado) -> None: ...


class ClienteNulo:
    """No registra nada y no falla nunca.

    Es el cliente por defecto cuando no hay Langfuse configurado. Que exista es lo que
    permite que la ausencia de observabilidad sea una degradacion y no una parada.
    """

    def abrir_traza(self, traza: Traza) -> None:
        return None

    def cerrar_traza(self, traza: Traza) -> None:
        return None

    def registrar_span(self, span: Span) -> None:
        return None

    def registrar_score(self, score: ScoreRegistrado) -> None:
        return None


@dataclass
class ClienteFalsoDeObservabilidad:
    """Cliente en memoria: lo que la suite usa en lugar de la red.

    No simula Langfuse: simula el **protocolo**, que es lo unico contra lo que el sistema
    programa. Comprobar aqui que el agregado por capitulo cuadra vale igual que
    comprobarlo contra el servicio, y no depende de que haya red.
    """

    trazas: list[Traza] = field(default_factory=list)
    spans: list[Span] = field(default_factory=list)
    scores: list[ScoreRegistrado] = field(default_factory=list)

    def abrir_traza(self, traza: Traza) -> None:
        self.trazas.append(traza)

    def cerrar_traza(self, traza: Traza) -> None:
        for guardada in self.trazas:
            if guardada.id == traza.id:
                guardada.terminada = True

    def registrar_span(self, span: Span) -> None:
        self.spans.append(span)

    def registrar_score(self, score: ScoreRegistrado) -> None:
        self.scores.append(score)

    # --- agregados, que son la razon de registrar ------------------------------------

    def coste_total(self) -> float:
        return sum(s.uso.coste for s in self.spans if s.uso is not None)

    def tokens_totales(self) -> tuple[int, int]:
        entrada = sum(s.uso.tokens_entrada for s in self.spans if s.uso is not None)
        salida = sum(s.uso.tokens_salida for s in self.spans if s.uso is not None)
        return entrada, salida

    def coste_de_capitulo(self, capitulo_id: str) -> float:
        return sum(
            s.uso.coste
            for s in self.spans
            if s.uso is not None and s.capitulo_id == capitulo_id
        )


@dataclass
class Observador:
    """La cara que el resto del sistema usa. Abre trazas, spans y registra scores."""

    cliente: ClienteDeObservabilidad
    sesion: str
    _traza_activa: Traza | None = field(default=None, repr=False)

    @contextmanager
    def traza(
        self, nombre: str, *, metadatos: Mapping[str, str] | None = None
    ) -> Iterator[Traza]:
        """Abre una traza y la cierra pase lo que pase."""
        traza = Traza(
            id=f"tr-{uuid.uuid4().hex[:12]}",
            nombre=nombre,
            sesion=self.sesion,
            metadatos=dict(metadatos or {}),
        )
        self.cliente.abrir_traza(traza)
        anterior, self._traza_activa = self._traza_activa, traza
        try:
            yield traza
        finally:
            self._traza_activa = anterior
            self.cliente.cerrar_traza(traza)

    @contextmanager
    def span(
        self,
        nombre: str,
        *,
        tipo: str,
        capitulo_id: str | None = None,
        version_de_prompt: str | None = None,
    ) -> Iterator[Span]:
        """Abre un tramo dentro de la traza activa.

        Un span de rol **exige** version de prompt: sin ella la iteracion de tuning no
        puede decir que version produjo cada resultado (RF-OBS-05). Las tools no la
        llevan porque no tienen prompt, y por eso la exigencia es por tipo.
        """
        if self._traza_activa is None:
            raise RuntimeError(
                f"El span «{nombre}» no tiene traza abierta. Un tramo suelto no se puede "
                f"agrupar por novela y se pierde."
            )
        if tipo == "rol" and not version_de_prompt:
            raise ValueError(
                f"El span de rol «{nombre}» no declara version_de_prompt. Sin ella, lo "
                f"generado deja de ser reproducible y la iteracion de tuning no puede "
                f"atribuir el resultado a ninguna version."
            )

        span = Span(
            id=f"sp-{uuid.uuid4().hex[:12]}",
            traza_id=self._traza_activa.id,
            nombre=nombre,
            tipo=tipo,
            capitulo_id=capitulo_id,
            version_de_prompt=version_de_prompt,
        )
        comienzo = time.monotonic()
        try:
            yield span
        except Exception as error:
            span.error = str(error)
            raise
        finally:
            span.latencia_ms = int((time.monotonic() - comienzo) * 1000)
            self.cliente.registrar_span(span)

    def score(self, score: Score) -> None:
        """Asocia el resultado de un validador a la traza activa."""
        if self._traza_activa is None:
            raise RuntimeError(
                f"El score «{score.nombre}» no tiene traza abierta. Perderlo en silencio "
                f"haria que el validador pareciera no haber corrido."
            )
        self.cliente.registrar_score(
            ScoreRegistrado(
                nombre=score.nombre,
                valor=score.valor,
                traza_id=self._traza_activa.id,
                comentario=score.comentario,
            )
        )
