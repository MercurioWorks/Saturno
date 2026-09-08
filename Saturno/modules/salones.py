# -*- coding: utf-8 -*-
"""Salones: donde va cada mesa dentro del salon.

Aqui se monta el salon tal y como queda en la realidad: se arrastra cada
mesa a su sitio y se guarda su posicion. Se puede poner de fondo una imagen
del plano del salon para colocarlas encima.

Las mesas que todavia no se han colocado esperan en una rejilla arriba, y se
van bajando al plano.
"""
import math
import os
import tkinter as tk
from tkinter import filedialog, messagebox

import customtkinter as ctk

from utils.theme import T

ORO = "#C9A84C"
ORO_TENUE = "#8a7333"
RADIO = 42


class VistaSalones:

    def __init__(self, padre, con, evento_id, app):
        self.con = con
        self.evento_id = evento_id
        self.app = app
        self.salon_activo = None
        self.imagen = None            # hay que guardarla o la borra el GC
        self._arrastre = None
        self._posiciones = {}         # mesa_id -> (x, y) mientras se arrastra

        self.frame = ctk.CTkFrame(padre, fg_color=T("bg_content"),
                                  corner_radius=0)
        self._construir()
        self.al_mostrar()

    def _construir(self):
        cab = ctk.CTkFrame(self.frame, fg_color=T("bg_header"),
                           corner_radius=0, height=64)
        cab.pack(fill="x")
        cab.pack_propagate(False)
        ctk.CTkLabel(cab, text="Salones",
                     font=ctk.CTkFont(family="Segoe UI", size=17,
                                      weight="bold"),
                     text_color=T("text_primary")).pack(side="left", padx=20)
        ctk.CTkLabel(cab, text="Arrastra cada mesa a su sitio en el salon",
                     font=ctk.CTkFont(family="Segoe UI", size=11),
                     text_color=T("text_dim")).pack(side="left")

        for texto, orden in (("Quitar plano", self._quitar_plano),
                             ("Poner plano de fondo", self._poner_plano),
                             ("Colocar en rejilla", self._auto_rejilla)):
            ctk.CTkButton(cab, text=texto, command=orden, width=150,
                          height=30, corner_radius=6).pack(side="right",
                                                           padx=(0, 12))

        self.cinta = ctk.CTkFrame(self.frame, fg_color=T("bg_kpi"),
                                  corner_radius=0, height=52)
        self.cinta.pack(fill="x")
        self.cinta.pack_propagate(False)

        marco = tk.Frame(self.frame, bg=T("bg_content"))
        marco.pack(fill="both", expand=True, padx=12, pady=12)
        self.lienzo = tk.Canvas(marco, bg=T("bg_surface"),
                                highlightthickness=1,
                                highlightbackground=T("border"))
        self.lienzo.pack(fill="both", expand=True)
        self.lienzo.bind("<Button-1>", self._pulsar)
        self.lienzo.bind("<B1-Motion>", self._arrastrar)
        self.lienzo.bind("<ButtonRelease-1>", self._soltar)

        self.pie = tk.Label(self.frame, text="", bg=T("bg_content"),
                            fg=T("text_dim"), font=("Segoe UI", 9),
                            anchor="w")
        self.pie.pack(fill="x", padx=16, pady=(0, 8))

    # ── Datos ─────────────────────────────────────────────────────

    def al_mostrar(self):
        self.salones = list(self.con.execute(
            "SELECT * FROM salon WHERE evento_id = ? AND gestionado = 1"
            " ORDER BY orden",
            (self.evento_id,)))
        # Cada zona se coloca por separado: la Naya esta en otra planta que
        # el resto del Palacio, asi que tiene su propio plano.
        self.superficies = []
        for salon in self.salones:
            for z in self.con.execute(
                "SELECT DISTINCT zona FROM mesa WHERE salon_id = ?"
                " ORDER BY zona = '' DESC, zona", (salon["id"],)
            ):
                self.superficies.append((salon, z["zona"]))
        if self.salon_activo is None and self.superficies:
            salon, zona = self.superficies[0]
            self.salon_activo = (salon["id"], zona)
        self._pintar_cinta()
        self._pintar()

    def _salon(self):
        return self.con.execute("SELECT * FROM salon WHERE id = ?",
                                (self.salon_activo[0],)).fetchone()

    def _pintar_cinta(self):
        for w in self.cinta.winfo_children():
            w.destroy()
        for salon, zona in self.superficies:
            clave = (salon["id"], zona)
            activo = clave == self.salon_activo
            fondo = T("active_bg") if activo else T("bg_kpi")
            caja = tk.Frame(self.cinta, bg=fondo, cursor="hand2",
                            highlightthickness=1,
                            highlightbackground=T("active_border") if activo
                            else T("border"))
            caja.pack(side="left", fill="y", padx=(12, 0), pady=8)
            etiqueta = tk.Label(caja, text=zona if zona else salon["nombre"],
                                bg=fondo,
                                fg=T("text_primary") if activo
                                else T("text_secondary"),
                                font=("Segoe UI", 11, "bold"))
            etiqueta.pack(padx=14, pady=4)
            for w in (caja, etiqueta):
                w.bind("<Button-1>", lambda e, c=clave: self._elegir(c))

    def _elegir(self, clave):
        self.salon_activo = clave
        self._pintar_cinta()
        self._pintar()

    # ── Dibujo ────────────────────────────────────────────────────

    def _pintar(self):
        c = self.lienzo
        c.delete("all")
        if not self.salon_activo:
            return
        salon = self._salon()

        self.imagen = None
        if salon["plano_imagen"] and os.path.exists(salon["plano_imagen"]):
            try:
                from PIL import Image, ImageTk
                img = Image.open(salon["plano_imagen"])
                ancho = c.winfo_width() or 1200
                alto = c.winfo_height() or 700
                img.thumbnail((ancho, alto))
                self.imagen = ImageTk.PhotoImage(img)
                c.create_image(0, 0, anchor="nw", image=self.imagen)
            except Exception as err:
                self.pie.configure(text="No se ha podido abrir el plano: %s"
                                        % err)

        mesas = list(self.con.execute(
            "SELECT * FROM mesa WHERE salon_id = ? AND zona = ?"
            " ORDER BY numero", self.salon_activo))
        sin_colocar = [m for m in mesas if m["pos_x"] is None]

        for mesa in mesas:
            if mesa["pos_x"] is None:
                continue
            self._dibujar_mesa(mesa, mesa["pos_x"], mesa["pos_y"])

        # Las que aun no tienen sitio esperan arriba, en fila.
        for i, mesa in enumerate(sin_colocar):
            self._dibujar_mesa(mesa, 60 + i * 46, 40, pendiente=True)

        self.pie.configure(
            text="%d mesas · %d colocadas · %d por colocar."
                 "   Arrastra una mesa para moverla."
                 % (len(mesas), len(mesas) - len(sin_colocar),
                    len(sin_colocar)))
        c.configure(scrollregion=c.bbox("all"))

    def _dibujar_mesa(self, mesa, x, y, pendiente=False):
        c = self.lienzo
        etiqueta = "mesa:%d" % mesa["id"]
        radio = 18 if pendiente else RADIO

        if not pendiente:
            # Una silla por plaza montada, como en el salon.
            for s in range(mesa["capacidad_montaje"] or mesa["capacidad"]):
                ang = 2 * math.pi * s / (mesa["capacidad_montaje"]
                                         or mesa["capacidad"]) - math.pi / 2
                sx = x + (radio + 13) * math.cos(ang)
                sy = y + (radio + 13) * math.sin(ang)
                c.create_oval(sx - 5, sy - 5, sx + 5, sy + 5, fill=ORO_TENUE,
                              outline="", tags=etiqueta)

        c.create_oval(x - radio, y - radio, x + radio, y + radio,
                      fill=T("bg_card"),
                      outline=T("border_card") if pendiente else ORO,
                      width=2, tags=etiqueta)
        c.create_text(x, y - (6 if not pendiente else 0),
                      text=str(mesa["numero"]), fill=T("text_primary"),
                      font=("Segoe UI", 14 if not pendiente else 9, "bold"),
                      tags=etiqueta)
        if not pendiente:
            c.create_text(x, y + 14,
                          text=str(mesa["capacidad_montaje"]
                                   or mesa["capacidad"]),
                          fill=T("text_dim"), font=("Segoe UI", 9),
                          tags=etiqueta)

    # ── Arrastrar mesas ───────────────────────────────────────────

    def _mesa_bajo(self, evento):
        x, y = self.lienzo.canvasx(evento.x), self.lienzo.canvasy(evento.y)
        for item in reversed(self.lienzo.find_overlapping(x - 1, y - 1,
                                                          x + 1, y + 1)):
            for etiqueta in self.lienzo.gettags(item):
                if etiqueta.startswith("mesa:"):
                    return int(etiqueta.split(":")[1])
        return None

    def _pulsar(self, evento):
        mesa_id = self._mesa_bajo(evento)
        if mesa_id is None:
            return
        self._arrastre = mesa_id

    def _arrastrar(self, evento):
        if self._arrastre is None:
            return
        x, y = self.lienzo.canvasx(evento.x), self.lienzo.canvasy(evento.y)
        self.lienzo.delete("fantasma")
        self.lienzo.create_oval(x - RADIO, y - RADIO, x + RADIO, y + RADIO,
                                outline=ORO, width=2, dash=(4, 3),
                                tags="fantasma")

    def _soltar(self, evento):
        mesa_id, self._arrastre = self._arrastre, None
        self.lienzo.delete("fantasma")
        if mesa_id is None:
            return
        x, y = self.lienzo.canvasx(evento.x), self.lienzo.canvasy(evento.y)
        with self.con:
            self.con.execute("UPDATE mesa SET pos_x = ?, pos_y = ?"
                             " WHERE id = ?", (x, y, mesa_id))
        self._pintar()

    # ── Acciones ──────────────────────────────────────────────────

    def _auto_rejilla(self):
        """Coloca todas las mesas en una rejilla, como punto de partida."""
        if not messagebox.askyesno(
            "Colocar en rejilla",
            "Se van a recolocar TODAS las mesas de este salon en una"
            " rejilla, perdiendo la disposicion actual.\n\n¿Seguimos?",
                parent=self.frame):
            return
        ancho = self.lienzo.winfo_width() or 1200
        por_fila = max(1, (ancho - 120) // 130)
        with self.con:
            for i, mesa in enumerate(self.con.execute(
                "SELECT id FROM mesa WHERE salon_id = ? AND zona = ?"
                " ORDER BY numero", self.salon_activo).fetchall()):
                x = 90 + (i % por_fila) * 130
                y = 110 + (i // por_fila) * 130
                self.con.execute("UPDATE mesa SET pos_x = ?, pos_y = ?"
                                 " WHERE id = ?", (x, y, mesa["id"]))
        self._pintar()

    def _poner_plano(self):
        ruta = filedialog.askopenfilename(
            title="Plano del salon",
            filetypes=[("Imagenes", "*.png *.jpg *.jpeg *.gif"),
                       ("Todos", "*.*")], parent=self.frame)
        if not ruta:
            return
        with self.con:
            self.con.execute("UPDATE salon SET plano_imagen = ? WHERE id = ?",
                             (ruta, self.salon_activo[0]))
        self._pintar()

    def _quitar_plano(self):
        with self.con:
            self.con.execute("UPDATE salon SET plano_imagen = '' WHERE id = ?",
                             (self.salon_activo[0],))
        self._pintar()
