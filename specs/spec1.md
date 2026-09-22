# SPEC-001 · Primera versión del backend — Especificación de requisitos (SRS)

| | |
| --- | --- |
| **Identificador** | SPEC-001 |
| **Título** | Primera versión del backend: núcleo de dominio, canon verificable y bucle de una escena |
| **Estado** | `aprobada` el 2026-09-22 por @Nabeel. Apartado 12 vacío y los 102 requisitos con verificación asignada: la puerta *Spec aprobada* de `AGENTS.md` §10.5 queda superada |
| **Fecha** | 2026-09-22 |
| **Documentos de referencia** | `docs/definitions.md`, `docs/domain-knowledge.md`, `docs/architecture.md`, `docs/verification.md`, `AGENTS.md`, `CLAUDE.md`, en su estado del 2026-09-22 |
| **Fase de adopción** | Fase 1 de `architecture.md` §13, más el DAG mínimo y el semáforo de crédito |

> Este documento es la spec única de `AGENTS.md` §10.2 redactada en forma de SRS: reúne
> en un solo texto el problema, el alcance, los requisitos numerados y comprobables por
> separado, el reparto de verificación, el impacto y los criterios de aceptación. El
> **plan de implementación no está aquí**: según `AGENTS.md` §10.3 se añade al final de
> este mismo documento *después* de que la spec pase a `aprobada`.

---

## 1. Problema

El repositorio contiene hoy cuatro documentos de diseño acordados y ningún código:
`backend/` y `frontend/` solo tienen un `.gitkeep`. Todo lo que `docs/` afirma sobre
coherencia verificable —hechos con vigencia, contradicciones detectables, siembras que no
se quedan abiertas, contexto de tamaño constante— es hoy una intención sin ejecución.

Las consecuencias concretas de esa ausencia:

1. **Ningún invariante existe.** `CLAUDE.md` §7.1 y `AGENTS.md` §10.4 dicen que un invariante
   sin test no existe. No hay tests, luego no hay invariantes: los ocho bloqueantes de
   `definitions.md` son prosa.
2. **No hay dónde poner el canon.** Sin esquema de SQLite ni capa `store/`, no existe la
   fuente de verdad estructurada contra la que se valida nada, y cualquier prueba de
   concepto acabaría guardando canon como prosa —lo que `CLAUDE.md` §3.1 prohíbe.
3. **No hay máquina que ejecute el contrato de los agentes.** `AGENTS.md` §7 describe un
   ciclo de vida de `Tarea`, una escalera de reintentos y una matriz de permisos de
   escritura que hoy nadie aplica. Una matriz de permisos que no se aplica en el
   orquestador es una convención, y las convenciones no sobreviven al primer atajo.
4. **Las cifras de diseño no están medidas.** `architecture.md` §4.2 declara reservas de
   tokens y avisa de que ninguna está medida. Sin una tubería que registre `Procedencia`,
   no hay forma de convertirlas en datos.

Lo que falta no es «un backend»: es el subconjunto mínimo que hace que las comprobaciones
deterministas puedan parar la línea. Mientras no exista, el proyecto solo puede producir
texto plausible sin nada que lo contraste.

---

## 2. Propósito y alcance del documento

### 2.1 Propósito

Especificar, para su aprobación, **qué debe construirse en la primera versión del
backend** y **cómo se comprobará cada requisito**. No describe cómo implementarlo.

### 2.2 Alcance funcional — qué entra

El corte es la **Fase 1** de `architecture.md` §13 más lo que esa misma sección declara no
diferible: el DAG mínimo y el semáforo de crédito, aunque sea con concurrencia 1.

| # | Bloque | Contenido |
| --- | --- | --- |
| A1 | `backend/domain/` | Las 12 clases del núcleo mínimo de `architecture.md` §13 más `Volumen`, sin dependencias de infraestructura |
| A2 | `backend/store/` | SQLite con WAL, esquema inicial, índices obligatorios, repositorios y canon versionado por eventos de cambio |
| A3 | `backend/migrations/` | Migración inicial hacia delante |
| A4 | `backend/quality/` | Verificadores deterministas de la fase 1 y las puertas *Outline aprobado*, *Escena limpia*, *Capítulo cerrado* y *Volumen cerrado* |
| A5 | `backend/context/` | Ensamblado del `PaqueteDeContexto` con recuento de tokens por componente, el orden de componentes del contrato de rol, orden de recorte y `hash` |
| A6 | `backend/orchestrator/` | `Plan` como DAG persistido, bucle de reconciliación, máquina de estados de `Tarea`, escalera de reintentos, semáforo de crédito, matriz de permisos y canonización |
| A7 | `backend/worker/` | Consumidor de la cola con un único rol que invoca modelo: el **Redactor** |
| A8 | `backend/api/` | FastAPI: alta de canon y esqueletos de escena, encolado con `202 Accepted`, SSE de progreso y lectura de borradores, defectos y puertas |
| A9 | Corpus de casos sembrados | Un par de casos por verificador de 4.4: un borrador con el defecto conocido de esa sola dimensión y el mismo borrador con la dimensión intacta. Es el material sobre el que corre 8.4 |

### 2.3 Fuera de alcance — qué no entra

Cada exclusión lleva su motivo. Una exclusión sin motivo se convierte en un olvido.

| Excluido | Motivo |
| --- | --- |
| `EstadoDeConocimiento`, `Narracion` y por tanto **fuga epistémica**, **disciplina de POV** y **consistencia de tiempo y persona** | Fase 2 de `architecture.md` §13. Las dos primeras son invariantes bloqueantes y su ausencia se declara en 4.4, no se disimula. La tercera se cae con ellas: sin `Narracion` no hay persona ni tiempo declarados contra los que comparar |
| `ReglaDelMundo` y su invariante de violación | No está en el núcleo mínimo de 12 clases; entra con el Worldbuilder |
| Pirámide de `UnidadDeContexto` y resumen progresivo | Fase 3. En v1 el paquete se acota por filtro estructural, no por compresión |
| Índice vectorial (`sqlite-vec`), embeddings y recuperación por similitud | Bloqueado por la pregunta abierta 6 de `architecture.md` §12: el modelo de embeddings determina el DDL, y cambiarlo después es una reindexación completa. v1 se queda con la mitad relacional de D-10, que es la fuente de verdad; el supuesto S-6 sobre el volumen de vectores no le aplica todavía |
| `Rubrica`, `Juicio`, `UmbralDeAceptacion` y el rol **Juez** | Fase 4. Nada de lo que producen bloquea, así que su ausencia no debilita ninguna puerta |
| `Motivo`, `Tema`, `PlantillaEstructural` | Fase 5. Con ellas se caen dos verificadores de `architecture.md` §7.2: frecuencia de motivos y conformidad de beats |
| `Relación` y el verificador de valencia cambiada sin evento | No está en el núcleo mínimo de 12 clases. Sin ella, la advertencia 7 de `definitions.md` no tiene sobre qué correr |
| `Restriccion`, `PoliticaDeContenido` y el alcance de contrato de `verification.md` §4 | Ninguna de las dos está en el núcleo mínimo. Por eso RF-QUA-18 cobra solo tres de las comprobaciones de *Outline aprobado* y declara el resto como evidencia ausente |
| Roles **Arquitecto**, **Worldbuilder**, **Investigador**, **Entrenador de voz**, **Editor de línea**, **Editor de desarrollo** | v1 implementa un solo rol con invocación de modelo para acotar el trabajo de prompts. Los esqueletos de escena, entidades y perfiles de estilo entran por API con los mismos campos obligatorios que `AGENTS.md` §4.2 exige al Arquitecto |
| Puerta *Acto cerrado* | `verification.md` §10 declara que no tiene invariantes enumerados en `definitions.md`. Implementarla hoy sería codificar una intención. *Outline aprobado* sí entra: `verification.md` §4 le asigna dimensiones y v1 puede cobrar tres de ellas (RF-QUA-18) |
| `frontend/` | Esta spec es del backend. La frontera queda fijada en 7 para que el frontend pueda especificarse aparte |
| Política de retención y borrado | Pregunta abierta 7 de `architecture.md` §12. En v1 nada se borra, y eso queda como riesgo declarado en 11 |

### 2.4 Definiciones

Este documento no define clases, roles ni valores de enumeración nuevos, **con una
excepción declarada**: el catálogo de predicados de RF-STO-07, necesario para que
«contradicción de hechos» sea un predicado ejecutable. Su tratamiento está en 9.2.

Todo el vocabulario restante es el de `docs/definitions.md`. Los nombres de clase se
escriben en español y sin sinónimos, según `CLAUDE.md` §5.1.

---

## 3. Descripción general

### 3.1 Contexto del sistema

```mermaid
flowchart LR
    CLI[Cliente HTTP] -->|alta de canon y escenas| API[api · FastAPI]
    CLI -->|peticion de generacion| API
    API -->|encola Tarea| DB[(SQLite)]
    API -->|SSE de eventos| CLI
    ORC[orchestrator] -->|reconcilia| DB
    ORC -->|reserva credito| SEM[Semaforo 100.000]
    ORC --> CTX[context · ensamblado]
    CTX --> ST[store]
    ORC --> W[worker · Redactor]
    W -.->|invocacion| LLM[API del modelo]
    W -->|artefacto y Procedencia| ORC
    ORC --> QA[quality · verificadores]
    QA --> ST
    ST --> DB
    DOM[domain]
    ORC --> DOM
    QA --> DOM
    CTX --> DOM
    ST --> DOM
```

### 3.2 Bucle que debe quedar cerrado en v1

Es el criterio que ordena todo lo demás: v1 está terminado cuando este recorrido se
ejecuta entero y es reproducible.

```
alta de Brief, Volumen, Capítulo, Personajes, Lugares, Eventos e Hilos por API
  → alta del esqueleto de Escena con sus campos obligatorios
  → petición de generación: se crea un Plan con una Tarea de redacción
  → el orquestador reserva crédito; la capa de contexto ensambla el paquete y lo hashea
  → el worker invoca al Redactor y devuelve prosa + hechos_nuevos_detectados + Procedencia
  → los verificadores deterministas evalúan la puerta Escena limpia
      · limpia     → Borrador aceptado → canonización → revisión de canon + 1
      · defectuosa → escalera de reintentos de architecture.md §6.3 hasta escalado
  → todo el recorrido visible por SSE y reproducible desde la Procedencia archivada

Es el camino de `architecture.md` §6.1 recorrido con una sola clase de tarea.
```

### 3.3 Actores

| Actor | Qué hace en v1 |
| --- | --- |
| Persona autora | Da de alta canon y esqueletos de escena, lanza la generación, lee borradores y defectos, resuelve escalados |
| Orquestador | Única autoridad sobre la máquina de estados y sobre la escritura en el canon |
| Worker | Invoca al Redactor e informa del resultado. No decide nada |
| Verificadores de `quality/` | Código determinista. Lo único que puede bloquear una puerta |

### 3.4 Restricciones de diseño heredadas

No se renegocian en esta spec; se citan porque condicionan los requisitos.

- Stack fijado: FastAPI, SQLite, React, techo de 100.000 tokens (`architecture.md` §2.1).
- Las siete reglas no negociables de `CLAUDE.md` §3.
- Los límites de módulos y las seis reglas de dependencia de `architecture.md` §2.3.
- La matriz de permisos de escritura por rol de `AGENTS.md` §2.
- Idioma: clases, campos y enumeraciones en español; funciones y variables en inglés;
  comentarios, docstrings y mensajes de error en español (`CLAUDE.md` §5.3).

### 3.5 Supuestos

Se heredan S-1 a S-8 de `architecture.md` §11 sin cambios. Se nombran uno a uno porque
cada uno sostiene requisitos concretos de esta spec, y un supuesto heredado en bloque
es un supuesto que nadie vuelve a mirar:

| # | Qué asume | Qué sostiene en v1 |
| --- | --- | --- |
| S-1 | Una novela por proceso, una sola persona autora | El semáforo en memoria y la cola en SQLite: RF-ORQ-08 y RF-ORQ-11 |
| S-2 | Un proveedor, un modelo por rol, ventana de 100.000 | RF-ORQ-20 y la pregunta P-1: sin equivalencia entre modelos, «no degradar» es comprobable |
| S-3 | El límite que importa es de ocupación simultánea, no de tokens por minuto | Que RF-ORQ-08 baste sin un regulador de tasa al lado |
| S-4 | El proveedor ofrece caché de prefijo con vida suficiente entre intentos | Nada bloqueante: si cae, RF-CTX-01 sigue siendo correcto y deja de ahorrar |
| S-5 | Un solo proceso de backend, sin réplicas | Que un contador en memoria acote algo. Si cae, el semáforo tiene que ser distribuido |
| S-6 | El volumen de vectores se queda en decenas de miles | No aplica a v1: el índice vectorial está fuera de alcance |
| S-7 | Las cifras de `architecture.md` §4.2 son del orden correcto | RF-ORQ-09: la conciliación mide la desviación, pero parte de esas cifras |
| S-8 | Ejecución local, turno medido en minutos, sin latencia interactiva | RF-API-03 y RF-ORQ-11: encolar es respuesta aceptable a la saturación |

Supuestos propios de esta spec. El primero ya está recogido en `architecture.md`
§11; los dos siguientes los abre esta revisión y todavía no están en ningún
documento de `docs/`:

- **S-9.** Una `Escena` de v1 se puede redactar sin filtro epistémico porque su ausencia
  produce falsos negativos —defectos que no se detectan—, no falsos positivos. Si
  resultara falso, es decir, si redactar sin filtro epistémico produjera prosa
  sistemáticamente inservible, la fase 2 dejaría de ser diferible y esta spec habría
  cortado por donde no debía.
- **S-10.** La declaración que emite el Redactor —`hechos_nuevos_detectados`,
  `eventos_narrados`, `siembras_tocadas`— es lo bastante completa para que las
  dimensiones **(E)** de `verification.md` §2 signifiquen algo. Es el supuesto más
  cargado de esta spec: v1 tiene un solo rol con invocación de modelo, así que toda
  su capa bloqueante descansa sobre una declaración suya, y el conjunto congelado que
  permitiría medir su *recall* no existe (`verification.md` §10). Si es falso, la
  capa bloqueante de v1 pasa en verde sin haber evaluado nada. RF-QUA-19 y RF-QUA-20
  no lo desmienten: solo hacen visible el caso extremo.
- **S-11.** La obra de v1 tiene una sola línea temporal, sin `ramas[]`. RF-QUA-02 y
  RF-QUA-03 se implementan sin ese atributo, así que una rama temporal, una realidad
  alternativa o un viaje en el tiempo producirían un defecto crítico falso. Si es
  falso, hace falta el mecanismo de excepción declarada de `verification.md` §4, que
  esa misma sección declara no expresable en la fase 1.

---

## 4. Requisitos

Un requisito por fila, comprobable y fallable por separado. La columna *Origen* cita el
documento que lo impone, para que un cambio en `docs/` se note aquí.

### 4.1 Dominio — `backend/domain/`

| ID | Requisito | Origen |
| --- | --- | --- |
| RF-DOM-01 | Existen como tipos del dominio las 12 clases del núcleo mínimo —`Brief`, `Personaje`, `Lugar`, `EventoNarrativo`, `Hecho`, `Escena`, `Capitulo`, `Hilo`, `ParSiembraPago`, `PerfilDeEstilo`, `Borrador`, `Defecto`— más `Volumen` | `architecture.md` §13 |
| RF-DOM-02 | Existen como tipos del dominio las clases de producción que la ejecución necesita: `Tarea`, `Plan`, `Puerta`, `Procedencia`, `PaqueteDeContexto` y `RegistroDeDecision` | `definitions.md` §Producción; `architecture.md` §6.4 |
| RF-DOM-03 | Cada vocabulario controlado de `definitions.md` que v1 usa es una enumeración cerrada del dominio; un valor fuera de ella es un error de construcción, no una cadena aceptada | `definitions.md` §Vocabularios; `CLAUDE.md` §5.2 |
| RF-DOM-04 | Construir una `Escena` con `valor_de_entrada` igual a `valor_de_salida` falla en el dominio, antes de llegar a la base de datos | `definitions.md` §Escena |
| RF-DOM-05 | Construir una `Escena` sin al menos una arista `renderiza` hacia un `EventoNarrativo` falla | `definitions.md` §Escena |
| RF-DOM-06 | Un `Hecho` exige `valido_desde` apuntando a un `EventoNarrativo`; `valido_hasta` es opcional y nulo significa vigente. No admite fechas sueltas | `CLAUDE.md` §3.2 |
| RF-DOM-07 | Ninguna clase del dominio expone atributos estáticos para dimensiones variables (ubicación, lealtad, salud, posesión, estado emocional): esas son `Hecho` | `CLAUDE.md` §3.2 |
| RF-DOM-08 | Los mensajes de error del dominio están en español y nombran la clase y el invariante violado | `CLAUDE.md` §5.3 |

### 4.2 Almacenamiento — `backend/store/` y `backend/migrations/`

| ID | Requisito | Origen |
| --- | --- | --- |
| RF-STO-01 | Toda conexión abierta por `store/` tiene `journal_mode=WAL` y `foreign_keys=ON` | `architecture.md` §3.1 |
| RF-STO-02 | El esquema inicial se crea por migración versionada y hacia delante; no hay creación implícita de tablas al arrancar | `architecture.md` §2.3, §3.1 |
| RF-STO-03 | Existen los índices sobre `HECHO(sujeto_id, predicado)` y sobre `EVENTO(posicion_en_historia)`. El de `ESTADO_CONOCIMIENTO(conocedor_id, hecho_id)` queda para la fase 2, con su tabla | `architecture.md` §3.1 |
| RF-STO-04 | `store/` es el único paquete que abre una conexión a SQLite; el resto accede por repositorios tipados | `architecture.md` §2.3 |
| RF-STO-05 | El canon se versiona guardando eventos de cambio; la revisión *N* se reconstruye sin copiar el canon entero por revisión | `architecture.md` §3.1 |
| RF-STO-06 | La escritura de un artefacto y la transición de estado de su `Tarea` ocurren en la misma transacción | `architecture.md` §6.4 D-04; `AGENTS.md` §7.4 |
| RF-STO-07 | Existe un catálogo declarado de predicados de `Hecho` con su exclusividad —`funcional`, a lo sumo un valor vigente por sujeto, o `multivalor`—. Un predicado no catalogado se rechaza al canonizar | Esta spec, 9.2 |
| RF-STO-08 | Las consultas transitivas sobre el grafo causal de `EventoNarrativo` se resuelven con CTEs recursivas dentro de `store/`, no reconstruyendo el grafo en memoria | `architecture.md` §3.1 |
| RF-STO-09 | Ninguna tabla del canon admite prosa. El único texto largo del esquema es `BORRADOR.texto` | `CLAUDE.md` §3.1 |
| RF-STO-10 | La migración inicial siembra el catálogo `PREDICADO` con los nueve predicados de partida de R-7. El catálogo nunca queda vacío al arrancar: con él vacío, RF-STO-07 rechaza toda canonización y el bucle de 3.2 no puede cerrarse | Esta spec, 9.2 R-7 |

### 4.3 Contexto — `backend/context/`

| ID | Requisito | Origen |
| --- | --- | --- |
| RF-CTX-01 | El ensamblador construye el `PaqueteDeContexto` con los componentes en el orden del contrato de rol —estático, estado del mundo, continuidad, arco, voz, epistémico, promesas, instrucción, y los defectos abiertos al final—, y ese orden es parte del contrato | `AGENTS.md` §4.5; `architecture.md` §4.3 y §4.7 D-16 |
| RF-CTX-02 | El ensamblador cuenta los tokens **antes** de invocar y almacena el recuento real por componente en el `PaqueteDeContexto` | `architecture.md` §4.4 |
| RF-CTX-03 | Un paquete que excede su presupuesto no se trunca: la `Tarea` pasa a `bloqueada` con `falta`. En ningún caso se recorta por la cola | `architecture.md` §4.1, §4.5 D-12 |
| RF-CTX-04 | El recorte por componente sigue el orden fijo de `architecture.md` §4.5, y los componentes *estático*, *instrucción* y *epistémico* no se recortan nunca | `architecture.md` §4.5 D-12 |
| RF-CTX-05 | El filtro temporal —hechos vigentes en el `momento_en_historia` de la escena— se aplica antes que cualquier filtro posterior, y el punto de inserción del filtro epistémico queda explícito aunque en v1 no filtre nada | `architecture.md` §4.4 |
| RF-CTX-06 | El `PaqueteDeContexto` referencia la revisión de canon con la que se construyó y lleva un `hash` estable: mismo canon, misma escena y misma versión de prompt producen el mismo hash | `architecture.md` §9 |
| RF-CTX-07 | El paquete se reconstruye entero desde el store en cada invocación; no existe historial acumulativo entre intentos. El borrador rechazado no entra; los `Defecto` abiertos sí, literales y con evidencia | `architecture.md` §3.2 D-09; esta spec, 9.2 R-4 |
| RF-CTX-08 | El paquete de una tarea de redacción no supera 25.000 tokens de entrada, con el techo del sistema en 100.000 | `architecture.md` §4.1 |

### 4.4 Calidad — `backend/quality/`

Los verificadores de v1 y, explícitamente, los que no están. Cinco de los ocho invariantes
bloqueantes de `definitions.md` quedan cubiertos; los otros tres se declaran ausentes en
RF-QUA-14, para que nadie los dé por cubiertos.

La lista de partida es la de `architecture.md` §7.2, y el reparto de autoridad el de
`architecture.md` §7.1: en v1 solo bloquean los verificadores programáticos, porque
no hay ni juez ni muestreo humano dentro del bucle.

Tres de los que sí entran son dimensiones **(E)** de `verification.md` §2: su predicado es
determinista, pero su entrada la declara el Redactor leyendo su propia prosa. RF-QUA-01
depende de `hechos_nuevos_detectados`, RF-QUA-04 de los eventos renderizados y RF-QUA-08
del reconocimiento de nombres propios. RF-QUA-19 y RF-QUA-20 existen por eso, y el
supuesto que lo sostiene es S-10.

| ID | Requisito | Severidad | Origen |
| --- | --- | --- | --- |
| RF-QUA-01 | Detecta contradicción de hechos: dos hechos con el mismo sujeto y un predicado `funcional` con intervalos de vigencia solapados | crítica | `definitions.md` bloqueante 3 |
| RF-QUA-02 | Detecta ciclos en el grafo causal de `EventoNarrativo` | crítica | `definitions.md` bloqueante 1 |
| RF-QUA-03 | Detecta que A causa B sin que A preceda a B en `posicion_en_historia` | crítica | `definitions.md` bloqueante 2 |
| RF-QUA-04 | Detecta escena sin cambio de valor o sin evento renderizado, también sobre datos ya persistidos | crítica | `definitions.md` bloqueante 7 y §Escena |
| RF-QUA-05 | Detecta más de un `Borrador` en estado `aceptado` para la misma escena | crítica | `definitions.md` bloqueante 8 |
| RF-QUA-06 | Detecta `ParSiembraPago` en estado `abierto` pasada su `distancia_maxima_aceptable`, y cualquiera abierto al cierre del volumen | media, y crítica al cierre | `definitions.md` §ParSiembraPago; `verification.md` §4 |
| RF-QUA-07 | Detecta desvío del presupuesto de palabras del capítulo por encima de su margen | baja | `verification.md` §4 |
| RF-QUA-08 | Detecta deriva de nombres: un nombre propio del borrador que no corresponde a ninguna entidad del canon ni a un alias declarado | alta | `verification.md` §4 |
| RF-QUA-09 | Detecta repetición de n-gramas: tetragramas del borrador repetidos contra **todos** los capítulos anteriores del volumen, con umbral de 2 apariciones, excluyendo stopwords puras y diálogo atribuido | media | `definitions.md` §Dimensiones verificables; esta spec, 9.2 R-8 |
| RF-QUA-10 | Todo `Defecto` emitido lleva `tipo`, `span`, `regla_violada`, `severidad` y `evidencia` citable. Un defecto sin evidencia se descarta antes de llegar al Orquestador, y el descarte queda contado | — | `verification.md` §3 |
| RF-QUA-11 | La puerta *Escena limpia* es bloqueante y cobra RF-QUA-01 a RF-QUA-05 | — | `verification.md` §6; `architecture.md` §7.3 |
| RF-QUA-12 | La puerta *Capítulo cerrado* es bloqueante y cobra, sobre el capítulo ya cerrado, la reejecución de las dimensiones de escena de 4.4, más RF-QUA-09 y RF-QUA-07 | — | `verification.md` §6 |
| RF-QUA-13 | La puerta *Volumen cerrado* es bloqueante y cobra RF-QUA-06, todo hilo con resolución o abandono declarado y, para los de `tipo` principal, que su `pregunta_dramatica` tenga escena de resolución declarada y no abandono | — | `verification.md` §6; `definitions.md` cierre 2 y 3 |
| RF-QUA-14 | Las puertas declaran como **evidencia ausente**, nunca como aprobado, los invariantes bloqueantes que v1 no implementa: fuga epistémica, disciplina de POV y violación de `ReglaDelMundo`. La proporción de puertas cerradas con evidencia ausente queda contada y es consultable | — | `architecture.md` §6.5; `verification.md` §12 V-04 |
| RF-QUA-15 | Ningún verificador de `quality/` consulta el índice vectorial por ninguna ruta | — | `architecture.md` §3.1 |
| RF-QUA-16 | Detecta `Hilo` sin `pregunta_dramatica` declarada | crítica | `verification.md` §4 alcance de contrato |
| RF-QUA-17 | Detecta `Personaje` de `relevancia` protagónica sin `Hilo` asociado, o con `necesidad_interna` vacía | crítica | `definitions.md` §Personaje; `verification.md` §4 |
| RF-QUA-18 | La puerta *Outline aprobado* es bloqueante y cobra RF-QUA-07, RF-QUA-16 y RF-QUA-17. Declara evidencia ausente para conformidad estructural y para restricciones y políticas de contenido, que quedan fuera del alcance de v1 | — | `verification.md` §6 |
| RF-QUA-19 | El `Defecto` de una dimensión **(E)** cita en su `evidencia` el bloque declarado contra el que se evaluó, no solo el span del texto | alta | `verification.md` §2 y §11 F-01 |
| RF-QUA-20 | Un `Borrador` cuyo bloque `hechos_nuevos_detectados` llega vacío no supera *Escena limpia* en silencio: la puerta registra RF-QUA-01 como evidencia ausente en lugar de como superada | — | `verification.md` §11 F-01; `architecture.md` §1 principio 8 |
| RF-QUA-21 | Detecta diversidad léxica por debajo del umbral y uso de `vocabulario_prohibido` del `PerfilDeEstilo` aplicable | baja | `architecture.md` §7.2; `verification.md` §4 |
| RF-QUA-22 | Detecta `Hilo` inactivo más de N escenas consecutivas, con N por `tipo_de_hilo` | media | `architecture.md` §7.2; `verification.md` §4 |

### 4.5 Orquestación — `backend/orchestrator/`

| ID | Requisito | Origen |
| --- | --- | --- |
| RF-ORQ-01 | El `Plan` es un DAG de `Tarea`s persistido en SQLite antes de ejecutar nada. Si contiene un ciclo se rechaza el plan entero; no se rompe el ciclo por heurística | `architecture.md` §6.4 D-01; `AGENTS.md` §7.2 |
| RF-ORQ-02 | Una `Tarea` pasa a `lista` cuando, y solo cuando, todas sus `depende_de` están `aceptada` | `AGENTS.md` §7.1 |
| RF-ORQ-03 | Las transiciones de estado de `Tarea` las escribe únicamente el Orquestador. El worker informa del resultado y no decide estado | `architecture.md` §6.4 D-02 |
| RF-ORQ-04 | La máquina de estados de `Tarea` implementa exactamente el vocabulario cerrado de `AGENTS.md` §7.1, y ninguna transición fuera de él | `AGENTS.md` §7.1 |
| RF-ORQ-05 | La escalera de reintentos es la de `architecture.md` §6.3: reescritura, reescritura con contexto ampliado, replanificación y escalado a humano | `architecture.md` §6.3 |
| RF-ORQ-06 | Dos intentos consecutivos con el mismo tipo de `Defecto` saltan directamente a replanificación | `architecture.md` §6.3; `AGENTS.md` §4.1 |
| RF-ORQ-07 | Los fallos se clasifican en transporte, contrato, contenido y presupuesto antes de reaccionar; solo contrato y contenido suman intento narrativo | `architecture.md` §6.5 D-06 |
| RF-ORQ-23 | Los reintentos de transporte los hace el cliente del SDK con `max_retries = 3` y retroceso exponencial con *jitter*. `worker/` no añade una segunda capa de reintentos | Esta spec, 9.2 R-2 |
| RF-ORQ-24 | El recuento de intentos es un historial tipificado de `(intento, clase_de_fallo, tipo_de_defecto, timestamp)`, no dos contadores enteros. Los contadores por clase salen por agregación, igual que la condición de RF-ORQ-06 | Esta spec, 9.2 R-3 |
| RF-ORQ-08 | Un semáforo de crédito de 100.000 unidades concede reserva antes de invocar y la libera en **toda** ruta de salida: éxito, fallo, timeout y cancelación. Las 100.000 son tokens en vuelo simultáneos, no por petición | `architecture.md` §6.6 D-14; §4.1 D-13 |
| RF-ORQ-09 | La reserva concedida se concilia después contra el uso real registrado en `Procedencia`, y la desviación queda registrada por clase de tarea | `architecture.md` §6.6 |
| RF-ORQ-10 | Una reserva mayor que el crédito total se rechaza como error de planificación; no se encola | `architecture.md` §6.6 D-15 |
| RF-ORQ-11 | La cola ordena por las cuatro clases de prioridad P0–P3 con envejecimiento; una tarea que espera por encima del umbral configurado sube de clase | `architecture.md` §6.6 |
| RF-ORQ-12 | Hay tres timeouts configurables, con valores de partida de 10 minutos por invocación, 30 minutos por `Tarea` incluidos sus reintentos y 8 horas por `Plan`. Un vencimiento libera la reserva y se trata como fallo de contrato | `architecture.md` §6.5 D-07; esta spec, 9.2 R-5 |
| RF-ORQ-13 | Reejecutar con la clave `(plan, objetivo, revision_de_canon, hash_del_paquete, version_de_prompt, intento)` devuelve el artefacto ya producido sin volver a invocar el modelo | `AGENTS.md` §7.4 |
| RF-ORQ-14 | Al arrancar, toda `Tarea` que quedó `en_curso` sin `Procedencia` vuelve a `lista` y suma un intento; si la `Procedencia` está registrada y el artefacto no, queda anotada como pagada y perdida | `AGENTS.md` §7.4 |
| RF-ORQ-15 | La matriz de permisos de escritura de `AGENTS.md` §2 se aplica en el orquestador: un artefacto de una clase que el rol no puede escribir se rechaza | `CLAUDE.md` §3.4; `architecture.md` §5; `verification.md` §8 |
| RF-ORQ-16 | Cancelar una `Tarea` cancela su subárbol de dependientes y marca `obsoleto` lo ya producido. Nada se borra | `AGENTS.md` §7.5 |
| RF-ORQ-17 | Si la revisión del canon cambia mientras una `Tarea` está `en_curso`, su resultado se descarta al volver | `AGENTS.md` §7.5 |
| RF-ORQ-18 | Las canonizaciones se serializan: el Orquestador toma la revisión del canon como recurso exclusivo | `AGENTS.md` §7.2 |
| RF-ORQ-19 | Cada transición de estado emite un evento con marca de tiempo, disponible para su retransmisión por SSE | `architecture.md` §9 |
| RF-ORQ-20 | No hay degradación automática de modelo, de prompt ni de paquete. Bajo presión el sistema va más lento, nunca peor | `architecture.md` §6.5 D-08 |
| RF-ORQ-21 | Una `Tarea` recibe el identificador de su `PaqueteDeContexto`, nunca la salida literal de la tarea anterior. El estado se pasa por referencia al store | `architecture.md` §6.4 D-03 |
| RF-ORQ-22 | La cadena de una misma escena es secuencial en el DAG; el paralelismo solo existe entre escenas independientes. Con concurrencia 1 la regla sigue expresada en el `Plan`, no implícita en la configuración | `architecture.md` §2.2 D-05; `AGENTS.md` §7.2 |

### 4.6 Canonización

| ID | Requisito | Origen |
| --- | --- | --- |
| RF-CAN-01 | Solo promueve un `Borrador` que haya superado la puerta *Escena limpia*. Es el único punto de promoción a memoria larga | `architecture.md` §3.3 D-11 y §8 |
| RF-CAN-02 | Normaliza sujeto, predicado y objeto de cada `hechos_nuevos_detectados` contra las entidades existentes, por nombre canónico y alias declarados. Lo que no normaliza produce `Defecto`, no una entidad nueva | `AGENTS.md` §4.10 |
| RF-CAN-03 | Deduplica de forma exacta por clave natural —sujeto, predicado, objeto e intervalo—. Un duplicado exacto no se inserta | `architecture.md` §3.3 |
| RF-CAN-04 | Una sucesión legítima cierra el intervalo anterior con `valido_hasta` en el evento correspondiente. Una contradicción genera un `Defecto` y **nunca** sobrescribe canon | `architecture.md` §3.3; `AGENTS.md` §4.10 |
| RF-CAN-05 | Una canonización correcta incrementa la revisión del canon en uno | `AGENTS.md` §4.10 |
| RF-CAN-06 | La invalidación en cascada —hechos que la escena establecía y `PaqueteDeContexto` que la citaban— es parte del cierre de la canonización, en su misma transacción, no un trabajo posterior | `architecture.md` §4.6; `AGENTS.md` §7.5 |

### 4.7 Worker — `backend/worker/` y `backend/agents/`

| ID | Requisito | Origen |
| --- | --- | --- |
| RF-WRK-01 | El worker consume la cola, invoca al modelo y devuelve el resultado con su `Procedencia`. No escribe estado de `Tarea`, no elige la siguiente y no decide reintentar | `architecture.md` §6.4 D-02 |
| RF-WRK-02 | El worker describe su fallo con precisión suficiente para que el Orquestador lo clasifique en una de las cuatro clases de RF-ORQ-07 | `architecture.md` §6.5 |
| RF-WRK-03 | Cada invocación registra `Procedencia` con agente, modelo, versión de prompt, hash del paquete, parámetros de muestreo, coste, latencia y clase de fallo si lo hubo | `CLAUDE.md` §3.5; `architecture.md` §9 |
| RF-WRK-04 | La salida del rol se valida contra el esquema del contrato común de `AGENTS.md` §3. Una salida que no valida, o truncada al alcanzar el techo de tokens, es fallo de contrato | `AGENTS.md` §3; `architecture.md` §6.5 |
| RF-WRK-05 | `contexto_insuficiente: true` devuelve `resultado: null` con la lista `falta`, y el Orquestador reconstruye el paquete o replanifica. El agente no inventa | `AGENTS.md` §3 |
| RF-WRK-06 | El rol **Redactor** está implementado con su prompt versionado en `backend/agents/redactor/prompts/`, y emite prosa más `hechos_nuevos_detectados`, `eventos_narrados`, `siembras_tocadas` y `recuento_palabras` | `AGENTS.md` §4.5 |
| RF-WRK-09 | El Redactor invoca `claude-opus-5` con pensamiento adaptativo y `effort: high`. El límite duro de generación es el techo de salida de la `Tarea`: **4.000 tokens**, el de `architecture.md` §4.2. No se usa prefill, que ese modelo rechaza | Esta spec, 9.2 R-1 |
| RF-WRK-07 | Un prompt editado sin incrementar su versión semántica se detecta: el hash del fichero cambia y la versión no | `AGENTS.md` §8; `verification.md` §8 |
| RF-WRK-08 | Ningún registro de ejecución contiene prosa; los registros referencian el id del `Borrador` | `architecture.md` §9 |

### 4.8 API — `backend/api/`

| ID | Requisito | Origen |
| --- | --- | --- |
| RF-API-01 | Alta y lectura de `Brief`, `Volumen`, `Capitulo`, `Personaje`, `Lugar`, `EventoNarrativo`, `Hilo`, `ParSiembraPago` y `PerfilDeEstilo` | 3.2 |
| RF-API-02 | Alta de esqueleto de `Escena` exigiendo los campos obligatorios de `AGENTS.md` §4.2, incluido `hechos_requeridos`. Si falta cualquiera, se rechaza con `422` | `AGENTS.md` §4.2 |
| RF-API-03 | Los endpoints de generación crean una `Tarea` y devuelven `202 Accepted` con su id. Ninguno bloquea hasta terminar | `architecture.md` §2.2 |
| RF-API-04 | `GET /tareas/{id}/eventos` retransmite por SSE las transiciones de estado. El cliente no hace *polling* | `architecture.md` §9 |
| RF-API-05 | Lectura de borradores por escena con sus versiones, de defectos por borrador y del resultado de cada puerta | `CLAUDE.md` §2.3 |
| RF-API-06 | Los esquemas Pydantic son la frontera de serialización; las clases del dominio no se exponen ni se serializan directamente | `CLAUDE.md` §2.3 |
| RF-API-07 | `api/` no alcanza al cliente de modelo por ninguna ruta: encola `Tarea` y lee estado | `architecture.md` §2.3, §6 |

### 4.9 Requisitos no funcionales y estructurales

| ID | Requisito | Origen |
| --- | --- | --- |
| RNF-01 | `domain/` no importa de ningún otro paquete, ni de FastAPI ni de Pydantic | `architecture.md` §2.3 |
| RNF-02 | `quality/` importa de `domain/` y nunca de `agents/` | `architecture.md` §2.3 |
| RNF-03 | `agents/` no importa de `agents/` | `architecture.md` §2.3 |
| RNF-04 | El crédito total del semáforo es 100.000 y el grado de paralelismo por defecto es 1, configurable | `architecture.md` §4.1, §13 |
| RNF-05 | Se registran cuatro de las cinco señales de `architecture.md` §9: reintentos por tipo de `Defecto`, deriva entre reserva y uso real, tokens por componente, y tiempo en cola por prioridad | `architecture.md` §9 |
| RNF-06 | `uv run pytest`, `uv run pytest -m invariants`, `ruff check`, `ruff format --check` y `mypy backend/` pasan en verde | `CLAUDE.md` §6 |
| RNF-07 | Todo invariante de 4.4 tiene un test que se ha visto fallar por el motivo correcto antes de implementarlo | `AGENTS.md` §10.4 |
| RNF-08 | Los comandos de `CLAUDE.md` §6 funcionan tal como están escritos al cerrar el cambio | `CLAUDE.md` §6 |

---

## 5. Modelo de datos

Las tablas del esquema inicial. El DDL concreto —tipos, claves foráneas y restricciones
`CHECK` de las enumeraciones— se escribe en la migración durante la implementación; aquí
se fija qué existe y qué no.

### 5.1 Canon y estructura

| Tabla | Notas |
| --- | --- |
| `BRIEF` | `genero`, `premisa`, `promesa_al_lector`, `extension_objetivo` |
| `VOLUMEN` | `titulo`, `presupuesto_palabras`, `perfil_estilo_id` |
| `CAPITULO` | `volumen_id`, `orden`, `presupuesto_palabras` |
| `ESCENA` | `capitulo_id`, `orden`, `pov_id`, `lugar_id`, `momento_en_historia`, `objetivo`, `conflicto`, `resultado`, `valor_entrada`, `valor_salida`, `funcion_en_trama`, `tipo`, `presupuesto_palabras` |
| `PERSONAJE` | `nombre_canonico`, `alias`, `relevancia`, `deseo_externo`, `necesidad_interna`, `creencia_falsa`, `arco_tipo`, `perfil_estilo_id`. `relevancia` es el atributo de `Entidad` que RF-QUA-17 necesita |
| `LUGAR` | `nombre_canonico`, `alias`, `atmosfera_sensorial` |
| `EVENTO` | `descripcion`, `posicion_en_historia`, `tipo`, `visibilidad`, `lugar_id` |
| `HECHO` | `sujeto_id`, `predicado`, `objeto`, `valido_desde` → `EVENTO`, `valido_hasta` → `EVENTO` (nulo = vigente), `certeza`, `establecido_en` → `ESCENA` |
| `PREDICADO` | Catálogo de RF-STO-07: `nombre`, `exclusividad`, `descripcion` |
| `HILO` | `tipo`, `pregunta_dramatica`, `estado`, `resuelto_en` → `ESCENA` |
| `SIEMBRA_PAGO` | `tipo`, `escena_siembra`, `escena_pago`, `estado`, `distancia_maxima` |
| `PERFIL_ESTILO` | `longitud_media_frase`, `registro`, `vocabulario_prohibido` |
| `ESCENA_EVENTO` | Arista `renderiza`, con la cardinalidad `1..*` de RF-DOM-05 |
| `ESCENA_HILO` | Arista `avanza` |
| `EVENTO_PARTICIPANTE` | `evento_id`, `entidad_id`, `rol_en_evento` |
| `EVENTO_CAUSA` | Arista `causa`, sobre la que operan RF-QUA-02 y RF-QUA-03 |
| `CANON_REVISION` | Revisión actual y eventos de cambio de RF-STO-05 |

### 5.2 Producción y ejecución

| Tabla | Notas |
| --- | --- |
| `BORRADOR` | `escena_id`, `version`, `texto`, `estado`, `recuento_palabras`, `procedencia_id`. Única tabla con texto largo |
| `HECHO_DETECTADO` | Los `hechos_nuevos_detectados` declarados por el Redactor, pendientes de canonizar |
| `DEFECTO` | `tipo`, `severidad`, `span`, `evidencia`, `regla_violada`, `estado`, `detectado_por` |
| `PLAN` | Contenedor del DAG, con su techo de coste |
| `TAREA` | `plan_id`, `tipo`, `rol_asignado`, `estado`, `prioridad`, `presupuesto`, `reserva`, `paquete_id`, `falta`. El recuento de intentos vive en `TAREA_INTENTO` (R-3), no en dos columnas |
| `TAREA_DEPENDENCIA` | Aristas `depende_de` del DAG |
| `TAREA_INTENTO` | Historial tipificado de RF-ORQ-24: `tarea_id`, `intento`, `clase_de_fallo`, `tipo_de_defecto`, `timestamp` |
| `TAREA_EVENTO` | Transiciones con marca de tiempo; origen del SSE de RF-API-04 |
| `PUERTA` | `fase`, `politica`, `resultado`, `evidencia_ausente` (RF-QUA-14) |
| `PAQUETE_CONTEXTO` | `tarea_id`, `revision_canon`, `hash`, recuento de tokens por componente |
| `PROCEDENCIA` | `agente`, `modelo`, `version_de_prompt`, `paquete_id`, `parametros_muestreo`, `coste`, `latencia`, `timestamp` |
| `REGISTRO_DECISION` | Inmutable: `decision`, `alternativas`, `motivo`, `ambito`, `reversible`, `tomada_en` |

### 5.3 Índices obligatorios

`HECHO(sujeto_id, predicado)` y `EVENTO(posicion_en_historia)`, según RF-STO-03.

---

## 6. Interfaz de la API

Forma de los endpoints de v1. Los esquemas concretos se definen con Pydantic durante la
implementación.

| Método y ruta | Qué hace | Respuesta |
| --- | --- | --- |
| `POST /brief`, `/volumenes`, `/capitulos`, `/personajes`, `/lugares`, `/eventos`, `/hilos`, `/siembras`, `/perfiles-estilo` | Alta de canon y estructura | `201` |
| `POST /escenas` | Alta de esqueleto con los campos obligatorios de RF-API-02 | `201`, o `422` si falta alguno |
| `GET /escenas/{id}` | Escena con sus aristas y su estado | `200` |
| `POST /escenas/{id}/redactar` | Crea `Plan` y `Tarea` de redacción | `202` con `tarea_id` |
| `GET /tareas/{id}` | Estado, intentos, reserva y `falta` | `200` |
| `GET /tareas/{id}/eventos` | SSE de transiciones | `200`, `text/event-stream` |
| `POST /tareas/{id}/cancelar` | Cancela la tarea y su subárbol | `202` |
| `GET /escenas/{id}/borradores` | Versiones con su estado | `200` |
| `GET /borradores/{id}/defectos` | Defectos con su evidencia | `200` |
| `GET /puertas` | Resultado de puertas por ámbito, incluida la evidencia ausente | `200` |
| `POST /escalados/{tarea_id}/resolver` | Resolución humana del intento 4: aprueba o rechaza | `200` |

---

## 7. Frontera con el frontend

Queda fijada aquí aunque el frontend esté fuera de alcance, porque condiciona la API:

- Toda validación ocurre en el backend. El frontend que necesite decidir si algo es
  válido llama a la API (`CLAUDE.md` §2.3).
- El progreso llega por SSE. El frontend no hace *polling* ni infiere progreso.
- Ningún invariante se duplica en JavaScript.

---

## 8. Verificación

Por requisito: metodología concreta, clase del marco T/A/I/D/U, `modo_de_verificacion` de
`definitions.md` y autoridad. El reparto sigue `verification.md`: **solo lo determinista
bloquea**.

### 8.1 Dominio

| ID | Metodología | Clase | Modo | Autoridad |
| --- | --- | --- | --- | --- |
| RF-DOM-01, RF-DOM-02 | Comprobación de tipos (`mypy`) más un test de presencia por clase | A | `programa` | Bloqueante |
| RF-DOM-03 | Prueba unitaria por enumeración: un valor fuera del vocabulario falla | T | `programa` | Bloqueante |
| RF-DOM-04, RF-DOM-05 | Prueba unitaria en rojo primero: construcción inválida que debe fallar | T | `programa` | Bloqueante |
| RF-DOM-06, RF-DOM-07 | Análisis estático de los tipos del dominio: ningún campo de fecha suelta ni atributo estático de dimensión variable | A | `programa` | Bloqueante |
| RF-DOM-08 | Inspección en revisión de código sobre los mensajes de error | I | `humano` | Bloqueante |

### 8.2 Almacenamiento

| ID | Metodología | Clase | Modo | Autoridad |
| --- | --- | --- | --- | --- |
| RF-STO-01 | Prueba unitaria sobre la factoría de conexiones: `PRAGMA journal_mode` y `foreign_keys` | T | `programa` | Bloqueante |
| RF-STO-02 | Prueba de integración: base vacía → migración → esquema esperado | T | `programa` | Bloqueante |
| RF-STO-03 | Prueba de integración sobre el plan de consulta de las validaciones más frecuentes | T | `programa` | Advertencia |
| RF-STO-04 | Análisis estático del grafo de importaciones: `sqlite3` no se alcanza fuera de `store/` | A | `programa` | Bloqueante |
| RF-STO-05 | Pruebas basadas en propiedades: reconstruir la revisión *N* y compararla con el estado en *N* | T | `programa` | Bloqueante |
| RF-STO-06 | Prueba de integración con fallo inyectado entre artefacto y transición: no queda escrito ninguno de los dos | T | `programa` | Bloqueante |
| RF-STO-07 | Prueba unitaria: un predicado no catalogado se rechaza al canonizar | T | `programa` | Bloqueante |
| RF-STO-08 | Prueba de integración sobre un grafo causal profundo, comparada con el resultado esperado | T | `programa` | Bloqueante |
| RF-STO-09 | Inspección del esquema en revisión de código, más análisis estático de las columnas de texto | I / A | `humano` | Bloqueante |
| RF-STO-10 | Prueba de integración: base vacía → migración → el catálogo trae el conjunto de partida, y una canonización de prueba no se rechaza por predicado no catalogado | T | `programa` | Bloqueante |

### 8.3 Contexto

| ID | Metodología | Clase | Modo | Autoridad |
| --- | --- | --- | --- | --- |
| RF-CTX-01 | Prueba unitaria sobre el orden de componentes del paquete ensamblado | T | `programa` | Bloqueante |
| RF-CTX-02 | Prueba unitaria: el recuento almacenado coincide con el contado antes de invocar | T | `programa` | Bloqueante |
| RF-CTX-03 | Prueba unitaria con un paquete por encima del presupuesto: la tarea queda `bloqueada` con `falta` y no se invoca al modelo | T | `programa` | Bloqueante |
| RF-CTX-04 | Prueba unitaria por escalón del orden de recorte, más un caso que confirma que los tres intocables no se tocan | T | `programa` | Bloqueante |
| RF-CTX-05 | Prueba unitaria con un hecho invalidado antes del `momento_en_historia`: no entra en el paquete | T | `programa` | Bloqueante |
| RF-CTX-06 | *Replay* desde una `Procedencia` archivada: misma revisión, mismo hash | T | `programa` | Bloqueante |
| RF-CTX-07 | Prueba unitaria: el paquete del intento 2 no contiene el borrador rechazado del intento 1 | T | `programa` | Bloqueante |
| RF-CTX-08 | Pruebas basadas en propiedades sobre escenas con distinta cantidad de canon previo | T | `programa` | Bloqueante |

### 8.4 Calidad

| ID | Metodología | Clase | Modo | Autoridad |
| --- | --- | --- | --- | --- |
| RF-QUA-01 a RF-QUA-09 | Dos casos sembrados por verificador: uno con el defecto conocido de esa sola dimensión, que debe detectar, y el mismo caso con la dimensión intacta, donde no debe inventar nada | T | `programa` | Bloqueante |
| RF-QUA-10 | Prueba unitaria: defecto sin evidencia descartado y contado | T | `programa` | Bloqueante |
| RF-QUA-11 a RF-QUA-13 | Pruebas de integración por puerta: un artefacto que la pasa y uno que la falla por cada comprobación que cobra | T | `programa` | Bloqueante |
| RF-QUA-14 | Prueba de integración: el resultado de la puerta enumera los invariantes no implementados como evidencia ausente, y ninguno aparece como superado | T | `programa` | Bloqueante |
| RF-QUA-15 | Análisis estático: el índice vectorial no se alcanza desde `quality/` por ninguna ruta | A | `programa` | Bloqueante |
| RF-QUA-16, RF-QUA-17 | Dos casos sembrados por verificador sobre el corpus de A9, igual que RF-QUA-01 a RF-QUA-09 | T | `programa` | Bloqueante |
| RF-QUA-18 | Pruebas de integración sobre la puerta: un outline que la pasa y uno que la falla por cada comprobación que cobra, más la comprobación de que lo no implementado sale como evidencia ausente | T | `programa` | Bloqueante |
| RF-QUA-19 | Prueba unitaria: un defecto de RF-QUA-01 sin referencia al bloque declarado se descarta como defecto sin evidencia | T | `programa` | Bloqueante |
| RF-QUA-20 | Prueba de integración con un borrador de bloque vacío: la puerta no lo declara limpio y la escena no se canoniza | T | `programa` | Bloqueante |
| RF-QUA-21, RF-QUA-22 | Dos casos sembrados por verificador sobre el corpus de A9, igual que RF-QUA-01 a RF-QUA-09 | T | `programa` | Bloqueante |
| Discriminación de la suite | Pruebas de mutación sobre `backend/quality/`: una suite que pasa siempre es indistinguible de una que no comprueba nada | T | `programa` | Advertencia |

### 8.5 Orquestación y canonización

| ID | Metodología | Clase | Modo | Autoridad |
| --- | --- | --- | --- | --- |
| RF-ORQ-01 | Prueba unitaria con un plan cíclico: se rechaza entero | T | `programa` | Bloqueante |
| RF-ORQ-02, RF-ORQ-04 | Comprobación de modelos sobre la máquina de estados de `architecture.md` §6.2: todo camino termina y no hay transición fuera del vocabulario | A | `programa` | Bloqueante |
| RF-ORQ-03, RF-ORQ-15 | Análisis del grafo de llamadas: ninguna escritura de estado ni de canon se emite fuera del orquestador, contrastado con la matriz de `AGENTS.md` §2 | A | `programa` | Bloqueante |
| RF-ORQ-05, RF-ORQ-06 | Pruebas unitarias sobre el contador: cuatro intentos, y salto a replanificación con dos defectos consecutivos del mismo tipo | T | `programa` | Bloqueante |
| RF-ORQ-07 | Prueba unitaria por clase de fallo: solo contrato y contenido incrementan el contador narrativo | T | `programa` | Bloqueante |
| RF-ORQ-08 | Pruebas basadas en propiedades sobre secuencias de éxito, fallo, timeout y cancelación: el crédito vuelve siempre a su valor inicial. Es V-10 de `verification.md` §12 | T | `programa` | Bloqueante |
| RF-ORQ-09 | Prueba de integración: la desviación entre reserva y uso real queda registrada por clase de tarea, conciliada al terminar cada `Plan` (V-10) | T | `programa` | Bloqueante |
| RF-ORQ-10 | Prueba unitaria con una reserva mayor que el crédito total | T | `programa` | Bloqueante |
| RF-ORQ-11 | Prueba unitaria de la cola: P0 antes que P1, y una tarea envejecida sube de clase | T | `programa` | Bloqueante |
| RF-ORQ-12 | Prueba unitaria por nivel de timeout: se cancela, se libera la reserva y se clasifica como contrato | T | `programa` | Bloqueante |
| RF-ORQ-23 | Prueba unitaria con un transporte que falla: el número total de invocaciones facturadas es el del SDK, no su cuadrado | T | `programa` | Bloqueante |
| RF-ORQ-24 | Pruebas basadas en propiedades: los contadores por clase derivados del historial coinciden con la secuencia de fallos inyectada | T | `programa` | Bloqueante |
| RF-ORQ-13, RF-ORQ-14 | Prueba de integración de reanudación: caída simulada del proceso y reconstrucción de la cola desde la tabla | T | `programa` | Bloqueante |
| RF-ORQ-16, RF-ORQ-17 | Pruebas de integración: cancelación en cascada sin borrados, y descarte del resultado generado contra una revisión superada | T | `programa` | Bloqueante |
| RF-ORQ-18 | Prueba de integración con dos canonizaciones concurrentes: se serializan y no aparece `database is locked` | T | `programa` | Bloqueante |
| RF-ORQ-19 | Prueba de contrato sobre el flujo SSE | T | `programa` | Bloqueante |
| RF-ORQ-20 | Inspección en revisión de código: no existe ninguna ruta que cambie de modelo o recorte el paquete sin dejarlo en `Procedencia` | I | `humano` | Bloqueante |
| RF-ORQ-21 | Análisis estático de las entradas del despachador: ninguna firma acepta el artefacto de la tarea anterior | A | `programa` | Bloqueante |
| RF-ORQ-22 | Prueba unitaria sobre el `Plan` generado: las tareas de una misma escena quedan encadenadas por `depende_de` aunque la concurrencia sea 1 | T | `programa` | Bloqueante |
| RF-CAN-01 a RF-CAN-05 | Pruebas basadas en propiedades sobre `hechos_nuevos_detectados`: compatibles, duplicados exactos, sucesiones legítimas y contradictorios. Ningún caso sobrescribe canon | T | `programa` | Bloqueante |
| RF-CAN-06 | Pruebas basadas en propiedades sobre cascadas de invalidación, dentro de la transacción de cierre, más la auditoría de `deriva_de` que pide V-09 de `verification.md` §12 | T | `programa` | Bloqueante |

### 8.6 Worker y API

| ID | Metodología | Clase | Modo | Autoridad |
| --- | --- | --- | --- | --- |
| RF-WRK-01 | Análisis estático: `worker/` no escribe en la tabla de `Tarea` | A | `programa` | Bloqueante |
| RF-WRK-02, RF-WRK-04 | Pruebas unitarias con salidas mal formadas y truncadas: clase de fallo correcta en cada caso | T | `programa` | Bloqueante |
| RF-WRK-03 | Prueba de integración: no hay invocación sin `Procedencia` registrada | T | `programa` | Bloqueante |
| RF-WRK-05 | Prueba unitaria: `contexto_insuficiente` devuelve `null` y la lista `falta` llega al Orquestador | T | `programa` | Bloqueante |
| RF-WRK-06 | Prueba de contrato sobre la salida del Redactor frente al esquema de `AGENTS.md` §4.5 | T | `programa` | Bloqueante |
| RF-WRK-09 | Prueba unitaria sobre los parámetros de invocación: modelo, pensamiento y `max_tokens` igual al techo de salida declarado en la `Tarea`, nunca mayor | T | `programa` | Bloqueante |
| RF-WRK-07 | Integración continua: el hash del fichero de prompt cambia y la versión no | A | `programa` | Bloqueante |
| RF-WRK-08 | Análisis estático de las rutas de registro, más inspección de una traza real | A / I | `programa` | Bloqueante |
| RF-API-01, RF-API-05 | Pruebas de contrato sobre cada endpoint | T | `programa` | Bloqueante |
| RF-API-02 | Prueba de contrato: si falta un campo obligatorio, `422` | T | `programa` | Bloqueante |
| RF-API-03 | Prueba de contrato: `202` con id de `Tarea`, sin bloqueo | T | `programa` | Bloqueante |
| RF-API-04 | Prueba de contrato sobre el flujo de eventos | T | `programa` | Bloqueante |
| RF-API-06 | Análisis estático: las clases del dominio no aparecen en ninguna firma de ruta | A | `programa` | Bloqueante |
| RF-API-07 | Análisis estático: el cliente de modelo no se alcanza desde `api/` | A | `programa` | Bloqueante |

### 8.7 No funcionales

| ID | Metodología | Clase | Modo | Autoridad |
| --- | --- | --- | --- | --- |
| RNF-01 a RNF-03 | Análisis estático del grafo de importaciones, en integración continua | A | `programa` | Bloqueante |
| RNF-04 | Prueba unitaria de la configuración por defecto | T | `programa` | Bloqueante |
| RNF-05 | Prueba de integración: las cuatro señales aparecen tras una ejecución completa | T | `programa` | Bloqueante |
| RNF-06, RNF-08 | Integración continua con los comandos de `CLAUDE.md` §6 | T | `programa` | Bloqueante |
| RNF-07 | Inspección en revisión de código: cada test de invariante se ha visto fallar antes | I | `humano` | Bloqueante |

### 8.8 Lo que en v1 no tiene verificación

Se declara para que nadie lo dé por cubierto, siguiendo el criterio de huecos declarados
de `verification.md` §10:

- **Fuga epistémica, disciplina de POV y violación de `ReglaDelMundo`.** Sin verificador
  en v1. RF-QUA-14 obliga a que las puertas los muestren como evidencia ausente.
- **La fiabilidad de la extracción del Redactor no se mide.** V-01 de `verification.md`
  §12 exige un *recall* de `hechos_nuevos_detectados` contra un inventario anotado a
  mano, y ese conjunto congelado no existe. RF-QUA-19 y RF-QUA-20 hacen depurable y
  visible el fallo, pero no lo cuantifican: el supuesto S-10 se queda sin medir en toda
  la v1. Es el hueco más serio de esta lista, porque afecta a tres de los cinco
  invariantes bloqueantes que v1 sí implementa.
- **Los nueve validadores restantes de `verification.md` §12** dependen de corpus que no
  existen o de fases posteriores. v1 solo cubre V-04 (RF-QUA-14), V-09 (RF-CAN-06) y
  V-10 (RF-ORQ-08 y RF-ORQ-09).
- **Deriva de compresión** (`verification.md` §7). Sin pirámide de resúmenes no es
  medible. RF-CTX-02 deja registrado el recuento por componente para poder medirla en
  cuanto exista la fase 3.
- **Dimensiones `juez_llm`.** Ninguna está en v1, así que ningún umbral de aceptación
  penaliza nada: las escenas se aceptan solo con evidencia determinista.
- **Dimensiones `humano`.** Valor literario, adecuación al mercado, originalidad y
  satisfacción de la promesa al lector siguen sin automatizarse y se muestrean.

---

## 9. Impacto

### 9.1 Documentos de `docs/`

| Documento | Impacto |
| --- | --- |
| `definitions.md` | **Cambia.** Añade la clase `Predicado` —catálogo de RF-STO-07— y el vocabulario cerrado `exclusividad_de_predicado` con los valores `funcional` y `multivalor`. Exige `RegistroDeDecision`, según `AGENTS.md` §10.1 |
| `domain-knowledge.md` | **Cambia.** El diagrama 8 incorpora `PREDICADO` y su arista con `HECHO`. Con `Volumen` y `PREDICADO` deja de ser «las 12 clases del núcleo» y pasa a ser el esquema de v1: hay que decidir cuál de las dos cosas es y ajustar su encabezado |
| `architecture.md` | **Cambia al cerrar.** Las cifras de §4.2 se corrigen con lo que registre `Procedencia`, según el TODO que ese apartado ya declara. El supuesto S-9 de 3.5 ya está recogido en §11; S-10 y S-11 tienen que añadirse ahí al cerrar. Además, su §12 pierde cinco entradas: R-1 responde las preguntas 1 y 2 —los 100.000 son operativos— y R-2, R-3 y R-4 responden la 3, la 4 y la 5. R-5 cierra el TODO de §6.5, y R-1 obliga a resolver el de caché de prefijo de §4.7 |
| `verification.md` | **Cambia al cerrar.** §10 pierde los huecos que v1 cierra y gana los que v1 abre, enumerados en 8.8 |
| `AGENTS.md`, `CLAUDE.md` | Sin cambios. v1 implementa lo que ya dicen |

### 9.2 Decisiones que esta spec registra

Las ocho resoluciones de las preguntas que abría el apartado 12, una por fila. Cada una
necesita su `RegistroDeDecision` al implementar, con el motivo y la alternativa que
aquí quedan escritos (`AGENTS.md` §9).

| # | Resuelve | Decisión | Motivo | Alternativa descartada |
| --- | --- | --- | --- | --- |
| R-1 | P-1 y la pregunta 2 de `architecture.md` §12 | El Redactor usa `claude-opus-5`, pensamiento adaptativo, `effort: high`, `max_tokens` igual al techo de salida de la `Tarea` (4.000) | Una llamada de redacción cuesta ≈ $0,21 y una novela de 120.000 palabras ≈ $15 de Redactor: el coste no domina y la prosa es el producto | `claude-sonnet-5` para ahorrar ≈ $9 por novela. Bajar de modelo por coste es lo que D-08 prohíbe hacer en silencio; si alguna vez se hace, se decide y se registra |
| R-2 | P-2 y la pregunta 3 de `architecture.md` §12 | Los reintentos de transporte los hace el cliente del SDK: `max_retries = 3`, retroceso exponencial con *jitter* | Una sola capa mantiene la contabilidad de coste de RF-ORQ-09 intacta | Implementar la escalera de transporte en `worker/`: dos capas multiplican —tres por tres son nueve llamadas pagadas por un corte de red— |
| R-3 | P-3 y la pregunta 4 de `architecture.md` §12 | Un historial tipificado por intento, no dos contadores | D-06 clasifica en cuatro clases, no en dos: con dos contadores, transporte y presupuesto caen en el mismo saco y se pierde la señal de §9 | Dos contadores enteros. Más baratos hoy, pero exigen migración en cuanto alguien pregunte por qué se reintentó |
| R-4 | P-4 y la pregunta 5 de `architecture.md` §12 | El borrador rechazado **no** entra en el intento siguiente; sí entran los `Defecto` abiertos | `architecture.md` §3.2: reinyectarlo invita a reproducirlo, y la prosa es el componente más caro del paquete | Incluirlo marcado como rechazado. Los modelos anclan en el texto presente por mucho que se etiquete, y el paquete dejaría de ser de tamaño constante |
| R-5 | P-5 y el TODO de `architecture.md` §6.5 | 10 minutos por invocación, 30 por `Tarea` con sus reintentos, 8 horas por `Plan` | S-8 dice que el turno se mide en minutos; los 30 quedan por debajo de los 40 que daría el reloj real de R-2 | Timeouts agresivos de 60 s / 5 min / 1 h. Cancelar no cancela el coste (§6.5): un vencimiento falso es una invocación pagada y perdida |
| R-6 | P-6 | Se acepta el corte: un solo rol con modelo y los esqueletos por API | El trabajo de prompts es lo más caro de iterar, y un esqueleto escrito a mano es el control del experimento | Añadir también al Arquitecto. Duplica el trabajo de prompts y un esqueleto generado por modelo contamina todas las verificaciones aguas abajo |
| R-7 | P-7 | Se acepta el catálogo de predicados, con el conjunto de partida de abajo | Sin él, «contradicción de hechos» no es un predicado ejecutable | Inferir la exclusividad con un modelo: mete no determinismo dentro del verificador que debe poder parar la línea |
| R-8 | P-8 | Tetragramas, contra todos los capítulos anteriores del volumen, umbral de 2 apariciones | El trigrama en castellano dispara falsos positivos; el fallo que se persigue es el de la escena 40 que no ve las 39 anteriores | Ventana de N capítulos. La repetición que más molesta al lector es justo la de larga distancia |

**R-1 · salvedad de fiabilidad.** El identificador del modelo, su ventana y su precio
salen de una tabla de referencia con fecha de corte anterior a esta spec, y no se han
podido contrastar contra la API de modelos porque este entorno no tiene credenciales.
Antes de implementar RF-WRK-09 hay que confirmarlos.

**R-7 · conjunto de partida del catálogo.** Nueve predicados, sin inventar vocabulario:
los siete valores de `dimensión_de_estado` de `definitions.md` —salud, ubicación,
lealtad, emoción, recursos, reputación y conocimiento— como `funcional`, más `posee` y
`conoce_a` como `multivalor`.

**Catálogo de predicados con exclusividad declarada.**

- **Decisión.** Un `Hecho` solo puede usar un predicado presente en el catálogo, y el
  catálogo declara si es `funcional` —a lo sumo un valor vigente por sujeto, y por tanto
  dos intervalos solapados son una contradicción— o `multivalor`.
- **Motivo.** El invariante 3 de `definitions.md` habla de «predicados mutuamente
  excluyentes» sin decir quién decide cuáles lo son. Sin ese dato, «contradicción de
  hechos» —la comprobación central de la fase 1— no es un predicado ejecutable.
- **Alternativas descartadas.** *Inferir la exclusividad del texto del predicado con un
  modelo*: mete una llamada no determinista dentro del verificador que debe poder parar la
  línea. *Lista de pares excluyentes en código*: crece sin gobierno y queda fuera del
  alcance de `RegistroDeDecision`, que es justamente lo que `CLAUDE.md` §5.2 evita.
- **Cómo entran los predicados.** Solo por migración, nunca por API en tiempo de
  ejecución: si añadir un predicado exige `RegistroDeDecision`, un endpoint de alta lo
  convertiría en un dato más y el vocabulario dejaría de estar cerrado. La migración
  inicial siembra el conjunto de partida (RF-STO-10) y cada predicado posterior es una
  migración con su decisión registrada. Queda dentro de lo que pregunta P-7.
- **Implicaciones.** Añadir un predicado es un cambio de vocabulario controlado y exige
  `RegistroDeDecision`. Es un coste de anotación real, del mismo tipo que
  `hechos_requeridos` en `AGENTS.md` §4.2, y por la misma razón.

### 9.3 Módulos y migraciones

- **Módulos nuevos:** los ocho bloques de 2.2. Ninguno fuera de la estructura ya fijada en
  `architecture.md` §2.3 y `CLAUDE.md` §4.
- **Migraciones:** una inicial, hacia delante, con las tablas de 5. No hay canon
  almacenado previo, así que no hay migración de datos.

---

## 10. Criterios de aceptación

El cambio se puede dar por cerrado cuando **todos** se cumplen:

1. El bucle de 3.2 se ejecuta de principio a fin sobre un `Brief` de prueba y produce un
   `Borrador` aceptado y canonizado, con la revisión del canon incrementada.
2. El mismo bucle, con un borrador que contradice el canon **repitiendo el tipo de
   defecto**, termina en `Defecto`, reescritura dirigida y replanificación en el segundo
   intento, tal como exige RF-ORQ-06, sin haber sobrescrito canon en ningún momento.
3. El mismo bucle, con defectos **de tipos distintos** en intentos sucesivos, recorre la
   escalera entera de RF-ORQ-05 y termina en `escalada` en el cuarto intento. Los dos
   caminos se comprueban por separado porque RF-ORQ-06 impide que un solo caso los
   recorra ambos.
4. Cada requisito de 4 tiene al menos un test asociado, y cada test de invariante se ha
   visto fallar antes de existir su implementación (RNF-07). Los de RF-QUA-01 a
   RF-QUA-09, RF-QUA-16 y RF-QUA-17 corren sobre el corpus de casos sembrados de A9.
5. `uv run pytest`, `uv run pytest -m invariants`, `ruff` y `mypy backend/` en verde.
6. El análisis estático de límites de módulos pasa: RNF-01 a RNF-03, RF-STO-04, RF-QUA-15,
   RF-API-06 y RF-API-07.
7. Una generación archivada se reproduce desde su `Procedencia`: misma revisión de canon y
   mismo hash de paquete (RF-CTX-06).
8. Tras una ejecución completa, las cuatro señales de RNF-05 están registradas y son
   consultables.
9. El `RegistroDeDecision` del catálogo de predicados existe, y `definitions.md` y
   `domain-knowledge.md` están actualizados según 9.1.
10. Esta spec está actualizada con lo que realmente se construyó, con cada desviación
   anotada y su motivo (`AGENTS.md` §10.4).

---

## 11. Riesgos

Los de `architecture.md` §10 que muerden en v1, más los que abre este corte de alcance.

| Riesgo | Señal temprana | Mitigación |
| --- | --- | --- |
| La ausencia del filtro epistémico (S-9) hace que la prosa de v1 no sea representativa | Defectos de continuidad que ningún verificador de v1 puede expresar | Muestreo humano de las primeras escenas antes de dar por buena la fase 1 |
| Reserva de tokens no liberada en alguna ruta de salida | El sistema se va parando sin errores visibles | Pruebas basadas en propiedades de RF-ORQ-08 sobre todas las secuencias de salida |
| El catálogo de predicados se convierte en un cuello de botella de anotación | Más canonizaciones fallidas por predicado no catalogado que por contradicción | Medir la proporción de rechazos por ese motivo; si domina, volver a la spec |
| Sin política de retención, el fichero de SQLite crece sin techo | Tamaño del fichero por capítulo | Declarado como deuda; bloqueado por la pregunta abierta 7 de `architecture.md` §12 |
| Un solo rol con modelo deja el resto de contratos de `AGENTS.md` sin ejercitar | Contratos de rol que, al implementarse en fase 2, no encajan con el orquestador | El contrato común de `AGENTS.md` §3 se implementa completo aunque en v1 solo lo use el Redactor |
| La suite de invariantes pasa sin discriminar | Mutaciones que sobreviven | Pruebas de mutación de 8.4, aunque su autoridad sea de advertencia |
| Canon fantasma: hechos vigentes que ninguna escena narra siguen condicionando lo que se escribe después | Hechos vigentes sin escena que los narre al cerrar el capítulo | RF-CAN-06 y la auditoría de `deriva_de` de V-09; en v1 es más probable porque sin pirámide de resúmenes la cascada tiene menos aristas que seguir |
| Anotar `hechos_requeridos` a mano por escena es el cuello de botella real de v1, y R-6 lo asume al dejar al Arquitecto fuera | Escenas dadas de alta con `hechos_requeridos` mínimo o vacío para salir del paso | Medir la media declarada por escena: si cae, la fuga epistémica de la fase 2 nacerá ciega. Con ~46 escenas el coste es asumible; a mayor escala, entra el Arquitecto |
| La caché de prefijo no llega a activarse y D-16 optimiza algo que no ocurre | `usage.cache_read_input_tokens` a cero de forma sostenida | El componente estático son 2.000 tokens y el prefijo mínimo cacheable del proveedor va de 512 a 4.096 según modelo: si queda por debajo, no cachea **y no avisa**. Comprobarlo en la primera ejecución real; si falla, S-4 es falso y hay que decidir si se agranda el prefijo |
| El corpus de A9 no representa lo que falla de verdad, y los verificadores pasan sobre casos cómodos | Defectos reales que ningún caso sembrado se parecía a ellos | Sembrar los casos a partir de defectos observados en ejecución, no solo inventados al escribir el test |

---

## 12. Preguntas abiertas

**Vacío.** Las ocho preguntas que este apartado contenía quedaron resueltas en 9.2, de
R-1 a R-8, cada una con su motivo y su alternativa descartada. Con el apartado vacío la
spec deja de estar bloqueada y puede aprobarse, que es justo la condición que fija
`AGENTS.md` §10.2.

Las cuatro preguntas restantes de `architecture.md` §12 siguen sin afectar a v1:

| Pregunta de `architecture.md` §12 | Estado |
| --- | --- |
| 1 · ¿El límite de 100.000 es del proveedor o de operación? | **Respondida por R-1**: el modelo elegido tiene ventana de 1M, así que los 100.000 son una decisión de operación. Se mantienen como límite duro y no se suben |
| 8 · ¿Qué umbral marca dos hechos como duplicado aproximado? | RF-CAN-03 deduplica solo de forma exacta. La deduplicación aproximada no entra en v1 |
| 9 · ¿Cuánto puede aplazarse una tarea P2? | No hay tareas P2 en v1: juicio y crítica están fuera de alcance |
| 10 · ¿Dónde se consultan las señales de §9? | RNF-05 obliga a registrarlas y RF-API-05 a poder leerlas; con qué herramienta se miran es una decisión de operación, no de esta spec |

---
## 13. Plan de implementación

| | |
| --- | --- |
| **Estado** | `aprobado` el 2026-09-22 por @Nabeel. La puerta *Plan aprobado* de `AGENTS.md` §10.5 queda superada: los 102 requisitos tienen paso y cada paso, test nombrado |
| **Fecha** | 2026-09-22 |
| **Spec de la que cuelga** | SPEC-001, `aprobada` el 2026-09-22 |

El orden no es el de los apartados de 4, es el de las dependencias: nada se construye
antes que aquello contra lo que se comprueba. Cada paso es lo bastante pequeño para
revisarse de una sentada, nombra su test antes de escribirlo y declara qué se hace si no
sale.

El ciclo de cada paso es el TDD de `AGENTS.md` §10.4: rojo, verde, refactor, con el test
visto fallar **por el motivo correcto** antes de implementar nada (RNF-07).

### 13.1 Fase A · Cimientos

Sin invocación de modelo. Al final de la fase existe el canon y se puede consultar.

| # | Paso | Módulos | Test que lo demuestra | Requisitos |
| --- | --- | --- | --- | --- |
| A1 | Esqueleto del paquete y **puerta de análisis estático en CI** de los límites de módulo | `backend/`, tubería de CI | `test_import_boundaries`: el grafo de importaciones viola una regla y la puerta falla | RNF-01 a RNF-03, RNF-06, RF-STO-04, RF-QUA-15, RF-API-06, RF-API-07 |
| A2 | Enumeraciones cerradas del dominio | `domain/` | `test_enum_rejects_unknown_value`: un valor fuera del vocabulario falla al construir | RF-DOM-03 |
| A3 | Clases del plano diegético: `Entidad`, `Personaje`, `Lugar`, `EventoNarrativo`, `Hecho` | `domain/diegetic/` | `test_hecho_exige_valido_desde_evento`, `test_sin_atributos_estaticos_variables` | RF-DOM-01 parcial, RF-DOM-06, RF-DOM-07 |
| A4 | Clases del plano discursivo y de producción, más `Volumen` | `domain/discursive/`, `domain/production/`, `domain/spec/` | `test_escena_rechaza_valor_entrada_igual_salida`, `test_escena_exige_renderiza` | RF-DOM-01, RF-DOM-02, RF-DOM-04, RF-DOM-05 |
| A5 | Mensajes de error del dominio en español, nombrando clase e invariante | `domain/` | Inspección en revisión de código sobre el catálogo de mensajes | RF-DOM-08 |
| A6 | Migración inicial: esquema, índices y **siembra del catálogo `PREDICADO`** | `migrations/` | `test_migracion_desde_base_vacia`: esquema esperado y catálogo con los nueve predicados de R-7 | RF-STO-02, RF-STO-03, RF-STO-09, RF-STO-10 |
| A7 | Factoría de conexiones con WAL y claves foráneas | `store/` | `test_pragmas_en_toda_conexion`: `journal_mode` y `foreign_keys` en cada conexión abierta | RF-STO-01 |
| A8 | Repositorios tipados y CTEs recursivas del grafo causal | `store/` | `test_cte_grafo_profundo` contra un resultado esperado calculado a mano | RF-STO-04, RF-STO-08 |
| A9 | Canon versionado por eventos de cambio | `store/` | `test_reconstruir_revision_n`: propiedad sobre secuencias de cambios, sin copia entera por revisión | RF-STO-05 |
| A10 | Catálogo de predicados y su exclusividad | `store/` | `test_predicado_no_catalogado_se_rechaza` | RF-STO-07 |

### 13.2 Fase B · Verificación determinista

Es la fase que justifica el proyecto, y va **antes** que la generación a propósito: hasta
que no exista lo que bloquea, no hay nada que pueda parar una escena mala.

| # | Paso | Módulos | Test que lo demuestra | Requisitos |
| --- | --- | --- | --- | --- |
| B1 | **Corpus de casos sembrados (A9 del alcance)**: un par por verificador, defecto conocido y caso intacto | `tests/corpus/` | El corpus es el insumo de B2 a B5; su propio test comprueba que cada par difiere en una sola dimensión | Bloque A9 de 2.2 |
| B2 | Verificadores de escena: contradicción, ciclos, precedencia, cambio de valor, borrador único | `quality/` | `test_detecta_<dimension>` y `test_no_inventa_<dimension>` sobre cada par del corpus | RF-QUA-01 a RF-QUA-05 |
| B3 | Verificadores de alcance local y global | `quality/` | Igual que B2, un par por dimensión | RF-QUA-06 a RF-QUA-09, RF-QUA-16, RF-QUA-17, RF-QUA-21, RF-QUA-22 |
| B4 | Forma del `Defecto`, evidencia citable y descarte contado | `quality/` | `test_defecto_sin_evidencia_se_descarta_y_se_cuenta`, `test_defecto_E_cita_bloque_declarado` | RF-QUA-10, RF-QUA-19 |
| B5 | Las cuatro puertas y la evidencia ausente | `quality/`, `orchestrator/gates` | Por puerta, un artefacto que pasa y uno que falla por cada comprobación; `test_evidencia_ausente_no_es_aprobado` | RF-QUA-11 a RF-QUA-14, RF-QUA-18, RF-QUA-20 |
| B6 | Pruebas de mutación sobre `quality/`, con autoridad de advertencia | Tubería de CI | Informe de mutantes supervivientes por dimensión | 8.4, «Discriminación de la suite» |

### 13.3 Fase C · Contexto

| # | Paso | Módulos | Test que lo demuestra | Requisitos |
| --- | --- | --- | --- | --- |
| C1 | Ensamblado con el orden de componentes del contrato de rol y recuento por componente | `context/` | `test_orden_de_componentes`, `test_recuento_coincide_con_lo_contado` | RF-CTX-01, RF-CTX-02 |
| C2 | Filtro temporal, punto de inserción explícito del epistémico y filtro estructural | `context/` | `test_hecho_invalidado_no_entra`, más el punto de inserción visible aunque no filtre | RF-CTX-05 |
| C3 | Presupuesto, orden de recorte fijo y bloqueo con `falta` | `context/` | `test_no_cabe_queda_bloqueada`, `test_intocables_no_se_recortan`, un caso por escalón | RF-CTX-03, RF-CTX-04, RF-CTX-08 |
| C4 | `hash` estable y referencia a la revisión de canon | `context/` | `test_hash_estable`: mismo canon, escena y versión de prompt, mismo hash | RF-CTX-06 |
| C5 | Reconstrucción entera por intento, sin historial acumulativo | `context/` | `test_intento_2_no_contiene_borrador_rechazado` | RF-CTX-07 |

### 13.4 Fase D · Orquestación y canonización

| # | Paso | Módulos | Test que lo demuestra | Requisitos |
| --- | --- | --- | --- | --- |
| D1 | `Plan` como DAG persistido y bucle de reconciliación | `orchestrator/reconcile` | `test_plan_ciclico_se_rechaza_entero`, `test_lista_solo_con_dependencias_aceptadas` | RF-ORQ-01, RF-ORQ-02, RF-ORQ-22 |
| D2 | Máquina de estados de `Tarea` e historial tipificado de intentos | `orchestrator/`, `store/` | Comprobación de modelos sobre la máquina; propiedad de que los contadores por clase derivan del historial | RF-ORQ-03, RF-ORQ-04, RF-ORQ-24, RF-STO-06 |
| D3 | Clasificación de fallos, escalera de reintentos y salto a replanificación | `orchestrator/retries` | `test_solo_contrato_y_contenido_suman_intento`, `test_dos_iguales_replanifican`, `test_transporte_no_duplica_reintentos` | RF-ORQ-05 a RF-ORQ-07, RF-ORQ-20, RF-ORQ-23 |
| D4 | Semáforo de crédito, cola por prioridad con envejecimiento y los tres timeouts | `orchestrator/admission` | Propiedad: el crédito vuelve al inicial en toda secuencia de salida; `test_reserva_mayor_que_credito_se_rechaza`, `test_configuracion_por_defecto` | RF-ORQ-08 a RF-ORQ-12, RNF-04 |
| D5 | Matriz de permisos, idempotencia y reanudación | `orchestrator/permissions`, `orchestrator/dispatch` | `test_rol_no_puede_escribir_clase_ajena`, prueba de caída simulada del proceso | RF-ORQ-13 a RF-ORQ-15, RF-ORQ-21 |
| D6 | Cancelación en cascada, descarte por revisión superada y eventos de transición | `orchestrator/` | `test_cancelacion_no_borra_nada`, `test_resultado_contra_revision_superada_se_descarta` | RF-ORQ-16 a RF-ORQ-19 |
| D7 | Canonización: normaliza, contrasta, promueve, incrementa revisión y cascada | `orchestrator/canonize` | Propiedades sobre `hechos_nuevos_detectados`: compatibles, duplicados, sucesiones y contradictorios; ninguno sobrescribe canon | RF-CAN-01 a RF-CAN-06 |

### 13.5 Fase E · Worker, API y cierre

| # | Paso | Módulos | Test que lo demuestra | Requisitos |
| --- | --- | --- | --- | --- |
| E1 | Worker sin estado, con clasificación precisa de su fallo | `worker/` | Análisis estático: `worker/` no escribe en la tabla de `Tarea`; casos de salida mal formada y truncada | RF-WRK-01, RF-WRK-02, RF-WRK-04 |
| E2 | Rol Redactor: prompt versionado e invocación con los parámetros de R-1 | `agents/redactor/` | `test_max_tokens_igual_al_techo_declarado`, prueba de contrato de la salida | RF-WRK-06, RF-WRK-09 |
| E3 | `Procedencia` en cada invocación y registros sin prosa | `worker/`, `store/` | `test_no_hay_invocacion_sin_procedencia`; análisis de las rutas de registro | RF-WRK-03, RF-WRK-08 |
| E4 | `contexto_insuficiente` y detección de prompt editado sin versionar | `worker/`, CI | `test_contexto_insuficiente_devuelve_null_y_falta`; el hash del prompt cambia y la versión no | RF-WRK-05, RF-WRK-07 |
| E5 | API de altas y lectura, con `422` en campos obligatorios | `api/` | Pruebas de contrato por endpoint; `test_escena_sin_hechos_requeridos_es_422` | RF-API-01, RF-API-02, RF-API-05, RF-API-06 |
| E6 | Encolado con `202` y SSE de transiciones | `api/` | Prueba de contrato del flujo de eventos y del `202` con id de `Tarea` | RF-API-03, RF-API-04, RF-API-07 |
| E7 | **Cierre**: bucle de 3.2 de extremo a extremo y las cinco señales | Todos | Los criterios 1, 2 y 3 de 10, ejecutados sobre un `Brief` de prueba | RNF-05, criterios de aceptación |
| E8 | Actualizar spec y `docs/` según el impacto declarado en 9 | `specs/`, `docs/` | La puerta *Spec y docs al día* de `AGENTS.md` §10.5, más los comandos de `CLAUDE.md` §6 ejecutados tal como están escritos | RNF-08, criterio 10 |

### 13.6 Migraciones

Una sola, en A6, hacia delante y sin migración de datos porque no hay canon previo. Todo
lo que la fase D añade al esquema —`TAREA_INTENTO` de R-3— entra en esa misma migración
inicial, no en una segunda: mientras no exista canon almacenado, rehacer la inicial es
más barato que encadenar migraciones.

### 13.7 Riesgos del plan y marcha atrás

| Paso | Si no sale | Marcha atrás |
| --- | --- | --- |
| A1 | Las reglas de dependencia resultan impracticables con la estructura elegida | Se vuelve a la spec: los límites de módulo son de `architecture.md` §2.3, no negociables en el plan |
| A6 | Los nueve predicados de R-7 no bastan para un `Brief` real | Ampliar el catálogo es un `RegistroDeDecision` más una migración, no un cambio de diseño |
| B1 | El corpus resulta caro de construir o poco representativo | Es el riesgo ya declarado en 11. Se reduce el par por verificador al mínimo y se siembra a partir de defectos reales en cuanto los haya |
| B2-B5 | Una dimensión no se puede expresar como predicado sobre el canon | Se declara evidencia ausente en su puerta, como RF-QUA-14; no se inventa un predicado débil |
| C3 | El paquete no cabe ni apretando los filtros | Es el caso previsto: `bloqueada` con `falta`. Si es sistemático, la spec cortó mal el alcance y se vuelve a ella |
| D4 | El semáforo resulta insuficiente por límite de tasa del proveedor | Cae S-3: hace falta un regulador de tasa junto al semáforo, y eso es spec nueva |
| E2 | El modelo de R-1 no está disponible o sus cifras cambiaron | Es la salvedad declarada en 9.2. Se confirma contra la Models API antes de empezar E2, y si cambia se registra la decisión |
| E7 | El bucle no cierra por acumulación de defectos falsos | Se mira primero el presupuesto de falsos positivos de `verification.md` §6; si se excede, el predicado está mal escrito y vuelve a B |

### 13.8 Lo que este plan no cubre

- Todo lo que 2.3 deja fuera de alcance sigue fuera: no hay pasos para ello.
- Las cifras de R-5 y el umbral de R-8 son de partida y se calibran con `Procedencia` y
  con el corpus; recalibrarlas no exige spec nueva, exige registrar la medida.
- El plan no fija estimaciones de tiempo. El orden es una dependencia, no un calendario.
