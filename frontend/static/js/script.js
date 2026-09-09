const elBuscador = document.getElementById("buscador");
const elBtnBuscar = document.getElementById("btn-buscar");
const elListaCategorias = document.getElementById("lista-categorias");
const elFiltroEstado = document.getElementById("filtro-estado");
const elGrid = document.getElementById("grid-productos");
const elContador = document.getElementById("contador-resultados");
const elMensajeError = document.getElementById("mensaje-error");
const elMensajeVacio = document.getElementById("mensaje-vacio");
const elToggleModo = document.getElementById("toggle-modo");
const elModoLabel = document.getElementById("modo-label");
const plantilla = document.getElementById("plantilla-producto");

let categoriaActual = "";
let temporizadorBusqueda = null;

const formatoCOP = new Intl.NumberFormat("es-CO", {
  style: "currency",
  currency: "COP",
  maximumFractionDigits: 0,
});

const ETIQUETAS_ESTADO = {
  disponible: "Disponible",
  stock_bajo: "Stock bajo",
  agotado: "Agotado",
};

document.addEventListener("DOMContentLoaded", () => {
  cargarCategorias();
  cargarProductos();
});

elToggleModo.addEventListener("change", () => {
  const esBodega = elToggleModo.checked;
  document.body.classList.toggle("modo-bodega", esBodega);
  elModoLabel.textContent = esBodega ? "Modo bodega" : "Modo cliente";
});

elBtnBuscar.addEventListener("click", () => cargarProductos());
elBuscador.addEventListener("input", () => {
  clearTimeout(temporizadorBusqueda);
  temporizadorBusqueda = setTimeout(cargarProductos, 350);
});
elBuscador.addEventListener("keydown", (evento) => {
  if (evento.key === "Enter") cargarProductos();
});
elFiltroEstado.addEventListener("change", () => cargarProductos());

async function cargarCategorias() {
  try {
    const respuesta = await fetch("/api/categorias");
    if (!respuesta.ok) throw new Error("No se pudieron cargar las categorías");
    const categorias = await respuesta.json();

    categorias.forEach((categoria) => {
      const boton = document.createElement("button");
      boton.className = "categoria-btn";
      boton.textContent = categoria;
      boton.dataset.categoria = categoria;
      boton.addEventListener("click", () => seleccionarCategoria(categoria, boton));
      elListaCategorias.appendChild(boton);
    });

    const botonTodas = elListaCategorias.querySelector('[data-categoria=""]');
    botonTodas.addEventListener("click", () => seleccionarCategoria("", botonTodas));
  } catch (error) {
    console.error(error);
  }
}

function seleccionarCategoria(categoria, botonClicado) {
  categoriaActual = categoria;
  document
    .querySelectorAll(".categoria-btn")
    .forEach((b) => b.classList.remove("categoria-btn--activa"));
  botonClicado.classList.add("categoria-btn--activa");
  cargarProductos();
}

async function cargarProductos() {
  ocultar(elMensajeError);
  ocultar(elMensajeVacio);
  elContador.textContent = "Cargando productos…";

  const parametros = new URLSearchParams();
  if (elBuscador.value.trim()) parametros.set("buscar", elBuscador.value.trim());
  if (categoriaActual) parametros.set("categoria", categoriaActual);
  if (elFiltroEstado.value) parametros.set("estado", elFiltroEstado.value);

  try {
    const respuesta = await fetch(`/api/productos?${parametros.toString()}`);
    if (!respuesta.ok) throw new Error("El servidor respondió con un error");
    const productos = await respuesta.json();
    renderizarProductos(productos);
  } catch (error) {
    console.error(error);
    elContador.textContent = "";
    mostrar(elMensajeError);
    elMensajeError.textContent =
      "No fue posible conectar con el servidor de inventario. Verifica que el backend esté en ejecución e inténtalo de nuevo.";
  }
}

function renderizarProductos(productos) {
  elGrid.innerHTML = "";

  if (productos.length === 0) {
    elContador.textContent = "0 productos encontrados";
    mostrar(elMensajeVacio);
    return;
  }

  elContador.textContent = `${productos.length} producto${productos.length === 1 ? "" : "s"} encontrado${productos.length === 1 ? "" : "s"}`;

  productos.forEach((producto) => elGrid.appendChild(crearTarjeta(producto)));
}

function crearTarjeta(producto) {
  const nodo = plantilla.content.cloneNode(true);
  const tarjeta = nodo.querySelector(".tarjeta");

  const badge = nodo.querySelector(".tarjeta__badge");
  badge.textContent = ETIQUETAS_ESTADO[producto.estado];
  badge.classList.add(`tarjeta__badge--${producto.estado}`);

  nodo.querySelector(".tarjeta__imagen span").textContent = iniciales(producto.nombre);
  nodo.querySelector(".tarjeta__categoria").textContent = producto.categoria;
  nodo.querySelector(".tarjeta__nombre").textContent = producto.nombre;
  nodo.querySelector(".tarjeta__tienda").textContent = `📍 ${producto.tienda}`;
  nodo.querySelector(".tarjeta__precio").textContent = formatoCOP.format(producto.precio);
  nodo.querySelector(".tarjeta__stock").textContent =
    `${producto.cantidad} ${producto.unidad} disponibles · mínimo ${producto.stock_minimo}`;
  nodo.querySelector(".tarjeta__actualizado").textContent =
    `Última actualización: ${producto.actualizado_en}`;

  const input = nodo.querySelector(".input-cantidad");
  input.value = producto.cantidad;
  input.placeholder = "Nueva cantidad";

  const boton = nodo.querySelector(".btn-guardar");
  const feedback = nodo.querySelector(".tarjeta__feedback");

  boton.addEventListener("click", () =>
    actualizarCantidad(producto.id, input, boton, feedback)
  );

  return nodo;
}

async function actualizarCantidad(id, input, boton, feedback) {
  feedback.textContent = "";
  feedback.className = "tarjeta__feedback";

  const valor = input.value.trim();

  if (valor === "" || isNaN(valor) || !Number.isInteger(Number(valor)) || Number(valor) < 0) {
    feedback.textContent = "Ingresa un número entero mayor o igual a 0.";
    feedback.classList.add("tarjeta__feedback--error");
    return;
  }

  boton.disabled = true;
  boton.textContent = "Guardando…";

  try {
    const respuesta = await fetch(`/api/productos/${id}`, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ cantidad: Number(valor) }),
    });

    const datos = await respuesta.json();

    if (!respuesta.ok) {
      throw new Error(datos.error || "No se pudo actualizar el producto");
    }

    feedback.textContent = "Inventario actualizado correctamente.";
    feedback.classList.add("tarjeta__feedback--ok");

    setTimeout(cargarProductos, 500);
  } catch (error) {
    feedback.textContent = error.message;
    feedback.classList.add("tarjeta__feedback--error");
  } finally {
    boton.disabled = false;
    boton.textContent = "Guardar";
  }
}

function iniciales(nombre) {
  return nombre
    .split(" ")
    .filter((palabra) => palabra.length > 2)
    .slice(0, 2)
    .map((palabra) => palabra[0].toUpperCase())
    .join("");
}

function mostrar(el) { el.hidden = false; }
function ocultar(el) { el.hidden = true; }