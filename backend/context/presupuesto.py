"""Presupuesto del `PaqueteDeContexto` y orden de recorte.

El reparto y el orden salen de `architecture.md` 4.3, y el orden es parte del contrato de
rol (D-16): cambiarlo mueve el `hash` del paquete y rompe la reproducibilidad de todo lo
generado antes.

Nunca se trunca por la cola. Truncar borra el final de la instruccion, que es justo lo que
el agente necesita para saber que se le pide (D-12).

Cubre RF-CTX-01, RF-CTX-03, RF-CTX-04 y RF-CTX-08.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import IntEnum

# Techo del sistema: tokens en vuelo simultaneos, no por peticion (D-13).
TECHO_DEL_SISTEMA = 100_000

# Objetivo de una tarea de redaccion. El techo es 100.000; el objetivo, muy inferior.
PRESUPUESTO_DE_REDACCION = 24_000
MAXIMO_DE_ENTRADA = 25_000

# Techo de salida declarado en architecture.md 4.2 para la redaccion de escena.
# Es el limite duro que se envia al modelo: si lo alcanza, la salida se trunca y eso es
# fallo de contrato, no una invitacion a ampliarlo.
TECHO_DE_SALIDA_REDACCION = 4_000


class Componente(IntEnum):
    """Los ocho componentes, en el orden del contrato de rol (`AGENTS.md` 4.5).

    El valor es la posicion: el orden no es decorativo, es lo que hace que el componente
    estatico sea un prefijo identico en todas las escenas de un volumen.
    """

    ESTATICO = 1
    ESTADO_DEL_MUNDO = 2
    CONTINUIDAD = 3
    ARCO = 4
    VOZ = 5
    EPISTEMICO = 6
    PROMESAS = 7
    INSTRUCCION = 8
    DEFECTOS_ABIERTOS = 9


# Reparto de referencia de `architecture.md` 4.3.
PRESUPUESTO_POR_COMPONENTE: dict[Componente, int] = {
    Componente.ESTATICO: 2_000,
    Componente.ESTADO_DEL_MUNDO: 6_000,
    Componente.CONTINUIDAD: 3_500,
    Componente.ARCO: 4_000,
    Componente.VOZ: 1_500,
    Componente.EPISTEMICO: 2_000,
    Componente.PROMESAS: 1_000,
    Componente.INSTRUCCION: 1_000,
}

MARGEN_DE_SEGURIDAD = 3_000

# Orden de recorte, declarado y fijo. Se sueltan primero los niveles mas lejanos de la
# piramide; lo ultimo que se toca es el estado del mundo y la voz.
ORDEN_DE_RECORTE: tuple[Componente, ...] = (
    Componente.ARCO,
    Componente.PROMESAS,
    Componente.CONTINUIDAD,
    Componente.ESTADO_DEL_MUNDO,
    Componente.VOZ,
)

# Intocables. Truncar la instruccion es perder el encargo; recortar lo epistemico produce
# fugas de informacion, que es el fallo mas dificil de detectar leyendo.
INTOCABLES: frozenset[Componente] = frozenset(
    {
        Componente.ESTATICO,
        Componente.EPISTEMICO,
        Componente.INSTRUCCION,
        Componente.DEFECTOS_ABIERTOS,
    }
)


class PresupuestoExcedido(Exception):
    """El paquete no cabe ni despues de recortar todo lo recortable.

    No es un error de programacion: es el caso previsto de `architecture.md` 4.1. La
    `Tarea` pasa a `bloqueada` con `falta`, y si ocurre de forma sistematica significa
    que el filtro estructural de esa escena esta mal acotado.
    """

    def __init__(self, tokens: int, presupuesto: int, faltan: int) -> None:
        self.tokens = tokens
        self.presupuesto = presupuesto
        self.faltan = faltan
        super().__init__(
            f"PaqueteDeContexto: no cabe en su presupuesto tras agotar el orden de "
            f"recorte. Ocupa {tokens} tokens sobre {presupuesto}; sobran {faltan}. "
            f"Apretar los filtros de AlcanceDeRelevancia, no subir el presupuesto."
        )


def contar_tokens(texto: str) -> int:
    """Estimacion del numero de tokens de un texto.

    Es una heuristica deliberadamente conservadora: cuenta palabras y signos y aplica un
    factor. **No sustituye al recuento del proveedor**: antes de invocar de verdad hay que
    cambiarla por `count_tokens` de la API, porque un recuento optimista convierte el
    techo duro del semaforo en un techo imaginario. Queda como hueco declarado.
    """
    piezas = re.findall(r"\w+|[^\w\s]", texto)
    return int(len(piezas) * 1.35) + 1 if piezas else 0


@dataclass(frozen=True)
class Bloque:
    """Un componente ya renderizado, con su contenido y su coste real."""

    componente: Componente
    contenido: str
    tokens: int

    @staticmethod
    def de(componente: Componente, contenido: str) -> Bloque:
        return Bloque(componente, contenido, contar_tokens(contenido))

    def recortado_a(self, tokens: int) -> Bloque:
        """Recorta el bloque **por su cola**, que aqui si es legitimo.

        Dentro de un componente lo ultimo es lo mas lejano: el resumen mas antiguo, la
        siembra con mas margen. Lo que D-12 prohibe es truncar el paquete entero por la
        cola, no adelgazar un componente por su parte menos urgente.
        """
        if tokens <= 0:
            return Bloque(self.componente, "", 0)
        if tokens >= self.tokens:
            return self
        proporcion = tokens / self.tokens
        corte = max(1, int(len(self.contenido) * proporcion))
        contenido = self.contenido[:corte].rstrip()
        return Bloque.de(self.componente, contenido)


def recortar(bloques: dict[Componente, Bloque], presupuesto: int) -> dict[Componente, Bloque]:
    """Aplica el orden de recorte hasta que el paquete quepa.

    Devuelve los bloques recortados. Si no cabe ni vaciando todo lo recortable, lanza
    `PresupuestoExcedido`: no se recorta lo intocable y no se trunca por la cola.
    """
    ajustados = dict(bloques)
    for componente in ORDEN_DE_RECORTE:
        total = sum(b.tokens for b in ajustados.values())
        if total <= presupuesto:
            return ajustados
        bloque = ajustados.get(componente)
        if bloque is None:
            continue
        sobra = total - presupuesto
        ajustados[componente] = bloque.recortado_a(max(0, bloque.tokens - sobra))

    total = sum(b.tokens for b in ajustados.values())
    if total > presupuesto:
        raise PresupuestoExcedido(total, presupuesto, total - presupuesto)
    return ajustados
