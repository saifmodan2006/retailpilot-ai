import { chromium, request } from '@playwright/test';
import fs from 'node:fs/promises';
import path from 'node:path';

const baseURL=process.env.E2E_BASE_URL??'http://127.0.0.1:5173';
const phase=process.argv[2]??'before';
const out=path.resolve('../docs/screenshots',phase);
await fs.mkdir(out,{recursive:true});
const http=await request.newContext({baseURL});
const session=await http.post('/api/v1/demo/session');
if(!session.ok())throw new Error(`Session unavailable: ${session.status()}`);
const {access_token}=await session.json();
const headers={Authorization:`Bearer ${access_token}`};
console.log('Seeding isolated fictional audit workspace');
const seeded=await http.post('/api/v1/demo/seed',{headers,timeout:120000});
if(!seeded.ok())throw new Error(`Seed failed: ${seeded.status()}`);
const post=(url,data)=>http.post('/api/v1'+url,{headers,data,timeout:90000});
await post('/reports',{kind:'Daily sales MIS'});
await post('/workflows',{kind:'daily-report',key:'visual-audit-daily'});
const recs=await (await http.get('/api/v1/recommendations',{headers})).json();
if(recs[0])await post(`/recommendations/${recs[0].id}/submit`);
await post('/demo/role');
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
