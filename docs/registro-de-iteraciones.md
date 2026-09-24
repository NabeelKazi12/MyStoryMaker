# Registro de iteraciones: qué cambió, por qué y qué lo provocó

2026-09-23 · SPEC-003 RF-EVA-05

## Qué contiene este documento

Un log de decisiones con causa y efecto, no un diario. Cada fila responde a tres cosas:
qué lo provocó —un test en rojo, un contraejemplo, una revisión—, qué cambió y por qué
ese cambio y no otro. Lo que no está aquí es el relato de la sesión: si una fila no
cambió el sistema, no es una iteración.

---

## 1. Iteraciones provocadas por un test en rojo

| # | Qué lo provocó | Qué cambió | Por qué así |
| --- | --- | --- | --- |
| I-01 | `test_un_hecho_registra_los_capitulos_en_que_se_usa` falló con `FOREIGN KEY constraint failed` | Se quitó la clave foránea de `hecho_capitulo.hecho_id` hacia `hecho` | Los hechos entran al canon como eventos de cambio en `canon_cambio`, no como filas de `hecho`. La clave foránea habría hecho fallar **toda** canonización: el test encontró un supuesto equivocado del plan, no un fallo del código |
| I-02 | `test_una_entrevista_con_contradiccion_no_produce_encargo` falló: buscaba «edad» y «tono» en el mensaje | El error de `BriefIncompleto` ahora nombra el par de campos antes del detalle | Quien recibe el error tiene que saber entre qué dos respuestas suyas elegir |
| I-03 | Cinco tests de observabilidad fallaron al exigir `version_de_prompt` en spans de rol | Se corrigieron **los tests**, no la regla | La regla era la correcta: un rol sin versión de prompt rompe la atribución de resultados. Los tests estaban infraespecificados |
| I-04 | `test_cada_coincidencia_deja_fila_en_el_audit_log` falló por clave foránea | El test crea el capítulo antes de auditar | El esquema tiene razón: un rastro de auditoría que apunta a un capítulo inventado no lleva a ninguna parte |
| I-05 | `test_las_decisiones_de_la_spec_estan_registradas` esperaba 8 filas y encontró 9, luego 11 | Se actualizó la cuenta y se añadió la comprobación de que `rd-r1` y `rd-d17` **conviven** | Una decisión que desaparece del registro deja de poder contradecirse a la vista |

## 2. Iteraciones provocadas por una revisión

| # | Qué lo provocó | Qué cambió | Por qué así |
| --- | --- | --- | --- |
| I-06 | El plan decía «tabla de cronología» | Se implementó como **vista** | Una copia obliga a sincronizarla y al desincronizarse Lean verifica una historia distinta de la que se lee. Anotado como desviación y registrado en `rd-d19` |
| I-07 | La spec marcaba «variantes simples» del guardarraíl como no comprobable | Se cerró la lista en tres transformaciones | Marcar algo como no verificable obliga a decidir qué se hace con ello; se decidió acotarlo en lugar de aceptarlo como riesgo |
| I-08 | Revisión del validador de nombres | Se decidió que **no** exija que el destinatario aparezca | Que aparezca lo cobra otro validador; dos validadores con la misma pregunta dejan sin decidir cuál manda |
| I-09 | El techo de 100.000 estaba declarado en tres sitios y aplicado en uno | `MAXIMO_DE_ENTRADA` pasó de constante muerta a límite, y el worker mide el prompt antes de enviarlo | Un techo que solo está escrito no es un techo |

## 3. Contraejemplos de TLC y fallos de Lean

| # | Herramienta | Estado |
| --- | --- | --- |
| I-10 | TLC sobre `tla/Generacion.tla` | **Sin ejecutar en este entorno**: no hay Java instalado. La especificación y su `.cfg` están commiteadas y el modelo es de 5 capítulos y 2 reintentos. Cualquier contraejemplo que aparezca al ejecutarlo se anota aquí con el cambio que provoque en el código |
| I-11 | `lake build` sobre `lean/` | **Sin ejecutar en este entorno**: no hay `lake` instalado. El proyecto, los invariantes y el generador están commiteados, y `tests/test_formal.py` comprueba que el fichero generado refleja la cronología de SQLite |
| I-12 | Incoherencia temporal sembrada | **Detectada**: `incoherencias_detectables` la caza y ningún otro validador lo hace. Es el caso que RF-LEAN-05 pide enseñar, documentado en `evaluacion.md` §3 |

La distinción entre I-10/I-11 y I-12 importa: lo segundo demuestra que **el fallo existe y
se puede detectar**; lo primero es la ejecución de la herramienta formal, que queda
pendiente de una máquina con el toolchain.
