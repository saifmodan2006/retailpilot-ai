// Targeted automated WCAG checks; not a screen-reader certification.
import {chromium,request} from '@playwright/test';
import AxeBuilder from '@axe-core/playwright';
import fs from 'node:fs/promises';
const baseURL='http://127.0.0.1:5174'; // Local only: never wakes the public API.
const http=await request.newContext({baseURL});
let access_token=process.env.LOCAL_AUDIT_TOKEN;
if(!access_token){
 access_token=(await (await http.post('/api/v1/demo/session')).json()).access_token;
 const seed=await http.post('/api/v1/demo/seed',{headers:{Authorization:`Bearer ${access_token}`},timeout:180000});
 if(!seed.ok())throw new Error(`Seed: ${seed.status()}`);
}
const browser=await chromium.launch();const context=await browser.newContext({baseURL,viewport:{width:1440,height:900},reducedMotion:'reduce'});const page=await context.newPage();
await page.addInitScript(t=>localStorage.setItem('rp-token',t),access_token);
const results=[];
for(const name of ['landing','overview','sales','inventory','forecast','imports','reports','analyst','workflows','approvals','audit','integrations','settings']){
 await page.goto(name==='landing'?'/':`/app/${name}`);await page.waitForLoadState('networkidle');
 await page.locator('.loading').waitFor({state:'hidden',timeout:120000});
 const result=await new AxeBuilder({page}).withTags(['wcag2a','wcag2aa','wcag21a','wcag21aa']).analyze();
 const violations=result.violations.map(v=>({id:v.id,impact:v.impact,description:v.description,nodes:v.nodes.map(n=>({target:n.target,summary:n.failureSummary}))}));
 results.push({page:name,violations,incomplete_checks:result.incomplete.length});
 console.log(name,violations.map(v=>`${v.id}:${v.nodes.length}`).join(', ')||'PASS');
}
await fs.writeFile('../docs/accessibility-verification.json',JSON.stringify({scope:'Local desktop automated WCAG 2 A/AA and 2.1 A/AA; manual checks and screen-reader review remain separate.',results},null,2));
await browser.close();await http.dispose();
if(results.some(r=>r.violations.length))process.exitCode=1;
