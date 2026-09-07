# -*- coding: utf-8 -*-
"""Motor de asignacion de mesas.

Reglas que aplica, todas configurables desde la BD (aqui no hay ni un salon
ni una agencia escritos a mano):

  * Cada reserva cae en un segmento segun su codigo o nombre de agencia.
  * Cada segmento tiene una lista ordenada de salones: el preferente y los
    de desborde cuando el primero se llena.
  * Una mesa admite varias reservas hasta su capacidad, que puede estirarse
    hasta la capacidad maxima del salon (mas sillas).
  * Los grupos ocupan mesas consecutivas para quedar juntos.
  * Lo fijado por peticion no se toca nunca al recalcular.
"""
from collections import defaultdict


class Mesa:
    def __init__(self, fila):
        self.id = fila["id"]
        self.salon_id = fila["salon_id"]
        self.numero = fila["numero"]
        self.zona = fila["zona"] or ""    # parte del salon donde esta la mesa
        self.capacidad = fila["capacidad"]
        # Tope propio de la mesa; 0 significa "el que diga el salon".
        self.tope_propio = fila["capacidad_max"] or 0
        self.ocupadas = 0
        self.reservas = []

    @property
    def libres(self):
        return self.capacidad - self.ocupadas

    def tope(self, tope_salon):
        """Hasta donde puede estirarse esta mesa concreta."""
        return self.tope_propio or tope_salon

    def sentar(self, reserva_id, pax):
        self.ocupadas += pax
        self.reservas.append((reserva_id, pax))


def _pax(r):
    return (r["adultos"] or 0) + (r["ninos"] or 0)


def cargar_reglas(con, evento_id):
    """Devuelve (segmentos, destinos, excluidos).

    segmentos es una lista EN ORDEN: cada uno con sus condiciones. Gana el
    primero que encaje, asi que el orden de la pantalla de Configuracion es
    el que decide cuando una reserva podria caer en dos sitios.
    """
    condiciones = {}
    for f in con.execute(
        "SELECT s.id, s.orden, r.tipo, r.valor FROM segmento s"
        " LEFT JOIN regla r ON r.segmento_id = s.id"
        " WHERE s.evento_id = ? ORDER BY s.orden, s.id", (evento_id,)
    ):
        c = condiciones.setdefault(
            f["id"], {"id": f["id"], "orden": f["orden"], "codigos": set(),
                      "patrones": [], "min_pax": None, "defecto": False})
        if f["tipo"] == "codigo":
            c["codigos"].add(str(f["valor"]).strip())
        elif f["tipo"] == "nombre":
            c["patrones"].append(str(f["valor"]).strip().upper())
        elif f["tipo"] == "min_pax":
            try:
                c["min_pax"] = int(f["valor"])
            except (TypeError, ValueError):
                pass
        elif f["tipo"] == "defecto":
            c["defecto"] = True
    segmentos = sorted(condiciones.values(), key=lambda c: (c["orden"],
                                                            c["id"]))

    destinos = defaultdict(list)
    for f in con.execute(
        "SELECT p.segmento_id, p.salon_id, p.zona FROM preferencia p"
        " JOIN segmento s ON s.id = p.segmento_id WHERE s.evento_id = ?"
        " ORDER BY p.orden", (evento_id,)
    ):
        destinos[f["segmento_id"]].append((f["salon_id"], f["zona"] or ""))

    excluidos = {f["id"] for f in con.execute(
        "SELECT id FROM segmento WHERE evento_id = ? AND excluir = 1",
        (evento_id,))}
    return segmentos, destinos, excluidos


def segmento_de(reserva, segmentos):
    """En que segmento cae una reserva: gana el primero que encaje.

    Un segmento encaja por codigo de agencia, por un texto del nombre de la
    agencia, o por tamano de la reserva (a partir de x comensales, que es
    como se reconoce un grupo). El que recoge 'todo lo demas' va al final.
    """
    cod = str(reserva["cod_agencia"] or "").strip()
    nombre = str(reserva["agencia"] or "").upper()
    pax = (reserva["adultos"] or 0) + (reserva["ninos"] or 0)

    ultimo = None
    for c in segmentos:
        if c["defecto"]:
            ultimo = c["id"]
        if c["codigos"] and cod in c["codigos"]:
            return c["id"]
        if any(p and p in nombre for p in c["patrones"]):
            return c["id"]
        if c["min_pax"] is not None and pax >= c["min_pax"]:
            return c["id"]
    return ultimo


def asignar(con, evento_id, respetar_fijadas=True):
    """Reasigna todo el evento. Devuelve un resumen con lo que no ha cabido."""
    salones = {f["id"]: f for f in con.execute(
        "SELECT * FROM salon WHERE evento_id = ? ORDER BY orden", (evento_id,))}
    mesas_por_salon = defaultdict(list)
    mesas = {}
    for f in con.execute(
        "SELECT m.* FROM mesa m JOIN salon s ON s.id = m.salon_id"
        " WHERE s.evento_id = ? ORDER BY m.salon_id, m.numero", (evento_id,)
    ):
        m = Mesa(f)
        # Cada pasada parte del montaje de la mesa: 10 por lo general, 12 en
        # las mesas grandes. Si no, las sillas anadidas un dia para cuadrar
        # una peticion se quedarian puestas para siempre.
        m.capacidad = (f["capacidad_montaje"]
                       or salones[m.salon_id]["capacidad_base"])
        mesas[m.id] = m
        mesas_por_salon[m.salon_id].append(m)

    reservas = list(con.execute(
        "SELECT * FROM reserva WHERE evento_id = ? ORDER BY id", (evento_id,)))

    # 1. Las peticiones fijadas se colocan primero y se quedan donde estan.
    fijadas = set()
    if respetar_fijadas:
        for f in con.execute(
            "SELECT a.* FROM asignacion a JOIN reserva r ON r.id = a.reserva_id"
            " WHERE r.evento_id = ? AND a.fijada = 1", (evento_id,)
        ):
            m = mesas.get(f["mesa_id"])
            if m is not None:
                m.sentar(f["reserva_id"], f["pax"])
                # Una peticion puede dejar la mesa por encima del montaje base;
                # se respeta, es una decision ya tomada a mano.
                m.capacidad = max(m.capacidad, m.ocupadas)
                fijadas.add(f["reserva_id"])

    segmentos, destinos, excluidos = cargar_reglas(con, evento_id)

    # 2. El resto, de mayor a menor: los grupos y las reservas grandes primero,
    #    que son las que peor encajan si se dejan para el final.
    pendientes = [r for r in reservas if r["id"] not in fijadas]
    grupos = defaultdict(list)
    sueltas = []
    for r in pendientes:
        if (r["grupo"] or "").strip():
            grupos[r["grupo"].strip()].append(r)
        else:
            sueltas.append(r)

    nuevas = []
    sin_sitio = []

    excluidas = []

    def destinos_para(reserva):
        """Donde se sienta, como lista de (salon_id, zona).

        Manda lo que hayas decidido tu en Reparto. Si no hay decision, la
        regla de su segmento. Y si tampoco hay regla, se queda esperando en
        Reparto en vez de que el programa se lo invente.

        Devuelve None si su segmento no se gestiona aqui (el Imserso).
        """
        if reserva["salon_id"] and reserva["salon_id"] in salones:
            return [(reserva["salon_id"], reserva["zona_destino"] or "")]
        seg = segmento_de(reserva, segmentos)
        if seg is None:
            return []
        if seg in excluidos:
            return None
        sitios = destinos.get(seg) or []
        return [(i, z) for i, z in sitios if i in salones]

    # Cuantas mesas se han ampliado ya en cada salon. El montaje tiene un
    # limite fisico: solo unas pocas mesas admiten sillas de mas.
    ampliadas = defaultdict(int)

    def puede_ampliar(salon_id):
        return ampliadas[salon_id] < (salones[salon_id]["mesas_ampliables"] or 0)

    def mesas_de(salon_id, zona):
        """Mesas de esa parte del salon.

        La zona vacia es una zona mas, la principal: los directos del Palacio
        no se sientan en la Naya, que tiene sus propias agencias.
        """
        return [m for m in mesas_por_salon[salon_id] if m.zona == zona]

    # 2a. Grupos: bloque de mesas consecutivas y libres en el mismo salon.
    for nombre, miembros in sorted(grupos.items(),
                                   key=lambda kv: -sum(_pax(r) for r in kv[1])):
        total = sum(_pax(r) for r in miembros)
        colocado = False
        # Igual que con las reservas sueltas: primero se busca sitio con el
        # montaje normal en todos los salones; solo despues se anaden sillas.
        sitios = destinos_para(miembros[0])
        if sitios is None:
            excluidas.append(("grupo " + nombre, total))
            continue
        for estirar in (False, True):
            for salon_id, zona in sitios:
                tope = salones[salon_id]["capacidad_max"]
                bloque = _bloque_consecutivo(
                    mesas_de(salon_id, zona), total, tope if estirar else None)
                if bloque:
                    _repartir(bloque, miembros, tope if estirar else None, nuevas)
                    colocado = True
                    break
            if colocado:
                break
        if not colocado:
            sin_sitio.append(("grupo " + nombre, total))

    # 2b. Reservas sueltas, de mayor a menor.
    for r in sorted(sueltas, key=lambda x: -_pax(x)):
        pax = _pax(r)
        if pax <= 0:
            continue
        sitios = destinos_para(r)
        if sitios is None:
            excluidas.append((r["cliente"], pax))
            continue
        if not _sentar_reserva(r, pax, sitios, mesas_de, salones, nuevas,
                               puede_ampliar, ampliadas):
            sin_sitio.append((r["cliente"], pax))

    with con:
        borrar = ("DELETE FROM asignacion WHERE reserva_id IN"
                  " (SELECT id FROM reserva WHERE evento_id = ?)")
        if respetar_fijadas:
            borrar += " AND fijada = 0"
        con.execute(borrar, (evento_id,))
        con.executemany(
            "INSERT INTO asignacion (reserva_id, mesa_id, pax, fijada)"
            " VALUES (?,?,?,0)", nuevas)
        for m in mesas.values():
            con.execute("UPDATE mesa SET capacidad = ? WHERE id = ?",
                        (m.capacidad, m.id))

    return {
        "asignadas": len(nuevas),
        "fijadas": len(fijadas),
        "sin_sitio": sin_sitio,
        "pax_sin_sitio": sum(p for _, p in sin_sitio),
        "excluidas": excluidas,
        "pax_excluidas": sum(p for _, p in excluidas),
    }


def _sentar_reserva(reserva, pax, sitios, mesas_de, salones, nuevas,
                    puede_ampliar, ampliadas):
    """Coloca una reserva respetando el orden de salones de su segmento.

    Primera vuelta por todos los salones con el montaje previsto; solo si
    ninguno tiene sitio se da una segunda vuelta anadiendo sillas. Asi no se
    llena el primer salon a 12 mientras el siguiente esta vacio.
    """
    for fase in (0, 1, 2):
        for salon_id, zona in sitios:
            tope = salones[salon_id]["capacidad_max"]
            mesas = mesas_de(salon_id, zona)

            if fase == 0:
                # Hueco en una mesa ya montada. Se elige la que queda mas
                # llena, evitando dejar huecos de una sola plaza, que casi
                # nunca se rellenan (la mayoria de reservas son de dos).
                candidatas = [m for m in mesas if m.libres >= pax]
                if candidatas:
                    m = min(candidatas,
                            key=lambda x: (x.libres - pax == 1, x.libres))
                    m.sentar(reserva["id"], pax)
                    nuevas.append((reserva["id"], m.id, pax))
                    return True

            elif fase == 1:
                # Mesas seguidas sin tocar el montaje, para las reservas que
                # no caben en una sola mesa.
                bloque = _bloque_consecutivo(mesas, pax)
                if bloque:
                    _repartir(bloque, [reserva], None, nuevas)
                    return True

            else:
                # Ultimo recurso: anadir sillas, y solo en las pocas mesas que
                # el salon admite ampliar. Agotadas esas, la reserva se queda
                # sin sitio y la decide direccion.
                if not puede_ampliar(salon_id):
                    continue

                vacias = [m for m in mesas
                          if m.ocupadas == 0 and m.tope(tope) >= pax]
                if vacias:
                    m = vacias[0]
                    m.capacidad = max(m.capacidad, pax)
                    m.sentar(reserva["id"], pax)
                    nuevas.append((reserva["id"], m.id, pax))
                    ampliadas[salon_id] += 1
                    return True

                estirables = [m for m in mesas
                              if m.capacidad < m.tope(tope)
                              and m.ocupadas + pax <= m.tope(tope)]
                if estirables:
                    m = max(estirables, key=lambda x: x.ocupadas)
                    m.capacidad = m.ocupadas + pax
                    m.sentar(reserva["id"], pax)
                    nuevas.append((reserva["id"], m.id, pax))
                    ampliadas[salon_id] += 1
                    return True
    return False


def _bloque_consecutivo(mesas, pax, tope=None):
    """Tramo de mesas seguidas y vacias con sitio para pax comensales.

    Con tope=None cuenta las sillas ya montadas; con un tope, cuenta hasta
    donde podria estirarse cada mesa. El tramo nunca cruza de zona: la Naya
    esta arriba y el Palacio abajo, aunque la numeracion sea seguida.
    """
    for i, m in enumerate(mesas):
        if m.ocupadas:
            continue
        cabe, tramo = 0, []
        for m2 in mesas[i:]:
            if m2.ocupadas or m2.zona != m.zona:
                break
            tramo.append(m2)
            cabe += m2.capacidad if tope is None else m2.tope(tope)
            if cabe >= pax:
                return tramo
    return None


def _repartir(bloque, reservas, tope, nuevas):
    """Reparte las reservas de un grupo por las mesas del bloque. No parte una
    reserva salvo que ella sola no quepa en una mesa.

    Con tope=None no toca el montaje: reparte sobre las sillas que ya hay.
    Con un tope, anade sillas solo en las mesas donde de verdad hagan falta.
    """
    i = 0
    for r in sorted(reservas, key=lambda x: -_pax(x)):
        queda = _pax(r)
        while queda > 0 and i < len(bloque):
            m = bloque[i]
            techo = m.tope(tope) if tope else m.capacidad
            if queda > m.libres and techo > m.capacidad:
                m.capacidad = max(m.capacidad, min(techo, m.ocupadas + queda))
            if m.libres <= 0:
                i += 1
                continue
            hueco = min(m.libres, queda)
            m.sentar(r["id"], hueco)
            nuevas.append((r["id"], m.id, hueco))
            queda -= hueco
            if m.libres <= 0:
                i += 1
