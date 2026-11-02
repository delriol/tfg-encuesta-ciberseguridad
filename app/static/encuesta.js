// Muestra la encuesta de a una sección. Sin JavaScript, todas las secciones quedan visibles
// y el servidor valida igual.
(function () {
  var form = document.getElementById("form-encuesta");
  if (!form) return;
  var secciones = Array.prototype.slice.call(form.querySelectorAll(".seccion"));
  var total = secciones.length;
  var enviar = document.getElementById("btn-enviar");
  var anterior = document.getElementById("btn-anterior");
  var siguiente = document.getElementById("btn-siguiente");
  var barra = document.getElementById("barra-progreso");
  var actual = 0;

  function respondida(fs) {
    var tipo = fs.dataset.tipo;
    if (tipo === "abierta") return fs.querySelector("textarea").value.trim() !== "";
    if (tipo === "desplegable") return fs.querySelector("select").value !== "";
    return fs.querySelector("input:checked") !== null;
  }

  function marcarError(fs, conError) {
    fs.classList.toggle("border-danger", conError);
    var aviso = fs.querySelector(".aviso-js");
    if (conError && !aviso) {
      aviso = document.createElement("div");
      aviso.className = "aviso-js text-danger small mt-2";
      aviso.textContent = "Falta responder esta pregunta.";
      fs.appendChild(aviso);
    } else if (!conError && aviso) {
      aviso.remove();
    }
  }

  function seccionCompleta(i) {
    var primera = null;
    secciones[i].querySelectorAll(".pregunta").forEach(function (fs) {
      var falta = fs.dataset.obligatoria === "si" && !respondida(fs);
      marcarError(fs, falta);
      if (falta && !primera) primera = fs;
    });
    if (primera) primera.scrollIntoView({ behavior: "smooth", block: "center" });
    return primera === null;
  }

  function mostrar(i) {
    actual = i;
    secciones.forEach(function (s, j) { s.hidden = j !== i; });
    anterior.hidden = i === 0;
    siguiente.hidden = i === total - 1;
    enviar.hidden = i !== total - 1;
    barra.style.width = Math.round(((i + 1) / total) * 100) + "%";
    barra.setAttribute("aria-valuenow", String(i + 1));
    window.scrollTo(0, 0);
  }

  siguiente.addEventListener("click", function () {
    if (seccionCompleta(actual)) mostrar(actual + 1);
  });
  anterior.addEventListener("click", function () { mostrar(actual - 1); });
  form.addEventListener("submit", function (e) {
    for (var i = 0; i < total; i++) {
      if (!seccionCompleta(i)) { e.preventDefault(); mostrar(i); seccionCompleta(i); return; }
    }
    enviar.disabled = true;
    enviar.textContent = "Enviando…";
  });

  // Al contestar, se quita la marca de error de esa pregunta.
  form.addEventListener("change", function (e) {
    var fs = e.target.closest(".pregunta");
    if (fs && respondida(fs)) marcarError(fs, false);
    // Una opción excluyente ("Ninguno") desmarca las demás, y al revés.
    if (e.target.type === "checkbox" && e.target.checked && fs) {
      var excl = e.target.dataset.excluyente === "si";
      fs.querySelectorAll("input[type=checkbox]").forEach(function (c) {
        if (c !== e.target && (excl || c.dataset.excluyente === "si")) c.checked = false;
      });
    }
  });

  // Si el servidor devolvió errores, se abre la primera sección con problemas.
  var conError = form.querySelector(".pregunta.border-danger");
  var inicio = conError ? secciones.indexOf(conError.closest(".seccion")) : 0;
  document.getElementById("navegacion").hidden = false;
  document.getElementById("progreso").hidden = false;
  mostrar(inicio < 0 ? 0 : inicio);
})();
