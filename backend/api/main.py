"""API. Encola tareas y lee estado; no invoca modelos por ninguna ruta.

La generacion de un capitulo tarda minutos, no milisegundos: nada de request/response
para tareas de generacion. Los endpoints de generacion crean una `Tarea` y devuelven su
id con `202 Accepted`; el progreso va por SSE (`architecture.md` 2.2).

Los modelos Pydantic son la frontera de serializacion, **no** las clases del dominio: las
clases del dominio no aparecen en ninguna firma de ruta (RF-API-06).

Cubre RF-API-01 a RF-API-07.
"""

from __future__ import annotations

import json
import uuid
from collections.abc import Iterator
from typing import Annotated, Any

from fastapi import Depends, FastAPI, HTTPException, Response, status
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from backend.store import database
from backend.store.database import Conexion as ConexionDelStore

app = FastAPI(
    title="MyStoryMaker",
    description="Canon verificable y bucle de una escena. La validacion ocurre aqui, "
    "nunca en el frontend: duplicar un invariante en JavaScript garantiza que las dos "
    "copias divergiran.",
    version="0.1.0",
)


def obtener_conexion() -> Iterator[Conexion]:
    """Dependencia de conexion. `store/` es el unico que abre SQLite."""
    with database.conexion() as conn:
        yield conn


Conexion = Annotated[ConexionDelStore, Depends(obtener_conexion)]


# --- esquemas de serializacion (no son clases del dominio) --------------------------


class BriefEntrada(BaseModel):
    id: str
    genero: str
    premisa: str
    promesa_al_lector: str
    extension_objetivo: int = Field(gt=0)


class EscenaEntrada(BaseModel):
    """Esqueleto de escena con los campos obligatorios de `AGENTS.md` 4.2.

    `hechos_requeridos` no es opcional: es lo que hace posible la validacion epistemica, y
    su coste de anotacion es real y esta declarado como riesgo en la spec.
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
    funcion_en_trama: str
    tipo: str
    renderiza: list[str] = Field(min_length=1)
    hechos_requeridos: list[str]
    presupuesto_palabras: int | None = None


class TareaCreada(BaseModel):
    tarea_id: str
    estado: str


class EstadoDeTareaSalida(BaseModel):
    tarea_id: str
    estado: str
    intentos_narrativos: int
    reserva: int
    falta: list[str]


# --- altas de canon y estructura (RF-API-01) ----------------------------------------


@app.post("/brief", status_code=status.HTTP_201_CREATED)
def alta_de_brief(entrada: BriefEntrada, conn: Conexion) -> dict[str, str]:
    """Alta del encargo. La validacion del dominio corre antes de tocar la base."""
    from backend.domain.errors import ErrorDeDominio
    from backend.domain.spec.encargo import Brief

    try:
        Brief(**entrada.model_dump())
    except ErrorDeDominio as error:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, str(error)) from error

    conn.execute(
        "INSERT INTO brief (id, genero, premisa, promesa_al_lector, extension_objetivo) "
        "VALUES (?, ?, ?, ?, ?)",
        (
            entrada.id,
            entrada.genero,
            entrada.premisa,
            entrada.promesa_al_lector,
            entrada.extension_objetivo,
        ),
    )
    return {"id": entrada.id}


@app.post("/escenas", status_code=status.HTTP_201_CREATED)
def alta_de_escena(entrada: EscenaEntrada, conn: Conexion) -> dict[str, str]:
    """Alta del esqueleto. Si falta un campo obligatorio, `422` (RF-API-02)."""
    from backend.domain.discursive.relato import Escena
    from backend.domain.errors import ErrorDeDominio
    from backend.domain.vocabularies import FuncionEnTrama, TipoDeEscena

    try:
        Escena(
            **{
                **entrada.model_dump(exclude={"funcion_en_trama", "tipo", "renderiza"}),
                "funcion_en_trama": FuncionEnTrama(entrada.funcion_en_trama),
                "tipo": TipoDeEscena(entrada.tipo),
                "renderiza": tuple(entrada.renderiza),
            }
        )
    except (ErrorDeDominio, ValueError) as error:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, str(error)) from error

    conn.execute(
        "INSERT INTO escena (id, capitulo_id, orden, pov_id, lugar_id, momento_en_historia,"
        " objetivo, conflicto, resultado, valor_entrada, valor_salida, funcion_en_trama,"
        " tipo, presupuesto_palabras) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
        (
            entrada.id,
            entrada.capitulo_id,
            entrada.orden,
            entrada.pov_id,
            entrada.lugar_id,
            entrada.momento_en_historia,
            entrada.objetivo,
            entrada.conflicto,
            entrada.resultado,
            entrada.valor_entrada,
            entrada.valor_salida,
            entrada.funcion_en_trama,
            entrada.tipo,
            entrada.presupuesto_palabras,
        ),
    )
    conn.executemany(
        "INSERT INTO escena_evento (escena_id, evento_id) VALUES (?, ?)",
        [(entrada.id, e) for e in entrada.renderiza],
    )
    conn.executemany(
        "INSERT INTO escena_hecho_requerido (escena_id, hecho_id) VALUES (?, ?)",
        [(entrada.id, h) for h in entrada.hechos_requeridos],
    )
    return {"id": entrada.id}


# --- generacion: se encola, no se bloquea (RF-API-03) --------------------------------


@app.post("/escenas/{escena_id}/redactar", status_code=status.HTTP_202_ACCEPTED)
def pedir_redaccion(escena_id: str, conn: Conexion, response: Response) -> TareaCreada:
    """Crea el `Plan` y su cadena de tareas. Devuelve el id; no espera a nada."""
    from backend.orchestrator.plan import cadena_de_escena

    plan_id = f"pl-{uuid.uuid4().hex[:8]}"
    conn.execute(
        "INSERT INTO plan (id, objetivo) VALUES (?, ?)", (plan_id, f"redactar {escena_id}")
    )
    tareas = cadena_de_escena(escena_id, plan_id)
    for tarea in tareas:
        conn.execute(
            "INSERT INTO tarea (id, plan_id, tipo, rol_asignado, estado, prioridad) "
            "VALUES (?,?,?,?,?,?)",
            (
                tarea.id,
                plan_id,
                tarea.tipo,
                tarea.rol_asignado,
                tarea.estado.value,
                tarea.prioridad,
            ),
        )
        for dependencia in tarea.depende_de:
            conn.execute(
                "INSERT INTO tarea_dependencia (tarea_id, depende_de) VALUES (?, ?)",
                (tarea.id, dependencia),
            )
    response.status_code = status.HTTP_202_ACCEPTED
    return TareaCreada(tarea_id=tareas[0].id, estado=tareas[0].estado.value)


@app.get("/tareas/{tarea_id}")
def estado_de_tarea(tarea_id: str, conn: Conexion) -> EstadoDeTareaSalida:
    fila = conn.execute(
        "SELECT id, estado, reserva, falta FROM tarea WHERE id = ?", (tarea_id,)
    ).fetchone()
    if fila is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"no existe la tarea {tarea_id}")

    narrativos = conn.execute(
        "SELECT COUNT(*) AS n FROM tarea_intento WHERE tarea_id = ? "
        "AND clase_de_fallo IN ('contrato', 'contenido')",
        (tarea_id,),
    ).fetchone()["n"]

    return EstadoDeTareaSalida(
        tarea_id=fila["id"],
        estado=fila["estado"],
        intentos_narrativos=narrativos,
        reserva=fila["reserva"],
        falta=[f for f in fila["falta"].split("|") if f],
    )


@app.get("/tareas/{tarea_id}/eventos")
def eventos_de_tarea(tarea_id: str, conn: Conexion) -> StreamingResponse:
    """SSE de transiciones. El frontend no hace polling ni infiere progreso.

    Las filas se leen **antes** de empezar a emitir, con la conexion de la peticion. Si el
    generador abriera la suya, se saltaria la configuracion de quien llama y acabaria
    leyendo de otra base sin avisar: es justo lo que hizo la primera version, y solo se
    vio porque un test uso una copia temporal.

    Lo que v1 emite es el historial ya registrado, no un flujo en vivo. Seguir la tabla
    mientras la tarea avanza exige decidir el mecanismo de espera, y eso no esta en el
    alcance de esta version.
    """
    filas = conn.execute(
        "SELECT estado, timestamp FROM tarea_evento WHERE tarea_id = ? ORDER BY id",
        (tarea_id,),
    ).fetchall()
    transiciones = [{"estado": f["estado"], "timestamp": f["timestamp"]} for f in filas]

    def emitir() -> Iterator[str]:
        for transicion in transiciones:
            yield f"data: {json.dumps(transicion)}\n\n"

    return StreamingResponse(emitir(), media_type="text/event-stream")


# --- lecturas (RF-API-05) ------------------------------------------------------------


@app.get("/escenas/{escena_id}/borradores")
def borradores_de_escena(escena_id: str, conn: Conexion) -> list[dict[str, Any]]:
    filas = conn.execute(
        "SELECT id, version, estado, recuento_palabras FROM borrador "
        "WHERE escena_id = ? ORDER BY version",
        (escena_id,),
    ).fetchall()
    return [dict(f) for f in filas]


@app.get("/borradores/{borrador_id}/defectos")
def defectos_de_borrador(borrador_id: str, conn: Conexion) -> list[dict[str, Any]]:
    filas = conn.execute(
        "SELECT id, tipo, severidad, regla_violada, evidencia, extraccion_evaluada "
        "FROM defecto WHERE borrador_id = ? ORDER BY id",
        (borrador_id,),
    ).fetchall()
    return [dict(f) for f in filas]


@app.get("/puertas")
def resultado_de_puertas(conn: Conexion) -> list[dict[str, Any]]:
    """Incluye la evidencia ausente: una puerta no dice solo si paso."""
    filas = conn.execute(
        "SELECT id, fase, politica, resultado, evidencia_ausente FROM puerta ORDER BY id"
    ).fetchall()
    return [dict(f) for f in filas]


@app.get("/predicados")
def catalogo_de_predicados(conn: Conexion) -> list[dict[str, Any]]:
    """El catalogo es de solo lectura por API: se amplia por migracion (R-7)."""
    filas = conn.execute(
        "SELECT nombre, exclusividad, descripcion FROM predicado ORDER BY nombre"
    ).fetchall()
    return [dict(f) for f in filas]
