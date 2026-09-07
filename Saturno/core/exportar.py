# -*- coding: utf-8 -*-
"""Exporta la asignacion a Excel con la disposicion de la hoja de siempre:
un panel de totales por salon y, debajo, la rejilla de mesas con sus
reservas (RSV / NOMBRE / AD / N) en bandas de cinco mesas.
"""
from openpyxl import Workbook
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side

MESAS_POR_BANDA = 5
ANCHO_BLOQUE = 6            # RSV, NOMBRE, AD, N, TOT, separador

_TITULO = Font(bold=True, size=14)
_CAB = Font(bold=True, color="FFFFFF")
_NEGRITA = Font(bold=True)
_RELLENO_SALON = PatternFill("solid", fgColor="1F4E79")
_RELLENO_ZONA = PatternFill("solid", fgColor="8EA9DB")
_RELLENO_MESA = PatternFill("solid", fgColor="D9E1F2")
_CENTRO = Alignment(horizontal="center", vertical="center")
_FINO = Side(style="thin", color="B0B0B0")
_BORDE = Border(left=_FINO, right=_FINO, top=_FINO, bottom=_FINO)


def _datos(con, evento_id):
    salones = list(con.execute(
        "SELECT * FROM salon WHERE evento_id = ? ORDER BY orden", (evento_id,)))
    mesas = {}
    for s in salones:
        mesas[s["id"]] = list(con.execute(
            "SELECT * FROM mesa WHERE salon_id = ? ORDER BY numero", (s["id"],)))
    ocupantes = {}
    for f in con.execute(
        "SELECT a.mesa_id, a.pax, a.fijada, r.num_reserva, r.cliente,"
        "       r.adultos, r.ninos, r.grupo"
        " FROM asignacion a JOIN reserva r ON r.id = a.reserva_id"
        " JOIN mesa m ON m.id = a.mesa_id JOIN salon s ON s.id = m.salon_id"
        " WHERE s.evento_id = ? ORDER BY a.id", (evento_id,)
    ):
        ocupantes.setdefault(f["mesa_id"], []).append(f)
    return salones, mesas, ocupantes


def _reparto(fila, pax):
    """Reparte los pax sentados de una reserva entre adultos y ninos.

    Una reserva partida en varias mesas no lleva sus ninos en todas: se
    colocan primero los adultos y los ninos caen en la ultima mesa.
    """
    adultos = min(pax, fila["adultos"])
    return adultos, pax - adultos


def _zonas(mesas):
    """Zonas del salon, en el orden en que aparecen sus mesas."""
    vistas = []
    for m in mesas:
        z = m["zona"] or ""
        if z not in vistas:
            vistas.append(z)
    return vistas


def _rotulo(hoja, fila, texto, fuente, relleno):
    c = hoja.cell(row=fila, column=1, value=texto)
    c.font, c.fill, c.alignment = fuente, relleno, _CENTRO
    hoja.merge_cells(start_row=fila, start_column=1, end_row=fila,
                     end_column=MESAS_POR_BANDA * ANCHO_BLOQUE)
    return fila + 1


def _pintar_mesa(hoja, fila, col, mesa, ocupantes, alto):
    """Pinta un bloque de mesa y devuelve sus totales de adultos y ninos."""
    c = hoja.cell(row=fila, column=col, value="MESA %d" % mesa["numero"])
    c.font, c.fill, c.alignment = _NEGRITA, _RELLENO_MESA, _CENTRO
    hoja.merge_cells(start_row=fila, start_column=col,
                     end_row=fila, end_column=col + 2)
    c = hoja.cell(row=fila, column=col + 3, value=mesa["capacidad"])
    c.font, c.fill, c.alignment = _NEGRITA, _RELLENO_MESA, _CENTRO

    for k, texto in enumerate(("RSV", "NOMBRE", "AD", "N")):
        c = hoja.cell(row=fila + 1, column=col + k, value=texto)
        c.font, c.alignment, c.border = _NEGRITA, _CENTRO, _BORDE

    ad = ni = 0
    for k, o in enumerate(ocupantes.get(mesa["id"], [])):
        a, n = _reparto(o, o["pax"])
        ad += a
        ni += n
        nombre = o["grupo"] or o["cliente"]
        if o["fijada"]:
            nombre += "  (P)"                     # peticion fijada a mano
        for x, v in enumerate([o["num_reserva"], nombre, a or "", n or ""]):
            c = hoja.cell(row=fila + 2 + k, column=col + x, value=v)
            c.border = _BORDE
            if x >= 2:
                c.alignment = _CENTRO

    for x, v in enumerate(["TOTAL", "", ad, ni]):
        c = hoja.cell(row=fila + 2 + alto, column=col + x, value=v)
        c.font, c.border = _NEGRITA, _BORDE
        if x >= 2:
            c.alignment = _CENTRO
    return ad, ni


def _rejilla(hoja, fila, lista, ocupantes):
    """Pinta las mesas de una zona en bandas y devuelve la fila siguiente."""
    for inicio in range(0, len(lista), MESAS_POR_BANDA):
        banda = lista[inicio:inicio + MESAS_POR_BANDA]
        alto = max((len(ocupantes.get(m["id"], [])) for m in banda), default=0)
        for j, mesa in enumerate(banda):
            _pintar_mesa(hoja, fila, 1 + j * ANCHO_BLOQUE, mesa, ocupantes, alto)
        fila += alto + 4
    return fila


def exportar(con, evento_id, ruta):
    evento = con.execute("SELECT * FROM evento WHERE id = ?",
                         (evento_id,)).fetchone()
    salones, mesas, ocupantes = _datos(con, evento_id)

    wb = Workbook()
    hoja = wb.active
    hoja.title = "MESAS"
    hoja["A1"] = evento["nombre"]
    hoja["A1"].font = _TITULO
    fila = 3

    # --- Panel de totales, con una linea por zona -------------------------
    for i, texto in enumerate(["SALON", "MESAS", "PLAZAS", "AD", "N", "TOT",
                               "REST"]):
        c = hoja.cell(row=fila, column=1 + i, value=texto)
        c.font, c.fill, c.alignment, c.border = (_CAB, _RELLENO_SALON,
                                                 _CENTRO, _BORDE)
    fila += 1

    def _linea(nombre, lista, negrita=False):
        plazas = sum(m["capacidad"] for m in lista)
        ad = ni = 0
        for m in lista:
            for o in ocupantes.get(m["id"], []):
                a, n = _reparto(o, o["pax"])
                ad += a
                ni += n
        valores = [nombre, len(lista), plazas, ad, ni, ad + ni,
                   plazas - ad - ni]
        for i, v in enumerate(valores):
            c = hoja.cell(row=fila, column=1 + i, value=v)
            c.border = _BORDE
            if negrita:
                c.font = _NEGRITA
            if i:
                c.alignment = _CENTRO
        return plazas, ad, ni

    todas = []
    for s in salones:
        lista = mesas[s["id"]]
        todas += lista
        _linea(s["nombre"], lista, negrita=True)
        fila += 1
        zonas = _zonas(lista)
        if len(zonas) > 1:
            for zona in zonas:
                _linea("    " + (zona or "PRINCIPAL"),
                       [m for m in lista if (m["zona"] or "") == zona])
                fila += 1
    _linea("TOTAL", todas, negrita=True)
    fila += 3

    # --- Rejilla de mesas -------------------------------------------------
    for s in salones:
        fila = _rotulo(hoja, fila, s["nombre"], _CAB, _RELLENO_SALON)
        lista = mesas[s["id"]]
        for zona in _zonas(lista):
            if zona:
                fila = _rotulo(hoja, fila, zona, _NEGRITA, _RELLENO_ZONA)
            fila = _rejilla(
                hoja, fila, [m for m in lista if (m["zona"] or "") == zona],
                ocupantes)
        fila += 1

    for j in range(MESAS_POR_BANDA):
        base = 1 + j * ANCHO_BLOQUE
        ancho = {0: 10, 1: 32, 2: 5, 3: 5, 5: 2}
        for extra, medida in ancho.items():
            letra = hoja.cell(row=1, column=base + extra).column_letter
            hoja.column_dimensions[letra].width = medida

    wb.save(ruta)
    return ruta
