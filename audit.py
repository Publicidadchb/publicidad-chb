"""Local historical audit store. Python 3 standard library; never changes Google."""
import argparse, calendar, csv, hashlib, io, json, re, sqlite3, zipfile
from datetime import date, datetime, timezone
from decimal import Decimal, InvalidOperation
from pathlib import Path

BASE=Path(__file__).resolve().parent
DB=BASE/'private'/'chavez_auditoria.sqlite'
MONTHS={'ene':1,'feb':2,'mar':3,'abr':4,'may':5,'jun':6,'jul':7,'ago':8,'sept':9,'sep':9,'oct':10,'nov':11,'dic':12}
METRICS={'Coste':('cost','USD','sum'),'Clics':('clicks','count','sum'),'Impresiones':('impressions','count','sum'),'Conversiones':('conversions','attributed_count','sum'),'Coste/conv.':('cost_per_conversion','USD','ratio'),'CPC medio':('average_cpc','USD','ratio'),'CTR':('ctr','fraction','ratio'),'Nivel de optimización':('optimization_score','fraction','snapshot'),'Porcentaje del total conocido':('known_total_share','fraction','ratio'),'Interacciones':('interactions','count','sum')}

def canon(x): return json.dumps(x,ensure_ascii=False,sort_keys=True,separators=(',',':'))
def digest(x): return hashlib.sha256(x).hexdigest()
def now(): return datetime.now(timezone.utc).isoformat(timespec='seconds')
def connect(path=DB,readonly=False):
    if readonly:
        c=sqlite3.connect(Path(path).resolve().as_uri()+'?mode=ro',uri=True)
        c.execute('PRAGMA query_only=ON')
    else:
        Path(path).parent.mkdir(parents=True,exist_ok=True)
        c=sqlite3.connect(path)
        c.execute('PRAGMA foreign_keys=ON')
        c.executescript((BASE/'schema.sql').read_text(encoding='utf-8'))
        c.execute('INSERT OR IGNORE INTO schema_version VALUES(1,?)',(now(),))
        c.commit()
    c.row_factory=sqlite3.Row
    return c

def getid(c,table,fields):
    cols=','.join(fields)
    c.execute(f'INSERT OR IGNORE INTO {table}({cols}) VALUES({",".join("?" for _ in fields)})',tuple(fields.values()))
    where=' AND '.join(f'{k} IS ?' for k in fields)
    row=c.execute(f'SELECT id FROM {table} WHERE {where}',tuple(fields.values())).fetchone()
    if row is None: raise ValueError(f'Conflicto de identidad en {table}: {fields}')
    return row[0]

def number(raw,unit):
    t=raw.strip().replace('\u00a0','').replace('\u202f','').replace(' ','')
    if unit=='stars_0_to_5':
        d=Decimal(t.replace(',','.'))
        if not Decimal(0)<=d<=Decimal(5):raise ValueError('Calificación fuera de rango')
        return (str(d),'exact',None,None)
    if t in ('','—','--','N/A'): return (None,'missing',None,None)
    qual='lt' if t.startswith('<') else 'exact'
    if qual=='lt': t=t[1:]
    t=t.replace('US$','').replace('$','').replace('%','')
    if not re.fullmatch(r'-?(?:\d+|\d{1,3}(?:\.\d{3})+)(?:,\d+)?',t):
        raise ValueError('Número español no válido: '+repr(raw))
    d=Decimal(t.replace('.','').replace(',','.'))
    if unit=='count' and (d<0 or d!=d.to_integral_value()):raise ValueError('Recuento no entero o negativo: '+raw)
    if unit=='fraction': d/=100
    v=format(d,'f')
    micros=int(d*1000000) if unit=='USD' and qual=='exact' else None
    return (v if qual=='exact' else None,qual,v if qual=='lt' else None,micros)

def account(c,service,key,key_type):
    bid=getid(c,'businesses',{'name':'Comercial Chávez Benavides'})
    return getid(c,'accounts',dict(business_id=bid,service=service,source_key=key,key_type=key_type,timezone='America/Guayaquil',currency='USD' if service=='google_ads' else None))

def run(c,aid,content,extracted_at,url,method,extra=''):
    stamp=datetime.fromisoformat(extracted_at)
    if stamp.tzinfo is None: raise ValueError('La fecha de extracción requiere zona horaria')
    extracted_at=stamp.astimezone(timezone.utc).isoformat(timespec='seconds')
    key=digest(canon([aid,digest(content),extracted_at,url,method,extra]).encode())
    old=c.execute('SELECT id FROM runs WHERE import_key=?',(key,)).fetchone()
    if old: return old[0],False
    rid=getid(c,'runs',dict(account_id=aid,extracted_at=extracted_at,imported_at=now(),source_url=url,method=method,import_key=key))
    return rid,True

def artifact(c,rid,content,name,media):
    sha=digest(content)
    old=c.execute('SELECT id FROM artifacts WHERE sha256=?',(sha,)).fetchone()
    ar=old[0] if old else getid(c,'artifacts',dict(sha256=sha,original_name=name,media_type=media,content=content))
    c.execute('INSERT OR IGNORE INTO run_artifacts VALUES(?,?)',(rid,ar))
    return ar

def entity(c,aid,kind,key,name,basis='provisional',parent=None):
    old=c.execute('SELECT id FROM entities WHERE account_id=? AND kind=? AND source_key=?',(aid,kind,key)).fetchone()
    return old[0] if old else getid(c,'entities',dict(account_id=aid,kind=kind,source_key=key,name=name,identity_basis=basis,parent_id=parent))

def period(c,start,end,grain,asof):
    date.fromisoformat(start);date.fromisoformat(end)
    return getid(c,'periods',dict(start_date=start,end_date=end,grain=grain))

def metric(c,rid,rr,eid,report,pid,code,raw,unit='count',aggregation='sum',dims=None):
    c.execute('INSERT OR IGNORE INTO metric_definitions VALUES(?,?,?)',(code,unit,aggregation))
    definition=c.execute('SELECT unit,aggregation FROM metric_definitions WHERE code=?',(code,)).fetchone()
    if tuple(definition)!=(unit,aggregation): raise ValueError('Definición de métrica incompatible: '+code)
    val,qual,bound,micros=number(raw,unit)
    oid=getid(c,'observations',dict(entity_id=eid,report_code=report,period_id=pid,metric_code=code,dimensions_json=canon(dims or {})))
    # Each distinct extraction keeps its own revision. Replay of the same run is idempotent.
    fields=dict(observation_id=oid,run_id=rid,value_decimal=val,qualifier=qual,bound_decimal=bound,raw_value=raw,money_micros=micros)
    rev=getid(c,'revisions',fields)
    c.execute('INSERT OR IGNORE INTO evidence VALUES(?,?,?)',(rid,rev,rr))

def rawtable(c,ar,member,report,headers):
    return getid(c,'raw_tables',dict(artifact_id=ar,member_name=member,report_code=report,headers_json=canon(headers)))
def rawrow(c,tid,n,row): return getid(c,'raw_rows',dict(table_id=tid,row_number=n,values_json=canon(row)))
def cover(c,rid,section,state,detail):
    c.execute('INSERT OR REPLACE INTO coverage(run_id,section,state,detail) VALUES(?,?,?,?)',(rid,section,state,detail))

def daily(raw):
    m=re.search(r'(\d{1,2}) ([a-záéíóú]+) (\d{4})$',raw)
    if not m or m[2] not in MONTHS: raise ValueError('Fecha no reconocida: '+raw)
    return date(int(m[3]),MONTHS[m[2]],int(m[1])).isoformat()

def import_overview(c,path,extracted_at,ocid,url):
    path=Path(path); content=path.read_bytes()
    aid=account(c,'google_ads',ocid,'ocid_from_observed_url')
    rid,fresh=run(c,aid,content,extracted_at,url,'Google Ads UI: Descargar datos de tarjetas en formato csv (.zip)','overview-v1')
    if not fresh:return {'run_id':rid,'replay':True}
    ar=artifact(c,rid,content,path.name,'application/zip')
    asof=datetime.fromisoformat(extracted_at).date().isoformat()
    root=entity(c,aid,'account',ocid,'COMERCIAL CHAVEZ BENAVIDES','account')
    totalrows=0
    with zipfile.ZipFile(io.BytesIO(content)) as z:
        for info in z.infolist():
            if info.is_dir():continue
            if not info.filename.endswith('.csv'):raise ValueError('Miembro no CSV en ZIP')
            if info.file_size>10000000:raise ValueError('Miembro excesivo')
            report=Path(info.filename).stem.split('(')[0]
            tail=Path(info.filename).stem.split('(',1)[1]
            variant=re.sub(r'_?\d{4}\..*$','',tail)
            report_key=report+(':'+variant if variant else '')
            stamps=re.findall(r'\d{4}\.\d{2}\.\d{2}',info.filename)
            if len(stamps) not in (2,4):raise ValueError('Falta periodo en '+info.filename)
            bounds=[s.replace('.','-') for s in stamps]
            parsed=list(csv.reader(io.StringIO(z.read(info).decode('utf-8-sig'))))
            headers=parsed[0]
            if len(headers)!=len(set(headers)):raise ValueError('Cabeceras duplicadas')
            tid=rawtable(c,ar,info.filename,report_key,headers)
            for n,values in enumerate(parsed[1:],2):
                if not values:continue
                if len(values)!=len(headers):raise ValueError('Ancho de fila incorrecto')
                row=dict(zip(headers,values));rr=rawrow(c,tid,n,row);totalrows+=1
                attrs={};dims={};eid=root
                for label,value in row.items():
                    base=label.replace(' (Comparación)','')
                    if base not in METRICS and label!='Fecha':dims[label]=value
                if report=='Campañas':
                    eid=entity(c,aid,'campaign','name:'+row['Nombre de la campaña'],row['Nombre de la campaña'])
                    attrs={k:v for k,v in row.items() if k.startswith('Estado') or k.startswith('Nombre')}
                    dims={}
                elif report=='Palabras_clave_de_búsqueda':
                    # No campaign/ad-group ID is present: keep a report-scoped provisional identity.
                    identity={'artifact_sha256':digest(content),'member':info.filename,'row':n}
                    eid=entity(c,aid,'keyword','unresolved-card-row:'+canon(identity),row['Palabra clave de búsqueda'])
                    attrs={k:v for k,v in dims.items() if k.startswith('Estado')}
                    dims={'Tipo de concordancia':row['Tipo de concordancia']}
                elif report=='Nivel_de_optimización':
                    eid=entity(c,aid,'campaign','name:'+row['Nombre de la campaña'],row['Nombre de la campaña'])
                    dims={}
                elif report=='Cambios_más_importantes':
                    campaign=entity(c,aid,'campaign','name:'+row['Nombre de la campaña'],row['Nombre de la campaña'])
                    eid=entity(c,aid,'ad_group','campaign-name:'+row['Nombre de la campaña']+'/group-name:'+row['Nombre del grupo de anuncios'],row['Nombre del grupo de anuncios'],parent=campaign) if row['Nombre del grupo de anuncios'] else campaign
                    dims={}
                if attrs:
                    c.execute('INSERT OR IGNORE INTO entity_observations(entity_id,run_id,raw_row_id,attributes_json) VALUES(?,?,?,?)',(eid,rid,rr,canon(attrs)))
                for label,raw in row.items():
                    base=label.replace(' (Comparación)','')
                    if base not in METRICS:continue
                    code,unit,aggregation=METRICS[base]
                    start,end=bounds[:2];grain='range'
                    if '(Comparación)' in label:
                        if len(bounds)!=4:raise ValueError('Periodo de comparación ausente')
                        start,end=bounds[2:]
                    if 'Fecha' in row:start=end=daily(row['Fecha']);grain='day'
                    if 'Trimestre' in row:
                        q=re.fullmatch(r'([1-4])\..* trimestre de (\d{4})',row['Trimestre'])
                        if not q:raise ValueError('Trimestre no reconocido: '+row['Trimestre'])
                        year=int(q[2]);month=(int(q[1])-1)*3+1
                        start=max(bounds[0],date(year,month,1).isoformat())
                        natural_end=date(year,month+2,calendar.monthrange(year,month+2)[1]).isoformat()
                        end=min(bounds[1],natural_end);grain='quarter' if end==natural_end else 'quarter_to_date'
                    if aggregation=='snapshot':start=end=asof;grain='snapshot'
                    metric(c,rid,rr,eid,report_key,period(c,start,end,grain,asof),code,raw,unit,aggregation,dims)
            cover(c,rid,report_key,'partial' if report in ('Búsquedas','Palabras_clave_de_búsqueda','Campañas','Cambios_más_importantes') else 'reviewed','Todos los renglones del CSV conservados. Exportación de tarjeta; no acredita exhaustividad de la tabla principal.')
    for section in ('Presupuestos e IDs nativos','Todos los anuncios','Acciones y ajustes de conversiones','Negativas','Configuración de campañas','Historial de cambios completo','Facturación detallada','Otros periodos de Ads'):
        cover(c,rid,section,'pending','Falta exportación detallada para acreditar cobertura completa. Revisar también los extractos UI de esta sesión.')
    return {'run_id':rid,'raw_rows':totalrows,'replay':False}

def import_ui(c,path):
    path=Path(path);content=path.read_bytes();doc=json.loads(content)
    aid=account(c,doc['service'],doc['account_key'],doc['key_type'])
    rid,fresh=run(c,aid,content,doc['extracted_at'],doc['url'],'Transcripción verificada de DOM/accesibilidad; extractos literales','ui-v1')
    if not fresh:return {'run_id':rid,'replay':True}
    ar=artifact(c,rid,content,path.name,'application/json')
    asof=datetime.fromisoformat(doc['extracted_at']).date().isoformat()
    tid=rawtable(c,ar,path.name,'ui_observations',['record'])
    root_kind='account' if doc['service']=='google_ads' else 'location'
    parent=entity(c,aid,root_kind,doc['account_key'],doc['name'],'account' if root_kind=='account' else 'native')
    for n,record in enumerate(doc['records'],1):
        rr=rawrow(c,tid,n,record)
        kind=record.get('kind','location');key=record.get('entity_key',doc['account_key'])
        eid=entity(c,aid,kind,key,record.get('name',doc['name']),record.get('identity_basis','native'),None if kind==root_kind and key==doc['account_key'] else parent)
        if 'attributes' in record:
            c.execute('INSERT OR IGNORE INTO entity_observations(entity_id,run_id,raw_row_id,attributes_json) VALUES(?,?,?,?)',(eid,rid,rr,canon(record['attributes'])))
        for m in record.get('metrics',[]):
            pid=period(c,m['start'],m['end'],m.get('grain','range'),asof)
            metric(c,rid,rr,eid,m.get('report','gbp_performance'),pid,m['code'],m['raw'],m.get('unit','count'),m.get('aggregation','sum'),m.get('dimensions',{}))
    for x in doc.get('coverage',[]):cover(c,rid,*x)
    for f in doc.get('findings',[]):
        c.execute('INSERT INTO findings(run_id,finding_key,priority,fact,interpretation,recommendation,evidence_json) VALUES(?,?,?,?,?,?,?)',(rid,f['key'],f['priority'],f['fact'],f['interpretation'],f['recommendation'],canon(f['evidence'])))
    return {'run_id':rid,'records':len(doc['records']),'replay':False}

def import_campaigns(c,path,extracted_at,ocid,url,start,end):
    path=Path(path);content=path.read_bytes();rows=list(csv.reader(io.StringIO(content.decode('utf-8-sig'))))
    if len(rows)<4 or rows[2][0]!='Estado de la campaña':raise ValueError('Formato de campañas no reconocido')
    longmonths=['enero','febrero','marzo','abril','mayo','junio','julio','agosto','septiembre','octubre','noviembre','diciembre']
    spans=re.findall(r'(\d{1,2}) de ([a-z]+) de (\d{4})',rows[1][0])
    observed=[date(int(y),longmonths.index(m)+1,int(d)).isoformat() for d,m,y in spans]
    if observed!=[start,end]:raise ValueError('El periodo indicado no coincide con el encabezado original')
    aid=account(c,'google_ads',ocid,'ocid_from_observed_url')
    rid,fresh=run(c,aid,content,extracted_at,url,'Google Ads UI: tabla de campañas .csv',canon([start,end,'campaign-table-v1']))
    if not fresh:return {'run_id':rid,'replay':True}
    ar=artifact(c,rid,content,path.name,'text/csv');tid=rawtable(c,ar,path.name,'campaign_table',rows[2])
    asof=datetime.fromisoformat(extracted_at).date().isoformat();count=0
    mapping=dict(METRICS);mapping.update({'Impr.':('impressions','count','sum'),'Tasa de conv.':('conversion_rate','fraction','ratio'),'Valor de conv.':('conversion_value','account_value','sum')})
    for n,values in enumerate(rows[3:],4):
        if not values:continue
        if len(values)!=len(rows[2]):raise ValueError('Ancho incorrecto en campañas')
        row=dict(zip(rows[2],values));rr=rawrow(c,tid,n,row)
        if row['Código de moneda']!='USD':raise ValueError('Moneda distinta de USD')
        total=row['Estado de la campaña'].startswith('Total:')
        if total and row['Estado de la campaña']!='Total: Cuenta':continue
        report='account_table' if total else 'campaign_table'
        eid=entity(c,aid,'account',ocid,'COMERCIAL CHAVEZ BENAVIDES','account') if total else entity(c,aid,'campaign','name:'+row['Campaña'],row['Campaña'])
        if not total:
            count+=1
            attrs={k:v for k,v in row.items() if k not in mapping and k!='Presupuesto'}
            c.execute('INSERT INTO entity_observations(entity_id,run_id,raw_row_id,attributes_json) VALUES(?,?,?,?)',(eid,rid,rr,canon(attrs)))
            metric(c,rid,rr,eid,'campaign_budget',period(c,asof,asof,'snapshot',asof),'daily_budget',row['Presupuesto'],'USD','snapshot')
        for label,definition in mapping.items():
            if label not in row:continue
            code,unit,agg=definition;raw=row[label]
            point=agg=='snapshot';a,b=(asof,asof) if point else (start,end)
            metric(c,rid,rr,eid,report,period(c,a,b,'snapshot' if point else 'range',asof),code,raw,unit,agg)
    cover(c,rid,'Tabla de campañas','partial',f'{count} campañas importadas. El CSV no acredita por sí solo cobertura completa ni entidades retiradas. Presupuestos/estados son de la extracción, no históricos.')
    return {'run_id':rid,'campaigns':count,'replay':False}

def validate(c):
    fk=[dict(x) for x in c.execute('PRAGMA foreign_key_check')]
    integrity=c.execute('PRAGMA integrity_check').fetchone()[0]
    noev=c.execute('SELECT count(*) FROM revisions r WHERE NOT EXISTS(SELECT 1 FROM evidence e WHERE e.revision_id=r.id)').fetchone()[0]
    return {'integrity':integrity,'foreign_key_errors':fk,'revisions_without_evidence':noev,'tables':{t:c.execute(f'SELECT count(*) FROM {t}').fetchone()[0] for t in ('runs','artifacts','raw_tables','raw_rows','entities','observations','revisions','evidence','findings')}}

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--db',default=str(DB));s=p.add_subparsers(dest='cmd',required=True)
    a=s.add_parser('import-overview');a.add_argument('zip');a.add_argument('--extracted-at',required=True);a.add_argument('--ocid',required=True);a.add_argument('--url',required=True)
    a=s.add_parser('import-ui');a.add_argument('json')
    a=s.add_parser('import-campaigns');a.add_argument('csv');a.add_argument('--extracted-at',required=True);a.add_argument('--ocid',required=True);a.add_argument('--url',required=True);a.add_argument('--start',required=True);a.add_argument('--end',required=True)
    a=s.add_parser('query');a.add_argument('--sql',required=True)
    s.add_parser('init',help='Crear una base vacía sin sustituir una existente')
    s.add_parser('check');a=s.add_parser('backup');a.add_argument('destination')
    args=p.parse_args()
    if args.cmd=='init' and Path(args.db).exists():p.error('La base ya existe; no se sobrescribe')
    if args.cmd in ('query','check','backup') and not Path(args.db).is_file():
        p.error('Base no encontrada. Recupere el histórico o ejecute init para crear una base vacía; demo.py crea una demostración separada.')
    c=connect(args.db,readonly=args.cmd in ('query','check','backup'))
    try:
        with c:
            if args.cmd=='import-overview':out=import_overview(c,args.zip,args.extracted_at,args.ocid,args.url)
            elif args.cmd=='import-ui':out=import_ui(c,args.json)
            elif args.cmd=='import-campaigns':out=import_campaigns(c,args.csv,args.extracted_at,args.ocid,args.url,args.start,args.end)
            elif args.cmd=='query':
                allowed={sqlite3.SQLITE_SELECT,sqlite3.SQLITE_READ,sqlite3.SQLITE_FUNCTION,sqlite3.SQLITE_RECURSIVE}
                c.set_authorizer(lambda action,*_:sqlite3.SQLITE_OK if action in allowed else sqlite3.SQLITE_DENY)
                out=[dict(x) for x in c.execute(args.sql)]
            elif args.cmd=='check':out=validate(c)
            elif args.cmd=='init':out={'initialized':str(Path(args.db).resolve()),'historical_data':False,**validate(c)}
            else:
                dest=Path(args.destination)
                if dest.exists():raise ValueError('La copia ya existe; elija otro nombre')
                dest.parent.mkdir(parents=True,exist_ok=True)
                with sqlite3.connect(dest) as target:c.backup(target)
                out={'backup':str(dest.resolve())}
        print(json.dumps(out,ensure_ascii=False,indent=2))
        if args.cmd=='check' and (out['integrity']!='ok' or out['foreign_key_errors'] or out['revisions_without_evidence']):
            raise SystemExit(1)
    finally:c.close()

if __name__=='__main__':main()
