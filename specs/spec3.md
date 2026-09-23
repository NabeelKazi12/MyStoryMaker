# SPEC-003 · La novela personalizada de regalo — Especificación de requisitos (SRS)

| | |
| --- | --- |
| **Identificador** | SPEC-003 |
| **Título** | Del generador de novela al producto del alcance: entrevista, lectura, harness de tres roles, guardarraíles, verificación formal y observabilidad |
| **Estado** | `aprobada` el 2026-09-23 por @Nabeel, con el apartado 9 vacío y los 61 requisitos con verificación asignada: la puerta *Spec aprobada* de `AGENTS.md` §10.5 queda superada. El plan del apartado 10 queda en `borrador` y necesita su propia firma antes de escribir código |
| **Fecha** | 2026-09-23 |
| **Origen** | El documento de alcance del proyecto entregado por la persona autora el 2026-09-23 |
| **Documentos de referencia** | `docs/definitions.md`, `docs/architecture.md`, `docs/verification.md`, `AGENTS.md`, `CLAUDE.md`, `specs/spec1.md` (SPEC-001, construida) y `specs/spec2.md` (SPEC-002, propuesta) |
| **Relación con las specs anteriores** | SPEC-001 construyó el núcleo y está en el repositorio. SPEC-002 especifica el frontend de operación. Esta spec **no las sustituye**: declara el delta entre lo construido y el alcance, y dice qué de SPEC-002 se absorbe |

> Esta spec es el delta. No repite lo que el repositorio ya hace: parte del inventario del
> apartado 1 y especifica únicamente lo que falta para cumplir el alcance. El **plan de
> implementación no está aquí**: según `AGENTS.md` §10.3 se añade después de que esta spec
> pase a `aprobada`, y hasta entonces no se escribe código.

---

## 1. Problema: qué hay y qué pide el alcance

El repositorio tiene hoy un núcleo construido y probado —216 tests en verde, 31 tablas, 12
verificadores deterministas, 4 puertas, semáforo de crédito, DAG y máquina de estados— y
**ninguna de las siete áreas del alcance completa**. El inventario, área por área:

| # | Área del alcance | Qué existe hoy | Qué falta |
| --- | --- | --- | --- |
| 1 | Configuración por entrevista | `Brief` como clase y `POST /brief` | Todo el agente entrevistador: no hay rol, ni detección de datos que faltan, ni detección de contradicciones, ni extracción de hechos de texto libre, ni tratamiento de ese texto como no confiable |
| 2 | Lectura web o PDF | `frontend/` vacío; SPEC-002 especifica un frontend de **operación**, no de lectura | Índice navegable, ficha de personajes y lugares con enlace al capítulo, portada con dedicatoria, petición de cambio desde la página, marcado de capítulos cambiados, versión anterior conservada, exportación a PDF |
| 3 | Harness de tres roles | Un rol implementado: `Redactor`. Máquina de estados, escalera de reintentos y contrato común ya existen | Planner y editor/critic; una skill reutilizable; dos hooks —validación de capítulo y policy—; registro de tokens y coste por novela en Langfuse |
| 4 | Memoria | Canon en SQLite con 31 tablas; `Hecho` con vigencia; `PaqueteDeContexto` reconstruido en cada invocación | Trazabilidad hecho → **capítulos** donde se usa (hoy solo hay enlace a escena); tabla de cronología; resúmenes por capítulo; checkpoint por capítulo con reanudación |
| 5 | Validación y evaluación | 12 verificadores deterministas, 4 puertas, evidencia ausente distinguida | Los cuatro tipos nombrados y enrutados a Langfuse; validación visual por browser MCP; LLM-as-judge con rúbrica; revisión humana comparada; **Lean 4**; **TLA+**; los cinco briefs de prueba y la tabla de resultados |
| 6 | Observabilidad | `Procedencia` y las cinco señales, registradas en SQLite | Langfuse entero: trazas por novela, sesión, spans por rol y por tool, coste y latencia, scores de validador, prompts versionados |
| 7 | Guardarraíles | Un verificador de `vocabulario_prohibido` del `PerfilDeEstilo`, comparación por minúsculas | Los tres niveles en SQLite, normalización de acentos y plurales, bucle de reescritura con límite, audit log, tests por nivel y variante. **El techo de 100.000 tokens concurrentes ya se cumple y se aplica** desde el cambio del 2026-09-23 |

Fuera de las siete áreas, el alcance exige entregables de repositorio que tampoco existen:
la novela de ejemplo en `/ejemplos/`, seis documentos de proceso en `docs/`, `.claude/` con
memoria, comandos y configuración de un MCP de navegador, y `.env.example`.

**La diferencia de fondo, y es la que ordena toda la spec:** lo construido es un generador
de novela; el alcance pide un **producto de regalo personalizado**, con un destinatario real
al que hay que nombrar, unos recuerdos que deben aparecer y unas palabras que no pueden
aparecer. Eso no es una capa por encima: cambia la ontología y por tanto exige
`RegistroDeDecision` (`AGENTS.md` §10.1).

---

## 2. Alcance

### 2.1 Qué entra

| # | Entra | Área |
| --- | --- | --- |
| A-01 | Rol entrevistador, con detección de huecos y de contradicciones, y extracción de hechos de texto libre no confiable | 1 |
| A-02 | Ontología del destinatario y de los elementos personalizados obligatorios | 1, 4 |
| A-03 | Lectura web con índice, ficha de personajes y lugares, portada con dedicatoria, y petición de cambio desde la página | 2 |
| A-04 | Regeneración selectiva por hecho cambiado, con marcado de capítulos modificados y conservación de la versión anterior | 2, 4 |
| A-05 | Exportación a PDF de la novela, con la página de novedades | 2 |
| A-06 | Roles planner y editor/critic, skill reutilizable y los dos hooks | 3 |
| A-07 | Trazabilidad hecho → capítulo, tabla de cronología, resúmenes por capítulo y checkpoint por capítulo | 4 |
| A-08 | Guardarraíl de palabras prohibidas en tres niveles, con normalización, bucle limitado y audit log | 7 |
| A-09 | Validadores de los cuatro tipos, incluida la validación visual por browser MCP | 5 |
| A-10 | Verificación formal de la historia en Lean 4 y del harness en TLA+ | 5 |
| A-11 | Observabilidad completa en Langfuse, con prompts versionados | 6 |
| A-12 | Los cinco briefs de prueba, la tabla por validador y la iteración de tuning documentada | 5 |
| A-13 | Entregables de repositorio: novela de ejemplo, documentos de proceso, `.claude/` y `.env.example` | — |

### 2.2 Qué no entra

| # | No entra | Por qué |
| --- | --- | --- |
| N-01 | Pagos, impresión física, ilustraciones, audio y despliegue en producción | El alcance los declara fuera |
| N-02 | Los apartados opcionales: servidor MCP de novelas, tools de escritura MCP, linters de prosa adicionales, linter de edición manual, invariantes extra de Lean, TLA+ del servidor MCP, login y agente de seguridad | Suman nota, no son requisito. Cada uno entraría por su propia spec. **Excepción**: el MCP de navegador de `.claude/` sí es obligatorio, y entra como A-13 |
| N-03 | Sustituir el panel de operación de SPEC-002 | Son cosas distintas: aquélla es la interfaz de quien opera el sistema; ésta es la lectura de quien recibe la novela. Conviven |
| N-04 | Cambiar el modelo, el techo de 100.000 o el orden del paquete de contexto | Ya decididos: D-17, D-13 y D-16 |

---

## 3. Supuestos y decisiones asumidas

Se escriben aquí, y no se dan por sabidas, porque cada una cambia trabajo. Si alguna es
falsa, se corrige la spec antes de planificar.

| # | Supuesto | Si es falso |
| --- | --- | --- |
| S-01 | **El formato de lectura es web, con PDF exportado.** *Confirmado por la persona autora el 2026-09-23.* La web es lo que habilita la petición de cambio desde la propia página, y el PDF se exige igualmente como evidencia en `/ejemplos/` | Deja de ser supuesto: es decisión. Cambiarlo ahora rehace la fase E |
| S-02 | Langfuse es el destino de trazas, spans y scores; `Procedencia` sigue siendo la fuente de verdad en SQLite y Langfuse es la vista | Si Langfuse debe ser la fuente, cambia `architecture.md` §9 y el sistema pasa a depender de un servicio externo para reproducir una ejecución |
| S-03 | Una persona autora y una novela en curso por proceso, como en SPEC-001 | Reaparece concurrencia; la especificación TLA+ tendría que modelarla |
| S-04 | El modelo es `claude-haiku-4-5` (D-17) y el techo de 100.000 tokens concurrentes se mantiene y ya se aplica | — |
| S-05 | Lean 4 y TLC se ejecutan en desarrollo y en la tubería, no dentro de la generación de cada capítulo | Si Lean tuviera que correr por capítulo, cambia el presupuesto de latencia del bucle |
| S-06 | **Langfuse, Lean 4 con `lake` y TLA+ con TLC están disponibles** en el entorno de la persona autora, según su confirmación del 2026-09-23 | Si alguna falta, su fase empieza por dejar la herramienta instalada y documentada, y eso se anota como desviación |

---

## 4. Requisitos

Uno por fila, comprobable por separado. La columna *Origen* cita el apartado del alcance.

### 4.1 Configuración y entrevista — RF-CFG

| ID | Requisito | Origen |
| --- | --- | --- |
| RF-CFG-01 | Existe un rol **Entrevistador** con su contrato común de `AGENTS.md` §3, que recoge nombre, edad, rasgos, recuerdos, género, tono y extensión del destinatario | 1 |
| RF-CFG-02 | La entrevista recoge además las palabras y temas que el cliente no quiere que aparezcan, y los persiste como lista de nivel novela del guardarraíl | 1, 7 |
| RF-CFG-03 | El sistema detecta los datos que faltan y los pide, en lugar de rellenarlos con suposiciones | 1 |
| RF-CFG-04 | El sistema detecta **al menos un tipo de contradicción** declarada —edad frente a género o tono— y la devuelve nombrando los dos datos que chocan | 1 |
| RF-CFG-05 | El cliente puede pegar texto libre del que se extraen hechos, y ese texto se trata como **contenido no confiable**: no puede alterar instrucciones del sistema ni políticas | 1 |
| RF-CFG-06 | La salida de la entrevista es un brief estructurado y validado contra su schema; un brief que no valida no entra al plan | 1 |
| RF-CFG-07 | Los elementos personalizados obligatorios —nombre del destinatario, recuerdos declarados— quedan marcados como tales y son consultables | 1, 5 |

### 4.2 Memoria y story bible — RF-BIB

| ID | Requisito | Origen |
| --- | --- | --- |
| RF-BIB-01 | Cada `Hecho` registra **en qué capítulos se usa**, no solo en qué escenas | 4 |
| RF-BIB-02 | Existe una tabla de cronología con evento, momento, personajes, lugar y fecha de nacimiento por personaje, que es la que alimenta el validador formal | 4, 5c |
| RF-BIB-03 | Cada capítulo tiene un resumen que se usa para construir el contexto de los siguientes | 4 |
| RF-BIB-04 | Existe checkpoint por capítulo: si la generación falla, se reanuda desde el último capítulo completado, sin duplicar ni perder capítulos | 4 |
| RF-BIB-05 | La story bible es consultable por personaje, lugar, hecho y cronología | 4, opcional MCP |

### 4.3 Harness — RF-HAR

| ID | Requisito | Origen |
| --- | --- | --- |
| RF-HAR-01 | Existen y se invocan al menos tres roles: **planner**, **writer** y **editor/critic**, cada uno con su prompt versionado | 3 |
| RF-HAR-02 | `CLAUDE.md` es el fichero de instrucciones del harness, cuidado y legible | 3 |
| RF-HAR-03 | Existe una **skill reutilizable**, commiteada y referenciada desde `docs/` | 3 |
| RF-HAR-04 | Existen dos hooks: uno de **validación de capítulo** y otro de **policy**, con su punto de ejecución declarado | 3 |
| RF-HAR-05 | Toda tool tiene schema validado, y una llamada que no valida es fallo de contrato | 3 |
| RF-HAR-06 | Los reintentos tienen límite, y agotarlo detiene la generación informando, en lugar de reintentar indefinidamente | 3 |

### 4.4 Lectura y versiones — RF-LEC

| ID | Requisito | Origen |
| --- | --- | --- |
| RF-LEC-01 | La lectura incluye índice de capítulos navegable | 2 |
| RF-LEC-02 | La lectura incluye ficha de personajes y lugares generada **desde la story bible**, con enlace al capítulo donde aparece cada uno | 2 |
| RF-LEC-03 | La lectura incluye portada con dedicatoria personalizada | 2 |
| RF-LEC-04 | Desde la página se puede seleccionar un fragmento o un hecho y pedir un cambio | 2 |
| RF-LEC-05 | Ante un cambio de hecho, el sistema identifica los capítulos que usan ese hecho y regenera **solo** ésos | 2, 4 |
| RF-LEC-06 | La lectura marca qué capítulos han cambiado respecto a la versión anterior | 2 |
| RF-LEC-07 | La versión anterior de la novela se conserva siempre | 2 |
| RF-LEC-08 | La novela se exporta a PDF con índice, ficha, portada y, cuando hay regeneración, página inicial de novedades con enlaces internos | 2 |

### 4.5 Guardarraíles — RF-GRD

| ID | Requisito | Origen |
| --- | --- | --- |
| RF-GRD-01 | Las listas de palabras prohibidas viven en SQLite en tres niveles: globales, por novela y las definidas por el cliente en la configuración | 7 |
| RF-GRD-02 | La detección **normaliza antes de comparar**: mayúsculas, acentos, plurales y variantes simples | 7 |
| RF-GRD-03 | El guardarraíl se aplica en código sobre **cada capítulo antes de aceptarlo** | 7 |
| RF-GRD-04 | Una coincidencia devuelve el capítulo al writer para reescribirlo, con límite de intentos; agotado el límite, la generación se detiene e informa | 7 |
| RF-GRD-05 | Cada coincidencia queda registrada en el audit log y en Langfuse | 7, 6 |
| RF-GRD-06 | Existe un audit log de las decisiones del policy engine | 7 |
| RF-GRD-07 | El sistema no supera 100.000 tokens concurrentes | 7 |

### 4.6 Validadores — RF-VAL

| ID | Requisito | Tipo | Origen |
| --- | --- | --- | --- |
| RF-VAL-01 | El brief y la salida de cada rol cumplen su schema | Programático | 5a |
| RF-VAL-02 | El nombre del destinatario y los personajes aparecen escritos **exactamente** como en la story bible | Programático | 5a |
| RF-VAL-03 | La longitud de cada capítulo está dentro del rango declarado | Programático | 5a |
| RF-VAL-04 | Cada elemento personalizado obligatorio aparece en al menos un capítulo, comprobado contra la tabla de hechos de SQLite | Programático | 5a |
| RF-VAL-05 | El guardarraíl de palabras prohibidas se ejecuta como validador con su nombre y su punto | Programático | 5a, 7 |
| RF-VAL-06 | Validación visual por browser MCP: se abre la novela, se navega por los capítulos y se verifica que índice, ficha y portada renderizan; un error visual se registra como fallo y vuelve al rol que corresponda | Programático | 5a |
| RF-VAL-07 | LLM-as-judge con rúbrica que puntúa continuidad, tono, calidad narrativa —arco, coherencia de personajes, ritmo— y naturalidad de la personalización, con puntuación **por criterio** y justificación | Semántico | 5b |
| RF-VAL-08 | Revisión humana de al menos una novela completa con la misma rúbrica, comparada con el juicio del LLM | Semántico | 5b |
| RF-VAL-09 | Cada validador tiene **nombre**, **punto de ejecución** declarado —hook, rol editor o puerta previa a publicar— y envía su resultado a Langfuse como score | Todos | 5 |

### 4.7 Verificación formal de la historia — RF-LEAN

| ID | Requisito | Origen |
| --- | --- | --- |
| RF-LEAN-01 | Desde la story bible en SQLite se **genera** un fichero Lean con los hechos temporales: eventos, momento, personajes presentes, lugar y fechas de nacimiento | 5c |
| RF-LEAN-02 | Se definen al menos dos invariantes en Lean, de entre: orden temporal de los eventos, edad coherente con la fecha de nacimiento, un personaje no está en dos lugares en el mismo momento, un personaje no aparece tras un evento que lo excluye | 5c |
| RF-LEAN-03 | La verificación se ejecuta de forma automática (`lake build` o `lean`) | 5c |
| RF-LEAN-04 | Si la verificación falla, **la versión no se publica** y el fallo vuelve al editor como feedback | 5c |
| RF-LEAN-05 | Se documenta al menos un caso real en que el validador formal detecta una incoherencia que los otros no detectaron, o se justifica por qué no apareció ninguno | 5c |

### 4.8 Verificación formal del sistema — RF-TLA

| ID | Requisito | Origen |
| --- | --- | --- |
| RF-TLA-01 | Existe una especificación TLA+ o PlusCal del flujo como máquina de estados: configuración → planificación → escritura → validación → publicación, con reintentos, reanudación desde checkpoint y regeneración por cambio del lector | 5d |
| RF-TLA-02 | Al menos tres invariantes de seguridad: no se publica una versión con un capítulo que no pasó todos los validadores; la reanudación no duplica ni pierde capítulos; la versión anterior se conserva; los reintentos no superan el límite | 5d |
| RF-TLA-03 | Al menos una propiedad de *liveness*: toda generación termina publicando o deteniéndose con error, y nunca queda en bucle infinito | 5d |
| RF-TLA-04 | Verificación con TLC sobre un modelo pequeño —5 capítulos, 2 reintentos—, con la configuración commiteada | 5d |
| RF-TLA-05 | El `README` explica qué estado o transición del código implementa cada acción de la especificación | 5d |
| RF-TLA-06 | Todo contraejemplo que TLC encontrara durante el desarrollo queda documentado junto con el cambio que provocó en el código | 5d |

### 4.9 Observabilidad — RF-OBS

| ID | Requisito | Origen |
| --- | --- | --- |
| RF-OBS-01 | Cada generación de novela es una traza en Langfuse, agrupada por **sesión**: una por novela, incluida la entrevista y las regeneraciones posteriores | 6 |
| RF-OBS-02 | Cada rol y cada llamada a tool aparece como span con nombre identificable | 6 |
| RF-OBS-03 | Tokens, coste y latencia visibles por llamada, por capítulo y por novela | 6, 3 |
| RF-OBS-04 | Los resultados de todos los validadores —programáticos, semánticos y Lean— se envían como scores asociados a su traza. TLC no: se ejecuta en desarrollo | 6 |
| RF-OBS-05 | Los prompts están versionados en Langfuse, de modo que la iteración de tuning muestre qué versión produjo cada resultado | 6 |

### 4.10 Evaluación y entregables — RF-EVA

| ID | Requisito | Origen |
| --- | --- | --- |
| RF-EVA-01 | Cinco briefs de prueba, incluido **uno adversarial** con *injection* en el texto libre y **uno** diseñado para provocar una incoherencia temporal | 5 |
| RF-EVA-02 | Una tabla que muestra, por brief, qué validadores pasaron y cuáles fallaron | 5 |
| RF-EVA-03 | Una iteración de tuning documentada, con resultados antes y después | 5 |
| RF-EVA-04 | `/ejemplos/novela-ejemplo.pdf`: una novela completa de 10 capítulos generada con el brief de ejemplo del `README` | Entregables |
| RF-EVA-05 | `docs/` contiene spec inicial, trade-offs, explainers, diagramas, registro de iteraciones y red-team log | Entregables |
| RF-EVA-06 | `.claude/` commiteada con memoria y comandos; `.claude/mcp.json` incluye un MCP de inspección de navegador; el uso real del navegador queda documentado en `docs/` | Entregables |
| RF-EVA-07 | Ninguna API key en el repositorio; existe `.env.example` | Entregables |

---

## 5. Verificación

Método por requisito, con el marco T/A/I/D/U de `docs/verification.md` §1–§2 y la regla que
ordena el documento: **solo lo determinista bloquea**.

### 5.1 Tabla de cobertura

| Requisitos | Nivel | Metodología | Clase | Punto de ejecución | Autoridad |
| --- | --- | --- | --- | --- | --- |
| RF-CFG-01, RF-CFG-06, RF-HAR-05, RF-VAL-01 | Artefacto | Validación contra schema, con casos válidos e inválidos por rol | T | Hook de validación | Bloqueante |
| RF-CFG-03, RF-CFG-04 | Artefacto | Casos de brief incompleto y de brief contradictorio, con el hueco y el par en conflicto esperados | T | Rol entrevistador | Bloqueante |
| RF-CFG-05 | Proceso | Corpus adversarial de *injection* en texto libre; se comprueba que la instrucción no altera comportamiento ni políticas | D | Evaluación, brief adversarial de RF-EVA-01 | Bloqueante |
| RF-CFG-07, RF-VAL-04 | Artefacto | Consulta a la tabla de hechos: cada elemento obligatorio aparece en ≥ 1 capítulo | T | Puerta previa a publicar | Bloqueante |
| RF-BIB-01, RF-BIB-02, RF-BIB-05 | Artefacto | Pruebas de repositorio sobre el esquema nuevo, con migración aplicada | T | Suite | Bloqueante |
| RF-BIB-03 | Artefacto | Prueba de que el contexto del capítulo *n* contiene el resumen de los anteriores y no su prosa | T | Suite | Bloqueante |
| RF-BIB-04, RF-HAR-06, RF-GRD-04 | Artefacto | Pruebas de integración con caída simulada y con límite agotado | T | Suite | Bloqueante |
| RF-BIB-04, RF-TLA-01 a RF-TLA-04 | Artefacto | Comprobación de modelos con TLC sobre el modelo pequeño | A | Desarrollo y tubería, no en generación | Bloqueante |
| RF-HAR-01 a RF-HAR-04 | Artefacto | Inspección en revisión más prueba de que los tres roles se invocan en una generación | I + T | Suite y revisión | Bloqueante |
| RF-LEC-01 a RF-LEC-03, RF-LEC-06 | Artefacto | Validación visual por browser MCP sobre la lectura publicada | T | Puerta previa a publicar | Bloqueante |
| RF-LEC-04, RF-LEC-05 | Artefacto | Caso: cambiar un hecho usado por dos capítulos regenera exactamente esos dos | T | Suite | Bloqueante |
| RF-LEC-07 | Artefacto | Prueba de que tras regenerar la versión anterior sigue siendo legible, más el invariante TLA+ correspondiente | T + A | Suite y TLC | Bloqueante |
| RF-LEC-08 | Artefacto | Exportación a PDF de una novela de prueba y comprobación de índice, ficha, portada y novedades | T | Suite | Bloqueante |
| RF-GRD-01 a RF-GRD-03, RF-VAL-05 | Artefacto | Tests por nivel —global, novela, cliente— y por variante —acento y plural— | T | Hook de policy, antes de aceptar el capítulo | Bloqueante |
| RF-GRD-05, RF-GRD-06 | Artefacto | Prueba de que cada coincidencia deja fila en el audit log y score en Langfuse | T | Suite | Bloqueante |
| RF-GRD-07 | Artefacto | Invariantes ya construidos: presupuesto fuera de rango, prompt sobredimensionado y semáforo | T | Suite | Bloqueante |
| RF-VAL-02, RF-VAL-03 | Artefacto | Comparación exacta contra la story bible y medición de longitud por capítulo | T | Hook de validación de capítulo | Bloqueante |
| RF-VAL-06 | Artefacto | Recorrido con browser MCP sobre la lectura, con captura y aserción por elemento | T | Puerta previa a publicar | Bloqueante |
| RF-VAL-07 | Proceso | Juez con rúbrica, puntuación por criterio y justificación; varianza *test-retest* vigilada | D | Rol editor | **Penaliza**, no bloquea |
| RF-VAL-08 | Proceso | Revisión humana de una novela completa con la misma rúbrica y comparación con el juez | I | Cierre | Penaliza |
| RF-VAL-09, RF-OBS-01 a RF-OBS-05 | Proceso | Inspección de una traza real: sesión, spans por rol y tool, coste, latencia, scores y versión de prompt | I + D | Cierre de cada iteración | Bloqueante para el cierre |
| RF-LEAN-01 a RF-LEAN-04 | Artefacto | Generación del fichero Lean desde SQLite y `lake build` en la tubería | A | Puerta previa a publicar | Bloqueante |
| RF-LEAN-05, RF-TLA-05, RF-TLA-06 | — | Inspección del documento de iteraciones y del `README` | I | Cierre | Bloqueante para el cierre |
| RF-EVA-01 a RF-EVA-03 | Proceso | Ejecución de los cinco briefs y volcado de la tabla por validador | D | Evaluación | Bloqueante para el cierre |
| RF-EVA-04 a RF-EVA-07 | — | Inspección del árbol del repositorio y análisis estático de secretos | I + A | Cierre | Bloqueante |

### 5.2 Lo que no es comprobable tal como está escrito

Ninguna fila U se queda sin decisión al lado.

| Requisito | Por qué es U | Decisión |
| --- | --- | --- |
| «Calidad narrativa» de RF-VAL-07 | No hay predicado que la decida; un juez basado en modelo varía entre llamadas | Se reformula como puntuación por criterio con umbral declarado, y **penaliza**: no bloquea. Bloquear con una puntuación inestable produce bucles caros |
| «La personalización está integrada de forma natural y no forzada» | Mismo caso, y además depende del destinatario | Se cobra en la rúbrica y se contrasta con la revisión humana de RF-VAL-08. Riesgo aceptado y escrito |
| «Variantes simples» de RF-GRD-02 | «Simple» no acota nada | Se cierra la lista de transformaciones en la spec del plan: minúsculas, sin acentos, plural en -s/-es y separadores. Lo que quede fuera se declara |
| RF-LEAN-05, en su rama «o justificar por qué no se encontró ninguno» | Depende de que exista el caso | Se acepta: si tras las cinco evaluaciones no aparece, el documento de iteraciones justifica por qué, que es exactamente lo que el alcance permite |

### 5.3 Huecos declarados

- **El juez y el writer pueden compartir modelo**, y un juez que puntúa prosa salida de su
  mismo prompt la aprueba: es F-07 de `verification.md` §11, ya catalogado, y su validador
  V-07 sigue vigente aquí.
- **`contar_tokens` sigue siendo una heurística**; el techo de 100.000 vale lo que valga esa
  cuenta hasta que se sustituya por el recuento del proveedor.
- **La validación visual por browser MCP comprueba que algo renderiza**, no que se lea bien:
  la maquetación sigue siendo inspección humana.

---

## 6. Impacto

### 6.1 Ontología y `docs/`

| Documento | Cambio |
| --- | --- |
| `definitions.md` | **Cambia.** Entran `Destinatario`, `ElementoPersonalizado`, `EventoDeCronologia`, `ListaDePalabrasProhibidas` y `VersionDeNovela`. Cada clase nueva exige `RegistroDeDecision` (`AGENTS.md` §10.1) |
| `architecture.md` | **Cambia.** Roles nuevos en §5, observabilidad en §9 —Langfuse como vista, SQLite como fuente—, y la frontera con Lean y TLC |
| `verification.md` | **Cambia.** Entra la tabla de §5.1 con los cuatro tipos de validador y su punto de ejecución |
| `docs/` nuevos | Spec inicial, trade-offs, explainers, diagramas, registro de iteraciones y red-team log (RF-EVA-05) |
| `CLAUDE.md` | **Cambia.** Comandos nuevos —Lean, TLC, exportación a PDF, evaluación— y la sección de roles |

### 6.2 Módulos y migraciones

| Módulo | Cambio |
| --- | --- |
| `backend/domain/` | Clases nuevas de 6.1 |
| `backend/store/` + `backend/migrations/` | **Migración**: uso de hecho por capítulo, cronología, resúmenes por capítulo, checkpoint, listas de palabras prohibidas, audit log y versiones de novela |
| `backend/agents/` | Entrevistador, planner y editor/critic |
| `backend/quality/` | Validadores nuevos y el guardarraíl |
| `backend/observability/` | Nuevo: cliente de Langfuse. Es el único directorio nuevo que esta spec crea |
| `backend/formal/` | Nuevo: generador del fichero Lean desde SQLite |
| `frontend/` | La lectura de A-03 y A-04 |
| `spec/` y raíz | `tla/` con la especificación y su configuración; `lean/` con el proyecto; `/ejemplos/` |

**Las cinco decisiones de stack de `architecture.md` §2.1 pasan a siete**: Langfuse y Lean 4
son dependencias nuevas y cada una necesita su `RegistroDeDecision`.

---

## 7. Criterios de aceptación

1. Una entrevista completa produce un brief validado, detecta un hueco y detecta una contradicción declarada.
2. Un texto libre con *injection* no altera el comportamiento del sistema, y el caso queda en el red-team log.
3. La novela se lee con índice, ficha de personajes y lugares enlazada al capítulo, y portada con dedicatoria.
4. Cambiar un hecho desde la lectura regenera **solo** los capítulos que lo usan, marca cuáles cambiaron y conserva la versión anterior.
5. El PDF exportado existe en `/ejemplos/novela-ejemplo.pdf` con 10 capítulos.
6. Los tres roles se invocan en una generación y aparecen como spans nombrados en una traza de Langfuse, con tokens, coste y latencia por llamada, capítulo y novela.
7. El guardarraíl detecta un caso de cada nivel y un caso de variante, devuelve el capítulo al writer, respeta el límite y deja fila en el audit log y score en Langfuse.
8. `lake build` verifica los invariantes de Lean sobre la cronología generada desde SQLite, y un fallo impide publicar.
9. TLC verifica los tres invariantes de seguridad y la propiedad de *liveness* sobre el modelo de 5 capítulos y 2 reintentos, con la configuración commiteada.
10. Los cinco briefs corren y producen la tabla por validador; la iteración de tuning muestra antes y después con la versión de prompt de cada resultado.
11. `docs/` contiene los seis documentos de proceso; `.claude/` está commiteada con su `mcp.json` de navegador; no hay ninguna API key y existe `.env.example`.
12. `uv run pytest`, `uv run pytest -m invariants`, `ruff`, `mypy backend/`, `npm run build` y `npm run lint` en verde.

---

## 8. Riesgos

| # | Riesgo | Mitigación |
| --- | --- | --- |
| R-01 | El alcance es cuatro o cinco veces el de SPEC-001 y se intenta entero a la vez | El plan lo parte en fases con entregable propio; ninguna fase empieza sin que la anterior tenga su suite en verde |
| R-02 | Lean y TLA+ se quedan en adorno: una especificación que no corresponde al código | RF-TLA-05 obliga a mapear acción ↔ transición en el `README`, y RF-LEAN-04 hace que Lean pare una publicación de verdad |
| R-03 | Langfuse se convierte en dependencia dura y sin red nada funciona | S-02 lo deja como vista: la fuente sigue siendo `Procedencia` en SQLite, y la suite corre sin Langfuse |
| R-04 | La ontología del destinatario se cuela como campos sueltos en `Brief` | Entra por `definitions.md` con `RegistroDeDecision`, como cualquier otra clase |
| R-05 | El guardarraíl con normalización produce falsos positivos y bloquea capítulos correctos | El límite de intentos de RF-GRD-04 lo hace visible en lugar de infinito, y cada coincidencia queda en el audit log para revisarla |
| R-06 | La regeneración selectiva rompe la continuidad entre capítulos vecinos | RF-BIB-01 es la precondición: sin saber qué capítulos usan el hecho no se puede regenerar solo ésos. Lean vuelve a verificar la cronología antes de publicar |

---

## 9. Preguntas abiertas

**Ninguna.** Las seis quedaron resueltas por la persona autora el 2026-09-23, antes de la
aprobación y no después, que es lo que `AGENTS.md` §10.2 pide. Se conservan aquí con su
respuesta porque el apartado 2 y el apartado 3 se apoyan en ellas.

| # | Pregunta | Respuesta |
| --- | --- | --- |
| P-01 | Formato de lectura | **Web, con PDF exportado.** Fija S-01, A-03 y A-05 |
| P-02 | Qué pasa con SPEC-002 | **Se aplaza.** Queda `propuesta` y en espera; se construye primero la lectura que el alcance evalúa. No se descarta ni se absorbe: N-03 sigue vigente y el panel de operación se retoma cuando esta spec cierre |
| P-03 | Apartados opcionales | **Ninguno entra ahora.** N-02 se mantiene entero. El esquema de la fase A deja sitio para propietario y versiones, para que añadir login o servidor MCP más adelante no obligue a rehacer la migración |
| P-04 | Langfuse | **Disponible.** La fase D no arranca instalando nada |
| P-05 | Lean 4 y TLA+ | **Disponibles**, con `lake` y con TLC. La fase F empieza por la especificación, no por la instalación |
| P-06 | Revisión humana de RF-VAL-08 | **La hace la persona autora sobre la novela de ejemplo** de `/ejemplos/novela-ejemplo.pdf`, que es la de 10 capítulos del `README`. Se elige ésa porque es la única que el repositorio conserva entera, así que su juicio se puede releer contra el texto exacto que lo produjo |

---

## 10. Plan de implementación — PLAN-003

| | |
| --- | --- |
| **Estado** | `borrador`. La puerta *Plan aprobado* de `AGENTS.md` §10.5 no está superada: hasta su firma no se escribe código |
| **Spec de la que cuelga** | Esta misma, `aprobada` el 2026-09-23 por @Nabeel |
| **Ubicación** | En el apartado final de la spec, como manda `AGENTS.md` §10.3, para que el qué y el cómo no puedan divergir en dos documentos |

El ciclo de cada paso es el TDD de `AGENTS.md` §10.4: el test se nombra aquí **antes** de
escribirlo, se ve fallar por el motivo correcto y solo entonces se implementa. Cada fase
cierra con `uv run pytest`, `uv run pytest -m invariants`, `ruff` y `mypy backend/` en verde.

### 10.1 Las fronteras que este plan no puede cruzar

`CLAUDE.md` §4 fija seis reglas de dependencia. Cuatro corren riesgo real en este plan, así
que cada una tiene su paso de puerta y no queda en buena voluntad:

| Regla | Riesgo concreto en este plan | Dónde se cobra |
| --- | --- | --- |
| `domain/` no importa de ningún otro paquete | `Destinatario` y `EventoDeCronologia` nacen junto a su persistencia y acaban importando el store | A-01, con la puerta de límites ampliada |
| Solo `store/` habla con SQLite | El guardarraíl lee sus listas de la base y el validador formal lee la cronología | B-02 y F-01 pasan por repositorio, nunca por `sqlite3` |
| `agents/` no importa de `agents/` | Entrevistador, planner y editor se llaman entre sí en lugar de coordinarse en `orchestrator/` | C-05 y C-06 |
| `api/` no invoca modelos | La petición de cambio del lector regenera capítulos desde la ruta HTTP | E-04 encola `Tarea`; la ruta devuelve `202` |

Regla nueva que este plan añade y que `test_import_boundaries` tendrá que hacer cumplir:
**nadie importa `observability/` desde `domain/`, `quality/` ni `agents/`**. La
instrumentación vive en `orchestrator/`, `worker/` y `api/`. Un juez que sabe que está
siendo observado es un juez distinto.

### 10.2 Fase A · Esquema y ontología

Al cerrar, existe dónde guardar todo lo que las demás fases escriben. Va primero porque una
migración tardía obliga a rehacer lo construido encima.

| # | Paso | Módulos | Test que lo demuestra | Requisitos |
| --- | --- | --- | --- | --- |
| A-01 | `Destinatario` y `ElementoPersonalizado` en `domain/spec/`, con su `RegistroDeDecision` y su entrada en `definitions.md` | `domain/spec/`, `docs/` | `test_destinatario_exige_nombre_y_al_menos_un_elemento_obligatorio` | RF-CFG-07 |
| A-02 | `EventoDeCronologia` y fecha de nacimiento de `Personaje` en el dominio | `domain/diegetic/` | `test_un_evento_de_cronologia_sin_momento_no_existe` | RF-BIB-02 |
| A-03 | Migración `0002`: `hecho_capitulo`, `evento_cronologia`, `resumen_capitulo`, `checkpoint_capitulo`, `lista_prohibida`, `audit_log` y `version_novela` | `migrations/` | `test_migracion_0002_crea_las_siete_tablas_y_es_reversible` | RF-BIB-01 a RF-BIB-04, RF-GRD-01, RF-GRD-06, RF-LEC-07 |
| A-04 | Repositorios de la story bible en `store/` | `store/` | `test_la_story_bible_se_consulta_por_personaje_lugar_hecho_y_cronologia` | RF-BIB-05 |
| A-05 | Registro de uso: al canonizar, cada `Hecho` anota los capítulos que lo usan | `store/`, `orchestrator/` | `test_un_hecho_usado_en_dos_capitulos_los_lista_ambos` | RF-BIB-01 |
| A-06 | Resumen por capítulo, y su entrada en el paquete de contexto | `context/`, `store/` | `test_el_contexto_del_capitulo_n_trae_resumenes_y_no_prosa_literal` | RF-BIB-03 |
| A-07 | Checkpoint por capítulo y reanudación | `orchestrator/`, `store/` | `test_reanudar_desde_checkpoint_no_duplica_ni_pierde_capitulos` | RF-BIB-04 |
| A-08 | Ampliar `test_import_boundaries` con los módulos nuevos | tubería | `test_import_boundaries` ampliado | §10.1 |

**Marcha atrás.** Si `0002` resulta más grande de lo que cabe en una revisión, se parte por
tabla, nunca por mitad de tabla: media migración aplicada es peor que ninguna.

### 10.3 Fase B · Guardarraíles y validadores programáticos

Al cerrar, el sistema puede rechazar un capítulo por sí solo. Van antes que los roles porque
son deterministas, baratos y son los que pueden parar la línea desde el primer capítulo.

| # | Paso | Módulos | Test que lo demuestra | Requisitos |
| --- | --- | --- | --- | --- |
| B-01 | Normalizador: minúsculas, acentos, plural en -s/-es y separadores, con la lista de transformaciones cerrada | `quality/` | `test_normaliza_mayusculas_acentos_plurales_y_separadores` | RF-GRD-02 |
| B-02 | Guardarraíl de tres niveles leyendo sus listas por repositorio | `quality/`, `store/` | `test_el_guardarrail_detecta_un_caso_de_cada_nivel`, `test_detecta_la_variante_con_acento_y_la_plural` | RF-GRD-01, RF-GRD-03 |
| B-03 | Devolución al writer con límite de intentos, y parada informada al agotarlo | `orchestrator/` | `test_agotado_el_limite_la_generacion_se_detiene_e_informa` | RF-GRD-04, RF-HAR-06 |
| B-04 | Audit log de las decisiones del policy engine | `store/`, `orchestrator/` | `test_cada_coincidencia_deja_fila_en_el_audit_log` | RF-GRD-05, RF-GRD-06 |
| B-05 | Validador de nombres exactos contra la story bible | `quality/` | `test_un_nombre_que_no_coincide_con_la_story_bible_es_defecto` | RF-VAL-02 |
| B-06 | Validador de longitud de capítulo | `quality/` | `test_un_capitulo_fuera_de_rango_es_defecto` | RF-VAL-03 |
| B-07 | Validador de elementos personalizados obligatorios contra la tabla de hechos | `quality/`, `store/` | `test_un_elemento_obligatorio_ausente_de_todos_los_capitulos_es_defecto` | RF-VAL-04, RF-CFG-07 |
| B-08 | Registro de validadores: cada uno con nombre y punto de ejecución declarado | `quality/` | `test_cada_validador_declara_nombre_y_punto_de_ejecucion` | RF-VAL-09 |

**Marcha atrás.** Si la normalización produce falsos positivos sobre el corpus congelado, se
estrecha la lista de transformaciones y se declara qué queda fuera. No se relaja el límite de
intentos para que «pase igual»: eso convierte el guardarraíl en decorativo.

### 10.4 Fase C · Los tres roles y los dos hooks

| # | Paso | Módulos | Test que lo demuestra | Requisitos |
| --- | --- | --- | --- | --- |
| C-01 | Rol **Entrevistador** con su contrato común y su prompt versionado | `agents/entrevistador/` | `test_la_entrevista_recoge_los_siete_campos_del_destinatario` | RF-CFG-01, RF-CFG-02 |
| C-02 | Detección de datos que faltan | `agents/entrevistador/` | `test_un_brief_incompleto_devuelve_los_huecos_y_no_los_inventa` | RF-CFG-03 |
| C-03 | Detección de contradicción edad ↔ tono | `agents/entrevistador/`, `quality/` | `test_edad_y_tono_incompatibles_se_devuelven_nombrando_el_par` | RF-CFG-04 |
| C-04 | Texto libre como contenido no confiable, con extracción de hechos | `agents/entrevistador/` | `test_una_instruccion_en_el_texto_libre_no_altera_el_comportamiento` | RF-CFG-05 |
| C-05 | Brief validado contra schema antes de entrar al plan | `api/`, `orchestrator/` | `test_un_brief_que_no_valida_no_entra_al_plan` | RF-CFG-06, RF-VAL-01 |
| C-06 | Rol **Planner** | `agents/planner/`, `orchestrator/` | `test_el_plan_cubre_todos_los_capitulos_declarados_en_el_brief` | RF-HAR-01 |
| C-07 | Rol **Editor/critic** | `agents/editor/` | `test_el_editor_devuelve_defectos_con_evidencia_citable` | RF-HAR-01 |
| C-08 | Hook de validación de capítulo | `orchestrator/` | `test_el_hook_de_capitulo_corre_antes_de_aceptarlo` | RF-HAR-04 |
| C-09 | Hook de policy | `orchestrator/` | `test_el_hook_de_policy_devuelve_el_capitulo_con_palabra_prohibida` | RF-HAR-04, RF-GRD-03 |
| C-10 | Tools con schema validado y reintentos con límite | `worker/`, `agents/` | `test_una_llamada_a_tool_que_no_valida_es_fallo_de_contrato` | RF-HAR-05, RF-HAR-06 |
| C-11 | Skill reutilizable commiteada, y `CLAUDE.md` al día | `.claude/skills/`, `CLAUDE.md` | Inspección en revisión | RF-HAR-02, RF-HAR-03 |

**Marcha atrás.** Si el entrevistador necesita más de una contradicción para ser útil, se
añade **una** más y se anota; el alcance pide «al menos un tipo», y perseguir un catálogo
completo de contradicciones es alcance que nadie aprobó.

### 10.5 Fase D · Observabilidad

Va antes que la evaluación a propósito: medir sin trazas obliga a repetirlo todo después.

| # | Paso | Módulos | Test que lo demuestra | Requisitos |
| --- | --- | --- | --- | --- |
| D-01 | Cliente de Langfuse detrás de un protocolo, con doble sin red | `observability/` | `test_con_langfuse_apagado_la_suite_pasa_entera` | S-02 |
| D-02 | Una traza por generación, agrupada por sesión de novela | `orchestrator/` | `test_una_generacion_produce_una_traza_con_su_sesion` | RF-OBS-01 |
| D-03 | Span por rol y por llamada a tool, con nombre identificable | `worker/`, `orchestrator/` | `test_cada_rol_y_cada_tool_aparece_como_span_nombrado` | RF-OBS-02 |
| D-04 | Tokens, coste y latencia por llamada, capítulo y novela | `observability/` | `test_el_coste_por_novela_es_la_suma_de_sus_llamadas` | RF-OBS-03 |
| D-05 | Scores de todos los validadores asociados a su traza | `quality/` → `orchestrator/` | `test_cada_validador_envia_su_score_a_su_traza` | RF-OBS-04, RF-VAL-09 |
| D-06 | Prompts versionados, con la versión registrada en la traza | `agents/`, `observability/` | `test_la_traza_registra_la_version_de_prompt_usada` | RF-OBS-05 |

**Marcha atrás.** Si Langfuse no está disponible en una ejecución, la generación **sigue** y
la traza se pierde con aviso. Lo contrario —que una novela no se escriba porque el
observador está caído— convierte la observabilidad en punto único de fallo.

### 10.6 Fase E · Lectura, versiones y PDF

| # | Paso | Módulos | Test que lo demuestra | Requisitos |
| --- | --- | --- | --- | --- |
| E-01 | Rutas de lectura en el contrato OpenAPI: novela, capítulo, ficha, versiones | `api/` | `test_el_contrato_publica_las_rutas_de_lectura_con_operation_id` | RF-LEC-01 a RF-LEC-03 |
| E-02 | Índice de capítulos navegable | `frontend/` | `test_el_indice_lista_los_capitulos_y_navega` | RF-LEC-01 |
| E-03 | Ficha de personajes y lugares desde la story bible, con enlace al capítulo | `frontend/` | `test_la_ficha_enlaza_cada_personaje_con_su_capitulo` | RF-LEC-02 |
| E-04 | Portada con dedicatoria personalizada | `frontend/` | `test_la_portada_muestra_la_dedicatoria_del_brief` | RF-LEC-03 |
| E-05 | Petición de cambio desde la página, seleccionando fragmento o hecho | `frontend/`, `api/` | `test_seleccionar_un_hecho_abre_la_peticion_de_cambio` | RF-LEC-04 |
| E-06 | Regeneración selectiva: solo los capítulos que usan el hecho | `orchestrator/` | `test_cambiar_un_hecho_regenera_solo_los_capitulos_que_lo_usan` | RF-LEC-05 |
| E-07 | Versión nueva, versión anterior conservada y capítulos cambiados marcados | `store/`, `frontend/` | `test_la_version_anterior_sigue_legible_tras_regenerar` | RF-LEC-06, RF-LEC-07 |
| E-08 | Exportación a PDF con índice, ficha, portada y página de novedades | `backend/`, tubería | `test_el_pdf_trae_indice_ficha_portada_y_novedades_con_enlaces` | RF-LEC-08 |
| E-09 | Validación visual por browser MCP sobre la lectura publicada | tubería, `.claude/mcp.json` | `test_browser_mcp_verifica_indice_ficha_y_portada` | RF-VAL-06 |

**Marcha atrás.** Si la regeneración selectiva rompe la continuidad entre capítulos vecinos,
no se ensancha el conjunto «por si acaso»: se corrige el registro de uso de A-05, que es
quien sabe qué capítulos tocan ese hecho, y Lean vuelve a verificar antes de publicar.

### 10.7 Fase F · Verificación formal

El harness tiene que existir antes de especificarlo, y la cronología antes de verificarla.

| # | Paso | Módulos | Test que lo demuestra | Requisitos |
| --- | --- | --- | --- | --- |
| F-01 | Generador del fichero Lean desde la story bible en SQLite | `formal/`, `store/` | `test_el_fichero_lean_refleja_la_cronologia_de_sqlite` | RF-LEAN-01 |
| F-02 | Dos invariantes en Lean: orden temporal y edad coherente con la fecha de nacimiento | `lean/` | `lake build` sobre una cronología sana y sobre una sembrada | RF-LEAN-02, RF-LEAN-03 |
| F-03 | Lean como puerta previa a publicar, con el fallo devuelto al editor | `orchestrator/` | `test_una_cronologia_incoherente_impide_publicar_y_vuelve_al_editor` | RF-LEAN-04 |
| F-04 | Especificación TLA+ del flujo: configuración → planificación → escritura → validación → publicación, con reintentos, checkpoint y regeneración | `tla/` | — (se verifica en F-05) | RF-TLA-01 |
| F-05 | Tres invariantes de seguridad y una propiedad de *liveness*, verificados con TLC sobre 5 capítulos y 2 reintentos | `tla/` | Ejecución de TLC con su `.cfg` commiteado | RF-TLA-02 a RF-TLA-04 |
| F-06 | Mapa acción ↔ estado del código en el `README`, y contraejemplos documentados | `README.md`, `docs/` | Inspección en revisión | RF-TLA-05, RF-TLA-06 |

**Marcha atrás.** Si TLC encuentra un contraejemplo, **manda el contraejemplo**: se corrige el
código y se documenta el cambio. Ajustar la especificación para que el modelo pase es
convertir la verificación formal en decoración, que es justo lo que RF-TLA-05 persigue.

### 10.8 Fase G · Evaluación y entregables

| # | Paso | Módulos | Test que lo demuestra | Requisitos |
| --- | --- | --- | --- | --- |
| G-01 | Cinco briefs de prueba, uno con *injection* y uno con incoherencia temporal sembrada | `tests/`, `docs/` | `test_los_cinco_briefs_corren_de_extremo_a_extremo` | RF-EVA-01 |
| G-02 | Tabla por brief y validador, con lo que pasó y lo que falló | `docs/` | Inspección; la tabla se genera de la ejecución, no a mano | RF-EVA-02 |
| G-03 | Una iteración de tuning con antes y después, y la versión de prompt de cada resultado | `docs/`, Langfuse | Inspección contra las trazas | RF-EVA-03 |
| G-04 | Novela de ejemplo de 10 capítulos en `/ejemplos/novela-ejemplo.pdf` | `/ejemplos/` | Existe y abre; 10 capítulos | RF-EVA-04 |
| G-05 | Los seis documentos de proceso en `docs/` | `docs/` | Inspección | RF-EVA-05 |
| G-06 | `.claude/` commiteada con memoria, comandos y `mcp.json` de navegador; `.env.example`; cero API keys | `.claude/`, raíz | `test_no_hay_secretos_en_el_arbol` y análisis del historial | RF-EVA-06, RF-EVA-07 |
| G-07 | Actualizar esta spec con lo construido y cada desviación con su motivo | `specs/` | La puerta *Spec y docs al día* de `AGENTS.md` §10.5 | `AGENTS.md` §10.4 |

### 10.9 Migraciones

**Una: `0002`, en A-03.** Añade siete tablas sobre el esquema de `0001` y no reescribe
ninguna existente. Si en cualquier fase posterior apareciera la necesidad de una columna
nueva, no se resuelve en el plan: vuelve a la spec, porque sería alcance que nadie aprobó.

A diferencia de SPEC-001, aquí **no se amplía la migración inicial**: ya hay canon almacenado
posible y una base creada, así que `0002` se encadena en lugar de reabrir `0001`.

### 10.10 Riesgos del plan y marcha atrás

| Paso | Si no sale | Marcha atrás |
| --- | --- | --- |
| A-03 | La migración toca más de lo previsto | Se parte por tabla y cada parte entra con su test. Media tabla aplicada es peor que ninguna |
| A-05 | El registro de uso por capítulo resulta ambiguo cuando un hecho se usa implícitamente | Se registra solo el uso explícito y se declara el hueco: un registro incompleto es honesto, uno inventado no |
| B-02 | Los tres niveles se solapan y una palabra global bloquea una novela legítima | La lista por novela puede **añadir** pero no levantar la global; si eso estorba, vuelve a la spec |
| C-04 | La extracción de hechos del texto libre trae hechos falsos | El texto libre es no confiable por diseño: lo extraído entra como propuesta y pasa por el mismo camino de canonización, nunca directo al canon |
| D-01 | Langfuse se cae o no hay red | La generación sigue con aviso; la observabilidad no es punto único de fallo |
| E-06 | La regeneración toca más capítulos de los debidos | Se corrige A-05, no se ensancha el conjunto |
| F-02 | Los dos invariantes de Lean resultan triviales sobre la cronología real | Se siembra una incoherencia en uno de los cinco briefs de G-01, que es lo que RF-LEAN-05 pide demostrar |
| F-05 | TLC no termina sobre el modelo pequeño | Se reduce el modelo antes que la propiedad: 3 capítulos y 1 reintento siguen siendo verificación; quitar un invariante no |
| G-04 | La novela de ejemplo sale corta o incoherente | Es la evidencia de que el sistema funciona: si no sale, el fallo está aguas arriba y se arregla ahí, no maquillando el PDF |

### 10.11 Lo que este plan no cubre

- Todo lo que el apartado 2.2 deja fuera sigue fuera, y en particular los siete opcionales.
- No fija estimaciones de tiempo. El orden es una dependencia, no un calendario.
- No decide la librería de PDF, la de schema ni la forma exacta de los prompts: se eligen en
  su paso y se registran si resultan no triviales.
- No salta la puerta siguiente. Aunque este plan se apruebe, cada paso empieza por su test en
  rojo visto fallar por el motivo correcto: un paso que se implementa primero y se cubre
  después documenta lo que hay, no comprueba lo que se pidió.
