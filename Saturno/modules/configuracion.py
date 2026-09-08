# -*- coding: utf-8 -*-
"""Configuracion del evento: salones, montaje y reparto de agencias.

Todo lo particular de un hotel se da de alta aqui. En el codigo no hay ni un
salon ni una agencia: un evento nuevo nace vacio y se llena desde esta
pantalla, o cargando una plantilla guardada.
"""
import tkinter as tk
from tkinter import messagebox, simpledialog

import customtkinter as ctk

from utils.theme import T
from core import plantillas

FILA_ALTO = 26


class VistaConfiguracion:

    def __init__(self, padre, con, evento_id, app):
        self.con = con
        self.evento_id = evento_id
        self.app = app
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
        ctk.CTkLabel(cab, text="Configuracion",
                     font=ctk.CTkFont(family="Segoe UI", size=17,
                                      weight="bold"),
                     text_color=T("text_primary")).pack(side="left", padx=20)
        ctk.CTkButton(cab, text="Guardar como plantilla", width=170,
                      height=30, corner_radius=6,
                      command=self._guardar_plantilla).pack(side="right",
                                                            padx=(0, 12))
        ctk.CTkButton(cab, text="Cargar plantilla", width=140, height=30,
                      corner_radius=6,
                      command=self._cargar_plantilla).pack(side="right",
                                                           padx=(0, 12))

        self.cuerpo = ctk.CTkScrollableFrame(self.frame,
                                             fg_color=T("bg_content"),
                                             corner_radius=0)
        self.cuerpo.pack(fill="both", expand=True, padx=16, pady=12)

    def al_mostrar(self):
        for w in self.cuerpo.winfo_children():
            w.destroy()
        self._bloque_salones()
        self._bloque_segmentos()

    def _titulo(self, texto, ayuda, boton=None, orden=None):
        barra = tk.Frame(self.cuerpo, bg=T("bg_content"))
        barra.pack(fill="x", pady=(16, 2))
        tk.Label(barra, text=texto, bg=T("bg_content"), fg=T("text_primary"),
                 font=("Segoe UI", 13, "bold")).pack(side="left")
        if boton:
            ctk.CTkButton(barra, text=boton, width=130, height=26,
                          corner_radius=6, command=orden).pack(side="right")
        tk.Label(self.cuerpo, text=ayuda, bg=T("bg_content"),
                 fg=T("text_dim"), font=("Segoe UI", 10),
                 anchor="w").pack(fill="x", pady=(0, 6))

    def _tabla(self, cabeceras, anchos, filas):
        """Dibuja una tabla.

        Cada fila es (valores, acciones, sangrada), donde acciones es una
        lista de (texto, funcion, peligrosa). Los botones van a la vista en
        cada fila: el doble clic sobre la primera accion queda como atajo,
        pero nunca como unica manera de llegar.
        """
        cab = tk.Frame(self.cuerpo, bg=T("table_head_bg"))
        cab.pack(fill="x")
        for texto, ancho in zip(cabeceras, anchos):
            tk.Label(cab, text=texto, bg=T("table_head_bg"),
                     fg=T("table_head_fg"), font=("Segoe UI", 9, "bold"),
                     width=ancho, anchor="w").pack(side="left", padx=3)

        for i, (valores, acciones, sangrada) in enumerate(filas):
            fondo = T("bg_row_par") if i % 2 else T("bg_row_impar")
            fila = tk.Frame(self.cuerpo, bg=fondo,
                            cursor="hand2" if acciones else "")
            fila.pack(fill="x")
            etiquetas = [fila]
            for j, (valor, ancho) in enumerate(zip(valores, anchos)):
                lbl = tk.Label(fila, text=valor, bg=fondo,
                               fg=T("text_dim") if sangrada and j == 0
                               else T("text_primary"),
                               font=("Segoe UI", 9), width=ancho, anchor="w")
                lbl.pack(side="left", padx=3)
                etiquetas.append(lbl)

            for texto, funcion, peligrosa in reversed(acciones or []):
                extra = {"fg_color": "#8a2f2c",
                         "hover_color": "#a33b37"} if peligrosa else {}
                ctk.CTkButton(fila, text=texto, width=64, height=20,
                              corner_radius=4, font=ctk.CTkFont(size=10),
                              command=funcion, **extra).pack(
                                  side="right", padx=4, pady=2)
            if acciones:
                for w in etiquetas:
                    w.bind("<Double-Button-1>",
                           lambda e, f=acciones[0][1]: f())

    # ── Salones ───────────────────────────────────────────────────

    def _bloque_salones(self):
        self._titulo(
            "Salones y montaje",
            "Las mesas grandes no son mesas estiradas: son mesas de mas"
            " plazas que se montan aparte.",
            "Nuevo salon", self._nuevo_salon)

        filas = []
        for s in self.con.execute(
            "SELECT * FROM salon WHERE evento_id = ? ORDER BY orden",
            (self.evento_id,)
        ):
            zonas = list(self.con.execute(
                "SELECT zona, COUNT(*) n,"
                " SUM(CASE WHEN capacidad_montaje > ? THEN 1 ELSE 0 END) g,"
                " SUM(capacidad_montaje) plazas, MIN(numero) a, MAX(numero) b"
                " FROM mesa WHERE salon_id = ? GROUP BY zona"
                " ORDER BY MIN(numero)", (s["capacidad_base"], s["id"])))
            acciones_salon = [
                ("Editar", lambda k=s["id"]: self._editar_salon(k), False),
                ("Borrar", lambda k=s["id"]: self._borrar_salon(k), True)]

            if not zonas:
                filas.append(((s["nombre"], "sin mesas", "", "", "", "",
                               str(s["capacidad_base"]),
                               str(s["mesas_ampliables"])),
                              acciones_salon, False))
                continue

            for j, z in enumerate(zonas):
                if j == 0:
                    # Primera fila: el salon, con sus botones.
                    valores = (s["nombre"] + ("" if s["gestionado"]
                                              else "   (no se reparte)"),
                               z["zona"] or "principal",
                               "%d-%d" % (z["a"], z["b"]),
                               str(z["n"] - (z["g"] or 0)),
                               str(z["g"] or 0), str(z["plazas"]),
                               str(s["capacidad_base"]),
                               str(s["mesas_ampliables"]))
                    filas.append((valores, acciones_salon, False))
                    continue
                # Las demas zonas cuelgan del salon y se editan aparte: son
                # partes del mismo sitio, no salones sueltos.
                valores = ("   └ " + s["nombre"], z["zona"],
                           "%d-%d" % (z["a"], z["b"]),
                           str(z["n"] - (z["g"] or 0)), str(z["g"] or 0),
                           str(z["plazas"]), str(s["capacidad_base"]),
                           str(s["mesas_ampliables"]))
                filas.append((valores, [
                    ("Editar", lambda k=s["id"]: self._editar_salon(k), False),
                    ("Quitar zona",
                     lambda k=s["id"], zz=z["zona"]: self._borrar_zona(k, zz),
                     True)], True))

        if not filas:
            filas = [(("Todavia no hay salones. Crea uno o carga una"
                       " plantilla.", "", "", "", "", "", "", ""), None,
                      False)]
        self._tabla(("SALON", "ZONA", "MESAS Nº", "NORMALES", "GRANDES",
                     "PLAZAS", "POR MESA", "AMPLIABLES"),
                    (26, 16, 10, 9, 8, 8, 9, 11), filas)

    def _nuevo_salon(self):
        VentanaSalon(self.frame, self.con, self.evento_id, None,
                     self.al_mostrar)

    def _editar_salon(self, salon_id):
        if salon_id is not None:
            VentanaSalon(self.frame, self.con, self.evento_id, salon_id,
                         self.al_mostrar)

    # ── Segmentos ─────────────────────────────────────────────────

    def _bloque_segmentos(self):
        self._titulo(
            "A que salon va cada agencia",
            "Este es el criterio con el que se asignan las mesas. Se miran"
            " EN ORDEN y gana el primero que encaje, asi que un grupo grande"
            " cae en el salon de grupos antes que en el de su agencia.",
            "Nuevo segmento", self._nuevo_segmento)

        filas = []
        for seg in self.con.execute(
            "SELECT * FROM segmento WHERE evento_id = ? ORDER BY orden",
            (self.evento_id,)
        ):
            destino = self.con.execute(
                "SELECT s.nombre, p.zona FROM preferencia p"
                " JOIN salon s ON s.id = p.salon_id"
                " WHERE p.segmento_id = ? ORDER BY p.orden",
                (seg["id"],)).fetchone()
            if seg["excluir"]:
                sitio = "no se gestiona aqui"
            elif destino:
                sitio = destino["nombre"] + (("  ·  " + destino["zona"])
                                             if destino["zona"] else "")
            else:
                sitio = "sin asignar"
            reglas = list(self.con.execute(
                "SELECT tipo, valor FROM regla WHERE segmento_id = ?",
                (seg["id"],)))
            texto = ", ".join(r["valor"] for r in reglas
                              if r["tipo"] == "codigo")
            patrones = [r["valor"] for r in reglas if r["tipo"] == "nombre"]
            if patrones:
                texto += ("  |  nombre: " if texto else "nombre: ") \
                    + ", ".join(patrones)
            umbral = next((r["valor"] for r in reglas
                           if r["tipo"] == "min_pax"), None)
            if umbral:
                texto += ("  |  " if texto else "") +                     "grupos de %s o mas" % umbral
            if any(r["tipo"] == "defecto" for r in reglas):
                texto += "  (y todo lo demas)" if texto else "todo lo demas"
            filas.append((
                ("%d.  %s" % (seg["orden"], seg["nombre"]), sitio, texto),
                [("Editar",
                  lambda k=seg["id"]: self._editar_segmento(k), False),
                 ("Borrar",
                  lambda k=seg["id"]: self._borrar_segmento(k), True)],
                False))
        if not filas:
            filas = [(("Todavia no hay segmentos.", "", ""), None, False)]
        self._tabla(("SEGMENTO", "SE SIENTA EN", "CODIGOS DE AGENCIA"),
                    (16, 30, 70), filas)

    def _borrar_salon(self, salon_id):
        salon = self.con.execute("SELECT * FROM salon WHERE id = ?",
                                 (salon_id,)).fetchone()
        sentados = self.con.execute(
            "SELECT COALESCE(SUM(a.pax), 0) FROM asignacion a"
            " JOIN mesa m ON m.id = a.mesa_id WHERE m.salon_id = ?",
            (salon_id,)).fetchone()[0]
        aviso = "Se borra el salon '%s' con todas sus mesas." % salon["nombre"]
        if sentados:
            aviso += ("\n\nHay %d comensales sentados en el, que se quedaran"
                      " sin mesa." % sentados)
        if not messagebox.askyesno("Borrar salon", aviso + "\n\n¿Seguro?",
                                   parent=self.frame):
            return
        with self.con:
            self.con.execute("DELETE FROM salon WHERE id = ?", (salon_id,))
        self.al_mostrar()

    def _borrar_zona(self, salon_id, zona):
        """Quita una zona del salon con sus mesas, y renumera el resto."""
        salon = self.con.execute("SELECT * FROM salon WHERE id = ?",
                                 (salon_id,)).fetchone()
        f = self.con.execute(
            "SELECT COUNT(*) mesas, COALESCE((SELECT SUM(a.pax) FROM asignacion"
            " a JOIN mesa m2 ON m2.id = a.mesa_id WHERE m2.salon_id = ?"
            " AND m2.zona = ?), 0) pax"
            " FROM mesa WHERE salon_id = ? AND zona = ?",
            (salon_id, zona, salon_id, zona)).fetchone()
        aviso = ("Se quita la zona '%s' de %s, con sus %d mesas."
                 % (zona, salon["nombre"], f["mesas"]))
        if f["pax"]:
            aviso += ("\n\nHay %d comensales sentados en ella, que se"
                      " quedaran sin mesa." % f["pax"])
        if not messagebox.askyesno("Quitar zona", aviso + "\n\n¿Seguro?",
                                   parent=self.frame):
            return
        with self.con:
            self.con.execute(
                "DELETE FROM mesa WHERE salon_id = ? AND zona = ?",
                (salon_id, zona))
            # La numeracion del salon es continua: al faltar una zona hay
            # que recorrerla de nuevo desde el uno.
            self.con.execute(
                "UPDATE mesa SET numero = numero + 100000 WHERE salon_id = ?",
                (salon_id,))
            for numero, mesa in enumerate(self.con.execute(
                "SELECT id FROM mesa WHERE salon_id = ?"
                " ORDER BY zona = '' DESC, zona, numero",
                    (salon_id,)).fetchall(), start=1):
                self.con.execute("UPDATE mesa SET numero = ? WHERE id = ?",
                                 (numero, mesa["id"]))
            self.con.execute(
                "UPDATE salon SET num_mesas ="
                " (SELECT COUNT(*) FROM mesa WHERE salon_id = ?) WHERE id = ?",
                (salon_id, salon_id))
        self.al_mostrar()

    def _borrar_segmento(self, segmento_id):
        seg = self.con.execute("SELECT nombre FROM segmento WHERE id = ?",
                               (segmento_id,)).fetchone()
        if not messagebox.askyesno(
            "Borrar segmento",
            "Se borra el segmento '%s'.\n\nSus agencias se quedaran sin salon"
            " asignado hasta que las metas en otro." % seg["nombre"],
                parent=self.frame):
            return
        with self.con:
            self.con.execute("DELETE FROM segmento WHERE id = ?",
                             (segmento_id,))
        self.al_mostrar()

    def _nuevo_segmento(self):
        VentanaSegmento(self.frame, self.con, self.evento_id, None,
                        self.al_mostrar)

    def _editar_segmento(self, segmento_id):
        if segmento_id is not None:
            VentanaSegmento(self.frame, self.con, self.evento_id, segmento_id,
                            self.al_mostrar)

    # ── Plantillas ────────────────────────────────────────────────

    def _guardar_plantilla(self):
        nombre = simpledialog.askstring(
            "Guardar plantilla",
            "Nombre de la plantilla (por ejemplo, el del hotel):",
            parent=self.frame)
        if not nombre:
            return
        ruta = plantillas.exportar(self.con, self.evento_id, nombre.strip())
        messagebox.showinfo("Plantilla guardada", ruta, parent=self.frame)

    def _cargar_plantilla(self):
        nombres = plantillas.disponibles()
        if not nombres:
            messagebox.showinfo(
                "Sin plantillas",
                "Todavia no hay ninguna plantilla guardada.",
                parent=self.frame)
            return
        VentanaElegirPlantilla(self.frame, nombres, self._aplicar_plantilla)

    def _aplicar_plantilla(self, nombre):
        if not messagebox.askyesno(
            "Cargar plantilla",
            "Se van a reemplazar los salones y las reglas de este evento por"
            " los de '%s'.\n\nLas reservas no se tocan, pero SI se pierden"
            " las mesas asignadas.\n\n¿Seguimos?" % nombre,
                parent=self.frame):
            return
        plantillas.importar(self.con, self.evento_id, nombre)
        self.al_mostrar()
        messagebox.showinfo("Plantilla cargada",
                            "Vuelve al plano y pulsa 'Asignar mesas'.",
                            parent=self.frame)


# ── Ventanas de edicion ───────────────────────────────────────────

class _Dialogo(ctk.CTkToplevel):
    """Base de las ventanas de edicion, con el aspecto de la aplicacion."""

    def __init__(self, padre, titulo, ancho, alto):
        super().__init__(padre)
        self.title(titulo)
        self.geometry("%dx%d" % (ancho, alto))
        self.configure(fg_color=T("bg_content"))
        self.transient(padre.winfo_toplevel())
        self.after(120, self.grab_set)

    def _campo(self, padre, texto, valor="", ancho=340):
        tk.Label(padre, text=texto, bg=T("bg_content"),
                 fg=T("text_secondary"), font=("Segoe UI", 10),
                 anchor="w").pack(fill="x", padx=24, pady=(8, 2))
        entrada = ctk.CTkEntry(padre, width=ancho, height=30)
        entrada.pack(padx=24, anchor="w")
        if valor != "":
            entrada.insert(0, str(valor))
        return entrada

    def _entero(self, entrada, defecto=0):
        try:
            return int(float(entrada.get().strip() or defecto))
        except ValueError:
            return defecto


class VentanaSalon(_Dialogo):
    """Alta y edicion de un salon con sus zonas."""

    def __init__(self, padre, con, evento_id, salon_id, al_guardar):
        super().__init__(padre, "Salon", 620, 700)
        self.con = con
        self.evento_id = evento_id
        self.salon_id = salon_id
        self.al_guardar = al_guardar

        salon = None
        if salon_id:
            salon = con.execute("SELECT * FROM salon WHERE id = ?",
                                (salon_id,)).fetchone()

        arriba = tk.Frame(self, bg=T("bg_content"))
        arriba.pack(fill="x")
        self.nombre = self._campo(arriba, "Nombre del salon",
                                  salon["nombre"] if salon else "")
        fila = tk.Frame(self, bg=T("bg_content"))
        fila.pack(fill="x")
        izq = tk.Frame(fila, bg=T("bg_content"))
        izq.pack(side="left")
        der = tk.Frame(fila, bg=T("bg_content"))
        der.pack(side="left")
        self.orden = self._campo(izq, "Orden en la lista",
                                 salon["orden"] if salon else 1, 120)
        self.cap_base = self._campo(izq, "Plazas por mesa",
                                    salon["capacidad_base"] if salon else 10,
                                    120)
        self.cap_max = self._campo(der, "Plazas de una mesa grande",
                                   salon["capacidad_max"] if salon else 12,
                                   180)
        self.ampliables = self._campo(
            der, "Mesas que admiten sillas de mas",
            salon["mesas_ampliables"] if salon else 0, 180)

        # Un salon puede existir solo para contar: el que lleva otra persona
        # suma sus plazas al total del hotel pero no se reparte aqui.
        self.gestionado = ctk.CTkCheckBox(
            self, text="Se reparte en este salon (si no, solo cuenta en el"
                       " resumen)")
        self.gestionado.pack(anchor="w", padx=24, pady=(14, 0))
        if salon is None or salon["gestionado"]:
            self.gestionado.select()

        tk.Label(self, text="Zonas del salon", bg=T("bg_content"),
                 fg=T("text_primary"), font=("Segoe UI", 11, "bold"),
                 anchor="w").pack(fill="x", padx=24, pady=(16, 0))
        tk.Label(self,
                 text="Una zona es una parte del salon con nombre propio (la"
                      " Naya, la terraza...).\nLa numeracion de mesas es"
                      " continua en todo el salon.",
                 bg=T("bg_content"), fg=T("text_dim"),
                 font=("Segoe UI", 9), justify="left",
                 anchor="w").pack(fill="x", padx=24, pady=(0, 6))

        self.zonas_marco = tk.Frame(self, bg=T("bg_content"))
        self.zonas_marco.pack(fill="both", expand=True, padx=24)
        cab = tk.Frame(self.zonas_marco, bg=T("table_head_bg"))
        cab.pack(fill="x")
        for texto, ancho in (("ZONA (vacia = principal)", 26),
                             ("MESAS NORMALES", 16), ("MESAS GRANDES", 15)):
            tk.Label(cab, text=texto, bg=T("table_head_bg"),
                     fg=T("table_head_fg"), font=("Segoe UI", 8, "bold"),
                     width=ancho, anchor="w").pack(side="left", padx=2)
        self.filas_zona = []

        existentes = []
        if salon_id:
            existentes = list(con.execute(
                "SELECT zona, COUNT(*) n,"
                " SUM(CASE WHEN capacidad_montaje > ? THEN 1 ELSE 0 END) g"
                " FROM mesa WHERE salon_id = ? GROUP BY zona"
                " ORDER BY MIN(numero)", (salon["capacidad_base"], salon_id)))
        for z in existentes:
            self._fila_zona(z["zona"], z["n"] - (z["g"] or 0), z["g"] or 0)
        if not existentes:
            self._fila_zona("", 10, 0)

        ctk.CTkButton(self, text="Anadir zona", width=120, height=26,
                      corner_radius=6,
                      command=lambda: self._fila_zona("", 0, 0)).pack(
                          anchor="w", padx=24, pady=(6, 0))

        pie = tk.Frame(self, bg=T("bg_content"))
        pie.pack(fill="x", pady=14)
        ctk.CTkButton(pie, text="Guardar", width=140, height=32,
                      command=self._guardar).pack(side="left", padx=(24, 8))
        if salon_id:
            ctk.CTkButton(pie, text="Borrar salon", width=130, height=32,
                          fg_color="#8a2f2c", hover_color="#a33b37",
                          command=self._borrar).pack(side="left")

    def _fila_zona(self, nombre, mesas, grandes):
        fila = tk.Frame(self.zonas_marco, bg=T("bg_row_impar"))
        fila.pack(fill="x", pady=1)
        e_nombre = ctk.CTkEntry(fila, width=190, height=26)
        e_nombre.pack(side="left", padx=2)
        e_nombre.insert(0, nombre)
        e_mesas = ctk.CTkEntry(fila, width=110, height=26)
        e_mesas.pack(side="left", padx=2)
        e_mesas.insert(0, str(mesas))
        e_grandes = ctk.CTkEntry(fila, width=110, height=26)
        e_grandes.pack(side="left", padx=2)
        e_grandes.insert(0, str(grandes))
        quitar = ctk.CTkButton(fila, text="✕", width=28, height=26,
                               fg_color="transparent",
                               command=lambda: self._quitar_zona(fila))
        quitar.pack(side="left", padx=4)
        self.filas_zona.append((fila, e_nombre, e_mesas, e_grandes))

    def _quitar_zona(self, fila):
        self.filas_zona = [f for f in self.filas_zona if f[0] is not fila]
        fila.destroy()

    def _guardar(self):
        nombre = self.nombre.get().strip()
        if not nombre:
            messagebox.showwarning("Falta el nombre",
                                   "El salon necesita un nombre.", parent=self)
            return
        cap_base = self._entero(self.cap_base, 10)
        cap_max = self._entero(self.cap_max, 12)
        if cap_base < 1:
            messagebox.showwarning("Plazas por mesa",
                                   "Una mesa tiene que tener al menos una"
                                   " plaza.", parent=self)
            return
        if cap_max < cap_base:
            messagebox.showwarning(
                "Mesa grande",
                "Una mesa grande no puede tener menos plazas que una normal.",
                parent=self)
            return

        zonas = []
        vistos = set()
        for _, e_nombre, e_mesas, e_grandes in self.filas_zona:
            z = e_nombre.get().strip()
            if z in vistos:
                messagebox.showwarning(
                    "Zona repetida",
                    "Hay dos zonas con el nombre '%s'." % (z or "principal"),
                    parent=self)
                return
            vistos.add(z)
            zonas.append((z, self._entero(e_mesas), self._entero(e_grandes)))
        if not zonas or sum(m + g for _, m, g in zonas) == 0:
            messagebox.showwarning("Sin mesas",
                                   "El salon no tiene ni una mesa.",
                                   parent=self)
            return

        with self.con:
            if self.salon_id is None:
                cur = self.con.execute(
                    "INSERT INTO salon (evento_id, nombre, orden,"
                    " capacidad_base, capacidad_max, mesas_ampliables,"
                    " gestionado, num_mesas) VALUES (?,?,?,?,?,?,?,0)",
                    (self.evento_id, nombre, self._entero(self.orden, 1),
                     cap_base, cap_max, self._entero(self.ampliables),
                     1 if self.gestionado.get() else 0))
                self.salon_id = cur.lastrowid
            else:
                self.con.execute(
                    "UPDATE salon SET nombre = ?, orden = ?,"
                    " capacidad_base = ?, capacidad_max = ?,"
                    " mesas_ampliables = ?, gestionado = ? WHERE id = ?",
                    (nombre, self._entero(self.orden, 1), cap_base, cap_max,
                     self._entero(self.ampliables),
                     1 if self.gestionado.get() else 0, self.salon_id))

        if not self._aplicar_zonas(zonas, cap_base, cap_max):
            return
        self.al_guardar()
        self.destroy()

    def _aplicar_zonas(self, zonas, cap_base, cap_max):
        """Ajusta las mesas del salon a las zonas pedidas.

        Conserva las mesas que ya existen; solo crea las que faltan y borra
        las que sobran, empezando por las ultimas. Si alguna de las que se
        van a borrar tiene gente sentada, avisa antes.
        """
        nombres = [z[0] for z in zonas]
        sobrantes = [f["id"] for f in self.con.execute(
            "SELECT id FROM mesa WHERE salon_id = ? AND zona NOT IN (%s)"
            % ",".join("?" * len(nombres)),
            [self.salon_id] + nombres)]

        for zona, mesas, grandes in zonas:
            actuales = [f["id"] for f in self.con.execute(
                "SELECT id FROM mesa WHERE salon_id = ? AND zona = ?"
                " ORDER BY numero", (self.salon_id, zona))]
            sobran = len(actuales) - (mesas + grandes)
            if sobran > 0:
                sobrantes += actuales[-sobran:]

        if sobrantes:
            ocupadas = self.con.execute(
                "SELECT COUNT(DISTINCT mesa_id) FROM asignacion WHERE mesa_id"
                " IN (%s)" % ",".join("?" * len(sobrantes)),
                sobrantes).fetchone()[0]
            if ocupadas and not messagebox.askyesno(
                "Se van a quitar mesas",
                "Se quitan %d mesas, y %d tienen gente sentada.\n"
                "Esas reservas se quedaran sin mesa.\n\n¿Seguimos?"
                % (len(sobrantes), ocupadas), parent=self):
                return False

        with self.con:
            if sobrantes:
                self.con.execute(
                    "DELETE FROM mesa WHERE id IN (%s)"
                    % ",".join("?" * len(sobrantes)), sobrantes)

            # Numero provisional alto y unico: el definitivo se pone en la
            # renumeracion de mas abajo, y no puede chocar con los que ya hay.
            provisional = (self.con.execute(
                "SELECT COALESCE(MAX(numero), 0) FROM mesa WHERE salon_id = ?",
                (self.salon_id,)).fetchone()[0] or 0) + 1000
            for zona, mesas, grandes in zonas:
                actuales = list(self.con.execute(
                    "SELECT id FROM mesa WHERE salon_id = ? AND zona = ?"
                    " ORDER BY numero", (self.salon_id, zona)))
                faltan = (mesas + grandes) - len(actuales)
                for _ in range(max(0, faltan)):
                    self.con.execute(
                        "INSERT INTO mesa (salon_id, zona, numero,"
                        " capacidad_montaje, capacidad) VALUES (?,?,?,?,?)",
                        (self.salon_id, zona, provisional, cap_base,
                         cap_base))
                    provisional += 1

            # Numeracion continua en todo el salon, zona a zona, y las mesas
            # grandes al final de cada zona. Se apartan primero a numeros
            # altos para que al renumerar no choquen entre ellas.
            self.con.execute(
                "UPDATE mesa SET numero = numero + 100000 WHERE salon_id = ?",
                (self.salon_id,))
            numero = 1
            for zona, mesas, grandes in zonas:
                ids = [f["id"] for f in self.con.execute(
                    "SELECT id FROM mesa WHERE salon_id = ? AND zona = ?"
                    " ORDER BY numero, id", (self.salon_id, zona))]
                for i, mesa_id in enumerate(ids):
                    grande = i >= mesas
                    cap = cap_max if grande else cap_base
                    self.con.execute(
                        "UPDATE mesa SET numero = ?, capacidad_montaje = ?,"
                        " capacidad = MAX(capacidad, ?) WHERE id = ?",
                        (numero, cap, cap, mesa_id))
                    numero += 1
            self.con.execute(
                "UPDATE salon SET num_mesas ="
                " (SELECT COUNT(*) FROM mesa WHERE salon_id = ?)"
                " WHERE id = ?", (self.salon_id, self.salon_id))
        return True

    def _borrar(self):
        if not messagebox.askyesno(
            "Borrar salon",
            "Se borra el salon con todas sus mesas y lo que hubiera sentado"
            " en ellas.\n\n¿Seguro?", parent=self):
            return
        with self.con:
            self.con.execute("DELETE FROM salon WHERE id = ?",
                             (self.salon_id,))
        self.al_guardar()
        self.destroy()


class VentanaSegmento(_Dialogo):
    """Alta y edicion de un segmento: que agencias y a que salon."""

    def __init__(self, padre, con, evento_id, segmento_id, al_guardar):
        super().__init__(padre, "Segmento", 560, 700)
        self.con = con
        self.evento_id = evento_id
        self.segmento_id = segmento_id
        self.al_guardar = al_guardar

        seg = None
        if segmento_id:
            seg = con.execute("SELECT * FROM segmento WHERE id = ?",
                              (segmento_id,)).fetchone()

        self.nombre = self._campo(self, "Nombre del segmento",
                                  seg["nombre"] if seg else "")
        self.orden = self._campo(self, "Orden", seg["orden"] if seg else 1,
                                 120)

        # Destino: cada superficie (salon + zona) es una opcion.
        self.destinos = [("", "", "-- sin asignar --")]
        for s in con.execute(
            "SELECT * FROM salon WHERE evento_id = ? ORDER BY orden",
            (evento_id,)
        ):
            for z in con.execute(
                "SELECT DISTINCT zona FROM mesa WHERE salon_id = ?"
                " ORDER BY zona = '' DESC, zona", (s["id"],)
            ):
                etiqueta = s["nombre"] + (("  ·  " + z["zona"])
                                          if z["zona"] else "")
                self.destinos.append((s["id"], z["zona"], etiqueta))

        tk.Label(self, text="Se sienta en", bg=T("bg_content"),
                 fg=T("text_secondary"), font=("Segoe UI", 10),
                 anchor="w").pack(fill="x", padx=24, pady=(10, 2))
        self.destino = ctk.CTkOptionMenu(
            self, width=340, height=30,
            values=[d[2] for d in self.destinos])
        self.destino.pack(padx=24, anchor="w")
        actual = "-- sin asignar --"
        if segmento_id:
            fila = con.execute(
                "SELECT salon_id, zona FROM preferencia WHERE segmento_id = ?",
                (segmento_id,)).fetchone()
            if fila:
                for sid, zona, etiqueta in self.destinos:
                    if sid == fila["salon_id"] and zona == (fila["zona"] or ""):
                        actual = etiqueta
                        break
        self.destino.set(actual)

        reglas = []
        if segmento_id:
            reglas = list(con.execute(
                "SELECT tipo, valor FROM regla WHERE segmento_id = ?",
                (segmento_id,)))
        self.codigos = self._campo(
            self, "Codigos de agencia, separados por comas",
            ", ".join(r["valor"] for r in reglas if r["tipo"] == "codigo"))
        self.patrones = self._campo(
            self, "Textos del nombre de la agencia, separados por comas",
            ", ".join(r["valor"] for r in reglas if r["tipo"] == "nombre"))
        self.min_pax = self._campo(
            self, "O por tamano: a partir de cuantos comensales (grupos)."
                  " Vacio = no mirar el tamano",
            next((r["valor"] for r in reglas if r["tipo"] == "min_pax"), ""),
            120)

        self.por_defecto = ctk.CTkCheckBox(
            self, text="Recoge todas las agencias que no encajen en otro"
                       " segmento")
        self.por_defecto.pack(anchor="w", padx=24, pady=(14, 4))
        if any(r["tipo"] == "defecto" for r in reglas):
            self.por_defecto.select()

        self.excluir = ctk.CTkCheckBox(
            self, text="No se sienta aqui (se gestiona fuera del programa)")
        self.excluir.pack(anchor="w", padx=24, pady=4)
        if seg and seg["excluir"]:
            self.excluir.select()

        pie = tk.Frame(self, bg=T("bg_content"))
        pie.pack(fill="x", pady=16)
        ctk.CTkButton(pie, text="Guardar", width=140, height=32,
                      command=self._guardar).pack(side="left", padx=(24, 8))
        if segmento_id:
            ctk.CTkButton(pie, text="Borrar", width=120, height=32,
                          fg_color="#8a2f2c", hover_color="#a33b37",
                          command=self._borrar).pack(side="left")

    def _guardar(self):
        nombre = self.nombre.get().strip()
        if not nombre:
            messagebox.showwarning("Falta el nombre",
                                   "El segmento necesita un nombre.",
                                   parent=self)
            return
        elegido = self.destino.get()
        salon_id, zona = "", ""
        for sid, z, etiqueta in self.destinos:
            if etiqueta == elegido:
                salon_id, zona = sid, z
                break
        excluir = bool(self.excluir.get())
        if not excluir and not salon_id:
            messagebox.showwarning(
                "Sin sitio",
                "Elige donde se sienta, o marcalo como que no se gestiona"
                " aqui.", parent=self)
            return

        with self.con:
            if self.segmento_id is None:
                cur = self.con.execute(
                    "INSERT INTO segmento (evento_id, nombre, orden, excluir)"
                    " VALUES (?,?,?,?)",
                    (self.evento_id, nombre, self._entero(self.orden, 1),
                     1 if excluir else 0))
                self.segmento_id = cur.lastrowid
            else:
                self.con.execute(
                    "UPDATE segmento SET nombre = ?, orden = ?, excluir = ?"
                    " WHERE id = ?",
                    (nombre, self._entero(self.orden, 1),
                     1 if excluir else 0, self.segmento_id))

            self.con.execute("DELETE FROM preferencia WHERE segmento_id = ?",
                             (self.segmento_id,))
            if salon_id and not excluir:
                self.con.execute(
                    "INSERT INTO preferencia (segmento_id, salon_id, zona,"
                    " orden) VALUES (?,?,?,0)",
                    (self.segmento_id, salon_id, zona))

            self.con.execute("DELETE FROM regla WHERE segmento_id = ?",
                             (self.segmento_id,))
            filas = [(self.segmento_id, "codigo", c.strip())
                     for c in self.codigos.get().split(",") if c.strip()]
            filas += [(self.segmento_id, "nombre", p.strip().upper())
                      for p in self.patrones.get().split(",") if p.strip()]
            if self.min_pax.get().strip():
                filas.append((self.segmento_id, "min_pax",
                              str(self._entero(self.min_pax))))
            if self.por_defecto.get():
                # Solo puede haber un segmento que recoja el resto.
                self.con.execute(
                    "DELETE FROM regla WHERE tipo = 'defecto' AND segmento_id"
                    " IN (SELECT id FROM segmento WHERE evento_id = ?)",
                    (self.evento_id,))
                filas.append((self.segmento_id, "defecto", ""))
            self.con.executemany(
                "INSERT INTO regla (segmento_id, tipo, valor) VALUES (?,?,?)",
                filas)
        self.al_guardar()
        self.destroy()

    def _borrar(self):
        if not messagebox.askyesno(
            "Borrar segmento",
            "Las agencias de este segmento se quedaran sin salon asignado."
            "\n\n¿Seguro?", parent=self):
            return
        with self.con:
            self.con.execute("DELETE FROM segmento WHERE id = ?",
                             (self.segmento_id,))
        self.al_guardar()
        self.destroy()


class VentanaElegirPlantilla(_Dialogo):

    def __init__(self, padre, nombres, al_elegir):
        super().__init__(padre, "Cargar plantilla", 380, 200)
        tk.Label(self, text="Plantillas guardadas", bg=T("bg_content"),
                 fg=T("text_secondary"), font=("Segoe UI", 10),
                 anchor="w").pack(fill="x", padx=24, pady=(20, 6))
        self.menu = ctk.CTkOptionMenu(self, width=320, height=30,
                                      values=nombres)
        self.menu.pack(padx=24, anchor="w")
        ctk.CTkButton(self, text="Cargar", width=140, height=32,
                      command=lambda: self._elegir(al_elegir)).pack(pady=22)

    def _elegir(self, al_elegir):
        nombre = self.menu.get()
        self.destroy()
        al_elegir(nombre)
