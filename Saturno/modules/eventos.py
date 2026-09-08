# -*- coding: utf-8 -*-
"""Eventos: la comida de Navidad, la gala de Nochevieja, lo que haga falta.

Todo el trabajo vive dentro de un evento: sus salones, sus reservas y su
reparto. Aqui se crean, se elige en cual se esta trabajando y se ve como va
cada uno.

Un evento nuevo nace sin salones. Se puede partir de una plantilla guardada
o copiar el montaje de un evento anterior, que es lo normal: el hotel monta
los mismos salones cada temporada.
"""
import datetime
import tkinter as tk
from tkinter import messagebox

import customtkinter as ctk

from utils.theme import T
from core import plantillas

ORO = "#C9A84C"
VERDE = "#25A873"


class VistaEventos:

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
        ctk.CTkLabel(cab, text="Eventos",
                     font=ctk.CTkFont(family="Segoe UI", size=17,
                                      weight="bold"),
                     text_color=T("text_primary")).pack(side="left", padx=20)
        ctk.CTkLabel(cab, text="cada gala con sus salones, sus reservas y su"
                              " reparto",
                     font=ctk.CTkFont(family="Segoe UI", size=11),
                     text_color=T("text_dim")).pack(side="left")
        ctk.CTkButton(cab, text="Nuevo evento", width=140, height=30,
                      corner_radius=6,
                      command=self._nuevo).pack(side="right", padx=(0, 20))

        self.cuerpo = ctk.CTkScrollableFrame(self.frame,
                                             fg_color=T("bg_content"),
                                             corner_radius=0)
        self.cuerpo.pack(fill="both", expand=True, padx=16, pady=12)

    # ── Datos ─────────────────────────────────────────────────────

    def al_mostrar(self):
        for w in self.cuerpo.winfo_children():
            w.destroy()
        eventos = list(self.con.execute(
            "SELECT * FROM evento ORDER BY fecha DESC, id DESC"))
        if not eventos:
            tk.Label(self.cuerpo, text="Todavia no hay ningun evento.",
                     bg=T("bg_content"), fg=T("text_secondary"),
                     font=("Segoe UI", 11)).pack(anchor="w", pady=20)
            return
        for e in eventos:
            self._tarjeta(e)

    def _cifras(self, evento_id):
        f = self.con.execute(
            "SELECT COUNT(*) reservas, COALESCE(SUM(adultos + ninos), 0) pax"
            " FROM reserva WHERE evento_id = ?", (evento_id,)).fetchone()
        g = self.con.execute(
            "SELECT COUNT(*) salones,"
            " (SELECT COUNT(*) FROM mesa m JOIN salon s2 ON s2.id = m.salon_id"
            "  WHERE s2.evento_id = ?) mesas,"
            " (SELECT COALESCE(SUM(m.capacidad), 0) FROM mesa m"
            "  JOIN salon s3 ON s3.id = m.salon_id WHERE s3.evento_id = ?)"
            "  plazas"
            " FROM salon s WHERE s.evento_id = ?",
            (evento_id, evento_id, evento_id)).fetchone()
        sentados = self.con.execute(
            "SELECT COALESCE(SUM(a.pax), 0) FROM asignacion a"
            " JOIN reserva r ON r.id = a.reserva_id WHERE r.evento_id = ?",
            (evento_id,)).fetchone()[0]
        return f, g, sentados

    # ── Tarjeta de evento ─────────────────────────────────────────

    def _tarjeta(self, e):
        activo = e["id"] == self.evento_id
        f, g, sentados = self._cifras(e["id"])
        fondo = T("active_bg") if activo else T("bg_card")
        borde = T("active_border") if activo else T("border")

        caja = tk.Frame(self.cuerpo, bg=fondo, highlightthickness=2,
                        highlightbackground=borde)
        caja.pack(fill="x", pady=(0, 10))

        arriba = tk.Frame(caja, bg=fondo)
        arriba.pack(fill="x", padx=16, pady=(12, 4))
        tk.Label(arriba, text=e["nombre"], bg=fondo, fg=T("text_primary"),
                 font=("Segoe UI", 14, "bold")).pack(side="left")
        tk.Label(arriba, text="   " + (e["fecha"] or "sin fecha"), bg=fondo,
                 fg=T("text_dim"), font=("Segoe UI", 10)).pack(side="left")
        if activo:
            tk.Label(arriba, text="  ·  EN EL QUE ESTAS TRABAJANDO", bg=fondo,
                     fg=ORO, font=("Segoe UI", 9, "bold")).pack(side="left")

        cifras = tk.Frame(caja, bg=fondo)
        cifras.pack(fill="x", padx=16, pady=(0, 6))
        for etiqueta, valor in (
                ("salones", g["salones"]), ("mesas", g["mesas"]),
                ("plazas", g["plazas"]), ("reservas", f["reservas"]),
                ("comensales", f["pax"]), ("sentados", sentados)):
            bloque = tk.Frame(cifras, bg=fondo)
            bloque.pack(side="left", padx=(0, 26))
            tk.Label(bloque, text=str(valor), bg=fondo,
                     fg=T("text_primary"),
                     font=("Segoe UI", 15, "bold")).pack(anchor="w")
            tk.Label(bloque, text=etiqueta, bg=fondo, fg=T("kpi_label"),
                     font=("Segoe UI", 9)).pack(anchor="w")

        botones = tk.Frame(caja, bg=fondo)
        botones.pack(fill="x", padx=16, pady=(0, 12))
        # Entrar lleva al reparto, que es por donde se empieza a trabajar.
        ctk.CTkButton(botones,
                      text="Entrar" if activo else "Entrar en este evento",
                      width=170, height=30, corner_radius=6,
                      command=lambda i=e["id"]: self._abrir(i)).pack(
                          side="left")
        ctk.CTkButton(botones, text="Renombrar", width=110, height=28,
                      corner_radius=6, fg_color="transparent", border_width=1,
                      border_color=T("border_card"),
                      text_color=T("text_secondary"),
                      command=lambda ev=e: self._renombrar(ev)).pack(
                          side="left", padx=8)
        ctk.CTkButton(botones, text="Borrar evento", width=120, height=28,
                      corner_radius=6, fg_color="#8a2f2c",
                      hover_color="#a33b37",
                      command=lambda ev=e: self._borrar(ev)).pack(side="right")

    # ── Acciones ──────────────────────────────────────────────────

    def _abrir(self, evento_id):
        """Entra en el evento y deja al usuario en el reparto."""
        if evento_id != self.evento_id:
            self.app.cambiar_evento(evento_id)
        self.app.mostrar("reparto")

    def _nuevo(self):
        VentanaNuevoEvento(self.frame, self.con, self.evento_id,
                           self.app.cambiar_evento)

    def _renombrar(self, e):
        VentanaNuevoEvento(self.frame, self.con, self.evento_id,
                           self.app.cambiar_evento, editar=e)

    def _borrar(self, e):
        f, _, _ = self._cifras(e["id"])
        aviso = "Se borra el evento '%s' con sus salones y su reparto." \
            % e["nombre"]
        if f["reservas"]:
            aviso += ("\n\nTiene %d reservas (%d comensales), que tambien se"
                      " van." % (f["reservas"], f["pax"]))
        total = self.con.execute("SELECT COUNT(*) FROM evento").fetchone()[0]
        if total == 1:
            messagebox.showwarning(
                "No se puede borrar",
                "Es el unico evento que hay. Crea otro antes de borrarlo.",
                parent=self.frame)
            return
        if not messagebox.askyesno("Borrar evento", aviso + "\n\n¿Seguro?",
                                   parent=self.frame):
            return
        with self.con:
            self.con.execute("DELETE FROM evento WHERE id = ?", (e["id"],))
        if e["id"] == self.evento_id:
            otro = self.con.execute(
                "SELECT id FROM evento ORDER BY id DESC").fetchone()
            self.app.cambiar_evento(otro["id"])
        else:
            self.al_mostrar()


class VentanaNuevoEvento(ctk.CTkToplevel):
    """Alta de un evento, con el montaje de donde se quiera partir."""

    def __init__(self, padre, con, evento_actual, al_crear, editar=None):
        super().__init__(padre)
        self.con = con
        self.al_crear = al_crear
        self.editar = editar

        self.title("Evento")
        self.geometry("480x420")
        self.configure(fg_color=T("bg_content"))
        self.transient(padre.winfo_toplevel())

        tk.Label(self, text="Nombre del evento", bg=T("bg_content"),
                 fg=T("text_secondary"), font=("Segoe UI", 10),
                 anchor="w").pack(fill="x", padx=24, pady=(20, 2))
        self.nombre = ctk.CTkEntry(self, width=420, height=32)
        self.nombre.pack(padx=24, anchor="w")
        if editar:
            self.nombre.insert(0, editar["nombre"])
        else:
            self.nombre.insert(0, "GALA NOCHEVIEJA %d"
                               % datetime.date.today().year)

        tk.Label(self, text="Fecha", bg=T("bg_content"),
                 fg=T("text_secondary"), font=("Segoe UI", 10),
                 anchor="w").pack(fill="x", padx=24, pady=(14, 2))
        self.fecha = ctk.CTkEntry(self, width=200, height=32,
                                  placeholder_text="31/12/2026")
        self.fecha.pack(padx=24, anchor="w")
        if editar and editar["fecha"]:
            self.fecha.insert(0, editar["fecha"])

        if not editar:
            tk.Label(self, text="Montaje de partida", bg=T("bg_content"),
                     fg=T("text_secondary"), font=("Segoe UI", 10),
                     anchor="w").pack(fill="x", padx=24, pady=(18, 2))
            tk.Label(self,
                     text="Los salones y las reglas con los que empieza. Se"
                          " pueden cambiar despues.",
                     bg=T("bg_content"), fg=T("text_dim"),
                     font=("Segoe UI", 9), anchor="w",
                     justify="left").pack(fill="x", padx=24, pady=(0, 6))

            self.origenes = [("", "Vacio: sin salones, se montan a mano")]
            for e in con.execute(
                "SELECT id, nombre FROM evento ORDER BY id DESC"
            ):
                self.origenes.append(("evento:%d" % e["id"],
                                      "Copiar el montaje de: " + e["nombre"]))
            for nombre in plantillas.disponibles():
                self.origenes.append(("plantilla:" + nombre,
                                      "Plantilla: " + nombre))
            self.origen = ctk.CTkOptionMenu(
                self, width=420, height=32,
                values=[t for _, t in self.origenes])
            self.origen.pack(padx=24, anchor="w")
            if len(self.origenes) > 1:
                self.origen.set(self.origenes[1][1])

        pie = tk.Frame(self, bg=T("bg_content"))
        pie.pack(fill="x", pady=24)
        ctk.CTkButton(pie, text="Guardar" if editar else "Crear y abrir",
                      width=160, height=34,
                      command=self._guardar).pack(padx=24, anchor="w")
        self.after(120, self.grab_set)

    def _guardar(self):
        nombre = self.nombre.get().strip()
        if not nombre:
            messagebox.showwarning("Falta el nombre",
                                   "El evento necesita un nombre.",
                                   parent=self)
            return
        fecha = self.fecha.get().strip()

        if self.editar:
            with self.con:
                self.con.execute(
                    "UPDATE evento SET nombre = ?, fecha = ? WHERE id = ?",
                    (nombre, fecha, self.editar["id"]))
            self.al_crear(self.editar["id"])
            self.destroy()
            return

        elegido = self.origen.get()
        clave = next((c for c, t in self.origenes if t == elegido), "")
        with self.con:
            cur = self.con.execute(
                "INSERT INTO evento (nombre, fecha) VALUES (?,?)",
                (nombre, fecha))
            nuevo = cur.lastrowid

        if clave.startswith("plantilla:"):
            plantillas.importar(self.con, nuevo, clave.split(":", 1)[1])
        elif clave.startswith("evento:"):
            self._copiar_montaje(int(clave.split(":", 1)[1]), nuevo)

        self.al_crear(nuevo)
        self.destroy()

    def _copiar_montaje(self, origen, destino):
        """Copia salones, mesas y reglas de otro evento. Las reservas no:
        cada gala tiene las suyas."""
        datos = plantillas.exportar(self.con, origen, "_temporal")
        import json
        import os
        with open(datos, encoding="utf-8") as f:
            plantillas.aplicar(self.con, destino, json.load(f))
        os.remove(datos)
