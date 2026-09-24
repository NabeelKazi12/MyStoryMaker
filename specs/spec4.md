# SPEC-004 · La novela se escribe y se lee — Especificación de requisitos (SRS)

| | |
| --- | --- |
| **Identificador** | SPEC-004 |
| **Título** | Del encargo a la prosa: apertura del canon, motor de escritura en el worker, rutas de escritura y de texto, y vista previa de la novela |
| **Estado** | `construida` el 2026-09-24. Aprobada ese mismo día por @Nabeel con el apartado 9 cerrado —la puerta *Spec aprobada* de `AGENTS.md` §10 superada, y el plan del apartado 10 firmado en el mismo acto—. Lo que quedó fuera y por qué está en §11 |
| **Fecha** | 2026-09-24 |
| **Origen** | Encargo de la persona autora el 2026-09-24: «en el frontend quiero que la página me dé un preview de la novela escrita, además de que no has habilitado el botón de escribir novela; corrígelo y haz las conexiones necesarias al backend para que sea posible observarlo» |
| **Documentos de referencia** | `docs/architecture.md`, `docs/definitions.md`, `docs/verification.md`, `AGENTS.md`, `CLAUDE.md`, `specs/spec3.md` (SPEC-003, construida) |
| **Relación con las specs anteriores** | SPEC-003 construyó la entrevista, la lectura y el harness como piezas sueltas. Esta spec **conecta esas piezas**: hoy ninguna ruta pone al sistema a escribir y ninguna ruta sirve prosa. No cambia ningún requisito de SPEC-003 |

---

## 1. Problema: qué hay y qué falta

El sistema tiene las dos puntas —se recoge el encargo, se lee la novela— y no tiene el
medio. Cinco hechos observables, cada uno comprobable por separado:

| # | Hecho observable hoy | Dónde se ve |
| --- | --- | --- |
| P-1 | `POST /entrevista` persiste `brief`, `volumen`, `destinatario` y los elementos personalizados, y nada más. La novela nace sin capítulos y sin escenas | `orchestrator/encargo.py`, función `_persistir` |
| P-2 | La lectura de una novela recién creada abre un índice vacío, indistinguible de una novela rota | `GET /novelas/{id}/lectura`, `frontend/src/pages/lectura/Lectura.tsx` |
| P-3 | Ninguna ruta pone al sistema a escribir una novela. `POST /escenas/{id}/redactar` encola la cadena de **una escena** que alguien tuvo que dar de alta a mano, y **nadie consume esa cola**: `python -m backend.worker` imprime un error y sale con 1 porque `construir_cliente_real()` lanza `NotImplementedError` | `api/main.py`, `worker/__main__.py`, `worker/modelo.py` |
| P-4 | Ninguna ruta sirve prosa. La lectura muestra «El texto de este capítulo se sirve cuando su borrador está aceptado», y en v1 **eso no puede ocurrir nunca**: `escena_limpia` declara tres invariantes en `AUSENTES_EN_V1`, una puerta con evidencia ausente no está superada, y un borrador que no supera su puerta no pasa a `aceptado` | `quality/puertas.py`, `Lectura.tsx` |
| P-5 | El botón dice «Crear la novela» y lo que crea es el encargo. El nombre promete lo que el sistema no hace | `frontend/src/pages/crear/CrearNovela.tsx` |

P-4 es el que más importa y el que menos se ve: la frase de la pantalla describe una
condición inalcanzable, así que la lectura queda permanentemente vacía y el sistema
parece estar esperando algo que nunca va a llegar.

---

## 2. Alcance

### 2.1 Qué entra

| # | Entra | Por qué |
| --- | --- | --- |
| A-01 | **Apertura del canon desde el encargo**: el Planner propone personajes, lugares, eventos y el reparto en capítulos con sus escenas; el Orquestador lo persiste o lo rechaza nombrando la fila que no valida | Sin canon no hay escena, y sin escena el Redactor no tiene qué redactar (P-1) |
| A-02 | **Motor de escritura en `worker/`**: consume la cola de `Tarea`, ensambla el paquete, invoca, verifica, evalúa la puerta, persiste `Borrador` con su `PaqueteDeContexto` y su `Procedencia`, canoniza los hechos declarados y registra cada transición | Es el bucle que hoy solo existe dentro de un test (P-3) |
| A-03 | **Rutas de escritura**: `POST /novelas/{id}/escritura` encola y devuelve `202`; `GET /novelas/{id}/escritura` devuelve el progreso por escena | `api/` encola y lee estado; el trabajo ocurre en `worker/` (`CLAUDE.md` §4) |
| A-04 | **Ruta de texto**: `GET /novelas/{id}/texto` sirve la prosa del **último borrador no obsoleto** de cada escena, con su estado y con la explicación de su puerta | Es lo que hace posible la vista previa sin mentir sobre el estado del borrador (P-4) |
| A-05 | **Cliente de modelo real**, cableado sobre la API de mensajes, y **modo demostración explícito** que solo se activa cuando quien llama lo pide por su nombre | Sin cliente no hay prosa; y un cliente falso que se active solo es exactamente la bajada silenciosa de modelo que D-08 prohíbe |
| A-06 | **Frontend**: botón de escribir habilitado y con el nombre de lo que hace, panel de progreso, y vista previa maquetada como una novela, con la marca de qué borrador no está aceptado y por qué | Es el encargo (P-5 y P-4) |
| A-07 | El botón de la entrevista pasa a llamarse **«Crear el encargo»**, y el de escribir vive en la lectura | Dos acciones distintas, dos botones distintos: hoy uno solo dice hacer las dos |

### 2.2 Qué no entra

| # | No entra | Por qué |
| --- | --- | --- |
| N-01 | Levantar la puerta `escena_limpia` o vaciar `AUSENTES_EN_V1` | Sería convertir ausencia de evidencia en evidencia favorable, que es lo que prohíbe el principio 8 de `architecture.md` §1. El borrador se **muestra** sin estar aceptado; no se acepta por mostrarlo |
| N-02 | Calidad literaria de la prosa, y cualquier juicio sobre ella | No es lo que un test decide (`AGENTS.md` §1). Lo que esta spec cobra es el recorrido, no el resultado |
| N-03 | Cambiar el modelo de D-17, el techo de 100.000 de D-13 o el orden del paquete de D-16 | Ya decididos |
| N-04 | Regeneración selectiva real desde la petición de cambio | `capitulos_afectados` ya calcula qué capítulos tocaría; encolar su reescritura es otra spec |
| N-05 | Exportación a PDF de la novela escrita | `export/pdf.py` existe y este cambio no lo toca |
| N-06 | El cliente generado del contrato OpenAPI de SPEC-002 | Sigue en `borrador`. El frontend de esta spec extiende el que SPEC-003 dejó escrito a mano, y esa deuda se declara, no se paga aquí |

---

## 3. Supuestos

| # | Supuesto | Si es falso |
| --- | --- | --- |
| S-01 | El entorno **no tiene** `ANTHROPIC_API_KEY` hoy: no hay `.env` en el repositorio y el SDK no está instalado. Por eso el modo demostración es lo que hace observable el recorrido ahora mismo | Si hay clave, el modo por defecto —el modelo real— funciona sin tocar nada más |
| S-02 | El cliente real se cablea sobre HTTP con la biblioteca estándar, sin añadir dependencia | Si se prefiere el SDK, cambia una función de `worker/modelo.py` y nada más: es la única frontera con el proveedor |
| S-03 | Una novela por proceso y un solo escritor sobre SQLite, como en SPEC-001 y SPEC-003 | Reaparece concurrencia y el worker necesitaría arrendamiento de tareas |
| S-04 | El worker corre como proceso aparte, arrancado por `run.ps1` junto a la API y la lectura | Si tuviera que correr dentro de uvicorn, `api/` acabaría invocando modelos y se rompe la regla 5 de `architecture.md` §2.3 |

---

## 4. Requisitos

### 4.1 Apertura del canon — RF-APE

| ID | Requisito | Origen |
| --- | --- | --- |
| RF-APE-01 | El Planner recibe el encargo —destinatario, rasgos, recuerdos obligatorios, género, tono, extensión— y propone personajes, lugares, eventos y el reparto en capítulos con una escena por capítulo | A-01 |
| RF-APE-02 | La salida del Planner se valida contra su esquema antes de tocar la base; una fila que no valida rechaza **el plan entero** nombrando la fila y el motivo, y no se parchea | A-01 |
| RF-APE-03 | Cada recuerdo marcado obligatorio en el encargo tiene al menos un capítulo asignado; un plan que se deja uno fuera no valida | A-01 |
| RF-APE-04 | La apertura es idempotente: pedirla dos veces sobre la misma novela no duplica canon ni capítulos | A-01 |
| RF-APE-05 | El prompt del Planner sube de versión al cambiar su contrato, y su hash queda en el manifiesto | `CLAUDE.md` §7.3 |

### 4.2 Motor de escritura — RF-ESC

| ID | Requisito | Origen |
| --- | --- | --- |
| RF-ESC-01 | Existe un proceso worker que consume la cola de `Tarea` y que arranca sin credenciales cuando se le pide el modo demostración por su nombre | A-02, A-05 |
| RF-ESC-02 | El worker no escribe el estado de la `Tarea`: informa, y el Orquestador transiciona. Toda transición queda registrada en `tarea_evento` | `CLAUDE.md` §3.4, D-02 |
| RF-ESC-03 | Toda invocación registra `PaqueteDeContexto` con su hash y `Procedencia`, también cuando falla | `CLAUDE.md` §3.5 |
| RF-ESC-04 | El crédito se reserva antes de invocar y se libera en toda ruta de salida: éxito, fallo, vencimiento y cancelación | RNF-04, D-14 |
| RF-ESC-05 | El borrador producido se persiste con su texto, su recuento de palabras y su procedencia, en estado `propuesto`, y **no** pasa a `aceptado` mientras su puerta traiga evidencia ausente | N-01 |
| RF-ESC-06 | Los hechos declarados por el Redactor pasan por el Canonizador; los que contradicen el canon vigente producen `Defecto` y no entran | `CLAUDE.md` §3.4 |
| RF-ESC-07 | El guardarraíl de términos prohibidos se evalúa sobre la prosa antes de persistirla, y una coincidencia devuelve el borrador al Redactor con el límite de reescrituras de RF-GRD-04 | RF-GRD-03 |
| RF-ESC-08 | La escalera de reintentos es la de `estados.py`: un corte de red no consume intentos narrativos, y agotarlos detiene la escena informando | RF-HAR-06 |
| RF-ESC-09 | Una escena ya escrita no se vuelve a invocar si su clave de ejecución coincide: se devuelve el artefacto registrado | RF-ORQ-13 |

### 4.3 Rutas — RF-RUT

| ID | Requisito | Origen |
| --- | --- | --- |
| RF-RUT-01 | `POST /novelas/{id}/escritura` crea el plan y su cadena de tareas y devuelve `202` con el identificador del plan; no invoca ningún modelo | `CLAUDE.md` §4 |
| RF-RUT-02 | La ruta de escritura declara el modo —`modelo` o `demostracion`— y el modo viaja en la respuesta y queda escrito en la `Procedencia` | A-05, D-08 |
| RF-RUT-03 | Pedir el modo `modelo` sin credencial devuelve `503` diciendo qué falta y qué alternativa hay; no cae en demostración por su cuenta | D-08 |
| RF-RUT-04 | `GET /novelas/{id}/escritura` devuelve el progreso: estado global, y por escena su estado, sus intentos narrativos y lo que le falta | A-03 |
| RF-RUT-05 | `GET /novelas/{id}/texto` devuelve, por capítulo y escena, la prosa del último borrador no obsoleto, su estado, su recuento de palabras y la explicación de su puerta | A-04 |
| RF-RUT-06 | Las tres rutas publican `operation_id` explícito en el contrato OpenAPI | RC-02 de SPEC-002 |
| RF-RUT-07 | Una novela que no existe devuelve `404`; una novela sin escribir devuelve `200` con la lista vacía y el estado que lo explica | P-2 |

### 4.4 Modelo — RF-MOD

| ID | Requisito | Origen |
| --- | --- | --- |
| RF-MOD-01 | `construir_cliente_real()` devuelve un cliente que invoca el modelo de D-17 con el techo de salida de `architecture.md` §4.2, y falla nombrando la variable de entorno que falta si no hay credencial | A-05 |
| RF-MOD-02 | Existe un cliente de demostración determinista que produce prosa a partir del paquete de contexto, y que **solo** se construye cuando el modo se pide por su nombre | A-05 |
| RF-MOD-03 | La `Procedencia` de una invocación de demostración registra `modelo = demostracion`, de modo que nada generado así puede confundirse después con prosa de modelo | D-08 |
| RF-MOD-04 | Toda respuesta y toda pantalla que muestre prosa de demostración lo dice | D-08 |

### 4.5 Lectura y vista previa — RF-PRE

| ID | Requisito | Origen |
| --- | --- | --- |
| RF-PRE-01 | La lectura ofrece un botón **«Escribir la novela»** habilitado siempre que la novela exista, y deshabilitado solo mientras hay escritura en curso | A-06 |
| RF-PRE-02 | Mientras se escribe, la página muestra el progreso por escena y no se queda en blanco ni finge estar terminada | A-06 |
| RF-PRE-03 | La vista previa maqueta la prosa **como una novela**: cuerpo serif, columna de medida legible, párrafos con sangría y separación de escenas; no como texto plano | A-06 |
| RF-PRE-04 | Cada capítulo previsualizado dice si su borrador está aceptado y, si no lo está, por qué no lo está, con la explicación que da la puerta | N-01, A-04 |
| RF-PRE-05 | Ningún aviso de la página se cierra ni se descarta solo | Preferencia declarada de interfaz |
| RF-PRE-06 | El botón de la entrevista se llama «Crear el encargo» y, al cerrarla, la página lleva a la lectura de la novela creada | A-07 |
| RF-PRE-07 | El frontend no decide nada del dominio: el estado de la escritura, el de cada borrador y el texto de las explicaciones vienen del backend | `CLAUDE.md` §4 |

---

## 5. Verificación

### 5.1 Tabla de cobertura

`T` test, `A` análisis, `I` inspección, `D` demostración, `U` no verificable tal como está escrito.

| Requisitos | Nivel | Metodología | Modo | Dónde corre | Autoridad |
| --- | --- | --- | --- | --- | --- |
| RF-APE-01 a RF-APE-04 | Artefacto | Caso: un encargo con dos recuerdos obligatorios abre canon y produce dos capítulos; repetir la apertura no duplica nada | T | Suite | Bloqueante |
| RF-APE-05 | Artefacto | El manifiesto de prompts se comprueba por hash, como el del Redactor | T | Suite | Bloqueante |
| RF-ESC-01, RF-ESC-02 | Artefacto | Recorrido del bucle con cliente falso: la cola se vacía y cada transición tiene su fila en `tarea_evento` | T | Suite | Bloqueante |
| RF-ESC-03 | Artefacto | Tras una escena hay tantas `Procedencia` como invocaciones, y ninguna contiene prosa | T | Suite | Bloqueante |
| RF-ESC-04 | Artefacto | Propiedad: tras cualquier secuencia de resultados, `en_vuelo` vuelve a cero | T | Suite | Bloqueante |
| RF-ESC-05 | Artefacto | El borrador queda `propuesto` y la puerta trae evidencia ausente; ningún borrador acaba `aceptado` en este recorrido | T | Suite | Bloqueante |
| RF-ESC-06 | Artefacto | Un hecho que contradice el canon vigente produce `Defecto` y no entra | T | Suite | Bloqueante |
| RF-ESC-07 | Artefacto | Prosa con un término vetado por el cliente vuelve al Redactor, y el límite de reescrituras se respeta | T | Suite | Bloqueante |
| RF-ESC-08 | Artefacto | Cuatro cortes de red no mandan una escena a escalado; cuatro defectos distintos sí | T | Suite | Bloqueante |
| RF-ESC-09 | Artefacto | Reejecutar con la misma clave no vuelve a invocar al cliente | T | Suite | Bloqueante |
| RF-RUT-01 a RF-RUT-07 | Artefacto | Pruebas de API con `httpx` sobre base temporal, una por código de respuesta | T | Suite | Bloqueante |
| RF-MOD-01 | Artefacto | Sin `ANTHROPIC_API_KEY` el constructor falla nombrando la variable; con una falsa, construye sin invocar | T | Suite | Bloqueante |
| RF-MOD-02, RF-MOD-03 | Artefacto | El cliente de demostración solo se construye con el modo pedido, y su `Procedencia` dice `demostracion` | T | Suite | Bloqueante |
| RF-MOD-04 | Proceso | Inspección en revisión de la respuesta de la ruta y de la pantalla | I | Revisión | Bloqueante |
| RF-PRE-01, RF-PRE-02, RF-PRE-04, RF-PRE-06 | Artefacto | Recorrido de la pantalla contra dobles derivados del contrato, con el sujeto en el frontend | T | Tubería del frontend | Bloqueante |
| RF-PRE-03, RF-PRE-05 | Artefacto | Inspección visual de la maqueta y comprobación de que ningún aviso tiene temporizador | I | Revisión | Bloqueante |
| RF-PRE-07 | Artefacto | La frontera: ninguna cadena de estado ni de explicación se construye en el frontend | T + I | Tubería del frontend | Bloqueante |

### 5.2 Lo que no es comprobable tal como está escrito

| Requisito | Por qué | Qué se hace |
| --- | --- | --- |
| «La novela se puede leer» | «Leer» no admite predicado: no hay umbral que separe una novela legible de una que no lo es | Se parte en lo que sí lo admite: hay prosa, tiene autor declarado, tiene estado declarado y tiene explicación de por qué no está aceptada. La calidad queda fuera por N-02 |
| RF-MOD-01 contra el proveedor real | Este entorno no tiene credencial ni red al proveedor | El test cubre la construcción y el fallo por credencial ausente; la invocación real queda como **D**, demostración manual con clave, y se anota como hueco declarado |

### 5.3 Huecos declarados

| # | Hueco | Consecuencia asumida |
| --- | --- | --- |
| H-1 | La invocación al proveedor real no se ejerce en la suite | El primer uso con credencial es también la primera prueba del transporte. Mitigación: el cliente es una función pequeña y su fallo se clasifica, no se traga |
| H-2 | El modelo de D-17 sigue sin contrastarse contra la API de modelos | Se mantiene la salvedad de SPEC-001 §9.2: el identificador viaja tal cual y un modelo inexistente sale como fallo de transporte con su mensaje |
| H-3 | La vista previa se cobra por inspección, no por browser MCP | RF-LEC de SPEC-003 preveía validación visual automatizada; aquí no se añade. Queda como deuda de SPEC-003 A-09 |

---

## 6. Impacto

### 6.1 `docs/`

| Documento | Cambio |
| --- | --- |
| `docs/architecture.md` | El motor de escritura como proceso y el modo de demostración, con D-20 y D-21 registradas |
| `docs/definitions.md` | `Capitulo` gana `titulo`; `Plan` gana el volumen al que sirve |
| `CLAUDE.md` §6 | El comando del worker pasa a ser real, con su modo |

### 6.2 Módulos y migraciones

| Módulo | Cambio |
| --- | --- |
| `backend/migrations/` | Migración `0004`: `capitulo.titulo`, `plan.volumen_id` |
| `backend/agents/planner/` | Prompt `v1.1.0` con la apertura del canon, y su entrada en el manifiesto |
| `backend/orchestrator/` | `apertura.py` nuevo; `escritura.py` nuevo |
| `backend/worker/` | `bucle.py` nuevo; `__main__.py` pasa a arrancar de verdad; `modelo.py` gana el cliente real y el de demostración |
| `backend/store/` | Repositorio de borradores y de progreso |
| `backend/api/` | Tres rutas nuevas |
| `frontend/` | `shared/api/`, `pages/lectura/`, `pages/crear/`, `shared/ui/estilos.css` |
| `run.ps1` | Arranca el worker |

### 6.3 Decisiones a registrar

| # | Decisión | Alternativa descartada |
| --- | --- | --- |
| D-20 | El modo de demostración existe, es explícito y se declara en la `Procedencia` | Que el sistema caiga en prosa falsa cuando no hay credencial. Descartada: es la bajada silenciosa de D-08, y produce una novela que nadie sabe que no es del modelo |
| D-21 | La vista previa sirve el borrador **no aceptado**, marcado como tal | Esperar a que la puerta lo acepte. Descartada: `AUSENTES_EN_V1` hace esa condición inalcanzable en v1, así que esperar es esperar para siempre |

---

## 7. Criterios de aceptación

| # | Criterio |
| --- | --- |
| C-1 | Desde la página, un encargo nuevo se convierte en una novela con capítulos, y su prosa se lee en la misma página, sin tocar la base a mano |
| C-2 | Mientras se escribe, la página dice por dónde va, escena a escena |
| C-3 | Ningún borrador aparece como aceptado; cada uno dice por qué no lo está |
| C-4 | Sin credencial, pedir el modo `modelo` devuelve `503` con el nombre de lo que falta; el modo `demostracion` funciona y se identifica como tal en la respuesta y en la pantalla |
| C-5 | `uv run pytest -m invariants` sigue verde, y `ruff`, `mypy` y `npm run lint` pasan |
| C-6 | `.\run.ps1` levanta API, worker y lectura, y el recorrido de C-1 se hace entero desde el navegador |

---

## 8. Riesgos

| # | Riesgo | Mitigación |
| --- | --- | --- |
| R-1 | El motor de escritura duplica lo que hoy vive disperso entre `orchestrator/` y el test del bucle | El motor **no reimplementa** nada: llama a `Semaforo`, `DAG`, `transicionar`, `Ensamblador`, `Guardarrail`, `puertas` y `Canonizador` tal como están |
| R-2 | El worker como proceso aparte introduce un segundo escritor sobre SQLite | Con paralelismo 1 y una novela por proceso se mantiene S-03. El worker es el único que escribe artefactos; la API solo encola y lee |
| R-3 | La prosa de demostración se cuela en una novela de verdad | `Procedencia.modelo = demostracion` y la marca en la respuesta y en la pantalla. Un borrador de demostración es reconocible en la base para siempre |
| R-4 | La apertura del canon propone entidades que contradicen canon existente | Pasa por el Canonizador como todo lo demás; lo que contradice sale como `Defecto` y no entra |

---

## 9. Preguntas abiertas

| # | Pregunta | Estado |
| --- | --- | --- |
| Q-1 | ¿El modo de demostración entra, o el recorrido se deja bloqueado hasta que haya credencial? | **Cerrada** el 2026-09-24: entra, con las cuatro condiciones de RF-MOD-01 a RF-MOD-04. El modo por defecto sigue siendo el modelo real |

---

## 10. Plan de implementación — PLAN-004

| | |
| --- | --- |
| **Identificador** | PLAN-004 |
| **Estado** | `aprobado` el 2026-09-24 por @Nabeel, en la misma firma que la spec. Autoriza escribir código |

El orden es el de las dependencias, no el de los apartados. Cada paso nombra su test antes de escribirlo.

### 10.1 Fase A · Esquema y contrato del Planner

| # | Paso | Dónde | Test |
| --- | --- | --- | --- |
| A-1 | Migración `0004`: `capitulo.titulo`, `plan.volumen_id` | `migrations/` | `test_migracion_0004_anade_titulo_y_volumen` |
| A-2 | Prompt del Planner `v1.1.0` con la apertura, y su hash en el manifiesto | `agents/planner/` | `test_el_manifiesto_del_planner_cubre_la_version_vigente` |
| A-3 | Parseo de la apertura: personajes, lugares, eventos, capítulos y escenas | `agents/planner/` | `test_una_apertura_incompleta_rechaza_el_plan_entero` |

### 10.2 Fase B · Apertura del canon

| # | Paso | Dónde | Test |
| --- | --- | --- | --- |
| B-1 | Persistencia de la apertura, transaccional e idempotente | `orchestrator/apertura.py` | `test_abrir_dos_veces_no_duplica_canon` |
| B-2 | Cobertura de los recuerdos obligatorios | `orchestrator/apertura.py` | `test_un_recuerdo_obligatorio_sin_capitulo_rechaza_el_plan` |

### 10.3 Fase C · Cliente de modelo

| # | Paso | Dónde | Test |
| --- | --- | --- | --- |
| C-1 | `construir_cliente_real()` sobre HTTP, con el techo de salida y la clasificación de fallos | `worker/modelo.py` | `test_sin_credencial_el_cliente_real_nombra_la_variable` |
| C-2 | `ClienteDeDemostracion`, determinista y explícito | `worker/modelo.py` | `test_el_cliente_de_demostracion_no_se_construye_sin_pedirlo` |
| C-3 | `Procedencia.modelo = demostracion` | `worker/worker.py` | `test_la_procedencia_de_demostracion_es_reconocible` |

### 10.4 Fase D · Motor de escritura

| # | Paso | Dónde | Test |
| --- | --- | --- | --- |
| D-1 | Ensamblado del paquete de una escena desde la story bible | `orchestrator/escritura.py` | `test_el_paquete_de_una_escena_lleva_los_intocables` |
| D-2 | Una vuelta del bucle: invocar, verificar, puerta, persistir, canonizar, transicionar | `worker/bucle.py` | `test_una_vuelta_deja_borrador_propuesto_y_transiciones_registradas` |
| D-3 | Guardarraíl antes de persistir, con límite de reescrituras | `worker/bucle.py` | `test_un_termino_vetado_devuelve_el_borrador_al_redactor` |
| D-4 | Escalera de reintentos y parada informada | `worker/bucle.py` | `test_agotada_la_escalera_la_escena_se_detiene_informando` |
| D-5 | Idempotencia por clave de ejecución | `worker/bucle.py` | `test_la_misma_clave_no_vuelve_a_invocar` |
| D-6 | Proceso worker: cola, crédito y reanudación | `worker/__main__.py` | `test_el_worker_vacia_la_cola_y_libera_el_credito` |

### 10.5 Fase E · Rutas

| # | Paso | Dónde | Test |
| --- | --- | --- | --- |
| E-1 | `POST /novelas/{id}/escritura` con su modo | `api/` | `test_pedir_escritura_devuelve_202_y_no_invoca_modelos` |
| E-2 | `503` sin credencial en modo `modelo` | `api/` | `test_sin_credencial_el_modo_modelo_devuelve_503_util` |
| E-3 | `GET /novelas/{id}/escritura` | `api/` | `test_el_progreso_enumera_las_escenas_con_su_estado` |
| E-4 | `GET /novelas/{id}/texto` | `api/` | `test_el_texto_sirve_el_ultimo_borrador_no_obsoleto_con_su_puerta` |

### 10.6 Fase F · Frontend

| # | Paso | Dónde | Test |
| --- | --- | --- | --- |
| F-1 | Cliente de las tres rutas en la única puerta de red | `shared/api/` | `test_todas_las_llamadas_pasan_por_shared_api` |
| F-2 | Botón «Escribir la novela» y panel de progreso | `pages/lectura/` | `test_escribir_encola_y_la_pagina_muestra_el_progreso` |
| F-3 | Vista previa maquetada como novela, con el estado de cada borrador | `pages/lectura/`, `shared/ui/` | `test_la_previa_marca_el_borrador_no_aceptado_y_su_motivo` |
| F-4 | «Crear el encargo» en la entrevista | `pages/crear/` | `test_cerrar_la_entrevista_lleva_a_la_lectura` |

### 10.7 Fase G · Cierre

| # | Paso | Dónde |
| --- | --- | --- |
| G-1 | `run.ps1` arranca el worker y espera a que responda | `run.ps1` |
| G-2 | D-20 y D-21 en `docs/architecture.md`; `capitulo.titulo` en `docs/definitions.md`; comandos en `CLAUDE.md` §6 | `docs/`, `CLAUDE.md` |
| G-3 | SPEC-004 a `construida`, con lo que quedó fuera y por qué | `specs/spec4.md` |

### 10.8 Marcha atrás

| Paso | Si no sale |
| --- | --- |
| C-1 | El cliente real se queda como está —lanzando con el motivo— y el recorrido se cobra solo en modo demostración. Se anota como desviación |
| D-2 | Si el bucle no cabe sin reimplementar piezas, se para y se replantea: duplicar el orquestador dentro del worker es peor que no tener el bucle |
| F-3 | Si la maqueta no se sostiene, se sirve la prosa sin adornos pero **nunca** sin su estado: la marca de borrador no es cosmética |

---

## 11. Lectura de ejecución

Qué se construyó, qué se desvió del plan y qué quedó sin hacer. Se escribe al cerrar, no al
empezar: un plan que se declara cumplido sin esta sección oculta justo lo que cuesta caro
descubrir después.

### 11.1 Estado por fase

| Fase | Estado | Nota |
| --- | --- | --- |
| A · Esquema y contrato del rol | Construida | Migración `0004` con `capitulo.titulo`, `plan.volumen_id` y `plan.modo`, más los dos `RegistroDeDecision`. Prompt del Planner `v1.1.0` con su hash en el manifiesto |
| B · Apertura del canon | Construida | `orchestrator/apertura.py`, idempotente por volumen y con los identificadores del rol traducidos a identificadores del volumen |
| C · Cliente de modelo | Construida | `ClienteAnthropic` sobre HTTP y `ClienteDeDemostracion`, con la separación de D-20 comprobada por test |
| D · Motor de escritura | Construida | `worker/bucle.py` y `worker/__main__.py`. El bucle encadena las piezas que ya había; no reimplementa ninguna |
| E · Rutas | Construida | Las tres, con `operation_id` y sus códigos de respuesta cubiertos |
| F · Frontend | Construida **sin sus tests** | Ver 11.3 |
| G · Cierre | Construida | `run.ps1` arranca el worker; `docs/` y `CLAUDE.md` §6 al día |

### 11.2 Desviaciones del plan

| # | Desviación | Por qué |
| --- | --- | --- |
| V-1 | Las dos decisiones nuevas son **D-20 y D-21**, no D-18 y D-19 como decía §6.3 al aprobarse | D-18 y D-19 ya estaban ocupadas por SPEC-003 en la migración `0002`. Reutilizar el número habría dado dos decisiones distintas con el mismo nombre, que es peor que renumerar |
| V-2 | El **hook de capítulo corre al cerrar el capítulo**, no en cada redacción | Su validador de longitud mide un capítulo contra el rango 800–3.000 palabras. Aplicado a una escena suelta la declara corta siempre, y la escalera de reintentos se agotaba con prosa que no tenía nada malo. El hook de policy sí corre por escena: una palabra vetada lo está en cualquier unidad de texto |
| V-3 | La canonización **aplica el cierre de intervalo** a la tabla `hecho`, no solo al registro de cambios | El Canonizador registra el cierre como evento y reconstruye plegando, pero `hecho` es la vista que lee la canonización siguiente. Sin aplicarlo, la tercera escena encontraba dos ubicaciones abiertas del mismo personaje y reportaba como contradicción lo que era una mudanza |
| V-4 | El componente de estado del mundo nombra su fila `escenario:`, no `lugar:` | El bloque de instrucción trae su propia fila `lugar:` con el nombre canónico a secas. Dos filas con la misma clave hacen que quien lea la primera se lleve la equivocada |
| V-5 | La pantalla **sondea** el progreso cada dos segundos en vez de abrir el SSE | `/tareas/{id}/eventos` emite el historial ya registrado de **una** tarea y se cierra; lo que la lectura necesita es el estado de la novela entera mientras avanza. Cambiarlo es del backend y no entraba en este alcance |

### 11.3 Lo que quedó sin hacer

| # | Sin hacer | Consecuencia y qué haría falta |
| --- | --- | --- |
| F-1 a F-4 | **Los cuatro tests del frontend que PLAN-004 §10.6 nombra** | El frontend no tiene tubería de pruebas: `package.json` no declara ni corredor ni script de test, y los dobles derivados del contrato que esos tests necesitan son el trabajo de PLAN-002 B-03, que sigue en `borrador`. Lo construido se cobra hoy por inspección y por el recorrido manual de C-1; montar la tubería es PLAN-002, no un apaño dentro de esta spec |
| RF-PRE-03, RF-PRE-05 | **La inspección visual se hizo sobre el código, no sobre la página en un navegador** | Este entorno no tiene con qué conducir un navegador. Compilan `tsc`, `eslint` y `vite build`, y el recorrido se comprobó entero contra la API; lo que no se ha visto con los ojos es la maqueta renderizada. Es la misma deuda que H-3 declaraba |
| H-1 | **La invocación al proveedor real sigue sin ejercerse** | Como se declaró: el primer uso con credencial es también la primera prueba del transporte |

### 11.4 Criterios de aceptación

| # | Criterio | Resultado |
| --- | --- | --- |
| C-1 | Del encargo a la prosa leída, sin tocar la base a mano | **Cumplido.** Recorrido hecho contra API y worker en marcha: tres recuerdos → tres capítulos con título, 1.023 palabras, ficha con su personaje y sus tres lugares |
| C-2 | La página dice por dónde va, escena a escena | **Cumplido** en la API y en la pantalla; la pantalla, por inspección (11.3) |
| C-3 | Ningún borrador aparece como aceptado, y cada uno dice por qué | **Cumplido.** Los tres quedaron `en_revision` con los tres invariantes ausentes nombrados |
| C-4 | `503` con lo que falta en modo `modelo`; demostración marcada como tal | **Cumplido** y comprobado por test y a mano |
| C-5 | `pytest`, `ruff`, `mypy` y `npm run lint` en verde | **Cumplido.** 392 tests, de los cuales 27 nuevos |
| C-6 | `.\run.ps1` levanta las tres mitades | **Parcial.** El script arranca el worker y lo comprueba, y sus tres procesos se ejecutaron por separado en este entorno; el script completo no se ha ejecutado de una pieza |
