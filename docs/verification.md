# Metodologías de Verificación

Hoja de referencia de las metodologías de verificación aplicables a código generado por
modelos y a sistemas agénticos. Cada entrada lleva una definición en lenguaje llano y un
enlace que explica la metodología en sí, no el producto de ningún proveedor.

**Cómo se usa.** Las dos primeras tablas responden a preguntas distintas y no son
intercambiables: la de nivel de artefacto pregunta si el código es correcto; la de nivel
de proceso pregunta si el agente se comporta de forma fiable. Un sistema que solo cubre
la primera produce código correcto invocado de forma insensata; uno que solo cubre la
segunda vigila bien un artefacto que nadie ha comprobado.

Las secciones 1 a 3 son neutrales y no prescriben nada. El apartado 4 es la aplicación a
este repositorio: qué metodología cubre cada invariante, cuál puede fallar una `Puerta` y
qué requisitos siguen sin ser comprobables.

---

## 1. Verificación a nivel de artefacto

¿El código es correcto?

| Metodología | Definición | Enlace de referencia |
| --- | --- | --- |
| Type checking | Comprobación automática de que los valores se usan de forma consistente con lo que las operaciones esperan de ellos | [Type system — Wikipedia](https://en.wikipedia.org/wiki/Type_system) |
| Static analysis / SAST | Análisis del código fuente sin ejecutarlo, contrastándolo con patrones conocidos como defectuosos | [Static program analysis — Wikipedia](https://en.wikipedia.org/wiki/Static_program_analysis) |
| Symbolic execution | Ejecución del código con entradas simbólicas para derivar las condiciones exactas de fallo mediante un solucionador SMT | [Symbolic execution — Wikipedia](https://en.wikipedia.org/wiki/Symbolic_execution) |
| Formal verification / theorem proving | Demostración matemática de que el código satisface una especificación para todas las entradas posibles | [Formal verification — Wikipedia](https://en.wikipedia.org/wiki/Formal_verification) |
| Unit / integration testing | Comprobación del comportamiento contra entradas de ejemplo concretas y sus salidas esperadas | [Unit testing — Wikipedia](https://en.wikipedia.org/wiki/Unit_testing) |
| Property-based testing | Especificación de una propiedad general y generación de muchas entradas para buscar una violación | [QuickCheck: A Lightweight Tool for Random Testing of Haskell Programs — Claessen & Hughes, 2000](https://dl.acm.org/doi/10.1145/351240.351266) |
| Mutation testing | Introducción deliberada de fallos pequeños para comprobar si la suite de pruebas los detecta | [Mutation testing — Wikipedia](https://en.wikipedia.org/wiki/Mutation_testing) |
| Contract testing | Verificación de que la interfaz entre dos servicios se mantiene consistente, con independencia de sus internos | [Contract Test — Martin Fowler](https://martinfowler.com/bliki/ContractTest.html) |

---

## 2. Verificación a nivel de proceso

¿El agente se comporta de forma fiable?

| Metodología | Definición | Enlace de referencia |
| --- | --- | --- |
| Runtime observability / tracing | Instrumentación del agente para que su trayectoria sea visible y consultable a posteriori | [Observability primer — OpenTelemetry](https://opentelemetry.io/docs/concepts/observability-primer/) |
| Evals | Pruebas estructuradas del comportamiento del agente contra un conjunto de datos y un método de puntuación | [Holistic Evaluation of Language Models (HELM) — Liang et al., 2022](https://arxiv.org/abs/2211.09110) |
| Sandboxed execution | Ejecución del código del agente en un entorno aislado, de modo que las acciones dañinas fallen de forma segura | [Sandbox (computer security) — Wikipedia](https://en.wikipedia.org/wiki/Sandbox_(computer_security)) |
| Guardrails | Políticas y filtros que acotan qué acciones puede llegar a producir un agente | [AI Risk Management Framework — NIST](https://www.nist.gov/itl/ai-risk-management-framework) |
| Human-in-the-loop review | Una persona aprueba, rechaza o edita las acciones del agente de mayor consecuencia | [Human-in-the-loop — Wikipedia](https://en.wikipedia.org/wiki/Human-in-the-loop) |
| Multi-agent verification | Patrones de crítico, debate, autoconsistencia, reflexión o conjunto que comprueban la salida del modelo | [AI Safety via Debate — Irving, Christiano, Amodei, 2018](https://arxiv.org/abs/1805.00899) |
| CI/CD integration | Encauzar los cambios generados por agentes por la misma tubería que el código escrito por humanos | [Continuous integration — Wikipedia](https://en.wikipedia.org/wiki/Continuous_integration) |
| Progressive rollout | Desplegar un cambio a un porcentaje pequeño del tráfico, tras un flag, antes de la publicación completa | [Feature toggle — Wikipedia](https://en.wikipedia.org/wiki/Feature_toggle) |
| Red-teaming / adversarial testing | Sondeo deliberado en busca de fallos bajo un modelo de amenaza adversario | [OWASP Top 10 for LLM Applications](https://owasp.org/www-project-top-10-for-large-language-model-applications/) |
| Model checking | Exploración exhaustiva de los estados y transiciones alcanzables del agente para verificar invariantes | [Model checking — Wikipedia](https://en.wikipedia.org/wiki/Model_checking) |

---

## 3. Marco de clasificación

| Método | Definición | Enlace de referencia |
| --- | --- | --- |
| T / A / I / D / U (Trust Spec) | Clasificación de cada requisito como Test, Analysis, Inspection, Demonstration o Unverifiable | [Verification and validation — Wikipedia](https://en.wikipedia.org/wiki/Verification_and_validation) |

El valor del esquema está en la última categoría. Marcar un requisito como
*Unverifiable* obliga a decidir explícitamente qué se hace con él — reformularlo hasta
que sea comprobable, o aceptarlo como riesgo asumido — en lugar de dejarlo flotando como
si estuviera cubierto.

---

## 4. Aplicación a este sistema

Las tablas anteriores son neutrales. Esta las ancla en los artefactos reales del
repositorio, con una columna de autoridad: solo lo determinista puede fallar una `Puerta`;
un juez basado en modelo penaliza, porque su puntuación varía entre llamadas sobre el
mismo texto y una puerta inestable produce bucles caros.

### 4.1 Nivel de artefacto

| Elemento | Metodología | Clase | Autoridad |
| --- | --- | --- | --- |
| Frontera de `src/domain/` (sin FastAPI, sin Pydantic, sin red) | Static analysis sobre el grafo de importaciones | A | Bloqueante |
| Tipos de las clases de la ontología | Type checking | A | Bloqueante |
| Los 8 invariantes de la puerta *Escena limpia* | Unit / integration testing en `src/quality/` | T | Bloqueante |
| Intervalos de validez de `Hecho` (`valido_desde` / `valido_hasta`) | Property-based testing sobre pares de eventos generados | T | Bloqueante |
| Ausencia de ciclos en el grafo causal de `EventoNarrativo` | Análisis del cierre transitivo (CTE recursiva) | A | Bloqueante |
| Cierre de `deriva_de`: ninguna `UnidadDeContexto` viva deriva de una fuente obsoleta | Property-based testing sobre cascadas de invalidación | T | Bloqueante |
| Presupuesto del `PaqueteDeContexto` (≤ presupuesto, y constante entre el capítulo 3 y el 40) | Property-based testing sobre longitud de libro | T | Bloqueante |
| Frontera API ↔ React (esquemas Pydantic, eventos SSE) | Contract testing | T | Bloqueante |
| Migraciones de SQLite hacia delante | Integration testing contra un canon real | T | Bloqueante |
| ¿La suite de invariantes detecta algo? | Mutation testing periódico sobre `src/quality/` | T | Advertencia |

La última fila es la que sostiene a las demás. «Un invariante sin test no existe» garantiza
que el test está escrito, no que discrimine: sin mutación, una suite que pasa siempre es
indistinguible de una suite que comprueba de verdad.

### 4.2 Nivel de proceso

| Elemento | Metodología | Clase | Autoridad |
| --- | --- | --- | --- |
| Reproducibilidad de cada generación (`Procedencia`, hash del paquete, versión de prompt) | Runtime observability / tracing | D | Informativa |
| Calidad narrativa del `Borrador` frente a las rúbricas | Evals con conjunto de escenas congelado | D | Penaliza |
| Separación de escritura por rol (el Redactor no escribe en el canon) | Guardrails en `store/` + inspección en revisión de código | A / I | Bloqueante |
| Continuidad del borrador frente al canon | Multi-agent verification: el Guardián no redacta, el Redactor no valida | D | Bloqueante vía `Defecto` |
| Paso de las puertas en cada cambio del repositorio | CI/CD integration: la misma tubería que el código humano | T | Bloqueante |
| Un prompt nuevo antes de aplicarlo al libro entero | Progressive rollout: un capítulo tras versión de prompt | D | Advertencia |
| Fugas epistémicas y colapso de voz bajo entradas hostiles | Red-teaming sobre paquetes de contexto construidos a mano | D | Informativa |
| Ciclo de vida de la escena (un solo `Borrador` aceptado, contador de reintentos que termina) | Model checking sobre la máquina de estados | A | Bloqueante |
| Borradores y escalados del intento 4 | Human-in-the-loop: muestreo y puertas de cierre | I | Bloqueante, con excepción autorizada |

*Sandboxed execution* no tiene aplicación aquí: ningún agente ejecuta código. Su superficie
de daño es la escritura en el canon, y eso lo acota el reparto de permisos por rol, no un
aislamiento de proceso.

### 4.3 Requisitos no comprobables

Marcar un requisito como *Unverifiable* obliga a decidir qué se hace con él. Estos son los
que el sistema tiene abiertos:

| Requisito | Clase | Decisión |
| --- | --- | --- |
| «La prosa debe sonar literaria» | U | Reformulado como umbrales de rúbrica del Juez, que penalizan y nunca bloquean; lo que queda fuera del umbral se acepta como riesgo |
| «El volumen cumple la promesa al lector» | U | Partido: siembras y hilos resueltos son comprobables (T) y bloquean; la satisfacción de la promesa pasa a inspección humana en la puerta de cierre |
| «El paquete de contexto contiene lo que la escena necesita» | U | Reformulado como cobertura: todo hecho vigente que el borrador referencia estaba en el paquete. Lo demás se depura a posteriori con la `Procedencia` |
| «El canon es coherente» | U | Sustituido por los invariantes enumerados en 4.1; «coherente» sin lista de invariantes no es un requisito, es una aspiración |

### 4.4 Huecos declarados

- No hay conjunto de datos congelado para los evals, así que las puntuaciones del Juez no
  son comparables entre versiones de prompt. Hasta que lo haya, *Progressive rollout* es la
  única señal real de que un prompt nuevo no ha empeorado nada.
- El mutation testing de 4.1 no está en la tubería. Mientras no lo esté, la cobertura de
  invariantes es una afirmación no verificada.
- El model checking del ciclo de vida se apoya en que el diagrama de estados y el código
  del Orquestador no diverjan. Nada lo comprueba hoy.

---

## 5. Notas

*Property-based testing* y *evals* no tienen una única referencia fundacional neutral, al
modo en que sí la tiene la verificación formal. Los enlaces de arriba apuntan al trabajo
que introdujo o formalizó la metodología en cada caso — QuickCheck para la primera, HELM
para la segunda —, y no son la única elección posible.

Las tablas recogen metodologías de uso habitual; ni son exhaustivas ni implican que todas
deban aplicarse a la vez. La elección depende del coste de un fallo no detectado en cada
punto del sistema.
