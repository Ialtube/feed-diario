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
2. La rutina de Claude publica **una sola edición IA al día**. Se intenta a las 09:30 y, si a esa
   hora no se pudo (ordenador apagado, error…), a las 18:30:
   1. Descarga el repositorio y ejecuta `python -m roast ai-context`.
   2. Lee `ai/GUIA.md` y escribe `ai/edicion-AAAA-MM-DD.json`.
   3. Lo aplica con `python -m roast apply-ai` y sube el resultado a GitHub.
3. Si la edición IA de hoy ya está publicada (por la pasada de las 09:30 o porque lanzaste la
   rutina a mano), cualquier otra pasada del día no hace nada. Solo la rehace si el robot volvió
   a generar la edición de plantilla y se perdió la versión IA.

**Para pedir una noticia o una edición especial**, apúntala en [`eventos.md`](eventos.md), en
«Pendientes». Se puede hacer desde la web de GitHub, con el lápiz. Sale en la siguiente edición
que aún no esté publicada (si la de hoy ya salió, en la de mañana). Igual con las propuestas de
los lectores.

Si la rutina no se ejecuta, la web conserva la edición de plantilla, así que nunca se queda vacía.
La rutina gasta del uso de tu plan de Claude, no de una clave de API.

## SoloQ Challenge

El reto de a ver quién llega más lejos en Solo/Dúo con una cuenta comprada de cero. Vive en
**`https://TU_USUARIO.github.io/feed-diario/soloq/`** y el periódico, que no cambia en nada más, lo enlaza con el botón
«🪓 SoloQ Challenge» del menú. Tiene su propio estilo: un tablón de madera con la clasificación clavada en el centro, la gráfica de LP de cada jugador
en otro papel debajo y, alrededor, placas talladas, un cartel de «Se busca» para el último, recortes de las noticias
del Rincón sobre el reto y notas clavadas con mala leche (del robot, de la redacción IA y de los lectores).

**Cómo va:**

1. **Inscripciones.** Cada uno apunta a mano su cuenta del reto en el «Bando de inscripción» del tablón: Riot ID,
   quién es del Rincón (la cuenta queda asociada a su nombre), mote, hasta dónde promete llegar y grito de guerra.
   Se guarda en Supabase (tablas `soloq_inscritos`, `soloq_notas` y `soloq_control`: vuelve a ejecutar
   `supabase/setup.sql`). También
   puedes apuntar a alguien a mano en `config.json` → `soloq.a_mano`.
2. **La salida la das tú** desde el tablón: botón «🔒 El pistoletazo» (arriba a la derecha), fecha y hora de salida,
   de final si quieres (si no, dura `soloq.duracion_dias`) y la contraseña. La contraseña la comprueba Supabase
   (función `soloq_programar`; en `setup.sql` solo está su huella) y el robot recoge la fecha en su siguiente pasada.
   Se puede volver a poner para retrasar la salida o acabar antes. Desde la salida cuentan las partidas de Solo/Dúo.
   En local también vale `python -m roast soloq --empezar --dias 30` / `--terminar`.
3. **El robot** (workflow «SoloQ Challenge», cada 30 minutos, con la misma `RIOT_API_KEY`) lee las inscripciones,
   mira la liga y las partidas de cada cuenta y regenera el tablón. Solo guarda si algo ha cambiado. Cuando acabe el
   reto deja de consultar a Riot; puedes desactivarlo en *Actions → SoloQ Challenge → Disable workflow*.
4. **Discord**: con el mismo `DISCORD_WEBHOOK_URL`, el robot avisa cuando pones la fecha y cuando empieza, manda **cada día a partir de las
   09:00** el parte del reto (la tabla con las subidas y bajadas del día anterior, quién se hunde, quién no jugó y una
   nota del tablón) y, al final, el podio y el castigo. Durante las inscripciones solo avisa si se apuntó alguien.
5. **El periódico**: cada edición guarda la tabla del reto al cierre para la redacción IA, que recibe `soloq_challenge` y ángulos del reto, escribe al menos una pieza al día y puede clavar notas
   en el tablón (`tablon` en su JSON). Las noticias del Rincón sobre el reto salen clavadas como recortes en el tablón.
6. **Moderar**: borra la fila en Supabase (*Table Editor → soloq_inscritos* o *soloq_notas*) y desaparece.

Ajustes en `config.json` → `soloq`:

| Campo | Para qué |
|---|---|
| `nombre`, `lema` | Nombre del reto y subtítulo |
| `duracion_dias` | Lo que dura desde el pistoletazo (vacío: hasta que lo termines) |
| `inicio`, `fin` | Opcional: fechas fijas (AAAA-MM-DD) en vez del pistoletazo a mano |
| `aviso_hora` | Hora a partir de la que sale el parte diario en Discord |
| `min_partidas` | Partidas mínimas para optar al trono |
| `max_inscritos` | Tope de cuentas (cuida el límite de la API de Riot) |
| `premio`, `castigo` | Lo que se juegan |
| `a_mano` | Inscripciones a mano: `[{"riot_id": "Nombre#TAG", "apodo": "…", "jugador": "slug", "objetivo": "DIAMOND"}]` |

Para verlo con datos inventados: `python -m roast soloq --demo` y abre `demo_site/soloq/index.html`.

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
| `python -m roast avisar` | Avisa a Discord de la edición IA de hoy (una vez; lo hace solo el workflow «Aviso de la edición IA») |
| `python -m roast previa` | Manda a Discord la previa de la noche con los mercados de la Lonja (workflow «Previa de la noche», 18:00) |
| `python -m roast informe` | Escribe el informe semanal de la redacción en `informes/` |
| `python -m roast soloq` | SoloQ Challenge: inscripciones, ligas, partidas, aviso a Discord → `docs/soloq/` (el workflow, cada 30 min) |
| `python -m roast soloq --empezar` / `--terminar` | Salida / fin del reto desde la terminal (lo normal es el botón del tablón) |
| `python -m roast soloq --solo-web` | Regenera el tablón sin consultar a Riot |

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
roast/soloq.py          SoloQ Challenge: inscripciones, ligas, clasificación y humor
roast/soloq_web.py      el tablón del SoloQ Challenge (docs/soloq/)
roast/demo.py           datos falsos para la demo y las pruebas
data/                   partidas y ediciones (lo rellena el robot)
docs/                   la web publicada (la genera el robot)
.github/workflows/      el robot diario
tests/                  pruebas
```

## Memoria del periódico, lectores y ACE League

- **Canon** (`data/canon.json`): personajes, elenco ficticio, sagas (hilos que se abren, escalan y se
  cierran), costumbres y chistes. Lo actualiza la rutina cada día; se ve en la página **Sagas** y en
  la «Ficha de Runeterra» de cada jugador.
- **Lectores**: «¿Quién eres?» (cuenta y smurfs), reacciones y comentarios en cada noticia, derecho de
  réplica del aludido, porra de quién será el peor, sorteo, visitas y «el cotilla del día». Todo vive en
  Supabase: si añades funciones nuevas, vuelve a ejecutar `supabase/setup.sql`.
- **ACE League**: edita [`data/ace_league.json`](data/ace_league.json) (también desde GitHub, con el
  lápiz) y añade los partidos con fecha, rival, resultado y marcador. El periódico abre su sección y
  lo cuenta como una temporada.
- **Riot**: además de las partidas, el robot descarga cada mañana la línea temporal de cada partida
  (primera sangre, muertes en el mismo sitio, objetivos) y los rangos de SoloQ y Flex para la Bolsa de LP.

## Redacción con vida propia y juegos de los lectores

- **La redacción** tiene su propia biblia (`roast/biblia.py`): cada personaje del elenco quiere algo, esconde algo
  y se lleva bien o mal con otro, y hay tramas de la redacción que avanzan cada día. Cada edición lleva además la
  réplica de **La Gaceta de Noxus**, el periódico rival.
- **La agenda** ([`agenda.md`](agenda.md)) es tu consejo de redacción de la semana: qué sagas empujar, quién
  descansa, qué especiales tocan. La rutina de Claude la obedece.
- **El calendario**: los domingos, perfil o reportaje largo; el último día del mes, El Juicio del Mes con veredicto
  del jurado popular.
- **La jornada en 30 segundos** imprime todas las partidas del día en orden, así que la redacción ya no tiene que
  contarlas una a una.
- **Para los lectores**: «Tu edición» (lo que el periódico dice hoy de ti), el **jurado popular** (veredicto al día
  siguiente), «Mañana en El Rincón», **¿Quién fue?** (adivinar de quién es una partida) y la **Lonja de Coronas**
  (apuestas con la moneda del periódico; el robot calcula los saldos desde cero en cada edición, así que no se
  pueden trampear desde el navegador).
- **Discord**: avisa con la edición de la IA cuando la rutina la sube (no con la de imprenta) y a las 18:00 manda
  la previa de la noche con las cuotas.
- Los juegos necesitan las tablas `jurado`, `quienfue` y `apuestas`: vuelve a ejecutar `supabase/setup.sql`.
- **Memes**: la redacción usa plantillas clásicas y el arte de los campeones (con sus aspectos), dibujados con
  memegen.link y guardados en `docs/img/memes/`. Las portadas de las ediciones especiales siempre llevan uno.
- **Biblioteca del grupo** ([`docs/img/biblioteca`](docs/img/biblioteca)): deja ahí tus memes y fotos (desde GitHub,
  *Add file → Upload files*) y descríbelos en su `LEEME.md`; la redacción los usa cuando encajan.
