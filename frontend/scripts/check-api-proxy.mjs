import assert from "node:assert/strict";
import {onRequest} from "../functions/api/v1/[[path]].js";

const original=globalThis.fetch;
let observed;
try {
 globalThis.fetch=async(url,options)=>{
  observed={url:String(url),options};
  return new Response(JSON.stringify({ok:true}),{headers:{
   "Content-Type":"application/json","Set-Cookie":"rp-account=fictional; HttpOnly; Secure; SameSite=Lax; Path=/api/v1",
   "Access-Control-Allow-Origin":"*","Cache-Control":"public,max-age=300"}});
 };
 const result=await onRequest({request:new Request("https://retailpilot-ai.pages.dev/api/v1/account/profile?next=https://attacker.example",{
  headers:{Cookie:"unrelated-private-cookie=never-forward; rp-account=fictional-session; rp-auth-challenge=fictional-pkce",Origin:"https://retailpilot-ai.pages.dev","X-RP-CSRF":"1","X-Organization":"forged"}})});
 assert(observed.url.startsWith("https://retailpilot-ai-api.onrender.com/api/v1/account/profile?"));
 assert.equal(observed.options.headers.get("cookie"),"rp-account=fictional-session; rp-auth-challenge=fictional-pkce");
 assert.equal(observed.options.headers.get("x-organization"),null);
 assert.equal(observed.options.redirect,"manual");
 assert.equal(result.headers.get("cache-control"),"no-store");
 assert.equal(result.headers.get("access-control-allow-origin"),null);
 assert.match(result.headers.get("set-cookie"),/HttpOnly; Secure; SameSite=Lax/);
 assert.equal((await onRequest({request:new Request("https://retailpilot-ai.pages.dev/api/v1/me",{method:"DELETE"})})).status,405);
 globalThis.fetch=async()=>{throw new Error("fictional upstream outage");};
 const failed=await onRequest({request:new Request("https://retailpilot-ai.pages.dev/api/v1/me")});
 assert.equal(failed.status,503);
 assert.equal(failed.headers.get("retry-after"),"15");
 console.log("API proxy: fixed upstream, cookie isolation, header isolation, redirect handling, no-store, HttpOnly forwarding, method restrictions and outage response passed.");
} finally {globalThis.fetch=original;}
