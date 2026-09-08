# -*- coding: utf-8 -*-
"""Plano de mesas: la pantalla de trabajo.

Dos maneras de ver lo mismo, que se alternan con un boton:

  Fichas   una ficha por mesa con quien esta sentado. Es la vista de diario.
  Plazas   una casilla por comensal. Mas densa: sirve para repasar al final
           y cazar los huecos sueltos que quedan repartidos.

Todo se dibuja en un Canvas en vez de crear widgets: un salon son 48 mesas
por varias reservas cada una, y con etiquetas sueltas la pantalla tardaba
segundos en aparecer y las mesas ni siquiera salian del mismo tamano.
"""
import tkinter as tk
from tkinter import filedialog, messagebox

import customtkinter as ctk

from utils.theme import T
from core import motor

ORO = "#C9A84C"
ROJO = "#d9534f"

# Colores para distinguir reservas dentro de una misma mesa.
PALETA = ["#C9A84C", "#4A9EEF", "#25A873", "#c07ad4", "#e0a458", "#7fd18a",
          "#E8A030", "#5B9CF6"]

FICHA_ANCHO, FICHA_ALTO, FICHA_HUECO = 300, 186, 14
PLAZA_LADO, PLAZA_HUECO, PLAZA_FILA = 26, 3, 40


def corto(texto, n):
    texto = (texto or "").strip()
    return texto if len(texto) <= n else texto[:n - 1] + "…"


class VistaPlano:

    def __init__(self, padre, con, evento_id, app):
        self.con = con
        self.evento_id = evento_id
        self.app = app
        self.salon_activo = None
        self.vista = "fichas"

        self._zonas_mesa = []      # (x1, y1, x2, y2, mesa_id) en el lienzo
        self._arrastre = None      # datos de lo que se lleva en la mano
        self._chip = []            # figuras del rotulo que sigue al raton
        self._resalte = None       # recuadro de la mesa de destino

        self.frame = ctk.CTkFrame(padre, fg_color=T("bg_content"),
                                  corner_radius=0)
        self._construir()
        self.al_mostrar()

    # ── Construccion ──────────────────────────────────────────────

    def _construir(self):
        cab = ctk.CTkFrame(self.frame, fg_color=T("bg_header"),
                           corner_radius=0, height=64)
        cab.pack(fill="x")
        cab.pack_propagate(False)
        ctk.CTkLabel(cab, text="Plano de mesas",
                     font=ctk.CTkFont(family="Segoe UI", size=17,
                                      weight="bold"),
                     text_color=T("text_primary")).pack(side="left", padx=20)

        self.selector = ctk.CTkSegmentedButton(
            cab, values=["Fichas", "Plazas"], command=self._cambiar_vista,
            width=180, height=30)
        self.selector.set("Fichas")
        self.selector.pack(side="left", padx=10)
        ctk.CTkLabel(cab, text="arrastra para cambiar de mesa · doble clic"
                              " para fijar · boton derecho para quitar",
                     font=ctk.CTkFont(family="Segoe UI", size=10),
                     text_color=T("text_dim")).pack(side="left", padx=10)

        for texto, orden in (("Exportar a Excel", self._exportar),
                             ("Asignar mesas", self._asignar),
                             ("Importar listado", self._importar)):
            ctk.CTkButton(cab, text=texto, command=orden, width=130,
                          height=30, corner_radius=6).pack(side="right",
                                                           padx=(0, 12))

        self.cinta = ctk.CTkFrame(self.frame, fg_color=T("bg_kpi"),
                                  corner_radius=0, height=78)
        self.cinta.pack(fill="x")
        self.cinta.pack_propagate(False)

        cuerpo = ctk.CTkFrame(self.frame, fg_color="transparent")
        cuerpo.pack(fill="both", expand=True)

        marco = tk.Frame(cuerpo, bg=T("bg_content"))
        marco.pack(fill="both", expand=True, padx=12, pady=12)
        self.lienzo = tk.Canvas(marco, bg=T("bg_content"),
                                highlightthickness=0)
        barra = tk.Scrollbar(marco, orient="vertical",
                             command=self.lienzo.yview)
        self.lienzo.configure(yscrollcommand=barra.set)
        barra.pack(side="right", fill="y")
        self.lienzo.pack(side="left", fill="both", expand=True)

        self.lienzo.bind("<Button-1>", self._pulsar)
        self.lienzo.bind("<B1-Motion>", self._arrastrar)
        self.lienzo.bind("<ButtonRelease-1>", self._soltar)
        self.lienzo.bind("<Double-Button-1>", self._doble_clic)
        # Boton derecho sobre alguien sentado: levantarlo de la mesa.
        self.lienzo.bind("<Button-3>", self._boton_derecho)
        self.lienzo.bind("<MouseWheel>", self._rueda)
        self.lienzo.bind("<Configure>", self._al_redimensionar)
        self._ancho_pintado = 0

    def _rueda(self, evento):
        self.lienzo.yview_scroll(-evento.delta // 120, "units")

    def _al_redimensionar(self, evento):
        """Recoloca las fichas cuando cambia el ancho, no en cada pixel."""
        if abs(evento.width - self._ancho_pintado) < FICHA_ANCHO / 2:
            return
        self._ancho_pintado = evento.width
        self._pintar_lienzo()

    def _cambiar_vista(self, valor):
        self.vista = "fichas" if valor == "Fichas" else "plazas"
        self._pintar_lienzo()

    # ── Datos ─────────────────────────────────────────────────────

    def al_mostrar(self):
        self.salones = list(self.con.execute(
            "SELECT * FROM salon WHERE evento_id = ? AND gestionado = 1"
            " ORDER BY orden", (self.evento_id,)))
        if self.salon_activo is None and self.salones:
            self.salon_activo = (self.salones[0]["id"], "")
        self._pintar_cinta()
        self._pintar_lienzo()

    def _zonas(self, salon_id):
        return [f["zona"] for f in self.con.execute(
            "SELECT DISTINCT zona FROM mesa WHERE salon_id = ?"
            " ORDER BY zona = '' DESC, zona", (salon_id,))]

    def _cargar_mesas(self):
        salon_id, zona = self.salon_activo
        mesas = list(self.con.execute(
            "SELECT * FROM mesa WHERE salon_id = ? AND zona = ?"
            " ORDER BY numero", (salon_id, zona)))
        ocupantes = {}
        for f in self.con.execute(
            "SELECT a.id, a.mesa_id, a.pax, a.fijada, r.id reserva_id,"
            "       r.cliente, r.agencia, r.num_reserva, r.adultos, r.ninos,"
            "       r.externa"
            " FROM asignacion a JOIN reserva r ON r.id = a.reserva_id"
            " JOIN mesa m ON m.id = a.mesa_id"
            " WHERE m.salon_id = ? AND m.zona = ? ORDER BY a.id",
            (salon_id, zona)
        ):
            ocupantes.setdefault(f["mesa_id"], []).append(f)
        return mesas, ocupantes

    # ── Cinta de salones ──────────────────────────────────────────

    def _pintar_cinta(self):
        for w in self.cinta.winfo_children():
            w.destroy()
        for salon in self.salones:
            for zona in self._zonas(salon["id"]):
                self._tarjeta_salon(salon, zona)

    def _tarjeta_salon(self, salon, zona):
        clave = (salon["id"], zona)
        activo = clave == self.salon_activo
        f = self.con.execute(
            "SELECT COUNT(*) mesas, COALESCE(SUM(m.capacidad),0) plazas,"
            " COALESCE(SUM((SELECT SUM(pax) FROM asignacion"
            "               WHERE mesa_id = m.id)),0) ocup"
            " FROM mesa m WHERE m.salon_id = ? AND m.zona = ?",
            (salon["id"], zona)).fetchone()

        fondo = T("active_bg") if activo else T("bg_kpi")
        caja = tk.Frame(self.cinta, bg=fondo, cursor="hand2",
                        highlightthickness=1,
                        highlightbackground=T("active_border") if activo
                        else T("border"))
        caja.pack(side="left", fill="y", padx=(12, 0), pady=8)
        titulo = tk.Label(caja, text=zona if zona else salon["nombre"],
                          bg=fondo, font=("Segoe UI", 11, "bold"),
                          fg=T("text_primary") if activo
                          else T("text_secondary"))
        titulo.pack(anchor="w", padx=12, pady=(6, 0))
        detalle = tk.Label(
            caja, text="%d/%d plazas  ·  %d mesas  ·  quedan %d"
                       % (f["ocup"], f["plazas"], f["mesas"],
                          f["plazas"] - f["ocup"]),
            bg=fondo, fg=T("kpi_label"), font=("Segoe UI", 9))
        detalle.pack(anchor="w", padx=12, pady=(0, 6))
        for w in (caja, titulo, detalle):
            w.bind("<Button-1>", lambda e, c=clave: self._elegir_salon(c))

    def _elegir_salon(self, clave):
        self.salon_activo = clave
        self._pintar_cinta()
        self._pintar_lienzo()

    # ── Dibujo del lienzo ─────────────────────────────────────────

    def _pintar_lienzo(self):
        self.lienzo.delete("all")
        self._zonas_mesa = []
        self._resalte = None
        if not self.salon_activo:
            return
        mesas, ocupantes = self._cargar_mesas()
        if self.vista == "fichas":
            self._dibujar_fichas(mesas, ocupantes)
        else:
            self._dibujar_plazas(mesas, ocupantes)
        self.lienzo.configure(scrollregion=self.lienzo.bbox("all"))

    def _columnas(self, ancho_pieza):
        # Antes de que la ventana se dibuje, winfo_width() devuelve 1: sin
        # este minimo saldria una sola columna de fichas.
        ancho = self.lienzo.winfo_width()
        if ancho < 100:
            ancho = 1200
        return max(1, (ancho - 20) // ancho_pieza)

    def _dibujar_fichas(self, mesas, ocupantes):
        c = self.lienzo
        por_fila = self._columnas(FICHA_ANCHO + FICHA_HUECO)

        # Cada banda de mesas es tan alta como la mesa mas cargada de esa
        # banda: si una mesa tiene ocho reservas, se ven las ocho. Antes se
        # cortaban a seis y dejabas de ver gente sentada.
        altos, y_banda, y = [], [], 14
        for inicio in range(0, len(mesas), por_fila):
            banda = mesas[inicio:inicio + por_fila]
            cabidas = max((len(ocupantes.get(m["id"], [])) for m in banda),
                          default=0)
            alto = max(FICHA_ALTO, 58 + max(1, cabidas) * 19 + 8)
            altos.append(alto)
            y_banda.append(y)
            y += alto + FICHA_HUECO

        for i, mesa in enumerate(mesas):
            gente = ocupantes.get(mesa["id"], [])
            ocup = sum(g["pax"] for g in gente)
            lleno = ocup >= mesa["capacidad"]
            alto_ficha = altos[i // por_fila]
            x = 14 + (i % por_fila) * (FICHA_ANCHO + FICHA_HUECO)
            y = y_banda[i // por_fila]

            c.create_rectangle(x, y, x + FICHA_ANCHO, y + alto_ficha,
                               fill=T("bg_card"),
                               outline=ORO if lleno else T("border_card"))
            c.create_rectangle(x, y, x + FICHA_ANCHO, y + 30,
                               fill=T("table_head_bg"), outline="")
            c.create_text(x + 12, y + 15, anchor="w",
                          text="MESA %d" % mesa["numero"],
                          fill=T("text_primary"),
                          font=("Segoe UI", 11, "bold"))
            ninos_mesa = sum(max(0, g["pax"] - g["adultos"]) for g in gente)
            resumen = "%d/%d" % (ocup, mesa["capacidad"])
            if ninos_mesa:
                resumen += "  (%dN)" % ninos_mesa
            c.create_text(x + FICHA_ANCHO - 12, y + 15, anchor="e",
                          text=resumen,
                          fill=ORO if lleno else T("text_dim"),
                          font=("Segoe UI", 10, "bold"))
            ratio = min(1.0, ocup / max(1, mesa["capacidad"]))
            c.create_rectangle(x, y + 30, x + FICHA_ANCHO, y + 33,
                               fill=T("bg_surface"), outline="")
            if ratio:
                c.create_rectangle(x, y + 30, x + FICHA_ANCHO * ratio,
                                   y + 33, fill=ORO, outline="")

            # Mismas columnas que la hoja de siempre: RSV, NOMBRE, AD y N.
            col_rsv, col_nombre = x + 10, x + 72
            col_ad, col_n = x + FICHA_ANCHO - 44, x + FICHA_ANCHO - 16
            fila = y + 44
            for titulo, col, anclaje in (("RSV", col_rsv, "w"),
                                         ("NOMBRE", col_nombre, "w"),
                                         ("AD", col_ad, "e"),
                                         ("N", col_n, "e")):
                c.create_text(col, fila, anchor=anclaje, text=titulo,
                              fill=T("table_head_fg"),
                              font=("Segoe UI", 7, "bold"))
            fila += 14

            for g in gente:
                if fila > y + alto_ficha - 12:
                    c.create_text(col_rsv, fila, anchor="w",
                                  text="+%d mas" % (len(gente) -
                                                    gente.index(g)),
                                  fill=T("text_dim"), font=("Segoe UI", 8))
                    break
                etiqueta = "res:%d" % g["id"]
                c.create_rectangle(x + 5, fila - 9, x + FICHA_ANCHO - 5,
                                   fila + 9, fill=T("bg_row_sel")
                                   if g["fijada"] else T("bg_card"),
                                   outline="", tags=etiqueta)
                # Una reserva partida entre varias mesas no lleva sus ninos
                # en todas: se sientan primero los adultos.
                adultos = min(g["pax"], g["adultos"])
                ninos = g["pax"] - adultos
                rsv = g["num_reserva"] or ("EXT" if g["externa"] else "")
                c.create_text(col_rsv, fila, anchor="w",
                              text=("🔒" if g["fijada"] else "") + rsv,
                              fill=T("text_dim"), font=("Consolas", 8),
                              tags=etiqueta)
                c.create_text(col_nombre, fila, anchor="w",
                              text=corto(g["cliente"], 22),
                              fill=T("text_primary"), font=("Segoe UI", 9),
                              tags=etiqueta)
                c.create_text(col_ad, fila, anchor="e", text=str(adultos),
                              fill=T("text_primary"), font=("Segoe UI", 9),
                              tags=etiqueta)
                c.create_text(col_n, fila, anchor="e",
                              text=str(ninos) if ninos else "",
                              fill=ORO if ninos else T("text_dim"),
                              font=("Segoe UI", 9, "bold" if ninos else
                                    "normal"), tags=etiqueta)
                fila += 19

            self._zonas_mesa.append((x, y, x + FICHA_ANCHO, y + alto_ficha,
                                     mesa["id"]))

    def _dibujar_plazas(self, mesas, ocupantes):
        c = self.lienzo
        for i, mesa in enumerate(mesas):
            gente = ocupantes.get(mesa["id"], [])
            y = 16 + i * PLAZA_FILA
            c.create_text(16, y + PLAZA_LADO / 2, anchor="w",
                          text="MESA %-3d" % mesa["numero"],
                          fill=T("text_secondary"),
                          font=("Consolas", 10, "bold"))
            x = 110
            plaza = 0
            for j, g in enumerate(gente):
                color = PALETA[j % len(PALETA)]
                etiqueta = "res:%d" % g["id"]
                for _ in range(g["pax"]):
                    if plaza >= mesa["capacidad"]:
                        break
                    c.create_rectangle(x, y, x + PLAZA_LADO, y + PLAZA_LADO,
                                       fill=color, outline=T("bg_content"),
                                       tags=etiqueta)
                    plaza += 1
                    x += PLAZA_LADO + PLAZA_HUECO
            for _ in range(mesa["capacidad"] - plaza):
                c.create_rectangle(x, y, x + PLAZA_LADO, y + PLAZA_LADO,
                                   fill=T("bg_surface"), outline=T("border"))
                x += PLAZA_LADO + PLAZA_HUECO

            texto = "   ".join(
                "%s %s (%d%s)" % (g["num_reserva"] or "EXT",
                                  corto(g["cliente"], 16), g["pax"],
                                  "+%dN" % (g["pax"] - g["adultos"])
                                  if g["pax"] > g["adultos"] else "")
                for g in gente)
            c.create_text(x + 16, y + PLAZA_LADO / 2, anchor="w",
                          text=texto or "libre",
                          fill=T("text_primary") if gente else T("text_dim"),
                          font=("Segoe UI", 9))
            self._zonas_mesa.append((100, y - 4, x + 10, y + PLAZA_LADO + 4,
                                     mesa["id"]))

    # ── Arrastrar y soltar ────────────────────────────────────────

    def _etiqueta_bajo(self, lienzo, evento, prefijo):
        x = lienzo.canvasx(evento.x)
        y = lienzo.canvasy(evento.y)
        for item in reversed(lienzo.find_overlapping(x - 1, y - 1, x + 1,
                                                     y + 1)):
            for etiqueta in lienzo.gettags(item):
                if etiqueta.startswith(prefijo):
                    return int(etiqueta.split(":")[1])
        return None

    def _pulsar(self, evento):
        asignacion_id = self._etiqueta_bajo(self.lienzo, evento, "res:")
        if asignacion_id is None:
            return
        f = self.con.execute(
            "SELECT a.id, a.pax, a.mesa_id, r.cliente FROM asignacion a"
            " JOIN reserva r ON r.id = a.reserva_id WHERE a.id = ?",
            (asignacion_id,)).fetchone()
        if f is None:
            return
        self._arrastre = {"id": f["id"], "reserva_id": None, "pax": f["pax"],
                          "cliente": f["cliente"], "origen": f["mesa_id"]}
        self._crear_chip(evento)

    def _crear_chip(self, evento, origen=None):
        """El rotulo que va pegado al raton mientras se arrastra."""
        self._borrar_chip()
        texto = "%s  ·  %d" % (corto(self._arrastre["cliente"], 22),
                               self._arrastre["pax"])
        x, y = self._raton_en_lienzo(evento, origen)
        ancho = 9 * len(texto)
        self._chip = [
            self.lienzo.create_rectangle(x, y, x + ancho, y + 22, fill=ORO,
                                         outline="", tags="chip"),
            self.lienzo.create_text(x + 10, y + 11, anchor="w", text=texto,
                                    fill="#1a1500",
                                    font=("Segoe UI", 9, "bold"),
                                    tags="chip"),
        ]

    def _raton_en_lienzo(self, evento, origen=None):
        """Coordenadas del raton dentro del lienzo."""
        return (self.lienzo.canvasx(evento.x) + 12,
                self.lienzo.canvasy(evento.y) + 12)

    def _borrar_chip(self):
        self.lienzo.delete("chip")
        self._chip = []

    def _arrastrar(self, evento):
        if self._arrastre is None:
            return
        origen = evento.widget if isinstance(evento.widget, tk.Canvas) else None
        x, y = self._raton_en_lienzo(evento, origen)
        if self._chip:
            self.lienzo.delete("chip")
            texto = "%s  ·  %d" % (corto(self._arrastre["cliente"], 22),
                                   self._arrastre["pax"])
            ancho = 9 * len(texto)
            mesa_id = self._mesa_en(x - 12, y - 12)
            cabe = self._cabe(mesa_id) if mesa_id else True
            color = ORO if cabe else ROJO
            self._chip = [
                self.lienzo.create_rectangle(x, y, x + ancho, y + 22,
                                             fill=color, outline="",
                                             tags="chip"),
                self.lienzo.create_text(x + 10, y + 11, anchor="w",
                                        text=texto, fill="#1a1500",
                                        font=("Segoe UI", 9, "bold"),
                                        tags="chip"),
            ]
        self._resaltar(self._mesa_en(x - 12, y - 12))

    def _mesa_en(self, x, y):
        for x1, y1, x2, y2, mesa_id in self._zonas_mesa:
            if x1 <= x <= x2 and y1 <= y <= y2:
                return mesa_id
        return None

    def _cabe(self, mesa_id):
        if mesa_id is None or self._arrastre is None:
            return True
        mesa = self.con.execute("SELECT capacidad FROM mesa WHERE id = ?",
                                (mesa_id,)).fetchone()
        ocup = self.con.execute(
            "SELECT COALESCE(SUM(pax),0) FROM asignacion WHERE mesa_id = ?"
            "  AND id IS NOT ?", (mesa_id, self._arrastre["id"])).fetchone()[0]
        return ocup + self._arrastre["pax"] <= mesa["capacidad"]

    def _resaltar(self, mesa_id):
        self.lienzo.delete("resalte")
        if mesa_id is None:
            return
        for x1, y1, x2, y2, mid in self._zonas_mesa:
            if mid == mesa_id:
                self.lienzo.create_rectangle(
                    x1 - 2, y1 - 2, x2 + 2, y2 + 2, outline=ORO
                    if self._cabe(mesa_id) else ROJO, width=2,
                    tags="resalte")
                break

    def _soltar(self, evento):
        arrastre, self._arrastre = self._arrastre, None
        self._borrar_chip()
        self.lienzo.delete("resalte")
        if arrastre is None:
            return
        origen = evento.widget if isinstance(evento.widget, tk.Canvas) else None
        x, y = self._raton_en_lienzo(evento, origen)
        mesa_id = self._mesa_en(x - 12, y - 12)
        if mesa_id is None or mesa_id == arrastre["origen"]:
            return

        mesa = self.con.execute("SELECT * FROM mesa WHERE id = ?",
                                (mesa_id,)).fetchone()
        ocup = self.con.execute(
            "SELECT COALESCE(SUM(pax),0) FROM asignacion WHERE mesa_id = ?"
            "  AND id IS NOT ?", (mesa_id, arrastre["id"])).fetchone()[0]
        sillas = ocup + arrastre["pax"] - mesa["capacidad"]
        if sillas > 0:
            if not messagebox.askyesno(
                "La mesa se queda corta",
                "La mesa %d tiene %d plazas y ya van %d.\n\n"
                "Sentar a %s (%d) obliga a poner %d silla(s) mas.\n"
                "¿Se ponen?"
                % (mesa["numero"], mesa["capacidad"], ocup,
                   arrastre["cliente"], arrastre["pax"], sillas),
                    parent=self.frame):
                return
            with self.con:
                self.con.execute("UPDATE mesa SET capacidad = ? WHERE id = ?",
                                 (ocup + arrastre["pax"], mesa_id))

        with self.con:
            if arrastre["id"] is None:
                self.con.execute(
                    "INSERT INTO asignacion (reserva_id, mesa_id, pax, fijada)"
                    " VALUES (?,?,?,1)",
                    (arrastre["reserva_id"], mesa_id, arrastre["pax"]))
            else:
                # Colocarla a mano es una peticion: queda fijada para que un
                # recalculo posterior no la devuelva a su sitio.
                self.con.execute(
                    "UPDATE asignacion SET mesa_id = ?, fijada = 1"
                    " WHERE id = ?", (mesa_id, arrastre["id"]))
        self.al_mostrar()

    def _boton_derecho(self, evento):
        """Saca a una reserva de la mesa y la devuelve a Reparto."""
        asignacion_id = self._etiqueta_bajo(self.lienzo, evento, "res:")
        if asignacion_id is None:
            return
        f = self.con.execute(
            "SELECT a.pax, r.id, r.cliente, r.num_reserva FROM asignacion a"
            " JOIN reserva r ON r.id = a.reserva_id WHERE a.id = ?",
            (asignacion_id,)).fetchone()
        if f is None:
            return
        if not messagebox.askyesno(
            "Quitar de la mesa",
            "%s (%s), %d comensales.\n\nSe levanta de la mesa y vuelve a"
            " POR REPARTIR, para decidir de nuevo a que salon va."
            "\n\n¿Seguimos?" % (f["cliente"], f["num_reserva"] or "externa",
                                f["pax"]), parent=self.frame):
            return
        with self.con:
            # Queda apartada para que ninguna regla la devuelva a su salon.
            self.con.execute(
                "UPDATE reserva SET salon_id = NULL, zona_destino = '',"
                " apartada = 1 WHERE id = ?", (f["id"],))
            self.con.execute("DELETE FROM asignacion WHERE reserva_id = ?",
                             (f["id"],))
        self.al_mostrar()

    def _doble_clic(self, evento):
        asignacion_id = self._etiqueta_bajo(self.lienzo, evento, "res:")
        if asignacion_id is None:
            return
        with self.con:
            self.con.execute(
                "UPDATE asignacion SET fijada = NOT fijada WHERE id = ?",
                (asignacion_id,))
        self._pintar_lienzo()

    # ── Acciones ──────────────────────────────────────────────────

    def _importar(self):
        ruta = filedialog.askopenfilename(
            title="Listado de reservas del sistema",
            filetypes=[("Excel", "*.xls *.xlsx"), ("Todos", "*.*")],
            parent=self.frame)
        if not ruta:
            return
        from core import importador
        try:
            n, pax, avisos = importador.importar(self.con, self.evento_id,
                                                 ruta)
        except Exception as err:
            messagebox.showerror("No se ha podido leer el listado", str(err),
                                 parent=self.frame)
            return
        messagebox.showinfo(
            "Listado importado", "%d reservas, %d comensales.%s"
            % (n, pax, "\n\n" + "\n".join(avisos) if avisos else ""),
            parent=self.frame)
        self.al_mostrar()

    def _asignar(self):
        res = motor.asignar(self.con, self.evento_id)
        texto = ("%d reservas sentadas.\n%d peticiones respetadas."
                 % (res["asignadas"], res["fijadas"]))
        if res["pax_sin_sitio"]:
            texto += ("\n\n%d comensales sin sitio en su salon: estan a la"
                      " derecha para colocarlos a mano."
                      % res["pax_sin_sitio"])
        if res["pax_excluidas"]:
            texto += ("\n\n%d comensales de segmentos que no se gestionan"
                      " aqui." % res["pax_excluidas"])
        messagebox.showinfo("Mesas asignadas", texto, parent=self.frame)
        self.al_mostrar()

    def _exportar(self):
        ruta = filedialog.asksaveasfilename(
            title="Guardar el plano", defaultextension=".xlsx",
            filetypes=[("Excel", "*.xlsx")], parent=self.frame)
        if not ruta:
            return
        from core import exportar
        exportar.exportar(self.con, self.evento_id, ruta)
        messagebox.showinfo("Plano exportado", ruta, parent=self.frame)
