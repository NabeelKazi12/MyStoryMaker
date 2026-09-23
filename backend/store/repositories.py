"""Repositorios tipados sobre SQLite.

El grafo del dominio se modela relacionalmente y las consultas transitivas se resuelven
con CTEs recursivas dentro de este paquete, no reconstruyendo el grafo en memoria: traerse
todas las aristas para recorrerlas en Python convierte una consulta de indice en un
barrido completo, y deja de funcionar justo cuando el libro crece (`architecture.md` 3.1).

El canon versionado no se copia entero por revision: se guardan eventos de cambio y se
reconstruye. Una copia por revision no escala a 40 capitulos.

Cubre RF-STO-05, RF-STO-07 y RF-STO-08, y desde SPEC-003 tambien RF-BIB-01 y
RF-BIB-05.
"""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass

from backend.domain.diegetic.canon import (
    EventoDeCronologia,
    Hecho,
    Lugar,
    Personaje,
    Predicado,
)
from backend.domain.errors import ErrorDeDominio
from backend.domain.vocabularies import ExclusividadDePredicado, Relevancia


@dataclass(frozen=True)
class CatalogoDePredicados:
    """Lectura del catalogo que hace ejecutable la contradiccion de hechos."""

    conn: sqlite3.Connection

    def todos(self) -> tuple[Predicado, ...]:
        filas = self.conn.execute(
            "SELECT nombre, exclusividad, descripcion FROM predicado ORDER BY nombre"
        ).fetchall()
        return tuple(
            Predicado(
                nombre=fila["nombre"],
                exclusividad=ExclusividadDePredicado(fila["exclusividad"]),
                descripcion=fila["descripcion"],
            )
            for fila in filas
        )

    def exclusividad_de(self, nombre: str) -> ExclusividadDePredicado:
        """Exclusividad declarada de un predicado. Uno no catalogado es un error.

        Se rechaza aqui y no al insertar para que el mensaje diga que hay que catalogarlo,
        en vez de dejar que aflore como una violacion de clave foranea.
        """
        fila = self.conn.execute(
            "SELECT exclusividad FROM predicado WHERE nombre = ?", (nombre,)
        ).fetchone()
        if fila is None:
            raise ErrorDeDominio(
                "Predicado",
                "todo predicado usado por un Hecho esta en el catalogo",
                f"nombre={nombre!r}; anadirlo exige un RegistroDeDecision y una migracion",
            )
        return ExclusividadDePredicado(fila["exclusividad"])

    def es_funcional(self, nombre: str) -> bool:
        """Un predicado funcional admite a lo sumo un valor vigente por sujeto."""
        return self.exclusividad_de(nombre) is ExclusividadDePredicado.FUNCIONAL


@dataclass(frozen=True)
class GrafoCausal:
    """Consultas transitivas sobre `evento_causa`, resueltas con CTE recursiva."""

    conn: sqlite3.Connection

    def alcanzables_desde(self, evento_id: str) -> frozenset[str]:
        """Todos los eventos que un evento causa, directa o indirectamente."""
        filas = self.conn.execute(
            """
            WITH RECURSIVE alcanzable(id) AS (
                SELECT efecto_id FROM evento_causa WHERE causa_id = ?
                UNION
                SELECT ec.efecto_id
                FROM evento_causa ec
                JOIN alcanzable a ON ec.causa_id = a.id
            )
            SELECT id FROM alcanzable
            """,
            (evento_id,),
        ).fetchall()
        return frozenset(fila["id"] for fila in filas)

    def ciclos(self) -> tuple[str, ...]:
        """Eventos que se alcanzan a si mismos. Un grafo causal con ciclos no es causal."""
        filas = self.conn.execute(
            """
            WITH RECURSIVE alcanzable(origen, id) AS (
                SELECT causa_id, efecto_id FROM evento_causa
                UNION
                SELECT a.origen, ec.efecto_id
                FROM evento_causa ec
                JOIN alcanzable a ON ec.causa_id = a.id
            )
            SELECT DISTINCT origen FROM alcanzable WHERE origen = id ORDER BY origen
            """
        ).fetchall()
        return tuple(fila["origen"] for fila in filas)

    def precedencias_violadas(self) -> tuple[tuple[str, str], ...]:
        """Pares (causa, efecto) en los que la causa no precede al efecto en la historia.

        Es el invariante 2 de `definitions.md`: si A causa B, A precede a B en tiempo de
        historia. Se comprueba sobre las aristas directas; los ciclos los cubre `ciclos`.
        """
        filas = self.conn.execute(
            """
            SELECT ec.causa_id, ec.efecto_id
            FROM evento_causa ec
            JOIN evento causa ON causa.id = ec.causa_id
            JOIN evento efecto ON efecto.id = ec.efecto_id
            WHERE causa.posicion_en_historia >= efecto.posicion_en_historia
            ORDER BY ec.causa_id, ec.efecto_id
            """
        ).fetchall()
        return tuple((fila["causa_id"], fila["efecto_id"]) for fila in filas)


@dataclass(frozen=True)
class CanonVersionado:
    """Revisiones del canon reconstruidas desde eventos de cambio.

    Cada canonizacion escribe sus cambios y sube la revision. Reconstruir la revision N
    es plegar los cambios de 0 a N, no leer una copia guardada.
    """

    conn: sqlite3.Connection

    def revision_actual(self) -> int:
        fila = self.conn.execute("SELECT MAX(revision) AS r FROM canon_revision").fetchone()
        return int(fila["r"] or 0)

    def abrir_revision(self, motivo: str = "") -> int:
        """Incrementa la revision. Solo la canonizacion deberia llamar a esto."""
        siguiente = self.revision_actual() + 1
        self.conn.execute(
            "INSERT INTO canon_revision (revision, creada_en, motivo) "
            "VALUES (?, datetime('now'), ?)",
            (siguiente, motivo),
        )
        return siguiente

    def registrar_insercion(self, revision: int, hecho: Hecho) -> None:
        """Deja constancia de que un hecho entro en el canon en esa revision."""
        self.conn.execute(
            "INSERT INTO canon_cambio (revision, tabla, fila_id, operacion, datos) "
            "VALUES (?, 'hecho', ?, 'insertar', ?)",
            (revision, hecho.id, hecho.valido_desde),
        )

    def registrar_cierre(self, revision: int, hecho_id: str, valido_hasta: str) -> None:
        """Deja constancia de que un intervalo se cerro en esa revision."""
        self.conn.execute(
            "INSERT INTO canon_cambio (revision, tabla, fila_id, operacion, datos) "
            "VALUES (?, 'hecho', ?, 'cerrar_intervalo', ?)",
            (revision, hecho_id, valido_hasta),
        )

    def hechos_vigentes_en(self, revision: int) -> frozenset[str]:
        """Que hechos estaban vigentes en la revision N.

        Responde a «que era verdad en el capitulo 12» sin guardar una copia del canon por
        capitulo, que es lo que RF-STO-05 exige.
        """
        filas = self.conn.execute(
            """
            SELECT fila_id, operacion
            FROM canon_cambio
            WHERE tabla = 'hecho' AND revision <= ?
            ORDER BY id
            """,
            (revision,),
        ).fetchall()

        vigentes: set[str] = set()
        for fila in filas:
            if fila["operacion"] == "insertar":
                vigentes.add(fila["fila_id"])
            else:
                vigentes.discard(fila["fila_id"])
        return frozenset(vigentes)


@dataclass(frozen=True)
class BorradoresAceptadosDuplicados:
    """Escenas con mas de un borrador aceptado, tal como las ve el store."""

    escena_id: str
    cuantos: int


@dataclass(frozen=True)
class SiembraAbierta:
    """Una siembra sin pagar, con la distancia que lleva y el limite que declaro."""

    id: str
    distancia: int
    distancia_maxima: int | None


@dataclass(frozen=True)
class DesvioDePresupuesto:
    """Un capitulo con su presupuesto declarado y su recuento real."""

    capitulo_id: str
    presupuesto: int
    real: int


@dataclass(frozen=True)
class ConsultasDeCalidad:
    """Lo que `quality/` necesita de la base, expresado como datos y no como SQL.

    Existe por la regla 4 de `architecture.md` 2.3: solo `store/` habla con SQLite. Los
    verificadores reciben filas ya tipadas, asi que se pueden probar sin base de datos y
    la frontera se mantiene sin depender de la disciplina de quien escribe el siguiente.
    """

    conn: sqlite3.Connection

    def borradores_aceptados_duplicados(self) -> tuple[BorradoresAceptadosDuplicados, ...]:
        filas = self.conn.execute(
            "SELECT escena_id, COUNT(*) AS n FROM borrador WHERE estado = 'aceptado' "
            "GROUP BY escena_id HAVING n > 1 ORDER BY escena_id"
        ).fetchall()
        return tuple(
            BorradoresAceptadosDuplicados(escena_id=f["escena_id"], cuantos=f["n"])
            for f in filas
        )

    def siembras_abiertas(self) -> tuple[SiembraAbierta, ...]:
        filas = self.conn.execute(
            """
            SELECT sp.id, sp.distancia_maxima, siembra.orden AS orden_siembra,
                   (SELECT MAX(orden) FROM escena) AS orden_actual
            FROM siembra_pago sp
            JOIN escena siembra ON siembra.id = sp.escena_siembra
            WHERE sp.estado = 'abierto'
            ORDER BY sp.id
            """
        ).fetchall()
        return tuple(
            SiembraAbierta(
                id=f["id"],
                distancia=(f["orden_actual"] or 0) - f["orden_siembra"],
                distancia_maxima=f["distancia_maxima"],
            )
            for f in filas
        )

    def desvios_de_presupuesto(self) -> tuple[DesvioDePresupuesto, ...]:
        filas = self.conn.execute(
            """
            SELECT c.id, c.presupuesto_palabras,
                   COALESCE(SUM(b.recuento_palabras), 0) AS real
            FROM capitulo c
            LEFT JOIN escena e ON e.capitulo_id = c.id
            LEFT JOIN borrador b ON b.escena_id = e.id AND b.estado = 'aceptado'
            WHERE c.presupuesto_palabras IS NOT NULL
            GROUP BY c.id
            ORDER BY c.id
            """
        ).fetchall()
        return tuple(
            DesvioDePresupuesto(
                capitulo_id=f["id"], presupuesto=f["presupuesto_palabras"], real=f["real"]
            )
            for f in filas
        )


@dataclass(frozen=True)
class StoryBible:
    """Lectura de la story bible: quien, donde, que es cierto y cuando paso.

    Es la unica puerta por la que la ficha de la lectura (RF-LEC-02) y el generador de
    Lean (RF-LEAN-01) leen el canon. Que los dos lean por aqui es lo que garantiza que la
    ficha que se publica y la cronologia que se verifica hablen de la misma historia.

    Cubre RF-BIB-05.
    """

    conn: sqlite3.Connection

    def personajes(self) -> tuple[Personaje, ...]:
        filas = self.conn.execute(
            "SELECT id, nombre_canonico, alias, relevancia, deseo_externo, "
            "necesidad_interna, creencia_falsa, anio_de_nacimiento "
            "FROM personaje ORDER BY id"
        ).fetchall()
        return tuple(
            Personaje(
                id=fila["id"],
                nombre_canonico=fila["nombre_canonico"],
                alias=tuple(a for a in fila["alias"].split("|") if a),
                relevancia=Relevancia(fila["relevancia"]),
                deseo_externo=fila["deseo_externo"],
                necesidad_interna=fila["necesidad_interna"],
                creencia_falsa=fila["creencia_falsa"],
                anio_de_nacimiento=fila["anio_de_nacimiento"],
            )
            for fila in filas
        )

    def lugares(self) -> tuple[Lugar, ...]:
        filas = self.conn.execute(
            "SELECT id, nombre_canonico, alias, atmosfera_sensorial, contenido_en "
            "FROM lugar ORDER BY id"
        ).fetchall()
        return tuple(
            Lugar(
                id=fila["id"],
                nombre_canonico=fila["nombre_canonico"],
                alias=tuple(a for a in fila["alias"].split("|") if a),
                atmosfera_sensorial=fila["atmosfera_sensorial"],
                contenido_en=fila["contenido_en"],
            )
            for fila in filas
        )

    def hechos(self) -> tuple[Hecho, ...]:
        filas = self.conn.execute(
            "SELECT id, sujeto_id, predicado, objeto, valido_desde, valido_hasta "
            "FROM hecho ORDER BY id"
        ).fetchall()
        return tuple(
            Hecho(
                id=fila["id"],
                sujeto_id=fila["sujeto_id"],
                predicado=fila["predicado"],
                objeto=fila["objeto"],
                valido_desde=fila["valido_desde"],
                valido_hasta=fila["valido_hasta"],
            )
            for fila in filas
        )

    def cronologia(self) -> tuple[EventoDeCronologia, ...]:
        """La cronologia de RF-BIB-02, leida de la vista y agrupada por evento.

        La vista devuelve una fila por participante; aqui se agrupan porque el invariante
        de Lean razona sobre eventos, no sobre pares evento-personaje.
        """
        filas = self.conn.execute(
            "SELECT evento_id, momento, lugar_id, personaje_id "
            "FROM evento_cronologia ORDER BY momento, evento_id, personaje_id"
        ).fetchall()

        agrupado: dict[str, list[str]] = {}
        datos: dict[str, tuple[int, str | None]] = {}
        for fila in filas:
            datos[fila["evento_id"]] = (fila["momento"], fila["lugar_id"])
            if fila["personaje_id"]:
                agrupado.setdefault(fila["evento_id"], []).append(fila["personaje_id"])

        return tuple(
            EventoDeCronologia(
                evento_id=evento_id,
                momento=momento,
                lugar_id=lugar_id,
                personajes=tuple(agrupado.get(evento_id, ())),
            )
            for evento_id, (momento, lugar_id) in datos.items()
        )


@dataclass(frozen=True)
class UsoDeHechos:
    """Que capitulos usan cada hecho, y al reves.

    Es la precondicion de la regeneracion selectiva (RF-LEC-05): sin esto, cambiar un
    hecho obliga a reescribir la novela entera. El registro es **declarado**, no deducido:
    un hecho puede estar vigente sin que ningun capitulo lo narre, y darlo por usado seria
    regenerar de mas.

    Cubre RF-BIB-01.
    """

    conn: sqlite3.Connection

    def registrar(self, hecho_id: str, capitulo_id: str) -> None:
        """Anota el uso. Idempotente: canonizar dos veces no duplica la fila."""
        self.conn.execute(
            "INSERT OR IGNORE INTO hecho_capitulo (hecho_id, capitulo_id, registrado_en) "
            "VALUES (?, ?, datetime('now'))",
            (hecho_id, capitulo_id),
        )

    def capitulos_de(self, hecho_id: str) -> tuple[str, ...]:
        """Los capitulos que hay que regenerar si ese hecho cambia."""
        filas = self.conn.execute(
            "SELECT capitulo_id FROM hecho_capitulo WHERE hecho_id = ? ORDER BY capitulo_id",
            (hecho_id,),
        ).fetchall()
        return tuple(fila["capitulo_id"] for fila in filas)

    def hechos_de(self, capitulo_id: str) -> tuple[str, ...]:
        filas = self.conn.execute(
            "SELECT hecho_id FROM hecho_capitulo WHERE capitulo_id = ? ORDER BY hecho_id",
            (capitulo_id,),
        ).fetchall()
        return tuple(fila["hecho_id"] for fila in filas)


@dataclass(frozen=True)
class ResumenDeCapitulo:
    """Lo que un capitulo deja para los que vienen detras."""

    capitulo_id: str
    texto: str
    tokens: int
    revision_canon: int


@dataclass(frozen=True)
class ResumenesDeCapitulo:
    """Resumen por capitulo, que es lo que alimenta el contexto de los siguientes.

    Es lo que mantiene el paquete de tamano constante en el capitulo 40: si el capitulo 3
    entrara con su prosa, el paquete creceria con el libro (`architecture.md` 4.4). Un
    capitulo tiene **un** resumen, no un historial: regenerarlo lo sustituye, porque dos
    resumenes del mismo capitulo son dos versiones de lo que paso y nadie sabria cual vale.

    Cubre RF-BIB-03.
    """

    conn: sqlite3.Connection

    def guardar(self, capitulo_id: str, texto: str, *, revision_canon: int) -> None:
        from backend.context.presupuesto import contar_tokens

        self.conn.execute(
            "INSERT INTO resumen_capitulo (capitulo_id, texto, tokens, revision_canon) "
            "VALUES (?, ?, ?, ?) "
            "ON CONFLICT(capitulo_id) DO UPDATE SET "
            "texto = excluded.texto, tokens = excluded.tokens, "
            "revision_canon = excluded.revision_canon",
            (capitulo_id, texto, contar_tokens(texto), revision_canon),
        )

    def anteriores_a(self, capitulo_id: str) -> tuple[ResumenDeCapitulo, ...]:
        """Los resumenes de los capitulos que van antes que este, en orden de lectura."""
        filas = self.conn.execute(
            """
            SELECT r.capitulo_id, r.texto, r.tokens, r.revision_canon
            FROM resumen_capitulo r
            JOIN capitulo c ON c.id = r.capitulo_id
            WHERE c.volumen_id = (SELECT volumen_id FROM capitulo WHERE id = ?)
              AND c.orden < (SELECT orden FROM capitulo WHERE id = ?)
            ORDER BY c.orden
            """,
            (capitulo_id, capitulo_id),
        ).fetchall()
        return tuple(
            ResumenDeCapitulo(
                capitulo_id=fila["capitulo_id"],
                texto=fila["texto"],
                tokens=fila["tokens"],
                revision_canon=fila["revision_canon"],
            )
            for fila in filas
        )


@dataclass(frozen=True)
class CheckpointDeCapitulos:
    """Por donde iba la generacion cuando se cayo.

    Los dos fallos que este repositorio existe para evitar son simetricos: reanudar
    rehaciendo el ultimo capitulo paga dos veces la invocacion, y reanudar saltandoselo
    deja un hueco que nadie ve hasta leer la novela entera. Por eso marcar es idempotente
    y `siguiente` se calcula del orden declarado, no de un contador propio.

    Cubre RF-BIB-04.
    """

    conn: sqlite3.Connection

    def marcar_completado(
        self, capitulo_id: str, *, orden: int, borrador_id: str | None = None
    ) -> None:
        self.conn.execute(
            "INSERT INTO checkpoint_capitulo (capitulo_id, orden, completado_en, borrador_id) "
            "VALUES (?, ?, datetime('now'), ?) "
            "ON CONFLICT(capitulo_id) DO NOTHING",
            (capitulo_id, orden, borrador_id),
        )

    def completados(self) -> tuple[str, ...]:
        filas = self.conn.execute(
            "SELECT capitulo_id FROM checkpoint_capitulo ORDER BY orden"
        ).fetchall()
        return tuple(fila["capitulo_id"] for fila in filas)

    def siguiente(self, plan: tuple[str, ...]) -> str | None:
        """El primer capitulo del plan que aun no esta completado, o `None` si no queda.

        Se le pasa el plan entero en lugar de deducirlo: el orden de los capitulos lo
        decide la planificacion, y un repositorio que lo adivinara empezaria a opinar
        sobre el plan.
        """
        hechos = set(self.completados())
        for capitulo_id in plan:
            if capitulo_id not in hechos:
                return capitulo_id
        return None
