"""Valida config/capitulos.json contra su esquema y las reglas de §12.

Uso:
    python scripts/validar_capitulos.py            # validacion directa
    ... | python scripts/validar_capitulos.py --hook   # PostToolUse

Comprueba (RM-03): esquema, n unico y consecutivo desde 1, actos ordenados,
coherencia entre unidad y campos de extension, y suma del plan dentro de la
tolerancia total.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _comun import CONFIG, bajo, bloquear, leer_evento_hook, leer_json, ruta_afectada

CAMPOS_LINEAS = ("lineas_totales_objetivo", "tolerancia_capitulo_lineas", "tolerancia_total_lineas")
CAMPOS_PALABRAS = ("palabras_totales_objetivo", "tolerancia_capitulo_pct", "tolerancia_total_pct")


def validar(config: dict) -> list[str]:
    errores: list[str] = []

    for campo in ("version", "titulo_trabajo", "extension", "capitulos"):
        if campo not in config:
            errores.append(f"falta el campo obligatorio '{campo}'")
    if errores:
        return errores

    if not isinstance(config["version"], int) or config["version"] < 1:
        errores.append("'version' debe ser un entero >= 1")

    ext = config["extension"]
    unidad = ext.get("unidad")
    if unidad not in ("lineas", "palabras"):
        return errores + ["'extension.unidad' debe ser 'lineas' o 'palabras'"]

    # Coherencia entre unidad y campos declarados (RM-03).
    esperados = CAMPOS_LINEAS if unidad == "lineas" else CAMPOS_PALABRAS
    prohibidos = CAMPOS_PALABRAS if unidad == "lineas" else CAMPOS_LINEAS
    for campo in esperados:
        if campo not in ext:
            errores.append(f"con unidad '{unidad}' falta 'extension.{campo}'")
    for campo in prohibidos:
        if campo in ext:
            errores.append(f"con unidad '{unidad}' sobra 'extension.{campo}'")

    capitulos = config["capitulos"]
    if not isinstance(capitulos, list) or not capitulos:
        return errores + ["'capitulos' debe ser una lista no vacia"]

    campo_obj = "lineas_objetivo" if unidad == "lineas" else "palabras_objetivo"
    por_defecto = config.get("defaults", {}).get(campo_obj)

    numeros = [c.get("n") for c in capitulos]
    if numeros != list(range(1, len(capitulos) + 1)):
        errores.append(f"'n' debe ser unico y consecutivo desde 1; se ha leido {numeros}")

    actos = [c.get("acto") for c in capitulos]
    if any(a not in (1, 2, 3) for a in actos):
        errores.append("'acto' debe ser 1, 2 o 3 en todos los capitulos")
    elif actos != sorted(actos):
        errores.append(f"los actos deben ir en orden no decreciente; se ha leido {actos}")

    suma = 0
    for cap in capitulos:
        n = cap.get("n")
        if not isinstance(cap.get("contiene_combate"), bool):
            errores.append(f"cap {n}: 'contiene_combate' es obligatorio y booleano")
        objetivo = cap.get(campo_obj, por_defecto)
        if objetivo is None:
            errores.append(f"cap {n}: sin '{campo_obj}' y sin valor en defaults")
        elif not isinstance(objetivo, int) or objetivo < 1:
            errores.append(f"cap {n}: '{campo_obj}' debe ser un entero >= 1")
        else:
            suma += objetivo

        # Si el capitulo declara estructura interna, tiene que cuadrar con su extension.
        defaults = config.get("defaults", {})
        parrafos = cap.get("parrafos_objetivo", defaults.get("parrafos_objetivo"))
        por_parrafo = cap.get("lineas_por_parrafo", defaults.get("lineas_por_parrafo"))
        if por_parrafo is not None and parrafos is None:
            errores.append(f"cap {n}: declara 'lineas_por_parrafo' sin 'parrafos_objetivo'")
        if parrafos is not None and unidad != "lineas":
            errores.append(f"cap {n}: 'parrafos_objetivo' solo tiene sentido con unidad 'lineas'")
        elif (parrafos is not None and por_parrafo is not None
              and isinstance(objetivo, int) and parrafos * por_parrafo != objetivo):
            errores.append(
                f"cap {n}: {parrafos} parrafos de {por_parrafo} lineas suman "
                f"{parrafos * por_parrafo}, y '{campo_obj}' dice {objetivo}"
            )

    if unidad == "lineas":
        total = ext.get("lineas_totales_objetivo")
        tolerancia = ext.get("tolerancia_total_lineas", 0)
    else:
        total = ext.get("palabras_totales_objetivo")
        tolerancia = round((total or 0) * float(ext.get("tolerancia_total_pct", 0)) / 100)
    if isinstance(total, int) and abs(suma - total) > int(tolerancia or 0):
        errores.append(
            f"la suma del plan ({suma}) se aleja del objetivo ({total}) "
            f"mas de la tolerancia total ({tolerancia})"
        )

    return errores


def main() -> int:
    modo_hook = "--hook" in sys.argv
    if modo_hook:
        evento = leer_evento_hook()
        ruta = ruta_afectada(evento)
        if ruta is None or not bajo(ruta, CONFIG.parent) or ruta.name != CONFIG.name:
            return 0

    try:
        config = leer_json(CONFIG)
    except FileNotFoundError:
        mensaje = f"config/capitulos.json no existe ({CONFIG})"
        bloquear(mensaje) if modo_hook else print(mensaje, file=sys.stderr)
        return 1
    except Exception as exc:
        mensaje = f"config/capitulos.json no es JSON valido: {exc}"
        bloquear(mensaje) if modo_hook else print(mensaje, file=sys.stderr)
        return 1

    errores = validar(config)
    if errores:
        detalle = "\n".join(f"  - {e}" for e in errores)
        mensaje = (
            "RM-03 - config/capitulos.json no valida:\n" + detalle +
            "\nCorrige el fichero antes de continuar; no reindexes outline.json con un plan invalido."
        )
        if modo_hook:
            bloquear(mensaje)
        print(mensaje, file=sys.stderr)
        return 1

    if not modo_hook:
        unidad = config["extension"]["unidad"]
        print(f"OK - {len(config['capitulos'])} capitulos, unidad '{unidad}', version {config['version']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
