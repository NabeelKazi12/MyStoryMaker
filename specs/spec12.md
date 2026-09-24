# SPEC-012 · Gastos y trazas — Especificación de requisitos (SRS)

| | |
| --- | --- |
| **Identificador** | SPEC-012 |
| **Título** | Pestaña «Gastos» en cada novela, leída de SQLite, y envío de cada llamada al modelo a Langfuse con enlace desde la pestaña |
| **Estado** | `construida` el 2026-09-24, **salvo el criterio 3** (envío real a Langfuse), que ejecuta la persona autora con sus claves. Aprobada ese mismo día con el apartado 7 vacío y el plan del apartado 8 firmado en el mismo acto. Desviaciones en §9.2; DV-1 y DV-2 cambian RF-LAN-05 y RF-LAN-07 y piden confirmación |
| **Fecha** | 2026-09-24 |
| **Origen** | Encargo de la persona autora el 2026-09-24: «quiero observar las trazas en Langfuse […] lo quiero observar junto con el gasto en el frontend; abre una pestaña llamada gastos en cada novela» |
| **Preguntas resueltas antes de redactar** | Alcance: **pestaña y envío a Langfuse** en esta spec. Contenido: **resumen, desglose por rol y por capítulo, y la lista de llamadas** una a una |
| **Documentos de referencia** | `specs/spec3.md` §4.9 (RF-OBS-01 a RF-OBS-05) y S-02 (SQLite es la fuente de verdad; Langfuse, la vista), `backend/observability/trazas.py`, `tests/test_import_boundaries.py`, `specs/spec9.md` (RF-ELI-05) |
| **Relación con las specs anteriores** | Cierra RF-OBS-01 a RF-OBS-03, que SPEC-003 dejó con el protocolo y el doble pero **sin cliente real ni conexión**. RF-OBS-04 y RF-OBS-05 quedan como están (N-03, N-04) |

---

## 1. Problema: qué hay hoy

| # | Hecho observable | Dónde |
| --- | --- | --- |
| P-1 | `observability/` define el protocolo, `ClienteNulo` y un doble, pero **ningún módulo lo usa** y no hay cliente de Langfuse: ninguna llamada al modelo llega a Langfuse | `backend/observability/trazas.py` |
| P-2 | El gasto real sí se guarda: cada llamada deja una `procedencia` con coste en USD —el que devuelve Claude Code—, latencia, modelo, versión de prompt y clase de fallo. Pero no se ve en ninguna pantalla | `procedencia`, `worker/modelo.py` |
| P-3 | Los tokens de entrada y salida llegan en la respuesta del modelo y **no se guardan**: `procedencia` no tiene columnas para ellos | `worker/modelo.py` `Respuesta`, migración `0001` |
| P-4 | Las variables `LANGFUSE_*` están en `.env.example`, pero nada lee `.env`: `run.ps1` no lo carga | `run.ps1` |

---

## 2. Alcance

### 2.1 Qué entra

| # | Entra |
| --- | --- |
| A-01 | Migración `0007`: `procedencia.tokens_entrada` y `procedencia.tokens_salida`, nulas para las filas anteriores |
| A-02 | El worker guarda los tokens de cada respuesta en su `procedencia` |
| A-03 | `GET /novelas/{id}/gastos` (`operationId` `readGastos`): totales, desglose por rol y por capítulo, y la lista de llamadas, todo desde SQLite |
| A-04 | `ClienteLangfuse` en `observability/`, sobre la API pública de ingesta con la biblioteca estándar —sin dependencia nueva—, activo solo si están `LANGFUSE_PUBLIC_KEY`, `LANGFUSE_SECRET_KEY` y `LANGFUSE_HOST`; sin ellas, `ClienteNulo` |
| A-05 | El worker envía cada llamada al modelo como **una traza** cuyo id es el de su `procedencia`, en la **sesión** de su novela, con una *generation* que lleva modelo, versión de prompt, tokens, coste, latencia y el fallo si lo hubo |
| A-06 | La ruta de gastos devuelve el enlace a cada traza en Langfuse cuando el cliente está activo |
| A-07 | `run.ps1` carga `.env` si existe, sin mostrar sus valores |
| A-08 | En la lectura, un botón **«Gastos»** en la barra superior abre un panel con: cifras (total en USD, llamadas, tokens, tiempo, fallidas), desglose por rol y por capítulo en barras, y la lista de llamadas con enlace «Ver en Langfuse» por fila |

### 2.2 Qué queda fuera

| # | Fuera | Por qué |
| --- | --- | --- |
| N-01 | Leer los gastos **de** Langfuse | SQLite es la fuente de verdad (SPEC-003 S-02). Si Langfuse está caído o sin configurar, la pestaña sigue mostrando todo |
| N-02 | Convertir a euros | El coste llega en USD de Claude Code. Un tipo de cambio sería un dato inventado |
| N-03 | Scores de validadores y puertas en Langfuse (RF-OBS-04) | El envío de scores cambia el bucle de verificación, no solo el de invocación; va en otra spec |
| N-04 | Prompts versionados **en** Langfuse (RF-OBS-05) | La versión de prompt viaja como metadato de cada traza; gestionar los prompts en Langfuse es otra spec |
| N-05 | Rellenar tokens de las llamadas antiguas | No se guardaron; la pestaña las muestra como «—» y no las cuenta en el total de tokens |
| N-06 | Enviar a Langfuse las llamadas ya hechas | Solo se envían las nuevas, desde que el cliente está activo |
| N-07 | Presupuestos o alertas de gasto | No se ha pedido |

---

## 3. Requisitos

| Id | Requisito |
| --- | --- |
| RF-GAS-01 | La migración `0007` añade `tokens_entrada` y `tokens_salida` a `procedencia`, nulas; las filas existentes no cambian |
| RF-GAS-02 | Cada `procedencia` nueva guarda los tokens que devolvió el cliente del modelo, también cuando la llamada falla por contrato o por guardarraíl |
| RF-GAS-03 | `GET /novelas/{id}/gastos` responde `200` con `moneda` = `USD`; `total` con `coste`, `llamadas`, `fallidas`, `tokens_entrada`, `tokens_salida`, `latencia_ms` y `llamadas_sin_tokens`; `por_rol` y `por_capitulo` con coste y llamadas; y `llamadas`, una por `procedencia` de la novela, en orden cronológico |
| RF-GAS-04 | Cada llamada lleva `id`, `momento`, `agente`, `modelo`, `version_de_prompt`, `tarea` (apertura o redacción), `escena_id` y `capitulo_orden` si es de redacción, `intento` (ordinal dentro de su tarea), `coste`, `latencia_ms`, `tokens_entrada`, `tokens_salida`, `clase_de_fallo` y `traza_url` |
| RF-GAS-05 | Una llamada pertenece a una novela por su `paquete_contexto` → `tarea` → `plan.volumen_id`. Las llamadas de otra novela nunca aparecen |
| RF-GAS-06 | Una novela sin llamadas responde `200` con ceros y listas vacías. Inexistente o retirada, `404` (RF-ELI-05) |
| RF-GAS-07 | La ruta es de solo lectura: no escribe en ninguna tabla |
| RF-LAN-01 | Con las tres variables `LANGFUSE_*` definidas, el worker usa `ClienteLangfuse`; con alguna ausente, `ClienteNulo`, y la novela se escribe igual |
| RF-LAN-02 | Cada llamada al modelo produce en Langfuse una traza con `id` = id de la `procedencia`, `sessionId` = id de la novela, nombre `<agente>:<tarea>`, y una *generation* con `model`, `usage` (tokens de entrada y salida), `costDetails` o coste total en USD, latencia, metadatos `version_de_prompt`, `escena_id`, `capitulo_orden`, `modo`, y nivel `ERROR` con la clase de fallo si la hubo |
| RF-LAN-03 | Un fallo al enviar a Langfuse —red, `4xx`, `5xx`, tiempo agotado— **nunca** interrumpe ni retrasa más de unos segundos la escritura: se registra en el log del worker y se descarta |
| RF-LAN-04 | El envío no lleva prosa ni el paquete de contexto: solo los datos de RF-LAN-02. La prosa vive en SQLite (`CLAUDE.md` §3.5) |
| RF-LAN-05 | `traza_url` es `<LANGFUSE_HOST>/project/<id del proyecto>/traces/<id>` cuando el cliente está activo y el id del proyecto se ha podido obtener de la API con las claves; si no, `null` |
| RF-LAN-06 | `observability/` sigue sin importar `agents/`, `api/`, `orchestrator/`, `worker/` ni `quality/`, y sin abrir la base (`test_import_boundaries`) |
| RF-LAN-07 | `run.ps1` carga las variables de `.env` si existe y no imprime ningún valor |
| RF-LEC-20 | La barra superior de la lectura tiene un botón «Gastos» que abre el panel del mismo nombre; se cierra como los demás paneles (RF-LEC-06) |
| RF-LEC-21 | El panel muestra, arriba, cuatro cifras —total en USD, llamadas (con las fallidas), tokens, tiempo—; debajo, barras por rol y por capítulo; y la lista de llamadas, la más reciente primero, con su rol, capítulo, intento, modelo, coste, tokens, latencia y fallo |
| RF-LEC-22 | Cada llamada con `traza_url` tiene «Ver en Langfuse», que abre la traza en una pestaña nueva. Sin Langfuse activo, el panel lo dice en una línea y no muestra enlaces |
| RF-LEC-23 | Con la escritura en curso, el panel se actualiza con el mismo sondeo del progreso mientras está abierto |
| RF-LEC-24 | Estados vacíos distintos: «Esta novela todavía no ha hecho ninguna llamada al modelo» frente a «No se han podido leer los gastos» con «Reintentar» |
| RF-CON-07 | El frontend no suma ni calcula costes: cifras, desgloses y enlaces vienen de la ruta |

---

## 4. Verificación

| Requisito | Metodología | Modo | Política |
| --- | --- | --- | --- |
| RF-GAS-01, RF-GAS-02 | Test de migración; test del worker en modo demostración: cada `procedencia` nueva lleva los tokens de la respuesta | T | Bloqueante |
| RF-GAS-03 a RF-GAS-07 | Tests de la ruta contra una base de prueba: dos novelas escritas en demostración, cifras de una sin rastro de la otra; totales iguales a la suma de las filas; `intento` y `capitulo_orden`; sin llamadas; retirada `404`; recuento de filas igual tras pedirla | T | Bloqueante |
| RF-LAN-01 a RF-LAN-05 | Tests del cliente con un transporte HTTP falso inyectado: forma exacta del lote de ingesta, sin prosa; `ClienteNulo` sin variables; un transporte que lanza o devuelve `500` no propaga nada; `traza_url` con y sin id de proyecto | T | Bloqueante |
| RF-LAN-06 | `test_import_boundaries`, sin cambios en la regla | T | Bloqueante |
| RF-LAN-02 (real) | Con las claves de la persona autora en `.env`, escribir una muestra y ver la traza en Langfuse, en su sesión y con su coste | D | Bloqueante para el cierre, **lo ejecuta la persona autora**: el agente no maneja las claves |
| RF-LAN-07 | Inspección de `run.ps1` y ejecución con un `.env` de prueba con valores ficticios | I + D | Bloqueante |
| RF-LEC-20 a RF-LEC-24, RF-CON-07 | Recorrido con Edge sin cabeza contra una copia de la base con la novela real ya escrita: panel, cifras, barras, lista, estados vacíos | D | Bloqueante |
| Todos | `uv run pytest`, `-m invariants`, ruff y mypy; `npm run lint` y `npm run build`; `grep` de `fetch(` | A | Bloqueante |

---

## 5. Impacto

| Dónde | Qué cambia |
| --- | --- |
| `backend/migrations/` | `0007_la_procedencia_cuenta_tokens.py` y `rd-d24` |
| `backend/domain/production/ejecucion.py` | `Procedencia` con `tokens_entrada` y `tokens_salida` opcionales |
| `backend/worker/` | `worker.py` pasa los tokens a la procedencia; `bucle.py` envía cada llamada al observador; `__main__.py` construye el cliente desde el entorno |
| `backend/observability/` | `langfuse.py`: `ClienteLangfuse` y `cliente_desde_el_entorno` |
| `backend/store/` | Lectura de gastos por novela |
| `backend/api/main.py` | `GET /novelas/{id}/gastos` con `NOVELA_VIVA` |
| `run.ps1` | Carga de `.env` |
| `frontend/` | `leerGastos`, botón y panel «Gastos» |
| `docs/definitions.md` | `Procedencia` con tokens |
| `docs/architecture.md` | D-24: una traza por llamada, con el id de la procedencia, en la sesión de la novela; alternativa descartada: una traza por novela, que no enlaza cada fila de la pestaña con su llamada |
| Dependencias | Ninguna nueva |

---

## 6. Criterios de aceptación

1. Suite de backend, invariantes, lint y tipos en verde; `npm run lint` y `npm run build` en verde.
2. Recorrido: abrir la novela ya escrita → «Gastos» → ver el total, el desglose y la lista de sus llamadas.
3. Con claves reales en `.env` (lo hace la persona autora): una muestra nueva aparece en Langfuse y su fila del panel enlaza a ella.
4. Desviaciones anotadas en §9.

---

## 7. Preguntas abiertas

Ninguna.

---

## 8. Plan de implementación — PLAN-012

| | |
| --- | --- |
| **Identificador** | PLAN-012 |
| **Estado** | `aprobado` el 2026-09-24 en la misma firma que la spec. Autoriza escribir código |

| # | Paso | Dónde | Test, nombrado antes de escribirlo | Requisitos |
| --- | --- | --- | --- | --- |
| A-1 | Migración `0007` y `Procedencia` con tokens | `migrations/`, `domain/` | `test_migracion_0007_anade_tokens_a_la_procedencia` | RF-GAS-01 |
| A-2 | El worker guarda los tokens | `worker/worker.py` | `test_cada_procedencia_nueva_lleva_sus_tokens` | RF-GAS-02 |
| B-1 | Lectura de gastos por novela | `store/` | `test_los_gastos_de_una_novela_no_mezclan_otra`, `test_el_total_es_la_suma_de_las_llamadas`, `test_cada_llamada_sabe_su_capitulo_e_intento` | RF-GAS-03 a RF-GAS-05 |
| B-2 | Ruta `GET /gastos` | `api/` | `test_sin_llamadas_los_gastos_son_cero`, `test_pedir_los_gastos_no_escribe_nada`, `test_la_ruta_publica_read_gastos` | RF-GAS-03, RF-GAS-06, RF-GAS-07 |
| C-1 | `ClienteLangfuse` sobre un transporte inyectable | `observability/langfuse.py` | `test_una_llamada_es_una_traza_en_la_sesion_de_su_novela`, `test_el_lote_no_lleva_prosa`, `test_sin_variables_el_cliente_es_nulo`, `test_un_fallo_al_enviar_no_se_propaga`, `test_la_url_de_la_traza_necesita_el_proyecto` | RF-LAN-01 a RF-LAN-05 |
| C-2 | El worker envía cada llamada | `worker/bucle.py`, `worker/__main__.py` | `test_el_bucle_envia_cada_llamada_al_observador` | RF-LAN-02 |
| C-3 | `.env` en `run.ps1` | `run.ps1` | Inspección y ejecución con `.env` ficticio | RF-LAN-07 |
| D-1 | Cliente, botón y panel «Gastos» | `shared/api/`, `pages/lectura/` | Recorrido del criterio 2 | RF-LEC-20 a RF-LEC-24, RF-CON-07 |
| E-1 | Cierre: `docs/`, tests que fijan el esquema (cabeza `0007`, 16 decisiones), spec a `construida` | `docs/`, `tests/`, `specs/spec12.md` | Apartado 4 | Todos |

**Módulos.** `observability/langfuse.py` recibe datos ya leídos —no abre la base ni importa
el worker—; el worker construye el cliente y le pasa cada llamada. `store/` lee los
gastos; `api/` solo los sirve.

**Marcha atrás.** Si la API de ingesta de Langfuse rechaza la forma del lote con las
claves reales, el cliente queda activo solo tras corregirlo; mientras, `ClienteNulo`, y la
pestaña sigue funcionando desde SQLite (N-01).

---

## 9. Lectura de ejecución

### 9.1 Cómo se cobró

| Requisito | Resultado |
| --- | --- |
| RF-GAS-01, RF-GAS-02 | `test_migracion_0007_…` y `test_cada_procedencia_nueva_lleva_sus_tokens` en verde |
| RF-GAS-03 a RF-GAS-07 | Siete tests de `tests/test_gastos.py`: dos novelas sin mezclarse, totales iguales a la suma, capítulo e intento, llamadas sin tokens contadas aparte, ceros sin llamadas, campos exactos de la ruta, ninguna fila nueva tras pedirla. RF-GAS-06 (`404` de una retirada) lo cobra además `test_ninguna_ruta_sirve_una_novela_eliminada`, que ahora recorre 12 rutas |
| RF-LAN-01 a RF-LAN-05 | Tests del cliente contra un transporte falso: lote `trace-create` + `generation-create` con id de la procedencia, `sessionId` de la novela, `usageDetails`, `costDetails` y metadatos; nivel `ERROR` con la clase de fallo; sin prosa; nulo sin variables o con los valores de `.env.example`; `500`, `401` y tiempo agotado no se propagan; enlace con y sin proyecto |
| RF-LAN-02 (bucle) | `test_el_bucle_envia_cada_llamada_al_observador`: una traza terminada por procedencia, en la sesión de la novela, con uso y versión de prompt |
| RF-LAN-06 | `test_import_boundaries` en verde **sin tocar la regla** (ver DV-1) |
| RF-LAN-07 | Bloque de `run.ps1` ejecutado aislado con un `.env` ficticio: carga las tres `LANGFUSE_*` presentes, ignora una comentada, quita comillas, no toca `MYSTORYMAKER_DB`, no imprime valores, y una variable ya definida en el entorno manda |
| Suite | `uv run pytest`: 489 en verde; `-m invariants`: 487; `ruff check` y `mypy backend/` sin errores. Los dos tests que fijan el esquema pasan a cabeza `0007` y 16 decisiones |
| RF-LEC-20 a RF-LEC-24, RF-CON-07 | Recorrido con Edge sin cabeza contra una copia migrada de la base, con API aislada y variables de Langfuse **ficticias**: la novela real enseña 1,52 US$, 22 llamadas, tokens «—» con su nota, 39 min 54 s, barras por rol y por 10 capítulos proporcionales, tooltip por foco, y ningún enlace; una muestra nueva enseña 3 llamadas con tokens y «Ver en Langfuse» en pestaña nueva; tema noche; 360 px sin desplazamiento horizontal; sin errores de consola |
| Paleta | `validate_palette.js` de la guía de visualización: la barra de cada tema pasa las seis comprobaciones contra su superficie (papel `#9a6424`, sepia `#9a5a1c`, noche `#c0822f`) |
| Frontend | `npm run lint` y `npm run build` en verde; `grep` de `fetch(` fuera de `shared/api/` sin resultados |
| **Criterio 3** | **Cobrado en parte**, con autorización de la persona autora: una traza de diagnóstico enviada con el mismo cliente y transporte que el worker y con sus claves —sin mostrarlas— recibió `207` con los dos eventos en `201` y ninguno en error. Queda ver una novela real en la interfaz de Langfuse |

### 9.2 Desviaciones

| # | Desviación | Motivo |
| --- | --- | --- |
| DV-1 | El transporte HTTP no está en `observability/`: lo inyecta el worker (`worker/transporte.py`). El enlace a la traza se compone con una cuarta variable, `LANGFUSE_PROJECT_ID`, en lugar de pedir el proyecto a la API de Langfuse (cambia RF-LAN-05) | `test_import_boundaries` prohíbe `urllib` y `http` en `observability/` y en `api/`. Relajar esa regla de SPEC-003 no lo autoriza esta spec; inyectar el transporte y leer el proyecto del entorno la respeta |
| DV-2 | `run.ps1` carga de `.env` **solo** las variables `LANGFUSE_*` (acota RF-LAN-07) | `.env.example` trae `MYSTORYMAKER_DB=./canon.db` y la base por defecto es `mystorymaker.db`: cargar el fichero entero haría que, tras copiar el ejemplo, la aplicación abriera otra base y las novelas «desaparecieran» |
| DV-3 | Solo enlazan a Langfuse las llamadas con tokens registrados | Las de antes de SPEC-012 no los tienen y nunca se enviaron (N-06): su enlace llevaría a una traza que no existe |
| DV-4 | El panel lleva una línea que dice si Langfuse está configurado y otra que avisa de las llamadas sin tokens | Sin ellas, «sin enlaces» y «tokens: —» parecerían un fallo |
| DV-5 | `run.ps1` para al arrancar cualquier worker huérfano de este proyecto, mata el árbol de procesos al salir (`taskkill /T`) y manda la salida del worker a `logs/worker.log` y `logs/worker.err.log` (`logs/` en `.gitignore`) | Se encontraron cuatro workers a la vez: `uv run` lanza un Python hijo que no moría con su padre, y cada `-Reiniciar` dejaba el anterior vivo. Los viejos, con código de antes de SPEC-012, cogían tareas y no enviaban nada. Y RF-LAN-03 manda anotar los fallos en el log del worker, que en una ventana oculta no leía nadie |

### 9.3 Hallazgos

| # | Hallazgo | Qué se hace |
| --- | --- | --- |
| H-1 | La respuesta de Langfuse avisa de que `POST /api/public/ingestion` (v3) está **obsoleta y deja de aceptar trazas en Langfuse Cloud el 2026-11-16**; lo que la sustituye es `POST /api/public/otel/v1/traces` (OpenTelemetry). También avisa de retrasos de varios minutos en los datos que entran por esta vía | Pendiente: una spec que cambie el cliente a OTLP antes de esa fecha. Hasta entonces el envío funciona; `ClienteLangfuse` está detrás del protocolo, así que el cambio no toca ni el worker ni la pestaña |
