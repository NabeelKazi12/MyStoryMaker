"""Precomputa el contexto exacto de un subagente (N3 y N4).

El orquestador pegaba rutas en el prompt del Task y cada subagente se abria sus
ficheros por su cuenta: el Escritor cuatro `Read`, el Revisor nueve. Medido sobre
el ciclo del capitulo 2, esas lecturas eran el 72% del coste del Revisor, y no
por lo que ocupan sino por como se pagan: cada resultado de herramienta anade un
segmento de cache nuevo, que se factura a 1,25 mientras que leer de cache cuesta
0,1. Explorar sale mas caro que recibir.

Aqui se arma ese mismo material una sola vez, en un proceso local que no cuesta
tokens, y ya recortado a lo que el capitulo N necesita: la ficha de N y no el
plan entero, las lesiones abiertas en N y no el ledger completo, el resumen
operativo de la investigacion y no los seis ficheros. Con la novela de 12 lineas
la diferencia es comoda; con cuarenta capitulos es la diferencia entre un coste
lineal y uno cuadratico, porque hoy cada capitulo hace leer el plan de todos.

El contrato con los agentes es que esto es **autoritativo**: lo que no esta en el
bloque no hace falta para el paso. Un subagente que se pone a leer ficheros ha
encontrado un hueco aqui, y eso se arregla en este script, no abriendo la mano
en su prompt.

El payload **no se imprime**: se deja en `.contexto/` y por stdout sale solo la
ruta. Esa distincion es el punto entero del script. El orquestador es quien lo
invoca, y todo lo que pasa por su stdout entra en su ventana y se vuelve a pagar
en cada turno que le queda por delante —eran 31 en el ciclo del capitulo 2—,
asi que imprimir aqui los 28 KB del contexto del Escritor costaria mas que las
lecturas que este script viene a evitar. El orquestador pasa la ruta, el
subagente hace un unico `Read`, y el material solo existe en la ventana que lo
necesita.

Subcomandos
-----------
    contexto.py N --para escritor [--iteracion K]  Material de N3
    contexto.py N --para revisor                   Material de N4
    contexto.py N --para reparacion                Solo texto y conteo (fallo de forma)

Opciones
--------
    --stdout    Imprime el payload en vez de escribirlo. Para depurar a mano;
                nunca desde el orquestador.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _comun import (BIBLE, CONFIG, LEDGER, MANUSCRITO, OUTLINE, RAIZ, RESEARCH, REVIEWS,
                    cuerpo_capitulo, estructura_de, leer_json, objetivo_de,
                    parrafos_capitulo)

# Los payloads son material derivado: se regeneran de memory/ y config/ en
# cualquier momento, asi que no se versionan.
DESTINO = RAIZ / ".contexto"

# Cuantos capitulos anteriores van completos. El resto, solo su resumen. Es la
# restriccion deliberada de SPECS: la continuidad la sostiene el ledger, no que
# el Escritor se relea la novela entera.
CAPITULOS_COMPLETOS = 2

# El tema de tecnica es el unico que va entero, y solo si hay combate. Los demas
# entran por su resumen operativo, que es justo la seccion que los ficheros de
# research/ traen escrita para esto.
TEMA_COMBATE = "01-tecnica-zurdo.md"


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


def ficha_de(outline: dict, n: int) -> dict:
    cap = next((c for c in outline.get("capitulos", []) if c.get("n") == n), None)
    if cap is None:
        fallo(f"El capitulo {n} no esta en memory/outline.json. Siembra la escaleta antes.")
    return cap


def bloque_json(titulo: str, datos) -> str:
    return f"### {titulo}\n\n```json\n{json.dumps(datos, ensure_ascii=False, indent=2)}\n```\n"


# --------------------------------------------------------------------------- rodajas

def voz_y_reglas(bible: dict) -> dict:
    """La biblia sin lo que no gobierna la escritura de un capitulo.

    Fuera van 'temas' —material de la escaleta, ya cuajado en la ficha— y los
    metadatos de version. Lo demas se queda entero: la voz y los vetos no se
    recortan sin cambiar la novela.
    """
    return {
        "voz": bible.get("voz", {}),
        "personajes": bible.get("personajes", []),
        "reglas_mundo": bible.get("reglas_mundo", []),
        "consecuencias_zurda": bible.get("consecuencias_zurda", []),
        "vetos": bible.get("vetos", []),
    }


def ledger_para(ledger: dict, n: int) -> dict:
    """Lo del ledger que puede contradecir al capitulo N, y nada mas.

    El criterio es el del Revisor: una lesion importa si sigue abierta y toca
    este capitulo; un hilo importa si aun no ha vencido. Lo ya saldado no puede
    generar contradiccion y solo ocupa contexto.
    """
    lesiones = [l for l in ledger.get("lesiones", [])
                if l.get("estado") == "abierto"
                and (not l.get("capitulos_afectados") or n in l.get("capitulos_afectados", []))]
    hilos = [h for h in ledger.get("hilos_abiertos", [])
             if h.get("cerrar_antes_de") is None or int(h.get("cerrar_antes_de", 0)) >= n]
    return {
        "record": ledger.get("record", {}),
        "combates": ledger.get("combates", []),
        "lesiones_abiertas_en_este_capitulo": lesiones,
        "hilos_vivos": hilos,
        "cronologia": ledger.get("cronologia", [])[-6:],
        "nota": ("Esta es la verdad sobre hechos duros. Ya viene filtrada para el capitulo "
                 f"{n}: lo saldado o cerrado no aparece porque no puede contradecirlo."),
    }


def resumen_operativo(ruta: Path) -> str:
    """La seccion '## Resumen operativo' de un fichero de research/."""
    try:
        texto = ruta.read_text(encoding="utf-8")
    except OSError:
        return ""
    m = re.search(r"^##\s+Resumen operativo\s*$(.*?)(?=^##\s|\Z)", texto,
                  re.MULTILINE | re.DOTALL)
    cuerpo = (m.group(1) if m else texto).strip()
    titulo = texto.splitlines()[0].lstrip("# ").strip() if texto else ruta.stem
    return f"**{titulo}** — {cuerpo}" if cuerpo else ""


def investigacion(contiene_combate: bool) -> str:
    """Resumen operativo de los seis temas; el de tecnica entero si hay combate."""
    partes = []
    for ruta in sorted(RESEARCH.glob("*.md")):
        if contiene_combate and ruta.name == TEMA_COMBATE:
            continue
        resumen = resumen_operativo(ruta)
        if resumen:
            partes.append(resumen)
    bloque = "### Investigacion (resumen operativo)\n\n" + "\n\n".join(partes) + "\n"
    if contiene_combate:
        completo = RESEARCH / TEMA_COMBATE
        if completo.exists():
            bloque += ("\n### Tecnica del zurdo — material completo (capitulo con combate)\n\n"
                       + completo.read_text(encoding="utf-8").strip() + "\n")
    else:
        bloque += ("\nEste capitulo no lleva combate: el material completo de tecnica no se "
                   "inyecta. Si lo necesitas, es que la ficha y el plan no coinciden; dilo "
                   "en `tensiones`.\n")
    return bloque


def anteriores(outline: dict, n: int) -> str:
    """Resumen de todos los capitulos previos y texto completo de los dos ultimos."""
    previos = sorted([c for c in outline.get("capitulos", [])
                      if c.get("n", 0) < n and c.get("estado") == "consolidado"],
                     key=lambda c: c["n"])
    if not previos:
        return ("### Capitulos anteriores\n\nNinguno: este es el primer capitulo "
                "consolidado de la novela.\n")
    lineas = ["### Capitulos anteriores (resumen)\n"]
    for cap in previos:
        lineas.append(f"- **Cap {cap['n']:02d} · {cap.get('titulo', '')}** — "
                      f"{cap.get('resumen') or 'sin resumen consolidado'}")
    bloque = "\n".join(lineas) + "\n"

    completos = previos[-CAPITULOS_COMPLETOS:]
    if completos:
        rotulo = ("del capitulo inmediatamente anterior" if len(completos) == 1
                  else f"de los {len(completos)} capitulos inmediatamente anteriores")
        bloque += f"\n### Texto completo {rotulo}\n"
        for cap in completos:
            ruta = MANUSCRITO / f"cap-{cap['n']:02d}.md"
            if ruta.exists():
                bloque += f"\n```markdown\n{ruta.read_text(encoding='utf-8').strip()}\n```\n"
    return bloque


def forma_exigida(config: dict, n: int) -> dict:
    objetivo, tolerancia, unidad = objetivo_de(config, n)
    parrafos, por_parrafo = estructura_de(config, n)
    cap = next((c for c in config["capitulos"] if c["n"] == n), {})
    return {
        "unidad": unidad,
        f"{unidad}_objetivo": objetivo,
        "tolerancia": tolerancia,
        "parrafos_objetivo": parrafos,
        "lineas_por_parrafo": por_parrafo,
        "contiene_combate": bool(cap.get("contiene_combate")),
        "reparto_exacto": ([por_parrafo] * parrafos) if parrafos and por_parrafo else None,
    }


def notas_de_revision(n: int) -> str:
    ruta = REVIEWS / f"cap-{n:02d}.json"
    if not ruta.exists():
        return ""
    try:
        review = leer_json(ruta)
    except Exception:
        return ""
    recorte = {
        "iteracion_revisada": review.get("iteracion"),
        "puntuaciones": review.get("puntuaciones", {}),
        "media": review.get("media"),
        "notas": review.get("notas", []),
        "contradicciones": review.get("contradicciones", []),
    }
    return ("### Notas del Revisor — esto es una reescritura\n\n"
            "Corrige lo senalado y **solo** lo senalado. Para cada nota, di en "
            "`notas_atendidas` que hiciste con ella.\n\n"
            + f"```json\n{json.dumps(recorte, ensure_ascii=False, indent=2)}\n```\n")


# --------------------------------------------------------------------------- salidas

def para_escritor(n: int, iteracion: int) -> str:
    config = leer_json(CONFIG)
    outline = cargar(OUTLINE, {"capitulos": []})
    bible = cargar(BIBLE, {})
    ledger = cargar(LEDGER, {})
    ficha = ficha_de(outline, n)
    forma = forma_exigida(config, n)

    partes = [
        f"## Contexto de N3 para el capitulo {n} (iteracion {iteracion})\n",
        "Este bloque es todo lo que necesitas y es autoritativo. **No abras ficheros.** "
        "Si echas algo en falta, escribe el capitulo igual y dilo en `tensiones`: el hueco "
        "se arregla en `scripts/contexto.py`, no leyendo por tu cuenta.\n",
        bloque_json("Ficha del capitulo (escaleta viva)", ficha),
        bloque_json("Forma exigida — exacta, tolerancia incluida", forma),
        bloque_json("Voz, personajes, reglas y vetos", voz_y_reglas(bible)),
        bloque_json(f"Ledger filtrado para el capitulo {n}", ledger_para(ledger, n)),
        anteriores(outline, n),
        investigacion(forma["contiene_combate"]),
    ]
    if iteracion > 1:
        partes.append(notas_de_revision(n))
    return "\n".join(partes)


def para_revisor(n: int) -> str:
    config = leer_json(CONFIG)
    outline = cargar(OUTLINE, {"capitulos": []})
    bible = cargar(BIBLE, {})
    ledger = cargar(LEDGER, {})
    ficha = ficha_de(outline, n)
    forma = forma_exigida(config, n)

    ruta = MANUSCRITO / f"cap-{n:02d}.md"
    if not ruta.exists():
        fallo(f"No existe {ruta.relative_to(RESEARCH.parent)}. N3 no ha corrido todavia.")
    texto = ruta.read_text(encoding="utf-8")

    # El conteo va hecho: que el Revisor juzgue la extension no exige que la
    # cuente, y una cifra calculada no se equivoca ni gasta razonamiento.
    medido = {
        "lineas": len(cuerpo_capitulo(texto)),
        "parrafos": [len(p) for p in parrafos_capitulo(texto)],
        "coincide_con_lo_exigido": (
            len(cuerpo_capitulo(texto)) == forma[f"{forma['unidad']}_objetivo"]
            and (forma["reparto_exacto"] is None
                 or [len(p) for p in parrafos_capitulo(texto)] == forma["reparto_exacto"])
        ),
    }

    return "\n".join([
        f"## Contexto de N4 para el capitulo {n}\n",
        "Este bloque es todo lo que necesitas y es autoritativo. **No abras ficheros.** "
        "El ledger ya viene filtrado a lo que puede contradecir a este capitulo y la "
        "extension ya viene contada: juzga con esto.\n",
        f"### Capitulo a evaluar\n\n```markdown\n{texto.strip()}\n```\n",
        bloque_json("Extension medida (no la recuentes)", medido),
        bloque_json("Forma exigida", forma),
        bloque_json("Que se suponia que tenia que hacer este capitulo", ficha),
        bloque_json("Voz, personajes, reglas y vetos", voz_y_reglas(bible)),
        bloque_json(f"Ledger filtrado para el capitulo {n}", ledger_para(ledger, n)),
        investigacion(forma["contiene_combate"]),
    ])


def para_reparacion(n: int) -> str:
    """Relanzamiento barato tras un rechazo de forma del hook.

    Un fallo de conteo no es un fallo de calidad y no deberia costar lo que
    cuesta reconstruir todo el contexto de N3. Aqui va lo justo: el texto, lo que
    se pidio y en que se ha desviado.
    """
    config = leer_json(CONFIG)
    forma = forma_exigida(config, n)
    ruta = MANUSCRITO / f"cap-{n:02d}.md"
    if not ruta.exists():
        fallo(f"No existe manuscript/cap-{n:02d}.md: no hay nada que reparar.")
    texto = ruta.read_text(encoding="utf-8")
    reparto = [len(p) for p in parrafos_capitulo(texto)]
    medido = {"lineas": len(cuerpo_capitulo(texto)), "parrafos": reparto}

    return "\n".join([
        f"## Reparacion de forma del capitulo {n}\n",
        "El hook `validar_extension.py` ha rechazado el capitulo por su forma, no por su "
        "contenido. **Ajusta el conteo y no toques nada mas**: misma historia, mismos "
        "hechos, mismo titulo. Devuelve solo el capitulo corregido, sin bloque JSON.\n",
        f"### Texto actual\n\n```markdown\n{texto.strip()}\n```\n",
        bloque_json("Lo que tiene", medido),
        bloque_json("Lo que debe tener", forma),
    ])


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Arma el contexto exacto de un subagente sin que tenga que explorar")
    parser.add_argument("n", type=int, help="Numero de capitulo")
    parser.add_argument("--para", required=True,
                        choices=("escritor", "revisor", "reparacion"))
    parser.add_argument("--iteracion", type=int, default=1)
    parser.add_argument("--stdout", action="store_true",
                        help="Imprime el payload en vez de escribirlo. Para depurar a mano: "
                             "invocado asi desde el orquestador cuesta mas de lo que ahorra.")
    args = parser.parse_args()

    if args.para == "escritor":
        payload = para_escritor(args.n, args.iteracion)
    elif args.para == "revisor":
        payload = para_revisor(args.n)
    else:
        payload = para_reparacion(args.n)

    if args.stdout:
        print(payload)
        return 0

    DESTINO.mkdir(parents=True, exist_ok=True)
    ruta = DESTINO / f"cap-{args.n:02d}-{args.para}.md"
    ruta.write_text(payload, encoding="utf-8", newline="\n")
    # Lo unico que entra en la ventana del orquestador: donde esta y cuanto pesa.
    print(f"{ruta}")
    print(f"  {len(payload):,} caracteres. Pasale esta ruta al subagente; no la abras tu.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
