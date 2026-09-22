# Ontología para generación agéntica de novelas — Diagramas Mermaid

2026-09-21 · @Nabeel

## Cómo leer estos diagramas

Ocho apartados del mismo modelo, de lo general a lo ejecutable: siete llevan diagrama Mermaid y el 5 conserva su número con el contenido movido a `architecture.md` §6.2. Las definiciones de cada clase están en el documento hermano.

| Diagrama | Tipo | Responde |
| --- | --- | --- |
| 1. Árbol maestro | `flowchart` | ¿Qué hay en el dominio? |
| 2. Plano diegético | `classDiagram` | ¿Cómo se estructura el canon? |
| 3. Plano discursivo | `classDiagram` | ¿Cómo se organiza el relato? |
| 4. Puente entre planos | `flowchart` | ¿Cómo se conectan historia y relato? |
| 5. Ciclo de vida de escena | — | ¿Cómo avanza el trabajo? → `architecture.md` §6.2 |
| 6. Ensamblado de contexto | `flowchart` | ¿Qué ve el agente en cada llamada? |
| 7. Bucle de calidad | `flowchart` | ¿Cómo se valida y cuándo se para? |
| 8. Núcleo mínimo | `erDiagram` | ¿Qué implemento primero? |

El diagrama 8 es el que se puede traducir directamente a esquema. Los demás son para razonar sobre el dominio.

## 1. Árbol taxonómico maestro

Tres planos y tres capas transversales, con las clases de cada uno.

```mermaid
flowchart LR
    ONT[Ontología<br/>de novela]

    ONT --> DIE[Plano diegético]
    ONT --> DIS[Plano discursivo]
    ONT --> PRO[Plano producción]
    ONT --> ESP[Capa especificación]
    ONT --> CTX[Capa contexto]
    ONT --> CAL[Capa calidad]

    DIE --> D1[Entidad]
    DIE --> D2[EventoNarrativo]
    DIE --> D3[Hecho temporal]
    DIE --> D4[EstadoConocimiento]
    DIE --> D5[ReglaDelMundo]
    DIE --> D6[LíneaTemporal]

    DIS --> S1[Jerarquía textual]
    DIS --> S2[Escena]
    DIS --> S3[Narración]
    DIS --> S4[Hilo]
    DIS --> S5[ParSiembraPago]
    DIS --> S6[Estilo y Motivo]

    PRO --> P1[RolDeAgente]
    PRO --> P2[Tarea y Plan]
    PRO --> P3[Borrador]
    PRO --> P4[Crítica]
    PRO --> P5[Procedencia]

    ESP --> E1[Brief]
    ESP --> E2[Restricción]

    CTX --> C1[UnidadDeContexto]
    CTX --> C2[Canon]
    CTX --> C3[PaqueteDeContexto]

    CAL --> Q1[Rúbrica y Juicio]
    CAL --> Q2[Defecto]
    CAL --> Q3[Puerta]
```

Las subclases de `Entidad` y los niveles de la jerarquía textual se detallan en los diagramas 2 y 3 para no pasar de seis hijos por nivel.

| Nodo agrupador | Contiene |
| --- | --- |
| Entidad | Personaje, Lugar, Objeto, Organización, Lore |
| Jerarquía textual | Serie, Volumen, Parte, Capítulo, Beat, Párrafo |
| Estilo y Motivo | PerfilDeEstilo, Motivo, Tema, PlantillaEstructural |
| Crítica | Revisión, Diff, RegistroDeDecisión |

## 2. Plano diegético

El `EventoNarrativo` es el pivote: establece hechos, los invalida y es el punto de anclaje de toda vigencia temporal.

```mermaid
classDiagram
    class Entidad {
        +id
        +nombre_canonico
        +alias[]
        +estatus_ontologico
        +relevancia
    }
    class Personaje {
        +deseo_externo
        +necesidad_interna
        +herida_de_origen
        +creencia_falsa
        +arco
        +funcion_dramatica[]
    }
    class Lugar {
        +tipo
        +atmosfera_sensorial
        +accesibilidad
    }
    class Objeto {
        +estado_fisico
        +significado_simbolico
        +es_siembra
    }
    class Organizacion {
        +objetivo
        +jerarquia
    }
    class Lore {
        +dominio
        +veracidad_en_diegesis
    }

    Entidad <|-- Personaje
    Entidad <|-- Lugar
    Entidad <|-- Objeto
    Entidad <|-- Organizacion
    Entidad <|-- Lore

    class EventoNarrativo {
        +descripcion
        +posicion_en_historia
        +tipo
        +visibilidad
    }
    class Hecho {
        +predicado
        +objeto
        +valido_desde
        +valido_hasta
        +certeza
    }
    class EstadoDeConocimiento {
        +estatus_epistemico
        +fuente
        +fiabilidad
    }
    class ReglaDelMundo {
        +enunciado
        +coste
        +excepciones[]
    }
    class Relacion {
        +tipo
        +valencia
        +valido_desde
    }
    class LineaTemporal {
        +granularidad
        +ramas[]
    }

    Entidad "1..*" --o "*" EventoNarrativo : participa_en
    EventoNarrativo "1" --> "*" Hecho : establece
    EventoNarrativo "*" --> "*" Hecho : invalida
    EventoNarrativo "*" --> "*" EventoNarrativo : causa
    EventoNarrativo "*" --> "1" Lugar : ocurre_en
    Hecho "1" --> "1" Entidad : sujeto
    EstadoDeConocimiento "*" --> "1" Personaje : conocedor
    EstadoDeConocimiento "*" --> "1" Hecho : sobre
    EstadoDeConocimiento "*" --> "1" EventoNarrativo : adquirido_en
    EstadoDeConocimiento "*" --> "*" EstadoDeConocimiento : sabe_que_sabe
    Relacion "*" --> "2" Entidad : vincula
    LineaTemporal "1" --> "*" EventoNarrativo : ordena
    ReglaDelMundo "*" --> "*" EventoNarrativo : restringe
```

Tres aristas hacen el trabajo pesado: `establece` e `invalida` delimitan la vigencia de cada hecho, y `adquirido_en` ancla el conocimiento de cada personaje a un punto concreto de la línea temporal. Con esas tres, las contradicciones y las fugas epistémicas son consultas, no lecturas.

## 3. Plano discursivo

La jerarquía contenedora y la `Escena` como unidad de trabajo, con todo lo que la configura.

```mermaid
classDiagram
    class Serie
    class Volumen {
        +presupuesto_palabras
        +promesa_al_lector
    }
    class Parte {
        +acto
        +orden
    }
    class Capitulo {
        +orden
        +presupuesto_palabras
        +gancho_final
    }
    class Escena {
        +pov
        +focalizacion
        +distancia_narrativa
        +tiempo_verbal
        +momento_en_historia
        +objetivo
        +conflicto
        +resultado
        +valor_entrada
        +valor_salida
        +carga_emocional
        +funcion_en_trama
        +tipo
        +presupuesto_palabras
    }
    class Beat {
        +tipo
        +duracion_relativa
        +intencion
    }

    Serie "1" *-- "1..*" Volumen
    Volumen "1" *-- "1..*" Parte
    Parte "1" *-- "1..*" Capitulo
    Capitulo "1" *-- "1..*" Escena
    Escena "1" *-- "1..*" Beat

    class Narracion {
        +persona
        +tipo_narrador
        +fiabilidad
        +acceso_a_conciencias[]
    }
    class Hilo {
        +tipo
        +pregunta_dramatica
        +curva_de_tension[]
        +estado
    }
    class ParSiembraPago {
        +tipo
        +estado
        +sutileza
        +distancia_maxima
    }
    class PlantillaEstructural {
        +beats_esperados[]
        +tolerancia
    }
    class PerfilDeEstilo {
        +longitud_media_frase
        +registro
        +tics_verbales[]
        +vocabulario_prohibido[]
    }
    class Motivo {
        +manifestacion
        +frecuencia_objetivo
    }
    class Tema

    Escena "*" --> "1" Narracion : narrada_por
    Escena "*" --> "1..*" Hilo : avanza
    Escena "*" --> "*" ParSiembraPago : siembra_o_paga
    Escena "*" --> "*" Motivo : manifiesta
    Escena "0..1" --> "1" PlantillaEstructural : conforma_a
    Escena "*" --> "0..1" PerfilDeEstilo : voz_aplicada
    Motivo "*" --> "1" Tema : vehicula
    Hilo "1" --> "0..1" Escena : resuelto_en
```

El par `valor_entrada` / `valor_salida` en la escena es lo que permite comprobar automáticamente que algo cambia. Si son iguales, la escena no está haciendo trabajo narrativo.

## 4. El puente entre planos

Este es el diagrama que conviene tener presente al implementar: muestra cómo un hecho del mundo llega a la página y cómo vuelve al canon.

```mermaid
flowchart TD
    subgraph DIE[Plano diegético · tiempo de historia]
        EV[EventoNarrativo]
        HE[Hecho<br/>vigente en intervalo]
        CO[EstadoConocimiento<br/>quién lo sabe]
        EN[Entidad]
    end

    subgraph DIS[Plano discursivo · tiempo de relato]
        ES[Escena]
        CA[Capítulo]
        HI[Hilo]
        SP[ParSiembraPago]
    end

    subgraph PRO[Producción]
        BO[Borrador]
        DE[Defecto]
    end

    EV -->|establece| HE
    EV -->|invalida| HE
    EN -->|participa_en| EV
    CO -->|sobre| HE
    CO -->|adquirido_en| EV

    ES -->|renderiza| EV
    ES -->|avanza| HI
    ES -->|siembra o paga| SP
    ES -->|contenida_en| CA

    ES -->|genera| BO
    BO -->|hechos nuevos| HE
    BO -->|si contradice| DE
    CO -.->|filtra qué puede narrar| ES
    HE -.->|estado del mundo| ES
```

Las dos flechas punteadas son la clave. `Hecho → Escena` alimenta el contexto con el estado del mundo en ese momento; `EstadoConocimiento → Escena` lo recorta a lo que el POV puede saber.

El ciclo completo es: el evento establece el hecho, la escena renderiza el evento, el borrador verbaliza la escena, y los hechos nuevos del borrador vuelven al canon — o generan un defecto si lo contradicen. Ese retorno es lo que mantiene canon y texto sincronizados.

## 5. Ciclo de vida de una escena

La máquina de estados del borrador y la política de reintentos son proceso, no dominio: están en `architecture.md` §6.2 y §6.3. Se deja aquí el hueco numerado para no renumerar los diagramas que vienen después.

Lo que sí es dominio, y por eso se queda dicho aquí, son las dos salidas que evitan bucles infinitos: cuando el fallo es del plan y no de la prosa, la escena se replanifica en lugar de reescribirse; y cuando una escena ya canonizada depende de otra que se reescribe, vuelve a la cola en lugar de quedarse quieta contradiciendo al texto.

## 6. Ensamblado del contexto

Qué entra en el paquete que recibe el Redactor, con los tres filtros que lo recortan.

```mermaid
flowchart LR
    subgraph FUENTES[Fuentes]
        BR[Brief y estilo]
        CN[Canon estructurado]
        PR[Prosa indexada]
        PY[Pirámide resúmenes]
        PS[Siembras abiertas]
    end

    subgraph FILTROS[AlcanceDeRelevancia]
        FT[Filtro temporal<br/>hechos vigentes]
        FE[Filtro epistémico<br/>lo que el POV sabe]
        FS[Filtro estructural<br/>hilos y entidades]
    end

    PQ[PaqueteDeContexto<br/>presupuesto fijo]
    AG[Redactor]
    PV[Procedencia]

    BR --> PQ
    CN --> FT
    FT --> FE
    FE --> PQ
    PY --> FS
    PR --> FS
    FS --> PQ
    PS --> PQ

    PQ --> AG
    PQ --> PV
    AG --> PV
```

El orden importa: el filtro temporal actúa antes del epistémico. Primero se determina qué es verdad en ese momento, y solo después qué de eso conoce el POV.

### Pirámide de resúmenes

```mermaid
flowchart TD
    A[Premisa de serie<br/>1-2 frases · siempre] --> B[Sinopsis de volumen<br/>200-400 palabras · siempre]
    B --> C[Resumen de parte<br/>100-200 palabras]
    C --> D[Resumen de capítulo<br/>50-100 palabras]
    D --> E[Resumen de escena<br/>1-3 frases]
    E --> F[Prosa literal<br/>solo escena anterior]

    F -.->|deriva_de| E
    E -.->|deriva_de| D
    D -.->|deriva_de| C
    C -.->|deriva_de| B
```

Las flechas punteadas van en sentido inverso a propósito: son las aristas `deriva_de` que permiten la invalidación en cascada. Al reescribir una escena, se sigue esa cadena hacia arriba marcando obsoleto todo lo que dependía de ella.

El efecto buscado es que el paquete tenga tamaño aproximadamente constante en el capítulo 3 y en el 40. Si crece con la longitud del libro, la pirámide no está funcionando.

## 7. Bucle de calidad

Tres vías de verificación con distinta autoridad: solo la programática puede bloquear.

```mermaid
flowchart TD
    BO[Borrador]

    BO --> V1[Verificación programática]
    BO --> V2[Juez LLM con rúbrica]
    BO --> V3[Muestreo humano]

    V1 --> D1[Contradicción de hechos]
    V1 --> D2[Fuga epistémica]
    V1 --> D3[Repetición n-gramas]
    V1 --> D4[Siembras abiertas]
    V1 --> D5[POV y tiempo verbal]

    V2 --> J1[Diálogo y cliché]
    V2 --> J2[Motivación y arco]
    V2 --> J3[Tensión e impacto]

    D1 --> DEF[Defecto]
    D2 --> DEF
    D3 --> DEF
    D4 --> DEF
    D5 --> DEF
    J1 --> JUI[Juicio con confianza]
    J2 --> JUI
    J3 --> JUI

    DEF --> PU[Puerta bloqueante]
    JUI --> UM[UmbralDeAceptación]
    V3 --> UM

    PU -->|falla| RW[Reescritura dirigida]
    UM -->|bajo umbral| RW
    PU -->|pasa| OK[Aceptado]
    UM -->|sobre umbral| OK
    RW --> BO
```

### Reparto de autoridad

Quién puede bloquear una puerta y quién solo penaliza está en `architecture.md` §7.1, y el reparto dimensión a dimensión en `verification.md` §4. Lo que importa para leer el diagrama: las tres vías no tienen la misma autoridad, y la diferencia no es de rigor sino de determinismo.

## 8. Núcleo mínimo viable

Las 12 clases con las que arrancar, más `Volumen` como contenedor y `Predicado` como catálogo, en forma directamente traducible a esquema. Con esas dos añadidas deja de ser el núcleo mínimo estricto y pasa a ser el esquema de la primera versión del backend.

```mermaid
erDiagram
    BRIEF ||--|| VOLUMEN : especifica
    VOLUMEN ||--o{ CAPITULO : contiene
    CAPITULO ||--o{ ESCENA : contiene
    ESCENA ||--o{ BORRADOR : tiene_versiones
    ESCENA }o--|| PERSONAJE : pov
    ESCENA }o--|| LUGAR : escenario
    ESCENA }|--|{ EVENTO : renderiza
    ESCENA }o--o{ HILO : avanza
    ESCENA ||--o{ SIEMBRA_PAGO : siembra
    EVENTO ||--o{ HECHO : establece
    EVENTO }o--o{ PERSONAJE : participan
    HECHO }o--|| PREDICADO : usa
    HECHO }o--|| PERSONAJE : sujeto_personaje
    HECHO }o--|| LUGAR : sujeto_lugar
    PERSONAJE ||--o| PERFIL_ESTILO : idiolecto
    VOLUMEN ||--|| PERFIL_ESTILO : estilo_global
    BORRADOR ||--o{ DEFECTO : reporta
    HILO ||--o| ESCENA : resuelto_en

    BRIEF {
        string id PK
        string genero
        string premisa
        string promesa_al_lector
        int extension_objetivo
    }
    PERSONAJE {
        string id PK
        string nombre_canonico
        string deseo_externo
        string necesidad_interna
        string creencia_falsa
        string arco_tipo
    }
    LUGAR {
        string id PK
        string nombre_canonico
        string atmosfera_sensorial
    }
    EVENTO {
        string id PK
        string descripcion
        int posicion_en_historia
        string tipo
        string visibilidad
    }
    PREDICADO {
        string nombre PK
        string exclusividad
        string descripcion
    }
    HECHO {
        string id PK
        string sujeto_id FK
        string predicado
        string objeto
        string valido_desde FK
        string valido_hasta FK
        string certeza
    }
    ESCENA {
        string id PK
        int orden
        string pov_id FK
        string lugar_id FK
        int momento_en_historia
        string objetivo
        string valor_entrada
        string valor_salida
        int presupuesto_palabras
    }
    CAPITULO {
        string id PK
        int orden
        int presupuesto_palabras
    }
    VOLUMEN {
        string id PK
        string titulo
    }
    HILO {
        string id PK
        string tipo
        string pregunta_dramatica
        string estado
    }
    SIEMBRA_PAGO {
        string id PK
        string tipo
        string escena_siembra FK
        string escena_pago FK
        string estado
        int distancia_maxima
    }
    PERFIL_ESTILO {
        string id PK
        int longitud_media_frase
        string registro
        string vocabulario_prohibido
    }
    BORRADOR {
        string id PK
        string escena_id FK
        int version
        string texto
        string estado
        int recuento_palabras
    }
    DEFECTO {
        string id PK
        string tipo
        string severidad
        string span
        string regla_violada
        string estado
    }
```

`PREDICADO` es lo que hace ejecutable la contradicción de hechos: sin saber qué predicados son mutuamente excluyentes, el invariante de intervalos solapados no se puede evaluar.

Dos observaciones sobre este esquema. `HECHO.valido_desde` y `valido_hasta` apuntan a `EVENTO`, no a fechas: es lo que hace posible la validación de intervalos. Y `BORRADOR` es la única tabla con texto largo — todo lo demás es estructura consultable.

Falta deliberadamente `ESTADO_CONOCIMIENTO`, que entra en la fase 2 del orden de adopción de `architecture.md` §13. Cuando se añada, su esquema es `(conocedor_id, hecho_id, estatus, adquirido_en_id, fuente)` con clave compuesta, y habilita la validación de fugas epistémicas descrita en el documento de definiciones.
