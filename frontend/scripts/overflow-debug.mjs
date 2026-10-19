import {chromium,request} from '@playwright/test';
const baseURL='http://127.0.0.1:5173';
const http=await request.newContext({baseURL});
const {access_token}=await (await http.post('/api/v1/demo/session')).json();
await http.post('/api/v1/demo/seed',{headers:{Authorization:`Bearer ${access_token}`},timeout:120000});
const browser=await chromium.launch();const page=await browser.newPage({baseURL,viewport:{width:390,height:844}});
await page.addInitScript(t=>localStorage.setItem('rp-token',t),access_token);
for(const name of ['inventory','sales','imports','settings']){
 await page.goto(`/app/${name}`);await page.waitForLoadState('networkidle');
 console.log(name,await page.evaluate(()=>[...document.querySelectorAll('main *')].filter(e=>e.getBoundingClientRect().right>innerWidth+2).map(e=>({tag:e.tagName,class:e.className,width:Math.round(e.getBoundingClientRect().width),right:Math.round(e.getBoundingClientRect().right),overflow:getComputedStyle(e).overflowX})).slice(0,12)));
}
await browser.close();await http.dispose();
