# SPEC-007 · La novela se aprueba — Especificación de requisitos (SRS)

| | |
| --- | --- |
| **Identificador** | SPEC-007 |
| **Título** | Aprobación humana de la novela al final de la lectura: cierra el volumen, bloquea los cambios y se puede reabrir |
| **Estado** | `construida` el 2026-09-24. Aprobada ese mismo día por la persona autora con el apartado 7 vacío y las dos propuestas aceptadas tal cual, y el plan del apartado 8 firmado en el mismo acto. Lo construido está en §9; **H-1 (§9.3) queda pendiente de decisión** |
| **Fecha** | 2026-09-24 |
| **Origen** | Encargo de la persona autora el 2026-09-24: «¿dónde tendría que aprobar la escritura de la novela? ¿Se puede agregar un botón de aprobación al final de la lectura de la novela?» |
| **Preguntas resueltas antes de redactar** | Efecto: la aprobación **cierra el volumen** —aporta la evidencia `humano` de *promesa al lector* a la puerta *Volumen cerrado*—. Condición: **solo con la escritura terminada**; los borradores sin aceptar se enumeran antes de firmar. Después: **cambios bloqueados, con «Reabrir»** |
| **Documentos de referencia** | `docs/verification.md` §2 (fila `humano`), §6 y §11 F-06; `docs/architecture.md` §6; `backend/quality/puertas.py`; `specs/spec4.md`, `spec5.md`, `spec6.md` |
| **Relación con las specs anteriores** | Añade dos rutas, un estado de la novela y una tabla. Cambia el comportamiento de `POST /escritura`, `POST /cambios` y `PATCH /portada` sobre una novela aprobada. El resto de SPEC-004 a SPEC-006 sigue vigente |

---

## 1. Problema: qué hay hoy

| # | Hecho observable | Dónde |
| --- | --- | --- |
| P-1 | No hay forma de aprobar una novela: ni ruta, ni estado, ni botón | `api/main.py`, `pages/lectura/` |
| P-2 | La puerta *Volumen cerrado* existe pero **nadie la evalúa**, y si se evaluara nunca se superaría: declara `promesa_al_lector` como evidencia ausente en v1, y `verification.md` §6 asigna esa dimensión a una persona | `quality/puertas.py`, `AUSENTES_EN_V1` |
| P-3 | Cuando el worker termina, publica una versión él solo con el motivo «escritura completa». Esa versión no ha pasado por nadie | `worker/bucle.py`, `_publicar_si_termino` |
| P-4 | La novela se puede reescribir, cambiar o retitular en cualquier momento: no existe una novela «definitiva» | rutas de SPEC-004 y SPEC-006 |

---

## 2. Alcance

### 2.1 Qué entra

| # | Entra |
| --- | --- |
| A-01 | `POST /novelas/{id}/aprobacion`: evalúa *Volumen cerrado* con la aprobación como evidencia de `promesa_al_lector` y, si se supera, registra la aprobación sobre la última versión publicada |
| A-02 | `POST /novelas/{id}/aprobacion/retirada`: reabre la novela. La aprobación no se borra: queda retirada, con fecha |
| A-03 | Migración `0005`: tabla `aprobacion_de_volumen` y registro de la puerta evaluada en `puerta` |
| A-04 | Con la novela aprobada, `POST /escritura`, `POST /cambios` y `PATCH /portada` responden `409` diciendo que hay que reabrirla |
| A-05 | `GET /novelas/{id}/lectura` añade `aprobacion`: `null` o `{ id, version_numero, aprobada_en }` |
| A-06 | En la lectura, la tarjeta «Fin» del último capítulo lleva **«Aprobar la novela»**, que abre un diálogo de confirmación con lo que se va a firmar |
| A-07 | Con la novela aprobada: sello «Aprobada» en la cubierta y la barra superior; los botones de escribir y «Pedir un cambio» y el bloque «Título y portada» quedan desactivados con el motivo; «Reabrir» en el Taller |

### 2.2 Qué queda fuera

| # | Fuera | Por qué |
| --- | --- | --- |
| N-01 | Aprobar escenas o borradores uno a uno, o pasarlos a `aceptado` | Sería saltar *Escena limpia* por excepción, que es el riesgo F-06 de `verification.md` §11. La aprobación es del volumen y no cambia el estado de ningún borrador |
| N-02 | Aprobar con defectos críticos deterministas en *Volumen cerrado* | `CLAUDE.md` §3.6: lo determinista bloquea, y una firma humana no lo levanta. La ruta responde `409` con los defectos |
| N-03 | Quién aprueba | No hay identidad de usuario en el sistema: la aprobación registra cuándo, no quién. Se anota como deuda frente a la métrica de F-06 |
| N-04 | Quitar del PDF la marca de borrador al aprobar | La marca describe el estado del borrador, que la aprobación no cambia (N-01) |
| N-05 | Evaluar *Volumen cerrado* de forma automática al terminar el worker | La puerta necesita la firma; evaluarla sin ella daría siempre evidencia ausente |

---

## 3. Requisitos

| Id | Requisito |
| --- | --- |
| RF-APR-01 | `POST /novelas/{id}/aprobacion` (`operationId` `createAprobacion`) solo procede si el estado de escritura es `escrita`. En cualquier otro estado responde `409` con el estado y la línea de `detalle` de `GET /escritura` |
| RF-APR-02 | Sin ninguna versión publicada responde `409`: no hay nada que firmar |
| RF-APR-03 | La ruta evalúa *Volumen cerrado* con `siembras_sin_pagar(cierre_de_volumen=True)` y `hilos_con_pregunta_dramatica` sobre el canon del volumen, y retira `promesa_al_lector` de la evidencia ausente **solo** porque la firma la aporta. El resultado se guarda en `puerta` con `ambito_id` = volumen |
| RF-APR-04 | Si la puerta tiene defectos críticos, responde `409` con cada defecto (código y diagnóstico) y no registra la aprobación |
| RF-APR-05 | Si se supera, registra la aprobación con `volumen_id`, `version_id` de la última versión y `aprobada_en`, y responde `201` con `aprobacion` y el número de borradores sin aceptar que se han firmado |
| RF-APR-06 | Aprobar una novela ya aprobada responde `409` y no duplica nada |
| RF-APR-07 | `POST /novelas/{id}/aprobacion/retirada` (`operationId` `createRetiradaDeAprobacion`) marca la aprobación vigente con `retirada_en` y responde `200`. Sin aprobación vigente, `409`. Ninguna fila de `aprobacion_de_volumen` se borra |
| RF-APR-08 | Con aprobación vigente, `POST /escritura`, `POST /cambios` y `PATCH /portada` responden `409` con «La novela está aprobada; reábrela para cambiarla» y no encolan ni guardan nada |
| RF-APR-09 | `GET /novelas/{id}/lectura` incluye `aprobacion` con la vigente o `null` |
| RF-APR-10 | Toda aprobación y toda retirada quedan en `audit_log` |
| RF-APR-11 | Un volumen inexistente responde `404` en las dos rutas |
| RF-LEC-12 | En el último capítulo, la tarjeta «Fin» muestra «Aprobar la novela» si la escritura está `escrita` y no hay aprobación vigente. Si la escritura no ha terminado, muestra el `detalle` del backend en su lugar |
| RF-LEC-13 | «Aprobar la novela» abre un diálogo con título, versión, capítulos, palabras y **cuántas escenas tienen el borrador sin aceptar**, que quedan firmadas tal como están. Se cierra solo con «Cancelar», Escape o al confirmar |
| RF-LEC-14 | Tras confirmar, el resultado llega como aviso que no se cierra solo; un `409` se muestra con el texto del backend, defectos incluidos |
| RF-LEC-15 | Con aprobación vigente, la cubierta y la barra superior muestran «Aprobada · v<n> · <fecha>»; «Escribir la novela», «Escribir una muestra», «Pedir un cambio» y «Guardar» del bloque de portada están desactivados y dicen por qué |
| RF-LEC-16 | El Taller muestra «Reabrir la novela», que pide confirmación en un diálogo; tras reabrir, todo vuelve a estar habilitado sin recargar |
| RF-CON-04 | El frontend no decide si se puede aprobar: el botón se muestra según el estado que dice el backend, y la ruta es quien acepta o rechaza |

---

## 4. Verificación

| Requisito | Metodología | Modo | Política |
| --- | --- | --- | --- |
| RF-APR-01 a RF-APR-11 | Tests de las rutas contra una base de prueba: escritura sin terminar, sin versión, con siembra abierta, aprobación correcta, doble aprobación, retirada, retirada sin aprobación, las tres rutas bloqueadas y desbloqueadas tras reabrir, volumen inexistente, `audit_log` | T | Bloqueante |
| RF-APR-03 | Test de la puerta: sin firma, `promesa_al_lector` sigue ausente y la puerta no se supera; con firma, sale de la evidencia ausente y nada más cambia | T | Bloqueante |
| RF-APR-07 | Invariante: el número de filas de `aprobacion_de_volumen` nunca baja | T (`-m invariants`) | Bloqueante |
| RF-LEC-12 a RF-LEC-16, RF-CON-04 | Recorrido contra el backend real con una novela escrita en modo demostración: aprobar, intentar cambiar, reabrir | D | Bloqueante |
| Todos | `uv run pytest`, `uv run pytest -m invariants`, lint y tipos; `npm run lint` y `npm run build` | A | Bloqueante |

---

## 5. Impacto

| Dónde | Qué cambia |
| --- | --- |
| `backend/migrations/` | `0005_la_novela_se_aprueba.py`: tabla `aprobacion_de_volumen (id, volumen_id, version_id, aprobada_en, retirada_en)` |
| `backend/quality/puertas.py` | `volumen_cerrado()` acepta la firma como evidencia de `promesa_al_lector` |
| `backend/orchestrator/` | `aprobacion.py`: evaluar la puerta, registrar, retirar y consultar la vigente |
| `backend/store/` | Repositorio `AprobacionesDeVolumen` |
| `backend/api/main.py` | Dos rutas nuevas; `409` en tres rutas; `aprobacion` en `/lectura` |
| `frontend/src/shared/api/lectura.ts` | Dos llamadas y el campo `aprobacion` |
| `frontend/src/pages/lectura/` | Tarjeta «Fin», diálogo, sello, Taller |
| `docs/definitions.md` | Clase `AprobacionDeVolumen` y su invariante (la tabla no pierde filas) |
| `docs/architecture.md` | D-22: la firma humana es la evidencia de *promesa al lector*; alternativa descartada: aceptar los borradores por excepción (N-01) |
| `docs/verification.md` | §6: *Volumen cerrado* ya se evalúa, con la firma como evidencia `humano` |

---

## 6. Criterios de aceptación

1. Suite de backend, invariantes, lint y tipos en verde; `npm run lint` y `npm run build` en verde.
2. Recorrido: escribir una muestra → leer hasta el final → aprobar → «Pedir un cambio» y «Escribir» bloqueados con su motivo → reabrir → vuelven a funcionar.
3. Desviaciones anotadas en §9.

---

## 7. Preguntas abiertas

Ninguna. Dos puntos son propuesta de esta spec y se aceptan o se corrigen al aprobarla: que el bloqueo alcance también a `PATCH /portada` (A-04), y que una siembra abierta al cierre impida aprobar (N-02, RF-APR-04).

---

## 8. Plan de implementación — PLAN-007

| | |
| --- | --- |
| **Identificador** | PLAN-007 |
| **Estado** | `aprobado` el 2026-09-24 en la misma firma que la spec. Autoriza escribir código |

| # | Paso | Dónde | Test, nombrado antes de escribirlo | Requisitos |
| --- | --- | --- | --- | --- |
| A-1 | Migración `0005` | `migrations/` | `test_migracion_0005_crea_aprobacion_de_volumen` | RF-APR-05 |
| A-2 | Firma como evidencia en *Volumen cerrado* | `quality/puertas.py` | `test_sin_firma_la_promesa_sigue_ausente`, `test_la_firma_solo_retira_la_promesa` | RF-APR-03 |
| B-1 | Repositorio y orquestación: evaluar, registrar, retirar | `store/`, `orchestrator/aprobacion.py` | `test_aprobar_registra_la_ultima_version`, `test_una_siembra_abierta_impide_aprobar`, `test_retirar_no_borra_la_aprobacion` | RF-APR-02 a RF-APR-07, RF-APR-10 |
| B-2 | Invariante de la tabla | `tests/` | `test_invariante_las_aprobaciones_no_se_pierden` | RF-APR-07 |
| C-1 | Rutas `aprobacion` y `retirada` | `api/` | `test_aprobar_sin_terminar_devuelve_409_con_el_detalle`, `test_aprobar_dos_veces_devuelve_409`, `test_volumen_inexistente_404` | RF-APR-01, RF-APR-06, RF-APR-11 |
| C-2 | `409` en escritura, cambios y portada; `aprobacion` en `/lectura` | `api/` | `test_una_novela_aprobada_no_se_reescribe_ni_se_retitula`, `test_la_lectura_trae_la_aprobacion_vigente` | RF-APR-08, RF-APR-09 |
| D-1 | Cliente de las dos rutas | `shared/api/` | Build; `grep` de `fetch(` | RF-CON-03, RF-CON-04 |
| D-2 | Tarjeta «Fin», diálogo, sello, bloqueos y «Reabrir» | `pages/lectura/` | Recorrido del criterio 2 | RF-LEC-12 a RF-LEC-16 |
| E-1 | Cierre: `docs/`, spec a `construida` | `docs/`, `specs/spec7.md` | Apartado 4 | Todos |

**Módulos.** `quality/` no importa de `store/` ni de `api/`: la firma llega a la puerta
como argumento. `orchestrator/aprobacion.py` es el único que junta puerta y repositorio.

**Marcha atrás.** Si evaluar *Volumen cerrado* sobre el canon real da defectos en novelas
ya escritas que nadie puede corregir desde la interfaz, se para y se vuelve a la spec: la
salida no es rebajar la puerta a advertencia sin decidirlo.

---

## 9. Lectura de ejecución

### 9.1 Cómo se cobró

| Requisito | Resultado |
| --- | --- |
| RF-APR-01 a RF-APR-11 | `tests/test_aprobacion.py`: 23 casos en verde. Sin terminar y ya aprobada dan `409` con el motivo; una siembra abierta da `409` con el defecto y no registra nada; la siembra de **otra** novela no bloquea esta; retirar deja la fila con `retirada_en`; con aprobación vigente, escritura, cambios y portada dan `409` y tras reabrir vuelven a funcionar; volumen inexistente, `404` con su motivo; aprobar y retirar quedan en `audit_log` |
| RF-APR-03 | `test_la_firma_solo_retira_la_promesa`: con firma, `promesa_al_lector` es lo único que sale de la evidencia ausente |
| RF-APR-07 | Invariantes: un `DELETE` sobre `aprobacion_de_volumen` lo rechaza un trigger, y una segunda aprobación vigente la rechaza un índice único parcial |
| Suite | `uv run pytest`: 448 en verde; `-m invariants`: 446; `ruff check` y `mypy backend/` sin errores. Dos tests fijaban el estado del esquema y se actualizan: cabeza `0005` y 14 decisiones registradas |
| RF-LEC-12 a RF-LEC-16, RF-CON-04 | Recorrido con Edge sin cabeza contra una **copia** de la base, migrada, con API y worker propios, y una novela escrita en modo demostración: tarjeta «Fin» con «Aprobar la novela» → diálogo con v1, 2 capítulos, 674 palabras y 2 escenas sin aceptar → aviso y sello «Aprobada · v1» en barra, cubierta y «Fin» → en el Taller, escribir y portada desactivados; en la ficha, «Pedir un cambio» desactivado → tras recargar sigue aprobada → «Reabrir» con confirmación → todo habilitado sin recargar. A 360 px sin desplazamiento horizontal; sin errores de consola |
| RF-CON-03 | `grep` de `fetch(` fuera de `shared/api/`: sin resultados |
| Frontend | `npm run lint` y `npm run build` en verde |

### 9.2 Desviaciones

| # | Desviación | Motivo |
| --- | --- | --- |
| DV-1 | La consulta de siembras abiertas es nueva y está acotada al volumen (`siembras_abiertas_del_volumen`), en lugar de reutilizar `siembras_abiertas` | La existente mira toda la base: con dos novelas, una siembra de la otra habría impedido aprobar esta. Lo cobra `test_la_siembra_de_otra_novela_no_bloquea_esta` |
| DV-2 | La línea que explica por qué algo está desactivado con la novela aprobada la compone el frontend | Es guía de pantalla antes de intentar nada; si se intenta igual, manda el `409` del backend (RF-APR-08) |
| DV-3 | Al abrir el diálogo de aprobar se vuelven a pedir las versiones | La versión que se firma es la última publicada, y puede haberse publicado después de abrir la lectura |

### 9.3 Hallazgos

| # | Hallazgo | Qué se hace |
| --- | --- | --- |
| H-1 | *Volumen cerrado* promete cobrar hilos resueltos, preguntas dramáticas respondidas y arcos con estado terminal, y RF-APR-03 —tal como se redactó— no los cobra **ni los declara como evidencia ausente**: `AUSENTES_EN_V1` solo declara `promesa_al_lector`. La puerta registra `superada` sin haberlos mirado, contra el principio 8 de `architecture.md` §1 | **Pendiente de decisión de la persona autora.** El defecto es de la spec, no del código: lo construido cumple RF-APR-03. Las salidas posibles están en el mensaje de entrega; cualquiera de ellas es un cambio de alcance y va a una spec |
| H-2 | La base local de trabajo (`mystorymaker.db`) sigue en `0004` | `run.ps1` ejecuta `alembic upgrade head` al arrancar; la API que estaba en marcha usa el código anterior hasta reiniciarla |
