
"""Sincronización mensual automática de precios CNE."""

import calendar
import csv
import datetime as dt
import io
import json
import math
import os
import time
import urllib.request
from pathlib import Path
from urllib.parse import quote

import openpyxl

ROOT = Path("monitor_ieps")
MESES = (
    "Enero", "Febrero", "Marzo", "Abril",
    "Mayo", "Junio", "Julio", "Agosto",
    "Septiembre", "Octubre", "Noviembre", "Diciembre"
)
COMBUSTIBLES = ("regular", "premium", "diesel")


def periodo_anterior():
    hoy = dt.datetime.now(
        dt.timezone(dt.timedelta(hours=-6))
    ).date()
    fin = hoy.replace(day=1) - dt.timedelta(days=1)
    inicio = fin.replace(day=1)
    return inicio, fin


def construir_url(inicio):
    mes = MESES[inicio.month - 1]
    carpeta = quote(
        "DATOS ABIERTOS (GASOLINAS Y DIÉSEL)", safe=""
    )
    nombre = (
        "Precios_promedio_diarios_y_mensuales_"
        "en_estaciones_de_servicio_"
        f"{mes.lower()}_{inicio.year}.xlsx"
    )
    return (
        f"https://www.cne.gob.mx/da/CNE/{carpeta}/"
        f"{inicio.year}/{mes}/{nombre}"
    )


def descargar(url):
    for intento in range(1, 4):
        try:
            req = urllib.request.Request(
                url,
                headers={
                    "User-Agent": "Mozilla/5.0",
                    "Cache-Control": "no-cache"
                }
            )
            with urllib.request.urlopen(req, timeout=90) as r:
                data = r.read()
                print("CNE HTTP:", r.status, flush=True)

            if not data.startswith(b"PK"):
                raise ValueError("Respuesta no es XLSX")
            return data

        except Exception as exc:
            print(f"CNE intento {intento}/3: {exc}")
            if intento == 3:
                raise
            time.sleep(3 * intento)


def convertir_fecha(valor):
    if isinstance(valor, dt.datetime):
        return valor.date()
    if isinstance(valor, dt.date):
        return valor

    if isinstance(valor, str):
        for formato in (
            "%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y"
        ):
            try:
                return dt.datetime.strptime(
                    valor.strip()[:10], formato
                ).date()
            except ValueError:
                pass

    return None


def extraer(data, inicio, fin):
    wb = openpyxl.load_workbook(
        io.BytesIO(data),
        read_only=True,
        data_only=True
    )
    try:
        hoja = wb["Cuadro 1.1"]
        precios = {}

        for fila in hoja.iter_rows(
            min_row=5, max_col=4, values_only=True
        ):
            dia = convertir_fecha(fila[0])

            if dia is None or not inicio <= dia <= fin:
                continue

            for combustible, valor in zip(
                COMBUSTIBLES, fila[1:4]
            ):
                precio = float(valor)
                if not math.isfinite(precio) or not 5 < precio < 100:
                    raise ValueError(
                        f"Precio inválido: {dia}, {combustible}"
                    )
                precios[(dia.isoformat(), combustible)] = precio

        esperados = (fin - inicio).days * 3 + 3
        print(f"CNE precios encontrados: {len(precios)}/{esperados}")

        if len(precios) != esperados:
            raise ValueError(
                f"Mes incompleto: {len(precios)}/{esperados}"
            )

        return precios
    finally:
        wb.close()


def guardar(precios, url):
    master = ROOT / "data/master.json"
    filas = json.loads(master.read_text(encoding="utf-8"))

    registros = {
        (r["fecha"], r["combustible"]): r
        for r in filas
    }

    for clave, precio in precios.items():
        fila = registros.get(clave)

        if fila is None:
            fila = {
                "fecha": clave[0],
                "combustible": clave[1],
                "cuota": None,
                "neto": None,
                "estado_cuota": "Pendiente DOF"
            }
            registros[clave] = fila

        fila["precio"] = precio
        fila["url_precio"] = url

        cuota = fila.get("cuota")
        fila["neto"] = (
            round(precio - float(cuota), 6)
            if cuota is not None else None
        )

    resultado = sorted(
        registros.values(),
        key=lambda r: (r["fecha"], r["combustible"])
    )

    temporal = master.with_suffix(".tmp")
    temporal.write_text(
        json.dumps(resultado, ensure_ascii=False),
        encoding="utf-8"
    )
    os.replace(temporal, master)

    with (ROOT / "data/master.csv").open(
        "w", newline="", encoding="utf-8-sig"
    ) as f:
        columnas = list(
            dict.fromkeys(
                k for fila in resultado for k in fila
            )
        )
        escritor = csv.DictWriter(f, fieldnames=columnas)
        escritor.writeheader()
        escritor.writerows(resultado)


def main():
    inicio, fin = periodo_anterior()
    url = construir_url(inicio)

    print("Periodo CNE:", inicio, fin, flush=True)
    print("URL CNE:", url, flush=True)

    try:
        data = descargar(url)
        precios = extraer(data, inicio, fin)
    except Exception as exc:
        print(
            "CNE pendiente; se conserva el histórico:",
            str(exc), flush=True
        )
        return

    guardar(precios, url)

    print(
        "CNE ACTUALIZADA:",
        len(precios),
        "precios hasta",
        fin.isoformat(),
        flush=True
    )


if __name__ == "__main__":
    main()
