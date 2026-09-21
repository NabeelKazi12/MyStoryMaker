# Verificación: qué método le toca a cada dimensión

2026-09-21

## Qué contiene este documento

El reparto concreto de la verificación. `definitions.md` enumera las dimensiones
de calidad y los invariantes, y `architecture.md` §5 describe en abstracto quién
tiene autoridad para bloquear; aquí se dice, para cada dimensión, **con qué
método se comprueba, quién la comprueba, qué recibe exactamente y con qué
severidad sale el `Defecto`**. La segunda mitad trata los otros dos niveles: cómo
se comprueba que el sistema que escribe la novela funciona, y cómo se comprueba
el código que lo sostiene.

Este documento no define dimensiones nuevas, ni roles nuevos, ni valores nuevos
de enumeración. Si una dimensión aparece aquí y no en `definitions.md`, es un
error de este documento. Si un rol aparece aquí y no en `AGENTS.md` §2, también.

## 1. Los tres niveles

La verificación se parte en niveles, y confundirlos es la causa de que un sistema
generativo parezca validado sin estarlo.

| Nivel | Pregunta | Objeto | Dónde se trata |
| --- | --- | --- | --- |
| Obra | ¿Es correcto el texto producido? | Párrafos, escenas, capítulos, el volumen entero | §4, §5 y §6 |
| Sistema | ¿Se comporta de forma fiable el conjunto de agentes? | Agentes, `Tarea`, `Defecto`, `Procedencia` | §7 |
| Repositorio | ¿Es correcto el código que comprueba la obra? | `backend/`, `frontend/` | §8 |

El nivel de obra se apoya en los otros dos. Un verificador programático cuya
suite nadie ha sometido a mutación no verifica, pasa; y un agente cuya tasa de
acierto nadie ha medido no verifica, opina con formato de tabla.

La diferencia con un sistema puramente agéntico está en el nivel de repositorio:
aquí la mayor parte de lo que bloquea es código determinista en `backend/quality/`,
no un agente leyendo. Eso es lo que permite la tercera decisión transversal de
`architecture.md` §1 — solo lo determinista bloquea — y también lo que obliga a
verificar ese código con el mismo rigor que la prosa.

## 2. Vocabulario controlado: `modo_de_verificación`

Tres valores cerrados, los de `definitions.md`. Toda `DimensiónDeCalidad` lleva
exactamente uno, y de ese valor se deriva la autoridad: no se decide dos veces.

| Valor | Qué significa | Fiabilidad | Puede bloquear |
| --- | --- | --- | --- |
| `programa` | Un verificador de `backend/quality/` evalúa un predicado sobre el canon y el borrador, sin leer prosa como lector | Alta y determinista: misma entrada, mismo resultado | Sí |
| `juez_llm` | El Juez puntúa contra una `Rubrica` con ejemplos ancla y devuelve `puntuacion` y `confianza` | Media, y variable entre llamadas sobre el mismo texto | No: penaliza y alimenta `UmbralDeAceptacion` |
| `humano` | Una persona lee y decide, por muestreo o en una puerta de cierre | Alta sobre lo que lee; no escala | Sí, con excepción autorizada |

El techo de este vocabulario es deliberado. Las cinco clases del marco T/A/I/D/U
—Test, Analysis, Inspection, Demonstration, Unverifiable— sirven para *describir*
cómo se comprueba algo, y se usan como columna auxiliar en §8; `modo_de_verificación`
sirve para *decidir quién bloquea*, y por eso tiene tres valores y no cinco.
Ampliarlo exige un `RegistroDeDecision`, igual que cualquier otra enumeración
cerrada.

**`humano` es una respuesta legítima y frecuente.** Declararla vale más que
fabricar un predicado falso, que es lo que convierte el bucle de revisión en un
generador de impresiones con número. Lo que no admite ningún predicado está
en §5.

## 3. El contrato de verificación

Toda dimensión que se entrega a un agente —es decir, todo lo que no es `programa`—
se entrega como un contrato de tres partes, y de ninguna otra forma.

- **Predicado.** Una frase que solo puede ser cierta o falsa, sobre entidades de
  la ontología. «El ritmo decae» no vale; «el `valor_de_entrada` declarado de la
  escena difiere de su `valor_de_salida`» sí.
- **Proyección mínima.** La lista cerrada de lo que el agente recibe, que es
  siempre un subconjunto de su `PaqueteDeContexto`. Lo que sobra en la proyección
  es lo que produce falsos positivos: un Guardián al que se le pasa el outline
  empieza a opinar sobre estructura.
- **Forma del `Defecto`.** Qué va en `tipo`, `span`, `regla_violada`, qué
  `severidad` por defecto y qué cuenta como `evidencia` citable. Un `Defecto` sin
  `evidencia` se descarta antes de llegar al Orquestador, así que el contrato debe
  decir qué evidencia acepta.

Una dimensión por tarea: al agente al que se le piden siete comprobaciones a la
vez solo le salen las dos primeras. El Guardián de Continuidad tiene un orden de
comprobación declarado en `AGENTS.md` §4.6 precisamente por esto.

## 4. Reparto de las dimensiones de la obra

La severidad de las tablas es la de partida, en los valores de `severidad` de
`definitions.md` — crítica · alta · media · baja · informativa. El enrutado
posterior (reescritura, replanificación, escalado) es el de `architecture.md` §5.4.

### Alcance local — frase y párrafo

La deriva de nombres se reparte entre dos comprobadores, y no por capricho: el
alias no declarado exige ver el canon, que el Editor de línea no recibe por
diseño. El alcance local describe dónde está el defecto, no quién lo encuentra.

| Dimensión | Modo | Quién comprueba | Proyección mínima | Severidad |
| --- | --- | --- | --- | --- |
| Deriva de nombres | `programa` | `backend/quality/` vía Guardián de Continuidad | Entidades del canon con sus alias declarados, texto del borrador | alta |
| Consistencia de tiempo y persona | `programa` | `backend/quality/` vía Guardián de Continuidad | Tiempo y persona del `ContratoDeEstilo`, texto del borrador | media |
| Repetición de n-gramas | `programa` | `backend/quality/` vía Editor de línea | Trigramas y tetragramas de los capítulos anteriores, texto nuevo | media |
| Diversidad léxica | `programa` | `backend/quality/` vía Editor de línea | Type-token ratio del capítulo y vocabulario delator del `ContratoDeEstilo` | baja |
| Variedad sintáctica percibida | `juez_llm` | Juez | Texto de la escena, rúbrica de estilo | baja, ruidosa |
| Especificidad sensorial | `juez_llm` | Juez | Texto de la escena, rúbrica de estilo | baja, ruidosa |
| Densidad de cliché | `juez_llm` | Juez | Texto de la escena, rúbrica de estilo | media, ruidosa |
| Naturalidad del diálogo | `juez_llm` | Juez | Réplicas de la escena, `PerfilDeEstilo` de los personajes presentes | media, ruidosa |

### Alcance de escena y capítulo

Aquí viven los ocho invariantes bloqueantes de `definitions.md`. Los seis
primeros son `programa` sin excepción: son la razón por la que la puerta *Escena
limpia* puede parar la línea.

| Dimensión | Modo | Quién comprueba | Proyección mínima | Severidad |
| --- | --- | --- | --- | --- |
| Contradicción de hechos | `programa` | `backend/quality/` vía Guardián de Continuidad | Hechos vigentes del sujeto con sus intervalos, `hechos_nuevos_detectados` del borrador | crítica |
| Fuga epistémica | `programa` | `backend/quality/` vía Guardián de Continuidad | `EstadoDeConocimiento` del elenco presente en ese punto, hechos que cada acción del texto usa | crítica |
| Violación de `ReglaDelMundo` | `programa` | `backend/quality/` vía Guardián de Continuidad | Reglas activas en el marco y sus excepciones declaradas, eventos narrados | crítica |
| Violación de línea temporal | `programa` | `backend/quality/` | Grafo causal de `EventoNarrativo` y `posicion_en_historia`, vía CTE recursiva | crítica |
| Disciplina de POV | `programa` | `backend/quality/` vía Guardián de Continuidad | `Narracion` declarada de la escena, conciencias a las que accede el texto | crítica |
| Escena con cambio de valor y con evento | `programa` | `backend/quality/` | `valor_de_entrada`, `valor_de_salida` y aristas `renderiza` de la escena | crítica |
| Un solo `Borrador` aceptado por escena | `programa` | `backend/quality/` | `estado_de_borrador` de todos los borradores de la escena | crítica |
| Conformidad estructural | `programa` | `backend/quality/` vía Editor de desarrollo | Beats de la `PlantillaEstructural` y beats realizados de la escena | media |
| Presupuesto de palabras | `programa` | `backend/quality/` | Presupuesto declarado del capítulo y recuento real | baja |
| Consistencia de motivación | `juez_llm` | Juez | Arco y `necesidad_interna` del POV, texto de la escena | media, ruidosa |
| Exposición forzada (*infodumping*) | `juez_llm` | Juez | Texto de la escena, rúbrica de exposición | media, ruidosa |
| Impacto emocional | `juez_llm` | Juez | Texto de la escena, `funcion_en_trama` declarada | baja, ruidosa |

### Alcance global — acto y volumen

| Dimensión | Modo | Quién comprueba | Proyección mínima | Severidad |
| --- | --- | --- | --- | --- |
| Siembras sin pagar | `programa` | `backend/quality/` vía Editor de desarrollo | Todos los `ParSiembraPago` con su `estado_de_siembra` y su límite | crítica al cierre del volumen |
| Hilos resueltos o abandonados | `programa` | `backend/quality/` vía Editor de desarrollo | Todos los `Hilo` con su resolución declarada | crítica al cierre del volumen |
| Hilo inactivo más de N escenas | `programa` | `backend/quality/` | Aristas `avanza` de todas las escenas en orden, N por `tipo_de_hilo` | media |
| Curva de tensión plana | `programa` | `backend/quality/` vía Editor de desarrollo | `funcion_en_trama` de todas las escenas del acto en orden | media |
| Frecuencia de motivos | `programa` | `backend/quality/` | Aristas `manifiesta` del volumen y frecuencia objetivo de cada `Motivo` | baja |
| Arcos con estado terminal | `programa` | `backend/quality/` vía Editor de desarrollo | Arco de cada protagónico con su estado declarado por capítulo | crítica al cierre del volumen |
| Coherencia temática | `juez_llm` | Juez | Resúmenes de todos los capítulos, `Tema` declarados | media, ruidosa |
| Tensión y curiosidad | `juez_llm` | Juez | Resúmenes de los capítulos del acto en orden | baja, ruidosa |
| Promesa al lector satisfecha | `humano` | Editor humano | Volumen cerrado y el `Brief` original | crítica, sin sustituto programático |

## 5. Lo que no admite predicado

Cuatro dimensiones salen `humano` del reparto, y son las de `definitions.md`
sección «Dimensiones humanas»: **valor literario, adecuación al mercado,
originalidad y satisfacción de la promesa al lector**. No se automatizan; se
muestrean.

La razón es la misma para las cuatro: no existe predicado sobre entidades de la
ontología cuya verdad implique la afirmación. Se puede comprobar que ninguna
siembra queda abierta; no se puede comprobar que el final se sienta ganado.

Tratamiento, por orden de preferencia:

1. **Partir el requisito.** «El volumen cumple la promesa al lector» se parte en
   siembras pagadas, hilos resueltos y preguntas dramáticas respondidas —todo
   `programa` y todo bloqueante— más un resto irreductible que va a la puerta
   *Volumen cerrado* como inspección humana.
2. **Reformular como umbral de rúbrica.** «La prosa debe sonar literaria» pasa a
   ser un conjunto de dimensiones `juez_llm` con umbrales que penalizan. Lo que
   queda fuera del umbral se acepta como riesgo, no se bloquea.
3. **Declararlo y muestrearlo.** Valor literario, adecuación al mercado y
   originalidad no se parten ni se reformulan: se muestrean. Declararlas aquí es
   lo que impide que alguien las dé por cubiertas.

Las dimensiones `juez_llm` de §4 no son inverificables, pero su salida se marca
aparte como ruidosa y **no dispara regeneración por sí sola**. Si una puntuación
baja reincide en el mismo personaje o en el mismo hilo a lo largo de varios
capítulos, eso sí es señal, y la señal es la reincidencia, no la puntuación de
una escena suelta.

## 6. Dónde se cobra cada dimensión: las puertas

Una dimensión sin puerta no bloquea nada, por determinista que sea su
verificador. `architecture.md` §5.2 fija cinco puertas y su política; esta tabla
dice qué dimensiones de §4 se cobran en cada una.

| Puerta | Cuándo | Qué se cobra | Política |
| --- | --- | --- | --- |
| Outline aprobado | Antes de redactar | Conformidad estructural, presupuesto de palabras, todo hilo con pregunta dramática declarada | Bloqueante |
| Escena limpia | Antes de aceptar un borrador | Los ocho invariantes bloqueantes de §4, alcance de escena | Bloqueante |
| Capítulo cerrado | Fin de capítulo | Continuidad acumulada, repetición de n-gramas contra capítulos anteriores, presupuesto | Bloqueante |
| Acto cerrado | Fin de acto | Curva de tensión, hilos inactivos, conformidad de beats, frecuencia de motivos | Advertencia |
| Volumen cerrado | Final | Siembras sin pagar, hilos resueltos, arcos con estado terminal, promesa al lector | Bloqueante |

*Acto cerrado* es la única puerta de advertencia, y lo es porque todo lo que
cobra es de grado: un acto con la curva algo plana sigue siendo un acto. Las
otras cuatro cobran predicados binarios.

## 7. Verificación del sistema que escribe

El nivel de obra mide la novela. Este mide el sistema, y es lo que permite
afirmar que el bucle converge en lugar de suponerlo.

| Qué se verifica | Clase | Cómo | Qué delata |
| --- | --- | --- | --- |
| Que los verificadores detectan | T | Casos sembrados: un borrador con un defecto conocido de una sola dimensión por caso | Tasa de detección por dimensión |
| Que no inventan defectos | T | Los mismos casos, con esa dimensión intacta | Falsos positivos por capítulo |
| Que el bucle converge | A | Recuento de intentos hasta `aceptado`, contra los cuatro de `architecture.md` §5.4 | Escenas que giran sin cerrar |
| Que no se repite el mismo fallo | A | Tipo de defecto en intentos consecutivos: dos iguales obligan a replanificar | Reescrituras que no arreglan nada |
| Que los defectos son utilizables | A | Proporción descartada por falta de `evidencia` | Agentes que opinan en vez de comprobar |
| Que los artefactos están bien formados | A | Recuento de rechazos por campo ausente, por rol | Un rol con demasiado alcance o con pocos ejemplos |
| Que una generación se puede reproducir | T | *Replay* desde una `Procedencia` archivada: misma revisión de canon, mismo hash de paquete | Prompts editados sin subir versión |
| Que el contexto no se degrada | D | Recuento por componente de `PaqueteDeContexto` a lo largo del libro | Deriva de compresión: el paquete de la escena 40 mayor que el de la 3 |
| Que el canon no acumula fantasmas | D | Auditoría de `deriva_de` en cada canonización | Hechos vigentes que ninguna escena narra |
| Que el sistema aguanta lo difícil | T | Briefs adversarios: personajes homónimos, narrador no fiable, saltos temporales largos, misterio con revelación tardía | Dimensiones que solo fallan bajo presión |
| Que cabe en el presupuesto | A | Tokens por ejecución frente al techo de 100.000 y al objetivo de 24.000 | Verificación que se come la generación |
| Que un prompt nuevo no empeora nada | D | Despliegue progresivo: un capítulo por versión de prompt antes de aplicarlo al volumen | Regresiones de estilo invisibles en una escena |

Tres señales de verificación mal diseñada, todas visibles en la `Procedencia`: el
agente que no encuentra nada nunca —casi siempre es una proyección incompleta, no
un texto impecable—, el que encuentra algo siempre —predicado vago, o proyección
con material de sobra que invita a opinar— y dos agentes que discrepan de forma
sistemática en la misma dimensión, lo que significa que ese predicado no era uno
solo.

Los guardarraíles del sistema no son un filtro añadido: son la matriz de permisos
de escritura de `AGENTS.md` §2, aplicada en el orquestador, y los vocabularios
controlados de `definitions.md`. Un atributo en texto libre es un atributo que
nadie puede verificar.

## 8. Verificación del repositorio

Lo que sostiene al nivel de obra. Aquí sí aplican las metodologías clásicas de
ingeniería de software, porque aquí sí hay especificación: los límites de módulos
de `architecture.md` §2 y los invariantes de `definitions.md`.

La columna *Clase* usa el marco T/A/I/D/U; la columna *Origen* cita el apartado
de `architecture.md` que impone el requisito, para que un cambio en un documento
se note en el otro.

### Límites de módulos

| Elemento | Metodología | Clase | Origen | Autoridad |
| --- | --- | --- | --- | --- |
| `domain/` no importa de ningún otro paquete (ni `store/`, ni `agents/`, ni FastAPI, ni Pydantic) | Análisis estático del grafo de importaciones | A | §2 | Bloqueante |
| `quality/` importa de `domain/` y nunca de `agents/` | Análisis estático del grafo de importaciones | A | §2 | Bloqueante |
| `agents/` no importa de `agents/`: la coordinación vive en `orchestrator/` | Análisis estático del grafo de importaciones | A | §2 | Bloqueante |
| Solo `store/` habla con SQLite y con el índice vectorial | Análisis estático: `sqlite3` y el cliente vectorial no se alcanzan desde ningún otro paquete | A | §2, §3.2 | Bloqueante |
| `api/` no invoca modelos: encola `Tarea` y lee estado | Análisis estático: el cliente de modelo no se alcanza desde `api/` | A | §2, §6 | Bloqueante |
| `frontend/` no contiene reglas de dominio ni invariantes duplicados | Inspección en revisión de código | I | §2, §6 | Bloqueante |
| Tipos de las clases de la ontología | Comprobación de tipos | A | §2 | Bloqueante |

### Almacenamiento

| Elemento | Metodología | Clase | Origen | Autoridad |
| --- | --- | --- | --- | --- |
| `journal_mode=WAL` y `foreign_keys=ON` en toda conexión abierta por `store/` | Pruebas unitarias sobre la factoría de conexiones | T | §3.1 | Bloqueante |
| Escritor único: ninguna escritura sobre el canon se emite fuera del orquestador | Análisis del grafo de llamadas + pruebas de integración con tareas concurrentes | A / T | §3.1, §9 | Bloqueante |
| Índices sobre `(sujeto_id, predicado)`, `posicion_en_historia` y `(conocedor_id, hecho_id)` | Pruebas de integración: plan de consulta de las validaciones más frecuentes | T | §3.1 | Advertencia |
| El canon versionado se reconstruye desde eventos de cambio, sin copia entera por revisión | Pruebas basadas en propiedades: reconstruir la revisión *N* y compararla con el estado en *N* | T | §3.1 | Bloqueante |
| Migraciones de SQLite hacia delante | Pruebas de integración contra un canon real | T | §2, §3.1 | Bloqueante |
| Ningún hecho se valida contra el índice vectorial | Análisis estático: `quality/` no alcanza el índice vectorial por ninguna ruta | A | §3.2 | Bloqueante |
| La canonización nunca sobrescribe canon: lo que lo contradice produce un `Defecto` | Pruebas basadas en propiedades sobre `hechos_nuevos_detectados` contradictorios | T | §3.3 | Bloqueante |

### Tubería de contexto

| Elemento | Metodología | Clase | Origen | Autoridad |
| --- | --- | --- | --- | --- |
| El `PaqueteDeContexto` cabe en 20.000–25.000 tokens, muy por debajo del techo de 100.000 | Pruebas basadas en propiedades sobre escenas generadas | T | §4.1 | Bloqueante |
| El ensamblador cuenta tokens antes de llamar y rechaza el paquete que excede; nunca trunca por la cola | Pruebas unitarias con paquetes por encima del presupuesto | T | §4.1 | Bloqueante |
| El paquete de la escena 3 y el de la escena 40 son equivalentes en tamaño | Pruebas basadas en propiedades sobre longitud de libro | T | §4.1 | Bloqueante |
| `PaqueteDeContexto` almacena el recuento real por componente | Pruebas unitarias sobre el ensamblado | T | §4.1 | Bloqueante |
| El filtro temporal actúa antes del epistémico | Prueba unitaria con un hecho vigente que el POV ignora: entra por el temporal, sale por el epistémico | T | §4.2 | Bloqueante |
| Cascada completa: resúmenes de la escena, de todo contenedor, hechos establecidos y paquetes que la citaban | Pruebas basadas en propiedades sobre cascadas de invalidación | T | §4.3 | Bloqueante |
| Cierre de `deriva_de`: ninguna `UnidadDeContexto` viva deriva de una fuente obsoleta | Pruebas basadas en propiedades sobre cascadas de invalidación | T | §4.3, §9 | Bloqueante |

### Proceso y fronteras

| Elemento | Metodología | Clase | Origen | Autoridad |
| --- | --- | --- | --- | --- |
| Separación de escritura por rol: el Canonizador es el único que escribe canon | Guardarraíles en `orchestrator/`, contrastados con la matriz de `AGENTS.md` §2 | A / T | §1, §2 | Bloqueante |
| Ciclo de vida de la escena: un solo `Borrador` aceptado, todo camino termina | Comprobación de modelos sobre la máquina de estados de §5.3 | A | §5.3 | Bloqueante |
| Escalado de reintentos: cuatro intentos, y salto a replanificación si dos consecutivos dan el mismo tipo de defecto | Pruebas unitarias sobre el contador del orquestador | T | §5.4, §9 | Bloqueante |
| Frontera API ↔ React (esquemas Pydantic, eventos SSE, `202 Accepted` con id de `Tarea`) | Pruebas de contrato | T | §6 | Bloqueante |
| Un prompt editado sin incrementar su versión semántica | Integración continua: el hash del prompt cambia y la versión no | A | §7 | Bloqueante |
| Cambio de stack o valor nuevo en una enumeración cerrada sin `RegistroDeDecision` | Integración continua: comprobación del registro en el propio cambio | A | §1, §9 | Bloqueante |
| Paso de las puertas en cada cambio del repositorio | Integración continua: la misma tubería que el código humano | T | §5.2 | Bloqueante |
| ¿La suite de invariantes detecta algo? | Pruebas de mutación periódicas sobre `backend/quality/` | T | §5.2 | Advertencia |

La última fila es la que sostiene a las demás. «Un invariante sin test no existe»
garantiza que el test está escrito, no que discrimine: sin mutación, una suite
que pasa siempre es indistinguible de una suite que comprueba de verdad.

## 9. Qué queda fuera, y por qué

**Sobre la obra.** Del catálogo de metodologías de la ingeniería de software,
tres no se aplican al texto: verificación formal, comprobación de modelos y
ejecución simbólica. La razón es la misma para las tres: **una novela no tiene
especificación formal contra la que probarse, y su espacio de estados no es
enumerable**. Sobre el canon sí se aplican, porque el canon no es prosa: es un
grafo con invariantes escritos, y ahí la comprobación de modelos de §8 tiene
sentido.

**Ejecución en sandbox.** No tiene aplicación aquí: ningún agente ejecuta código.
Su superficie de daño es la escritura en el canon, y eso lo acota el escritor
único del orquestador, no un aislamiento de proceso.

**Revisión humana.** A diferencia de un sistema sin puertas, aquí sí está dentro
del ciclo, pero acotada a dos puntos: el muestreo y los escalados del intento 4
(`architecture.md` §5.4), y la puerta *Volumen cerrado*. El editor no ejecuta
pasos intermedios.

## 10. Huecos declarados

Lo que este documento exige y hoy no tiene verificación real. Una tabla de
verificación sin huecos declarados suele significar que no se ha mirado.

- **No hay conjunto de escenas congelado para los evals de §7.** Sin él, las
  puntuaciones del Juez no son comparables entre versiones de prompt, y el
  despliegue progresivo es la única señal de que un prompt nuevo no ha empeorado
  nada.
- **Las pruebas de mutación de §8 no están en la tubería.** Mientras no lo estén,
  la cobertura de invariantes es una afirmación no verificada.
- **La comprobación de modelos del ciclo de vida** se apoya en que el diagrama de
  `architecture.md` §5.3 y el código del orquestador no diverjan. Nada lo
  comprueba hoy.
- **Las puertas *Outline aprobado* y *Acto cerrado*** de §6 no tienen invariantes
  enumerados en `definitions.md` al modo de las otras tres. Hasta que los tengan,
  su contenido es una intención, no una comprobación.
- **El *replay* de §7 supone** que el índice vectorial devuelve los mismos vecinos
  para la misma consulta tras una reindexación. No está comprobado; si no se
  cumple, el *replay* reproduce la llamada pero no el paquete.
- **Las tres decisiones transversales** de `architecture.md` §1 no viven en
  ninguna enumeración, así que la comprobación de `RegistroDeDecision` no detecta
  que cambien.
