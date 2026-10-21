import {test, expect, type Page} from "@playwright/test";
import AxeBuilder from "@axe-core/playwright";
import {mkdir, writeFile} from "node:fs/promises";

test.skip(process.env.SAAS_E2E !== "1", "Requires the isolated loopback identity mock and disposable database.");
const passphrase="fictional-test-passphrase";
const headers={Origin:"http://127.0.0.1:5174","X-RP-CSRF":"1"};
async function register(page:Page,email:string) {
 await page.goto("/auth/signup");
 await page.getByLabel("Email address").fill(email);
 await page.getByLabel("Password",{exact:true}).fill(passphrase);
 await page.getByRole("button",{name:"Create free account",exact:true}).click();
 await expect(page).toHaveURL(/auth\/verify/);
 await page.getByLabel("Email address").fill(email);
 await page.getByLabel("Verification code").fill("123456");
 await page.getByRole("button",{name:"Verify code"}).click();
 await expect(page).toHaveURL(/onboarding/);
}

test("verified account, resumable onboarding, profile, workspaces, team, role revocation and logout",async({page,browser})=>{
 await register(page,"owner@example.test");
 await page.getByLabel("Full name").fill("Fictional Owner");
 await page.getByLabel("Job title").fill("Portfolio retail analyst");
 await page.getByRole("button",{name:"Save and continue"}).click();
 await page.getByLabel("Organization name").fill("Fictional Private Retail");
 await page.getByRole("button",{name:"Save and continue"}).click();
 await page.reload();
 await expect(page.getByLabel("Workspace name")).toBeVisible();
 await page.getByRole("button",{name:"Save and continue"}).click();
 await page.getByLabel(/Load fictional retail data/).check();
 await page.getByRole("button",{name:"Create private workspace"}).click();
 await expect(page).toHaveURL(/app\/overview/,{timeout:150000});
 await expect(page.getByText("Welcome back, Fictional Owner.")).toBeVisible();
 await page.reload();
 await expect(page.getByText("Welcome back, Fictional Owner.")).toBeVisible();
 await page.goto("/app/profile");
 await page.getByLabel("Job title").fill("Senior fictional analyst");
 await page.getByRole("button",{name:"Save profile"}).click();
 await expect(page.getByRole("status")).toContainText("Saved");
 await page.goto("/app/workspaces");
 await page.getByLabel("Organization name").fill("Fictional Second Retail");
 await page.getByRole("button",{name:"Create private organization"}).click();
 await expect(page).toHaveURL(/app\/overview/);
 await expect(page.getByText("Your private workspace is ready",{exact:true})).toBeVisible();
 await page.goto("/app/workspaces");
 await page.getByText("Fictional Private Retail",{exact:true}).locator("..").getByRole("button").click();
 await expect(page).toHaveURL(/app\/overview/);
 await page.goto("/app/team");
 await page.getByLabel("Colleague's email").fill("member@example.test");
 await page.getByRole("button",{name:"Create invitation"}).click();
 const invite=await page.getByLabel("Single-use invitation link (shown once)").inputValue();
 await expect(page.getByRole("status")).toContainText("email was not sent");
 await page.getByRole("button",{name:"Hide link"}).click();
 const member=await browser.newContext({baseURL:process.env.E2E_BASE_URL});const memberPage=await member.newPage();
 await register(memberPage,"member@example.test");
 await memberPage.goto(invite);
 await memberPage.getByRole("button",{name:"Confirm decision"}).click();
 await expect(memberPage).toHaveURL(/app\/overview/);
 expect((await memberPage.request.post("/api/v1/reports",{headers,data:{kind:"Daily sales MIS"}})).status()).toBe(403);
 await expect(memberPage.getByRole("button",{name:"Use demo manager"})).toHaveCount(0);
 await page.reload();
 await page.getByLabel("Role for member@example.test").selectOption("analyst");
 await expect(page.getByRole("status")).toContainText("Membership role updated");
 expect((await memberPage.request.post("/api/v1/approvals/1/decision",{headers,data:{decision:"approve",reason:"Forbidden viewer attempt"}})).status()).toBe(403);
 await page.getByText("member@example.test",{exact:true}).first().locator("..").getByRole("button",{name:"Remove"}).click();
 await expect(page.getByRole("status")).toContainText("Membership removed");
 expect((await memberPage.request.get("/api/v1/analytics")).status()).toBe(403);
 await member.close();
 const evidence=[];
 await mkdir("../docs/screenshots/accounts",{recursive:true});
 for(const [width,height] of [[1440,1000],[768,1024],[390,844]]) {
  await page.setViewportSize({width,height});
  for(const route of ["profile","account","organization","workspaces","team"]) {
   await page.goto(`/app/${route}`);
   await expect(page.locator(".account-section").first()).toBeVisible();
   await expect(page.locator(".loading")).toHaveCount(0);
   const axe=await new AxeBuilder({page}).withTags(["wcag2a","wcag2aa","wcag21aa"]).analyze();
   expect(axe.violations,route).toEqual([]);
   expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1),route).toBe(true);
   await page.screenshot({path:`../docs/screenshots/accounts/${route}-${width}.png`,fullPage:true});
   evidence.push({route,width,violations:axe.violations.length,incomplete:axe.incomplete.length});
  }
 }
 await writeFile("../docs/saas-browser-accessibility.json",JSON.stringify({provider:"mocked test boundary; not live Supabase",screens:evidence},null,2));
 await page.goto("/app/account");
 await page.getByRole("button",{name:"Sign out",exact:true}).click();
 await expect(page).toHaveURL(/auth\/login/);
 expect((await page.request.get("/api/v1/account/profile")).status()).toBe(401);
 await page.getByLabel("Email address").fill("owner@example.test");await page.getByLabel("Password",{exact:true}).fill(passphrase);
 await page.getByRole("button",{name:"Sign in",exact:true}).click();
 await expect(page).toHaveURL(/app\/overview/);
 await page.goto("/app/profile");
 await expect(page.getByLabel("Job title")).toHaveValue("Senior fictional analyst");
});

test("password recovery, expired session state and honest unconfigured authentication screens",async({page})=>{
 await register(page,"other@example.test");
 await page.goto("/auth/forgot-password");
 await page.getByLabel("Email address").fill("other@example.test");
 await page.getByRole("button",{name:"Send recovery email"}).click();
 await expect(page.getByRole("status")).toContainText("eligible account");
 await page.getByRole("link",{name:"I have a recovery code"}).click();
 await expect(page.getByRole("heading",{name:"Recover your account",exact:true})).toBeVisible();
 await page.getByLabel("Email address").fill("other@example.test");await page.getByLabel("Verification code").fill("123456");
 await page.getByRole("button",{name:"Verify code"}).click();
 await expect(page).toHaveURL(/auth\/reset-password/);
 await page.getByLabel("Password",{exact:true}).fill("new-fictional-passphrase");
 await page.getByRole("button",{name:"Save new password"}).click();
 await expect(page).toHaveURL(/auth\/login/);
 await page.getByLabel("Email address").fill("other@example.test");await page.getByLabel("Password",{exact:true}).fill("new-fictional-passphrase");await page.getByRole("button",{name:"Sign in",exact:true}).click();
 await expect(page).toHaveURL(/onboarding/);
 await page.context().clearCookies();await page.goto("/app/profile");
 await expect(page).toHaveURL(/auth\/session-expired/);
 await page.route("**/api/v1/auth/config",route=>route.fulfill({json:{configured:false,registration:false,google:false}}));
 for(const width of [1440,768,390]) {
  await page.setViewportSize({width,height:900});
  for(const route of ["signup","login","verify","forgot-password","recovery","reset-password","session-expired"]) {
   await page.goto(`/auth/${route}`);
   await expect(page.getByText("Private accounts are not open yet.")).toBeVisible();
   expect(await page.getByRole("button",{name:/Google/}).count()).toBe(0);
   expect((await new AxeBuilder({page}).withTags(["wcag2a","wcag2aa","wcag21aa"]).analyze()).violations,route).toEqual([]);
   expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1),route).toBe(true);
   await page.screenshot({path:`../docs/screenshots/accounts/auth-${route}-${width}.png`,fullPage:true});
  }
 }
});

test("default-template PKCE email links, callback, recovery and responsive onboarding",async({page})=>{
 await page.goto("/auth/signup");
 await page.getByLabel("Email address").fill("links@example.test");
 await page.getByLabel("Password",{exact:true}).fill(passphrase);
 await page.getByRole("button",{name:"Create free account",exact:true}).click();
 await expect(page).toHaveURL(/auth\/verify/);
 await page.goto("/auth/callback?code=link-links-signup");
 await expect(page).toHaveURL(/\/auth\/callback$/);
 await page.getByRole("button",{name:"Continue verification"}).click();
 await expect(page).toHaveURL(/onboarding/);
 expect(await page.evaluate(()=>localStorage.getItem("rp-token"))).toBeNull();
 const cookies=await page.context().cookies();
 expect(cookies.find(c=>c.name==="rp-account")?.httpOnly).toBe(true);
 expect(cookies.find(c=>c.name==="rp-auth-challenge")).toBeUndefined();
 const screens=[];
 for(const width of [1440,768,390]) {
  await page.setViewportSize({width,height:900});
  await page.goto("/onboarding");await expect(page.getByLabel("Full name")).toBeVisible();
  const axe=await new AxeBuilder({page}).withTags(["wcag2a","wcag2aa","wcag21aa"]).analyze();
  expect(axe.violations).toEqual([]);
  expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1)).toBe(true);
  await page.screenshot({path:`../docs/screenshots/accounts/onboarding-${width}.png`,fullPage:true});
  screens.push({route:"onboarding",width,violations:axe.violations.length});
  await page.goto("/auth/callback");
  await expect(page.getByText(/No pending email-link code/)).toBeVisible();
  const callback=await new AxeBuilder({page}).withTags(["wcag2a","wcag2aa","wcag21aa"]).analyze();
  expect(callback.violations).toEqual([]);
  await page.screenshot({path:`../docs/screenshots/accounts/callback-${width}.png`,fullPage:true});
  screens.push({route:"callback",width,violations:callback.violations.length});
 }
 await writeFile("../docs/saas-pkce-browser-verification.json",JSON.stringify({provider:"mocked provider; real application and SDK contract separately tested",screens},null,2));
 await page.goto("/auth/forgot-password");await page.getByLabel("Email address").fill("links@example.test");
 await page.getByRole("button",{name:"Send recovery email"}).click();
 await expect(page.getByRole("status")).toContainText("eligible account");
 await page.goto("/auth/callback?code=link-links-recovery");await page.getByRole("button",{name:"Continue verification"}).click();
 await expect(page).toHaveURL(/auth\/reset-password/);
 await page.getByLabel("Password",{exact:true}).fill("new-fictional-link-passphrase");
 await page.getByRole("button",{name:"Save new password"}).click();
 await expect(page).toHaveURL(/auth\/login/);
 expect((await page.request.get("/api/v1/account/profile")).status()).toBe(401);
});
