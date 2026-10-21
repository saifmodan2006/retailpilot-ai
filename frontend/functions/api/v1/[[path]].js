// Same-origin BFF transport. Only the fixed RetailPilot API is reachable.
// Provider/session credentials never enter frontend JavaScript or build variables.
export async function onRequest({request}) {
  if (!["GET", "POST", "PATCH", "OPTIONS"].includes(request.method))
    return new Response("Method not allowed", {status:405});
  const url = new URL(request.url);
  const upstream = new URL("https://retailpilot-ai-api.onrender.com");
  upstream.pathname = url.pathname;
  upstream.search = url.search;
  const headers = new Headers();
  for (const name of ["accept","authorization","content-type","origin","x-rp-csrf"])
    if (request.headers.has(name)) headers.set(name, request.headers.get(name));
  const cookies = (request.headers.get("cookie") || "").split(";").map(s=>s.trim()).filter(s=>s.startsWith("rp-account=")||s.startsWith("rp-auth-challenge="));
  if (cookies.length) headers.set("cookie", cookies.join("; "));
  try {
    const response = await fetch(upstream, {method:request.method, headers,
      body:["GET","HEAD"].includes(request.method)?undefined:request.body, redirect:"manual"});
    const output = new Headers(response.headers);
    output.set("Cache-Control","no-store");
    output.delete("access-control-allow-origin");
    output.delete("access-control-allow-credentials");
    return new Response(response.body,{status:response.status,headers:output});
  } catch {
    return Response.json({detail:"The API is waking up or temporarily unavailable. Please retry shortly."},{status:503,headers:{"Cache-Control":"no-store","Retry-After":"15"}});
  }
}
