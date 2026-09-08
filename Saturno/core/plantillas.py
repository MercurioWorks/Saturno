# -*- coding: utf-8 -*-
"""Plantillas de configuracion: salones y reparto de agencias en un fichero.

Un evento nuevo nace VACIO. La configuracion de un hotel concreto no vive en
el codigo: se guarda como plantilla en la carpeta 'plantillas' y se carga
cuando hace falta. Asi el programa vale para cualquier hotel, y el de casa
es una plantilla mas que se puede editar, exportar o tirar.
"""
import json
import os

CARPETA = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(
    __file__))), "plantillas")


def carpeta():
    os.makedirs(CARPETA, exist_ok=True)
    return CARPETA


def disponibles():
    """Nombres de las plantillas guardadas."""
    if not os.path.isdir(CARPETA):
        return []
    return sorted(f[:-5] for f in os.listdir(CARPETA) if f.endswith(".json"))


def ruta(nombre):
    return os.path.join(carpeta(), "%s.json" % nombre)


# ── Guardar ───────────────────────────────────────────────────────

def exportar(con, evento_id, nombre):
    """Guarda la configuracion de un evento como plantilla reutilizable."""
    datos = {"salones": [], "segmentos": []}

    for s in con.execute(
        "SELECT * FROM salon WHERE evento_id = ? ORDER BY orden",
        (evento_id,)
    ):
        zonas = []
        for z in con.execute(
            "SELECT zona, COUNT(*) n,"
            " SUM(CASE WHEN capacidad_montaje > ? THEN 1 ELSE 0 END) grandes"
            " FROM mesa WHERE salon_id = ? GROUP BY zona"
            " ORDER BY MIN(numero)", (s["capacidad_base"], s["id"])
        ):
            zonas.append({"nombre": z["zona"],
                          "mesas": z["n"] - (z["grandes"] or 0),
                          "grandes": z["grandes"] or 0})
        datos["salones"].append({
            "nombre": s["nombre"], "orden": s["orden"],
            "capacidad_base": s["capacidad_base"],
            "capacidad_max": s["capacidad_max"],
            "mesas_ampliables": s["mesas_ampliables"],
            "precio_menu": s["precio_menu"],
            "gestionado": bool(s["gestionado"]), "zonas": zonas,
        })

    for seg in con.execute(
        "SELECT * FROM segmento WHERE evento_id = ? ORDER BY orden",
        (evento_id,)
    ):
        destino = con.execute(
            "SELECT s.nombre, p.zona FROM preferencia p"
            " JOIN salon s ON s.id = p.salon_id"
            " WHERE p.segmento_id = ? ORDER BY p.orden",
            (seg["id"],)).fetchone()
        reglas = list(con.execute(
            "SELECT tipo, valor FROM regla WHERE segmento_id = ?",
            (seg["id"],)))
        datos["segmentos"].append({
            "nombre": seg["nombre"], "orden": seg["orden"],
            "excluir": bool(seg["excluir"]),
            "salon": destino["nombre"] if destino else "",
            "zona": destino["zona"] if destino else "",
            "codigos": [r["valor"] for r in reglas if r["tipo"] == "codigo"],
            "patrones": [r["valor"] for r in reglas if r["tipo"] == "nombre"],
            "min_pax": next((int(r["valor"]) for r in reglas
                             if r["tipo"] == "min_pax"), None),
            "por_defecto": any(r["tipo"] == "defecto" for r in reglas),
        })

    with open(ruta(nombre), "w", encoding="utf-8") as f:
        json.dump(datos, f, indent=2, ensure_ascii=False)
    return ruta(nombre)


# ── Cargar ────────────────────────────────────────────────────────

def aplicar(con, evento_id, datos):
    """Vuelca una plantilla sobre un evento, reemplazando su configuracion.

    No toca las reservas: solo salones, mesas y reglas.
    """
    with con:
        con.execute("DELETE FROM salon WHERE evento_id = ?", (evento_id,))
        con.execute("DELETE FROM segmento WHERE evento_id = ?", (evento_id,))

        ids = {}
        for s in datos.get("salones", []):
            zonas = s.get("zonas") or [{"nombre": "", "mesas": 0,
                                        "grandes": 0}]
            total = sum(z["mesas"] + z.get("grandes", 0) for z in zonas)
            cur = con.execute(
                "INSERT INTO salon (evento_id, nombre, orden, capacidad_base,"
                " capacidad_max, mesas_ampliables, precio_menu, gestionado,"
                " num_mesas) VALUES (?,?,?,?,?,?,?,?,?)",
                (evento_id, s["nombre"], s.get("orden", 0),
                 s.get("capacidad_base", 10), s.get("capacidad_max", 12),
                 s.get("mesas_ampliables", 0), s.get("precio_menu", 0),
                 1 if s.get("gestionado", True) else 0, total))
            ids[s["nombre"]] = cur.lastrowid
            numero = 1
            for z in zonas:
                filas = []
                for _ in range(z.get("mesas", 0)):
                    filas.append((cur.lastrowid, z["nombre"], numero,
                                  s.get("capacidad_base", 10),
                                  s.get("capacidad_base", 10)))
                    numero += 1
                for _ in range(z.get("grandes", 0)):
                    filas.append((cur.lastrowid, z["nombre"], numero,
                                  s.get("capacidad_max", 12),
                                  s.get("capacidad_max", 12)))
                    numero += 1
                con.executemany(
                    "INSERT INTO mesa (salon_id, zona, numero,"
                    " capacidad_montaje, capacidad) VALUES (?,?,?,?,?)", filas)

        for seg in datos.get("segmentos", []):
            cur = con.execute(
                "INSERT INTO segmento (evento_id, nombre, orden, excluir)"
                " VALUES (?,?,?,?)",
                (evento_id, seg["nombre"], seg.get("orden", 0),
                 1 if seg.get("excluir") else 0))
            seg_id = cur.lastrowid
            if seg.get("salon") and seg["salon"] in ids:
                con.execute(
                    "INSERT INTO preferencia (segmento_id, salon_id, zona,"
                    " orden) VALUES (?,?,?,0)",
                    (seg_id, ids[seg["salon"]], seg.get("zona", "")))
            filas = [(seg_id, "codigo", c) for c in seg.get("codigos", [])]
            filas += [(seg_id, "nombre", p) for p in seg.get("patrones", [])]
            if seg.get("min_pax"):
                filas.append((seg_id, "min_pax", str(seg["min_pax"])))
            if seg.get("por_defecto"):
                filas.append((seg_id, "defecto", ""))
            con.executemany(
                "INSERT INTO regla (segmento_id, tipo, valor) VALUES (?,?,?)",
                filas)


def importar(con, evento_id, nombre):
    with open(ruta(nombre), encoding="utf-8") as f:
        aplicar(con, evento_id, json.load(f))


def crear_evento(con, nombre, fecha, plantilla=None):
    """Crea un evento. Sin plantilla nace vacio, sin un solo salon."""
    with con:
        cur = con.execute("INSERT INTO evento (nombre, fecha) VALUES (?,?)",
                          (nombre, fecha))
        evento_id = cur.lastrowid
    if plantilla:
        importar(con, evento_id, plantilla)
    return evento_id
