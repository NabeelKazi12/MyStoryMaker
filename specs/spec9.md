# SPEC-009 · Eliminar una novela — Especificación de requisitos (SRS)

| | |
| --- | --- |
| **Identificador** | SPEC-009 |
| **Título** | «Eliminar esta novela» desde la lectura: la novela se retira —desaparece de la biblioteca y de la API— y se conserva en la base |
| **Estado** | `construida` el 2026-09-24. Aprobada ese mismo día por la persona autora con el apartado 7 vacío, y el plan del apartado 8 firmado en el mismo acto. Lo construido y sus desviaciones están en §9 |
| **Fecha** | 2026-09-24 |
| **Origen** | Encargo de la persona autora el 2026-09-24: «dame un botón como opción para eliminar novelas; desde el apartado de lectura de cada novela añade el botón de "Eliminar esta novela"» |
| **Preguntas resueltas antes de redactar** | Qué hace: **retirar**, no borrar filas. Límites: **ni aprobada ni escribiéndose**. Recuperar: **no desde la interfaz**; la confirmación pide escribir el título |
| **Documentos de referencia** | `specs/spec7.md` (aprobación y su trigger), `specs/spec8.md` (biblioteca), `docs/architecture.md` (TLA+ `VersionAnteriorSeConserva`), `docs/definitions.md` (jerarquía contenedora) |
| **Relación con las specs anteriores** | Añade una ruta, una columna y un estado de la novela. Cambia la respuesta de las diez rutas `/novelas/{id}/…` para una novela retirada (`404`) y la lista de SPEC-008, que deja de incluirlas |

---

## 1. Problema: qué hay hoy

| # | Hecho observable | Dónde |
| --- | --- | --- |
| P-1 | Una novela no se puede quitar: toda novela encargada, incluso las de prueba o las abandonadas, se queda para siempre en la biblioteca | `GET /novelas`, `pages/biblioteca/` |
| P-2 | Borrarla de verdad chocaría con tres reglas vigentes: las versiones no se pierden (`VersionAnteriorSeConserva`), las aprobaciones no se borran (trigger de `0005`) y `audit_log` y `registro_decision` son inmutables | `store/`, `migrations/` |

---

## 2. Alcance

### 2.1 Qué entra

| # | Entra |
| --- | --- |
| A-01 | Migración `0006`: `volumen.eliminada_en` (nula mientras la novela existe) y la decisión D-23 |
| A-02 | `DELETE /novelas/{id}` (`operationId` `deleteNovela`): retira la novela, con fecha, si no está aprobada ni escribiéndose |
| A-03 | Una novela retirada **no existe para la API**: las diez rutas `/novelas/{id}/…` responden `404` y `GET /novelas` no la lista |
| A-04 | En la lectura, al final del Taller, un bloque **«Eliminar esta novela»**, desactivado con su motivo si está aprobada o escribiéndose |
| A-05 | Diálogo de confirmación que explica qué pasa y pide **escribir el título** para habilitar el botón |
| A-06 | Tras eliminar, la aplicación vuelve a la biblioteca —o a la entrevista si no queda ninguna— con un aviso que no se cierra solo |

### 2.2 Qué queda fuera

| # | Fuera | Por qué |
| --- | --- | --- |
| N-01 | Borrar filas de la base: capítulos, escenas, borradores, canon, versiones, tareas, aprobaciones | Rompería los tres invariantes de P-2. La novela retirada se conserva entera |
| N-02 | Restaurar una novela retirada desde la interfaz | Decidido así. Se puede hacer a mano en la base (`eliminada_en = NULL`); se anota en D-23 |
| N-03 | Eliminar una novela aprobada o con escritura en curso | Aprobada: primero se reabre (SPEC-007). En curso: el worker la está escribiendo; se espera a que termine o se detenga |
| N-04 | Eliminar varias a la vez o desde la biblioteca | El encargo es desde la lectura de cada novela |

---

## 3. Requisitos

| Id | Requisito |
| --- | --- |
| RF-ELI-01 | `DELETE /novelas/{id}` marca `volumen.eliminada_en` y responde `200` con `volumen_id`, `titulo` y `eliminada_en` |
| RF-ELI-02 | Con aprobación vigente responde `409` «La novela está aprobada; reábrela antes de eliminarla» y no cambia nada |
| RF-ELI-03 | Con la escritura en `abriendo` o `escribiendo` responde `409` con el estado y el `detalle` de `GET /escritura`, y no cambia nada |
| RF-ELI-04 | Un volumen inexistente o ya retirado responde `404` «no existe el volumen <id>» |
| RF-ELI-05 | Con la novela retirada, todas las rutas con `{volumen_id}` responden `404` con ese mismo motivo. Lo cobra un test que recorre **todas** las rutas de la aplicación con `{volumen_id}`, de modo que una ruta nueva que olvide la comprobación hace fallar la suite |
| RF-ELI-06 | `GET /novelas` no incluye las retiradas |
| RF-ELI-07 | Retirar no borra ni modifica ninguna otra fila: capítulos, escenas, borradores, versiones, aprobaciones, tareas y canon quedan igual |
| RF-ELI-08 | La retirada queda en `audit_log` con el id y el título de la novela |
| RF-LEC-17 | Al final del Taller, el bloque «Eliminar esta novela» explica en una línea qué hace. Con la novela aprobada o escribiéndose, el botón está desactivado y dice por qué |
| RF-LEC-18 | El botón abre un diálogo que dice que la novela desaparecerá de la biblioteca y no se puede deshacer desde aquí, y pide escribir el título; «Eliminar» solo se habilita cuando lo escrito coincide con el título. Se cierra solo por «Cancelar», Escape o al confirmar |
| RF-LEC-19 | Tras eliminar se vuelve a la biblioteca con el aviso «Se ha eliminado «<título>»», que no se cierra solo; si no queda ninguna novela, a la entrevista. Un `409` o `404` se muestra en la lectura con el texto del backend y no se sale de ella |
| RF-CON-06 | El frontend no decide si se puede eliminar: desactiva el botón según el estado que le da el backend, y la ruta es quien acepta o rechaza |

---

## 4. Verificación

| Requisito | Metodología | Modo | Política |
| --- | --- | --- | --- |
| RF-ELI-01 a RF-ELI-04, RF-ELI-06 a RF-ELI-08 | Tests de la ruta contra una base de prueba: eliminar una sin empezar y una escrita; aprobada y en curso dan `409` sin cambios; inexistente y ya retirada dan `404`; la lista la excluye; recuento de filas de las tablas de P-2 igual antes y después; `audit_log` | T | Bloqueante |
| RF-ELI-05 | Test que enumera `app.routes` con `{volumen_id}` y comprueba `404` en cada una para una novela retirada | T (`-m invariants`) | Bloqueante |
| RF-LEC-17 a RF-LEC-19, RF-CON-06 | Recorrido con Edge sin cabeza contra una copia de la base: bloque desactivado con novela aprobada; confirmación con título mal y bien escrito; vuelta a la biblioteca con el aviso y sin la novela | D | Bloqueante |
| Todos | `uv run pytest`, `-m invariants`, ruff y mypy; `npm run lint` y `npm run build`; `grep` de `fetch(` | A | Bloqueante |

---

## 5. Impacto

| Dónde | Qué cambia |
| --- | --- |
| `backend/migrations/` | `0006_la_novela_se_retira.py`: `volumen.eliminada_en` y `rd-d23` |
| `backend/orchestrator/` | `eliminacion.py`: precondiciones, retirada y `audit_log` |
| `backend/orchestrator/biblioteca.py` | Excluye las retiradas |
| `backend/api/main.py` | `DELETE /novelas/{id}` y una dependencia común que da `404` a una novela retirada en las rutas con `{volumen_id}` |
| `frontend/src/shared/api/lectura.ts` | `eliminarNovela` |
| `frontend/src/pages/lectura/` | Bloque en el Taller y diálogo |
| `frontend/src/app/main.tsx`, `pages/biblioteca/` | Vuelta a la biblioteca con aviso |
| `docs/definitions.md` | `Volumen` lleva `eliminada_en`; una novela retirada se conserva y no se sirve |
| `docs/architecture.md` | D-23: retirar en lugar de borrar; alternativa descartada: borrado en cascada |

---

## 6. Criterios de aceptación

1. Suite de backend, invariantes, lint y tipos en verde; `npm run lint` y `npm run build` en verde.
2. Recorrido: abrir una novela → Taller → «Eliminar esta novela» → escribir el título → la biblioteca ya no la muestra y enseña el aviso.
3. Desviaciones anotadas en §9.

---

## 7. Preguntas abiertas

Ninguna.

---

## 8. Plan de implementación — PLAN-009

| | |
| --- | --- |
| **Identificador** | PLAN-009 |
| **Estado** | `aprobado` el 2026-09-24 en la misma firma que la spec. Autoriza escribir código |

| # | Paso | Dónde | Test, nombrado antes de escribirlo | Requisitos |
| --- | --- | --- | --- | --- |
| A-1 | Migración `0006` | `migrations/` | `test_migracion_0006_anade_eliminada_en` | RF-ELI-01 |
| B-1 | Retirada y precondiciones | `orchestrator/eliminacion.py` | `test_eliminar_marca_la_fecha_y_no_toca_nada_mas`, `test_una_aprobada_no_se_elimina`, `test_una_en_curso_no_se_elimina`, `test_eliminar_queda_en_audit_log` | RF-ELI-01 a RF-ELI-03, RF-ELI-07, RF-ELI-08 |
| B-2 | La biblioteca las excluye | `orchestrator/biblioteca.py` | `test_la_biblioteca_no_lista_las_eliminadas` | RF-ELI-06 |
| C-1 | Ruta `DELETE` y dependencia común | `api/` | `test_eliminar_por_la_ruta`, `test_eliminar_dos_veces_da_404`, `test_ninguna_ruta_sirve_una_novela_eliminada` | RF-ELI-01, RF-ELI-04, RF-ELI-05 |
| D-1 | Cliente, bloque del Taller, diálogo y vuelta a la biblioteca | `shared/api/`, `pages/lectura/`, `pages/biblioteca/`, `app/` | Recorrido del criterio 2 | RF-LEC-17 a RF-LEC-19, RF-CON-06 |
| E-1 | Cierre: `docs/`, dos tests que fijan el esquema (cabeza `0006`, 15 decisiones), spec a `construida` | `docs/`, `tests/`, `specs/spec9.md` | Apartado 4 | Todos |

**Módulos.** `orchestrator/eliminacion.py` reutiliza `progreso` y `vigente` para las
precondiciones, como la biblioteca y la aprobación.

**Marcha atrás.** Si alguna ruta no puede recibir la dependencia común sin cambiar su
contrato, se para y se vuelve a la spec: servir una novela retirada por una sola ruta es
exactamente el fallo que RF-ELI-05 existe para impedir.

---

## 9. Lectura de ejecución

### 9.1 Cómo se cobró

| Requisito | Resultado |
| --- | --- |
| RF-ELI-01 a RF-ELI-04, RF-ELI-06 a RF-ELI-08 | `tests/test_eliminacion.py`: 12 casos en verde. Se elimina una escrita y una sin empezar; las cuentas de `capitulo`, `escena`, `borrador`, `version_novela`, `version_capitulo`, `aprobacion_de_volumen`, `tarea`, `hecho`, `personaje`, `lugar` y `registro_decision` no cambian; aprobada y abriéndose dan el rechazo sin marcar nada; eliminar dos veces o un volumen inexistente, `404`; la biblioteca la excluye; `audit_log` lleva id y título |
| RF-ELI-05 | `test_ninguna_ruta_sirve_una_novela_eliminada` recorre las 11 rutas con `{volumen_id}` de `app.routes` —las diez de antes y `DELETE`— y todas dan `404` «no existe el volumen». Una ruta nueva sin la dependencia hace fallar la suite |
| Suite | `uv run pytest`: 466 en verde; `-m invariants`: 464; `ruff check` y `mypy backend/` sin errores. Los dos tests que fijan el esquema pasan a cabeza `0006` y 15 decisiones |
| RF-LEC-17 | Recorrido con Edge sin cabeza contra una copia migrada de la base: con la novela aprobada, el botón está desactivado y el bloque dice «Está aprobada: reábrela antes de eliminarla.» |
| RF-LEC-18 | Sin título y con un título equivocado, «Eliminar» desactivado; con el título exacto, activo |
| RF-LEC-19 | Tras confirmar: biblioteca, URL limpia, una cubierta menos y el aviso «Se ha eliminado «<título>».»; abrir su URL después da «No se ha podido leer la novela» con el `404` |
| RF-CON-06 | `DELETE` directo sobre la aprobada: `409` con el motivo del backend |
| Frontend | `npm run lint` y `npm run build` en verde; `grep` de `fetch(` fuera de `shared/api/` sin resultados; sin errores de consola |

### 9.2 Desviaciones

| # | Desviación | Motivo |
| --- | --- | --- |
| DV-1 | El aviso «Se ha eliminado…» lo guarda la aplicación y no la biblioteca | La lectura que lo produce desaparece al volver; así se ve también en la entrevista si ya no queda ninguna novela (RF-LEC-19) |
| DV-2 | La línea que explica por qué el botón está desactivado la compone el frontend | Igual que SPEC-007 DV-2: es guía de pantalla, y si se intenta igual manda el `409` |
