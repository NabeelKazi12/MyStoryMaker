"""Lo que ha costado cada novela, leido de las procedencias.

SQLite es la fuente de verdad del gasto (SPEC-003 S-02): cada llamada al modelo deja una
`procedencia` con su coste, su latencia y, desde SPEC-012, sus tokens. Aqui se leen las de
una novela y se agregan. Langfuse es otra vista de lo mismo, y esta lectura no depende de
que este configurado ni en marcha (SPEC-012 N-01).

Una llamada pertenece a una novela por su paquete: `procedencia` → `paquete_contexto` →
`tarea` → `plan.volumen_id`. Sin ese camino, las llamadas de una novela se mezclarian con
las de otra en cuanto hubiera dos en la base (RF-GAS-05).

Cubre RF-GAS-03 a RF-GAS-05 y RF-GAS-07.
"""

from __future__ import annotations

import sqlite3
from collections.abc import Iterable
from dataclasses import dataclass


@dataclass(frozen=True)
class LlamadaDeGasto:
    id: str
    momento: str
    agente: str
    modelo: str
    version_de_prompt: str
    tarea: str
    escena_id: str | None
    capitulo_orden: int | None
    # Ordinal de la llamada dentro de su tarea: 1 la primera, 2 el primer reintento...
    intento: int
    coste: float
    latencia_ms: int
    tokens_entrada: int | None
    tokens_salida: int | None
    clase_de_fallo: str | None


@dataclass(frozen=True)
class TotalDeGasto:
    coste: float
    llamadas: int
    fallidas: int
    tokens_entrada: int
    tokens_salida: int
    latencia_ms: int
    # Las llamadas de antes de SPEC-012 no guardaron tokens: no suman, pero se cuentan
    # para que un total de tokens bajo no parezca una novela barata (N-05).
    llamadas_sin_tokens: int


@dataclass(frozen=True)
class Desglose:
    nombre: str
    coste: float
    llamadas: int


@dataclass(frozen=True)
class ResumenDeGasto:
    total: TotalDeGasto
    por_rol: tuple[Desglose, ...]
    por_capitulo: tuple[Desglose, ...]
    llamadas: tuple[LlamadaDeGasto, ...]


@dataclass(frozen=True)
class GastosDeLaNovela:
    conn: sqlite3.Connection

    def llamadas(self, volumen_id: str) -> tuple[LlamadaDeGasto, ...]:
        """Todas las llamadas de la novela, en el orden en que ocurrieron."""
        filas = self.conn.execute(
            """
            SELECT p.id, p.timestamp, p.agente, p.modelo, p.version_de_prompt, p.coste,
                   p.latencia_ms, p.tokens_entrada, p.tokens_salida, p.clase_de_fallo,
                   t.tipo, e.id AS escena_id, c.orden AS capitulo_orden,
                   ROW_NUMBER() OVER (
                       PARTITION BY t.id ORDER BY p.timestamp, p.rowid
                   ) AS intento
            FROM procedencia p
            JOIN paquete_contexto pq ON pq.id = p.paquete_id
            JOIN tarea t ON t.id = pq.tarea_id
            JOIN plan pl ON pl.id = t.plan_id
            LEFT JOIN escena e ON t.id = e.id || ':redaccion'
            LEFT JOIN capitulo c ON c.id = e.capitulo_id
            WHERE pl.volumen_id = ?
            ORDER BY p.timestamp, p.rowid
            """,
            (volumen_id,),
        ).fetchall()
        return tuple(
            LlamadaDeGasto(
                id=f["id"],
                momento=f["timestamp"],
                agente=f["agente"],
                modelo=f["modelo"],
                version_de_prompt=f["version_de_prompt"],
                tarea=f["tipo"],
                escena_id=f["escena_id"],
                capitulo_orden=f["capitulo_orden"],
                intento=int(f["intento"]),
                coste=float(f["coste"]),
                latencia_ms=int(f["latencia_ms"]),
                tokens_entrada=f["tokens_entrada"],
                tokens_salida=f["tokens_salida"],
                clase_de_fallo=f["clase_de_fallo"],
            )
            for f in filas
        )

    def resumen(self, volumen_id: str) -> ResumenDeGasto:
        llamadas = self.llamadas(volumen_id)
        total = TotalDeGasto(
            coste=sum(ll.coste for ll in llamadas),
            llamadas=len(llamadas),
            fallidas=sum(1 for ll in llamadas if ll.clase_de_fallo is not None),
            tokens_entrada=sum(ll.tokens_entrada or 0 for ll in llamadas),
            tokens_salida=sum(ll.tokens_salida or 0 for ll in llamadas),
            latencia_ms=sum(ll.latencia_ms for ll in llamadas),
            llamadas_sin_tokens=sum(
                1 for ll in llamadas if ll.tokens_entrada is None and ll.tokens_salida is None
            ),
        )
        return ResumenDeGasto(
            total=total,
            por_rol=_desglose((ll.agente, ll) for ll in llamadas),
            por_capitulo=_desglose(
                (f"Capítulo {ll.capitulo_orden}", ll)
                for ll in sorted(
                    (ll for ll in llamadas if ll.capitulo_orden is not None),
                    key=lambda ll: ll.capitulo_orden or 0,
                )
            ),
            llamadas=llamadas,
        )


def _desglose(pares: Iterable[tuple[str, LlamadaDeGasto]]) -> tuple[Desglose, ...]:
    """Agrupa conservando el orden en que aparece cada grupo por primera vez."""
    grupos: dict[str, list[LlamadaDeGasto]] = {}
    for nombre, llamada in pares:
        grupos.setdefault(nombre, []).append(llamada)
    return tuple(
        Desglose(nombre=nombre, coste=sum(ll.coste for ll in grupo), llamadas=len(grupo))
        for nombre, grupo in grupos.items()
    )
