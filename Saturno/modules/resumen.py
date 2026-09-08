# -*- coding: utf-8 -*-
"""Resumen del evento: el panel de totales de la hoja de siempre.

Mismas columnas y mismas cuentas que se llevaban en el Excel:

    MESAS   cuantas de la capacidad normal y cuantas grandes
    T1 T2   las plazas que suma cada clase de mesa
    PLAZAS  el total montado
    AD N    los comensales sentados, adultos y ninos
    TOT     la suma
    REST    las plazas montadas que se quedan sin cubrir

Los segmentos que no se gestionan aqui (el Imserso, por ejemplo) se cuentan
aparte, igual que estaban en la hoja.
"""
import tkinter as tk

import customtkinter as ctk

from utils.theme import T
from core import motor

ORO = "#C9A84C"
ROJO = "#d9534f"


class VistaResumen:

    COLUMNAS = (("", 22, "w"), ("MESAS", 7, "e"), ("de 12", 7, "e"),
                ("T1", 8, "e"), ("T2", 6, "e"), ("PLAZAS", 9, "e"),
                ("AD", 7, "e"), ("N", 5, "e"), ("TOT", 7, "e"),
                ("REST", 7, "e"))

    def __init__(self, padre, con, evento_id, app):
        self.con = con
        self.evento_id = evento_id
        self.app = app
        self.frame = ctk.CTkFrame(padre, fg_color=T("bg_content"),
                                  corner_radius=0)
        self._construir()
        self.al_mostrar()

    def _construir(self):
        cab = ctk.CTkFrame(self.frame, fg_color=T("bg_header"),
                           corner_radius=0, height=64)
        cab.pack(fill="x")
        cab.pack_propagate(False)
        self.titulo = ctk.CTkLabel(
            cab, text="Resumen",
            font=ctk.CTkFont(family="Segoe UI", size=17, weight="bold"),
            text_color=T("text_primary"))
        self.titulo.pack(side="left", padx=20)
        ctk.CTkButton(cab, text="Exportar a Excel", width=140, height=30,
                      corner_radius=6,
                      command=self._exportar).pack(side="right", padx=(0, 20))

        self.cuerpo = ctk.CTkScrollableFrame(self.frame,
                                             fg_color=T("bg_content"),
                                             corner_radius=0)
        self.cuerpo.pack(fill="both", expand=True, padx=20, pady=14)

    # ── Datos ─────────────────────────────────────────────────────

    def al_mostrar(self):
        for w in self.cuerpo.winfo_children():
            w.destroy()
        evento = self.con.execute("SELECT * FROM evento WHERE id = ?",
                                  (self.evento_id,)).fetchone()
        self.titulo.configure(text="Resumen  ·  %s" % (evento["nombre"]
                                                       if evento else ""))
        filas = self._filas()
        if not filas:
            tk.Label(self.cuerpo, text="Este evento no tiene salones todavia.",
                     bg=T("bg_content"), fg=T("text_secondary"),
                     font=("Segoe UI", 11)).pack(anchor="w", pady=20)
            return

        self._tabla("SALONES", filas)
        self._totales(filas)

        otros = self._filas(gestionados=False)
        if otros:
            tk.Frame(self.cuerpo, height=24,
                     bg=T("bg_content")).pack(fill="x")
            self._tabla("SALONES QUE NO SE REPARTEN AQUI", otros)
            plazas = sum(f["plazas"] for f in otros)
            ad = sum(f["ad"] for f in otros)
            ni = sum(f["ni"] for f in otros)
            tk.Frame(self.cuerpo, height=8, bg=T("bg_content")).pack(fill="x")
            self._linea("TOTAL PLAZAS", plazas, True)
            self._linea("TOTAL PLAZAS DISPONIBLES", plazas - ad - ni, True,
                        ORO if plazas - ad - ni else None)
            self._linea("TOTAL PAX", ad + ni, True)

        self._total_hotel(filas, otros)
        self._aparte()

    def _filas(self, gestionados=True):
        """Una fila por zona de salon, con las cuentas de la hoja."""
        filas = []
        for s in self.con.execute(
            "SELECT * FROM salon WHERE evento_id = ? AND gestionado = ?"
            " ORDER BY orden", (self.evento_id, 1 if gestionados else 0)
        ):
            for z in self.con.execute(
                "SELECT zona FROM mesa WHERE salon_id = ? GROUP BY zona"
                " ORDER BY MIN(numero)", (s["id"],)
            ):
                mesas = list(self.con.execute(
                    "SELECT * FROM mesa WHERE salon_id = ? AND zona = ?",
                    (s["id"], z["zona"])))
                normales = [m for m in mesas
                            if m["capacidad_montaje"] <= s["capacidad_base"]]
                grandes = [m for m in mesas
                           if m["capacidad_montaje"] > s["capacidad_base"]]
                t1 = sum(m["capacidad_montaje"] for m in normales)
                t2 = sum(m["capacidad_montaje"] for m in grandes)

                ad = ni = 0
                if s["gestionado"]:
                    for m in mesas:
                        for o in self.con.execute(
                            "SELECT a.pax, r.adultos FROM asignacion a"
                            " JOIN reserva r ON r.id = a.reserva_id"
                            " WHERE a.mesa_id = ?", (m["id"],)
                        ):
                            adultos = min(o["pax"], o["adultos"])
                            ad += adultos
                            ni += o["pax"] - adultos
                else:
                    # Aqui no se sientan mesas: se cuenta la gente que va a
                    # ese salon, que es lo que interesa para el total.
                    ad, ni = self._pax_de_salon(s["id"])
                filas.append({
                    "nombre": z["zona"] or s["nombre"],
                    "mesas": len(normales), "grandes": len(grandes),
                    "t1": t1, "t2": t2, "plazas": t1 + t2,
                    "ad": ad, "ni": ni, "tot": ad + ni,
                    "rest": t1 + t2 - ad - ni,
                })
        return filas

    def _pax_de_salon(self, salon_id):
        """Adultos y ninos que van a un salon que no se reparte aqui."""
        segmentos, destinos, _ = motor.cargar_reglas(self.con, self.evento_id)
        ad = ni = 0
        for r in self.con.execute("SELECT * FROM reserva WHERE evento_id = ?",
                                  (self.evento_id,)):
            destino = r["salon_id"]
            if destino is None and not r["apartada"]:
                seg = motor.segmento_de(r, segmentos)
                sitios = destinos.get(seg)
                destino = sitios[0][0] if sitios else None
            if destino == salon_id:
                ad += r["adultos"]
                ni += r["ninos"]
        return ad, ni

    # ── Dibujo ────────────────────────────────────────────────────

    def _tabla(self, titulo, filas):
        tk.Label(self.cuerpo, text=titulo, bg=T("bg_content"),
                 fg=T("text_primary"), font=("Segoe UI", 12, "bold"),
                 anchor="w").pack(fill="x", pady=(6, 6))

        cab = tk.Frame(self.cuerpo, bg=T("table_head_bg"))
        cab.pack(fill="x")
        for texto, ancho, lado in self.COLUMNAS:
            tk.Label(cab, text=texto, bg=T("table_head_bg"),
                     fg=T("table_head_fg"), font=("Segoe UI", 9, "bold"),
                     width=ancho, anchor=lado).pack(side="left", padx=2)

        for i, f in enumerate(filas):
            fondo = T("bg_row_par") if i % 2 else T("bg_row_impar")
            fila = tk.Frame(self.cuerpo, bg=fondo)
            fila.pack(fill="x")
            valores = (f["nombre"], f["mesas"], f["grandes"] or "",
                       f["t1"], f["t2"] or "", f["plazas"], f["ad"],
                       f["ni"] or "", f["tot"], f["rest"])
            for (texto, ancho, lado), valor in zip(self.COLUMNAS, valores):
                color = T("text_primary")
                if texto == "REST" and valor:
                    color = ROJO if isinstance(valor, int) and valor < 0 \
                        else T("text_dim")
                if texto == "N" and valor:
                    color = ORO
                tk.Label(fila, text=valor, bg=fondo, fg=color,
                         font=("Segoe UI", 10), width=ancho,
                         anchor=lado).pack(side="left", padx=2)

    def _linea(self, etiqueta, valor, destacado=False, color=None):
        fila = tk.Frame(self.cuerpo, bg=T("bg_content"))
        fila.pack(fill="x", pady=1)
        tk.Label(fila, text=etiqueta, bg=T("bg_surface"),
                 fg=T("text_secondary"),
                 font=("Segoe UI", 10, "bold" if destacado else "normal"),
                 width=34, anchor="e").pack(side="left", padx=(0, 6), ipady=3)
        tk.Label(fila, text=valor, bg=T("bg_card"),
                 fg=color or T("text_primary"),
                 font=("Segoe UI", 11, "bold" if destacado else "normal"),
                 width=20, anchor="center").pack(side="left", ipady=3)

    def _totales(self, filas):
        plazas = sum(f["plazas"] for f in filas)
        ad = sum(f["ad"] for f in filas)
        ni = sum(f["ni"] for f in filas)
        tk.Frame(self.cuerpo, height=10,
                 bg=T("bg_content")).pack(fill="x")
        self._linea("TOTAL PLAZAS SALONES", plazas, True)
        self._linea("TOTAL PLAZAS DISPONIBLES", plazas - ad - ni, True,
                    ORO if plazas - ad - ni else None)
        tk.Frame(self.cuerpo, height=8, bg=T("bg_content")).pack(fill="x")
        self._linea("TOTAL ADULTOS Y NIÑOS", "%d  +  %d" % (ad, ni))
        self._linea("TOTAL PAX", ad + ni, True)

    def _total_hotel(self, filas, otros):
        """Lo que en la hoja era el TOTAL GENERAL: todo el hotel junto."""
        todas = filas + otros
        plazas = sum(f["plazas"] for f in todas)
        ad = sum(f["ad"] for f in todas)
        ni = sum(f["ni"] for f in todas)

        tk.Frame(self.cuerpo, height=26, bg=T("bg_content")).pack(fill="x")
        tk.Label(self.cuerpo, text="TOTAL GENERAL", bg=T("bg_content"),
                 fg=T("text_primary"), font=("Segoe UI", 12, "bold"),
                 anchor="w").pack(fill="x", pady=(0, 6))
        self._linea("TOTAL PLAZAS HOTEL", plazas, True)
        self._linea("TOTAL PLAZAS DISPONIBLES", plazas - ad - ni, True,
                    ORO if plazas - ad - ni else None)
        tk.Frame(self.cuerpo, height=8, bg=T("bg_content")).pack(fill="x")
        self._linea("TOTAL ADULTOS Y NIÑOS", "%d  +  %d" % (ad, ni))
        self._linea("TOTAL PAX", ad + ni, True)

    def _aparte(self):
        """Lo que no se sienta aqui, contado por separado como en la hoja."""
        segmentos, destinos, excluidos = motor.cargar_reglas(self.con,
                                                             self.evento_id)
        if not excluidos:
            return
        nombres = {f["id"]: f["nombre"] for f in self.con.execute(
            "SELECT id, nombre FROM segmento WHERE evento_id = ?",
            (self.evento_id,))}
        por_segmento = {}
        for r in self.con.execute(
            "SELECT * FROM reserva WHERE evento_id = ?", (self.evento_id,)
        ):
            seg = motor.segmento_de(r, segmentos)
            if seg in excluidos:
                d = por_segmento.setdefault(seg, [0, 0])
                d[0] += r["adultos"]
                d[1] += r["ninos"]
        if not por_segmento:
            return

        tk.Frame(self.cuerpo, height=22, bg=T("bg_content")).pack(fill="x")
        tk.Label(self.cuerpo, text="FUERA DE ESTOS SALONES",
                 bg=T("bg_content"), fg=T("text_primary"),
                 font=("Segoe UI", 12, "bold"), anchor="w").pack(fill="x")
        tk.Label(self.cuerpo,
                 text="segmentos que no se sientan aqui y se llevan aparte",
                 bg=T("bg_content"), fg=T("text_dim"),
                 font=("Segoe UI", 9), anchor="w").pack(fill="x", pady=(0, 6))
        total = 0
        for seg, (ad, ni) in por_segmento.items():
            self._linea(nombres.get(seg, "?"),
                        "%d AD  +  %d N  =  %d" % (ad, ni, ad + ni))
            total += ad + ni

        tk.Frame(self.cuerpo, height=16, bg=T("bg_content")).pack(fill="x")
        tk.Label(self.cuerpo, text="TOTAL GENERAL", bg=T("bg_content"),
                 fg=T("text_primary"), font=("Segoe UI", 12, "bold"),
                 anchor="w").pack(fill="x", pady=(0, 6))
        f = self.con.execute(
            "SELECT COALESCE(SUM(adultos), 0) ad, COALESCE(SUM(ninos), 0) ni"
            " FROM reserva WHERE evento_id = ?", (self.evento_id,)).fetchone()
        self._linea("TOTAL ADULTOS Y NIÑOS", "%d  +  %d" % (f["ad"], f["ni"]))
        self._linea("TOTAL PAX DEL EVENTO", f["ad"] + f["ni"], True)

    def _exportar(self):
        from tkinter import filedialog, messagebox
        ruta = filedialog.asksaveasfilename(
            title="Guardar el plano", defaultextension=".xlsx",
            filetypes=[("Excel", "*.xlsx")], parent=self.frame)
        if not ruta:
            return
        from core import exportar
        exportar.exportar(self.con, self.evento_id, ruta)
        messagebox.showinfo("Exportado", ruta, parent=self.frame)
