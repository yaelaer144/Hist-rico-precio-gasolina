
"""Actualiza automáticamente las fechas visibles del dashboard IEPS."""

from pathlib import Path
from collections import defaultdict
import datetime as dt
import json
import re

ROOT = Path("monitor_ieps")
DATA = ROOT / "data/master.json"
HTML = ROOT / "index.html"
COMBUSTIBLES = {"regular", "premium", "diesel"}

MESES = (
    "enero", "febrero", "marzo", "abril",
    "mayo", "junio", "julio", "agosto",
    "septiembre", "octubre", "noviembre", "diciembre"
)


def texto_fecha(fecha):
    dia = dt.date.fromisoformat(fecha)
    return (
        f"{dia.day} de {MESES[dia.month - 1]} "
        f"de {dia.year}"
    )


def main():
    filas = json.loads(DATA.read_text(encoding="utf-8"))
    precios_por_fecha = defaultdict(set)
    ultima_cuota = None

    for fila in filas:
        fecha = fila.get("fecha")
        combustible = fila.get("combustible")

        if not fecha or combustible not in COMBUSTIBLES:
            continue

        if fila.get("precio") is not None:
            precios_por_fecha[fecha].add(combustible)

        if fila.get("cuota") is not None:
            ultima_cuota = max(ultima_cuota or fecha, fecha)

    completas = [
        fecha
        for fecha, combustibles in precios_por_fecha.items()
        if combustibles == COMBUSTIBLES
    ]

    if not completas:
        raise RuntimeError(
            "No existen fechas con precios de los tres combustibles"
        )

    ultimo_precio = max(completas)
    html = HTML.read_text(encoding="utf-8")

    # Actualizar el aviso de precios.
    patron = (
        r"Los precios disponibles terminan el\s*"
        r"<b>.*?</b>\."
    )

    nuevo = (
        "Los precios disponibles terminan el "
        f"<b>{texto_fecha(ultimo_precio)}</b>."
    )

    html, cambios = re.subn(
        patron, nuevo, html, count=1, flags=re.I
    )

    if cambios != 1:
        raise RuntimeError(
            "No se encontró el aviso de precios"
        )

    # Actualizar la fecha de las cuotas.
    if ultima_cuota:
        nuevo_fiscal = (
            "Las cuotas disponibles llegan hasta el "
            f"<b>{texto_fecha(ultima_cuota)}</b>."
        )

        for patron in (
            r"El Excel contiene cuotas hasta el corte del\s*"
            r"<b>.*?</b>\.",
            r"Las cuotas disponibles llegan hasta el\s*"
            r"<b>.*?</b>\."
        ):
            html = re.sub(
                patron, nuevo_fiscal, html,
                count=1, flags=re.I
            )

    # Mostrar inicialmente el último día con precios completos.
    html, cambios = re.subn(
        r'(<input\s+id="end"\s+type="date"\s+value=")'
        r'[^"]+("\s+min=)',
        lambda m: m.group(1) + ultimo_precio + m.group(2),
        html,
        count=1
    )

    if cambios != 1:
        raise RuntimeError(
            "No se encontró el selector final de fechas"
        )

    # Comprobar que la fecha realmente existe en el HTML.
    if ultimo_precio not in html:
        raise RuntimeError(
            "El HTML no contiene la última fecha de precios"
        )

    HTML.write_text(html, encoding="utf-8")

    print(
        "CNE: última fecha completa de precios:",
        ultimo_precio
    )
    print("DOF: última fecha con cuota:", ultima_cuota)
    print("HTML actualizado automáticamente.")


if __name__ == "__main__":
    main()
