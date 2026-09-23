# SPEC-002 · Primera versión del frontend — Especificación de requisitos (SRS)

| | |
| --- | --- |
| **Identificador** | SPEC-002 |
| **Título** | Primera versión del frontend: las tres vistas de `CLAUDE.md` §2.3, generadas del contrato y cobradas por sus validadores |
| **Estado** | `aplazada` el 2026-09-23 por decisión de la persona autora, tras el documento de alcance que origina SPEC-003. Sigue siendo `propuesta` en lo demás —sus cuatro preguntas abiertas siguen abiertas— y no se construye hasta que SPEC-003 cierre |
| **Por qué se aplaza** | SPEC-003 pide un frontend de **lectura** para quien recibe la novela; éste especifica un frontend de **operación** para quien conduce el sistema. No se contradicen y no se descarta ninguno de los dos: se ordenan. Lo que el alcance evalúa es la lectura |
| **Fecha** | 2026-09-23 |
| **Documentos de referencia** | `docs/verification.md`, `docs/definitions.md`, `docs/architecture.md`, `AGENTS.md`, `CLAUDE.md` y la skill de Feature-Sliced Design, en su estado del 2026-09-23 |
| **Sujeto** | El frontend, y solo el frontend. Ningún requisito de este documento se satisface escribiendo código en `backend/` |
| **Contrato de la frontera** | El documento OpenAPI 3.1 que publica FastAPI. Manda él; ninguna tabla de este documento compite con el contrato |

> Esta es la spec única de `AGENTS.md` §10.2 para la primera versión del frontend, redactada
> como SRS. Tiene **dos pilares y nada más**: lo que el frontend puede dar por cierto es lo
> que declara el **contrato OpenAPI**, y lo que el frontend da por terminado es lo que firman
> sus **validadores**. Todo lo que no se deduce de uno de los dos —qué rutas debe añadir el
> backend, cómo se calculan las señales, qué invariantes valen— pertenece a la otra mitad y a
> otra spec. El **plan de implementación no está aquí**: según `AGENTS.md` §10.3 se añade
> después de que esta spec pase a `aprobada`.

---

## 1. Problema

`frontend/` está vacío. El backend de SPEC-001 deja el bucle de una escena ejecutable, pero
solo se conduce escribiendo peticiones HTTP a mano. Eso rompe cuatro cosas que el sistema ya
produce y nadie mira:

1. **El escalado no se ve.** Una `Tarea` en estado `escalada` solo se descubre consultando
   `GET /tareas/{id}` con el identificador ya en la mano. Un escalado que nadie ve es un
   sistema parado que parece lento (`AGENTS.md` §7.6).
2. **La evidencia ausente se confunde con evidencia favorable.** Una `Puerta` con
   `evidencia_ausente` no vacía solo se distingue de una superada leyendo el JSON. Es el
   fallo silencioso F-04 de `verification.md` §11 trasladado a la pantalla, y contradice el
   principio 8 de `architecture.md` §1.
3. **Los defectos no se leen con su evidencia.** `GET /borradores/{id}/defectos` devuelve
   evidencia citable y regla violada; sin vista, la corrección se hace a ojo.
4. **No hay ningún consumidor del contrato.** Mientras nadie genere un cliente del documento
   OpenAPI, el contrato no es un contrato: es documentación. Una rotura de frontera no
   aparece hasta que alguien escribe la petición equivocada.

Lo que falta no es «una interfaz»: es el **consumidor del contrato** que convierte lo que el
backend ya registra en algo legible, y los validadores que impiden que ese consumidor se
convierta en una segunda implementación del dominio.

---

## 2. Propósito y alcance

### 2.1 Propósito

Especificar, para su aprobación, **qué debe construir la primera versión del frontend** y
**con qué validador se comprueba cada requisito**. No describe cómo implementarlo.

### 2.2 Los dos pilares, y por qué solo dos

| Pilar | Qué fija | Consecuencia práctica |
| --- | --- | --- |
| **Contrato OpenAPI** | Todo lo que el frontend puede saber del backend: operaciones, esquemas, errores, vocabularios cerrados y flujo de eventos | Los tipos y el cliente se **generan**; nada se escribe a mano ni se mantiene en espejo con los esquemas Pydantic |
| **Validadores de sujeto frontend** | Cuándo un requisito está terminado, y qué **no** comprueba cada uno | Un validador que al fallar señala al backend está mal colocado y se traslada a la suite del backend |

De ahí salen las dos reglas que ordenan el documento entero: **si no está en el contrato, el
frontend no lo asume**, y **si al fallar no señala al frontend, no es un criterio de esta
spec**.

### 2.3 Alcance funcional — qué entra

| # | Entra |
| --- | --- |
| A-01 | Proyecto `frontend/` con Vite + React + TypeScript estricto y las capas FSD `app/`, `pages/`, `shared/` |
| A-02 | Generación de tipos y cliente a partir del documento OpenAPI congelado, con su comando y su directorio propio |
| A-03 | Dobles del backend **derivados del mismo documento**, contra los que corre toda la suite del frontend |
| A-04 | Una única capa de red en `shared/api/`: HTTP, `202` sin espera y flujo de eventos |
| A-05 | Las tres vistas de `CLAUDE.md` §2.3: editor de canon, lector de borradores y panel |
| A-06 | El comportamiento de interfaz del apartado 6.4: estado que sobrevive al refresco, avisos que no se autodestruyen, estados vacíos honestos |
| A-07 | El catálogo de validadores del apartado 8, incorporado a `docs/verification.md` y corriendo en la tubería |

### 2.4 Fuera de alcance — qué no entra

| # | No entra | Por qué |
| --- | --- | --- |
| N-01 | **Cualquier cambio en `backend/`**, incluidas las rutas que hoy faltan y la forma del contrato | Es la otra mitad; tiene su propia spec y su propia suite. Aquí solo se declara como dependencia (§3.3) |
| N-02 | Autenticación, multiusuario y permisos | Una novela por proceso y una sola persona autora |
| N-03 | Edición de prosa desde la interfaz | Un texto sin `Procedencia` no es un `Borrador` |
| N-04 | Panel de juicios, paginación, búsqueda, tema visual y despliegue | No hay juicios en esta versión; el resto es volumen que todavía no existe |
| N-05 | Progreso estimado, barras de avance y estados intermedios inventados | El frontend muestra las transiciones que el flujo de eventos declara, ni una más |
| N-06 | Persistencia de canon en el navegador, lectura de ficheros y acceso a base de datos | `architecture.md` §2.3, regla 6 |
| N-07 | Traducción, resumen o reescritura de los mensajes de error del backend | El mensaje del dominio es el que sabe qué pasó |

No se definen clases, roles ni valores de enumeración nuevos: el vocabulario es el de
`docs/definitions.md`, y llega al frontend por el contrato, nunca transcrito.

---

## 3. Descripción general

### 3.1 Contexto: una sola frontera

```
  persona autora
        │
        ▼
  frontend/  ──── genera tipos, cliente y dobles ───►  documento OpenAPI (congelado)
        │                                                        ▲
        └──────────── HTTP + text/event-stream ──────────────────┘
                                                         publica
                                                     backend/api/
```

El frontend no tiene ninguna otra entrada: ni ficheros, ni SQLite, ni constantes que
describan el dominio. Todo lo que muestra ha entrado por una operación del contrato.

### 3.2 El recorrido que debe quedar cerrado

El frontend está terminado cuando esto se recorre entero **desde el navegador**, sin una sola
petición escrita a mano:

```
editor de canon → alta de las clases de canon que el contrato publica, con los
    desplegables poblados desde el contrato
  → alta del esqueleto de Escena; el 422 del backend se lee y se corrige sin salir de ahi
  → peticion de generacion: 202, se guarda el tarea_id y se abre su flujo de eventos
  → el panel muestra estado, intentos por clase de fallo, reserva y falta[]
  → los defectos se leen con su evidencia citable y su regla violada
  → si la tarea escala, aparece destacada y no desaparece hasta que se resuelve
  → el lector muestra el borrador maquetado como un libro, el diff contra la version
    anterior y la Procedencia que permitio producirlo
  → las puertas se leen distinguiendo superada de no evaluada
```

### 3.3 Dependencia declarada: qué necesita el frontend del contrato

Esta spec **no pide** que se construyan estas operaciones: declara que sin ellas el recorrido
de §3.2 no se puede cerrar desde el navegador, y que construirlas es trabajo de la otra
mitad. Cada fila es una precondición, no un requisito de este documento.

| # | Lo que el recorrido necesita del contrato | Estado hoy |
| --- | --- | --- |
| DEP-01 | Altas de las nueve clases de canon, no solo `POST /brief` | Solo `POST /brief` y `POST /escenas` publicadas |
| DEP-02 | Altas de aristas (`escena_hilo`, `evento_participante`, `evento_causa`) y de `Hecho` de partida | No publicadas |
| DEP-03 | Lecturas por clase de canon y `GET /escenas/{id}` con sus aristas | Parcial |
| DEP-04 | `GET /borradores/{id}` con el texto, la `Procedencia` y los hechos declarados | No publicada |
| DEP-05 | `GET /tareas` filtrable, para ver un escalado sin conocer su id | No publicada |
| DEP-06 | `POST /tareas/{id}/cancelar` y `POST /escalados/{tarea_id}/resolver` | No publicadas |
| DEP-07 | `GET /senales` y `GET /vocabularios` | No publicadas |
| DEP-08 | CORS por lista explícita de orígenes | No configurado |

**Regla de dependencia.** Una operación ausente del contrato no se simula, no se apaña con
otra ruta y no se implementa en el cliente: la vista que la necesita declara *no publicada por
el contrato* y el recorrido de §3.2 queda incompleto hasta que aparezca. Rellenar el hueco
desde el frontend es exactamente el conflicto que el contrato venía a evitar.

### 3.4 Restricciones heredadas

| Restricción | Origen |
| --- | --- |
| El frontend no contiene ninguna regla de dominio: ni invariantes, ni vigencia de hechos, ni umbrales, ni orden de puertas | `CLAUDE.md` §2.3 |
| El formulario no decide si algo es válido: envía y muestra el `422` junto al campo | `CLAUDE.md` §2.3 |
| El progreso llega por el flujo de eventos; no hay sondeo ni progreso inferido | `CLAUDE.md` §2.3 |
| El frontend no lee ficheros ni base de datos | `architecture.md` §2.3, regla 6 |
| Nada se cierra ni se descarta solo; un refresco no destruye lo que la persona tiene abierto; una vista previa se maqueta como el artefacto que representa | Preferencias declaradas por la persona autora |

### 3.5 Supuestos

| # | Supuesto | Si resulta falso |
| --- | --- | --- |
| S-01 | El documento OpenAPI queda congelado en el repositorio y la tubería del backend lo compara con el que publica la aplicación | La generación se hace contra un blanco móvil; esta spec se revisa antes de empezar |
| S-02 | Los vocabularios cerrados salen del contrato como `enum`, derivados de `domain/vocabularies.py` | Los desplegables quedan sin fuente y RF-CAN-02 no es satisfacible |
| S-03 | El flujo de eventos publica transiciones ya registradas (desviación 3 de SPEC-001), no telemetría en vivo | El panel muestra lo que llega y ofrece releer; no cambia ningún requisito |
| S-04 | Una sola persona autora y un solo proceso | Reaparece concurrencia de interfaz, hoy fuera de alcance |

---

## 4. Requisitos sobre el contrato — RC

Requisitos que el frontend **exige del documento OpenAPI para poder generarse**. No son
trabajo de esta spec (§2.4, N-01): son la forma que el contrato debe tener para que el pilar 1
sostenga algo. Se comprueban en la tubería del backend; se listan aquí porque un
incumplimiento bloquea todos los requisitos RF-GEN.

| ID | Requisito | Por qué lo necesita el frontend |
| --- | --- | --- |
| RC-01 | El documento está congelado en el repositorio y una puerta lo compara con el que publica la aplicación | Sin congelar no hay fuente de generación reproducible |
| RC-02 | Cada operación tiene `operationId` explícito y estable: verbo en inglés más clase del dominio en español (`listBorradores`, `createEscena`) | De ahí salen los nombres del cliente generado; el identificador que deriva FastAPI (`alta_de_brief_brief_post`) no sirve como nombre |
| RC-03 | Toda entrada y toda salida van contra un esquema nombrado de `components`; ninguna respuesta es objeto anónimo ni `additionalProperties` | Un diccionario abierto genera un cliente que devuelve objetos opacos |
| RC-04 | Un único esquema de error, y todas las respuestas de error declaradas por ruta (`404`, `409`, `422`) | Un solo camino de presentación de errores en `shared/api/` |
| RC-05 | Los vocabularios cerrados se publican como `enum` | Es lo que hace innecesario transcribirlos (VF-05) |
| RC-06 | La ruta de eventos declara `text/event-stream` y el esquema de cada `data:` | Sin esquema del evento, el panel adivina |
| RC-07 | `info.version` con versionado semántico, y el criterio de incremento escrito | Permite saber si una regeneración es compatible |
| RC-08 | CORS por lista explícita de orígenes, nunca comodín | El navegador es el único cliente; sin cabecera no hay recorrido |

**Si un cambio del contrato rompe la generación**, el cambio es incompatible: se incrementa la
versión mayor en el backend y se regenera. No se parchea a mano el código generado, y no se
ajusta el doble para que la suite pase.

---

## 5. Requisitos del frontend — estructura, generación y red

### 5.1 Estructura — RF-EST

| ID | Requisito |
| --- | --- |
| RF-EST-01 | Proyecto Vite + React + TypeScript en modo estricto, con los comandos exactamente como los escribe `CLAUDE.md` §6 (`npm run build`, `npm run lint`) |
| RF-EST-02 | Tres capas y nada más: `app/` (arranque, providers, enrutado), `pages/` (`canon/`, `borradores/`, `panel/`) y `shared/` (`api/`, `ui/`). Sin `entities/`, sin `features/` y sin `widgets/` |
| RF-EST-03 | Cada slice expone API pública; ninguna importación entra por un camino interno ni apunta a una capa superior |
| RF-EST-04 | `shared/ui/` no conoce el dominio: no importa tipos generados ni nombres de clases de la ontología |

`entities/` se queda fuera a propósito: modelar la ontología en el frontend sería crear la
segunda copia del dominio que `CLAUDE.md` §2.3 prohíbe, y además nada se usa hoy en más de un
sitio.

Estructura resultante, sin inventar directorios:

```
frontend/src/
├── app/       arranque, providers, enrutado
├── pages/     canon/ · borradores/ · panel/      (tres slices, nada mas)
└── shared/
    ├── api/   cliente HTTP y flujo de eventos
    │   └── generated/   generado del contrato; no se edita
    └── ui/    piezas sin conocimiento del dominio
```

### 5.2 Generación — RF-GEN

| ID | Requisito |
| --- | --- |
| RF-GEN-01 | Tipos y cliente se generan del documento OpenAPI congelado, a un directorio propio (`shared/api/generated/`) marcado como no editable |
| RF-GEN-02 | Regenerar sobre un árbol limpio no produce diferencias |
| RF-GEN-03 | Los dobles contra los que corre la suite se derivan del mismo documento; no se escriben a mano |
| RF-GEN-04 | Ningún tipo de la frontera se escribe a mano ni se mantiene en espejo con los esquemas Pydantic |

### 5.3 Capa de red — RF-RED

| ID | Requisito |
| --- | --- |
| RF-RED-01 | Todas las peticiones salen de `shared/api/`; ninguna página llama a `fetch` ni a `EventSource` |
| RF-RED-02 | Una respuesta `202` se acepta sin esperar resultado: se guarda el identificador de la tarea y se abre su flujo de eventos |
| RF-RED-03 | El flujo de eventos se cierra al desmontar la vista, y su reconexión usa retroceso exponencial |
| RF-RED-04 | Ningún `4xx` se reintenta |
| RF-RED-05 | El error del backend se traslada íntegro, en español y sin resumir, hasta la pantalla |
| RF-RED-06 | No existe ningún temporizador que consulte estado: el progreso se lee del flujo de eventos |

---

## 6. Requisitos de las tres vistas y del comportamiento

### 6.1 Panel — RF-PAN

| ID | Requisito |
| --- | --- |
| RF-PAN-01 | Tareas con estado, prioridad, reserva y `falta[]`, con los intentos **por clase de fallo** —transporte, contrato, contenido, presupuesto— y no un contador único |
| RF-PAN-02 | Las tareas escaladas aparecen destacadas sin filtrar ni buscar, y no se retiran de la vista hasta que se resuelven |
| RF-PAN-03 | Cancelar y resolver exigen confirmación explícita que nombra el subárbol que la acción arrastra |
| RF-PAN-04 | Las transiciones se muestran tal como llegan por el flujo de eventos: sin estados inventados ni barras estimadas |
| RF-PAN-05 | Defectos por severidad, cada uno con su evidencia citable y su regla violada, más el contador de descartados por falta de evidencia |
| RF-PAN-06 | Las puertas distinguen tres resultados —superada, fallada y **no evaluada**— y la no evaluada nombra qué evidencia falta |
| RF-PAN-07 | Las señales se muestran con su nombre completo; la ausencia de juicios en esta versión se declara por escrito, en vez de dejar una sección vacía |

### 6.2 Lector — RF-LEC

| ID | Requisito |
| --- | --- |
| RF-LEC-01 | Versiones con su estado y su recuento; el estado se lee antes que el texto |
| RF-LEC-02 | La lectura se maqueta como prosa: serifa, párrafos corridos, medida de lectura limitada. La vista técnica —líneas numeradas— vive en otra pestaña y **no** es la de por defecto |
| RF-LEC-03 | Diff por palabra entre dos versiones cualesquiera, legible sin distinguir color |
| RF-LEC-04 | `Procedencia`, hechos declarados y hechos canonizados visibles junto al texto |
| RF-LEC-05 | Ningún control de edición de prosa |

### 6.3 Editor de canon — RF-CAN

| ID | Requisito |
| --- | --- |
| RF-CAN-01 | Listados de las clases de canon que el contrato publica, con la revisión de canon vigente visible mientras se edita |
| RF-CAN-02 | Los desplegables se pueblan del `enum` del contrato o de la operación de vocabularios, y muestran el valor **crudo** del dominio, sin traducir |
| RF-CAN-03 | El envío nunca se bloquea por criterio propio: se envía y se muestra el `422` junto al campo que lo provocó |
| RF-CAN-04 | Alta del esqueleto de `Escena` con al menos un `renderiza`, y `hechos_requeridos` como campo de primera clase con su recuento a la vista |
| RF-CAN-05 | Los hechos se muestran siempre con su intervalo (`valido_hasta` nulo = vigente) y nunca como atributo de un personaje o un lugar; la línea temporal se ordena por `posicion_en_historia` |
| RF-CAN-06 | El catálogo de predicados es de solo lectura, y dice que se amplía por migración y no por formulario |

RF-CAN-05 y RF-CAN-06 no son reglas de dominio implementadas en el frontend: son **formas de
presentar** lo que el contrato ya devuelve. El frontend no calcula vigencia; muestra el
intervalo que viene en la respuesta.

### 6.4 Comportamiento de interfaz — RF-UI

| ID | Requisito |
| --- | --- |
| RF-UI-01 | Estado de dominio y estado de interfaz separados: un refresco de datos parchea la vista en vez de reconstruirla |
| RF-UI-02 | Lo desplegado, la pestaña activa y lo escrito en un formulario sobreviven a varios refrescos y a una recarga de página |
| RF-UI-03 | Ningún aviso se autodestruye: hay cierre por aviso y un «limpiar todo» |
| RF-UI-04 | Los estados vacíos distinguen «no hay nada» de «no he podido leer» en todas las vistas de lectura |
| RF-UI-05 | Accesibilidad mínima: foco visible, recorrido por teclado en formularios y diálogos, y diff legible en escala de grises |

### 6.5 No funcionales — RF-NF

| ID | Requisito |
| --- | --- |
| RF-NF-01 | Con el backend apagado, la suite del frontend pasa entera salvo el único recorrido de sistema declarado |
| RF-NF-02 | `npm run build` y `npm run lint` en verde, con los comandos tal como los escribe `CLAUDE.md` §6 |
| RF-NF-03 | El frontend no accede a ficheros, ni a base de datos, ni persiste canon en el navegador |
| RF-NF-04 | Ningún vocabulario cerrado, umbral, orden de puertas ni predicado de invariante aparece escrito en el código del frontend |

---

## 7. Modos de fallo silencioso del frontend — FF

Mismo criterio que `verification.md` §11: son formas de fallar que **se presentan como verde**.
La pantalla muestra algo plausible, nadie emite un error y no queda nada que mirar. Cada fila
tiene su validador en §8.

| # | Qué es | Señal indirecta que lo delataría |
| --- | --- | --- |
| FF-01 | Una puerta que nadie evaluó se pinta como superada | Todo en verde con `evidencia_ausente` no vacía en la respuesta |
| FF-02 | Un fallo de lectura se muestra como lista vacía | «Sin defectos» queriendo decir «no he podido preguntar» |
| FF-03 | Un refresco destruye el estado de interfaz | Paneles que se cierran solos mientras corre una generación de minutos |
| FF-04 | El frontend reimplanta una regla del dominio | Un envío deshabilitado por criterio propio; una vigencia calculada en cliente |
| FF-05 | Un vocabulario transcrito a mano queda obsoleto tras una migración | Un valor del dominio que nunca aparece en el desplegable |
| FF-06 | El código generado se edita a mano | No se nota hasta la siguiente regeneración, que borra el parche |
| FF-07 | Los dobles se desincronizan del contrato | La suite pasa en verde contra una API que ya no existe |
| FF-08 | Vuelve el sondeo disfrazado de refresco | Peticiones que crecen con el tiempo que la pantalla lleva abierta |
| FF-09 | Un aviso se autodestruye y el escalado no llega a leerse | Tareas escaladas esperando sin que nadie las haya visto |
| FF-10 | La lectura del borrador se degrada a volcado de texto | Prosa que no se puede juzgar como prosa |
| FF-11 | El error del backend se resume o se reescribe al mostrarlo | Un `422` del dominio convertido en «datos inválidos» |
| FF-12 | Una página se salta la capa de red y llama al backend por su cuenta | Una cabecera o un error tratados de dos maneras distintas según la vista |
| FF-13 | Un flujo de eventos no se cierra al desmontar | Conexiones que se acumulan al navegar entre vistas |
| FF-14 | La suite del frontend empieza a necesitar el backend en marcha | Fallos de frontend causados por cambios de backend, y una suite que acaba desactivada |

FF-12, FF-13 y FF-14 no estaban en el catálogo del sistema (`verification.md` §11) porque no
existían: aparecen con el primer consumidor del contrato.

---

## 8. Verificación — los validadores del frontend

Uno por fila de §7. Todos comparten la propiedad que los hace pertenecer aquí: **cuando
fallan, señalan al frontend**. Ninguno comprueba que el backend devolviera lo correcto.

Las clases son las de `verification.md` §1–§2: **T** test, **A** análisis, **I** inspección,
**D** demostración. Los umbrales son objetivos declarados de diseño, no medidas.

| ID | Valida | Método | Clase | Umbral objetivo | Si no se cumple |
| --- | --- | --- | --- | --- | --- |
| VF-01 | FF-01 | Recorrido sobre dobles con una puerta superada, una fallada y una con `evidencia_ausente` no vacía; se comprueba el estado pintado y el texto que nombra la evidencia que falta | T | 3 de 3 distinguibles; 0 puertas no evaluadas en verde | Bloquea. Es el principio 8 de `architecture.md` §1 llevado a la pantalla |
| VF-02 | FF-02 | Para cada vista de lectura, dos dobles: respuesta vacía y respuesta con error de transporte. Se comprueba que las dos pantallas son distintas | T | 100 % de las vistas de lectura con ambos casos cubiertos | Bloquea |
| VF-03 | FF-03 | Recorrido con Playwright: tres paneles abiertos, un formulario a medio escribir, tres refrescos de datos y una recarga de página | D | Todo lo abierto sigue abierto y lo escrito sigue escrito | Bloquea |
| VF-04 | FF-04 | Análisis estático: ausencia de umbrales numéricos, predicados de invariante y cálculos de vigencia en `frontend/src/`; más un caso en que el doble responde `422` a un envío que el formulario podría haber rechazado | A + T | 0 coincidencias; el envío siempre se produce | Bloquea. Es el modo de fallo que `CLAUDE.md` §2.3 llama tentador |
| VF-05 | FF-05 | Análisis estático: ningún literal de un vocabulario cerrado fuera de `shared/api/generated/`; más un doble con un valor de `enum` añadido, que debe aparecer en el desplegable sin reconstruir | A + T | 0 literales transcritos; el valor nuevo aparece | Bloquea |
| VF-06 | FF-06 | Regenerar el cliente en la tubería y comparar con lo versionado | A | 0 diferencias | Bloquea. No vale «se regenerará luego»: el parche a mano ya está en el árbol |
| VF-07 | FF-07 | Los dobles se derivan del documento congelado en el mismo paso de tubería que el cliente, y se comprueba que no hay dobles escritos a mano | A | 0 dobles fuera del directorio generado | Bloquea |
| VF-08 | FF-08 | Análisis estático de temporizadores de consulta (`setInterval`, y `setTimeout` que reintenta una lectura) fuera de la reconexión declarada; más recuento de peticiones en un recorrido de 60 s con una tarea en curso | A + T | 0 temporizadores de consulta; el recuento no crece con el tiempo en pantalla | Bloquea |
| VF-09 | FF-09 | Recorrido con un aviso de escalado: se espera sin interactuar y se comprueba que sigue presente; después, que existen cierre por aviso y «limpiar todo» | T | El aviso sigue tras la espera; 0 temporizadores de cierre | Bloquea |
| VF-10 | FF-10 | Inspección de capturas por la persona autora: serifa, párrafos corridos, medida limitada y vista técnica en pestaña no activa por defecto | I | Aprobación explícita | Bloquea la aceptación de la vista, no la tubería |
| VF-11 | FF-11 | El doble responde `422` con un mensaje conocido del dominio; se compara carácter a carácter con el texto que aparece en pantalla | T | Coincidencia exacta del mensaje | Bloquea |
| VF-12 | FF-12 | Análisis estático de capas e importaciones FSD, más prohibición de `fetch` y `EventSource` fuera de `shared/api/` | A | 0 infracciones | Bloquea |
| VF-13 | FF-13 | Montaje y desmontaje repetido de la vista con flujo de eventos, contando conexiones abiertas contra el doble | T | Vuelve exactamente a cero | Bloquea |
| VF-14 | FF-14 | La tubería ejecuta la suite del frontend **con el backend apagado** | A | Verde entera salvo el recorrido de sistema declarado | Bloquea. Un fallo aquí significa que una prueba de frontend se apoyó en la otra mitad |

### 8.1 La frontera de cada validador

Columna obligatoria: qué **no** comprueba cada validador, y quién lo comprueba en la otra
mitad. Sin ella, dos suites acaban respondiendo a la misma pregunta y ninguna manda.

| ID | No comprueba | Quién lo comprueba |
| --- | --- | --- |
| VF-01 | Que la puerta se evaluara bien, ni que `evidencia_ausente` esté bien calculada | Backend: `verification.md` §6 y V-04 |
| VF-02 | Que la lectura del backend sea correcta cuando no falla | Suite del backend |
| VF-03 | Que el dato recargado sea el correcto | Suite del backend |
| VF-04 | Que el invariante del dominio sea correcto; solo que el frontend no lo replique | `uv run pytest -m invariants` |
| VF-05 | Que el `enum` del contrato contenga los valores correctos | Puerta de contrato del backend (RC-05) |
| VF-06 | Que el documento congelado coincida con el que publica la aplicación | Puerta de congelación del backend (RC-01) |
| VF-07 | Que el backend responda como responde el doble | Suite del backend |
| VF-08 | Que el backend emita las transiciones que debe emitir | Suite del backend |
| VF-09 | Que el escalado fuera correcto, ni que la resolución haga lo que dice | `orchestrator/`, suite del backend |
| VF-10 | La calidad literaria del texto | `verification.md` §4 |
| VF-11 | Que el `422` del backend sea el que corresponde a esa entrada | Suite del backend |
| VF-12 | Nada del backend | — |
| VF-13 | Que el backend cierre su lado de la conexión | Suite del backend |
| VF-14 | Nada del backend, por construcción | — |

### 8.2 La única excepción declarada

| Nombre | Qué hace | Por qué es excepción |
| --- | --- | --- |
| Recorrido de sistema | Ejecuta el recorrido de §3.2 de extremo a extremo con Playwright contra las dos mitades en marcha | Es el único que cruza la frontera. Se declara como tal, corre aparte y **no** cuenta para VF-14. Si falla, lo primero es decidir de qué mitad viene el fallo antes de tocar nada; si es del backend, el arreglo va a su suite |

### 8.3 Trazabilidad requisito → validador

| Requisitos | Validador |
| --- | --- |
| RF-EST-02, RF-EST-03, RF-EST-04, RF-RED-01 | VF-12 |
| RF-EST-01, RF-NF-02 | Tubería: `npm run build`, `npm run lint` |
| RF-GEN-01, RF-GEN-02, RF-GEN-04 | VF-06 |
| RF-GEN-03 | VF-07 |
| RF-RED-02, RF-RED-03 | VF-13 |
| RF-RED-04, RF-RED-06 | VF-08 |
| RF-RED-05 | VF-11 |
| RF-PAN-01, RF-PAN-04, RF-PAN-05 | VF-02, VF-08 |
| RF-PAN-02, RF-PAN-03 | VF-09 |
| RF-PAN-06, RF-PAN-07 | VF-01 |
| RF-LEC-01, RF-LEC-03, RF-LEC-04, RF-LEC-05 | VF-02, VF-10 |
| RF-LEC-02 | VF-10 |
| RF-CAN-01, RF-CAN-04, RF-CAN-05, RF-CAN-06 | VF-02, VF-04 |
| RF-CAN-02 | VF-05 |
| RF-CAN-03 | VF-04, VF-11 |
| RF-UI-01, RF-UI-02 | VF-03 |
| RF-UI-03 | VF-09 |
| RF-UI-04 | VF-02 |
| RF-UI-05 | Inspección en revisión: avisa, no bloquea el cierre |
| RF-NF-01 | VF-14 |
| RF-NF-03, RF-NF-04 | VF-04, VF-05 |
| RC-01 … RC-08 | Puertas de contrato del backend; aquí solo se consumen |

Ningún requisito queda sin validador salvo RF-UI-05, que se verifica por inspección
declarada: la accesibilidad mínima avisa y no bloquea el cierre.

---

## 9. Impacto

### 9.1 Documentos de `docs/`

| Documento | Cambio |
| --- | --- |
| `verification.md` | Se añaden FF-01…FF-14 y VF-01…VF-14 como apartados propios, con la columna de frontera de §8.1. No se toca la numeración existente (F-01…F-12, V-01…V-12) ni las referencias cruzadas que la citan |
| `architecture.md` | Una fila en el reparto de responsabilidades: el frontend es consumidor generado del contrato, sin acceso a almacenamiento |
| `CLAUDE.md` §6 | Los comandos del frontend quedan exactamente como se implementen, incluido el de generación |
| `definitions.md` | Sin cambios. Esta spec no crea clases, roles ni valores de enumeración |

### 9.2 Módulos

| Módulo | Cambio |
| --- | --- |
| `frontend/` | Todo lo que esta spec especifica |
| `backend/` | **Ninguno.** Lo que el recorrido necesita está en §3.3 como dependencia, y se construye en otra spec |

### 9.3 Decisiones que esta spec registra

| Decisión | Alternativa descartada | Motivo |
| --- | --- | --- |
| Los desplegables muestran el valor crudo del dominio, sin traducir | Etiquetas traducidas a castellano de lectura | Una traducción en el frontend es una segunda ontología; `CLAUDE.md` §5.1 prohíbe sustituir los nombres por sinónimos |
| «El frontend no contiene reglas de dominio» se verifica por análisis estático declarado, no solo por revisión | Confiar en la revisión de código | Una regla que solo vigila la revisión reaparece en el primer formulario con prisa |
| La accesibilidad mínima avisa y no bloquea el cierre | Puerta bloqueante de accesibilidad | El alcance es una sola persona autora; bloquear aquí pararía el cierre por algo que nadie sufre todavía |
| Sin `entities/` ni `features/` | Estructura FSD completa desde el principio | Modelar la ontología en `entities/` crea la segunda copia del dominio; nada se usa hoy en más de un sitio |
| Los dobles se generan del contrato | Dobles escritos a mano | Un doble escrito a mano se desincroniza en silencio y la suite pasa contra una API que ya no existe (FF-07) |

---

## 10. Criterios de aceptación

1. El recorrido de §3.2 se ejecuta entero desde el navegador sobre un `Brief` de prueba, sin una sola petición escrita a mano, para todas las operaciones que el contrato publica.
2. Una tarea `escalada` aparece destacada sin buscarla y permanece visible hasta que se resuelve.
3. Una `Puerta` con `evidencia_ausente` se muestra como no evaluada y nombra qué evidencia falta.
4. Un borrador con defectos sembrados muestra cada uno con su evidencia citable, y el contador de descartados es visible.
5. El lector muestra prosa maquetada, con la vista técnica en otra pestaña y el diff entre dos versiones cualesquiera legible en escala de grises.
6. Regenerar cliente, tipos y dobles del documento congelado no produce diferencias.
7. Los catorce validadores de §8 corren en la tubería, y VF-14 pasa con el backend apagado.
8. Tres refrescos y una recarga dejan la interfaz como estaba, con tres paneles abiertos y un formulario a medio escribir.
9. `npm run build` y `npm run lint` en verde, con los comandos tal como los escribe `CLAUDE.md` §6.
10. `verification.md` recoge FF-01…FF-14 y VF-01…VF-14 con su columna de frontera, sin dejar colgando ninguna referencia cruzada existente.
11. Esta spec queda actualizada con lo que realmente se construyó, y cada desviación anotada con su motivo.

Una operación de §3.3 que siga sin publicarse en el contrato **no impide cerrar** los
criterios 2–9: se anota como desviación nombrando la dependencia, y el criterio 1 queda
parcial hasta que el contrato la publique.

---

## 11. Riesgos

| # | Riesgo | Mitigación |
| --- | --- | --- |
| R-01 | El contrato no llega a cumplir RC-01…RC-08 y la generación produce un cliente que hay que corregir a mano | Ningún requisito RF-GEN empieza antes de que el contrato los cumpla; corregir a mano está prohibido por VF-06 |
| R-02 | Las dependencias de §3.3 se construyen a medias y las vistas se rellenan con datos inventados | La vista declara *no publicada por el contrato*; §3.3 lo prohíbe explícitamente |
| R-03 | Los validadores estáticos VF-04, VF-05, VF-08 y VF-12 se escriben después de las tres vistas y se convierten en una lista de excepciones | Se escriben sobre el proyecto vacío. Un temporizador puesto en la primera vista sobrevive a cualquier revisión posterior si nadie lo prohíbe antes de escribirlo |
| R-04 | El recorrido de sistema se vuelve el sitio donde se comprueba todo y la suite del frontend se vacía | Es la única excepción declarada (§8.2) y no cuenta para VF-14 |
| R-05 | VF-10 depende de la inspección de una persona y se convierte en cuello de botella | Se inspecciona sobre capturas, no sobre el entorno en marcha, y solo bloquea la aceptación de esa vista |

---

## 12. Preguntas abiertas

Bloquean la aprobación (`AGENTS.md` §10.2).

| # | Pregunta | Por qué bloquea |
| --- | --- | --- |
| P-01 | ¿Se aprueba que las dependencias de §3.3 queden fuera de esta spec y vayan en una spec propia del backend, aunque eso deje el criterio 1 parcial en el primer cierre? | Cambia qué significa «terminado» para este documento |
| P-02 | ¿El flujo de eventos publicará transiciones ya registradas (S-03) o se corrige antes para emitir en vivo? | Cambia RF-PAN-04 y VF-08 |
| P-03 | ¿Los catorce validadores entran en `verification.md` como apartados nuevos, o en un documento hermano del frontend? | `AGENTS.md` §10.1 exige arreglar las referencias cruzadas en el mismo cambio |
| P-04 | ¿Qué orígenes concretos entran en la lista de CORS (RC-08) para el entorno de desarrollo? | Sin ella el recorrido no arranca en el navegador |

---

## 13. Plan de implementación

Según `AGENTS.md` §10.3 se añade a este mismo documento **después** de que la spec pase a
`aprobada` y con el apartado 12 vacío. Mientras tanto vive aparte, en
`specs/plan-frontend.md`, en estado `borrador` y con el mismo sujeto que esta spec: su paso 0
comprueba las precondiciones RC-01…RC-08 y levanta el inventario de §3.3, y ninguno de sus
pasos escribe en `backend/`. Al aprobar se decide si se pliega dentro de este documento o si
la referencia queda permanente.
