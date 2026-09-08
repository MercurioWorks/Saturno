# -*- coding: utf-8 -*-
"""Listado de reservas del evento: buscar, dar de alta, editar y borrar.

Todo es editable. Las reservas llegan del listado del sistema, pero luego se
corrigen a mano: un nombre mal escrito, uno que se cae, dos que se apuntan
mas, o una reserva externa de alguien que no se aloja y no viene en ningun
listado.

Desde aqui tambien se cambia de salon, sin pasar por Reparto.
"""
import tkinter as tk
from tkinter import messagebox

import customtkinter as ctk

from utils.theme import T

ORO = "#C9A84C"
FILA = 22


class VistaReservas:

    COLUMNAS = (("RESERVA", 14, 90), ("AGENCIA", 26, 210),
                ("CLIENTE", 34, 270), ("AD", 3, 40), ("N", 3, 40),
                ("SALON", 24, 200), ("MESA", 8, 70))

    def __init__(self, padre, con, evento_id, app):
        self.con = con
        self.evento_id = evento_id
        self.app = app
        self.filas = []
        self.elegida = None
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
        ctk.CTkLabel(cab, text="doble clic para editar cualquiera",
                     font=ctk.CTkFont(family="Segoe UI", size=10),
                     text_color=T("text_dim")).pack(side="left")

        ctk.CTkButton(cab, text="Nueva reserva", width=130, height=30,
                      corner_radius=6,
                      command=self._nueva).pack(side="right", padx=(0, 12))
        self.boton_borrar = ctk.CTkButton(
            cab, text="Borrar", width=90, height=30, corner_radius=6,
            fg_color="#8a2f2c", hover_color="#a33b37",
            command=self._borrar, state="disabled")
        self.boton_borrar.pack(side="right", padx=(0, 12))
        self.boton_editar = ctk.CTkButton(
            cab, text="Editar", width=90, height=30, corner_radius=6,
            fg_color="transparent", border_width=1,
            border_color=T("border_card"), text_color=T("text_secondary"),
            command=self._editar, state="disabled")
        self.boton_editar.pack(side="right", padx=(0, 8))

        self.buscador = ctk.CTkEntry(cab, width=230, height=30,
                                     placeholder_text="Buscar por nombre,"
                                                      " agencia o reserva")
        self.buscador.pack(side="right", padx=(0, 12))
        self.buscador.bind("<KeyRelease>", lambda e: self._pintar())

        self.resumen = ctk.CTkLabel(
            self.frame, text="", font=ctk.CTkFont(family="Segoe UI", size=11),
            text_color=T("text_dim"))
        self.resumen.pack(anchor="w", padx=20, pady=(10, 4))

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
        self.lienzo.bind("<Button-1>", self._pulsar)
        self.lienzo.bind("<Double-Button-1>", lambda e: self._editar())

    def al_mostrar(self):
        self._pintar()

    # ── Listado ───────────────────────────────────────────────────

    def _pintar(self):
        c = self.lienzo
        c.delete("all")
        patron = "%" + self.buscador.get().strip() + "%"
        # Una linea por reserva. Con el enlace a las mesas sin agrupar, una
        # reserva repartida en tres mesas salia tres veces y sus comensales
        # se contaban tres veces en el resumen de abajo.
        self.filas = list(self.con.execute(
            "SELECT r.*, s.nombre salon, m.zona, sd.nombre salon_destino,"
            "       GROUP_CONCAT(m.numero) mesas,"
            "       MAX(a.fijada) fijada"
            " FROM reserva r"
            " LEFT JOIN asignacion a ON a.reserva_id = r.id"
            " LEFT JOIN mesa m ON m.id = a.mesa_id"
            " LEFT JOIN salon s ON s.id = m.salon_id"
            " LEFT JOIN salon sd ON sd.id = r.salon_id"
            " WHERE r.evento_id = ? AND (r.cliente LIKE ? OR r.agencia LIKE ?"
            "       OR r.num_reserva LIKE ?)"
            " GROUP BY r.id ORDER BY r.cliente",
            (self.evento_id, patron, patron, patron)))
        pax = sum(f["adultos"] + f["ninos"] for f in self.filas)
        self.resumen.configure(text="%d lineas · %d comensales"
                                    % (len(self.filas), pax))

        ancho = sum(col[2] for col in self.COLUMNAS) + 20
        c.create_rectangle(0, 0, ancho, 26, fill=T("table_head_bg"),
                           outline="")
        x = 10
        for titulo, _, w in self.COLUMNAS:
            c.create_text(x, 13, anchor="w", text=titulo,
                          fill=T("table_head_fg"),
                          font=("Segoe UI", 9, "bold"))
            x += w

        for i, f in enumerate(self.filas):
            y = 26 + i * FILA
            if self.elegida == f["id"]:
                c.create_rectangle(0, y, ancho, y + FILA,
                                   fill=T("bg_row_sel"), outline=ORO)
            elif i % 2:
                c.create_rectangle(0, y, ancho, y + FILA,
                                   fill=T("bg_row_par"), outline="")

            if f["mesas"]:
                sitio = f["zona"] or f["salon"]
            elif f["salon_destino"]:
                sitio = (f["zona_destino"] or f["salon_destino"]) \
                    + "  (sin sentar)"
            else:
                sitio = "sin asignar"
            valores = (f["num_reserva"] or ("EXTERNA" if f["externa"] else ""),
                       f["agencia"], f["cliente"], str(f["adultos"]),
                       str(f["ninos"] or ""), sitio,
                       ("%s%s" % (f["mesas"], " 🔒" if f["fijada"] else ""))
                       if f["mesas"] else "")
            x = 10
            for valor, (_, largo, w) in zip(valores, self.COLUMNAS):
                texto = valor if len(valor) <= largo \
                    else valor[:largo - 1] + "…"
                c.create_text(x, y + 11, anchor="w", text=texto,
                              fill=T("text_primary") if f["mesas"]
                              else T("text_dim"), font=("Segoe UI", 9))
                x += w
        c.configure(scrollregion=c.bbox("all"))

    def _pulsar(self, evento):
        i = int((self.lienzo.canvasy(evento.y) - 26) // FILA)
        if 0 <= i < len(self.filas):
            self.elegida = self.filas[i]["id"]
            estado = "normal"
        else:
            self.elegida = None
            estado = "disabled"
        self.boton_editar.configure(state=estado)
        self.boton_borrar.configure(state=estado)
        self._pintar()

    def _fila_elegida(self):
        return next((f for f in self.filas if f["id"] == self.elegida), None)

    # ── Acciones ──────────────────────────────────────────────────

    def _nueva(self):
        VentanaReserva(self.frame, self.con, self.evento_id, None,
                       self._tras_guardar)

    def _editar(self):
        f = self._fila_elegida()
        if f:
            VentanaReserva(self.frame, self.con, self.evento_id, f["id"],
                           self._tras_guardar)

    def _borrar(self):
        f = self._fila_elegida()
        if not f:
            return
        if not messagebox.askyesno(
            "Borrar reserva",
            "%s (%s), %d comensales.\n\nSe borra del evento y de la mesa"
            " donde estuviera sentada.\n\n¿Seguro?"
            % (f["cliente"], f["num_reserva"] or "externa",
               f["adultos"] + f["ninos"]), parent=self.frame):
            return
        with self.con:
            self.con.execute("DELETE FROM reserva WHERE id = ?", (f["id"],))
        self.elegida = None
        self._tras_guardar()

    def _tras_guardar(self):
        self.boton_editar.configure(state="disabled")
        self.boton_borrar.configure(state="disabled")
        self._pintar()


class VentanaReserva(ctk.CTkToplevel):
    """Alta y edicion de una reserva, venga del listado del sistema o no."""

    def __init__(self, padre, con, evento_id, reserva_id, al_guardar):
        super().__init__(padre)
        self.con = con
        self.evento_id = evento_id
        self.reserva_id = reserva_id
        self.al_guardar = al_guardar

        r = None
        if reserva_id:
            r = con.execute("SELECT * FROM reserva WHERE id = ?",
                            (reserva_id,)).fetchone()

        self.title("Reserva" if r else "Nueva reserva")
        self.geometry("520x580")
        self.configure(fg_color=T("bg_content"))
        self.transient(padre.winfo_toplevel())

        self.campos = {}
        for clave, texto, ancho in (
                ("num_reserva", "Numero de reserva  (vacio si es externa)",
                 200),
                ("cod_agencia", "Codigo de agencia", 150),
                ("agencia", "Agencia o procedencia", 440),
                ("cliente", "Nombre y apellidos", 440)):
            tk.Label(self, text=texto, bg=T("bg_content"),
                     fg=T("text_secondary"), font=("Segoe UI", 10),
                     anchor="w").pack(fill="x", padx=24, pady=(10, 2))
            campo = ctk.CTkEntry(self, width=ancho, height=30)
            campo.pack(padx=24, anchor="w")
            if r:
                campo.insert(0, r[clave] or "")
            self.campos[clave] = campo

        fila = tk.Frame(self, bg=T("bg_content"))
        fila.pack(fill="x", padx=24, pady=(12, 0))
        for clave, texto in (("adultos", "Adultos"), ("ninos", "Niños")):
            bloque = tk.Frame(fila, bg=T("bg_content"))
            bloque.pack(side="left", padx=(0, 20))
            tk.Label(bloque, text=texto, bg=T("bg_content"),
                     fg=T("text_secondary"), font=("Segoe UI", 10),
                     anchor="w").pack(anchor="w", pady=(0, 2))
            campo = ctk.CTkEntry(bloque, width=90, height=30)
            campo.pack(anchor="w")
            campo.insert(0, str(r[clave]) if r
                         else ("2" if clave == "adultos" else "0"))
            self.campos[clave] = campo

        # Donde va: se puede cambiar de salon sin pasar por Reparto.
        tk.Label(self, text="Salon", bg=T("bg_content"),
                 fg=T("text_secondary"), font=("Segoe UI", 10),
                 anchor="w").pack(fill="x", padx=24, pady=(16, 2))
        self.destinos = [(None, "", "Sin decidir: espera en Reparto")]
        for s in con.execute(
            "SELECT * FROM salon WHERE evento_id = ? AND gestionado = 1"
            " ORDER BY orden", (evento_id,)
        ):
            for z in con.execute(
                "SELECT DISTINCT zona FROM mesa WHERE salon_id = ?"
                " ORDER BY zona = '' DESC, zona", (s["id"],)
            ):
                self.destinos.append(
                    (s["id"], z["zona"],
                     s["nombre"] + (("  ·  " + z["zona"]) if z["zona"]
                                    else "")))
        self.salon = ctk.CTkOptionMenu(
            self, width=440, height=30,
            values=[t for _, _, t in self.destinos])
        self.salon.pack(padx=24, anchor="w")
        if r and r["salon_id"]:
            for sid, zona, etiqueta in self.destinos:
                if sid == r["salon_id"] and zona == (r["zona_destino"] or ""):
                    self.salon.set(etiqueta)
                    break

        pie = tk.Frame(self, bg=T("bg_content"))
        pie.pack(fill="x", pady=20)
        ctk.CTkButton(pie, text="Guardar", width=150, height=34,
                      command=self._guardar).pack(side="left", padx=(24, 8))
        if reserva_id:
            ctk.CTkButton(pie, text="Borrar", width=110, height=34,
                          fg_color="#8a2f2c", hover_color="#a33b37",
                          command=self._borrar).pack(side="left")
        self.after(120, self.grab_set)

    def _entero(self, clave):
        try:
            return int(float(self.campos[clave].get().strip() or 0))
        except ValueError:
            return -1

    def _guardar(self):
        cliente = self.campos["cliente"].get().strip()
        if not cliente:
            messagebox.showwarning("Falta el nombre",
                                   "La reserva necesita un nombre.",
                                   parent=self)
            return
        adultos, ninos = self._entero("adultos"), self._entero("ninos")
        if adultos < 0 or ninos < 0:
            messagebox.showwarning("Numero no valido",
                                   "Adultos y niños tienen que ser numeros.",
                                   parent=self)
            return
        if adultos + ninos <= 0:
            messagebox.showwarning("Sin comensales",
                                   "La reserva no tiene a nadie.",
                                   parent=self)
            return

        elegido = self.salon.get()
        salon_id, zona = next(((s, z) for s, z, t in self.destinos
                               if t == elegido), (None, ""))
        num = self.campos["num_reserva"].get().strip()
        codigo = self.campos["cod_agencia"].get().strip()
        agencia = self.campos["agencia"].get().strip()

        with self.con:
            if self.reserva_id is None:
                cur = self.con.execute(
                    "INSERT INTO reserva (evento_id, num_reserva,"
                    " cod_agencia, agencia, cliente, adultos, ninos, externa,"
                    " salon_id, zona_destino, apartada)"
                    " VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                    (self.evento_id, num, codigo, agencia, cliente, adultos,
                     ninos, 0 if num else 1, salon_id, zona,
                     1 if salon_id is None else 0))
                self.reserva_id = cur.lastrowid
            else:
                self.con.execute(
                    "UPDATE reserva SET num_reserva = ?, cod_agencia = ?,"
                    " agencia = ?, cliente = ?, adultos = ?, ninos = ?,"
                    " salon_id = ?, zona_destino = ?, apartada = ?"
                    " WHERE id = ?",
                    (num, codigo, agencia, cliente, adultos, ninos, salon_id,
                     zona, 1 if salon_id is None else 0, self.reserva_id))
            # Cambiar los comensales o el salon deja sin valor la mesa que
            # tuviera: se le da otra al recalcular.
            self.con.execute("DELETE FROM asignacion WHERE reserva_id = ?",
                             (self.reserva_id,))

        from core import motor
        motor.asignar(self.con, self.evento_id)
        self.al_guardar()
        self.destroy()

    def _borrar(self):
        if not messagebox.askyesno(
            "Borrar reserva",
            "Se borra del evento y de la mesa donde estuviera.\n\n¿Seguro?",
                parent=self):
            return
        with self.con:
            self.con.execute("DELETE FROM reserva WHERE id = ?",
                             (self.reserva_id,))
        self.al_guardar()
        self.destroy()
