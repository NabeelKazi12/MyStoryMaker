# SPEC-005 · Una interfaz de lectura — Especificación de requisitos (SRS)

| | |
| --- | --- |
| **Identificador** | SPEC-005 |
| **Título** | La entrevista como recorrido por pasos y la lectura como lector de libros: ajustes de lectura, navegación por capítulos, paneles y diálogo propio |
| **Estado** | `construida` el 2026-09-24. Aprobada ese mismo día por la persona autora con el apartado 7 vacío —puerta *Spec aprobada* de `AGENTS.md` §10.5 superada— y el plan del apartado 8 firmado en el mismo acto. Lo construido y sus desviaciones están en §9 |
| **Fecha** | 2026-09-24 |
| **Origen** | Encargo de la persona autora el 2026-09-24: «modifica la interfaz del frontend, quiero que sea más interactiva, que se vea más profesional y que no se vea solo como un golpe de instrucciones. Toma como referencia alguna de las páginas de lectura online» |
| **Referencia** | Lectores web de libros: Kindle Cloud Reader, Google Play Books (de donde sale la tipografía Literata) y Apple Books. De ellos se toman el menú «Aa», la columna centrada, un capítulo por pantalla con paso de página y la barra de progreso de lectura |
| **Documentos de referencia** | `specs/spec2.md` (RF-UI-01 a RF-UI-05), `specs/spec4.md` (RF-PRE-01 a RF-PRE-07), `CLAUDE.md` §2.3 y §4 |
| **Relación con las specs anteriores** | Solo cambia la presentación. No añade rutas, no cambia el contrato y no toca el backend. Todo requisito de SPEC-002 y SPEC-004 que afecte a la interfaz sigue vigente y se vuelve a cobrar aquí |

---

## 1. Problema: qué hay hoy

| # | Hecho observable | Dónde |
| --- | --- | --- |
| P-1 | La entrevista es un formulario de diez campos en una sola columna, precedido y seguido de párrafos explicativos. Se lee como un reglamento, no como una conversación | `pages/crear/CrearNovela.tsx` |
| P-2 | La lectura vuelca todos los capítulos seguidos en una única página. No hay capítulo actual, ni paso de página, ni indicación de cuánto queda | `pages/lectura/Lectura.tsx` |
| P-3 | El índice lateral mezcla tres cosas —capítulos, controles de escritura y versiones— con el mismo peso visual | `nav.indice` |
| P-4 | Quien lee no puede ajustar nada: tamaño de letra, tema y ancho de columna son fijos | `shared/ui/estilos.css` |
| P-5 | «Pedir un cambio» abre `window.prompt`: un diálogo del navegador, sin estilo y sin contexto del personaje | `solicitarCambio` |
| P-6 | Lo escrito en la entrevista se pierde al recargar, contra RF-UI-02 de SPEC-002 | `CrearNovela.tsx` |

---

## 2. Alcance

### 2.1 Qué entra

| # | Entra |
| --- | --- |
| A-01 | Entrevista en **cuatro pasos** —*Para quién*, *Lo que no puede faltar*, *La historia*, *El toque final*— con indicador de paso, «Anterior»/«Siguiente» y un resumen antes de crear el encargo |
| A-02 | Rasgos, recuerdos y palabras vetadas como **listas de etiquetas**: se añade con Intro, se quita con su aspa. Siguen enviándose como listas |
| A-03 | Borrador de la entrevista guardado en el navegador y recuperado al recargar |
| A-04 | Lectura con **barra superior** —título, índice, ajustes, ficha, taller— y **un capítulo por pantalla**, con paso anterior/siguiente por botón y por flechas del teclado |
| A-05 | **Menú de ajustes «Aa»**: tamaño de letra, interlineado, ancho de columna, familia (serifa o sin serifa) y tema (papel, sepia, noche). Persisten en el navegador |
| A-06 | **Barra de progreso de lectura** del capítulo, posición «Capítulo n de N» y minutos estimados de lectura |
| A-07 | **Cubierta**: primera pantalla de la lectura con título, destinatario, dedicatoria y botón «Empezar a leer» o «Seguir leyendo» |
| A-08 | Recordar el último capítulo leído por novela |
| A-09 | **Paneles laterales** que se abren y se cierran solo a petición: *Índice* (con el capítulo actual resaltado y la marca «cambiado»), *Quién es quién* (personajes y lugares en pestañas) y *Taller* (escribir, progreso, PDF, versiones, crear otro encargo) |
| A-10 | **Diálogo propio** para «pedir un cambio», con el nombre del personaje, recorrido por teclado y cierre solo explícito |
| A-11 | Sistema visual nuevo: tokens de color por tema, tipografías Literata (lectura) e Inter (interfaz) servidas por Google Fonts con reserva en las del sistema, y adaptación a móvil |

### 2.2 Qué queda fuera

| # | Fuera | Por qué |
| --- | --- | --- |
| N-01 | Cualquier cambio en backend, rutas o contrato | El encargo es de interfaz. Lo que la pantalla muestra sigue viniendo tal cual del backend |
| N-02 | Validar en el navegador. «Siguiente» no comprueba nada | `CLAUDE.md` §2.3: toda validación ocurre en el backend |
| N-03 | Paginación por páginas físicas dentro de un capítulo | Depende del tamaño de ventana y de letra; un capítulo por pantalla da el paso de página sin ese coste |
| N-04 | Subrayados, notas y marcadores múltiples | Necesitan persistencia en el backend; son otra spec |
| N-05 | La tubería de pruebas del frontend | Es PLAN-002 B-03, en `borrador`, como ya declaró SPEC-004 F-1 a F-4 |
| N-06 | Sustituir el sondeo del progreso por eventos | Decisión de SPEC-004; no cambia aquí |

---

## 3. Requisitos

| Id | Requisito |
| --- | --- |
| RF-INT-01 | La entrevista muestra un paso cada vez, con su número y su nombre, y permite ir y volver entre pasos sin perder lo escrito |
| RF-INT-02 | Ningún paso bloquea el avance por su contenido. «Crear el encargo» envía lo que haya |
| RF-INT-03 | Si el backend responde `422`, la entrevista marca con «falta» los campos nombrados en `huecos`, marca los pasos que los contienen y lleva al primero de ellos; las contradicciones se muestran con el texto del backend |
| RF-INT-04 | Rasgos, recuerdos y vetadas se editan como etiquetas y se envían como listas, en el orden en que se añadieron |
| RF-INT-05 | Lo escrito en la entrevista sobrevive a una recarga y se descarta al crear el encargo o con «Empezar de cero» |
| RF-INT-06 | El aviso de texto con forma de orden (`intentos_de_injection`) se muestra y no se cierra solo |
| RF-LEC-01 | La lectura abre en la cubierta; «Empezar a leer» o «Seguir leyendo» lleva al primer capítulo o al último leído |
| RF-LEC-02 | Se lee un capítulo por pantalla. Anterior y siguiente funcionan por botón y por las flechas izquierda y derecha, salvo cuando el foco está en un campo de texto o hay un diálogo abierto |
| RF-LEC-03 | La barra de progreso refleja la parte leída del capítulo actual; la barra superior dice «Capítulo n de N» |
| RF-LEC-04 | El menú «Aa» cambia tamaño, interlineado, ancho, familia y tema, el cambio se ve en el acto y persiste en el navegador |
| RF-LEC-05 | El tema noche mantiene legibles la prosa, la marca de borrador y la marca «cambiado» |
| RF-LEC-06 | Índice, ficha y taller se abren en panel lateral, uno a la vez, y solo se cierran por su botón, por Escape o al elegir un capítulo del índice. Ninguno se cierra por temporizador |
| RF-LEC-07 | «Pedir un cambio» abre un diálogo propio: se recorre por teclado, lleva el foco al campo, se cierra solo por «Cancelar», Escape o al enviar, y el resultado llega como aviso |
| RF-LEC-08 | El índice resalta el capítulo actual y conserva la marca «cambiado» |
| RF-LEC-09 | La interfaz es usable a 360 px de ancho sin desplazamiento horizontal |
| RF-CON-01 | Se conservan RF-PRE-01 a RF-PRE-07: cada escena lleva su estado de borrador y su motivo, visibles; la marca de modo demostración sigue antes de la prosa; progreso y texto vienen del backend |
| RF-CON-02 | Se conservan RF-UI-03 y RF-UI-04: avisos sin autodestrucción con «limpiar todo», y «no hay nada» distinto de «no he podido leer» |
| RF-CON-03 | Todas las llamadas de red siguen pasando por `shared/api/lectura.ts` |

---

## 4. Verificación

El frontend sigue sin tubería de pruebas (N-05). Lo que no se puede cobrar por test se
cobra por inspección y por el recorrido manual de C-1, y se declara así.

| Requisito | Metodología | Modo | Política |
| --- | --- | --- | --- |
| RF-INT-01 a RF-INT-06 | Recorrido manual contra el backend real: entrevista vacía, entrevista con huecos, texto con forma de orden, recarga a mitad | D | Bloqueante |
| RF-LEC-01 a RF-LEC-08 | Recorrido manual con una novela escrita en modo demostración | D | Bloqueante |
| RF-LEC-09 | Inspección a 360 px con las herramientas del navegador | I | Avisa |
| RF-CON-01, RF-CON-02 | Inspección del código: la marca de borrador y los estados vacíos no dependen del tema ni del paso | I | Bloqueante |
| RF-CON-03 | `grep` de `fetch(` fuera de `shared/api/` sin resultados | A | Bloqueante |
| Todos | `npm run lint` y `npm run build` (incluye `tsc`) en verde | A | Bloqueante |

---

## 5. Impacto

| Dónde | Qué cambia |
| --- | --- |
| `frontend/src/pages/crear/` | `CrearNovela.tsx` reescrito como recorrido por pasos |
| `frontend/src/pages/lectura/` | `Lectura.tsx` partido en cubierta, lector, paneles y taller |
| `frontend/src/shared/ui/` | `estilos.css` reescrito con tokens y temas; componentes nuevos: `Panel`, `Dialogo`, `Etiquetas`, `ajustes` (preferencias de lectura) y `almacen` (lectura y escritura en el navegador, protegidas) |
| `frontend/index.html` | Enlace a Google Fonts y título «MyStoryMaker» |
| `docs/` | Ninguno: no cambia ontología, módulos ni quién comprueba qué |
| Backend, migraciones | Ninguno |

---

## 6. Criterios de aceptación

1. `npm run lint` y `npm run build` en verde.
2. El recorrido C-1 de SPEC-004 —entrevista, escribir una muestra, leer, descargar el PDF— se completa con la interfaz nueva.
3. Cada requisito del apartado 3 comprobado con su metodología del apartado 4, y las desviaciones anotadas en el apartado 9.

---

## 7. Preguntas abiertas

Ninguna.

---

## 8. Plan de implementación — PLAN-005

| | |
| --- | --- |
| **Identificador** | PLAN-005 |
| **Estado** | `aprobado` el 2026-09-24 en la misma firma que la spec. Autoriza escribir código |

| # | Paso | Dónde | Comprobación | Requisitos |
| --- | --- | --- | --- | --- |
| A-1 | Tokens, temas y tipografía; `almacen` con lectura y escritura protegidas | `shared/ui/`, `index.html` | Build; cambio de tema a mano | RF-LEC-04, RF-LEC-05 |
| A-2 | `Panel` y `Dialogo`: foco, Escape, cierre solo explícito | `shared/ui/` | Recorrido por teclado | RF-LEC-06, RF-LEC-07 |
| A-3 | `Etiquetas` | `shared/ui/` | Añadir, quitar, orden | RF-INT-04 |
| B-1 | Entrevista por pasos, resumen, borrador persistente | `pages/crear/` | Recorrido: vacía, con huecos, recarga | RF-INT-01 a RF-INT-06 |
| C-1 | Cubierta, lector por capítulo, flechas, progreso, último capítulo | `pages/lectura/` | Recorrido con novela de demostración | RF-LEC-01 a RF-LEC-03, RF-LEC-08 |
| C-2 | Menú «Aa» | `pages/lectura/`, `shared/ui/` | Cada ajuste, recarga | RF-LEC-04 |
| C-3 | Paneles de índice, ficha y taller; diálogo de cambio | `pages/lectura/` | Recorrido | RF-LEC-06, RF-LEC-07 |
| D-1 | Adaptación a móvil | `shared/ui/estilos.css` | Inspección a 360 px | RF-LEC-09 |
| D-2 | Cierre: lint, build, `grep` de `fetch(`, recorrido C-1, spec a `construida` | `specs/spec5.md` | Apartado 4 | Todos |

**Módulos.** Todo queda en `pages/` y `shared/`; `shared/` no importa de `pages/`, y
ninguna página llama a `fetch`.

**Marcha atrás.** Si el lector por capítulo no se sostiene con novelas largas, se vuelve
al desplazamiento continuo conservando barra superior, ajustes y paneles. La marca de
borrador de cada escena no se quita en ningún caso: no es cosmética (PLAN-004 §10.8).

---

## 9. Lectura de ejecución

### 9.1 Cómo se cobró

El recorrido C-1 se hizo con Edge sin cabeza gobernado por CDP contra el backend real y
una novela de 10 capítulos en escritura, con capturas de cada estado. Es la misma
demostración del apartado 4, automatizada para poder repetirla; no es una tubería de
pruebas y no sustituye a N-05.

| Requisito | Resultado |
| --- | --- |
| RF-INT-01, RF-INT-05 | Ida y vuelta entre pasos sin pérdida; tras recargar, nombre y etiquetas siguen ahí; «Empezar de cero» los descarta |
| RF-INT-02, RF-INT-03 | Con la entrevista a medias, «Crear el encargo» envía; el `422` marca los campos, los tres pasos con hueco y lleva al primero |
| RF-INT-04 | Etiquetas añadidas con el botón y con Intro, quitadas con el aspa |
| RF-INT-06 | Por inspección: con `intentos_de_injection` la pantalla se queda en el aviso hasta pulsar «Ir a la novela» |
| RF-LEC-01, RF-LEC-02 | Cubierta → «Empezar a leer»; la flecha derecha lleva al capítulo 2; tras recargar, «Seguir leyendo · <capítulo>» |
| RF-LEC-03, RF-LEC-08 | Barra de progreso visible al desplazarse; «Capítulo 2 de 10»; índice con el actual resaltado |
| RF-LEC-04, RF-LEC-05 | Sepia, noche y cambio de tamaño aplicados en el acto; el tema noche legible, marca de borrador con borde propio |
| RF-LEC-06, RF-LEC-07 | Escape cierra el menú «Aa» y el panel; con el diálogo encima, Escape cierra solo el diálogo y el panel sigue abierto |
| RF-LEC-09 | A 360 px, `scrollWidth` = 360 en cubierta, capítulo y entrevista |
| RF-CON-03 | `grep` de `fetch(` fuera de `shared/api/`: sin resultados |
| Todos | `npm run lint` y `npm run build` en verde; sin errores de consola en el recorrido |

### 9.2 Desviaciones

| # | Desviación | Motivo |
| --- | --- | --- |
| DV-1 | La pantalla de error de la lectura lleva un botón **«Reintentar»** que la spec no pedía | El recorrido encontró H-1; sin él, un fallo pasajero obliga a recargar la página entera |
| DV-2 | El repaso se muestra como quinta entrada del indicador de pasos | Hace que el repaso sea alcanzable desde cualquier paso; los pasos de la entrevista siguen siendo cuatro |
| DV-3 | El indicador no marca con ✓ los pasos ya recorridos | Un paso recorrido no es un paso completo: el ✓ afirmaría algo que solo sabe el backend (N-02) |
| DV-4 | La cubierta omite «Para <destinatario>» cuando el título ya lo contiene | El título que compone el backend suele ser ya «Para …», y repetirlo debajo era eco |

### 9.3 Hallazgos fuera de alcance

| # | Hallazgo | Qué se hace |
| --- | --- | --- |
| H-1 | Con el worker escribiendo, las rutas de lectura responden `500` de forma intermitente a peticiones concurrentes: 4 de 45 en una ráfaga de lectura, texto y escritura en paralelo | Es del backend (N-01) y se reproduce igual con la interfaz anterior. La interfaz lo muestra como «no he podido leer» y permite reintentar. Queda para una spec del backend |
