"""Escritura en memoria (M1). Unico camino por el que memory/ cambia.

El hook bloquear_memoria.py deniega cualquier Write o Edit sobre memory/, asi
que todo lo que entra en la biblia, la escaleta viva o el ledger pasa por aqui.
El script se invoca con Bash, herramienta que ningun subagente tiene: eso es lo
que convierte INV-09 en una propiedad de la topologia y no en una promesa del
prompt.

Toda escritura es atomica (temporal + renombrado) e incrementa 'version'
(SPECS 11). Consolidar dos veces el mismo capitulo no duplica entradas en el
ledger: cada hecho lleva la marca del capitulo que lo produjo y se sustituye,
no se acumula.

Subcomandos
-----------
    estado                       Progreso segun outline.json
    sembrar-bible  FICHERO       Escribe memory/bible.json desde la salida de N2
    sembrar-outline FICHERO      Escribe memory/outline.json desde la salida de N2
    sincronizar                  Aplica a outline.json un cambio de config (12.4)
    marcar N ESTADO              Cambia el estado de produccion de un capitulo
    capitulo N --iteracion K     Consolida el capitulo N aprobado por D1
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _comun import (BIBLE, CONFIG, ESTADOS, LEDGER, LOGS, MANUSCRITO, MARCADORES, MAX_ITER,
                    MEMORIA, OUTLINE, REVIEWS, contar_lineas, contar_palabras,
                    escribir_json_atomico, estructura_de, leer_json, objetivo_de,
                    parrafos_capitulo)

VICTORIA, DERROTA, EMPATE = "victoria", "derrota", "empate"


# --------------------------------------------------------------------------- utilidades

def fallo(mensaje: str) -> None:
    print(f"ERROR: {mensaje}", file=sys.stderr)
    raise SystemExit(1)


def cargar(ruta: Path, por_defecto: dict) -> dict:
    if not ruta.exists():
        return dict(por_defecto)
    try:
        return leer_json(ruta)
    except Exception as exc:
        fallo(f"{ruta.name} ilegible: {exc}")
        return {}


def guardar(ruta: Path, datos: dict) -> int:
    datos["version"] = int(datos.get("version", 0)) + 1
    datos["actualizado"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
    escribir_json_atomico(ruta, datos)
    return datos["version"]


def outline_actual() -> dict:
    outline = cargar(OUTLINE, {"version": 0, "capitulos": []})
    if not outline.get("capitulos"):
        fallo("memory/outline.json esta vacio. Ejecuta antes N2 (escaleta) y persiste "
              "su plan con 'sembrar-outline'.")
    return outline


def ledger_actual() -> dict:
    return cargar(LEDGER, {
        "version": 0,
        "record": {"victorias": 0, "derrotas": 0, "empates": 0, "ko": 0},
        "cronologia": [], "combates": [], "lesiones": [], "hilos_abiertos": [],
    })


def capitulo_de(outline: dict, n: int) -> dict:
    cap = next((c for c in outline.get("capitulos", []) if c.get("n") == n), None)
    if cap is None:
        fallo(f"El capitulo {n} no esta en memory/outline.json")
    return cap


def aprobado(review: dict) -> tuple[bool, str]:
    """D1 (SPECS 8). continuidad >= 3 y min(criterios) >= 3 y media >= 4,0."""
    p = review.get("puntuaciones") or {}
    criterios = ("tension", "verosimilitud_tecnica", "avance_arco", "prosa", "continuidad")
    faltan = [c for c in criterios if not isinstance(p.get(c), int)]
    if faltan:
        return False, f"la revision no puntua {', '.join(faltan)}"
    if p["continuidad"] <= 2:
        return False, f"rechazo duro por continuidad ({p['continuidad']}), RN-02"
    if min(p[c] for c in criterios) < 3:
        return False, "algun criterio por debajo de 3 (RN-01)"
    media = sum(p[c] for c in criterios) / len(criterios)
    if media < 4.0:
        return False, f"media {media:.2f} < 4,0 (RN-01)"
    return True, f"media {media:.2f}, minimo {min(p[c] for c in criterios)}"


def traza(registro: dict) -> None:
    LOGS.mkdir(parents=True, exist_ok=True)
    registro["ts"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
    destino = LOGS / f"run-{datetime.now(timezone.utc).strftime('%Y%m%d')}.jsonl"
    with open(destino, "a", encoding="utf-8", newline="\n") as fh:
        fh.write(json.dumps(registro, ensure_ascii=False) + "\n")


# --------------------------------------------------------------------------- ledger

def sin_el_capitulo(entradas: list, n: int) -> list:
    """Idempotencia: al reconsolidar se retiran las entradas previas del capitulo."""
    return [e for e in entradas if e.get("capitulo") != n]


def aplicar_hechos(ledger: dict, n: int, hechos: list, contiene_combate: bool) -> list[str]:
    avisos: list[str] = []

    ledger["cronologia"] = sin_el_capitulo(ledger.get("cronologia", []), n)
    ledger["combates"] = sin_el_capitulo(ledger.get("combates", []), n)
    ledger["lesiones"] = sin_el_capitulo(ledger.get("lesiones", []), n)

    for hecho in hechos:
        tipo = (hecho.get("tipo") or "").lower()
        datos = {k: v for k, v in hecho.items() if k != "tipo"}
        datos["capitulo"] = n

        if tipo == "combate":
            if not contiene_combate:
                avisos.append(
                    f"INV-04: el cap {n} declara un combate pero config/capitulos.json dice "
                    "contiene_combate=false. El combate se descarta y el record no cambia."
                )
                continue
            ledger["combates"].append(datos)
        elif tipo == "lesion":
            ledger["lesiones"].append(datos)
        elif tipo == "cronologia":
            ledger["cronologia"].append(datos)
        elif tipo == "hilo_abierto":
            hilos = ledger.setdefault("hilos_abiertos", [])
            hid = hecho.get("id") or f"h-{n:02d}-{len(hilos) + 1}"
            if not any(h.get("id") == hid for h in hilos):
                hilos.append({
                    "id": hid,
                    "descripcion": hecho.get("descripcion", ""),
                    "abierto_en": n,
                    "cerrar_antes_de": hecho.get("cerrar_antes_de"),
                })
        elif tipo == "hilo_cerrado":
            hid = hecho.get("id")
            antes = len(ledger.get("hilos_abiertos", []))
            ledger["hilos_abiertos"] = [h for h in ledger.get("hilos_abiertos", [])
                                        if h.get("id") != hid]
            if len(ledger["hilos_abiertos"]) == antes:
                avisos.append(f"El cap {n} cierra el hilo '{hid}', que no estaba abierto.")
        else:
            avisos.append(f"Hecho de tipo desconocido en el cap {n}: '{tipo}'. Ignorado.")

    # INV-04: el record se recalcula desde cero sobre los combates del ledger,
    # de modo que reconsolidar nunca lo desplaza.
    record = {"victorias": 0, "derrotas": 0, "empates": 0, "ko": 0}
    for combate in ledger["combates"]:
        resultado = (combate.get("resultado_prota") or "").lower()
        via = (combate.get("via") or combate.get("resultado") or "").lower()
        if resultado == VICTORIA:
            record["victorias"] += 1
            if "ko" in via:
                record["ko"] += 1
        elif resultado == DERROTA:
            record["derrotas"] += 1
        elif resultado == EMPATE:
            record["empates"] += 1
        else:
            avisos.append(
                f"Combate del cap {combate.get('capitulo')} sin 'resultado_prota' valido "
                "(victoria|derrota|empate): no cuenta para el record."
            )
    ledger["record"] = record
    return avisos


# --------------------------------------------------------------------------- comandos

def cmd_estado(_: argparse.Namespace) -> int:
    config = leer_json(CONFIG)
    if not cargar(OUTLINE, {"capitulos": []}).get("capitulos"):
        print("Escaleta no sembrada. Siguiente paso: N1 (investigacion) y N2 (escaleta).")
        print(f"Plan del autor: {len(config['capitulos'])} capitulos, "
              f"unidad '{config['extension']['unidad']}', config version {config['version']}.")
        return 0

    outline = leer_json(OUTLINE)
    ledger = ledger_actual()
    print(f"outline.json version {outline.get('version')} - "
          f"config version {outline.get('config_version', '?')} "
          f"(config actual: {config['version']})")
    for cap in outline.get("capitulos", []):
        marca = {"consolidado": "[x]", "escalado": "[!]",
                 "en_revision": "[~]", "pendiente": "[ ]"}.get(cap.get("estado"), "[?]")
        print(f"  {marca} cap {cap['n']:02d} {cap.get('titulo', ''):<24} "
              f"{cap.get('estado', '?'):<12} iteraciones={cap.get('iteraciones', 0)}")

    pendientes = [c for c in outline.get("capitulos", []) if c.get("estado") == "pendiente"]
    escalados = [c for c in outline.get("capitulos", []) if c.get("estado") == "escalado"]
    r = ledger.get("record", {})
    print(f"Record: {r.get('victorias', 0)}-{r.get('derrotas', 0)}-{r.get('empates', 0)} "
          f"({r.get('ko', 0)} KO) - hilos abiertos: {len(ledger.get('hilos_abiertos', []))}")
    if escalados:
        print(f"ESCALADO al autor: capitulos {[c['n'] for c in escalados]}. D2 no avanza.")
    elif pendientes:
        print(f"Siguiente: cap {pendientes[0]['n']:02d} (E9).")
    else:
        print("Sin pendientes. Siguiente: N5, compilar el manuscrito (E10).")
    return 0


def cmd_sembrar_bible(args: argparse.Namespace) -> int:
    datos = leer_json(Path(args.fichero))
    for campo in ("voz", "personajes", "reglas_mundo"):
        if campo not in datos:
            fallo(f"la biblia no declara '{campo}' (SPECS 5: debe existir muestra de voz)")
    if not (datos.get("voz") or {}).get("muestra"):
        fallo("la biblia no trae muestra de voz. Es condicion de salida de N2.")
    previa = cargar(BIBLE, {"version": 0})
    datos["version"] = previa.get("version", 0)
    version = guardar(BIBLE, datos)
    print(f"memory/bible.json escrito, version {version}, "
          f"{len(datos.get('personajes', []))} personajes.")
    return 0


def cmd_sembrar_outline(args: argparse.Namespace) -> int:
    propuesta = leer_json(Path(args.fichero))
    config = leer_json(CONFIG)
    plan = {c["n"]: c for c in config["capitulos"]}
    entrantes = {c["n"]: c for c in propuesta.get("capitulos", [])}

    if set(entrantes) != set(plan):
        fallo(f"N2 propone los capitulos {sorted(entrantes)} y config/capitulos.json "
              f"fija {sorted(plan)}. N2 no decide cuantos capitulos hay (SPECS 5).")

    previo = cargar(OUTLINE, {"version": 0, "capitulos": []})
    estados = {c["n"]: c for c in previo.get("capitulos", [])}
    unidad_cfg = config["extension"]["unidad"]
    campo_obj = "lineas_objetivo" if unidad_cfg == "lineas" else "palabras_objetivo"

    capitulos = []
    for n in sorted(plan):
        origen, fijado = entrantes[n], plan[n]
        objetivo, _, _ = objetivo_de(config, n)
        antes = estados.get(n, {})
        if antes.get("estado") == "consolidado":
            fallo(f"el cap {n} ya esta consolidado; sembrar de nuevo la escaleta lo pisaria "
                  "(RM-02). Usa 'sincronizar' o marca el capitulo para reescritura.")
        capitulos.append({
            "n": n,
            "titulo": origen.get("titulo") or fijado.get("titulo", ""),
            "objetivo": origen.get("objetivo", ""),
            "pov": origen.get("pov") or config.get("defaults", {}).get("pov", "prota"),
            "conflicto": origen.get("conflicto", ""),
            "salida": origen.get("salida", ""),
            "problema_tactico": origen.get("problema_tactico"),
            "acto": fijado["acto"],
            "contiene_combate": fijado["contiene_combate"],
            campo_obj: objetivo,
            "estado": antes.get("estado", "pendiente"),
            "iteraciones": antes.get("iteraciones", 0),
        })

    for campo in ("objetivo", "conflicto", "salida"):
        vacios = [c["n"] for c in capitulos if not c.get(campo)]
        if vacios:
            fallo(f"los capitulos {vacios} no declaran '{campo}'. Es condicion de salida de N2.")

    combates = [c for c in capitulos if c["contiene_combate"]]
    problemas = [c.get("problema_tactico") for c in combates]
    if any(not p for p in problemas):
        fallo("todo capitulo con combate declara un problema tactico (SPECS 5).")
    if len(set(problemas)) != len(problemas):
        fallo("dos combates comparten problema tactico. Deben ser distintos (SPECS 5).")

    outline = {
        "version": previo.get("version", 0),
        "config_version": config["version"],
        "unidad": config["extension"]["unidad"],
        "capitulos": capitulos,
    }
    version = guardar(OUTLINE, outline)
    print(f"memory/outline.json escrito, version {version}, {len(capitulos)} capitulos "
          f"contra config version {config['version']}.")
    return 0


def cmd_sincronizar(_: argparse.Namespace) -> int:
    """SPECS 12.4: reproyecta config/capitulos.json sobre la escaleta viva."""
    config = leer_json(CONFIG)
    outline = outline_actual()
    plan = {c["n"]: c for c in config["capitulos"]}
    vivos = {c["n"]: c for c in outline.get("capitulos", [])}
    unidad = config["extension"]["unidad"]
    campo = "lineas_objetivo" if unidad == "lineas" else "palabras_objetivo"
    avisos, cambios = [], []

    if outline.get("unidad") and outline["unidad"] != unidad:
        for cap in vivos.values():                                    # RM-08
            cap["estado"] = "pendiente"
            cap["iteraciones"] = 0
        avisos.append("RM-08: ha cambiado extension.unidad; todo el plan vuelve a pendiente.")
        outline["unidad"] = unidad

    nuevos = []
    for n in sorted(plan):
        fijado = plan[n]
        objetivo, tolerancia, _ = objetivo_de(config, n)
        cap = vivos.get(n)
        if cap is None:                                               # RM-01
            nuevos.append({
                "n": n, "titulo": fijado.get("titulo", ""), "objetivo": "", "pov":
                config.get("defaults", {}).get("pov", "prota"), "conflicto": "", "salida": "",
                "problema_tactico": None, "acto": fijado["acto"],
                "contiene_combate": fijado["contiene_combate"], campo: objetivo,
                "estado": "pendiente", "iteraciones": 0,
            })
            cambios.append(f"cap {n} anadido como pendiente (RM-01). N2 debe rellenarlo.")
            continue

        consolidado = cap.get("estado") == "consolidado"
        if cap.get("contiene_combate") != fijado["contiene_combate"]:
            cap["contiene_combate"] = fijado["contiene_combate"]
            if consolidado and fijado["contiene_combate"]:            # RM-06
                cap["estado"] = "pendiente"
                cap["iteraciones"] = 0
                cambios.append(f"RM-06: el cap {n} pasa a tener combate y vuelve a pendiente.")
        if cap.get(campo) != objetivo:
            diferencia = abs((cap.get(campo) or 0) - objetivo)
            cap[campo] = objetivo
            if consolidado and diferencia > tolerancia:               # RM-07
                cap["estado"] = "pendiente"
                cap["iteraciones"] = 0
                cambios.append(f"RM-07: cambia la extension del cap {n} y vuelve a pendiente.")
        cap["acto"] = fijado["acto"]

    fuera = sorted(set(vivos) - set(plan))
    for n in fuera:                                                   # SPECS 12.4 punto 3
        cap = vivos.pop(n)
        if cap.get("estado") == "consolidado":
            avisos.append(f"El cap {n} sale del plan pero su texto se conserva en manuscript/. "
                          "Revisa si dejaba algun hilo abierto en el ledger.")
        else:
            cambios.append(f"cap {n} eliminado del plan.")

    outline["capitulos"] = sorted(list(vivos.values()) + nuevos, key=lambda c: c["n"])
    outline["config_version"] = config["version"]
    version = guardar(OUTLINE, outline)

    huerfanos = [h for h in ledger_actual().get("hilos_abiertos", [])
                 if h.get("abierto_en") in fuera]
    for hilo in huerfanos:
        avisos.append(f"Hilo huerfano '{hilo.get('id')}': lo abria un capitulo eliminado. "
                      "Resolucion manual del autor.")

    print(f"outline.json sincronizado con config version {config['version']} "
          f"(outline version {version}).")
    for linea in cambios + avisos:
        print(f"  - {linea}")
    if not cambios and not avisos:
        print("  - sin cambios.")
    return 0


def cmd_marcar(args: argparse.Namespace) -> int:
    if args.estado not in ESTADOS:
        fallo(f"estado invalido '{args.estado}'. Validos: {', '.join(ESTADOS)}")
    outline = outline_actual()
    cap = capitulo_de(outline, args.n)
    if cap.get("estado") == "consolidado" and args.estado != "consolidado":
        print(f"Aviso: el cap {args.n} estaba consolidado; se devuelve a '{args.estado}' "
              "por decision explicita (RM-02).")
    cap["estado"] = args.estado
    if args.iteraciones is not None:
        cap["iteraciones"] = args.iteraciones
    version = guardar(OUTLINE, outline)
    print(f"cap {args.n:02d} -> {args.estado} (outline version {version}, "
          f"iteraciones={cap.get('iteraciones', 0)})")
    return 0


def cmd_capitulo(args: argparse.Namespace) -> int:
    n = args.n
    config = leer_json(CONFIG)
    outline = outline_actual()
    cap = capitulo_de(outline, n)

    # INV-05: orden estricto.
    previos = [c for c in outline["capitulos"] if c["n"] < n and c.get("estado") != "consolidado"]
    if previos:
        fallo(f"INV-05: los capitulos {[c['n'] for c in previos]} no estan consolidados. "
              f"El orden es estricto; consolidar el cap {n} ahora romperia el ledger.")

    texto_path = MANUSCRITO / f"cap-{n:02d}.md"
    if not texto_path.exists():
        fallo(f"no existe manuscript/cap-{n:02d}.md")
    texto = texto_path.read_text(encoding="utf-8")

    objetivo, tolerancia, unidad = objetivo_de(config, n)
    medido = contar_lineas(texto) if unidad == "lineas" else contar_palabras(texto)
    if abs(medido - objetivo) > tolerancia:
        fallo(f"el cap {n} mide {medido} {unidad} y el objetivo es {objetivo} "
              f"(tolerancia {tolerancia}). No se consolida.")

    parrafos_obj, por_parrafo = estructura_de(config, n)
    if parrafos_obj is not None:
        reparto = [len(p) for p in parrafos_capitulo(texto)]
        esperado = [por_parrafo] * parrafos_obj if por_parrafo else None
        if len(reparto) != parrafos_obj or (esperado and reparto != esperado):
            fallo(f"el cap {n} no respeta la estructura exigida: {parrafos_obj} parrafos"
                  + (f" de {por_parrafo} lineas" if por_parrafo else "")
                  + f". Reparto leido: {reparto}. No se consolida.")

    review_path = REVIEWS / f"cap-{n:02d}.json"
    if not review_path.exists():
        fallo(f"INV-01: no hay revision en reviews/cap-{n:02d}.json. Ningun capitulo entra "
              "en memoria sin revision aprobada.")
    review = leer_json(review_path)

    ok, motivo = aprobado(review)
    if not ok:
        fallo(f"D1 rechaza el cap {n}: {motivo}. No se consolida.")

    iteracion = args.iteracion if args.iteracion is not None else review.get("iteracion", 1)
    if iteracion > MAX_ITER:
        fallo(f"INV-02: iteracion {iteracion} supera el maximo de {MAX_ITER}.")

    ledger = ledger_actual()
    hechos = review.get("hechos_nuevos") or []
    avisos = aplicar_hechos(ledger, n, hechos, cap.get("contiene_combate", False))
    version_ledger = guardar(LEDGER, ledger)

    bible = cargar(BIBLE, {"version": 0})
    cap["estado"] = "consolidado"
    cap["iteraciones"] = iteracion
    cap["consolidado_en"] = {
        "iteracion": iteracion,
        "media": review.get("media"),
        "bible_version": bible.get("version"),
        "ledger_version": version_ledger,
        "resumen": args.resumen or cap.get("resumen") or review.get("resumen", ""),
    }
    if args.resumen:
        cap["resumen"] = args.resumen
    version_outline = guardar(OUTLINE, outline)

    traza({"evento": "consolidacion", "capitulo": n, "iteracion": iteracion,
           "media": review.get("media"), "outline_version": version_outline,
           "ledger_version": version_ledger, "ok": True})

    print(f"cap-{n:02d} consolidado (iteracion {iteracion}, {motivo}).")
    print(f"  outline.json version {version_outline}, ledger.json version {version_ledger}")
    for aviso in avisos:
        print(f"  aviso: {aviso}")
    print(f"  commit sugerido: cap-{n:02d}: consolidado (iteracion {iteracion}, "
          f"media {review.get('media')})")
    return 0


def main() -> int:
    MEMORIA.mkdir(parents=True, exist_ok=True)
    parser = argparse.ArgumentParser(description="Escritura en la memoria de MyStoryMaker")
    sub = parser.add_subparsers(dest="cmd", required=True)

    sub.add_parser("estado").set_defaults(func=cmd_estado)

    p = sub.add_parser("sembrar-bible"); p.add_argument("fichero")
    p.set_defaults(func=cmd_sembrar_bible)

    p = sub.add_parser("sembrar-outline"); p.add_argument("fichero")
    p.set_defaults(func=cmd_sembrar_outline)

    sub.add_parser("sincronizar").set_defaults(func=cmd_sincronizar)

    p = sub.add_parser("marcar")
    p.add_argument("n", type=int); p.add_argument("estado")
    p.add_argument("--iteraciones", type=int)
    p.set_defaults(func=cmd_marcar)

    p = sub.add_parser("capitulo")
    p.add_argument("n", type=int)
    p.add_argument("--iteracion", type=int)
    p.add_argument("--resumen", help="Resumen de una o dos frases para los capitulos siguientes")
    p.set_defaults(func=cmd_capitulo)

    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
