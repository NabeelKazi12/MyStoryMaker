# SPEC-006 · Título, portada y dedicatoria — Especificación de requisitos (SRS)

| | |
| --- | --- |
| **Identificador** | SPEC-006 |
| **Título** | Editar el título y la dedicatoria desde el Taller; portada tipográfica propia y dedicatoria como primera página, en la lectura y en el PDF |
| **Estado** | `construida` el 2026-09-24. Aprobada ese mismo día por la persona autora con el apartado 7 vacío —puerta *Spec aprobada* de `AGENTS.md` §10.5 superada— y el plan del apartado 8 firmado en el mismo acto. Lo construido y sus desviaciones están en §9 |
| **Fecha** | 2026-09-24 |
| **Origen** | Encargo de la persona autora el 2026-09-24: «añade un apartado dentro de las modificaciones en donde pueda modificar el título de la novela, que se le agregue una portada y la dedicatoria vaya dentro de ello como primer página» |
| **Preguntas resueltas antes de redactar** | Dónde: un bloque nuevo en el panel **Taller**. Alcance: **PDF y lectura**. Portada: **tipográfica**, sin imágenes. Qué se edita: **título y dedicatoria** |
| **Documentos de referencia** | `specs/spec4.md` (rutas de escritura y lectura), `specs/spec5.md` (cubierta, paneles, RF-LEC-01 y RF-LEC-06), `backend/export/pdf.py` (RF-LEC-08 de SPEC-003) |
| **Relación con las specs anteriores** | Añade una ruta de escritura y cambia dos presentaciones. Todo requisito de SPEC-004 y SPEC-005 sigue vigente salvo RF-LEC-01 de SPEC-005, que se amplía en RF-LEC-11 |

---

## 1. Problema: qué hay hoy

| # | Hecho observable | Dónde |
| --- | --- | --- |
| P-1 | El título lo compone el backend al cerrar la entrevista («Para <nombre>») y no hay ninguna forma de cambiarlo después | `orchestrator/encargo.py`, `volumen.titulo` |
| P-2 | La dedicatoria es la de la entrevista y tampoco se puede cambiar después | `destinatario.dedicatoria` |
| P-3 | En el PDF, título, dedicatoria y «Para …» comparten la primera página: no hay portada propiamente dicha ni página de dedicatoria | `export/pdf.py`, sección `portada` |
| P-4 | En la lectura, la dedicatoria va dentro de la cubierta, debajo del título, y «Empezar a leer» salta directamente al capítulo 1 | `pages/lectura/Lectura.tsx` |

---

## 2. Alcance

### 2.1 Qué entra

| # | Entra |
| --- | --- |
| A-01 | Ruta de escritura para cambiar título y dedicatoria de una novela |
| A-02 | Bloque **«Título y portada»** en el panel Taller: dos campos, una vista previa de la portada y de la página de dedicatoria maquetadas como tales, y «Guardar» |
| A-03 | PDF: **portada tipográfica** a página completa (fondo de color, ornamento, título y «Para …») y, detrás, la **dedicatoria sola en su página** |
| A-04 | Lectura: la cubierta deja de llevar la dedicatoria; la dedicatoria pasa a ser una página propia entre la cubierta y el capítulo 1 |

### 2.2 Qué queda fuera

| # | Fuera | Por qué |
| --- | --- | --- |
| N-01 | Portadas con imagen, subir ficheros | Decidido así: portada tipográfica. Guardar ficheros es otra spec |
| N-02 | Elegir colores o plantillas de portada | La portada es una sola, del sistema |
| N-03 | Editar otros datos del encargo (nombre, rasgos, recuerdos…) | Cambian lo que la novela cuenta, no cómo se presenta; eso es regenerar |
| N-04 | Publicar una versión nueva al cambiar el título | Una versión es un cambio de prosa (SPEC-003); el título no toca capítulos |
| N-05 | Autor o firma en la portada | No se ha pedido |
| N-06 | Tubería de pruebas del frontend | Sigue siendo PLAN-002 B-03 (SPEC-005 N-05) |

---

## 3. Requisitos

| Id | Requisito |
| --- | --- |
| RF-POR-01 | `PATCH /novelas/{id}/portada` (`operationId` `updatePortada`) recibe `titulo` y `dedicatoria`, los dos opcionales pero al menos uno, y devuelve la novela con los valores guardados |
| RF-POR-02 | El título se guarda sin espacios sobrantes y tiene entre 1 y 120 caracteres; vacío o más largo responde `422` diciendo cuál de los dos límites falla |
| RF-POR-03 | La dedicatoria se guarda sin espacios sobrantes y admite hasta 500 caracteres. Vacía significa «sin dedicatoria» |
| RF-POR-04 | Un título o una dedicatoria con un término vetado —del cliente o global— responde `422` nombrando el término, igual que el guardarraíl hace con la prosa, y no se guarda nada |
| RF-POR-05 | Una novela que no existe responde `404` |
| RF-POR-06 | Tras guardar, `/lectura`, `/texto` y `/pdf` sirven el título y la dedicatoria nuevos. No se toca prosa, canon, tareas ni versiones |
| RF-POR-07 | Cada cambio queda en `audit_log` con el valor anterior y el nuevo |
| RF-PDF-01 | La primera página del PDF es la portada: fondo de color a página completa, ornamento, título y «Para <destinatario>» (omitido si el título ya lo contiene, como DV-4 de SPEC-005). La dedicatoria no va en ella |
| RF-PDF-02 | Si hay dedicatoria, la segunda página la lleva sola, centrada. Sin dedicatoria, esa página no existe |
| RF-PDF-03 | Detrás siguen, en el orden de hoy, novedades (solo desde la versión 2), índice, ficha y capítulos |
| RF-LEC-10 | La cubierta de la lectura muestra título y «Para …», y no la dedicatoria |
| RF-LEC-11 | «Empezar a leer» lleva a la página de dedicatoria si la hay y, desde ella, «Siguiente» lleva al capítulo 1; «Anterior» desde el capítulo 1 vuelve a la dedicatoria. «Seguir leyendo» sigue yendo al último capítulo leído. Las flechas del teclado recorren el mismo camino |
| RF-TAL-01 | El bloque «Título y portada» del Taller abre con el título y la dedicatoria actuales, y su vista previa —maquetada como la portada y la página de dedicatoria, no como texto plano— cambia mientras se escribe |
| RF-TAL-02 | «Guardar» envía lo escrito sin validarlo en el navegador. Un `422` se muestra con el texto del backend; el resultado, bueno o malo, llega como aviso que no se cierra solo. Tras guardar, la cubierta y la barra superior muestran el título nuevo sin recargar |
| RF-TAL-03 | «Guardar» está desactivado mientras se guarda y cuando no hay nada cambiado |

---

## 4. Verificación

| Requisito | Metodología | Modo | Política |
| --- | --- | --- | --- |
| RF-POR-01 a RF-POR-07 | Tests de la ruta contra una base de prueba: cambio válido, título vacío, título de 121 caracteres, dedicatoria vacía, término vetado, volumen inexistente, y comprobación de que prosa, tareas y versiones no cambian | T | Bloqueante |
| RF-PDF-01 a RF-PDF-03 | Tests del exportador: orden de secciones, número de página de la dedicatoria, dedicatoria ausente de la portada, sin página de dedicatoria cuando está vacía | T | Bloqueante |
| RF-PDF-01 | Inspección visual de un PDF generado | I | Avisa |
| RF-LEC-10, RF-LEC-11, RF-TAL-01 a RF-TAL-03 | Recorrido manual contra el backend real con la novela ya escrita | D | Bloqueante |
| Todos | `pytest`, `ruff`, `mypy`, `npm run lint` y `npm run build` en verde; `grep` de `fetch(` fuera de `shared/api/` sin resultados | A | Bloqueante |

---

## 5. Impacto

| Dónde | Qué cambia |
| --- | --- |
| `backend/api/main.py` | Ruta `PATCH /novelas/{id}/portada` |
| `backend/store/` | Escritura del título y la dedicatoria, con su fila de `audit_log`. La ruta no escribe SQL |
| `backend/export/pdf.py` | Portada a página completa y página de dedicatoria |
| `frontend/src/shared/api/lectura.ts` | `actualizarPortada` |
| `frontend/src/pages/lectura/` | `Taller.tsx` (bloque nuevo), `Lectura.tsx` (cubierta y página de dedicatoria) |
| `frontend/src/shared/ui/estilos.css` | Estilos de la vista previa y de la página de dedicatoria |
| `docs/` | Ninguno: no cambia ontología, módulos ni quién comprueba qué |
| Migraciones | Ninguna: `volumen.titulo` y `destinatario.dedicatoria` ya existen |

---

## 6. Criterios de aceptación

1. Todas las comprobaciones del apartado 4 en verde.
2. Con la novela ya escrita: cambiar el título y la dedicatoria desde el Taller, verlos en la cubierta y en la página de dedicatoria, y descargar un PDF cuya primera página es la portada y la segunda la dedicatoria.

---

## 7. Preguntas abiertas

Ninguna. Los límites de 120 y 500 caracteres y la aplicación del guardarraíl (RF-POR-02 a RF-POR-04) son propuesta de esta spec: se aceptan o se corrigen al aprobarla.

---

## 8. Plan de implementación — PLAN-006

| | |
| --- | --- |
| **Identificador** | PLAN-006 |
| **Estado** | `aprobado` el 2026-09-24 en la misma firma que la spec. Autoriza escribir código |

| # | Paso | Dónde | Comprobación | Requisitos |
| --- | --- | --- | --- | --- |
| A-1 | Tests de la ruta en rojo; escritura en `store/` con `audit_log`; ruta en `api/` | `store/`, `api/main.py`, `tests/` | `pytest` | RF-POR-01 a RF-POR-07 |
| A-2 | Tests del exportador en rojo; portada a página completa y página de dedicatoria | `export/pdf.py`, `tests/test_exportacion_pdf.py` | `pytest`, inspección del PDF | RF-PDF-01 a RF-PDF-03 |
| B-1 | `actualizarPortada` y bloque «Título y portada» con vista previa | `shared/api/`, `pages/lectura/Taller.tsx` | Recorrido | RF-TAL-01 a RF-TAL-03 |
| B-2 | Cubierta sin dedicatoria y página de dedicatoria en el recorrido de lectura | `pages/lectura/Lectura.tsx`, `estilos.css` | Recorrido, flechas | RF-LEC-10, RF-LEC-11 |
| C-1 | Cierre: todas las comprobaciones, recorrido con la novela escrita, spec a `construida` con desviaciones | `specs/spec6.md` | Apartado 4 | Todos |

**Módulos.** `api/` llama a `store/` para escribir y a `quality/` para el guardarraíl; no
abre SQL propio. En el frontend, `shared/` no importa de `pages/` y ninguna página llama a
`fetch`.

**Marcha atrás.** Si la página de dedicatoria estorba en la lectura, se vuelve a mostrar
en la cubierta sin tocar la ruta ni el PDF.

---

## 9. Lectura de ejecución

### 9.1 Cómo se cobró

Tests para la ruta y el exportador; para la interfaz, el recorrido del apartado 4 con Edge
sin cabeza gobernado por CDP contra el backend real y la novela ya escrita
(`vol-cb7143c310`), con capturas de cada estado. El recorrido guarda un título de prueba y
lo deshace al terminar: la novela queda con su título y su dedicatoria, y el `audit_log`
conserva las dos ediciones.

| Requisito | Resultado |
| --- | --- |
| RF-POR-01 a RF-POR-07 | `tests/test_portada.py`: 13 casos en verde. Un título vacío, uno de 121 caracteres, una dedicatoria de 501 y un término vetado responden `422` con su motivo y no guardan nada; prosa, tareas, versiones y hechos no cambian |
| RF-PDF-01 a RF-PDF-03 | `tests/test_exportacion_pdf.py`: orden `portada, dedicatoria, novedades, indice, ficha, capitulos`; dedicatoria en la página 2; sin ella, la sección no existe. Inspección del PDF de la novela real: portada a página completa, dedicatoria sola en la segunda |
| RF-LEC-10 | La cubierta ya no lleva la dedicatoria |
| RF-LEC-11 | «Empezar a leer» → dedicatoria; → capítulo 1 («Capítulo 1 de 10»); ← dedicatoria; ← cubierta. Por botón y por flechas |
| RF-TAL-01 | El bloque abre con el título y la dedicatoria guardados; la previa cambia al escribir y, con un título propio, añade «Para <destinatario>» |
| RF-TAL-02 | Título vacío: aviso «No se ha guardado la portada: el titulo no puede quedar vacio». Título válido: aviso de guardado y barra superior con el título nuevo sin recargar; el aviso sigue a los 6 s |
| RF-TAL-03 | «Guardar» desactivado sin cambios |
| Todos | `pytest` (425), `ruff`, `mypy`, `eslint` y `npm run build` en verde; `grep` de `fetch(` fuera de `shared/api/` sin resultados |

### 9.2 Desviaciones

| # | Desviación | Motivo |
| --- | --- | --- |
| DV-1 | La coordinación vive en `orchestrator/portada.py`, no en la ruta llamando a `store/` y `quality/` como decía el plan | Es lo que hace `encargo.py` con la entrevista: `api/` traduce a HTTP y `orchestrator/` coordina la regla de calidad con el almacén |
| DV-2 | `Guardarrail` gana `coincidencias()`, que busca sin registrar | `revisar()` deja en el `audit_log` un «devolver_al_writer» que en un título no es verdad: no hay writer al que devolverlo |
| DV-3 | La portada del PDF usa los colores de la cubierta de la lectura | Quien la ve en pantalla y quien la recibe impresa tienen que reconocer el mismo libro |
| DV-4 | Se corrige H-1 de SPEC-005: `check_same_thread=False` en `store/database.py`, con su test | El recorrido no podía completarse: FastAPI abre la conexión en un hilo y la cierra en otro, y SQLite respondía `500` de forma intermitente. Es un fallo, no comportamiento nuevo |

