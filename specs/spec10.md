# SPEC-010 · Tiempo de escritura — Especificación de requisitos (SRS)

| | |
| --- | --- |
| **Identificador** | SPEC-010 |
| **Título** | Que una novela de referencia se escriba en 2 a 10 minutos: sin pensamiento extendido y con la apertura pedida a varios candidatos a la vez |
| **Estado** | `construida` el 2026-09-24. Aprobada ese mismo día por la persona autora con el apartado 7 vacío —puerta *Spec aprobada* de `AGENTS.md` §10.5 superada— y el plan del apartado 8 firmado en el mismo acto. Lo construido y sus desviaciones están en §9 |
| **Fecha** | 2026-09-24 |
| **Origen** | Encargo de la persona autora el 2026-09-24: «optimiza el tiempo de escritura de las novelas, que se realice entre 2 y 10 minutos» |
| **Preguntas resueltas antes de redactar** | Referencia: una novela **como la de `vol-cb7143c310`** (unas 10.000 palabras, 10 capítulos, ~20 escenas). Escenas: **en serie**, conservando la continuidad. Apertura: **varios candidatos a la vez** |
| **Documentos de referencia** | `specs/spec4.md` (bucle de escritura), `backend/worker/modelo.py` (`PENSAMIENTO = None`), `architecture.md` §4.2 (techo de salida) y D-13 (techo de tokens en vuelo) |

---

## 1. Problema: qué hay hoy

Medido sobre la novela de referencia, escrita el 2026-09-24 entre las 16:04 y las 16:44.

| # | Hecho observable | Dónde |
| --- | --- | --- |
| P-1 | La novela tardó **40 minutos**: 2 llamadas al Planner (309 s) y 20 al Redactor (2.085 s, media 104 s, máximo 181 s), todas en serie | `procedencia` de `vol-cb7143c310` |
| P-2 | Claude Code enciende el pensamiento extendido por su cuenta, contra `PENSAMIENTO = None`. En una escena real: 15.933 tokens pensando para 620 palabras, 124 s y 0,092 $. La misma escena sin pensar: 13 s y 0,011 $. El Planner sin pensar: 24–34 s | `worker/modelo.py` |
| P-3 | Sin pensar, el Planner falla el formato en 2 de cada 6 aperturas (una fila con una columna de menos; `climax` como tipo de evento). Con reintentos en serie, una apertura puede tardar dos minutos y, con mala suerte, rechazarse entera: le pasó a la primera prueba cronometrada, con 4 fallos seguidos en 104 s | `worker/bucle.py`, `_abrir` |

---

## 2. Alcance

### 2.1 Qué entra

| # | Entra |
| --- | --- |
| A-01 | Invocar a Claude Code sin pensamiento extendido, como ya decide `PENSAMIENTO = None` |
| A-02 | La apertura pide **3 candidatos a la vez** en cada vuelta y se queda con el primero que valida, en orden de candidato |

### 2.2 Qué queda fuera

| # | Fuera | Por qué |
| --- | --- | --- |
| N-01 | Escribir escenas en paralelo | Decidido así: cada escena tiene que ver el canon y los resúmenes de las anteriores |
| N-02 | El objetivo para novelas más largas que la de referencia | En serie, el tiempo crece con las escenas: unas 30.000 palabras rondarían los 15 minutos |
| N-03 | Cambiar de modelo | D-17 lo fija; bajar de modelo en silencio es lo que D-08 prohíbe |
| N-04 | Candidatos en modo demostración y con los clientes de prueba | Son deterministas: tres candidatos iguales no añaden nada y harían los tests dependientes del orden de los hilos |

---

## 3. Requisitos

| Id | Requisito |
| --- | --- |
| RF-TIE-01 | Toda invocación a Claude Code va sin pensamiento extendido, por las dos vías que admite: el ajuste `alwaysThinkingEnabled: false` y `MAX_THINKING_TOKENS=0` |
| RF-TIE-02 | En cada vuelta de la apertura, un cliente que lo admite recibe 3 invocaciones simultáneas con el mismo paquete; se persiste el primer candidato, en orden, que valida. Si ninguno valida, la vuelta siguiente lleva el motivo del rechazo del primero, como hoy |
| RF-TIE-03 | Cada candidato deja su `Procedencia`, valide o no: los pagados y descartados tienen que verse |
| RF-TIE-04 | Cada candidato reserva su crédito en el semáforo y lo libera al terminar, en toda ruta de salida. Tres reservas caben en el techo de D-13 (3 × 28.000 ≤ 100.000) |
| RF-TIE-05 | Los clientes que no declaran admitir concurrencia —demostración y pruebas— siguen con un solo candidato por vuelta |
| RF-TIE-06 | El encargo de referencia se escribe entero, en modo `modelo`, en **2 a 10 minutos** desde que se pulsa «Escribir la novela» |

---

## 4. Verificación

| Requisito | Metodología | Modo | Política |
| --- | --- | --- | --- |
| RF-TIE-01 | Test de los argumentos y del entorno del proceso, sin lanzar `claude` | T | Bloqueante |
| RF-TIE-02, RF-TIE-03 | Test con un cliente concurrente de prueba: dos candidatos inválidos y uno válido se resuelven en una vuelta, con tres procedencias | T | Bloqueante |
| RF-TIE-04 | Test: el crédito en vuelo vuelve a cero tras una apertura con candidatos, también si todos fallan | T | Bloqueante |
| RF-TIE-05 | La suite actual sigue en verde sin cambiar sus guiones | T | Bloqueante |
| RF-TIE-06 | Cronometrar el encargo de referencia contra Claude Code real, en una base temporal | D | Bloqueante |
| Todos | `pytest`, `ruff`, `mypy` en verde | A | Bloqueante |

---

## 5. Impacto

| Dónde | Qué cambia |
| --- | --- |
| `backend/worker/modelo.py` | Argumentos y entorno sin pensamiento; `ClienteClaudeCode` declara que admite concurrencia |
| `backend/worker/bucle.py` | `_abrir` con candidatos simultáneos |
| `tests/` | `test_claude_code.py`, `test_escritura.py` |
| `docs/`, migraciones, frontend | Ninguno |

---

## 6. Criterios de aceptación

1. Todas las comprobaciones del apartado 4 en verde.
2. El encargo de referencia, cronometrado, entre 2 y 10 minutos, con sus 10 capítulos escritos.

---

## 7. Preguntas abiertas

Ninguna. El número de candidatos (3) es propuesta de esta spec: se acepta o se corrige al aprobarla.

---

## 8. Plan de implementación — PLAN-010

| | |
| --- | --- |
| **Identificador** | PLAN-010 |
| **Estado** | `aprobado` el 2026-09-24 en la misma firma que la spec. Autoriza escribir código |

| # | Paso | Dónde | Comprobación | Requisitos |
| --- | --- | --- | --- | --- |
| A-1 | Sin pensamiento extendido, con su test. Ya hecho al medir P-2, porque restaura una decisión existente | `worker/modelo.py`, `tests/test_claude_code.py` | `pytest` | RF-TIE-01 |
| A-2 | Tests en rojo; candidatos simultáneos en la apertura, con procedencia y crédito por candidato | `worker/bucle.py`, `tests/test_escritura.py` | `pytest` | RF-TIE-02 a RF-TIE-05 |
| B-1 | Cronometrar el encargo de referencia; spec a `construida` con el tiempo medido y sus desviaciones | `specs/spec10.md` | Apartado 4 | RF-TIE-06 |

**Concurrencia.** Los hilos solo invocan al modelo. Ensamblar el paquete, registrar la
procedencia y escribir en la base siguen en el hilo del bucle: una conexión SQLite no se
comparte entre hilos a la vez.

**Marcha atrás.** Con un candidato por vuelta se vuelve al comportamiento de hoy sin tocar
nada más.

---

## 9. Lectura de ejecución

### 9.1 Cómo se cobró

| Requisito | Resultado |
| --- | --- |
| RF-TIE-01 | `test_invoca_haiku_sin_herramientas_y_con_el_prompt_por_stdin` comprueba el ajuste y la variable de entorno |
| RF-TIE-02, RF-TIE-03 | `test_la_apertura_resuelve_con_el_candidato_que_valida_en_una_vuelta`: tres invocaciones simultáneas —una barrera obliga a que lleguen a la vez—, una vuelta y tres procedencias. Con `CANDIDATOS_DE_APERTURA = 1` el test falla |
| RF-TIE-04 | `test_si_ningun_candidato_valida_se_para_y_el_credito_vuelve_a_cero`: 12 invocaciones en 4 vueltas, apertura parada y crédito en vuelo a cero |
| RF-TIE-05 | La suite anterior pasa sin tocar sus guiones: 468 tests en verde |
| RF-TIE-06 | El encargo de referencia, en modo `modelo` contra Claude Code real y en una base temporal: **303 s (5 min 3 s)** desde el encargo hasta «Las 22 escenas estan escritas». Apertura aceptada en la primera vuelta; ningún fallo ni escalado. Antes: 40 min |
| Todos | `pytest`, `ruff` y `mypy` en verde |

### 9.2 Desviaciones

| # | Desviación | Motivo |
| --- | --- | --- |
| DV-1 | A-1 se construyó antes de aprobar la spec | Restaura una decisión ya tomada (`PENSAMIENTO = None`), y hacía falta para medir P-2 y P-3 |

### 9.3 Hallazgos fuera de alcance

| # | Hallazgo | Qué se hace |
| --- | --- | --- |
| H-1 | Sin pensamiento extendido, las escenas salen más cortas de lo pedido: la novela cronometrada tiene 8.997 palabras sobre 11.000 (82 %), y 9 de sus 11 capítulos quedan por debajo de 1.000 palabras | Afecta a la extensión, no al tiempo. Se corrige pidiendo más palabras por escena o insistiendo en la extensión en el prompt del Redactor, en una spec aparte |
| H-2 | El Planner repartió la novela en 11 capítulos para 10 recuerdos obligatorios | El número de capítulos lo decide el rol; el encargo no lo fija |

