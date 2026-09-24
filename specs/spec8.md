# SPEC-008 · La biblioteca — Especificación de requisitos (SRS)

| | |
| --- | --- |
| **Identificador** | SPEC-008 |
| **Título** | Ver las novelas escritas antes: ruta que lista las novelas y biblioteca como pantalla de inicio |
| **Estado** | `construida` el 2026-09-24. Aprobada ese mismo día por la persona autora con el apartado 7 vacío, y el plan del apartado 8 firmado en el mismo acto. Lo construido y sus desviaciones están en §9 |
| **Fecha** | 2026-09-24 |
| **Origen** | Encargo de la persona autora el 2026-09-24: «agrega la función de poder ver las novelas escritas previamente; desde la pantalla de carga original no puedo observar la novela que escribimos anteriormente» |
| **Documentos de referencia** | `specs/spec4.md` (rutas de lectura), `specs/spec5.md` (entrevista y lector), `specs/spec6.md` (portada), `specs/spec7.md` (aprobación) |
| **Relación con las specs anteriores** | Añade una ruta de lectura y una pantalla. No cambia ninguna ruta existente. Cambia a dónde lleva «Crear otro encargo» y qué se ve al abrir la aplicación sin `?volumen=` |

---

## 1. Problema: qué hay hoy

| # | Hecho observable | Dónde |
| --- | --- | --- |
| P-1 | Sin `?volumen=<id>` en la URL, la aplicación abre siempre la entrevista. Una novela ya escrita solo se puede volver a abrir sabiendo su identificador | `frontend/src/app/main.tsx` |
| P-2 | No hay ninguna ruta que liste las novelas: el backend solo sirve una novela cuyo id ya se conoce | `api/main.py` |
| P-3 | «Crear otro encargo» borra el `?volumen=` y deja la novela anterior sin camino de vuelta | `Taller.tsx`, `main.tsx` |

---

## 2. Alcance

### 2.1 Qué entra

| # | Entra |
| --- | --- |
| A-01 | `GET /novelas` (`operationId` `listNovelas`): todas las novelas, de la más reciente a la más antigua, con lo que la biblioteca enseña de cada una |
| A-02 | **Biblioteca** como pantalla de inicio: una estantería de cubiertas —la misma cubierta tipográfica de la lectura— con título, «Para …», estado de escritura, palabras y sello si está aprobada. Pulsar una cubierta abre su lectura |
| A-03 | En la biblioteca, **«Nueva novela»** abre la entrevista; desde la entrevista, **«Volver a la biblioteca»** |
| A-04 | Si no hay ninguna novela, la aplicación abre directamente la entrevista, como hoy |
| A-05 | En la lectura, el botón del título de la barra superior lleva a la cubierta como hoy, y un botón nuevo **«Biblioteca»** vuelve a la estantería. «Crear otro encargo» del Taller pasa a llamarse «Nueva novela» y abre la entrevista |
| A-06 | La biblioteca distingue «no hay novelas» de «no he podido leer la lista», con «Reintentar» |

### 2.2 Qué queda fuera

| # | Fuera | Por qué |
| --- | --- | --- |
| N-01 | Borrar, archivar o renombrar novelas desde la biblioteca | Borrar toca el canon y las versiones; renombrar ya existe en el Taller (SPEC-006) |
| N-02 | Búsqueda, filtros y paginación | Con una base de un solo autor y decenas de novelas no hacen falta; se revisa si crece |
| N-03 | Separar novelas por persona usuaria | No hay identidad en el sistema (SPEC-007 N-03) |
| N-04 | Una columna de fecha de creación en `volumen` | El orden sale del orden de inserción; la fecha que se enseña es la de la última versión publicada, que ya existe. Sin migración |

---

## 3. Requisitos

| Id | Requisito |
| --- | --- |
| RF-BIB-01 | `GET /novelas` responde `200` con una lista; cada elemento lleva `volumen_id`, `titulo`, `destinatario`, `estado` y `detalle` de escritura —los mismos de `GET /escritura`—, `capitulos`, `palabras`, `ultima_version_en` (o `null`) y `aprobacion` (la vigente o `null`, como en `/lectura`) |
| RF-BIB-02 | El orden es de la novela creada más recientemente a la más antigua |
| RF-BIB-03 | Sin novelas responde `200` con lista vacía, no `404` |
| RF-BIB-04 | La ruta es de solo lectura: no encola, no escribe y no toca `audit_log` |
| RF-BIB-05 | Al abrir la aplicación sin `?volumen=`, se pide la lista: con novelas se ve la biblioteca; sin novelas, la entrevista |
| RF-BIB-06 | Cada novela se ve como una cubierta con título, «Para <destinatario>» (omitido si el título ya lo contiene, como en SPEC-005 DV-4), el estado y el `detalle` del backend, palabras, y el sello «Aprobada · v<n>» si lo está. Se abre con clic o con Intro, y la URL pasa a `?volumen=<id>` |
| RF-BIB-07 | «Nueva novela» abre la entrevista; la entrevista, si hay novelas, muestra «Volver a la biblioteca». El borrador de la entrevista se conserva al ir y volver (RF-INT-05 de SPEC-005) |
| RF-BIB-08 | Desde la lectura, «Biblioteca» vuelve a la estantería sin recargar, y la biblioteca vuelve a pedir la lista, de modo que el estado y el título que enseña son los de ahora |
| RF-BIB-09 | Si la lista no se puede leer, la biblioteca dice «No se ha podido leer la biblioteca» con el texto del backend y «Reintentar», y ofrece igualmente «Nueva novela» |
| RF-BIB-10 | Usable a 360 px sin desplazamiento horizontal |
| RF-CON-05 | La biblioteca no calcula estados: estado, `detalle` y aprobación vienen de la ruta |

---

## 4. Verificación

| Requisito | Metodología | Modo | Política |
| --- | --- | --- | --- |
| RF-BIB-01 a RF-BIB-04 | Tests de la ruta contra una base de prueba: lista vacía; dos novelas en orden, una escrita en demostración y otra sin empezar, con sus estados, palabras y versión; una aprobada con su aprobación; ninguna fila nueva en `tarea` ni en `audit_log` tras pedirla | T | Bloqueante |
| RF-BIB-05 a RF-BIB-10, RF-CON-05 | Recorrido con Edge sin cabeza contra una copia de la base: biblioteca con novelas, abrir una, volver, nueva novela, volver a la biblioteca con el borrador intacto; base vacía abre la entrevista; API caída muestra el error y «Reintentar»; 360 px | D | Bloqueante |
| Todos | `uv run pytest`, `-m invariants`, ruff y mypy; `npm run lint` y `npm run build`; `grep` de `fetch(` fuera de `shared/api/` | A | Bloqueante |

---

## 5. Impacto

| Dónde | Qué cambia |
| --- | --- |
| `backend/orchestrator/` o `backend/store/` | Consulta de la biblioteca: una fila por volumen con su progreso, palabras, última versión y aprobación |
| `backend/api/main.py` | Ruta `GET /novelas` |
| `frontend/src/shared/api/lectura.ts` | `leerBiblioteca` y su tipo |
| `frontend/src/pages/biblioteca/` | Página nueva |
| `frontend/src/app/main.tsx` | Tres pantallas: biblioteca, entrevista, lectura |
| `frontend/src/pages/crear/`, `pages/lectura/` | «Volver a la biblioteca», «Biblioteca», «Nueva novela» |
| `docs/` | Ninguno: no cambia ontología, módulos ni quién comprueba qué |
| Migraciones | Ninguna (N-04) |

---

## 6. Criterios de aceptación

1. Suite de backend, invariantes, lint y tipos en verde; `npm run lint` y `npm run build` en verde.
2. Recorrido: abrir la aplicación → ver la novela escrita antes en la estantería → abrirla y leerla → volver a la biblioteca → «Nueva novela» → volver.
3. Desviaciones anotadas en §9.

---

## 7. Preguntas abiertas

Ninguna.

---

## 8. Plan de implementación — PLAN-008

| | |
| --- | --- |
| **Identificador** | PLAN-008 |
| **Estado** | `aprobado` el 2026-09-24 en la misma firma que la spec. Autoriza escribir código |

| # | Paso | Dónde | Test, nombrado antes de escribirlo | Requisitos |
| --- | --- | --- | --- | --- |
| A-1 | Consulta de la biblioteca | `orchestrator/biblioteca.py` | `test_la_biblioteca_trae_cada_novela_con_su_estado`, `test_la_mas_reciente_va_primero` | RF-BIB-01, RF-BIB-02 |
| A-2 | Ruta `GET /novelas` | `api/` | `test_sin_novelas_la_biblioteca_esta_vacia`, `test_pedir_la_biblioteca_no_escribe_nada`, `test_la_ruta_publica_list_novelas` | RF-BIB-01 a RF-BIB-04 |
| B-1 | Cliente de la ruta | `shared/api/` | Build; `grep` de `fetch(` | RF-CON-03 |
| B-2 | Página de biblioteca y navegación entre las tres pantallas | `pages/biblioteca/`, `app/main.tsx`, `pages/crear/`, `pages/lectura/` | Recorrido del criterio 2 | RF-BIB-05 a RF-BIB-10, RF-CON-05 |
| C-1 | Cierre: spec a `construida` | `specs/spec8.md` | Apartado 4 | Todos |

**Módulos.** `orchestrator/biblioteca.py` reutiliza `progreso` de `orchestrator/escritura.py`
y `vigente` de `orchestrator/aprobacion.py` en lugar de volver a calcular estados.

**Marcha atrás.** Si calcular el progreso de cada novela hace lenta la ruta con muchas
novelas, se para y se vuelve a la spec: la salida no es inventar el estado en el frontend.

---

## 9. Lectura de ejecución

### 9.1 Cómo se cobró

| Requisito | Resultado |
| --- | --- |
| RF-BIB-01 a RF-BIB-04 | `tests/test_biblioteca.py`: 6 casos en verde. Una novela sin empezar y otra escrita y aprobada salen con su estado, `detalle`, palabras, versión y aprobación; tres novelas salen en orden inverso de creación; sin novelas, `200` y `[]`; título, destinatario, estado, `detalle` y aprobación coinciden con `/lectura` y `/escritura`; pedir la lista dos veces no añade filas a `tarea`, `audit_log` ni `puerta` |
| Suite | `uv run pytest`: 454 en verde; `-m invariants`: 452; `ruff check` y `mypy backend/` sin errores |
| RF-BIB-05, RF-BIB-06, RF-BIB-08 | Recorrido con Edge sin cabeza contra una copia migrada de la base de trabajo: la aplicación abre en la biblioteca con cuatro novelas; la escrita se abre, la URL pasa a `?volumen=<id>` y se lee; «Biblioteca» vuelve a la estantería y limpia la URL |
| RF-BIB-07 | «Nueva novela» → entrevista → se escribe un nombre → «Volver a la biblioteca» → «Nueva novela» otra vez: el nombre sigue ahí |
| RF-BIB-09 | Con la API parada: «No se ha podido leer la biblioteca», «Reintentar» y «Nueva novela», que abre la entrevista |
| RF-BIB-05 (vacía) | Contra una base migrada sin novelas: abre la entrevista, sin «Volver a la biblioteca» |
| RF-BIB-10 | A 360 px, `scrollWidth` = 360; la estantería pasa a dos columnas |
| RF-CON-03 | `grep` de `fetch(` fuera de `shared/api/`: sin resultados |
| Frontend | `npm run lint` y `npm run build` en verde; sin errores de consola en los tres recorridos |

### 9.2 Desviaciones

| # | Desviación | Motivo |
| --- | --- | --- |
| DV-1 | La cubierta de la estantería pone nombre legible al estado («Escrita», «Sin escribir»…) a partir del valor del backend; un valor desconocido se enseña tal cual | Es una etiqueta, no un cálculo: el estado lo sigue decidiendo el backend (RF-CON-05), y la línea `detalle` se enseña sin tocar debajo |
| DV-2 | La pantalla de error de la lectura dice «Volver a la biblioteca» en lugar de «Volver a la entrevista» | Con biblioteca, volver a la entrevista dejaba sin camino a las demás novelas, que es P-3 |
