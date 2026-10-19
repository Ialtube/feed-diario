# El Rincón del Feeder

Un periódico satírico que se escribe solo cada mañana con las partidas de League of Legends de tu grupo de amigos.

Cada día, un robot gratuito de GitHub:

1. Descarga de la **API oficial de Riot** las partidas nuevas de cada amigo de `friends.json`.
2. Calcula de cada uno: victorias y derrotas, muertes, KDA, **cuota de daño y de oro dentro de su equipo**, si fue el que menos daño hizo, participación en kills, tiempo muerto, farmeo, visión, pings, rendiciones, rachas, dúos entre amigos y derbis (amigos en equipos contrarios).
3. Escribe las noticias del día (portada para el peor, sucesos, economía, deportes...) y la **clasificación de la vergüenza**.
4. Regenera la web (portada, hemeroteca y una ficha por jugador) y la publica.
5. Opcional: avisa en un canal de **Discord** con la portada.

Todo es gratis. Claude para titulares más graciosos es opcional y cuesta céntimos.

```
GitHub Actions (cada día 08:15)
   └─ python -m roast run
        ├─ Riot API ──► data/matches/*.jsonl   (partidas, resumidas)
        ├─ análisis  ──► data/editions/AAAA-MM-DD.json
        ├─ (Claude)  ──► titulares reescritos (opcional)
        ├─ web       ──► docs/  ──► GitHub Pages o Cloudflare Pages
        └─ Discord   ──► aviso con la portada (opcional)
```

> **¿Por qué no rewind.lol?** No tiene API pública y obliga a crear el perfil a mano desde su web. La API de Riot da más detalle (el daño, el oro y la visión de cada partida, comparados con el resto del equipo) y es oficial y gratuita.

---

## Ver cómo queda sin configurar nada

Necesitas Python 3.10 o superior.

```bash
python -m roast demo
```

Genera 7 días de partidas inventadas y la web en `demo_site/index.html`. Ábrela con el navegador.

```bash
python -m unittest discover -s tests
```

---

## Puesta en marcha (unos 20 minutos)

### 1. Clave de la API de Riot

1. Entra en <https://developer.riotgames.com> con tu cuenta de Riot.
2. Arriba verás una **Development API Key**. Sirve para probar, pero **caduca cada 24 horas**.
3. Para que el robot funcione solo, pide una **Personal API Key**: *Register Product → Personal API Key*. Descríbelo como «web privada para un grupo de amigos que muestra sus estadísticas diarias». Riot suele aprobarla en unos días y no caduca.
4. Mientras llega, puedes usar la de desarrollo y renovarla a mano cada día (paso 3).

Con la clave puedes comprobar en local que encuentra a todos:

```bash
RIOT_API_KEY=RGAPI-xxxx python -m roast check
```

En PowerShell: `$env:RIOT_API_KEY="RGAPI-xxxx"; python -m roast check`

### 2. Sube la carpeta a GitHub

1. Crea una cuenta en <https://github.com> si no tienes.
2. *New repository* → nombre, por ejemplo, `feed-diario`.
   - **Público** si vas a usar GitHub Pages (opción A).
   - **Privado** si vas a usar Cloudflare Pages con acceso restringido (opción B).
3. Sube esta carpeta. Lo más fácil es con [GitHub Desktop](https://desktop.github.com): *Add existing repository*, eliges la carpeta y *Publish*. Con la terminal:

```bash
git init
git add .
git commit -m "El Rincón del Feeder"
git branch -M main
git remote add origin https://github.com/TU_USUARIO/feed-diario.git
git push -u origin main
```

### 3. Mete los secretos

En el repositorio: *Settings → Secrets and variables → Actions*.

| Tipo | Nombre | Valor | ¿Obligatorio? |
|---|---|---|---|
| Secret | `RIOT_API_KEY` | Tu clave de Riot | Sí |
| Secret | `DISCORD_WEBHOOK_URL` | URL del webhook del canal | No |
| Secret | `ANTHROPIC_API_KEY` | Clave de la API de Claude | No |
| Variable | `SITE_URL` | URL pública de la web (para el enlace de Discord) | No |

Para el webhook de Discord: en tu servidor, *Ajustes del canal → Integraciones → Webhooks → Nuevo webhook → Copiar URL*.

### 4. Publica la web (elige una)

**Opción A: GitHub Pages.** Lo más sencillo; la web es pública, pero la URL solo la conoce quien se la pases.

1. *Settings → Pages → Build and deployment → Deploy from a branch*.
2. Rama `main`, carpeta `/docs`, *Save*.
3. En un par de minutos estará en `https://TU_USUARIO.github.io/feed-diario/`. Pon esa URL en la variable `SITE_URL`.

**Opción B: Cloudflare Pages + Access.** Repo privado y web cerrada: solo entran los correos que tú digas.

1. Cuenta gratis en <https://dash.cloudflare.com> → *Workers & Pages → Create → Pages → Connect to Git*.
2. Elige el repo. *Build command*: vacío. *Build output directory*: `docs`.
3. Cada vez que el robot guarde la edición del día, Cloudflare la publica sola.
4. Para cerrarla: *Zero Trust → Access → Applications → Add → Self-hosted*, pon el dominio `*.pages.dev` del proyecto y una regla *Emails* con los correos de tus amigos. Entran con un código que les llega al correo. El plan gratuito permite hasta 50 personas.

### 5. Saca la primera edición

*Actions → Edición diaria → Run workflow*. En 1–2 minutos verás la edición en la web, y desde entonces sale sola cada mañana (06:15 UTC, que son las 08:15 en verano y 07:15 en invierno en España). Cada edición cubre las partidas desde la anterior.

> GitHub puede retrasar los trabajos programados unos minutos en horas de mucho uso. Es normal.

---

## Añadir o quitar amigos

Edita `friends.json`:

```json
{"riot_id": "Nombre#TAG", "alias": "Como queráis llamarlo"}
```

- `riot_id` es el Riot ID exacto, con mayúsculas, espacios, acentos y el tag después de `#`.
- Para desactivar a alguien sin borrarlo, añade `"enabled": false`.
- Ya vienen los cuatro de siempre activados y otros seis de vuestras tablas desactivados.

## Ajustes (`config.json`)

| Campo | Para qué |
|---|---|
| `site_title`, `site_tagline` | Nombre y lema del periódico |
| `region`, `platform` | `europe` / `euw1` para EUW |
| `timezone` | Zona horaria para la fecha de cada edición |
| `window_hours` | Horas que cubre la primera edición |
| `max_backfill_hours` | Máximo que mira hacia atrás si el robot se salta días |
| `ignored_queues` | Colas que no cuentan (Arena, personalizadas...) |
| `items_per_player` | Cuántas noticias como máximo por jugador y día |
| `llm_model` | Modelo de Claude si usas la reescritura opcional |

## Cómo se decide quién es el peor del día

Cada partida suma «puntos de vergüenza»: muertes, poca cuota de daño (salvo soportes), ser el que menos daño hizo del equipo, perder, 10 o más muertes y poca participación en kills. Restan las kills, las asistencias y ganar con buen KDA. El peor del día es quien tiene la media más alta, y se suma medio punto por derrota.

En la **general de la vergüenza**, el peor de cada día suma 5 puntos, el segundo 3, el tercero 2 y el cuarto 1.

Las cifras de las noticias salen de los datos de las partidas: si un titular dice «el 12 % del daño de su equipo», es lo que pasó. Las remakes (menos de 5 minutos) no cuentan.

## Claude (opcional)

Si añades `ANTHROPIC_API_KEY`, cada día se manda a Claude la lista de noticias para que reescriba los titulares con más gracia, sin tocar las cifras, y solo metiéndose con cómo jugáis. Si falla por lo que sea, se publican los titulares de plantilla.

- Usa `claude-opus-5-5` con la opción de respaldo automático de Anthropic (`fallbacks: "default"`) por si el modelo rechaza la petición. Puedes cambiar el modelo en `config.json`.
- Es una sola petición al día: unos céntimos al mes. Sin la clave, todo sigue siendo gratis.

## Edición IA con una rutina de Claude (en tu ordenador)

Además de la edición de plantilla del robot de GitHub, una rutina programada en la app de Claude
reescribe cada día la edición. Puede añadir artículos nuevos, una columna de opinión, ediciones
especiales y las noticias que tú le pidas.

Cómo funciona:

1. El robot de GitHub saca los datos y la edición de plantilla (06:15 UTC).
2. La rutina de Claude se ejecuta en tu ordenador dos veces al día:
   1. Descarga el repositorio y ejecuta `python -m roast ai-context`.
   2. Lee `ai/GUIA.md` y escribe `ai/edicion-AAAA-MM-DD.json`.
   3. Lo aplica con `python -m roast apply-ai` y sube el resultado a GitHub.
3. La segunda pasada del día no hace nada si la edición ya está hecha. Solo actúa si la primera
   falló, si hay eventos nuevos en `eventos.md` o si el robot volvió a generar la edición.

**Para pedir una noticia o una edición especial**, apúntala en [`eventos.md`](eventos.md), en
«Pendientes». Se puede hacer desde la web de GitHub, con el lápiz. Sale en la siguiente pasada.

Si la rutina no se ejecuta, la web conserva la edición de plantilla, así que nunca se queda vacía.
La rutina gasta del uso de tu plan de Claude, no de una clave de API.

## Comentarios y «Proponer noticia» (Supabase, gratis)

La web tiene dos cosas que necesitan guardar lo que escribe la gente:
- **Cartas al director**: comentarios al final de cada edición.
- **Proponer noticia**: un buzón donde cualquiera manda texto y foto o meme. La rutina IA lo revisa y
  lo publica al día siguiente en la sección **La Voz de Runeterra**.

GitHub Pages solo sirve páginas, así que esos datos van a [Supabase](https://supabase.com), que es
gratis. Tus amigos no necesitan cuenta para comentar ni para proponer. Hasta que lo configures, la
web muestra los formularios desactivados.

1. Crea una cuenta en supabase.com y un proyecto nuevo (*New project*; región Europa).
2. *SQL Editor → New query*, pega todo el archivo [`supabase/setup.sql`](supabase/setup.sql) y pulsa *Run*.
3. *Project Settings → API*: copia la **Project URL** y la clave **anon public**.
4. Ponlas en `config.json`, en `supabase_url` y `supabase_anon_key`, y súbelo a GitHub. La clave
   *anon* está pensada para ir en webs públicas; la *service_role* no la pongas nunca.
5. La siguiente edición ya sale con los formularios activos.

Para moderar, borra lo que no quieras desde Supabase, en *Table Editor → comentarios* o *propuestas*.
Las propuestas no se publican solas: la rutina descarta las que no son publicables. Aun así, la clave
es pública, así que cualquiera con la web podría escribir. Si alguien abusa, se puede cerrar con un
cambio de política.

## Comandos

| Comando | Qué hace |
|---|---|
| `python -m roast run` | Edición de hoy: descarga, escribe, genera `docs/` y avisa a Discord |
| `python -m roast run --no-llm --no-notify` | Lo mismo, sin Claude ni Discord |
| `python -m roast build` | Regenera la web con las ediciones guardadas |
| `python -m roast check` | Comprueba la clave de Riot y que encuentra a todos |
| `python -m roast demo` | Demo con datos inventados en `demo_site/` |
| `python -m roast ai-status` | Indica si la edición de hoy ya tiene versión IA |
| `python -m roast ai-context` | Prepara `ai/contexto-FECHA.json` para la rutina |
| `python -m roast apply-ai ai/edicion-FECHA.json` | Aplica lo que escribió Claude y regenera la web |

## Límites y cosas a saber

- **Clave de desarrollo**: caduca cada 24 h. Si el robot falla con «HTTP 401/403», renueva la clave o consigue la Personal.
- **Límite de la API**: 100 peticiones cada 2 minutos. El cliente espera solo cuando hace falta; con 10 amigos sobra.
- **Arena y personalizadas** no cuentan (no hay equipos de 5 con los que comparar).
- La **primera edición** solo mira las últimas 24 h. No reconstruye el histórico de antes.
- **Normas de Riot**: la web lleva el aviso legal obligatorio. Una Personal Key es para uso propio o de un grupo pequeño; no la conviertas en un producto público.
- Es humor entre amigos: los textos se meten con cómo jugáis, no con quién sois. Si alguien del grupo no quiere salir, ponle `"enabled": false`.

## Estructura

```
friends.json            amigos (Riot ID + alias)
config.json             ajustes
roast/riot.py           cliente de la API de Riot con control de límites
roast/fetch.py          descarga y resumen de partidas
roast/analyze.py        estadísticas por jugador y día
roast/roasts.py         plantillas y detectores de noticias
roast/llm.py            reescritura opcional con Claude
roast/site.py           generador de la web
roast/notify.py         aviso a Discord
roast/demo.py           datos falsos para la demo y las pruebas
data/                   partidas y ediciones (lo rellena el robot)
docs/                   la web publicada (la genera el robot)
.github/workflows/      el robot diario
tests/                  pruebas
```
