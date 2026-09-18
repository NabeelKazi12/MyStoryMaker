# MyStoryMaker

Escritura agéntica de una novela sobre un boxeador zurdo en la época actual.

No es una aplicación: es un **harness sobre Claude Code**. La sesión principal
orquesta, cada agente es un subagente con su propia ventana de contexto, y el
estado vive en ficheros del repositorio. Sin servidor, sin base de datos; la
auditoría es el historial de git.

```
N0 brief → N1 investigación → N2 escaleta → N3 escritor → N4 revisor → D1 ¿aprobado?
                                              ↑ no, iter<3 ┘   │ sí
                                                               ↓
                                          D2 ¿quedan capítulos? → N5 manuscrito
```

## Empezar

1. Rellena los seis campos de [`brief.md`](brief.md). El sistema no inventa
   valores por defecto y no arranca sin ellos.
2. Ajusta [`config/capitulos.json`](config/capitulos.json) si quieres otra
   extensión. Lo vigente es **1 capítulo de 3 párrafos de 4 líneas**: una prueba
   mínima que recorre el circuito completo en minutos.
3. En Claude Code, dentro del repositorio:

```
/novela preparar      investigación y escaleta, hasta la aprobación del autor
/novela continuar     produce capítulos hasta agotar pendientes o escalar
/novela estado        progreso
/novela compilar      manuscrito final en dist/
```

Sin sesión interactiva —lotes largos, CI o simplemente dejarlo trabajando— una
sola orden hace todo el recorrido y deja el manuscrito en `dist/`:

```
python scripts/compilar.py
```

Abre una sesión headless por paso, no repite el trabajo ya hecho y se detiene con
el motivo por escrito en cuanto el sistema necesita una decisión del autor.

## Panel de control

Para gobernar el harness sin terminal ni sesión de Claude Code delante: un
servidor local que envuelve `scripts/` en una página con el progreso, botones
para lanzar cada paso como un job en segundo plano con log en vivo, y pantallas
para decidir en los cuatro puntos que son del autor (brief incompleto, escaleta,
capítulo escalado y manuscrito final).

```
pip install -r requirements.txt
python ui/server.py
```

Abre `http://127.0.0.1:8765`. Es la única parte del proyecto con una dependencia
externa (FastAPI); `scripts/` sigue sin necesitar nada fuera de la librería
estándar. El plan de N2 pendiente de aprobar se guarda en `ui/pendientes/` —
fuera de `memory/`, que el hook `bloquear_memoria.py` protege— y la aprobación
del manuscrito final en `ui/estado_ui.json`; ninguno de los dos se versiona.

## Estructura

| Ruta | Qué hay |
|---|---|
| [`SPECS.md`](SPECS.md) | El contrato. Manda sobre todo lo demás |
| [`CLAUDE.md`](CLAUDE.md) | Constitución de la sesión: el orquestador |
| [`.claude/agents/`](.claude/agents/) | Los cuatro subagentes: investigación, escaleta, escritor, revisor |
| [`.claude/skills/novela/`](.claude/skills/novela/SKILL.md) | El comando `/novela` |
| [`.claude/settings.json`](.claude/settings.json) | Hooks: las condiciones de salida hechas ejecutables |
| [`scripts/`](scripts/) | Validadores, escritura atómica en memoria, lanzador y compilación |
| [`scripts/contexto.py`](scripts/contexto.py) | Precomputa el contexto de cada subagente: lo recibe hecho en vez de explorarlo |
| [`config/`](config/) | Plan de capítulos del autor y su esquema |
| `memory/` | Biblia, escaleta viva y ledger de continuidad |
| `research/` `manuscript/` `reviews/` `logs/` `dist/` | Producción |
| [`specs/`](specs/README.md) | Especificación funcional y técnica |
| [`docs/operacion.md`](docs/operacion.md) | Hooks, observabilidad y economía de tokens del circuito |
| [`docs/diagrama.drawio`](docs/diagrama.drawio) | El diagrama de referencia |

## Las tres reglas que sostienen el diseño

- **El revisor no escribe lo que juzga.** Contextos separados: si el mismo
  contexto redacta y evalúa, la evaluación defiende su propio texto.
- **Solo el orquestador escribe en `memory/`,** y solo al consolidar un capítulo
  aprobado. Un hook deniega cualquier otra vía.
- **Un nodo sin condición de salida verificable no se implementa.** Si no se puede
  comprobar con un script, no es una condición: es un deseo.
