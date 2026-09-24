"""Cliente de modelo. Aqui, y solo aqui, viven las llamadas al proveedor.

`api/` no lo alcanza por ninguna ruta: encola una `Tarea` y lee estado. El trabajo ocurre
aqui (`architecture.md` 2.3, regla 5).

La invocacion esta detras de un protocolo a proposito. No es una abstraccion gratuita:
sin ella el bucle de E7 no se podria ejecutar ni probar sin credenciales, y el sistema
solo se sabria roto la primera vez que alguien pagara por descubrirlo.

Desde SPEC-004 hay **dos** clientes construibles y la diferencia entre ellos no se puede
perder de vista: el real invoca el modelo de D-17, y el de demostracion fabrica prosa
determinista para que el recorrido se pueda ver sin credencial. El segundo **nunca** se
elige solo (D-20): hay que pedirlo por su nombre, y lo que produce queda marcado en la
`Procedencia` con `modelo = demostracion`. Caer en el en silencio seria exactamente la
bajada de modelo que D-08 prohibe, y produciria una novela que nadie sabe que no es del
modelo.

Cubre RF-WRK-01 a RF-WRK-05, RF-WRK-09 y RF-MOD-01 a RF-MOD-03.
"""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import tempfile
import time
from dataclasses import dataclass, field
from typing import Any, Protocol

from backend.context.presupuesto import TECHO_DE_SALIDA_REDACCION
from backend.domain.vocabularies import ClaseDeFallo, ModoDeEscritura

# D-17 (`architecture.md` 5.1), que sustituye a R-1. Es el nombre canonico que queda en la
# `Procedencia` cuando Claude Code no informa de otro.
MODELO_DEL_REDACTOR = "claude-haiku-4-5"

# El nombre que lleva toda `Procedencia` producida sin modelo. Es deliberadamente un
# nombre y no una bandera aparte: quien mire la tabla dentro de un anio vera en la misma
# columna que mira siempre que ese borrador no salio de ningun proveedor.
MODELO_DE_DEMOSTRACION = "demostracion"

# El modelo real se invoca a traves de Claude Code, no de la API HTTP: asi el sistema no
# pide ninguna clave propia y reutiliza la sesion con la que Claude Code ya esta
# autenticado. `haiku` es el alias de Claude Code para el Haiku vigente.
MODELO_DE_CLAUDE_CODE = "haiku"

# Por si `claude` no esta en el PATH del proceso que arranca el worker: aqui se puede dar
# la ruta completa del ejecutable.
VARIABLE_DEL_EJECUTABLE = "MYSTORYMAKER_CLAUDE"

# Claude Code trae su propio prompt de sistema de asistente de programacion. Se sustituye
# por uno que lo deja en lo que el sistema necesita: un modelo que contesta en el formato
# que pide el contrato del rol, sin preambulo.
PROMPT_DE_SISTEMA = (
    "Eres el modelo de texto de MyStoryMaker. Responde unicamente con lo que pide el "
    "mensaje del usuario, en exactamente el formato que su contrato describe: sin "
    "preambulo, sin comentarios, sin bloques de codigo alrededor y sin explicar lo que "
    "vas a hacer. Escribe en espanol."
)

TIMEOUT_DE_INVOCACION_S = 10 * 60

# El techo de salida es el de `architecture.md` 4.2, no uno mayor: con 8.000 la reserva
# subiria a 32.000 y tres escenas concurrentes mas un juicio pasarian de 100.000.
MAX_TOKENS_REDACCION = TECHO_DE_SALIDA_REDACCION

# Sin pensamiento extendido: este modelo solo admite presupuesto fijo, y ese presupuesto
# sale del mismo techo de 4.000 que la prosa. Pensar recortaria la escena hasta truncarla,
# y una salida truncada es fallo de contrato (`architecture.md` 6.5). Activarlo exige subir
# el techo y recalibrar 4.2, o sea una spec.
PENSAMIENTO = None
# Sin `effort`: el modelo lo rechaza.
ESFUERZO = None


class FalloDeInvocacion(Exception):
    """Un fallo que el worker describe con precision suficiente para clasificarlo.

    Un worker que solo sabe decir «ha fallado» obliga al Orquestador a tratar todo fallo
    como el peor caso (D-02).
    """

    def __init__(self, clase: ClaseDeFallo, detalle: str) -> None:
        self.clase = clase
        self.detalle = detalle
        super().__init__(f"Invocacion fallida [{clase.value}]: {detalle}")


class ClaudeCodeAusente(RuntimeError):
    """No hay con que invocar el modelo, y se dice exactamente que falta y que hacer.

    Es su propia excepcion y no un `FalloDeInvocacion` porque no es un fallo de la
    invocacion: es que la invocacion no se puede ni intentar. La ruta la traduce en un
    `503` con este mismo texto, en lugar de caer en demostracion por su cuenta.
    """

    def __init__(self) -> None:
        super().__init__(
            f"No se encuentra Claude Code: el ejecutable «claude» no esta en el PATH del "
            f"proceso. Instalalo (npm install -g @anthropic-ai/claude-code), inicia sesion "
            f"una vez con «claude» y vuelve a arrancar, o da su ruta completa en la "
            f"variable {VARIABLE_DEL_EJECUTABLE}. Tambien puedes pedir explicitamente el "
            f"modo «demostracion», que escribe prosa determinista sin modelo y la marca "
            f"como tal. Lo que no ocurre es caer en demostracion en silencio: una novela "
            f"que nadie sabe que no es del modelo es peor que una novela que no esta escrita."
        )


@dataclass(frozen=True)
class Respuesta:
    """Lo que devuelve una invocacion, con lo que hace falta para la `Procedencia`."""

    texto: str
    tokens_entrada: int
    tokens_salida: int
    modelo: str
    truncada: bool = False
    coste: float = 0.0
    latencia_ms: int = 0


class ClienteDeModelo(Protocol):
    """Lo minimo que el worker necesita de un proveedor."""

    @property
    def modelo(self) -> str:
        """Que hay al otro lado. Es lo que acaba escrito en la `Procedencia`."""
        ...

    def invocar(self, prompt: str, *, max_tokens: int) -> Respuesta: ...


@dataclass
class ClienteFalso:
    """Cliente determinista para pruebas y para el bucle de E7 sin credenciales.

    No simula calidad literaria: simula el **contrato**. Devuelve lo que se le programa,
    y eso basta para comprobar que el orquestador clasifica, reintenta, canoniza y
    escala como debe.
    """

    respuestas: list[Respuesta | Exception] = field(default_factory=list)
    invocaciones: list[str] = field(default_factory=list)

    @property
    def modelo(self) -> str:
        return MODELO_DEL_REDACTOR

    def invocar(self, prompt: str, *, max_tokens: int) -> Respuesta:
        self.invocaciones.append(prompt)
        if not self.respuestas:
            raise FalloDeInvocacion(ClaseDeFallo.TRANSPORTE, "sin respuestas programadas")
        siguiente = self.respuestas.pop(0)
        if isinstance(siguiente, Exception):
            raise siguiente
        if siguiente.tokens_salida > max_tokens:
            # Alcanzar el techo trunca la salida, y eso es fallo de contrato, no una
            # invitacion a ampliar el techo (`architecture.md` 6.6).
            raise FalloDeInvocacion(
                ClaseDeFallo.CONTRATO,
                f"salida truncada al alcanzar max_tokens={max_tokens}",
            )
        return siguiente


@dataclass
class ClienteClaudeCode:
    """El proveedor de verdad: Claude Code en modo no interactivo, con Haiku.

    El orquestador del sistema sigue siendo `orchestrator/`; lo que cambia es **quien
    responde** a cada invocacion. En lugar de hablar HTTP con la API de mensajes -que
    exige una clave propia-, se lanza `claude -p` y se reutiliza la sesion con la que la
    persona ya tiene Claude Code autenticado. No hay credencial que copiar a `.env`.

    Se invoca como modelo de texto y nada mas: sin herramientas, sin MCP, sin ajustes de
    proyecto y sin persistir la sesion. Un Claude Code con herramientas podria leer el
    repositorio o escribir ficheros en mitad de una escena, y eso no es redactar.

    El prompt viaja por la entrada estandar y no como argumento: un paquete de contexto
    pasa con holgura del limite de la linea de comandos de Windows.

    Es una funcion de proceso y poco mas, a proposito: toda la politica -reintentos
    narrativos, clasificacion, presupuesto- vive fuera. Lo unico que este objeto decide es
    como se traduce un fallo del proceso en una de las cuatro clases de D-06.
    """

    ejecutable: str
    modelo_solicitado: str = MODELO_DE_CLAUDE_CODE
    timeout_s: int = TIMEOUT_DE_INVOCACION_S

    @property
    def modelo(self) -> str:
        return MODELO_DEL_REDACTOR

    def argumentos(self) -> list[str]:
        return [
            self.ejecutable,
            "-p",
            "--model",
            self.modelo_solicitado,
            "--output-format",
            "json",
            "--tools",
            "",
            "--strict-mcp-config",
            "--setting-sources",
            "",
            "--no-session-persistence",
            "--system-prompt",
            PROMPT_DE_SISTEMA,
        ]

    def invocar(self, prompt: str, *, max_tokens: int) -> Respuesta:
        comienzo = time.monotonic()
        # Si el worker se arranca desde dentro de otra sesion de Claude Code, estas
        # variables harian creer al hijo que es una sesion anidada.
        entorno = {
            clave: valor
            for clave, valor in os.environ.items()
            if clave not in ("CLAUDECODE", "CLAUDE_CODE_ENTRYPOINT")
        }
        try:
            proceso = subprocess.run(
                self.argumentos(),
                input=prompt,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=self.timeout_s,
                env=entorno,
                # Fuera del repositorio: que no cargue su CLAUDE.md como instrucciones.
                cwd=tempfile.gettempdir(),
                check=False,
            )
        except subprocess.TimeoutExpired as error:
            raise FalloDeInvocacion(
                ClaseDeFallo.TRANSPORTE,
                f"Claude Code no respondio en {self.timeout_s} s",
            ) from error
        except OSError as error:
            raise FalloDeInvocacion(ClaseDeFallo.TRANSPORTE, str(error)) from error

        try:
            carga: dict[str, Any] = json.loads(proceso.stdout)
        except json.JSONDecodeError as error:
            detalle = (proceso.stderr or proceso.stdout).strip()[:500]
            raise FalloDeInvocacion(
                ClaseDeFallo.TRANSPORTE,
                f"Claude Code salio con {proceso.returncode} sin respuesta legible: "
                f"{detalle}",
            ) from error

        if carga.get("is_error") or carga.get("subtype") != "success":
            detalle = str(carga.get("result") or carga.get("subtype") or proceso.stderr)
            # Un error de la API con estado 4xx no mejora reintentando; el resto -cortes,
            # sobrecarga, limite de uso momentaneo- si puede.
            estado = carga.get("api_error_status")
            clase = (
                ClaseDeFallo.CONTRATO
                if isinstance(estado, int) and 400 <= estado < 500 and estado != 429
                else ClaseDeFallo.TRANSPORTE
            )
            raise FalloDeInvocacion(clase, f"Claude Code respondio con error: {detalle[:500]}")

        if carga.get("stop_reason") == "max_tokens":
            raise FalloDeInvocacion(
                ClaseDeFallo.CONTRATO,
                f"salida truncada al alcanzar max_tokens={max_tokens}",
            )

        uso = carga.get("usage", {})
        modelos = list((carga.get("modelUsage") or {}).keys())
        return Respuesta(
            texto=str(carga.get("result", "")),
            tokens_entrada=int(uso.get("input_tokens", 0))
            + int(uso.get("cache_read_input_tokens", 0))
            + int(uso.get("cache_creation_input_tokens", 0)),
            tokens_salida=int(uso.get("output_tokens", 0)),
            modelo=modelos[0] if modelos else MODELO_DEL_REDACTOR,
            coste=float(carga.get("total_cost_usd", 0.0) or 0.0),
            latencia_ms=int((time.monotonic() - comienzo) * 1000),
        )


@dataclass
class ClienteDeDemostracion:
    """Prosa determinista fabricada a partir del paquete de contexto, sin modelo.

    Existe para una cosa y solo para una: que el recorrido entero -encargo, apertura,
    escritura, lectura- se pueda **ver** en un entorno sin credencial. No simula calidad
    literaria y no pretende parecerlo; lo que respeta es el contrato de cada rol, que es
    lo unico que el resto del sistema consume.

    Lee el prompt para saber a quien contesta. No es un truco: el prompt empieza por el
    contrato del rol, asi que la misma senal que usaria un modelo es la que usa esto.
    """

    invocaciones: list[str] = field(default_factory=list)

    @property
    def modelo(self) -> str:
        return MODELO_DE_DEMOSTRACION

    def invocar(self, prompt: str, *, max_tokens: int) -> Respuesta:
        comienzo = time.monotonic()
        self.invocaciones.append(prompt)
        texto = (
            _apertura_de_demostracion(prompt)
            if "# Planner" in prompt
            else _prosa_de_demostracion(prompt)
        )
        return Respuesta(
            texto=texto,
            tokens_entrada=len(prompt) // 4,
            tokens_salida=len(texto) // 4,
            modelo=MODELO_DE_DEMOSTRACION,
            latencia_ms=int((time.monotonic() - comienzo) * 1000),
        )


# --- construccion -----------------------------------------------------------------------


def localizar_claude() -> str | None:
    """La ruta del ejecutable de Claude Code, o `None` si no hay.

    `shutil.which` resuelve tambien el `claude.cmd` que instala npm en Windows.
    """
    explicito = os.environ.get(VARIABLE_DEL_EJECUTABLE, "").strip()
    if explicito:
        return shutil.which(explicito)
    return shutil.which("claude")


def construir_cliente_real() -> ClienteDeModelo:
    """El cliente de Claude Code con Haiku.

    No se construye en import time: sin Claude Code instalado, importar este modulo debe
    seguir funcionando para que la suite corra.
    """
    ejecutable = localizar_claude()
    if ejecutable is None:
        raise ClaudeCodeAusente()
    return ClienteClaudeCode(ejecutable=ejecutable)


def construir_cliente(modo: ModoDeEscritura) -> ClienteDeModelo:
    """El cliente del modo pedido. El de demostracion **solo** si se pide por su nombre."""
    if modo is ModoDeEscritura.DEMOSTRACION:
        return ClienteDeDemostracion()
    return construir_cliente_real()


def exigir_que_se_puede_escribir(modo: ModoDeEscritura) -> None:
    """Comprueba que el modo se puede servir, sin construir nada que invoque.

    Existe para que `api/` pueda decidir el codigo de respuesta sin llegar a tener un
    cliente de modelo en el proceso web.
    """
    if modo is ModoDeEscritura.DEMOSTRACION:
        return
    if localizar_claude() is None:
        raise ClaudeCodeAusente()


def clasificar_excepcion(error: Exception) -> ClaseDeFallo:
    """Traduce un fallo en una de las cuatro clases de D-06.

    Es lo que permite que un corte de red no consuma el presupuesto de reescrituras de
    una escena.
    """
    if isinstance(error, FalloDeInvocacion):
        return error.clase
    if isinstance(error, TimeoutError):
        # Un vencimiento cuenta como fallo de contrato (D-07).
        return ClaseDeFallo.CONTRATO
    if isinstance(error, (ConnectionError, OSError)):
        return ClaseDeFallo.TRANSPORTE
    return ClaseDeFallo.CONTRATO


# --- la fabrica de la demostracion -------------------------------------------------------
# Lo que sigue compone texto a partir de las lineas que el ensamblador escribe en el
# componente de instruccion. Vive aqui, junto al cliente, porque es parte de lo que
# «el proveedor» devuelve: si viviera en `orchestrator/`, el orquestador estaria
# fabricando la salida que luego valida, que es justo lo que `AGENTS.md` 1 prohibe.


def _campo(prompt: str, nombre: str, por_defecto: str = "") -> str:
    coincidencia = re.search(rf"^{nombre}:\s*(.+)$", prompt, re.M)
    return coincidencia.group(1).strip() if coincidencia else por_defecto


def _lista(prompt: str, nombre: str) -> list[tuple[str, str]]:
    """Las filas `nombre id | contenido` del prompt, en el orden en que aparecen."""
    return [
        (coincidencia.group(1).strip(), coincidencia.group(2).strip())
        for coincidencia in re.finditer(rf"^{nombre}\s+(\S+)\s*\|\s*(.+)$", prompt, re.M)
    ]


def _identificador(texto: str, prefijo: str, numero: int) -> str:
    """Un id legible y estable. Estable importa: la apertura tiene que ser idempotente."""
    limpio = re.sub(r"[^a-z0-9]+", "-", texto.lower()).strip("-")[:20] or "sin-nombre"
    return f"{prefijo}-{numero}-{limpio}"


# Cuatro giros distintos, en rotacion. Que los capitulos de la muestra no salgan todos
# iguales no es un adorno: una previa en la que los dos capitulos son el mismo parrafo no
# deja ver si el sistema esta escribiendo dos cosas o repitiendo una.
GIROS: tuple[tuple[str, str, str, str], ...] = (
    (
        "lo que entonces no se dijo sigue sin decirse",
        "esta vez se dice",
        "distancia",
        "cercania",
    ),
    (
        "el sitio ya no es el que recordaba",
        "se queda de todas formas",
        "nostalgia",
        "incomodidad",
    ),
    (
        "nadie se acuerda igual que ella",
        "acepta que su version tambien vale",
        "duda",
        "certeza",
    ),
    (
        "hay una promesa vieja de por medio",
        "la cumple sin avisar a nadie",
        "deuda",
        "calma",
    ),
)


def _giro(numero: int) -> tuple[str, str, str, str]:
    """Conflicto, resultado y los dos valores de la escena. Deterministas por numero."""
    return GIROS[(numero - 1) % len(GIROS)]


def _nombre_de_lugar(recuerdo: str, numero: int) -> str:
    """Un nombre de lugar sacado del propio recuerdo, no una etiqueta generica.

    «el verano en que aprendio a nadar en Gijon» da «Gijon», que es un lugar; «El lugar de
    el verano en que aprendio a...» no lo es, y en la portada se nota.
    """
    # El `.*` es codicioso a proposito: en «el verano en que aprendio a nadar en Gijon» lo
    # que nombra el lugar es el ultimo «en», no el primero.
    coincidencia = re.search(r".*\ben\s+([^,.;]+)\s*$", recuerdo.strip(), re.I)
    if coincidencia:
        nombre = coincidencia.group(1).strip()
        return nombre[0].upper() + nombre[1:] if nombre else f"El lugar {numero}"
    return f"El lugar del recuerdo {numero}"


def _titular(recuerdo: str) -> str:
    """El recuerdo convertido en titulo de capitulo: acotado y con mayuscula inicial."""
    corto = recuerdo.strip()[:60].rstrip(" ,;:")
    return corto[0].upper() + corto[1:] if corto else "Sin titulo"


def _apertura_de_demostracion(prompt: str) -> str:
    """Un canon minimo y un reparto derivados del encargo, no inventados al azar."""
    nombre = _campo(prompt, "destinatario", "la persona que recibe la novela")
    tono = _campo(prompt, "tono", "cercano")
    recuerdos = _lista(prompt, "recuerdo")
    if not recuerdos:
        recuerdos = [("ep-0", f"un dia cualquiera en la vida de {nombre}")]

    protagonista = _identificador(nombre, "pe", 1)
    personajes = [
        f"- {protagonista} | {nombre} | protagonico | reconocerse en lo que le contaron",
        "- pe-2-voz-que-recuerda | La voz que recuerda | secundario | contar sin adornar",
    ]
    personajes = [f"{fila} | -" for fila in personajes]

    lugares: list[str] = []
    eventos: list[str] = []
    capitulos: list[str] = []
    escenas: list[str] = []
    for numero, (recuerdo_id, crudo) in enumerate(recuerdos, start=1):
        # La barra es el separador de campos del contrato: un recuerdo que la traiga
        # partiria la fila en dos y el plan se rechazaria por una razon que no es la suya.
        recuerdo = crudo.replace("|", "/")
        lugar = _identificador(recuerdo, "lu", numero)
        evento = _identificador(recuerdo, "ev", numero)
        conflicto, resultado, entrada, salida = _giro(numero)
        lugares.append(
            f"- {lugar} | {_nombre_de_lugar(recuerdo, numero)} | lo que alli se oye y "
            f"huele, en tono {tono}"
        )
        eventos.append(
            f"- {evento} | {recuerdo} | {numero * 10} | accion | {lugar} | {protagonista}"
        )
        capitulos.append(
            f"{numero}. {_titular(recuerdo)} | {evento} | {recuerdo} | {recuerdo_id}"
        )
        escenas.append(
            f"- esc-{numero} | {numero} | {protagonista} | {lugar} | {numero * 10} | "
            f"volver a {recuerdo} | {conflicto} | {resultado} | {entrada} | {salida} | "
            f"{'climax' if numero == len(recuerdos) else 'complicacion'} | accion | {evento}"
        )

    hechos = [f"- he-{numero}" for numero in range(1, len(recuerdos) + 1)]

    return "\n".join(
        [
            "## personajes",
            *personajes,
            "",
            "## lugares",
            *lugares,
            "",
            "## eventos",
            *eventos,
            "",
            "## capitulos",
            *capitulos,
            "",
            "## escenas",
            *escenas,
            "",
            "## hechos_requeridos",
            *hechos,
        ]
    )


def _prosa_de_demostracion(prompt: str) -> str:
    """Prosa compuesta con el esqueleto de la escena. Determinista y sin modelo."""
    pov = _campo(prompt, "pov", "quien mira")
    pov_id = _campo(prompt, "pov_id", "pe-desconocido")
    lugar = _campo(prompt, "lugar", "el sitio")
    objetivo = _campo(prompt, "objetivo", "algo que hacer")
    conflicto = _campo(prompt, "conflicto", "algo que se interpone")
    resultado = _campo(prompt, "resultado", "algo que cambia")
    entrada = _campo(prompt, "valor_entrada", "como estaba")
    salida = _campo(prompt, "valor_salida", "como queda")
    evento = _campo(prompt, "renderiza", "ev-1")

    parrafos = [
        f"{lugar} tenia esa manera de estar quieto que solo tienen los sitios a los que "
        f"se vuelve. {pov} lo reconocio antes de mirarlo, por el aire, por la forma en que "
        f"la luz caia sobre las cosas sin pedirle permiso a nadie. Penso, como se piensan "
        f"estas cosas -de lado, sin querer-, que los lugares no cambian: cambia quien "
        f"llega a ellos.",
        f"Habia venido a {objetivo.lower()}. Lo habia dicho en voz alta esa manana, delante "
        f"del espejo y sin mirarse del todo, y decirlo lo habia hecho mas pequeno y mas "
        f"posible a la vez. Era una de esas frases que solo funcionan si nadie las repite.",
        "Durante un rato no paso nada. Eso tambien forma parte de estas cosas: la mayoria "
        "del tiempo no pasa nada, y uno se convence de que asi va a seguir.",
        f"Pero {conflicto.lower()}. No de golpe, que habria sido mas facil, sino despacio, "
        f"como se estropean las cosas de verdad: dando tiempo a mirarlas, dando tiempo a "
        f"pensar que todavia se pueden arreglar.",
        f"{pov} se quedo quieto donde estaba. Hubo un momento -uno solo, y despues seria "
        f"imposible senalarlo- en que la cosa pudo haber ido de otra manera. Paso de largo "
        f"como pasan los trenes que no son el tuyo.",
        "Lo que vino despues fue mas simple de lo que nadie habria dicho. Casi siempre lo "
        "es. Las decisiones grandes se toman con la misma cara con la que se elige que "
        "comer, y por eso cuesta tanto reconocerlas cuando estan ocurriendo.",
        f"Y sin embargo {resultado.lower()}. No hubo ningun gesto que lo anunciara, ni una "
        f"frase que sirviera para contarlo despues. Hubo una manera distinta de respirar y "
        f"ya esta.",
        f"{pov} no supo en que momento exacto habia dejado de estar {entrada.lower()}. "
        f"Al salir de {lugar} ya estaba {salida.lower()}, y eso era lo unico que iba a "
        f"recordar de aquel dia cuando alguien, muchos anos despues, le preguntara como "
        f"fue.",
    ]

    return "\n".join(
        [
            "## prosa",
            "\n\n".join(parrafos),
            "",
            "## hechos_nuevos_detectados",
            f"- {pov_id} | ubicacion | {lugar}",
            "",
            "## eventos_narrados",
            f"- {evento}",
            "",
            "## siembras_tocadas",
        ]
    )
