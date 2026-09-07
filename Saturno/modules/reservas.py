# -*- coding: utf-8 -*-
"""Listado de reservas del evento, con buscador y alta manual.

El alta manual es para las reservas externas: gente no alojada que compra la
gala y que por eso no viene en el listado del sistema.
"""
import tkinter as tk
from tkinter import messagebox

import customtkinter as ctk

from utils.theme import T


class VistaReservas:

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
        ctk.CTkLabel(cab, text="Reservas",
                     font=ctk.CTkFont(family="Segoe UI", size=17,
                                      weight="bold"),
                     text_color=T("text_primary")).pack(side="left", padx=20)
        ctk.CTkButton(cab, text="Nueva reserva externa", width=170, height=30,
                      corner_radius=6,
                      command=self._nueva).pack(side="right", padx=(0, 12))

        self.buscador = ctk.CTkEntry(cab, width=260, height=30,
                                     placeholder_text="Buscar por nombre,"
                                                      " agencia o reserva")
        self.buscador.pack(side="right", padx=(0, 12))
        self.buscador.bind("<KeyRelease>", lambda e: self._pintar())

        self.resumen = ctk.CTkLabel(
            self.frame, text="", font=ctk.CTkFont(family="Segoe UI", size=11),
            text_color=T("text_dim"))
        self.resumen.pack(anchor="w", padx=20, pady=(10, 4))

        # El listado se dibuja en un Canvas: con 439 reservas por 7 columnas
        # salen 3.000 etiquetas, y creandolas una a una la pantalla tardaba
        # varios segundos en abrirse.
        marco = tk.Frame(self.frame, bg=T("bg_content"))
        marco.pack(fill="both", expand=True, padx=12, pady=(0, 12))
        self.lienzo = tk.Canvas(marco, bg=T("bg_content"),
                                highlightthickness=0)
        barra = tk.Scrollbar(marco, orient="vertical",
                             command=self.lienzo.yview)
        self.lienzo.configure(yscrollcommand=barra.set)
        barra.pack(side="right", fill="y")
        self.lienzo.pack(side="left", fill="both", expand=True)
        self.lienzo.bind(
            "<MouseWheel>",
            lambda e: self.lienzo.yview_scroll(-e.delta // 120, "units"))

    def al_mostrar(self):
        self._pintar()

    COLUMNAS = (("RESERVA", 14, 90), ("AGENCIA", 26, 210),
                ("CLIENTE", 34, 270), ("AD", 3, 40), ("N", 3, 40),
                ("SALON", 22, 190), ("MESA", 8, 70))

    def _pintar(self):
        c = self.lienzo
        c.delete("all")
        patron = "%" + self.buscador.get().strip() + "%"
        filas = list(self.con.execute(
            "SELECT r.*, s.nombre salon, m.numero mesa, m.zona, a.fijada"
            " FROM reserva r"
            " LEFT JOIN asignacion a ON a.reserva_id = r.id"
            " LEFT JOIN mesa m ON m.id = a.mesa_id"
            " LEFT JOIN salon s ON s.id = m.salon_id"
            " WHERE r.evento_id = ? AND (r.cliente LIKE ? OR r.agencia LIKE ?"
            "       OR r.num_reserva LIKE ?)"
            " ORDER BY r.cliente", (self.evento_id, patron, patron, patron)))
        pax = sum(f["adultos"] + f["ninos"] for f in filas)
        self.resumen.configure(text="%d lineas · %d comensales"
                                    % (len(filas), pax))

        ancho = sum(col[2] for col in self.COLUMNAS) + 20
        c.create_rectangle(0, 0, ancho, 26, fill=T("table_head_bg"),
                           outline="")
        x = 10
        for titulo, _, w in self.COLUMNAS:
            c.create_text(x, 13, anchor="w", text=titulo,
                          fill=T("table_head_fg"),
                          font=("Segoe UI", 9, "bold"))
            x += w

        for i, f in enumerate(filas):
            y = 26 + i * 22
            if i % 2:
                c.create_rectangle(0, y, ancho, y + 22, fill=T("bg_row_par"),
                                   outline="")
            sitio = f["salon"] or "sin asignar"
            if f["zona"]:
                sitio = f["zona"]
            valores = (f["num_reserva"] or ("EXTERNO" if f["externa"] else ""),
                       f["agencia"], f["cliente"], str(f["adultos"]),
                       str(f["ninos"] or ""), sitio,
                       ("%s%s" % (f["mesa"], " 🔒" if f["fijada"] else ""))
                       if f["mesa"] else "")
            x = 10
            for valor, (_, largo, w) in zip(valores, self.COLUMNAS):
                texto = valor if len(valor) <= largo else valor[:largo - 1] + "…"
                c.create_text(x, y + 11, anchor="w", text=texto,
                              fill=T("text_primary") if f["salon"]
                              else T("text_dim"),
                              font=("Segoe UI", 9))
                x += w
        c.configure(scrollregion=c.bbox("all"))

    def _nueva(self):
        VentanaReservaExterna(self.frame, self.con, self.evento_id,
                              self.al_mostrar)


class VentanaReservaExterna(ctk.CTkToplevel):
    """Alta de una reserva que no viene en el listado del sistema."""

    def __init__(self, padre, con, evento_id, al_guardar):
        super().__init__(padre)
        self.con = con
        self.evento_id = evento_id
        self.al_guardar = al_guardar

        self.title("Nueva reserva externa")
        self.geometry("420x300")
        self.configure(fg_color=T("bg_content"))
        self.transient(padre.winfo_toplevel())

        self.campos = {}
        for clave, texto in (("cliente", "Nombre y apellidos"),
                             ("agencia", "Agencia o procedencia"),
                             ("adultos", "Adultos"),
                             ("ninos", "Ninos")):
            ctk.CTkLabel(self, text=texto, text_color=T("text_secondary"),
                         font=ctk.CTkFont(family="Segoe UI", size=11)
                         ).pack(anchor="w", padx=24, pady=(10, 2))
            campo = ctk.CTkEntry(self, width=360, height=30)
            campo.pack(padx=24)
            self.campos[clave] = campo
        self.campos["adultos"].insert(0, "2")
        self.campos["ninos"].insert(0, "0")

        ctk.CTkButton(self, text="Guardar", height=32, width=140,
                      command=self._guardar).pack(pady=18)
        self.after(120, self.grab_set)

    def _guardar(self):
        cliente = self.campos["cliente"].get().strip()
        if not cliente:
            messagebox.showwarning("Falta el nombre",
                                   "Escribe el nombre del cliente.",
                                   parent=self)
            return
        try:
            adultos = int(self.campos["adultos"].get() or 0)
            ninos = int(self.campos["ninos"].get() or 0)
        except ValueError:
            messagebox.showwarning("Numero no valido",
                                   "Adultos y ninos tienen que ser numeros.",
                                   parent=self)
            return
        if adultos + ninos <= 0:
            messagebox.showwarning("Sin comensales",
                                   "La reserva no tiene a nadie.", parent=self)
            return
        with self.con:
            self.con.execute(
                "INSERT INTO reserva (evento_id, agencia, cliente, adultos,"
                " ninos, externa) VALUES (?,?,?,?,?,1)",
                (self.evento_id, self.campos["agencia"].get().strip(),
                 cliente, adultos, ninos))
        self.al_guardar()
        self.destroy()
