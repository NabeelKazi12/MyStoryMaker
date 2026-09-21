# AGENTS.md

Contrato de los agentes que producen la novela: qué hace cada rol, qué puede escribir,
qué contexto recibe y cuándo termina.

Para instrucciones de desarrollo del repositorio, ver `CLAUDE.md`.
Para las definiciones de las clases citadas aquí, ver `docs/ontologia-definiciones.md`.

---

## 1. Principios de la línea

1. **Quien genera no valida.** Ningún agente juzga su propia salida.
2. **Cada rol escribe en un conjunto cerrado de clases.** Ver la tabla del apartado 2.
3. **Nadie ve el libro entero.** Cada agente recibe un `PaqueteDeContexto` de tamaño
   acotado, construido por la capa de contexto, no por el propio agente.
4. **Todo lo que sale de un agente es estructurado.** Prosa más un bloque de datos; no
   prosa de la que otro modelo tenga que inferir datos después.
5. **El canon solo cambia por canonización.** Un agente propone hechos; la promoción es
   un paso separado con verificación.
6. **Todo agente puede rendirse.** Cada rol tiene un criterio explícito de "no puedo
   hacer esto con lo que me han dado" que devuelve el control al Orquestador. Es
   preferible a producir algo plausible pero incoherente.

---

## 2. Roles y permisos de escritura

| Rol | Lee | Escribe | Nunca escribe |
| --- | --- | --- | --- |
| Orquestador | Todo (metadatos) | `Tarea`, `Plan`, `Puerta` | Prosa, canon |
| Arquitecto | `Brief`, canon, plantillas | `Hilo`, `Escena` (esqueleto), `ParSiembraPago` | Prosa, `Hecho` |
| Worldbuilder | `Brief`, canon | `Entidad`, `ReglaDelMundo`, `Lore` | Prosa, `Escena` |
| Investigador | `Brief`, consultas externas | `Lore`, `Hecho` (fase de setup) | Prosa, `Escena` |
| Entrenador de voz | `Brief`, `Personaje`, muestras | `PerfilDeEstilo` | Prosa de escena, canon |
| Redactor | Su `PaqueteDeContexto` | `Borrador` | Canon, `Escena`, `Juicio` |
| Guardián de Continuidad | Canon, `Borrador` | `Defecto` | Prosa, canon, `Juicio` |
| Editor de línea | `Borrador`, `PerfilDeEstilo` | `Revision` | Canon, `Escena` |
| Editor de desarrollo | `Borrador`, `Hilo`, `Escena` | `Critica` | Prosa, canon |
| Juez | `Borrador`, `Rubrica` | `Juicio` | `Defecto`, prosa, canon |
| Canonizador | `Borrador` aceptado, canon | `Hecho`, `EstadoDePersonaje`, `EstadoDeConocimiento` | Prosa, `Juicio` |

El Canonizador es el único rol con escritura en el canon, y actúa solo sobre borradores
ya aceptados.

---

## 3. Contrato común

Toda invocación de un agente sigue la misma forma.

**Entrada**

```
{
  tarea: Tarea,
  paquete_de_contexto: PaqueteDeContexto,   // con hash, inmutable
  restricciones: Restriccion[],              // duras y blandas
  intento: int                               // número de reintento
}
```

**Salida**

```
{
  resultado: <artefacto de su clase permitida> | null,
  datos_estructurados: { ... },              // específico del rol
  confianza: 0.0–1.0,
  contexto_insuficiente: bool,               // true = me falta algo, ver `falta`
  falta: string[],                           // qué necesita, si aplica
  procedencia: Procedencia
}
```

Reglas transversales:

- Si `contexto_insuficiente` es `true`, el agente **no inventa**. Devuelve `resultado:
  null` y enumera qué le falta. El Orquestador reconstruye el paquete o replanifica.
- `confianza` por debajo del umbral del rol escala igual que un fallo de umbral.
- Ningún agente puede modificar su propio `PaqueteDeContexto` ni solicitar más contexto
  directamente al store.

---

## 4. Especificación por rol

### 4.1 Orquestador

**Objetivo.** Descomponer el encargo en `Tarea`s, asignarlas, evaluar `Puerta`s y decidir
reintento, escalado o replanificación.

**No escribe prosa nunca.** Si te encuentras el Orquestador generando texto narrativo,
es un error de diseño.

**Decisiones que le corresponden en exclusiva:**

- Reintentar una escena con el mismo plan (fallo de prosa).
- Replanificar la escena (el fallo es del plan, no del texto).
- Escalar a humano (agotados los reintentos).
- Aceptar con penalización (restricción blanda incumplida, dentro de tolerancia).

**Criterio de replanificación.** Si dos reintentos consecutivos producen el mismo tipo
de `Defecto`, el problema no es la redacción. Replanifica en lugar de reintentar: es lo
que impide que el sistema reescriba indefinidamente una escena imposible.

---

### 4.2 Arquitecto

**Objetivo.** Producir la estructura: `Hilo`s con su pregunta dramática y curva de
tensión, esqueletos de `Escena` y los `ParSiembraPago` que la obra va a abrir.

**Contexto.** `Brief`, canon completo (comprimido), `PlantillaEstructural` aplicable,
presupuestos de palabras por acto.

**Salida obligatoria por escena.** No es opcional: el Redactor no puede trabajar sin esto.

```
{
  pov, escenario, momento_en_historia,
  objetivo, conflicto, resultado,
  valor_entrada, valor_salida,        // deben ser distintos
  funcion_en_trama, tipo,
  hilos_activos[], eventos_a_renderizar[],
  presupuesto_palabras,
  hechos_requeridos[]                  // qué hechos usa esta escena
}
```

`hechos_requeridos` tiene un coste de anotación real y es lo que hace posible la
validación epistémica. No es negociable.

**Prohibido.** `valor_entrada == valor_salida`. Una escena en la que nada cambia es una
escena que sobra, y el verificador la rechaza.

---

### 4.3 Worldbuilder

**Objetivo.** Poblar el mundo con entidades y reglas consistentes.

**Regla de oro.** Toda `ReglaDelMundo` lleva un `coste` declarado. Una regla sin coste
(magia, tecnología, poder social) es una regla que el relato va a usar para resolver
problemas de forma insatisfactoria.

**Toda `Entidad` nueva** lleva `estatus_ontologico`, para que el sistema pueda manejar
rumores y leyendas falsas sin corromper el canon.

**Todo `Lugar`** lleva `atmosfera_sensorial`: un banco de detalles reutilizables. Sin él,
cada visita se describe con vocabulario distinto y el lugar deja de sentirse el mismo.

---

### 4.4 Entrenador de voz

**Objetivo.** Definir y mantener `PerfilDeEstilo` global y un idiolecto por personaje con
diálogo relevante.

**Atención al `vocabulario_prohibido`.** Es la defensa más eficaz contra el léxico
delator de los modelos de lenguaje. Aliméntalo con lo que aparezca de forma recurrente en
los borradores, no solo con una lista inicial.

---

### 4.5 Redactor

**Objetivo.** Convertir un esqueleto de escena en prosa.

**Contexto que recibe** (compuesto por la capa de contexto, en este orden):

1. Estático: premisa, `ContratoDeEstilo`, `PoliticaDeContenido`.
2. Estado del mundo: hechos vigentes de las entidades presentes, filtrados por el momento
   de historia de la escena.
3. Continuidad inmediata: **prosa literal** de la escena anterior.
4. Arco: resumen del capítulo y posición en la curva de tensión de los hilos activos.
5. Voz: perfil global más idiolecto de los personajes con diálogo.
6. Epistémico: qué sabe y qué ignora el POV.
7. Promesas: siembras abiertas próximas a su límite, motivos pendientes.
8. Instrucción: el esqueleto de escena completo.

**Salida.** Prosa, más:

```
{
  hechos_nuevos_detectados[],     // candidatos a canonización, declarados
  eventos_narrados[],
  siembras_tocadas[],
  motivos_manifestados[],
  recuento_palabras
}
```

Declarar los hechos nuevos es más fiable que extraerlos después con otro modelo. Es el
punto más frágil de toda la tubería y por eso se resuelve declarando, no infiriendo.

**Prohibiciones duras:**

- No narrar conciencias que la `Narracion` de la escena no autoriza.
- No usar información que el POV ignora según su `EstadoDeConocimiento`.
- No introducir entidades nuevas con nombre propio. Si la escena las necesita, devuelve
  `contexto_insuficiente` y pide al Worldbuilder que las cree.
- No resolver una siembra que no esté en `siembras_asignadas`.

---

### 4.6 Guardián de Continuidad

**Objetivo.** Detectar incoherencias entre un borrador y el canon. Solo reporta.

**No propone reescrituras.** Su salida es una lista de `Defecto` con evidencia y regla
violada. Separar diagnóstico de tratamiento evita que el guardián negocie consigo mismo
la gravedad de lo que ha encontrado.

**Orden de comprobación** (las tres primeras son bloqueantes):

1. Contradicción de hechos: intervalos de validez solapados con predicados excluyentes.
2. Fuga epistémica: el personaje actúa sobre un hecho que ignora.
3. Violación de `ReglaDelMundo` sin excepción declarada.
4. Deriva de nombres, alias no declarados, ortografía inconsistente.
5. Inconsistencia de POV, tiempo verbal o persona.

La fuga epistémica es el fallo más difícil de detectar leyendo y el más letal para el
misterio. Priorízala.

---

### 4.7 Editor de línea

**Objetivo.** Ritmo, claridad y voz frase a frase, contra el `ContratoDeEstilo`.

**Restricción.** No puede cambiar hechos, eventos ni diálogo que porte información
narrativa. Si una corrección de estilo requiere alterar contenido, emite una `Critica`
para el Editor de desarrollo en lugar de una `Revision`.

Incluye la comprobación de repetición de n-gramas contra los capítulos anteriores. Es el
fallo más característico de los modelos en texto largo: invisible dentro de una escena y
muy visible al leer el libro seguido. Un redactor que escribe la escena 40 sin ver las 39
anteriores repetirá sus propias imágenes favoritas.

---

### 4.8 Editor de desarrollo

**Objetivo.** Estructura, motivación y arco. Opera a nivel de escena y de capítulo.

**Salida.** `Critica` con `span`, `dimension`, `severidad`, `diagnostico` y `sugerencia`.

**Puede rechazar críticas propias anteriores** con justificación. El estado `rechazada`
es necesario: sin él, el sistema entra en revisión perpetua atendiendo observaciones
cuestionables.

---

### 4.9 Juez

**Objetivo.** Puntuar contra `Rubrica` en las dimensiones no deterministas: naturalidad
del diálogo, densidad de cliché, consistencia de motivación, coherencia temática, impacto
emocional, tensión, especificidad sensorial, exposición forzada.

**Reglas:**

- No puede ser la misma instancia ni el mismo prompt que redactó el borrador.
- Toda puntuación va con `confianza` y con la `rubrica_usada`.
- Los descriptores de la rúbrica llevan **ejemplos ancla**. Sin ellos la puntuación no
  es reproducible entre llamadas.
- **Nunca bloquea una puerta.** Solo penaliza y alimenta `UmbralDeAceptacion`.

---

### 4.10 Canonizador

**Objetivo.** Promover al canon los hechos de un borrador aceptado.

**Procedimiento:**

1. Toma `hechos_nuevos_detectados` del borrador aceptado.
2. Normaliza sujeto, predicado y objeto contra las entidades existentes.
3. Comprueba contra el canon vigente.
4. Los compatibles se promueven con `valido_desde` en el evento correspondiente.
5. Los que contradicen el canon **generan un `Defecto`**, no lo sobrescriben.
6. Actualiza `EstadoDeConocimiento` de los personajes presentes y testigos.
7. Incrementa la revisión del canon.
8. Dispara la invalidación en cascada de las `UnidadDeContexto` afectadas.

El paso 5 es el que protege el canon. Un canonizador que resuelve contradicciones por su
cuenta convierte errores detectables en deriva silenciosa.

---

## 5. Puertas

| Puerta | Cuándo | Comprobaciones | Política |
| --- | --- | --- | --- |
| Outline aprobado | Antes de redactar | Conformidad estructural, presupuestos, todo hilo con pregunta dramática | Bloqueante |
| Escena limpia | Antes de aceptar un borrador | Los 8 invariantes bloqueantes | Bloqueante |
| Capítulo cerrado | Fin de capítulo | Continuidad acumulada, n-gramas, presupuesto | Bloqueante |
| Acto cerrado | Fin de acto | Curvas de tensión, hilos activos, beats de plantilla | Advertencia |
| Volumen cerrado | Final | Siembras resueltas, hilos resueltos, promesa al lector | Bloqueante |

Los invariantes concretos de cada puerta están en el apartado 11 del documento de
definiciones y viven como tests en `backend/quality/`.

---

## 6. Reintentos y escalado

```
intento 1  → reescritura con los defectos como instrucción
intento 2  → reescritura con contexto ampliado (ventana anterior mayor)
intento 3  → replanificación de la escena por el Arquitecto
intento 4  → escalado a humano
```

Si dos intentos consecutivos producen el mismo tipo de defecto, salta directamente a
replanificación. Repetir la misma operación esperando un resultado distinto es el modo de
fallo más caro de estos sistemas.

---

## 7. Gestión de procesos

Los apartados anteriores describen qué produce cada rol. Este describe cómo se ejecuta:
ciclo de vida de una `Tarea`, concurrencia, presupuestos y recuperación. La ejecución
vive en `backend/orchestrator/` (decide) y `backend/worker/` (invoca modelos); `api/`
solo encola y lee estado.

### 7.1 Ciclo de vida de una `Tarea`

```
pendiente → lista → en_curso → en_verificacion → aceptada
                        │            │
                        │            ├→ rechazada → (reintento: lista)
                        │            └→ escalada  → (espera humano)
                        ├→ fallida   → (reintento: lista)
                        ├→ bloqueada → (falta contexto o dependencia)
                        └→ cancelada
```

Una `Tarea` pasa a `lista` cuando todas sus `depende_de` están `aceptada`. Ningún otro
criterio la desbloquea: si un plan necesita adelantar trabajo sobre una dependencia sin
aceptar, el plan está mal descompuesto.

Las transiciones las escribe **solo el Orquestador**. El worker informa del resultado de
la invocación; no decide el estado. Esto mantiene una única autoridad sobre la máquina de
estados y encaja con el escritor único de SQLite.

El vocabulario de `Tarea.estado` es cerrado, como el resto de enumeraciones: añadir un
valor requiere un `RegistroDeDecision` y actualizar `docs/definitions.md`.

### 7.2 Planificación y concurrencia

- El `Plan` es un DAG de `Tarea`s. Si aparece un ciclo, es un error de planificación y
  se rechaza el plan entero; no se rompe el ciclo por heurística.
- **Se paraleliza por escenas independientes**, no dentro de una escena. Redacción,
  continuidad y juicio de una misma escena son secuenciales por construcción.
- **Un solo escritor sobre el canon.** Las tareas que canonizan se serializan, aunque
  las que las preceden hayan corrido en paralelo.
- Dos tareas que dependan de la misma revisión del canon no pueden solaparse con una
  canonización en curso. El Orquestador toma la revisión del canon como recurso
  exclusivo, no como dato compartido.
- El grado de paralelismo es configuración del Orquestador, no del worker. Un worker que
  decide cuánto trabajo coger convierte el coste en algo impredecible.

### 7.3 Presupuestos y límites

Toda `Tarea` lleva `presupuesto` en tokens, coste y tiempo, y los tres se comprueban:

- **Tokens.** El ensamblador cuenta antes de llamar y rechaza el paquete si excede.
  Excederse es `bloqueada` con `falta`, no truncar.
- **Tiempo.** Una invocación sin respuesta dentro de su límite se cancela y cuenta como
  intento. Una tarea colgada bloquea todo su subárbol de dependencias.
- **Coste.** El plan tiene un techo acumulado. Al alcanzarlo, el Orquestador no degrada
  la calidad en silencio: detiene la ejecución y escala.

Un presupuesto que solo se registra y nunca se hace cumplir es documentación, no control.

### 7.4 Idempotencia y reanudación

- Una `Tarea` se identifica por `(plan, objetivo, revision_de_canon, hash_del_paquete,
  version_de_prompt, intento)`. Reejecutar con la misma clave devuelve el artefacto ya
  producido en lugar de volver a invocar el modelo.
- El estado vive en SQLite, no en memoria del worker. Si el proceso cae, el Orquestador
  reconstruye la cola desde la tabla de `Tarea`.
- Al arrancar, toda `Tarea` que quedó `en_curso` sin `Procedencia` registrada vuelve a
  `lista` y suma un intento. Si la `Procedencia` está registrada pero no el artefacto,
  la invocación se pagó y se perdió: queda anotado, porque es la métrica que revela
  caídas recurrentes del worker.
- La escritura del artefacto y la transición de estado ocurren en la misma transacción.
  Separarlas produce borradores huérfanos y tareas que parecen pendientes con el trabajo
  ya hecho.

### 7.5 Cancelación e invalidación

- Cancelar una `Tarea` cancela su subárbol de dependientes; los artefactos ya producidos
  se marcan `obsoleto`, nunca se borran.
- Si el canon cambia bajo una tarea `en_curso`, su resultado se descarta al volver: se
  generó contra una revisión que ya no es la vigente. Aceptarlo "porque está bien
  escrito" es exactamente cómo entra la deriva.
- La invalidación en cascada de `UnidadDeContexto` es parte del cierre de la
  canonización, no un trabajo posterior opcional.

### 7.6 Observabilidad

- Cada transición de estado emite un evento con marca de tiempo; la API lo retransmite
  por SSE (`/tareas/{id}/eventos`). El frontend no hace polling ni infiere progreso.
- Por `Tarea` se registran intentos, coste acumulado, latencia y tipo de `Defecto` que
  provocó cada rechazo. Los reintentos por tipo de defecto son la señal que dice si lo
  que falla es la redacción o el plan.
- Una tarea `escalada` es visible sin buscarla. Un escalado que nadie ve es un sistema
  parado que parece lento.

---

## 8. Prompts y procedencia

- Un fichero por rol bajo `backend/agents/<rol>/prompts/`, versionado semánticamente.
- Editar un prompt sin incrementar su versión rompe la reproducibilidad de todo lo
  generado antes. No lo hagas.
- Cada llamada registra `Procedencia` con `agente`, `modelo`, `version_de_prompt`, `hash`
  del paquete de contexto, parámetros de muestreo, coste y latencia.
- El enlace al paquete de contexto es lo que permite responder a la única pregunta que
  importa al depurar: ¿el agente se equivocó, o nunca recibió el dato?

---

## 9. Registro de decisiones

Toda decisión creativa no trivial se registra como `RegistroDeDecision` con su
alternativa descartada y su motivo.

En obras largas la deriva rara vez viene de mala prosa. Viene de decisiones olvidadas y
luego contradichas sin que nadie se dé cuenta.
