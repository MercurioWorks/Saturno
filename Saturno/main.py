# -*- coding: utf-8 -*-
"""Arranque de Saturno."""
import logging
import os
import sys

import customtkinter as ctk

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import db                                                    # noqa: E402
from core import plantillas                                  # noqa: E402
from core.app import SaturnoApp                              # noqa: E402

logging.basicConfig(level=logging.INFO,
                    format="%(asctime)s %(levelname)s %(name)s: %(message)s")


def evento_de_trabajo(con):
    """Devuelve el evento activo; si no hay ninguno, crea uno vacio.

    Un evento nuevo no trae salones: se cargan desde una plantilla o se dan
    de alta en Configuracion. Aqui no hay nada de ningun hotel concreto.
    """
    fila = con.execute(
        "SELECT id FROM evento WHERE activo = 1 ORDER BY id DESC").fetchone()
    if fila:
        return fila["id"]
    return plantillas.crear_evento(con, "NUEVO EVENTO", "")


def main():
    db.crear_esquema()
    con = db.conectar()
    evento_id = evento_de_trabajo(con)

    ctk.set_appearance_mode("dark")
    app = SaturnoApp(con, evento_id)
    app.mainloop()
    con.close()


if __name__ == "__main__":
    main()
