// Authorized synthetic release checks. Tokens remain only in process memory.
import {chromium, request} from '@playwright/test';
import fs from 'node:fs/promises';
import path from 'node:path';
import assert from 'node:assert/strict';
const frontend=process.env.E2E_BASE_URL??'https://retailpilot-ai.pages.dev';
const backend=process.env.E2E_API_URL??'https://retailpilot-ai-api.onrender.com';
const out=path.resolve('../docs/screenshots/public');await fs.mkdir(out,{recursive:true});
const http=await request.newContext({baseURL:backend,timeout:180000});
let token='';const evidence={frontend,backend,checked_at:new Date().toISOString(),checks:[],pages:[]};
const check=(name)=>{evidence.checks.push(name);console.log('PASS:',name)};
const call=async(method,url,data)=>{
 const r=await http[method]('/api/v1'+url,{headers:{Authorization:`Bearer ${token}`},...(data?{data}: {})});
 assert(r.ok(),`${method} ${url}: ${r.status()}`);return r.json();
};
const health=await http.get('/api/v1/health');assert.equal(health.status(),200);check('Public API and database health');
const session=await call('post','/demo/session');token=session.access_token;
evidence.organization_id=session.user.org_id;
await call('post','/demo/seed');check('Isolated fictional dataset seeded');
const before=await call('get','/analytics');
const arbitrary=await http.post('/api/v1/imports/preview',{headers:{Authorization:`Bearer ${token}`},multipart:{file:{name:'private.csv',mimeType:'text/csv',buffer:Buffer.from('sku,quantity\nPRIVATE,1')}}});
assert.equal(arbitrary.status(),403);check('Arbitrary public upload denied');
const sample=await fs.readFile('../sample_data/sales_import.xlsx');
const preview=await http.post('/api/v1/imports/preview',{headers:{Authorization:`Bearer ${token}`},multipart:{file:{name:'sales_import.xlsx',mimeType:'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',buffer:sample}}});
assert.equal(preview.status(),200);const batch=await preview.json();assert.equal(batch.accepted,15);assert.equal(batch.rejected,4);
await call('post',`/imports/${batch.id}/commit`);const after=await call('get','/analytics');
assert(Math.abs(after.metrics.revenue-before.metrics.revenue-55532.25)<0.01);evidence.revenue=after.metrics.revenue;check('Upload, validation, import and exact revenue increment');
const recommendations=await call('get','/recommendations');const approval=await call('post',`/recommendations/${recommendations[0].id}/submit`);
const denied=await http.post(`/api/v1/approvals/${approval.id}/decision`,{headers:{Authorization:`Bearer ${token}`},data:{decision:'approve',reason:'Role guard verification'}});assert.equal(denied.status(),403);check('Analyst cannot approve purchase');
token=(await call('post','/demo/role')).access_token;
await call('post',`/approvals/${approval.id}/decision`,{decision:'approve',reason:'Synthetic release verification: demand and supplier evidence reviewed.'});
assert((await call('get','/purchase-orders')).some(r=>r.status==='Simulated Draft'));check('Manager approval creates simulated draft');
const report=await call('post','/reports',{kind:'Daily sales MIS'});evidence.report_id=report.id;evidence.report_metrics=report.metrics;
for(const format of ['xlsx','pdf']){
 const r=await http.get(`/api/v1/reports/${report.id}/download?format=${format}`,{headers:{Authorization:`Bearer ${token}`}});assert.equal(r.status(),200);
 assert((await r.body()).subarray(0,format==='pdf'?4:2).equals(Buffer.from(format==='pdf'?'%PDF':'PK')));check(`Real ${format.toUpperCase()} export`);
}
for(const question of ['stores','stockouts','dead-stock','inventory','reorder','revenue']){
 const answer=await call('post','/analyst/query',{question});assert.equal(answer.tool,question);check(`Deterministic analyst: ${question}`);
}
for(const origin of [frontend,'https://untrusted.example']){
 const r=await http.fetch('/api/v1/analytics',{method:'OPTIONS',headers:{Origin:origin,'Access-Control-Request-Method':'GET','Access-Control-Request-Headers':'authorization'}});
 assert.equal(r.headers()['access-control-allow-origin'],origin===frontend?frontend:undefined);
}check('Exact CORS origin enforced');
assert.equal((await http.get('/api/v1/analytics')).status(),401);check('Unauthenticated analytics denied');
for(const url of ['/docs','/openapi.json'])assert.equal((await http.get(url)).status(),404);check('Public API documentation disabled');
const browser=await chromium.launch();const page=await browser.newPage({baseURL:frontend,viewport:{width:1440,height:900},reducedMotion:'reduce'});
const browserErrors=[];page.on('pageerror',e=>browserErrors.push(e.message));
await page.addInitScript(t=>localStorage.setItem('rp-token',t),token);
for(const name of ['overview','sales','inventory','forecast','imports','reports','analyst','workflows','approvals','audit','integrations','settings']){
 const r=await page.goto(`/app/${name}`);assert.equal(r.status(),200);await page.waitForLoadState('networkidle',{timeout:120000});
 await page.locator('.loading').waitFor({state:'hidden',timeout:120000});
 assert.equal(await page.getByRole('alert').count(),0,`Error on ${name}`);
 const overflow=await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth);assert.equal(overflow,false);
 await page.screenshot({path:path.join(out,`${name}.png`),fullPage:true,animations:'disabled'});evidence.pages.push(name);console.log('PAGE:',name);
}
await page.reload();await page.waitForLoadState('networkidle');assert.equal(await page.getByRole('alert').count(),0);check('Direct route navigation and browser refresh');
assert.deepEqual(browserErrors,[]);check('All workspace pages without browser exceptions');
await browser.close();
await fs.writeFile('../docs/public-runtime-verification.json',JSON.stringify(evidence,null,2));
console.log('READY_FOR_RESTART: token retained in memory; press Enter after the authorized Render restart/redeploy.');
await new Promise(resolve=>process.stdin.once('data',resolve));
let ready=false;const start=Date.now();
for(let i=0;i<40;i++){
 try{if((await http.get('/api/v1/health',{timeout:5000})).ok()){ready=true;break;}}catch{/* Temporary unavailability is expected during the deliberate restart. */}
 await new Promise(resolve=>setTimeout(resolve,2000));
}
assert(ready,'API did not recover after restart');evidence.restart_recovery_seconds=(Date.now()-start)/1000;
const reports=await call('get','/reports');assert.deepEqual(reports.find(r=>r.id===report.id).metrics,report.metrics);
assert.equal((await call('get','/analytics')).metrics.revenue,evidence.revenue);
check('Database records and signed session persist across service restart');
const pdf=await http.get(`/api/v1/reports/${report.id}/download?format=pdf`,{headers:{Authorization:`Bearer ${token}`}});assert.equal(pdf.status(),200);check('Persisted report exports after restart');
const dup=await http.post(`/api/v1/imports/${batch.id}/commit`,{headers:{Authorization:`Bearer ${token}`}});assert.equal(dup.status(),200);assert.equal((await dup.json()).idempotent_replay,true);assert.equal((await call('get','/analytics')).metrics.revenue,evidence.revenue);check('Import remains idempotent after restart');
assert.equal((await call('post','/analyst/query',{question:'inventory'})).tool,'inventory');check('Analyst works after restart');
evidence.persistence_after_restart=true;
await call('post','/demo/end');
assert.equal((await http.get('/api/v1/me',{headers:{Authorization:`Bearer ${token}`}})).status(),403);
check('Disposable public test session ended and token revoked');
await fs.writeFile('../docs/public-runtime-verification.json',JSON.stringify(evidence,null,2));
await http.dispose();console.log(`PASS: ${evidence.checks.length} public checks and ${evidence.pages.length} workspace routes`);
process.exit(0);
