---
name: feature-sliced-design
description: Feature-Sliced Design v2.1 aplicado al frontend de este repositorio. Úsala cuando haya que decidir dónde va un fichero de `frontend/`, organizar la estructura por capas, colocar assets estáticos, definir APIs públicas y límites de importación, resolver *cross-imports* o el patrón `@x`, decidir si crear o eliminar una `entity` o una `feature`, o integrar FSD con Vite y React Router. Aplícala antes de crear cualquier carpeta nueva bajo `frontend/`: aquí casi nada debe subir de `pages/`, porque el dominio vive en el backend.
---

# Feature-Sliced Design

Skill oficial de Feature-Sliced Design v2.1, para organizar la estructura del frontend por
capas, decidir dónde va un fichero, colocar assets estáticos, definir APIs públicas y
límites de importación, resolver *cross-imports*, decidir si crear o eliminar una entidad, e
integrar FSD con el framework.

Principio rector: **«Start simple, extract when needed.»** La skill original está escrita en
inglés y su cuerpo, con las referencias, supera las cuatro mil líneas; lo que sigue es lo
que decide el 90 % de los casos.

## Las seis capas

```text
app/       → Inicialización, providers, routing
pages/     → Composición a nivel de ruta; tiene su propia lógica
widgets/   → Bloques de UI reutilizables (desaconsejada)
features/  → Interacciones de usuario reutilizables
entities/  → Modelos de dominio reutilizables
shared/    → Infraestructura sin lógica de negocio (UI kit, utils, cliente API)
```

**No todas las capas son obligatorias.** La mayoría de proyectos empiezan con `shared/`,
`pages/` y `app/`, y añaden `features/` y `entities/` solo cuando aportan algo. No se crean
carpetas de capa vacías «por si acaso». La capa `widgets/` está **desaconsejada** por la
referencia oficial: en código real los bloques de UI llevan *fetching*, estado y manejo de
eventos, con lo que su frontera con `features/` —que cubre los flujos de usuario— deja de
estar clara. Desaconsejada no es obsoleta: una capa `widgets/` que ya exista sigue siendo
válida.

## La regla de extracción

El código va primero a `pages/`. La duplicación entre páginas es aceptable y no obliga por
sí sola a extraer. Se extrae solo cuando se cumplen las tres:

1. El mismo código se usa en varios sitios **ahora**, no hipotéticamente.
2. Tiene un motivo de cambio independiente de cualquiera de sus consumidores.
3. La frontera tiene una responsabilidad enfocada.

**Regla de oro: en la duda, se queda en `pages/`.** Dos copias parecidas que van
divergiendo se quedan cada una en su página.

## La regla de importación

Un módulo solo importa de capas estrictamente inferiores: `app → pages → widgets →
features → entities → shared`. Las importaciones hacia arriba están prohibidas, y también
los *cross-imports* entre slices de la misma capa —salvo, como último recurso, a través de
la API pública de la otra slice (el patrón `@x`).

Cada slice exporta por su `index.ts` y los consumidores externos solo importan de ahí;
importar un fichero interno salta la API pública. `shared/` no tiene slices: define una API
pública por segmento (`shared/ui/index.ts`, `shared/api/index.ts`) en vez de un
`shared/index.ts` único.

```typescript
// Correcto
import { Button } from "@/shared/ui/Button";   // features → shared
import { LoginForm } from "@/features/auth";   // por la API pública

// Violación
import { loginUser } from "@/features/auth";              // entities → features
import { LoginForm } from "@/features/auth/ui/LoginForm"; // salta la API pública
```

La capa `processes/` está **deprecada** en v2.1.

## En este repositorio

El frontend sirve tres vistas —editor de canon, lector de borradores con diff y panel de
defectos y puertas— y `CLAUDE.md` §2.3 dice que **ninguna lleva lógica de dominio**. Eso
resuelve de antemano la pregunta más difícil de FSD: aquí casi nada sube de `pages/`, porque
lo que justificaría una `entity` o una `feature` es precisamente la regla de negocio que el
backend no cede. Una `entities/hecho/` que validara intervalos en JavaScript sería una
violación de FSD y del invariante a la vez.

Consecuencias prácticas:

- Las tres vistas son tres slices de `pages/`. Empieza y quédate ahí.
- El cliente de la API, el consumo de SSE de `/tareas/{id}/eventos` y los tipos generados
  desde los modelos Pydantic van a `shared/api/`. Intercambiar datos con el backend no es
  lógica de negocio.
- Toda validación la responde la API. Si el frontend necesita saber si algo es válido,
  pregunta; duplicar un invariante en JavaScript garantiza que las dos copias divergirán.
- No crees `entities/` ni `features/` para reflejar la ontología. El dominio vive en
  `backend/domain/`; el frontend solo lo muestra.

## Referencias

En `~/.claude/skills/feature-sliced-design/references/`: `layer-structure.md`,
`cross-import-patterns.md`, `auth-and-api.md`, `state-management.md`, `asset-handling.md`,
`excessive-entities.md`, `framework-integration.md`, `growth-walkthrough.md` y
`migration-guide.md`. Carga solo la que haga falta; no las precargues todas.
