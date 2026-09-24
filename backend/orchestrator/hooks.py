"""Los dos hooks del harness: validacion de capitulo y policy.

Corren en el orquestador y no en los roles, porque la coordinacion vive aqui
(`CLAUDE.md` 4) y porque un rol que se valida a si mismo es el caso que `AGENTS.md` 1
prohibe: quien genera no valida.

La diferencia entre los dos no es de contenido, es de autoridad:

- **El hook de capitulo** cobra los validadores deterministas de la prosa -longitud y
  nombres- y devuelve defectos para que el writer reescriba.
- **El hook de policy** cobra el guardarrail. Una palabra vetada no es un defecto de
  calidad que se pueda negociar: es una linea que el cliente trazo, y por eso su
  resultado se registra en el audit log aunque el capitulo se acepte despues.

Cubre RF-HAR-04.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from backend.domain.production.ejecucion import Defecto
from backend.domain.spec.encargo import Destinatario
from backend.quality.guardarrail import Guardarrail
from backend.quality.personalizacion import longitud_de_capitulo, nombres_exactos
from backend.store.database import Conexion


@dataclass(frozen=True)
class ResultadoDeHook:
    """Lo que un hook decide sobre un capitulo."""

    acepta: bool
    defectos: tuple[Defecto, ...] = ()
    motivo: str = ""


def hook_de_capitulo(
    texto: str,
    *,
    conn: Conexion,
    destinatario: Destinatario | None,
    personajes: Sequence[str] = (),
    rango: tuple[int, int] | None = None,
) -> ResultadoDeHook:
    """Los validadores deterministas de la prosa, antes de aceptar el capitulo.

    `conn` entra aunque hoy no se use en todos los caminos: el hook es el punto declarado
    de ejecucion de RF-VAL-02 y RF-VAL-03, y los validadores que vengan detras leeran la
    story bible desde aqui en lugar de abrirse su propio acceso.
    """
    defectos: list[Defecto] = []
    defectos += (
        longitud_de_capitulo(texto, rango=rango)
        if rango is not None
        else longitud_de_capitulo(texto)
    )
    if destinatario is not None:
        defectos += nombres_exactos(texto, destinatario=destinatario, personajes=personajes)

    return ResultadoDeHook(acepta=not defectos, defectos=tuple(defectos))


def hook_de_policy(
    texto: str,
    *,
    conn: Conexion,
    capitulo_id: str | None = None,
    brief_id: str | None = None,
    destinatario_id: str | None = None,
    tarea_id: str | None = None,
    intento: int = 1,
) -> ResultadoDeHook:
    """El guardarrail de palabras prohibidas, con su rastro en el audit log."""
    veredicto = Guardarrail(conn).revisar(
        texto,
        brief_id=brief_id,
        destinatario_id=destinatario_id,
        capitulo_id=capitulo_id,
        tarea_id=tarea_id,
        intento=intento,
    )
    if veredicto.limpio:
        return ResultadoDeHook(acepta=True)

    terminos = ", ".join(c.termino for c in veredicto.coincidencias)
    return ResultadoDeHook(
        acepta=False,
        motivo=f"terminos vetados presentes en el capitulo: {terminos}",
    )
