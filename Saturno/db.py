# -*- coding: utf-8 -*-
"""Acceso a la base de datos de Saturno."""
import os
import sqlite3
import sys

APP_NAME = "Saturno"


def ruta_bd():
    """En desarrollo la BD vive en el proyecto; en el .exe, en %APPDATA%."""
    if getattr(sys, "frozen", False):
        base = os.path.join(os.environ.get("APPDATA", os.path.expanduser("~")), APP_NAME)
    else:
        base = os.path.dirname(os.path.abspath(__file__))
    os.makedirs(base, exist_ok=True)
    return os.path.join(base, "saturno.db")


ESQUEMA = """
CREATE TABLE IF NOT EXISTS evento (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    nombre      TEXT NOT NULL,
    fecha       TEXT NOT NULL,
    activo      INTEGER NOT NULL DEFAULT 1
);

CREATE TABLE IF NOT EXISTS salon (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    evento_id      INTEGER NOT NULL REFERENCES evento(id) ON DELETE CASCADE,
    nombre         TEXT NOT NULL,
    orden          INTEGER NOT NULL DEFAULT 0,
    capacidad_base INTEGER NOT NULL DEFAULT 10,
    capacidad_max  INTEGER NOT NULL DEFAULT 12,
    -- Precio del menu de ESTE salon. Es solo un dato informativo: no se
    -- cobran cambios de salon. Se guarda porque no todos los salones valen
    -- lo mismo, pero hoy no interviene en nada.
    precio_menu    REAL NOT NULL DEFAULT 0,
    -- Imagen del plano del salon, para colocar las mesas encima.
    plano_imagen   TEXT NOT NULL DEFAULT '',
    -- A 0 el salon existe pero no se reparte aqui: no sale como destino ni
    -- se sientan mesas en el, pero SI cuenta en el resumen y en el total de
    -- plazas del hotel. Es el caso de un salon que lleva otra persona.
    gestionado     INTEGER NOT NULL DEFAULT 1,
    -- Cuantas mesas del salon se pueden montar con sillas de mas. Es un
    -- limite fisico: en la gala de 2025 fueron 2 en Palacio y 1 en Bordon.
    -- A 0, el salon no estira nada y lo que no cabe se reporta.
    mesas_ampliables INTEGER NOT NULL DEFAULT 0,
    num_mesas      INTEGER NOT NULL DEFAULT 0
);

-- capacidad_montaje = sillas con las que se monta la mesa (10, o 12 en las
--                     mesas grandes). Es a lo que se vuelve en cada calculo.
-- capacidad     = sillas que tiene ahora mismo (montaje + alguna de mas)
-- capacidad_max = hasta donde se puede estirar ESA mesa; 0 = lo que diga el
--                 salon. No todas admiten 12: depende del hueco que tengan.
-- zona = parte del salon donde esta la mesa (la Naya es la parte de arriba
--        del Palacio). La numeracion de mesas es continua en todo el salon:
--        la Naya sigue a las del Palacio, 47 en adelante. Vacia si el salon
--        no esta dividido en partes.
CREATE TABLE IF NOT EXISTS mesa (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    salon_id      INTEGER NOT NULL REFERENCES salon(id) ON DELETE CASCADE,
    zona          TEXT NOT NULL DEFAULT '',
    numero        INTEGER NOT NULL,
    capacidad_montaje INTEGER NOT NULL DEFAULT 0,
    capacidad     INTEGER NOT NULL,
    capacidad_max INTEGER NOT NULL DEFAULT 0,
    -- Donde esta la mesa en el plano del salon, en pixeles del lienzo.
    -- A NULL todavia no se ha colocado y se dibuja en la rejilla de siempre.
    pos_x         REAL,
    pos_y         REAL,
    forma         TEXT NOT NULL DEFAULT 'redonda',
    UNIQUE (salon_id, numero)
);

-- excluir = este segmento no se sienta aqui (el Imserso va a Gregal, que no
--           se gestiona con este programa). No cuenta como gente sin sitio.
CREATE TABLE IF NOT EXISTS segmento (
    id        INTEGER PRIMARY KEY AUTOINCREMENT,
    evento_id INTEGER NOT NULL REFERENCES evento(id) ON DELETE CASCADE,
    nombre    TEXT NOT NULL,
    orden     INTEGER NOT NULL DEFAULT 0,
    excluir   INTEGER NOT NULL DEFAULT 0
);

-- Donde se sienta un segmento. zona vacia = cualquier mesa del salon; con
-- zona, solo esa parte (Traveltino, por ejemplo, va siempre a la Naya).
CREATE TABLE IF NOT EXISTS preferencia (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    segmento_id  INTEGER NOT NULL REFERENCES segmento(id) ON DELETE CASCADE,
    salon_id     INTEGER NOT NULL REFERENCES salon(id) ON DELETE CASCADE,
    zona         TEXT NOT NULL DEFAULT '',
    orden        INTEGER NOT NULL DEFAULT 0
);

-- Que codigo o nombre de agencia cae en que segmento.
CREATE TABLE IF NOT EXISTS regla (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    segmento_id  INTEGER NOT NULL REFERENCES segmento(id) ON DELETE CASCADE,
    tipo         TEXT NOT NULL,           -- 'codigo' | 'nombre' | 'defecto'
    valor        TEXT NOT NULL DEFAULT ''
);

CREATE TABLE IF NOT EXISTS reserva (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    evento_id    INTEGER NOT NULL REFERENCES evento(id) ON DELETE CASCADE,
    num_reserva  TEXT NOT NULL DEFAULT '',
    cod_agencia  TEXT NOT NULL DEFAULT '',
    agencia      TEXT NOT NULL DEFAULT '',
    cliente      TEXT NOT NULL DEFAULT '',
    adultos      INTEGER NOT NULL DEFAULT 0,
    ninos        INTEGER NOT NULL DEFAULT 0,
    grupo        TEXT NOT NULL DEFAULT '',
    externa      INTEGER NOT NULL DEFAULT 0,
    notas        TEXT NOT NULL DEFAULT '',
    -- Salon que le has dado tu en la pantalla de Reparto. Manda sobre
    -- cualquier regla: las reglas solo deciden lo que no has decidido.
    salon_id     INTEGER REFERENCES salon(id) ON DELETE SET NULL,
    zona_destino TEXT NOT NULL DEFAULT '',
    -- Apartada a mano: se ha sacado de su salon y espera en Reparto. Sin
    -- esto, una reserva que llego por una regla volvia a su salon en
    -- cuanto se devolvia, y no habia forma de sacarla de ahi.
    apartada     INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS asignacion (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    reserva_id INTEGER NOT NULL REFERENCES reserva(id) ON DELETE CASCADE,
    mesa_id    INTEGER NOT NULL REFERENCES mesa(id) ON DELETE CASCADE,
    pax        INTEGER NOT NULL DEFAULT 0,
    fijada     INTEGER NOT NULL DEFAULT 0,
    peticion   TEXT NOT NULL DEFAULT ''
);

CREATE INDEX IF NOT EXISTS ix_reserva_evento ON reserva(evento_id);
CREATE INDEX IF NOT EXISTS ix_asig_mesa ON asignacion(mesa_id);
CREATE INDEX IF NOT EXISTS ix_asig_reserva ON asignacion(reserva_id);
"""


def conectar():
    con = sqlite3.connect(ruta_bd())
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA foreign_keys = ON")
    return con


# Columnas anadidas despues de la primera version. Se aplican siempre, tanto
# a la BD de desarrollo como a la del .exe.
MIGRACIONES = [
    ("mesa", "capacidad_max", "INTEGER NOT NULL DEFAULT 0"),
    ("mesa", "zona", "TEXT NOT NULL DEFAULT ''"),
    ("preferencia", "zona", "TEXT NOT NULL DEFAULT ''"),
    ("segmento", "excluir", "INTEGER NOT NULL DEFAULT 0"),
    ("salon", "mesas_ampliables", "INTEGER NOT NULL DEFAULT 0"),
    ("mesa", "capacidad_montaje", "INTEGER NOT NULL DEFAULT 0"),
    ("salon", "precio_menu", "REAL NOT NULL DEFAULT 0"),
    ("mesa", "pos_x", "REAL"),
    ("mesa", "pos_y", "REAL"),
    ("mesa", "forma", "TEXT NOT NULL DEFAULT 'redonda'"),
    ("salon", "plano_imagen", "TEXT NOT NULL DEFAULT ''"),
    ("reserva", "salon_id", "INTEGER"),
    ("reserva", "zona_destino", "TEXT NOT NULL DEFAULT ''"),
    ("reserva", "apartada", "INTEGER NOT NULL DEFAULT 0"),
    ("salon", "gestionado", "INTEGER NOT NULL DEFAULT 1"),
]


def crear_esquema():
    con = conectar()
    with con:
        con.executescript(ESQUEMA)
        for tabla, columna, tipo in MIGRACIONES:
            existentes = {f["name"] for f in con.execute(
                "PRAGMA table_info(%s)" % tabla)}
            if columna not in existentes:
                con.execute("ALTER TABLE %s ADD COLUMN %s %s"
                            % (tabla, columna, tipo))
    con.close()
