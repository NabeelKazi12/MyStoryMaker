---
name: metodologias-de-verificacion
description: Método para decidir cómo se verifica algo en este repositorio — invariantes del dominio, requisitos, `Puerta`s y el comportamiento de los agentes —, separando la verificación a nivel de artefacto (¿el código es correcto?) de la verificación a nivel de proceso (¿el agente se comporta de forma fiable?) y clasificando cada requisito como T/A/I/D/U. Úsala siempre que aparezcan verificación, validación, estrategia de pruebas, cobertura, puertas de calidad, invariantes, evals, guardarraíles, red-teaming, observabilidad de agentes o revisión humana; y en particular al escribir o revisar `docs/verification.md`. Aplícala aunque nadie diga «metodología»: si hay que justificar cómo se demuestra que algo funciona, va antes que improvisar una lista de pruebas.
---

# Metodologías de verificación

Catálogo y método para decidir cómo se verifica algo — código generado por modelos,
invariantes, requisitos, tuberías de calidad y sistemas agénticos —, separando la
verificación a nivel de artefacto de la verificación a nivel de proceso y clasificando
cada requisito como T/A/I/D/U.

## El error que evita

Las dos familias responden a preguntas distintas y no son intercambiables. Un sistema que
solo cubre el nivel de artefacto produce código correcto invocado de forma insensata; uno
que solo cubre el nivel de proceso vigila bien un artefacto que nadie ha comprobado. Cuando
alguien pide «más tests» casi siempre falta una de las dos mitades, no más casos de la que
ya está cubierta. Empieza preguntando cuál de las dos está vacía.

## Procedimiento

1. **Enumera** requisitos, invariantes y propiedades, uno por fila. Si una fila mezcla dos
   afirmaciones, pártela: lo que no se puede fallar por separado tampoco se puede verificar
   por separado.
2. **Clasifica** cada fila como T (Test, se ejecuta y se compara la salida), A (Analysis, se
   demuestra sin ejecutar: tipos, análisis estático, verificación formal), I (Inspection,
   alguien lo mira), D (Demonstration, se observa el sistema funcionando: trazas, evals,
   despliegue progresivo) o U (Unverifiable).
3. **Asigna metodología concreta**, no la familia. «Testing» no es una asignación;
   *property-based testing sobre los intervalos de `Hecho`* sí lo es.
4. **Calibra por el coste de un fallo no detectado.** La verificación formal se paga sola
   donde un fallo silencioso corrompe estado que nadie volverá a revisar —el canon—; en un
   adaptador de presentación es dinero tirado.
5. **Separa quién bloquea de quién avisa.** Es la regla 3.6 de `CLAUDE.md` vista desde la
   verificación: una comprobación determinista puede parar la línea porque da el mismo
   resultado sobre la misma entrada; un juez basado en modelo varía entre llamadas, así que
   penaliza y prioriza, pero no bloquea.
6. **Señala los huecos.** Una tabla de verificación sin huecos declarados suele significar
   que no se ha mirado, no que no los haya.

El valor del esquema está en la última clase. Marcar algo *Unverifiable* obliga a decidir
explícitamente qué se hace con ello —reformularlo hasta que sea comprobable, o aceptarlo
como riesgo asumido— en lugar de dejarlo flotando como si estuviera cubierto. **Ninguna
fila U se queda sin decisión escrita al lado.**

## Formato de salida

Tablas, siempre: es el formato en el que estas decisiones se releen y se discuten, y fuerza
a que cada fila tenga una asignación real.

| Elemento | Nivel | Metodología | Clase | Autoridad |
| --- | --- | --- | --- | --- |
| Invariante de intervalos de `Hecho` | Artefacto | Property-based testing | T | Bloqueante |
| Comportamiento del Redactor | Proceso | Evals + trazas | D | Penaliza |

| Requisito | Clase | Decisión |
| --- | --- | --- |
| «La prosa debe sonar literaria» | U | Reformulado como umbral de rúbrica; el resto se acepta como riesgo |

## En este repositorio

`docs/verification.md` es la aplicación de esta skill al proyecto, y está organizado por
niveles, no por catálogo: §4 reparte las dimensiones de la obra, §6 dice en qué `Puerta` se
cobra cada una, §7 verifica el sistema de agentes y §8 verifica el código del repositorio.
El vocabulario que decide quién bloquea es `modo_de_verificación` de `definitions.md` —tres
valores: `programa`, `juez_llm`, `humano`—; el marco T/A/I/D/U se usa solo como columna
descriptiva en §7 y §8. Al editarlo, respeta su estructura y su numeración, añade donde
encaje y no reescribas secciones que el encargo no toca. No introduzcas dimensiones, roles
ni valores de enumeración que no estén ya en `definitions.md` y `AGENTS.md`, y termina
siempre dejando los huecos declarados en §10.

## Referencias

Referencia completa: `~/.claude/skills/metodologias-de-verificacion/references/catalogo.md`
(8 metodologías de artefacto, 10 de proceso y el marco T/A/I/D/U). Cópialas de ahí en vez de
reconstruirlas de memoria: los enlaces apuntan al trabajo fundacional o al estándar neutral
de cada metodología y es fácil sustituirlos sin querer por documentación de un proveedor.
