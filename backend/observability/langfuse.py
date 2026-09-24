"""El cliente de Langfuse: cada llamada al modelo, como traza, en la sesion de su novela.

Implementa `ClienteDeObservabilidad` sobre la API publica de ingesta
(`POST /api/public/ingestion`), sin SDK: el protocolo ya es lo unico contra lo que el
sistema programa, y un SDK entero para cuatro eventos es una dependencia que no paga su
peso (SPEC-012 A-04).

**Este modulo no hace HTTP.** `test_import_boundaries` prohibe a `observability/` las
bibliotecas de red —observa y no participa—, asi que el transporte se le inyecta: lo pone
el worker, que es quien ya habla con la red (SPEC-012 DV-1). Por lo mismo, el enlace a
una traza se compone con `LANGFUSE_PROJECT_ID` en lugar de preguntarle el proyecto a
Langfuse.

Tres reglas, las tres de SPEC-003 y SPEC-012:

1. **Observar no puede romper la escritura.** Un fallo al enviar —red, `4xx`, `5xx`,
   tiempo agotado— se anota en el log y se descarta (RF-LAN-03).
2. **No sale prosa.** Solo modelo, tokens, coste, latencia, version de prompt y la
   posicion en la novela (RF-LAN-04). La prosa y el paquete viven en SQLite.
3. **Sin claves, nada.** Si falta alguna variable `LANGFUSE_*`, o trae el valor de
   ejemplo de `.env.example`, el cliente es `ClienteNulo` (RF-LAN-01). Las claves nunca se
   escriben en el log.

Cubre RF-LAN-01 a RF-LAN-05, con RF-LAN-05 en la forma de DV-1.
"""

from __future__ import annotations

import base64
import json
import logging
import os
import uuid
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from threading import Lock

from backend.observability.trazas import (
    ClienteDeObservabilidad,
    ClienteNulo,
    ScoreRegistrado,
    Span,
    Traza,
    Uso,
)

registro = logging.getLogger(__name__)

VARIABLES = ("LANGFUSE_PUBLIC_KEY", "LANGFUSE_SECRET_KEY", "LANGFUSE_HOST")
PROYECTO = "LANGFUSE_PROJECT_ID"
# Lo que trae `.env.example`: con esto no hay nada que activar.
MARCAS_DE_EJEMPLO = ("TU_CLAVE_AQUI", "TU_PROYECTO_AQUI")
ESPERA_SEGUNDOS = 3.0

# metodo, url, cabeceras, cuerpo, espera -> (estado, cuerpo). Lo inyecta el worker; la
# suite, uno falso.
Transporte = Callable[[str, str, dict[str, str], bytes | None, float], tuple[int, bytes]]


@dataclass(frozen=True)
class LlamadaObservada:
    """Lo que se cuenta de una llamada al modelo. Nada de prosa ni de paquete."""

    procedencia_id: str
    volumen_id: str
    agente: str
    tarea: str
    modelo: str
    version_de_prompt: str
    tokens_entrada: int | None
    tokens_salida: int | None
    coste: float
    latencia_ms: int
    clase_de_fallo: str | None
    escena_id: str | None
    capitulo_orden: int | None
    modo: str


def registrar_llamada(cliente: ClienteDeObservabilidad, llamada: LlamadaObservada) -> None:
    """Una llamada es una traza —con el id de su procedencia— y un span dentro de ella.

    La traza lleva por sesion la novela: en Langfuse, todas las llamadas de una novela se
    ven juntas, y cada fila de la pestaña de gastos enlaza a la suya (D-24).
    """
    traza = Traza(
        id=llamada.procedencia_id,
        nombre=f"{llamada.agente}:{llamada.tarea}",
        sesion=llamada.volumen_id,
        metadatos={"modo": llamada.modo},
    )
    metadatos = {"version_de_prompt": llamada.version_de_prompt, "modo": llamada.modo}
    if llamada.escena_id is not None:
        metadatos["escena_id"] = llamada.escena_id
    if llamada.capitulo_orden is not None:
        metadatos["capitulo_orden"] = str(llamada.capitulo_orden)
    span = Span(
        id=f"ge-{llamada.procedencia_id}",
        traza_id=llamada.procedencia_id,
        nombre=llamada.agente,
        tipo="rol",
        version_de_prompt=llamada.version_de_prompt,
        latencia_ms=llamada.latencia_ms,
        uso=Uso(
            tokens_entrada=llamada.tokens_entrada or 0,
            tokens_salida=llamada.tokens_salida or 0,
            coste=llamada.coste,
        ),
        error=llamada.clase_de_fallo,
        modelo=llamada.modelo,
        metadatos=metadatos,
    )
    cliente.abrir_traza(traza)
    cliente.registrar_span(span)
    cliente.cerrar_traza(traza)


@dataclass
class ClienteLangfuse:
    """Acumula los eventos de cada traza y los envia en un lote al cerrarla."""

    host: str
    clave_publica: str
    clave_secreta: str
    transporte: Transporte
    espera: float = ESPERA_SEGUNDOS
    _pendientes: dict[str, list[dict[str, object]]] = field(default_factory=dict, repr=False)
    _cerrojo: Lock = field(default_factory=Lock, repr=False)

    def abrir_traza(self, traza: Traza) -> None:
        cuerpo: dict[str, object] = {
            "id": traza.id,
            "name": traza.nombre,
            "sessionId": traza.sesion,
            "timestamp": _ahora(),
            "metadata": dict(traza.metadatos),
        }
        with self._cerrojo:
            self._pendientes[traza.id] = [_evento("trace-create", cuerpo)]

    def registrar_span(self, span: Span) -> None:
        fin = datetime.now(UTC)
        inicio = fin - timedelta(milliseconds=span.latencia_ms)
        cuerpo: dict[str, object] = {
            "id": span.id,
            "traceId": span.traza_id,
            "name": span.nombre,
            "startTime": _iso(inicio),
            "endTime": _iso(fin),
            "metadata": dict(span.metadatos),
        }
        if span.modelo is not None:
            cuerpo["model"] = span.modelo
        if span.uso is not None:
            cuerpo["usageDetails"] = {
                "input": span.uso.tokens_entrada,
                "output": span.uso.tokens_salida,
            }
            cuerpo["costDetails"] = {"total": span.uso.coste}
        if span.error is not None:
            cuerpo["level"] = "ERROR"
            cuerpo["statusMessage"] = f"fallo de {span.error}"
        with self._cerrojo:
            self._pendientes.setdefault(span.traza_id, []).append(
                _evento("generation-create", cuerpo)
            )

    def registrar_score(self, score: ScoreRegistrado) -> None:
        cuerpo: dict[str, object] = {
            "id": f"sc-{uuid.uuid4().hex[:12]}",
            "traceId": score.traza_id,
            "name": score.nombre,
            "value": score.valor,
            "comment": score.comentario,
        }
        with self._cerrojo:
            self._pendientes.setdefault(score.traza_id, []).append(
                _evento("score-create", cuerpo)
            )

    def cerrar_traza(self, traza: Traza) -> None:
        with self._cerrojo:
            lote = self._pendientes.pop(traza.id, [])
        if lote:
            self._enviar("/api/public/ingestion", {"batch": lote})

    def _enviar(self, ruta: str, carga: Mapping[str, object]) -> None:
        """Envia el lote. Cualquier fallo se anota y se descarta (RF-LAN-03)."""
        credencial = base64.b64encode(
            f"{self.clave_publica}:{self.clave_secreta}".encode()
        ).decode()
        cabeceras = {"Authorization": f"Basic {credencial}", "Content-Type": "application/json"}
        url = f"{self.host.rstrip('/')}{ruta}"
        try:
            estado, respuesta = self.transporte(
                "POST", url, cabeceras, json.dumps(carga).encode(), self.espera
            )
        except Exception as error:  # noqa: BLE001 - observar nunca para la escritura
            registro.warning("Langfuse no ha respondido a %s: %s", ruta, error)
            return
        if not 200 <= estado < 300:
            registro.warning(
                "Langfuse ha respondido %s a %s: %s", estado, ruta, respuesta[:200]
            )


def langfuse_activo(entorno: Mapping[str, str] | None = None) -> bool:
    """Si estan las tres variables con valores reales, no los de `.env.example`."""
    return _valores(entorno) is not None


def cliente_desde_el_entorno(
    entorno: Mapping[str, str] | None, transporte: Transporte
) -> ClienteLangfuse | ClienteNulo:
    """`ClienteLangfuse` si Langfuse esta configurado; si no, nulo (RF-LAN-01)."""
    valores = _valores(entorno)
    if valores is None:
        return ClienteNulo()
    publica, secreta, host = valores
    return ClienteLangfuse(
        host=host, clave_publica=publica, clave_secreta=secreta, transporte=transporte
    )


def url_de_traza(entorno: Mapping[str, str] | None, traza_id: str) -> str | None:
    """`<host>/project/<proyecto>/traces/<id>`, o `None` si falta algo para componerla."""
    valores = _valores(entorno)
    variables = os.environ if entorno is None else entorno
    proyecto = variables.get(PROYECTO, "").strip()
    if valores is None or not proyecto or _es_de_ejemplo(proyecto):
        return None
    return f"{valores[2].rstrip('/')}/project/{proyecto}/traces/{traza_id}"


def _valores(entorno: Mapping[str, str] | None) -> tuple[str, str, str] | None:
    variables = os.environ if entorno is None else entorno
    publica, secreta, host = (variables.get(nombre, "").strip() for nombre in VARIABLES)
    if not (publica and secreta and host):
        return None
    if any(_es_de_ejemplo(valor) for valor in (publica, secreta, host)):
        return None
    return publica, secreta, host


def _es_de_ejemplo(valor: str) -> bool:
    return any(marca in valor for marca in MARCAS_DE_EJEMPLO)


def _evento(tipo: str, cuerpo: dict[str, object]) -> dict[str, object]:
    return {"id": uuid.uuid4().hex, "type": tipo, "timestamp": _ahora(), "body": cuerpo}


def _ahora() -> str:
    return _iso(datetime.now(UTC))


def _iso(momento: datetime) -> str:
    return momento.isoformat(timespec="milliseconds").replace("+00:00", "Z")
