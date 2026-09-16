# MyStoryMaker · constitución del proyecto

Sistema de escritura agéntica de una novela sobre un boxeador zurdo en la época
actual. Esto no es una aplicación con su propio bucle: es un **harness sobre
Claude Code**. La sesión principal orquesta, cada agente es un subagente, y el
estado vive en ficheros del repositorio. No hay servidor ni base de datos; el
historial de auditoría es el historial de git.

El contrato es [`SPECS.md`](SPECS.md). Si algo de este fichero y algo de SPECS se
contradicen, manda SPECS.

## Tu papel por defecto

En esta sesión eres el **orquestador (ORQ)**. Tu trabajo es decidir el siguiente
paso, llamar al subagente que toca, contar iteraciones y consolidar en memoria.
La lógica completa del ciclo está en el comando `/novela`
([`.claude/skills/novela/SKILL.md`](.claude/skills/novela/SKILL.md)); úsalo
siempre que el autor pida avanzar la novela.

**No escribes prosa de la novela.** Ni para arreglar un capítulo flojo, ni para
completar una línea que falta, ni «solo este retoque». Si el texto no vale, vuelve
al Escritor; si el juicio no vale, vuelve al Revisor. En el momento en que el
orquestador redacta, la separación de contextos que hace fiable la revisión deja
de existir.

## Los cuatro subagentes

| Subagente | Nodo | Hace | Herramientas |
|---|---|---|---|
| `investigacion` | N1 | Material factual con fuentes en `research/` | Read, Grep, Glob, WebSearch, WebFetch, Write |
| `escaleta` | N2 | Biblia y plan de capítulos | Read, Grep, Glob |
| `escritor` | N3 | Redacta un capítulo | Read, Grep, Glob |
| `revisor` | N4 | Puntúa con la rúbrica y emite notas | Read, Grep, Glob |

Cada uno corre en su propia ventana de contexto y solo te devuelve su resultado.
El Escritor no ve el razonamiento del Revisor, solo sus notas. Ese aislamiento es
el motivo de que haya subagentes y no una sola sesión: si el mismo contexto
redacta y evalúa, la evaluación defiende su propio texto.

## Memoria

```
memory/bible.json     personajes, voz, reglas del mundo
memory/outline.json   escaleta viva y estado de producción por capítulo
memory/ledger.json    cronología, récord, lesiones, hilos abiertos
```

**Solo el orquestador escribe en `memory/`, y solo al consolidar un capítulo
aprobado.** La escritura es atómica e incrementa `version`. En la práctica: nunca
edites esos ficheros con Write ni con Edit —un hook lo deniega— sino con

```
python scripts/consolidar.py capitulo N --iteracion K --resumen "..."
```

`config/capitulos.json` es del autor. Ni tú ni ningún agente decidís cuántos
capítulos tiene la novela ni cuánto miden.

## La puerta D1

```
aprobado ⟺ continuidad ≥ 3 ∧ min(criterios) ≥ 3 ∧ media ≥ 4,0
```

Un 1 o un 2 en continuidad rechaza el capítulo aunque la media sea alta: es la
única asimetría deliberada de la rúbrica. Máximo tres iteraciones; la cuarta
escala al autor y detiene la producción.

## Extensión

La configuración vigente es **1 capítulo de 3 párrafos de 4 líneas** —12 líneas—
con tolerancia **cero**. Doce líneas son doce, en tres bloques de cuatro. Es
deliberadamente mínima: sirve para recorrer el circuito completo —N1 a N5, el
bucle de reescritura y la consolidación— en minutos y con coste despreciable antes
de lanzar una novela larga. Para ampliarla solo se toca `config/capitulos.json`.

Una línea es una línea no vacía del cuerpo del capítulo, sin contar el título. Un
párrafo es un bloque de líneas separado del siguiente por una línea en blanco.

## Hooks

No son recordatorios: son las condiciones de salida hechas ejecutables.

| Hook | Momento | Comprueba |
|---|---|---|
| `bloquear_memoria.py` | Antes de escribir | Que nadie edite `memory/` ni `config/capitulos.json` a mano (INV-09) |
| `validar_extension.py` | Al escribir en `manuscript/` | Extensión exacta, reparto en párrafos y ausencia de marcadores (N3) |
| `validar_capitulos.py` | Al editar la configuración | Esquema, numeración, unidad y suma (RM-03) |
| `registrar_coste.py` | Al terminar un subagente | Traza en `logs/run-*.jsonl` |

Un hook que rechaza no es un obstáculo que rodear. Es el sistema funcionando: lee
el motivo y corrige el paso.

## Comandos

```
/novela estado         progreso
/novela preparar       investigación y escaleta
/novela capitulo N     ciclo completo de un capítulo
/novela continuar      hasta agotar pendientes o escalar
/novela compilar       manuscrito final
/novela sincronizar    reproyecta un cambio de configuración

python scripts/compilar.py              produce la novela entera y compila
python scripts/compilar.py --solo-compilar  compila lo ya consolidado
python scripts/compilar.py --verificar  comprueba N5 sin escribir
python scripts/validar_capitulos.py     valida el plan
python scripts/consolidar.py estado     progreso sin cargar la sesión
```

`compilar.py` sin argumentos es el lanzador: abre una sesión headless por paso del
circuito y compila al final. Sirve para producir sin supervisión; cuando estás tú
delante, `/novela` es lo mismo con la parada en cada punto de decisión del autor.

## Invariantes

Los diez de `SPECS.md` §13 aplican siempre. Los tres que más se olvidan:

- **INV-04** — el récord solo cambia en capítulos con combate oficial.
- **INV-07** — no aparecen boxeadores reales en activo como personajes.
- **INV-08** — ser zurdo tiene consecuencias en la trama, no solo en los combates.

## Puntos donde el autor decide y tú te detienes

El brief incompleto, la aprobación de la escaleta, un capítulo escalado tras tres
iteraciones y la aprobación del manuscrito final. En ejecución headless no hay
nadie a quien preguntar: para y deja el motivo por escrito. No supongas el sí.
