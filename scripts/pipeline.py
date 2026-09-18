"""Lanzador de los agentes: convierte el ciclo de SPECS en pasos ejecutables.

`compilar.py` lo usa para que una sola orden ponga a trabajar a los agentes y
termine con el manuscrito en `dist/`. Cada paso es una sesion headless de Claude
Code —el modo de ejecucion de SPECS 2.6— que hace de orquestador, llama a los
subagentes de `.claude/agents/` y persiste su resultado por las vias de siempre:
`manuscript/`, `reviews/` y `scripts/consolidar.py`.

El lanzador no escribe prosa, no puntua y no toca `memory/`. Solo decide que
paso falta, lo lanza y comprueba el estado despues. Toda la logica de D1, el
maximo de iteraciones y el orden estricto sigue viviendo donde vivia.

Cada paso comprueba primero si su trabajo ya esta hecho, asi que interrumpir la
ejecucion y volver a lanzarla continua donde se quedo.
"""
from __future__ import annotations

import shutil
import subprocess
import sys
import threading
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import langfuse_cliente as lf
from _comun import CONFIG, MANUSCRITO, OUTLINE, RAIZ, RESEARCH, leer_json

# Herramientas que la sesion headless necesita. El workspace puede no estar
# marcado como de confianza, en cuyo caso Claude Code ignora la lista `allow`
# de .claude/settings.json; pasarlas por linea de ordenes evita depender de eso.
HERRAMIENTAS = [
    "Bash(python scripts/consolidar.py:*)",
    "Bash(python scripts/compilar.py:*)",
    "Bash(python scripts/validar_capitulos.py:*)",
    "Read", "Glob", "Grep", "Write", "Edit", "WebSearch", "WebFetch", "Task", "Skill",
]

AUTORIZACION = (
    "Autorizacion del autor para esta ejecucion: ha pedido expresamente que los agentes "
    "trabajen y produzcan la novela con la configuracion vigente de config/capitulos.json, "
    "y ha lanzado el script que te invoca. Esa instruccion cubre la aprobacion de la "
    "escaleta y la del manuscrito final para esta configuracion, y nada mas. No supongas "
    "ninguna otra aprobacion: si el brief esta incompleto o un capitulo escala tras tres "
    "iteraciones, detente y deja el motivo por escrito."
)

TIMEOUT_PREPARAR = 1800
TIMEOUT_CAPITULO = 1800


class PasoFallido(RuntimeError):
    pass


def orden_claude() -> list[str]:
    ruta = shutil.which("claude")
    if not ruta:
        raise PasoFallido(
            "No encuentro el ejecutable 'claude' en el PATH. El lanzador necesita Claude "
            "Code instalado para poder abrir las sesiones de cada paso."
        )
    # En Windows, `claude` en el PATH suele ser un .cmd que reenvia con %*, y esa
    # reexpansion destroza los argumentos con parentesis y comodines: las reglas
    # de --allowed-tools llegan rotas y la sesion se queda sin permisos. Se busca
    # el ejecutable real que el .cmd invoca y se llama directamente.
    if ruta.lower().endswith((".cmd", ".bat")):
        real = (Path(ruta).parent / "node_modules" / "@anthropic-ai" / "claude-code"
                / "bin" / "claude.exe")
        if real.exists():
            return [str(real)]
        return ["cmd", "/c", ruta]
    return [ruta]


def lanzar(etiqueta: str, prompt: str, timeout: int, *, on_linea=None,
           registrar_proceso=None) -> str:
    """Abre una sesion headless y devuelve su salida final.

    `on_linea`, si se pasa, se llama con cada linea de salida segun se produce
    (lo usa la UI para mostrar el log en vivo; sin el, el comportamiento -y la
    salida por consola- es identico al de antes). `registrar_proceso` recibe el
    Popen nada mas arrancar, para que quien lanzo el paso pueda cancelarlo.
    """
    orden = orden_claude() + [
        "-p", prompt,
        "--permission-mode", "acceptEdits",
        "--allowed-tools", *HERRAMIENTAS,
        "--max-turns", "200",
    ]
    print(f"\n>>> {etiqueta}", flush=True)
    print(f"    sesion headless en curso (limite {timeout // 60} min)...", flush=True)
    inicio = time.time()
    proceso = subprocess.Popen(orden, cwd=str(RAIZ), stdout=subprocess.PIPE,
                                stderr=subprocess.STDOUT, text=True, encoding="utf-8",
                                errors="replace", bufsize=1)
    if registrar_proceso:
        registrar_proceso(proceso)

    agotado = threading.Event()
    temporizador = threading.Timer(timeout, lambda: (agotado.set(), proceso.kill()))
    temporizador.daemon = True
    temporizador.start()

    lineas: list[str] = []
    try:
        for linea in proceso.stdout:
            linea = linea.rstrip("\n")
            lineas.append(linea)
            if on_linea:
                on_linea(linea)
    finally:
        proceso.wait()
        temporizador.cancel()

    minutos = (time.time() - inicio) / 60
    salida = "\n".join(lineas).strip()
    if agotado.is_set():
        raise PasoFallido(
            f"{etiqueta}: la sesion ha superado {timeout // 60} minutos y se ha cortado. "
            "Lo ya escrito en disco se conserva; vuelve a lanzar el script y continuara "
            "desde donde se quedo."
        )
    if proceso.returncode != 0:
        detalle = salida[-800:] or "sin salida"
        raise PasoFallido(f"{etiqueta}: la sesion ha terminado con error.\n{detalle}")
    print(f"    hecho en {minutos:.1f} min", flush=True)
    enlace = traza_del_paso()
    if enlace:
        print(f"    traza: {enlace}", flush=True)
    if salida:
        print("    " + "\n    ".join(salida.splitlines()[-12:]), flush=True)
    return salida


def traza_del_paso() -> str:
    """Enlace a la traza de la sesion headless que acaba de terminar.

    Cada paso abre su propia sesion, y por tanto su propia traza. El hook de
    SessionStart deja apuntado cual es; aqui solo se traduce a URL para no tener
    que ir a buscarla a Langfuse a mano.
    """
    try:
        if not lf.activo():
            return ""
        sesion = lf.sesion_actual()
        return lf.enlace(sesion["trace_id"]) if sesion and sesion.get("trace_id") else ""
    except Exception:
        return ""


# --------------------------------------------------------------------------- pasos

def hay_investigacion() -> bool:
    return len(list(RESEARCH.glob("*.md"))) >= 6


def escaleta_sembrada() -> bool:
    if not OUTLINE.exists():
        return False
    return bool(leer_json(OUTLINE).get("capitulos"))


def estado_capitulo(n: int) -> str:
    for cap in leer_json(OUTLINE).get("capitulos", []):
        if cap.get("n") == n:
            return cap.get("estado", "pendiente")
    return "ausente"


def paso_preparar(*, on_linea=None, registrar_proceso=None) -> None:
    if escaleta_sembrada():
        print(">>> N1 y N2 ya estan hechos: escaleta sembrada.", flush=True)
        return

    investigacion = (
        "research/ ya tiene los seis temas cubiertos: NO vuelvas a lanzar el subagente "
        "'investigacion', leelos y pasa directamente a N2."
        if hay_investigacion() else
        "research/ esta vacio: lanza el subagente 'investigacion' (N1) y cubre sus seis "
        "temas obligatorios antes de N2."
    )

    lanzar("N1 y N2 - investigacion y escaleta", f"""/novela preparar

{AUTORIZACION}

{investigacion}

Cuando el subagente 'escaleta' (N2) te devuelva la biblia y el plan, guardalos en dos
ficheros temporales y persistelos:
    python scripts/consolidar.py sembrar-bible <fichero>
    python scripts/consolidar.py sembrar-outline <fichero>

Detente ahi: el capitulo lo escribe una ejecucion posterior. Termina con dos lineas
diciendo que has sembrado y con que titulo y objetivo queda el capitulo.""",
           TIMEOUT_PREPARAR, on_linea=on_linea, registrar_proceso=registrar_proceso)

    if not escaleta_sembrada():
        raise PasoFallido(
            "N2 ha terminado pero memory/outline.json sigue sin capitulos. Revisa la salida "
            "del paso: lo mas probable es que consolidar.py rechazara el plan (no coincide "
            "con config/capitulos.json, falta muestra de voz o algun capitulo sin objetivo)."
        )


PENDIENTES = RAIZ / "ui" / "pendientes"
BIBLE_PENDIENTE = PENDIENTES / "bible.json"
OUTLINE_PENDIENTE = PENDIENTES / "outline.json"


def escaleta_pendiente_de_aprobacion() -> bool:
    return BIBLE_PENDIENTE.exists() and OUTLINE_PENDIENTE.exists()


def paso_preparar_ui(indicaciones: str | None = None, *, on_linea=None,
                      registrar_proceso=None) -> None:
    """Variante interactiva de N1/N2: genera el plan y se detiene sin persistir.

    A diferencia de `paso_preparar` (pensado para `compilar.py`, sin nadie
    delante a quien preguntar), aqui la aprobacion del autor es real: el paso
    deja la biblia y el plan en `ui/pendientes/` -fuera de `memory/`, que el
    hook `bloquear_memoria.py` protege- para que la UI se los muestre antes de
    sembrarlos con `consolidar.py`.
    """
    if escaleta_sembrada():
        print(">>> N1 y N2 ya estan hechos: escaleta sembrada.", flush=True)
        return

    investigacion = (
        "research/ ya tiene los seis temas cubiertos: NO vuelvas a lanzar el subagente "
        "'investigacion', leelos y pasa directamente a N2."
        if hay_investigacion() else
        "research/ esta vacio: lanza el subagente 'investigacion' (N1) y cubre sus seis "
        "temas obligatorios antes de N2."
    )
    reintento = (
        f"""

Este plan es un reintento: el autor rechazo la version anterior con este motivo,
atiendelo antes que nada:
{indicaciones}"""
        if indicaciones else ""
    )

    PENDIENTES.mkdir(parents=True, exist_ok=True)
    for ruta in (BIBLE_PENDIENTE, OUTLINE_PENDIENTE):
        ruta.unlink(missing_ok=True)

    lanzar("N1 y N2 - investigacion y escaleta (pendiente de aprobacion)", f"""/novela preparar

Autorizacion del autor para esta ejecucion: ha pedido expresamente que se investigue
y se prepare la escaleta con la configuracion vigente de config/capitulos.json, y ha
lanzado esta sesion desde su panel de control. Esa instruccion NO cubre la aprobacion
de la escaleta: eso lo decide el autor a mano en cuanto la vea, en un paso posterior.

{investigacion}
{reintento}

Cuando el subagente 'escaleta' (N2) te devuelva la biblia y el plan, escribelos tal
cual en estos dos ficheros (creando la carpeta si hace falta) y PARA AHI, sin llamar a
consolidar.py y sin escribir nada en memory/:
    ui/pendientes/bible.json
    ui/pendientes/outline.json

No sembres nada. Termina con dos o tres lineas resumiendo el plan (numero de
capitulos y de que trata cada uno) para que el autor decida sin tener que abrir los
ficheros.""",
           TIMEOUT_PREPARAR, on_linea=on_linea, registrar_proceso=registrar_proceso)

    if not escaleta_pendiente_de_aprobacion():
        raise PasoFallido(
            "N2 ha terminado pero no ha dejado ui/pendientes/bible.json y "
            "ui/pendientes/outline.json. Revisa el log del paso."
        )


def paso_capitulo(n: int, *, indicaciones: str | None = None, on_linea=None,
                   registrar_proceso=None) -> None:
    estado = estado_capitulo(n)
    if estado == "consolidado":
        print(f">>> cap {n:02d} ya consolidado.", flush=True)
        return
    if estado == "escalado" and not indicaciones:
        raise PasoFallido(
            f"El cap {n} esta escalado: agoto las tres iteraciones y la decision es del autor "
            f"(aceptar, reescribir con indicaciones nuevas o cambiar la escaleta). Mira "
            f"manuscript/cap-{n:02d}.md y reviews/cap-{n:02d}.json."
        )

    config = leer_json(CONFIG)
    cap = next((c for c in config["capitulos"] if c["n"] == n), {})
    defaults = config.get("defaults", {})
    parrafos = cap.get("parrafos_objetivo", defaults.get("parrafos_objetivo"))
    por_parrafo = cap.get("lineas_por_parrafo", defaults.get("lineas_por_parrafo"))
    forma = (f"{parrafos} parrafos de exactamente {por_parrafo} lineas cada uno"
             if parrafos and por_parrafo else
             f"{cap.get('lineas_objetivo', defaults.get('lineas_objetivo'))} lineas")

    indicaciones_bloque = (
        f"""

El autor ha escalado este capitulo antes y ahora pide reescribirlo con estas
indicaciones nuevas; atiendelas en la reescritura:
{indicaciones}"""
        if indicaciones else ""
    )

    lanzar(f"N3, N4 y D1 - capitulo {n:02d}", f"""/novela capitulo {n}

{AUTORIZACION}

La forma exigida es {forma}. Es igualdad exacta, sin tolerancia: un hook la comprueba al
guardar en manuscript/ y su rechazo consume una de las tres iteraciones.
{indicaciones_bloque}

Recuerda el ciclo: subagente 'escritor' -> guardas manuscript/cap-{n:02d}.md -> subagente
'revisor' en contexto limpio -> guardas reviews/cap-{n:02d}.json -> recalculas D1 tu mismo
-> si aprueba, 'python scripts/consolidar.py capitulo {n} --iteracion K --resumen "..."'.

Si al guardar el capitulo el hook lo rechaza por extension o por forma, NO es un problema
de permisos ni un fallo del sistema: es la condicion de salida de N3 funcionando. El fichero
queda en disco con la version rechazada; vuelve a lanzar al Escritor pasandole el mensaje
del hook, sobrescribe el mismo fichero y sigue. Ese rechazo consume iteracion.

No escribas ni retoques la prosa tu: si el texto no vale, vuelve al Escritor.
No termines el paso a medias: o el capitulo queda consolidado con consolidar.py, o queda
marcado como escalado tras agotar las tres iteraciones. Cualquier otro final es un paso
fallido, y dejarlo asi obliga a repetir el trabajo.

Termina con una linea: capitulo, iteraciones gastadas y media de la revision.""",
           TIMEOUT_CAPITULO, on_linea=on_linea, registrar_proceso=registrar_proceso)

    estado = estado_capitulo(n)
    if estado == "escalado":
        raise PasoFallido(
            f"El cap {n} ha escalado tras tres iteraciones. El sistema se detiene aqui por "
            "diseno: la decision es del autor."
        )
    if estado != "consolidado":
        raise PasoFallido(
            f"El cap {n} ha terminado el paso en estado '{estado}'. No se ha consolidado, asi "
            f"que no entra en el manuscrito. Revisa reviews/cap-{n:02d}.json y la salida del paso."
        )


def producir(*, on_linea=None, registrar_proceso=None) -> None:
    """Recorre el circuito hasta que no quede capitulo pendiente."""
    paso_preparar(on_linea=on_linea, registrar_proceso=registrar_proceso)
    for cap in sorted(leer_json(OUTLINE).get("capitulos", []), key=lambda c: c["n"]):
        paso_capitulo(cap["n"], on_linea=on_linea, registrar_proceso=registrar_proceso)
