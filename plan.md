# Plan de implementación del backend — SPEC-001

| | |
| --- | --- |
| **Identificador** | PLAN-001 |
| **Spec de la que cuelga** | `specs/spec1.md` (SPEC-001), `aprobada` el 2026-09-22 por @Nabeel |
| **Estado** | `aprobado` el 2026-09-22 y **ejecutado**. Fases A–E construidas y auditadas fila por fila en una segunda pasada |
| **Alcance** | Fase 1 de `docs/architecture.md` §13, más el DAG mínimo y el semáforo de crédito con concurrencia 1 |
| **Fuente canónica** | `specs/spec1.md` §13. Este documento es una **lectura derivada** de aquel apartado, ampliada con lo que cada paso dejó realmente en el repositorio |
| **Resultado** | 213 tests en verde · ~3.240 líneas en `backend/` · 14 paquetes · 1 migración · 12 verificadores · 4 puertas |

> `AGENTS.md` §10.3 obliga a que el plan viva en el apartado final de la propia spec, para
> que el qué y el cómo no puedan divergir en dos documentos. Ese sigue siendo el original:
> `specs/spec1.md` §13. Este `plan.md` no lo sustituye ni lo modifica; lo reexpone con la
> traza de ejecución. Si ambos discrepan, manda la spec.

---

## 1. La cadena que hubo que recorrer antes de escribir código

`AGENTS.md` §10 no admite atajos: cada flecha es una puerta bloqueante y quien aprueba es
siempre una persona, nunca el agente que redactó el artefacto.

```
docs/  ──►  specs/  ──►  plan de implementación  ──►  código
            aprobada        aprobado                  TDD
                                                       │
                                └──────────────────────┘
                                  cierre: spec y docs al día
```

| Puerta (`AGENTS.md` §10.5) | Condición de paso | Cómo se superó |
| --- | --- | --- |
| `docs/` acordados | Cuatro documentos de referencia sin contradicciones ni referencias rotas | `definitions.md`, `domain-knowledge.md`, `architecture.md` y `verification.md`, en su estado del 2026-09-22 |
| *Spec aprobada* | Apartado *Preguntas abiertas* vacío y **todos** los requisitos con verificación asignada | 102 requisitos con `modo_de_verificación`; apartado 12 vacío; aprobada por una persona |
| *Plan aprobado* | Pasos ordenados por dependencia, cada uno con módulos, test nombrado antes de escribirlo y marcha atrás | Apartado 13 de la spec, añadido **después** de aprobarla |
| *Spec y docs al día* | El impacto declarado en §9 aplicado, y los comandos de `CLAUDE.md` §6 ejecutados tal como están escritos | Paso E8, cerrado en la segunda pasada |

## 2. Las tres decisiones que fijan el orden

El orden de los pasos **no** es el de los apartados de requisitos. Es el de las
dependencias: nada se construye antes que aquello contra lo que se comprueba.

| # | Decisión | Motivo |
| --- | --- | --- |
| 1 | La **puerta de análisis estático de los límites de módulo va primero**, en el paso A1 | Si las reglas de dependencia de `architecture.md` §2.3 no se comprueban desde el primer commit, son una convención, y las convenciones no sobreviven al primer atajo. Cazó tres violaciones propias durante la ejecución |
| 2 | La **fase de verificación va antes que la de generación** | Hasta que no existe lo que bloquea, no hay nada capaz de parar una escena mala. Generar primero habría producido texto plausible sin nada que lo contrastara |
| 3 | El **orden es una dependencia, no un calendario** | El plan no fija estimaciones de tiempo |

El ciclo de cada paso es el TDD de `AGENTS.md` §10.4: rojo, verde, refactor, con el test
visto fallar **por el motivo correcto** antes de implementar nada (RNF-07). Un invariante
sin test no existe (`CLAUDE.md` §7.1).

---

## 3. Fase A · Cimientos

Sin invocación de modelo. Al final de la fase existe el canon y se puede consultar.

| # | Paso | Módulos | Test que lo demuestra | Requisitos |
| --- | --- | --- | --- | --- |
| A1 | Esqueleto del paquete y puerta de análisis estático de los límites de módulo | `backend/` | `test_paquete_respeta_sus_limites`, `test_ningun_rol_importa_de_otro_rol`, `test_el_esqueleto_de_paquetes_esta_completo` | RNF-01 a RNF-03, RNF-06, RF-STO-04, RF-QUA-15, RF-API-06, RF-API-07 |
| A2 | Enumeraciones cerradas del dominio | `domain/vocabularies.py` | `test_rechaza_un_valor_no_declarado`, `test_los_valores_son_los_de_definitions` | RF-DOM-03 |
| A3 | Plano diegético: `Entidad`, `Personaje`, `Lugar`, `EventoNarrativo`, `Hecho` | `domain/diegetic/canon.py` | `test_hecho_exige_valido_desde`, `test_ninguna_entidad_expone_dimensiones_variables`, `test_evento_no_se_causa_a_si_mismo` | RF-DOM-01 parcial, RF-DOM-06, RF-DOM-07 |
| A4 | Plano discursivo y de producción, más `Volumen` | `domain/discursive/`, `domain/production/`, `domain/spec/` | `test_escena_con_valor_entrada_igual_a_salida_falla`, `test_escena_sin_evento_renderizado_falla`, `test_hilo_exige_pregunta_dramatica` | RF-DOM-01, RF-DOM-02, RF-DOM-04, RF-DOM-05 |
| A5 | Mensajes de error en español, nombrando clase e invariante violado | `domain/errors.py` | `test_los_mensajes_nombran_clase_e_invariante` | RF-DOM-08 |
| A6 | Migración inicial: esquema, índices obligatorios y siembra del catálogo `PREDICADO` | `migrations/versions/0001_esquema_inicial.py` | `test_la_migracion_sella_su_version`, `test_estan_las_tablas_del_modelo_de_datos`, `test_estan_los_indices_obligatorios`, `test_el_catalogo_de_predicados_viene_sembrado` | RF-STO-02, RF-STO-03, RF-STO-09, RF-STO-10 |
| A7 | Factoría única de conexiones con WAL y claves foráneas | `store/database.py` | `test_toda_conexion_lleva_wal_y_claves_foraneas` | RF-STO-01 |
| A8 | Repositorios tipados y CTEs recursivas del grafo causal | `store/repositories.py` | `test_alcanzables_recorre_el_grafo_en_profundidad`, `test_detecta_un_ciclo_indirecto` | RF-STO-04, RF-STO-08 |
| A9 | Canon versionado por eventos de cambio | `store/repositories.py` | `test_reconstruye_la_revision_n_sin_copiar_el_canon`, `test_la_revision_solo_avanza` | RF-STO-05 |
| A10 | Catálogo de predicados y su exclusividad | `store/`, `domain/` | `test_un_predicado_no_catalogado_se_rechaza`, `test_el_catalogo_declara_la_exclusividad` | RF-STO-07 |

**Lo que dejó** (commit `3a865ad`): 14 paquetes, 16 vocabularios cerrados, 20 clases de
dominio inmutables con sus invariantes en `__post_init__`, 30 tablas por migración, 9
predicados sembrados. **84 tests en verde.**

**Hallazgo del camino.** `alembic upgrade head` terminaba con código 0 sin escribir el
sello de versión ni las filas sembradas: SQLAlchemy 2.0 descarta la transacción al cerrar
y el DDL sobrevivía solo por el autocommit de SQLite. Ahora tiene test. Los invariantes se
duplican en el esquema y no solo en el dominio, para que una escritura directa a la base
no pueda esquivarlos.

---

## 4. Fase B · Verificación determinista

| # | Paso | Módulos | Test que lo demuestra | Requisitos |
| --- | --- | --- | --- | --- |
| B1 | Corpus de casos sembrados: un par por verificador, defecto conocido y caso intacto | `tests/corpus.py`, `tests/conftest.py` | El corpus es el insumo de B2–B5; cada par difiere en **una sola** dimensión | Bloque A9 de la spec §2.2 |
| B2 | Verificadores de escena: contradicción, ciclos, precedencia, cambio de valor, borrador único | `quality/verificadores.py` | `test_detecta_<dimension>` y `test_no_inventa_<dimension>` por par | RF-QUA-01 a RF-QUA-05 |
| B3 | Verificadores de alcance local y global | `quality/verificadores.py` | `test_detecta_tetragrama_repetido`, `test_detecta_hilo_principal_inactivo`, `test_detecta_vocabulario_prohibido`, y sus `no_inventa` | RF-QUA-06 a RF-QUA-09, RF-QUA-16, RF-QUA-17, RF-QUA-21, RF-QUA-22 |
| B4 | Forma del `Defecto`, evidencia citable y descarte contado | `quality/defectos.py` | `test_un_defecto_sin_evidencia_se_descarta_y_se_cuenta`, `test_un_defecto_de_dimension_E_sin_bloque_declarado_se_descarta` | RF-QUA-10, RF-QUA-19 |
| B5 | Las cuatro puertas y la evidencia ausente | `quality/puertas.py` | `test_una_puerta_sin_defectos_no_esta_superada_si_le_falta_evidencia`, `test_un_bloque_de_extraccion_vacio_no_da_una_escena_limpia` | RF-QUA-11 a RF-QUA-14, RF-QUA-18, RF-QUA-20 |
| B6 | Pruebas de mutación sobre `quality/`, con autoridad de advertencia | Tubería de CI | Informe de mutantes supervivientes por dimensión | §8.4 de la spec |

**Lo que dejó** (commit `fb50709`): 12 verificadores, cada uno con su par *detecta* /
*no inventa*; 4 puertas; 33 tests nuevos de calidad.

**La decisión que ordena las puertas** es el principio 8 de `architecture.md`: la ausencia
de evidencia nunca se convierte en evidencia favorable. Una puerta no devuelve un booleano
—un booleano no distingue *limpia* de *no encontré nada porque no miré*—. Los tres
invariantes bloqueantes que v1 no implementa (fuga epistémica, disciplina de POV,
consistencia de tiempo y persona) salen como **evidencia ausente** en toda puerta que los
cobraría, y un bloque de extracción vacío tampoco da una escena limpia: es F-01 de
`verification.md` §11.

**Hallazgo del camino.** La puerta de A1 cazó un fallo propio: `quality` importaba
`sqlite3`, violando la regla 4. Las consultas se movieron a `store` como datos tipados, de
forma que los verificadores se prueban sin base de datos.

**No ejecutado.** B6 no se llegó a montar: no hay tubería de CI en el repositorio y la
puerta de límites de A1 vive como test de la suite, no como paso de CI. Su autoridad era
de advertencia, así que no bloquea ningún criterio de aceptación, pero queda pendiente.

---

## 5. Fase C · Contexto

| # | Paso | Módulos | Test que lo demuestra | Requisitos |
| --- | --- | --- | --- | --- |
| C1 | Ensamblado en el orden de componentes del contrato de rol y recuento por componente | `context/ensamblado.py` | `test_el_paquete_sale_en_el_orden_del_contrato_de_rol`, `test_el_recuento_guardado_coincide_con_lo_contado` | RF-CTX-01, RF-CTX-02 |
| C2 | Filtro temporal, punto de inserción explícito del epistémico y filtro estructural | `context/filtros.py` | `test_un_hecho_invalidado_antes_del_momento_no_entra`, `test_el_filtro_epistemico_existe_y_en_v1_no_filtra` | RF-CTX-05 |
| C3 | Presupuesto, orden de recorte fijo y bloqueo con `falta` | `context/presupuesto.py` | `test_un_paquete_que_no_cabe_no_se_trunca_sino_que_bloquea`, `test_los_tres_intocables_no_se_recortan_nunca` | RF-CTX-03, RF-CTX-04, RF-CTX-08 |
| C4 | `hash` estable y referencia a la revisión de canon | `context/ensamblado.py` | `test_mismo_canon_y_misma_escena_dan_el_mismo_hash`, `test_otra_revision_de_canon_da_otro_hash` | RF-CTX-06 |
| C5 | Reconstrucción entera por intento, sin historial acumulativo | `context/` | `test_el_paquete_del_intento_2_no_contiene_el_borrador_rechazado`, `test_el_paquete_no_crece_con_la_longitud_del_libro` | RF-CTX-07 |

El filtro epistémico se construye **con su punto de inserción explícito aunque en v1 no
filtre**: cuando llegue la fase 2 no habrá que discutir dónde va.

---

## 6. Fase D · Orquestación y canonización

| # | Paso | Módulos | Test que lo demuestra | Requisitos |
| --- | --- | --- | --- | --- |
| D1 | `Plan` como DAG persistido y bucle de reconciliación | `orchestrator/plan.py` | `test_un_plan_ciclico_se_rechaza_entero`, `test_una_tarea_se_lista_solo_con_sus_dependencias_aceptadas`, `test_la_reconciliacion_es_determinista` | RF-ORQ-01, RF-ORQ-02, RF-ORQ-22 |
| D2 | Máquina de estados de `Tarea` e historial tipificado de intentos | `orchestrator/estados.py`, `store/` | `test_todo_camino_de_la_maquina_termina`, `test_los_terminales_no_tienen_salida`, `test_recuento_de_palabras_es_derivado` | RF-ORQ-03, RF-ORQ-04, RF-ORQ-24, RF-STO-06 |
| D3 | Clasificación de fallos, escalera de reintentos y salto a replanificación | `orchestrator/estados.py` | `test_solo_contrato_y_contenido_suman_intento_narrativo`, `test_dos_defectos_iguales_saltan_directamente_a_replanificacion`, `test_un_corte_de_red_no_gasta_la_escalera` | RF-ORQ-05 a RF-ORQ-07, RF-ORQ-20, RF-ORQ-23 |
| D4 | Semáforo de crédito, cola por prioridad con envejecimiento y los tres timeouts | `orchestrator/admision.py` | `test_el_credito_vuelve_al_inicial_en_toda_ruta_de_salida`, `test_una_reserva_mayor_que_el_credito_se_rechaza_sin_encolar`, `test_los_tres_niveles_de_timeout_tienen_valor_y_orden` | RF-ORQ-08 a RF-ORQ-12, RNF-04 |
| D5 | Matriz de permisos, idempotencia y reanudación | `orchestrator/permisos.py`, `orchestrator/ejecucion.py` | `test_un_rol_no_puede_escribir_una_clase_ajena`, `test_ningun_rol_genera_y_valida_a_la_vez`, `test_reejecutar_con_la_misma_clave_devuelve_el_artefacto` | RF-ORQ-13 a RF-ORQ-15, RF-ORQ-21 |
| D6 | Cancelación en cascada, descarte por revisión superada y eventos de transición | `orchestrator/ejecucion.py` | `test_cancelar_alcanza_el_subarbol_y_no_borra_nada`, `test_un_resultado_contra_una_revision_superada_se_descarta`, `test_una_transicion_emite_su_evento` | RF-ORQ-16 a RF-ORQ-19 |
| D7 | Canonización: normaliza, contrasta, promueve, incrementa revisión y cascada | `orchestrator/canonize.py` | `test_una_sucesion_legitima_cierra_el_intervalo_anterior`, `test_una_contradiccion_genera_defecto_y_no_toca_el_canon`, `test_un_duplicado_exacto_no_se_inserta` | RF-CAN-01 a RF-CAN-06 |

La canonización distingue **sucesión legítima de contradicción** y nunca sobrescribe
canon: un hecho nuevo cierra el intervalo del anterior o genera defecto, pero no pisa lo
ya promovido.

---

## 7. Fase E · Worker, API y cierre

| # | Paso | Módulos | Test que lo demuestra | Requisitos |
| --- | --- | --- | --- | --- |
| E1 | Worker sin estado, con clasificación precisa de su fallo | `worker/worker.py` | `test_el_worker_no_devuelve_ningun_estado_de_tarea`, `test_una_salida_truncada_al_techo_es_fallo_de_contrato` | RF-WRK-01, RF-WRK-02, RF-WRK-04 |
| E2 | Rol Redactor: prompt versionado e invocación con los parámetros de R-1 | `agents/redactor/`, `prompts/v1.0.0.md` | `test_el_max_tokens_es_el_techo_declarado_y_no_uno_mayor`, `test_la_salida_valida_se_convierte_en_objeto_tipado` | RF-WRK-06, RF-WRK-09 |
| E3 | `Procedencia` en cada invocación y registros sin prosa | `worker/`, `store/` | `test_el_worker_devuelve_procedencia_tambien_cuando_falla`, `test_ningun_registro_de_ejecucion_contiene_prosa` | RF-WRK-03, RF-WRK-08 |
| E4 | `contexto_insuficiente` y detección de prompt editado sin versionar | `worker/`, `agents/redactor/` | `test_contexto_insuficiente_devuelve_su_falta_y_no_prosa`, `test_un_prompt_editado_sin_subir_version_se_detecta` | RF-WRK-05, RF-WRK-07 |
| E5 | API de altas y lectura, con `422` en campos obligatorios | `api/main.py` | `test_una_escena_sin_un_campo_obligatorio_da_422`, `test_una_escena_sin_cambio_de_valor_da_422` | RF-API-01, RF-API-02, RF-API-05, RF-API-06 |
| E6 | Encolado con `202` y SSE de transiciones | `api/main.py` | `test_pedir_redaccion_devuelve_202_con_id_de_tarea`, `test_el_flujo_de_eventos_es_event_stream` | RF-API-03, RF-API-04, RF-API-07 |
| E7 | **Cierre**: bucle de extremo a extremo y las cinco señales | Todos | `test_el_bucle_completo_acepta_y_canoniza`, `test_las_cinco_senales_se_leen_de_lo_ya_registrado` | RNF-05, criterios de aceptación |
| E8 | Actualizar spec y `docs/` según el impacto declarado | `specs/`, `docs/` | Puerta *Spec y docs al día* más los comandos de `CLAUDE.md` §6 | RNF-08, criterio 10 |

**Lo que dejó** (commit `81e4a24`, fases C+D+E): el bucle cierra de extremo a extremo.
**196 tests en verde** y los comandos de `CLAUDE.md` §6 funcionando, incluidos `alembic`,
la API y el worker.

**El cliente de modelo está detrás de un protocolo a propósito**: sin él, E7 no se podría
ejecutar ni probar sin credenciales, y el sistema solo se sabría roto la primera vez que
alguien pagara por descubrirlo.

**Hallazgo del camino.** La puerta de límites volvió a cazar dos fallos propios: `api` y
`orchestrator` importaban `sqlite3`. El `store` exporta ahora el tipo de conexión, así que
el resto del sistema habla de *una conexión que le dan* y no de SQLite, y la regla 4 se
sostiene también en las anotaciones de tipo.

---

## 8. Segunda pasada · auditoría del plan fila por fila

Una revisión del plan paso a paso encontró que **tres pasos se habían dado por cerrados
con solo su primera mitad hecha**. Los tests pasaban porque probaban lo que sí se había
construido. Es el modo de fallo que justifica auditar el plan contra el código y no contra
la suite.

| Requisito | Lo que faltaba | Cómo se cerró |
| --- | --- | --- |
| RF-ORQ-13 | Idempotencia declarada pero sin clave | Clave de seis campos: reejecutar devuelve el artefacto en lugar de volver a pagar la invocación |
| RF-ORQ-14 | Reanudación sin recuperar lo que quedó en curso | Al arrancar se distingue la invocación que no llegó a registrarse de la que se pagó y se perdió |
| RF-ORQ-16 | La cancelación borraba en vez de marcar | Marca obsoleto: borrar destruiría la única evidencia de por qué se llegó hasta ahí |
| RF-ORQ-17 | Sin descarte por revisión superada | El resultado generado contra una revisión ya superada se descarta |
| RF-ORQ-19 | La tabla de transiciones existía vacía | Se escriben las transiciones; sin ellas el endpoint SSE no podía emitir nada |
| RF-WRK-07 | Hash del prompt sin anclar | Cada prompt queda anclado a su versión en un manifiesto |
| RNF-05 | Señales sin fuente | Las cinco señales se leen de lo que el sistema ya escribe, no de un contador paralelo |
| E8 | No se había hecho | `definitions.md` gana la clase `Predicado` y el vocabulario `exclusividad_de_predicado`; el diagrama 8 gana `PREDICADO` y su arista con `HECHO`; la migración siembra los ocho `RegistroDeDecision` de R-1 a R-8 más el del catálogo |

**Lo que dejó** (commit `c8ba6b3`): `orchestrator/ejecucion.py`, `orchestrator/senales.py`
y 14 tests nuevos. **213 tests en verde, puerta de límites limpia y 0 referencias rotas
entre documentos.** Con esto el criterio de aceptación 8 pasa a cumplirse.

---

## 9. Migraciones

Una sola, en A6, hacia delante y sin migración de datos porque no hay canon previo. Todo
lo que la fase D añade al esquema —`TAREA_INTENTO`— entró en esa misma migración inicial y
no en una segunda: mientras no exista canon almacenado, rehacer la inicial es más barato
que encadenar migraciones. La segunda pasada aplicó el mismo criterio al ampliarla con los
`RegistroDeDecision` sembrados.

## 10. Riesgos del plan y marcha atrás

| Paso | Si no sale | Marcha atrás |
| --- | --- | --- |
| A1 | Las reglas de dependencia resultan impracticables con la estructura elegida | Se vuelve a la spec: los límites de módulo son de `architecture.md` §2.3, no negociables en el plan |
| A6 | Los nueve predicados no bastan para un `Brief` real | Ampliar el catálogo es un `RegistroDeDecision` más una migración, no un cambio de diseño |
| B1 | El corpus resulta caro de construir o poco representativo | Se reduce el par por verificador al mínimo y se siembra a partir de defectos reales en cuanto los haya |
| B2–B5 | Una dimensión no se puede expresar como predicado sobre el canon | Se declara evidencia ausente en su puerta; no se inventa un predicado débil |
| C3 | El paquete no cabe ni apretando los filtros | Es el caso previsto: `bloqueada` con `falta`. Si es sistemático, la spec cortó mal el alcance |
| D4 | El semáforo resulta insuficiente por límite de tasa del proveedor | Hace falta un regulador de tasa junto al semáforo, y eso es spec nueva |
| E2 | El modelo de R-1 no está disponible o sus cifras cambiaron | Se confirma contra la Models API antes de empezar E2, y si cambia se registra la decisión |
| E7 | El bucle no cierra por acumulación de defectos falsos | Se mira el presupuesto de falsos positivos de `verification.md` §6; si se excede, el predicado está mal escrito y vuelve a la fase B |

## 11. Desviaciones registradas

Anotadas en `specs/spec1.md` §13 según `AGENTS.md` §10.4.

| # | Desviación | Consecuencia |
| --- | --- | --- |
| 1 | El cliente de modelo real no está cableado: `construir_cliente_real` lanza `NotImplementedError` citando la salvedad de R-1, porque este entorno no tiene credenciales para confirmar el modelo contra la Models API | El bucle corre con un cliente falso que simula el **contrato**, no la calidad de la prosa |
| 2 | El recuento de tokens de `context/presupuesto.py` es una heurística, no el `count_tokens` del proveedor | Un recuento optimista convertiría el techo duro del semáforo en uno imaginario: hay que cambiarlo **antes** de invocar de verdad |
| 3 | El SSE de RF-API-04 emite el historial ya registrado, no un flujo en vivo | Seguir la tabla mientras la tarea avanza exige decidir el mecanismo de espera, que no estaba en el alcance. Las transiciones sí se escriben ya (RF-ORQ-19), así que el flujo no está vacío |
| 4 | La migración inicial se amplió en lugar de encadenar una segunda | Es lo que decidió §13.6: sin canon almacenado, rehacerla sale más barato |
| 5 | B6 (pruebas de mutación) no se ejecutó y no hay tubería de CI: la puerta de límites de A1 vive como test de la suite | Su autoridad era de advertencia, así que no bloquea ningún criterio de aceptación |

## 12. Lo que este plan no cubre

- Todo lo que el alcance de la spec §2.3 deja fuera sigue fuera: no hay pasos para ello.
  En particular `EstadoDeConocimiento`, `Narracion`, `ReglaDelMundo`, el índice vectorial,
  la `Rubrica` y el rol Juez, y los seis roles distintos del Redactor.
- Las cifras de partida —reservas de tokens, umbrales— se calibran con `Procedencia` y con
  el corpus; recalibrarlas no exige spec nueva, exige registrar la medida.
- El plan no fija estimaciones de tiempo.

## 13. Trazabilidad

| Fase | Commit | Contenido |
| --- | --- | --- |
| Aprobación | `1464dbf` | Aprobar SPEC-001 y su plan de implementación |
| A | `3a865ad` | Dominio, vocabularios cerrados, esquema y store — 84 tests |
| B | `fb50709` | Verificadores deterministas, corpus y puertas — 12 verificadores, 4 puertas |
| C, D, E | `81e4a24` | Contexto, orquestación, worker y API — 196 tests, bucle cerrado |
| Auditoría | `c8ba6b3` | Los seis requisitos que la primera pasada dejó a medias — 213 tests |

## 14. Cómo se comprueba hoy

```bash
uv sync                        # dependencias
uv run pytest                  # 213 tests
uv run pytest -m invariants    # solo invariantes de dominio
uv run ruff check . && uv run ruff format --check .
uv run mypy backend/           # strict
uv run alembic upgrade head    # migración inicial sobre SQLite

uv run uvicorn backend.api.main:app --reload   # API en :8000
uv run python -m backend.worker                # worker de generación
```
