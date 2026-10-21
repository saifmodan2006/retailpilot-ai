import React from "react";
import ReactDOM from "react-dom/client";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { BrowserRouter, useLocation, useNavigate } from "react-router-dom";
import App from "./App";
import AuthPage from "./pages/Accounts";
import {Onboarding} from "./pages/WorkspaceAccounts";
import {InvitationPage} from "./pages/Team";
import AuthCallback from "./pages/AuthCallback";
import "@fontsource-variable/inter";
import "./style.css";
import "./premium.css";
const client = new QueryClient({
  defaultOptions: {
    queries: { retry: 1, staleTime: 30000, refetchOnWindowFocus: false },
  },
});
function ProductRoutes() {
  const location = useLocation(), navigate = useNavigate();
  React.useEffect(() => {
    const expired = () => { sessionStorage.removeItem("rp-account-active"); client.clear(); navigate("/auth/session-expired"); };
    window.addEventListener("rp-session-expired", expired);
    return () => window.removeEventListener("rp-session-expired", expired);
  }, [navigate]);
  return location.pathname === "/auth/callback" ? <AuthCallback/> : location.pathname === "/auth/invitation" ? <InvitationPage/> : location.pathname.startsWith("/auth/") ? <AuthPage key={location.pathname}/> : location.pathname === "/onboarding" ? <Onboarding/> : <App/>;
}
ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <QueryClientProvider client={client}>
      <BrowserRouter>
        <ProductRoutes />
      </BrowserRouter>
    </QueryClientProvider>
  </React.StrictMode>,
);
