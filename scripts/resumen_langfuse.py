"""Resume en la consola lo que costo la ultima tanda, agente por agente.

Langfuse tiene la interfaz, pero para la pregunta de siempre —cuanto ha costado
esto y quien se lo ha gastado— ir a la web y sumar a mano es peor que una tabla
de seis lineas. Esto consulta la API de metricas y la imprime.

    python scripts/resumen_langfuse.py             ultima hora
    python scripts/resumen_langfuse.py --horas 6   ventana mas ancha
    python scripts/resumen_langfuse.py --traza ID  una traza concreta

El coste lo calcula Langfuse a partir de su tabla de modelos. Si el modelo no
esta en esa tabla el coste sale a cero aunque los tokens esten bien contados, asi
que se avisa en vez de dar un cero por bueno.
"""
from __future__ import annotations

import argparse
import datetime
import json
import sys
import urllib.parse
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import langfuse_cliente as lf
from verificar_langfuse import _get

# Los cuatro subagentes de SPECS; lo demas son herramientas o la sesion misma.
AGENTES = {"investigacion": "N1", "escaleta": "N2", "escritor": "N3", "revisor": "N4"}


def consultar(cfg: dict, vista: str, dimensiones: list[str], metricas: list[dict],
              desde: str, hasta: str, filtros: list[dict] | None = None) -> list[dict]:
    consulta = {
        "view": vista,
        "dimensions": [{"field": d} for d in dimensiones],
        "metrics": metricas,
        "fromTimestamp": desde,
        "toTimestamp": hasta,
    }
    if filtros:
        consulta["filters"] = filtros
    ruta = "/api/public/v2/metrics?" + urllib.parse.urlencode({"query": json.dumps(consulta)})
    return _get(ruta, cfg).get("data", [])


def main() -> int:
    parser = argparse.ArgumentParser(description="Coste y consumo de la ultima tanda")
    parser.add_argument("--horas", type=float, default=1.0)
    parser.add_argument("--traza", help="limita el resumen a una traza concreta")
    args = parser.parse_args()

    cfg = lf.config()
    if cfg is None:
        print("Langfuse no esta configurado: no hay .env con las claves.")
        return 1

    ahora = datetime.datetime.now(datetime.timezone.utc)
    desde = (ahora - datetime.timedelta(hours=args.horas)).isoformat().replace("+00:00", "Z")
    hasta = (ahora + datetime.timedelta(minutes=5)).isoformat().replace("+00:00", "Z")
    filtros = ([{"column": "traceId", "operator": "=", "value": args.traza, "type": "string"}]
               if args.traza else None)

    metricas = [{"measure": "totalTokens", "aggregation": "sum"},
                {"measure": "totalCost", "aggregation": "sum"},
                {"measure": "count", "aggregation": "count"},
                {"measure": "latency", "aggregation": "sum"}]
    try:
        filas = consultar(cfg, "observations", ["name"], metricas, desde, hasta, filtros)
    except Exception as error:
        print(f"No se ha podido consultar Langfuse: {error}")
        return 1

    def num(fila: dict, clave: str) -> float:
        valor = fila.get(clave)
        return float(valor) if valor not in (None, "") else 0.0

    agentes = [f for f in filas if f.get("name") in AGENTES]
    otros = [f for f in filas if f.get("name") not in AGENTES]

    print(f"Ventana: ultimas {args.horas:g} h" + (f" - traza {args.traza}" if args.traza else ""))
    print()
    if not agentes:
        print("Ningun subagente en esta ventana. Los nombres vistos son:")
        print("  " + ", ".join(sorted(str(f.get("name")) for f in filas)) or "  (ninguno)")
        return 0

    print(f"{'nodo':5} {'agente':15} {'llamadas':>9} {'tokens':>12} {'coste USD':>11} {'tiempo':>9}")
    print("-" * 66)
    total_tokens = total_coste = total_llamadas = 0.0
    for fila in sorted(agentes, key=lambda f: AGENTES[f["name"]]):
        tokens, coste = num(fila, "sum_totalTokens"), num(fila, "sum_totalCost")
        # La API de metricas da la latencia en milisegundos.
        llamadas = num(fila, "count_count")
        segundos = num(fila, "sum_latency") / 1000.0
        total_tokens += tokens
        total_coste += coste
        total_llamadas += llamadas
        print(f"{AGENTES[fila['name']]:5} {fila['name']:15} {llamadas:>9.0f} "
              f"{tokens:>12,.0f} {coste:>11.4f} {segundos:>8.1f}s")
    print("-" * 66)
    print(f"{'':5} {'total':15} {total_llamadas:>9.0f} {total_tokens:>12,.0f} {total_coste:>11.4f}")

    if total_tokens and not total_coste:
        print()
        print("Aviso: los tokens estan contados pero el coste sale a 0. Langfuse solo")
        print("calcula coste de los modelos que tiene en su tabla de precios; si el")
        print("modelo de estas trazas no esta, hay que darlo de alta en el proyecto.")

    if otros:
        ruido = sum(num(f, "sum_totalTokens") for f in otros)
        print()
        print(f"({len(otros)} observaciones mas (sesiones y herramientas) con {ruido:,.0f} tokens)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
