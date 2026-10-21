import {useEffect, useRef, useState} from "react";
import {useQuery} from "@tanstack/react-query";
import {api} from "./api";

type TurnstileAPI = {
 render: (element: HTMLElement, options: Record<string, unknown>) => string;
 remove: (id: string) => void;
 reset: (id: string) => void;
};
declare global {interface Window {turnstile?: TurnstileAPI}}
let loading: Promise<void> | undefined;
function loadTurnstile() {
 if(window.turnstile) return Promise.resolve();
 if(!loading) loading=new Promise<void>((resolve,reject)=>{
  const script=document.createElement("script");
  script.src="https://challenges.cloudflare.com/turnstile/v0/api.js?render=explicit";
  script.async=true;script.defer=true;
  script.onload=()=>resolve();script.onerror=()=>{loading=undefined;reject(new Error("Bot protection could not load. Please retry."));};
  document.head.appendChild(script);
 });
 return loading;
}
function Widget({siteKey}:{siteKey:string}) {
 const target=useRef<HTMLDivElement>(null),[token,setToken]=useState(""),[error,setError]=useState("");
 useEffect(()=>{
  let stopped=false,id:string|undefined;
  const form=target.current?.closest("form");
  const reset=()=>{setTimeout(()=>{if(!stopped&&id&&window.turnstile){setToken("");window.turnstile.reset(id);}},0);};
  void loadTurnstile().then(()=>{
   if(stopped||!target.current||!window.turnstile)return;
   id=window.turnstile.render(target.current,{sitekey:siteKey,theme:"light",size:"flexible","response-field":false,
    callback:(value:string)=>{setToken(value);setError("");},"expired-callback":()=>setToken(""),
    "error-callback":()=>{setToken("");setError("Bot protection is temporarily unavailable. Reload and try again.");}});
  }).catch(e=>{if(!stopped)setError((e as Error).message);});
  form?.addEventListener("submit",reset);
  return()=>{stopped=true;form?.removeEventListener("submit",reset);if(id)window.turnstile?.remove(id);};
 },[siteKey]);
 return <div className="account-captcha"><div ref={target}/><input type="hidden" name="captcha_token" value={token}/>{error&&<p role="alert">{error}</p>}</div>;
}
export function AccountCaptcha() {
 const {data}=useQuery({queryKey:["auth-capabilities"],queryFn:()=>api("/auth/config"),staleTime:30000});
 return data?.captcha&&data.captcha_site_key?<Widget siteKey={data.captcha_site_key}/>:null;
}
