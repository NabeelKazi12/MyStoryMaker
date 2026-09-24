# Trade-offs: las decisiones de diseño, con lo que se descartó

2026-09-23

## Qué contiene este documento

Cada decisión relevante como decisión: qué opciones había, con qué criterio se eligió y
qué se pierde con la elegida. No repite la arquitectura —eso es `architecture.md`— ni los
requisitos —eso son las specs—. Lo que aporta es el **porqué**, que es lo que se olvida
primero y lo que hace que seis meses después alguien deshaga una decisión sin saber que
lo era.

El formato es tabular a propósito: un bloque ADR por decisión hincha el documento hasta
que nadie lo lee.

---

## 1. Las decisiones que ordenan el sistema

| # | Decisión | Alternativas descartadas | Criterio | Qué se pierde |
| --- | --- | --- | --- | --- |
| T-01 | **Multi-agente con roles separados** (entrevistador, planner, writer, editor) | Un solo agente con un prompt largo | Quien genera no valida (`AGENTS.md` §1). Un agente que se juzga a sí mismo aprueba lo que escribe | Más invocaciones por capítulo y más latencia |
| T-02 | **Story bible en SQLite normalizada**, no prosa | Guardar el canon como resúmenes en texto | Sin hechos normalizados, «contradicción» no es un predicado ejecutable y ningún validador puede parar la línea | Anotar cuesta: `hechos_requeridos` es el cuello de botella declarado |
| T-03 | **Lectura web con PDF exportado** | PDF interactivo como formato principal | La web es lo que permite pedir un cambio seleccionando el fragmento, que es la pieza que más valor da al lector | El PDF no tiene vía de cambio propia: se pide desde la web |
| T-04 | **La cronología es una vista derivada**, no una tabla | Tabla `evento_cronologia` mantenida en paralelo | Una copia hay que sincronizarla; cuando se desincroniza, Lean verifica una historia que ya no es la que se lee | Cada consulta recalcula el `JOIN` |
| T-05 | **Lean verifica la cronología concreta**, no una demostración general | Teoremas sobre cualquier cronología | Una demostración general cuesta semanas y no detecta nada que la concreta no detecte en este proyecto | Cada novela se verifica por separado |
| T-06 | **TLA+ modela el harness, no la obra** | Modelar también la calidad del texto | El model checker razona sobre estados finitos; «la prosa es buena» no es un estado | El modelo no dice nada sobre la novela, solo sobre el proceso |
| T-07 | **Langfuse es la vista; SQLite es la fuente** | Langfuse como almacén de la ejecución | Si el observador fuera la fuente, reproducir una ejecución dependería de un servicio externo y de que no haya caducado la retención | Hay que escribir dos veces: en `Procedencia` y en la traza |
| T-08 | **El guardarraíl detecta y devuelve; no corrige** | Tachar o sustituir el término vetado | Corregir desde el guardarraíl produce prosa que nadie escribió y que no pasa por ningún validador | Cuesta una reescritura, y con ella una invocación |
| T-09 | **Normalización mínima** (minúsculas, acentos, separadores) | Añadir fonética, raíz o distancia de edición | Un falso positivo bloquea un capítulo correcto; el coste de un falso negativo es que el término aparezca escrito raro | «Rikardo» escapa al guardarraíl |
| T-10 | **La regeneración selectiva sale del registro de uso**, no de una heurística | Regenerar la novela entera; regenerar solo el capítulo donde se leyó | Regenerar de más paga invocaciones; de menos deja la novela contradiciéndose | Hay que anotar el uso al canonizar, y lo implícito se queda fuera |
| T-11 | **El juez con rúbrica penaliza, no bloquea** | Puerta bloqueante por puntuación de rúbrica | Un juez basado en modelo varía entre llamadas sobre el mismo texto: una puerta inestable produce bucles caros | Un capítulo mediocre puede publicarse si lo determinista pasa |
| T-12 | **Ningún opcional entra en la primera versión** | Servidor MCP y login desde el principio | Los dos condicionan el esquema; meterlos a medias cuesta una migración y no suma nota si lo obligatorio no está | Añadirlos después costará una migración de todas formas |

## 2. Las decisiones que se tomaron sobre la marcha

Estas no estaban en la spec: aparecieron al construir y se resolvieron con el criterio de
arriba. Cada una está anotada en su sitio; aquí quedan juntas para poder releerlas.

| # | Decisión | Dónde salió | Por qué |
| --- | --- | --- | --- |
| T-13 | `hecho_capitulo.hecho_id` **sin** clave foránea a `hecho` | Fase A, al ejecutar el test | Los hechos entran al canon como eventos de cambio en `canon_cambio`, no como filas de `hecho`: la clave foránea habría hecho fallar toda canonización |
| T-14 | El plural se genera sobre el **término vetado**, no recortando el texto | Fase B | Quitar la `s` final a cada palabra del capítulo convierte `mas` en `ma` y empieza a haber coincidencias que nadie escribió |
| T-15 | El validador de nombres **no** exige que el destinatario aparezca | Fase B | Que aparezca en algún capítulo lo cobra otro validador; exigirlo en dos sitios deja sin decidir cuál manda |
| T-16 | La edad negativa **no** se corrige en el dominio | Fase A | Es la incoherencia que el validador formal tiene que encontrar; taparla lo dejaría sin nada que detectar |
| T-17 | Un span de rol exige versión de prompt; uno de tool, no | Fase D | Un rol siempre corre con un prompt y sin su versión el resultado deja de ser atribuible; una tool no tiene prompt |
| T-18 | La página de novedades solo aparece desde la versión 2 | Fase E | «Novedades respecto a qué»: en la primera versión es ruido en la primera página del regalo |
