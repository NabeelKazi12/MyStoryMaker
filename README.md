# MyStoryMaker

Sistema multiagente que escribe una novela personalizada de regalo manteniendo coherencia
verificable: lo que la novela afirma se guarda como canon normalizado, se comprueba con
validadores deterministas y se verifica formalmente antes de publicarse.

| | |
| --- | --- |
| **Backend** | Python 3.12 · FastAPI · SQLite · Alembic |
| **Frontend** | Vite · React · TypeScript |
| **Modelo** | `claude-haiku-4-5` (D-17, `docs/architecture.md` §5.1) |
| **Verificación formal** | Lean 4 (la historia) · TLA+ con TLC (el harness) |
| **Observabilidad** | Langfuse, como vista; la fuente de verdad es SQLite |

---

## Cómo se arranca

```bash
# Backend
uv sync
uv run alembic upgrade head                      # crea el esquema
uv run uvicorn backend.api.main:app --reload     # API en :8000
uv run python -m backend.worker                  # worker de generación

# Frontend (lectura de la novela)
cd frontend && npm install
cd frontend && npm run dev                       # lectura en :5173
```

**No hace falta ninguna clave de API.** El worker escribe con Haiku a través de Claude Code
(`claude -p --model haiku`, sin herramientas) y reutiliza la sesión con la que Claude Code
ya está autenticado: basta con tenerlo instalado (`npm install -g @anthropic-ai/claude-code`)
y haber iniciado sesión una vez ejecutando `claude`. Si `claude` no está en el `PATH` del
worker, su ruta va en `MYSTORYMAKER_CLAUDE` (ver `.env.example`).

## Cómo se prueba todo junto

Dos terminales desde la raíz del repositorio. **No hace falta ninguna variable de
entorno**: sin ella se usa `mystorymaker.db`, que es la base por defecto.

```bash
# Terminal A — base de datos y semilla (solo la primera vez)
uv run alembic upgrade head
uv run python -m backend.store.semilla_demo

# Terminal A — API en :8000
uv run uvicorn backend.api.main:app --reload

# Terminal B — lectura en :5173
cd frontend
npm run dev
```

Los mismos comandos valen en PowerShell, salvo que el `cd frontend` va en su propia línea.

Si prefieres otra base, `MYSTORYMAKER_DB` la cambia —en PowerShell, `$env:MYSTORYMAKER_DB =
"otra.db"` en su propia línea antes del comando—, pero entonces hay que migrarla y sembrarla
con la variable puesta también. **Dos avisos que cuestan un rato si no se saben**: `--reload`
vigila el código y no la base, así que cambiar de base exige reiniciar la API; y SQLite
**crea** el fichero si no existe en vez de fallar, así que una ruta equivocada no da error,
da una base vacía. Cuando eso pasa, la API responde `503` diciendo exactamente eso.

Abre **http://localhost:5173**. Lo que se ve y qué demuestra cada cosa:

| Qué mirar | Qué demuestra |
| --- | --- |
| Portada con «Para Marta, que siempre vuelve al mar» | La dedicatoria sale del `Destinatario`, no de una plantilla |
| Índice con el capítulo 3 marcado como *cambiado* | La versión 2 sabe qué cambió respecto a la 1 |
| Ficha con Marta, El abuelo, Gijón y El espigón | Se genera de la story bible, no de una lista escrita a mano |
| Botón **pedir un cambio** en Marta | Avisa que se regenerarán los capítulos que usan ese hecho, y el aviso **no** se cierra solo |

Y desde otra terminal, la pieza que más cuesta ver en la pantalla:

```bash
# El perro sale en el capítulo 1 y en el 3: la respuesta trae esos dos, no los tres.
curl -X POST http://localhost:8000/novelas/vol-1/cambios -H "Content-Type: application/json" -d '{"hecho_id":"he-perro","descripcion":"el perro se llama Nala"}'

# La casa solo sale en el 1.
curl -X POST http://localhost:8000/novelas/vol-1/cambios -H "Content-Type: application/json" -d '{"hecho_id":"he-casa","descripcion":"la casa era azul"}'
```

El contrato completo, en http://localhost:8000/docs.

**«Escribir la novela»** encola la escritura y el worker la va redactando escena a escena
con Haiku; la lectura se actualiza sola. Cuando hay prosa aparece **«Descargar la novela
(PDF)»**, que sirve `GET /novelas/{id}/pdf`. Una novela de dos o tres capítulos tarda del
orden de cinco a diez minutos.

## Cómo se comprueba

```bash
uv run pytest                      # suite completa
uv run pytest -m invariants        # invariantes de dominio
uv run ruff check . && uv run ruff format --check .
uv run mypy backend/
cd frontend && npm run build && npm run lint

# Verificación formal (necesita sus toolchains)
cd lean && lake build              # invariantes de la cronología
cd tla && tlc Generacion.tla -config Generacion.cfg    # invariantes del harness
```

## El brief de ejemplo

El que genera `ejemplos/novela-ejemplo.pdf`:

```
nombre:     Marta
edad:       34
rasgos:     terca, nada sentimental
recuerdos:  el verano en que aprendió a nadar en Gijón
género:     memoria novelada
tono:       luminoso
extensión:  30.000 palabras
vetadas:    Ricardo
```

---

## Qué implementa cada acción de la especificación TLA+

`tla/Generacion.tla` modela el flujo como máquina de estados. Esta tabla es lo que RF-TLA-05
exige: **qué estado o transición del código implementa cada acción**. Si una fila deja de
ser cierta, la especificación ha dejado de describir el sistema y verificarla no dice nada.

| Acción TLA+ | Código que la implementa | Estado real |
| --- | --- | --- |
| `CerrarEncargo` | `backend/agents/entrevistador/entrevistador.py` → `construir_encargo` | Implementado |
| `Planificar` | `backend/agents/planner/planner.py` → `parsear_plan` | Implementado |
| `Escribir(c)` | `backend/worker/worker.py` → `Worker.ejecutar` | Implementado, con cliente de modelo falso |
| `ValidarBien(c)` | `backend/orchestrator/hooks.py` → `hook_de_capitulo` + `hook_de_policy` | Implementado |
| `ValidarMal(c)` | `backend/quality/guardarrail.py` → `Guardarrail.revisar` | Implementado |
| `AgotarReintentos(c)` | `LimiteDeReescriturasAgotado` en `guardarrail.py` | Implementado |
| `Publicar` | `backend/orchestrator/regeneracion.py` → `publicar_version` | Implementado |
| `PedirCambio(c)` | `capitulos_afectados` + `UsoDeHechos.capitulos_de` | Implementado |
| `Reanudar` | `backend/store/repositories.py` → `CheckpointDeCapitulos.siguiente` | Implementado |

Los cuatro invariantes de seguridad y la propiedad de *liveness* están en el mismo fichero,
con su configuración en `tla/Generacion.cfg` (modelo de 5 capítulos y 2 reintentos).

## Estructura

```
backend/
  domain/        ontología: canon, producción, especificación del encargo
  context/       presupuesto y ensamblado del PaqueteDeContexto
  quality/       verificadores, guardarraíl y validadores de personalización
  agents/        un módulo por rol, con prompts versionados
  store/         SQLite: único acceso a datos
  orchestrator/  planificación, estados, hooks, canonización, regeneración
  api/           FastAPI: rutas y SSE, sin lógica de dominio
  worker/        consumidor de la cola; aquí viven las llamadas al modelo
  observability/ trazas, spans y scores (vista, nunca fuente)
  formal/        generación del fichero Lean desde la story bible
  export/        exportación a PDF
frontend/        lectura de la novela: portada, índice, ficha y petición de cambio
lean/            invariantes de la cronología
tla/             especificación del harness y su configuración de TLC
docs/            arquitectura, definiciones, verificación y documentación de proceso
specs/           una spec por cambio
ejemplos/        la novela de ejemplo en PDF
```

## Documentación

| Documento | Qué responde |
| --- | --- |
| `docs/architecture.md` | Cómo está construido y por qué |
| `docs/definitions.md` | La ontología y los vocabularios cerrados |
| `docs/verification.md` | Qué método verifica cada cosa y quién bloquea |
| `docs/trade-offs.md` | Cada decisión con lo que se descartó |
| `docs/explainers.md` | Los conceptos del curso aplicados aquí |
| `docs/diagramas.md` | Harness, máquina de estados, esquema y validadores |
| `docs/evaluacion.md` | Los cinco briefs y qué cazó cada validador |
| `docs/red-team-log.md` | Casos adversariales, incluidos los que **no** se paran |
| `docs/registro-de-iteraciones.md` | Qué cambió, qué lo provocó y por qué |
| `AGENTS.md` | El contrato de los agentes y el proceso de cambio |
| `CLAUDE.md` | Convenciones, límites de módulo y comandos |

## Trabajo con Claude Code

- `CLAUDE.md` es el fichero de instrucciones del harness.
- `.claude/skills/` contiene las skills usadas, indexadas en `.claude/skills/SKILLS.md`.
- `.claude/mcp.json` configura el MCP de navegador (Playwright) con el que se verifica
  visualmente la lectura.
