# Saturno

Asignación de mesas para galas de hotel: comida de Navidad, Nochevieja y
cualquier evento en el que haya que sentar a cientos de comensales repartidos
por varios salones.

Sustituye la hoja de cálculo que se rehacía cada año a mano.

## Cómo funciona

El trabajo se divide en dos decisiones, y solo una es automática:

1. **A qué salón va cada reserva.** La decide una persona, en la pantalla de
   *Reparto*. Solo se automatiza lo que nunca cambia (la venta directa a su
   salón, las agencias inglesas al suyo); el resto se reparte a mano porque
   cambia cada año y depende de criterios que no están en ningún dato.
2. **En qué mesa concreta dentro de ese salón.** Esto sí es automático: se
   llenan las mesas sin partir reservas, dejando juntos a los grupos y sin
   dejar huecos sueltos.

## Pantallas

- **Reparto** — un tablero con una columna por salón y otra con lo que queda
  por decidir. Los bloques se mueven de columna a columna; devolver algo es
  el mismo gesto que mandarlo.
- **Plano de mesas** — las mesas de cada salón con quién está sentado, en dos
  vistas: fichas (RSV, nombre, adultos y niños) y tira de plazas, más densa,
  para repasar huecos. Las reservas se arrastran de una mesa a otra.
- **Reservas** — el listado completo, con buscador y alta de reservas
  externas (gente no alojada, que no viene en el listado del sistema).
- **Salones** — dónde está cada mesa dentro del salón, con la posibilidad de
  poner el plano del salón de fondo.
- **Configuración** — salones, montaje y reglas. Aquí vive todo lo particular
  de un hotel: en el código no hay ni un salón ni una agencia.

## Para otro hotel

Un evento nuevo nace vacío. La configuración de un hotel concreto se guarda
como plantilla en `saturno/plantillas/*.json` y se carga desde
Configuración, así que el programa no lleva nada de ningún hotel dentro.

## Datos

Las reservas se importan del listado que saca el PMS (.xls o .xlsx). El
importador no asume posiciones de columna: busca la cabecera por sus rótulos
y admite sinónimos.

La base de datos (`saturno.db`) **no se sube al repositorio**: lleva nombres
y apellidos de clientes reales. En desarrollo vive junto al código; en el
ejecutable, en `%APPDATA%\Saturno`.

## Ejecutar

```
python main.py
```

Necesita Python 3, `customtkinter`, `openpyxl`, `xlrd` (para los .xls que
salen del PMS) y `pillow`.
