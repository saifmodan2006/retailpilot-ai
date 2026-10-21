import {useState, type FormEvent} from "react";
import {Link} from "react-router-dom";
import {useQuery, useQueryClient} from "@tanstack/react-query";
import {api, money, type Row} from "../api";

export default function PrivateCatalog({enabled,synthetic,manage}:{enabled:boolean;synthetic:boolean;manage:boolean}) {
 const [preview,setPreview]=useState<Row|null>(null),[busy,setBusy]=useState(false),[error,setError]=useState(""),[notice,setNotice]=useState("");
 const qc=useQueryClient();
 const catalog=useQuery({queryKey:["private-product-catalog"],queryFn:()=>api<Row[]>("/skus"),enabled:enabled&&!synthetic});
 async function run(job:()=>Promise<void>) {setBusy(true);setError("");setNotice("");try{await job();}catch(e){setError((e as Error).message);}finally{setBusy(false);}}
 async function save(rows:Row[]) {const result=await api("/organizations/current/catalog",{method:"POST",body:JSON.stringify({rows})});await qc.invalidateQueries();setPreview(null);setNotice(`${result.created} catalog item(s) added. You can now validate sales and inventory files using these SKU codes.`);}
 function add(event:FormEvent<HTMLFormElement>) {event.preventDefault();const form=event.currentTarget,values=Object.fromEntries(new FormData(form));void run(async()=>{await save([values]);form.reset();});}
 return <section className="account-section"><h2>Your product catalog</h2>
 {!enabled?<p>Private file imports are awaiting activation.</p>:synthetic?<p>This workspace contains fictional samples. <Link to="/app/workspaces">Create an empty workspace</Link> for your own business data so the datasets stay separate.</p>:<>
 <p>Add your stores above, then create your SKU catalog before importing sales and stock. Use business records you are authorized to process. Omit customer names, contact details, payment data and credentials. <Link to="/privacy/">Read retention and privacy information</Link>.</p>
 {error&&<div className="error account-errors" role="alert">{error}</div>}{notice&&<p className="toast" role="status">{notice}</p>}
 {manage&&<><form onSubmit={add}><h3>Add a SKU</h3><div className="account-grid">
 {[["sku","SKU code"],["product","Product name"],["brand","Brand"],["category","Category"],["supplier","Supplier"],["size","Size (optional)"],["color","Color (optional)"]].map(([name,label])=><label className="account-field" key={name}>{label}<input name={name} maxLength={name==="sku"?40:name==="size"||name==="color"?40:name==="product"?120:80} pattern={name==="sku"?"[A-Za-z0-9_-]+":undefined} required={!["size","color"].includes(name)}/></label>)}
 {[["cost","Purchase cost",0,10000000,"0.01"],["price","Selling price",0,10000000,"0.01"],["lead_days","Supplier lead time (days)",0,365,"1"],["moq","Minimum order quantity",1,10000,"1"],["pack_size","Supplier pack size",1,10000,"1"]].map(([name,label,min,max,step])=><label className="account-field" key={String(name)}>{label}<input name={String(name)} type="number" min={Number(min)} max={Number(max)} step={String(step)} defaultValue={name==="lead_days"?10:name==="moq"||name==="pack_size"?1:undefined} required/></label>)}
 </div><p>Use the same planning rules for an existing supplier. Prices use your workspace currency.</p><button className="btn primary" disabled={busy}>Add catalog item</button></form>
 <h3>Import a catalog file</h3><p>Up to 500 new SKUs and 1 MB per CSV/XLSX file; 1,000 SKUs per workspace. Existing SKU codes are preserved. All rows must validate before saving.</p>
 <a className="btn" href="/templates/catalog.csv" download>Download catalog template</a>
 <label className="account-field">Catalog CSV or XLSX<input type="file" accept=".csv,.xlsx" disabled={busy} onChange={e=>{const file=e.target.files?.[0];e.target.value="";if(file)void run(async()=>{setPreview(null);const form=new FormData();form.append("file",file);setPreview(await api("/organizations/current/catalog/preview",{method:"POST",body:form}));});}}/></label>
 {preview&&<><p role="status">{preview.accepted} valid rows · {preview.rejected} rejected rows</p>{preview.errors.length>0&&<ul>{preview.errors.slice(0,10).map((e:Row,i:number)=><li key={i}>{e.sheet}, row {e.row}: {e.message}</li>)}</ul>}<button className="btn primary" disabled={busy||preview.rejected>0||!preview.accepted} onClick={()=>run(()=>save(preview.rows))}>Save validated catalog</button></>}
 </>}
 <div className="account-scroll" tabIndex={0} role="region" aria-label="Product catalog"><table className="account-table"><thead><tr><th>SKU</th><th>Product</th><th>Cost</th><th>Price</th></tr></thead><tbody>{catalog.data?.map(s=><tr key={s.sku_id}><td>{s.sku}</td><td>{s.product}</td><td>{money(s.cost)}</td><td>{money(s.price)}</td></tr>)}</tbody></table></div>
 <p><Link to="/app/imports">Continue to sales and inventory imports</Link></p>
 </>}
 </section>;
}
