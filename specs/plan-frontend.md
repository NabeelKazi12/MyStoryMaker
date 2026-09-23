# Plan de implementación del frontend — SPEC-002

| | |
| --- | --- |
| **Identificador** | PLAN-002 |
| **Spec de la que cuelga** | SPEC-002, hoy `propuesta`, con el apartado 12 sin vaciar |
| **Estado** | `borrador`. La puerta *Spec aprobada* de `AGENTS.md` §10.5 **no está superada**, así que este plan no se puede aprobar todavía y no autoriza escribir código. Se redacta ahora para que la aprobación de la spec y la del plan puedan encadenarse |
| **Fecha** | 2026-09-23 |
| **Sujeto** | El frontend. **Ningún paso de este plan escribe en `backend/`**; lo que el recorrido necesita de la otra mitad está en SPEC-002 §3.3 como dependencia y se construye en otra spec con su propio plan |
| **Ubicación** | `AGENTS.md` §10.3 quiere el plan en el apartado final de la propia spec. Este documento vive aparte por petición explícita; `specs/spec2.md` §13 no lo copia, lo referencia, y al aprobar se decide si se pliega dentro o la referencia queda permanente |

> El orden no es el de los apartados de la spec, es el de las dependencias: nada se
> construye antes que aquello contra lo que se comprueba. Cada paso es lo bastante pequeño
> para revisarse de una sentada, nombra su test **antes** de escribirlo, dice qué validador
> de SPEC-002 §8 lo cobra, y declara qué se hace si no sale.

---

## 1. Cómo se ejecuta cada paso

El ciclo es el TDD de `AGENTS.md` §10.4: rojo, verde, refactor, con el test visto fallar
**por el motivo correcto** antes de implementar nada.

Tres reglas propias de este plan, que salen de los dos pilares de SPEC-002 §2.2 y no del
proceso general:

1. **Todo paso tiene el mismo sujeto: el frontend.** Se cierra con la tubería del frontend
   contra dobles derivados del contrato, nunca contra el backend en marcha. Un test que
   falla por un error del backend está mal colocado y se traslada a la suite del backend
   (VF-14).
2. **El contrato va delante y no se toca desde aquí.** Si el documento OpenAPI no cumple
   RC-01…RC-08, no se genera nada: se anota como bloqueo y se espera. Corregir el cliente
   generado a mano está prohibido por VF-06, y apañar el contrato desde el frontend es el
   conflicto que el contrato venía a evitar.
3. **Cada paso nombra su validador.** Un paso sin validador en la columna correspondiente
   no está terminado: está escrito. La columna *Cobra* remite a SPEC-002 §8.

---

## 2. Paso 0 · Precondiciones, antes de escribir nada

No es una fase de construcción: es la comprobación que decide si el plan puede arrancar.
Se hace leyendo el documento OpenAPI publicado, sin escribir código de frontend.

| # | Comprobación | Resultado si falla |
| --- | --- | --- |
| 0.1 | El documento está congelado en el repositorio y la tubería del backend lo compara con el que publica la aplicación (RC-01), con `info.version` semántica y su criterio de incremento escrito (RC-07) | Bloqueo duro: la fase B no arranca. No se genera contra un blanco móvil, ni contra uno que no sepa decir si un cambio suyo es compatible |
| 0.2 | Todas las operaciones tienen `operationId` explícito con la forma acordada (RC-02) | Bloqueo duro: los nombres del cliente generado no serían estables |
| 0.3 | Ninguna respuesta es objeto anónimo ni `additionalProperties`; hay esquema único de error (RC-03, RC-04) | Bloqueo duro de la fase B para las operaciones afectadas |
| 0.4 | Los vocabularios cerrados se publican como `enum` (RC-05) | Bloqueo de C-04 y de D-11: sin `enum` no hay desplegable con fuente |
| 0.5 | La ruta de eventos declara `text/event-stream` y el esquema de cada `data:` (RC-06) | Bloqueo de la capa de eventos (fase C) y de D-04 |
| 0.6 | CORS por lista explícita incluye el origen de desarrollo (RC-08) | Bloqueo del recorrido de sistema (E-05); el resto del plan sigue, porque corre sobre dobles |
| 0.7 | Inventario de las operaciones de SPEC-002 §3.3 que el contrato publica hoy | No es un fallo: es el que fija qué partes del recorrido quedan parciales |

**Qué se hace con lo que 0.7 encuentre ausente.** No se simula, no se apaña con otra ruta y
no se implementa en el cliente. La vista declara *no publicada por el contrato*, el paso que
dependía de ella se marca parcial con su DEP citada, y el criterio de aceptación 1 queda
parcial hasta que aparezca. Las cuatro preguntas abiertas de SPEC-002 §12 se resuelven antes
de aprobar; P-01 es la que decide si esto es aceptable para cerrar.

---

## 3. Fase A · Esqueleto y guardarraíles · sujeto: frontend

Al cerrar la fase no hay ninguna vista y no se ha generado nada todavía: existen el
proyecto, las capas y las puertas que impiden que el resto del plan se desvíe. Van primero
porque son baratas sobre un proyecto vacío y caras sobre uno con tres vistas escritas.

| # | Paso | Módulos | Test que lo demuestra | Requisitos | Cobra |
| --- | --- | --- | --- | --- | --- |
| A-01 | Proyecto Vite + React + TypeScript estricto, con los comandos exactamente como los escribe `CLAUDE.md` §6 | `frontend/`, `CLAUDE.md` | La tubería ejecuta `npm run build` y `npm run lint` tal como están escritos | RF-EST-01, RF-NF-02 | Tubería |
| A-02 | Las tres capas `app/`, `pages/`, `shared/`, con API pública por slice y sin `entities/`, `features/` ni `widgets/` | `frontend/src/` | `test_capas`: una importación hacia arriba y un salto de API pública hacen fallar la puerta | RF-EST-02, RF-EST-03 | **VF-12** |
| A-03 | Prohibir `fetch` y `EventSource` fuera de `shared/api/`, con autoridad bloqueante | tubería del frontend | `test_una_sola_puerta_de_red`: un `fetch` en una página hace fallar | RF-RED-01 | **VF-12** |
| A-04 | Prohibir temporizadores de consulta (`setInterval`, y `setTimeout` que reintenta una lectura) fuera de la reconexión declarada | tubería del frontend | `test_sin_temporizadores_de_consulta` | RF-RED-06 | **VF-08** |
| A-05 | Prohibir literales de vocabulario cerrado, umbrales, órdenes de puerta y predicados de invariante fuera del directorio generado | tubería del frontend | `test_sin_literales_de_vocabulario`, `test_sin_umbrales_ni_predicados` | RF-NF-04, RF-CAN-02 | **VF-04**, **VF-05** |
| A-06 | Prohibir acceso a ficheros, a base de datos y persistencia de canon en el navegador | tubería del frontend | `test_sin_modulos_de_sistema`, `test_sin_canon_en_almacenamiento_local` | RF-NF-03 | **VF-04** |
| A-07 | `shared/ui/` sin conocimiento del dominio: no importa tipos generados ni nombres de la ontología | `shared/ui/` | `test_ui_no_importa_generated` | RF-EST-04 | **VF-12** |

**Por qué A-04 y A-05 van aquí.** Un `setInterval` puesto en la primera vista sobrevive a
cualquier revisión posterior si nadie lo prohíbe antes de escribirlo, y un vocabulario
transcrito no se nota hasta la migración que lo deja viejo. Los dos son FF-08 y FF-05, y los
dos se apagan escribiendo la puerta antes que el código que la infringiría.

---

## 4. Fase B · Generación · sujeto: frontend

Al cerrar la fase existe el cliente, existen los tipos y existen los dobles, los tres
derivados del mismo documento. Es la fase que decide si el resto del trabajo se apoya en el
contrato o lo esquiva.

| # | Paso | Módulos | Test que lo demuestra | Requisitos | Cobra |
| --- | --- | --- | --- | --- | --- |
| B-01 | Generar tipos y cliente del documento congelado a `shared/api/generated/`, con su comando escrito en `CLAUDE.md` §6 y el directorio marcado como no editable | `shared/api/generated/`, `CLAUDE.md` | `test_regenerar_no_produce_diferencias` sobre árbol limpio | RF-GEN-01, RF-GEN-02 | **VF-06** |
| B-02 | Retirar cualquier tipo de la frontera escrito a mano; nada en espejo con los esquemas Pydantic | `shared/api/` | `test_sin_tipos_de_frontera_fuera_de_generated` | RF-GEN-04 | **VF-06** |
| B-03 | Generar los dobles del mismo documento, en el mismo paso de tubería que el cliente | `frontend/tests/` | `test_dobles_regenerados_sin_diferencias`; `test_sin_dobles_escritos_a_mano` | RF-GEN-03 | **VF-07** |
| B-04 | Dejar la tubería ejecutando la suite del frontend **con el backend apagado** | tubería del frontend | La suite entera pasa sin backend, salvo el recorrido de sistema declarado | RF-NF-01 | **VF-14** |

**Si el generador produce tipos laxos**, se corrige el documento —es un fallo de RC-03, y
pertenece a la otra mitad—, nunca el código generado. Entre las dos cosas que pueden ceder,
la que no cede es VF-06.

---

## 5. Fase C · Capa de red · sujeto: frontend

Al cerrar la fase, todo lo que el frontend sabe del backend entra por un solo sitio y se
comporta igual en las tres vistas.

| # | Paso | Módulos | Test que lo demuestra | Requisitos | Cobra |
| --- | --- | --- | --- | --- | --- |
| C-01 | Cliente HTTP sobre lo generado, único punto de salida de peticiones | `shared/api/` | `test_todas_las_llamadas_pasan_por_shared_api` | RF-RED-01 | **VF-12** |
| C-02 | `202` sin espera: se guarda el identificador de la tarea y se abre su flujo de eventos | `shared/api/` | `test_202_guarda_id_y_no_espera` | RF-RED-02 | **VF-13** |
| C-03 | Flujo de eventos con cierre al desmontar y reconexión con retroceso exponencial | `shared/api/` | `test_sse_se_cierra_al_desmontar`: montar y desmontar en bucle deja las conexiones abiertas en cero | RF-RED-03 | **VF-13** |
| C-04 | Ningún `4xx` se reintenta | `shared/api/` | `test_4xx_no_se_reintenta` | RF-RED-04 | **VF-08** |
| C-05 | El error del backend se traslada íntegro hasta la capa de presentación, sin resumir ni traducir | `shared/api/` | `test_mensaje_de_error_llega_integro`: comparación carácter a carácter con el `422` del doble | RF-RED-05 | **VF-11** |

C-04 y A-04 se cobran con el mismo validador a propósito: reintentar un `4xx` y sondear con
un temporizador son la misma enfermedad —peticiones que crecen sin que nadie las pida— y
conviene que las delate el mismo recuento.

---

## 6. Fase D · Las tres vistas · sujeto: frontend

El orden es deliberado: primero lo que hace visible el bucle, después lo que se lee, y al
final lo que más formulario tiene. Cada paso corre sobre dobles.

| # | Paso | Módulos | Test que lo demuestra | Requisitos | Cobra |
| --- | --- | --- | --- | --- | --- |
| D-01 | Panel: tareas con estado, prioridad, reserva y `falta[]`, con los intentos por clase de fallo y no un contador único | `pages/panel/` | Recorrido sobre dobles con una tarea por estado y las cuatro clases de fallo pobladas | RF-PAN-01 | **VF-02** |
| D-02 | Panel: escalados destacados sin filtrar ni buscar, que no se retiran hasta resolverse | `pages/panel/` | `test_escalada_visible_sin_filtrar`; `test_el_aviso_de_escalado_sigue_tras_la_espera` | RF-PAN-02 | **VF-09** |
| D-03 | Panel: cancelar y resolver con confirmación explícita que nombra el subárbol arrastrado | `pages/panel/` | `test_cancelar_pide_confirmacion_y_nombra_el_subarbol` | RF-PAN-03 | **VF-09** |
| D-04 | Panel: transiciones tal como llegan por el flujo de eventos, sin estados inventados ni barras estimadas | `pages/panel/` | `test_solo_se_pintan_las_transiciones_recibidas`; recuento de peticiones estable en 60 s | RF-PAN-04 | **VF-08** |
| D-05 | Panel: defectos por severidad con su evidencia citable y su regla violada, más el contador de descartados | `pages/panel/` | Recorrido con defectos sembrados en el doble y un descarte por falta de evidencia | RF-PAN-05 | **VF-02** |
| D-06 | Panel: puertas distinguiendo superada, fallada y **no evaluada**, nombrando la evidencia que falta | `pages/panel/` | Los tres estados de puerta sobre dobles; la evidencia ausente nunca se pinta en verde | RF-PAN-06 | **VF-01** |
| D-07 | Panel: señales con su nombre completo y la ausencia de juicios declarada por escrito | `pages/panel/` | Recorrido sobre el doble de señales; `test_no_hay_seccion_vacia_de_juicios` | RF-PAN-07 | **VF-01**, **VF-02** |
| D-08 | Lector: versiones con su estado y recuento, con el estado antes que el texto | `pages/borradores/` | Recorrido sobre dobles de versiones | RF-LEC-01 | **VF-02** |
| D-09 | Lector: lectura maquetada como prosa, con la vista técnica en otra pestaña y no por defecto | `pages/borradores/` | Capturas revisadas por la persona autora; `test_vista_tecnica_no_es_la_predeterminada` | RF-LEC-02 | **VF-10** |
| D-10 | Lector: diff por palabra entre dos versiones cualesquiera, legible en escala de grises | `pages/borradores/` | `test_diff_sobre_pares_conocidos` más inspección del diff sin color | RF-LEC-03, RF-UI-05 | **VF-10** |
| D-11 | Lector: `Procedencia`, hechos declarados y canonizados, y ningún control de edición de prosa | `pages/borradores/` | `test_no_hay_control_de_edicion_de_prosa` | RF-LEC-04, RF-LEC-05 | **VF-02** |
| D-12 | Editor: listados de las clases de canon que el contrato publica, con la revisión de canon vigente a la vista | `pages/canon/` | Recorrido sobre los dobles de lectura disponibles; las ausentes se declaran no publicadas | RF-CAN-01 | **VF-02** |
| D-13 | Editor: desplegables poblados del `enum` del contrato o de la operación de vocabularios, con el valor crudo del dominio | `pages/canon/` | Un valor de `enum` añadido al doble aparece en el desplegable sin reconstruir | RF-CAN-02 | **VF-05** |
| D-14 | Editor: el envío nunca se bloquea por criterio propio; el `422` se muestra junto al campo que lo provocó | `pages/canon/` | `test_envio_no_se_bloquea_y_el_422_se_ve_junto_al_campo` | RF-CAN-03 | **VF-04**, **VF-11** |
| D-15 | Editor: esqueleto de `Escena` con al menos un `renderiza` y `hechos_requeridos` de primera clase, con su recuento a la vista | `pages/canon/` | `test_recuento_de_hechos_requeridos_visible` | RF-CAN-04 | **VF-02** |
| D-16 | Editor: hechos siempre con su intervalo, nunca como atributo de una entidad, y línea temporal por `posicion_en_historia` | `pages/canon/` | `test_la_ficha_de_personaje_no_lista_dimensiones_variables`; el intervalo se pinta tal como llega, sin calcular vigencia | RF-CAN-05 | **VF-04** |
| D-17 | Editor: catálogo de predicados en solo lectura, diciendo que se amplía por migración y no por formulario | `pages/canon/` | Recorrido sobre el doble del catálogo; `test_no_hay_formulario_de_predicado` | RF-CAN-06 | **VF-02** |

**D-16 no implementa ninguna regla de vigencia.** Pinta el intervalo que viene en la
respuesta. Si en algún momento hiciera falta decidir en el cliente si un hecho sigue
vigente, el paso está mal planteado y vuelve a la spec: es exactamente FF-04.

---

## 7. Fase E · Comportamiento de la interfaz y cierre

| # | Paso | Módulos | Test que lo demuestra | Requisitos | Cobra |
| --- | --- | --- | --- | --- | --- |
| E-01 | Separar estado de dominio y estado de interfaz; parchear los nodos existentes en vez de reconstruir la vista | `app/`, `pages/` | Recorrido con tres paneles abiertos y un formulario a medio escribir, más tres refrescos de datos | RF-UI-01 | **VF-03** |
| E-02 | Conservar lo desplegado, la pestaña activa y lo escrito ante una recarga de página, sin persistir canon | `app/`, `shared/` | El recorrido de E-01 más una recarga; `test_sin_canon_en_almacenamiento_local` | RF-UI-02, RF-NF-03 | **VF-03**, **VF-04** |
| E-03 | Avisos que no se autodestruyen, con cierre por aviso y «limpiar todo» | `shared/ui/`, `app/` | `test_sin_temporizador_que_cierre_avisos`; el aviso sigue presente tras la espera | RF-UI-03 | **VF-09** |
| E-04 | Estados vacíos que distinguen «no hay nada» de «no he podido leer» en todas las vistas de lectura | `pages/`, `shared/ui/` | Dos dobles por vista —respuesta vacía y error de transporte— y dos pantallas distintas | RF-UI-04 | **VF-02** |
| E-05 | Accesibilidad mínima: foco visible, recorrido por teclado en formularios y diálogos | `frontend/` | Recorrido por teclado más inspección | RF-UI-05 | Inspección: avisa, no bloquea el cierre |
| E-06 | **Recorrido de sistema**: el recorrido de SPEC-002 §3.2 de extremo a extremo con Playwright contra las dos mitades | Todos | El único que cruza la frontera; declarado como excepción y excluido de VF-14 | Criterios 1–5 | SPEC-002 §8.2 |
| E-07 | Llevar FF-01…FF-14 y VF-01…VF-14 a `docs/verification.md` con su columna de frontera, sin dejar referencias colgando | `docs/` | La puerta *Spec y docs al día* de `AGENTS.md` §10.5; recuento de referencias cruzadas rotas en cero | Criterio 10 | Inspección |
| E-08 | Cierre documental: `CLAUDE.md` §6 con los comandos reales y la fila de `architecture.md` sobre el frontend como consumidor generado | `docs/`, `CLAUDE.md` | Los comandos del documento se ejecutan tal como están escritos | SPEC-002 §9.1 | Tubería |
| E-09 | Actualizar SPEC-002 con lo que realmente se construyó y cada desviación con su motivo | `specs/` | Inspección: ninguna desviación sin motivo; las DEP que siguieran ausentes, nombradas | Criterio 11 | Inspección |

**Si E-06 falla**, lo primero es decidir de qué mitad viene el fallo **antes** de tocar nada.
Si es del backend, el arreglo va a su spec y a su suite, no a este recorrido y no al
frontend. Un recorrido de sistema que se arregla parcheando la vista deja de ser una
comprobación y pasa a ser un disfraz.

---

## 8. Qué fijan las decisiones ya cerradas

SPEC-002 §9.3 cierra cinco decisiones. Ningún paso queda bloqueado por ellas; lo que cambia
es que al llegar ya no admiten discusión.

| Decisión de SPEC-002 §9.3 | Qué fija | Paso |
| --- | --- | --- |
| Valores crudos en los desplegables | D-13 no espera a ninguna capa de traducción, y no se crea | D-13 |
| «Sin reglas de dominio» por análisis estático declarado | A-05 y A-06 se escriben como puertas, no como nota de revisión | A-05, A-06 |
| Accesibilidad que avisa y no bloquea | E-05 implementa el mínimo y su comprobación no para el cierre | E-05 |
| Sin `entities/` ni `features/` | A-02 fija tres capas y la puerta las hace cumplir | A-02 |
| Dobles generados del contrato | B-03 no admite un doble escrito a mano, por cómodo que resulte | B-03 |

---

## 9. Migraciones

**Ninguna.** Este plan no toca `backend/`, ni el esquema de SQLite, ni el canon almacenado.
Si en algún paso apareciera la necesidad de una columna, una ruta o un campo nuevo en el
contrato, no se resuelve aquí: se anota como dependencia de SPEC-002 §3.3 y se lleva a la
spec del backend. Un plan que decide alcance es una spec encubierta que nadie aprobó.

---

## 10. Riesgos del plan y marcha atrás

| Paso | Si no sale | Marcha atrás |
| --- | --- | --- |
| Paso 0 | El contrato no cumple RC-01…RC-08 | Bloqueo declarado: se anota qué requisito falta y se espera a la otra mitad. No se genera contra un documento que no sirve de contrato, y no se parchea el cliente |
| Paso 0.7 | Faltan operaciones de §3.3 | La vista declara *no publicada por el contrato* y el paso queda parcial con su DEP citada. No se simula ni se apaña desde el cliente |
| A-05 | Algún vocabulario no llega por `enum` y el desplegable se queda sin fuente | Se puebla solo desde la operación de vocabularios, sin tipo derivado, y se anota como desviación. Transcribirlo sigue prohibido |
| B-01 | El generador produce tipos laxos o no soporta algo del documento | Se corrige el documento en la otra mitad, nunca el código generado. Es un fallo de RC-03 |
| B-03 | Mantener los dobles resulta más caro que arrancar el backend | Es la tentación que VF-14 existe para frenar. Antes de ceder se mide; si se cede, cambia el sujeto de la suite y eso vuelve a la spec |
| C-03 | El cierre del flujo de eventos deja conexiones colgando y no se reproduce en el doble | Se acota el recorrido a montar y desmontar en bucle contando conexiones, que es lo que VF-13 exige, en vez de perseguirlo en el navegador real |
| D-09 | La maquetación no convence a quien la lee | Es inspección humana por diseño y no admite umbral: se vuelve a maquetar hasta que la persona autora lo apruebe. No se sustituye por una métrica |
| E-01 | Conservar el estado de interfaz obliga a rehacer la gestión de estado entera | Se acota a lo que VF-03 comprueba —paneles, pestaña activa y formulario a medio escribir— en lugar de generalizar |
| E-06 | El recorrido completo no cierra | Se mira primero si el fallo es del backend: el cliente de modelo real sigue sin cablearse (desviación 1 de SPEC-001) y el recorrido corre sobre uno falso |

---

## 11. Lo que este plan no cubre

- **Nada de `backend/`.** Ni el contrato, ni las rutas de SPEC-002 §3.3, ni la resolución de
  escalado. Tienen su spec y su plan, y este documento solo las consume.
- Todo lo que SPEC-002 §2.4 deja fuera sigue fuera: sin autenticación, sin paginación, sin
  panel de juicios, sin tema visual y sin despliegue.
- No fija estimaciones de tiempo. El orden es una dependencia, no un calendario.
- No elige herramientas concretas de generación, de dobles ni de análisis de capas: se
  deciden en su paso y se registran si resultan no triviales.
- No salta la puerta siguiente. Aunque este plan se apruebe, cada paso empieza por su test
  en rojo, visto fallar **por el motivo correcto** (`AGENTS.md` §10.4): un paso que se
  implementa primero y se cubre después documenta lo que hay, no comprueba lo que se pidió.
