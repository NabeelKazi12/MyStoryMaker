"""Ensamblado del `PaqueteDeContexto`.

El ensamblador cuenta tokens **antes** de llamar y guarda el recuento real por componente:
es la metrica que dice si la compresion se degrada a lo largo del libro
(`architecture.md` 4.4).

El paquete se reconstruye entero desde el store en cada invocacion. No existe historial
acumulativo: es lo unico que hace cierto el invariante de que el paquete de la escena 3 y
el de la escena 40 midan lo mismo, y lo que evita arrastrar prosa ya rechazada al intento
siguiente (D-09).

Cubre RF-CTX-01, RF-CTX-02, RF-CTX-03, RF-CTX-04, RF-CTX-06, RF-CTX-07 y RF-CTX-08.
"""

from __future__ import annotations

import hashlib
from collections.abc import Sequence
from dataclasses import dataclass, field

from backend.context.presupuesto import (
    INTOCABLES,
    MAXIMO_DE_ENTRADA,
    PRESUPUESTO_DE_REDACCION,
    Bloque,
    Componente,
    PresupuestoExcedido,
    PresupuestoFueraDeRango,
    recortar,
)
from backend.domain.production.ejecucion import Defecto, PaqueteDeContexto


@dataclass
class Ensamblador:
    """Construye el paquete de una invocacion, en el orden del contrato de rol.

    No recibe el intento anterior ni acumula nada entre llamadas: cada `ensamblar` parte
    de cero. Lo unico que cambia entre el intento 1 y el 2 es la cola —los defectos
    abiertos—, que es justo lo que hace util la cache de prefijo.
    """

    revision_canon: int
    version_de_prompt: str
    presupuesto: int = PRESUPUESTO_DE_REDACCION
    _bloques: dict[Componente, Bloque] = field(default_factory=dict)

    def __post_init__(self) -> None:
        """RF-CTX-08: el maximo de entrada es un limite, no una sugerencia."""
        if self.presupuesto > MAXIMO_DE_ENTRADA or self.presupuesto <= 0:
            raise PresupuestoFueraDeRango(self.presupuesto)

    def poner(self, componente: Componente, contenido: str) -> Ensamblador:
        """Coloca un componente. El orden de llamada da igual: manda el del contrato."""
        self._bloques[componente] = Bloque.de(componente, contenido)
        return self

    def con_defectos(self, defectos: Sequence[Defecto]) -> Ensamblador:
        """Los defectos abiertos del intento anterior van al final y no se recortan.

        Son la instruccion de reescritura: sin ellos el intento 2 repite el intento 1.
        El borrador rechazado, en cambio, **no entra** (R-4): reinyectarlo invita a
        reproducirlo.
        """
        if not defectos:
            return self
        texto = "\n".join(
            f"- [{d.severidad.value}] {d.regla_violada}. Evidencia: {d.evidencia}"
            for d in defectos
        )
        return self.poner(Componente.DEFECTOS_ABIERTOS, texto)

    def ensamblar(self, tarea_id: str, paquete_id: str) -> tuple[PaqueteDeContexto, str]:
        """Cuenta, recorta si hace falta, hashea y devuelve el paquete con su texto.

        Lanza `PresupuestoExcedido` si no cabe ni tras agotar el orden de recorte. Quien
        llama lo traduce en `Tarea` a `bloqueada` con `falta`: no se trunca, no se sube el
        presupuesto.
        """
        ajustados = recortar(self._bloques, self.presupuesto)
        ordenados = [ajustados[c] for c in sorted(ajustados) if ajustados[c].tokens > 0]
        texto = "\n\n".join(b.contenido for b in ordenados)

        paquete = PaqueteDeContexto(
            id=paquete_id,
            tarea_id=tarea_id,
            revision_canon=self.revision_canon,
            hash=self.hash_de(texto),
            tokens_por_componente=tuple((b.componente.name, b.tokens) for b in ordenados),
        )
        return paquete, texto

    def hash_de(self, texto: str) -> str:
        """Hash estable del paquete.

        Entra la revision de canon y la version de prompt, no solo el texto: dos paquetes
        con el mismo texto construidos contra canones distintos no son reproducibles el
        uno desde el otro, y confundirlos haria pasar un *replay* que en realidad miente.
        """
        semilla = f"{self.revision_canon}|{self.version_de_prompt}|{texto}"
        return hashlib.sha256(semilla.encode("utf-8")).hexdigest()

    @property
    def tokens_actuales(self) -> int:
        return sum(b.tokens for b in self._bloques.values())

    def intocables_presentes(self) -> frozenset[Componente]:
        """Que componentes intocables se han puesto. Util para comprobar el contrato."""
        return frozenset(c for c in self._bloques if c in INTOCABLES)


def bloqueada_por_presupuesto(error: PresupuestoExcedido) -> tuple[str, ...]:
    """Traduce el desbordamiento en la lista `falta` de la `Tarea`.

    Decir «no cabe» no sirve de nada: lo que el Orquestador necesita saber es cuanto sobra
    y que palanca queda, que es apretar el filtro estructural.
    """
    return (
        f"el paquete excede su presupuesto en {error.faltan} tokens",
        "apretar el filtro estructural de AlcanceDeRelevancia",
        "no subir el presupuesto: esconderia que el filtro esta mal acotado",
    )
