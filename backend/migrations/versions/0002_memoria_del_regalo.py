"""Memoria del regalo: destinatario, uso por capitulo, cronologia, guardarrail y versiones.

SPEC-003, paso A-03. Nueve tablas, dos columnas nuevas y una vista, encadenadas sobre
`0001` en lugar de reabrirla: a diferencia de SPEC-001 ya hay base creada y canon posible,
asi que reabrir la inicial destruiria lo almacenado.

Tres decisiones que conviene leer aqui y no deducirlas del esquema:

1. **La cronologia es una vista, no una tabla.** RF-BIB-02 pide una cronologia que
   alimente al validador formal. Copiarla en una tabla obliga a sincronizarla con el
   canon, y una copia que se desincroniza hace que Lean verifique una historia que ya no
   es la que se lee. La vista se deriva de `evento`, `evento_participante` y `personaje`.
2. **`hecho_capitulo` es una tabla y no una vista**, al reves que la anterior. El uso de
   un hecho en un capitulo no se deduce del canon: lo declara quien canoniza, porque un
   hecho puede estar vigente sin que ningun capitulo lo narre (es F-09 de
   `verification.md` 11).
3. **Las versiones se encadenan por `anterior_id`.** Sobrescribir la version anterior es
   exactamente lo que RF-LEC-07 prohibe, y un encadenamiento explicito lo hace imposible
   sin un `UPDATE` que ningun camino del codigo escribe.

Revision ID: 0002
"""

from __future__ import annotations

from alembic import op

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None

ESQUEMA = """
-- --- Para quien se escribe (RF-CFG-01, RF-CFG-07) -----------------------------------

CREATE TABLE destinatario (
    id TEXT PRIMARY KEY,
    brief_id TEXT NOT NULL REFERENCES brief(id),
    nombre TEXT NOT NULL,
    edad INTEGER NOT NULL CHECK (edad > 0),
    rasgos TEXT NOT NULL DEFAULT '',
    dedicatoria TEXT NOT NULL DEFAULT ''
);

CREATE TABLE elemento_personalizado (
    id TEXT PRIMARY KEY,
    destinatario_id TEXT NOT NULL REFERENCES destinatario(id),
    tipo TEXT NOT NULL CHECK (tipo IN ('recuerdo', 'rasgo', 'vinculo')),
    contenido TEXT NOT NULL,
    -- Lo obligatorio es lo que RF-VAL-04 exige encontrar en algun capitulo.
    obligatorio INTEGER NOT NULL DEFAULT 1
);

CREATE INDEX idx_elemento_por_destinatario ON elemento_personalizado(destinatario_id);

-- --- Que capitulos usan cada hecho (RF-BIB-01) --------------------------------------
-- Es la precondicion de la regeneracion selectiva: sin esto, cambiar un hecho obliga a
-- reescribir la novela entera.

-- `hecho_id` no lleva clave foranea a `hecho` a proposito: un hecho entra al canon como
-- evento de cambio en `canon_cambio`, no como fila de `hecho` (RF-STO-05). Exigir la fila
-- haria fallar toda canonizacion, que es justo el camino que este registro sirve.
CREATE TABLE hecho_capitulo (
    hecho_id TEXT NOT NULL,
    capitulo_id TEXT NOT NULL REFERENCES capitulo(id),
    registrado_en TEXT NOT NULL,
    PRIMARY KEY (hecho_id, capitulo_id)
);

CREATE INDEX idx_hecho_capitulo_por_capitulo ON hecho_capitulo(capitulo_id);

-- --- Resumen por capitulo (RF-BIB-03) -----------------------------------------------
-- Alimenta el contexto de los capitulos siguientes sin arrastrar su prosa literal.

CREATE TABLE resumen_capitulo (
    capitulo_id TEXT PRIMARY KEY REFERENCES capitulo(id),
    texto TEXT NOT NULL,
    tokens INTEGER NOT NULL DEFAULT 0,
    revision_canon INTEGER NOT NULL
);

-- --- Checkpoint por capitulo (RF-BIB-04) --------------------------------------------
-- Un capitulo completado se anota aqui. La reanudacion arranca del ultimo, y por eso no
-- puede haber dos filas para el mismo capitulo.

CREATE TABLE checkpoint_capitulo (
    capitulo_id TEXT PRIMARY KEY REFERENCES capitulo(id),
    orden INTEGER NOT NULL,
    completado_en TEXT NOT NULL,
    borrador_id TEXT REFERENCES borrador(id)
);

-- --- Guardarrail de palabras prohibidas (RF-GRD-01) ---------------------------------
-- Tres niveles. `ambito_id` queda nulo en el nivel global y apunta al brief o al
-- destinatario en los otros dos: sin el, una palabra vetada por un cliente vetaria las
-- novelas de todos.

CREATE TABLE lista_prohibida (
    id TEXT PRIMARY KEY,
    nivel TEXT NOT NULL CHECK (nivel IN ('global', 'novela', 'cliente')),
    termino TEXT NOT NULL,
    ambito_id TEXT,
    motivo TEXT NOT NULL DEFAULT '',
    CHECK (nivel = 'global' OR ambito_id IS NOT NULL)
);

CREATE UNIQUE INDEX idx_lista_prohibida_termino ON lista_prohibida(nivel, termino, ambito_id);

-- --- Audit log del policy engine (RF-GRD-05, RF-GRD-06) -----------------------------
-- Inmutable por convencion, como `registro_decision`: una decision de politica que se
-- puede editar despues no sirve como evidencia de nada.

CREATE TABLE audit_log (
    id TEXT PRIMARY KEY,
    ocurrido_en TEXT NOT NULL,
    decision TEXT NOT NULL,
    motivo TEXT NOT NULL,
    ambito TEXT NOT NULL DEFAULT '',
    tarea_id TEXT REFERENCES tarea(id),
    capitulo_id TEXT REFERENCES capitulo(id),
    termino TEXT
);

CREATE INDEX idx_audit_log_por_capitulo ON audit_log(capitulo_id);

-- --- Versiones de la novela (RF-LEC-06, RF-LEC-07) ----------------------------------

CREATE TABLE version_novela (
    id TEXT PRIMARY KEY,
    volumen_id TEXT NOT NULL REFERENCES volumen(id),
    numero INTEGER NOT NULL,
    anterior_id TEXT REFERENCES version_novela(id),
    publicada_en TEXT NOT NULL,
    motivo TEXT NOT NULL DEFAULT '',
    UNIQUE (volumen_id, numero),
    -- La primera version no tiene anterior, ninguna otra puede no tenerlo.
    CHECK (numero = 1 OR anterior_id IS NOT NULL)
);

CREATE TABLE version_capitulo (
    version_id TEXT NOT NULL REFERENCES version_novela(id),
    capitulo_id TEXT NOT NULL REFERENCES capitulo(id),
    borrador_id TEXT REFERENCES borrador(id),
    -- Lo que la lectura marca como cambiado respecto a la version anterior.
    cambiado INTEGER NOT NULL DEFAULT 0,
    PRIMARY KEY (version_id, capitulo_id)
);
"""

# `momento` fecha el evento en tiempo de historia; `posicion_en_historia` solo lo ordena.
# Con un orden no se puede decir que edad tenia nadie, que es el segundo invariante de
# RF-LEAN-02. Anclar un `Hecho` a una fecha seguiria prohibido (`CLAUDE.md` 3.2): lo que
# se fecha es el evento, que es el ancla de toda vigencia.
COLUMNAS = (
    "ALTER TABLE evento ADD COLUMN momento INTEGER",
    "ALTER TABLE personaje ADD COLUMN anio_de_nacimiento INTEGER",
)

# La cronologia de RF-BIB-02, derivada y no copiada. Un evento sin `momento` no aparece:
# lo que falta se cuenta aparte en lugar de recibir una fecha inventada.
VISTA = """
CREATE VIEW evento_cronologia AS
SELECT
    e.id AS evento_id,
    e.momento AS momento,
    e.lugar_id AS lugar_id,
    p.id AS personaje_id,
    p.anio_de_nacimiento AS anio_de_nacimiento
FROM evento e
LEFT JOIN evento_participante ep ON ep.evento_id = e.id
LEFT JOIN personaje p ON p.id = ep.entidad_id
WHERE e.momento IS NOT NULL
"""

# La decision de ontologia que SPEC-003 6.1 exige registrar.
DECISIONES = (
    (
        "rd-d18",
        "El destinatario es una clase del dominio con sus elementos personalizados, no "
        "campos sueltos colgando de Brief",
        "Anadir nombre, edad y recuerdos como columnas de brief",
        "La personalizacion tiene que ser verificable: RF-VAL-02 compara el nombre contra "
        "la story bible y RF-VAL-04 busca cada elemento obligatorio en los capitulos. Una "
        "lista de campos sueltos no distingue lo obligatorio de lo que solo enriquece",
        "domain, store, quality",
    ),
    (
        "rd-d19",
        "La cronologia es una vista derivada del canon, no una tabla propia",
        "Una tabla evento_cronologia mantenida en paralelo",
        "Una copia obliga a sincronizarla, y cuando se desincroniza Lean verifica una "
        "historia que ya no es la que se lee: verificacion formal que da falsos verdes",
        "store, formal",
    ),
)


def upgrade() -> None:
    op.execute("PRAGMA foreign_keys = ON")
    for sentencia in filter(None, (s.strip() for s in ESQUEMA.split(";"))):
        op.execute(sentencia)
    for sentencia in COLUMNAS:
        op.execute(sentencia)
    op.execute(VISTA.strip())

    for identificador, decision, alternativas, motivo, ambito in DECISIONES:
        op.execute(
            "INSERT INTO registro_decision "
            "(id, decision, alternativas, motivo, ambito, reversible, tomada_en) VALUES "
            f"('{identificador}', '{decision}', '{alternativas}', '{motivo}', "
            f"'{ambito}', 1, datetime('now'))"
        )


def downgrade() -> None:
    """No hay marcha atras: las migraciones son hacia delante (RF-STO-02)."""
    raise NotImplementedError(
        "Las migraciones de este proyecto son hacia delante. Para volver atras, "
        "reconstruye la base desde cero."
    )
