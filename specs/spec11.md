# SPEC-011 · Los personajes del encargo — Especificación de requisitos (SRS)

| | |
| --- | --- |
| **Identificador** | SPEC-011 |
| **Título** | Definir los personajes antes de escribir: paso «Los personajes» en la entrevista, edición en el Taller hasta que empiece la escritura, y el Planner obligado a usarlos |
| **Estado** | `construida` el 2026-09-24. Aprobada ese mismo día por la persona autora con el apartado 7 vacío y los límites propuestos aceptados, y el plan del apartado 8 firmado en el mismo acto. **DV-2 endurece RF-PER-06** y pide confirmación; el resto de desviaciones, en §9.2 |
| **Fecha** | 2026-09-24 |
| **Origen** | Encargo de la persona autora el 2026-09-24: «agrega un apartado en el que antes de la creación de la novela se definan los personajes de la novela; de momento no está» |
| **Preguntas resueltas antes de redactar** | Dónde: **paso nuevo en la entrevista**, editable en el Taller hasta que empiece la escritura. Planner: **usa todos y puede añadir**; si falta uno, el plan se rechaza. Campos: **nombre, papel, relación con la persona destinataria y descripción** |
| **Documentos de referencia** | `docs/definitions.md` (Destinatario, ElementoPersonalizado, Personaje), `AGENTS.md` §2, `backend/orchestrator/apertura.py`, `backend/agents/planner/`, `specs/spec4.md` (apertura), `specs/spec5.md` (entrevista por pasos) |
| **Relación con las specs anteriores** | Añade una clase del encargo, un campo a la entrevista, una comprobación a la apertura, dos rutas y una versión del prompt del Planner. Cambia RF-INT-01 de SPEC-005: la entrevista pasa de cuatro pasos a cinco |

---

## 1. Problema: qué hay hoy

| # | Hecho observable | Dónde |
| --- | --- | --- |
| P-1 | Los personajes los inventa el Planner al abrir la novela. Quien encarga no puede decir quién sale en ella | `orchestrator/apertura.py` `persistir_apertura`, prompt `v1.2.0` |
| P-2 | Que la persona destinataria sea protagonista solo lo pide el prompt: el parser comprueba que haya *algún* protagonista, no que sea ella | `agents/planner/planner.py` `_personajes` |
| P-3 | La entrevista no tiene ningún campo de personajes, y `vinculo` —el tipo de elemento personalizado pensado para las relaciones— no lo produce nadie | `entrevistador.py`, `vocabularies.py` |

---

## 2. Alcance

### 2.1 Qué entra

| # | Entra |
| --- | --- |
| A-01 | Clase del encargo **`PersonajeDeclarado`**: nombre, papel (`protagonico`, `secundario`, `ambiental`), relación con la persona destinataria, descripción y si es la destinataria. Migración `0008` con su tabla y la decisión D-25 |
| A-02 | La entrevista acepta `personajes` en sus respuestas. La persona destinataria se declara **siempre**, como protagonista, aunque no se envíe: sale del nombre de la entrevista |
| A-03 | Paso **«Los personajes»** en la entrevista, entre «Lo que no puede faltar» y «La historia», con la destinataria ya puesta y bloqueada, y un formulario para añadir, editar y quitar los demás; aparecen en el repaso |
| A-04 | El prompt del Planner `v1.3.0` recibe los personajes declarados y la regla de usarlos todos con su nombre y su papel |
| A-05 | La apertura **rechaza el plan entero** si falta un personaje declarado o si su papel no coincide, nombrando cuál, como ya hace con los recuerdos obligatorios |
| A-06 | `GET` y `PUT /novelas/{id}/personajes`: leer y reemplazar la lista mientras la escritura esté `sin_empezar` y la novela no esté aprobada |
| A-07 | Bloque **«Personajes»** en el Taller, con el mismo formulario, editable solo mientras la escritura no ha empezado |
| A-08 | El modo demostración incluye los personajes declarados en su apertura |

### 2.2 Qué queda fuera

| # | Fuera | Por qué |
| --- | --- | --- |
| N-01 | Editar personajes después de empezar la escritura | Ya están en el canon y en la prosa; cambiarlos es un cambio del lector (`POST /cambios`), que regenera capítulos |
| N-02 | Deseo, necesidad, creencia falsa y tipo de arco | Decidido así; los completa el Planner. `necesidad_interna` sigue siendo obligatoria para un protagonista en el canon, y la pone él |
| N-03 | Retratos o imágenes | No se ha pedido |
| N-04 | Comprobar la descripción contra las palabras vetadas | Las escribe quien encarga, igual que la dedicatoria en la entrevista; el guardarraíl sigue actuando sobre la prosa |
| N-05 | Que el declarado quede ya en el canon al crear el encargo | El canon lo escribe la apertura; declarar es encargar, no canonizar (`AGENTS.md` §1.5) |

---

## 3. Requisitos

| Id | Requisito |
| --- | --- |
| RF-PER-01 | Un `PersonajeDeclarado` tiene `nombre` (1–80 caracteres, sin espacios sobrantes), `papel` del vocabulario `relevancia`, `relacion` (hasta 120), `descripcion` (hasta 500) y `es_destinatario` |
| RF-PER-02 | Cada encargo tiene **exactamente una** persona destinataria declarada, protagonista, con el nombre de la entrevista y la relación «a quien va dedicada». Si `personajes` no la trae, el backend la añade; si la trae con otro papel, el papel se corrige a protagonista |
| RF-PER-03 | Los nombres son únicos dentro del encargo, sin distinguir mayúsculas ni acentos. Como mucho, 12 personajes |
| RF-PER-04 | Un personaje mal formado —nombre vacío o largo, papel desconocido, nombre repetido, más de 12— hace que la entrevista responda `422` con `personajes` en `huecos` o una contradicción que nombra cuál y por qué, y no se crea nada |
| RF-PER-05 | La apertura recibe, por cada declarado, una línea `personaje declarado | nombre | papel | relación | descripción` |
| RF-PER-06 | Tras parsear la apertura, cada declarado tiene que aparecer entre los personajes propuestos con el mismo nombre —comparado sin mayúsculas ni acentos— y el mismo papel. Si no, el plan se rechaza entero, con `falta` que nombra cada personaje ausente o con otro papel, y la tarea cuenta el intento como fallo de contrato |
| RF-PER-07 | El Planner puede proponer personajes no declarados, de cualquier papel |
| RF-PER-08 | `GET /novelas/{id}/personajes` (`operationId` `readPersonajes`) devuelve la lista en orden; `PUT` (`operationId` `updatePersonajes`) la reemplaza con las reglas de RF-PER-01 a RF-PER-04 (`422` si no valen) y responde la lista guardada |
| RF-PER-09 | `PUT` responde `409` si la escritura no está `sin_empezar` —«La escritura ya ha empezado: los personajes están en la novela; pide un cambio»— o si la novela está aprobada. Retirada o inexistente, `404` (RF-ELI-05) |
| RF-PER-10 | Cambiar la lista queda en `audit_log` con la lista anterior y la nueva |
| RF-PER-11 | El prompt `v1.3.0` está en el manifiesto con su hash, y es la versión vigente |
| RF-PER-12 | El modo demostración compone su apertura con todos los declarados, con su papel, y la escritura de una muestra pasa la comprobación de RF-PER-06 |
| RF-LEC-25 | La entrevista tiene cinco pasos: *Para quién*, *Lo que no puede faltar*, **Los personajes**, *La historia*, *El toque final*, y el repaso. En «Los personajes» la destinataria aparece primera, con su nombre del paso 1, papel protagonista y relación fijos; su descripción sí se puede escribir |
| RF-LEC-26 | Añadir un personaje abre un formulario con nombre, papel (Protagonista, Secundario, De fondo), relación y descripción; cada personaje se puede editar y quitar. El formulario no valida: los `422` del backend marcan el paso con «falta» y dicen qué personaje falla |
| RF-LEC-27 | Lo escrito en el paso se conserva al recargar, como el resto de la entrevista (RF-INT-05) |
| RF-LEC-28 | El bloque «Personajes» del Taller muestra la lista y, mientras la escritura esté `sin_empezar` y la novela no esté aprobada, permite editarla con el mismo formulario y «Guardar». Si no, la muestra sin editar y dice por qué |
| RF-CON-08 | El frontend no decide si un personaje vale ni si se puede editar: envía, y enseña lo que el backend responda |

---

## 4. Verificación

| Requisito | Metodología | Modo | Política |
| --- | --- | --- | --- |
| RF-PER-01 a RF-PER-04 | Tests del dominio y de la entrevista: sin `personajes` se declara la destinataria; con la destinataria como secundaria se corrige; nombres repetidos con otra capitalización o acento, vacío, 81 caracteres, papel desconocido y 13 personajes dan `422` sin crear nada | T | Bloqueante |
| RF-PER-05 a RF-PER-07 | Tests de la apertura: la instrucción lleva cada declarado; un plan sin uno de ellos o con otro papel se rechaza nombrándolo; un plan con los declarados y uno extra se acepta | T | Bloqueante |
| RF-PER-08 a RF-PER-10 | Tests de las rutas: leer; reemplazar; `422`; `409` tras encolar la escritura y con la novela aprobada; `404` retirada; `audit_log` | T | Bloqueante |
| RF-PER-11 | `test_el_manifiesto_del_planner_cubre_la_version_vigente` con `v1.3.0` | T | Bloqueante |
| RF-PER-12 | Test de escritura en demostración con un secundario declarado: la apertura se acepta y el personaje está en el canon | T | Bloqueante |
| RF-LEC-25 a RF-LEC-28, RF-CON-08 | Recorrido con Edge sin cabeza contra una copia de la base: entrevista con dos personajes más, recarga a mitad, `422` por nombre repetido, crear, ver y editar en el Taller, escribir una muestra y ver los personajes en «Quién es quién»; Taller bloqueado tras escribir | D | Bloqueante |
| Todos | `uv run pytest`, `-m invariants`, ruff y mypy; `npm run lint` y `npm run build` | A | Bloqueante |

---

## 5. Impacto

| Dónde | Qué cambia |
| --- | --- |
| `backend/domain/spec/encargo.py` | `PersonajeDeclarado` y sus invariantes |
| `backend/migrations/` | `0008_los_personajes_se_declaran.py`: tabla `personaje_declarado (id, brief_id, orden, nombre, papel, relacion, descripcion, es_destinatario)` y `rd-d25` |
| `backend/agents/entrevistador/` | Lee y valida `personajes`; añade la destinataria |
| `backend/orchestrator/encargo.py`, `apertura.py` | Persistir los declarados; pasarlos a la instrucción; comprobar la cobertura |
| `backend/orchestrator/personajes.py` | Leer y reemplazar la lista con sus precondiciones |
| `backend/agents/planner/` | Prompt `v1.3.0` y manifiesto |
| `backend/worker/modelo.py` | La apertura de demostración incluye los declarados |
| `backend/store/` | Repositorio de declarados |
| `backend/api/main.py` | `GET` y `PUT /novelas/{id}/personajes` con `NOVELA_VIVA` |
| `frontend/` | Paso de la entrevista, bloque del Taller, cliente de las dos rutas |
| `docs/definitions.md` | Clase `PersonajeDeclarado` en la capa de especificación |
| `docs/architecture.md` | D-25: los personajes se declaran en el encargo y la apertura los cobra; alternativa descartada: escribirlos en el canon al cerrar la entrevista, que saltaría la apertura y haría del encargo una canonización |

---

## 6. Criterios de aceptación

1. Suite de backend, invariantes, lint y tipos en verde; `npm run lint` y `npm run build` en verde.
2. Recorrido: entrevista con la destinataria y dos personajes más → «Escribir una muestra» → los tres en «Quién es quién».
3. Desviaciones anotadas en §9.

---

## 7. Preguntas abiertas

Ninguna. Tres límites son propuesta de esta spec y se aceptan o se corrigen al aprobarla: 12 personajes como máximo, 80 caracteres de nombre y 500 de descripción.

---

## 8. Plan de implementación — PLAN-011

| | |
| --- | --- |
| **Identificador** | PLAN-011 |
| **Estado** | `aprobado` el 2026-09-24 en la misma firma que la spec. Autoriza escribir código |

| # | Paso | Dónde | Test, nombrado antes de escribirlo | Requisitos |
| --- | --- | --- | --- | --- |
| A-1 | `PersonajeDeclarado` y migración `0008` | `domain/`, `migrations/` | `test_un_declarado_sin_nombre_no_valida`, `test_migracion_0008_crea_personaje_declarado` | RF-PER-01 |
| A-2 | La entrevista lee, valida y completa los declarados | `agents/entrevistador/`, `orchestrator/encargo.py`, `store/` | `test_sin_personajes_se_declara_la_destinataria`, `test_la_destinataria_siempre_es_protagonista`, `test_un_nombre_repetido_da_422_sin_crear_nada`, `test_trece_personajes_dan_422` | RF-PER-02 a RF-PER-04 |
| B-1 | Instrucción y prompt `v1.3.0` | `orchestrator/apertura.py`, `agents/planner/` | `test_la_instruccion_lleva_cada_declarado`, `test_el_manifiesto_del_planner_cubre_la_version_vigente` | RF-PER-05, RF-PER-11 |
| B-2 | Cobertura en la apertura | `orchestrator/apertura.py` | `test_un_plan_sin_un_declarado_se_rechaza_nombrandolo`, `test_un_declarado_con_otro_papel_se_rechaza`, `test_el_planner_puede_anadir_personajes` | RF-PER-06, RF-PER-07 |
| B-3 | Demostración con los declarados | `worker/modelo.py` | `test_una_muestra_lleva_los_personajes_declarados_al_canon` | RF-PER-12 |
| C-1 | Rutas `GET`/`PUT` | `orchestrator/personajes.py`, `api/` | `test_leer_y_reemplazar_los_personajes`, `test_con_la_escritura_empezada_no_se_editan`, `test_una_aprobada_no_se_edita`, `test_editar_queda_en_audit_log` | RF-PER-08 a RF-PER-10 |
| D-1 | Paso de la entrevista y bloque del Taller | `pages/crear/`, `pages/lectura/`, `shared/` | Recorrido del criterio 2 | RF-LEC-25 a RF-LEC-28, RF-CON-08 |
| E-1 | Cierre: `docs/`, tests que fijan el esquema (cabeza `0008`, 17 decisiones), spec a `construida` | `docs/`, `tests/`, `specs/spec11.md` | Apartado 4 | Todos |

**Módulos.** La validación de los declarados vive en el dominio y en el Entrevistador; la
cobertura, en `orchestrator/apertura.py`, junto a la de los recuerdos. `agents/` no escribe
en la base.

**Marcha atrás.** Si con el modelo real el Planner rechaza la apertura una y otra vez por un
declarado —por ejemplo, porque cambia el nombre—, se para y se vuelve a la spec: la salida
no es relajar la comparación sin decidirlo.

---

## 9. Lectura de ejecución

### 9.1 Cómo se cobró

| Requisito | Resultado |
| --- | --- |
| RF-PER-01 a RF-PER-04 | `tests/test_personajes.py`: la clase rechaza nombre vacío, de 81 caracteres y descripción de 501; sin `personajes` se declara la destinataria; con otro papel se corrige y conserva su descripción; «Luis» y «luís», un personaje con el nombre de la destinataria, nombre vacío o largo, papel desconocido, descripción larga, una fila que no es un personaje y 13 personajes dan `422` sin crear ningún brief; 12 se aceptan |
| RF-PER-05 | La instrucción lleva una línea por declarado, con la barra del contrato cambiada por `/` |
| RF-PER-06, RF-PER-07 | Un plan sin un declarado, con otro papel o con uno que no sale en ninguna escena ni evento se rechaza nombrándolo; «MÁRTA» casa con «Marta»; el Planner puede añadir personajes |
| RF-PER-08 a RF-PER-10 | Leer y reemplazar; `422` con nombre repetido sin tocar la lista; `409` con la escritura encolada y con la novela aprobada; `audit_log` con la lista anterior y la nueva. `test_ninguna_ruta_sirve_una_novela_eliminada` cubre ya las dos rutas nuevas |
| RF-PER-11 | `test_el_manifiesto_del_planner_cubre_la_version_vigente` con `v1.3.0` |
| RF-PER-12 | Una muestra con un secundario declarado lo lleva al canon y a la ficha de la lectura |
| Suite | `uv run pytest`: 515 en verde; `-m invariants`: 513; `ruff check` y `mypy backend/` sin errores. Los dos tests que fijan el esquema pasan a cabeza `0008` y 17 decisiones |
| RF-LEC-25 a RF-LEC-28, RF-CON-08 | Recorrido con Edge sin cabeza contra una copia migrada de la base, con API, worker y Vite aislados: seis entradas en el indicador; la destinataria puesta con el nombre del paso 1; tras recargar, las tres fichas y el paso siguen; «luís» repetido da el `422`, marca el paso y la ficha con «falta» y dice «Personajes: «luís» esta repetido…»; quitado, se crea el encargo; el Taller los muestra editables; tras «Escribir una muestra» (3 escenas) el bloque queda bloqueado con su motivo y «Quién es quién» enseña a los tres. A 360 px sin desplazamiento horizontal; sin errores de consola |
| Frontend | `npm run lint` y `npm run build` en verde; `grep` de `fetch(` fuera de `shared/api/` sin resultados |

### 9.2 Desviaciones

| # | Desviación | Motivo |
| --- | --- | --- |
| DV-1 | La cobertura de los declarados vive en el parser del Planner (`parsear_apertura`, parámetro `personajes_declarados`), junto a la de los recuerdos, y no en `orchestrator/apertura.py` como decía el plan | Es donde ya se cobran los recuerdos obligatorios, y así el rechazo sale con el mismo tipo —`SalidaInvalidaDelPlanner`— y el bucle lo cuenta como fallo de contrato sin cambiar nada |
| DV-2 | **RF-PER-06 es más estricto que como se redactó**: además de estar en la lista con su nombre y su papel, cada declarado tiene que participar en algún evento o ser el POV de alguna escena. El prompt `v1.3.0` lo dice | El recorrido mostró que una apertura podía listar a un declarado sin usarlo: estaba en el canon pero no en la novela, y «Quién es quién» no lo enseñaba. La decisión de la persona autora fue que los declarados «tienen que aparecer», y la versión redactada no lo garantizaba |
| DV-3 | El prompt `v1.3.0` se editó una vez después de crearlo, para añadir la regla de DV-2, y su hash del manifiesto se actualizó | La versión no había salido de la suite y de una copia aislada de la base: ninguna procedencia de la base de trabajo la cita |
| DV-4 | El modo demostración da a cada declarado su propio evento y su propia escena, repartidos entre los capítulos | Es lo que le hace cumplir DV-2. Una muestra con dos declarados pasa de una escena a tres |
| DV-5 | El indicador de pasos se desplaza dentro de sí mismo en pantallas estrechas | Con seis entradas no cabía en 360 px y ensanchaba la página |
