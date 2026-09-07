# -*- coding: utf-8 -*-
"""Reparto: a que salon va cada bloque de reservas.

Un tablero con una columna por salon mas la de lo que queda por repartir.
Los bloques se ven todos a la vez y se mueven de columna a columna, asi que
devolver algo a su sitio es tan facil como mandarlo: no hay que acertar a la
primera.

No se intenta escribir en reglas lo que cambia cada ano. Las reglas resuelven
lo que siempre es igual y lo demas se decide aqui. Lo unico automatico es lo
mecanico: en que mesa concreta se sienta cada uno dentro de su salon.
"""
import tkinter as tk
from tkinter import messagebox

import customtkinter as ctk

from utils.theme import T
from core import motor

ORO = "#C9A84C"
ROJO = "#d9534f"
VERDE = "#25A873"

ANCHO_PENDIENTES = 330
ANCHO_COLUMNA = 250
CABECERA = 74
TARJETA = 58
FILA_RESERVA = 22
HUECO = 6
UMBRAL_GRUPO = 8      # a partir de aqui una reserva se trata como un bloque


def corto(texto, n):
    texto = (texto or "").strip()
    return texto if len(texto) <= n else texto[:n - 1] + "…"


class VistaReparto:

    def __init__(self, padre, con, evento_id, app):
        self.con = con
        self.evento_id = evento_id
        self.app = app
        self.columnas = []        # [{clave, titulo, bloques, plazas, ocup}]
        # La seleccion es de RESERVAS, no de bloques: asi se puede mover
        # un bloque entero o solo algunas de las reservas que lo forman.
        self.seleccion = set()
        self.desplegados = set()  # (columna, titulo del bloque)
        self.hover = None
        self.hover_columna = None
        self._cajas = []          # (x1, y1, x2, y2, columna, indice)
        self._cajas_reserva = []  # (x1, y1, x2, y2, columna, reserva)
        self._plegables = []      # (x1, y1, x2, y2, columna, indice)
        self._cabeceras = []      # (x1, y1, x2, y2, columna)

        self.frame = ctk.CTkFrame(padre, fg_color=T("bg_content"),
                                  corner_radius=0)
        self._construir()
        self.al_mostrar()

    # ── Estructura ────────────────────────────────────────────────

    def _construir(self):
        cab = ctk.CTkFrame(self.frame, fg_color=T("bg_header"),
                           corner_radius=0, height=64)
        cab.pack(fill="x")
        cab.pack_propagate(False)
        ctk.CTkLabel(cab, text="Reparto",
                     font=ctk.CTkFont(family="Segoe UI", size=17,
                                      weight="bold"),
                     text_color=T("text_primary")).pack(side="left", padx=20)
        self.subtitulo = ctk.CTkLabel(
            cab, text="", font=ctk.CTkFont(family="Segoe UI", size=11),
            text_color=T("text_dim"))
        self.subtitulo.pack(side="left")

        self.boton_sentar = ctk.CTkButton(
            cab, text="Asignar mesas", width=130, height=30, corner_radius=6,
            command=self._asignar)
        self.boton_sentar.pack(side="right", padx=(0, 20))

        pie = tk.Frame(self.frame, bg=T("bg_kpi"), height=44)
        pie.pack(fill="x", side="bottom")
        pie.pack_propagate(False)
        self.resumen = tk.Label(pie, text="", bg=T("bg_kpi"),
                                fg=T("text_secondary"),
                                font=("Segoe UI", 10), anchor="w")
        self.resumen.pack(side="left", padx=20)
        ctk.CTkButton(
            pie, text="Quitar seleccion", width=130, height=26,
            corner_radius=6, fg_color="transparent", border_width=1,
            border_color=T("border_card"), text_color=T("text_secondary"),
            command=self._limpiar).pack(side="right", padx=20, pady=9)

        marco = tk.Frame(self.frame, bg=T("bg_content"))
        marco.pack(fill="both", expand=True, padx=12, pady=(10, 0))
        self.lienzo = tk.Canvas(marco, bg=T("bg_content"),
                                highlightthickness=0)
        vbar = tk.Scrollbar(marco, orient="vertical",
                            command=self.lienzo.yview)
        vbar.pack(side="right", fill="y")
        hbar = tk.Scrollbar(marco, orient="horizontal",
                            command=self.lienzo.xview)
        hbar.pack(side="bottom", fill="x")
        self.lienzo.configure(yscrollcommand=vbar.set, xscrollcommand=hbar.set)
        self.lienzo.pack(side="left", fill="both", expand=True)

        self.lienzo.bind("<Button-1>", self._pulsar)
        self.lienzo.bind("<Motion>", self._mover_raton)
        self.lienzo.bind("<Leave>", lambda e: self._quitar_hover())
        self.lienzo.bind("<MouseWheel>",
                         lambda e: self.lienzo.yview_scroll(-e.delta // 120,
                                                            "units"))
        self.lienzo.bind("<Shift-MouseWheel>",
                         lambda e: self.lienzo.xview_scroll(-e.delta // 120,
                                                            "units"))
        self.lienzo.bind("<Configure>", lambda e: self._pintar())

    # ── Datos ─────────────────────────────────────────────────────

    def al_mostrar(self):
        self._cargar()
        self._pintar()
        self._pintar_resumen()

    def _bloques_de(self, reservas, regla_de=None):
        """Agrupa reservas en bloques: cada grupo suelto, el resto por codigo.

        Se agrupa por CODIGO y no por nombre porque en la venta directa el
        listado trae el nombre del cliente en la casilla de la agencia, y por
        nombre cada reserva salia como un bloque aparte.
        """
        regla_de = regla_de or {}
        grupos, sueltas = [], {}
        for r in reservas:
            pax = r["adultos"] + r["ninos"]
            if pax >= UMBRAL_GRUPO:
                grupos.append({
                    "titulo": r["cliente"] or r["agencia"] or "Sin nombre",
                    "detalle": "%s · rsv %s"
                               % (corto(r["agencia"] or "sin agencia", 20),
                                  r["num_reserva"] or "externa"),
                    "grupo": True, "pax": pax, "adultos": r["adultos"],
                    "ninos": r["ninos"], "reservas": [r["id"]],
                    "detalle_reservas": [r],
                    "regla": regla_de.get(r["id"], False)})
                continue
            b = sueltas.setdefault(r["cod_agencia"], {
                "titulo": "", "nombres": set(), "grupo": False, "pax": 0,
                "adultos": 0, "ninos": 0, "reservas": [], "n": 0,
                "cod": r["cod_agencia"], "detalle_reservas": [],
                "regla": regla_de.get(r["id"], False)})
            b["pax"] += pax
            b["adultos"] += r["adultos"]
            b["ninos"] += r["ninos"]
            b["reservas"].append(r["id"])
            b["detalle_reservas"].append(r)
            b["nombres"].add((r["agencia"] or "").strip())
            b["n"] += 1

        for b in sueltas.values():
            nombres = {n for n in b["nombres"] if n}
            b["titulo"] = (nombres.pop() if len(nombres) == 1
                           else "Codigo %s" % (b["cod"] or "sin codigo"))
            b["detalle"] = "%d reservas sueltas" % b["n"]
        return sorted(grupos + list(sueltas.values()),
                      key=lambda b: (not b["grupo"], -b["pax"]))

    def _cargar(self):
        segmentos, destinos, excluidos = motor.cargar_reglas(self.con,
                                                             self.evento_id)
        salones = list(self.con.execute(
            "SELECT * FROM salon WHERE evento_id = ? ORDER BY orden",
            (self.evento_id,)))
        nombres = {s["id"]: s["nombre"] for s in salones}

        por_sitio, pendientes, regla_de = {}, [], {}
        for r in self.con.execute(
            "SELECT * FROM reserva WHERE evento_id = ?"
            " ORDER BY agencia, cliente", (self.evento_id,)
        ):
            seg = motor.segmento_de(r, segmentos)
            if seg in excluidos:
                continue
            if r["salon_id"]:
                por_sitio.setdefault(
                    (r["salon_id"], r["zona_destino"] or ""), []).append(r)
            elif seg is not None and destinos.get(seg):
                salon_id, zona = destinos[seg][0]
                por_sitio.setdefault((salon_id, zona), []).append(r)
                regla_de[r["id"]] = True
            else:
                pendientes.append(r)

        self.columnas = [{
            "clave": None, "titulo": "POR REPARTIR",
            "subtitulo": "esperando tu orden",
            "bloques": self._bloques_de(pendientes),
            "plazas": None, "ocup": 0,
        }]
        for s in salones:
            for z in self.con.execute(
                "SELECT DISTINCT zona FROM mesa WHERE salon_id = ?"
                " ORDER BY zona = '' DESC, zona", (s["id"],)
            ):
                clave = (s["id"], z["zona"])
                reservas = por_sitio.get(clave, [])
                plazas = self.con.execute(
                    "SELECT COALESCE(SUM(capacidad), 0) FROM mesa"
                    " WHERE salon_id = ? AND zona = ?", clave).fetchone()[0]
                self.columnas.append({
                    "clave": clave,
                    "titulo": z["zona"] or nombres[s["id"]],
                    "subtitulo": nombres[s["id"]] if z["zona"] else "",
                    "bloques": self._bloques_de(reservas, regla_de),
                    "plazas": plazas,
                    "ocup": sum(r["adultos"] + r["ninos"] for r in reservas),
                })

        vivas = {r["id"] for c in self.columnas
                 for b in c["bloques"] for r in b["detalle_reservas"]}
        self.seleccion &= vivas
        pend = sum(b["pax"] for b in self.columnas[0]["bloques"])
        self.subtitulo.configure(
            text="   %d comensales por repartir   ·   elige bloques y pincha"
                 " la cabecera del salon donde van" % pend)

    # ── Dibujo ────────────────────────────────────────────────────

    def _x_columna(self, indice):
        if indice == 0:
            return 0, ANCHO_PENDIENTES
        x = ANCHO_PENDIENTES + 16 + (indice - 1) * (ANCHO_COLUMNA + 10)
        return x, x + ANCHO_COLUMNA

    def _pax_seleccionado(self):
        total = 0
        for columna in self.columnas:
            for b in columna["bloques"]:
                for r in b["detalle_reservas"]:
                    if r["id"] in self.seleccion:
                        total += r["adultos"] + r["ninos"]
        return total

    def _pintar(self):
        c = self.lienzo
        c.delete("all")
        self._cajas, self._cabeceras = [], []
        self._cajas_reserva, self._plegables = [], []
        pax_sel = self._pax_seleccionado()

        for indice, columna in enumerate(self.columnas):
            x1, x2 = self._x_columna(indice)
            self._cabecera_columna(indice, columna, x1, x2, pax_sel)
            y = CABECERA + 10
            for i, b in enumerate(columna["bloques"]):
                self._tarjeta(indice, i, b, x1, x2, y)
                y += TARJETA
                if (indice, b["titulo"]) in self.desplegados:
                    y = self._desplegar(indice, b, x1, x2, y)
                y += HUECO
            if not columna["bloques"]:
                c.create_text((x1 + x2) / 2, CABECERA + 34, text="vacio",
                              fill=T("text_disabled"), font=("Segoe UI", 9))
        c.configure(scrollregion=c.bbox("all"))

    def _cabecera_columna(self, indice, columna, x1, x2, pax_sel):
        c = self.lienzo
        es_destino = pax_sel > 0
        libres = None
        if columna["plazas"] is not None:
            libres = columna["plazas"] - columna["ocup"]
        cabe = libres is None or pax_sel <= libres
        encima = self.hover_columna == indice
        et = "col:%d" % indice

        borde = T("border")
        if es_destino:
            borde = VERDE if cabe else ROJO
        fondo = T("bg_surface") if encima and es_destino else T("bg_card")

        c.create_rectangle(x1, 0, x2, CABECERA, fill=fondo, outline=borde,
                           width=2 if es_destino else 1, tags=et)
        c.create_text(x1 + 12, 18, anchor="w", text=columna["titulo"],
                      fill=T("text_primary"), font=("Segoe UI", 11, "bold"),
                      tags=et)

        if columna["plazas"] is None:
            c.create_text(x2 - 12, 18, anchor="e",
                          text="%d pax" % sum(b["pax"]
                                              for b in columna["bloques"]),
                          fill=T("text_secondary"),
                          font=("Segoe UI", 10, "bold"), tags=et)
            c.create_text(x1 + 12, 42, anchor="w",
                          text="devuelve aqui lo que quieras replantear"
                          if es_destino else columna["subtitulo"],
                          fill=VERDE if es_destino else T("text_dim"),
                          font=("Segoe UI", 8), tags=et)
        else:
            c.create_text(x2 - 12, 18, anchor="e",
                          text="%d/%d" % (columna["ocup"], columna["plazas"]),
                          fill=ORO if columna["ocup"] else T("text_dim"),
                          font=("Segoe UI", 10, "bold"), tags=et)
            ancho = x2 - x1 - 24
            c.create_rectangle(x1 + 12, 34, x2 - 12, 40, fill=T("bg_surface"),
                               outline="", tags=et)
            if columna["plazas"]:
                usado = ancho * min(1.0, columna["ocup"] / columna["plazas"])
                c.create_rectangle(x1 + 12, 34, x1 + 12 + usado, 40, fill=ORO,
                                   outline="", tags=et)
                if es_destino and cabe:
                    hasta = ancho * min(
                        1.0, (columna["ocup"] + pax_sel) / columna["plazas"])
                    c.create_rectangle(x1 + 12 + usado, 34, x1 + 12 + hasta,
                                       40, fill=VERDE, outline="", tags=et)
            texto = "quedan %d plazas" % libres
            color = T("text_dim")
            if es_destino:
                texto = ("caben los %d" % pax_sel) if cabe else \
                    ("faltan %d plazas" % (pax_sel - libres))
                color = VERDE if cabe else ROJO
            c.create_text(x1 + 12, 56, anchor="w", text=texto, fill=color,
                          font=("Segoe UI", 9,
                                "bold" if es_destino else "normal"), tags=et)

        self._cabeceras.append((x1, 0, x2, CABECERA, indice))

    def _tarjeta(self, columna, i, b, x1, x2, y):
        c = self.lienzo
        marcadas = sum(1 for r in b["detalle_reservas"]
                       if r["id"] in self.seleccion)
        elegido = marcadas > 0 and marcadas == len(b["reservas"])
        parcial = 0 < marcadas < len(b["reservas"])
        encima = self.hover == (columna, i)
        fondo = T("active_bg") if elegido or parcial else (
            T("bg_surface") if encima else T("bg_card"))
        borde = ORO if elegido else (T("active_border") if parcial else (
            T("border_card") if encima else T("border")))
        et = "t:%d:%d" % (columna, i)
        abierto = (columna, b["titulo"]) in self.desplegados

        c.create_rectangle(x1 + 4, y, x2 - 4, y + TARJETA, fill=fondo,
                           outline=borde,
                           width=2 if elegido or parcial else 1, tags=et)
        c.create_rectangle(x1 + 4, y, x1 + 8, y + TARJETA,
                           fill=ORO if b["grupo"] else T("border_card"),
                           outline="", tags=et)
        # Triangulo para abrir el bloque y ver que reservas lo forman.
        c.create_text(x1 + 18, y + 16, text="▾" if abierto else "▸",
                      fill=T("text_secondary"), font=("Segoe UI", 9))
        self._plegables.append((x1 + 8, y, x1 + 28, y + TARJETA,
                                columna, i))
        c.create_text(x1 + 32, y + 16, anchor="w",
                      text=corto(b["titulo"], 29 if columna == 0 else 18),
                      fill=T("text_primary"), font=("Segoe UI", 10, "bold"),
                      tags=et)
        c.create_text(x2 - 12, y + 16, anchor="e", text=str(b["pax"]),
                      fill=T("text_primary"), font=("Segoe UI", 14, "bold"),
                      tags=et)
        detalle = b["detalle"]
        if b.get("regla"):
            detalle += "  · por regla"
        if parcial:
            detalle = "%d de %d reservas marcadas" % (marcadas,
                                                     len(b["reservas"]))
        c.create_text(x1 + 32, y + 38, anchor="w",
                      text=corto(detalle, 33 if columna == 0 else 21),
                      fill=T("text_dim"), font=("Segoe UI", 8), tags=et)
        if b["ninos"]:
            c.create_text(x2 - 12, y + 38, anchor="e",
                          text="%d niños" % b["ninos"], fill=ORO,
                          font=("Segoe UI", 8, "bold"), tags=et)
        self._cajas.append((x1 + 4, y, x2 - 4, y + TARJETA, columna, i))

    def _desplegar(self, columna, b, x1, x2, y):
        """Las reservas del bloque, una a una y marcables por separado."""
        c = self.lienzo
        for r in sorted(b["detalle_reservas"],
                        key=lambda x: -(x["adultos"] + x["ninos"])):
            marcada = r["id"] in self.seleccion
            c.create_rectangle(x1 + 14, y, x2 - 4, y + FILA_RESERVA,
                               fill=T("bg_row_sel") if marcada
                               else T("bg_row_impar"), outline="")
            c.create_text(x1 + 24, y + 11, anchor="w",
                          text="■" if marcada else "□",
                          fill=ORO if marcada else T("text_dim"),
                          font=("Segoe UI", 8))
            c.create_text(x1 + 38, y + 11, anchor="w",
                          text=r["num_reserva"] or "EXT",
                          fill=T("text_dim"), font=("Consolas", 8))
            c.create_text(x1 + 86, y + 11, anchor="w",
                          text=corto(r["cliente"],
                                     24 if columna == 0 else 12),
                          fill=T("text_primary"), font=("Segoe UI", 8))
            pax = "%d" % r["adultos"]
            if r["ninos"]:
                pax += "+%dN" % r["ninos"]
            c.create_text(x2 - 12, y + 11, anchor="e", text=pax,
                          fill=ORO if r["ninos"] else T("text_secondary"),
                          font=("Segoe UI", 8))
            self._cajas_reserva.append((x1 + 14, y, x2 - 4,
                                        y + FILA_RESERVA, columna,
                                        r["id"]))
            y += FILA_RESERVA
        return y

    # ── Interaccion ───────────────────────────────────────────────

    def _donde(self, evento):
        x = self.lienzo.canvasx(evento.x)
        y = self.lienzo.canvasy(evento.y)
        for x1, y1, x2, y2, col, i in self._plegables:
            if x1 <= x <= x2 and y1 <= y <= y2:
                return ("plegar", col, i)
        for x1, y1, x2, y2, col, rid in self._cajas_reserva:
            if x1 <= x <= x2 and y1 <= y <= y2:
                return ("reserva", col, rid)
        for x1, y1, x2, y2, col, i in self._cajas:
            if x1 <= x <= x2 and y1 <= y <= y2:
                return ("tarjeta", col, i)
        for x1, y1, x2, y2, col in self._cabeceras:
            if x1 <= x <= x2 and y1 <= y <= y2:
                return ("columna", col, None)
        return (None, None, None)

    def _pulsar(self, evento):
        que, col, i = self._donde(evento)
        if que == "plegar":
            clave = (col, self.columnas[col]["bloques"][i]["titulo"])
            self.desplegados.symmetric_difference_update({clave})
            self._pintar()
        elif que == "reserva":
            self.seleccion.symmetric_difference_update({i})
            self._pintar()
            self._pintar_resumen()
        elif que == "tarjeta":
            # Pinchar el bloque marca o desmarca todas sus reservas.
            ids = set(self.columnas[col]["bloques"][i]["reservas"])
            if ids <= self.seleccion:
                self.seleccion -= ids
            else:
                self.seleccion |= ids
            self._pintar()
            self._pintar_resumen()
        elif que == "columna" and self.seleccion:
            self._mandar(self.columnas[col])

    def _mover_raton(self, evento):
        que, col, i = self._donde(evento)
        tarjeta = (col, i) if que in ("tarjeta", "plegar") else None
        columna = col if que == "columna" else None
        if tarjeta != self.hover or columna != self.hover_columna:
            self.hover, self.hover_columna = tarjeta, columna
            self.lienzo.configure(cursor="hand2" if que else "")
            self._pintar()

    def _quitar_hover(self):
        if self.hover or self.hover_columna is not None:
            self.hover, self.hover_columna = None, None
            self._pintar()

    def _limpiar(self):
        self.seleccion.clear()
        self._pintar()
        self._pintar_resumen()

    # ── Mover ─────────────────────────────────────────────────────

    def _mandar(self, columna):
        ids = list(self.seleccion)
        pax = self._pax_seleccionado()
        if not ids:
            return

        if columna["plazas"] is not None:
            libres = columna["plazas"] - columna["ocup"]
            if pax > libres and not messagebox.askyesno(
                "No caben todos",
                "Mandas %d comensales a %s, donde quedan %d plazas.\n\n"
                "Los que sobren se quedaran sin mesa hasta que hagas sitio."
                "\n\n¿Seguimos?" % (pax, columna["titulo"], libres),
                    parent=self.frame):
                return

        salon_id, zona = columna["clave"] if columna["clave"] else (None, "")
        with self.con:
            self.con.executemany(
                "UPDATE reserva SET salon_id = ?, zona_destino = ?"
                " WHERE id = ?", [(salon_id, zona, r) for r in ids])
            # Cambiar de salon deja sin efecto la mesa que tuvieran: se les
            # da otra al pulsar «Asignar mesas».
            self.con.executemany(
                "DELETE FROM asignacion WHERE reserva_id = ?",
                [(r,) for r in ids])
        self.seleccion.clear()
        self.al_mostrar()

    def _asignar(self):
        res = motor.asignar(self.con, self.evento_id)
        texto = "%d reservas sentadas en su mesa." % res["asignadas"]
        if res["pax_sin_sitio"]:
            texto += ("\n\n%d comensales no caben en el salon que les has"
                      " dado." % res["pax_sin_sitio"])
        messagebox.showinfo("Mesas asignadas", texto, parent=self.frame)
        self.al_mostrar()

    def _pintar_resumen(self):
        if not self.seleccion:
            self.resumen.configure(
                text="Pincha los bloques que quieras mover y luego la"
                     " cabecera de la columna a donde van."
                     "   Para revertir algo, mandalo a POR REPARTIR.")
            return
        pax = self._pax_seleccionado()
        ninos = sum(r["ninos"] for c in self.columnas
                    for b in c["bloques"] for r in b["detalle_reservas"]
                    if r["id"] in self.seleccion)
        texto = "%d reservas · %d comensales" % (len(self.seleccion),
                                                 pax)
        if ninos:
            texto += " (%d niños)" % ninos
        self.resumen.configure(text=texto + "   →   pincha la columna destino")
