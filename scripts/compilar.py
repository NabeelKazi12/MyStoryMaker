"""Produce la novela y cierra N5.

Lanzado sin argumentos, esta es la unica orden que hace falta: pone a trabajar a
los agentes —investigacion, escaleta, escritor y revisor— hasta que no queda
capitulo pendiente, y despues compila `dist/manuscrito.md`. Cada paso es una
sesion headless de Claude Code (SPECS 2.6) que hace de orquestador; el trabajo
que ya este hecho no se repite, asi que relanzarlo continua donde se quedo.

Condiciones de salida de N5 (SPECS 10 e INV-10): sin hilos abiertos en el
ledger, record coherente con la suma de combates, sin marcadores de trabajo,
extension total igual a la declarada en config/capitulos.json. La aprobacion
final del autor es humana y este script no la suple: se limita a dejar el
entregable en un estado en el que esa aprobacion sea posible.

    python scripts/compilar.py                # produce la novela y compila
    python scripts/compilar.py --solo-compilar # compila lo ya consolidado
    python scripts/compilar.py --verificar     # solo comprueba, no escribe
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _comun import (CONFIG, DIST, LEDGER, MANUSCRITO, MARCADORES, OUTLINE, contar_lineas,
                    contar_palabras, leer_json, parrafos_capitulo)


def verificar() -> tuple[list[str], list[str], dict]:
    problemas: list[str] = []
    avisos: list[str] = []

    config = leer_json(CONFIG)
    if not OUTLINE.exists():
        return ["memory/outline.json no existe: no hay nada que compilar."], [], {}
    outline = leer_json(OUTLINE)
    if not outline.get("capitulos"):
        # Sin escaleta sembrada no procede hablar de extension ni de sincronizacion:
        # el problema no es que el plan se haya desviado, es que N2 no ha corrido.
        return ([
            "la escaleta no esta sembrada: memory/outline.json no tiene capitulos. "
            "No es un desajuste con config/capitulos.json, asi que 'sincronizar' no lo "
            "arregla. Ejecuta N2 con '/novela preparar' y persiste su plan con "
            "'python scripts/consolidar.py sembrar-outline <fichero>'."
        ], [], {})
    ledger = leer_json(LEDGER) if LEDGER.exists() else {}
    unidad = config["extension"]["unidad"]

    capitulos = sorted(outline.get("capitulos", []), key=lambda c: c["n"])
    if len(capitulos) != len(config["capitulos"]):
        problemas.append(
            f"INV-10: outline.json tiene {len(capitulos)} capitulos y config "
            f"{len(config['capitulos'])}. Sincroniza antes de compilar."
        )

    sin_consolidar = [c["n"] for c in capitulos if c.get("estado") != "consolidado"]
    if sin_consolidar:
        problemas.append(f"quedan capitulos sin consolidar: {sin_consolidar} (D2 no ha cerrado).")

    total = 0
    textos: dict[int, str] = {}
    for cap in capitulos:
        ruta = MANUSCRITO / f"cap-{cap['n']:02d}.md"
        if not ruta.exists():
            problemas.append(f"falta manuscript/cap-{cap['n']:02d}.md")
            continue
        texto = ruta.read_text(encoding="utf-8")
        textos[cap["n"]] = texto
        total += contar_lineas(texto) if unidad == "lineas" else contar_palabras(texto)
        limpio = re.sub(r"<!--.*?-->", "", texto, flags=re.DOTALL)
        marcador = MARCADORES.search(limpio)
        if marcador:
            problemas.append(
                f"cap-{cap['n']:02d}.md conserva un marcador de trabajo: '{marcador.group(0)}'"
            )

    objetivo = (config["extension"].get("lineas_totales_objetivo") if unidad == "lineas"
                else config["extension"].get("palabras_totales_objetivo"))
    tolerancia = (config["extension"].get("tolerancia_total_lineas", 0) if unidad == "lineas"
                  else round((objetivo or 0) * float(
                      config["extension"].get("tolerancia_total_pct", 0)) / 100))
    if objetivo is not None and abs(total - objetivo) > int(tolerancia or 0):
        problemas.append(
            f"INV-10: el manuscrito mide {total} {unidad} y el objetivo es {objetivo} "
            f"(tolerancia {tolerancia})."
        )

    # Hilos abiertos. Un hilo incumple la condicion de salida cuando debia haberse
    # cerrado dentro del plan: su 'cerrar_antes_de' cae en un capitulo que existe, o
    # no declara plazo y por tanto vence al final. Un hilo que vence en un capitulo
    # que el plan no llega a tener no es un fallo del manuscrito sino una consecuencia
    # de donde el autor ha puesto el limite, y se avisa sin bloquear.
    ultimo = max((c["n"] for c in config["capitulos"]), default=0)
    vencidos, fuera_de_plan = [], []
    for hilo in ledger.get("hilos_abiertos") or []:
        plazo = hilo.get("cerrar_antes_de")
        (fuera_de_plan if isinstance(plazo, int) and plazo > ultimo else vencidos).append(hilo)

    def describir(hilos: list) -> str:
        return ", ".join(f"{h.get('id')} ({h.get('descripcion', '')[:40]})" for h in hilos)

    if vencidos:
        problemas.append(
            "hilos que el plan tenia que cerrar y siguen abiertos: " + describir(vencidos)
        )
    if fuera_de_plan:
        avisos.append(
            f"{len(fuera_de_plan)} hilos quedan abiertos porque vencian despues del capitulo "
            f"{ultimo}, que es el ultimo del plan: {describir(fuera_de_plan)}. "
            "El manuscrito se cierra con ellos pendientes; si no es lo que quieres, amplia "
            "config/capitulos.json o pide que se cierren en el capitulo final."
        )

    record = ledger.get("record") or {}
    combates = ledger.get("combates") or []
    suma = (record.get("victorias", 0) + record.get("derrotas", 0) + record.get("empates", 0))
    if suma != len(combates):
        problemas.append(
            f"INV-04: el record suma {suma} combates y el ledger registra {len(combates)}."
        )
    planificados = sum(1 for c in config["capitulos"] if c.get("contiene_combate"))
    if len(combates) != planificados:
        avisos.append(
            f"el plan declara {planificados} capitulos con combate y el ledger guarda "
            f"{len(combates)} combates."
        )

    contexto = {"config": config, "outline": outline, "ledger": ledger,
                "textos": textos, "total": total, "unidad": unidad}
    return problemas, avisos, contexto


def compilar(contexto: dict) -> Path:
    config, outline = contexto["config"], contexto["outline"]
    partes = [f"# {config.get('titulo_trabajo', 'Manuscrito')}", ""]
    for cap in sorted(outline["capitulos"], key=lambda c: c["n"]):
        texto = contexto["textos"][cap["n"]]
        titulo = cap.get("titulo") or f"Capitulo {cap['n']}"
        partes.append(f"## {cap['n']}. {titulo}")
        partes.append("")
        for parrafo in parrafos_capitulo(texto):
            # Se conserva el reparto en parrafos con el que se escribio el capitulo:
            # dentro del parrafo, una linea por renglon; entre parrafos, linea en blanco.
            partes.extend(parrafo)
            partes.append("")

    DIST.mkdir(parents=True, exist_ok=True)
    destino = DIST / "manuscrito.md"
    destino.write_text("\n".join(partes).rstrip() + "\n", encoding="utf-8", newline="\n")
    return destino


def main() -> int:
    solo_compilar = "--solo-compilar" in sys.argv or "--verificar" in sys.argv

    if not solo_compilar:
        # Validar el plan antes de gastar un token: producir contra una
        # configuracion invalida es tirar el trabajo de los cuatro agentes.
        from validar_capitulos import validar
        errores = validar(leer_json(CONFIG))
        if errores:
            print("RM-03 - config/capitulos.json no valida:", file=sys.stderr)
            for e in errores:
                print(f"  - {e}", file=sys.stderr)
            return 1

        from pipeline import PasoFallido, producir
        try:
            producir()
        except PasoFallido as exc:
            print(f"\nLa produccion se detiene: {exc}", file=sys.stderr)
            return 1

    problemas, avisos, contexto = verificar()
    for aviso in avisos:
        print(f"aviso: {aviso}")
    if problemas:
        print("N5 no se cierra. Condiciones de salida incumplidas:", file=sys.stderr)
        for p in problemas:
            print(f"  - {p}", file=sys.stderr)
        return 1

    if "--verificar" in sys.argv:
        print(f"Verificacion OK: {contexto['total']} {contexto['unidad']} listos para compilar.")
        return 0

    destino = compilar(contexto)
    print(f"\ndist/{destino.name} escrito: {contexto['total']} "
          f"{contexto['unidad']} en {len(contexto['textos'])} capitulos.")
    print("Falta la aprobacion explicita del autor (SPECS 10). El sistema no la da por si mismo.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
