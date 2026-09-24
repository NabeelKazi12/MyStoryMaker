"""Escritura de una novela entera: encolar, expandir el plan y contar como va.

Este modulo es el que convierte «escribe esta novela» en `Tarea`s, y el que sabe leer la
cola al reves para decirle a la pantalla por donde va. No invoca modelos y no ensambla
prosa: lo primero es del worker y lo segundo tambien.

El plan crece en dos tiempos, y no por comodidad. Cuando se encarga la escritura todavia
no se sabe cuantas escenas tiene la novela -eso lo decide la apertura-, asi que el plan
nace con una sola tarea y se expande cuando esa tarea termina. La alternativa seria
inventar un numero de escenas antes de planificarlas, y entonces el plan dejaria de ser
el estado deseado y pasaria a ser una suposicion.

Cubre RF-ESC-01 a RF-ESC-04, RF-RUT-01 y RF-RUT-04.
"""

from __future__ import annotations

import uuid
from collections.abc import Sequence
from dataclasses import dataclass

from backend.context.ensamblado import Ensamblador
from backend.context.presupuesto import Componente
from backend.domain.vocabularies import EstadoDeTarea, ModoDeEscritura
from backend.orchestrator.apertura import (
    EncargoDeNovela,
    NovelaDesconocida,
    esta_abierta,
    instruccion_de_apertura,
    leer_encargo,
    prompt_del_planner,
)
from backend.orchestrator.ejecucion import registrar_transicion
from backend.orchestrator.plan import cadena_de_escena
from backend.store.database import Conexion, Fila

TIPO_DE_APERTURA = "apertura"
ROL_DE_APERTURA = "planner"

# La apertura es P0: mientras no exista el canon, ninguna otra tarea de la novela puede
# siquiera crearse, asi que dejarla competir por prioridad seria dejar que el sistema
# esperara a algo que el mismo esta bloqueando.
PRIORIDAD_DE_APERTURA = 0

# Presupuesto de palabras de una escena cuando la suya no esta declarada. No sale de la
# nada: con el techo de salida de 4.000 tokens de `architecture.md` 4.2, pedir mucho mas
# es pedir una escena que se va a truncar, y una salida truncada es fallo de contrato.
PALABRAS_POR_ESCENA = 800


class NoHayConQueEscribir(RuntimeError):
    """El modo pedido no se puede servir en este entorno, y se dice que falta.

    Vive aqui y no en `worker/` para que `api/` pueda traducirlo a un `503` sin nombrar el
    paquete del worker. La API encola y lee estado: no alcanza el cliente de modelo ni
    siquiera para preguntarle si existe.
    """


@dataclass(frozen=True)
class EscrituraEncolada:
    """Lo que deja el encargo de escritura. No hay prosa todavia, y se dice."""

    plan_id: str
    volumen_id: str
    modo: ModoDeEscritura
    tareas: tuple[str, ...]
    ya_estaba_abierta: bool


@dataclass(frozen=True)
class EstadoDeEscena:
    """Como va una escena, vista desde su cadena de tareas."""

    escena_id: str
    capitulo_id: str
    capitulo_orden: int
    estado: str
    intentos_narrativos: int
    falta: tuple[str, ...]


@dataclass(frozen=True)
class Progreso:
    """Por donde va la escritura de una novela.

    `estado` es del conjunto cerrado que la pantalla sabe pintar. No es una cadena libre:
    una pantalla que tuviera que deducir el estado global de una lista de tareas estaria
    tomando una decision del dominio, y eso vive aqui.
    """

    volumen_id: str
    estado: str
    modo: ModoDeEscritura | None
    plan_id: str | None
    escenas: tuple[EstadoDeEscena, ...]
    escritas: int
    totales: int
    detalle: str = ""

    @property
    def en_curso(self) -> bool:
        return self.estado in ("abriendo", "escribiendo")


def encolar_escritura(
    conn: Conexion, volumen_id: str, modo: ModoDeEscritura
) -> EscrituraEncolada:
    """Crea el plan y la primera tanda de tareas. No invoca nada (RF-RUT-01).

    Si la novela ya esta abierta, se salta la apertura y encola directamente la cadena de
    cada escena: volver a abrirla duplicaria el canon, y no abrirla ni escribir dejaria el
    boton sin efecto visible, que es peor que un error.

    Lo primero que hace es comprobar que el modo se puede servir. Encolar sin poder
    escribir dejaria una novela a medio empezar que nadie puede terminar, y el boton
    habria respondido que si.
    """
    exigir_con_que_escribir(modo)
    encargo = leer_encargo(conn, volumen_id)
    plan_id = f"pl-{uuid.uuid4().hex[:8]}"
    conn.execute(
        "INSERT INTO plan (id, objetivo, volumen_id, modo) VALUES (?, ?, ?, ?)",
        (plan_id, f"escribir {encargo.titulo}", volumen_id, modo.value),
    )

    abierta = esta_abierta(conn, volumen_id)
    if abierta:
        escenas = _escenas_del_volumen(conn, volumen_id)
        tareas = expandir_plan(conn, plan_id, escenas)
    else:
        tareas = (_encolar_apertura(conn, plan_id, volumen_id),)

    return EscrituraEncolada(
        plan_id=plan_id,
        volumen_id=volumen_id,
        modo=modo,
        tareas=tareas,
        ya_estaba_abierta=abierta,
    )


def exigir_con_que_escribir(modo: ModoDeEscritura) -> None:
    """Falla si el modo pedido no se puede servir en este entorno.

    Pregunta al worker, que es quien sabe que hace falta para invocar, y vuelve a lanzar
    el fallo con el tipo de este paquete. La traduccion no es burocracia: es lo que
    permite que quien encola conozca la respuesta sin conocer al cliente de modelo.
    """
    from backend.worker.modelo import ClaudeCodeAusente, exigir_que_se_puede_escribir

    try:
        exigir_que_se_puede_escribir(modo)
    except ClaudeCodeAusente as ausente:
        raise NoHayConQueEscribir(str(ausente)) from None


def _encolar_apertura(conn: Conexion, plan_id: str, volumen_id: str) -> str:
    tarea_id = f"{volumen_id}:apertura"
    conn.execute(
        "INSERT INTO tarea (id, plan_id, tipo, rol_asignado, estado, prioridad) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        (
            tarea_id,
            plan_id,
            TIPO_DE_APERTURA,
            ROL_DE_APERTURA,
            EstadoDeTarea.PENDIENTE.value,
            PRIORIDAD_DE_APERTURA,
        ),
    )
    registrar_transicion(conn, tarea_id, EstadoDeTarea.LISTA.value)
    return tarea_id


def expandir_plan(
    conn: Conexion, plan_id: str, escenas: Sequence[str]
) -> tuple[str, ...]:
    """Materializa la cadena de cada escena en la tabla de tareas.

    Es idempotente por construccion: los identificadores salen de la escena, asi que
    reejecutar la expansion no crea tareas nuevas. Sin eso, una apertura que se reintenta
    dejaria la novela con dos cadenas por escena y el progreso contaria el doble.
    """
    creadas: list[str] = []
    for escena_id in escenas:
        for tarea in cadena_de_escena(escena_id, plan_id):
            ya = conn.execute("SELECT 1 FROM tarea WHERE id = ?", (tarea.id,)).fetchone()
            if ya is not None:
                continue
            conn.execute(
                "INSERT INTO tarea (id, plan_id, tipo, rol_asignado, estado, prioridad) "
                "VALUES (?, ?, ?, ?, ?, ?)",
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
                    "INSERT OR IGNORE INTO tarea_dependencia (tarea_id, depende_de) "
                    "VALUES (?, ?)",
                    (tarea.id, dependencia),
                )
            creadas.append(tarea.id)
            if not tarea.depende_de:
                registrar_transicion(conn, tarea.id, EstadoDeTarea.LISTA.value)

    return tuple(creadas)


def _escenas_del_volumen(conn: Conexion, volumen_id: str) -> tuple[str, ...]:
    filas = conn.execute(
        "SELECT e.id FROM escena e JOIN capitulo c ON c.id = e.capitulo_id "
        "WHERE c.volumen_id = ? ORDER BY c.orden, e.orden",
        (volumen_id,),
    ).fetchall()
    return tuple(fila["id"] for fila in filas)


# --- los paquetes -------------------------------------------------------------------------


def paquete_de_apertura(
    conn: Conexion, volumen_id: str, revision_canon: int
) -> Ensamblador:
    """El paquete con el que se le pide al Planner que abra la novela.

    Lleva solo dos componentes y los dos son intocables: el contrato del rol y el encargo.
    No hay estado del mundo que poner -la novela todavia no tiene canon- y ponerlo vacio
    para «cumplir el formato» haria creer que se miro y no habia nada.
    """
    from backend.agents.planner.planner import VERSION_DE_PROMPT

    encargo = leer_encargo(conn, volumen_id)
    ensamblador = Ensamblador(
        revision_canon=revision_canon, version_de_prompt=VERSION_DE_PROMPT
    )
    ensamblador.poner(Componente.ESTATICO, prompt_del_planner())
    ensamblador.poner(Componente.INSTRUCCION, instruccion_de_apertura(encargo))
    return ensamblador


def paquete_de_escena(conn: Conexion, escena_id: str, revision_canon: int) -> Ensamblador:
    """Ensambla el paquete de una redaccion desde el canon, en el orden del contrato.

    Se reconstruye entero en cada invocacion: no hay historial acumulativo, y eso es lo
    unico que hace cierto el invariante de que el paquete de la escena 3 y el de la 40
    midan lo mismo (D-09).
    """
    from backend.agents.redactor.redactor import VERSION_DE_PROMPT, prompt_vigente
    from backend.store.repositories import CatalogoDePredicados

    escena = conn.execute(
        """
        SELECT e.id, e.capitulo_id, e.orden, e.objetivo, e.conflicto, e.resultado,
               e.valor_entrada, e.valor_salida, e.funcion_en_trama, e.tipo,
               e.momento_en_historia, e.presupuesto_palabras,
               c.orden AS capitulo_orden, c.titulo AS capitulo_titulo,
               c.volumen_id,
               pov.id AS pov_id, pov.nombre_canonico AS pov, pov.necesidad_interna,
               lug.id AS lugar_id, lug.nombre_canonico AS lugar, lug.atmosfera_sensorial,
               (SELECT se.evento_id FROM escena_evento se
                 WHERE se.escena_id = e.id ORDER BY se.evento_id LIMIT 1) AS renderiza
        FROM escena e
        JOIN capitulo c ON c.id = e.capitulo_id
        JOIN personaje pov ON pov.id = e.pov_id
        JOIN lugar lug ON lug.id = e.lugar_id
        WHERE e.id = ?
        """,
        (escena_id,),
    ).fetchone()
    if escena is None:
        raise NovelaDesconocida(escena_id, "no existe la escena que se pidio redactar")

    encargo = leer_encargo(conn, escena["volumen_id"])
    ensamblador = Ensamblador(
        revision_canon=revision_canon, version_de_prompt=VERSION_DE_PROMPT
    )

    ensamblador.poner(
        Componente.ESTATICO,
        "\n\n".join(
            [
                prompt_vigente(),
                f"premisa: {encargo.premisa}",
                f"promesa al lector: {encargo.promesa_al_lector}",
                f"genero: {encargo.genero}",
                f"tono: {encargo.tono}",
                # El catalogo es cerrado: un hecho con otro predicado no se puede
                # canonizar, asi que el rol tiene que saber cuales hay.
                "predicados: "
                + ", ".join(
                    f"{p.nombre} ({p.descripcion.lower()})"
                    for p in CatalogoDePredicados(conn).todos()
                ),
            ]
        ),
    )
    ensamblador.poner(
        Componente.ESTADO_DEL_MUNDO,
        _estado_del_mundo(conn, escena, escena["volumen_id"]),
    )
    ensamblador.poner(
        Componente.VOZ,
        f"Quien mira es {escena['pov']}. Lo que necesita por dentro, sin decirlo: "
        f"{escena['necesidad_interna'] or 'sin declarar'}.",
    )
    ensamblador.poner(
        Componente.EPISTEMICO,
        f"El punto de vista es {escena['pov']} y solo sabe lo que el estado del mundo "
        f"declara de el. Nada de lo que no este ahi puede darse por sabido.",
    )
    ensamblador.poner(Componente.ARCO, _arco(conn, escena["capitulo_id"]))
    ensamblador.poner(Componente.INSTRUCCION, _instruccion_de_escena(escena, encargo))
    return ensamblador


def _estado_del_mundo(conn: Conexion, escena: Fila, volumen_id: str) -> str:
    """Lo que hay que saber del mundo para esta escena, acotado a **su** novela.

    El acotado no es una optimizacion: sin el, el paquete de la novela de Ana llevaria los
    hechos de la novela de Marta. Con una novela por base no se nota, y en cuanto hay dos
    es una fuga entre clientes que ademas engorda el paquete con cosas que nadie narra.
    """
    # La clave es `escenario` y no `lugar` a proposito: el bloque de instruccion trae su
    # propia fila `lugar:` con el nombre canonico a secas, y dos filas con la misma clave
    # hacen que quien lea la primera se lleve la equivocada.
    escenario = (
        f"{escena['lugar']}: {escena['atmosfera_sensorial'] or 'sin atmosfera declarada'}"
    )
    hechos = conn.execute(
        """
        SELECT DISTINCT h.sujeto_id, h.predicado, h.objeto
        FROM hecho h
        JOIN escena e ON e.pov_id = h.sujeto_id
        JOIN capitulo c ON c.id = e.capitulo_id
        WHERE h.valido_hasta IS NULL AND c.volumen_id = ?
        ORDER BY h.sujeto_id, h.predicado
        """,
        (volumen_id,),
    ).fetchall()
    lineas = [f"escenario: {escenario}"]
    lineas += [f"hecho: {h['sujeto_id']} {h['predicado']} {h['objeto']}" for h in hechos]
    return "\n".join(lineas)


def _arco(conn: Conexion, capitulo_id: str) -> str:
    """Los resumenes de los capitulos anteriores, que es lo que mantiene el tamano."""
    from backend.context.ensamblado import bloque_de_arco
    from backend.store.repositories import ResumenesDeCapitulo

    resumenes = ResumenesDeCapitulo(conn).anteriores_a(capitulo_id)
    return bloque_de_arco([(r.capitulo_id, r.texto) for r in resumenes])


def _instruccion_de_escena(escena: Fila, encargo: EncargoDeNovela) -> str:
    """El esqueleto de la escena, en filas `clave: valor`.

    Mismo motivo que en la apertura: el modo de demostracion compone su prosa de estas
    filas, y una muestra que no hablara de esta escena no demostraria nada.
    """
    return "\n".join(
        [
            "Escribe esta escena.",
            "",
            f"escena: {escena['id']}",
            f"capitulo: {escena['capitulo_titulo'] or escena['capitulo_orden']}",
            f"pov: {escena['pov']}",
            f"pov_id: {escena['pov_id']}",
            f"lugar: {escena['lugar']}",
            f"objetivo: {escena['objetivo']}",
            f"conflicto: {escena['conflicto']}",
            f"resultado: {escena['resultado']}",
            f"valor_entrada: {escena['valor_entrada']}",
            f"valor_salida: {escena['valor_salida']}",
            f"funcion_en_trama: {escena['funcion_en_trama']}",
            f"tipo: {escena['tipo']}",
            f"renderiza: {escena['renderiza']}",
            f"palabras: {escena['presupuesto_palabras'] or PALABRAS_POR_ESCENA}",
            f"destinatario: {encargo.nombre}",
        ]
    )


# --- como va ------------------------------------------------------------------------------


def progreso(conn: Conexion, volumen_id: str) -> Progreso:
    """El estado de la escritura de una novela, para la pantalla y para el worker."""
    plan = conn.execute(
        "SELECT id, modo FROM plan WHERE volumen_id = ? ORDER BY rowid DESC LIMIT 1",
        (volumen_id,),
    ).fetchone()
    if plan is None:
        return Progreso(
            volumen_id=volumen_id,
            estado="sin_empezar",
            modo=None,
            plan_id=None,
            escenas=(),
            escritas=0,
            totales=0,
            detalle="Esta novela todavia no se ha encargado a nadie.",
        )

    modo = ModoDeEscritura(plan["modo"])
    apertura = conn.execute(
        "SELECT estado, falta FROM tarea WHERE plan_id = ? AND tipo = ?",
        (plan["id"], TIPO_DE_APERTURA),
    ).fetchone()

    filas = conn.execute(
        """
        SELECT t.id, t.estado, t.falta, e.id AS escena_id, e.capitulo_id,
               c.orden AS capitulo_orden,
               (SELECT COUNT(*) FROM tarea_intento i
                 WHERE i.tarea_id = t.id
                   AND i.clase_de_fallo IN ('contrato', 'contenido')) AS narrativos
        FROM tarea t
        JOIN escena e ON t.id = e.id || ':redaccion'
        JOIN capitulo c ON c.id = e.capitulo_id
        WHERE t.plan_id = ?
        ORDER BY c.orden, e.orden
        """,
        (plan["id"],),
    ).fetchall()

    escenas = tuple(
        EstadoDeEscena(
            escena_id=fila["escena_id"],
            capitulo_id=fila["capitulo_id"],
            capitulo_orden=fila["capitulo_orden"],
            estado=fila["estado"],
            intentos_narrativos=fila["narrativos"],
            falta=tuple(f for f in (fila["falta"] or "").split("|") if f),
        )
        for fila in filas
    )
    escritas = sum(1 for e in escenas if e.estado == EstadoDeTarea.ACEPTADA.value)

    return Progreso(
        volumen_id=volumen_id,
        estado=_estado_global(apertura, escenas, escritas),
        modo=modo,
        plan_id=plan["id"],
        escenas=escenas,
        escritas=escritas,
        totales=len(escenas),
        detalle=_detalle(apertura, escenas, escritas),
    )


def _estado_global(
    apertura: Fila | None, escenas: Sequence[EstadoDeEscena], escritas: int
) -> str:
    if apertura is not None and apertura["estado"] not in (
        EstadoDeTarea.ACEPTADA.value,
        EstadoDeTarea.CANCELADA.value,
    ):
        if apertura["estado"] == EstadoDeTarea.ESCALADA.value:
            return "fallida"
        return "abriendo"
    if not escenas:
        return "abriendo"
    if any(e.estado == EstadoDeTarea.ESCALADA.value for e in escenas):
        return "detenida"
    if escritas == len(escenas):
        return "escrita"
    return "escribiendo"


def _detalle(apertura: Fila | None, escenas: Sequence[EstadoDeEscena], escritas: int) -> str:
    """Una linea que explique el estado. La pantalla la muestra; no la compone."""
    estado = _estado_global(apertura, escenas, escritas)
    if estado == "abriendo":
        return "Repartiendo la novela en capitulos y abriendo su canon."
    if estado == "escribiendo":
        return f"Escritas {escritas} de {len(escenas)} escenas."
    if estado == "escrita":
        return f"Las {len(escenas)} escenas estan escritas."
    if estado == "detenida":
        detenidas = [e.escena_id for e in escenas if e.estado == EstadoDeTarea.ESCALADA.value]
        return (
            f"La escritura se detuvo e informa en lugar de reintentar sin fin: "
            f"{', '.join(detenidas)} agotaron su escalera de reintentos."
        )
    if estado == "fallida" and apertura is not None:
        falta = tuple(f for f in (apertura["falta"] or "").split("|") if f)
        return (
            "No se pudo abrir la novela. "
            + ("El rol dijo que le falta: " + "; ".join(falta) if falta else "")
        ).strip()
    return "Esta novela todavia no se ha encargado a nadie."
