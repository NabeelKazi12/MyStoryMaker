"""Cliente de Langfuse por OTLP, sin dependencias externas.

El harness no puede permitirse que la observabilidad lo rompa: los hooks corren
en el entorno del autor y un `pip install` fallido convertiria un guardian en un
fallo silencioso. Por eso aqui no hay SDK, solo urllib y el endpoint OpenTelemetry
de Langfuse, que es el que sobrevive al apagado de la API v3 (16-nov-2026).

Dos decisiones cargan con todo el peso:

1. Los identificadores son deterministas. Cada hook es un proceso distinto y no
   hay memoria compartida entre ellos. El id de traza sale de hashear el
   session_id y el de cada span de hashear una clave estable, asi que un hook que
   arranca en frio sabe colgar su span del tronco correcto sin preguntarle a nadie.

2. Nada se envia en caliente. Los spans se encolan en `logs/langfuse-cola.jsonl` y
   se vacian por lotes al terminar un subagente o la sesion. Una red lenta retrasa
   la traza, nunca el trabajo.

Ninguna funcion de este modulo lanza excepciones hacia fuera. Si Langfuse no esta
configurado, todo son operaciones nulas y el harness funciona igual que antes.
"""
from __future__ import annotations

import base64
import hashlib
import json
import os
import time
import urllib.error
import urllib.request
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
LOGS = RAIZ / "logs"
COLA = LOGS / "langfuse-cola.jsonl"
SESION = LOGS / ".langfuse-sesion.json"
PROYECTO = LOGS / ".langfuse-proyecto.json"
ESTADO = LOGS / ".langfuse-estado.json"

SERVICIO = "mystorymaker"
MAX_INTENTOS = 5          # lotes que se reintentan antes de tirar la traza
UMBRAL_VACIADO = 20       # spans encolados que disparan un envio sin esperar al final
LIMITE_TEXTO = 2000       # recorte de entradas y salidas; una traza no es un backup
TIMEOUT = 8


# --------------------------------------------------------------- configuracion

def _cargar_env() -> None:
    """Lee `.env` de la raiz sin pisar lo que ya venga del entorno."""
    ruta = RAIZ / ".env"
    try:
        if not ruta.exists():
            return
        for linea in ruta.read_text(encoding="utf-8").splitlines():
            linea = linea.strip()
            if not linea or linea.startswith("#") or "=" not in linea:
                continue
            clave, _, valor = linea.partition("=")
            os.environ.setdefault(clave.strip(), valor.strip().strip('"').strip("'"))
    except OSError:
        return


def config() -> dict | None:
    """Devuelve la configuracion vigente, o None si falta alguna clave."""
    _cargar_env()
    pk = os.environ.get("LANGFUSE_PUBLIC_KEY", "").strip()
    sk = os.environ.get("LANGFUSE_SECRET_KEY", "").strip()
    if not pk or not sk:
        return None
    host = os.environ.get("LANGFUSE_HOST", "https://cloud.langfuse.com").strip().rstrip("/")
    return {
        "host": host,
        "pk": pk,
        "sk": sk,
        "entorno": os.environ.get("LANGFUSE_TRACING_ENVIRONMENT", "default").strip() or "default",
        "usuario": os.environ.get("LANGFUSE_USER_ID", "autor").strip() or "autor",
    }


def activo() -> bool:
    return config() is not None


def trazar_herramientas() -> bool:
    """El span por herramienta es lo unico opcional: es fiel pero ruidoso."""
    _cargar_env()
    return os.environ.get("LANGFUSE_TRAZAR_HERRAMIENTAS", "1").strip() not in ("0", "false", "no")


def _cabeceras(cfg: dict) -> dict:
    credencial = base64.b64encode(f"{cfg['pk']}:{cfg['sk']}".encode()).decode()
    return {"Authorization": "Basic " + credencial, "Content-Type": "application/json"}


# ------------------------------------------------------------ identificadores

def id_traza(session_id: str) -> str:
    """32 hex deterministas por sesion de Claude Code: una sesion, una traza."""
    return hashlib.sha1(f"{SERVICIO}:traza:{session_id}".encode()).hexdigest()[:32]


def id_span(session_id: str, clave: str) -> str:
    """16 hex deterministas. Misma clave en dos procesos, mismo span."""
    return hashlib.sha1(f"{SERVICIO}:span:{session_id}:{clave}".encode()).hexdigest()[:16]


def ahora_ns() -> int:
    return time.time_ns()


# --------------------------------------------------------------------- spans

def recortar(valor, limite: int = LIMITE_TEXTO) -> str:
    """Texto acotado. Una traza documenta lo que paso, no lo guarda entero."""
    try:
        texto = valor if isinstance(valor, str) else json.dumps(valor, ensure_ascii=False, default=str)
    except (TypeError, ValueError):
        texto = str(valor)
    if len(texto) > limite:
        return texto[:limite] + f"... [recortado, {len(texto)} caracteres]"
    return texto


def span(session_id: str, clave: str, nombre: str, inicio_ns: int, fin_ns: int,
         tipo: str = "span", padre: str | None = "raiz", atributos: dict | None = None) -> dict:
    """Construye un span listo para encolar.

    `padre` es la clave del span padre, no su id: quien llama piensa en el arbol
    del sistema ('raiz', 'subagente:escritor') y el hash hace el resto.
    """
    registro = {
        "traceId": id_traza(session_id),
        "spanId": id_span(session_id, clave),
        "name": nombre,
        "start": int(inicio_ns),
        "end": int(max(fin_ns, inicio_ns)),
        "attrs": {"langfuse.observation.type": tipo, **(atributos or {})},
    }
    if padre:
        registro["parentSpanId"] = id_span(session_id, padre)
    return registro


def atributos_traza(nombre: str, session_id: str, cfg: dict, etiquetas: list[str] | None = None,
                    metadatos: dict | None = None) -> dict:
    """Atributos que Langfuse promueve al nivel de traza. Van en el span raiz."""
    attrs = {
        "langfuse.trace.name": nombre,
        "langfuse.session.id": session_id,
        "langfuse.user.id": cfg["usuario"],
        "langfuse.environment": cfg["entorno"],
    }
    if etiquetas:
        attrs["langfuse.trace.tags"] = json.dumps(etiquetas, ensure_ascii=False)
    for clave, valor in (metadatos or {}).items():
        if valor is not None:
            attrs[f"langfuse.trace.metadata.{clave}"] = valor
    return attrs


# --------------------------------------------------------------------- envio

def _valor_otlp(valor):
    if isinstance(valor, bool):
        return {"boolValue": valor}
    if isinstance(valor, int):
        return {"intValue": str(valor)}
    if isinstance(valor, float):
        return {"doubleValue": valor}
    return {"stringValue": str(valor)}


def _payload(spans: list[dict], cfg: dict) -> dict:
    return {"resourceSpans": [{
        "resource": {"attributes": [
            {"key": "service.name", "value": {"stringValue": SERVICIO}},
            {"key": "deployment.environment.name", "value": {"stringValue": cfg["entorno"]}},
        ]},
        "scopeSpans": [{
            "scope": {"name": "mystorymaker.harness"},
            "spans": [{
                "traceId": s["traceId"],
                "spanId": s["spanId"],
                **({"parentSpanId": s["parentSpanId"]} if s.get("parentSpanId") else {}),
                "name": s["name"],
                "kind": 1,
                "startTimeUnixNano": str(s["start"]),
                "endTimeUnixNano": str(s["end"]),
                "attributes": [{"key": k, "value": _valor_otlp(v)}
                               for k, v in (s.get("attrs") or {}).items() if v is not None],
            } for s in spans],
        }],
    }]}


def _post(ruta: str, cuerpo: dict, cfg: dict) -> bool:
    peticion = urllib.request.Request(cfg["host"] + ruta, data=json.dumps(cuerpo).encode("utf-8"),
                                      headers=_cabeceras(cfg), method="POST")
    try:
        with urllib.request.urlopen(peticion, timeout=TIMEOUT) as respuesta:
            return 200 <= respuesta.status < 300
    except urllib.error.HTTPError as error:
        # Un 4xx que no sea 429 es culpa del payload: reintentarlo no lo arregla,
        # asi que se da por consumido y el span se descarta en vez de atascar la cola.
        return 400 <= error.code < 500 and error.code != 429
    except Exception:
        return False


# ---------------------------------------------------------------------- cola

def encolar(spans: list[dict], vaciar_ahora: bool = False) -> None:
    """Deja los spans en la cola y decide si toca enviar."""
    if not spans or not activo():
        return
    try:
        LOGS.mkdir(parents=True, exist_ok=True)
        with open(COLA, "a", encoding="utf-8", newline="\n") as fh:
            for s in spans:
                fh.write(json.dumps(s, ensure_ascii=False) + "\n")
        if vaciar_ahora or _pendientes() >= UMBRAL_VACIADO:
            vaciar()
    except Exception:
        return


def _pendientes() -> int:
    try:
        with open(COLA, encoding="utf-8") as fh:
            return sum(1 for linea in fh if linea.strip())
    except OSError:
        return 0


def vaciar() -> int:
    """Envia la cola entera. Devuelve cuantos spans se han ido.

    La cola se reserva renombrandola: si dos hooks vacian a la vez, solo uno se
    queda con el lote y el otro no duplica nada. Lo que no entra vuelve a la cola
    con su contador de intentos, y se tira tras MAX_INTENTOS para que un fallo
    permanente no engorde el fichero para siempre.
    """
    cfg = config()
    if cfg is None:
        return 0
    reserva = COLA.with_suffix(f".{os.getpid()}.{int(time.time())}.envio")
    try:
        if not COLA.exists():
            return 0
        os.replace(COLA, reserva)
    except OSError:
        return 0

    enviados = 0
    devueltos: list[dict] = []
    try:
        spans: list[dict] = []
        with open(reserva, encoding="utf-8") as fh:
            for linea in fh:
                linea = linea.strip()
                if not linea:
                    continue
                try:
                    spans.append(json.loads(linea))
                except json.JSONDecodeError:
                    continue
        for i in range(0, len(spans), 100):
            lote = spans[i:i + 100]
            if _post("/api/public/otel/v1/traces", _payload(lote, cfg), cfg):
                enviados += len(lote)
            else:
                for s in lote:
                    s["intentos"] = int(s.get("intentos", 0)) + 1
                    if s["intentos"] < MAX_INTENTOS:
                        devueltos.append(s)
    except Exception:
        pass
    finally:
        try:
            if devueltos:
                with open(COLA, "a", encoding="utf-8", newline="\n") as fh:
                    for s in devueltos:
                        fh.write(json.dumps(s, ensure_ascii=False) + "\n")
            if reserva.exists():
                os.unlink(reserva)
        except OSError:
            pass
    return enviados


# -------------------------------------------------------------- puntuaciones

def puntuar(traza: str, nombre: str, valor, comentario: str | None = None,
            observacion: str | None = None) -> bool:
    """Manda una puntuacion. Son pocas y valen mas al instante que en un lote."""
    cfg = config()
    if cfg is None:
        return False
    cuerpo = {
        "traceId": traza,
        "name": nombre,
        "value": valor,
        "dataType": "CATEGORICAL" if isinstance(valor, str) else "NUMERIC",
        "environment": cfg["entorno"],
    }
    if comentario:
        cuerpo["comment"] = recortar(comentario, 900)
    if observacion:
        cuerpo["observationId"] = observacion
    return _post("/api/public/scores", cuerpo, cfg)


# ------------------------------------------------------- estado de la sesion

def guardar_sesion(session_id: str, inicio_ns: int, nombre: str) -> None:
    """Deja a mano la sesion viva: consolidar.py no recibe el payload del hook."""
    try:
        LOGS.mkdir(parents=True, exist_ok=True)
        tmp = SESION.with_suffix(".tmp")
        tmp.write_text(json.dumps({
            "session_id": session_id, "trace_id": id_traza(session_id),
            "inicio_ns": inicio_ns, "nombre": nombre,
        }, ensure_ascii=False), encoding="utf-8")
        os.replace(tmp, SESION)
    except OSError:
        return


def sesion_actual() -> dict | None:
    try:
        return json.loads(SESION.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


def leer_estado() -> dict:
    """Estado compartido entre hooks: llamadas abiertas y subagentes terminados.

    Vive en disco porque cada hook es un proceso nuevo. No es una base de datos:
    si dos hooks paralelos se pisan, se pierde un span, no un capitulo.
    """
    try:
        return json.loads(ESTADO.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}


def escribir_estado(estado: dict) -> None:
    try:
        LOGS.mkdir(parents=True, exist_ok=True)
        tmp = ESTADO.with_suffix(".tmp")
        tmp.write_text(json.dumps(estado, ensure_ascii=False), encoding="utf-8")
        os.replace(tmp, ESTADO)
    except OSError:
        return


def id_proyecto(cfg: dict) -> str | None:
    """El id de proyecto solo hace falta para construir enlaces; se cachea."""
    try:
        return json.loads(PROYECTO.read_text(encoding="utf-8"))["id"]
    except (OSError, json.JSONDecodeError, KeyError):
        pass
    peticion = urllib.request.Request(cfg["host"] + "/api/public/projects", headers=_cabeceras(cfg))
    try:
        with urllib.request.urlopen(peticion, timeout=TIMEOUT) as respuesta:
            datos = json.loads(respuesta.read().decode("utf-8"))
        pid = datos["data"][0]["id"]
        LOGS.mkdir(parents=True, exist_ok=True)
        PROYECTO.write_text(json.dumps({"id": pid}), encoding="utf-8")
        return pid
    except Exception:
        return None


def enlace(traza: str) -> str:
    cfg = config()
    if cfg is None:
        return ""
    pid = id_proyecto(cfg)
    return f"{cfg['host']}/project/{pid}/traces/{traza}" if pid else f"{cfg['host']}/traces/{traza}"
