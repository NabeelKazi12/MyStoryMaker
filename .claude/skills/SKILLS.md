# SKILLS.md

Índice de las skills de proyecto que viven en esta carpeta. Para las instrucciones
generales de trabajo, ver `CLAUDE.md`; para el contrato de los agentes que generan la
novela, `AGENTS.md`.

Una skill no es documentación: es un procedimiento que se carga **antes** de escribir, no
una referencia que se consulta después de haberse equivocado. Este fichero existe para que
se sepa cuál toca sin tener que abrir las tres.

---

## 1. Índice

| Skill | Se dispara cuando | Zona del proyecto |
| --- | --- | --- |
| [`metodologias-de-verificacion`](metodologias-de-verificacion/SKILL.md) | Hay que justificar cómo se demuestra que algo funciona | `docs/verification.md`, invariantes, `Puerta` |
| [`sqlite-vec`](sqlite-vec/SKILL.md) | Hay que guardar embeddings y consultarlos por similitud | `backend/store/`, índice vectorial de `UnidadDeContexto` |
| [`feature-sliced-design`](feature-sliced-design/SKILL.md) | Hay que decidir dónde va un fichero del frontend | `frontend/` (Vite + React) |

---

## 2. Cómo está organizado

```text
.claude/skills/
  SKILLS.md                              este índice
  metodologias-de-verificacion/SKILL.md
  sqlite-vec/SKILL.md
  feature-sliced-design/SKILL.md
```

Cada carpeta contiene el `SKILL.md` que Claude Code carga, con su `description` escrita
como condición de disparo —cuándo aplicarla, no qué contiene— y el procedimiento anclado en
los nombres reales del dominio.

Las referencias largas de cada skill (catálogos, sintaxis completa, guías de migración) no
se copian aquí: siguen en `~/.claude/skills/<nombre>/references/` y cada `SKILL.md` apunta a
las suyas en su último apartado. Se cargan una a una, cuando hacen falta.

Estas versiones de proyecto tienen precedencia sobre las del usuario con el mismo nombre.
Si el `SKILL.md` de aquí y su referencia original discrepan en un detalle técnico, manda la
referencia; lo que añade esta copia es qué significa en este repositorio.

---

## 3. Añadir una skill

Una skill entra aquí cuando cumple las tres condiciones de la regla de extracción aplicadas
a procedimientos: se ha necesitado más de una vez, tiene un criterio propio que no se deduce
de `CLAUDE.md`, y equivocarse cuesta más que leerla.

El orden es:

1. Crea `.claude/skills/<nombre>/SKILL.md` con `name` y `description` en el *frontmatter*,
   y la `description` redactada como condición de disparo.
2. Escribe el cuerpo con el mismo esqueleto que las tres anteriores: qué error evita, el
   procedimiento condensado, y **qué significa en este repositorio**, con nombres reales del
   dominio. Una sección que no llega a ese último apartado es documentación genérica y no se
   va a leer dos veces.
3. Deja las referencias largas fuera del `SKILL.md` y enlázalas al final.
4. Añade la fila correspondiente a la tabla del apartado 1.
