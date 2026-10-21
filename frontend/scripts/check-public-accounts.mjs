// Read-only live browser verification; never creates an identity or submits credentials.
import {chromium} from "@playwright/test";
import AxeBuilder from "@axe-core/playwright";
import assert from "node:assert/strict";
import {writeFile} from "node:fs/promises";

const browser=await chromium.launch();
const pilot=process.argv.includes("--pilot");
const open=process.argv.includes("--open");
const evidence={origin:"https://retailpilot-ai.pages.dev",checked_at:new Date().toISOString(),pages:[]};
try {
 const context=await browser.newContext();
 const page=await context.newPage();
 for(const width of [1440,768,390]) {
  await page.setViewportSize({width,height:900});
  for(const route of ["signup","login","callback"]) {
   await page.goto(`${evidence.origin}/auth/${route}`);
   if(route!=="callback") await page.getByRole("button",{name:route==="signup"?"Create free account":"Sign in",exact:true}).waitFor();
   if(open&&route!=="callback") {
    await page.getByRole("button",{name:"Continue with Google",exact:true}).waitFor();
    const response=await page.request.get(`${evidence.origin}/api/v1/auth/config`);
    assert(response.ok());const config=await response.json();
    assert.equal(config.registration_mode,"open");assert.equal(config.google,true);
    assert.equal(config.captcha,true);assert.equal(config.email_delivery,"custom_smtp");
    assert.equal(await page.getByText("Registration is limited to explicitly invited pilot participants. General registration is closed.").count(),0);
   } else if(route==="signup") await page.getByText(pilot?"Registration is limited to explicitly invited pilot participants. General registration is closed.":"Registration is closed during security validation.").waitFor();
   const axe=await new AxeBuilder({page}).withTags(["wcag2a","wcag2aa","wcag21aa"]).analyze();
   assert.deepEqual(axe.violations,[],`${route} at ${width}px`);
   assert(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1));
   await page.screenshot({path:`../docs/screenshots/accounts/live-${route}-${width}.png`,fullPage:true});
   evidence.pages.push({route,width,axe_violations:0,horizontal_overflow:false});
  }
  await page.goto(`${evidence.origin}/privacy/`);
  await page.getByRole("heading",{name:"Privacy information",exact:true}).waitFor();
  const privacyAxe=await new AxeBuilder({page}).withTags(["wcag2a","wcag2aa","wcag21aa"]).analyze();
  assert.deepEqual(privacyAxe.violations,[],`privacy at ${width}px`);
  assert(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1));
  await page.screenshot({path:`../docs/screenshots/accounts/live-privacy-${width}.png`,fullPage:true});
  evidence.pages.push({route:"privacy",width,axe_violations:0,horizontal_overflow:false});
 }
 await page.goto(`${evidence.origin}/onboarding/`);
 await page.waitForURL("**/auth/login");
 evidence.anonymous_onboarding_redirect="/auth/login";
 await writeFile("../docs/saas-public-browser-verification.json",JSON.stringify(evidence,null,2)+"\n");
 console.log(JSON.stringify(evidence));
} finally {await browser.close();}
