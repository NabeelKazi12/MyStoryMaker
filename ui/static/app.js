"use strict";

const $ = (sel, el) => (el || document).querySelector(sel);
const crear = (tag, props, ...hijos) => {
  const el = document.createElement(tag);
  Object.entries(props || {}).forEach(([k, v]) => {
    if (k === "class") el.className = v;
    else if (k === "html") el.innerHTML = v;
    else if (k.startsWith("on")) el.addEventListener(k.slice(2), v);
    else el.setAttribute(k, v);
  });
  hijos.flat().forEach((h) => el.append(h instanceof Node ? h : document.createTextNode(h)));
  return el;
};

async function api(ruta, opciones) {
  const resp = await fetch(ruta, {
    headers: { "Content-Type": "application/json" },
    ...opciones,
  });
  let cuerpo = null;
  try { cuerpo = await resp.json(); } catch (_) { /* sin cuerpo */ }
  if (!resp.ok) {
    const motivo = (cuerpo && cuerpo.detail) || `HTTP ${resp.status}`;
    throw new Error(motivo);
  }
  return cuerpo;
}
const post = (ruta, datos) => api(ruta, { method: "POST", body: datos ? JSON.stringify(datos) : undefined });

function avisar(error) {
  alert(typeof error === "string" ? error : error.message || "Ha fallado la operación.");
}

// --------------------------------------------------------------------------- log en vivo

const panelLog = $("#panel-log");
const logCuerpo = $("#log-cuerpo");
const logTitulo = $("#log-titulo");
const logPunto = $("#log-punto");
const logCancelar = $("#log-cancelar");
let jobSeguido = null;
let logTimer = null;

const ETIQUETAS_JOB = {
  preparar: "N1 y N2 · investigación y escaleta",
  capitulo: (meta) => `Capítulo ${String(meta.n).padStart(2, "0")}${meta.reescritura ? " (reescritura)" : ""}`,
  continuar: "Continuar hasta agotar pendientes o escalar",
};

function etiquetaJob(job) {
  const base = ETIQUETAS_JOB[job.kind];
  return typeof base === "function" ? base(job.meta || {}) : base || job.kind;
}

function abrirPanelLog() {
  panelLog.classList.add("abierto");
}

$("#log-cabecera").addEventListener("click", (ev) => {
  if (ev.target === logCancelar) return;
  panelLog.classList.toggle("abierto");
});

logCancelar.addEventListener("click", async () => {
  if (!jobSeguido) return;
  try {
    await post(`/api/jobs/${jobSeguido}/cancelar`);
  } catch (error) {
    avisar(error);
  }
});

function seguirJob(jobId) {
  jobSeguido = jobId;
  logCuerpo.textContent = "";
  abrirPanelLog();
  if (logTimer) clearInterval(logTimer);
  let desde = 0;
  const paso = async () => {
    try {
      const datos = await api(`/api/jobs/${jobId}?desde=${desde}`);
      if (datos.lineas.length) {
        const pegado = logCuerpo.scrollTop + logCuerpo.clientHeight >= logCuerpo.scrollHeight - 8;
        logCuerpo.textContent += (desde > 0 ? "\n" : "") + datos.lineas.join("\n");
        desde = datos.total;
        if (pegado) logCuerpo.scrollTop = logCuerpo.scrollHeight;
      }
      logTitulo.textContent = etiquetaJob(datos);
      logPunto.className = "punto " + (
        datos.estado === "en_curso" ? "punto-curso" : datos.estado === "ok" ? "punto-ok" : "punto-error"
      );
      logCancelar.hidden = datos.estado !== "en_curso";
      if (datos.estado !== "en_curso") {
        clearInterval(logTimer);
        logTimer = null;
        if (datos.estado === "error" && datos.error) {
          logCuerpo.textContent += `\n\n--- ${datos.error}`;
          logCuerpo.scrollTop = logCuerpo.scrollHeight;
        }
        cargarEstado();
      }
    } catch (error) {
      clearInterval(logTimer);
      logTimer = null;
    }
  };
  paso();
  logTimer = setInterval(paso, 1500);
}

async function lanzar(ruta, datos, opts) {
  try {
    const { job_id } = await post(ruta, datos);
    seguirJob(job_id);
    if (opts && opts.trasArrancar) opts.trasArrancar();
  } catch (error) {
    avisar(error);
  }
}

// --------------------------------------------------------------------------- render

let estado = null;

function badge(texto, clase) {
  return crear("span", { class: `badge badge-${clase}` }, texto);
}

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
  if (estado.job_activo) {
    badges.append(badge(`en curso: ${etiquetaJob(estado.job_activo)}`, "aviso"));
  }
}

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
  const escalados = estado.capitulos.filter((c) => c.estado === "escalado");
  escalados.forEach((c) => {
    cont.append(crear("div", { class: "alerta alerta-aviso" },
      `El capítulo ${c.n} («${c.titulo}») ha escalado tras tres iteraciones y espera tu decisión más abajo.`));
  });
  if (estado.manuscrito.compilado && !estado.manuscrito.aprobado) {
    cont.append(crear("div", { class: "alerta alerta-aviso" },
      "El manuscrito está compilado y espera tu aprobación explícita al final de la página."));
  }
}

function renderBrief() {
  const cont = $("#brief-cuerpo");
  cont.innerHTML = "";
  if (!estado.brief.existe) {
    cont.append(crear("p", { class: "tenue" }, "No existe brief.md."));
    return;
  }
  const dl = crear("div", {});
  Object.entries(estado.brief.secciones).forEach(([nombre, texto]) => {
    dl.append(crear("p", {}, crear("strong", {}, nombre + ": "), texto));
  });
  cont.append(dl);
}

function textoEscaletaEstado() {
  if (estado.escaleta.pendiente_aprobacion) return "Hay un plan de N2 pendiente de tu aprobación.";
  if (estado.escaleta.sembrada) return "La escaleta ya está sembrada en memory/.";
  return "Todavía no hay escaleta.";
}

async function renderEscaleta() {
  const cont = $("#escaleta-cuerpo");
  cont.innerHTML = "";
  cont.append(crear("p", { class: "tenue" }, textoEscaletaEstado()));

  if (!estado.brief.completo) {
    cont.append(crear("p", {}, crear("em", {}, "Completa el brief antes de preparar la escaleta.")));
    return;
  }

  if (estado.escaleta.pendiente_aprobacion) {
    const datos = await api("/api/escaleta/pendiente");
    const bible = datos.bible || {};
    const outline = datos.outline || {};
    const resumen = crear("div", {});
    if (bible.voz && bible.voz.muestra) {
      resumen.append(crear("p", {}, crear("strong", {}, "Muestra de voz: "), bible.voz.muestra));
    }
    (outline.capitulos || []).forEach((c) => {
      resumen.append(crear("p", {},
        crear("strong", {}, `Cap. ${c.n} — ${c.titulo || "(sin título)"}: `),
        c.objetivo || ""));
    });
    cont.append(resumen);

    const textareaMotivo = crear("textarea", { rows: "2", placeholder: "Motivo del rechazo (para relanzar N2 con este apunte)…" });
    cont.append(crear("div", { class: "fila", style: "margin-top:0.7rem" },
      crear("button", { class: "primario", onclick: async () => {
        try { await post("/api/escaleta/aprobar"); cargarEstado(); }
        catch (error) { avisar(error); }
      } }, "Aprobar y sembrar en memory/"),
      crear("button", { class: "peligro", onclick: () => {
        const motivo = textareaMotivo.value.trim();
        if (!motivo) { avisar("Escribe un motivo antes de rechazar."); return; }
        lanzar("/api/escaleta/rechazar", { motivo });
      } }, "Rechazar y relanzar N2"),
    ));
    cont.append(textareaMotivo);
    return;
  }

  if (!estado.escaleta.sembrada) {
    cont.append(crear("button", { class: "primario", onclick: () => lanzar("/api/escaleta/preparar") },
      "Lanzar N1 y N2"));
  }
}

function badgeEstadoCapitulo(estadoCap) {
  const mapa = { consolidado: "ok", escalado: "error", en_revision: "aviso", pendiente: "neutro" };
  return badge(estadoCap, mapa[estadoCap] || "neutro");
}

async function alternarDetalleCapitulo(cap, contenedor) {
  const yaAbierto = contenedor.classList.contains("abierto");
  if (yaAbierto) { contenedor.classList.remove("abierto"); return; }
  contenedor.classList.add("abierto");
  if (contenedor.dataset.cargado) return;
  contenedor.dataset.cargado = "1";
  contenedor.innerHTML = "cargando…";
  try {
    const datos = await api(`/api/capitulos/${cap.n}`);
    contenedor.innerHTML = "";
    if (datos.texto) {
      contenedor.append(crear("pre", { class: "texto" }, datos.texto));
    } else {
      contenedor.append(crear("p", { class: "tenue" }, "Todavía no hay manuscrito para este capítulo."));
    }
    if (datos.review) {
      const r = datos.review;
      const puntos = Object.entries(r.puntuaciones || {}).map(([k, v]) => `${k}: ${v}`).join(" · ");
      contenedor.append(crear("p", {}, crear("strong", {}, `Media ${r.media} (${r.veredicto}) — `), puntos));
      if ((r.notas || []).length) {
        const ul = crear("ul", { class: "notas-review" });
        r.notas.forEach((n) => ul.append(crear("li", {}, `[${n.severidad}] ${n.ubicacion}: ${n.problema}`)));
        contenedor.append(ul);
      }
    }
  } catch (error) {
    contenedor.innerHTML = "";
    contenedor.append(crear("p", { class: "tenue" }, "No se ha podido cargar el detalle."));
  }
}

function renderCapitulo(cap) {
  const puedeLanzar = estado.escaleta.sembrada && cap.estado !== "consolidado" && cap.estado !== "escalado"
    && !estado.job_activo;
  const fila = crear("div", { class: "fila-entre" },
    crear("div", { class: "fila" },
      crear("strong", {}, `Cap. ${String(cap.n).padStart(2, "0")}`),
      cap.titulo || crear("span", { class: "tenue" }, "(sin título)"),
      badgeEstadoCapitulo(cap.estado),
      cap.media != null ? crear("span", { class: "tenue" }, `media ${cap.media}`) : "",
      cap.iteraciones ? crear("span", { class: "tenue" }, `it. ${cap.iteraciones}/3`) : "",
    ),
    crear("div", { class: "fila" },
      crear("button", { class: "chico", onclick: (ev) => alternarDetalleCapitulo(cap, ev.target.closest(".capitulo").querySelector(".detalle")) }, "Ver texto y revisión"),
      cap.estado !== "escalado" ? crear("button", {
        class: "chico primario", disabled: puedeLanzar ? null : "disabled",
        onclick: () => lanzar(`/api/capitulos/${cap.n}/lanzar`, undefined),
      }, cap.estado === "consolidado" ? "Ya consolidado" : "Lanzar ciclo (N3→N4→D1)") : "",
    ),
  );
  const div = crear("div", { class: `capitulo${cap.estado === "escalado" ? " escalado" : ""}` }, fila);
  const detalle = crear("div", { class: "detalle" });
  div.append(detalle);

  if (cap.estado === "escalado") {
    const textareaIndic = crear("textarea", { rows: "2",
      placeholder: "Indicaciones nuevas para el Escritor antes de reescribir…" });
    div.append(crear("div", { style: "margin-top:0.6rem" },
      crear("p", { class: "tenue" }, "Tres iteraciones agotadas. Lee el texto y la revisión, y decide: "
        + "reescribe con indicaciones nuevas, o cambia la escaleta a mano (config/capitulos.json) y sincroniza."),
      textareaIndic,
      crear("div", { class: "fila", style: "margin-top:0.4rem" },
        crear("button", {
          class: "primario", disabled: estado.job_activo ? "disabled" : null,
          onclick: () => {
            const indicaciones = textareaIndic.value.trim();
            if (!indicaciones) { avisar("Escribe unas indicaciones antes de reescribir."); return; }
            lanzar(`/api/capitulos/${cap.n}/reescribir`, { indicaciones });
          },
        }, "Reescribir con estas indicaciones"),
      )));
  }
  return div;
}

function renderCapitulos() {
  const lista = $("#capitulos-lista");
  lista.innerHTML = "";
  estado.capitulos.forEach((cap) => lista.append(renderCapitulo(cap)));
  const consolidados = estado.capitulos.filter((c) => c.estado === "consolidado").length;
  $("#capitulos-resumen").textContent = `${consolidados} / ${estado.capitulos.length} consolidados`;

  const btnContinuar = $("#btn-continuar");
  btnContinuar.disabled = !estado.escaleta.sembrada || estado.escaleta.pendiente_aprobacion || !!estado.job_activo
    || consolidados === estado.capitulos.length;
  btnContinuar.onclick = () => lanzar("/api/continuar");
}

async function renderManuscrito() {
  const cont = $("#manuscrito-cuerpo");
  cont.innerHTML = "";
  const m = estado.manuscrito;

  if (!m.compilado) {
    cont.append(crear("p", { class: "tenue" },
      "Todavía no se ha compilado. Necesita todos los capítulos consolidados y sin hilos pendientes."));
    cont.append(crear("button", { class: "primario", onclick: async () => {
      try {
        const r = await post("/api/manuscrito/compilar");
        if (!r.ok) {
          avisar("N5 no se cierra:\n" + r.problemas.join("\n"));
        }
        cargarEstado();
      } catch (error) { avisar(error); }
    } }, "Compilar dist/manuscrito.md"));
    return;
  }

  if (m.aprobado) {
    cont.append(badge(`aprobado el ${new Date(m.aprobado_en).toLocaleString()}`, "ok"));
  } else {
    cont.append(badge("pendiente de aprobación", "aviso"));
  }
  if (m.motivo_rechazo) {
    cont.append(crear("p", { class: "tenue" }, `Última vez se rechazó por: ${m.motivo_rechazo}`));
  }

  const datos = await api("/api/manuscrito");
  const detalle = crear("details", {}, crear("summary", {}, "Ver manuscrito completo"));
  detalle.append(crear("pre", { class: "texto" }, datos.contenido || ""));
  cont.append(detalle);

  if (!m.aprobado) {
    const textareaMotivo = crear("textarea", { rows: "2", placeholder: "Motivo si lo rechazas (opcional)…" });
    cont.append(crear("div", { class: "fila", style: "margin-top:0.7rem" },
      crear("button", { class: "primario", onclick: async () => {
        try { await post("/api/manuscrito/aprobar"); cargarEstado(); } catch (error) { avisar(error); }
      } }, "Aprobar manuscrito final"),
      crear("button", { class: "peligro", onclick: async () => {
        try { await post("/api/manuscrito/rechazar", { motivo: textareaMotivo.value.trim() }); cargarEstado(); }
        catch (error) { avisar(error); }
      } }, "Rechazar"),
    ));
    cont.append(textareaMotivo);
  } else {
    cont.append(crear("div", { style: "margin-top:0.6rem" },
      crear("button", { class: "chico", onclick: async () => {
        try { await post("/api/manuscrito/rechazar", { motivo: "" }); cargarEstado(); } catch (error) { avisar(error); }
      } }, "Quitar aprobación")));
  }
}

function renderAccionesGenerales() {
  // El botón de sincronizar vive junto a la escaleta porque es lo que
  // reproyecta config/capitulos.json sobre memory/outline.json.
  const cont = $("#escaleta-cuerpo");
  if (estado.escaleta.sembrada) {
    cont.append(crear("div", { style: "margin-top:0.7rem" },
      crear("button", { class: "chico", onclick: async () => {
        try { const r = await post("/api/sincronizar"); alert(r.salida); cargarEstado(); }
        catch (error) { avisar(error); }
      } }, "Sincronizar con config/capitulos.json")));
  }
}

$("#btn-coste").addEventListener("click", async () => {
  const cont = $("#coste-cuerpo");
  cont.innerHTML = "cargando…";
  try {
    const datos = await api("/api/coste?horas=720");
    if (!datos.disponible) {
      cont.innerHTML = "";
      cont.append(crear("p", { class: "tenue" }, datos.motivo));
      return;
    }
    cont.innerHTML = "";
    if (!datos.filas.length) {
      cont.append(crear("p", { class: "tenue" }, "Sin observaciones de subagentes en los últimos 30 días."));
      return;
    }
    const tabla = crear("table", { class: "coste" },
      crear("thead", {}, crear("tr", {}, crear("th", {}, "nodo"), crear("th", {}, "agente"),
        crear("th", {}, "llamadas"), crear("th", {}, "tokens"), crear("th", {}, "coste USD"))),
      crear("tbody", {}, ...datos.filas.map((f) => crear("tr", {},
        crear("td", {}, f.nodo), crear("td", {}, f.agente), crear("td", {}, f.llamadas.toFixed(0)),
        crear("td", {}, f.tokens.toLocaleString()), crear("td", {}, f.coste.toFixed(4))))));
    cont.append(tabla);
  } catch (error) {
    cont.innerHTML = "";
    cont.append(crear("p", { class: "tenue" }, "No se ha podido cargar."));
  }
});

async function cargarEstado() {
  estado = await api("/api/estado");
  renderCabecera();
  renderAlertas();
  renderBrief();
  await renderEscaleta();
  renderAccionesGenerales();
  renderCapitulos();
  await renderManuscrito();

  if (estado.job_activo && jobSeguido !== estado.job_activo.id) {
    seguirJob(estado.job_activo.id);
  }
}

cargarEstado().catch((error) => {
  $("#main").innerHTML = "";
  $("#main").append(crear("div", { class: "alerta alerta-error" },
    `No se ha podido cargar el estado: ${error.message}`));
});

// Refresco periódico ligero: por si hay otro proceso tocando memory/ (por
// ejemplo, `python scripts/compilar.py` lanzado a mano en otra terminal).
setInterval(() => { if (!jobSeguido) cargarEstado().catch(() => {}); }, 8000);
