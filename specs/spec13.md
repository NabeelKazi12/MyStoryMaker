# SPEC-013 · Cambiar el nombre de un personaje — Especificación de requisitos (SRS)

| | |
| --- | --- |
| **Identificador** | SPEC-013 |
| **Título** | Cambiar el nombre de un personaje desde «Pedir un cambio» y que el nombre nuevo quede en toda la novela: canon, esqueleto, resúmenes y prosa, con versión nueva y la anterior conservada |
| **Estado** | `construida` el 2026-09-25. Aprobada ese mismo día por la persona autora con el apartado 7 vacío y los límites propuestos aceptados, y el plan del apartado 8 firmado en el mismo acto. Desviaciones en §9.2 |
| **Fecha** | 2026-09-25 |
| **Origen** | Encargo de la persona autora el 2026-09-25: «haz que se pueda cambiar el nombre según la petición que se haga y que ese cambio persista para toda la novela». Viene de un fallo: «Pedir un cambio» sobre un personaje respondía siempre «Ese hecho no consta usado en ningún capítulo» |
| **Preguntas resueltas antes de redactar** | Entrada: **campo «Nuevo nombre»** explícito, no interpretación del texto libre. Prosa: **sustitución exacta**, no regeneración con el modelo. Nombre compuesto: **el completo y cada parte**. Destinataria: **fuera**, su nombre no se cambia por aquí |
| **Documentos de referencia** | `docs/definitions.md` (Entidad, Personaje, PersonajeDeclarado), `docs/architecture.md` (canon versionado), `backend/orchestrator/regeneracion.py`, `backend/store/escritura.py` (`TextoDeLaNovela`), `specs/spec3.md` (RF-LEC-05 a RF-LEC-07), `specs/spec11.md` (N-01) |
| **Relación con las specs anteriores** | Cierra el N-01 de SPEC-011 para el nombre. Se apoya en el arreglo previo, sin commit, que ancla `POST /cambios` a un personaje (`entidad_id`) y no solo a un hecho. No cambia qué hace `POST /cambios` con los demás cambios: sigue diciendo qué capítulos se tocarían, sin regenerarlos |

---

## 1. Problema: qué hay hoy

| # | Hecho observable | Dónde |
| --- | --- | --- |
| P-1 | Ninguna ruta cambia `personaje.nombre_canonico` después de la apertura | `backend/api/main.py`, `backend/orchestrator/` |
| P-2 | `POST /cambios` solo calcula los capítulos afectados. No toca canon ni prosa, y aun así el aviso dice «Se regenerarán N capítulo(s)» | `pedir_cambio`, `Lectura.tsx` `enviarCambio` |
| P-3 | El nombre vive copiado en varios sitios: el canon (`personaje`, `hecho.objeto`), el esqueleto (`escena.objetivo/conflicto/resultado`, `evento.descripcion`, `capitulo.titulo`), los resúmenes que alimentan los capítulos siguientes (`resumen_capitulo`), el encargo (`personaje_declarado`) y la prosa (`borrador.texto`). Cambiar solo uno deja canon fantasma (`CLAUDE.md` §7.4) | Esquema `0001`–`0008` |
| P-4 | `canon_cambio.operacion` solo admite `insertar` y `cerrar_intervalo`: un cambio de nombre no se puede registrar como evento de canon | `0001_esquema_inicial.py` |

---

## 2. Alcance

### 2.1 Qué entra

| # | Entra |
| --- | --- |
| A-01 | Ruta `PUT /novelas/{id}/personajes/{personaje_id}/nombre` que cambia el nombre de un personaje de esa novela, síncrona y sin invocar modelos |
| A-02 | Sustitución determinista del nombre viejo por el nuevo, como palabra completa, en todos los textos de P-3 de esa novela |
| A-03 | La prosa cambiada no se sobrescribe: cada escena tocada recibe un `Borrador` nuevo y el anterior queda `obsoleto = 1`, conservado |
| A-04 | Versión nueva de la novela con los capítulos cambiados marcados, si la prosa cambió |
| A-05 | Revisión nueva del canon con eventos `renombrar`. Migración `0009` y decisión D-26 |
| A-06 | La lectura dice, por personaje, si es la persona destinataria |
| A-07 | El diálogo «Pedir un cambio» lleva un campo «Nuevo nombre»; al enviarlo, la lectura se recarga con el nombre nuevo y los capítulos cambiados marcados |

### 2.2 Qué queda fuera

| # | Fuera | Por qué |
| --- | --- | --- |
| N-01 | Cambiar el nombre de la persona destinataria | Decidido así: su nombre viene del encargo y está en la dedicatoria y la portada; cambiarlo es otro encargo |
| N-02 | Interpretar el texto libre («que se llame Lucía») | Decidido así: exigiría una tarea con modelo y podría interpretar mal |
| N-03 | Regenerar con el modelo los capítulos del personaje | Decidido así: un nombre se cambia con una sustitución exacta; regenerar cambiaría el resto del texto y costaría invocaciones |
| N-04 | Declinaciones, apodos, diminutivos y menciones en minúscula («luisito») | La sustitución es exacta; lo que no casa se queda como está y es visible en la lectura |
| N-05 | Cambiar el nombre de lugares | No se ha pedido |
| N-06 | Leer la prosa de una versión anterior desde la lectura | No existe hoy; esta spec la conserva (A-03), no la enseña |
| N-07 | Tocar `hecho_detectado`, `paquete_contexto` y `procedencia` | Son registro de lo que ocurrió con el nombre de entonces; reescribirlos falsearía la reproducibilidad (`CLAUDE.md` §3.5) |
| N-08 | Que `POST /cambios` regenere los demás cambios | Sigue igual; solo se corrige su aviso (RF-NOM-14) |

---

## 3. Requisitos

| Id | Requisito |
| --- | --- |
| RF-NOM-01 | `PUT /novelas/{id}/personajes/{personaje_id}/nombre` (`operationId` `updateNombreDePersonaje`) recibe `{"nombre": "..."}` y responde `200` con el nombre anterior, el nuevo, la revisión del canon, la versión publicada (o `null`) y los capítulos cambiados, cada uno con su `id` y su `orden`, ordenados por `orden` |
| RF-NOM-02 | El nombre nuevo, sin espacios sobrantes, tiene 1–80 caracteres. Si no, `422` |
| RF-NOM-03 | Si el nombre nuevo coincide con el actual o con el de otro personaje de la novela —sin distinguir mayúsculas ni acentos—, `422` que dice con cuál |
| RF-NOM-04 | Si el personaje no sale en la novela (no es POV de ninguna escena ni participa en ningún evento suyo), `404`. Novela retirada o inexistente, `404` (RF-ELI-05) |
| RF-NOM-05 | Si el personaje es la persona destinataria —su nombre coincide, sin mayúsculas ni acentos, con el del destinatario del encargo—, `409` con el motivo |
| RF-NOM-06 | Si la novela está aprobada, `409` (como el resto de cambios). Si la escritura está `abriendo` o `escribiendo`, `409` «Espera a que termine la escritura»: una escena en vuelo volvería con el nombre viejo |
| RF-NOM-07 | Se sustituye el nombre completo como palabra completa, en su forma exacta y en mayúsculas («LUIS ORTEGA» → «PABLO RUIZ»). Además, cada palabra del nombre viejo que empiece por mayúscula se sustituye suelta por la palabra en la misma posición del nuevo si ambos tienen el mismo número de palabras; si no, solo la primera por la primera. «Ana» no casa dentro de «Anabel» |
| RF-NOM-08 | Una palabra suelta no se sustituye si forma parte del nombre de otro personaje de la novela: con dos Ortega, «Ortega» suelto se queda, y solo se cambia «Luis Ortega» completo y «Luis» |
| RF-NOM-09 | La sustitución es de una sola pasada: lo que ya se ha sustituido no se vuelve a sustituir, aunque el nombre nuevo contenga el viejo |
| RF-NOM-10 | Se sustituye en `personaje.nombre_canonico`, `personaje_declarado.nombre`, `hecho.objeto`, `evento.descripcion`, `escena.objetivo`, `escena.conflicto`, `escena.resultado`, `capitulo.titulo`, `resumen_capitulo.texto` y la prosa, todo de esa novela y en una sola transacción: o cambia todo o nada |
| RF-NOM-11 | Cada escena cuya prosa cambia recibe un `Borrador` nuevo con `version` siguiente, el mismo `estado` y `procedencia_id` que el anterior y el texto sustituido; el anterior pasa a `obsoleto = 1` y no se borra. La lectura y el PDF sirven el nuevo sin más cambios, porque ya sirven el último no obsoleto |
| RF-NOM-12 | El canon abre una revisión nueva con un evento `renombrar` por fila de `personaje` y de `hecho` cambiada, con el valor anterior y el nuevo en `datos` |
| RF-NOM-13 | Si la prosa cambió, se publica una versión nueva con todos los capítulos de la novela y `cambiado = 1` en los tocados, con motivo ««Luis» pasa a llamarse «Pablo»». Si no cambió, no se publica y la respuesta lo dice con `version: null` |
| RF-NOM-14 | El cambio queda en `audit_log` con el personaje, el nombre anterior y el nuevo. Y el aviso de `POST /cambios` deja de decir «Se regenerarán»: dice «Afectaría a N capítulo(s)» |
| RF-NOM-15 | Tras el cambio, los capítulos que se escriban después usan el nombre nuevo: su `PaqueteDeContexto` no contiene el viejo en ningún componente |
| RF-LEC-29 | Cada personaje de la ficha trae `es_destinatario`. El diálogo «Pedir un cambio» de un personaje que no es la destinataria lleva el campo «Nuevo nombre» encima del texto libre; el de la destinataria no lo lleva y dice por qué |
| RF-LEC-30 | Con «Nuevo nombre» escrito, «Pedir el cambio» llama a la ruta de RF-NOM-01, y el texto libre, si lo hay, sigue yendo a `POST /cambios`. El resultado llega como aviso: «Luis pasa a llamarse Pablo en 3 capítulo(s): 1, 4, 7.» o «… no aparecía en la prosa escrita; el cambio queda en la ficha y en lo que se escriba» |
| RF-LEC-31 | Tras un cambio de nombre la lectura se recarga: ficha, índice y texto enseñan el nombre nuevo, y los capítulos tocados llevan la marca «cambiado» (RF-LEC-06) |
| RF-CON-09 | El frontend no decide si un nombre vale ni si se puede cambiar: envía, y enseña el `422`/`409` que devuelva el backend |

---

## 4. Verificación

| Requisito | Metodología | Modo | Política |
| --- | --- | --- | --- |
| RF-NOM-02 a RF-NOM-06 | Tests de la ruta: vacío, 81 caracteres, el mismo nombre, el de otro personaje con otra capitalización, personaje ajeno, novela retirada, destinataria, novela aprobada y escritura en curso, cada uno con su código y sin tocar nada | T | Bloqueante |
| RF-NOM-07 a RF-NOM-09 | Tests unitarios de la sustitución: completo, mayúsculas, partes con igual y distinto número de palabras, partícula en minúscula («de la») que no se sustituye suelta, «Anabel» intacta, dos Ortega, nombre nuevo que contiene el viejo («Ana» → «Ana María») | T | Bloqueante |
| RF-NOM-10 a RF-NOM-13 | Test de extremo a extremo sobre una novela con prosa: tras renombrar, ninguna de las columnas de RF-NOM-10 de esa novela contiene el nombre viejo como palabra; los borradores anteriores siguen con `obsoleto = 1`; hay una revisión nueva con eventos `renombrar`; la versión nueva marca solo los capítulos tocados. Y un fallo forzado a mitad deja la base como estaba | T | Bloqueante |
| RF-NOM-14 | Test de `audit_log` | T | Bloqueante |
| RF-NOM-15 | Test: tras renombrar, el paquete de la siguiente escena en modo demostración no contiene el nombre viejo | T | Bloqueante |
| RF-NOM-12 | `test_migracion_0009_admite_renombrar_y_es_reversible` y los tests que fijan el esquema (cabeza `0009`, 18 decisiones) | T | Bloqueante |
| RF-LEC-29 a RF-LEC-31, RF-CON-09 | Recorrido con Edge sin cabeza contra una copia de la base: renombrar un secundario con prosa y ver ficha, índice, texto y marca «cambiado»; `422` por nombre repetido; la destinataria sin campo; bloqueo con la novela aprobada | D | Bloqueante |
| Todos | `uv run pytest`, `-m invariants`, ruff y mypy; `npm run lint` y `npm run build` | A | Bloqueante |

---

## 5. Impacto

| Dónde | Qué cambia |
| --- | --- |
| `backend/domain/` | Función pura de sustitución de nombre (sin dependencias), con las reglas de RF-NOM-07 a RF-NOM-09 |
| `backend/orchestrator/renombrar.py` | Precondiciones (RF-NOM-02 a RF-NOM-06) y la transacción de RF-NOM-10 a RF-NOM-14 |
| `backend/store/` | Lectura y escritura de los textos de la novela, borrador nuevo por escena y evento `renombrar` en `CanonVersionado` |
| `backend/migrations/` | `0009_el_nombre_se_cambia.py`: `canon_cambio.operacion` admite `renombrar` (reconstruyendo la tabla, porque SQLite no altera un `CHECK`) y `rd-d26` |
| `backend/api/main.py` | Ruta `PUT …/nombre`; `es_destinatario` en los personajes de `/lectura` |
| `frontend/` | Campo en el diálogo, cliente de la ruta, recarga tras el cambio, aviso de `POST /cambios` |
| `docs/definitions.md` | `nombre_canónico` de `Entidad`: cambia por petición del lector con un evento `renombrar`, nunca en sitio sin revisión |
| `docs/architecture.md` | D-26: el cambio de nombre es una sustitución determinista que versiona canon y prosa. Alternativa descartada: regenerar los capítulos con el Redactor, que cuesta invocaciones y reescribe lo que nadie pidió cambiar |

---

## 6. Criterios de aceptación

1. Suite de backend, invariantes, lint y tipos en verde; `npm run lint` y `npm run build` en verde.
2. Recorrido: en una novela con prosa, renombrar un secundario → la ficha, el índice y el texto lo enseñan con el nombre nuevo, los capítulos tocados salen marcados y el PDF también lleva el nombre nuevo.
3. Desviaciones anotadas en §9.

---

## 7. Preguntas abiertas

Ninguna. Dos límites son propuesta de esta spec y se aceptan o se corrigen al aprobarla: 80 caracteres de nombre, como en SPEC-011, y el bloqueo mientras la escritura está en curso (RF-NOM-06).

---

## 8. Plan de implementación — PLAN-013

| | |
| --- | --- |
| **Identificador** | PLAN-013 |
| **Estado** | `aprobado` el 2026-09-25 en la misma firma que la spec. Autoriza escribir código |

| # | Paso | Dónde | Test, nombrado antes de escribirlo | Requisitos |
| --- | --- | --- | --- | --- |
| A-1 | Sustitución pura | `domain/` | `test_sustituye_el_nombre_completo_y_en_mayusculas`, `test_sustituye_cada_parte_si_tienen_las_mismas_palabras`, `test_con_distinto_numero_de_palabras_solo_la_primera`, `test_no_sustituye_dentro_de_otra_palabra`, `test_no_sustituye_una_parte_de_otro_personaje`, `test_una_particula_en_minuscula_no_se_sustituye_suelta`, `test_una_sola_pasada_aunque_el_nuevo_contenga_el_viejo` | RF-NOM-07 a RF-NOM-09 |
| A-2 | Migración `0009` y `rd-d26` | `migrations/`, `store/` | `test_migracion_0009_admite_renombrar_y_es_reversible` | RF-NOM-12 |
| B-1 | Precondiciones | `orchestrator/renombrar.py` | `test_un_nombre_vacio_o_largo_da_422`, `test_el_mismo_nombre_o_el_de_otro_da_422`, `test_un_personaje_ajeno_da_404`, `test_la_destinataria_da_409`, `test_aprobada_o_escribiendo_da_409` | RF-NOM-02 a RF-NOM-06 |
| B-2 | Transacción: textos, borradores, canon, versión, auditoría | `orchestrator/renombrar.py`, `store/` | `test_tras_renombrar_ningun_texto_de_la_novela_lleva_el_nombre_viejo`, `test_el_borrador_anterior_se_conserva_obsoleto`, `test_renombrar_abre_una_revision_con_eventos_renombrar`, `test_la_version_nueva_marca_solo_los_capitulos_tocados`, `test_sin_prosa_no_se_publica_version`, `test_un_fallo_a_mitad_no_deja_nada_cambiado`, `test_renombrar_queda_en_audit_log` | RF-NOM-10 a RF-NOM-14 |
| B-3 | Lo que se escribe después | `tests/` | `test_el_paquete_siguiente_no_lleva_el_nombre_viejo` | RF-NOM-15 |
| C-1 | Ruta y `es_destinatario` | `api/` | `test_renombrar_por_la_ruta_responde_los_capitulos_cambiados`, `test_la_lectura_dice_quien_es_la_destinataria`, más `test_ninguna_ruta_sirve_una_novela_eliminada` cubriendo la ruta nueva | RF-NOM-01, RF-LEC-29 |
| D-1 | Diálogo, recarga y avisos | `pages/lectura/`, `shared/api/` | Recorrido del criterio 2 | RF-LEC-29 a RF-LEC-31, RF-CON-09, RF-NOM-14 |
| E-1 | Cierre: `docs/`, tests que fijan el esquema, spec a `construida` | `docs/`, `tests/`, `specs/spec13.md` | Apartado 4 | Todos |

**Módulos.** La sustitución es una función pura en `domain/`, sin importar nada; la
orquestación y las precondiciones, en `orchestrator/`; solo `store/` toca SQLite; `api/`
traduce a `422`/`404`/`409` y no invoca modelos. Ningún agente interviene.

**Marcha atrás.** Si la reconstrucción de `canon_cambio` en `0009` no es reversible sin
pérdida, se para y se vuelve a la spec: la alternativa sería registrar el cambio solo en
`audit_log`, y eso deja el canon sin versionar, que es una decisión que tiene que tomar la
persona autora.

---

## 9. Lectura de ejecución

### 9.1 Cómo se cobró

| Requisito | Resultado |
| --- | --- |
| RF-NOM-07 a RF-NOM-09 | `tests/test_renombrar.py`: nombre completo y en mayúsculas; partes con igual número de palabras; con distinto, solo la primera; «Anabel» y «Santana» intactas; dos Ortega; «de la» no se sustituye suelta; «Ana» → «Ana María» en una sola pasada; nombres con acentos |
| RF-NOM-02 a RF-NOM-06 | Vacío y 81 caracteres; «luís» (el mismo) y «márta» (la destinataria) dan `NombreInvalido` nombrando con quién choca; personaje ajeno, destinataria, novela aprobada y escritura encolada, cada uno con su excepción |
| RF-NOM-10 a RF-NOM-14 | Sobre una muestra con Luis de secundario: ninguna columna de RF-NOM-10 de la novela lleva «Luis» como palabra; cada borrador tocado queda `obsoleto = 1` con su texto intacto y el nuevo lleva `version + 1`, el mismo estado y procedencia; revisión nueva con `renombrar` y `{"antes", "despues"}`; versión nueva con todos los capítulos y solo los tocados marcados; sin prosa que lo nombre, `version: null`; un fallo forzado al publicar deja la base como estaba; `audit_log` con personaje y nombres |
| RF-NOM-15 | El paquete de cada escena, ensamblado tras renombrar, no lleva el nombre viejo. Antes del cambio lo llevaba al menos uno, comprobado a mano: el test no pasa en vacío |
| RF-NOM-12 | `test_migracion_0009_admite_renombrar`, `test_renombrar_un_hecho_no_lo_saca_del_canon`; los tests que fijan el esquema pasan a cabeza `0009` y 18 decisiones |
| RF-NOM-01, RF-LEC-29 | Por HTTP: `200` con capítulos ordenados por `orden`; `422`, `404` (personaje y novela) y `409`; `/lectura` trae `es_destinatario`. `test_ninguna_ruta_sirve_una_novela_eliminada` recorre ya la ruta nueva |
| Suite | `uv run pytest`: 545 en verde; `-m invariants`: 543; `ruff check` y `mypy backend/` sin errores. `ruff format --check` sigue marcando los 8 ficheros que ya marcaba antes |
| RF-LEC-29 a RF-LEC-31, RF-CON-09 | Recorrido con Edge sin cabeza contra una copia migrada de la base de trabajo, con API y Vite aislados en otros puertos: la destinataria no tiene campo y dice por qué; «luís» da el `422` como aviso; el secundario pasa a «Bruno» en los 4 capítulos, la ficha y la prosa ya no lo nombran como antes, la versión nueva marca los 4 y el PDF se genera; a 360 px sin desplazamiento horizontal |
| Frontend | `npm run lint` y `npm run build` en verde |

### 9.2 Desviaciones

| # | Desviación | Motivo |
| --- | --- | --- |
| DV-1 | El test de la migración se llama `test_migracion_0009_admite_renombrar` y no `…_y_es_reversible`, y la marcha atrás del plan no aplica | Las migraciones son solo hacia delante (RF-STO-02): `downgrade` lanza, como en `0001`–`0008` |
| DV-2 | `CanonVersionado.hechos_vigentes_en` pasa a tratar como cierre solo `cerrar_intervalo` | Trataba cualquier operación distinta de `insertar` como cierre: un `renombrar` sobre un hecho lo habría sacado del canon |
| DV-3 | El aviso de `POST /cambios` enseña números de capítulo y no ids | Con ids salían en orden alfabético (`…-10` antes de `…-2`) e ilegibles para quien lee |
| DV-4 | La consola del recorrido registra un `404` de un recurso estático de Vite, además del `422` provocado | No pasa por la API y no tiene que ver con este cambio |
| DV-5 | La lectura aún no enseña la prosa de una versión anterior | Declarado en N-06; los borradores anteriores se conservan con `obsoleto = 1` |
