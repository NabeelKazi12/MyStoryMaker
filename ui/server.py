"""Panel de control de MyStoryMaker.

Servidor local (FastAPI) que envuelve `scripts/` en una API HTTP y sirve una
pagina para gobernar el harness sin terminal: ver el progreso, lanzar N1/N2,
un capitulo o el ciclo completo como jobs en segundo plano con log en vivo, y
decidir en los cuatro puntos que SPECS.md reserva al autor -brief incompleto,
aprobacion de la escaleta, capitulo escalado tras tres iteraciones y
aprobacion del manuscrito final.

No sustituye a `scripts/consolidar.py` ni a los hooks: sigue siendo el unico
camino de escritura en `memory/`, esto solo lo pulsa por ti y te ensena el
resultado. El plan de N2 pendiente de aprobar se guarda en `ui/pendientes/`,
fuera de `memory/`, para que el hook `bloquear_memoria.py` no tenga que saber
que existe esta UI.

    python ui/server.py            arranca en http://127.0.0.1:8765
"""
from __future__ import annotations

import difflib
import json
import re
import subprocess
import sys
import threading
import time
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ / "scripts"))

import compilar as compilar_mod  # noqa: E402
import langfuse_cliente as lf  # noqa: E402
import pipeline  # noqa: E402
import resumen_langfuse  # noqa: E402
import validar_capitulos  # noqa: E402
from _comun import (BIBLE, CONFIG, ITERACIONES, LEDGER, MANUSCRITO, OUTLINE,  # noqa: E402
                    REVIEWS,
                    escribir_json_atomico, leer_json, parrafos_capitulo)

from fastapi import FastAPI, HTTPException  # noqa: E402
from fastapi.responses import Response  # noqa: E402
from fastapi.staticfiles import StaticFiles  # noqa: E402
from pydantic import BaseModel  # noqa: E402

ESTADO_UI = RAIZ / "ui" / "estado_ui.json"
ESTATICOS = Path(__file__).resolve().parent / "static"

app = FastAPI(title="MyStoryMaker - panel de control")


# --------------------------------------------------------------------------- jobs

class Job:
    """Un paso lanzado en segundo plano: preparar, un capitulo o continuar.

    `lineas` guarda toda la salida del paso segun se produce, para que la UI
    pueda pedir "lo que haya desde la linea N" y hacer polling barato en vez
    de reenviar el log entero cada vez.
    """

    def __init__(self, id_: str, kind: str, meta: dict):
        self.id = id_
        self.kind = kind
        self.meta = meta
        self.estado = "en_curso"
        self.error: str | None = None
        self.lineas: list[str] = []
        self.proceso = None
        self.cancelado = False
        self.creado = time.time()
        self.terminado: float | None = None
        self.fase: dict = {"nodo": None, "capitulo": meta.get("n"), "iteracion": None,
                            "ultimo": None}
        self._lock = threading.Lock()

    def linea(self, texto: str) -> None:
        with self._lock:
            self.lineas.append(texto)
            self._actualizar_fase(texto)

    # El orquestador tiene orden de decir en una linea donde esta tras cada paso
    # -nodo, capitulo, iteracion-, y esa linea es la unica senal de progreso que
    # produce una sesion headless. Leerla aqui convierte un log que hay que mirar
    # en un estado que la pagina puede dibujar.
    _NODO = re.compile(r"\bN([0-5])\b")
    _ITER = re.compile(r"iteraci[oó]n\s*:?\s*(\d+)", re.IGNORECASE)
    _CAP = re.compile(r"cap(?:itulo|ítulo)?\.?\s*0*(\d+)", re.IGNORECASE)

    def _actualizar_fase(self, texto: str) -> None:
        # Las lineas del lanzador (">>> N3, N4 y D1 - capitulo 03") son el rotulo
        # del paso, no su progreso: anunciarlas como fase daria por empezado lo
        # que aun no ha empezado.
        if texto.startswith(">>>") or texto.startswith("    "):
            return
        nodo = self._NODO.search(texto)
        if nodo:
            self.fase["nodo"] = f"N{nodo.group(1)}"
        elif "D1" in texto:
            self.fase["nodo"] = "D1"
        iteracion = self._ITER.search(texto)
        if iteracion:
            self.fase["iteracion"] = int(iteracion.group(1))
        capitulo = self._CAP.search(texto)
        if capitulo:
            self.fase["capitulo"] = int(capitulo.group(1))
        # Por raiz y no por palabra entera: el orquestador escribe «rechaza»,
        # «rechazado» y «ha rechazado» segun le cae la frase, y buscar la forma
        # exacta dejaba el rotulo clavado en el evento anterior.
        bajo = texto.lower()
        for raiz, etiqueta in (("consolidad", "consolidado"), ("escalad", "escalado"),
                                ("rechaz", "rechazado"), ("aprob", "aprobado"),
                                ("reparaci", "reparación")):
            if raiz in bajo:
                self.fase["ultimo"] = etiqueta
                break

    def registrar_proceso(self, proceso) -> None:
        with self._lock:
            self.proceso = proceso
            if self.cancelado:
                proceso.kill()

    def pedir_cancelacion(self) -> None:
        with self._lock:
            self.cancelado = True
            if self.proceso is not None and self.proceso.poll() is None:
                self.proceso.kill()

    def snapshot(self, desde: int = 0) -> dict:
        with self._lock:
            return {
                "id": self.id, "kind": self.kind, "meta": self.meta,
                "estado": self.estado, "error": self.error,
                "lineas": list(self.lineas[desde:]), "total": len(self.lineas),
                "creado": self.creado, "terminado": self.terminado,
                "fase": dict(self.fase),
            }


JOBS: dict[str, Job] = {}
JOBS_LOCK = threading.Lock()
CLASES_ACTIVAS = {"preparar", "capitulo", "continuar", "nuevo_capitulo"}


def job_activo() -> Job | None:
    with JOBS_LOCK:
        for job in JOBS.values():
            if job.kind in CLASES_ACTIVAS and job.estado == "en_curso":
                return job
    return None


def lanzar_job(kind: str, meta: dict, tarea) -> Job:
    job = Job(uuid.uuid4().hex[:8], kind, meta)
    with JOBS_LOCK:
        JOBS[job.id] = job

    def correr() -> None:
        try:
            tarea(job)
            with job._lock:
                if job.estado == "en_curso":
                    job.estado = "ok"
        except pipeline.PasoFallido as exc:
            with job._lock:
                job.estado = "cancelado" if job.cancelado else "error"
                job.error = str(exc)
        except Exception as exc:  # el job no debe tirar el servidor
            with job._lock:
                job.estado = "error"
                job.error = f"error inesperado: {exc}"
        finally:
            job.terminado = time.time()

    threading.Thread(target=correr, daemon=True).start()
    return job


def exigir_libre() -> None:
    activo = job_activo()
    if activo:
        raise HTTPException(
            409, f"Ya hay un paso en curso ({activo.kind}, job {activo.id}). "
                 "Espera a que termine o cancelalo antes de lanzar otro."
        )


def ejecutar_consolidar(*args: str) -> tuple[bool, str]:
    proceso = subprocess.run(
        [sys.executable, str(RAIZ / "scripts" / "consolidar.py"), *args],
        cwd=str(RAIZ), capture_output=True, text=True, encoding="utf-8", errors="replace",
    )
    salida = ((proceso.stdout or "") + (proceso.stderr or "")).strip()
    return proceso.returncode == 0, salida


# --------------------------------------------------------------------------- estado ui

def leer_estado_ui() -> dict:
    if not ESTADO_UI.exists():
        return {}
    try:
        return json.loads(ESTADO_UI.read_text(encoding="utf-8"))
    except Exception:
        return {}


def escribir_estado_ui(datos: dict) -> None:
    ESTADO_UI.parent.mkdir(parents=True, exist_ok=True)
    ESTADO_UI.write_text(json.dumps(datos, ensure_ascii=False, indent=2), encoding="utf-8")


# --------------------------------------------------------------------------- lectura del brief

CAMPOS_BRIEF = [
    "Premisa", "Tono", "Persona y tiempo narrativos",
    "Extensión objetivo", "Arco deseado", "Vetos",
]


def parsear_brief() -> dict:
    ruta = RAIZ / "brief.md"
    if not ruta.exists():
        return {"existe": False, "completo": False, "faltantes": CAMPOS_BRIEF, "secciones": {}}
    texto = ruta.read_text(encoding="utf-8")
    secciones: dict[str, str] = {}
    for match in re.finditer(r"^##\s+(.+?)\s*$\n(.*?)(?=^##\s|\Z)", texto, re.M | re.S):
        nombre = match.group(1).strip()
        cuerpo = re.sub(r"^-{3,}\s*$", "", match.group(2).strip(), flags=re.M).strip()
        if cuerpo:
            secciones[nombre] = cuerpo
    faltantes = [c for c in CAMPOS_BRIEF if not secciones.get(c)]
    return {"existe": True, "completo": not faltantes, "faltantes": faltantes, "secciones": secciones}


# --------------------------------------------------------------------------- estado agregado

def construir_capitulos() -> list[dict]:
    outline = leer_json(OUTLINE) if OUTLINE.exists() else {"capitulos": []}
    config = leer_json(CONFIG) if CONFIG.exists() else {"capitulos": []}
    vivos = {c["n"]: c for c in outline.get("capitulos", [])}
    fijados = {c["n"]: c for c in config.get("capitulos", [])}
    resultado = []
    for n in sorted(set(vivos) | set(fijados)):
        cap = vivos.get(n, {})
        fijado = fijados.get(n, {})
        review_path = REVIEWS / f"cap-{n:02d}.json"
        review = leer_json(review_path) if review_path.exists() else None
        resultado.append({
            "n": n,
            "titulo": cap.get("titulo") or fijado.get("titulo") or "",
            "estado": cap.get("estado", "pendiente") if cap else "sin_escaleta",
            "iteraciones": cap.get("iteraciones", 0),
            "lineas_objetivo": cap.get("lineas_objetivo") or fijado.get("lineas_objetivo"),
            "contiene_combate": cap.get("contiene_combate", fijado.get("contiene_combate", False)),
            "media": (review or {}).get("media"),
            "manuscrito_existe": (MANUSCRITO / f"cap-{n:02d}.md").exists(),
            # Un capitulo recien anadido esta en la escaleta pero sin ficha: la UI
            # tiene que poder distinguirlo de uno pendiente de verdad.
            "ficha_completa": bool(cap) and all(
                str(cap.get(k) or "").strip() for k in ("objetivo", "conflicto", "salida")),
        })
    return resultado


def construir_ledger() -> dict:
    if not LEDGER.exists():
        return {"record": None, "hilos_abiertos": []}
    ledger = leer_json(LEDGER)
    return {"record": ledger.get("record"), "hilos_abiertos": ledger.get("hilos_abiertos", [])}


def construir_langfuse() -> dict:
    try:
        activo = lf.config() is not None
    except Exception:
        activo = False
    return {"configurado": activo}


@app.get("/api/estado")
def api_estado() -> dict:
    config = leer_json(CONFIG) if CONFIG.exists() else {}
    outline = leer_json(OUTLINE) if OUTLINE.exists() else {}
    job = job_activo()
    return {
        "titulo": config.get("titulo_trabajo", ""),
        "config_version": config.get("version"),
        "brief": parsear_brief(),
        "investigacion": pipeline.hay_investigacion(),
        "escaleta": {
            "sembrada": pipeline.escaleta_sembrada(),
            "pendiente_aprobacion": pipeline.escaleta_pendiente_de_aprobacion(),
            "desincronizada": bool(outline.get("capitulos"))
            and outline.get("config_version") != config.get("version"),
        },
        "capitulos": construir_capitulos(),
        "ledger": construir_ledger(),
        "manuscrito": {
            "compilado": (RAIZ / "dist" / "manuscrito.md").exists(),
            "aprobado": bool(leer_estado_ui().get("manuscrito_aprobado")),
            "aprobado_en": leer_estado_ui().get("manuscrito_aprobado_en"),
            "motivo_rechazo": leer_estado_ui().get("manuscrito_motivo_rechazo"),
        },
        "langfuse": construir_langfuse(),
        "job_activo": None if job is None else {"id": job.id, "kind": job.kind,
                                                 "meta": job.meta, "fase": dict(job.fase)},
    }


# --------------------------------------------------------------------------- escaleta (N1/N2)

@app.get("/api/escaleta/pendiente")
def api_escaleta_pendiente() -> dict:
    if not pipeline.escaleta_pendiente_de_aprobacion():
        return {"pendiente": False}
    return {
        "pendiente": True,
        "bible": leer_json(pipeline.BIBLE_PENDIENTE),
        "outline": leer_json(pipeline.OUTLINE_PENDIENTE),
    }


@app.post("/api/escaleta/preparar")
def api_escaleta_preparar() -> dict:
    if pipeline.escaleta_sembrada():
        raise HTTPException(400, "La escaleta ya esta sembrada; no hace falta volver a N2.")
    if pipeline.escaleta_pendiente_de_aprobacion():
        raise HTTPException(400, "Ya hay un plan pendiente de aprobacion en ui/pendientes/.")
    exigir_libre()

    def tarea(job: Job) -> None:
        pipeline.paso_preparar_ui(on_linea=job.linea, registrar_proceso=job.registrar_proceso)

    job = lanzar_job("preparar", {}, tarea)
    return {"job_id": job.id}


class RechazoEscaletaBody(BaseModel):
    motivo: str


@app.post("/api/escaleta/rechazar")
def api_escaleta_rechazar(body: RechazoEscaletaBody) -> dict:
    if not pipeline.escaleta_pendiente_de_aprobacion():
        raise HTTPException(400, "No hay ningun plan pendiente de aprobacion.")
    exigir_libre()

    def tarea(job: Job) -> None:
        pipeline.paso_preparar_ui(body.motivo, on_linea=job.linea,
                                   registrar_proceso=job.registrar_proceso)

    job = lanzar_job("preparar", {"reintento": True, "motivo": body.motivo}, tarea)
    return {"job_id": job.id}


@app.post("/api/escaleta/aprobar")
def api_escaleta_aprobar() -> dict:
    if not pipeline.escaleta_pendiente_de_aprobacion():
        raise HTTPException(400, "No hay ningun plan pendiente de aprobacion.")
    ok, salida = ejecutar_consolidar("sembrar-bible", str(pipeline.BIBLE_PENDIENTE))
    if not ok:
        raise HTTPException(400, f"consolidar.py sembrar-bible ha fallado:\n{salida}")
    ok, salida2 = ejecutar_consolidar("sembrar-outline", str(pipeline.OUTLINE_PENDIENTE))
    if not ok:
        raise HTTPException(
            400, f"La biblia ya quedo sembrada, pero sembrar-outline ha fallado:\n{salida2}"
        )
    pipeline.BIBLE_PENDIENTE.unlink(missing_ok=True)
    pipeline.OUTLINE_PENDIENTE.unlink(missing_ok=True)
    return {"ok": True, "salida": f"{salida}\n{salida2}".strip()}


# --------------------------------------------------------------------------- capitulos

@app.get("/api/capitulos/{n}")
def api_capitulo_detalle(n: int) -> dict:
    outline = leer_json(OUTLINE) if OUTLINE.exists() else {}
    cap = next((c for c in outline.get("capitulos", []) if c["n"] == n), None)
    if cap is None:
        raise HTTPException(404, f"El capitulo {n} no esta en la escaleta.")
    texto_path = MANUSCRITO / f"cap-{n:02d}.md"
    review_path = REVIEWS / f"cap-{n:02d}.json"
    return {
        "ficha": cap,
        "texto": texto_path.read_text(encoding="utf-8") if texto_path.exists() else None,
        "review": leer_json(review_path) if review_path.exists() else None,
        "versiones": versiones_de(n),
    }


def versiones_de(n: int) -> list[dict]:
    """Las versiones archivadas de un capitulo, de la mas antigua a la mas nueva.

    Las apila el hook `validar_extension.py` segun se escriben, rechazadas
    incluidas. Si el directorio no existe es que el capitulo se produjo antes de
    que el harness archivara nada, y eso hay que decirlo en vez de fingir que no
    hubo iteraciones.
    """
    carpeta = ITERACIONES / f"cap-{n:02d}"
    if not carpeta.is_dir():
        return []
    versiones = []
    for ruta in sorted(carpeta.iterdir()):
        partes = ruta.stem.split("-", 1)
        if len(partes) != 2:
            continue
        marca, tipo = partes
        versiones.append({
            "id": ruta.name, "marca": marca, "tipo": tipo,
            "cuando": datetime.strptime(marca, "%Y%m%dT%H%M%S")
                              .replace(tzinfo=timezone.utc).isoformat(),
            "bytes": ruta.stat().st_size,
        })
    return versiones


def ruta_version(n: int, id_: str) -> Path:
    carpeta = (ITERACIONES / f"cap-{n:02d}").resolve()
    ruta = (carpeta / id_).resolve()
    # El id llega del navegador: sin esta comprobacion, un '../..' leeria
    # cualquier fichero de la maquina a traves de la API.
    if not str(ruta).startswith(str(carpeta)) or not ruta.is_file():
        raise HTTPException(404, "Esa version no existe.")
    return ruta


@app.get("/api/capitulos/{n}/versiones")
def api_capitulo_versiones(n: int) -> dict:
    return {"versiones": versiones_de(n)}


@app.get("/api/capitulos/{n}/version/{id_}")
def api_capitulo_version(n: int, id_: str) -> dict:
    return {"id": id_, "contenido": ruta_version(n, id_).read_text(encoding="utf-8")}


@app.get("/api/capitulos/{n}/diff")
def api_capitulo_diff(n: int, a: str, b: str) -> dict:
    """Diff por lineas entre dos versiones archivadas del mismo capitulo.

    Se calcula aqui y no en el navegador para no arrastrar una libreria de diff
    al front por algo que la biblioteca estandar ya hace bien.
    """
    texto_a = ruta_version(n, a).read_text(encoding="utf-8").splitlines()
    texto_b = ruta_version(n, b).read_text(encoding="utf-8").splitlines()
    filas = []
    for linea in difflib.unified_diff(texto_a, texto_b, lineterm="", n=3):
        if linea.startswith("+++") or linea.startswith("---"):
            continue
        clase = ("cabecera" if linea.startswith("@@")
                 else "mas" if linea.startswith("+")
                 else "menos" if linea.startswith("-") else "igual")
        filas.append({"clase": clase, "texto": linea})
    iguales = texto_a == texto_b
    return {"a": a, "b": b, "iguales": iguales, "filas": filas}


@app.post("/api/capitulos/{n}/lanzar")
def api_capitulo_lanzar(n: int) -> dict:
    if not pipeline.escaleta_sembrada():
        raise HTTPException(400, "La escaleta no esta sembrada todavia.")
    exigir_libre()

    def tarea(job: Job) -> None:
        pipeline.paso_capitulo(n, on_linea=job.linea, registrar_proceso=job.registrar_proceso)

    job = lanzar_job("capitulo", {"n": n}, tarea)
    return {"job_id": job.id}


class ReescrituraBody(BaseModel):
    indicaciones: str


@app.post("/api/capitulos/{n}/reescribir")
def api_capitulo_reescribir(n: int, body: ReescrituraBody) -> dict:
    outline = leer_json(OUTLINE) if OUTLINE.exists() else {}
    cap = next((c for c in outline.get("capitulos", []) if c["n"] == n), None)
    if cap is None:
        raise HTTPException(404, f"El capitulo {n} no esta en la escaleta.")
    if cap.get("estado") != "escalado":
        raise HTTPException(400, f"El cap {n} no esta escalado (estado actual: {cap.get('estado')}).")
    exigir_libre()

    ok, salida = ejecutar_consolidar("marcar", str(n), "pendiente", "--iteraciones", "0")
    if not ok:
        raise HTTPException(400, f"No se ha podido reiniciar el capitulo escalado:\n{salida}")

    def tarea(job: Job) -> None:
        pipeline.paso_capitulo(n, indicaciones=body.indicaciones, on_linea=job.linea,
                                registrar_proceso=job.registrar_proceso)

    job = lanzar_job("capitulo", {"n": n, "reescritura": True}, tarea)
    return {"job_id": job.id}


@app.post("/api/continuar")
def api_continuar() -> dict:
    if not pipeline.escaleta_sembrada():
        raise HTTPException(400, "Prepara y aprueba la escaleta antes de continuar.")
    if pipeline.escaleta_pendiente_de_aprobacion():
        raise HTTPException(400, "Hay un plan de escaleta pendiente de aprobacion.")
    exigir_libre()

    def tarea(job: Job) -> None:
        outline = leer_json(OUTLINE)
        for cap in sorted(outline.get("capitulos", []), key=lambda c: c["n"]):
            pipeline.paso_capitulo(cap["n"], on_linea=job.linea,
                                    registrar_proceso=job.registrar_proceso)

    job = lanzar_job("continuar", {}, tarea)
    return {"job_id": job.id}


class NuevoCapituloBody(BaseModel):
    """La forma del capitulo nuevo. Todo viene del autor: el sistema no la inventa."""
    lineas_objetivo: int
    parrafos_objetivo: int | None = None
    lineas_por_parrafo: int | None = None
    contiene_combate: bool = False
    acto: int = 1
    producir: bool = False


@app.post("/api/capitulos/nuevo")
def api_capitulo_nuevo(body: NuevoCapituloBody) -> dict:
    """Anade un capitulo al plan y lo deja listo para producir.

    `config/capitulos.json` es del autor (INV-03) y un hook deniega que ningun
    agente lo edite. Esta ruta no rompe eso: la UI *es* la mano del autor, y por
    eso la forma del capitulo -cuantas lineas, en cuantos parrafos, si lleva
    combate- llega entera desde el formulario y aqui no se rellena ningun hueco
    con un valor por defecto inventado.

    Son tres pasos encadenados porque separarlos deja el plan a medias: se
    escribe el plan, se reproyecta sobre la escaleta viva (RM-01 mete el
    capitulo como pendiente con la ficha en blanco) y se lanza N2 para esa ficha.
    """
    if not pipeline.escaleta_sembrada():
        raise HTTPException(400, "La escaleta no esta sembrada: prepara N1 y N2 antes de anadir "
                                 "capitulos sueltos.")
    if pipeline.escaleta_pendiente_de_aprobacion():
        raise HTTPException(400, "Hay un plan de escaleta pendiente de aprobacion; resuelvelo antes.")
    if body.lineas_objetivo < 1:
        raise HTTPException(400, "lineas_objetivo tiene que ser al menos 1.")
    if bool(body.parrafos_objetivo) != bool(body.lineas_por_parrafo):
        raise HTTPException(400, "El reparto en parrafos se declara entero o no se declara: "
                                 "parrafos_objetivo y lineas_por_parrafo van juntos.")
    if body.parrafos_objetivo and body.parrafos_objetivo * body.lineas_por_parrafo != body.lineas_objetivo:
        raise HTTPException(
            400, f"El reparto no cuadra: {body.parrafos_objetivo} x {body.lineas_por_parrafo} = "
                 f"{body.parrafos_objetivo * body.lineas_por_parrafo}, y has pedido "
                 f"{body.lineas_objetivo} lineas."
        )
    exigir_libre()

    config = leer_json(CONFIG)
    if config.get("extension", {}).get("unidad") != "lineas":
        raise HTTPException(400, "Esta pantalla solo sabe anadir capitulos en la unidad 'lineas'. "
                                 "Edita config/capitulos.json a mano para otras unidades.")
    n = max((c["n"] for c in config["capitulos"]), default=0) + 1
    nuevo = {
        "n": n, "acto": body.acto, "lineas_objetivo": body.lineas_objetivo,
        "contiene_combate": body.contiene_combate,
    }
    if body.parrafos_objetivo:
        nuevo["parrafos_objetivo"] = body.parrafos_objetivo
        nuevo["lineas_por_parrafo"] = body.lineas_por_parrafo

    propuesta = json.loads(json.dumps(config))          # no tocar el plan vigente si no valida
    propuesta["capitulos"].append(nuevo)
    propuesta["extension"]["lineas_totales_objetivo"] = sum(
        c["lineas_objetivo"] for c in propuesta["capitulos"])
    propuesta["version"] = int(propuesta.get("version", 0)) + 1

    errores = validar_capitulos.validar(propuesta)
    if errores:
        raise HTTPException(400, "El plan resultante no valida (RM-03):\n" + "\n".join(errores))
    escribir_json_atomico(CONFIG, propuesta)

    ok, salida = ejecutar_consolidar("sincronizar")
    if not ok:
        raise HTTPException(500, f"El capitulo {n} se anadio al plan pero 'sincronizar' ha "
                                 f"fallado; la escaleta se ha quedado atras:\n{salida}")

    def tarea(job: Job) -> None:
        pipeline.paso_ficha(n, on_linea=job.linea, registrar_proceso=job.registrar_proceso)
        if body.producir:
            pipeline.paso_capitulo(n, on_linea=job.linea, registrar_proceso=job.registrar_proceso)

    job = lanzar_job("nuevo_capitulo", {"n": n, "producir": body.producir}, tarea)
    return {"job_id": job.id, "n": n, "config_version": propuesta["version"], "sincronizar": salida}


@app.post("/api/capitulos/{n}/ficha")
def api_capitulo_ficha(n: int) -> dict:
    """Relanza N2 para una ficha que quedo en blanco (o cuyo paso fallo a medias)."""
    if not pipeline.ficha_incompleta(n):
        raise HTTPException(400, f"La ficha del cap {n} ya esta rellena.")
    exigir_libre()

    def tarea(job: Job) -> None:
        pipeline.paso_ficha(n, on_linea=job.linea, registrar_proceso=job.registrar_proceso)

    job = lanzar_job("nuevo_capitulo", {"n": n, "solo_ficha": True}, tarea)
    return {"job_id": job.id}


# --------------------------------------------------------------------------- lectura

def partir_capitulo(texto: str) -> dict:
    """Separa el titulo del cuerpo y el cuerpo en parrafos, para leerlo como un libro.

    Se hace aqui y no en el navegador porque el formato de un capitulo ya esta
    definido en `_comun.parrafos_capitulo`, que es lo que el hook cuenta al
    guardar: si la lectura partiera los parrafos por su cuenta, la pagina podria
    ensenar una forma distinta de la que el sistema valida.
    """
    titulo = ""
    for linea in texto.splitlines():
        if linea.strip().startswith("#"):
            titulo = linea.strip().lstrip("#").strip()
            break
    # Los capitulos se titulan «3. Jueves, de nueve a diez»: el numero va aparte
    # en la pagina, asi que aqui sobra y duplicado queda feo en la portadilla.
    titulo = re.sub(r"^\d+\s*[.—-]\s*", "", titulo)
    return {"titulo": titulo, "parrafos": parrafos_capitulo(texto)}


@app.get("/api/lectura")
def api_lectura() -> dict:
    """La novela tal como va, para leerla seguida.

    Se sirve desde `manuscript/` y no desde `dist/manuscrito.md` a proposito: el
    manuscrito compilado solo existe cuando N5 cierra, y leer lo que hay es util
    mucho antes de eso. Solo entran los capitulos consolidados, porque un
    capitulo en revision o escalado todavia no es texto de la novela.
    """
    config = leer_json(CONFIG) if CONFIG.exists() else {}
    outline = leer_json(OUTLINE) if OUTLINE.exists() else {"capitulos": []}
    bible = leer_json(BIBLE) if BIBLE.exists() else {}

    capitulos, pendientes = [], []
    for cap in sorted(outline.get("capitulos", []), key=lambda c: c["n"]):
        n = cap["n"]
        ruta = MANUSCRITO / f"cap-{n:02d}.md"
        if cap.get("estado") != "consolidado" or not ruta.exists():
            pendientes.append({"n": n, "titulo": cap.get("titulo", ""),
                               "estado": cap.get("estado", "pendiente")})
            continue
        datos = partir_capitulo(ruta.read_text(encoding="utf-8"))
        capitulos.append({"n": n, "titulo": datos["titulo"] or cap.get("titulo", ""),
                          "parrafos": datos["parrafos"]})

    return {
        "titulo": config.get("titulo_trabajo", "") or bible.get("titulo_trabajo", ""),
        "capitulos": capitulos,
        "pendientes": pendientes,
        "lineas": sum(len(p) for c in capitulos for p in c["parrafos"]),
        "compilado": (RAIZ / "dist" / "manuscrito.md").exists(),
    }


@app.post("/api/sincronizar")
def api_sincronizar() -> dict:
    ok, salida = ejecutar_consolidar("sincronizar")
    if not ok:
        raise HTTPException(400, salida)
    return {"ok": True, "salida": salida}


# --------------------------------------------------------------------------- manuscrito (N5)

@app.get("/api/manuscrito")
def api_manuscrito() -> dict:
    ruta = RAIZ / "dist" / "manuscrito.md"
    estado_ui = leer_estado_ui()
    return {
        "compilado": ruta.exists(),
        "contenido": ruta.read_text(encoding="utf-8") if ruta.exists() else None,
        "aprobado": bool(estado_ui.get("manuscrito_aprobado")),
        "aprobado_en": estado_ui.get("manuscrito_aprobado_en"),
        "motivo_rechazo": estado_ui.get("manuscrito_motivo_rechazo"),
    }


@app.post("/api/manuscrito/compilar")
def api_manuscrito_compilar() -> dict:
    problemas, avisos, contexto = compilar_mod.verificar()
    if problemas:
        return {"ok": False, "problemas": problemas, "avisos": avisos}
    destino = compilar_mod.compilar(contexto)
    estado_ui = leer_estado_ui()
    estado_ui["manuscrito_aprobado"] = False
    estado_ui.pop("manuscrito_motivo_rechazo", None)
    escribir_estado_ui(estado_ui)
    return {
        "ok": True, "avisos": avisos,
        "ruta": str(destino.relative_to(RAIZ)).replace("\\", "/"),
        "total": contexto["total"], "unidad": contexto["unidad"],
        "capitulos": len(contexto["textos"]),
    }


@app.post("/api/manuscrito/aprobar")
def api_manuscrito_aprobar() -> dict:
    if not (RAIZ / "dist" / "manuscrito.md").exists():
        raise HTTPException(400, "Todavia no hay manuscrito compilado.")
    estado_ui = leer_estado_ui()
    estado_ui["manuscrito_aprobado"] = True
    estado_ui["manuscrito_aprobado_en"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
    estado_ui.pop("manuscrito_motivo_rechazo", None)
    escribir_estado_ui(estado_ui)
    return {"ok": True}


class RechazoManuscritoBody(BaseModel):
    motivo: str = ""


@app.post("/api/manuscrito/rechazar")
def api_manuscrito_rechazar(body: RechazoManuscritoBody) -> dict:
    estado_ui = leer_estado_ui()
    estado_ui["manuscrito_aprobado"] = False
    estado_ui["manuscrito_motivo_rechazo"] = body.motivo
    escribir_estado_ui(estado_ui)
    return {"ok": True}


# --------------------------------------------------------------------------- coste (langfuse)

@app.get("/api/coste")
def api_coste(horas: float = 24.0) -> dict:
    cfg = lf.config()
    if cfg is None:
        return {"disponible": False, "motivo": "Langfuse no esta configurado (falta .env)."}
    ahora = datetime.now(timezone.utc)
    desde = (ahora - timedelta(hours=horas)).isoformat().replace("+00:00", "Z")
    hasta = (ahora + timedelta(minutes=5)).isoformat().replace("+00:00", "Z")
    metricas = [{"measure": "totalTokens", "aggregation": "sum"},
                {"measure": "totalCost", "aggregation": "sum"},
                {"measure": "count", "aggregation": "count"}]
    try:
        filas = resumen_langfuse.consultar(cfg, "observations", ["name"], metricas, desde, hasta)
    except Exception as exc:
        return {"disponible": False, "motivo": f"No se ha podido consultar Langfuse: {exc}"}

    agentes = [f for f in filas if f.get("name") in resumen_langfuse.AGENTES]

    def num(fila: dict, clave: str) -> float:
        valor = fila.get(clave)
        return float(valor) if valor not in (None, "") else 0.0

    filas_out = [{
        "nodo": resumen_langfuse.AGENTES[f["name"]], "agente": f["name"],
        "llamadas": num(f, "count_count"), "tokens": num(f, "sum_totalTokens"),
        "coste": num(f, "sum_totalCost"),
    } for f in sorted(agentes, key=lambda f: resumen_langfuse.AGENTES[f["name"]])]
    return {"disponible": True, "horas": horas, "filas": filas_out}


# --------------------------------------------------------------------------- jobs

@app.get("/api/jobs")
def api_jobs() -> list[dict]:
    with JOBS_LOCK:
        items = sorted(JOBS.values(), key=lambda j: j.creado, reverse=True)[:20]
    return [{"id": j.id, "kind": j.kind, "meta": j.meta, "estado": j.estado,
              "error": j.error, "creado": j.creado, "terminado": j.terminado} for j in items]


@app.get("/api/jobs/{job_id}")
def api_job_detalle(job_id: str, desde: int = 0) -> dict:
    job = JOBS.get(job_id)
    if job is None:
        raise HTTPException(404, "job no encontrado (el servidor se ha reiniciado desde entonces).")
    return job.snapshot(desde)


@app.post("/api/jobs/{job_id}/cancelar")
def api_job_cancelar(job_id: str) -> dict:
    job = JOBS.get(job_id)
    if job is None:
        raise HTTPException(404, "job no encontrado.")
    if job.estado != "en_curso":
        raise HTTPException(400, "el job ya ha terminado.")
    job.pedir_cancelacion()
    return {"ok": True}


# --------------------------------------------------------------------------- estaticos

class EstaticosRevalidados(StaticFiles):
    """Sirve los estaticos obligando a revalidar en cada carga.

    `StaticFiles` manda `etag` y `last-modified` pero ningun `Cache-Control`, y
    sin esa cabecera el navegador aplica **caché heurística**: se queda el
    fichero durante un rato -tipicamente un 10% del tiempo transcurrido desde su
    ultima modificacion- y lo sirve sin preguntar al servidor. En una pagina que
    se edita mientras se usa eso produce un fallo desconcertante: el `index.html`
    llega nuevo y el `app.js` llega viejo, asi que la pagina queda a medias -un
    boton sin su manejador, la logica antigua de pintado- sin un solo error en
    consola que lo delate.

    `no-cache` no significa «no guardes», significa «pregunta siempre antes de
    usarlo». Con el `etag` que ya se manda, esa pregunta se responde con un 304
    de unos pocos bytes: no cuesta nada y el navegador no puede quedarse atras.
    """

    async def get_response(self, path: str, scope):
        respuesta = await super().get_response(path, scope)
        respuesta.headers["Cache-Control"] = "no-cache, must-revalidate"
        return respuesta


app.mount("/static", EstaticosRevalidados(directory=str(ESTATICOS)), name="static")


def version_de(nombre: str) -> str:
    """Huella del fichero, para colgarla de su URL."""
    try:
        return str(int((ESTATICOS / nombre).stat().st_mtime))
    except OSError:
        return "0"


@app.get("/")
def index() -> Response:
    """La pagina, con los estaticos versionados por su fecha de modificacion.

    El `no-cache` de arriba ya basta con un navegador que se porte bien, pero el
    sufijo `?v=` hace que un `app.js` editado sea *otra URL*: ni un proxy ni una
    cache agresiva pueden servir el anterior. Cinturon y tirantes, porque el
    modo de fallo de servir medio front viejo cuesta mucho de diagnosticar.
    """
    html = (ESTATICOS / "index.html").read_text(encoding="utf-8")
    for nombre in ("app.js", "style.css"):
        html = html.replace(f"/static/{nombre}", f"/static/{nombre}?v={version_de(nombre)}")
    return Response(html, media_type="text/html; charset=utf-8",
                    headers={"Cache-Control": "no-store"})


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8765)
