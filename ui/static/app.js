"use strict";

// Panel de control de MyStoryMaker.
//
// La regla que ordena este fichero: el estado del PROYECTO se recarga solo cada
// pocos segundos, y el estado de la INTERFAZ no se toca nunca al recargar. Antes
// no era asi -cada refresco reconstruia el DOM entero- y eso cerraba en tus
// narices cualquier capitulo que tuvieras abierto mientras corria un paso, que
// es justo cuando quieres tenerlo abierto. Por eso las filas de capitulo se
// parchean en vez de rehacerse, y todo lo desplegable guarda si esta abierto.

const $ = (sel, el) => (el || document).querySelector(sel);
const $$ = (sel, el) => Array.from((el || document).querySelectorAll(sel));

const crear = (tag, props, ...hijos) => {
  const el = document.createElement(tag);
  Object.entries(props || {}).forEach(([k, v]) => {
    if (v === null || v === undefined || v === false) return;
    if (k === "class") el.className = v;
    else if (k === "html") el.innerHTML = v;
    else if (k.startsWith("on")) el.addEventListener(k.slice(2), v);
    else el.setAttribute(k, v);
  });
  hijos.flat().filter((h) => h !== null && h !== undefined && h !== false && h !== "")
    .forEach((h) => el.append(h instanceof Node ? h : document.createTextNode(h)));
  return el;
};

const SVG_NS = "http://www.w3.org/2000/svg";
const svg = (tag, props, ...hijos) => {
  const el = document.createElementNS(SVG_NS, tag);
  Object.entries(props || {}).forEach(([k, v]) => {
    if (v === null || v === undefined) return;
    if (k.startsWith("on")) el.addEventListener(k.slice(2), v);
    else el.setAttribute(k, v);
  });
  hijos.flat().filter(Boolean).forEach((h) => el.append(h));
  return el;
};

async function api(ruta, opciones) {
  const resp = await fetch(ruta, { headers: { "Content-Type": "application/json" }, ...opciones });
  let cuerpo = null;
  try { cuerpo = await resp.json(); } catch (_) { /* sin cuerpo */ }
  if (!resp.ok) throw new Error((cuerpo && cuerpo.detail) || `HTTP ${resp.status}`);
  return cuerpo;
}
const post = (ruta, datos) => api(ruta, { method: "POST", body: datos ? JSON.stringify(datos) : undefined });

// --------------------------------------------------------------------------- estado de la interfaz

// Lo que el autor ha abierto, elegido o movido. Sobrevive a los refrescos y a
// recargar la pagina; no lo toca nada de lo que llega del servidor.
const ui = {
  abiertos: new Set(),          // claves de <details> desplegados
  capitulos: new Set(),         // numeros de capitulo con el detalle abierto
  pestanas: {},                 // n -> pestana activa del detalle
  logAbierto: false,
  logAltura: null,
  lectorTamano: 19,
  lectorTema: "sepia",
};

function cargarUI() {
  try {
    const guardado = JSON.parse(sessionStorage.getItem("ui") || "{}");
    if (guardado.abiertos) ui.abiertos = new Set(guardado.abiertos);
    if (guardado.capitulos) ui.capitulos = new Set(guardado.capitulos);
    Object.assign(ui, {
      pestanas: guardado.pestanas || {},
      logAbierto: !!guardado.logAbierto,
      logAltura: guardado.logAltura || null,
      lectorTamano: guardado.lectorTamano || 19,
      lectorTema: guardado.lectorTema || "sepia",
    });
  } catch (_) { /* primera visita o almacenamiento bloqueado */ }
}

function guardarUI() {
  try {
    sessionStorage.setItem("ui", JSON.stringify({
      ...ui, abiertos: [...ui.abiertos], capitulos: [...ui.capitulos],
    }));
  } catch (_) { /* modo privado: la sesion funciona igual, solo no recuerda */ }
}
cargarUI();

// Un <details> que recuerda si estaba abierto. Todo lo desplegable de la pagina
// pasa por aqui, que es lo que evita que un refresco lo cierre.
function detalles(clave, resumen, ...hijos) {
  const el = crear("details", { class: "desplegable" },
    crear("summary", {}, resumen), ...hijos);
  el.open = ui.abiertos.has(clave);
  el.addEventListener("toggle", () => {
    if (el.open) ui.abiertos.add(clave); else ui.abiertos.delete(clave);
    guardarUI();
  });
  return el;
}

// --------------------------------------------------------------------------- avisos

// Nada se cierra solo. Un aviso es algo que el sistema tiene que decirte, y
// decidir cuando has terminado de leerlo es tuyo, no de un temporizador.
const zonaAvisos = $("#avisos-zona");
const contAvisos = $("#avisos");

function refrescarZonaAvisos() {
  const n = contAvisos.childElementCount;
  zonaAvisos.hidden = n === 0;
  $("#avisos-cuenta").textContent = n === 1 ? "1 aviso" : `${n} avisos`;
}

function aviso(texto, clase) {
  const cierre = crear("button", { class: "aviso-cerrar", title: "Cerrar" }, "×");
  const caja = crear("div", { class: `aviso aviso-${clase || "neutro"}` },
    crear("div", { class: "aviso-texto" },
      ...String(texto).split("\n").filter(Boolean).map((l) => crear("p", {}, l))),
    cierre);
  cierre.addEventListener("click", () => { caja.remove(); refrescarZonaAvisos(); });
  contAvisos.prepend(caja);
  refrescarZonaAvisos();
  return caja;
}
const avisar = (e) => aviso(typeof e === "string" ? e : e.message || "Ha fallado la operación.", "error");

$("#avisos-limpiar").addEventListener("click", () => {
  contAvisos.innerHTML = "";
  refrescarZonaAvisos();
});

// --------------------------------------------------------------------------- notificaciones

let permisoPedido = false;
function pedirPermisoNotificacion() {
  if (!("Notification" in window) || permisoPedido) return;
  permisoPedido = true;
  if (Notification.permission === "default") Notification.requestPermission().catch(() => {});
}
function notificar(titulo, cuerpo) {
  if (!("Notification" in window) || Notification.permission !== "granted" || !document.hidden) return;
  try { new Notification(titulo, { body: cuerpo, tag: "mystorymaker" }); } catch (_) { /* nada */ }
}

// --------------------------------------------------------------------------- job en vivo

const panelLog = $("#panel-log");
const logCuerpo = $("#log-cuerpo");
let jobSeguido = null;
let logTimer = null;
let relojTimer = null;

const ETIQUETAS_JOB = {
  preparar: () => "N1 y N2 · investigación y escaleta",
  capitulo: (m) => `Capítulo ${String(m.n).padStart(2, "0")}${m.reescritura ? " · reescritura" : ""}`,
  continuar: () => "Continuar hasta agotar pendientes o escalar",
  nuevo_capitulo: (m) => m.solo_ficha
    ? `N2 · ficha del capítulo ${String(m.n).padStart(2, "0")}`
    : `Capítulo ${String(m.n).padStart(2, "0")} nuevo${m.producir ? " · ficha y producción" : " · ficha"}`,
};
const etiquetaJob = (job) => (ETIQUETAS_JOB[job.kind] || (() => job.kind))(job.meta || {});

function pintarVacioLog() {
  if (logCuerpo.textContent.trim()) return;
  logCuerpo.innerHTML = "";
  logCuerpo.append(crear("div", { class: "vacio-log" },
    "Aquí sale la salida del paso que esté corriendo. Todavía no hay ninguno."));
}

function abrirLog(abierto) {
  ui.logAbierto = abierto;
  panelLog.classList.toggle("abierto", abierto);
  $("#log-chevron").textContent = abierto ? "▾" : "▴";
  if (abierto) pintarVacioLog();
  guardarUI();
}
if (ui.logAltura) panelLog.style.setProperty("--alto-log", `${ui.logAltura}px`);
abrirLog(ui.logAbierto);

$("#log-cabecera").addEventListener("click", (ev) => {
  if (ev.target.closest("button")) return;
  abrirLog(!panelLog.classList.contains("abierto"));
});

// El log se arrastra para hacerlo mas alto: diez minutos de salida no caben en
// el hueco que le venga bien a la pagina.
(() => {
  const tirador = $("#log-tirador");
  let arrastrando = false;
  tirador.addEventListener("pointerdown", (ev) => {
    arrastrando = true; tirador.setPointerCapture(ev.pointerId);
    panelLog.classList.add("arrastrando");
  });
  tirador.addEventListener("pointermove", (ev) => {
    if (!arrastrando) return;
    const alto = Math.min(window.innerHeight * 0.85, Math.max(120, window.innerHeight - ev.clientY));
    ui.logAltura = Math.round(alto);
    panelLog.style.setProperty("--alto-log", `${ui.logAltura}px`);
  });
  const soltar = () => {
    if (!arrastrando) return;
    arrastrando = false; panelLog.classList.remove("arrastrando"); guardarUI();
  };
  tirador.addEventListener("pointerup", soltar);
  tirador.addEventListener("pointercancel", soltar);
})();

$("#log-cancelar").addEventListener("click", async () => {
  if (!jobSeguido) return;
  try { await post(`/api/jobs/${jobSeguido}/cancelar`); } catch (e) { avisar(e); }
});

const PASOS_CICLO = ["N3", "N4", "D1"];

function renderPasos(fase, enCurso) {
  const cont = $("#log-pasos");
  cont.innerHTML = "";
  if (!fase || !fase.nodo) return;
  const i = PASOS_CICLO.indexOf(fase.nodo);
  if (i === -1) {
    cont.append(crear("span", { class: `paso ${enCurso ? "paso-activo" : "paso-hecho"}` }, fase.nodo));
  } else {
    PASOS_CICLO.forEach((p, j) => {
      const clase = j < i ? "paso-hecho" : j === i ? (enCurso ? "paso-activo" : "paso-hecho") : "";
      cont.append(crear("span", { class: `paso ${clase}` }, p));
    });
  }
  if (fase.iteracion) cont.append(crear("span", { class: "paso-iter" }, `iteración ${fase.iteracion}/3`));
  if (fase.ultimo) cont.append(crear("span", { class: "paso-iter paso-ultimo" }, fase.ultimo));
}

function formatearDuracion(segundos) {
  const m = Math.floor(segundos / 60), s = Math.floor(segundos % 60);
  return `${m}:${String(s).padStart(2, "0")}`;
}

function arrancarReloj(desde) {
  clearInterval(relojTimer);
  const pinta = () => { $("#log-reloj").textContent = formatearDuracion((Date.now() / 1000) - desde); };
  pinta();
  relojTimer = setInterval(pinta, 1000);
}

function seguirJob(jobId) {
  if (jobSeguido === jobId && logTimer) return;   // ya lo estamos siguiendo
  jobSeguido = jobId;
  logCuerpo.innerHTML = "";
  abrirLog(true);
  clearInterval(logTimer);
  let desde = 0;
  let ultimoRefresco = 0;

  const paso = async () => {
    try {
      const datos = await api(`/api/jobs/${jobId}?desde=${desde}`);
      if (datos.lineas.length) {
        const pegado = logCuerpo.scrollTop + logCuerpo.clientHeight >= logCuerpo.scrollHeight - 12;
        logCuerpo.textContent += (desde > 0 ? "\n" : "") + datos.lineas.join("\n");
        desde = datos.total;
        if (pegado) logCuerpo.scrollTop = logCuerpo.scrollHeight;
      }
      const enCurso = datos.estado === "en_curso";
      $("#log-titulo").textContent = etiquetaJob(datos);
      $("#log-punto").className = "punto " + (enCurso ? "punto-curso" : datos.estado === "ok" ? "punto-ok" : "punto-error");
      renderPasos(datos.fase, enCurso);
      $("#log-cancelar").hidden = !enCurso;
      if (enCurso) arrancarReloj(datos.creado);
      else { clearInterval(relojTimer); $("#log-reloj").textContent = formatearDuracion((datos.terminado || 0) - datos.creado); }

      // El proyecto cambia por debajo mientras el paso corre. Se recarga su
      // estado, nunca la interfaz.
      if (enCurso && Date.now() - ultimoRefresco > 4000) {
        ultimoRefresco = Date.now();
        cargarEstado().catch(() => {});
      }

      if (!enCurso) {
        clearInterval(logTimer); logTimer = null; jobSeguido = null;
        if (datos.estado === "ok") {
          aviso(`${etiquetaJob(datos)} — terminado.`, "ok");
          notificar("Paso terminado", etiquetaJob(datos));
        } else {
          if (datos.error) logCuerpo.textContent += `\n\n--- ${datos.error}`;
          logCuerpo.scrollTop = logCuerpo.scrollHeight;
          aviso(`${etiquetaJob(datos)} ha fallado:\n${datos.error || datos.estado}`, "error");
          notificar("Paso fallido", etiquetaJob(datos));
        }
        cargarEstado();
      }
    } catch (_) {
      clearInterval(logTimer); logTimer = null; jobSeguido = null;
    }
  };
  paso();
  logTimer = setInterval(paso, 1500);
}

async function lanzar(ruta, datos) {
  pedirPermisoNotificacion();
  try {
    const { job_id } = await post(ruta, datos);
    seguirJob(job_id);
    cargarEstado();
  } catch (e) { avisar(e); }
}

// --------------------------------------------------------------------------- estado

let estado = null;
const badge = (texto, clase) => crear("span", { class: `badge badge-${clase}` }, texto);

function renderCabecera() {
  $("#subtitulo").textContent = estado.titulo ? `«${estado.titulo}» — config v${estado.config_version}` : "";
  const badges = $("#badges");
  badges.innerHTML = "";
  badges.append(
    estado.brief.completo ? badge("brief completo", "ok") : badge("brief incompleto", "error"),
    estado.escaleta.pendiente_aprobacion ? badge("escaleta pendiente de aprobar", "aviso")
      : estado.escaleta.sembrada ? badge("escaleta sembrada", "ok") : badge("sin escaleta", "neutro"),
    estado.langfuse.configurado ? badge("Langfuse activo", "neutro") : badge("Langfuse inactivo", "neutro"),
  );
}

// --------------------------------------------------------------------------- el circuito

const NODOS = [
  { id: "N0", etiqueta: "brief", x: 8 },
  { id: "N1", etiqueta: "investigación", x: 126 },
  { id: "N2", etiqueta: "escaleta", x: 244 },
  { id: "N3", etiqueta: "escribir", x: 392 },
  { id: "N4", etiqueta: "revisar", x: 510 },
  { id: "D1", etiqueta: "¿aprueba?", x: 628, decision: true },
  { id: "D2", etiqueta: "¿quedan?", x: 776, decision: true },
  { id: "N5", etiqueta: "manuscrito", x: 894 },
];
const ANCHO = 92, ALTO = 40, Y = 50;

function contextoCircuito() {
  const caps = estado.capitulos || [];
  const consolidados = caps.filter((c) => c.estado === "consolidado").length;
  const pendiente = caps.find((c) => c.estado === "pendiente");
  const fase = (estado.job_activo && estado.job_activo.fase) || {};
  const enCiclo = !!estado.job_activo && ["capitulo", "continuar", "nuevo_capitulo"].includes(estado.job_activo.kind);
  const todo = caps.length > 0 && consolidados === caps.length;

  const marca = {};
  marca.N0 = estado.brief.completo ? "hecho" : "activo";
  marca.N1 = estado.investigacion ? "hecho" : estado.brief.completo ? "listo" : "bloqueado";
  marca.N2 = estado.escaleta.pendiente_aprobacion ? "activo"
    : estado.escaleta.sembrada ? "hecho" : estado.investigacion ? "listo" : "bloqueado";

  const listo = estado.escaleta.sembrada && !estado.escaleta.pendiente_aprobacion;
  ["N3", "N4", "D1"].forEach((id) => {
    marca[id] = !listo ? "bloqueado"
      : (enCiclo && fase.nodo === id) ? "activo"
      : todo ? "hecho" : pendiente ? "listo" : "hecho";
  });
  marca.D2 = !listo ? "bloqueado" : todo ? "hecho" : "listo";
  marca.N5 = estado.manuscrito.aprobado ? "hecho"
    : estado.manuscrito.compilado ? "activo" : todo ? "listo" : "bloqueado";
  return { marca, pendiente, consolidados, fase, total: caps.length };
}

function accionDeNodo(id, ctx) {
  const ocupado = !!estado.job_activo;
  const irA = (sel) => () => $(sel).scrollIntoView({ behavior: "smooth", block: "center" });
  switch (id) {
    case "N0": return { titulo: "Ver el brief", accion: irA("#tarjeta-brief") };
    case "N1": case "N2":
      if (estado.escaleta.pendiente_aprobacion) return { titulo: "Hay un plan esperando tu aprobación", accion: irA("#tarjeta-escaleta") };
      if (!estado.escaleta.sembrada) return { titulo: "Lanzar N1 y N2", accion: () => lanzar("/api/escaleta/preparar"), pulsable: !ocupado };
      return { titulo: "La escaleta ya está sembrada", accion: irA("#tarjeta-escaleta") };
    case "N3": case "N4": case "D1":
      if (ctx.pendiente) {
        const n = ctx.pendiente.n;
        const falta = ctx.pendiente.ficha_completa === false;
        return {
          titulo: falta ? `El capítulo ${n} no tiene ficha: lanzar N2` : `Lanzar el ciclo del capítulo ${n}`,
          accion: () => lanzar(falta ? `/api/capitulos/${n}/ficha` : `/api/capitulos/${n}/lanzar`),
          pulsable: !ocupado,
        };
      }
      return { titulo: "No queda ningún capítulo pendiente", accion: irA("#tarjeta-capitulos") };
    case "D2":
      if (ctx.pendiente) return { titulo: "Continuar hasta agotar pendientes o escalar", accion: () => lanzar("/api/continuar"), pulsable: !ocupado };
      return { titulo: "Sin pendientes: el siguiente paso es N5", accion: irA("#tarjeta-manuscrito") };
    case "N5": return { titulo: "Compilar y aprobar el manuscrito", accion: irA("#tarjeta-manuscrito") };
    default: return { titulo: "", accion: () => {} };
  }
}

function renderCircuito() {
  const cont = $("#circuito");
  cont.innerHTML = "";
  const ctx = contextoCircuito();

  const lienzo = svg("svg", { viewBox: "0 0 1000 152", class: "circuito", preserveAspectRatio: "xMidYMid meet" },
    svg("defs", {}, svg("marker", { id: "punta", viewBox: "0 0 10 10", refX: "9", refY: "5", markerWidth: "6", markerHeight: "6", orient: "auto-start-reverse" },
      svg("path", { d: "M 0 0 L 10 5 L 0 10 z" }))),
    svg("rect", { x: 376, y: 32, width: 344, height: 76, rx: 12, class: "marco-ciclo" }),
    svg("text", { x: 548, y: 26, class: "marco-titulo" }, document.createTextNode("el ciclo de un capítulo")),
  );

  NODOS.forEach((nodo, i) => {
    const sig = NODOS[i + 1];
    if (sig) lienzo.append(svg("line", {
      x1: nodo.x + ANCHO, y1: Y + ALTO / 2, x2: sig.x - 3, y2: Y + ALTO / 2,
      class: `arista${ctx.marca[sig.id] === "bloqueado" ? "" : " arista-viva"}`, "marker-end": "url(#punta)",
    }));
  });
  lienzo.append(
    svg("path", { d: "M 674 90 L 674 126 L 438 126 L 438 93", class: "arista arista-vuelta", "marker-end": "url(#punta)", fill: "none" }),
    svg("text", { x: 556, y: 140, class: "arista-etiqueta" }, document.createTextNode("E6 · rechazado, vuelve a escribir")),
  );

  NODOS.forEach((nodo) => {
    const marca = ctx.marca[nodo.id];
    const { titulo, accion, pulsable } = accionDeNodo(nodo.id, ctx);
    const clicable = pulsable !== false && marca !== "bloqueado";
    lienzo.append(svg("g", {
      class: `nodo nodo-${marca}${clicable ? " nodo-clicable" : ""}`,
      role: "button", tabindex: clicable ? "0" : null,
      onclick: clicable ? accion : null,
      onkeydown: clicable ? ((ev) => { if (ev.key === "Enter" || ev.key === " ") { ev.preventDefault(); accion(); } }) : null,
    },
      svg("title", {}, document.createTextNode(titulo)),
      svg("rect", { x: nodo.x, y: Y, width: ANCHO, height: ALTO, rx: nodo.decision ? 20 : 8 }),
      svg("text", { x: nodo.x + ANCHO / 2, y: Y + 17, class: "nodo-id" }, document.createTextNode(nodo.id)),
      svg("text", { x: nodo.x + ANCHO / 2, y: Y + 31, class: "nodo-etiqueta" }, document.createTextNode(nodo.etiqueta)),
    ));
  });
  cont.append(lienzo);

  const donde = $("#circuito-donde");
  if (estado.job_activo && ctx.fase.nodo) {
    donde.textContent = `· ahora en ${ctx.fase.nodo}`
      + (ctx.fase.capitulo ? `, capítulo ${ctx.fase.capitulo}` : "")
      + (ctx.fase.iteracion ? `, iteración ${ctx.fase.iteracion}` : "");
  } else if (ctx.pendiente) donde.textContent = `· siguiente: capítulo ${ctx.pendiente.n}`;
  else donde.textContent = ctx.total ? "· sin capítulos pendientes" : "";
}

// --------------------------------------------------------------------------- alertas y brief

function renderAlertas() {
  const cont = $("#alertas");
  cont.innerHTML = "";
  if (!estado.brief.completo) {
    cont.append(crear("div", { class: "alerta alerta-error" },
      `Falta completar el brief (${estado.brief.faltantes.join(", ")}) en brief.md. `
      + "El sistema no inventa valores por defecto y no arranca sin ellos."));
  }
  if (estado.escaleta.desincronizada) {
    cont.append(crear("div", { class: "alerta alerta-aviso" },
      "config/capitulos.json ha cambiado desde que se sembró la escaleta. Pulsa «Sincronizar» antes de continuar."));
  }
  estado.capitulos.filter((c) => c.estado === "escalado").forEach((c) => {
    cont.append(crear("div", { class: "alerta alerta-aviso" },
      `El capítulo ${c.n} («${c.titulo}») ha escalado tras tres iteraciones y espera tu decisión.`));
  });
  if (estado.manuscrito.compilado && !estado.manuscrito.aprobado) {
    cont.append(crear("div", { class: "alerta alerta-aviso" },
      "El manuscrito está compilado y espera tu aprobación explícita al final de la página."));
  }
}

function renderBrief() {
  const cont = $("#brief-cuerpo");
  cont.innerHTML = "";
  if (!estado.brief.existe) { cont.append(crear("p", { class: "tenue" }, "No existe brief.md.")); return; }
  Object.entries(estado.brief.secciones).forEach(([nombre, texto]) => {
    cont.append(crear("p", {}, crear("strong", {}, nombre + ": "), texto));
  });
}

async function renderEscaleta() {
  const cont = $("#escaleta-cuerpo");
  cont.innerHTML = "";
  cont.append(crear("p", { class: "tenue" },
    estado.escaleta.pendiente_aprobacion ? "Hay un plan de N2 pendiente de tu aprobación."
      : estado.escaleta.sembrada ? "La escaleta ya está sembrada en memory/."
      : "Todavía no hay escaleta."));

  if (!estado.brief.completo) {
    cont.append(crear("p", {}, crear("em", {}, "Completa el brief antes de preparar la escaleta.")));
    return;
  }

  if (estado.escaleta.pendiente_aprobacion) {
    const datos = await api("/api/escaleta/pendiente");
    const bible = datos.bible || {}, outline = datos.outline || {};
    const resumen = crear("div", {});
    if (bible.voz && bible.voz.muestra) resumen.append(crear("p", {}, crear("strong", {}, "Muestra de voz: "), bible.voz.muestra));
    (outline.capitulos || []).forEach((c) => resumen.append(crear("p", {},
      crear("strong", {}, `Cap. ${c.n} — ${c.titulo || "(sin título)"}: `), c.objetivo || "")));
    cont.append(resumen);

    const motivo = crear("textarea", { rows: "2", placeholder: "Motivo del rechazo (para relanzar N2 con este apunte)…" });
    cont.append(crear("div", { class: "fila", style: "margin-top:0.7rem" },
      crear("button", { class: "primario", onclick: async () => {
        try { await post("/api/escaleta/aprobar"); aviso("Biblia y escaleta sembradas en memory/.", "ok"); cargarEstado(); }
        catch (e) { avisar(e); }
      } }, "Aprobar y sembrar en memory/"),
      crear("button", { class: "peligro", onclick: () => {
        const m = motivo.value.trim();
        if (!m) { avisar("Escribe un motivo antes de rechazar."); return; }
        lanzar("/api/escaleta/rechazar", { motivo: m });
      } }, "Rechazar y relanzar N2")));
    cont.append(motivo);
    return;
  }

  if (!estado.escaleta.sembrada) {
    cont.append(crear("button", { class: "primario", onclick: () => lanzar("/api/escaleta/preparar") }, "Lanzar N1 y N2"));
  } else {
    cont.append(crear("div", { style: "margin-top:0.7rem" },
      crear("button", { class: "chico", onclick: async () => {
        try { const r = await post("/api/sincronizar"); aviso(r.salida, "neutro"); cargarEstado(); }
        catch (e) { avisar(e); }
      } }, "Sincronizar con config/capitulos.json")));
  }
}

// --------------------------------------------------------------------------- texto de un capítulo

// El Revisor escribe la ubicación en prosa («linea 3»), porque la escribe para
// quien va a reescribir. De ahí se saca el número para poder saltar al sitio.
function lineaDeNota(nota) {
  const casa = /l[ií]neas?\s*(\d+)/i.exec(nota.ubicacion || "");
  return casa ? Number(casa[1]) : null;
}

function parrafosDe(texto) {
  const parrafos = [];
  let actual = [];
  texto.split("\n").forEach((linea) => {
    const limpia = linea.trim();
    if (!limpia) { if (actual.length) { parrafos.push(actual); actual = []; } return; }
    if (limpia.startsWith("#")) { if (actual.length) { parrafos.push(actual); actual = []; } return; }
    actual.push(limpia);
  });
  if (actual.length) parrafos.push(actual);
  return parrafos;
}

// Un capítulo se lee como se lee un libro: párrafos corridos, tipografía con
// serifa, sangría francesa. Las líneas siguen estando ahí como anclas invisibles
// -el conteo por líneas es cosa del hook, no de cómo se lee- para que una nota
// del Revisor pueda seguir señalando su sitio exacto sin numerarlo todo.
function renderProsa(texto, notas, opciones) {
  const conNumeros = !!(opciones && opciones.numeros);
  const marcadas = new Set((notas || []).map(lineaDeNota).filter(Boolean));
  const cont = crear("div", { class: `prosa${conNumeros ? " prosa-numerada" : ""}` });
  let n = 0;
  parrafosDe(texto).forEach((parrafo) => {
    const p = crear("p", {});
    parrafo.forEach((linea, i) => {
      n += 1;
      if (conNumeros) p.append(crear("span", { class: "ln-num" }, String(n)));
      p.append(crear("span", {
        class: `ln${marcadas.has(n) ? " ln-marcada" : ""}`, "data-linea": String(n),
        title: marcadas.has(n) ? "El Revisor señala esta línea" : null,
      }, linea));
      if (i < parrafo.length - 1) p.append(document.createTextNode(" "));
    });
    cont.append(p);
  });
  return cont;
}

function saltarALinea(zona, num) {
  const destino = zona.querySelector(`.ln[data-linea="${num}"]`);
  if (!destino) return;
  $$(".ln-activa", zona).forEach((e) => e.classList.remove("ln-activa"));
  destino.classList.add("ln-activa");
  destino.scrollIntoView({ behavior: "smooth", block: "center" });
}

function renderNotas(notas, zona) {
  const ul = crear("ul", { class: "notas" });
  (notas || []).forEach((nota) => {
    const num = lineaDeNota(nota);
    const li = crear("li", { class: `nota nota-${nota.severidad || "media"}${num ? " nota-anclada" : ""}` },
      crear("div", { class: "nota-cab" },
        crear("span", { class: "nota-sev" }, nota.severidad || "media"),
        crear("span", { class: "nota-donde" }, nota.ubicacion || "")),
      crear("div", {}, nota.problema),
      nota.sugerencia ? crear("div", { class: "nota-sugerencia" }, nota.sugerencia) : null);
    if (num) li.addEventListener("click", () => saltarALinea(zona, num));
    ul.append(li);
  });
  return ul;
}

function renderComparador(n, versiones) {
  const textos = versiones.filter((v) => v.tipo === "texto");
  const caja = crear("div", {});
  if (textos.length < 2) {
    caja.append(crear("p", { class: "tenue" }, textos.length === 1
      ? "Solo hay una versión archivada: no hubo reescritura."
      : "Sin versiones archivadas. El harness empezó a guardarlas al añadir esta pantalla; los capítulos anteriores solo existen en su forma final."));
    return caja;
  }
  const etiqueta = (v, i) => `${i + 1}ª · ${new Date(v.cuando).toLocaleString()}`;
  const selA = crear("select", {}, ...textos.map((v, i) => crear("option", { value: v.id }, etiqueta(v, i))));
  const selB = crear("select", {}, ...textos.map((v, i) => crear("option", { value: v.id }, etiqueta(v, i))));
  selA.value = textos[textos.length - 2].id;
  selB.value = textos[textos.length - 1].id;
  const salida = crear("div", { class: "diff" });

  const comparar = async () => {
    salida.innerHTML = "";
    salida.append(crear("p", { class: "tenue" }, "comparando…"));
    try {
      const d = await api(`/api/capitulos/${n}/diff?a=${encodeURIComponent(selA.value)}&b=${encodeURIComponent(selB.value)}`);
      salida.innerHTML = "";
      if (d.iguales) { salida.append(crear("p", { class: "tenue" }, "Las dos versiones son idénticas.")); return; }
      d.filas.forEach((f) => salida.append(crear("div", { class: `diff-linea diff-${f.clase}` }, f.texto)));
    } catch (e) {
      salida.innerHTML = "";
      salida.append(crear("p", { class: "tenue" }, `No se ha podido comparar: ${e.message}`));
    }
  };
  selA.addEventListener("change", comparar);
  selB.addEventListener("change", comparar);
  caja.append(crear("div", { class: "fila" }, selA, crear("span", { class: "tenue" }, "→"), selB), salida);
  comparar();
  return caja;
}

// --------------------------------------------------------------------------- detalle de capítulo

const PESTANAS = [
  { id: "lectura", etiqueta: "Lectura" },
  { id: "revision", etiqueta: "Revisión" },
  { id: "ficha", etiqueta: "Ficha" },
  { id: "versiones", etiqueta: "Versiones" },
];

async function pintarDetalle(n, contenedor) {
  contenedor.innerHTML = "";
  contenedor.append(crear("p", { class: "tenue" }, "cargando…"));
  let datos;
  try { datos = await api(`/api/capitulos/${n}`); }
  catch (e) {
    contenedor.innerHTML = "";
    contenedor.append(crear("p", { class: "tenue" }, `No se ha podido cargar: ${e.message}`));
    return;
  }
  contenedor.innerHTML = "";

  const review = datos.review || {};
  const notas = review.notas || [];
  const panel = crear("div", { class: "panel-pestana" });

  const pestanas = crear("div", { class: "pestanas" });
  const activa = ui.pestanas[n] || "lectura";
  PESTANAS.forEach((p) => {
    const disponible = p.id === "lectura" || p.id === "ficha"
      ? true : p.id === "revision" ? !!datos.review : true;
    const boton = crear("button", {
      class: `pestana${p.id === activa ? " pestana-activa" : ""}`,
      disabled: !disponible,
      onclick: () => {
        ui.pestanas[n] = p.id; guardarUI();
        $$(".pestana", pestanas).forEach((b) => b.classList.toggle("pestana-activa", b === boton));
        pintarPanel(p.id);
      },
    }, p.etiqueta);
    pestanas.append(boton);
  });

  function pintarPanel(id) {
    panel.innerHTML = "";
    if (id === "lectura") {
      if (!datos.texto) { panel.append(crear("p", { class: "tenue" }, "Todavía no hay manuscrito para este capítulo.")); return; }
      panel.append(crear("div", { class: "hoja" },
        crear("p", { class: "hoja-num" }, String(n)),
        crear("h3", {}, (datos.ficha || {}).titulo || ""),
        renderProsa(datos.texto, notas)));
      panel.append(crear("div", { class: "fila", style: "margin-top:0.6rem" },
        crear("button", { class: "chico", onclick: () => abrirLector(n) }, "Leerlo en el libro entero →")));
      return;
    }
    if (id === "revision") {
      if (!datos.review) { panel.append(crear("p", { class: "tenue" }, "Este capítulo aún no tiene revisión.")); return; }
      panel.append(crear("div", { class: "rubrica" },
        ...Object.entries(review.puntuaciones || {}).map(([k, v]) => crear("span",
          { class: `punt punt-${v <= 2 ? "malo" : v === 3 ? "justo" : "bien"}` },
          crear("em", {}, k.replace(/_/g, " ")), String(v))),
        crear("span", { class: `punt punt-media punt-${review.veredicto === "aprobado" ? "bien" : "malo"}` },
          crear("em", {}, "media"), String(review.media))));
      const zona = renderProsa(datos.texto || "", notas, { numeros: true });
      panel.append(zona);
      if (notas.length) {
        panel.append(crear("p", { class: "tenue pista" }, "Pulsa una nota para saltar a la línea que señala."));
        panel.append(renderNotas(notas, zona));
      } else {
        panel.append(crear("p", { class: "tenue" }, "El Revisor no dejó notas."));
      }
      return;
    }
    if (id === "ficha") {
      const f = datos.ficha || {};
      const filas = [["Objetivo", f.objetivo], ["Conflicto", f.conflicto], ["Salida", f.salida],
        ["Problema táctico", f.problema_tactico], ["Punto de vista", f.pov],
        ["Resumen consolidado", f.resumen]];
      let alguna = false;
      filas.forEach(([k, v]) => { if (v) { alguna = true; panel.append(crear("p", {}, crear("strong", {}, `${k}: `), v)); } });
      if (!alguna) panel.append(crear("p", { class: "tenue" }, "La ficha está en blanco: falta N2."));
      return;
    }
    panel.append(renderComparador(n, datos.versiones || []));
  }

  contenedor.append(pestanas, panel);
  pintarPanel(activa);
}

// --------------------------------------------------------------------------- lista de capítulos

// Cada fila se crea una vez y luego se parchea. Es lo que permite tener un
// capítulo abierto mientras el circuito avanza por debajo sin que se cierre.
const filas = new Map();

function construirFila(cap) {
  const cabecera = crear("div", { class: "cap-cab" });
  const acciones = crear("div", { class: "fila cap-acciones" });
  const detalle = crear("div", { class: "detalle" });
  const fila = crear("div", { class: "capitulo" }, cabecera, detalle);

  const alternar = () => {
    const abierto = ui.capitulos.has(cap.n);
    if (abierto) { ui.capitulos.delete(cap.n); detalle.classList.remove("abierto"); }
    else {
      ui.capitulos.add(cap.n);
      detalle.classList.add("abierto");
      pintarDetalle(cap.n, detalle);
    }
    guardarUI();
    fila.classList.toggle("cap-abierto", !abierto);
  };

  cabecera.addEventListener("click", (ev) => { if (!ev.target.closest("button")) alternar(); });
  fila._alternar = alternar;
  fila._cabecera = cabecera;
  fila._acciones = acciones;
  fila._detalle = detalle;
  return fila;
}

function actualizarFila(fila, cap) {
  const abierto = ui.capitulos.has(cap.n);
  const sinFicha = cap.ficha_completa === false && cap.estado !== "consolidado";
  const ocupado = !!estado.job_activo;
  const enCurso = estado.job_activo && (estado.job_activo.fase || {}).capitulo === cap.n;

  fila.className = `capitulo${cap.estado === "escalado" ? " escalado" : ""}`
    + `${abierto ? " cap-abierto" : ""}${enCurso ? " cap-en-curso" : ""}`;

  const cab = fila._cabecera;
  cab.innerHTML = "";
  // Ojo con `append`: convierte null en el texto "null", al contrario que
  // `crear`, que los filtra. Aquí se filtran a mano antes de añadirlos.
  [
    crear("span", { class: "cap-chevron" }, abierto ? "▾" : "▸"),
    crear("strong", {}, `Cap. ${String(cap.n).padStart(2, "0")}`),
    crear("span", { class: "cap-titulo" }, cap.titulo || "(sin título)"),
    badge(cap.estado, { consolidado: "ok", escalado: "error", en_revision: "aviso" }[cap.estado] || "neutro"),
    sinFicha ? badge("sin ficha", "aviso") : null,
    enCurso ? badge("en curso", "aviso") : null,
    cap.media != null ? crear("span", { class: "tenue" }, `media ${cap.media}`) : null,
    cap.iteraciones ? crear("span", { class: "tenue" }, `it. ${cap.iteraciones}/3`) : null,
    fila._acciones,
  ].filter(Boolean).forEach((n) => cab.append(n));

  const acc = fila._acciones;
  acc.innerHTML = "";
  if (cap.manuscrito_existe) {
    acc.append(crear("button", { class: "chico", onclick: () => abrirLector(cap.n) }, "Leer"));
  }
  if (sinFicha) {
    acc.append(crear("button", { class: "chico primario", disabled: ocupado,
      onclick: () => lanzar(`/api/capitulos/${cap.n}/ficha`) }, "Rellenar ficha (N2)"));
  } else if (cap.estado === "escalado") {
    acc.append(crear("button", { class: "chico peligro", onclick: () => fila._alternar() }, "Decidir"));
  } else if (cap.estado !== "consolidado") {
    acc.append(crear("button", { class: "chico primario", disabled: ocupado,
      onclick: () => lanzar(`/api/capitulos/${cap.n}/lanzar`) }, "Lanzar ciclo (N3→N4→D1)"));
  }

  fila._detalle.classList.toggle("abierto", abierto);
  if (abierto && !fila._detalle.childElementCount) pintarDetalle(cap.n, fila._detalle);

  // El bloque de decisión de un capítulo escalado vive dentro del detalle para
  // que no se pueda decidir sin haber abierto el texto y la revisión.
  if (cap.estado === "escalado" && abierto && !fila._detalle.querySelector(".escalado-decision")) {
    const indic = crear("textarea", { rows: "2", placeholder: "Indicaciones nuevas para el Escritor antes de reescribir…" });
    fila._detalle.append(crear("div", { class: "escalado-decision" },
      crear("p", { class: "tenue" }, "Tres iteraciones agotadas. Lee el texto y la revisión, y decide: "
        + "reescribe con indicaciones nuevas, o cambia la escaleta y sincroniza."),
      indic,
      crear("button", { class: "primario", disabled: ocupado, onclick: () => {
        const v = indic.value.trim();
        if (!v) { avisar("Escribe unas indicaciones antes de reescribir."); return; }
        lanzar(`/api/capitulos/${cap.n}/reescribir`, { indicaciones: v });
      } }, "Reescribir con estas indicaciones")));
  }
}

function renderCapitulos() {
  const lista = $("#capitulos-lista");
  const vistos = new Set();

  estado.capitulos.forEach((cap, i) => {
    vistos.add(cap.n);
    let fila = filas.get(cap.n);
    if (!fila) { fila = construirFila(cap); filas.set(cap.n, fila); }
    actualizarFila(fila, cap);
    if (lista.children[i] !== fila) lista.insertBefore(fila, lista.children[i] || null);
  });
  [...filas.keys()].filter((n) => !vistos.has(n)).forEach((n) => {
    filas.get(n).remove(); filas.delete(n);
  });

  const consolidados = estado.capitulos.filter((c) => c.estado === "consolidado").length;
  $("#capitulos-resumen").textContent = `${consolidados} / ${estado.capitulos.length} consolidados`;
  const btn = $("#btn-continuar");
  btn.disabled = !estado.escaleta.sembrada || estado.escaleta.pendiente_aprobacion
    || !!estado.job_activo || consolidados === estado.capitulos.length;
  btn.onclick = () => lanzar("/api/continuar");
}

// --------------------------------------------------------------------------- capítulo nuevo

let nuevoCapMontado = false;

function renderNuevoCapitulo() {
  const cont = $("#nuevo-capitulo");
  if (!estado.escaleta.sembrada) { cont.innerHTML = ""; nuevoCapMontado = false; return; }
  if (nuevoCapMontado) {
    // Solo se refresca lo que depende del estado; el formulario que el autor
    // esté rellenando no se toca.
    const b = cont.querySelector(".btn-anadir");
    if (b) b.disabled = !!estado.job_activo;
    return;
  }
  nuevoCapMontado = true;
  cont.innerHTML = "";

  const ultimo = estado.capitulos[estado.capitulos.length - 1] || {};
  const campo = (etiqueta, valor) => {
    const input = crear("input", { type: "number", min: "1", value: String(valor) });
    return { input, nodo: crear("label", { class: "campo" }, etiqueta, input) };
  };
  const lineas = campo("Líneas", ultimo.lineas_objetivo || 12);
  const parrafos = campo("Párrafos", 3);
  const porParrafo = campo("Líneas por párrafo", 4);
  const combate = crear("input", { type: "checkbox" });
  const producir = crear("input", { type: "checkbox" });
  const pista = crear("p", { class: "tenue pista-reparto" });

  const revisar = () => {
    const l = Number(lineas.input.value), p = Number(parrafos.input.value), pp = Number(porParrafo.input.value);
    if (p && pp) {
      pista.textContent = p * pp === l ? `✓ ${p} × ${pp} = ${l} líneas`
        : `✗ ${p} × ${pp} = ${p * pp}, y has pedido ${l}`;
      pista.className = `tenue pista-reparto ${p * pp === l ? "cuadra" : "no-cuadra"}`;
    } else pista.textContent = "";
  };
  [lineas.input, parrafos.input, porParrafo.input].forEach((i) => i.addEventListener("input", revisar));
  revisar();

  const boton = crear("button", { class: "primario btn-anadir", disabled: !!estado.job_activo,
    onclick: async () => {
      try {
        const r = await post("/api/capitulos/nuevo", {
          lineas_objetivo: Number(lineas.input.value),
          parrafos_objetivo: Number(parrafos.input.value) || null,
          lineas_por_parrafo: Number(porParrafo.input.value) || null,
          contiene_combate: combate.checked,
          producir: producir.checked,
        });
        aviso(`Capítulo ${r.n} añadido al plan (config v${r.config_version}). Lanzando N2 para su ficha.`, "ok");
        seguirJob(r.job_id);
        cargarEstado();
      } catch (e) { avisar(e); }
    } }, "Añadir capítulo");

  cont.append(detalles("nuevo-capitulo", "Añadir un capítulo al plan",
    crear("p", { class: "tenue" },
      "Esto escribe en config/capitulos.json, que es tuyo: la forma la decides aquí y el sistema "
      + "no rellena ningún hueco por su cuenta. Después reproyecta la escaleta y lanza N2 para la "
      + "ficha del capítulo nuevo, sin tocar los ya consolidados."),
    crear("div", { class: "fila campos" }, lineas.nodo, parrafos.nodo, porParrafo.nodo,
      crear("label", { class: "campo-check" }, combate, "Contiene combate")),
    pista,
    crear("div", { class: "fila", style: "margin-top:0.6rem" }, boton,
      crear("label", { class: "campo-check" }, producir, "y producirlo a continuación"))));
}

// --------------------------------------------------------------------------- manuscrito

function renderManuscrito() {
  const cont = $("#manuscrito-cuerpo");
  cont.innerHTML = "";
  const m = estado.manuscrito;

  if (!m.compilado) {
    cont.append(crear("p", { class: "tenue" },
      "Todavía no se ha compilado. Necesita todos los capítulos consolidados y sin hilos pendientes."));
    cont.append(crear("button", { class: "primario", onclick: async () => {
      try {
        const r = await post("/api/manuscrito/compilar");
        if (!r.ok) aviso("N5 no se cierra:\n" + r.problemas.join("\n"), "error");
        else {
          aviso(`Compilado: ${r.capitulos} capítulos, ${r.total} ${r.unidad} en ${r.ruta}.`, "ok");
          (r.avisos || []).forEach((a) => aviso(a, "neutro"));
        }
        cargarEstado();
      } catch (e) { avisar(e); }
    } }, "Compilar dist/manuscrito.md"));
    return;
  }

  cont.append(m.aprobado ? badge(`aprobado el ${new Date(m.aprobado_en).toLocaleString()}`, "ok")
    : badge("pendiente de aprobación", "aviso"));
  if (m.motivo_rechazo) cont.append(crear("p", { class: "tenue" }, `Última vez se rechazó por: ${m.motivo_rechazo}`));

  cont.append(crear("div", { class: "fila", style: "margin-top:0.7rem" },
    crear("button", { class: "primario", onclick: () => abrirLector() }, "Leer el manuscrito")));

  if (!m.aprobado) {
    const motivo = crear("textarea", { rows: "2", placeholder: "Motivo si lo rechazas (opcional)…" });
    cont.append(crear("div", { class: "fila", style: "margin-top:0.7rem" },
      crear("button", { class: "primario", onclick: async () => {
        try { await post("/api/manuscrito/aprobar"); aviso("Manuscrito aprobado.", "ok"); cargarEstado(); }
        catch (e) { avisar(e); }
      } }, "Aprobar manuscrito final"),
      crear("button", { class: "peligro", onclick: async () => {
        try { await post("/api/manuscrito/rechazar", { motivo: motivo.value.trim() }); cargarEstado(); }
        catch (e) { avisar(e); }
      } }, "Rechazar")), motivo);
  } else {
    cont.append(crear("div", { style: "margin-top:0.6rem" },
      crear("button", { class: "chico", onclick: async () => {
        try { await post("/api/manuscrito/rechazar", { motivo: "" }); cargarEstado(); } catch (e) { avisar(e); }
      } }, "Quitar aprobación")));
  }
}

// --------------------------------------------------------------------------- coste

$("#btn-coste").addEventListener("click", async () => {
  const cont = $("#coste-cuerpo");
  cont.innerHTML = "cargando…";
  try {
    const datos = await api("/api/coste?horas=720");
    cont.innerHTML = "";
    if (!datos.disponible) { cont.append(crear("p", { class: "tenue" }, datos.motivo)); return; }
    if (!datos.filas.length) { cont.append(crear("p", { class: "tenue" }, "Sin observaciones de subagentes en los últimos 30 días.")); return; }
    cont.append(crear("table", { class: "coste" },
      crear("thead", {}, crear("tr", {}, ...["nodo", "agente", "llamadas", "tokens", "coste USD"].map((h) => crear("th", {}, h)))),
      crear("tbody", {}, ...datos.filas.map((f) => crear("tr", {},
        crear("td", {}, f.nodo), crear("td", {}, f.agente), crear("td", {}, f.llamadas.toFixed(0)),
        crear("td", {}, f.tokens.toLocaleString()), crear("td", {}, f.coste.toFixed(4)))))));
  } catch (_) {
    cont.innerHTML = "";
    cont.append(crear("p", { class: "tenue" }, "No se ha podido cargar."));
  }
});

// --------------------------------------------------------------------------- el lector

const lector = $("#lector");
const paginas = $("#lector-paginas");
const TEMAS = ["claro", "sepia", "oscuro"];
let libro = null;
let capActual = 0;

function aplicarLector() {
  paginas.style.fontSize = `${ui.lectorTamano}px`;
  lector.dataset.tema = ui.lectorTema;
  guardarUI();
}

function cerrarLector() {
  lector.hidden = true;
  document.body.classList.remove("leyendo");
}

function irACapitulo(i) {
  if (!libro || !libro.capitulos.length) return;
  capActual = Math.max(0, Math.min(libro.capitulos.length - 1, i));
  const destino = paginas.querySelector(`[data-cap="${libro.capitulos[capActual].n}"]`);
  if (destino) destino.scrollIntoView({ behavior: "smooth", block: "start" });
}

function actualizarProgreso() {
  const total = paginas.scrollHeight - paginas.clientHeight;
  const pct = total > 0 ? (paginas.scrollTop / total) * 100 : 0;
  $("#lector-barra").style.width = `${pct}%`;
  // El capítulo actual es el último cuyo comienzo ya ha pasado por arriba.
  if (!libro) return;
  let i = 0;
  libro.capitulos.forEach((c, j) => {
    const el = paginas.querySelector(`[data-cap="${c.n}"]`);
    if (el && el.offsetTop - paginas.scrollTop <= paginas.clientHeight * 0.35) i = j;
  });
  capActual = i;
  const cap = libro.capitulos[i];
  $("#lector-donde").textContent = cap ? `${i + 1} de ${libro.capitulos.length} · ${cap.titulo}` : "";
  $$(".toc-item", $("#lector-toc")).forEach((b, j) => b.classList.toggle("toc-activo", j === i));
}
paginas.addEventListener("scroll", () => requestAnimationFrame(actualizarProgreso));

async function abrirLector(capitulo) {
  lector.hidden = false;
  document.body.classList.add("leyendo");
  aplicarLector();
  paginas.innerHTML = "";
  paginas.append(crear("p", { class: "tenue vacio" }, "cargando…"));
  try {
    libro = await api("/api/lectura");
  } catch (e) {
    paginas.innerHTML = "";
    paginas.append(crear("p", { class: "tenue vacio" }, `No se ha podido cargar: ${e.message}`));
    return;
  }
  paginas.innerHTML = "";

  paginas.append(crear("div", { class: "portada" },
    crear("h1", {}, libro.titulo || "Sin título"),
    crear("p", { class: "portada-datos" },
      `${libro.capitulos.length} ${libro.capitulos.length === 1 ? "capítulo" : "capítulos"} · ${libro.lineas} líneas`)));

  if (!libro.capitulos.length) {
    paginas.append(crear("p", { class: "tenue vacio" }, "Todavía no hay ningún capítulo consolidado que leer."));
  }

  libro.capitulos.forEach((cap) => {
    const sec = crear("section", { class: "cap-lectura", "data-cap": String(cap.n) },
      crear("p", { class: "numero" }, String(cap.n)),
      crear("h2", {}, cap.titulo || ""));
    cap.parrafos.forEach((parrafo) => sec.append(crear("p", {}, parrafo.join(" "))));
    paginas.append(sec);
  });

  if (libro.pendientes.length) {
    paginas.append(crear("p", { class: "tenue vacio" },
      "Aún sin consolidar: " + libro.pendientes.map((c) => `${c.n} (${c.estado})`).join(", ")));
  }

  const toc = $("#lector-toc");
  toc.innerHTML = "";
  libro.capitulos.forEach((cap, i) => {
    toc.append(crear("button", { class: "toc-item", onclick: () => { irACapitulo(i); cerrarIndice(); } },
      crear("span", { class: "toc-num" }, String(cap.n)), cap.titulo || "(sin título)"));
  });

  $("#lector-estado").textContent = libro.compilado
    ? "leyendo manuscript/ · hay un manuscrito compilado"
    : "leyendo manuscript/ · sin compilar todavía";

  paginas.scrollTop = 0;
  if (capitulo) {
    const i = libro.capitulos.findIndex((c) => c.n === capitulo);
    if (i >= 0) requestAnimationFrame(() => irACapitulo(i));
  }
  actualizarProgreso();
}

function cerrarIndice() {
  $("#lector-toc").hidden = true;
  $("#lector-indice").setAttribute("aria-expanded", "false");
}

$("#btn-leer").addEventListener("click", () => abrirLector());
$("#lector-cerrar").addEventListener("click", cerrarLector);
$("#lector-indice").addEventListener("click", () => {
  const toc = $("#lector-toc");
  toc.hidden = !toc.hidden;
  $("#lector-indice").setAttribute("aria-expanded", String(!toc.hidden));
});
$("#lector-mas").addEventListener("click", () => { ui.lectorTamano = Math.min(30, ui.lectorTamano + 1); aplicarLector(); });
$("#lector-menos").addEventListener("click", () => { ui.lectorTamano = Math.max(14, ui.lectorTamano - 1); aplicarLector(); });
$("#lector-tema").addEventListener("click", () => {
  ui.lectorTema = TEMAS[(TEMAS.indexOf(ui.lectorTema) + 1) % TEMAS.length];
  aplicarLector();
});
$("#lector-anterior").addEventListener("click", () => irACapitulo(capActual - 1));
$("#lector-siguiente").addEventListener("click", () => irACapitulo(capActual + 1));

document.addEventListener("keydown", (ev) => {
  if (lector.hidden) return;
  if (ev.key === "Escape") { if (!$("#lector-toc").hidden) cerrarIndice(); else cerrarLector(); }
  else if (ev.key === "ArrowRight") irACapitulo(capActual + 1);
  else if (ev.key === "ArrowLeft") irACapitulo(capActual - 1);
  else if (ev.key === "+") { ui.lectorTamano = Math.min(30, ui.lectorTamano + 1); aplicarLector(); }
  else if (ev.key === "-") { ui.lectorTamano = Math.max(14, ui.lectorTamano - 1); aplicarLector(); }
});

// --------------------------------------------------------------------------- arranque

async function cargarEstado() {
  estado = await api("/api/estado");
  renderCabecera();
  renderCircuito();
  renderAlertas();
  renderBrief();
  await renderEscaleta();
  renderCapitulos();
  renderNuevoCapitulo();
  renderManuscrito();
  if (estado.job_activo) seguirJob(estado.job_activo.id);
}

cargarEstado().catch((error) => {
  $("#main").innerHTML = "";
  $("#main").append(crear("div", { class: "alerta alerta-error" },
    `No se ha podido cargar el estado: ${error.message}`));
});

// Refresco de fondo: por si otro proceso toca memory/ (un `compilar.py` lanzado
// a mano en otra terminal). Cuando hay un job, ya refresca el seguidor.
setInterval(() => { if (!jobSeguido && lector.hidden) cargarEstado().catch(() => {}); }, 8000);
