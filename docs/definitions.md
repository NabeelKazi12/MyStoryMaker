# Ontología para generación agéntica de novelas — Definiciones

2026-09-21 · @Nabeel

## Propósito y alcance

Esta ontología existe para que un sistema multiagente pueda escribir una novela de 80.000–150.000 palabras sin perder coherencia, y para poder demostrarlo con comprobaciones automáticas en lugar de lectura humana completa.

Resuelve cuatro fallos concretos que aparecen siempre en generación de texto largo:

1. **Deriva de canon.** Un personaje tiene los ojos verdes en el capítulo 2 y grises en el 19. Sin hechos con vigencia temporal explícita no hay nada contra lo que validar.
2. **Fuga epistémica.** Un personaje actúa usando información que aún no ha recibido. Es el fallo más difícil de detectar leyendo y el más letal para el misterio y la tensión.
3. **Cabos sueltos.** Se siembra un objeto, una amenaza o una promesa y nunca se paga.
4. **Saturación de contexto.** A partir de \~40.000 palabras no cabe el texto previo en la ventana, y resumirlo de forma ingenua borra justo los detalles que hacen falta.

Queda dentro del alcance: el modelo conceptual del dominio, los atributos e invariantes de cada clase, y las políticas de contexto y calidad. Queda fuera: la arquitectura de despliegue, la elección de modelos y los prompts concretos.

El documento hermano contiene los diagramas Mermaid del mismo modelo.

## Principios de modelado

El dominio se divide en tres planos y tres capas transversales; confundirlos es la causa raíz de la mayoría de los fallos de coherencia.

| Plano / capa | Pregunta que responde | Clase pivote |
| --- | --- | --- |
| Diegético (*fabula*) | ¿Qué es verdad en el mundo y cuándo? | `EventoNarrativo` |
| Discursivo (*syuzhet*) | ¿Cómo se cuenta y en qué orden? | `Escena` |
| Producción | ¿Quién lo generó, con qué y con qué resultado? | `Borrador` |
| Especificación | ¿Qué se pidió y qué restringe? | `Brief` |
| Contexto | ¿Qué ve el agente en cada llamada? | `PaqueteDeContexto` |
| Calidad | ¿Está bien y cómo lo sabemos? | `Juicio` |

Cinco principios rigen el modelo:

1. **Separar historia de relato.** Un `EventoNarrativo` ocurre en tiempo de historia; una `Escena` lo narra en tiempo de relato. La relación entre ambos es de muchos a muchos: una escena puede narrar varios eventos, y un evento puede aparecer en varias escenas (flashback, relato de un testigo, revelación).
2. **Nada es atemporal.** Todo hecho del mundo es válido en un intervalo delimitado por eventos, no por fechas absolutas. Los atributos estáticos son el origen de la deriva de canon.
3. **El conocimiento es una relación, no un atributo.** Quién sabe qué, desde cuándo y con qué grado de certeza es información de primera clase.
4. **Las promesas narrativas son objetos.** Siembras, misterios y arcos se modelan como pares con estado, no como notas en prosa.
5. **Todo artefacto generado lleva procedencia.** Sin registrar qué contexto exacto recibió un agente, un fallo de coherencia no es depurable.

Una consecuencia práctica: el canon nunca se almacena como prosa. La prosa es la salida; el canon es la estructura de la que se deriva y contra la que se valida.

## Convenciones de notación

Cada clase se documenta con el mismo esqueleto: definición en una frase, atributos con tipo, relaciones salientes con cardinalidad, e invariantes.

- Nombres de clase en `PascalCase`, relaciones en `snake_case`.
- Cardinalidad al estilo UML: `1`, `0..1`, `1..*`, `*`.
- Los atributos marcados **(D)** son derivados: se calculan, no se escriben a mano.
- Los atributos marcados **(C)** son canónicos: solo cambian por promoción desde un borrador aceptado.
- El tiempo de historia se expresa siempre en relación a eventos (`válido_desde: EventoNarrativo`), nunca como fecha suelta, salvo en obras con calendario explícito, donde la fecha es un atributo adicional del evento.

## Plano diegético — el canon

Este plano contiene todo lo que es verdad dentro del mundo ficcional, con independencia de si ya se ha narrado.

### Entidad (abstracta)

Cualquier cosa a la que el relato pueda referirse de forma persistente.

Atributos: `id`, `nombre_canónico`, `alias[]`, `primera_aparición` (D: escena), `estatus_ontológico` (real en la diégesis / rumor / legendario / inventado por un personaje), `relevancia` (protagónico / secundario / ambiental).

El `estatus_ontológico` importa: permite que el sistema maneje información falsa dentro de la ficción sin corromper el canon.

El `nombre_canónico` de un `Personaje` cambia por petición del lector, nunca en sitio sin revisión: el cambio abre una revisión de canon con eventos `renombrar` (anterior y nuevo) y se sustituye como palabra completa en el canon, el esqueleto, los resúmenes y la prosa de su novela, con un `Borrador` nuevo por escena tocada y el anterior conservado (D-26, SPEC-013). El del destinatario no cambia por esta vía.

Subclases: `Personaje`, `Lugar`, `Objeto`, `Organización`, `Lore`.

### Personaje

Entidad con agencia, capaz de querer, saber y actuar.

Atributos: `deseo_externo` (lo que persigue), `necesidad_interna` (lo que le falta y no reconoce), `herida_de_origen`, `creencia_falsa`, `rasgos[]`, `contradicción_definitoria`, `arco` (tipo y estado), `nivel_de_agencia`, `función_dramática[]`, `idiolecto` → `PerfilDeEstilo`, `descripción_física` (C).

`creencia_falsa` no es adorno: es la palanca del arco y lo que hace que las decisiones del personaje sean predecibles para el planificador y sorprendentes para el lector.

Invariante: todo personaje protagónico tiene al menos un `Hilo` asociado y una `necesidad_interna` no vacía.

### Lugar

Entidad espacial donde pueden situarse escenas y eventos.

Atributos: `tipo`, `contiene` / `contenido_en` (jerarquía espacial), `atmósfera_sensorial` (paleta de detalles reutilizables), `accesibilidad` (quién puede entrar y bajo qué condición), `distancia_a[]`.

La `atmósfera_sensorial` resuelve un problema real: sin un banco de detalles por lugar, cada visita se describe con vocabulario distinto y el lugar deja de sentirse el mismo.

### Objeto

Entidad material con capacidad de cambiar de poseedor o de estado.

Atributos: `poseedor_actual` (D, derivado de eventos), `estado_físico`, `significado_simbólico`, `es_siembra` (booleano), `propiedades_especiales[]`.

### Organización

Entidad colectiva con intereses propios: familia, gremio, gobierno, culto, empresa.

Atributos: `miembros[]` con rol y vigencia, `objetivo`, `recursos`, `jerarquía`, `relación_con[]` otras organizaciones.

### Lore

Conocimiento del mundo que no es una cosa concreta: mitos, historia, idiomas, costumbres, sistemas mágicos o tecnológicos.

Atributos: `dominio`, `veracidad_en_la_diégesis`, `quién_lo_conoce[]`, `nivel_de_revelación_al_lector`.

### ReglaDelMundo

Restricción invariable de la física, magia, sociedad o tecnología del mundo.

Atributos: `enunciado`, `ámbito`, `coste` (qué cuesta usarla), `excepciones[]`, `revelada_en` (escena).

Invariante crítico: ningún `EventoNarrativo` puede violar una `ReglaDelMundo` activa sin invocar una excepción declarada. Esta es la comprobación que preserva la credibilidad del mundo.

### EventoNarrativo

Ocurrencia atómica y fechable en tiempo de historia que cambia el estado del mundo. Es la clase pivote del plano.

Atributos: `id`, `descripción`, `posición_en_tiempo_de_historia` (orden parcial u ordinal), `duración`, `lugar`, `participantes[]` con rol (agente / paciente / testigo / mencionado), `tipo` (acción, decisión, revelación, encuentro, pérdida, cambio de estado), `visibilidad` (público / privado / secreto), `es_narrado` (D).

Relaciones: `causa` / `posibilita` / `impide` → `EventoNarrativo` (`*`), `establece` → `Hecho` (`*`), `invalida` → `Hecho` (`*`), `narrado_por` → `Escena` (`*`).

Dos invariantes: el grafo de causalidad es acíclico, y si A causa B entonces A precede a B en tiempo de historia.

### Hecho

Proposición sobre el mundo verdadera durante un intervalo delimitado por eventos.

Atributos: `sujeto` → Entidad, `predicado`, `objeto`, `válido_desde` → EventoNarrativo, `válido_hasta` → EventoNarrativo (`0..1`; nulo = vigente), `certeza`, `establecido_en` → Escena (dónde se canoniza ante el lector), `es_público`.

Invariante: dos hechos con el mismo sujeto y predicado mutuamente excluyente no pueden tener intervalos de validez solapados. Esta única regla elimina la mayor parte de las contradicciones de continuidad.

### Predicado

Entrada del catálogo de predicados admitidos para un `Hecho`, con su exclusividad declarada.

Atributos: `nombre`, `exclusividad` (funcional / multivalor), `descripción`.

Un predicado `funcional` admite a lo sumo un valor vigente por sujeto, y por tanto dos intervalos solapados son una contradicción; uno `multivalor` no. Sin esta distinción, el invariante de intervalos solapados no es ejecutable: nadie sabe qué predicados son mutuamente excluyentes. Un `Hecho` cuyo predicado no está en el catálogo se rechaza al canonizar.

Invariante: todo `Hecho` usa un predicado presente en el catálogo. Añadir uno es un cambio de vocabulario controlado y exige un `RegistroDeDecisión`.

### EstadoDePersonaje

Valor de un atributo variable de un personaje en un intervalo: salud, posición, lealtad, estado emocional, recursos, reputación.

Atributos: `personaje`, `dimensión`, `valor`, `válido_desde`, `válido_hasta`, `causado_por` → EventoNarrativo.

Es una especialización de `Hecho` con dimensiones enumeradas, para poder consultar trayectorias emocionales y dibujar la curva del arco.

### EstadoDeConocimiento

Qué sabe un personaje sobre un hecho, desde cuándo y con qué exactitud. La clase que más fallos previene y que casi ningún sistema incluye.

Atributos: `conocedor` → Personaje, `hecho` → Hecho, `estatus` (ignora / sospecha / cree\_falsamente / sabe / sabe\_y\_oculta), `adquirido_en` → EventoNarrativo, `fuente` (testigo directo / le fue contado / deducción / documento), `fiabilidad_de_la_fuente`, `sabe_que_X_sabe` → recursivo (`*`).

Invariante: un personaje no puede actuar en un evento apoyándose en un hecho cuyo `EstadoDeConocimiento` sea `ignora` en ese punto de la línea temporal.

El anidamiento recursivo (`sabe_que_X_sabe`) es lo que permite construir engaño, ironía dramática y suspense de forma deliberada en lugar de accidental.

### Relación

Vínculo entre dos entidades, con vigencia y valencia.

Atributos: `origen`, `destino`, `tipo` (parentesco, alianza, rivalidad, deuda, amor, jerarquía), `valencia` (−5..+5), `simetría`, `válido_desde`, `válido_hasta`, `conocida_por[]`.

La valencia con vigencia temporal permite graficar la evolución de una relación y detectar cambios sin escena que los justifique.

### LíneaTemporal

Ordenación completa de eventos en tiempo de historia, incluidos los anteriores al inicio del relato.

Atributos: `eventos_ordenados[]`, `granularidad`, `calendario` (opcional), `ramas[]` (para realidades alternativas o viajes temporales).

Invariante: todo evento narrado tiene posición asignada en al menos una línea temporal.

## Plano discursivo — el relato

Este plano describe cómo se selecciona, ordena y verbaliza el material diegético. La `Escena` es su unidad atómica y la unidad de trabajo de los agentes.

### Jerarquía contenedora

`Serie` → `Volumen` → `Parte` / `Acto` → `Capítulo` → `Escena` → `Beat` → `Párrafo`

Cada nivel tiene `presupuesto_de_palabras` (objetivo y tolerancia), `orden` y `resumen` (D). El presupuesto es lo que impide que el acto tercero se coma el 60% del libro.

El `Volumen` lleva además `eliminada_en`, vacío mientras la novela existe (D-23). Una novela eliminada se **retira**, no se borra: sus capítulos, escenas, borradores, canon, versiones y aprobaciones se conservan, pero no se lista ni se sirve por ninguna ruta. No se elimina una novela con aprobación vigente ni con la escritura en curso.

El `Capítulo` tiene además `título`, que lo declara el reparto y no la escritura. Sin él, la lectura no tiene más remedio que llamar «Capítulo 3» al capítulo 3, y un índice numerado no dice de qué va nada: es la diferencia entre poder elegir por dónde seguir leyendo y tener que abrirlos todos.

### Escena

Unidad continua de narración en un lugar, un tiempo y un punto de vista, que produce un cambio de valor.

| Atributo | Para qué sirve |
| --- | --- |
| `pov` → Personaje | Filtra qué puede narrarse y qué se sabe |
| `focalización` | Interna, externa, omnisciente |
| `distancia_narrativa` | De panorámica a pensamiento íntimo |
| `tiempo_verbal`, `persona` | Consistencia gramatical verificable |
| `escenario` → Lugar | Continuidad sensorial |
| `momento_en_historia` | Ancla en la línea temporal |
| `objetivo`, `conflicto`, `resultado` | Estructura interna mínima |
| `valor_de_entrada` → `valor_de_salida` | El cambio que justifica la escena |
| `carga_emocional_entrada/salida` | Curva emocional y variación de ritmo |
| `función_en_trama` | Detonante, giro, revelación, clímax, secuela |
| `tipo` | Escena de acción vs. secuela reflexiva |
| `presupuesto_de_palabras` | Control de ritmo |
| `renderiza` → EventoNarrativo (`1..*`) | El puente con el plano diegético |
| `hilos_activos[]` → Hilo | Qué subtramas avanza |

Invariante: `valor_de_entrada ≠ valor_de_salida`. Una escena en la que nada cambia es una escena que sobra, y esto es comprobable automáticamente.

Segundo invariante: toda escena narra al menos un evento. Si no, es exposición disfrazada.

### Beat

Subdivisión de una escena: un intercambio, un gesto, un giro menor. Atributos: `tipo` (acción / reacción / diálogo / pensamiento / descripción), `duración_relativa`, `intención`.

Sirve para dos cosas: dar al redactor una estructura antes de escribir prosa, y medir la proporción diálogo/narración/descripción sin analizar el texto a posteriori.

### Narración

Configuración de voz del relato, global o por sección.

Atributos: `persona` (1ª, 2ª, 3ª), `tipo_de_narrador`, `fiabilidad`, `acceso_a_conciencias[]`, `temporalidad` (simultánea, retrospectiva), `ironía_permitida`.

Modelarla explícitamente permite validar que una escena en tercera limitada no filtre pensamientos de otro personaje: el error de POV más frecuente.

### Hilo (subtrama)

Secuencia de escenas que desarrolla una línea de tensión hasta su resolución.

Atributos: `tipo` (principal, romántica, de misterio, temática, de personaje), `protagonista`, `pregunta_dramática`, `curva_de_tensión[]` (tensión objetivo por escena), `estado`, `escenas[]` ordenadas, `resolución` → Escena.

Invariantes: ningún hilo puede estar inactivo más de N escenas consecutivas (parámetro por tipo de hilo), y todo hilo abierto tiene resolución o abandono declarado antes del final.

### PlantillaEstructural

Esquema de referencia con beats esperados y su posición relativa: tres actos, viaje del héroe, *Save the Cat*, kishōtenketsu, estructura en siete puntos.

Atributos: `nombre`, `beats_esperados[]` con `posición_relativa` (0.0–1.0) y `tolerancia`, `género_afín[]`, `obligatoriedad`.

Se usa como referencia de conformidad, no como molde: el sistema informa de desviaciones, y la decisión de aceptarlas se registra en un `RegistroDeDecisión`.

### Motivo y Tema

`Tema` es la pregunta moral o conceptual que la obra explora; `Motivo` es su vehículo concreto y repetible (una imagen, un objeto, una frase, un color).

Atributos de `Motivo`: `manifestación`, `apariciones[]` → Escena, `frecuencia_objetivo`, `evolución_semántica`, `vinculado_a` → Tema.

La `frecuencia_objetivo` tiene un uso doble: garantiza que el motivo aparezca lo suficiente para leerse como intencional, y detecta cuándo se ha vuelto insistente.

### PerfilDeEstilo

Contrato de voz aplicable a la obra entera o a un personaje.

Atributos: `longitud_media_de_frase` y varianza, `registro`, `densidad_léxica`, `uso_de_metáfora`, `proporción_diálogo`, `tics_verbales[]`, `vocabulario_prohibido[]`, `vocabulario_característico[]`, `puntuación_preferida`, `ejemplos_de_referencia[]`.

El `vocabulario_prohibido` es, en la práctica, la defensa más eficaz contra el vocabulario delator de los modelos de lenguaje.

### ParSiembraPago

Promesa narrativa con su cumplimiento: el rifle de Chéjov como objeto de primera clase.

Atributos: `descripción_de_la_promesa`, `tipo` (objeto, habilidad, información, amenaza, relación, pregunta), `escena_de_siembra`, `escena_de_pago` (`0..1`), `estado` (abierto / resuelto / subvertido / abandonado), `sutileza` (1–5), `distancia_máxima_aceptable`.

Invariante: al final de la obra, ningún par queda en estado `abierto`. Esto convierte los cabos sueltos en una lista de tareas verificable en lugar de una impresión de lectura.

## Plano de producción agéntica

Este plano modela el trabajo: quién hizo qué, con qué entrada y con qué resultado. Es lo que hace el sistema depurable.

### RolDeAgente

Función especializada con responsabilidad, permisos de escritura y herramientas propias.

| Rol | Escribe en | Responsabilidad |
| --- | --- | --- |
| Orquestador | Tarea, Plan, Puerta | Descompone y asigna; no escribe prosa |
| Arquitecto | Hilo, Escena (esqueleto), ParSiembraPago | Estructura global y outline |
| Worldbuilder | Entidad, ReglaDelMundo, Lore | Consistencia del mundo |
| Guardián de Continuidad | Defecto | Solo lectura sobre el canon; solo reporta |
| Redactor | Borrador | Prosa de escena |
| Editor de línea | Revisión | Ritmo, claridad, voz frase a frase |
| Editor de desarrollo | Crítica | Estructura, motivación, arco |
| Crítico / Juez | Juicio | Puntuación contra rúbrica |
| Investigador | Lore, Hecho | Verosimilitud factual |
| Entrenador de voz | PerfilDeEstilo | Idiolecto y consistencia de voz |
| Canonizador | Hecho, EstadoDePersonaje, EstadoDeConocimiento | Promueve al canon los hechos de un borrador aceptado; único rol con escritura en el canon |

El principio de diseño más importante aquí: **el Guardián de Continuidad no escribe prosa y el Redactor no escribe canon**. Separar quien genera de quien valida evita que el mismo agente racionalice sus propias incoherencias.

### Tarea

Unidad de trabajo asignable. Atributos: `tipo`, `objetivo`, `rol_asignado`, `entradas[]`, `salida_esperada`, `criterios_de_aceptación[]`, `estado`, `intentos`, `depende_de[]`, `presupuesto` (tokens, coste, tiempo).

### Plan

Árbol de tareas con dependencias que produce un artefacto de nivel superior: un capítulo, un acto, el outline completo.

### Borrador

Versión concreta de la prosa de una escena o capítulo.

Atributos: `escena`, `versión`, `texto`, `estado` (propuesto / en\_revisión / aceptado / rechazado / obsoleto), `recuento_de_palabras`, `procedencia` → Procedencia, `hechos_nuevos_detectados[]` (candidatos a canonización).

Invariante: solo un borrador por escena puede estar en estado `aceptado`. El canon se deriva de los aceptados.

### Revisión y Diff

`Revisión` es un cambio propuesto sobre un borrador, con `motivo` y `crítica_que_la_origina`. `Diff` registra el cambio a nivel de span para poder auditar qué se tocó y por qué.

Retener el diff permite algo valioso: medir si las revisiones mejoran las puntuaciones o solo mueven el texto.

### Crítica

Observación evaluativa sobre un artefacto, emitida por un agente.

Atributos: `objetivo` (borrador y span), `dimensión`, `severidad`, `diagnóstico`, `sugerencia`, `estado` (abierta / aceptada / rechazada / resuelta), `emitida_por`.

El estado `rechazada` con justificación es necesario: sin él, el sistema entra en bucles de revisión perpetua atendiendo críticas cuestionables.

### Puerta (Gate)

Condición que debe cumplirse para avanzar de fase. Atributos: `fase`, `comprobaciones[]`, `política` (bloqueante / advertencia), `resultado`, `excepciones_autorizadas[]`.

Qué puertas existen, cuándo se evalúan y con qué política —bloqueante o advertencia— está en `architecture.md` §7.3. Aquí solo está la clase; los invariantes que cada puerta cobra están en el apartado «Invariantes y reglas de validación».

### AprobacionDeVolumen

Firma de una persona sobre una versión publicada de la novela. Es la evidencia `humano` de *promesa al lector* en la puerta *Volumen cerrado* (D-22).

Atributos: `volumen` → Volumen, `versión` → versión publicada, `aprobada_en`, `retirada_en` (vacío mientras está vigente).

Invariantes: una aprobación nunca se borra —reabrir la novela la retira con fecha—, y un volumen tiene como mucho una vigente. Mientras hay una vigente, la novela no se reescribe, no admite cambios del lector y no se retitula. Aprobar no cambia el estado de ningún `Borrador`.

### RegistroDeDecisión

Decisión creativa tomada, con su alternativa descartada y su motivo.

Atributos: `decisión`, `alternativas_consideradas[]`, `motivo`, `ámbito_afectado`, `reversible`, `tomada_en`.

En obras largas la deriva rara vez viene de mala prosa: viene de decisiones olvidadas y luego contradichas sin darse cuenta.

### Procedencia

Registro de cómo se generó un artefacto: `agente`, `modelo`, `versión_de_prompt`, `paquete_de_contexto` → PaqueteDeContexto, `parámetros_de_muestreo`, `coste`, `latencia`, `tokens_entrada`, `tokens_salida`, `timestamp`.

Los tokens son los que devolvió el cliente del modelo; vacíos cuando no hubo respuesta y en las procedencias anteriores a SPEC-012. La suma de las procedencias de una novela es su gasto, y es lo que enseña la pestaña «Gastos»; Langfuse recibe cada una como traza con el mismo id (D-24).

El enlace al `PaqueteDeContexto` es el atributo que convierte un fallo de coherencia en algo reproducible: permite ver exactamente qué sabía el agente cuando falló.

## Capa de especificación

Es el contrato del encargo: lo que la capa de calidad usa como referencia para medir.

### Brief

Atributos: `género`, `subgénero`, `obras_comparables[]`, `audiencia`, `tono`, `extensión_objetivo`, `pov_objetivo`, `premisa`, `logline`, `promesa_al_lector`, `tabúes[]`, `idioma`, `mercado`.

La `promesa_al_lector` merece atención especial: es el compromiso implícito del género (un misterio se resuelve, un romance culmina) y su incumplimiento es el fallo de calidad más grave y menos detectable frase a frase.

### Destinatario

Para quien se escribe la novela. Es lo que separa un generador de novelas de un regalo, y
lo que hace **verificable** la personalización: sin nombre no hay nada que comparar contra
la story bible, y sin elemento obligatorio no hay nada que buscar en los capítulos.

Atributos: `id`, `nombre`, `edad`, `rasgos[]`, `elementos[]` → ElementoPersonalizado,
`dedicatoria`.

Invariantes: el nombre no está vacío —es lo que el validador de nombres compara carácter a
carácter—, la edad es un número de años positivo —es una de las dos patas de la
contradicción que el entrevistador detecta— y todo destinatario aporta al menos un
`ElementoPersonalizado` obligatorio.

### ElementoPersonalizado

Algo del destinatario que la novela tiene que llevar dentro.

Atributos: `id`, `tipo` (`recuerdo` / `rasgo` / `vínculo`), `contenido`, `obligatorio`.

`obligatorio` no es un adorno: separa lo que un validador exige encontrar en algún capítulo
de lo que solo enriquece si cabe. Marcarlo todo como obligatorio convierte ese validador en
un bloqueo permanente; no marcar nada lo convierte en decorativo.

### PersonajeDeclarado

Alguien que quien encarga quiere ver en la novela, dicho antes de escribirla (SPEC-011, D-25).

Atributos: `nombre`, `papel` (`relevancia`: protagónico / secundario / ambiental), `relación` con el destinatario, `descripción`, `es_destinatario`.

Vive en la capa de especificación, no en el canon: declarar es encargar. El destinatario se declara siempre, protagonista y con la relación «a quien va dedicada». Como mucho doce por encargo, con nombres únicos sin distinguir mayúsculas ni acentos. La apertura tiene que proponerlos todos con su nombre y su papel, y cada uno tiene que salir en la historia —participar en un evento o ser el POV de una escena—; si no, el plan se rechaza entero, como con los recuerdos obligatorios. Se editan hasta que empieza la escritura; después, cambiarlos es un cambio del lector.

### EventoDeCronologia

Proyección del canon —evento, momento, lugar y quién estaba— que alimenta al validador
formal. **No es una clase persistida**: se deriva de `EventoNarrativo`, y una cronología
declarada aparte diverge del canon en cuanto alguien edita un evento, con lo que la
verificación formal pasaría a comprobar una historia distinta de la que se lee (rd-d19).

Un `EventoNarrativo` gana para esto un atributo `momento`, que lo **fecha** en tiempo de
historia; `posición_en_tiempo_de_historia` solo lo **ordena**, y con un orden no se puede
decir qué edad tenía nadie. Un `Personaje` gana `año_de_nacimiento` por la misma razón.

### Restricción

Condición que limita las salidas válidas.

Atributos: `enunciado`, `dureza` (dura = bloquea publicación / blanda = penaliza puntuación), `ámbito`, `verificable_por` (programa / juez / humano), `origen` (usuario / género / legal / editorial).

Distinguir dura de blanda es lo que permite que el orquestador decida si reintenta o acepta con penalización, en lugar de reintentar indefinidamente.

### ContratoDeEstilo

Instancia de `PerfilDeEstilo` elevada a obligación contractual, con umbrales numéricos y márgenes de tolerancia.

### PolíticaDeContenido

Límites sobre materia sensible: violencia, sexo, lenguaje, representación de grupos, temas prohibidos.

Atributos: `categoría`, `nivel_permitido`, `tratamiento_requerido`, `aplicable_a` (ámbito).

## Capa de contexto

La gestión de contexto se modela como entidades del dominio, no como lógica suelta en el código. Es la decisión que más diferencia hay entre un prototipo y un sistema que aguanta 120.000 palabras.

### UnidadDeContexto

Fragmento de información recuperable con un nivel de granularidad declarado.

Atributos: `nivel`, `contenido`, `deriva_de[]` (trazabilidad hacia arriba), `vigencia` (rev del canon con la que se generó), `tokens`, `embedding`.

Los niveles forman una pirámide de resumen multirresolución:

| Nivel | Extensión típica | Uso |
| --- | --- | --- |
| Premisa de serie | 1–2 frases | Siempre presente |
| Sinopsis de volumen | 200–400 palabras | Siempre presente |
| Resumen de parte | 100–200 palabras | Partes distintas de la actual |
| Resumen de capítulo | 50–100 palabras | Capítulos anteriores |
| Resumen de escena | 1–3 frases | Escenas de la parte actual |
| Prosa literal | Completa | Escena inmediatamente anterior |

La regla operativa: cuanto más cerca está el material del punto de escritura, mayor resolución recibe. Solo la escena anterior entra literal, y entra porque la continuidad de tono y de última frase no sobrevive al resumen.

### Canon (Story Bible)

Almacén estructurado y normalizado de hechos, entidades, eventos y reglas: la fuente única de verdad.

Atributos: `revisión`, `hechos[]`, `entidades[]`, `eventos[]`, `reglas[]`, `última_canonización`.

No contiene prosa. Esta restricción es deliberada: en cuanto el canon admite prosa, deja de ser consultable y vuelve a ser un documento que alguien debe leer entero.

### PaqueteDeContexto

Objeto de primera clase que registra exactamente qué se inyectó a un agente en una llamada.

Atributos: `tarea`, `unidades[]` con orden y tokens, `presupuesto_de_tokens`, `política_aplicada`, `hash`.

Composición típica para redactar una escena:

1. **Estático**: premisa, contrato de estilo, plantilla estructural, políticas de contenido.
2. **Estado del mundo**: hechos vigentes de las entidades presentes en la escena, filtrados por el momento en la línea temporal.
3. **Continuidad inmediata**: prosa literal de la escena anterior, últimos párrafos completos.
4. **Arco**: resumen del capítulo y del hilo activo, con posición en su curva de tensión.
5. **Voz**: `PerfilDeEstilo` global más el idiolecto de los personajes con diálogo.
6. **Epistémico**: estado de conocimiento del personaje POV — lo que puede y no puede saber.
7. **Promesas**: siembras abiertas con distancia al límite y motivos pendientes de aparición.
8. **Instrucción**: objetivo, conflicto, resultado y presupuesto de palabras de la escena.

Guardar el paquete con su `hash` cuesta poco y resuelve la pregunta que siempre aparece al depurar: ¿el agente se equivocó, o nunca recibió el dato?

### AlcanceDeRelevancia

Filtro que decide qué entra en un paquete. Tres dimensiones combinadas:

- **Temporal**: solo hechos vigentes en el momento de historia de la escena. Un hecho invalidado en el capítulo 8 no debe aparecer al escribir el 12.
- **Epistémico**: en POV limitado, solo lo que el narrador puede conocer. Este filtro es lo que impide la fuga de información.
- **Estructural**: hilos activos, entidades presentes o mencionadas, motivos del acto en curso.

### Políticas

La mecánica de la **canonización** y de la **invalidación en cascada** es arquitectura, no dominio, y está en `architecture.md` §8 y §4.6. Lo que este documento fija es la regla que ninguna implementación puede saltarse: un hecho que contradice el canon genera un `Defecto` y nunca lo sobrescribe.

## Capa de calidad

Cada dimensión de calidad se clasifica por **cómo se verifica**, porque eso determina si se puede poner en una puerta bloqueante o solo informar.

### Clases

- **DimensiónDeCalidad**: `nombre`, `definición`, `modo_de_verificación`, `escala`, `peso`, `nivel_aplicable` (frase / escena / capítulo / obra).
- **Rúbrica**: conjunto de dimensiones con descriptores por nivel y ejemplos ancla. Los ejemplos ancla son lo que hace reproducible a un juez LLM.
- **Juicio**: `objetivo`, `dimensión`, `puntuación`, `justificación`, `juez`, `confianza`, `rúbrica_usada`, `timestamp`.
- **Defecto**: `tipo`, `severidad`, `span`, `evidencia`, `regla_violada`, `estado`, `detectado_por`.
- **UmbralDeAceptación**: `dimensión`, `mínimo`, `política_si_falla` (reescribir / marcar / escalar a humano), `máximo_de_reintentos`.

### Dimensiones verificables por programa

Su resultado es determinista. El reparto de autoridad —cuál de las tres vías puede bloquear una puerta y cuál solo penaliza— está en `architecture.md` §7.1, y el reparto dimensión a dimensión en `verification.md` §4.

| Comprobación | Regla |
| --- | --- |
| Violación de línea temporal | Evento usado antes de su causa |
| Contradicción de hechos | Intervalos de validez solapados con predicados excluyentes |
| Fuga epistémica | Personaje actúa sobre un hecho que ignora |
| Disciplina de POV | Acceso a conciencias no autorizado por `Narración` |
| Consistencia de tiempo y persona | Deriva gramatical entre escenas |
| Repetición de n-gramas | Trigramas y tetragramas repetidos entre capítulos |
| Diversidad léxica | Type-token ratio y vocabulario delator |
| Siembras sin pagar | Pares en estado `abierto` pasado su límite |
| Conformidad estructural | Desviación de beats respecto a la plantilla |
| Presupuesto de palabras | Desvío por acto y capítulo |
| Deriva de nombres | Alias no declarados, ortografía inconsistente |

La repetición de n-gramas merece prioridad: es el fallo más característico de los modelos de lenguaje en texto largo, invisible dentro de una escena y muy visible al leer el libro seguido. Un agente que escribe la escena 40 sin ver las 39 anteriores repetirá sus propias imágenes favoritas.

### Dimensiones evaluadas por juez LLM

Naturalidad del diálogo, densidad de cliché, consistencia de motivación, coherencia temática, impacto emocional, tensión y curiosidad, especificidad sensorial, exposición forzada (*infodumping*), variedad sintáctica percibida.

Dos reglas para que sirvan: el juez no puede ser el mismo agente que escribió, y la puntuación va siempre acompañada de `confianza` para poder descartar juicios inestables.

### Dimensiones humanas

Valor literario, adecuación al mercado, originalidad, satisfacción de la promesa al lector. No se automatizan; se muestrean.

### Invariantes tipo test

El modelo permite escribir aserciones ejecutables sobre la obra, igual que pruebas sobre código:

- Ningún personaje conoce el hecho `F` antes de la escena `S`.
- Todo `ParSiembraPago` está resuelto o subvertido al final del volumen.
- Ninguna imagen del catálogo de motivos aparece más de `N` veces.
- Todo hilo principal tiene al menos una escena cada `M` capítulos.
- Ningún capítulo excede su presupuesto en más del `X%`.

## Catálogo de relaciones

Estas son las aristas que cruzan planos y sostienen las validaciones. Las intra-plano quedan descritas en cada clase.

| Relación | Dominio | Rango | Card. | Para qué |
| --- | --- | --- | --- | --- |
| `renderiza` | Escena | EventoNarrativo | `1..*` | Puente historia ↔ relato |
| `establece` | EventoNarrativo | Hecho | `*` | Origen del canon |
| `invalida` | EventoNarrativo | Hecho | `*` | Cierre de vigencia |
| `establecido_en` | Hecho | Escena | `0..1` | Dónde lo sabe el lector |
| `conoce` | Personaje | Hecho | `*` | Vía EstadoDeConocimiento |
| `participa_en` | Entidad | EventoNarrativo | `*` | Con rol |
| `causa` | EventoNarrativo | EventoNarrativo | `*` | Grafo causal acíclico |
| `avanza` | Escena | Hilo | `1..*` | Actividad de subtramas |
| `siembra` / `paga` | Escena | ParSiembraPago | `*` | Promesas |
| `manifiesta` | Escena | Motivo | `*` | Tejido temático |
| `conforma_a` | Escena | Beat de plantilla | `0..1` | Conformidad estructural |
| `narrada_por` | Escena | Narración | `1` | Reglas de POV |
| `habla_con_voz` | Personaje | PerfilDeEstilo | `0..1` | Idiolecto |
| `borrador_de` | Borrador | Escena | `1` | Producción |
| `evalúa` | Juicio | Borrador | `1` | Calidad |
| `reporta` | Defecto | Borrador o Canon | `1` | Trazabilidad del fallo |
| `contextualizado_por` | Procedencia | PaqueteDeContexto | `1` | Depuración |
| `deriva_de` | UnidadDeContexto | UnidadDeContexto | `*` | Cascada de resúmenes |
| `restringe` | Restricción | cualquier clase | `*` | Contrato |

La arista `deriva_de` es la que hace posible la invalidación en cascada; sin ella, los resúmenes obsoletos no son detectables.

## Invariantes y reglas de validación

Las reglas se agrupan por severidad, que determina qué hace el orquestador al detectarlas.

### Bloqueantes (impiden aceptar el borrador)

1. Grafo causal sin ciclos.
2. Si A causa B, A precede a B en tiempo de historia.
3. Sin intervalos de validez solapados para predicados mutuamente excluyentes.
4. Ningún personaje actúa sobre un hecho que ignora en ese momento.
5. Ninguna escena filtra conciencias que su `Narración` no autoriza.
6. Ningún evento viola una `ReglaDelMundo` activa sin excepción declarada.
7. Toda escena narra al menos un evento.
8. Un solo borrador `aceptado` por escena.

### De cierre (se comprueban en la puerta de fin de volumen)

1. Ningún `ParSiembraPago` en estado `abierto`.
2. Todo hilo con resolución o abandono declarado.
3. Toda pregunta dramática de hilo principal respondida.
4. Arco de cada protagónico con estado terminal.
5. Promesa al lector del `Brief` satisfecha (juicio humano, no programa: la evidencia es la `AprobacionDeVolumen`).

### De advertencia (penalizan, no bloquean)

1. Desviación de beats respecto a la plantilla por encima de la tolerancia.
2. Desvío de presupuesto de palabras superior al margen.
3. Hilo inactivo más de N escenas.
4. Repetición de n-gramas por encima del umbral.
5. Motivo por debajo o por encima de su frecuencia objetivo.
6. Métricas de estilo fuera de los márgenes del `ContratoDeEstilo`.
7. Valencia de relación cambiada sin evento que lo justifique.
8. Curva de tensión plana en tres o más escenas consecutivas.

Una nota de diseño: la regla 4 de las bloqueantes (fuga epistémica) requiere que el planificador declare qué hechos usa cada evento. Es un coste real de anotación, y es lo que separa un sistema que valida coherencia de uno que solo espera que salga bien.

## Vocabularios controlados

Cerrar estos conjuntos es lo que permite consultar y validar; si son texto libre, ninguna regla es ejecutable.

| Enumeración | Valores |
| --- | --- |
| `estatus_epistémico` | ignora · sospecha · cree\_falsamente · sabe · sabe\_y\_oculta |
| `tipo_de_evento` | acción · decisión · revelación · encuentro · pérdida · cambio\_de\_estado |
| `visibilidad_de_evento` | público · privado · secreto |
| `rol_en_evento` | agente · paciente · testigo · mencionado |
| `focalización` | interna · externa · omnisciente · variable |
| `distancia_narrativa` | panorámica · escénica · íntima · corriente\_de\_conciencia |
| `función_en_trama` | detonante · complicación · giro · revelación · crisis · clímax · secuela · resolución |
| `tipo_de_escena` | acción · secuela · diálogo · transición · interludio |
| `tipo_de_hilo` | principal · secundario · romántico · misterio · temático · de\_personaje |
| `tipo_de_arco` | positivo · negativo · plano · corruptor · redentor |
| `tipo_de_siembra` | objeto · habilidad · información · amenaza · relación · pregunta |
| `estado_de_siembra` | abierto · resuelto · subvertido · abandonado |
| `estado_de_borrador` | propuesto · en\_revisión · aceptado · rechazado · obsoleto |
| `exclusividad_de_predicado` | funcional · multivalor |
| `estado_de_tarea` | pendiente · lista · en\_curso · en\_verificación · aceptada · rechazada · escalada · fallida · bloqueada · cancelada |
| `severidad` | crítica · alta · media · baja · informativa |
| `modo_de_verificación` | programa · juez\_llm · humano |
| `dureza_de_restricción` | dura · blanda |
| `nivel_de_contexto` | serie · volumen · parte · capítulo · escena · literal |
| `dimensión_de_estado` | salud · ubicación · lealtad · emoción · recursos · reputación · conocimiento |

Un consejo de gobierno del modelo: añadir un valor a estas enumeraciones debería requerir un `RegistroDeDecisión`. Las enumeraciones que crecen sin control dejan de ser vocabularios y vuelven a ser texto libre.

## Notas de implementación

Están en `architecture.md`, que es donde vive todo lo que cambiaría al cambiar de stack: el grafo sobre SQLite y el porqué de un property graph tipado en §3.1, el reparto entre grafo y vectorial en §3.1, la extracción de hechos en §8, el versionado y la reproducibilidad en §9, y el control de coste de los filtros de `AlcanceDeRelevancia` en §4.1.

## Núcleo mínimo viable

Las 12 clases con las que se arranca, el motivo por el que cada una está en el núcleo y el orden de adopción de las cinco fases están en `architecture.md` §13. El diagrama entidad-relación de ese núcleo es el 8 de `domain-knowledge.md`.
