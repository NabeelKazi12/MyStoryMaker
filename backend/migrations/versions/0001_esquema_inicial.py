"""Esquema inicial del canon y de la ejecucion, con el catalogo de predicados sembrado.

Hacia delante y sin migracion de datos: no hay canon almacenado previo (SPEC-001, 9.3).

La siembra del catalogo no es un detalle de conveniencia. Con `PREDICADO` vacio,
RF-STO-07 rechaza toda canonizacion y el bucle nunca cierra (RF-STO-10).

Revision ID: 0001
"""

from __future__ import annotations

from alembic import op

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None

# Los siete valores de `dimension_de_estado` de definitions.md mas dos multivalor.
# Son los de SPEC-001 9.2 R-7: no inventan vocabulario, reutilizan uno ya cerrado.
PREDICADOS_DE_PARTIDA = (
    ("salud", "funcional", "Estado fisico del sujeto"),
    ("ubicacion", "funcional", "Donde esta el sujeto"),
    ("lealtad", "funcional", "A quien o a que responde"),
    ("emocion", "funcional", "Estado emocional dominante"),
    ("recursos", "funcional", "De que dispone"),
    ("reputacion", "funcional", "Como lo ve su entorno"),
    ("conocimiento", "funcional", "Que domina o ignora como capacidad"),
    ("posee", "multivalor", "Objetos en posesion del sujeto"),
    ("conoce_a", "multivalor", "Entidades con las que tiene trato"),
)

# Los RegistroDeDecision que SPEC-001 9.2 exige. Son inmutables y no se borran: en obras
# largas la deriva rara vez viene de mala prosa, viene de decisiones olvidadas y luego
# contradichas sin que nadie se de cuenta.
DECISIONES_REGISTRADAS = (
    (
        "rd-predicados",
        "Catalogo de predicados con exclusividad declarada",
        "Inferir la exclusividad del texto del predicado con un modelo; lista de pares "
        "excluyentes en codigo",
        "Sin saber que predicados son mutuamente excluyentes, contradiccion de hechos no es "
        "un predicado ejecutable",
        "definitions.md, store",
    ),
    (
        "rd-r1",
        "El Redactor usa claude-opus-5 con pensamiento adaptativo y effort high",
        "claude-sonnet-5 para ahorrar unos 9 dolares por novela",
        "Una llamada cuesta unos 0,21 dolares y una novela unos 15: el coste no domina y la "
        "prosa es el producto",
        "worker, agents",
    ),
    (
        "rd-r2",
        "Los reintentos de transporte los hace el cliente del SDK con max_retries 3",
        "Implementar la escalera de transporte en worker/",
        "Dos capas multiplican: tres por tres son nueve llamadas pagadas por un corte de red",
        "orchestrator, worker",
    ),
    (
        "rd-r3",
        "Historial tipificado de intentos en lugar de dos contadores",
        "Dos contadores enteros, narrativos e infraestructura",
        "D-06 clasifica en cuatro clases, no en dos: con dos contadores se pierde la senal",
        "domain, store",
    ),
    (
        "rd-r4",
        "El borrador rechazado no entra en el intento siguiente",
        "Incluirlo marcado como rechazado",
        "Reinyectarlo invita a reproducirlo, y la prosa es el componente mas caro del paquete",
        "context",
    ),
    (
        "rd-r5",
        "Timeouts de 10 minutos por invocacion, 30 por tarea y 8 horas por plan",
        "Timeouts agresivos de 60 segundos, 5 minutos y 1 hora",
        "Cancelar no cancela el coste: un vencimiento falso es una invocacion pagada y perdida",
        "orchestrator",
    ),
    (
        "rd-r6",
        "v1 tiene un solo rol con invocacion de modelo y los esqueletos entran por API",
        "Incluir tambien al Arquitecto para generar los esqueletos",
        "El trabajo de prompts es lo mas caro de iterar y un esqueleto a mano es el control "
        "del experimento",
        "alcance",
    ),
    (
        "rd-r8",
        "Tetragramas contra todos los capitulos anteriores, umbral de 2 apariciones",
        "Ventana de N capitulos anteriores",
        "El trigrama en castellano dispara falsos positivos y la repeticion que mas molesta "
        "es la de larga distancia",
        "quality",
    ),
)

ESQUEMA = """
-- ---------------------------------------------------------------- canon y estructura
CREATE TABLE brief (
    id TEXT PRIMARY KEY,
    genero TEXT NOT NULL,
    premisa TEXT NOT NULL,
    promesa_al_lector TEXT NOT NULL,
    extension_objetivo INTEGER NOT NULL CHECK (extension_objetivo > 0)
);

CREATE TABLE perfil_estilo (
    id TEXT PRIMARY KEY,
    longitud_media_frase INTEGER,
    registro TEXT NOT NULL DEFAULT '',
    vocabulario_prohibido TEXT NOT NULL DEFAULT ''
);

CREATE TABLE volumen (
    id TEXT PRIMARY KEY,
    titulo TEXT NOT NULL,
    presupuesto_palabras INTEGER,
    perfil_estilo_id TEXT REFERENCES perfil_estilo(id)
);

CREATE TABLE capitulo (
    id TEXT PRIMARY KEY,
    volumen_id TEXT NOT NULL REFERENCES volumen(id),
    orden INTEGER NOT NULL,
    presupuesto_palabras INTEGER,
    UNIQUE (volumen_id, orden)
);

CREATE TABLE personaje (
    id TEXT PRIMARY KEY,
    nombre_canonico TEXT NOT NULL,
    alias TEXT NOT NULL DEFAULT '',
    relevancia TEXT NOT NULL DEFAULT 'secundario'
        CHECK (relevancia IN ('protagonico', 'secundario', 'ambiental')),
    estatus_ontologico TEXT NOT NULL DEFAULT 'real_en_la_diegesis',
    deseo_externo TEXT NOT NULL DEFAULT '',
    necesidad_interna TEXT NOT NULL DEFAULT '',
    creencia_falsa TEXT NOT NULL DEFAULT '',
    arco_tipo TEXT CHECK (
        arco_tipo IS NULL
        OR arco_tipo IN ('positivo', 'negativo', 'plano', 'corruptor', 'redentor')
    ),
    perfil_estilo_id TEXT REFERENCES perfil_estilo(id)
);

CREATE TABLE lugar (
    id TEXT PRIMARY KEY,
    nombre_canonico TEXT NOT NULL,
    alias TEXT NOT NULL DEFAULT '',
    atmosfera_sensorial TEXT NOT NULL DEFAULT '',
    contenido_en TEXT REFERENCES lugar(id)
);

CREATE TABLE evento (
    id TEXT PRIMARY KEY,
    descripcion TEXT NOT NULL,
    posicion_en_historia INTEGER NOT NULL,
    tipo TEXT NOT NULL CHECK (tipo IN (
        'accion', 'decision', 'revelacion', 'encuentro', 'perdida', 'cambio_de_estado')),
    visibilidad TEXT NOT NULL DEFAULT 'publico'
        CHECK (visibilidad IN ('publico', 'privado', 'secreto')),
    lugar_id TEXT REFERENCES lugar(id)
);

-- El catalogo que hace ejecutable la contradiccion de hechos (RF-STO-07).
CREATE TABLE predicado (
    nombre TEXT PRIMARY KEY,
    exclusividad TEXT NOT NULL CHECK (exclusividad IN ('funcional', 'multivalor')),
    descripcion TEXT NOT NULL DEFAULT ''
);

CREATE TABLE hecho (
    id TEXT PRIMARY KEY,
    sujeto_id TEXT NOT NULL,
    predicado TEXT NOT NULL REFERENCES predicado(nombre),
    objeto TEXT NOT NULL,
    valido_desde TEXT NOT NULL REFERENCES evento(id),
    valido_hasta TEXT REFERENCES evento(id),
    certeza TEXT NOT NULL DEFAULT 'cierto',
    establecido_en TEXT,
    es_publico INTEGER NOT NULL DEFAULT 1,
    CHECK (valido_hasta IS NULL OR valido_hasta <> valido_desde)
);

CREATE TABLE escena (
    id TEXT PRIMARY KEY,
    capitulo_id TEXT NOT NULL REFERENCES capitulo(id),
    orden INTEGER NOT NULL,
    pov_id TEXT NOT NULL REFERENCES personaje(id),
    lugar_id TEXT NOT NULL REFERENCES lugar(id),
    momento_en_historia INTEGER NOT NULL,
    objetivo TEXT NOT NULL,
    conflicto TEXT NOT NULL,
    resultado TEXT NOT NULL,
    valor_entrada TEXT NOT NULL,
    valor_salida TEXT NOT NULL,
    funcion_en_trama TEXT NOT NULL,
    tipo TEXT NOT NULL,
    presupuesto_palabras INTEGER,
    UNIQUE (capitulo_id, orden),
    -- El invariante de RF-DOM-04, tambien en el esquema: el dominio no es la unica
    -- puerta, porque una escritura directa lo esquivaria.
    CHECK (valor_entrada <> valor_salida)
);

CREATE TABLE hilo (
    id TEXT PRIMARY KEY,
    tipo TEXT NOT NULL CHECK (tipo IN (
        'principal', 'secundario', 'romantico', 'misterio', 'tematico', 'de_personaje')),
    pregunta_dramatica TEXT NOT NULL CHECK (trim(pregunta_dramatica) <> ''),
    protagonista_id TEXT REFERENCES personaje(id),
    resuelto_en TEXT REFERENCES escena(id),
    abandonado INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE siembra_pago (
    id TEXT PRIMARY KEY,
    tipo TEXT NOT NULL CHECK (tipo IN (
        'objeto', 'habilidad', 'informacion', 'amenaza', 'relacion', 'pregunta')),
    escena_siembra TEXT NOT NULL REFERENCES escena(id),
    escena_pago TEXT REFERENCES escena(id),
    estado TEXT NOT NULL DEFAULT 'abierto'
        CHECK (estado IN ('abierto', 'resuelto', 'subvertido', 'abandonado')),
    distancia_maxima INTEGER
);

-- ------------------------------------------------------------------------- aristas
CREATE TABLE escena_evento (
    escena_id TEXT NOT NULL REFERENCES escena(id),
    evento_id TEXT NOT NULL REFERENCES evento(id),
    PRIMARY KEY (escena_id, evento_id)
);

CREATE TABLE escena_hilo (
    escena_id TEXT NOT NULL REFERENCES escena(id),
    hilo_id TEXT NOT NULL REFERENCES hilo(id),
    PRIMARY KEY (escena_id, hilo_id)
);

CREATE TABLE evento_participante (
    evento_id TEXT NOT NULL REFERENCES evento(id),
    entidad_id TEXT NOT NULL,
    rol_en_evento TEXT NOT NULL CHECK (rol_en_evento IN (
        'agente', 'paciente', 'testigo', 'mencionado')),
    PRIMARY KEY (evento_id, entidad_id, rol_en_evento)
);

CREATE TABLE evento_causa (
    causa_id TEXT NOT NULL REFERENCES evento(id),
    efecto_id TEXT NOT NULL REFERENCES evento(id),
    PRIMARY KEY (causa_id, efecto_id),
    CHECK (causa_id <> efecto_id)
);

CREATE TABLE escena_hecho_requerido (
    escena_id TEXT NOT NULL REFERENCES escena(id),
    hecho_id TEXT NOT NULL,
    PRIMARY KEY (escena_id, hecho_id)
);

-- --------------------------------------------------------------- canon versionado
CREATE TABLE canon_revision (
    revision INTEGER PRIMARY KEY,
    creada_en TEXT NOT NULL,
    motivo TEXT NOT NULL DEFAULT ''
);

-- El canon no se copia entero por revision: se guardan eventos de cambio y se
-- reconstruye. Una copia por revision no escala a 40 capitulos (RF-STO-05).
CREATE TABLE canon_cambio (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    revision INTEGER NOT NULL REFERENCES canon_revision(revision),
    tabla TEXT NOT NULL,
    fila_id TEXT NOT NULL,
    operacion TEXT NOT NULL CHECK (operacion IN ('insertar', 'cerrar_intervalo')),
    datos TEXT NOT NULL DEFAULT ''
);

-- ----------------------------------------------------------- produccion y ejecucion
CREATE TABLE plan (
    id TEXT PRIMARY KEY,
    objetivo TEXT NOT NULL,
    techo_de_coste REAL
);

CREATE TABLE paquete_contexto (
    id TEXT PRIMARY KEY,
    tarea_id TEXT NOT NULL,
    revision_canon INTEGER NOT NULL,
    hash TEXT NOT NULL CHECK (trim(hash) <> ''),
    tokens_por_componente TEXT NOT NULL DEFAULT ''
);

CREATE TABLE procedencia (
    id TEXT PRIMARY KEY,
    agente TEXT NOT NULL,
    modelo TEXT NOT NULL,
    version_de_prompt TEXT NOT NULL,
    paquete_id TEXT NOT NULL REFERENCES paquete_contexto(id),
    parametros_muestreo TEXT NOT NULL DEFAULT '',
    coste REAL NOT NULL DEFAULT 0,
    latencia_ms INTEGER NOT NULL DEFAULT 0,
    clase_de_fallo TEXT,
    timestamp TEXT NOT NULL
);

CREATE TABLE tarea (
    id TEXT PRIMARY KEY,
    plan_id TEXT NOT NULL REFERENCES plan(id),
    tipo TEXT NOT NULL,
    rol_asignado TEXT NOT NULL,
    estado TEXT NOT NULL DEFAULT 'pendiente' CHECK (estado IN (
        'pendiente', 'lista', 'en_curso', 'en_verificacion', 'aceptada',
        'rechazada', 'escalada', 'fallida', 'bloqueada', 'cancelada')),
    prioridad INTEGER NOT NULL DEFAULT 1 CHECK (prioridad BETWEEN 0 AND 3),
    techo_de_salida INTEGER NOT NULL DEFAULT 0,
    reserva INTEGER NOT NULL DEFAULT 0,
    paquete_id TEXT REFERENCES paquete_contexto(id),
    falta TEXT NOT NULL DEFAULT ''
);

-- Historial tipificado, no dos contadores: las cuatro clases de fallo de D-06 no caben
-- en dos enteros (SPEC-001, 9.2 R-3).
CREATE TABLE tarea_intento (
    tarea_id TEXT NOT NULL REFERENCES tarea(id),
    numero INTEGER NOT NULL,
    clase_de_fallo TEXT CHECK (clase_de_fallo IS NULL OR clase_de_fallo IN (
        'transporte', 'contrato', 'contenido', 'presupuesto')),
    tipo_de_defecto TEXT,
    timestamp TEXT NOT NULL,
    PRIMARY KEY (tarea_id, numero)
);

CREATE TABLE tarea_dependencia (
    tarea_id TEXT NOT NULL REFERENCES tarea(id),
    depende_de TEXT NOT NULL REFERENCES tarea(id),
    PRIMARY KEY (tarea_id, depende_de),
    CHECK (tarea_id <> depende_de)
);

CREATE TABLE tarea_evento (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    tarea_id TEXT NOT NULL REFERENCES tarea(id),
    estado TEXT NOT NULL,
    timestamp TEXT NOT NULL
);

-- Idempotencia: reejecutar con la misma clave devuelve el artefacto ya producido en
-- lugar de volver a invocar el modelo (RF-ORQ-13). La clave son los seis campos de
-- architecture.md 6.4, no un identificador inventado: dos ejecuciones son la misma
-- ejecucion cuando coinciden en todos ellos.
CREATE TABLE artefacto_de_tarea (
    plan_id TEXT NOT NULL,
    objetivo TEXT NOT NULL,
    revision_de_canon INTEGER NOT NULL,
    hash_del_paquete TEXT NOT NULL,
    version_de_prompt TEXT NOT NULL,
    intento INTEGER NOT NULL,
    artefacto_id TEXT NOT NULL,
    creado_en TEXT NOT NULL,
    PRIMARY KEY (plan_id, objetivo, revision_de_canon, hash_del_paquete,
                 version_de_prompt, intento)
);

CREATE TABLE borrador (
    id TEXT PRIMARY KEY,
    escena_id TEXT NOT NULL REFERENCES escena(id),
    version INTEGER NOT NULL CHECK (version >= 1),
    texto TEXT NOT NULL,
    estado TEXT NOT NULL DEFAULT 'propuesto' CHECK (estado IN (
        'propuesto', 'en_revision', 'aceptado', 'rechazado', 'obsoleto')),
    recuento_palabras INTEGER NOT NULL DEFAULT 0,
    procedencia_id TEXT REFERENCES procedencia(id),
    obsoleto INTEGER NOT NULL DEFAULT 0,
    UNIQUE (escena_id, version)
);

-- Un solo borrador aceptado por escena, en el esquema y no solo en el verificador.
CREATE UNIQUE INDEX ix_borrador_aceptado_unico
    ON borrador (escena_id) WHERE estado = 'aceptado';

CREATE TABLE hecho_detectado (
    id TEXT PRIMARY KEY,
    borrador_id TEXT NOT NULL REFERENCES borrador(id),
    sujeto_id TEXT NOT NULL,
    predicado TEXT NOT NULL,
    objeto TEXT NOT NULL,
    canonizado INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE defecto (
    id TEXT PRIMARY KEY,
    tipo TEXT NOT NULL,
    severidad TEXT NOT NULL CHECK (severidad IN (
        'critica', 'alta', 'media', 'baja', 'informativa')),
    regla_violada TEXT NOT NULL,
    evidencia TEXT NOT NULL,
    span TEXT,
    estado TEXT NOT NULL DEFAULT 'abierto',
    detectado_por TEXT NOT NULL DEFAULT '',
    extraccion_evaluada TEXT,
    borrador_id TEXT REFERENCES borrador(id)
);

CREATE TABLE puerta (
    id TEXT PRIMARY KEY,
    fase TEXT NOT NULL,
    politica TEXT NOT NULL CHECK (politica IN ('bloqueante', 'advertencia')),
    resultado TEXT,
    evidencia_ausente TEXT NOT NULL DEFAULT '',
    ambito_id TEXT
);

CREATE TABLE registro_decision (
    id TEXT PRIMARY KEY,
    decision TEXT NOT NULL,
    alternativas TEXT NOT NULL CHECK (trim(alternativas) <> ''),
    motivo TEXT NOT NULL CHECK (trim(motivo) <> ''),
    ambito TEXT NOT NULL DEFAULT '',
    reversible INTEGER NOT NULL DEFAULT 1,
    tomada_en TEXT NOT NULL
);

-- --------------------------------------------------------------------- indices (RF-STO-03)
CREATE INDEX ix_hecho_sujeto_predicado ON hecho (sujeto_id, predicado);
CREATE INDEX ix_evento_posicion_en_historia ON evento (posicion_en_historia);
"""


def upgrade() -> None:
    """Crea el esquema y siembra el catalogo de predicados."""
    for sentencia in filter(None, (s.strip() for s in ESQUEMA.split(";"))):
        op.execute(sentencia)

    for nombre, exclusividad, descripcion in PREDICADOS_DE_PARTIDA:
        op.execute(
            "INSERT INTO predicado (nombre, exclusividad, descripcion) "
            f"VALUES ('{nombre}', '{exclusividad}', '{descripcion}')"
        )

    for identificador, decision, alternativas, motivo, ambito in DECISIONES_REGISTRADAS:
        op.execute(
            "INSERT INTO registro_decision "
            "(id, decision, alternativas, motivo, ambito, reversible, tomada_en) VALUES "
            f"('{identificador}', '{decision}', '{alternativas}', '{motivo}', "
            f"'{ambito}', 1, datetime('now'))"
        )

    op.execute(
        "INSERT INTO canon_revision (revision, creada_en, motivo) "
        "VALUES (0, datetime('now'), 'esquema inicial')"
    )


def downgrade() -> None:
    """No hay marcha atras: las migraciones son hacia delante (RF-STO-02)."""
    raise NotImplementedError(
        "Las migraciones de este proyecto son hacia delante. Para volver atras, "
        "reconstruye la base desde cero: en v1 no hay canon previo que preservar."
    )
