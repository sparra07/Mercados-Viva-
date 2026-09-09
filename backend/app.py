"""
Mercado VIVA - MVP de Consulta y Actualización de Inventario
--------------------------------------------------------------
BACKEND (Python + Flask)

Este archivo vive en /backend y sirve las vistas que están en /frontend
(templates y static), además de exponer la API REST que consume el
JavaScript del frontend.

Responsabilidades del backend:
  - Exponer la API REST (/api/...)
  - Aplicar las reglas de negocio (ej. calcular el estado del stock)
  - Validar los datos que llegan del frontend
  - Leer y escribir en la base de datos SQLite
"""

from flask import Flask, jsonify, request, render_template, g
import sqlite3
import os
from datetime import datetime

BASE_DIR = os.path.dirname(os.path.abspath(__file__))          # .../backend
FRONTEND_DIR = os.path.join(BASE_DIR, "..", "frontend")        # .../frontend
DB_PATH = os.path.join(BASE_DIR, "inventario.db")              # la BD vive en backend

app = Flask(
    __name__,
    template_folder=os.path.join(FRONTEND_DIR, "templates"),
    static_folder=os.path.join(FRONTEND_DIR, "static"),
)

# ---------------------------------------------------------------------------
# Conexión a la base de datos
# ---------------------------------------------------------------------------

def get_db():
    if "db" not in g:
        g.db = sqlite3.connect(DB_PATH)
        g.db.row_factory = sqlite3.Row
    return g.db


@app.teardown_appcontext
def close_db(exception=None):
    db = g.pop("db", None)
    if db is not None:
        db.close()


def init_db():
    """Crea la tabla de productos y la siembra con datos de ejemplo
    si la base de datos todavía no existe."""
    nueva = not os.path.exists(DB_PATH)
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS productos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nombre TEXT NOT NULL,
            categoria TEXT NOT NULL,
            precio INTEGER NOT NULL,
            cantidad INTEGER NOT NULL DEFAULT 0,
            stock_minimo INTEGER NOT NULL DEFAULT 5,
            tienda TEXT NOT NULL,
            unidad TEXT NOT NULL DEFAULT 'un',
            actualizado_en TEXT NOT NULL
        )
        """
    )

    if nueva:
        ahora = datetime.now().strftime("%Y-%m-%d %H:%M")
        productos_iniciales = [
            ("Banano criollo x kg", "Frutas y Verduras", 3200, 42, 10, "Mercado VIVA Laureles", "kg"),
            ("Aguacate hass x kg", "Frutas y Verduras", 8900, 6, 10, "Mercado VIVA Laureles", "kg"),
            ("Tomate chonto x kg", "Frutas y Verduras", 4100, 0, 8, "Mercado VIVA Envigado", "kg"),
            ("Leche entera x 1L", "Lácteos y Huevos", 4650, 120, 30, "Mercado VIVA Laureles", "un"),
            ("Huevos AA x 30 unidades", "Lácteos y Huevos", 17900, 18, 15, "Mercado VIVA Envigado", "un"),
            ("Queso campesino x 500g", "Lácteos y Huevos", 12500, 3, 10, "Mercado VIVA Laureles", "un"),
            ("Arroz premium x 5kg", "Despensa", 24900, 65, 20, "Mercado VIVA Sabaneta", "un"),
            ("Aceite de girasol x 1L", "Despensa", 13200, 9, 15, "Mercado VIVA Sabaneta", "un"),
            ("Panela redonda x 1kg", "Despensa", 5200, 0, 10, "Mercado VIVA Laureles", "un"),
            ("Pechuga de pollo x kg", "Carnes y Pescados", 15900, 22, 12, "Mercado VIVA Envigado", "kg"),
            ("Carne de res molida x kg", "Carnes y Pescados", 21500, 4, 10, "Mercado VIVA Sabaneta", "kg"),
            ("Papel higiénico x 12 rollos", "Aseo del Hogar", 27900, 40, 15, "Mercado VIVA Laureles", "un"),
            ("Detergente líquido x 3L", "Aseo del Hogar", 32900, 11, 10, "Mercado VIVA Envigado", "un"),
            ("Jabón de manos x 250ml", "Cuidado Personal", 8700, 2, 12, "Mercado VIVA Sabaneta", "un"),
            ("Shampoo anticaspa x 400ml", "Cuidado Personal", 19900, 27, 10, "Mercado VIVA Laureles", "un"),
        ]
        cur.executemany(
            """
            INSERT INTO productos (nombre, categoria, precio, cantidad, stock_minimo, tienda, unidad, actualizado_en)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [(*p, ahora) for p in productos_iniciales],
        )
        conn.commit()
    conn.close()


def calcular_estado(cantidad, stock_minimo):
    if cantidad <= 0:
        return "agotado"
    if cantidad < stock_minimo:
        return "stock_bajo"
    return "disponible"


def producto_a_dict(row):
    d = dict(row)
    d["estado"] = calcular_estado(d["cantidad"], d["stock_minimo"])
    return d


# ---------------------------------------------------------------------------
# Ruta que entrega el frontend (index.html)
# ---------------------------------------------------------------------------

@app.route("/")
def index():
    return render_template("index.html")


# ---------------------------------------------------------------------------
# API REST — consumida por frontend/static/js/script.js
# ---------------------------------------------------------------------------

@app.route("/api/categorias", methods=["GET"])
def listar_categorias():
    db = get_db()
    filas = db.execute(
        "SELECT DISTINCT categoria FROM productos ORDER BY categoria"
    ).fetchall()
    categorias = [f["categoria"] for f in filas]
    return jsonify(categorias)


@app.route("/api/productos", methods=["GET"])
def listar_productos():
    """Consulta de inventario con filtros opcionales:
    ?buscar=texto          -> coincidencia por nombre
    ?categoria=nombre      -> filtra por categoría exacta
    ?estado=disponible|stock_bajo|agotado
    """
    buscar = request.args.get("buscar", "").strip()
    categoria = request.args.get("categoria", "").strip()
    estado_filtro = request.args.get("estado", "").strip()

    consulta = "SELECT * FROM productos WHERE 1=1"
    parametros = []

    if buscar:
        consulta += " AND LOWER(nombre) LIKE ?"
        parametros.append(f"%{buscar.lower()}%")

    if categoria:
        consulta += " AND categoria = ?"
        parametros.append(categoria)

    consulta += " ORDER BY nombre"

    db = get_db()
    filas = db.execute(consulta, parametros).fetchall()
    productos = [producto_a_dict(f) for f in filas]

    if estado_filtro:
        productos = [p for p in productos if p["estado"] == estado_filtro]

    return jsonify(productos)


@app.route("/api/productos/<int:producto_id>", methods=["GET"])
def obtener_producto(producto_id):
    db = get_db()
    fila = db.execute(
        "SELECT * FROM productos WHERE id = ?", (producto_id,)
    ).fetchone()
    if fila is None:
        return jsonify({"error": "Producto no encontrado"}), 404
    return jsonify(producto_a_dict(fila))


@app.route("/api/productos/<int:producto_id>", methods=["PUT"])
def actualizar_producto(producto_id):
    """Actualiza la cantidad real en inventario de un producto
    (proceso usado por el encargado de bodega tras un conteo físico)."""
    datos = request.get_json(silent=True)

    if not datos or "cantidad" not in datos:
        return jsonify({"error": "Debes enviar el campo 'cantidad'"}), 400

    cantidad = datos.get("cantidad")

    if not isinstance(cantidad, int) or isinstance(cantidad, bool):
        return jsonify({"error": "La cantidad debe ser un número entero"}), 400

    if cantidad < 0:
        return jsonify({"error": "La cantidad no puede ser negativa"}), 400

    db = get_db()
    fila = db.execute(
        "SELECT * FROM productos WHERE id = ?", (producto_id,)
    ).fetchone()

    if fila is None:
        return jsonify({"error": "Producto no encontrado"}), 404

    ahora = datetime.now().strftime("%Y-%m-%d %H:%M")
    db.execute(
        "UPDATE productos SET cantidad = ?, actualizado_en = ? WHERE id = ?",
        (cantidad, ahora, producto_id),
    )
    db.commit()

    fila_actualizada = db.execute(
        "SELECT * FROM productos WHERE id = ?", (producto_id,)
    ).fetchone()
    return jsonify(producto_a_dict(fila_actualizada))

if __name__ == "__main__":
    init_db()
    app.run(debug=True, host="0.0.0.0", port=5000)