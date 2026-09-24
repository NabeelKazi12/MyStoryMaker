# Explainers: los conceptos del curso, aplicados a este proyecto

2026-09-23 · SPEC-003 RF-EVA-05

## Qué contiene este documento

Uno por concepto, breve, y siempre en términos de **este** repositorio: qué es, dónde
está aplicado y qué se rompería sin él. No es teoría copiada; si un explainer se pudiera
pegar en otro proyecto sin cambiar una palabra, está mal escrito.

---

## 1. Harness multiagente

Un harness es lo que convierte varias llamadas a un modelo en un proceso con estados,
reintentos y puertas. Aquí son cuatro roles —entrevistador, planner, writer, editor— que
no se llaman entre sí: la coordinación vive en `orchestrator/`, y la puerta de límites lo
hace cumplir. Sin esa separación, el rol que escribe acabaría decidiendo si lo que
escribió vale, que es el fallo que `AGENTS.md` §1 prohíbe.

## 2. Tools con schema

Una tool sin schema es una llamada que nadie comprueba: el error aparece dentro del
modelo, no en el código. En `backend/worker/tools.py` cada llamada valida obligatorios y
tipos antes de ejecutarse, y un argumento mal formado **no se reintenta**, porque repetir
la misma llamada produce el mismo error y lo paga otra vez.

## 3. Hooks

Un hook es un punto declarado donde algo corre siempre, no cuando alguien se acuerda.
Aquí hay dos: el de capítulo cobra los validadores deterministas de la prosa, y el de
policy cobra el guardarraíl. La diferencia entre ellos no es de contenido sino de
autoridad: una palabra vetada no es un defecto negociable, es una línea que el cliente
trazó.

## 4. Guardrails

Un guardrail no juzga calidad: comprueba una regla dura antes de aceptar. El de aquí
normaliza el texto y lo compara con tres listas. Lo interesante es lo que **no** hace:
no corrige. Corregir desde el guardrail produciría prosa que nadie escribió.

## 5. Validadores deterministas frente a LLM-as-judge

Los deterministas dan el mismo resultado sobre la misma entrada, así que pueden parar la
línea. El juez varía entre llamadas sobre el mismo texto, así que **penaliza y no
bloquea**: una puerta con puntuación inestable produce bucles caros de reescritura. Es la
regla que ordena `verification.md` entero.

## 6. Verificación formal de la historia (Lean 4)

Lean demuestra propiedades sobre datos, no sobre prosa. Aquí modela la cronología —quién
estaba dónde y cuándo— y prueba dos invariantes: orden temporal y edad no negativa. Vale
la pena porque hay un fallo que ningún otro validador ve: un personaje que aparece antes
de nacer se lee perfectamente.

## 7. Verificación formal del sistema (TLA+)

Mientras Lean mira la obra, TLC mira el proceso: explora todos los entrelazados posibles
de escritura, validación, reintento, caída y regeneración, y comprueba que nunca se
publica sin validar y que la reanudación no duplica ni pierde. Es lo que un test no puede
hacer, porque un test recorre un camino y el model checker los recorre todos.

## 8. Observabilidad

Trazar no es registrar por si acaso: es poder responder «cuánto costó esta novela» y «qué
versión de prompt produjo este resultado» sin reconstruir la ejecución. La regla que lo
mantiene honesto aquí es que el observador no puede ser punto único de fallo: con
Langfuse caído, la novela se escribe igual.

## 9. Memoria y contexto de tamaño constante

La novela crece y el paquete de contexto no. Se consigue reconstruyendo el paquete entero
en cada invocación desde resúmenes por capítulo, en lugar de arrastrar un historial. Es
lo que hace cierto que el paquete del capítulo 3 y el del 40 midan lo mismo, y por tanto
que el `hash` del paquete signifique algo.

## 10. Checkpoint y reanudación

Un checkpoint por capítulo permite continuar donde se cayó. Los dos fallos que evita son
simétricos y por eso la operación es idempotente: reanudar rehaciendo el último capítulo
paga dos veces la invocación; reanudar saltándoselo deja un hueco que nadie ve hasta leer
la novela entera.

## 11. Prompt injection

El texto que pega el cliente es dato, no instrucción. La defensa real no es la lista de
patrones —esa solo sirve para anotar el intento— sino el envoltorio: el texto entra
delimitado y ningún prompt lo concatena como orden. Por eso una injection redactada de
forma que ningún patrón caza sigue siendo inofensiva.
