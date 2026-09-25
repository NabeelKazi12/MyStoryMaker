# SPEC-014 · Lo que destapó la evaluación de extremo a extremo — Especificación de requisitos (SRS)

| | |
| --- | --- |
| **Identificador** | SPEC-014 |
| **Título** | Adoptar el Redactor `v1.2.0` medido en `evaluacion.md` §5, que la `Procedencia` diga la verdad sobre qué prompt y qué parámetros corrieron, e incorporar al repositorio el arnés de extremo a extremo |
| **Estado** | `aprobada` el 2026-09-25 por la persona autora —puerta *Spec aprobada* de `AGENTS.md` §10.5 superada—, con las cuatro preguntas de §7 cerradas por la recomendación de cada una. El plan del apartado 8 está en `borrador`, pendiente de firma |
| **Fecha** | 2026-09-25 |
| **Origen** | Encargo de la persona autora el 2026-09-25: dejar el proyecto listo para la evaluación de cinco briefs, tabla de validadores por brief e iteración de tuning con el antes y el después. La evaluación está en `docs/evaluacion.md` |
| **Documentos de referencia** | `docs/evaluacion.md` §3, §5 y §6; `specs/spec10.md` H-1; `AGENTS.md` §8 (prompts y procedencia); `backend/worker/worker.py`; `backend/worker/bucle.py` |

---

## 1. Problema: qué hay hoy

| # | Hecho observable | Dónde |
| --- | --- | --- |
| P-1 | Las escenas del Redactor `v1.1.0` miden el 47 % del presupuesto de palabras que les pide el esqueleto (mediana de 28 escenas en 4 briefs). Ninguna llega al 90 % | `evaluacion.md` §5 |
| P-2 | Un prompt candidato `v1.2.0` sube la mediana a 0,585 en 34 escenas, por 0,0018 $ más por invocación. Se midió inyectado desde fuera del repositorio | `evaluacion.md` §5 |
| P-3 | La `Procedencia` de toda invocación registra `VERSION_DE_PROMPT` del Redactor, también la del Planner: en la evaluación, el Planner consta como `1.1.0` y corre la `1.3.0` | `worker/worker.py` `_procedencia` |
| P-4 | La `ClaveDeTarea` de idempotencia usa la versión del Redactor también para la apertura: un cambio de prompt del Planner no invalida la clave | `worker/bucle.py` `_clave` |
| P-5 | `parametros_muestreo` se registra como `thinking=adaptive;effort=high`, cuando RF-TIE-01 invoca sin pensamiento extendido | `worker/worker.py` `_procedencia` |
| P-6 | El nivel de extremo a extremo de `evaluacion.md` lo produjo un arnés que no está en el repositorio: la tabla no se puede regenerar | `evaluacion.md` §7 |

---

## 2. Alcance

### 2.1 Qué entra

| # | Entra |
| --- | --- |
| A-01 | Prompt del Redactor `v1.2.0`, con el texto medido en `evaluacion.md` §5, su hash en el manifiesto y `VERSION_DE_PROMPT = "1.2.0"` |
| A-02 | Cada invocación registra en su `Procedencia` la versión del prompt **del rol que invoca** y los parámetros con los que se invocó de verdad |
| A-03 | La `ClaveDeTarea` usa la versión del rol de la tarea |
| A-04 | El arnés de extremo a extremo, en el repositorio, fuera de la suite por defecto: nunca invoca al modelo desde `uv run pytest` |

### 2.2 Qué queda fuera

Cada fila es un hallazgo de `evaluacion.md` §6 que necesita su propia decisión de alcance.

| # | Fuera | Por qué |
| --- | --- | --- |
| N-01 | Que el texto libre llegue a los roles, envuelto (H-01) | Decide qué hace la novela con lo que el cliente escribe: es producto, no corrección |
| N-02 | Fechas absolutas en los eventos del Planner y conexión del validador formal a la puerta de publicación (H-02, H-03) | Cambia el formato del Planner y la puerta *Volumen cerrado*; cierra RF-LEAN-04 de verdad |
| N-03 | Conectar `elementos_obligatorios_presentes` (H-03) | Necesita la atadura entre elemento y hecho, que hoy nadie escribe |
| N-04 | Envoltorio y detector sobre recuerdos, rasgos y nombres, y patrones de injection a mitad de línea (H-07, H-08) | Cambia la entrada del Planner |
| N-05 | Que `nombres_exactos` deje de marcar palabras comunes (H-04) | Hay que decidir el umbral por longitud de nombre y si una tilde cuenta como errata |
| N-06 | Que el número de escenas dependa de la extensión encargada (H-06) | Aunque el Redactor escriba el 100 %, una novela de 30.000 palabras en 7 escenas no puede pasar de 8.400 |

---

## 3. Requisitos

| Id | Requisito |
| --- | --- |
| RF-TUN-01 | Existe `backend/agents/redactor/prompts/v1.2.0.md` con el texto medido, su hash está en `MANIFIESTO` y `VERSION_DE_PROMPT` es `"1.2.0"`. La `v1.1.0` sigue en el manifiesto con su hash |
| RF-TUN-02 | Una invocación del Planner registra en `procedencia.version_de_prompt` la versión del Planner, y una del Redactor la del Redactor |
| RF-TUN-03 | `procedencia.parametros_muestreo` refleja la invocación real; con el cliente de Claude Code, sin pensamiento extendido |
| RF-TUN-04 | La `ClaveDeTarea` de una apertura cambia si cambia la versión del prompt del Planner, y no si cambia solo la del Redactor |
| RF-TUN-05 | El arnés recorre los cinco briefs de `tests/briefs/` por el camino de producción, en una base temporal por brief, y escribe por brief un informe con lo que saltó en la tubería y lo que se calcula a posteriori |
| RF-TUN-06 | `uv run pytest` no invoca nunca el arnés ni al modelo real |

---

## 4. Verificación

| Requisito | Metodología | Modo | Política |
| --- | --- | --- | --- |
| RF-TUN-01 | `test_el_prompt_vigente_coincide_con_su_manifiesto` (`tests/test_ejecucion.py`), ya existente, sobre la `1.2.0` | T | Bloqueante |
| RF-TUN-01 | Arnés sobre los cuatro briefs que generan: la mediana de palabras entre presupuesto por escena no baja de la de `evaluacion.md` §5 | D | Advertencia: el modelo no es determinista |
| RF-TUN-02, RF-TUN-03 | Test del bucle con `ClienteFalso`: una apertura y una redacción dejan dos procedencias con la versión de su rol y los parámetros del cliente | T | Bloqueante |
| RF-TUN-04 | Test de `_clave` con dos versiones de Planner y la misma del Redactor | T | Bloqueante |
| RF-TUN-05 | Ejecución manual del arnés y comparación con la tabla de `evaluacion.md` §3 | D | Bloqueante |
| RF-TUN-06 | El arnés no se llama `test_*` y el `conftest.py` sigue apuntando `MYSTORYMAKER_CLAUDE` a una ruta inexistente | I | Bloqueante |
| Todos | `uv run pytest`, `-m invariants`, ruff y mypy | A | Bloqueante |

---

## 5. Impacto

| Dónde | Qué cambia |
| --- | --- |
| `backend/agents/redactor/` | Prompt `v1.2.0`, manifiesto y versión |
| `backend/worker/worker.py` | `Worker` recibe la versión de su rol y los parámetros del cliente, en lugar de importar la del Redactor |
| `backend/worker/bucle.py` | `_clave` y `_invocar` pasan la versión del rol de la tarea |
| Arnés | Ubicación según Q-3 |
| `docs/evaluacion.md` | §5 pasa de «candidato» a «adoptado»; §7 con el comando del arnés |

---

## 6. Criterios de aceptación

1. Suite, invariantes, lint y tipos en verde.
2. Una ejecución del arnés con el repositorio en la rama de la spec reproduce la tabla de `evaluacion.md` §3, con las procedencias del Planner en `1.3.0`.
3. Desviaciones anotadas en §9.

---

## 7. Preguntas abiertas

Ninguna. Las cuatro que tenía el borrador se cerraron al aprobar con la recomendación de
cada una; se corrigen aquí si la persona autora dice otra cosa.

| # | Pregunta | Cierre |
| --- | --- | --- |
| Q-1 | ¿Se adopta la `v1.2.0` aunque ninguna escena llegue al 90 %? | **Sí.** Es mejor que la `v1.1.0` en los cuatro briefs y cuesta 0,0018 $ más por invocación. Una segunda iteración va en su propia spec |
| Q-2 | ¿Qué umbral de extensión por escena da por buena una versión? | La mediana de 0,9 queda como **objetivo**, no como puerta. La comprobación de RF-TUN-01 es de no regresión: la mediana no baja de 0,585, con política *Advertencia* |
| Q-3 | ¿Dónde vive el arnés? | `tests/evaluacion_e2e.py`: su nombre no empieza por `test_` y pytest no lo recoge. Sin directorios nuevos |
| Q-4 | ¿Corre el arnés en integración continua? | **No.** Se ejecuta a mano: cuesta dinero y necesita una sesión de Claude Code |

---

## 8. Plan de implementación — PLAN-014

Estado: `borrador`. Requiere firma antes de escribir código (`AGENTS.md` §10.4).

| Paso | Qué | Módulos | Test que lo demuestra, escrito antes |
| --- | --- | --- | --- |
| 1 | Cada cliente declara `parametros_muestreo` (`ClassVar[str]`): Claude Code `thinking=off;max_tokens=<n>`, demostración `determinista`, falso `falso`. `Worker._procedencia` lo lee del cliente en lugar de la constante | `worker/modelo.py`, `worker/worker.py` | `test_la_procedencia_lleva_los_parametros_del_cliente` |
| 2 | `Worker` recibe `version_de_prompt` y deja de importar la del Redactor. `Bucle` pasa la del Planner en `_abrir` y en `_invocar_candidatos`, y la del Redactor en `_redactar`. `_clave` elige la versión por el tipo de la tarea | `worker/worker.py`, `worker/bucle.py` | `test_apertura_y_redaccion_registran_la_version_de_su_rol` y `test_la_clave_de_apertura_cambia_con_el_prompt_del_planner` |
| 3 | Prompt `v1.2.0` del Redactor con el texto medido en `evaluacion.md` §5, su hash en `MANIFIESTO` y `VERSION_DE_PROMPT = "1.2.0"` | `agents/redactor/` | `test_el_prompt_vigente_coincide_con_su_manifiesto`, ya existente |
| 4 | Arnés en `tests/evaluacion_e2e.py`, con el comportamiento de `evaluacion.md` §3 y §7 | `tests/` | Inspección (RF-TUN-06) y una ejecución manual (RF-TUN-05) |
| 5 | Ejecución del arnés sobre los cinco briefs con el repositorio del paso 4 | — | Mediana ≥ 0,585 y Planner registrado como `1.3.0` (criterio 2 de §6) |
| 6 | `evaluacion.md` §5 y §7 al día, y §9 de esta spec | `docs/`, `specs/` | — |

**Reglas de dependencia (`CLAUDE.md` §4).** `worker/` ya importa de `agents/` para
conocer las versiones, y no se añade ninguna flecha nueva. El arnés importa de
`orchestrator/`, `worker/` y `store/` como hacen hoy los tests.

**Migraciones.** Ninguna: las columnas `version_de_prompt` y `parametros_muestreo` ya existen.

**Riesgos y marcha atrás.** Las procedencias ya escritas conservan la versión equivocada.
No se reescriben, porque son registro de lo que se anotó entonces (`CLAUDE.md` §3.5); se
declara aquí que las anteriores a esta spec no distinguen la versión del Planner. Si la
`v1.2.0` empeora algo que el arnés no mide, basta con devolver `VERSION_DE_PROMPT` a
`"1.1.0"`: las dos versiones siguen en el manifiesto.
