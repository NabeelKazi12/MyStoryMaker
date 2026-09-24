"""Regeneracion selectiva por un cambio que pide el lector.

«El perro se llama Nala» no puede obligar a reescribir la novela entera, y tampoco puede
tocar solo el capitulo donde el lector lo leyo: hay que tocar todos los que usan ese
hecho, y solo esos. Los dos errores son caros de formas distintas -regenerar de mas paga
invocaciones, regenerar de menos deja la novela contradiciendose a si misma-, y por eso
el conjunto sale del registro de uso y no de una heuristica.

Cubre RF-LEC-05, RF-LEC-06 y RF-LEC-07.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass

from backend.store.database import Conexion
from backend.store.repositories import UsoDeHechos, VersionesDeNovela


@dataclass(frozen=True)
class CambioDelLector:
    """Lo que el lector pide cambiar, anclado a un hecho del canon.

    Va anclado a un `Hecho` y no a un fragmento de texto a proposito: un fragmento solo
    sabe de un capitulo, y el mismo hecho puede estar sosteniendo otros cinco.
    """

    hecho_id: str
    descripcion: str


def capitulos_afectados(cambio: CambioDelLector, *, usos: UsoDeHechos) -> tuple[str, ...]:
    """Los capitulos que hay que regenerar, ni uno mas.

    Si el hecho no consta usado en ningun capitulo, la respuesta es vacio y no «toda la
    novela»: lo primero se puede investigar, lo segundo cuesta una novela entera.
    """
    return usos.capitulos_de(cambio.hecho_id)


def publicar_version(
    conn: Conexion,
    *,
    volumen_id: str,
    capitulos: tuple[str, ...],
    cambiados: tuple[str, ...] = (),
    motivo: str = "",
) -> str:
    """Publica una version nueva encadenada a la anterior, que se conserva."""
    identificador = f"ver-{uuid.uuid4().hex[:12]}"
    return VersionesDeNovela(conn).publicar(
        identificador,
        volumen_id=volumen_id,
        capitulos=capitulos,
        cambiados=cambiados,
        motivo=motivo,
    )
