# -*- coding: utf-8 -*-
"""Ventana principal de Saturno.

Mismo esqueleto que Mercurio: barra lateral de 224 px con un color por
modulo, area de contenido a la derecha y tema oscuro/claro conmutable.
"""
import logging
import tkinter as tk

import customtkinter as ctk

from utils.theme import T, is_dark, toggle as theme_toggle

_log = logging.getLogger(__name__)

# Un color por modulo, igual que en Mercurio: el color significa lo mismo en
# la barra lateral y dentro de la pantalla.
MODULOS = [
    ("eventos",  "Eventos",        "#7fd18a"),
    ("reparto",  "Reparto",        "#c07ad4"),
    ("plano",    "Plano de mesas", "#C9A84C"),
    ("reservas", "Reservas",       "#4A9EEF"),
    ("resumen",  "Resumen",        "#5B9CF6"),
    ("salones",  "Salones",        "#25A873"),
    ("config",   "Configuracion",  "#e0a458"),
]

ICONOS = {"eventos": "◆", "reparto": "⇄", "plano": "▦", "reservas": "≡",
          "resumen": "∑", "salones": "◎", "config": "⚙"}


def _apagar(color, fuerza=0.45):
    """El mismo color, mas apagado, para lo que no esta activo."""
    try:
        r, g, b = (int(color[i:i + 2], 16) for i in (1, 3, 5))
        return "#%02x%02x%02x" % (int(r * fuerza), int(g * fuerza),
                                  int(b * fuerza))
    except Exception:
        return color


class SaturnoApp(ctk.CTk):

    def __init__(self, con, evento_id):
        super().__init__()
        self.con = con
        self.evento_id = evento_id
        self.modulo_activo = None
        self._instancias = {}
        self._botones = {}

        evento = con.execute("SELECT * FROM evento WHERE id = ?",
                             (evento_id,)).fetchone()
        self.title("Saturno - %s" % (evento["nombre"] if evento else ""))
        self.geometry("1280x800")
        self.minsize(1024, 700)
        self.configure(fg_color=T("bg_main"))
        self.after(0, lambda: self.state("zoomed"))

        self._construir_layout()
        self._construir_sidebar()
        self.mostrar("reparto")

    # ── Estructura ────────────────────────────────────────────────

    def _construir_layout(self):
        self.sidebar = ctk.CTkFrame(self, width=224, corner_radius=0,
                                    fg_color=T("bg_sidebar"), border_width=0)
        self.sidebar.pack(side="left", fill="y")
        self.sidebar.pack_propagate(False)

        self.contenido = ctk.CTkFrame(self, corner_radius=0,
                                      fg_color=T("bg_content"))
        self.contenido.pack(side="right", fill="both", expand=True)

    def _construir_sidebar(self):
        cabecera = ctk.CTkFrame(self.sidebar, fg_color="transparent")
        cabecera.pack(fill="x", padx=20, pady=(18, 16))
        ctk.CTkLabel(cabecera, text="SATURNO",
                     font=ctk.CTkFont(family="Segoe UI", size=22,
                                      weight="bold"),
                     text_color=T("text_primary")).pack(anchor="w")
        evento = self.con.execute("SELECT * FROM evento WHERE id = ?",
                                  (self.evento_id,)).fetchone()
        self.etiqueta_evento = ctk.CTkLabel(
            cabecera, text=evento["nombre"] if evento else "sin evento",
            font=ctk.CTkFont(family="Segoe UI", size=11, weight="bold"),
            text_color="#C9A84C", anchor="w")
        self.etiqueta_evento.pack(anchor="w", fill="x")
        ctk.CTkLabel(cabecera, text=(evento["fecha"] or "") if evento else "",
                     font=ctk.CTkFont(family="Segoe UI", size=10),
                     text_color=T("text_dim")).pack(anchor="w")

        ctk.CTkFrame(self.sidebar, height=1, fg_color=T("border")).pack(fill="x")

        nav = ctk.CTkFrame(self.sidebar, fg_color="transparent")
        nav.pack(fill="x", pady=(10, 0))
        for codigo, texto, color in MODULOS:
            self._boton_modulo(nav, codigo, texto, color)

        pie = ctk.CTkFrame(self.sidebar, fg_color="transparent")
        pie.pack(side="bottom", fill="x", pady=(0, 12))
        self._boton_pie(pie, "Cambiar tema", self._cambiar_tema)
        ctk.CTkLabel(pie, text="Saturno v0.1",
                     font=ctk.CTkFont(family="Segoe UI", size=10),
                     text_color=T("text_disabled")).pack(anchor="w", padx=20,
                                                         pady=(8, 0))

    def _boton_modulo(self, padre, codigo, texto, color):
        fondo = T("bg_sidebar")
        fila = tk.Frame(padre, bg=fondo, height=42, cursor="hand2")
        fila.pack(fill="x")
        fila.pack_propagate(False)

        icono = tk.Label(fila, text=ICONOS.get(codigo, "●"), bg=fondo,
                         fg=_apagar(color), font=("Segoe UI", 14))
        icono.pack(side="left", padx=(20, 10))
        etiqueta = tk.Label(fila, text=texto, bg=fondo, fg=T("text_secondary"),
                            font=("Segoe UI", 12))
        etiqueta.pack(side="left")

        self._botones[codigo] = (fila, icono, etiqueta, color)
        for w in (fila, icono, etiqueta):
            w.bind("<Button-1>", lambda e, c=codigo: self.mostrar(c))
            w.bind("<Enter>", lambda e, c=codigo: self._hover(c, True))
            w.bind("<Leave>", lambda e, c=codigo: self._hover(c, False))

    def _boton_pie(self, padre, texto, comando):
        fondo = T("bg_sidebar")
        fila = tk.Frame(padre, bg=fondo, height=30, cursor="hand2")
        fila.pack(fill="x")
        fila.pack_propagate(False)
        etiqueta = tk.Label(fila, text=texto, bg=fondo, fg=T("text_dim"),
                            font=("Segoe UI", 11))
        etiqueta.pack(side="left", padx=(20, 0))
        for w in (fila, etiqueta):
            w.bind("<Button-1>", lambda e: comando())

    def _hover(self, codigo, dentro):
        if codigo == self.modulo_activo:
            return
        fila, icono, etiqueta, _ = self._botones[codigo]
        fondo = T("hover_bg") if dentro else T("bg_sidebar")
        for w in (fila, icono, etiqueta):
            w.configure(bg=fondo)

    def _pintar_botones(self):
        for codigo, (fila, icono, etiqueta, color) in self._botones.items():
            activo = codigo == self.modulo_activo
            fondo = T("active_bg") if activo else T("bg_sidebar")
            for w in (fila, icono, etiqueta):
                w.configure(bg=fondo)
            icono.configure(fg=color if activo else _apagar(color))
            etiqueta.configure(
                fg=T("text_primary") if activo else T("text_secondary"))

    # ── Navegacion ────────────────────────────────────────────────

    def mostrar(self, codigo):
        if codigo == self.modulo_activo:
            # Ya esta delante: se recarga, que los datos pueden haber cambiado.
            vista = self._instancias.get(codigo)
            if vista is not None and hasattr(vista, "al_mostrar"):
                vista.al_mostrar()
            return

        for hijo in self.contenido.winfo_children():
            hijo.pack_forget()

        vista = self._instancias.get(codigo)
        if vista is None:
            vista = self._crear_vista(codigo)
            self._instancias[codigo] = vista
        elif hasattr(vista, "al_mostrar"):
            # Se reaprovechan los widgets, pero SIEMPRE se relee la base.
            vista.al_mostrar()

        vista.frame.pack(fill="both", expand=True)
        self.modulo_activo = codigo
        self._pintar_botones()

    def _crear_vista(self, codigo):
        if codigo == "eventos":
            from modules.eventos import VistaEventos
            return VistaEventos(self.contenido, self.con, self.evento_id, self)
        if codigo == "resumen":
            from modules.resumen import VistaResumen
            return VistaResumen(self.contenido, self.con, self.evento_id, self)
        if codigo == "reparto":
            from modules.reparto import VistaReparto
            return VistaReparto(self.contenido, self.con, self.evento_id, self)
        if codigo == "plano":
            from modules.plano import VistaPlano
            return VistaPlano(self.contenido, self.con, self.evento_id, self)
        if codigo == "reservas":
            from modules.reservas import VistaReservas
            return VistaReservas(self.contenido, self.con, self.evento_id, self)
        if codigo == "salones":
            from modules.salones import VistaSalones
            return VistaSalones(self.contenido, self.con, self.evento_id, self)
        from modules.configuracion import VistaConfiguracion
        return VistaConfiguracion(self.contenido, self.con, self.evento_id, self)

    def cambiar_evento(self, evento_id):
        """Pasa a trabajar en otro evento: se rehace todo con sus datos."""
        self.evento_id = evento_id
        # Queda anotado para volver aqui la proxima vez que se abra.
        with self.con:
            self.con.execute("UPDATE evento SET activo = 0")
            self.con.execute("UPDATE evento SET activo = 1 WHERE id = ?",
                             (evento_id,))
        evento = self.con.execute("SELECT * FROM evento WHERE id = ?",
                                  (evento_id,)).fetchone()
        self.title("Saturno - %s" % (evento["nombre"] if evento else ""))
        for vista in self._instancias.values():
            vista.frame.destroy()
        self._instancias.clear()
        for hijo in self.sidebar.winfo_children():
            hijo.destroy()
        self._botones.clear()
        self._construir_sidebar()
        self.modulo_activo = None
        self.mostrar("reparto")

    def _cambiar_tema(self):
        theme_toggle()
        self.configure(fg_color=T("bg_main"))
        self.sidebar.configure(fg_color=T("bg_sidebar"))
        self.contenido.configure(fg_color=T("bg_content"))
        for hijo in self.sidebar.winfo_children():
            hijo.destroy()
        self._botones.clear()
        self._construir_sidebar()
        # Las vistas se reconstruyen con los colores nuevos.
        for vista in self._instancias.values():
            vista.frame.destroy()
        self._instancias.clear()
        activo, self.modulo_activo = self.modulo_activo, None
        self.mostrar(activo or "reparto")
