---
name: sqlite-vec
description: Búsqueda vectorial dentro de SQLite con la extensión sqlite-vec — tablas virtuales `vec0`, consultas KNN con `match` y `k`, columnas de metadatos, *partition keys* y columnas auxiliares, tipos float32 / int8 / bit, cuantización y carga de la extensión. Úsala siempre que aparezcan búsqueda semántica, embeddings, similitud de vectores, RAG, vecinos más cercanos, índice vectorial, `vec0`, sqlite-vec o sqlite-vss, y en particular al tocar el índice vectorial de `UnidadDeContexto` en `backend/store/`. Aplícala aunque no se nombre la extensión: si hay que guardar embeddings y consultarlos por similitud sobre SQLite, las trampas están en la serialización, en las dimensiones y en qué se puede poner en el `WHERE`.
---

# sqlite-vec

Extensión en C puro, sin dependencias, que sustituye a `sqlite-vss`. Es **pre-v1**: fija la
versión que uses, porque hay cambios rompientes entre versiones.

## Cuándo encaja

Hace **búsqueda exhaustiva, no ANN**: compara la consulta contra todos los vectores del
*partition* correspondiente. Es la elección correcta con corpus de miles a algunos millones
de vectores, un solo escritor y un fichero en vez de un servicio — que es exactamente el
perfil descrito en `CLAUDE.md` §2.1. Si algún día hicieran falta escrituras concurrentes
sobre decenas de millones de vectores, ese es el momento de cambiar de motor, no de forzar
particiones.

Antes de tocar nada, fija tres cosas: **dimensión** del embedding, **tipo** de vector y
**métrica**. Las tres quedan clavadas en el DDL y cambiarlas obliga a recrear y repoblar la
tabla, así que conviene que estén en una migración desde el primer día.

## Decisiones de esquema

| Clase | Sintaxis | Para qué | Límite |
| --- | --- | --- | --- |
| Vector | `embedding float[768]` | Lo que se compara | — |
| Metadatos | `capitulo integer`, `revision integer` | Filtrar dentro del KNN | 16 |
| Partition key | `novela_id integer partition key` | Shardear y saltarse vectores | 4 |
| Auxiliar | `+texto text` | Guardar el original sin JOIN | 16 |

Una columna va a **metadatos** si aparecerá en el `WHERE` de una búsqueda, y a **auxiliar**
si solo se devuelve. Una columna auxiliar en el `WHERE` es un error, no una consulta lenta.
Una *partition key* solo se paga con cientos de vectores por valor distinto; con pocos,
degrada la búsqueda en vez de acelerarla.

`float[N]` es el caso normal; `int8[N]` reduce el tamaño a un cuarto y `bit[N]` a un
treintaidosavo, comparándose por distancia Hamming, útil como primer filtro antes de
reordenar con los vectores completos. La métrica se declara en la columna
(`distance_metric=cosine`, `L2` por defecto); con embeddings ya normalizados, L2 y coseno
ordenan igual.

## Las cuatro trampas

1. **La serialización.** Un vector entra como JSON (`'[0.1, 0.2]'`) o como BLOB compacto de
   float32: `serialize_float32(lista)` o `array.astype(np.float32)`. Nunca un `bytes` de
   float64 — entra sin error y da distancias sin sentido.
2. **La dimensión.** Debe coincidir exactamente con la declarada. Cambiar de modelo de
   embeddings a mitad de proyecto es una migración, no un `UPDATE`.
3. **Qué admite el `WHERE`.** Sobre metadatos solo `=`, `!=`, `>`, `>=`, `<`, `<=`. `LIKE`,
   `IS NULL`, `GLOB` o cualquier función escalar dan error o resultados incorrectos, que es
   la peor de las dos opciones porque no se nota.
4. **La forma del KNN.** Hace falta `match` sobre la columna vector **y** un límite
   (`and k = 10`, o `limit 10`). Sin límite no es una consulta KNN y el filtrado de
   metadatos deja de aplicarse como esperas. Solo se puede hacer `match` sobre una columna
   vector por consulta.

## Forma canónica

```sql
select unidad_id, distance, texto
from vec_contexto
where embedding match :vector_consulta
  and k = 10
  and novela_id = :novela_id      -- partition key: descarta shards enteros
  and revision <= :revision       -- metadato: filtra durante el KNN
order by distance;
```

El filtrado de metadatos ocurre **dentro** del cálculo del KNN, no después: por eso estas
condiciones van en el mismo `WHERE` y no en una subconsulta envolvente. Filtrar por fuera
devuelve menos de `k` resultados y la diferencia es silenciosa.

## En este repositorio

- La carga de la extensión y la serialización viven **solo en `store/`**. El resto del
  código pasa listas de floats. Es la misma frontera que ya fija `CLAUDE.md` §2.1: solo
  `store/` sabe si el índice vectorial está en el mismo fichero o en uno aparte, y si
  `serialize_float32` aparece en tres módulos, la próxima migración de dimensión se hace en
  tres sitios.
- Guarda junto a cada vector el **modelo y la versión** que lo generó. Mezclar embeddings de
  dos modelos produce resultados plausibles y equivocados, que es justo el fallo que nadie
  detecta. Encaja con la regla 3.5: toda generación lleva procedencia.
- La tabla `vec0` es un **índice derivado, no la fuente de verdad**. Debe poder
  reconstruirse desde el canon, y el comando que lo hace conviene que exista antes de
  necesitarlo — es lo que salva una invalidación en cascada (§7.4).
- **Nunca valides un hecho contra el índice vectorial.** La similitud semántica no distingue
  entre lo que ocurrió y lo que casi ocurrió (`CLAUDE.md` §4.1).
- En Python, comprueba `sqlite3.sqlite_version` (≥ 3.41 recomendado) y ten en cuenta que el
  SQLite del sistema en macOS no permite cargar extensiones.

## Referencias

Referencias completas: `~/.claude/skills/sqlite-vec/references/sql.md` (sintaxis de `vec0`,
reglas del KNN, funciones) y `references/python.md` (carga, serialización, patrones).
