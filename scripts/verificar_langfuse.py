"""Comprueba que la observabilidad esta viva, de la configuracion al dato subido.

Sirve para dos preguntas distintas. Sin argumentos responde a "esto esta bien
montado?": lee la configuracion, llama a Langfuse y sube una traza de prueba con
la misma forma que las de verdad. Con `estado` responde a "que se ha trazado?":
mira la cola local y cuenta lo que hay arriba en la ultima hora.

    python scripts/verificar_langfuse.py            prueba de extremo a extremo
    python scripts/verificar_langfuse.py estado     que hay en la cola y en Langfuse
"""
from __future__ import annotations

import base64
import datetime
import json
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import langfuse_cliente as lf

TIEMPO_ESPERA = 8  # la ingesta es asincrona; no aparece al instante


def _get(ruta: str, cfg: dict):
    peticion = urllib.request.Request(cfg["host"] + ruta, headers={
        "Authorization": "Basic " + base64.b64encode(f"{cfg['pk']}:{cfg['sk']}".encode()).decode()})
    with urllib.request.urlopen(peticion, timeout=20) as respuesta:
        return json.loads(respuesta.read().decode("utf-8"))


def observaciones_recientes(cfg: dict, horas: int = 1) -> list[dict]:
    ahora = datetime.datetime.now(datetime.timezone.utc)
    consulta = urllib.parse.urlencode({
        "fromStartTime": (ahora - datetime.timedelta(hours=horas)).isoformat().replace("+00:00", "Z"),
        "toStartTime": (ahora + datetime.timedelta(minutes=5)).isoformat().replace("+00:00", "Z"),
        "limit": 100,
    })
    return _get("/api/public/v2/observations?" + consulta, cfg).get("data", [])


def cmd_prueba() -> int:
    cfg = lf.config()
    if cfg is None:
        print("ERROR: faltan LANGFUSE_PUBLIC_KEY o LANGFUSE_SECRET_KEY.")
        print("Copia .env.example a .env y pon tus claves. Sin eso el harness")
        print("funciona igual, pero no traza nada.")
        return 1

    print(f"host      {cfg['host']}")
    print(f"entorno   {cfg['entorno']}")
    print(f"clave     {cfg['pk'][:12]}...")

    try:
        proyectos = _get("/api/public/projects", cfg)["data"]
        print(f"proyecto  {proyectos[0]['name']} ({proyectos[0]['id']})")
    except urllib.error.HTTPError as error:
        print(f"ERROR: Langfuse rechaza las claves (HTTP {error.code}). Revisa .env.")
        return 1
    except Exception as error:
        print(f"ERROR: no se puede hablar con Langfuse: {error}")
        return 1

    # Una traza con la misma forma que las reales: sesion, subagente y puntuacion.
    sesion = f"verificacion-{datetime.datetime.now().strftime('%Y%m%d-%H%M%S')}"
    ahora = lf.ahora_ns()
    raiz = lf.span(sesion, "raiz", "verificacion del harness", ahora - 3_000_000_000, ahora,
                   tipo="agent", padre=None,
                   atributos={**lf.atributos_traza("verificacion del harness", sesion, cfg,
                                                   etiquetas=["mystorymaker", "verificacion"]),
                              "langfuse.observation.input": "python scripts/verificar_langfuse.py"})
    hijo = lf.span(sesion, "subagente:prueba:0", "revisor", ahora - 2_000_000_000, ahora - 500_000_000,
                   tipo="generation",
                   atributos={"langfuse.observation.model.name": "claude-opus-5",
                              "langfuse.observation.usage_details": json.dumps({"input": 1000, "output": 100}),
                              "langfuse.observation.output": "traza de prueba"})
    lf.encolar([raiz, hijo], vaciar_ahora=True)
    traza = lf.id_traza(sesion)

    pendientes = lf._pendientes()
    if pendientes:
        print(f"ERROR: {pendientes} spans se han quedado en la cola: el envio ha fallado.")
        print(f"       cola en {lf.COLA}")
        return 1
    print("envio     2 spans aceptados por el endpoint OTel")

    puntuada = lf.puntuar(traza, "verificacion", 5, comentario="prueba de extremo a extremo")
    print(f"scores    {'aceptado' if puntuada else 'RECHAZADO'}")

    import time
    time.sleep(TIEMPO_ESPERA)
    try:
        ids = {o.get("traceId") for o in observaciones_recientes(cfg)}
        if traza in ids:
            print("lectura   la traza ya se ve en Langfuse")
        else:
            print("lectura   aun no aparece; la ingesta tarda unos segundos, no es un fallo")
    except Exception as error:
        print(f"lectura   no se ha podido comprobar: {error}")

    print()
    print("Traza de prueba:")
    print("  " + lf.enlace(traza))
    return 0 if puntuada else 1


def cmd_estado() -> int:
    cfg = lf.config()
    if cfg is None:
        print("Langfuse no esta configurado: no hay .env con las claves.")
        return 1
    print(f"cola local        {lf._pendientes()} spans sin enviar")
    sesion = lf.sesion_actual()
    if sesion:
        print(f"sesion apuntada   {sesion.get('nombre')} ({sesion.get('session_id')})")
        print(f"  " + lf.enlace(sesion["trace_id"]))
    else:
        print("sesion apuntada   ninguna (aun no ha corrido el hook SessionStart)")
    try:
        obs = observaciones_recientes(cfg)
    except Exception as error:
        print(f"Langfuse          no se ha podido consultar: {error}")
        return 1
    print(f"ultima hora       {len(obs)} observaciones en {len({o.get('traceId') for o in obs})} trazas")
    for tipo in ("AGENT", "GENERATION", "TOOL", "SPAN"):
        n = sum(1 for o in obs if o.get("type") == tipo)
        if n:
            print(f"  {tipo.lower():12} {n}")
    return 0


def main() -> int:
    if len(sys.argv) > 1 and sys.argv[1] == "estado":
        return cmd_estado()
    return cmd_prueba()


if __name__ == "__main__":
    raise SystemExit(main())
