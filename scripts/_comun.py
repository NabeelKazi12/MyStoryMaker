"""Utilidades compartidas por los scripts del harness.

Sin dependencias externas a proposito: los hooks se ejecutan en el entorno del
autor y una instalacion fallida de paquetes convertiria un guardian en un
fallo silencioso.
"""
from __future__ import annotations

import json
import os
import re
import sys
import tempfile
from pathlib import Path

# La consola de Windows va en cp1252 y lo que se imprime aqui —la salida de una
# sesion headless, el titulo de un capitulo, el motivo de un hook— trae flechas,
# comillas tipograficas y guiones largos. Sin esto, un solo caracter fuera de la
# tabla lanza UnicodeEncodeError: en `compilar.py` eso aborta la produccion justo
# despues de haberla pagado, con el capitulo ya consolidado en disco y N5 sin
# correr. Se conserva la codificacion de la consola y solo se relaja el error,
# asi que un caracter raro sale como '?' en vez de tirar el proceso.
for _flujo in (sys.stdout, sys.stderr):
    if hasattr(_flujo, "reconfigure"):
        try:
            _flujo.reconfigure(errors="replace")
        except (ValueError, OSError):
            pass

RAIZ = Path(__file__).resolve().parent.parent

CONFIG = RAIZ / "config" / "capitulos.json"
MEMORIA = RAIZ / "memory"
BIBLE = MEMORIA / "bible.json"
LEDGER = MEMORIA / "ledger.json"
OUTLINE = MEMORIA / "outline.json"
MANUSCRITO = RAIZ / "manuscript"
RESEARCH = RAIZ / "research"
REVIEWS = RAIZ / "reviews"
LOGS = RAIZ / "logs"
DIST = RAIZ / "dist"

ESTADOS = ("pendiente", "en_revision", "escalado", "consolidado")
MAX_ITER = 3

# Marcadores de trabajo prohibidos en el manuscrito final (§10, CA-5).
#
# Los marcadores en ingles van en MAYUSCULAS y con limite de palabra, y eso no es
# cosmetico: con IGNORECASE, `TODO` casaba con la palabra espanola «todo» —y con
# «todos», y con «todo el gimnasio»—, asi que cualquier capitulo escrito en
# castellano normal era rechazado por el hook. Costo una reparacion en el cap 3
# antes de verse. Un marcador de trabajo real se escribe TODO, no todo.
MARCADORES = re.compile(
    r"\[[^\]]*\]"                            # corchetes: [pendiente], [nombre?]
    r"|\bTODO\b|\bTBD\b|\bFIXME\b|\bXXX\b"   # solo en mayusculas
    r"|(?i:\bLOREM\b|<[^>]*PENDIENTE[^>]*>)"
)


def leer_json(ruta: Path) -> dict:
    with open(ruta, encoding="utf-8") as fh:
        return json.load(fh)


def escribir_json_atomico(ruta: Path, datos: dict) -> None:
    """Escritura atomica: fichero temporal en el mismo directorio y renombrado.

    Es lo que exige §11 de SPECS para toda escritura en memoria.
    """
    ruta.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=str(ruta.parent), prefix=f".{ruta.name}.", suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as fh:
            json.dump(datos, fh, ensure_ascii=False, indent=2)
            fh.write("\n")
        os.replace(tmp, ruta)
    except BaseException:
        if os.path.exists(tmp):
            os.unlink(tmp)
        raise


def parrafos_capitulo(texto: str) -> list[list[str]]:
    """Parrafos del cuerpo: bloques separados por una linea en blanco.

    Un parrafo es una lista de lineas no vacias. El titulo y los comentarios
    HTML que el orquestador adjunta al consolidar no cuentan.
    """
    texto = re.sub(r"<!--.*?-->", "", texto, flags=re.DOTALL)
    parrafos: list[list[str]] = []
    actual: list[str] = []
    for linea in texto.splitlines():
        limpia = linea.strip()
        if not limpia:
            if actual:
                parrafos.append(actual)
                actual = []
            continue
        if limpia.startswith("#"):
            if actual:
                parrafos.append(actual)
                actual = []
            continue
        actual.append(limpia)
    if actual:
        parrafos.append(actual)
    return parrafos


def cuerpo_capitulo(texto: str) -> list[str]:
    """Lineas no vacias del cuerpo, excluyendo el titulo (§12.1).

    Se descartan tambien los bloques de metadatos en HTML comment que el
    orquestador adjunta al consolidar, para que no cuenten como prosa.
    """
    texto = re.sub(r"<!--.*?-->", "", texto, flags=re.DOTALL)
    lineas = []
    for linea in texto.splitlines():
        limpia = linea.strip()
        if not limpia:
            continue
        if limpia.startswith("#"):
            continue
        lineas.append(limpia)
    return lineas


def contar_lineas(texto: str) -> int:
    return len(cuerpo_capitulo(texto))


def contar_palabras(texto: str) -> int:
    return sum(len(linea.split()) for linea in cuerpo_capitulo(texto))


def objetivo_de(config: dict, n: int) -> tuple[int, int, str]:
    """Devuelve (objetivo, tolerancia, unidad) para el capitulo n."""
    unidad = config["extension"]["unidad"]
    campo = "lineas_objetivo" if unidad == "lineas" else "palabras_objetivo"
    cap = next((c for c in config["capitulos"] if c["n"] == n), None)
    if cap is None:
        raise KeyError(f"El capitulo {n} no existe en config/capitulos.json")
    objetivo = cap.get(campo, config.get("defaults", {}).get(campo))
    if objetivo is None:
        raise KeyError(f"El capitulo {n} no declara {campo} ni hay valor en defaults")
    ext = config["extension"]
    if unidad == "lineas":
        tolerancia = int(ext.get("tolerancia_capitulo_lineas", 0))
    else:
        tolerancia = round(objetivo * float(ext.get("tolerancia_capitulo_pct", 0)) / 100)
    return int(objetivo), int(tolerancia), unidad


def estructura_de(config: dict, n: int) -> tuple[int | None, int | None]:
    """Devuelve (parrafos_objetivo, lineas_por_parrafo) para el capitulo n.

    Ambos pueden ser None: la estructura interna del capitulo es opcional. Si
    se declara, deja de bastar con que el total de lineas cuadre y el capitulo
    tiene que venir repartido en parrafos exactos.
    """
    cap = next((c for c in config["capitulos"] if c["n"] == n), {})
    defaults = config.get("defaults", {})
    parrafos = cap.get("parrafos_objetivo", defaults.get("parrafos_objetivo"))
    por_parrafo = cap.get("lineas_por_parrafo", defaults.get("lineas_por_parrafo"))
    return parrafos, por_parrafo


def leer_evento_hook() -> dict:
    """Payload JSON que Claude Code entrega al hook por stdin."""
    try:
        crudo = sys.stdin.read()
    except Exception:
        return {}
    if not crudo.strip():
        return {}
    try:
        return json.loads(crudo)
    except json.JSONDecodeError:
        return {}


def ruta_afectada(evento: dict) -> Path | None:
    entrada = evento.get("tool_input") or {}
    for clave in ("file_path", "path", "notebook_path"):
        valor = entrada.get(clave)
        if valor:
            return Path(valor)
    return None


def bajo(ruta: Path, directorio: Path) -> bool:
    try:
        Path(ruta).resolve().relative_to(directorio.resolve())
        return True
    except (ValueError, OSError):
        return False


def bloquear(mensaje: str) -> None:
    """Rechaza el paso: codigo 2 devuelve el motivo al agente (no al usuario)."""
    print(mensaje, file=sys.stderr)
    sys.exit(2)
