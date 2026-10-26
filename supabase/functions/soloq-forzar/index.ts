// El botón «Forzar la pasada» del tablón del SoloQ Challenge.
// Comprueba la contraseña del jefe en la base de datos (rpc soloq_forzar) y, si es buena, le pide a
// GitHub que lance ya el workflow del robot (.github/workflows/soloq.yml).
// Secretos que necesita (Supabase → Edge Functions → Secrets):
//   GITHUB_TOKEN  token «fine-grained» con permiso Actions: Read and write sobre el repositorio
//   GITHUB_REPO   dueño/repositorio, p. ej. Ialtube/feed-diario
// SUPABASE_URL lo pone Supabase solo; la clave pública es la misma que manda el tablón.
// Hay que desplegarla SIN verificación de JWT (la clave publicable del tablón no es un JWT).

const CORS = {
  "Access-Control-Allow-Origin": "*",
  "Access-Control-Allow-Headers": "authorization, apikey, content-type",
  "Access-Control-Allow-Methods": "POST, OPTIONS",
};

function reply(status: number, body: Record<string, unknown>) {
  return new Response(JSON.stringify(body), { status, headers: { ...CORS, "Content-Type": "application/json" } });
}

Deno.serve(async (req) => {
  if (req.method === "OPTIONS") return new Response("ok", { headers: CORS });
  if (req.method !== "POST") return reply(405, { error: "Solo POST" });

  const { clave } = await req.json().catch(() => ({}));
  if (!clave || typeof clave !== "string") return reply(400, { error: "Falta la contraseña" });

  const url = Deno.env.get("SUPABASE_URL")!;
  const anon = req.headers.get("apikey") || Deno.env.get("SUPABASE_ANON_KEY") || "";
  const check = await fetch(`${url}/rest/v1/rpc/soloq_forzar`, {
    method: "POST",
    headers: { apikey: anon, Authorization: `Bearer ${anon}`, "Content-Type": "application/json" },
    body: JSON.stringify({ clave }),
  });
  if (!check.ok) {
    const e = await check.json().catch(() => ({}));
    return reply(check.status === 401 || check.status === 403 ? 403 : 400, { error: e.message || "No" });
  }

  const repo = Deno.env.get("GITHUB_REPO") || "Ialtube/feed-diario";
  const gh = await fetch(`https://api.github.com/repos/${repo}/actions/workflows/soloq.yml/dispatches`, {
    method: "POST",
    headers: {
      Authorization: `Bearer ${Deno.env.get("GITHUB_TOKEN")}`,
      Accept: "application/vnd.github+json",
      "X-GitHub-Api-Version": "2022-11-28",
      "User-Agent": "soloq-forzar",
    },
    body: JSON.stringify({ ref: "main" }),
  });
  if (gh.status !== 204) return reply(502, { error: `GitHub dice ${gh.status}: ${await gh.text()}` });
  return reply(200, { ok: true });
});
