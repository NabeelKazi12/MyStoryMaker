---
name: capitulo-verificable
description: Escribir o revisar un capítulo de MyStoryMaker de forma que los validadores puedan cobrarlo. Úsala siempre que haya que redactar prosa de novela en este repositorio, revisar un capítulo generado, decidir qué hechos declara un capítulo, o entender por qué un capítulo fue devuelto por el hook de capítulo o el de policy. Aplícala aunque el encargo diga solo "escribe el capítulo 3": lo que separa un capítulo aceptable de uno rechazado en este sistema no es el estilo, es lo que declara y lo que no nombra.
---

# Un capítulo que los validadores pueden cobrar

En MyStoryMaker un capítulo no se acepta porque esté bien escrito. Se acepta porque pasa
cuatro comprobaciones deterministas y una rúbrica. Esta skill es lo que hay que tener
delante para no chocar con las cuatro primeras, que son las que bloquean.

## Lo que se comprueba, y dónde

| Qué | Dónde corre | Qué pasa si falla |
| --- | --- | --- |
| Palabras vetadas, en tres niveles | Hook de policy, antes de aceptar | Vuelve al writer; a la cuarta, la generación se detiene |
| Longitud dentro del rango | Hook de capítulo | Vuelve al writer |
| Nombres escritos como en la story bible | Hook de capítulo | Vuelve al writer |
| Cada elemento obligatorio en algún capítulo | Puerta previa a publicar | No se publica la versión |
| Continuidad, tono, ritmo, personalización natural | Rol editor, con rúbrica | Penaliza, **no** bloquea |

## Las cinco reglas que evitan casi todos los rechazos

1. **Escribe los nombres exactamente como están en la story bible.** `Marte` por `Marta`
   es un defecto crítico, no una errata: el validador compara carácter a carácter y una
   novela de regalo que escribe mal el nombre deja de ser un regalo.
2. **Declara los hechos nuevos en el bloque, no solo en la prosa.** Lo que no se declara
   no llega al canon, y el capítulo siguiente escribirá como si nunca hubiera pasado.
3. **Si te falta contexto, dilo y para.** `contexto_insuficiente: true` con su lista
   `falta` es una respuesta válida. Inventar para rellenar produce canon fantasma, que es
   el fallo más caro de detectar porque se lee perfectamente.
4. **No metas la palabra vetada ni siquiera para negarla.** El guardarraíl normaliza
   mayúsculas, acentos y plurales: «no volvió a hablar de Ricardo» sigue siendo Ricardo.
5. **La personalización va integrada, no pegada.** Un recuerdo del destinatario metido
   como inciso explicativo pasa el validador de presencia y hunde la rúbrica.

## Lo que esta skill no decide

No dice si la prosa es buena. Eso es `juez_llm`, penaliza y no bloquea, y su puntuación
varía entre llamadas sobre el mismo texto: por eso no puede parar la línea y por eso no
hay que optimizar contra ella.
