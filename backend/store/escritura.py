"""Lo que la escritura escribe y lo que la lectura lee de ella.

Vive aqui porque `store/` es el unico que habla con SQLite (`CLAUDE.md` 4). El bucle del
worker decide; estos repositorios guardan y devuelven, y no opinan sobre nada.

Una nota sobre el estado de los borradores, porque es lo que mas se malinterpreta al leer
este modulo: **ningun borrador llega a `aceptado` en v1**. La puerta `escena_limpia`
declara tres invariantes que v1 no implementa, y una puerta con evidencia ausente no esta
superada. Lo que la escritura produce es un borrador `propuesto` que, si pasa lo que si se
puede comprobar, avanza a `en_revision`. La lectura lo sirve marcado como tal. Servirlo sin
marca lo haria pasar por definitivo; no servirlo lo haria invisible para siempre.

Cubre RF-ESC-03, RF-ESC-05 y RF-RUT-05.
"""

from __future__ import annotations

import sqlite3
from collections.abc import Sequence
from dataclasses import dataclass

from backend.domain.production.ejecucion import Defecto, PaqueteDeContexto, Procedencia
from backend.domain.vocabularies import EstadoDeBorrador


@dataclass(frozen=True)
class RegistroDeInvocacion:
    """El paquete y la procedencia de cada llamada a un modelo.

    Se guardan siempre, tambien cuando la llamada falla: una invocacion que se pago y se
    perdio es la metrica que revela caidas recurrentes del worker, y si solo se anotaran
    las que salen bien, el sistema pareceria mas sano cuanto peor funcionase.

    Cubre la parte persistente de `CLAUDE.md` 3.5.
    """

    conn: sqlite3.Connection

    def guardar_paquete(self, paquete: PaqueteDeContexto) -> None:
        self.conn.execute(
            "INSERT OR IGNORE INTO paquete_contexto "
            "(id, tarea_id, revision_canon, hash, tokens_por_componente) "
            "VALUES (?, ?, ?, ?, ?)",
            (
                paquete.id,
                paquete.tarea_id,
                paquete.revision_canon,
                paquete.hash,
                ";".join(
                    f"{nombre}={tokens}"
                    for nombre, tokens in paquete.tokens_por_componente
                ),
            ),
        )

    def guardar_procedencia(self, procedencia: Procedencia) -> None:
        self.conn.execute(
            "INSERT INTO procedencia (id, agente, modelo, version_de_prompt, paquete_id, "
            "parametros_muestreo, coste, latencia_ms, clase_de_fallo, timestamp) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, datetime('now'))",
            (
                procedencia.id,
                procedencia.agente,
                procedencia.modelo,
                procedencia.version_de_prompt,
                procedencia.paquete_id,
                procedencia.parametros_muestreo,
                procedencia.coste,
                procedencia.latencia_ms,
                (
                    None
                    if procedencia.clase_de_fallo is None
                    else procedencia.clase_de_fallo.value
                ),
            ),
        )


@dataclass(frozen=True)
class ColaDeTareas:
    """La cola de `Tarea`, leida. Quien la mueve es el Orquestador, no esto.

    La separacion importa: un repositorio que ademas decidiera transiciones seria un
    segundo escritor sobre la maquina de estados, y la maquina deja de poder comprobarse
    por modelos en cuanto tiene dos autoridades (D-02).
    """

    conn: sqlite3.Connection

    def siguiente_lista(self) -> sqlite3.Row | None:
        """La tarea lista mas prioritaria. P0 antes que P1, y a igualdad, la mas antigua."""
        fila: sqlite3.Row | None = self.conn.execute(
            "SELECT t.id, t.plan_id, t.tipo, t.rol_asignado, t.prioridad, p.volumen_id, "
            "p.modo FROM tarea t JOIN plan p ON p.id = t.plan_id "
            "WHERE t.estado = 'lista' ORDER BY t.prioridad, t.rowid LIMIT 1"
        ).fetchone()
        return fila

    def listas_del_plan(self, plan_id: str) -> int:
        fila = self.conn.execute(
            "SELECT COUNT(*) AS n FROM tarea WHERE plan_id = ? AND estado IN "
            "('pendiente', 'lista', 'en_curso', 'en_verificacion', 'rechazada')",
            (plan_id,),
        ).fetchone()
        return int(fila["n"])

    def intentos_de(self, tarea_id: str) -> tuple[sqlite3.Row, ...]:
        return tuple(
            self.conn.execute(
                "SELECT numero, clase_de_fallo, tipo_de_defecto FROM tarea_intento "
                "WHERE tarea_id = ? ORDER BY numero",
                (tarea_id,),
            ).fetchall()
        )

    def anotar_intento(
        self, tarea_id: str, *, clase: str, tipo_de_defecto: str | None
    ) -> None:
        self.conn.execute(
            "INSERT INTO tarea_intento (tarea_id, numero, clase_de_fallo, "
            "tipo_de_defecto, timestamp) SELECT ?, COALESCE(MAX(numero), 0) + 1, ?, ?, "
            "datetime('now') FROM tarea_intento WHERE tarea_id = ?",
            (tarea_id, clase, tipo_de_defecto, tarea_id),
        )

    def anotar_falta(self, tarea_id: str, falta: Sequence[str]) -> None:
        """Lo que a una tarea le falta para poder avanzar. Es lo que la pantalla ensena."""
        self.conn.execute(
            "UPDATE tarea SET falta = ? WHERE id = ?", ("|".join(falta), tarea_id)
        )

    def desbloqueables(self, plan_id: str) -> tuple[str, ...]:
        """Tareas pendientes cuyas dependencias estan todas aceptadas.

        Es la reconciliacion de `plan.py` resuelta en SQL sobre el estado real. Una tarea
        pasa a lista cuando, y solo cuando, todas sus `depende_de` estan `aceptada`:
        ningun otro criterio la desbloquea.
        """
        filas = self.conn.execute(
            """
            SELECT t.id FROM tarea t
            WHERE t.plan_id = ? AND t.estado = 'pendiente'
              AND NOT EXISTS (
                SELECT 1 FROM tarea_dependencia d
                JOIN tarea dep ON dep.id = d.depende_de
                WHERE d.tarea_id = t.id AND dep.estado <> 'aceptada'
              )
            ORDER BY t.prioridad, t.rowid
            """,
            (plan_id,),
        ).fetchall()
        return tuple(fila["id"] for fila in filas)


@dataclass(frozen=True)
class Borradores:
    """Las versiones de la prosa de una escena."""

    conn: sqlite3.Connection

    def siguiente_version(self, escena_id: str) -> int:
        fila = self.conn.execute(
            "SELECT COALESCE(MAX(version), 0) + 1 AS v FROM borrador WHERE escena_id = ?",
            (escena_id,),
        ).fetchone()
        return int(fila["v"])

    def guardar(
        self,
        borrador_id: str,
        *,
        escena_id: str,
        version: int,
        texto: str,
        procedencia_id: str | None,
        hechos_detectados: Sequence[tuple[str, str, str]] = (),
    ) -> None:
        """Guarda la prosa como `propuesto` y sus hechos declarados sin canonizar.

        Los hechos van a su propia tabla y con `canonizado = 0`: son una **declaracion**
        del Redactor, no canon, y la distancia entre las dos cosas es todo el diseno.
        """
        self.conn.execute(
            "INSERT INTO borrador (id, escena_id, version, texto, estado, "
            "recuento_palabras, procedencia_id) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (
                borrador_id,
                escena_id,
                version,
                texto,
                EstadoDeBorrador.PROPUESTO.value,
                len(texto.split()),
                procedencia_id,
            ),
        )
        for numero, (sujeto, predicado, objeto) in enumerate(hechos_detectados, start=1):
            self.conn.execute(
                "INSERT INTO hecho_detectado (id, borrador_id, sujeto_id, predicado, "
                "objeto, canonizado) VALUES (?, ?, ?, ?, ?, 0)",
                (f"{borrador_id}-hd-{numero}", borrador_id, sujeto, predicado, objeto),
            )

    def marcar(self, borrador_id: str, estado: EstadoDeBorrador) -> None:
        self.conn.execute(
            "UPDATE borrador SET estado = ? WHERE id = ?", (estado.value, borrador_id)
        )

    def marcar_canonizados(self, borrador_id: str) -> None:
        self.conn.execute(
            "UPDATE hecho_detectado SET canonizado = 1 WHERE borrador_id = ?", (borrador_id,)
        )

    def ultimo_no_obsoleto(self, escena_id: str) -> sqlite3.Row | None:
        """El borrador vigente de una escena: el ultimo que nadie ha invalidado."""
        fila: sqlite3.Row | None = self.conn.execute(
            "SELECT id, escena_id, version, texto, estado, recuento_palabras, "
            "procedencia_id FROM borrador WHERE escena_id = ? AND obsoleto = 0 "
            "ORDER BY version DESC LIMIT 1",
            (escena_id,),
        ).fetchone()
        return fila

    def hechos_declarados(self, borrador_id: str) -> tuple[tuple[str, str, str], ...]:
        filas = self.conn.execute(
            "SELECT sujeto_id, predicado, objeto FROM hecho_detectado "
            "WHERE borrador_id = ? ORDER BY id",
            (borrador_id,),
        ).fetchall()
        return tuple((f["sujeto_id"], f["predicado"], f["objeto"]) for f in filas)


@dataclass(frozen=True)
class Defectos:
    """Los defectos detectados sobre un borrador, con quien los detecto."""

    conn: sqlite3.Connection

    def guardar(self, defectos: Sequence[Defecto], *, detectado_por: str) -> None:
        for defecto in defectos:
            if not defecto.tiene_evidencia:
                # Un defecto sin evidencia no llega al Orquestador (`AGENTS.md` 5): se
                # descarta aqui en lugar de guardarse, porque guardarlo lo convertiria en
                # una opinion con numero de registro.
                continue
            self.conn.execute(
                "INSERT OR REPLACE INTO defecto (id, tipo, severidad, regla_violada, "
                "evidencia, span, estado, detectado_por, extraccion_evaluada, borrador_id) "
                "VALUES (?, ?, ?, ?, ?, ?, 'abierto', ?, ?, ?)",
                (
                    defecto.id,
                    defecto.tipo,
                    defecto.severidad.value,
                    defecto.regla_violada,
                    defecto.evidencia,
                    defecto.span,
                    detectado_por,
                    defecto.extraccion_evaluada,
                    defecto.borrador_id,
                ),
            )

    def abiertos_de(self, borrador_id: str) -> tuple[sqlite3.Row, ...]:
        return tuple(
            self.conn.execute(
                "SELECT id, tipo, severidad, regla_violada, evidencia FROM defecto "
                "WHERE borrador_id = ? AND estado = 'abierto' ORDER BY id",
                (borrador_id,),
            ).fetchall()
        )


@dataclass(frozen=True)
class Puertas:
    """El resultado de cada puerta evaluada, con lo que no pudo comprobar."""

    conn: sqlite3.Connection

    def registrar(
        self,
        puerta_id: str,
        *,
        fase: str,
        politica: str,
        superada: bool,
        evidencia_ausente: Sequence[str],
        ambito_id: str,
    ) -> None:
        self.conn.execute(
            "INSERT OR REPLACE INTO puerta (id, fase, politica, resultado, "
            "evidencia_ausente, ambito_id) VALUES (?, ?, ?, ?, ?, ?)",
            (
                puerta_id,
                fase,
                politica,
                "superada" if superada else "no_superada",
                "|".join(evidencia_ausente),
                ambito_id,
            ),
        )

    def de_ambito(self, ambito_id: str) -> sqlite3.Row | None:
        fila: sqlite3.Row | None = self.conn.execute(
            "SELECT id, fase, politica, resultado, evidencia_ausente FROM puerta "
            "WHERE ambito_id = ? ORDER BY id DESC LIMIT 1",
            (ambito_id,),
        ).fetchone()
        return fila


@dataclass(frozen=True)
class EscenaLeida:
    """Una escena tal como la lectura la necesita: con su prosa y con su estado."""

    id: str
    orden: int
    texto: str
    palabras: int
    estado: str
    aceptado: bool
    motivo: str
    modelo: str


@dataclass(frozen=True)
class CapituloLeido:
    """Un capitulo con las escenas que ya tienen prosa."""

    id: str
    orden: int
    titulo: str
    escenas: tuple[EscenaLeida, ...]

    @property
    def palabras(self) -> int:
        return sum(escena.palabras for escena in self.escenas)


@dataclass(frozen=True)
class TextoDeLaNovela:
    """La prosa de una novela, capitulo a capitulo, con el estado de cada borrador.

    Es la lectura de RF-RUT-05. Devuelve el ultimo borrador **no obsoleto** de cada
    escena, no el aceptado: en v1 no hay aceptados, y una lectura que solo sirviera
    aceptados estaria permanentemente vacia sin que nada lo explicara.
    """

    conn: sqlite3.Connection

    def por_capitulos(self, volumen_id: str) -> tuple[CapituloLeido, ...]:
        capitulos = self.conn.execute(
            "SELECT id, orden, titulo FROM capitulo WHERE volumen_id = ? ORDER BY orden",
            (volumen_id,),
        ).fetchall()

        leidos: list[CapituloLeido] = []
        for capitulo in capitulos:
            filas = self.conn.execute(
                """
                SELECT e.id AS escena_id, e.orden AS orden, b.id AS borrador_id,
                       b.texto, b.estado, b.recuento_palabras,
                       COALESCE(pr.modelo, '') AS modelo,
                       p.resultado AS puerta, p.evidencia_ausente
                FROM escena e
                JOIN borrador b ON b.escena_id = e.id AND b.obsoleto = 0
                LEFT JOIN procedencia pr ON pr.id = b.procedencia_id
                LEFT JOIN puerta p ON p.ambito_id = b.id
                WHERE e.capitulo_id = ?
                  AND b.version = (SELECT MAX(version) FROM borrador
                                    WHERE escena_id = e.id AND obsoleto = 0)
                ORDER BY e.orden
                """,
                (capitulo["id"],),
            ).fetchall()

            leidos.append(
                CapituloLeido(
                    id=capitulo["id"],
                    orden=capitulo["orden"],
                    titulo=capitulo["titulo"],
                    escenas=tuple(
                        EscenaLeida(
                            id=fila["escena_id"],
                            orden=fila["orden"],
                            texto=fila["texto"],
                            palabras=fila["recuento_palabras"],
                            estado=fila["estado"],
                            aceptado=fila["estado"] == EstadoDeBorrador.ACEPTADO.value,
                            motivo=_motivo(
                                fila["estado"], fila["puerta"], fila["evidencia_ausente"]
                            ),
                            modelo=fila["modelo"],
                        )
                        for fila in filas
                    ),
                )
            )
        return tuple(leidos)


def _motivo(estado: str, puerta: str | None, ausente: str | None) -> str:
    """Por que este borrador no esta aceptado, en una linea que la pantalla no compone.

    Que el texto salga de aqui y no del frontend no es un capricho de reparto: la razon
    por la que una puerta no se supera es una regla del dominio, y una pantalla que la
    redactara acabaria diciendo algo distinto de lo que el sistema hizo.
    """
    if estado == EstadoDeBorrador.ACEPTADO.value:
        return ""
    if puerta is None:
        return "Escrito y todavia sin verificar: su puerta no se ha evaluado."
    faltantes = [f for f in (ausente or "").split("|") if f]
    if faltantes:
        return (
            "No esta aceptado porque su puerta no pudo comprobarlo todo. Invariantes que "
            f"esta version no implementa: {', '.join(faltantes)}. La ausencia de evidencia "
            "no se cuenta como evidencia a favor."
        )
    return "No esta aceptado: su puerta encontro defectos y la escena vuelve al Redactor."


@dataclass(frozen=True)
class Portada:
    """Lo que se ve de una novela antes del capitulo 1, y a quien pertenece."""

    volumen_id: str
    titulo: str
    dedicatoria: str
    brief_id: str | None
    destinatario_id: str | None


@dataclass(frozen=True)
class Portadas:
    """Titulo y dedicatoria de una novela (SPEC-006).

    Los dos viven donde ya vivian -`volumen.titulo` y `destinatario.dedicatoria`- para que
    la lectura, el texto y el PDF los sirvan sin saber que se pueden editar.
    """

    conn: sqlite3.Connection

    def de(self, volumen_id: str) -> Portada | None:
        fila = self.conn.execute(
            """
            SELECT v.id, v.titulo, v.brief_id, d.id AS destinatario_id, d.dedicatoria
            FROM volumen v
            LEFT JOIN destinatario d ON d.brief_id = v.brief_id
            WHERE v.id = ?
            LIMIT 1
            """,
            (volumen_id,),
        ).fetchone()
        if fila is None:
            return None
        return Portada(
            volumen_id=fila["id"],
            titulo=fila["titulo"],
            dedicatoria=fila["dedicatoria"] or "",
            brief_id=fila["brief_id"],
            destinatario_id=fila["destinatario_id"],
        )

    def guardar(self, portada: Portada) -> None:
        self.conn.execute(
            "UPDATE volumen SET titulo = ? WHERE id = ?", (portada.titulo, portada.volumen_id)
        )
        if portada.destinatario_id is not None:
            self.conn.execute(
                "UPDATE destinatario SET dedicatoria = ? WHERE id = ?",
                (portada.dedicatoria, portada.destinatario_id),
            )
