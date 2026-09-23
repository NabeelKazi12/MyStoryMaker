# Verificación: qué método le toca a cada dimensión

2026-09-21

## Qué contiene este documento

El reparto concreto de la verificación. `definitions.md` enumera las dimensiones
de calidad y los invariantes, y `architecture.md` §7 describe en abstracto quién
tiene autoridad para bloquear; aquí se dice, para cada dimensión, **con qué
método se comprueba, quién la comprueba, qué recibe exactamente y con qué
severidad sale el `Defecto`**. La segunda mitad trata los otros dos niveles: cómo
se comprueba que el sistema que escribe la novela funciona, y cómo se comprueba
el código que lo sostiene. Los dos últimos apartados cierran por el otro lado:
qué fallos se presentan como verde (§11) y qué valida cada uno (§12).

Este documento no define dimensiones nuevas, ni roles nuevos, ni valores nuevos
de enumeración. Si una dimensión aparece aquí y no en `definitions.md`, es un
error de este documento. Si un rol aparece aquí y no en `AGENTS.md` §2, también.

## 1. Los tres niveles

La verificación se parte en niveles, y confundirlos es la causa de que un sistema
generativo parezca validado sin estarlo.

| Nivel | Pregunta | Objeto | Dónde se trata |
| --- | --- | --- | --- |
| Obra | ¿Es correcto el texto producido? | Párrafos, escenas, capítulos, el volumen entero | §4, §5 y §6 |
| Sistema | ¿Se comporta de forma fiable el conjunto de agentes? | Agentes, `Tarea`, `Defecto`, `Procedencia` | §7, §11 y §12 |
| Repositorio | ¿Es correcto el código que comprueba la obra? | `backend/`, `frontend/`, `docs/` | §8 |

El nivel de obra se apoya en los otros dos. Un verificador programático cuya
suite nadie ha sometido a mutación no verifica, pasa; y un agente cuya tasa de
acierto nadie ha medido no verifica, opina con formato de tabla.

La diferencia con un sistema puramente agéntico está en el nivel de repositorio:
aquí la mayor parte de lo que bloquea es código determinista en `backend/quality/`,
no un agente leyendo. Eso es lo que permite el cuarto principio de diseño de
`architecture.md` §1 — solo lo determinista bloquea — y también lo que obliga a
verificar ese código con el mismo rigor que la prosa.

## 2. Vocabulario controlado: `modo_de_verificación`

Tres valores cerrados, los de `definitions.md`. Toda `DimensiónDeCalidad` lleva
exactamente uno, y de ese valor se deriva la autoridad: no se decide dos veces.

| Valor | Qué significa | Fiabilidad | Puede bloquear |
| --- | --- | --- | --- |
| `programa` | Un verificador de `backend/quality/` evalúa un predicado sobre el canon y sobre datos estructurados del borrador; no interpreta prosa como lector | Determinista **sobre su entrada**: misma entrada, mismo resultado | Sí |
| `juez_llm` | El Juez puntúa contra una `Rubrica` con ejemplos ancla y devuelve `puntuacion` y `confianza` | Media, y variable entre llamadas sobre el mismo texto | No: penaliza y alimenta `UmbralDeAceptacion` |
| `humano` | Una persona lee y decide, por muestreo o en una puerta de cierre | Alta sobre lo que lee; no escala | Sí, con excepción autorizada |

**El predicado es determinista; su entrada no siempre lo es.** Varias dimensiones
de §4 no operan sobre el canon sino sobre una extracción del texto: los
`hechos_nuevos_detectados`, los `eventos_narrados` y las `siembras_tocadas` que
declara el Redactor (`AGENTS.md` §4.5), los `hechos_requeridos` que declara el
Arquitecto (§4.2), las conciencias a las que accede el texto, o los nombres
propios que no corresponden a ningún alias declarado. Esas entradas las produce
un modelo leyendo, o un extractor que se equivoca de otra manera.

Eso no degrada el modo —el predicado sigue siendo `programa`, sigue siendo
reproducible y sigue pudiendo bloquear—, pero traslada el error a un sitio que
hay que declarar: **si la extracción omite algo, el verificador pasa en verde sin
haber evaluado nada.** Las dimensiones en esa situación se marcan **(E)** en la
columna *Modo* de §4, la fiabilidad de cada extracción se mide en §7, y el fallo
que producen es F-01 y F-02 de §11.

**Cinco de los ocho invariantes bloqueantes son (E)**: contradicción de hechos,
fuga epistémica, violación de `ReglaDelMundo`, disciplina de POV y escena con
evento renderizado. Es el dato más incómodo de este documento y por eso está
aquí y no en una nota al pie.

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
posterior (reescritura, replanificación, escalado) es el de `architecture.md` §6.3.

**(E)** en la columna *Modo* marca las dimensiones cuyo predicado es determinista
pero cuya entrada es una extracción del texto (§2). Su fiabilidad no se da por
supuesta: se mide en §7 y su modo de fallo está en §11.

### Alcance local — frase y párrafo

La deriva de nombres se reparte entre dos comprobadores, y no por capricho: el
alias no declarado exige ver el canon, que el Editor de línea no recibe por
diseño. El alcance local describe dónde está el defecto, no quién lo encuentra.

| Dimensión | Modo | Quién comprueba | Proyección mínima | Severidad |
| --- | --- | --- | --- | --- |
| Deriva de nombres | `programa` **(E)** | `backend/quality/` vía Guardián de Continuidad | Entidades del canon con sus alias declarados, texto del borrador | alta |
| Consistencia de tiempo y persona | `programa` | `backend/quality/` vía Guardián de Continuidad | Tiempo y persona del `ContratoDeEstilo`, texto del borrador | media |
| Repetición de n-gramas | `programa` | `backend/quality/` vía Editor de línea | Trigramas y tetragramas de los capítulos anteriores, texto nuevo | media |
| Diversidad léxica | `programa` | `backend/quality/` vía Editor de línea | Type-token ratio del capítulo y vocabulario delator del `ContratoDeEstilo` | baja |
| Métricas de estilo del `ContratoDeEstilo` | `programa` | `backend/quality/` vía Editor de línea | Umbrales numéricos del `ContratoDeEstilo` —longitud media de frase y varianza, densidad léxica, proporción de diálogo, tics verbales— y texto del borrador | media |
| Variedad sintáctica percibida | `juez_llm` | Juez | Texto de la escena, rúbrica de estilo | baja, ruidosa |
| Especificidad sensorial | `juez_llm` | Juez | Texto de la escena, rúbrica de estilo | baja, ruidosa |
| Densidad de cliché | `juez_llm` | Juez | Texto de la escena, rúbrica de estilo | media, ruidosa |
| Naturalidad del diálogo | `juez_llm` | Juez | Réplicas de la escena, `PerfilDeEstilo` de los personajes presentes | media, ruidosa |

### Alcance de escena y capítulo

Aquí viven los ocho invariantes bloqueantes de `definitions.md`. Las siete
primeras filas los cubren y todas son `programa` sin excepción: son la razón por
la que la puerta *Escena limpia* puede parar la línea.

| Dimensión | Modo | Quién comprueba | Proyección mínima | Severidad |
| --- | --- | --- | --- | --- |
| Contradicción de hechos | `programa` **(E)** | `backend/quality/` vía Guardián de Continuidad | Hechos vigentes del sujeto con sus intervalos, `hechos_nuevos_detectados` del borrador | crítica |
| Fuga epistémica | `programa` **(E)** | `backend/quality/` vía Guardián de Continuidad | `EstadoDeConocimiento` del elenco presente en ese punto, hechos que cada acción del texto usa | crítica |
| Violación de `ReglaDelMundo` | `programa` **(E)** | `backend/quality/` vía Guardián de Continuidad | Reglas activas en el marco y sus excepciones declaradas, eventos narrados | crítica |
| Violación de línea temporal | `programa` | `backend/quality/` | Grafo causal de `EventoNarrativo`, `posicion_en_historia` y las `ramas[]` de la `LineaTemporal`, vía CTE recursiva | crítica |
| Disciplina de POV | `programa` **(E)** | `backend/quality/` vía Guardián de Continuidad | `Narracion` de la escena con su `fiabilidad` y su `acceso_a_conciencias[]`, conciencias a las que accede el texto | crítica |
| Escena con cambio de valor y con evento | `programa` **(E)** | `backend/quality/` | `valor_de_entrada`, `valor_de_salida` y aristas `renderiza` de la escena | crítica |
| Un solo `Borrador` aceptado por escena | `programa` | `backend/quality/` | `estado_de_borrador` de todos los borradores de la escena | crítica |
| Evento narrado con posición en la línea temporal | `programa` | `backend/quality/` | `posicion_en_historia` de los eventos que la escena renderiza | alta |
| Conformidad estructural | `programa` | `backend/quality/` vía Editor de desarrollo | Beats de la `PlantillaEstructural` y beats realizados de la escena | media |
| Presupuesto de palabras | `programa` | `backend/quality/` | Presupuesto declarado del capítulo y recuento real | baja |
| Consistencia de motivación | `juez_llm` | Juez | Arco y `necesidad_interna` del POV, texto de la escena | media, ruidosa |
| Exposición forzada (*infodumping*) | `juez_llm` | Juez | Texto de la escena, rúbrica de exposición | media, ruidosa |
| Impacto emocional | `juez_llm` | Juez | Texto de la escena, `funcion_en_trama` declarada | baja, ruidosa |

### Alcance global — acto y volumen

| Dimensión | Modo | Quién comprueba | Proyección mínima | Severidad |
| --- | --- | --- | --- | --- |
| Siembras sin pagar | `programa` **(E)** | `backend/quality/` vía Editor de desarrollo | Todos los `ParSiembraPago` con su `estado_de_siembra` y su límite | crítica al cierre del volumen |
| Hilos resueltos o abandonados | `programa` | `backend/quality/` vía Editor de desarrollo | Todos los `Hilo` con su resolución declarada | crítica al cierre del volumen |
| Pregunta dramática de hilo principal respondida | `programa` | `backend/quality/` vía Editor de desarrollo | `pregunta_dramatica` de cada `Hilo` principal y la escena declarada como su resolución | crítica al cierre del volumen |
| Hilo inactivo más de N escenas | `programa` | `backend/quality/` | Aristas `avanza` de todas las escenas en orden, N por `tipo_de_hilo` | media |
| Valencia de relación cambiada sin evento | `programa` | `backend/quality/` vía Guardián de Continuidad | `valencia` de cada `Relación` por intervalo y eventos vigentes en el punto del cambio | media |
| Curva de tensión plana | `programa` | `backend/quality/` vía Editor de desarrollo | `funcion_en_trama` de todas las escenas del acto en orden | media |
| Frecuencia de motivos | `programa` **(E)** | `backend/quality/` | Aristas `manifiesta` del volumen y frecuencia objetivo de cada `Motivo` | baja |
| Arcos con estado terminal | `programa` | `backend/quality/` vía Editor de desarrollo | Arco de cada protagónico con su estado declarado por capítulo | crítica al cierre del volumen |
| Coherencia temática | `juez_llm` | Juez | Resúmenes de todos los capítulos, `Tema` declarados | media, ruidosa |
| Tensión y curiosidad | `juez_llm` | Juez | Resúmenes de los capítulos del acto en orden | baja, ruidosa |
| Promesa al lector satisfecha | `humano` | Editor humano | Volumen cerrado y el `Brief` original | crítica, sin sustituto programático |

### Alcance de contrato — Brief, restricciones y outline

Las dimensiones anteriores proyectan sobre el texto de un `Borrador`. Estas no:
se cobran en la puerta *Outline aprobado*, antes de que exista prosa, o sobre el
encargo entero, así que su proyección es el `Brief` y la estructura declarada.

`Restriccion` es el único elemento cuyo modo no es fijo: cada instancia lo lleva
en su atributo `verificable_por`, y la consecuencia de incumplirla sale de su
`dureza` —dura bloquea, blanda penaliza—. Las filas de abajo son las
combinaciones que hoy tienen sentido; la que no lo tiene está declarada en §10.

| Dimensión | Modo | Quién comprueba | Proyección mínima | Severidad |
| --- | --- | --- | --- | --- |
| Todo hilo con pregunta dramática declarada | `programa` | `backend/quality/` vía Editor de desarrollo | `pregunta_dramatica` de cada `Hilo` del outline | crítica |
| Protagónico con `Hilo` y `necesidad_interna` | `programa` | `backend/quality/` | `relevancia`, `necesidad_interna` y aristas a `Hilo` de cada `Personaje` | crítica |
| `Restriccion` dura verificable por programa | `programa` | `backend/quality/` | Enunciado y ámbito de la `Restriccion`, artefacto de ese ámbito | crítica |
| `Restriccion` dura verificable por persona | `humano` | Editor humano | Enunciado y ámbito de la `Restriccion`, artefacto de ese ámbito | crítica, en puerta de cierre |
| `Restriccion` blanda | `juez_llm` | Juez | Enunciado y ámbito de la `Restriccion`, artefacto de ese ámbito | media, ruidosa |
| `PoliticaDeContenido` y `tabúes` del `Brief` | `programa` **(E)** | `backend/quality/` | `categoria` y `nivel_permitido` de cada política, `tabúes[]` del `Brief`, texto del borrador | crítica |
| `tratamiento_requerido` de materia sensible | `juez_llm` | Juez | Texto de la escena y `tratamiento_requerido` de la política aplicable | media, ruidosa |

Sin estas filas, la decisión «aceptar con penalización» que `AGENTS.md` §4.1
reserva al Orquestador se toma sobre una restricción que nadie ha evaluado.

### Excepciones declaradas

§7 somete al sistema a briefs con narrador no fiable y con saltos temporales
largos, y §4 marca la disciplina de POV y la línea temporal como críticas y
bloqueantes. Sin un mecanismo de excepción esas dos cosas se contradicen: la
obra que el sistema debe aguantar es justo la que la puerta rechaza.

La excepción no se concede en la puerta: **se declara en el canon antes de
redactar**, con clases que `definitions.md` ya trae, y el verificador la lee como
parte de su proyección. Ninguna de estas filas añade nada a la ontología.

| Desviación | Qué la autoriza | Dónde se declara |
| --- | --- | --- |
| El texto entra en una conciencia que la focalización no permitiría | `acceso_a_conciencias[]` de la `Narracion` | `Narracion` de la escena o de la sección |
| Narrador no fiable que afirma lo que el canon desmiente | `fiabilidad` de la `Narracion`, con la `certeza` del `Hecho` y el `estatus_ontológico` de la entidad | `Narracion` y canon |
| El relato cuenta los hechos en otro orden | Nada, porque no es una desviación: el invariante ordena el tiempo de historia, no el del relato | — |
| Rama temporal, realidad alternativa o viaje en el tiempo | `ramas[]` de la `LineaTemporal` | `LineaTemporal` |
| Evento que contradice una regla del mundo | `excepciones[]` de la `ReglaDelMundo` | `ReglaDelMundo` |

Una desviación que no encaja en ninguna de las anteriores no se arregla
declarándola: sube a `excepciones_autorizadas[]` de la `Puerta`, exige un
`RegistroDeDecision` y queda contada por la fila «Que la puerta trasera no se
convierte en la puerta» de §7. Ese camino es caro a propósito.

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
verificador. `architecture.md` §7.3 fija cinco puertas y su política; esta tabla
dice qué dimensiones de §4 se cobran en cada una.

| Puerta | Cuándo | Qué se cobra | Política | Presupuesto de falsos positivos |
| --- | --- | --- | --- | --- |
| Outline aprobado | Antes de redactar | Conformidad estructural, presupuesto de palabras y las dimensiones de alcance de contrato de §4 | Bloqueante | ≤ 1 por volumen |
| Escena limpia | Antes de aceptar un borrador | Los ocho invariantes bloqueantes de §4, alcance de escena | Bloqueante | ≤ 1 por capítulo, agregado sobre los ocho |
| Capítulo cerrado | Fin de capítulo | Las dimensiones de escena de §4 reejecutadas sobre el capítulo cerrado, repetición de n-gramas contra capítulos anteriores, presupuesto | Bloqueante | ≤ 1 por acto |
| Acto cerrado | Fin de acto | Curva de tensión, hilos inactivos, conformidad de beats, frecuencia de motivos, más los indicadores adelantados de abajo | Advertencia | No aplica: no bloquea |
| Volumen cerrado | Final | Siembras sin pagar, hilos resueltos, preguntas dramáticas respondidas, arcos con estado terminal, promesa al lector | Bloqueante | 0: lo que llega aquí se inspecciona a mano |

**El presupuesto de falsos positivos es agregado, no por dimensión.** *Escena
limpia* cobra ocho invariantes sobre cada borrador, así que sus tasas se suman:
ocho comprobaciones al 1 % dan una puerta al 8 %, y cinco de esas ocho son **(E)**,
donde el error no es el del predicado sino el de la extracción. El coste tampoco
es un reintento: por `architecture.md` §6.3, dos defectos consecutivos del mismo
tipo saltan a replanificación, así que un falso positivo sistemático replanifica
una escena que estaba bien. Por eso el presupuesto se declara por puerta, y por
eso lo vigila V-05 en §12.

Las cifras son presupuestos declarados de diseño, no medidas, igual que las de
`architecture.md` §4.2. Calibrarlas exige el corpus de casos sembrados que §10
declara inexistente.

«Continuidad acumulada» no es una dimensión aparte, y por eso no tiene fila en
§4: es la reejecución de las dimensiones de escena sobre el capítulo ya cerrado,
donde los intervalos de vigencia y las fugas epistémicas se ven entre escenas y
no dentro de una sola.

*Acto cerrado* es la única puerta de advertencia, y lo es porque todo lo que
cobra es de grado: un acto con la curva algo plana sigue siendo un acto. Las
otras cuatro cobran predicados binarios.

Eso deja un hueco de tiempo que conviene ver: siembras, hilos y arcos solo se
cobran en *Volumen cerrado*, donde un fallo ya no se arregla reescribiendo una
escena. **Los indicadores adelantados** son esas mismas dimensiones medidas
antes y sin bloquear, para que lo que va a fallar al final se vea en el acto
segundo y no en el último.

| Indicador adelantado | Dimensión de §4 que anticipa | Qué se mira al cerrar el acto |
| --- | --- | --- |
| Siembras cuya `distancia_maxima_aceptable` vence dentro del acto siguiente | Siembras sin pagar | Cuántas quedan abiertas y cuánto margen les resta |
| Hilos sin escena de resolución planificada en lo que queda de outline | Hilos resueltos o abandonados | Hilos abiertos sin destino en el plan |
| Preguntas dramáticas de hilo principal sin escena candidata de respuesta | Pregunta dramática de hilo principal respondida | Preguntas sin salida prevista |
| Arcos de protagónico cuyo estado no ha avanzado en todo el acto | Arcos con estado terminal | Arcos parados |

Ninguno es una dimensión nueva: son proyecciones anticipadas de cuatro filas que
§4 ya tiene, cobradas como advertencia. Sus umbrales están sin fijar, y eso está
declarado en §10.

## 7. Verificación del sistema que escribe

El nivel de obra mide la novela. Este mide el sistema, y es lo que permite
afirmar que el bucle converge en lugar de suponerlo.

| Qué se verifica | Clase | Cómo | Qué delata | Hoy |
| --- | --- | --- | --- | --- |
| Que los verificadores detectan | T | Casos sembrados: un borrador con un defecto conocido de una sola dimensión por caso | Tasa de detección por dimensión | Bloqueada |
| Que no inventan defectos | T | Los mismos casos, con esa dimensión intacta | Falsos positivos por capítulo | Bloqueada |
| Que el bucle converge | A | Recuento de intentos hasta `aceptado`, contra los cuatro de `architecture.md` §6.3 | Escenas que giran sin cerrar | Corre |
| Que no se repite el mismo fallo | A | Tipo de defecto en intentos consecutivos: dos iguales obligan a replanificar | Reescrituras que no arreglan nada | Corre |
| Que los defectos son utilizables | A | Proporción descartada por falta de `evidencia` | Agentes que opinan en vez de comprobar | Corre |
| Que los artefactos están bien formados | A | Recuento de rechazos por campo ausente, por rol | Un rol con demasiado alcance o con pocos ejemplos | Corre |
| Que una generación se puede reproducir | T | *Replay* desde una `Procedencia` archivada: misma revisión de canon, mismo hash de paquete | Prompts editados sin subir versión | Corre |
| Que el contexto no se degrada | D | Recuento por componente de `PaqueteDeContexto` a lo largo del libro | Deriva de compresión: el paquete de la escena 40 mayor que el de la 3 | Corre |
| Que el canon no acumula fantasmas | D | Auditoría de `deriva_de` en cada canonización | Hechos vigentes que ninguna escena narra | Corre |
| Que el sistema aguanta lo difícil | T | Briefs adversarios: personajes homónimos, narrador no fiable, saltos temporales largos, misterio con revelación tardía | Dimensiones que solo fallan bajo presión | Bloqueada |
| Que cabe en el presupuesto | A | Tokens por ejecución frente al techo de 100.000 y al objetivo de 24.000 | Verificación que se come la generación | Corre |
| Que un prompt nuevo no empeora nada | D | Despliegue progresivo: un capítulo por versión de prompt antes de aplicarlo al volumen | Regresiones de estilo invisibles en una escena | Bloqueada |
| Que lo declarado cubre lo narrado | D | Conjunto congelado de escenas con su inventario de hechos anotado a mano: se mide el *recall* de `hechos_nuevos_detectados`, no su precisión | Canon incompleto que ningún verificador puede ver | Bloqueada |
| Que `hechos_requeridos` no se queda corto | I | Muestreo humano sobre escenas aceptadas: hechos que el texto usa y la escena no declaró requerir | Fugas epistémicas que el verificador nunca llega a evaluar | Corre |
| Que el juez no evalúa su propia prosa | A | Invariante sobre `Procedencia`: el juez y la `version_de_prompt` del `Juicio` difieren de los del `Borrador` | La separación entre generar y validar rota sin que nadie lo note | Corre |
| Que la proyección mínima no lleva material de sobra | D | Red-teaming: se amplía la proyección de un rol con material que no le toca y se mide el aumento de falsos positivos | Predicados vagos y agentes que opinan | Bloqueada |
| Que el agente se rinde en lugar de inventar | D | Paquetes mutilados a propósito: debe devolver `resultado: null` con su `falta`, nunca prosa | Contexto insuficiente resuelto inventando | Bloqueada |
| Que la puntuación del juez es estable | D | Test-retest: la misma escena puntuada varias veces; varianza por dimensión | Umbrales calibrados sobre ruido | Bloqueada |
| Que la puerta trasera no se convierte en la puerta | D | Proporción de puertas superadas con `excepciones_autorizadas`, por invariante y por persona | Un invariante que en la práctica ya no bloquea | Corre |

**Ocho de las diecinueve filas no corren hoy**, y todas por lo mismo: no existe
el material sobre el que correrlas. Son tres corpus distintos y conviene no
confundirlos, porque se construyen de forma distinta y cuestan distinto.

| Corpus | Qué es | Filas que desbloquea |
| --- | --- | --- |
| Casos sembrados | Un borrador con un defecto conocido de una sola dimensión, y el mismo caso intacto | Que los verificadores detectan · Que no inventan defectos |
| Conjunto congelado de escenas | Material que no cambia, para comparar entre versiones de prompt y medir varianza y *recall* | Que un prompt nuevo no empeora nada · Que lo declarado cubre lo narrado · Que la puntuación del juez es estable · Que la proyección mínima no lleva material de sobra · Que el agente se rinde |
| Briefs adversarios | Encargos con lo que se sabe que le cuesta: homónimos, narrador no fiable, saltos temporales, revelación tardía | Que el sistema aguanta lo difícil |

Mientras no existan, **la mitad del nivel de sistema es una intención**. Las once
filas que sí corren son todas señales de producción: dicen cómo se comporta el
sistema, no si acierta.

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
de `architecture.md` §2.3 y los invariantes de `definitions.md`.

La columna *Clase* usa el marco T/A/I/D/U; la columna *Origen* cita el apartado
de `architecture.md` —o del documento que se nombre— que impone el requisito,
para que un cambio en un documento se note en el otro.

### Límites de módulos

| Elemento | Metodología | Clase | Origen | Autoridad |
| --- | --- | --- | --- | --- |
| `domain/` no importa de ningún otro paquete (ni `store/`, ni `agents/`, ni FastAPI, ni Pydantic) | Análisis estático del grafo de importaciones | A | §2.3 | Bloqueante |
| `quality/` importa de `domain/` y nunca de `agents/` | Análisis estático del grafo de importaciones | A | §2.3 | Bloqueante |
| `agents/` no importa de `agents/`: la coordinación vive en `orchestrator/` | Análisis estático del grafo de importaciones | A | §2.3 | Bloqueante |
| Solo `store/` habla con SQLite y con el índice vectorial | Análisis estático: `sqlite3` y el cliente vectorial no se alcanzan desde ningún otro paquete | A | §2.3, §3.1 | Bloqueante |
| `api/` no invoca modelos: encola `Tarea` y lee estado | Análisis estático: el cliente de modelo no se alcanza desde `api/` | A | §2.3, §2.2 | Bloqueante |
| `frontend/` no contiene reglas de dominio ni invariantes duplicados | Inspección en revisión de código | I | §2.3, §2.2 | Bloqueante |
| Tipos de las clases de la ontología | Comprobación de tipos | A | §2.3 | Bloqueante |

### Almacenamiento

| Elemento | Metodología | Clase | Origen | Autoridad |
| --- | --- | --- | --- | --- |
| `journal_mode=WAL` y `foreign_keys=ON` en toda conexión abierta por `store/` | Pruebas unitarias sobre la factoría de conexiones | T | §3.1 | Bloqueante |
| Escritor único: ninguna escritura sobre el canon se emite fuera del orquestador | Análisis del grafo de llamadas + pruebas de integración con tareas concurrentes | A / T | §3.1, §9 | Bloqueante |
| Índices sobre `(sujeto_id, predicado)`, `posicion_en_historia` y `(conocedor_id, hecho_id)` | Pruebas de integración: plan de consulta de las validaciones más frecuentes | T | §3.1 | Advertencia |
| El canon versionado se reconstruye desde eventos de cambio, sin copia entera por revisión | Pruebas basadas en propiedades: reconstruir la revisión *N* y compararla con el estado en *N* | T | §3.1 | Bloqueante |
| Migraciones de SQLite hacia delante | Pruebas de integración contra un canon real | T | §2.3, §3.1 | Bloqueante |
| Ningún hecho se valida contra el índice vectorial | Análisis estático: `quality/` no alcanza el índice vectorial por ninguna ruta | A | §3.1 | Bloqueante |
| Modelo y versión del embedding guardados junto a cada vector, con reindexación completa al cambiarlos | Pruebas unitarias sobre la escritura en el índice, más comprobación del esquema `vec0` | T | §3.1 | Bloqueante |
| El filtrado por metadatos ocurre dentro del predicado del KNN, no después | Prueba de integración: un filtro que descarta candidatos no reduce el número de vecinos devueltos | T | §3.1 | Bloqueante |
| La canonización nunca sobrescribe canon: lo que lo contradice produce un `Defecto` | Pruebas basadas en propiedades sobre `hechos_nuevos_detectados` contradictorios | T | §8 | Bloqueante |

### Tubería de contexto

| Elemento | Metodología | Clase | Origen | Autoridad |
| --- | --- | --- | --- | --- |
| El `PaqueteDeContexto` cabe en 20.000–25.000 tokens, muy por debajo del techo de 100.000 | Pruebas basadas en propiedades sobre escenas generadas | T | §4.1 | Bloqueante |
| El ensamblador cuenta tokens antes de llamar y rechaza el paquete que excede; nunca trunca por la cola | Pruebas unitarias con paquetes por encima del presupuesto | T | §4.1 | Bloqueante |
| El paquete de la escena 3 y el de la escena 40 son equivalentes en tamaño | Pruebas basadas en propiedades sobre longitud de libro | T | §4.1 | Bloqueante |
| `PaqueteDeContexto` almacena el recuento real por componente | Pruebas unitarias sobre el ensamblado | T | §4.4 | Bloqueante |
| El filtro temporal actúa antes del epistémico | Prueba unitaria con un hecho vigente que el POV ignora: entra por el temporal, sale por el epistémico | T | §4.4 | Bloqueante |
| Cascada completa: resúmenes de la escena, de todo contenedor, hechos establecidos y paquetes que la citaban | Pruebas basadas en propiedades sobre cascadas de invalidación | T | §4.6 | Bloqueante |
| Cierre de `deriva_de`: ninguna `UnidadDeContexto` viva deriva de una fuente obsoleta | Pruebas basadas en propiedades sobre cascadas de invalidación | T | §4.6, §9 | Bloqueante |

### Admisión y presupuesto

| Elemento | Metodología | Clase | Origen | Autoridad |
| --- | --- | --- | --- | --- |
| El crédito vuelve a su valor inicial tras cualquier secuencia de éxito, fallo, timeout y cancelación | Pruebas basadas en propiedades sobre secuencias generadas de rutas de salida | T | §6.6 | Bloqueante |
| Los tokens en vuelo nunca superan 100.000, y una reserva mayor que el crédito total se rechaza como error de planificación | Pruebas basadas en propiedades sobre planes generados | T | §4.1, §6.6 | Bloqueante |
| Ninguna tarea P2 o P3 espera indefinidamente: la cola envejece | Comprobación de modelos sobre la política de admisión | A | §6.6 | Advertencia |
| Cada nivel de timeout vence, libera la reserva y se clasifica como fallo de contrato | Pruebas unitarias por nivel de timeout | T | §6.5 | Bloqueante |
| Idempotencia: reejecutar con la misma clave devuelve el artefacto en lugar de invocar el modelo | Pruebas basadas en propiedades sobre la clave de seis campos | T | §6.4 | Bloqueante |
| Reanudación: toda `Tarea` que quedó `en_curso` sin `Procedencia` vuelve a `lista` y suma un intento | Pruebas de integración con caída simulada del proceso | T | §6.4 | Bloqueante |
| Sin degradación silenciosa: ninguna ruta cambia modelo, prompt o paquete sin dejarlo en `Procedencia` | Análisis del grafo de llamadas más inspección en revisión de código | A / I | §6.5 | Bloqueante |
| El modelo invocado es el declarado en `architecture.md` §5.1, y la llamada no lleva `effort` ni pensamiento extendido | Prueba de contrato sobre los parámetros con que `worker/` construye la invocación, más comprobación de que `Procedencia` registra ese mismo identificador | T | §5.1, §9 | Bloqueante |
| El estado se pasa por referencia: ninguna `Tarea` recibe la salida literal de la anterior | Análisis estático de las entradas de `dispatch` | A | §6.4 | Bloqueante |

Esta tabla es la que faltaba cuando `architecture.md` §10 llama a la reserva no
liberada «el modo de fallo más difícil de diagnosticar»: un crédito que se
pierde no produce ningún error, solo un sistema que se va parando.

### Proceso y fronteras

| Elemento | Metodología | Clase | Origen | Autoridad |
| --- | --- | --- | --- | --- |
| Separación de escritura por rol: el Canonizador es el único que escribe canon | Guardarraíles en `orchestrator/`, contrastados con la matriz de `AGENTS.md` §2 | A / T | §1, §2.3 | Bloqueante |
| Ciclo de vida de la escena: un solo `Borrador` aceptado, todo camino termina | Comprobación de modelos sobre la máquina de estados de `architecture.md` §6.2 | A | §6.2 | Bloqueante |
| Escalado de reintentos: cuatro intentos, y salto a replanificación si dos consecutivos dan el mismo tipo de defecto | Pruebas unitarias sobre el contador del orquestador | T | §6.3, §9 | Bloqueante |
| Frontera API ↔ React (esquemas Pydantic, eventos SSE, `202 Accepted` con id de `Tarea`) | Pruebas de contrato | T | §2.2 | Bloqueante |
| Un prompt editado sin incrementar su versión semántica | Integración continua: el hash del prompt cambia y la versión no | A | §9 | Bloqueante |
| Cambio de stack o valor nuevo en una enumeración cerrada sin `RegistroDeDecision` | Integración continua: comprobación del registro en el propio cambio | A | §2.1, §9 | Bloqueante |
| Paso de las puertas en cada cambio del repositorio | Integración continua: la misma tubería que el código humano | T | §7.3 | Bloqueante |
| La proyección mínima de cada rol es un subconjunto de su `PaqueteDeContexto` | Pruebas de contrato por rol contra el paquete ensamblado | T | §4.3 | Bloqueante |
| Toda `Rubrica` lleva ejemplo ancla por nivel de la escala | Análisis estático sobre los ficheros de rúbrica | A | §7.1 | Bloqueante |
| Toda `Restriccion` dura tiene verificador asociado; un `verificable_por` que no resuelve es error de construcción | Análisis estático | A | §7.1 | Bloqueante |
| ¿La suite de invariantes detecta algo? | Pruebas de mutación periódicas sobre `backend/quality/` | T | §7.3 | Advertencia |

La última fila es la que sostiene a las demás. «Un invariante sin test no existe»
garantiza que el test está escrito, no que discrimine: sin mutación, una suite
que pasa siempre es indistinguible de una suite que comprueba de verdad.

### Documentación

`docs/` es la especificación contra la que se verifica todo lo anterior, así que
también se verifica. No es celo: la revisión que añadió este apartado encontró
once referencias `§N.N` apuntando a apartados inexistentes o equivocados.

| Elemento | Metodología | Clase | Origen | Autoridad |
| --- | --- | --- | --- | --- |
| Toda referencia de la forma `documento §N.N` resuelve a un encabezado existente | Análisis estático sobre `docs/`, `AGENTS.md`, `CLAUDE.md` y `specs/`, en integración continua | A | `AGENTS.md` §10.1 | Bloqueante |
| Todo identificador `D-NN` citado existe en el Índice de decisiones | Análisis estático | A | Apéndice A | Bloqueante |
| Todo rol citado existe en `AGENTS.md` §2 y toda dimensión citada, en `definitions.md` | Análisis estático | A | Encabezado de este documento | Bloqueante |

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
(`architecture.md` §6.3), y la puerta *Volumen cerrado*. El editor no ejecuta
pasos intermedios.

## 10. Huecos declarados

Lo que este documento exige y hoy no tiene verificación real. Una tabla de
verificación sin huecos declarados suele significar que no se ha mirado.

- **No existe ninguno de los tres corpus de §7** —casos sembrados, conjunto
  congelado de escenas y briefs adversarios—, y con ellos no corren ocho de sus
  diecinueve filas. El hueco se declaraba antes solo para el conjunto congelado;
  los otros dos estaban dados por supuestos. Sin casos sembrados no hay tasa de
  detección ni de falsos positivos, así que tampoco se pueden calibrar los
  presupuestos de §6 ni el umbral de V-05.
- **Las pruebas de mutación de §8 no están en la tubería.** Mientras no lo estén,
  la cobertura de invariantes es una afirmación no verificada.
- **La comprobación de modelos del ciclo de vida** se apoya en que el diagrama de
  `architecture.md` §6.2 y el código del orquestador no diverjan. Nada lo
  comprueba hoy.
- **La puerta *Acto cerrado*** de §6 no tiene invariantes enumerados en
  `definitions.md` al modo de las otras. Hasta que los tenga, su contenido es una
  intención, no una comprobación. *Outline aprobado* ya tiene dimensiones
  asignadas en §4, pero tampoco figuran en esa lista.
- **El *replay* de §7 supone** que el índice vectorial devuelve los mismos vecinos
  para la misma consulta tras una reindexación. No está comprobado; si no se
  cumple, el *replay* reproduce la llamada pero no el paquete.
- **Las cinco decisiones de stack** de `architecture.md` §2.1 —desde que D-17
  añadió el modelo generador— no viven en ninguna enumeración, así que la
  comprobación de `RegistroDeDecision` no detecta que cambien.
- **Que la prosa de `claude-haiku-4-5` dé el listón no está medido.** D-17
  (`architecture.md` §5.1) elige el modelo por coste y deja escrito que la calidad
  es una hipótesis. Refutarla o confirmarla corresponde a las dimensiones de
  estilo de §4, y hoy ninguna puede: las de `juez_llm` solo penalizan, los
  umbrales del `ContratoDeEstilo` no están decididos —el hueco de abajo— y el
  conjunto congelado de escenas de §7, que es lo único que permitiría comparar dos
  modelos sobre el mismo material, no existe. Clase U mientras siga así. La
  decisión escrita al lado: se acepta como riesgo, porque el modelo se puede
  cambiar sin migración y el gasto de elegir mal son ≈ $3 por novela, no un
  esquema que rehacer.
- **Los umbrales numéricos del `ContratoDeEstilo`** que cobra la fila «Métricas de
  estilo» de §4 no están decididos. La fila declara quién comprueba y con qué
  proyección; qué margen tolera cada métrica es comportamiento nuevo y exige spec.
- **Una `Restriccion` con `dureza: dura` y `verificable_por: juez` es hoy una
  combinación contradictoria**: §2 dice que un juez nunca bloquea y
  `definitions.md` dice que una restricción dura bloquea. Mientras no se resuelva,
  §4 no le asigna fila y el reparto la trata como blanda.
- **El catálogo de `PoliticaDeContenido` está vacío.** La fila existe en §4, pero
  sin categorías ni niveles declarados no comprueba nada.
- **La reincidencia de §5 no tiene ventana ni umbral.** «La señal es la
  reincidencia, no la puntuación de una escena suelta» no es ejecutable hasta que
  se diga cuántas escenas y cuánta caída.
- **La proporción de excepciones autorizadas que mide §7 no tiene umbral**, así
  que hoy es una cifra observable sin nadie que reaccione a ella. V-06 propone
  uno; no está acordado.
- **Ninguna dimensión (E) tiene medida de la fiabilidad de su extracción.** Cinco
  de los ocho invariantes bloqueantes dependen de una entrada que produce un
  modelo, y hoy nadie sabe con qué tasa omite. Hasta que V-01 y V-02 corran, la
  autoridad de bloqueo de esas cinco descansa sobre un supuesto sin medir.
- **Los presupuestos de falsos positivos de §6 son declarados, no medidos**, igual
  que las cifras de `architecture.md` §4.2. Hasta calibrarlos, V-05 compara contra
  un número inventado de buena fe.
- **Los indicadores adelantados de *Acto cerrado* no tienen umbral.** Se sabe qué
  mirar y no cuánto es demasiado, así que hoy informan y no accionan.
- **Los umbrales objetivo de §12 son de diseño.** Ninguno sale de una medición, y
  cambiarlos con datos reales no exige spec: exige registrar la medida.
- **La excepción declarada de §4 no es expresable en la fase 1.** `Narracion`
  entra en la fase 2 de `architecture.md` §13 y `LineaTemporal` no está en el
  núcleo mínimo, así que hasta entonces ni el narrador no fiable ni las ramas
  temporales se pueden declarar, y esa parte de los briefs adversarios no corre.

## 11. Modos de fallo silencioso

Todo lo anterior describe cómo se detecta un fallo. Este apartado describe los
que **no** se detectan, porque se presentan como verde: la puerta pasa, no se
emite ningún `Defecto` y no queda nada que mirar.

No son dimensiones de calidad nuevas ni roles nuevos —el documento sigue sin
definirlos, según su encabezado—: son formas de fallar del propio sistema de
verificación, y por eso no tienen fila en §4. La columna *Señal indirecta* es lo
único que hay, porque un fallo silencioso no tiene señal directa por definición.
Cada fila tiene su validador en §12.

| # | Qué es | Se origina en | Señal indirecta que lo delataría |
| --- | --- | --- | --- |
| F-01 | La extracción omite un hecho: `hechos_nuevos_detectados` no lo trae, la contradicción nunca llega a evaluarse y el canon queda incompleto sin que nada falle | §2 **(E)**, §4 alcance de escena | Hechos nuevos por millar de palabras cayendo a lo largo del volumen; entidades presentes en la prosa sin ningún hecho nuevo en varios capítulos seguidos |
| F-02 | `hechos_requeridos` se queda corto y la fuga epistémica se evalúa sobre menos hechos de los que la escena usa | §4 alcance de escena | Razón entre entidades presentes en la escena y hechos requeridos declarados, por escena y por rol que la planificó |
| F-03 | La suite de invariantes pasa siempre porque no discrimina, no porque el texto esté limpio | §8, donde la mutación es *Advertencia* | Dimensiones con cero defectos en un volumen entero; tasa de detección que no se mueve entre versiones de prompt |
| F-04 | La evidencia ausente se lee como aprobado y la puerta cierra sin el juicio que nunca llegó | §6, §2 | Puertas cerradas con evidencia ausente no vacía, y su proporción creciendo capítulo a capítulo |
| F-05 | Un falso positivo sistemático se convierte en replanificación: dos defectos consecutivos del mismo tipo replanifican una escena que estaba bien | §6 | Replanificaciones concentradas en una sola dimensión; escenas replanificadas cuyo resultado apenas difiere del primero |
| F-06 | La excepción autorizada se normaliza y el invariante deja de bloquear en la práctica sin que nadie lo derogue | §2, fila `humano` | Proporción de puertas superadas por excepción, desglosada por invariante y por persona |
| F-07 | El juez puntúa prosa salida de su mismo prompt y la aprueba | §2 `juez_llm`, filas de juez de §4 | `confianza` alta con varianza baja; una dimensión cuya puntuación no baja nunca |
| F-08 | La pirámide mantiene el paquete constante borrando en lugar de comprimir | §8 tubería de contexto | Tokens por componente planos mientras los defectos de continuidad crecen con el número de capítulo |
| F-09 | Canon fantasma: hechos vigentes que ninguna escena narra siguen condicionando las escenas siguientes | §7, §8 tubería de contexto | Hechos vigentes sin escena que los narre; `UnidadDeContexto` viva derivada de una fuente ya obsoleta |
| F-10 | Una reserva de crédito no liberada va parando el sistema sin producir ningún error | §8 admisión y presupuesto | Tokens en vuelo que no vuelven a cero entre planes; tareas admitidas por hora cayendo sin cambio de carga |
| F-11 | Vectores de dos modelos de embedding mezclados devuelven vecinos plausibles y equivocados | §8 almacenamiento | Distribución de distancias que cambia de escala tras un despliegue; recuperaciones que dejan de repetirse en un *replay* |
| F-12 | *Acto cerrado* es de advertencia, nadie lee sus avisos y llegan intactos a *Volumen cerrado*, donde ya no se arreglan | §6 | Avisos de acto abiertos y sin decisión al abrir el acto siguiente |

Cuatro de los doce —F-01, F-02, F-05 y F-07— nacen de decisiones que este mismo
documento toma. No están aquí como riesgo externo: son el precio de haber puesto
autoridad de bloqueo sobre entradas que no controla del todo, y por eso su
validador importa más que el de los otros ocho.

## 12. Validadores

Uno por fila de §11. Ninguno introduce dimensiones ni roles: comprueban la
ejecución, no la obra, y por eso viven aquí y no en §4.

Los umbrales son **objetivos declarados de diseño, no medidas**, igual que las
cifras de `architecture.md` §4.2. La columna *Si no se cumple* respeta la regla
que ordena todo el documento —la ausencia de evidencia nunca se convierte en
evidencia favorable, `architecture.md` §1, principio 8—, así que ninguna reacción
es «seguir adelante».

| ID | Valida | Método | Umbral objetivo | Si no se cumple |
| --- | --- | --- | --- | --- |
| V-01 | F-01 | *Recall* de `hechos_nuevos_detectados` contra el inventario anotado a mano del conjunto congelado | ≥ 0,95 por capítulo | Las dimensiones **(E)** que dependen de esa extracción dejan de contar como evidencia favorable: la puerta las declara ausentes y la escena escala a muestreo humano |
| V-02 | F-02 | Muestreo humano sobre escenas aceptadas: hechos que el texto usa y no estaban en `hechos_requeridos` | ≤ 1 omisión por capítulo muestreado | La escena vuelve a planificación para completar la anotación; si se repite en dos capítulos, la fuga epistémica pasa a evidencia ausente en su puerta |
| V-03 | F-03 | Pruebas de mutación sobre `backend/quality/`, por dimensión y nunca agregadas | ≥ 0,80 de mutantes muertos por dimensión | La dimensión se declara no verificada en las puertas que la cobran y la escena escala, en lugar de contar como superada |
| V-04 | F-04 | Recuento de puertas cerradas con evidencia ausente no vacía, sobre el total de puertas evaluadas | ≤ 5 % de las puertas de un capítulo | Se detiene el avance de fase y se escala: es exactamente el caso que el principio 8 prohíbe resolver avanzando |
| V-05 | F-05 | Falsos positivos agregados por puerta sobre los casos sembrados, contra el presupuesto de §6 | Dentro del presupuesto declarado en §6 | Se revisa el predicado de esa dimensión antes de seguir cobrándola en una puerta bloqueante: el salto a replanificación de `architecture.md` §6.3 está multiplicando el coste del error |
| V-06 | F-06 | Proporción de puertas superadas por `excepciones_autorizadas`, por invariante y por persona | ≤ 2 % por invariante y por volumen | Se revisa el invariante: una excepción frecuente significa que el predicado está mal escrito, no que la obra sea excepcional |
| V-07 | F-07 | Invariante sobre `Procedencia` —juez y `version_de_prompt` distintos de los del `Borrador`— más varianza test-retest por dimensión | 0 coincidencias; varianza dentro del margen declarado de la `Rubrica` | El `Juicio` se descarta y se repite con otro juez; si la varianza no baja, la dimensión deja de alimentar su `UmbralDeAceptacion` |
| V-08 | F-08 | Recuento de tokens por componente frente a defectos de continuidad, ambos por número de capítulo | Sin correlación creciente entre capítulo y defectos de continuidad | Se audita la pirámide de resúmenes antes de seguir generando: el paquete constante estaba ocultando pérdida de información |
| V-09 | F-09 | Auditoría de `deriva_de` en cada canonización, más recuento de hechos vigentes sin escena que los narre | 0 hechos vigentes huérfanos al cerrar el capítulo | Se marca obsoleto lo que la cascada no alcanzó, y queda registrado por qué no lo alcanzó |
| V-10 | F-10 | Conciliación del semáforo: crédito en vuelo al terminar cada `Plan`, contra su valor inicial | Vuelve exactamente al inicial | Se detiene la admisión y se reconstruye el contador desde el estado de SQLite, que es la única fuente fiable |
| V-11 | F-11 | Comprobación del par modelo/versión de embedding en cada vector del índice, más *replay* de una consulta archivada | 100 % de los vectores con par declarado; mismos vecinos en el *replay* | Reindexación completa antes de volver a recuperar; el `PaqueteDeContexto` afectado deja de ser reproducible y se marca como tal |
| V-12 | F-12 | Avisos de *Acto cerrado* que siguen abiertos al abrir el acto siguiente | 0 abiertos | El acto siguiente no arranca hasta que cada aviso tenga decisión registrada: resuelto, o aceptado con penalización y su `RegistroDeDecision` |

Los doce comparten una propiedad que conviene no perder: **ninguno lee prosa**.
Miran la ejecución —`Procedencia`, `Puerta`, `Tarea`, el índice, el semáforo—,
que es lo que sigue registrado cuando el texto ya no dice nada sobre lo que
falló. Un fallo silencioso no se detecta leyendo mejor; se detecta mirando otra
cosa.
