
"""Corrige automáticamente la descarga y carga mensual CNE."""
from pathlib import Path

src = Path("monitor_ieps/src")
mensual = src / "actualizar_mensual.py"
calendario = src / "calendario_actualizacion.py"

texto = mensual.read_text(encoding="utf-8")
entrada = "if __name__=='__main__':main()"

if entrada not in texto:
    raise RuntimeError("No se encontró el programa mensual original")

texto = texto.replace(entrada, "", 1)

texto += r'''

# Actualización automática de precios CNE.
from urllib.parse import quote
import re
import time

MESES_CNE = (
    "Enero", "Febrero", "Marzo", "Abril",
    "Mayo", "Junio", "Julio", "Agosto",
    "Septiembre", "Octubre", "Noviembre", "Diciembre"
)

def url_mensual_cne(inicio):
    mes = MESES_CNE[inicio.month - 1]
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

def descargar_excel_cne(url):
    for intento in range(1, 4):
        try:
            req = urllib.request.Request(
                url,
                headers={
                    "User-Agent": "Mozilla/5.0",
                    "Accept": "application/vnd.openxmlformats-"
                              "officedocument.spreadsheetml.sheet,*/*",
                    "Cache-Control": "no-cache"
                }
            )
            with urllib.request.urlopen(req, timeout=90) as resp:
                contenido = resp.read()
                print(
                    "CNE HTTP:", resp.status,
                    "bytes:", len(contenido),
                    "URL:", resp.url,
                    flush=True
                )
            if not contenido.startswith(b"PK"):
                raise ValueError("La respuesta no es un Excel XLSX")
            return contenido
        except Exception as exc:
            print(
                f"CNE intento {intento}/3: {exc}",
                flush=True
            )
            if intento == 3:
                raise
            time.sleep(3 * intento)

def leer_excel_cne(contenido, inicio, fin):
    libro = openpyxl.load_workbook(
        io.BytesIO(contenido),
        read_only=True,
        data_only=True
    )
    try:
        if "Cuadro 1.1" not in libro.sheetnames:
            raise ValueError(
                f"No existe Cuadro 1.1: {libro.sheetnames}"
            )

        hoja = libro["Cuadro 1.1"]
        precios = {}
        ultima_fecha = None

        for fila in hoja.iter_rows(
            min_row=5, max_col=4, values_only=True
        ):
            valor = fila[0]
            try:
                if isinstance(valor, dt.datetime):
                    dia = valor.date()
                elif isinstance(valor, dt.date):
                    dia = valor
                else:
                    cadena = str(valor).strip().split(" ")[0]
                    dia = None
                    for formato in (
                        "%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y"
                    ):
                        try:
                            dia = dt.datetime.strptime(
                                cadena, formato
                            ).date()
                            break
                        except ValueError:
                            continue

                    if dia is None:
                        continue

                ultima_fecha = (
                    max(ultima_fecha, dia)
                    if ultima_fecha else dia
                )

                if not inicio <= dia <= fin:
                    continue

                for combustible, valor_precio in zip(
                    ("regular", "premium", "diesel"),
                    fila[1:4]
                ):
                    precio = float(valor_precio)

                    if not math.isfinite(precio) or not 5 <= precio <= 100:
                        raise ValueError(
                            f"Precio inválido: {dia} {combustible}"
                        )

                    precios[(dia.isoformat(), combustible)] = precio

            except (TypeError, ValueError) as exc:
                if (
                    isinstance(valor, (dt.date, dt.datetime))
                    or re.match(r"^\d{4}-\d\d-\d\d$", str(valor))
                ):
                    raise ValueError(
                        f"Fila CNE inválida: {valor}: {exc}"
                    ) from exc

        esperados = ((fin - inicio).days + 1) * 3

        print(
            f"CNE última fecha del Excel: {ultima_fecha}",
            f"Precios: {len(precios)}/{esperados}",
            flush=True
        )

        if len(precios) != esperados:
            raise ValueError(
                f"CNE incompleta para {inicio} a {fin}: "
                f"{len(precios)}/{esperados}"
            )

        return precios
    finally:
        libro.close()

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--fecha", default=dt.date.today().isoformat()
    )
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    inicio, fin = periodo(
        dt.date.fromisoformat(args.fecha)
    )

    url = url_mensual_cne(inicio)
    print("CNE URL mensual:", url, flush=True)

    contenido = descargar_excel_cne(url)
    precios = leer_excel_cne(contenido, inicio, fin)

    archivo = ROOT / "data/master.json"
    base = json.loads(
        archivo.read_text(encoding="utf-8")
    )

    registros = {
        (r["fecha"], r["combustible"]): r
        for r in base
    }

    faltantes = set(precios) - set(registros)

    if faltantes:
        raise ValueError(
            "Faltan registros fiscales en la base: "
            + str(sorted(faltantes)[:5])
        )

    for clave, precio in precios.items():
        fila = registros[clave]
        fila["precio"] = precio
        fila["url_precio"] = url
        fila["fuente"] = (
            "CNE (precio); datos fiscales conservados"
        )

        cuota = fila.get("cuota")
        fila["neto"] = (
            round(precio - float(cuota), 6)
            if cuota is not None else None
        )

    reporte = {
        "periodo": inicio.strftime("%Y-%m"),
        "inicio": inicio.isoformat(),
        "fin": fin.isoformat(),
        "filas_actualizadas": len(precios),
        "fuente_precio": url,
        "estado": "CNE: cobertura diaria completa"
    }

    if args.dry_run:
        print(json.dumps(reporte, ensure_ascii=False, indent=2))
        return

    filas = sorted(
        registros.values(),
        key=lambda r: (r["fecha"], r["combustible"])
    )

    temporal = archivo.with_suffix(".tmp")
    temporal.write_text(
        json.dumps(filas, ensure_ascii=False),
        encoding="utf-8"
    )
    os.replace(temporal, archivo)

    with (ROOT / "data/master.csv").open(
        "w", newline="", encoding="utf-8-sig"
    ) as salida:
        columnas = list(
            dict.fromkeys(c for f in filas for c in f)
        )
        escritor = csv.DictWriter(
            salida, fieldnames=columnas
        )
        escritor.writeheader()
        escritor.writerows(filas)

    (ROOT / "data/actualizacion_mensual.json").write_text(
        json.dumps(reporte, ensure_ascii=False, indent=2),
        encoding="utf-8"
    )

    (ROOT / "raw").mkdir(exist_ok=True)
    (ROOT / "raw/precios.xlsx").write_bytes(contenido)

    print(
        "CNE: PRECIOS INCORPORADOS",
        len(precios), "hasta", fin,
        flush=True
    )

if __name__ == "__main__":
    main()
'''

mensual.write_text(texto, encoding="utf-8")

# Recuperación de tareas mensuales y reintentos.
codigo = calendario.read_text(encoding="utf-8")

codigo = codigo.replace(
    "if hoy.day==10:",
    "if hoy.day==10 or (15 <= hoy.day <= 27):",
    1
)

codigo = codigo.replace(
    "if tarea['estado']!='pendiente':",
    "if tarea['estado']!='pendiente' or modo=='mensual':",
    1
)

calendario.write_text(codigo, encoding="utf-8")

print(
    "CNE automático: corrección aplicada; "
    "cuotas y funciones originales conservadas."
)


# Adaptar la prueba al estado real de la base.
prueba = Path("monitor_ieps/tests/test_reintentos.py")
codigo = prueba.read_text(encoding="utf-8")

inicio = (
    "   antes=(root/'data/master.json').read_bytes()"
)
reemplazo = (
    "   antes=(root/'data/master.json').read_bytes()\n"
    "   fecha_anterior=json.loads("
    "(root/'data/estado_actualizacion.json').read_text()"
    ")['ultima_actualizacion_datos']"
)

if inicio in codigo:
    codigo = codigo.replace(inicio, reemplazo, 1)

    objetivo = (
        "self.assertEqual("
        "e['ultima_actualizacion_datos'],'2026-10-09')"
    )

    posicion = codigo.index(
        "class FallaConsulta"
    )
    anterior = codigo[:posicion]
    posterior = codigo[posicion:].replace(
        objetivo,
        "self.assertEqual("
        "e['ultima_actualizacion_datos'],fecha_anterior)",
        1
    )
    codigo = anterior + posterior

    prueba.write_text(codigo, encoding="utf-8")
    print("Prueba de conservación del estado corregida")

elif "fecha_anterior=json.loads(" in codigo:
    print("La prueba ya fue corregida")

else:
    raise RuntimeError(
        "No se encontró la estructura esperada de la prueba"
    )

