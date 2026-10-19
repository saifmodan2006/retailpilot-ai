import { chromium, request } from '@playwright/test';
import fs from 'node:fs/promises';
import path from 'node:path';

const baseURL=process.env.E2E_BASE_URL??'http://127.0.0.1:5173';
const phase=process.argv[2]??'before';
const out=path.resolve('../docs/screenshots',phase);
await fs.mkdir(out,{recursive:true});
const http=await request.newContext({baseURL});
let access_token=process.env.LOCAL_AUDIT_TOKEN;
if(access_token&&!['127.0.0.1','localhost'].includes(new URL(baseURL).hostname))throw new Error('Local audit tokens must stay on loopback');
if(!access_token){
 const session=await http.post('/api/v1/demo/session');
 if(!session.ok())throw new Error(`Session unavailable: ${session.status()}`);
 access_token=(await session.json()).access_token;
}
const headers={Authorization:`Bearer ${access_token}`};
if(!process.env.LOCAL_AUDIT_TOKEN){
 console.log('Seeding isolated fictional audit workspace');
 const seeded=await http.post('/api/v1/demo/seed',{headers,timeout:180000});
 if(!seeded.ok())throw new Error(`Seed failed: ${seeded.status()}`);
}
const post=(url,data)=>http.post('/api/v1'+url,{headers,data,timeout:90000});
await post('/reports',{kind:'Daily sales MIS'});
await post('/workflows',{kind:'daily-report',key:'visual-audit-daily'});
const recs=await (await http.get('/api/v1/recommendations',{headers})).json();
const suggestion=recs.find(r=>r.status==='Suggested');
if(suggestion)await post(`/recommendations/${suggestion.id}/submit`);
const me=await (await http.get('/api/v1/me',{headers})).json();
if(me.user.role!=='manager')await post('/demo/role');
const browser=await chromium.launch();
const page=await browser.newPage({baseURL,viewport:{width:1440,height:900},reducedMotion:'reduce'});
await page.addInitScript(token=>localStorage.setItem('rp-token',token),access_token);
const pages=['landing','overview','sales','inventory','forecast','imports','reports','analyst','workflows','approvals','audit','integrations','settings'];
const sizes=phase==='before'?[[1440,900]]:[[1440,900],[1280,800],[768,1024],[390,844]];
const evidence=[];
for(const [width,height] of sizes){
 await page.setViewportSize({width,height});
 for(const name of pages){
  await page.goto(name==='landing'?'/':`/app/${name}`);
  await page.waitForLoadState('networkidle',{timeout:30000}).catch(()=>{});
  await page.locator('.loading').waitFor({state:'hidden',timeout:60000}).catch(()=>{});
  const main=page.locator('main');
  await main.waitFor({state:'visible'});
  const overflow=await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth);
  const alerts=await page.getByRole('alert').allTextContents();
  await page.screenshot({path:path.join(out,`${name}-${width}.png`),fullPage:true,animations:'disabled'});
  evidence.push({page:name,width,height,overflow,alerts});
  console.log(`${phase}: ${name} ${width} overflow=${overflow} alerts=${alerts.length}`);
 }
}
await fs.writeFile(path.join(out,'evidence.json'),JSON.stringify(evidence,null,2));
await browser.close();await http.dispose();
if(evidence.some(e=>e.overflow||e.alerts.length))process.exitCode=1;
