# Especificación funcional · MyStiryMaker

**Versión:** 1.0 (borrador)
**Alcance:** sistema agéntico de escritura de una novela larga sobre un boxeador zurdo en la época actual.

---

## 1. Objetivo

Producir un manuscrito completo y coherente de entre 80.000 y 100.000 palabras mediante cuatro agentes especializados que trabajan sobre una memoria compartida, con el autor como única autoridad de aprobación en los puntos de control definidos.

El sistema no busca escribir sin supervisión. Busca que el autor no tenga que recordar en el capítulo 28 qué peso tenía el protagonista en el capítulo 6.

## 2. Fuera de alcance

- Publicación, maquetación comercial o gestión editorial.
- Traducción a otros idiomas.
- Generación de portada o material gráfico.
- Escritura de más de una novela en paralelo dentro de la misma ejecución.

## 3. Actores

| Actor | Tipo | Responsabilidad |
|---|---|---|
| **Autor** | Humano | Aporta el brief, aprueba la escaleta, resuelve escalados, aprueba el manuscrito final |
| **Agente Investigación** | Automático | Reúne y verifica material factual sobre boxeo y contexto actual |
| **Agente Escaleta** | Automático | Define personajes, ambientación y plan de capítulos |
| **Agente Escritor** | Automático | Redacta el capítulo N en prosa |
| **Agente Revisor** | Automático | Evalúa continuidad, estilo y verosimilitud técnica; puntúa con rúbrica |
| **Orquestador** | Automático | Decide el siguiente paso, cuenta iteraciones, escala al autor |

## 4. Flujo funcional

| Paso | Actor | Entrada | Salida | Condición de salida |
|---|---|---|---|---|
| F1 | Autor | — | `brief.md` | Brief completo según §5 |
| F2 | Investigación | `brief.md` | `research/*.md` + fuentes | Todos los temas obligatorios cubiertos |
| F3 | Escaleta | brief + investigación | `bible.json`, `outline.json` | Escaleta aprobada por el autor |
| F4 | Escritor | escaleta + memoria | `manuscript/cap-NN.md` | Capítulo redactado dentro del rango de palabras |
| F5 | Revisor | capítulo + memoria | `reviews/cap-NN.json` | Rúbrica puntuada y notas emitidas |
| F6 | Orquestador (G1) | rúbrica | decisión | Aprobado, reescritura o escalado |
| F7 | Orquestador | capítulo aprobado | memoria actualizada | Biblia, ledger y vector store escritos |
| F8 | Orquestador (G2) | escaleta | decisión | Siguiente capítulo o cierre |
| F9 | Autor | manuscrito completo | aprobación | Manuscrito final |

## 5. Contenido mínimo del brief

El sistema no arranca si falta alguno de estos campos:

- **Premisa**: una frase con el conflicto central del protagonista zurdo.
- **Tono**: realismo sucio, deportivo clásico, literario introspectivo u otro declarado.
- **Persona y tiempo narrativos**: por ejemplo, primera persona en pasado.
- **Extensión objetivo**: palabras totales y número aproximado de capítulos.
- **Arco deseado**: punto de partida y punto final del protagonista.
- **Vetos**: temas, escenas o recursos que el autor no quiere ver.

## 6. Casos de uso

### CU-01 · Iniciar proyecto
El autor entrega el brief. El sistema valida los campos obligatorios y, si faltan, los solicita uno a uno antes de continuar.

### CU-02 · Investigar el dominio
El Agente Investigación cubre obligatoriamente: técnica del zurdo frente al ortodoxo, categorías y reglamento vigente, funcionamiento del circuito profesional actual (bolsas, promotoras, retransmisión), proceso de pesaje y corte de peso, lesiones habituales y figura del cut man, y contexto contemporáneo (redes sociales, patrocinios, presión mediática). Cada afirmación factual queda con fuente o marcada explícitamente como licencia narrativa.

### CU-03 · Diseñar personajes y escaleta
El Agente Escaleta produce la biblia y el plan de capítulos. Cada capítulo del plan declara: objetivo dramático, punto de vista, conflicto, salida, si contiene combate o sparring, y extensión objetivo.

### CU-04 · Escribir un capítulo
El Agente Escritor redacta el capítulo N usando la biblia, la escaleta y los resúmenes de los capítulos anteriores. No puede introducir hechos duros nuevos (fechas, resultados, lesiones) sin declararlos para el ledger.

### CU-05 · Revisar un capítulo
El Agente Revisor evalúa el capítulo con la rúbrica de §7 y emite notas accionables. En capítulos con combate, verifica además la coreografía: coherencia de la guardia invertida, duelo de pie adelantado, uso del clinch, trabajo de esquina y lectura de tarjetas.

### CU-06 · Reescribir tras rechazo
Si el capítulo no supera el umbral, el Escritor recibe las notas y reescribe solo lo señalado. Máximo tres iteraciones.

### CU-07 · Escalar al autor
Agotadas las tres iteraciones, el sistema detiene el capítulo y presenta al autor el texto, las notas y las puntuaciones para que decida: aceptar, reescribir con indicaciones nuevas o modificar la escaleta.

### CU-08 · Cerrar la novela
Cuando no quedan capítulos pendientes, el sistema compila el manuscrito y lo presenta para aprobación final.

## 7. Rúbrica de calidad

Cinco criterios, cada uno de 1 a 5:

| Criterio | Qué mide |
|---|---|
| **Tensión** | El capítulo abre una pregunta y la mantiene |
| **Verosimilitud técnica** | El boxeo resiste la lectura de alguien que lo conoce |
| **Avance del arco** | El protagonista termina distinto de como empezó |
| **Calidad de prosa** | Ritmo, diálogo, ausencia de clichés deportivos |
| **Continuidad** | Nada contradice el ledger ni la biblia |

## 8. Reglas de negocio

| ID | Regla |
|---|---|
| RN-01 | Un capítulo se aprueba si la media es ≥ 4,0 **y** ningún criterio está por debajo de 3 |
| RN-02 | Una puntuación de 1 o 2 en **Continuidad** provoca rechazo automático, sea cual sea la media |
| RN-03 | Máximo 3 iteraciones por capítulo; la cuarta escala al autor |
| RN-04 | Ningún capítulo se consolida en memoria antes de ser aprobado |
| RN-05 | La escaleta no se modifica durante la producción sin intervención del autor |
| RN-06 | El récord del protagonista solo cambia en capítulos que contienen un combate oficial |
| RN-07 | Los hechos duros nuevos que introduzca el Escritor se registran en el ledger al consolidar |
| RN-08 | No se usan nombres de boxeadores reales en activo como personajes |
| RN-09 | La desviación de extensión admitida por capítulo es del ±15 % respecto al objetivo |
| RN-10 | La ventaja y el coste de ser zurdo deben aparecer en la trama, no solo en las escenas de combate |

## 9. Artefactos del sistema

| Artefacto | Ruta | Propietario |
|---|---|---|
| Brief | `brief.md` | Autor |
| Notas de investigación | `research/` | Investigación |
| Biblia | `memory/bible.json` | Escaleta |
| Ledger de continuidad | `memory/ledger.json` | Revisor y orquestador |
| Escaleta viva | `memory/outline.json` | Escaleta y orquestador |
| Capítulos | `manuscript/cap-NN.md` | Escritor |
| Revisiones | `reviews/cap-NN.json` | Revisor |
| Manuscrito final | `dist/manuscrito.md` | Orquestador |

## 10. Criterios de aceptación del sistema

1. Con un brief válido, el sistema produce una escaleta completa sin intervención.
2. Ningún capítulo llega al manuscrito sin una revisión registrada.
3. Una contradicción introducida a propósito en un capítulo (por ejemplo, cambiar el récord sin combate) es detectada por el Revisor.
4. El bucle de reescritura nunca excede tres iteraciones.
5. El manuscrito final no contiene marcadores de trabajo, notas del agente ni texto entre corchetes.
6. Toda afirmación factual sobre boxeo tiene fuente en `research/` o está marcada como licencia narrativa.

## 11. Requisitos no funcionales

| Requisito | Objetivo |
|---|---|
| Reanudabilidad | Una ejecución interrumpida continúa desde el último capítulo consolidado |
| Trazabilidad | Para cada capítulo consta qué versión de la biblia y qué iteración lo produjeron |
| Coste | Presupuesto declarado por capítulo; el orquestador detiene la ejecución si se supera el total |
| Idempotencia | Reprocesar un capítulo ya consolidado no duplica entradas en el ledger |
| Privacidad | No se introducen datos personales reales de terceros en el brief ni en la investigación |

## 12. Riesgos funcionales

| Riesgo | Mitigación |
|---|---|
| Prosa homogénea entre capítulos | Rotar el foco sensorial y el registro; criterio de prosa en la rúbrica |
| Deriva de la voz del protagonista | Muestra de voz fijada en la biblia y usada como referencia en cada capítulo |
| Combates repetitivos | Cada combate declara en la escaleta un problema táctico distinto |
| Sobreuso del recurso «zurdo» | RN-10 y revisión temática al cierre de cada acto |
| Aprobación automática complaciente | Rúbrica con rechazo duro por continuidad (RN-02) y muestreo manual del autor |
