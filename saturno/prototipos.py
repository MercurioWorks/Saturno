# -*- coding: utf-8 -*-
"""Tres maneras de dibujar el plano de mesas, para elegir una.

Todo va sobre un Canvas: se dibujan figuras, no widgets. Un Canvas con dos
mil figuras se pinta y se desplaza sin despeinarse, que es justo lo que le
faltaba a la primera version.

    python prototipos.py a     mapa de sala (mesas redondas con sillas)
    python prototipos.py b     fichas de mesa (rejilla ordenada)
    python prototipos.py c     tira de plazas (una casilla por comensal)
"""
import os
import sys
import tkinter as tk

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import db                                                    # noqa: E402
from utils.theme import T                                    # noqa: E402

ORO = "#C9A84C"
ORO_TENUE = "#8a7333"


def datos(con, nombre_salon="PALACIO%", zona=""):
    salon = con.execute(
        "SELECT * FROM salon WHERE nombre LIKE ?", (nombre_salon,)).fetchone()
    mesas = list(con.execute(
        "SELECT * FROM mesa WHERE salon_id = ? AND zona = ? ORDER BY numero",
        (salon["id"], zona)))
    ocupantes = {}
    for f in con.execute(
        "SELECT a.mesa_id, a.pax, a.fijada, r.cliente, r.agencia"
        " FROM asignacion a JOIN reserva r ON r.id = a.reserva_id"
        " JOIN mesa m ON m.id = a.mesa_id"
        " WHERE m.salon_id = ? AND m.zona = ? ORDER BY a.id",
        (salon["id"], zona)
    ):
        ocupantes.setdefault(f["mesa_id"], []).append(f)
    return salon, mesas, ocupantes


def corto(texto, n):
    texto = (texto or "").strip()
    return texto if len(texto) <= n else texto[:n - 1] + "…"


class Prototipo(tk.Tk):

    def __init__(self, variante):
        super().__init__()
        self.variante = variante
        self.title("Saturno · prototipo %s" % variante.upper())
        self.geometry("1600x900")
        self.configure(bg=T("bg_content"))

        con = db.conectar()
        self.salon, self.mesas, self.ocupantes = datos(con)

        titulos = {"a": "Mapa de sala", "b": "Fichas de mesa",
                   "c": "Tira de plazas"}
        pies = {
            "a": "Las mesas como se montan en el salon. Las sillas ocupadas"
                 " se ven doradas; se pincha una mesa y se abre su detalle.",
            "b": "Una ficha por mesa, todas del mismo tamano, con quien esta"
                 " sentado y una barra de ocupacion.",
            "c": "Una casilla por plaza. De un vistazo se ve donde quedan"
                 " huecos en todo el salon.",
        }

        cab = tk.Frame(self, bg=T("bg_header"), height=64)
        cab.pack(fill="x")
        cab.pack_propagate(False)
        tk.Label(cab, text=titulos[variante], bg=T("bg_header"),
                 fg=T("text_primary"),
                 font=("Segoe UI", 16, "bold")).pack(side="left", padx=20)
        tk.Label(cab, text=pies[variante], bg=T("bg_header"),
                 fg=T("text_dim"), font=("Segoe UI", 10)).pack(side="left")

        contenedor = tk.Frame(self, bg=T("bg_content"))
        contenedor.pack(fill="both", expand=True)
        self.lienzo = tk.Canvas(contenedor, bg=T("bg_content"),
                                highlightthickness=0)
        barra = tk.Scrollbar(contenedor, orient="vertical",
                             command=self.lienzo.yview)
        self.lienzo.configure(yscrollcommand=barra.set)
        barra.pack(side="right", fill="y")
        self.lienzo.pack(side="left", fill="both", expand=True)
        self.lienzo.bind_all(
            "<MouseWheel>",
            lambda e: self.lienzo.yview_scroll(-e.delta // 120, "units"))

        getattr(self, "_dibujar_" + variante)()
        self.lienzo.configure(scrollregion=self.lienzo.bbox("all"))

    # ── A. Mapa de sala ───────────────────────────────────────────

    def _dibujar_a(self):
        c = self.lienzo
        radio, paso_x, paso_y = 52, 190, 190
        por_fila = 8
        for i, mesa in enumerate(self.mesas):
            gente = self.ocupantes.get(mesa["id"], [])
            ocup = sum(g["pax"] for g in gente)
            cx = 110 + (i % por_fila) * paso_x
            cy = 100 + (i // por_fila) * paso_y

            # Sillas alrededor: una por plaza montada.
            import math
            for s in range(mesa["capacidad"]):
                ang = 2 * math.pi * s / mesa["capacidad"] - math.pi / 2
                sx = cx + (radio + 16) * math.cos(ang)
                sy = cy + (radio + 16) * math.sin(ang)
                lleno = s < ocup
                c.create_oval(sx - 7, sy - 7, sx + 7, sy + 7,
                              fill=ORO if lleno else T("bg_surface"),
                              outline=ORO_TENUE if lleno else T("border"))

            lleno = ocup >= mesa["capacidad"]
            c.create_oval(cx - radio, cy - radio, cx + radio, cy + radio,
                          fill=T("bg_card"),
                          outline=ORO if lleno else T("border_card"), width=2)
            c.create_text(cx, cy - 12, text=str(mesa["numero"]),
                          fill=T("text_primary"),
                          font=("Segoe UI", 20, "bold"))
            c.create_text(cx, cy + 14,
                          text="%d/%d" % (ocup, mesa["capacidad"]),
                          fill=ORO if lleno else T("text_dim"),
                          font=("Segoe UI", 10))
            if any(g["fijada"] for g in gente):
                c.create_text(cx + radio - 12, cy - radio + 12, text="🔒",
                              font=("Segoe UI", 11))

    # ── B. Fichas de mesa ─────────────────────────────────────────

    def _dibujar_b(self):
        c = self.lienzo
        ancho, alto, hueco = 250, 172, 14
        por_fila = 6
        for i, mesa in enumerate(self.mesas):
            gente = self.ocupantes.get(mesa["id"], [])
            ocup = sum(g["pax"] for g in gente)
            lleno = ocup >= mesa["capacidad"]
            x = 20 + (i % por_fila) * (ancho + hueco)
            y = 20 + (i // por_fila) * (alto + hueco)

            c.create_rectangle(x, y, x + ancho, y + alto, fill=T("bg_card"),
                               outline=ORO if lleno else T("border_card"),
                               width=1)
            c.create_rectangle(x, y, x + ancho, y + 30,
                               fill=T("table_head_bg"), outline="")
            c.create_text(x + 12, y + 15, anchor="w",
                          text="MESA %d" % mesa["numero"],
                          fill=T("text_primary"),
                          font=("Segoe UI", 11, "bold"))
            c.create_text(x + ancho - 12, y + 15, anchor="e",
                          text="%d/%d" % (ocup, mesa["capacidad"]),
                          fill=ORO if lleno else T("text_dim"),
                          font=("Segoe UI", 10, "bold"))

            # Barra de ocupacion: se ve el llenado sin leer numeros.
            ratio = min(1.0, ocup / max(1, mesa["capacidad"]))
            c.create_rectangle(x, y + 30, x + ancho, y + 33,
                               fill=T("bg_surface"), outline="")
            if ratio:
                c.create_rectangle(x, y + 30, x + ancho * ratio, y + 33,
                                   fill=ORO, outline="")

            fila = y + 45
            for g in gente[:6]:
                if g["fijada"]:
                    c.create_text(x + 10, fila, anchor="w", text="🔒",
                                  font=("Segoe UI", 8))
                c.create_text(x + (22 if g["fijada"] else 12), fila, anchor="w",
                              text=corto(g["cliente"], 24),
                              fill=T("text_primary"), font=("Segoe UI", 9))
                c.create_text(x + ancho - 12, fila, anchor="e",
                              text=str(g["pax"]), fill=T("text_dim"),
                              font=("Segoe UI", 9))
                fila += 19
            if len(gente) > 6:
                c.create_text(x + 12, fila, anchor="w",
                              text="+%d mas" % (len(gente) - 6),
                              fill=T("text_dim"), font=("Segoe UI", 8))

    # ── C. Tira de plazas ─────────────────────────────────────────

    def _dibujar_c(self):
        c = self.lienzo
        lado, hueco, alto_fila = 26, 3, 40
        colores = ["#C9A84C", "#4A9EEF", "#25A873", "#c07ad4", "#e0a458",
                   "#7fd18a", "#E8A030", "#5B9CF6"]
        for i, mesa in enumerate(self.mesas):
            gente = self.ocupantes.get(mesa["id"], [])
            y = 20 + i * alto_fila
            c.create_text(20, y + lado / 2, anchor="w",
                          text="MESA %-3d" % mesa["numero"],
                          fill=T("text_secondary"),
                          font=("Consolas", 10, "bold"))

            x = 110
            plaza = 0
            for j, g in enumerate(gente):
                color = colores[j % len(colores)]
                for _ in range(g["pax"]):
                    if plaza >= mesa["capacidad"]:
                        break
                    c.create_rectangle(x, y, x + lado, y + lado, fill=color,
                                       outline=T("bg_content"), width=1)
                    plaza += 1
                    x += lado + hueco
                # Nombre al lado del bloque de esa reserva.
            for _ in range(mesa["capacidad"] - plaza):
                c.create_rectangle(x, y, x + lado, y + lado,
                                   fill=T("bg_surface"),
                                   outline=T("border"), width=1)
                x += lado + hueco

            nombres = "   ".join("%s (%d)" % (corto(g["cliente"], 18),
                                              g["pax"]) for g in gente)
            c.create_text(x + 16, y + lado / 2, anchor="w",
                          text=nombres or "libre",
                          fill=T("text_dim") if not gente else T("text_primary"),
                          font=("Segoe UI", 9))


if __name__ == "__main__":
    variante = (sys.argv[1] if len(sys.argv) > 1 else "b").lower()
    Prototipo(variante).mainloop()
