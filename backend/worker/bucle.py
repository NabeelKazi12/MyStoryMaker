"""El bucle que escribe: consume la cola de `Tarea` y produce artefactos.

Hasta SPEC-004 este recorrido solo existia dentro de un test. Aqui esta como proceso, y la
regla que lo ordena es que **no reimplementa nada**: el semaforo, la maquina de estados, la
escalera de reintentos, el ensamblado, los hooks, las puertas y la canonizacion son los que
ya habia. Este modulo los encadena y registra lo que pasa.

Cuatro tipos de tarea y cada uno hace una sola cosa:

| tipo | quien | que produce |
| --- | --- | --- |
| `apertura` | Planner | el canon minimo y la estructura de la novela |
| `redaccion` | Redactor | un `Borrador` en estado `propuesto` |
| `verificacion` | Guardian de continuidad | `Defecto`s y el resultado de la puerta |
| `canonizacion` | Canonizador | hechos promovidos y la revision de canon + 1 |

Lo que este bucle **no** hace es aceptar un borrador. La puerta `escena_limpia` declara
tres invariantes que v1 no implementa, y una puerta con evidencia ausente no esta superada.
El borrador llega a `en_revision` y ahi se queda, con el motivo escrito. Forzar el
`aceptado` seria convertir la ausencia de evidencia en evidencia favorable, que es el
principio que sostiene todo el modulo de calidad.

Cubre RF-ESC-01 a RF-ESC-09.
"""

from __future__ import annotations

import uuid
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field

from backend.agents.planner.planner import (
    SalidaInvalidaDelPlanner,
    parsear_apertura,
)
from backend.agents.redactor.redactor import VERSION_DE_PROMPT as VERSION_DEL_REDACTOR
from backend.agents.redactor.redactor import (
    SalidaDelRedactor,
    SalidaInvalida,
    parsear,
)
from backend.context.ensamblado import Ensamblador, bloqueada_por_presupuesto
from backend.context.presupuesto import (
    PRESUPUESTO_DE_REDACCION,
    Componente,
    PresupuestoExcedido,
)
from backend.domain.diegetic.canon import Hecho
from backend.domain.production.ejecucion import (
    Defecto,
    PaqueteDeContexto,
    Procedencia,
    Tarea,
)
from backend.domain.spec.encargo import Destinatario, ElementoPersonalizado
from backend.domain.vocabularies import (
    ClaseDeFallo,
    EstadoDeBorrador,
    EstadoDeTarea,
    ModoDeEscritura,
    Severidad,
    TipoDeElementoPersonalizado,
)
from backend.observability.langfuse import LlamadaObservada, registrar_llamada
from backend.observability.trazas import ClienteDeObservabilidad, ClienteNulo
from backend.orchestrator.admision import Semaforo
from backend.orchestrator.apertura import (
    AperturaImposible,
    EncargoDeNovela,
    leer_encargo,
    persistir_apertura,
)
from backend.orchestrator.canonize import Canonizador
from backend.orchestrator.ejecucion import (
    ClaveDeTarea,
    artefacto_ya_producido,
    registrar_artefacto,
    registrar_transicion,
)
from backend.orchestrator.escritura import (
    expandir_plan,
    paquete_de_apertura,
    paquete_de_escena,
)
from backend.orchestrator.estados import Accion, clasificar, siguiente_accion
from backend.orchestrator.hooks import hook_de_capitulo, hook_de_policy
from backend.quality import puertas
from backend.quality.guardarrail import LimiteDeReescriturasAgotado
from backend.store.database import Conexion, Fila
from backend.store.escritura import (
    Borradores,
    ColaDeTareas,
    Defectos,
    Puertas,
    RegistroDeInvocacion,
)
from backend.store.repositories import (
    CanonVersionado,
    CatalogoDePredicados,
    ResumenesDeCapitulo,
    VersionesDeNovela,
)
from backend.worker.modelo import MAX_TOKENS_REDACCION, ClienteDeModelo, construir_cliente
from backend.worker.worker import InformeCrudo, Worker

# Lo que una redaccion reserva del techo del sistema: lo que ocupa su paquete mas lo que
# como mucho va a devolver. Reservar solo la entrada dejaria pasar tres tareas cuyas
# salidas juntas rompen el techo, que es justo lo que D-13 acota.
RESERVA_DE_REDACCION = PRESUPUESTO_DE_REDACCION + MAX_TOKENS_REDACCION

# Tope de vueltas de la escalera dentro de una redaccion. Es el mismo numero que
# `estados.MAXIMO_DE_INTENTOS`, y esta aqui como red: quien decide de verdad cuando parar
# es `siguiente_accion`, leyendo el historial tipificado.
VUELTAS_DE_LA_ESCALERA = 4

# Cuantas aperturas se piden a la vez a un cliente que lo admite (SPEC-010 RF-TIE-02). Sin
# pensamiento extendido, el Planner valida en torno a 2 de cada 3 aperturas: con tres a la
# vez, que fallen todas es raro y la apertura tarda lo que tarda una sola. Las tres
# reservas caben en el techo de D-13: 3 x RESERVA_DE_REDACCION = 84.000 <= 100.000.
CANDIDATOS_DE_APERTURA = 3


@dataclass(frozen=True)
class ResultadoDeVuelta:
    """Lo que hizo una vuelta del bucle. Siempre dice de que tarea habla."""

    tarea_id: str
    tipo: str
    estado: str
    detalle: str = ""


@dataclass(frozen=True)
class Invocacion:
    """Una llamada pagada, con el paquete que la origino."""

    crudo: InformeCrudo
    paquete: PaqueteDeContexto


@dataclass
class Bucle:
    """Una novela, un modo, un cliente y el credito del sistema.

    El cliente se construye una vez y por el modo del plan, no por tarea: una novela que
    empezara con el modelo y acabara en demostracion porque entretanto se cayo la
    credencial seria medio libro de cada cosa, y la `Procedencia` diria la verdad sobre
    cada capitulo mientras la novela entera mentiria.
    """

    conn: Conexion
    modo: ModoDeEscritura
    cliente: ClienteDeModelo
    semaforo: Semaforo = field(default_factory=Semaforo)
    # A donde va cada llamada ademas de a SQLite (SPEC-012). Nulo por defecto: sin
    # Langfuse la novela se escribe igual, que es la regla de SPEC-003.
    observabilidad: ClienteDeObservabilidad = field(default_factory=ClienteNulo)

    @classmethod
    def para(cls, conn: Conexion, modo: ModoDeEscritura) -> Bucle:
        """El bucle de un modo, con su cliente ya construido.

        Construirlo aqui y no dentro de cada vuelta es lo que hace que un modo `modelo`
        sin credencial falle **al arrancar**, con su mensaje, en lugar de fallar en la
        escena 7 dejando media novela escrita.
        """
        return cls(conn=conn, modo=modo, cliente=construir_cliente(modo))

    # --- la vuelta ---------------------------------------------------------------------

    def una_vuelta(self) -> ResultadoDeVuelta | None:
        """Coge la tarea lista mas prioritaria y la lleva hasta un estado terminal.

        Devuelve `None` cuando no queda nada que hacer. Quien llama decide si eso
        significa «terminado» o «bloqueado»: este bucle no opina sobre el plan.
        """
        tarea = ColaDeTareas(self.conn).siguiente_lista()
        if tarea is None:
            return None

        registrar_transicion(self.conn, tarea["id"], EstadoDeTarea.EN_CURSO.value)
        try:
            return self._despachar(tarea)
        except LimiteDeReescriturasAgotado as agotado:
            return self._parar(tarea, str(agotado))
        except Exception as error:  # noqa: BLE001 - se registra y se para, no se traga
            registrar_transicion(self.conn, tarea["id"], EstadoDeTarea.FALLIDA.value)
            ColaDeTareas(self.conn).anotar_falta(tarea["id"], (str(error),))
            return ResultadoDeVuelta(
                tarea_id=tarea["id"],
                tipo=tarea["tipo"],
                estado=EstadoDeTarea.FALLIDA.value,
                detalle=str(error),
            )
        finally:
            # Toda ruta de salida libera la reserva: exito, fallo, parada y excepcion. Una
            # reserva no liberada es credito perdido para siempre, y el sistema se va
            # parando sin ningun error visible, que es el fallo mas dificil de diagnosticar.
            self.semaforo.liberar(tarea["id"])
            self._desbloquear(tarea["plan_id"])

    def escribir_todo(self, limite_de_vueltas: int = 500) -> tuple[ResultadoDeVuelta, ...]:
        """Vacia la cola. El limite existe para que un plan mal formado no cuelgue nada."""
        hechas: list[ResultadoDeVuelta] = []
        for _ in range(limite_de_vueltas):
            vuelta = self.una_vuelta()
            if vuelta is None:
                break
            hechas.append(vuelta)
        return tuple(hechas)

    def _despachar(self, tarea: Fila) -> ResultadoDeVuelta:
        if tarea["tipo"] == "apertura":
            return self._abrir(tarea)
        if tarea["tipo"] == "redaccion":
            return self._redactar(tarea)
        if tarea["tipo"] == "verificacion":
            return self._verificar(tarea)
        if tarea["tipo"] == "canonizacion":
            return self._canonizar(tarea)
        raise ValueError(
            f"Tarea de tipo desconocido {tarea['tipo']!r}. El vocabulario de tipos es "
            f"cerrado: apertura, redaccion, verificacion y canonizacion."
        )

    def _desbloquear(self, plan_id: str) -> None:
        """Pasa a lista lo que las aceptaciones acaban de desbloquear."""
        for tarea_id in ColaDeTareas(self.conn).desbloqueables(plan_id):
            registrar_transicion(self.conn, tarea_id, EstadoDeTarea.LISTA.value)

    # --- apertura -----------------------------------------------------------------------

    def _abrir(self, tarea: Fila) -> ResultadoDeVuelta:
        """Le pide al Planner el canon minimo y lo persiste, o para informando."""
        volumen_id = tarea["volumen_id"]
        encargo = leer_encargo(self.conn, volumen_id)
        rechazo = ""

        # Un modelo real se equivoca de formato de vez en cuando -un «inicio» donde va un
        # numero, una columna de menos-. Rechazar la novela entera a la primera por eso es
        # tirar un encargo bueno, asi que el plan rechazado vuelve al Planner con el motivo
        # exacto, igual que la prosa vuelve al Redactor con sus defectos.
        for _ in range(VUELTAS_DE_LA_ESCALERA):
            ensamblador = paquete_de_apertura(self.conn, volumen_id, self._revision())
            if rechazo:
                ensamblador.poner(
                    Componente.DEFECTOS_ABIERTOS,
                    "Tu plan anterior se rechazo entero por este motivo: "
                    f"{rechazo}. Devuelve el plan completo otra vez, corregido, "
                    "respetando exactamente el formato de cada columna.",
                )

            invocaciones = self._invocar_candidatos(
                tarea, ensamblador, agente="planner", cuantos=self._candidatos_de_apertura()
            )
            if not invocaciones:
                if self._toca_escalar(tarea["id"]):
                    return self._parar(tarea, "no se pudo invocar al Planner")
                continue

            # El primero que valida, en orden de candidato. Los que no, cuentan como intento
            # y el motivo del primero es el que viaja a la vuelta siguiente.
            resultado = None
            rendicion: AperturaImposible | None = None
            motivos: list[str] = []
            for invocacion in invocaciones:
                try:
                    apertura = parsear_apertura(
                        invocacion.crudo.texto,
                        recuerdos_obligatorios=encargo.ids_de_recuerdos,
                        personajes_declarados=encargo.personajes_a_cobrar,
                    )
                    resultado = persistir_apertura(self.conn, encargo, apertura)
                    break
                except AperturaImposible as error:
                    self._anotar_apertura_rechazada(tarea)
                    rendicion = rendicion or error
                except SalidaInvalidaDelPlanner as error:
                    self._anotar_apertura_rechazada(tarea)
                    motivos.append(str(error))
            if resultado is not None:
                break
            if rendicion is not None:
                # Rendirse no es un error de formato: reintentar no le da lo que le falta.
                return self._parar(tarea, str(rendicion))
            rechazo = motivos[0]
        else:
            return self._parar(tarea, rechazo or "no se pudo invocar al Planner")

        self._aceptar(tarea)
        expandir_plan(self.conn, tarea["plan_id"], self._escenas_de(volumen_id))

        return ResultadoDeVuelta(
            tarea_id=tarea["id"],
            tipo=tarea["tipo"],
            estado=EstadoDeTarea.ACEPTADA.value,
            detalle=(
                "la novela ya estaba abierta; no se ha duplicado nada"
                if resultado.ya_estaba
                else f"{len(resultado.capitulos)} capitulos y {len(resultado.escenas)} escenas"
            ),
        )

    # --- redaccion ----------------------------------------------------------------------

    def _redactar(self, tarea: Fila) -> ResultadoDeVuelta:
        """Escribe la escena, la pasa por los dos hooks y persiste el borrador.

        La escalera vive aqui dentro y no fuera: reescribir es volver a invocar con los
        defectos como instruccion, y eso es la misma tarea en otro intento, no una tarea
        nueva. Sacarla fuera obligaria a crear una `Tarea` por intento y el plan dejaria de
        poder leerse de un vistazo.
        """
        escena_id = _sujeto_de(tarea["id"])
        encargo = leer_encargo(self.conn, tarea["volumen_id"])
        cola = ColaDeTareas(self.conn)
        defectos_abiertos: list[Defecto] = []

        for intento in range(1, VUELTAS_DE_LA_ESCALERA + 1):
            ensamblador = paquete_de_escena(self.conn, escena_id, self._revision())
            ensamblador.con_defectos(defectos_abiertos)

            reutilizado = self._artefacto_previo(tarea, ensamblador, intento)
            if reutilizado is not None:
                self._aceptar(tarea)
                return ResultadoDeVuelta(
                    tarea_id=tarea["id"],
                    tipo=tarea["tipo"],
                    estado=EstadoDeTarea.ACEPTADA.value,
                    detalle=f"{reutilizado} ya estaba producido con esta misma clave",
                )

            invocacion = self._invocar(tarea, ensamblador, agente="redactor")
            if invocacion is None:
                if self._toca_escalar(tarea["id"]):
                    return self._parar(tarea, "la invocacion no se pudo completar")
                continue

            salida = _prosa_de(invocacion.crudo.texto)
            if salida is None:
                cola.anotar_intento(
                    tarea["id"],
                    clase=ClaseDeFallo.CONTRATO.value,
                    tipo_de_defecto="contrato",
                )
                if self._toca_escalar(tarea["id"]):
                    return self._parar(
                        tarea, "la salida del Redactor no valida contra su esquema"
                    )
                continue

            if salida.contexto_insuficiente:
                # Rendirse es un resultado legitimo, no un fallo: el rol prefirio decir
                # que le falta antes que inventar. Lo que no es legitimo es taparlo.
                cola.anotar_falta(tarea["id"], salida.falta)
                return self._parar(
                    tarea,
                    "el Redactor se rindio en lugar de inventar, y dijo que le falta: "
                    + "; ".join(salida.falta),
                )

            senalados = self._hook_de_policy(
                salida.prosa, encargo=encargo, escena_id=escena_id, tarea=tarea, intento=intento
            )
            if senalados:
                defectos_abiertos = list(senalados)
                cola.anotar_intento(
                    tarea["id"],
                    clase=ClaseDeFallo.CONTENIDO.value,
                    tipo_de_defecto=defectos_abiertos[0].tipo,
                )
                if self._toca_escalar(tarea["id"]):
                    return self._parar(
                        tarea,
                        "la escalera de reintentos se agoto sin una prosa que pasara los "
                        "hooks: " + defectos_abiertos[0].regla_violada,
                    )
                continue

            borrador_id = self._persistir_borrador(
                escena_id, salida, procedencia_id=invocacion.crudo.procedencia.id
            )
            registrar_artefacto(
                self.conn, self._clave(tarea, invocacion.paquete, intento), borrador_id
            )
            self._aceptar(tarea)
            return ResultadoDeVuelta(
                tarea_id=tarea["id"],
                tipo=tarea["tipo"],
                estado=EstadoDeTarea.ACEPTADA.value,
                detalle=f"{borrador_id}, {len(salida.prosa.split())} palabras",
            )

        return self._parar(tarea, "la escalera de reintentos se agoto")

    def _hook_de_policy(
        self,
        prosa: str,
        *,
        encargo: EncargoDeNovela,
        escena_id: str,
        tarea: Fila,
        intento: int,
    ) -> tuple[Defecto, ...]:
        """El guardarrail sobre la prosa recien escrita, antes de persistirla.

        Es el unico de los dos hooks que corre por escena, y es correcto que asi sea: una
        palabra vetada lo esta en cualquier unidad de texto. El de capitulo se queda para
        cuando hay capitulo -su validador de longitud mide un capitulo, no una escena, y
        aplicado a una escena suelta la declara corta siempre-.
        """
        policy = hook_de_policy(
            prosa,
            conn=self.conn,
            capitulo_id=self._capitulo_de(escena_id),
            brief_id=encargo.brief_id,
            destinatario_id=encargo.destinatario_id,
            tarea_id=tarea["id"],
            intento=intento,
        )
        if policy.acepta:
            return ()
        return (
            Defecto(
                id=f"df-{uuid.uuid4().hex[:12]}",
                tipo="policy",
                severidad=Severidad.CRITICA,
                regla_violada="termino vetado por el cliente o por la politica global",
                evidencia=policy.motivo,
            ),
        )

    def _cerrar_capitulo(self, capitulo_id: str, encargo: EncargoDeNovela) -> None:
        """El hook de capitulo, sobre el capitulo entero, cuando ya lo hay.

        Corre aqui y no en cada redaccion porque su sujeto es el capitulo: `RF-VAL-03` mide
        la longitud de un capitulo, y evaluarla escena a escena la declararia corta
        siempre, mandando a escalado prosa que no tiene nada malo.

        Sus defectos no bloquean por si mismos: un capitulo corto es un aviso, y quien
        decide si para la linea es la puerta, no el validador.
        """
        escenas = self.conn.execute(
            """
            SELECT b.id AS borrador_id, b.texto
            FROM escena e
            JOIN borrador b ON b.escena_id = e.id AND b.obsoleto = 0
            WHERE e.capitulo_id = ?
              AND b.version = (SELECT MAX(version) FROM borrador
                                WHERE escena_id = e.id AND obsoleto = 0)
            ORDER BY e.orden
            """,
            (capitulo_id,),
        ).fetchall()
        if not escenas:
            return

        resultado = hook_de_capitulo(
            "\n\n".join(fila["texto"] for fila in escenas),
            conn=self.conn,
            destinatario=_destinatario_de(encargo),
            personajes=self._personajes_del_capitulo(capitulo_id),
        )
        ultimo = escenas[-1]["borrador_id"]
        Defectos(self.conn).guardar(
            [
                Defecto(
                    id=f"{defecto.id}:{capitulo_id}",
                    tipo=defecto.tipo,
                    severidad=defecto.severidad,
                    regla_violada=defecto.regla_violada,
                    evidencia=defecto.evidencia,
                    borrador_id=ultimo,
                )
                for defecto in resultado.defectos
            ],
            detectado_por="hook_de_capitulo",
        )

        puerta = puertas.capitulo_cerrado().evaluar(list(resultado.defectos))
        Puertas(self.conn).registrar(
            f"pu-{capitulo_id}",
            fase=puerta.fase,
            politica=puerta.politica.value,
            superada=puerta.superada,
            evidencia_ausente=puerta.evidencia_ausente,
            ambito_id=capitulo_id,
        )

    def _capitulo_completo(self, capitulo_id: str) -> bool:
        """Si todas las escenas del capitulo tienen ya un borrador vigente."""
        fila = self.conn.execute(
            """
            SELECT COUNT(*) AS pendientes FROM escena e
            WHERE e.capitulo_id = ?
              AND NOT EXISTS (
                SELECT 1 FROM borrador b WHERE b.escena_id = e.id AND b.obsoleto = 0
              )
            """,
            (capitulo_id,),
        ).fetchone()
        return int(fila["pendientes"]) == 0

    def _persistir_borrador(
        self, escena_id: str, salida: SalidaDelRedactor, *, procedencia_id: str
    ) -> str:
        borradores = Borradores(self.conn)
        version = borradores.siguiente_version(escena_id)
        borrador_id = f"bo-{escena_id}-v{version}"
        borradores.guardar(
            borrador_id,
            escena_id=escena_id,
            version=version,
            texto=salida.prosa,
            procedencia_id=procedencia_id,
            hechos_detectados=salida.hechos_nuevos_detectados,
        )
        return borrador_id

    # --- verificacion -------------------------------------------------------------------

    def _verificar(self, tarea: Fila) -> ResultadoDeVuelta:
        """Evalua la puerta `escena_limpia` sobre el borrador y registra lo que vio.

        La distincion que este metodo sostiene es la que hace util todo el modulo de
        calidad: un **defecto critico** es culpa de la prosa y manda la escena de vuelta;
        la **evidencia ausente** no lo es, y reescribir no la arregla, porque el invariante
        que falta seguiria sin implementarse en el intento siguiente. Mezclar las dos cosas
        mandaria toda escena de v1 a escalado sin que nadie haya leido nunca una prosa mala.
        """
        escena_id = _sujeto_de(tarea["id"])
        borradores = Borradores(self.conn)
        borrador = borradores.ultimo_no_obsoleto(escena_id)
        if borrador is None:
            return self._parar(tarea, "no hay borrador que verificar")

        # F-01 de `verification.md` 11: una declaracion vacia no es una escena limpia. No
        # hay nada que contradecir porque no se declaro nada, y eso es evidencia ausente.
        declarados = borradores.hechos_declarados(borrador["id"])
        vacias = () if declarados else ("hechos_nuevos_detectados",)
        encontrados = [
            Defecto(
                id=fila["id"],
                tipo=fila["tipo"],
                severidad=Severidad(fila["severidad"]),
                regla_violada=fila["regla_violada"],
                evidencia=fila["evidencia"],
                borrador_id=borrador["id"],
            )
            for fila in Defectos(self.conn).abiertos_de(borrador["id"])
        ]

        resultado = puertas.escena_limpia().evaluar(encontrados, extracciones_vacias=vacias)
        Puertas(self.conn).registrar(
            f"pu-{borrador['id']}",
            fase=resultado.fase,
            politica=resultado.politica.value,
            superada=resultado.superada,
            evidencia_ausente=resultado.evidencia_ausente,
            ambito_id=borrador["id"],
        )
        registrar_transicion(self.conn, tarea["id"], EstadoDeTarea.EN_VERIFICACION.value)

        if resultado.bloqueantes:
            borradores.marcar(borrador["id"], EstadoDeBorrador.RECHAZADO)
            registrar_transicion(self.conn, tarea["id"], EstadoDeTarea.RECHAZADA.value)
            registrar_transicion(self.conn, tarea["id"], EstadoDeTarea.ESCALADA.value)
            ColaDeTareas(self.conn).anotar_falta(
                tarea["id"], tuple(d.regla_violada for d in resultado.bloqueantes)
            )
            return ResultadoDeVuelta(
                tarea_id=tarea["id"],
                tipo=tarea["tipo"],
                estado=EstadoDeTarea.ESCALADA.value,
                detalle=resultado.explicacion(),
            )

        # Sin defectos criticos el borrador avanza hasta donde v1 puede llevarlo, y no mas.
        # `en_revision` y no `aceptado`: la puerta sigue trayendo evidencia ausente.
        borradores.marcar(borrador["id"], EstadoDeBorrador.EN_REVISION)
        registrar_transicion(self.conn, tarea["id"], EstadoDeTarea.ACEPTADA.value)
        return ResultadoDeVuelta(
            tarea_id=tarea["id"],
            tipo=tarea["tipo"],
            estado=EstadoDeTarea.ACEPTADA.value,
            detalle=resultado.explicacion(),
        )

    # --- canonizacion -------------------------------------------------------------------

    def _canonizar(self, tarea: Fila) -> ResultadoDeVuelta:
        """Contrasta los hechos declarados contra el canon vigente y promueve lo que cabe.

        Se canoniza aunque el borrador no este `aceptado`, y conviene decir por que: lo que
        protege al canon no es el estado del borrador, es el propio Canonizador, que nunca
        sobrescribe lo que contradice y emite un `Defecto` en su lugar. Si se esperara a la
        aceptacion, en v1 el canon no creceria nunca y el capitulo 2 se escribiria sin saber
        nada del 1.
        """
        escena_id = _sujeto_de(tarea["id"])
        borradores = Borradores(self.conn)
        borrador = borradores.ultimo_no_obsoleto(escena_id)
        if borrador is None:
            return self._parar(tarea, "no hay borrador que canonizar")

        capitulo_id = self._capitulo_de(escena_id)
        evento = self._evento_de(escena_id)
        declarados = list(
            enumerate(borradores.hechos_declarados(borrador["id"]), start=1)
        )
        # El catalogo de predicados es cerrado y se amplia por migracion (R-7). Un modelo
        # real declara a veces predicados que no estan -«estado_inicial», «accion»-, y
        # meterlos tal cual rompia la canonizacion entera con una violacion de clave
        # foranea. Se promueve lo que cabe y lo que no queda anotado como defecto, con el
        # hecho entero como evidencia, en lugar de perderse o de tumbar la escena.
        catalogo = {predicado.nombre for predicado in CatalogoDePredicados(self.conn).todos()}
        fuera_de_catalogo = [
            (numero, hecho) for numero, hecho in declarados if hecho[1] not in catalogo
        ]
        Defectos(self.conn).guardar(
            [
                Defecto(
                    id=f"df-{borrador['id']}-predicado-{numero}",
                    tipo="predicado_fuera_de_catalogo",
                    severidad=Severidad.BAJA,
                    regla_violada="todo predicado usado por un Hecho esta en el catalogo",
                    evidencia=f"{sujeto} | {predicado} | {objeto}",
                    borrador_id=borrador["id"],
                )
                for numero, (sujeto, predicado, objeto) in fuera_de_catalogo
            ],
            detectado_por="canonizador",
        )
        nuevos = [
            Hecho(
                id=f"he-{borrador['id']}-{numero}",
                sujeto_id=sujeto,
                predicado=predicado,
                objeto=objeto,
                valido_desde=evento,
            )
            for numero, (sujeto, predicado, objeto) in declarados
            if evento and predicado in catalogo
        ]

        resultado = Canonizador(self.conn).canonizar(
            borrador["id"],
            nuevos,
            self._hechos_vigentes(),
            self._orden_de_eventos(),
            escena_id=escena_id,
            capitulo_id=capitulo_id,
        )
        Defectos(self.conn).guardar(resultado.defectos, detectado_por="canonizador")
        if resultado.promovidos:
            self._cerrar_intervalos(resultado.intervalos_cerrados, nuevos)
            self._insertar_hechos(nuevos, resultado.promovidos)
            borradores.marcar_canonizados(borrador["id"])

        self._resumir_capitulo(capitulo_id, resultado.revision)
        if self._capitulo_completo(capitulo_id):
            self._cerrar_capitulo(capitulo_id, leer_encargo(self.conn, tarea["volumen_id"]))
        self._aceptar(tarea)
        self._publicar_si_termino(tarea)

        return ResultadoDeVuelta(
            tarea_id=tarea["id"],
            tipo=tarea["tipo"],
            estado=EstadoDeTarea.ACEPTADA.value,
            detalle=(
                f"revision {resultado.revision}; {len(resultado.promovidos)} hecho(s) "
                f"promovido(s), {len(resultado.defectos)} contradiccion(es)"
            ),
        )

    def _cerrar_intervalos(self, cerrados: tuple[str, ...], nuevos: list[Hecho]) -> None:
        """Aplica a la tabla de hechos los intervalos que la canonizacion cerro.

        El Canonizador registra el cierre como evento de cambio -el canon se reconstruye
        plegando, no copiando- pero la tabla `hecho` es la vista materializada que leen
        tanto la story bible como la propia canonizacion siguiente. Sin este paso, la
        escena 3 encuentra dos ubicaciones abiertas del mismo personaje, no puede decidir
        cual sucede a cual, y reporta como contradiccion lo que era una mudanza.
        """
        if not nuevos:
            return
        corte = nuevos[0].valido_desde
        for identificador in cerrados:
            self.conn.execute(
                "UPDATE hecho SET valido_hasta = ? WHERE id = ? AND valido_hasta IS NULL",
                (corte, identificador),
            )

    def _insertar_hechos(self, nuevos: list[Hecho], promovidos: tuple[str, ...]) -> None:
        """Escribe en `hecho` lo que la canonizacion dejo promovido, y solo eso."""
        for hecho in nuevos:
            if hecho.id not in promovidos:
                continue
            self.conn.execute(
                "INSERT OR IGNORE INTO hecho (id, sujeto_id, predicado, objeto, "
                "valido_desde) VALUES (?, ?, ?, ?, ?)",
                (
                    hecho.id,
                    hecho.sujeto_id,
                    hecho.predicado,
                    hecho.objeto,
                    hecho.valido_desde,
                ),
            )

    def _publicar_si_termino(self, tarea: Fila) -> None:
        """Publica la version cuando ya no queda trabajo vivo en el plan.

        La version anterior no se toca nunca (RF-LEC-07): se publica una nueva con su
        numero, y la lectura puede seguir abriendo la de antes.
        """
        if ColaDeTareas(self.conn).listas_del_plan(tarea["plan_id"]) > 0:
            return
        capitulos = tuple(
            fila["id"]
            for fila in self.conn.execute(
                "SELECT id FROM capitulo WHERE volumen_id = ? ORDER BY orden",
                (tarea["volumen_id"],),
            ).fetchall()
        )
        if not capitulos:
            return
        VersionesDeNovela(self.conn).publicar(
            f"ver-{uuid.uuid4().hex[:8]}",
            volumen_id=tarea["volumen_id"],
            capitulos=capitulos,
            motivo=f"escritura completa en modo {self.modo.value}",
        )

    def _resumir_capitulo(self, capitulo_id: str, revision: int) -> None:
        """Un resumen del capitulo compuesto de sus escenas, sin invocar a nadie.

        Es lo que mantiene constante el paquete del capitulo 40 (RF-BIB-03). Se compone de
        los esqueletos y no de la prosa a proposito: un resumen generado costaria una
        invocacion por capitulo y podria contar algo que la escena no cuenta.
        """
        filas = self.conn.execute(
            "SELECT objetivo, resultado FROM escena WHERE capitulo_id = ? ORDER BY orden",
            (capitulo_id,),
        ).fetchall()
        if not filas:
            return
        texto = " ".join(f"{fila['objetivo']}; {fila['resultado']}." for fila in filas)
        ResumenesDeCapitulo(self.conn).guardar(capitulo_id, texto, revision_canon=revision)

    # --- piezas comunes ------------------------------------------------------------------

    def _invocar(
        self, tarea: Fila, ensamblador: Ensamblador, *, agente: str
    ) -> Invocacion | None:
        """Reserva, ensambla, invoca y registra. Devuelve `None` si la llamada no salio.

        El registro del paquete y de la procedencia ocurre **siempre**, incluso cuando la
        invocacion falla: sin eso, un fallo de coherencia deja de ser reproducible, y las
        invocaciones pagadas y perdidas no se ven en ningun sitio.
        """
        paquete_id = f"pq-{uuid.uuid4().hex[:12]}"
        try:
            paquete, prompt = ensamblador.ensamblar(tarea["id"], paquete_id)
        except PresupuestoExcedido as excedido:
            ColaDeTareas(self.conn).anotar_falta(
                tarea["id"], bloqueada_por_presupuesto(excedido)
            )
            return None

        registro = RegistroDeInvocacion(self.conn)
        registro.guardar_paquete(paquete)
        self.semaforo.admitir(tarea["id"], RESERVA_DE_REDACCION, tarea["prioridad"])

        # Se confirma lo escrito hasta aqui -la tarea `en_curso` y su paquete- antes de
        # invocar. Una invocacion tarda de segundos a minutos, y mantener abierta la
        # transaccion de escritura todo ese tiempo bloquea la base para la API: guardar
        # una entrevista mientras se escribe otra novela acababa en «database is locked».
        # No rompe RF-STO-06: el artefacto y la transicion que lo acepta se siguen
        # escribiendo juntos, despues de la invocacion. Y un `en_curso` confirmado es
        # justo lo que `reanudar_al_arrancar` sabe recuperar si el proceso se cae aqui.
        self.conn.commit()

        crudo = Worker(cliente=self.cliente, agente=agente).invocar(
            tarea["id"], paquete_id, prompt
        )
        registro.guardar_procedencia(crudo.procedencia)
        self._observar(tarea, crudo.procedencia)

        if crudo.clase_de_fallo is not None:
            cola = ColaDeTareas(self.conn)
            cola.anotar_intento(
                tarea["id"], clase=crudo.clase_de_fallo.value, tipo_de_defecto=None
            )
            cola.anotar_falta(tarea["id"], (crudo.detalle_del_fallo,))
            return None
        return Invocacion(crudo=crudo, paquete=paquete)

    def _observar(self, tarea: Fila, procedencia: Procedencia) -> None:
        """Envia la llamada al observador, despues de guardarla en SQLite.

        Va despues a proposito: la procedencia es la fuente de verdad y ya esta escrita
        cuando se observa (SPEC-003 S-02). El cliente de Langfuse descarta sus propios
        fallos; este `try` es para que ni un cliente mal hecho pare la escritura.
        """
        posicion = self.conn.execute(
            """
            SELECT pl.volumen_id, e.id AS escena_id, c.orden AS capitulo_orden
            FROM tarea t
            JOIN plan pl ON pl.id = t.plan_id
            LEFT JOIN escena e ON t.id = e.id || ':redaccion'
            LEFT JOIN capitulo c ON c.id = e.capitulo_id
            WHERE t.id = ?
            """,
            (tarea["id"],),
        ).fetchone()
        if posicion is None or posicion["volumen_id"] is None:
            return
        try:
            registrar_llamada(
                self.observabilidad,
                LlamadaObservada(
                    procedencia_id=procedencia.id,
                    volumen_id=posicion["volumen_id"],
                    agente=procedencia.agente,
                    tarea=tarea["tipo"],
                    modelo=procedencia.modelo,
                    version_de_prompt=procedencia.version_de_prompt,
                    tokens_entrada=procedencia.tokens_entrada,
                    tokens_salida=procedencia.tokens_salida,
                    coste=procedencia.coste,
                    latencia_ms=procedencia.latencia_ms,
                    clase_de_fallo=(
                        None
                        if procedencia.clase_de_fallo is None
                        else procedencia.clase_de_fallo.value
                    ),
                    escena_id=posicion["escena_id"],
                    capitulo_orden=posicion["capitulo_orden"],
                    modo=self.modo.value,
                ),
            )
        except Exception:  # noqa: BLE001 - observar nunca para la escritura (RF-LAN-03)
            return

    def _anotar_apertura_rechazada(self, tarea: Fila) -> None:
        ColaDeTareas(self.conn).anotar_intento(
            tarea["id"], clase=ClaseDeFallo.CONTRATO.value, tipo_de_defecto="apertura"
        )

    def _candidatos_de_apertura(self) -> int:
        """Tres si el cliente admite invocaciones simultaneas; uno si no (RF-TIE-05).

        Los clientes deterministas -demostracion y pruebas- devolverian tres veces lo mismo,
        y con varios hilos sus guiones dependerian del orden en que llegan.
        """
        if getattr(self.cliente, "admite_concurrencia", False):
            return CANDIDATOS_DE_APERTURA
        return 1

    def _invocar_candidatos(
        self, tarea: Fila, ensamblador: Ensamblador, *, agente: str, cuantos: int
    ) -> list[Invocacion]:
        """El mismo paquete a `cuantos` invocaciones simultaneas. Devuelve las que salieron.

        Los hilos **solo** invocan al modelo: ensamblar, registrar la procedencia y escribir
        en la base se queda en este hilo, porque la conexion SQLite no se comparte entre
        hilos a la vez. Cada candidato reserva su credito y lo libera al terminar, salga
        bien o mal (RF-TIE-04), y deja su procedencia aunque se descarte (RF-TIE-03).
        """
        if cuantos <= 1:
            invocacion = self._invocar(tarea, ensamblador, agente=agente)
            return [] if invocacion is None else [invocacion]

        paquete_id = f"pq-{uuid.uuid4().hex[:12]}"
        try:
            paquete, prompt = ensamblador.ensamblar(tarea["id"], paquete_id)
        except PresupuestoExcedido as excedido:
            ColaDeTareas(self.conn).anotar_falta(
                tarea["id"], bloqueada_por_presupuesto(excedido)
            )
            return []

        registro = RegistroDeInvocacion(self.conn)
        registro.guardar_paquete(paquete)
        # Tantos candidatos como quepan en el credito libre, y al menos uno: encolar un
        # candidato detras de los otros dos seria volver a invocar en serie.
        libre = self.semaforo.credito_total - self.semaforo.en_vuelo
        cuantos = max(1, min(cuantos, libre // RESERVA_DE_REDACCION))
        reservas = [f"{tarea['id']}#candidato-{numero}" for numero in range(1, cuantos + 1)]
        for reserva in reservas:
            self.semaforo.admitir(reserva, RESERVA_DE_REDACCION, tarea["prioridad"])
        self.conn.commit()

        worker = Worker(cliente=self.cliente, agente=agente)
        try:
            with ThreadPoolExecutor(max_workers=cuantos) as hilos:
                crudos = list(
                    hilos.map(
                        lambda _: worker.invocar(tarea["id"], paquete_id, prompt), reservas
                    )
                )
        finally:
            for reserva in reservas:
                self.semaforo.liberar(reserva)

        cola = ColaDeTareas(self.conn)
        salieron: list[Invocacion] = []
        for crudo in crudos:
            registro.guardar_procedencia(crudo.procedencia)
            self._observar(tarea, crudo.procedencia)
            if crudo.clase_de_fallo is not None:
                cola.anotar_intento(
                    tarea["id"], clase=crudo.clase_de_fallo.value, tipo_de_defecto=None
                )
                cola.anotar_falta(tarea["id"], (crudo.detalle_del_fallo,))
                continue
            salieron.append(Invocacion(crudo=crudo, paquete=paquete))
        return salieron

    def _artefacto_previo(
        self, tarea: Fila, ensamblador: Ensamblador, intento: int
    ) -> str | None:
        """Lo ya producido con esta misma clave de ejecucion, si lo hay (RF-ORQ-13).

        Se comprueba antes de invocar y no despues, que es lo unico que lo hace valer para
        algo: comprobarlo despues ahorraria la escritura y no la llamada, que es lo caro.
        """
        paquete_id = f"pq-{uuid.uuid4().hex[:12]}"
        try:
            paquete, _ = ensamblador.ensamblar(tarea["id"], paquete_id)
        except PresupuestoExcedido:
            return None
        return artefacto_ya_producido(self.conn, self._clave(tarea, paquete, intento))

    def _clave(
        self, tarea: Fila, paquete: PaqueteDeContexto, intento: int
    ) -> ClaveDeTarea:
        return ClaveDeTarea(
            plan_id=tarea["plan_id"],
            objetivo=tarea["id"],
            revision_de_canon=paquete.revision_canon,
            hash_del_paquete=paquete.hash,
            version_de_prompt=VERSION_DEL_REDACTOR,
            intento=intento,
        )

    def _toca_escalar(self, tarea_id: str) -> bool:
        """Si la escalera de `estados.py` dice que ya no hay que reintentar."""
        tarea = Tarea(id=tarea_id, plan_id="", tipo="redaccion", rol_asignado="redactor")
        for fila in ColaDeTareas(self.conn).intentos_de(tarea_id):
            if fila["clase_de_fallo"] is None:
                continue
            tarea = clasificar(
                tarea, ClaseDeFallo(fila["clase_de_fallo"]), fila["tipo_de_defecto"]
            )
        return siguiente_accion(tarea) is Accion.ESCALAR

    def _aceptar(self, tarea: Fila) -> None:
        registrar_transicion(self.conn, tarea["id"], EstadoDeTarea.EN_VERIFICACION.value)
        registrar_transicion(self.conn, tarea["id"], EstadoDeTarea.ACEPTADA.value)

    def _parar(self, tarea: Fila, motivo: str) -> ResultadoDeVuelta:
        """Detiene la tarea informando. Nunca se reintenta indefinidamente (RF-HAR-06)."""
        registrar_transicion(self.conn, tarea["id"], EstadoDeTarea.EN_VERIFICACION.value)
        registrar_transicion(self.conn, tarea["id"], EstadoDeTarea.ESCALADA.value)
        ColaDeTareas(self.conn).anotar_falta(tarea["id"], (motivo,))
        return ResultadoDeVuelta(
            tarea_id=tarea["id"],
            tipo=tarea["tipo"],
            estado=EstadoDeTarea.ESCALADA.value,
            detalle=motivo,
        )

    # --- lecturas de apoyo -----------------------------------------------------------------

    def _revision(self) -> int:
        return CanonVersionado(self.conn).revision_actual()

    def _escenas_de(self, volumen_id: str) -> tuple[str, ...]:
        filas = self.conn.execute(
            "SELECT e.id FROM escena e JOIN capitulo c ON c.id = e.capitulo_id "
            "WHERE c.volumen_id = ? ORDER BY c.orden, e.orden",
            (volumen_id,),
        ).fetchall()
        return tuple(fila["id"] for fila in filas)

    def _capitulo_de(self, escena_id: str) -> str:
        fila = self.conn.execute(
            "SELECT capitulo_id FROM escena WHERE id = ?", (escena_id,)
        ).fetchone()
        return "" if fila is None else str(fila["capitulo_id"])

    def _evento_de(self, escena_id: str) -> str:
        fila = self.conn.execute(
            "SELECT evento_id FROM escena_evento WHERE escena_id = ? ORDER BY evento_id "
            "LIMIT 1",
            (escena_id,),
        ).fetchone()
        return "" if fila is None else str(fila["evento_id"])

    def _personajes_del_capitulo(self, capitulo_id: str) -> tuple[str, ...]:
        """Los nombres canonicos que el capitulo puede nombrar, para RF-VAL-02."""
        filas = self.conn.execute(
            """
            SELECT DISTINCT p.nombre_canonico
            FROM personaje p
            JOIN escena e ON e.pov_id = p.id
            WHERE e.capitulo_id = ?
            ORDER BY p.nombre_canonico
            """,
            (capitulo_id,),
        ).fetchall()
        return tuple(fila["nombre_canonico"] for fila in filas)

    def _hechos_vigentes(self) -> list[Hecho]:
        filas = self.conn.execute(
            "SELECT id, sujeto_id, predicado, objeto, valido_desde, valido_hasta "
            "FROM hecho ORDER BY id"
        ).fetchall()
        return [
            Hecho(
                id=fila["id"],
                sujeto_id=fila["sujeto_id"],
                predicado=fila["predicado"],
                objeto=fila["objeto"],
                valido_desde=fila["valido_desde"],
                valido_hasta=fila["valido_hasta"],
            )
            for fila in filas
        ]

    def _orden_de_eventos(self) -> dict[str, int]:
        filas = self.conn.execute(
            "SELECT id, posicion_en_historia FROM evento ORDER BY posicion_en_historia"
        ).fetchall()
        return {fila["id"]: int(fila["posicion_en_historia"]) for fila in filas}


# --- funciones de apoyo -----------------------------------------------------------------


def _sujeto_de(tarea_id: str) -> str:
    """La escena de la que habla una tarea. El sufijo es el tipo, no parte del nombre."""
    return tarea_id.rsplit(":", 1)[0]


def _prosa_de(texto: str) -> SalidaDelRedactor | None:
    """La salida del Redactor, validada, o `None` si no valida contra su esquema."""
    try:
        return parsear(texto)
    except SalidaInvalida:
        return None


def _destinatario_de(encargo: EncargoDeNovela) -> Destinatario:
    """El destinatario que el hook de capitulo necesita, reconstruido del encargo.

    Los recuerdos obligatorios entran como `ElementoPersonalizado`: no es un detalle de
    construccion, es que un `Destinatario` sin ninguno no es valido por invariante, y con
    razon -sin elemento obligatorio no hay nada que el validador de RF-VAL-04 pueda buscar
    en los capitulos-.
    """
    return Destinatario(
        id=encargo.destinatario_id,
        nombre=encargo.nombre,
        edad=encargo.edad or 0,
        rasgos=encargo.rasgos,
        elementos=tuple(
            ElementoPersonalizado(
                id=recuerdo.id,
                tipo=TipoDeElementoPersonalizado.RECUERDO,
                contenido=recuerdo.contenido,
            )
            for recuerdo in encargo.recuerdos
        ),
        dedicatoria=encargo.dedicatoria,
    )
