# -*- coding: utf-8 -*-
"""Importa el listado de reservas que sale del sistema (.xls o .xlsx).

No asume posiciones fijas de columna: localiza la fila de cabecera buscando
los rotulos conocidos y admite sinonimos, para que sirva con listados de
otros hoteles o de otras versiones del PMS.
"""
import os
import re
import unicodedata

# rotulo normalizado -> campo interno
SINONIMOS = {
    "reserva": "num_reserva", "nreserva": "num_reserva", "numreserva": "num_reserva",
    "localizador": "num_reserva", "bono": "num_reserva",
    "agen": "cod_agencia", "agencia": "cod_agencia", "codagencia": "cod_agencia",
    "codigoagencia": "cod_agencia", "cod": "cod_agencia",
    "nombredelaagencia": "agencia", "nombreagencia": "agencia", "touroperador": "agencia",
    "nombredelcliente": "cliente", "cliente": "cliente", "nombre": "cliente",
    "titular": "cliente", "nombreyapellidos": "cliente",
    "ad": "adultos", "adultos": "adultos", "adl": "adultos", "pax": "adultos",
    "ni": "ninos", "ninos": "ninos", "nins": "ninos", "chd": "ninos", "n": "ninos",
    "fentra": "entrada", "fentrada": "entrada", "llegada": "entrada",
    "fsalida": "salida", "salida": "salida",
}

OBLIGATORIOS = {"cliente", "adultos"}


def _norm(v):
    """Minusculas, sin acentos y sin puntuacion, para comparar rotulos."""
    s = str(v or "").strip().lower()
    s = unicodedata.normalize("NFKD", s)
    s = "".join(c for c in s if not unicodedata.combining(c))
    return re.sub(r"[^a-z0-9]", "", s)


def _texto(v):
    """Las celdas numericas de xlrd llegan como float: 793579.0 -> '793579'."""
    if v is None:
        return ""
    if isinstance(v, float) and v == int(v):
        return str(int(v))
    return str(v).strip()


def _entero(v):
    try:
        return int(float(str(v).replace(",", ".")))
    except (TypeError, ValueError):
        return 0


def _leer_filas(ruta):
    """Devuelve una lista de listas con el contenido crudo de la hoja."""
    ext = os.path.splitext(ruta)[1].lower()
    if ext in (".xlsx", ".xlsm"):
        import openpyxl
        wb = openpyxl.load_workbook(ruta, data_only=True, read_only=True)
        hoja = wb.active
        return [list(f) for f in hoja.iter_rows(values_only=True)]
    import xlrd
    libro = xlrd.open_workbook(ruta)
    hoja = libro.sheet_by_index(0)
    return [[hoja.cell_value(r, c) for c in range(hoja.ncols)] for r in range(hoja.nrows)]


def _localizar_cabecera(filas):
    """Busca en las primeras filas la que mas rotulos conocidos contiene."""
    mejor, mejor_mapa, mejor_n = None, None, 0
    for i, fila in enumerate(filas[:25]):
        mapa = {}
        for col, celda in enumerate(fila):
            campo = SINONIMOS.get(_norm(celda))
            if campo and campo not in mapa:
                mapa[campo] = col
        if len(mapa) > mejor_n:
            mejor, mejor_mapa, mejor_n = i, mapa, len(mapa)
    if mejor is None or not OBLIGATORIOS.issubset(mejor_mapa or {}):
        return None, None
    return mejor, mejor_mapa


def leer_listado(ruta):
    """Lee el fichero y devuelve (reservas, avisos).

    Cada reserva es un dict con num_reserva, cod_agencia, agencia, cliente,
    adultos y ninos. No toca la base de datos.
    """
    filas = _leer_filas(ruta)
    i_cab, mapa = _localizar_cabecera(filas)
    if mapa is None:
        raise ValueError(
            "No encuentro la fila de cabecera. Debe tener al menos las columnas "
            "de nombre del cliente y de adultos."
        )

    avisos = []
    for campo in ("num_reserva", "cod_agencia", "agencia", "ninos"):
        if campo not in mapa:
            avisos.append("El listado no trae la columna '%s'." % campo)

    reservas = []
    for fila in filas[i_cab + 1:]:
        def val(campo):
            col = mapa.get(campo)
            return fila[col] if col is not None and col < len(fila) else None

        adultos, ninos = _entero(val("adultos")), _entero(val("ninos"))
        if adultos + ninos <= 0:
            continue                      # filas de totales, separadores o vacias
        cliente = _texto(val("cliente"))
        agencia = _texto(val("agencia"))
        if not cliente:
            # Algunas reservas dejan vacio el nombre del cliente y lo dejan
            # en la columna de la agencia. Preferimos un nombre a nada.
            cliente = agencia
        if _norm(cliente) in ("", "total", "totales", "totalgeneral"):
            continue
        reservas.append({
            "num_reserva": _texto(val("num_reserva")),
            "cod_agencia": _texto(val("cod_agencia")),
            "agencia": agencia,
            "cliente": cliente,
            "adultos": adultos,
            "ninos": ninos,
        })
    return reservas, avisos


def importar(con, evento_id, ruta, reemplazar=True):
    """Vuelca el listado en la BD. Devuelve (n_reservas, pax, avisos).

    Con reemplazar=True borra las reservas importadas del evento (las dadas de
    alta a mano, las externas, se respetan siempre).
    """
    reservas, avisos = leer_listado(ruta)
    with con:
        if reemplazar:
            con.execute(
                "DELETE FROM reserva WHERE evento_id = ? AND externa = 0", (evento_id,)
            )
        con.executemany(
            "INSERT INTO reserva (evento_id, num_reserva, cod_agencia, agencia,"
            " cliente, adultos, ninos) VALUES (?,?,?,?,?,?,?)",
            [(evento_id, r["num_reserva"], r["cod_agencia"], r["agencia"],
              r["cliente"], r["adultos"], r["ninos"]) for r in reservas],
        )
    pax = sum(r["adultos"] + r["ninos"] for r in reservas)
    return len(reservas), pax, avisos
