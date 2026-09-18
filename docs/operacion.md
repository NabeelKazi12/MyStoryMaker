# Operación del harness

Lo que hace falta para **manejar** MyStoryMaker, no para escribir la novela. Vive
fuera de `CLAUDE.md` a propósito: ese fichero se inyecta entero en la ventana del
orquestador y en la de los cuatro subagentes, y en cada turno de cada uno. El
Escritor no necesita saber cómo se configura Langfuse, y pagarlo cincuenta veces
por capítulo para que no lo use es la clase de gasto que este proyecto mide.

El contrato sigue siendo [`SPECS.md`](../SPECS.md).

## Comandos

```
/novela estado         progreso
/novela preparar       investigación y escaleta
/novela capitulo N     ciclo completo de un capítulo
/novela continuar      hasta agotar pendientes o escalar
/novela compilar       manuscrito final
/novela sincronizar    reproyecta un cambio de configuración

python scripts/consolidar.py estado --json   estado completo en una línea
python scripts/consolidar.py estado          lo mismo, legible para humanos
python scripts/contexto.py N --para escritor|revisor|reparacion
python scripts/compilar.py                   produce la novela entera y compila
python scripts/compilar.py --solo-compilar   compila lo ya consolidado
python scripts/compilar.py --verificar       comprueba N5 sin escribir
python scripts/validar_capitulos.py          valida el plan
python scripts/verificar_langfuse.py         comprueba que la traza llega
python scripts/resumen_langfuse.py           tokens y coste por agente
```

`compilar.py` sin argumentos es el lanzador: abre una sesión headless por paso del
circuito y compila al final. Sirve para producir sin supervisión; cuando estás tú
delante, `/novela` es lo mismo con la parada en cada punto de decisión del autor.

## Hooks

No son recordatorios: son las condiciones de salida hechas ejecutables.

| Hook | Momento | Comprueba |
|---|---|---|
| `bloquear_memoria.py` | Antes de escribir | Que nadie edite `memory/` ni `config/capitulos.json` a mano (INV-09) |
| `validar_extension.py` | Al escribir en `manuscript/` | Extensión exacta, reparto en párrafos y ausencia de marcadores (N3) |
| `validar_capitulos.py` | Al editar la configuración | Esquema, numeración, unidad y suma (RM-03) |
| `registrar_coste.py` | Al terminar un subagente | Mide su consumo real y publica su span en Langfuse |
| `traza_langfuse.py` | Inicio y fin de sesión, y cada herramienta | Publica la traza en Langfuse (observa, nunca deniega) |

Un hook que rechaza no es un obstáculo que rodear. Es el sistema funcionando: lee
el motivo y corrige el paso.

`traza_langfuse.py` es la excepción a esa frase: no rechaza nada. Es el único
hook que no es una condición de salida sino un observador, y por eso está escrito
para no fallar jamás —si Langfuse está caído o mal configurado, el harness
produce la novela exactamente igual y lo único que se pierde es la traza.

## Observabilidad

Cada sesión de Claude Code es **una traza** en Langfuse. Dentro cuelgan, del
tronco, un span por cada llamada a herramienta y uno por cada subagente, este
último con su modelo y sus tokens. Como el lanzador abre una sesión headless por
paso del circuito, en Langfuse se ve una traza por paso: «N1 y N2», cada capítulo.

Las puntuaciones del Revisor suben como *scores* de Langfuse —los cinco criterios,
la media, la iteración y el fallo de D1— tanto si el capítulo se aprueba como si
se rechaza. Eso es lo que permite comparar iteraciones y capítulos entre sí en vez
de solo mirar trazas sueltas: si la media sube mientras los tokens bajan, el
sistema está mejorando; si D1 rechaza tres veces seguidas por continuidad, el
problema está en la escaleta y no en el Escritor.

```
python scripts/verificar_langfuse.py          prueba de extremo a extremo
python scripts/verificar_langfuse.py estado   qué hay en la cola y qué ha subido
```

La configuración está en `.env` (fuera de git; la plantilla es `.env.example`).
Sin claves, todo esto son operaciones nulas. `LANGFUSE_TRAZAR_HERRAMIENTAS=0`
deja solo los subagentes, que es lo que conviene si el span por herramienta
resulta demasiado ruido.

Los spans no se envían en caliente: se encolan en `logs/langfuse-cola.jsonl` y
suben por lotes al cerrarse un subagente o la sesión. Una red lenta retrasa la
traza, nunca el trabajo. Si la cola no se vacía nunca, ahí está el fallo.

### Dos cosas que no son obvias y cuestan una tarde

**`Task` no dispara `PreToolUse` ni `PostToolUse`.** El único evento de un
subagente es `SubagentStop`, y por eso su span lo emite `registrar_coste.py` y no
`traza_langfuse.py`. Si algún día un span de subagente aparece con duración cero,
es que alguien ha vuelto a colgarlo del ciclo de vida de una herramienta.

**El `transcript_path` de `SubagentStop` es el del orquestador, no el del
subagente.** Sumarlo atribuye a cada agente el gasto acumulado de la sesión
entera: el Revisor siempre parecería más caro que el Escritor solo por correr
después. La transcripción buena está en `<sesión>/subagents/agent-*.jsonl` y es la
última modificada. De ahí salen tokens, modelo, inicio y fin, desglosando entrada
fresca, escritura de caché y lectura de caché —que valen 1, 1,25 y 0,1— porque
meterlo todo en «input» infla el coste alrededor de un 50%.

## Economía de tokens

El circuito se instrumentó antes de optimizarlo, y la primera medición seria —el
ciclo del capítulo 2, una sola iteración— dejó dos sorpresas. Ponderando cada
tramo por lo que cuesta (fresca ×1, caché escrita ×1,25, caché leída ×0,1):

| Agente | Turnos | Ponderado de entrada |
|---|---|---|
| Orquestador | 31 | 347.092 |
| `escritor` | 7 | 89.232 |
| `revisor` | 13 | 144.005 |

**El orquestador era el 60% del coste de un capítulo sin escribir una línea de
novela**, porque abría `bible.json`, `outline.json`, `ledger.json` y `cap-01.md`
para material que solo usaban los subagentes, y porque repitió `validar_capitulos.py`
tres veces y `estado` dos. Cada fichero que entra en su ventana se vuelve a pagar
en cada uno de los turnos que le quedan.

Y en los subagentes lo caro no era leer de caché sino **escribirla**: cada
resultado de herramienta abre un segmento nuevo que se factura a 1,25. Las nueve
lecturas del Revisor eran el 72% de su coste. Explorar sale más caro que recibir.

De ahí las tres piezas que gobiernan hoy el gasto:

- **`scripts/contexto.py`** arma el material de cada subagente en un proceso local
  que no cuesta tokens, ya recortado al capítulo, y lo deja en `.contexto/`. El
  orquestador pasa la ruta; el subagente hace **un** `Read`. Que el payload no se
  imprima por stdout es el punto entero del script.
- **`consolidar.py estado --json`** responde en una línea lo que antes costaba
  cinco turnos.
- **La sección «Economía de contexto»** de la skill `/novela`, que le prohíbe al
  orquestador abrir `memory/`, `manuscript/`, `reviews/` y `research/`.

Además, una reparación de forma —el hook de extensión rechaza por conteo— ya no
reconstruye el contexto entero de N3: `contexto.py N --para reparacion` son unos
2 KB en vez de 28, y no consume iteración de las tres, con un tope de dos por
iteración.

### El A/B del Revisor

El Revisor corre en `sonnet` desde esta tanda; el Escritor sigue en `opus` porque
la prosa es el producto. El control es la propia observabilidad: los cinco
criterios suben como scores a Langfuse, así que la pregunta «¿ha perdido finura la
rúbrica?» se responde comparando medias y tasa de rechazo contra los capítulos 1
y 2, que se juzgaron con `opus`. Si la señal se degrada, la vuelta atrás es una
línea en [`.claude/agents/revisor.md`](../.claude/agents/revisor.md).

Dos cautelas al leer esa comparación: la muestra histórica es de dos capítulos, y
el cambio de modelo entró a la vez que el contexto precomputado, así que un
movimiento en las notas no atribuye solo. Si quieres separar las dos causas, corre
un capítulo con `opus` y contexto precomputado antes de dar por buena la lectura.
