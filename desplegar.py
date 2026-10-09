"""Extrae el proyecto en Actions y guarda todos los datos en un único ZIP."""
from pathlib import Path,PurePosixPath
import argparse,hashlib,os,shutil,stat,zipfile
ROOT=Path(__file__).resolve().parent
BASE=ROOT/'monitor_ieps_base.zip'
PROJECT=ROOT/'monitor_ieps'
def extraer():
 with zipfile.ZipFile(BASE) as z:
  for item in z.infolist():
   path=PurePosixPath(item.filename)
   if path.is_absolute() or '..' in path.parts or not path.parts or path.parts[0]!='monitor_ieps' or '\\' in item.filename:raise ValueError('Ruta inválida en el paquete')
   if stat.S_ISLNK(item.external_attr>>16):raise ValueError('No se permiten enlaces simbólicos')
  if sum(i.file_size for i in z.infolist())>512*1024*1024:raise ValueError('Paquete demasiado grande')
  z.extractall(ROOT)
 for p in ['src/ejecutar_actualizacion.py','data/master.json','requirements.txt']:
  if not (PROJECT/p).is_file():raise ValueError('Falta archivo requerido: '+p)
 print('Proyecto e histórico preparados por Actions.')
def guardar():
 files=[p for p in sorted(PROJECT.rglob('*')) if p.is_file() and '__pycache__' not in p.parts and 'diagnostico_presto' not in p.parts and p.suffix not in ('.tmp','.pyc')]
 current={str(PurePosixPath('monitor_ieps')/p.relative_to(PROJECT)):p for p in files}
 changed=False
 with zipfile.ZipFile(BASE) as z:
  old={i.filename:i for i in z.infolist() if not i.is_dir()}
  changed=set(old)!=set(current)
  if not changed:
   for name,p in current.items():
    if hashlib.sha256(z.read(name)).digest()!=hashlib.sha256(p.read_bytes()).digest():changed=True;break
 if changed:
  tmp=BASE.with_suffix('.tmp')
  with zipfile.ZipFile(tmp,'w',zipfile.ZIP_DEFLATED) as z:
   for name,p in current.items():z.write(p,name)
  with zipfile.ZipFile(tmp) as z:
   if z.testzip():raise ValueError('Paquete generado no verificado')
  os.replace(tmp,BASE)
 shutil.copyfile(PROJECT/'index.html',ROOT/'index.html')
 print('Dashboard listo; paquete '+('actualizado.' if changed else 'sin cambios.'))
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('operacion',choices=['extraer','guardar']);args=p.parse_args()
 extraer() if args.operacion=='extraer' else guardar()
