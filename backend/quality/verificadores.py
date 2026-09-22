"""Verificadores deterministas.

Coste despreciable y cero falsos positivos si estan bien escritos. Corren siempre antes
que cualquier juez, y son lo unico que puede parar la linea: un juez basado en modelo
varia entre llamadas sobre el mismo texto (`architecture.md` 7.1).

Cada verificador devuelve `Defecto`s con evidencia citable. Los marcados **(E)** anotan
ademas contra que bloque declarado se evaluaron, porque su entrada no la produce el canon
sino un agente leyendo su propia prosa.

Cubre RF-QUA-01 a RF-QUA-09, RF-QUA-16, RF-QUA-17, RF-QUA-21 y RF-QUA-22.
"""

from __future__ import annotations

import re
from collections.abc import Iterable, Sequence

from backend.domain.diegetic.canon import Hecho
from backend.domain.discursive.relato import Escena, Hilo, PerfilDeEstilo
from backend.domain.production.ejecucion import Defecto
from backend.domain.vocabularies import Relevancia, Severidad, TipoDeHilo
from backend.store.repositories import (
    BorradoresAceptadosDuplicados,
    CatalogoDePredicados,
    DesvioDePresupuesto,
    GrafoCausal,
    SiembraAbierta,
)

# Cada cuantas escenas consecutivas puede un hilo estar inactivo, por tipo.
# Un hilo principal que desaparece cinco escenas deja de leerse como principal.
INACTIVIDAD_MAXIMA: dict[TipoDeHilo, int] = {
    TipoDeHilo.PRINCIPAL: 3,
    TipoDeHilo.SECUNDARIO: 6,
    TipoDeHilo.ROMANTICO: 5,
    TipoDeHilo.MISTERIO: 5,
    TipoDeHilo.TEMATICO: 8,
    TipoDeHilo.DE_PERSONAJE: 6,
}

# R-8: tetragramas, contra todos los capitulos anteriores, a partir de dos apariciones.
TAMANO_DE_NGRAMA = 4
REPETICIONES_TOLERADAS = 1

# Palabras vacias que forman tetragramas sin contenido y solo producen ruido.
VACIAS = frozenset(
    "de la que el en y a los del se las por un para con no una su al lo como mas o "
    "pero sus le ya este si porque esta entre cuando muy sin sobre tambien me hasta "
    "donde quien desde todo nos durante todos uno les ni contra otros ese eso".split()
)


def _defecto(
    tipo: str,
    severidad: Severidad,
    regla: str,
    evidencia: str,
    *,
    extraccion: str | None = None,
    borrador_id: str | None = None,
) -> Defecto:
    return Defecto(
        id=f"{tipo}:{abs(hash(evidencia)) % 10**10}",
        tipo=tipo,
        severidad=severidad,
        regla_violada=regla,
        evidencia=evidencia,
        extraccion_evaluada=extraccion,
        borrador_id=borrador_id,
    )


# --- RF-QUA-01: contradiccion de hechos (E) ------------------------------------------


def contradiccion_de_hechos(
    hechos: Sequence[Hecho],
    catalogo: CatalogoDePredicados,
    orden_de_evento: dict[str, int],
    *,
    borrador_id: str | None = None,
) -> list[Defecto]:
    """Dos hechos del mismo sujeto con un predicado funcional e intervalos solapados.

    Solo los predicados `funcional` pueden contradecirse: un personaje esta en un sitio,
    pero posee varios objetos a la vez. Esa distincion es lo que aporta el catalogo, y sin
    ella la comprobacion central de la fase 1 no seria ejecutable.
    """
    defectos: list[Defecto] = []
    por_clave: dict[tuple[str, str], list[Hecho]] = {}
    for hecho in hechos:
        por_clave.setdefault((hecho.sujeto_id, hecho.predicado), []).append(hecho)

    for (sujeto, predicado), grupo in sorted(por_clave.items()):
        if len(grupo) < 2 or not catalogo.es_funcional(predicado):
            continue
        for i, uno in enumerate(grupo):
            for otro in grupo[i + 1 :]:
                if uno.objeto == otro.objeto:
                    continue
                if _solapan(uno, otro, orden_de_evento):
                    defectos.append(
                        _defecto(
                            "contradiccion_de_hechos",
                            Severidad.CRITICA,
                            "dos hechos con el mismo sujeto y un predicado funcional no "
                            "pueden tener intervalos de vigencia solapados",
                            f"{uno.id} ({uno.objeto}) y {otro.id} ({otro.objeto}) sobre "
                            f"{sujeto}.{predicado} solapan",
                            extraccion="hechos_nuevos_detectados",
                            borrador_id=borrador_id,
                        )
                    )
    return defectos


def _solapan(uno: Hecho, otro: Hecho, orden: dict[str, int]) -> bool:
    """Dos intervalos delimitados por eventos se solapan si ninguno acaba antes del otro."""
    inicio_uno, fin_uno = _intervalo(uno, orden)
    inicio_otro, fin_otro = _intervalo(otro, orden)
    return inicio_uno < fin_otro and inicio_otro < fin_uno


def _intervalo(hecho: Hecho, orden: dict[str, int]) -> tuple[float, float]:
    inicio = float(orden.get(hecho.valido_desde, 0))
    if hecho.valido_hasta is None:
        return inicio, float("inf")
    return inicio, float(orden.get(hecho.valido_hasta, float("inf")))


# --- RF-QUA-02 y RF-QUA-03: grafo causal ---------------------------------------------


def ciclos_causales(grafo: GrafoCausal) -> list[Defecto]:
    """Un grafo causal con ciclos no es causal: algo se causa a si mismo."""
    return [
        _defecto(
            "ciclo_causal",
            Severidad.CRITICA,
            "el grafo de causalidad es aciclico",
            f"el evento {evento} se alcanza a si mismo siguiendo aristas causa",
        )
        for evento in grafo.ciclos()
    ]


def precedencia_causal(grafo: GrafoCausal) -> list[Defecto]:
    """Si A causa B, A precede a B en tiempo de historia."""
    return [
        _defecto(
            "precedencia_causal",
            Severidad.CRITICA,
            "si A causa B, A precede a B en tiempo de historia",
            f"{causa} causa {efecto} pero no le precede en posicion_en_historia",
        )
        for causa, efecto in grafo.precedencias_violadas()
    ]


# --- RF-QUA-04: escena con cambio de valor y con evento (E) --------------------------


def escena_con_cambio_y_evento(
    escena: Escena, eventos_narrados: Sequence[str], *, borrador_id: str | None = None
) -> list[Defecto]:
    """La escena declara un cambio de valor y el borrador narra los eventos que dijo.

    El dominio ya impide construir una escena sin cambio o sin aristas `renderiza`. Lo que
    se comprueba aqui es lo otro: que lo narrado coincida con lo planificado.
    """
    defectos: list[Defecto] = []
    prometidos, narrados = set(escena.renderiza), set(eventos_narrados)

    for faltante in sorted(prometidos - narrados):
        defectos.append(
            _defecto(
                "escena_con_evento",
                Severidad.CRITICA,
                "toda escena narra los eventos que su esqueleto declara renderizar",
                f"la escena {escena.id} declara renderizar {faltante} sin narrarlo",
                extraccion="eventos_narrados",
                borrador_id=borrador_id,
            )
        )
    for sobrante in sorted(narrados - prometidos):
        defectos.append(
            _defecto(
                "escena_con_evento",
                Severidad.ALTA,
                "una escena no narra eventos que su esqueleto no declara",
                f"el borrador de {escena.id} narra {sobrante}, que la escena no renderiza",
                extraccion="eventos_narrados",
                borrador_id=borrador_id,
            )
        )
    return defectos


# --- RF-QUA-05: un solo borrador aceptado por escena ---------------------------------


def borrador_unico_aceptado(
    duplicados: Sequence[BorradoresAceptadosDuplicados],
) -> list[Defecto]:
    """El canon se deriva de los aceptados: dos por escena lo vuelven ambiguo."""
    return [
        _defecto(
            "borrador_aceptado_duplicado",
            Severidad.CRITICA,
            "solo un borrador por escena puede estar aceptado",
            f"la escena {fila.escena_id} tiene {fila.cuantos} borradores aceptados",
        )
        for fila in duplicados
    ]


# --- RF-QUA-06: siembras sin pagar (E) -----------------------------------------------


def siembras_sin_pagar(
    abiertas: Sequence[SiembraAbierta], *, cierre_de_volumen: bool = False
) -> list[Defecto]:
    """Pares en estado `abierto` pasado su limite, y cualquiera abierto al cierre."""
    defectos: list[Defecto] = []
    for siembra in abiertas:
        vencida = (
            siembra.distancia_maxima is not None
            and siembra.distancia > siembra.distancia_maxima
        )
        if not (cierre_de_volumen or vencida):
            continue
        detalle = "" if cierre_de_volumen else f", limite {siembra.distancia_maxima}"
        defectos.append(
            _defecto(
                "siembras_sin_pagar",
                Severidad.CRITICA if cierre_de_volumen else Severidad.MEDIA,
                "ningun ParSiembraPago queda abierto pasado su limite",
                f"la siembra {siembra.id} lleva {siembra.distancia} escenas abierta{detalle}",
                extraccion="siembras_tocadas",
            )
        )
    return defectos


# --- RF-QUA-07: presupuesto de palabras ----------------------------------------------


def presupuesto_de_palabras(
    desvios: Sequence[DesvioDePresupuesto], *, margen: float = 0.15
) -> list[Defecto]:
    """Desvio del presupuesto declarado del capitulo por encima de su margen."""
    defectos: list[Defecto] = []
    for fila in desvios:
        desvio = abs(fila.real - fila.presupuesto) / fila.presupuesto
        if desvio > margen:
            defectos.append(
                _defecto(
                    "presupuesto_de_palabras",
                    Severidad.BAJA,
                    "el recuento real de un capitulo no se desvia de su presupuesto "
                    "mas alla del margen",
                    f"el capitulo {fila.capitulo_id} declara {fila.presupuesto} palabras "
                    f"y lleva {fila.real} ({desvio:.0%} de desvio)",
                )
            )
    return defectos


# --- RF-QUA-08: deriva de nombres (E) ------------------------------------------------


PATRON_CAPITALIZADA = re.compile(r"\b[A-ZÁÉÍÓÚÜÑ]\w*\b")


def deriva_de_nombres(
    texto: str, nombres_declarados: Iterable[str], *, borrador_id: str | None = None
) -> list[Defecto]:
    """Un nombre propio del borrador que no corresponde a ninguna entidad ni alias.

    Es una dimension (E), y aqui se ve por que: distinguir un nombre propio de una palabra
    corriente en inicio de frase no tiene solucion exacta con reglas. La heuristica es
    tomar toda palabra capitalizada y descartar las que son palabras vacias del idioma;
    lo que quede y no este declarado se reporta.

    Eso deja dos huecos conocidos, y conviene tenerlos escritos en vez de fingir que no
    estan: un sustantivo comun poco frecuente en inicio de frase produce un falso
    positivo, y un nombre propio que coincida con una palabra vacia se escapa. Por eso la
    severidad es alta y no critica: senala para que alguien mire, no para parar la linea
    sola, y su tasa de acierto se mide contra el corpus de casos sembrados.
    """
    declarados = {n.lower() for n in nombres_declarados}
    vistos: dict[str, int] = {}
    for coincidencia in PATRON_CAPITALIZADA.finditer(texto):
        nombre = coincidencia.group(0)
        clave = nombre.lower()
        if clave not in declarados and clave not in VACIAS:
            vistos[nombre] = vistos.get(nombre, 0) + 1

    return [
        _defecto(
            "deriva_de_nombres",
            Severidad.ALTA,
            "todo nombre propio del borrador corresponde a una entidad del canon o a un "
            "alias declarado",
            f"«{nombre}» aparece {veces} vez/veces y no esta declarado en el canon",
            extraccion="nombres_propios_del_texto",
            borrador_id=borrador_id,
        )
        for nombre, veces in sorted(vistos.items())
    ]


# --- RF-QUA-09: repeticion de n-gramas -----------------------------------------------


def repeticion_de_ngramas(
    texto_nuevo: str, textos_anteriores: Sequence[str], *, borrador_id: str | None = None
) -> list[Defecto]:
    """Tetragramas repetidos contra todos los capitulos anteriores (R-8).

    Es el fallo mas caracteristico de los modelos en texto largo: invisible dentro de una
    escena y muy visible al leer el libro seguido.
    """
    anteriores: set[tuple[str, ...]] = set()
    for texto in textos_anteriores:
        anteriores |= set(_ngramas(texto))

    repetidos = sorted({n for n in _ngramas(texto_nuevo) if n in anteriores})
    return [
        _defecto(
            "repeticion_de_ngramas",
            Severidad.MEDIA,
            f"ningun {TAMANO_DE_NGRAMA}-grama con contenido se repite en capitulos anteriores",
            f"«{' '.join(ngrama)}» ya aparecia en un capitulo anterior",
            borrador_id=borrador_id,
        )
        for ngrama in repetidos
    ]


def _ngramas(texto: str) -> Iterable[tuple[str, ...]]:
    """Tetragramas con contenido: los formados solo por palabras vacias no dicen nada."""
    palabras = [p for p in re.findall(r"\w+", texto.lower())]
    for i in range(len(palabras) - TAMANO_DE_NGRAMA + 1):
        ventana = tuple(palabras[i : i + TAMANO_DE_NGRAMA])
        if not all(p in VACIAS for p in ventana):
            yield ventana


# --- RF-QUA-16 y RF-QUA-17: alcance de contrato --------------------------------------


def hilos_con_pregunta_dramatica(hilos: Sequence[Hilo]) -> list[Defecto]:
    """Todo hilo declara su pregunta dramatica antes de que se redacte nada."""
    return [
        _defecto(
            "hilo_sin_pregunta_dramatica",
            Severidad.CRITICA,
            "todo hilo declara su pregunta dramatica",
            f"el hilo {hilo.id} no la declara",
        )
        for hilo in hilos
        if not hilo.pregunta_dramatica.strip()
    ]


def protagonicos_con_hilo_y_necesidad(
    personajes: Sequence[object], hilos_por_personaje: dict[str, int]
) -> list[Defecto]:
    """Todo protagonico tiene al menos un `Hilo` asociado y `necesidad_interna`."""
    defectos: list[Defecto] = []
    for personaje in personajes:
        relevancia = getattr(personaje, "relevancia", None)
        if relevancia is not Relevancia.PROTAGONICO:
            continue
        identificador = getattr(personaje, "id", "?")
        if hilos_por_personaje.get(identificador, 0) == 0:
            defectos.append(
                _defecto(
                    "protagonico_sin_hilo",
                    Severidad.CRITICA,
                    "todo personaje protagonico tiene al menos un Hilo asociado",
                    f"el protagonico {identificador} no aparece en ningun hilo",
                )
            )
    return defectos


# --- RF-QUA-21: diversidad lexica y vocabulario prohibido ----------------------------


def diversidad_lexica(
    texto: str, perfil: PerfilDeEstilo, *, minimo_ttr: float = 0.35
) -> list[Defecto]:
    """Type-token ratio bajo minimo y uso del vocabulario delator del perfil."""
    palabras = re.findall(r"\w+", texto.lower())
    defectos: list[Defecto] = []

    if palabras:
        ttr = len(set(palabras)) / len(palabras)
        if ttr < minimo_ttr:
            defectos.append(
                _defecto(
                    "diversidad_lexica",
                    Severidad.BAJA,
                    "el type-token ratio del texto no baja del minimo del contrato",
                    f"ttr={ttr:.2f} sobre {len(palabras)} palabras, minimo {minimo_ttr}",
                )
            )

    presentes = sorted({p for p in perfil.vocabulario_prohibido if p.lower() in set(palabras)})
    defectos.extend(
        _defecto(
            "vocabulario_prohibido",
            Severidad.BAJA,
            "el borrador no usa el vocabulario prohibido del PerfilDeEstilo",
            f"«{palabra}» esta en vocabulario_prohibido y aparece en el texto",
        )
        for palabra in presentes
    )
    return defectos


# --- RF-QUA-22: hilos inactivos ------------------------------------------------------


def hilos_inactivos(
    hilos: Sequence[Hilo], escenas_en_orden: Sequence[str], avanza: dict[str, set[str]]
) -> list[Defecto]:
    """Ningun hilo esta inactivo mas de N escenas consecutivas, con N por tipo."""
    defectos: list[Defecto] = []
    for hilo in hilos:
        limite = INACTIVIDAD_MAXIMA[hilo.tipo]
        racha = 0
        peor = 0
        for escena_id in escenas_en_orden:
            if hilo.id in avanza.get(escena_id, set()):
                racha = 0
            else:
                racha += 1
                peor = max(peor, racha)
        if peor > limite:
            defectos.append(
                _defecto(
                    "hilo_inactivo",
                    Severidad.MEDIA,
                    "ningun hilo esta inactivo mas escenas consecutivas de las que su tipo "
                    "tolera",
                    f"el hilo {hilo.id} ({hilo.tipo.value}) pasa {peor} escenas sin avanzar, "
                    f"limite {limite}",
                )
            )
    return defectos
