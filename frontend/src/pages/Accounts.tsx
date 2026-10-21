import {useEffect, useRef, useState, type FormEvent, type ReactNode} from "react";
import {Link, useLocation, useNavigate} from "react-router-dom";
import {useQueryClient} from "@tanstack/react-query";
import {ArrowLeft, BarChart3, Eye, EyeOff, Loader2, ShieldCheck} from "lucide-react";
import {api, type Row} from "../api";
import "../accounts.css";

export function AccountFrame({title, subtitle, children}: {title:string;subtitle:string;children:ReactNode}) {
 return <main className="account-layout"><aside className="account-story"><Link to="/" className="brand"><BarChart3/> RetailPilot AI</Link><div><span className="eyebrow">YOUR BUSINESS, CONNECTED</span><h1>A private workspace.<br/>A clearer retail day.</h1><p>Bring your people, reporting and inventory decisions together with access you control.</p><p><ShieldCheck size={18}/> Verified identity. Organization permissions. An auditable workflow.</p></div><small>Existing demo available without an account.</small></aside><section className="account-main"><Link to="/" className="text-link"><ArrowLeft size={15}/> Back to RetailPilot</Link><div className="account-card"><h1>{title}</h1><p>{subtitle}</p>{children}</div></section></main>;
}

export function PasswordField({name="password", label="Password", minimum=12,login=false}: {name?:string;label?:string;minimum?:number;login?:boolean}) {
 const [visible,setVisible]=useState(false);
 return <label className="account-field">{label}<span className="password-field"><input name={name} type={visible?"text":"password"} minLength={minimum} maxLength={128} autoComplete={name==="current_password"||login?"current-password":"new-password"} required/><button type="button" aria-label={visible?`Hide ${label.toLowerCase()}`:`Show ${label.toLowerCase()}`} onClick={()=>setVisible(!visible)}>{visible?<EyeOff size={18}/>:<Eye size={18}/>}</button></span></label>;
}

export default function AuthPage() {
 const location=useLocation(),navigate=useNavigate(),qc=useQueryClient();
 const mode=location.pathname.split("/")[2]||"login";
 const [config,setConfig]=useState<Row|null>(null),[busy,setBusy]=useState(false),[error,setError]=useState(""),[notice,setNotice]=useState("");
 const errorRef=useRef<HTMLDivElement>(null);
 useEffect(()=>{api("/auth/config").then(setConfig).catch(()=>setError("The service is temporarily unavailable. Please retry shortly."));},[]);
 useEffect(()=>{if(error)errorRef.current?.focus();},[error]);
 const names:Record<string,[string,string]>={login:["Welcome back","Sign in to your private retail workspace."],signup:["Create your account","Start with a verified email and your own organization."],verify:["Verify your email","Open the email link in this browser. If your provider sent a code, enter it below."],"forgot-password":["Reset your password","Request a recovery email for your verified address."],"reset-password":["Choose a new password","Your verified recovery session expires after ten minutes."],recovery:["Recover your account","Open your recovery email link. If your provider sent a code, you can enter it here."],"session-expired":["Your session has expired","Sign in again to continue. Your organization data remains saved."]};
 const [title,subtitle]=names[mode]||names.login;
 async function submit(event:FormEvent<HTMLFormElement>) {
  event.preventDefault();setBusy(true);setError("");setNotice("");
  const values=Object.fromEntries(new FormData(event.currentTarget));
  try {
   if(mode==="signup") {const r=await api("/auth/signup",{method:"POST",body:JSON.stringify(values)});setNotice(r.message);navigate("/auth/verify");}
   else if(mode==="forgot-password") {const r=await api("/auth/recover",{method:"POST",body:JSON.stringify(values)});setNotice(r.message);}
   else if(mode==="reset-password") {const r=await api("/auth/reset-password",{method:"POST",body:JSON.stringify(values)});sessionStorage.removeItem("rp-account-active");qc.clear();setNotice(r.message);navigate("/auth/login");}
   else {
    const r=await api(mode==="login"?"/auth/login":"/auth/verify",{method:"POST",body:JSON.stringify({...values,...(mode!=="login"?{kind:mode==="recovery"?"recovery":"signup"}:{})})});
    localStorage.removeItem("rp-token");sessionStorage.setItem("rp-account-active","true");qc.clear();
    navigate(r.recovery?"/auth/reset-password":r.profile.onboarding?.completed?"/app/overview":"/onboarding/");
   }
  } catch(e){setError((e as Error).message);}finally{setBusy(false);}
 }
 const unavailable=config&&!config.configured;
 return <AccountFrame title={title} subtitle={subtitle}>
  {error&&<div className="error" role="alert" ref={errorRef} tabIndex={-1}>{error}</div>}{notice&&<div className="toast" role="status">{notice}</div>}
  {unavailable&&<div className="account-notice" role="status"><strong>Private accounts are not open yet.</strong><p>Identity and verified email delivery are awaiting configuration. You can explore the isolated fictional demo today.</p><Link to="/">Try the live demo</Link></div>}
  {mode==="session-expired"?<Link className="btn primary" to="/auth/login">Sign in again</Link>:<form onSubmit={submit}>
   {mode!=="reset-password"&&<label className="account-field">Email address<input name="email" type="email" autoComplete="email" maxLength={254} required/></label>}
   {["signup","login","reset-password"].includes(mode)&&<><PasswordField minimum={mode==="login"?1:12} login={mode==="login"}/><small>Use at least 12 characters for a new password.</small></>}
   {["verify","recovery"].includes(mode)&&<label className="account-field">Verification code<input name="token" inputMode="numeric" autoComplete="one-time-code" pattern="[0-9]{6,10}" maxLength={10} required/></label>}
   <button className="btn primary" disabled={busy||!config||Boolean(unavailable)||(mode==="signup"&&!config.registration)}>{busy&&<Loader2 size={17} className="spin"/>}{mode==="login"?"Sign in":mode==="signup"?"Create free account":mode==="forgot-password"?"Send recovery email":mode==="reset-password"?"Save new password":"Verify code"}</button>
   {mode==="verify"&&<button className="btn" type="button" disabled={busy||Boolean(unavailable)||!config} onClick={async e=>{const email=new FormData(e.currentTarget.form!).get("email");setBusy(true);setError("");try{const result=await api("/auth/resend",{method:"POST",body:JSON.stringify({email})});setNotice(result.message);}catch(err){setError((err as Error).message);}finally{setBusy(false);}}}>Resend verification email</button>}
   {mode==="signup"&&config?.configured&&!config.registration&&<p className="account-notice">Registration is closed during security validation.</p>}
  </form>}
  <div className="account-links"><Link to="/auth/login">Sign in</Link><Link to="/auth/signup">Create free account</Link><Link to="/auth/forgot-password">Forgot password?</Link><Link to="/auth/recovery">Account recovery</Link></div>
  {mode==="forgot-password"&&<Link className="text-link" to="/auth/recovery">I have a recovery code</Link>}
 </AccountFrame>;
}
