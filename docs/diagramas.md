# Diagramas: harness, máquina de estados, esquema y validadores

2026-09-23 · SPEC-003 RF-EVA-05

## Qué contiene este documento

Los cuatro diagramas que el alcance pide, cada uno con una frase de qué mirar en él. No
sustituyen a `architecture.md`: son la vista de conjunto que ese documento no da porque
va por capas.

---

## 1. Arquitectura del harness

Lo que hay que ver: **ningún rol llama a otro rol**. Todas las flechas entre roles pasan
por el orquestador, y esa es la regla que la puerta de límites hace cumplir.

```
      cliente
         │  entrevista (texto libre = dato, nunca instrucción)
         ▼
  ┌──────────────┐
  │ Entrevistador│──► Brief + Destinatario (validados contra schema)
  └──────────────┘
         │
         ▼
  ┌──────────────────────────── orchestrator/ ────────────────────────────┐
  │   plan ──► DAG ──► semáforo de crédito (techo 100.000 concurrentes)    │
  │     │                        │                                         │
  │     ▼                        ▼                                         │
  │  Planner                  Tarea ──► worker/ ──► modelo (haiku 4.5)     │
  │                              │                                         │
  │                              ▼                                         │
  │                   hook de capítulo  +  hook de policy                  │
  │                              │                                         │
  │                              ▼                                         │
  │                          Editor/critic ──► defectos con evidencia      │
  │                              │                                         │
  │                              ▼                                         │
  │                   canonización ──► story bible (SQLite)                │
  └───────────────────────────────┬───────────────────────────────────────┘
                                  │
             ┌────────────────────┼────────────────────┐
             ▼                    ▼                    ▼
        puertas +           observability/         export/ (PDF)
        Lean (cronología)   (Langfuse: vista)      frontend/ (lectura web)
```

## 2. Máquina de estados de TLA+

Lo que hay que ver: **`publicada` solo se alcanza desde `publicacion`**, y a
`publicacion` solo se llega con todos los capítulos validados. Es el invariante
`NoPublicarSinValidar` dibujado.

```
  configuracion ──CerrarEncargo──► planificacion ──Planificar──► escritura
                                                                     │
                                                          Escribir(c)│
                                                                     ▼
                                                                validacion
                                          ┌──────────────┬───────────┴───────────┐
                              ValidarBien │   ValidarMal │        AgotarReintentos
                            (todos listos)│  (reintento) │      (limite alcanzado)
                                          ▼              ▼                       ▼
                                    publicacion      escritura                error
                                          │
                                   Publicar│
                                          ▼
                                     publicada ──PedirCambio(c)──► escritura
                                                (solo los capítulos que usan el hecho)

  Reanudar: desde escritura o validacion, vuelve a lo que confirma el checkpoint.
```

Correspondencia acción ↔ código: cada acción de `tla/Generacion.tla` lleva en su
comentario el fichero y la función que la implementa. La tabla completa está en el
`README`.

## 3. Esquema de SQLite

Lo que hay que ver: **los hechos no cuelgan de las entidades**. Un `Hecho` apunta a dos
eventos —su `valido_desde` y su `valido_hasta`—, que es lo que hace que nada sea atemporal.

```
  brief ──1:N──► volumen ──1:N──► capitulo ──1:N──► escena
    │                                  │
    │ 1:1                              │ N:M (hecho_capitulo)   ◄── SPEC-003 A-03
    ▼                                  ▼
  destinatario ──1:N──► elemento_personalizado        hecho
    │                                                  │  │
    │                                       valido_desde  valido_hasta
    │                                                  ▼  ▼
    └── palabras vetadas ──► lista_prohibida         evento ──► lugar
                (global | novela | cliente)            │
                                                       │ N:M
                                                       ▼
                                                  personaje (anio_de_nacimiento)

  evento_cronologia  = VISTA sobre evento + evento_participante + personaje
                       (derivada, nunca copiada: rd-d19)

  version_novela ──anterior_id──► version_novela   (encadenada, nunca sobrescrita)
        │
        └──1:N──► version_capitulo (cambiado: 0|1)

  audit_log · checkpoint_capitulo · resumen_capitulo · registro_decision
```

## 4. Validadores y su punto de ejecución

Lo que hay que ver: **solo lo determinista bloquea**, y la única fila que no bloquea es la
única cuya puntuación varía entre llamadas.

| Validador | Punto de ejecución | Tipo | Autoridad |
| --- | --- | --- | --- |
| `guardarrail_palabras_prohibidas` | Hook de policy | Programático | Bloquea |
| `nombres_exactos` | Hook de capítulo | Programático | Bloquea |
| `longitud_de_capitulo` | Hook de capítulo | Programático | Bloquea |
| `elementos_obligatorios_presentes` | Puerta previa a publicar | Programático | Bloquea |
| Validación visual (browser MCP) | Puerta previa a publicar | Programático | Bloquea |
| Invariantes de cronología (Lean) | Puerta previa a publicar | Formal | Bloquea |
| Juez con rúbrica | Rol editor | Semántico | **Penaliza** |
| Revisión humana | Cierre | Inspección | Penaliza |
| Invariantes del harness (TLC) | Desarrollo y tubería | Formal | Bloquea el cambio, no la generación |
