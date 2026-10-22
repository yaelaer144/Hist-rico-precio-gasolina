"""Parche idempotente: separa fechas CNE y DOF en generador y selector."""
from pathlib import Path
import re

root = Path('monitor_ieps/src')
template = root / 'plantilla.html'
generator = root / 'generar_index.py'

html = template.read_text(encoding='utf-8')
# El navegador debe iniciar en la última fecha con precios completos,
# no en la fecha actual ni en la última cuota fiscal.
new_load = '''function load(){
 data=embeddedData;
 if(!data.length)return;
 const fuels=['regular','premium','diesel'];
 const first=data[0].fecha;
 const dates=new Map();
 for(const r of data){
  if(fuels.includes(r.combustible) && typeof r.precio==='number' && Number.isFinite(r.precio)){
   if(!dates.has(r.fecha))dates.set(r.fecha,new Set());
   dates.get(r.fecha).add(r.combustible);
  }
 }
 const complete=[...dates].filter(([date,set])=>fuels.every(f=>set.has(f))).map(([date])=>date).sort();
 if(!complete.length){el('status').textContent='No hay fechas con precios completos';return;}
 const lastPrice=complete[complete.length-1];
 const lastFiscal=data.filter(r=>r.cuota!==null && r.cuota!==undefined).map(r=>r.fecha).sort().at(-1)||lastPrice;
 const lastRange=lastPrice>lastFiscal?lastPrice:lastFiscal;
 for(const id of ['start','end']){el(id).min=first;el(id).max=lastRange;}
 el('start').value=first;
 el('end').value=lastPrice;
 el('range').innerHTML='<option value="all">Desde '+first.slice(0,4)+'</option>'+Array.from({length:Number(lastRange.slice(0,4))-Number(first.slice(0,4))+1},(_,i)=>Number(first.slice(0,4))+i).map(y=>'<option value="'+y+'">'+y+'</option>').join('');
 render();
}'''
pat_load = r'function load\(\)\{.*?\}\nfunction render\('
if not re.search(pat_load, html, re.S):
    raise RuntimeError('No se encontró load() en plantilla.html')
html = re.sub(pat_load, lambda m: new_load + '\nfunction render(', html, count=1, flags=re.S)
template.write_text(html, encoding='utf-8')

code = generator.read_text(encoding='utf-8')
start = " last=max(r['fecha'] for r in json.loads(data));s=s.replace('max=\"2026-10-05\"',f'max=\"{last}\"').replace('value=\"2026-08-31\"',f'value=\"{last}\"')"
replacement = ''' # Fechas independientes: CNE exige los tres combustibles, DOF solo cuota.
 from collections import defaultdict
 import datetime as dt
 fuel_dates=defaultdict(set)
 fiscal_dates=[]
 for row in rows:
  if row.get('precio') is not None and row.get('combustible') in ('regular','premium','diesel'):
   fuel_dates[row['fecha']].add(row['combustible'])
  if row.get('cuota') is not None:
   fiscal_dates.append(row['fecha'])
 valid_prices=[date for date,fuels in fuel_dates.items() if len(fuels)==3]
 if not valid_prices:raise ValueError('No hay fecha con precios completos CNE')
 price_end=max(valid_prices)
 fiscal_end=max(fiscal_dates) if fiscal_dates else None
 data_end=max(price_end,fiscal_end or price_end)
 meses=('enero','febrero','marzo','abril','mayo','junio','julio','agosto','septiembre','octubre','noviembre','diciembre')
 def display_date(iso):
  date=dt.date.fromisoformat(iso)
  return f'{date.day} de {meses[date.month-1]} de {date.year}'
 # Limites de ambos calendarios, pero vista inicial hasta CNE.
 s=re.sub(r'(<input\\s+id="(?:start|end)"[^>]*?\\smax=")[^"]+"',lambda m:m.group(1)+data_end+'"',s)
 s=re.sub(r'(<input\\s+id="end"[^>]*?\\svalue=")[^"]+"',lambda m:m.group(1)+price_end+'"',s)
 # Avisos independientes generados desde los datos (no fechas fijas).
 s=re.sub(r'Los precios disponibles terminan el\\s*<b>.*?</b>\\.', 'Los precios disponibles terminan el <b>'+display_date(price_end)+'</b>.', s, count=1, flags=re.S)
 if fiscal_end:
  s=re.sub(r'(?:El Excel contiene cuotas hasta el corte del|Las cuotas disponibles llegan hasta el)\\s*<b>.*?</b>\\.', 'Las cuotas disponibles llegan hasta el <b>'+display_date(fiscal_end)+'</b>.', s, count=1, flags=re.S)
 print('CNE: precios hasta', price_end, '| DOF: cuotas hasta', fiscal_end)
'''
if start in code:
    code=code.replace(start,replacement,1)
elif '# Fechas independientes: CNE exige los tres combustibles' not in code:
    raise RuntimeError('No se encontró la línea original last=max(...) en generar_index.py')
generator.write_text(code, encoding='utf-8')
print('Separación CNE/DOF instalada (o ya existente).')
