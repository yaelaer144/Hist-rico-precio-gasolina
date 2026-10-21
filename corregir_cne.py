
from pathlib import Path

src = Path("monitor_ieps/src")
archivo = src / "actualizar_mensual.py"
codigo = archivo.read_text(encoding="utf-8")

url_vieja = (
    "URL='https://www.cne.gob.mx/da/"
    "Precios_promedio_diarios_y_mensuales_"
    "en_estaciones_de_servicio.xlsx'"
)

url_nueva = """from urllib.parse import quote

MESES = (
 'Enero','Febrero','Marzo','Abril',
 'Mayo','Junio','Julio','Agosto',
 'Septiembre','Octubre','Noviembre','Diciembre'
)

def url_cne(inicio):
 mes = MESES[inicio.month-1]
 carpeta = quote('DATOS ABIERTOS (GASOLINAS Y DIÉSEL)')
 nombre = (
  'Precios_promedio_diarios_y_mensuales_'
  'en_estaciones_de_servicio_'
  f'{mes.lower()}_{inicio.year}.xlsx'
 )
 return (
  f'https://www.cne.gob.mx/da/CNE/{carpeta}/'
  f'{inicio.year}/{mes}/{nombre}'
 )

URL = None"""

if url_vieja in codigo:
    codigo = codigo.replace(url_vieja, url_nueva, 1)
elif "def url_cne(inicio):" not in codigo:
    raise SystemExit("No se encontró la URL original")

inicio_viejo = (
    " inicio,fin=periodo(dt.date.fromisoformat(a.fecha))\n"
    " request=urllib.request.Request(URL"
)

inicio_nuevo = (
    " inicio,fin=periodo(dt.date.fromisoformat(a.fecha))\n"
    " global URL\n"
    " URL=url_cne(inicio)\n"
    ' print("CNE: descargando",URL,flush=True)\n'
    " request=urllib.request.Request(URL"
)

if inicio_viejo in codigo:
    codigo = codigo.replace(
        inicio_viejo, inicio_nuevo, 1
    )
elif " URL=url_cne(inicio)" not in codigo:
    raise SystemExit("No se encontró la consulta mensual")

lectura_vieja = (
    "dt.datetime.strptime("
    "str(row[0]).strip(),'%d/%m/%Y').date()"
)

if lectura_vieja in codigo:
    codigo = codigo.replace(
        lectura_vieja, "parsear_fecha(row[0])", 1
    )
elif "parsear_fecha(row[0])" not in codigo:
    raise SystemExit("No se encontró la lectura original")

if "def parsear_fecha(valor):" not in codigo:
    funcion = """def parsear_fecha(valor):
 if isinstance(valor,str):
  texto=valor.strip().split(' ')[0]
  for formato in ('%Y-%m-%d','%d/%m/%Y','%d-%m-%Y'):
   try:
    return dt.datetime.strptime(texto,formato).date()
   except ValueError:
    pass
 raise ValueError(f'Fecha CNE no reconocida: {valor!r}')

"""
    codigo = codigo.replace(
        "def periodo(fecha):",
        funcion + "def periodo(fecha):",
        1
    )

marca = " libro.close()\n viernes=[]"

if marca in codigo:
    codigo = codigo.replace(
        marca,
        """ libro.close()
 print(
  f'CNE: {len(precios)} precios encontrados '
  f'para {inicio} a {fin}',
  flush=True
 )
 viernes=[]""",
        1
    )

archivo.write_text(codigo, encoding="utf-8")

# Permitir repetir manualmente una consulta mensual.
calendario = src / "calendario_actualizacion.py"
texto = calendario.read_text(encoding="utf-8")

original = "if tarea['estado']!='pendiente':"
corregido = (
    "if tarea['estado']!='pendiente' "
    "or modo=='mensual':"
)

if original in texto:
    texto = texto.replace(original, corregido, 1)
elif corregido not in texto:
    raise SystemExit("Calendario original diferente")

calendario.write_text(texto, encoding="utf-8")

print("Corrección CNE aplicada correctamente")
