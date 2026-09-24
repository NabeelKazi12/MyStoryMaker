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

from backend.domain.vocabularies import ModoDeEscritura
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
    """Dependencia de conexion. `store/` es el unico que abre SQLite.

    Comprueba que la base esta migrada antes de servir nada. SQLite **crea** el fichero
    al conectarse, asi que una ruta equivocada no falla: produce una base vacia, y la
    primera consulta muere con «no such table» y un 500 sin cuerpo. El sintoma real -la
    variable de entorno sin poner- queda a dos saltos del mensaje, y hay que ir a los
    logs del servidor para verlo.
    """
    with database.conexion() as conn:
        if not _esta_migrada(conn):
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=(
                    f"La base de datos {database.ruta_de_la_base()} no esta migrada: no "
                    f"tiene tablas. Comprueba que MYSTORYMAKER_DB apunta a la base "
                    f"correcta y ejecuta «uv run alembic upgrade head»."
                ),
            )
        yield conn


def _esta_migrada(conn: Conexion) -> bool:
    """Si el esquema existe. Se mira una tabla del canon, no `alembic_version`.

    Una base sellada por Alembic pero sin tablas -que pasa si alguien sella a mano- es
    tan inutil como una vacia, y este predicado tiene que decir que no en los dos casos.
    """
    fila = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = 'volumen'"
    ).fetchone()
    return fila is not None


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


# --- SPEC-003, fase E: las rutas de lectura ------------------------------------------
# Son de solo lectura y viven aqui porque `api/` encola y lee estado (CLAUDE.md 4). La
# peticion de cambio del lector no regenera nada desde la ruta: encola una Tarea y
# devuelve 202, como toda generacion.


class PeticionDeCambio(BaseModel):
    """Lo que el lector pide cambiar, anclado a un hecho del canon."""

    hecho_id: str = Field(min_length=1)
    descripcion: str = Field(min_length=1)


@app.get("/novelas/{volumen_id}/lectura", operation_id="readNovela")
def lectura_de_novela(volumen_id: str, conn: Conexion) -> dict[str, Any]:
    """Todo lo que la lectura necesita: portada, indice y ficha, en una sola llamada.

    Una sola llamada y no cuatro porque la lectura se abre entera: encadenar peticiones
    produce una portada que aparece antes que su indice.
    """
    volumen = conn.execute(
        "SELECT id, titulo FROM volumen WHERE id = ?", (volumen_id,)
    ).fetchone()
    if volumen is None:
        raise HTTPException(status_code=404, detail=f"no existe el volumen {volumen_id}")

    capitulos = conn.execute(
        "SELECT id, orden FROM capitulo WHERE volumen_id = ? ORDER BY orden",
        (volumen_id,),
    ).fetchall()
    # La ficha sale de lo que **esta** novela narra, no del canon entero. Sin acotar, el
    # regalo de Ana mostraria los personajes de la novela de Marta: con una novela por
    # proceso no se notaba, y en cuanto hay dos en la misma base es una fuga entre
    # clientes.
    personajes = conn.execute(
        """
        SELECT DISTINCT p.id, p.nombre_canonico
        FROM personaje p
        JOIN escena e ON e.pov_id = p.id
        JOIN capitulo c ON c.id = e.capitulo_id
        WHERE c.volumen_id = ?
        UNION
        SELECT DISTINCT p.id, p.nombre_canonico
        FROM personaje p
        JOIN evento_participante ep ON ep.entidad_id = p.id
        JOIN escena_evento se ON se.evento_id = ep.evento_id
        JOIN escena e ON e.id = se.escena_id
        JOIN capitulo c ON c.id = e.capitulo_id
        WHERE c.volumen_id = ?
        ORDER BY 2
        """,
        (volumen_id, volumen_id),
    ).fetchall()
    lugares = conn.execute(
        """
        SELECT DISTINCT l.id, l.nombre_canonico
        FROM lugar l
        JOIN escena e ON e.lugar_id = l.id
        JOIN capitulo c ON c.id = e.capitulo_id
        WHERE c.volumen_id = ?
        ORDER BY 2
        """,
        (volumen_id,),
    ).fetchall()
    # El destinatario es el del brief de **esta** novela. La columna `volumen.brief_id`
    # existe justamente para poder preguntarlo en lugar de adivinarlo.
    destinatario = conn.execute(
        """
        SELECT d.nombre, d.dedicatoria
        FROM destinatario d
        JOIN volumen v ON v.brief_id = d.brief_id
        WHERE v.id = ?
        LIMIT 1
        """,
        (volumen_id,),
    ).fetchone()

    return {
        "volumen_id": volumen["id"],
        "titulo": volumen["titulo"],
        "dedicatoria": "" if destinatario is None else destinatario["dedicatoria"],
        "destinatario": "" if destinatario is None else destinatario["nombre"],
        "capitulos": [dict(f) for f in capitulos],
        "personajes": [dict(f) for f in personajes],
        "lugares": [dict(f) for f in lugares],
    }


@app.get("/novelas/{volumen_id}/versiones", operation_id="listVersiones")
def versiones_de_novela(volumen_id: str, conn: Conexion) -> list[dict[str, Any]]:
    """El historial. La version anterior se conserva siempre (RF-LEC-07)."""
    filas = conn.execute(
        "SELECT id, numero, anterior_id, publicada_en, motivo FROM version_novela "
        "WHERE volumen_id = ? ORDER BY numero",
        (volumen_id,),
    ).fetchall()
    return [dict(f) for f in filas]


@app.get("/versiones/{version_id}/capitulos", operation_id="listCapitulosDeVersion")
def capitulos_de_version(version_id: str, conn: Conexion) -> list[dict[str, Any]]:
    """Que capitulos lleva una version y cuales cambiaron respecto a la anterior."""
    filas = conn.execute(
        "SELECT capitulo_id, borrador_id, cambiado FROM version_capitulo "
        "WHERE version_id = ? ORDER BY capitulo_id",
        (version_id,),
    ).fetchall()
    return [dict(f) for f in filas]


@app.post(
    "/novelas/{volumen_id}/cambios",
    status_code=status.HTTP_202_ACCEPTED,
    operation_id="createCambioDelLector",
)
def pedir_cambio(volumen_id: str, peticion: PeticionDeCambio, conn: Conexion) -> dict[str, Any]:
    """Acepta el cambio y devuelve **que capitulos** se van a regenerar.

    Devolver la lista en la respuesta no es un detalle: es lo que permite al lector ver
    que pedir un nombre de perro no reescribe la novela entera.
    """
    from backend.orchestrator.regeneracion import CambioDelLector, capitulos_afectados
    from backend.store.repositories import UsoDeHechos

    afectados = capitulos_afectados(
        CambioDelLector(hecho_id=peticion.hecho_id, descripcion=peticion.descripcion),
        usos=UsoDeHechos(conn),
    )
    return {
        "volumen_id": volumen_id,
        "hecho_id": peticion.hecho_id,
        "capitulos_afectados": list(afectados),
        "estado": "aceptado",
    }


# --- SPEC-004: escribir la novela y leer lo escrito ---------------------------------
# Las tres rutas mantienen la regla 5 de `architecture.md` 2.3: la de escritura **encola**
# y devuelve 202; quien invoca modelos es el worker. Las otras dos son lecturas.


class PeticionDeEscritura(BaseModel):
    """Con que se quiere escribir la novela. El modo se pide, no se adivina."""

    modo: str = "modelo"


class EscrituraAceptada(BaseModel):
    """Lo que devuelve encargar la escritura. No hay prosa todavia, y se dice."""

    volumen_id: str
    plan_id: str
    modo: str
    tareas: list[str]
    aviso: str


class EscenaEnProgreso(BaseModel):
    escena_id: str
    capitulo_id: str
    capitulo_orden: int
    estado: str
    intentos_narrativos: int
    falta: list[str]


class ProgresoDeEscritura(BaseModel):
    volumen_id: str
    estado: str
    modo: str | None
    plan_id: str | None
    escritas: int
    totales: int
    detalle: str
    escenas: list[EscenaEnProgreso]


class EscenaConTexto(BaseModel):
    """Una escena con su prosa y con la verdad sobre su estado."""

    id: str
    orden: int
    texto: str
    palabras: int
    estado: str
    aceptado: bool
    motivo: str
    modelo: str


class CapituloConTexto(BaseModel):
    id: str
    orden: int
    titulo: str
    palabras: int
    escenas: list[EscenaConTexto]


class TextoDeNovela(BaseModel):
    volumen_id: str
    titulo: str
    palabras: int
    de_demostracion: bool
    capitulos: list[CapituloConTexto]


@app.post(
    "/novelas/{volumen_id}/escritura",
    status_code=status.HTTP_202_ACCEPTED,
    operation_id="createEscritura",
)
def encargar_escritura(
    volumen_id: str, peticion: PeticionDeEscritura, conn: Conexion
) -> EscrituraAceptada:
    """Encola la escritura de la novela entera. No invoca ningun modelo (RF-RUT-01).

    Si el modo es `modelo` y no hay credencial, responde `503` **antes** de encolar nada.
    Encolar igualmente dejaria una novela a medio empezar que nadie puede terminar, y caer
    en demostracion por cuenta propia seria la bajada silenciosa que D-08 prohibe.
    """
    from backend.orchestrator.apertura import NovelaDesconocida
    from backend.orchestrator.escritura import NoHayConQueEscribir, encolar_escritura

    try:
        modo = ModoDeEscritura(peticion.modo)
    except ValueError:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            f"modo desconocido {peticion.modo!r}; hay «modelo» y «demostracion»",
        ) from None

    try:
        encolada = encolar_escritura(conn, volumen_id, modo)
    except NoHayConQueEscribir as sin_credencial:
        # Ni se encola ni se cae en demostracion por cuenta propia (D-08): se dice que
        # falta y quien pidio la escritura decide.
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE, str(sin_credencial)
        ) from None
    except NovelaDesconocida as desconocida:
        raise HTTPException(status.HTTP_404_NOT_FOUND, str(desconocida)) from None

    return EscrituraAceptada(
        volumen_id=encolada.volumen_id,
        plan_id=encolada.plan_id,
        modo=encolada.modo.value,
        tareas=list(encolada.tareas),
        aviso=_aviso_del_modo(encolada.modo),
    )


def _aviso_del_modo(modo: ModoDeEscritura) -> str:
    if modo is ModoDeEscritura.DEMOSTRACION:
        return (
            "Modo demostracion: la prosa la compone el sistema a partir del encargo, sin "
            "modelo. Queda marcada como tal en la procedencia de cada borrador y en la "
            "lectura, y no debe confundirse con una novela escrita."
        )
    return (
        "Encolada. El worker la ira escribiendo escena a escena; consulta el progreso en "
        "esta misma ruta con GET."
    )


@app.get("/novelas/{volumen_id}/escritura", operation_id="readProgresoDeEscritura")
def progreso_de_escritura(volumen_id: str, conn: Conexion) -> ProgresoDeEscritura:
    """Por donde va la escritura. Una novela sin encargar responde `200`, no `404`."""
    from backend.orchestrator.escritura import progreso

    _exigir_volumen(conn, volumen_id)
    estado = progreso(conn, volumen_id)
    return ProgresoDeEscritura(
        volumen_id=estado.volumen_id,
        estado=estado.estado,
        modo=None if estado.modo is None else estado.modo.value,
        plan_id=estado.plan_id,
        escritas=estado.escritas,
        totales=estado.totales,
        detalle=estado.detalle,
        escenas=[
            EscenaEnProgreso(
                escena_id=escena.escena_id,
                capitulo_id=escena.capitulo_id,
                capitulo_orden=escena.capitulo_orden,
                estado=escena.estado,
                intentos_narrativos=escena.intentos_narrativos,
                falta=list(escena.falta),
            )
            for escena in estado.escenas
        ],
    )


@app.get("/novelas/{volumen_id}/texto", operation_id="readTextoDeNovela")
def texto_de_novela(volumen_id: str, conn: Conexion) -> TextoDeNovela:
    """La prosa escrita, capitulo a capitulo, con el estado de cada borrador.

    Sirve el ultimo borrador **no obsoleto**, no el aceptado: en v1 la puerta
    `escena_limpia` siempre trae evidencia ausente, asi que no hay aceptados y una lectura
    que solo los sirviera estaria vacia para siempre sin que nada lo explicara (D-21).
    """
    from backend.store.escritura import TextoDeLaNovela

    volumen = _exigir_volumen(conn, volumen_id)
    capitulos = TextoDeLaNovela(conn).por_capitulos(volumen_id)
    escenas = [escena for capitulo in capitulos for escena in capitulo.escenas]

    return TextoDeNovela(
        volumen_id=volumen_id,
        titulo=volumen["titulo"],
        palabras=sum(escena.palabras for escena in escenas),
        # Basta con que una escena lo sea: media novela de demostracion es una novela de
        # demostracion, y redondear hacia «esto es del modelo» seria mentir por omision.
        de_demostracion=any(escena.modelo == "demostracion" for escena in escenas),
        capitulos=[
            CapituloConTexto(
                id=capitulo.id,
                orden=capitulo.orden,
                titulo=capitulo.titulo,
                palabras=capitulo.palabras,
                escenas=[
                    EscenaConTexto(
                        id=escena.id,
                        orden=escena.orden,
                        texto=escena.texto,
                        palabras=escena.palabras,
                        estado=escena.estado,
                        aceptado=escena.aceptado,
                        motivo=escena.motivo,
                        modelo=escena.modelo,
                    )
                    for escena in capitulo.escenas
                ],
            )
            for capitulo in capitulos
        ],
    )


@app.get(
    "/novelas/{volumen_id}/pdf",
    operation_id="readPdfDeNovela",
    response_class=Response,
    responses={200: {"content": {"application/pdf": {}}}},
)
def pdf_de_novela(volumen_id: str, conn: Conexion) -> Response:
    """La novela escrita como PDF, para guardarla o regalarla.

    Maqueta lo mismo que sirve `/texto` -el ultimo borrador no obsoleto de cada escena-,
    con la portada y la ficha de `/lectura`. Una novela sin prosa responde `409` en vez
    de un PDF con capitulos vacios, que pareceria un regalo y no lo seria.
    """
    import tempfile
    from pathlib import Path

    from backend.export.pdf import CapituloParaPDF, NovelaParaPDF, exportar_pdf

    lectura = lectura_de_novela(volumen_id, conn)
    texto = texto_de_novela(volumen_id, conn)
    capitulos = tuple(
        CapituloParaPDF(
            id=capitulo.id,
            orden=capitulo.orden,
            titulo=capitulo.titulo or f"Capitulo {capitulo.orden}",
            texto="\n\n".join(escena.texto for escena in capitulo.escenas),
        )
        for capitulo in texto.capitulos
        if capitulo.escenas
    )
    if not capitulos:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            "La novela todavia no tiene prosa escrita. Pulsa «Escribir la novela» y "
            "descargala cuando termine.",
        )

    primero = capitulos[0].id
    novela = NovelaParaPDF(
        titulo=lectura["titulo"],
        dedicatoria=lectura["dedicatoria"] or "",
        destinatario=lectura["destinatario"] or "",
        personajes=tuple((p["nombre_canonico"], primero) for p in lectura["personajes"]),
        lugares=tuple((lugar["nombre_canonico"], primero) for lugar in lectura["lugares"]),
        capitulos=capitulos,
    )
    with tempfile.TemporaryDirectory() as carpeta:
        destino = Path(carpeta) / "novela.pdf"
        exportar_pdf(novela, destino)
        contenido = destino.read_bytes()

    # La cabecera solo admite latin-1: el nombre del fichero va en ASCII.
    nombre = "".join(
        c if c.isascii() and c.isalnum() else "-" for c in lectura["titulo"]
    ).strip("-")
    return Response(
        content=contenido,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'attachment; filename="{nombre or volumen_id}.pdf"'
        },
    )


class PeticionDePortada(BaseModel):
    """Lo que se quiere cambiar de la portada. Lo que no se envia, no cambia."""

    titulo: str | None = None
    dedicatoria: str | None = None


class PortadaGuardada(BaseModel):
    volumen_id: str
    titulo: str
    dedicatoria: str


@app.patch("/novelas/{volumen_id}/portada", operation_id="updatePortada")
def editar_portada(
    volumen_id: str, peticion: PeticionDePortada, conn: Conexion
) -> PortadaGuardada:
    """Cambia el titulo o la dedicatoria. No toca prosa, canon, tareas ni versiones.

    Los limites y el guardarrail los decide `orchestrator/`; aqui solo se traducen a `422`
    con su motivo, para que la pantalla lo muestre tal cual.
    """
    from backend.orchestrator.portada import (
        NovelaSinPortada,
        PortadaInvalida,
    )
    from backend.orchestrator.portada import (
        editar_portada as editar,
    )

    try:
        portada = editar(
            conn, volumen_id, titulo=peticion.titulo, dedicatoria=peticion.dedicatoria
        )
    except NovelaSinPortada as ausente:
        raise HTTPException(status.HTTP_404_NOT_FOUND, str(ausente)) from None
    except PortadaInvalida as invalida:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, str(invalida)) from None

    return PortadaGuardada(
        volumen_id=portada.volumen_id, titulo=portada.titulo, dedicatoria=portada.dedicatoria
    )


def _exigir_volumen(conn: Conexion, volumen_id: str) -> Any:
    fila = conn.execute(
        "SELECT id, titulo FROM volumen WHERE id = ?", (volumen_id,)
    ).fetchone()
    if fila is None:
        raise HTTPException(
            status.HTTP_404_NOT_FOUND, f"no existe el volumen {volumen_id}"
        )
    return fila


# --- SPEC-003, fase C: la entrevista es la puerta de entrada ------------------------
# Es la unica ruta por la que entra texto que nadie del sistema ha escrito. El texto se
# conserva entero -de el salen los recuerdos- y lo que parezca una orden se devuelve
# como aviso en lugar de ejecutarse.


class PeticionDeEntrevista(BaseModel):
    """Las respuestas recogidas y, si lo hay, el texto que el cliente pego."""

    respuestas: dict[str, Any]
    texto_libre: str = ""


@app.post("/entrevista", status_code=status.HTTP_201_CREATED, operation_id="createEntrevista")
def cerrar_entrevista(peticion: PeticionDeEntrevista, conn: Conexion) -> dict[str, Any]:
    """Cierra la entrevista y crea la novela, o dice que falta y que choca.

    La ruta no habla con el rol: eso es de `orchestrator/`, porque `api/` no importa de
    `agents/` (`CLAUDE.md` 4). Aqui solo se traduce el fallo del dominio en un `422` que
    enumera los huecos y las contradicciones, en vez de un «datos invalidos» que obligaria
    a repetir la entrevista entera.
    """
    from backend.orchestrator.encargo import (
        EntrevistaSinCerrar,
        crear_novela_desde_entrevista,
    )

    try:
        creada = crear_novela_desde_entrevista(conn, peticion.respuestas, peticion.texto_libre)
    except EntrevistaSinCerrar as sin_cerrar:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={
                "huecos": list(sin_cerrar.huecos),
                "contradicciones": [
                    {"campos": list(campos), "detalle": detalle}
                    for campos, detalle in sin_cerrar.contradicciones
                ],
            },
        ) from None

    return {
        "brief_id": creada.brief_id,
        "volumen_id": creada.volumen_id,
        "titulo": creada.titulo,
        "destinatario": creada.destinatario,
        "palabras_vetadas": list(creada.palabras_vetadas),
        "intentos_de_injection": list(creada.intentos_de_injection),
        "hechos_propuestos": list(creada.hechos_propuestos),
    }
