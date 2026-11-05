// Los botones del tablón del SoloQ Challenge que despiertan al robot:
//   · «↻ Actualizar» (público, sin contraseña): { accion: "actualizar" } lanza una pasada si no hay otra en curso;
//     { accion: "estado" } dice si hay una. Solo hay una pasada manual a la vez para todo el mundo.
//   · «Forzar la pasada» (el jefe): { clave } como siempre.
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

const REPO = () => Deno.env.get("GITHUB_REPO") || "Ialtube/feed-diario";
const GH = () => ({
  Authorization: `Bearer ${Deno.env.get("GITHUB_TOKEN")}`,
  Accept: "application/vnd.github+json",
  "X-GitHub-Api-Version": "2022-11-28",
  "User-Agent": "soloq-forzar",
});

// La pasada manual en curso (el workflow las llama «SoloQ manual», ver run-name en soloq.yml): en cola, corriendo,
// o lanzada hace nada y todavía sin aparecer. Devuelve cuándo empezó, o null si no hay ninguna.
async function pasadaManual(): Promise<number | null> {
  const r = await fetch(
    `https://api.github.com/repos/${REPO()}/actions/workflows/soloq.yml/runs?event=workflow_dispatch&per_page=10`,
    { headers: GH() },
  );
  if (!r.ok) throw new Error(`GitHub dice ${r.status}`);
  const { workflow_runs = [] } = await r.json();
  const vivas = workflow_runs
    .filter((w: { name?: string; display_title?: string }) => (w.display_title || w.name || "").startsWith("SoloQ manual"))
    .filter((w: { status: string; created_at: string }) => w.status !== "completed" || Date.now() - Date.parse(w.created_at) < 15000)
    .map((w: { created_at: string }) => Date.parse(w.created_at));
  return vivas.length ? Math.min(...vivas) : null;
}

const seg = (desde: number) => Math.max(0, Math.round((Date.now() - desde) / 1000));

Deno.serve(async (req) => {
  if (req.method === "OPTIONS") return new Response("ok", { headers: CORS });
  if (req.method !== "POST") return reply(405, { error: "Solo POST" });

  const { clave, accion } = await req.json().catch(() => ({}));

  if (accion === "estado" || accion === "actualizar") {
    try {
      let desde = await pasadaManual();
      if (desde === null && accion === "actualizar") {
        const t0 = Date.now();
        const gh = await fetch(`https://api.github.com/repos/${REPO()}/actions/workflows/soloq.yml/dispatches`, {
          method: "POST",
          headers: GH(),
          body: JSON.stringify({ ref: "main" }),
        });
        if (gh.status !== 204) return reply(502, { error: `GitHub dice ${gh.status}: ${await gh.text()}` });
        desde = t0;
        // GitHub tarda unos segundos en mostrar la pasada nueva: se espera a verla para que, mientras tanto,
        // nadie más pueda lanzar otra.
        for (let i = 0; i < 8; i++) {
          await new Promise((ok) => setTimeout(ok, 1000));
          if ((await pasadaManual()) !== null) break;
        }
      }
      return reply(200, desde === null ? { enCurso: false } : { enCurso: true, transcurrido: seg(desde) });
    } catch (e) {
      return reply(502, { error: String(e) });
    }
  }

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
