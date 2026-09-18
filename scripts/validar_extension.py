"""Hook PostToolUse: comprueba la extension de un capitulo recien escrito.

Condicion de salida de N3 (SPECS 6): con unidad 'lineas' y tolerancia 0,
cuatro lineas son cuatro, ni tres ni cinco. Se valida DESPUES de la escritura,
no a mitad: bloquear al agente mientras redacta produce peores resultados que
dejarle terminar y rechazar despues (SPECS 2.5).

Comprueba tambien que no queden marcadores de trabajo en el texto.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from datetime import datetime, timezone

from _comun import (CONFIG, ITERACIONES, MANUSCRITO, MARCADORES, REVIEWS, bajo, bloquear,
                    contar_lineas, contar_palabras, cuerpo_capitulo, estructura_de,
                    leer_evento_hook, leer_json, objetivo_de, parrafos_capitulo,
                    ruta_afectada)

PATRON = re.compile(r"^cap-(\d{2,})\.md$")
PATRON_REVIEW = re.compile(r"^cap-(\d{2,})\.json$")


def archivar(ruta: Path) -> None:
    """Guarda una copia de lo que se acaba de escribir, antes de juzgarlo.

    `manuscript/cap-NN.md` y `reviews/cap-NN.json` se sobrescriben en cada
    iteracion, asi que hasta ahora la unica version que sobrevivia era la ultima:
    comparar la iteracion 1 con la 2 era imposible porque la 1 ya no existia en
    ninguna parte. Aqui se apila cada version segun se escribe, incluidas las que
    este mismo hook va a rechazar a continuacion -que son justamente las que
    explican por que hubo una segunda-.

    Es material derivado y ruidoso, asi que vive fuera de git. Y no puede hacer
    fallar el hook: si archivar no funciona, la condicion de salida de N3 sigue
    siendo la que es.
    """
    try:
        nombre = ruta.name
        casa = PATRON.match(nombre) or PATRON_REVIEW.match(nombre)
        if not casa:
            return
        tipo = "texto" if nombre.endswith(".md") else "review"
        destino = ITERACIONES / f"cap-{int(casa.group(1)):02d}"
        destino.mkdir(parents=True, exist_ok=True)
        marca = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S")
        copia = destino / f"{marca}-{tipo}{ruta.suffix}"
        contenido = ruta.read_bytes()
        # Sin duplicados: reguardar un fichero identico al anterior solo ensucia
        # la comparacion con versiones que no cambiaron nada.
        previas = sorted(destino.glob(f"*-{tipo}{ruta.suffix}"))
        if previas and previas[-1].read_bytes() == contenido:
            return
        copia.write_bytes(contenido)
    except Exception:
        pass


def main() -> int:
    evento = leer_evento_hook()
    ruta = ruta_afectada(evento)
    if ruta is None:
        return 0
    if bajo(ruta, REVIEWS):
        archivar(Path(ruta))
        return 0
    if not bajo(ruta, MANUSCRITO):
        return 0
    archivar(Path(ruta))

    casa = PATRON.match(Path(ruta).name)
    if not casa:
        bloquear(
            f"Nombre invalido en manuscript/: '{Path(ruta).name}'. "
            "El formato obligatorio es cap-NN.md (SPECS 11)."
        )
        return 2

    n = int(casa.group(1))
    try:
        texto = Path(ruta).read_text(encoding="utf-8")
    except OSError as exc:
        bloquear(f"No se ha podido releer {ruta}: {exc}")
        return 2

    try:
        config = leer_json(CONFIG)
        objetivo, tolerancia, unidad = objetivo_de(config, n)
    except Exception as exc:
        bloquear(f"No se puede validar la extension del cap {n:02d}: {exc}")
        return 2

    medido = contar_lineas(texto) if unidad == "lineas" else contar_palabras(texto)
    if abs(medido - objetivo) > tolerancia:
        lineas = cuerpo_capitulo(texto)
        muestra = "\n".join(f"    {i + 1}. {l[:70]}" for i, l in enumerate(lineas[:12]))
        exigencia = (
            f"exactamente {objetivo}" if tolerancia == 0
            else f"entre {objetivo - tolerancia} y {objetivo + tolerancia}"
        )
        bloquear(
            f"N3 - cap-{n:02d}.md fuera de extension: {medido} {unidad}, se exige {exigencia}.\n"
            "Cuentan las lineas no vacias del cuerpo, sin el titulo ni los comentarios HTML.\n"
            f"Cuerpo leido:\n{muestra}\n"
            "Reescribe el capitulo con la extension exacta antes de pasarlo al Revisor."
        )
        return 2

    # Estructura interna: parrafos exactos y lineas exactas dentro de cada uno.
    parrafos_obj, por_parrafo = estructura_de(config, n)
    if parrafos_obj is not None:
        parrafos = parrafos_capitulo(texto)
        reparto = [len(p) for p in parrafos]
        if len(parrafos) != parrafos_obj:
            bloquear(
                f"N3 - cap-{n:02d}.md tiene {len(parrafos)} parrafos y se exigen "
                f"{parrafos_obj}. Reparto leido: {reparto}.\n"
                "Un parrafo es un bloque separado del siguiente por una linea en blanco."
            )
            return 2
        if por_parrafo is not None:
            malos = [i + 1 for i, p in enumerate(parrafos) if len(p) != por_parrafo]
            if malos:
                bloquear(
                    f"N3 - cap-{n:02d}.md: los parrafos {malos} no tienen exactamente "
                    f"{por_parrafo} lineas. Reparto leido: {reparto}.\n"
                    f"Se exigen {parrafos_obj} parrafos de {por_parrafo} lineas cada uno; "
                    "dentro de un parrafo cada linea va en su propio renglon, sin dejar "
                    "lineas en blanco entre ellas."
                )
                return 2

    marcador = MARCADORES.search(re.sub(r"<!--.*?-->", "", texto, flags=re.DOTALL))
    if marcador:
        bloquear(
            f"N3 - cap-{n:02d}.md contiene un marcador de trabajo: '{marcador.group(0)}'.\n"
            "El capitulo debe entregarse limpio, sin corchetes, TODO, TBD ni notas del agente."
        )
        return 2

    forma = ""
    if parrafos_obj is not None:
        forma = f", {parrafos_obj} parrafos de {por_parrafo}" if por_parrafo else f", {parrafos_obj} parrafos"
    print(f"cap-{n:02d}.md OK: {medido} {unidad} (objetivo {objetivo}, "
          f"tolerancia {tolerancia}{forma})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
