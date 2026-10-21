import {useEffect, useState} from "react";
import {Link, useNavigate} from "react-router-dom";
import {useQueryClient} from "@tanstack/react-query";
import {api} from "../api";
import {AccountFrame} from "./Accounts";
import {Feedback, useAccountAction} from "./WorkspaceAccounts";

export default function AuthCallback() {
 const [code]=useState(()=>new URLSearchParams(window.location.search).get("code")||"");
 const action=useAccountAction(),navigate=useNavigate(),qc=useQueryClient();
 useEffect(()=>{window.history.replaceState(null,"","/auth/callback");},[]);
 return <AccountFrame title="Complete verification" subtitle="Finish secure sign-in on the browser that started it."><Feedback {...action}/>{code?<><p>Continue to verify the single-use authorization code with your identity provider and open your private workspace. Provider tokens are never stored in browser JavaScript.</p><button className="btn primary" disabled={action.busy} onClick={()=>action.run(async()=>{const result=await api("/auth/exchange",{method:"POST",body:JSON.stringify({code})});localStorage.removeItem("rp-token");sessionStorage.setItem("rp-account-active","true");qc.clear();navigate(result.recovery?"/auth/reset-password":result.profile.onboarding?.completed?"/app/overview":"/onboarding/");})}>{action.busy?"Verifying…":"Continue verification"}</button></>:<div className="account-notice">No pending authorization code is present. If you changed your email, sign in again after confirming both addresses. Otherwise start sign-in again or request a fresh email on this browser.</div>}<div className="account-links"><Link to="/auth/login">Sign in</Link><Link to="/auth/forgot-password">Request account recovery</Link><Link to="/auth/verify">Enter a verification code</Link></div></AccountFrame>;
}
