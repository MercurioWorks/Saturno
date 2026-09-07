"""
Sistema de temas de Saturno.
Es el mismo de Mercurio, para que las dos aplicaciones se vean igual.
Uso:  from utils.theme import T
      bg = T("bg_content")
"""

DARK = {
    # Fondos
    "bg_main":       "#1e1e20",
    "bg_sidebar":    "#1a1a1c",
    "bg_content":    "#1c1c1e",
    "bg_header":     "#242426",
    "bg_surface":    "#323238",
    "bg_card":       "#242428",
    "bg_filter":     "#1e1e20",
    "bg_kpi":        "#18181b",
    "bg_row_par":    "#323238",
    "bg_row_impar":  "#242426",
    "bg_row_sel":    "#1a1500",
    "bg_row_hover":  "#2a1c00",
    "bg_row_hover2": "#2c2c38",  # hover neutro en listados (no dorado)
    "bg_search":     "#161618",
    "bg_popup":      "#161618",
    "bg_popup_row":  "#1a1a1c",

    # Bordes
    "border":        "#2e2e32",
    "border_gold":   "#2a1c00",
    "border_sep":    "#2a2a32",
    "border_card":   "#3e3e44",
    "border_active": "#3a2800",

    # Textos
    "text_primary":  "#e8e8ea",
    "text_secondary":"#9898b4",
    "text_dim":      "#858595",
    "text_disabled": "#4a4a56",

    # Acento activo en sidebar
    "active_bg":     "#1a1500",
    "active_border": "#3a2800",
    "active_hover":  "#2a2000",
    "hover_bg":      "#1e1e20",

    # KPI
    "kpi_sep":       "#2a2a32",
    "kpi_label":     "#757585",

    # Tabla
    "table_head_bg": "#242426",
    "table_head_fg": "#858595",
}

LIGHT = {
    # Fondos — blanco calido "ceramico" (porcelana), no blanco frio puro
    "bg_main":       "#f5f2ec",
    "bg_sidebar":    "#faf8f4",
    "bg_content":    "#f7f4ee",
    "bg_header":     "#faf8f4",
    "bg_surface":    "#efe9dd",
    "bg_card":       "#faf8f4",
    "bg_filter":     "#f2eee5",
    "bg_kpi":        "#fbf9f5",
    "bg_row_par":    "#f3efe7",
    "bg_row_impar":  "#faf8f4",
    "bg_row_sel":    "#fdf6e3",
    "bg_row_hover":  "#faeecb",
    "bg_row_hover2": "#f0eadd",  # hover neutro en listados (no dorado)
    "bg_search":     "#f7f4ee",
    "bg_popup":      "#faf8f4",
    "bg_popup_row":  "#f5f2ec",

    # Bordes
    "border":        "#ddd4c0",
    "border_gold":   "#f0e6c4",
    "border_sep":    "#e6dfd0",
    "border_card":   "#d4cab5",
    "border_active": "#dcc478",

    # Textos — negro calido, no azulado
    "text_primary":  "#28241d",
    "text_secondary":"#6b6355",
    "text_dim":      "#948c7a",
    "text_disabled": "#c0b7a3",

    # Acento activo en sidebar
    "active_bg":     "#fdf6e3",
    "active_border": "#dcc478",
    "active_hover":  "#f7e9bd",
    "hover_bg":      "#f2ede0",

    # KPI
    "kpi_sep":       "#e6dfd0",
    "kpi_label":     "#948c7a",

    # Tabla
    "table_head_bg": "#f5f2ec",
    "table_head_fg": "#8c8471",
}

_active = "dark"


def active() -> str:
    return _active


def toggle():
    global _active
    _active = "light" if _active == "dark" else "dark"


def set_theme(name: str):
    global _active
    assert name in ("dark", "light")
    _active = name


def T(key: str) -> str:
    palette = DARK if _active == "dark" else LIGHT
    return palette.get(key, "#ff00ff")   # magenta = clave desconocida


def is_dark() -> bool:
    return _active == "dark"
