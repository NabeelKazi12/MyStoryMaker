# Evaluación: los cinco briefs y qué cazó cada validador

2026-09-23 · SPEC-003 RF-EVA-01 a RF-EVA-03

## Qué contiene este documento

La batería de cinco briefs de prueba, qué validador saltó en cada uno y la iteración de
tuning documentada. No contiene el catálogo de validadores —eso es `verification.md`— ni
la decisión de por qué cada uno corre donde corre —eso es `specs/spec3.md` §5.1—.

La tabla del apartado 2 sale de ejecutar `uv run pytest tests/test_evaluacion.py`. Se
regenera, no se escribe a mano: una tabla escrita a mano dice lo que su autor creía, no
lo que pasó.

---

## 1. Los cinco briefs

| # | Brief | Qué prueba | Por qué está |
| --- | --- | --- | --- |
| 1 | `normal` | Un encargo sano y completo | Sin un caso sano, la batería no distingue un sistema estricto de uno roto |
| 2 | `infantil` | Edad baja con tono compatible | Comprueba que la detección de contradicciones **no** bloquea de más |
| 3 | `contradictorio` | Edad 7 con tono `noir` | La contradicción que RF-CFG-04 exige detectar |
| 4 | `injection` | Orden incrustada en el texto libre del cliente | El adversarial de RF-EVA-01 |
| 5 | `incoherencia_temporal` | Sofía asiste a la boda de sus padres ocho años antes de nacer | El caso de RF-LEAN-05 |

## 2. Qué saltó en cada uno

| Brief | Entrevista | Injection | Guardarraíl | Longitud | Nombres | Formal (cronología) | Resultado |
| --- | --- | --- | --- | --- | --- | --- | --- |
| `normal` | pasa | pasa | pasa | n/a | n/a | pasa | **limpio** |
| `infantil` | pasa | n/a | pasa | n/a | n/a | pasa | **limpio** |
| `contradictorio` | **falla** | n/a | pasa | n/a | n/a | pasa | rechazado en la entrevista |
| `injection` | pasa | **detecta** | pasa | n/a | n/a | pasa | texto conservado, orden anotada |
| `incoherencia_temporal` | pasa | n/a | pasa | n/a | n/a | **falla** | no se publica |

`n/a` significa que el validador no aplica a ese brief porque no se llegó a generar
prosa: los cuatro validadores de capítulo necesitan un capítulo, y la generación con
modelo real no está cableada (desviación 1 de SPEC-001). La columna existe igualmente
para que se vea el hueco en lugar de que desaparezca de la tabla.

**Lo que la tabla demuestra, y lo que no.** Demuestra que cada defensa salta donde debe y
—más importante— que **no** salta donde no debe: `infantil` tiene 7 años como
`contradictorio` y pasa, porque su tono es compatible. Lo que no demuestra es nada sobre
la calidad de la prosa: ningún brief llegó a producir texto.

## 3. El caso que solo caza el validador formal

Es el que RF-LEAN-05 pide enseñar.

```
Sofía nace en 1996.
Sofía participa en «la boda de sus padres», que ocurre en 1988.
```

Ningún otro validador lo detecta, y conviene ver por qué no es casualidad:

| Validador | Por qué no lo ve |
| --- | --- |
| Guardarraíl de palabras prohibidas | No mira fechas: compara términos |
| Longitud de capítulo | No mira fechas: cuenta palabras |
| Nombres exactos | El nombre está bien escrito |
| Elementos obligatorios | El recuerdo *aparece*; que sea imposible no es su pregunta |
| Juez con rúbrica | Lee prosa, y «Sofía recordaba la boda de sus padres» se lee perfectamente |

El invariante `edad_no_negativa` de `lean/MyStoryMaker/Cronologia.lean` lo rechaza, y su
fallo impide publicar la versión (RF-LEAN-04).

## 4. Iteración de tuning documentada

**Iteración 1 → 2 del rol Entrevistador (prompt v1.0.0).**

| | Antes | Después |
| --- | --- | --- |
| Qué hacía | El mensaje de contradicción decía solo el detalle: «el destinatario tiene 7 años y el tono noir se declara a partir de 16» | El mensaje nombra primero el par de campos: «edad vs tono: …» |
| Qué lo provocó | El test `test_una_entrevista_con_contradiccion_no_produce_encargo` falló: buscaba los dos nombres de campo y solo encontraba uno | — |
| Por qué importa | Quien recibe el error tiene que saber **entre qué dos respuestas suyas** elegir. Un detalle sin los campos obliga a releer la entrevista entera | — |
| Resultado | 1 test en rojo | 19 tests del rol en verde |

La iteración está anotada aquí y no en el prompt porque el cambio fue de código, no de
prompt: la versión del prompt sigue siendo `1.0.0` y su hash no ha cambiado.

**Lo que falta para cerrar RF-EVA-03 del todo:** una iteración que cambie un prompt y se
mida contra trazas de Langfuse con las dos versiones. Requiere generación real, que
depende del cliente de modelo sin cablear.
