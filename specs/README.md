# specs/

| Documento | Papel | Estado |
|---|---|---|
| [`../SPECS.md`](../SPECS.md) | Contrato entre diagrama, harness e implementación | **Vigente (v2.1)** |
| [`especificacion-funcional.md`](especificacion-funcional.md) | Casos de uso y reglas de negocio | Vigente (v1.0) |
| [`especificacion-tecnica.md`](especificacion-tecnica.md) | Esquemas de datos y detalle interno | Vigente (v1.0) con salvedades |

`SPECS.md` manda. Cuando un documento de esta carpeta lo contradiga, gana SPECS.

## Salvedades de la especificación técnica

Se redactó suponiendo una aplicación Python con CLI propia. La implementación
vigente es un **harness sobre Claude Code** (SPECS §2), así que estas partes hay
que leerlas como historia del diseño y no como descripción del sistema:

- **§1–§3 (arquitectura, stack, `src/mystirymaker/`)** — no hay paquete Python ni
  máquina de estados en código. El orquestador es la sesión principal, los agentes
  son subagentes de `.claude/agents/` y la CLI es el comando `/novela`. De
  `scripts/` solo existe lo que vigila una condición de salida.
- **`prompts/`** — vive en `.claude/agents/`: el cuerpo de cada subagente es su
  prompt de sistema.
- **Vector store (ChromaDB)** — no se usa. La recuperación de contexto es lo que
  el orquestador inyecta: resúmenes de los capítulos anteriores y texto completo
  de los dos inmediatos.
- **§8 `.env`** — sin claves propias: las credenciales las gestiona Claude Code.
- **RN-09 (±15 %)** — sustituida por tolerancia en líneas. Con capítulos de cuatro
  líneas, el 15 % son 0,6 líneas y no significa nada; la comprobación de N3 es
  igualdad exacta (SPECS §12.1).
- **§4.3 `palabras_objetivo`** — con `extension.unidad: "lineas"` el campo es
  `lineas_objetivo`. `outline.json` declara la unidad que usa.

Lo que sigue vigente y se ha implementado tal cual: el modelo de datos de la
biblia, el ledger y las revisiones (§4), la función de aprobación (§6.3), la
escritura atómica con incremento de `version` (§7) y la traza por línea en
`logs/run-*.jsonl` (§9).
