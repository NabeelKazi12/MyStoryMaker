# CLAUDE.md

Instrucciones para agentes de código que trabajan en este repositorio.
Para el contrato de los agentes que **generan la novela**, ver `AGENTS.md`.

---

## 1. Qué es este proyecto

Un sistema multiagente que escribe novelas de 80.000–150.000 palabras manteniendo
coherencia verificable. El dominio está modelado como una ontología explícita: tres
planos (diegético, discursivo, producción) y tres capas transversales (especificación,
contexto, calidad).

El modelo completo está en `docs/definitions.md` y `docs/domain-knowledge.md`.
**Léelos antes de tocar cualquier cosa bajo `backend/domain/`.**

La tesis del proyecto: la calidad narrativa en texto largo no se consigue con mejores
prompts, sino con estado estructurado y validaciones ejecutables. Cualquier cambio que
mueva lógica de dominio hacia dentro de un prompt va en contra del diseño.

---

## 2. Decisiones técnicas

Stack fijado. Un cambio en esta tabla requiere un `RegistroDeDecision`.

| Capa | Decisión |
| --- | --- |
| Backend | FastAPI (Python) |
| Frontend | React |
| Persistencia | SQLite |
| Límite de contexto del modelo | 100.000 tokens |

Las tres subsecciones siguientes son las consecuencias que condicionan el diseño. No son
opcionales: cada una de estas elecciones cierra puertas que conviene no intentar abrir.

### 2.1 SQLite como grafo

No hay base de datos de grafos. El grafo del dominio se modela relacionalmente y las
consultas transitivas se hacen con CTEs recursivas:

- Grafo causal de `EventoNarrativo` (detección de ciclos, precedencia).
- Cierre de `deriva_de` en `UnidadDeContexto` (invalidación en cascada).
- Jerarquía espacial de `Lugar` (`contiene` / `contenido_en`).

Consecuencias operativas:

- **Activa WAL** (`journal_mode=WAL`) y `foreign_keys=ON` en cada conexión.
- **Un solo escritor.** SQLite serializa escrituras; el Orquestador es el único punto que
  las emite. Ningún agente escribe en paralelo sobre la misma revisión del canon.
- **Índices explícitos** sobre `(sujeto_id, predicado)` en `HECHO`, sobre
  `posicion_en_historia` en `EVENTO` y sobre `(conocedor_id, hecho_id)` en
  `ESTADO_CONOCIMIENTO`. Las validaciones de intervalos y de fugas epistémicas son las
  consultas más frecuentes del sistema.
- **Índice vectorial**: extensión `sqlite-vec` en el mismo fichero, o un fichero aparte.
  En cualquier caso, solo `backend/store/` conoce la diferencia.
- **El canon versionado no se copia entero** por revisión. Guarda eventos de cambio y
  reconstruye por revisión; una copia por revisión no escala a 40 capítulos.

SQLite es una elección razonable aquí porque el volumen es pequeño (decenas de miles de
filas) y el patrón es un solo autor. Si en el futuro hay varias novelas concurrentes en
el mismo proceso, ese es el momento de revisar la decisión, no antes.

### 2.2 Presupuesto de 100.000 tokens

El límite es un techo duro, no un objetivo. El `PaqueteDeContexto` de una escena debe
apuntar a **20.000–25.000 tokens**, con el resto como margen.

Reparto de referencia para una tarea de redacción:

| Componente | Tokens |
| --- | --- |
| Estático (premisa, contrato de estilo, políticas) | 2.000 |
| Estado del mundo (hechos vigentes filtrados) | 6.000 |
| Prosa literal de la escena anterior | 3.500 |
| Pirámide de resúmenes (parte, capítulo, escenas) | 4.000 |
| Voz (perfil global + idiolectos presentes) | 1.500 |
| Epistémico (lo que el POV sabe e ignora) | 2.000 |
| Promesas (siembras abiertas, motivos pendientes) | 1.000 |
| Instrucción (esqueleto de escena) | 1.000 |
| Margen de seguridad | 3.000 |
| **Total entrada** | **24.000** |
| Salida esperada | 3.000–4.000 |

Reglas que se derivan de esto:

- El ensamblador **cuenta tokens antes de llamar** y rechaza el paquete si excede su
  presupuesto. Nunca se trunca por la cola: truncar borra justo el final de la
  instrucción.
- Si un paquete no cabe, **se aprietan los filtros de `AlcanceDeRelevancia`**, no se sube
  el presupuesto. Subirlo esconde el síntoma de que la pirámide de resúmenes no está
  funcionando.
- El margen de 75.000 tokens libres existe para las tareas que sí necesitan más: revisión
  de capítulo completo, verificación de n-gramas contra varios capítulos, juicio a nivel
  de acto. No es espacio disponible para la redacción de escena.
- `PaqueteDeContexto` almacena el recuento real de tokens por componente. Es la métrica
  que dice si la compresión se está degradando a lo largo del libro.

Y una lectura del límite que no es evidente: **los 100.000 no son por petición, sino
tokens en vuelo simultáneos en todo el sistema** (`docs/architecture.md` §4.1, decisión
D-13). Lo hace cumplir un semáforo de crédito en el Orquestador, que reserva antes de
invocar y libera en toda ruta de salida. La consecuencia para quien escribe código: el
grado de paralelismo no es un parámetro libre, sale del crédito disponible.

### 2.3 FastAPI y React

**Backend.** La generación de un capítulo tarda minutos, no milisegundos. Nada de
request/response para tareas de generación:

- Endpoints de generación crean una `Tarea` y devuelven su id. `202 Accepted`.
- El progreso se transmite por SSE (`/tareas/{id}/eventos`). WebSocket solo si hace falta
  bidireccionalidad real.
- Un worker consume la cola. El proceso web no invoca modelos.
- Los modelos Pydantic son la frontera de serialización, **no las clases del dominio**.
  `backend/domain/` no importa FastAPI ni Pydantic.

**Frontend.** React sirve tres vistas, y ninguna lleva lógica de dominio:

- Editor de canon (entidades, hechos, línea temporal).
- Lector de borradores con diff entre versiones.
- Panel de defectos, juicios y estado de puertas.

Toda validación ocurre en el backend. Si el frontend necesita decidir si algo es válido,
llama a la API. Duplicar un invariante en JavaScript garantiza que las dos copias
divergirán.

---

## 3. Reglas no negociables

Estas no son preferencias de estilo. Romper cualquiera de ellas rompe el sistema.

### 3.1 El canon nunca se almacena como prosa

`Canon` contiene hechos, entidades, eventos y reglas normalizados. Nunca texto
narrativo. Si te ves tentado de guardar un párrafo "de contexto" en el canon, lo que
necesitas es una `UnidadDeContexto`, no un campo nuevo.

### 3.2 Ningún hecho es atemporal

Todo `Hecho` tiene `valido_desde` y `valido_hasta` apuntando a un `EventoNarrativo`,
no a una fecha. No añadas atributos estáticos a `Personaje` o `Lugar` para cosas que
pueden cambiar (ubicación, lealtad, salud, posesión, estado emocional). Eso es un
`Hecho` o un `EstadoDePersonaje`.

Excepción única: `descripcion_fisica` y otros atributos marcados `(C)` en el documento
de definiciones, que solo cambian por canonización.

### 3.3 El conocimiento es una relación, no un atributo

Quién sabe qué vive en `EstadoDeConocimiento(conocedor, hecho, estatus, adquirido_en)`.
Nunca como un array `conoce[]` en `Personaje`.

### 3.4 Separación de escritura por rol

Un agente escribe solo en las clases que `AGENTS.md` le asigna. En particular:

- El **Redactor** no escribe en el canon. Emite `hechos_nuevos_detectados` en el
  borrador; la canonización es un paso posterior y separado.
- El **Guardián de Continuidad** no escribe prosa. Solo emite `Defecto`.
- El **Juez** no escribe `Defecto`. Solo emite `Juicio`.

Si un PR permite que el mismo agente genere y valide el mismo artefacto, rechaza el
diseño: un modelo racionaliza sus propias incoherencias.

### 3.5 Toda generación lleva procedencia

Cada llamada a un modelo registra un `PaqueteDeContexto` con su `hash` y una
`Procedencia`. Sin esto, un fallo de coherencia no es reproducible. No añadas rutas
de generación que salten este registro, ni siquiera para scripts de prueba.

### 3.6 Solo lo determinista puede bloquear

Las verificaciones programáticas pueden fallar una `Puerta`. Los juicios de un juez LLM
solo penalizan. Nunca pongas un juez LLM en una puerta bloqueante: su puntuación varía
entre llamadas sobre el mismo texto y produce bucles caros.

### 3.7 Presupuesto de contexto constante

El `PaqueteDeContexto` de una escena debe tener tamaño aproximadamente constante en el
capítulo 3 y en el 40. Si un cambio hace que crezca con la longitud del libro, es un
bug, no una mejora de contexto.

---

## 4. Arquitectura y límites de módulos

```
backend/
  domain/        Clases de la ontología. Sin dependencias de infraestructura.
    diegetic/    Entidad, EventoNarrativo, Hecho, EstadoDeConocimiento, ReglaDelMundo
    discursive/  Escena, Capitulo, Hilo, ParSiembraPago, PerfilDeEstilo, Motivo
    production/  Tarea, Borrador, Critica, Puerta, Procedencia
    spec/        Brief, Restriccion, ContratoDeEstilo
  context/       Pirámide de resúmenes, AlcanceDeRelevancia, ensamblado de paquetes
  quality/       Verificadores programáticos, rúbricas, jueces, umbrales
  agents/        Un módulo por rol. Prompts versionados.
  store/         SQLite (fuente de verdad) + índice vectorial. Único acceso a datos.
  orchestrator/  Planificación, asignación, puertas, reintentos
  api/           FastAPI: rutas, esquemas Pydantic, SSE. Sin lógica de dominio.
  worker/        Consumidor de la cola de Tarea. Aquí viven las llamadas a modelos.
  migrations/    Esquema de SQLite, versionado y hacia delante.
frontend/        Vite + React. Editor de canon, lector de borradores, panel de defectos.
docs/            Ontología, arquitectura y reparto de la verificación.
specs/           Una spec por cambio: qué se cambia y por qué.
```

Reglas de dependencia:

- `domain/` no importa de ningún otro paquete. Ni del store, ni de agents, ni de
  FastAPI ni Pydantic.
- `quality/` importa de `domain/`, nunca de `agents/`.
- `agents/` no importa de `agents/`. La coordinación entre roles vive en
  `orchestrator/`.
- Solo `store/` habla con SQLite y con el índice vectorial.
- `api/` no invoca modelos. Encola tareas y lee estado; el trabajo ocurre en `worker/`.
- `frontend/` no contiene reglas de dominio. Ninguna, y nunca lee ficheros del
  sistema: todo lo que muestra lo pide al `backend/`.

### 4.1 Grafo vs. vectorial

- **Grafo**: hechos, eventos, estados, relaciones. Fuente única de verdad.
- **Vectorial**: prosa, para recuperar por similitud (cómo se describió antes un lugar,
  escenas de tono análogo, detectar una imagen ya usada).

**Nunca valides un hecho contra el índice vectorial.** La similitud semántica no
distingue entre lo que ocurrió y lo que casi ocurrió.

---

## 5. Convenciones de código

### 5.1 Nomenclatura del dominio

Los nombres de la ontología son vocabulario compartido con los documentos y con los
prompts. Úsalos literalmente, sin sinónimos:

| Usa | No uses |
| --- | --- |
| `EventoNarrativo` | `Event`, `PlotPoint`, `Beat` |
| `Hecho` | `Fact`, `Attribute`, `State` |
| `EstadoDeConocimiento` | `Knowledge`, `Awareness` |
| `ParSiembraPago` | `Setup`, `Foreshadowing`, `Payoff` |
| `PaqueteDeContexto` | `Prompt`, `ContextWindow` |
| `Borrador` | `Draft`, `Version`, `Text` |

Si necesitas un concepto que no está en la ontología, ese es el problema a resolver
primero: propón la clase en `docs/definitions.md` y déjalo registrado como
`RegistroDeDecision`. No lo introduzcas de tapadillo como un campo suelto.

### 5.2 Enumeraciones

Los vocabularios controlados están cerrados a propósito (ver el documento de
definiciones). Añadir un valor requiere un `RegistroDeDecision`. Una enumeración que
crece sin control vuelve a ser texto libre y ninguna regla es ya ejecutable.

### 5.3 Idioma

- Nombres de clases, campos y enumeraciones: español, igual que la ontología.
- Nombres de funciones y variables locales: inglés.
- Comentarios y docstrings: español.
- Mensajes de error: español, y siempre nombran la clase y el invariante violado.

---

## 6. Comandos

> Mantén esta sección exacta. Un comando desactualizado aquí cuesta más que la ausencia
> de la sección.

```bash
# Backend
uv sync                        # dependencias
uv run pytest                  # suite completa
uv run pytest -m invariants    # solo invariantes de dominio — corre esto siempre
uv run ruff check . && uv run ruff format --check .
uv run mypy backend/
uv run alembic upgrade head    # migraciones de SQLite

uv run uvicorn backend.api.main:app --reload   # API en :8000
uv run python -m backend.worker                # worker de generación

# Frontend
cd frontend && npm install
cd frontend && npm run dev     # Vite en :5173
cd frontend && npm run build
cd frontend && npm run lint

# Dominio
uv run python -m backend.quality.validate --canon <ruta>   # verificación programática
uv run python -m backend.context.budget --escena <id>      # recuento de tokens del paquete
```

## 7. Cómo trabajar aquí

### 7.1 Invariantes primero

Los invariantes del documento de definiciones son pruebas, no documentación. Antes de
implementar una regla nueva:

1. Escribe el test que la viola y falla.
2. Implementa el verificador.
3. Comprueba que el test pasa y que `uv run pytest -m invariants` sigue verde.

Un invariante sin test no existe.

### 7.2 Cambios en el dominio

Un cambio en `backend/domain/` es un cambio en la ontología. Debe ir acompañado de:

- Actualización de `docs/definitions.md`.
- Actualización del diagrama correspondiente en `docs/domain-knowledge.md`.
- Un `RegistroDeDecision` con la alternativa descartada y el motivo.
- Una migración, si el canon almacenado se ve afectado.

### 7.3 Cambios en prompts

Los prompts son versionados y referenciados por `Procedencia.version_de_prompt`. No los
edites en sitio sin incrementar la versión: rompes la reproducibilidad de todo lo
generado antes.

### 7.4 Invalidación en cascada

Si tocas algo que genera `UnidadDeContexto`, verifica que las aristas `deriva_de` siguen
siendo correctas. Un resumen que no se marca obsoleto cuando su fuente cambia produce
canon fantasma: hechos que ya nadie narra pero que siguen condicionando las escenas
siguientes. Es el fallo más insidioso del sistema, porque sigue pareciendo coherente
consigo mismo mientras se separa del texto real.

---

## 8. Qué no hacer

- No muevas lógica de validación a un prompt. Si es determinista, es código.
- No pidas a un modelo que "recuerde" continuidad. Eso es trabajo del contexto.
- No pases el texto completo del libro a un agente "por si acaso".
- No permitas más de un `Borrador` en estado `aceptado` por escena.
- No escribas en el canon desde un agente de generación.
- No elimines el contador de reintentos de la máquina de estados. Es lo único que impide
  un bucle de revisión perpetua.
- No añadas dependencias de red en `backend/domain/`.
- No invoques modelos desde `backend/api/`. Encola una `Tarea`.
- No dupliques un invariante en el frontend. Si React necesita validar, llama a la API.
- No hagas escrituras concurrentes a SQLite desde varios agentes.
- No subas el presupuesto de tokens del paquete para que quepa. Aprieta los filtros.
- No borres un `RegistroDeDecision`. Son inmutables.

---

## 9. Cuando algo no está claro

Si una decisión de diseño no está cubierta aquí ni en los documentos de ontología,
prefiere la opción que deja más estado explícito y consultable, aunque sea más verbosa.
El coste de un campo extra es trivial; el coste de una incoherencia descubierta en el
capítulo 30 es una reescritura.

Y si el cambio parece requerir que un agente "entienda" algo que no está en su paquete
de contexto, el arreglo está en la capa de contexto, no en el prompt.
