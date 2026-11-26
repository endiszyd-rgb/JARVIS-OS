// Usage: npm i better-sqlite3@11 in a scratch folder, then
//   NODE_PATH=<scratch>/node_modules AUTOLOGIKA_REPO=/path/to/Autologika-OS PORT=18787 node scripts/autologika_contract_harness.cjs
// JARVIS: AutoLogika view → connection http://127.0.0.1:18787, PIN 246810.
// Contract harness: real AutoLogika-OS db.cjs (schema 18 migrations) + the real orderSelect SQL and
// the two GET handlers copied from electron/main.cjs createMobileServer. Synthetic data only.
const Module=require('module'),path=require('path'),fs=require('fs'),http=require('http')
const REPO=process.env.AUTOLOGIKA_REPO, DATA=process.env.HARNESS_DATA||require('os').tmpdir()+'/autologika-harness'
if(!REPO)throw new Error('Set AUTOLOGIKA_REPO to a checkout of endiszyd-rgb/Autologika-OS (read-only use)')
fs.rmSync(DATA,{recursive:true,force:true});fs.mkdirSync(DATA,{recursive:true})
const SQLITE=require.resolve('better-sqlite3')
const STUB=path.join(DATA,'..','autologika-harness-electron-stub.cjs')
const origResolve=Module._resolveFilename
Module._resolveFilename=function(request,...rest){if(request==='electron')return STUB;if(request==='better-sqlite3')return SQLITE;return origResolve.call(this,request,...rest)}
fs.writeFileSync(STUB,`module.exports={app:{getPath:()=>${JSON.stringify(DATA)},getAppPath:()=>${JSON.stringify(REPO)},isPackaged:false,getVersion:()=>'harness'}}`)
const {getDb,SCHEMA_VERSION}=require(REPO+'/electron/db.cjs')
const {ORDER_BASE_SQL,ORDER_TOTAL_SQL,ORDER_COST_SQL}=require(REPO+'/electron/order-financials.cjs')
const main=fs.readFileSync(REPO+'/electron/main.cjs','utf8')
const selectSource=main.match(/const orderSelect = (`[\s\S]*?`)\n/)[1]
const orderSelect=eval(selectSource)
const db=getDb()
const today=new Date().toISOString().slice(0,10)
const c1=db.prepare("INSERT INTO customers(name,phone,email,company,notes) VALUES ('Jan Testowy','500100200','','','')").run().lastInsertRowid
const v1=db.prepare("INSERT INTO vehicles(customer_id,plate,vin,make,model,year,engine,mileage,notes) VALUES (?,?,?,?,?,?,?,?,?)").run(c1,'PO12345','','Skoda','Fabia',1999,'1.4 MPI',210000,'').lastInsertRowid
const v2=db.prepare("INSERT INTO vehicles(customer_id,plate,vin,make,model,year,engine,mileage,notes) VALUES (?,?,?,?,?,?,?,?,?)").run(c1,'WX9876A','','Audi','A4',2008,'2.0 TDI',300000,'').lastInsertRowid
const v3=db.prepare("INSERT INTO vehicles(customer_id,plate,vin,make,model,year,engine,mileage,notes) VALUES (?,?,?,?,?,?,?,?,?)").run(c1,'KR5555B','','VW','Golf',2012,'1.6 TDI',180000,'').lastInsertRowid
const order=(v,title,status,wait,due)=>db.prepare("INSERT INTO orders(vehicle_id,title,complaint,status,priority,diagnosis_limit,labor_rate,diagnosis_fee,source,wait_state,due_at) VALUES (?,?,?,?,?,?,?,?,?,?,?)").run(v,title,'',status,'NORMALNY',350,150,0,'desk',wait,due).lastInsertRowid
const o1=order(v1,'Wymiana rozrządu','NAPRAWA','CZESCI',today)
const o2=order(v2,'Diagnostyka DPF','GOTOWE','BRAK',today)
const o3=order(v3,'Hamulce przód','AKCEPTACJA','KLIENT','2000-01-01')
order(v3,'Stara naprawa','WYDANE','BRAK','2000-01-01')
const part=(o,name,no,status)=>db.prepare("INSERT INTO job_part_orders(order_id,part_no,name,qty,unit_cost,unit_price,status) VALUES (?,?,?,?,?,?,?)").run(o,no,name,1,100,150,status)
part(o1,'Zestaw rozrządu','INA-530','DO_ZAMOWIENIA');part(o1,'Pompa wody','SKF-VKPC','W_DRODZE');part(o1,'Pasek osprzętu','GATES-6PK','ODEBRANE')
const PIN='246810'
http.createServer((req,res)=>{const u=new URL(req.url,'http://x'),p=u.pathname
  const send=(s,d)=>{res.writeHead(s,{'Content-Type':'application/json; charset=utf-8'});res.end(JSON.stringify(d))}
  if(String(req.headers['x-autologika-pin']||'')!==PIN)return send(401,{error:'Nieprawidłowy PIN'})
  if(req.method==='GET'&&p==='/api/orders')return send(200,db.prepare(`${orderSelect} WHERE o.status!='WYDANE' ORDER BY o.opened_at DESC LIMIT 100`).all())
  const m=p.match(/^\/api\/order\/(\d+)$/)
  if(m&&req.method==='GET'){const id=Number(m[1]),order=db.prepare(`${orderSelect} WHERE o.id=?`).get(id);if(!order)return send(404,{error:'Nie znaleziono zlecenia'})
    const notes=db.prepare('SELECT * FROM order_notes WHERE order_id=?').get(id)||{},diag=db.prepare('SELECT * FROM diagnostics WHERE order_id=?').get(id)||{}
    const parts=db.prepare(`SELECT jp.*,s.name supplier FROM job_part_orders jp LEFT JOIN suppliers s ON s.id=jp.supplier_id WHERE jp.order_id=? ORDER BY jp.created_at DESC`).all(id)
    const payments=db.prepare('SELECT * FROM payments WHERE order_id=? ORDER BY paid_at DESC').all(id)
    return send(200,{order,notes,diag,parts,payments})}
  send(404,{error:'nie ma'})
}).listen(Number(process.env.PORT||18787),'127.0.0.1',()=>console.log('harness schema',SCHEMA_VERSION,'user_version',db.pragma('user_version',{simple:true}),'ready'))
