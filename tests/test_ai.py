"""Tests for the AI edition flow (context -> Claude's JSON -> apply)."""
import sys
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from roast import ai  # noqa: E402
from roast.demo import DemoRiot, generate_matches  # noqa: E402
from roast.fetch import fetch_new_matches, resolve_players  # noqa: E402
from roast.pipeline import make_edition  # noqa: E402
from roast.site import build_site  # noqa: E402
from roast.store import Store  # noqa: E402
from roast.util import load_config, save_json  # noqa: E402

from test_pipeline import FRIENDS  # noqa: E402

TZ = timezone(timedelta(hours=2))

# what every format-2 edition carries besides its stories
NEWSROOM = {
    "gaceta": {"titular": "¡EL RINCÓN MIENTE OTRA VEZ!",
               "cuerpo": "Fuentes de toda solvencia aseguran a esta Gaceta que el Rincón del Feeder ha vuelto a "
                         "retorcer las cifras para humillar a quien le conviene. Exigimos rectificación inmediata."},
    "jurado": {"pregunta": "¿Quién tuvo la culpa de la segunda Flex?", "opciones": ["El jungla", "El tirador", "Todos"]},
    "manana": [{"texto": "¿Romperá alguien la racha de derrotas en Flex?"}],
}


def demo_store(tmp, days=3):
    cfg = load_config()
    now = datetime(2026, 10, 19, 8, 0, tzinfo=TZ)
    raw = generate_matches(FRIENDS, days=days, seed=11, now=now)
    client = DemoRiot(FRIENDS, raw)
    store = Store(Path(tmp) / "data")
    players = resolve_players(client, store, FRIENDS, log=lambda *_: None)
    fetch_new_matches(client, store, players, int((now - timedelta(days=days + 1)).timestamp() * 1000), 100,
                      log=lambda *_: None)
    for i in range(days, 0, -1):
        end = now - timedelta(days=i - 1)
        ed = make_edition(cfg, store, players, int((end - timedelta(days=1)).timestamp() * 1000),
                          int(end.timestamp() * 1000), end.date().isoformat(), days - i + 1)
        store.save_edition(ed)
    return cfg, store


class AIFlowTest(unittest.TestCase):
    def test_context_apply_and_site(self):
        with tempfile.TemporaryDirectory() as tmp:
            cfg, store = demo_store(tmp)
            ctx = ai.build_context(store, "2026-10-19", cfg=cfg, friends=FRIENDS)
            self.assertEqual(ctx["estado_ia"], "pendiente")
            self.assertEqual(len(ctx["historial"]), 2)
            self.assertEqual(ctx["formato_edicion"], 2)
            first = store.edition("2026-10-19")["items"][0]
            data = {
                "items": [{"id": first["id"], "headline": "Titular nuevo escrito por la IA",
                           "body": "Cuerpo nuevo con mucha más gracia que la plantilla."}],
                "extra": [{"section": "entrevista", "headline": "Hablamos con un súbdito superviviente",
                           "body": "Dice que nunca había visto tanta paz en la línea.", "player": "fr4nux",
                           "portada": True}],
                "columna": {"titulo": "El daño invisible", "autor": "Doña Tilt",
                            "cuerpo": ["Primer párrafo de la columna de opinión de hoy."]},
                "especial": {"antetitulo": "Edición especial", "titulo": "Lunes negro en la Grieta",
                             "subtitulo": "Resumen semanal", "tema": "oro"},
                "frase": "Una frase nueva para el día de hoy.",
            }
            path = Path(tmp) / "edicion-2026-10-19.json"
            save_json(path, data)
            ed, clean, _ = ai.apply_file(store, path)
            self.assertEqual(ed["items"][0]["section"], "ENTREVISTA")  # extra with portada goes first
            self.assertEqual(ed["items"][0]["alias"], "Fr4nux")
            self.assertEqual(ed["ai"]["version"], 1)
            self.assertEqual(ai.ai_status(store.edition("2026-10-19")), "hecha")
            rewritten = [it for it in ed["items"] if it.get("template_headline")]
            self.assertEqual(len(rewritten), 1)

            # applying again is idempotent on the template text and bumps the version
            ed2, _, _ = ai.apply_file(store, path)
            self.assertEqual(ed2["ai"]["version"], 2)
            self.assertEqual(sum(1 for it in ed2["items"] if it["kind"] == "ia"), 1)
            self.assertEqual(len(ed2["items"]), len(ed["items"]))

            out = build_site(cfg, FRIENDS, store.editions(), Path(tmp) / "docs")
            html = (out / "index.html").read_text(encoding="utf-8")
            for text in ("Lunes negro en la Grieta", "El daño invisible", "súbdito superviviente",
                         "Una frase nueva"):
                self.assertIn(text, html)
            archive = (out / "archivo.html").read_text(encoding="utf-8")
            self.assertIn("Lunes negro en la Grieta", archive)

            # regenerating the day marks it stale but keeps the column
            regenerated = ai.mark_stale_on_regenerate(store.edition("2026-10-19"),
                                                      make_edition(cfg, store, [], 0, 1, "2026-10-19", 3))
            self.assertEqual(ai.ai_status(regenerated), "obsoleta")
            self.assertEqual(regenerated["columna"]["titulo"], "El daño invisible")

    def test_validation_errors(self):
        with tempfile.TemporaryDirectory() as tmp:
            _, store = demo_store(tmp, days=1)
            ed = store.edition("2026-10-19")
            known = {f["slug"] for f in FRIENDS}
            bad = [
                {"items": [{"id": 999, "headline": "Titular válido", "body": "Cuerpo válido aquí"}]},
                {"extra": [{"headline": "Corto", "body": "Cuerpo válido aquí"}]},
                {"extra": [{"headline": "Titular válido", "body": "Cuerpo válido aquí", "player": "nadie"}]},
                {"especial": {"titulo": "Especial", "tema": "fucsia"}},
                {},
            ]
            for data in bad:
                with self.assertRaises(ai.AIError):
                    ai.validate(data, ed, known)

    def test_reader_proposals_and_memes(self):
        from roast import propuestas as voz
        pending = {7: {"id": 7, "nombre": "Lector Anónimo", "titulo": "Wôlf rompe el teclado",
                       "texto": "Tras la quinta derrota seguida", "imagen_local": None}}
        marked = {}
        old_cache, old_mark = voz.pending_cache, voz.mark
        voz.pending_cache = lambda: pending
        voz.mark = lambda used, discarded: marked.update(used=list(used), discarded=list(discarded))
        try:
            with tempfile.TemporaryDirectory() as tmp:
                cfg, store = demo_store(tmp, days=1)
                data = {
                    "extra": [
                        {"section": "LA VOZ DE RUNETERRA", "propuesta": 7, "headline": "Un teclado menos en la Grieta",
                         "body": "Según nos cuenta un lector, la quinta derrota fue demasiado para las teclas."},
                        {"section": "ECONOMÍA", "headline": "La Lonja abre la sesión en rojo",
                         "body": "Los valores del grupo cotizan a la baja tras otra jornada de pérdidas.",
                         "campeon": "Gangplank", "meme_arriba": "CUANDO INVIERTES EN EL GRUPO",
                         "meme_abajo": "Y TODO CAE"},
                    ],
                    "propuestas_descartadas": [],
                }
                path = Path(tmp) / "edicion-2026-10-19.json"
                save_json(path, data)
                ed, clean, _ = ai.apply_file(store, path)
                self.assertEqual(marked["used"], [7])
                voz_item = next(it for it in ed["items"] if it["section"] == "LA VOZ DE RUNETERRA")
                self.assertEqual(voz_item["lector"], "Lector Anónimo")
                out = build_site(cfg, FRIENDS, store.editions(), Path(tmp) / "docs")
                html = (out / "index.html").read_text(encoding="utf-8")
                for text in ("La Voz de Runeterra", "Enviado por Lector Anónimo", "CUANDO INVIERTES EN EL GRUPO",
                             'id="comentarios"', "Cotizaciones del día"):
                    self.assertIn(text, html)
                self.assertTrue((out / "proponer.html").exists())
                self.assertTrue((out / "lectores.js").exists())
                with self.assertRaises(ai.AIError):
                    ai.validate({"extra": [{"section": "LA VOZ DE RUNETERRA", "propuesta": 99,
                                            "headline": "Titular válido", "body": "Cuerpo válido aquí"}]},
                                ed, {f["slug"] for f in FRIENDS})
        finally:
            voz.pending_cache, voz.mark = old_cache, old_mark

    def test_edition_format_2(self):
        from roast.dossier import build_dossier
        from roast import propuestas as voz
        old_cache = voz.pending_cache
        voz.pending_cache = lambda: {}
        try:
            with tempfile.TemporaryDirectory() as tmp:
                cfg, store = demo_store(tmp)
                ed = store.edition("2026-10-19")
                dossier = build_dossier(cfg, store, FRIENDS, ed, store.editions())
                angles = dossier["angulos"]
                self.assertTrue(angles)
                faro = next((a for a in angles if a["tipo"] == "faro"), None)
                required = [a for a in angles if a["tipo"] in ("sesion_flex", "colas")]
                others = [a for a in angles if a is not faro and a not in required]
                roll = ", ".join(r["alias"] for r in ed["ranking"])   # everybody who played gets a mention
                long_text = "Texto de prueba con suficiente longitud para una pieza. " * 14 + roll + "."
                mid_text = "Texto de prueba para una pieza mediana del periódico. " * 9
                short_text = "Breve de prueba con unas pocas frases. " * 4
                piezas = [
                    {"angulo": others[0]["id"], "peso": "grande", "portada": True, "formato": "crónica",
                     "headline": "Titular de portada", "body": long_text},
                    {"angulo": faro["id"] if faro else None, "peso": "mediana", "formato": "nota de prensa",
                     "seccion": "EL FARO DE LA ESPERANZA", "headline": "Titular del Faro", "body": mid_text},
                    {"angulo": None, "peso": "mediana", "formato": "parte policial", "seccion": "SUCESOS",
                     "headline": "Titular mediano", "body": mid_text + " " + roll + "."},
                    {"angulo": required[0]["id"] if required else None, "peso": "breve", "formato": "telegrama",
                     "headline": "Breve uno", "body": short_text},
                    {"angulo": required[1]["id"] if len(required) > 1 else None, "peso": "breve", "formato": "breve",
                     "headline": "Breve dos", "body": short_text},
                    {"angulo": None, "peso": "breve", "formato": "anuncio por palabras", "headline": "Breve tres",
                     "body": short_text},
                ]
                horos = [{"signo": s, "texto": "Los astros dicen algo bastante largo sobre tu rol hoy."}
                         for s in ai.SIGNOS]
                tiempo = [{"jugador": r["slug"], "texto": "Niebla persistente con chubascos de muertes al caer la tarde."}
                          for r in ed["ranking"]]
                data = {"piezas": piezas, "horoscopo": horos, "frase": "Una frase nueva para hoy.", "tiempo": tiempo,
                        "columna": {"titulo": "Columna de prueba", "cuerpo": ["Un párrafo de columna de prueba."]},
                        **NEWSROOM}
                known = {f["slug"] for f in FRIENDS}
                clean = ai.validate_v2(data, ed, known, dossier)
                ai.apply_v2(ed, clean)
                ai.prepare_games(ed, store.editions(), cfg)
                self.assertEqual(ed["gaceta"]["firma"], "Valeria Puñoférreo")
                self.assertEqual(len(ed["jurado"]["opciones"]), 3)
                self.assertEqual(ed["items"][0]["headline"], "Titular de portada")
                self.assertEqual(ed["ai"]["formato"], 2)
                self.assertIn(others[0]["clave"], ed["angulos_usados"])
                self.assertTrue(ed["items_plantilla"])
                store.save_edition(ed)
                out = build_site(cfg, FRIENDS, store.editions(), Path(tmp) / "docs")
                html = (out / "index.html").read_text(encoding="utf-8")
                for text in ("Titular de portada", "Breves", "Horóscopo de Runeterra", "Sorteo de la Grieta",
                             'id="boleto"', "Actualidad", "La jornada en 30 segundos", "La Gaceta de Noxus",
                             "El jurado popular", "Mañana en El Rincón", 'id="quienfue"', "La Lonja de Coronas",
                             'id="tu-edicion"', 'id="ed-datos"'):
                    self.assertIn(text, html)
                # the next day, that angle counts as recently used
                nxt = build_dossier(cfg, store, FRIENDS, {**ed, "date": "2026-10-20"}, store.editions())
                same = [a for a in nxt["angulos"] if a["clave"] == others[0]["clave"]]
                if same and same[0]["tipo"] not in ("faro", "ausentes"):
                    self.assertTrue(same[0]["novedad"].startswith("usado"))
                bad = [
                    dict(data, piezas=[dict(p, portada=False) for p in piezas]),          # no front page
                    dict(data, piezas=[dict(p, formato="noticia") for p in piezas]),      # one format only
                    dict(data, piezas=piezas[:3]),                                       # too few briefs
                    dict(data, horoscopo=horos[:4]),                                     # a sign missing
                    dict(data, piezas=[dict(piezas[0], body="Demasiado corto")] + piezas[1:]),
                    dict(data, piezas=[dict(p, body=p["body"].replace(roll, "")) for p in piezas]),  # someone spared
                    dict(data, gaceta=None),                                             # no rival paper
                    dict(data, jurado={"pregunta": "¿Una sola respuesta?", "opciones": ["Sí"]}),
                    dict(data, manana=[]),                                               # nothing to watch
                ]
                for b in bad:
                    with self.assertRaises(ai.AIError):
                        ai.validate_v2(b, ed, known, dossier)
                # a special edition opens with a meme or a picture from the group's library
                especial = {"titulo": "Edición especial de prueba", "tema": "oro"}
                with self.assertRaises(ai.AIError):
                    ai.validate_v2(dict(data, especial=especial), ed, known, dossier)
                meme = {"plantilla": "drake", "lineas": ["Ganar la Flex", "Pickear Zed de tirador"]}
                ok = ai.validate_v2(dict(data, especial=especial, piezas=[dict(piezas[0], meme=meme)] + piezas[1:]),
                                    ed, known, dossier)
                self.assertEqual(ok["piezas"][0]["meme"], meme)
                for bad_meme in ({"plantilla": "no-existe", "lineas": ["a"]}, {"plantilla": "cmm", "lineas": ["a", "b"]},
                                 {"lineas": ["sin plantilla ni campeón"]}, {"campeon": "Zed", "lineas": ["a", "b", "c"]}):
                    with self.assertRaises(ai.AIError):
                        ai.validate_v2(dict(data, piezas=[dict(piezas[0], meme=bad_meme)] + piezas[1:]), ed, known, dossier)
                # the whole session is printed by the page: Flex and SoloQ need no story of their own
                ai.validate_v2(dict(data, piezas=piezas[:3] + [dict(p, angulo=None) for p in piezas[3:]]), ed, known, dossier)
                # yesterday's promises and jury: tomorrow's paper must answer them
                extra = {"promesas_ayer": [{"n": 1, "texto": "¿Romperá alguien la racha?"}],
                         "jurado_ayer": {"pregunta": "¿Culpa?", "opciones": [], "total": 3}}
                with self.assertRaises(ai.AIError):
                    ai.validate_v2(data, ed, known, dossier, None, extra)
                ok = ai.validate_v2(dict(data, promesas=[{"n": 1, "texto": "Nadie la rompió: tres derrotas más."}],
                                         jurado_veredicto="El pueblo ha hablado: la culpa fue del jungla, por goleada."),
                                    ed, known, dossier, None, extra)
                self.assertEqual(ok["promesas"][0]["pregunta"], "¿Romperá alguien la racha?")
        finally:
            voz.pending_cache = old_cache

    def test_edition_window_cutoff(self):
        from roast.__main__ import edition_window
        cfg = {"cutoff_hour": 7}
        tz = timezone(timedelta(hours=2))
        # an evening run does not grab tonight's games: they belong to tomorrow's paper
        for now, date in [(datetime(2026, 10, 20, 8, 15, tzinfo=tz), "2026-10-20"),
                          (datetime(2026, 10, 19, 23, 41, tzinfo=tz), "2026-10-19"),
                          (datetime(2026, 10, 20, 2, 0, tzinfo=tz), "2026-10-19")]:
            d, start, end = edition_window(cfg, now)
            self.assertEqual(d, date)
            self.assertEqual(datetime.fromtimestamp(end / 1000, tz).hour, 7)
            self.assertEqual(end - start, 24 * 3600 * 1000)

    def test_canon_threads(self):
        from roast import canon
        with tempfile.TemporaryDirectory() as tmp:
            cfg, store = demo_store(tmp)
            ed = store.edition("2026-10-19")
            from roast.dossier import build_dossier
            dossier = build_dossier(cfg, store, FRIENDS, ed, store.editions())
            known = {f["slug"] for f in FRIENDS}
            path = Path(tmp) / "canon.json"
            seed = canon.empty()
            for hid in ("moneda", "dano"):
                seed["hilos"].append({"id": hid, "titulo": f"Hilo {hid}", "abierto": "2026-10-10", "semilla": True,
                                      "estados": [{"fecha": "2026-10-10", "estado": "abierto"}], "capitulos": []})
            canon.save(seed, path)
            roll = ", ".join(r["alias"] for r in ed["ranking"])
            angles = dossier["angulos"]
            faro = next((a for a in angles if a["tipo"] == "faro"), None)
            required = [a for a in angles if a["tipo"] in ("sesion_flex", "colas")]
            first = next(a for a in angles if a is not faro and a not in required)
            body = "Una historia larga contada con calma y sin tantas cifras por medio. " * 12 + roll + "."
            mid = "Una pieza mediana que avanza la trama del día con mala leche. " * 7 + roll + "."
            brief = "Breve con su veneno correspondiente para el lector. " * 3
            piezas = [
                {"angulo": first["id"], "peso": "grande", "portada": True, "formato": "crónica", "hilo": "moneda",
                 "headline": "Portada con saga", "body": body},
                {"angulo": faro["id"] if faro else None, "peso": "mediana", "formato": "nota de prensa",
                 "seccion": "EL FARO DE LA ESPERANZA", "hilo": "dano", "headline": "Luz en el Faro", "body": mid},
                {"angulo": None, "peso": "mediana", "formato": "reportaje", "hilo": "nuevo-hilo",
                 "headline": "Se abre una trama", "body": mid},
                {"angulo": required[0]["id"] if required else None, "peso": "breve", "formato": "telegrama",
                 "headline": "Breve uno", "body": brief},
                {"angulo": required[1]["id"] if len(required) > 1 else None, "peso": "breve", "formato": "breve",
                 "headline": "Breve dos", "body": brief},
                {"angulo": None, "peso": "breve", "formato": "anuncio por palabras", "headline": "Breve tres", "body": brief,
                 "hilo": "el-escandalo-de-la-lonja"},
            ]
            data = {"piezas": piezas, "frase": "Frase del día de prueba.", **NEWSROOM,
                    "columna": {"titulo": "Columna", "cuerpo": ["Un párrafo de columna de prueba."]},
                    "horoscopo": [{"signo": s, "texto": "Los astros dicen algo bastante largo sobre tu rol hoy."}
                                  for s in ai.SIGNOS],
                    "tiempo": [{"jugador": r["slug"], "texto": "Niebla Negra persistente sobre su carril."}
                               for r in ed["ranking"]],
                    "canon": {"hilos": [
                        {"id": "moneda", "accion": "avanzar", "estado": "escalando", "resumen": "La moneda vuelve a caer de cruz."},
                        {"id": "dano", "accion": "avanzar", "resumen": "El daño sigue sin aparecer."},
                        {"id": "nuevo-hilo", "accion": "abrir", "titulo": "Una trama nueva", "resumen": "Empieza algo raro."},
                        {"id": "el-escandalo-de-la-lonja", "accion": "avanzar", "resumen": "Barbanegra, suspendido de empleo."}],
                        "personajes": {"fr4nux": {"apodo": "El Desaparecido",
                                                  "arco": {"tipo": "redención", "texto": "Busca el daño que nunca tuvo"}}},
                        "elenco": [{"nombre": "Barbanegra el Contable", "estado": "Suspendido de empleo y sueldo"},
                                   {"nombre": "Sor Pólvora", "cargo": "Armera de Aguasturbias", "deseo": "Venderle balas a Fr4nux"}],
                        "sindicato": [{"campeon": "Diana", "jugador": "fr4nux", "motivo": "Estrenada y enterrada la misma noche"}],
                        "chistes": ["la moneda"]}}
            c = canon.load(path)
            clean = ai.validate_v2(data, ed, known, dossier, c)
            ai.apply_v2(ed, clean, path)
            clean = ai.validate_v2(data, ed, known, dossier, canon.load(path))   # the same day validates again
            ai.apply_v2(ed, clean, path)        # rewriting the same day does not pile up chapters
            c = canon.load(path)
            ids = [h["id"] for h in c["hilos"]]
            self.assertEqual(ids.count("nuevo-hilo"), 1)
            moneda = next(h for h in c["hilos"] if h["id"] == "moneda")
            self.assertEqual(len(moneda["capitulos"]), 1)
            self.assertEqual(canon.hilo_estado(moneda), "escalando")
            self.assertEqual(ed["items"][0]["saga"], {"id": "moneda", "titulo": "Hilo moneda", "capitulo": 1, "estado": "escalando"})
            self.assertEqual(canon.texts(c["personajes"]["fr4nux"]["apodos"]), ["El Desaparecido"])
            self.assertEqual(canon.current_arc(c["personajes"]["fr4nux"])["tipo"], "redención")
            barba = next(e for e in c["elenco"] if e["nombre"] == "Barbanegra el Contable")
            self.assertEqual(canon.cast_value(barba, "estado"), "Suspendido de empleo y sueldo")
            self.assertEqual(len(barba["cambios"]), 1)          # rewriting the day does not pile up changes
            self.assertEqual(sum(1 for e in c["elenco"] if e["nombre"] == "Sor Pólvora"), 1)
            self.assertEqual(len(c["sindicato"]), 1)
            self.assertTrue(any(h["id"] == "la-guerra-de-los-periodicos" for h in c["hilos"]))   # the newsroom's bible
            bad = [
                dict(data, piezas=[dict(p, hilo=None) for p in piezas]),                      # no threads
                dict(data, piezas=[dict(piezas[0], hilo=None)] + piezas[1:]),                  # front page without saga
                dict(data, canon={"hilos": []}),                                               # threads not recorded
                dict(data, tiempo=[]),                                                         # no weather
                dict(data, piezas=[dict(piezas[0], body="El 4/17/23 de las 21:55, con 38 minutos y 59 muertes, "
                                         "deja 7.060 de oro, 9,9 minutos y 0 objetivos. " * 10 + roll)] + piezas[1:]),
                dict(data, piezas=piezas[:5] + [dict(piezas[5], formato="parte meteorológico", seccion="DEPORTES")]),
                dict(data, piezas=piezas[:5] + [dict(piezas[5], hilo=None)]),                  # the newsroom stands still
                dict(data, canon=dict(data["canon"], elenco=[{"nombre": "Alguien nuevo sin cargo"}])),
                dict(data, canon=dict(data["canon"], hilos=data["canon"]["hilos"] + [
                    {"accion": "abrir", "titulo": "Trama con un desconocido", "resumen": "Alguien que no existe.",
                     "reparto": ["Nadie Conocido"]}])),
            ]
            for b in bad:
                with self.assertRaises(ai.AIError):
                    ai.validate_v2(b, ed, known, dossier, canon.load(path))
            # the admin's new corrections must be turned into style guidelines
            extra = {"correcciones_nuevas": [{"id": 1, "antes": "a", "despues": "b"}]}
            with self.assertRaises(ai.AIError):
                ai.validate_v2(data, ed, known, dossier, canon.load(path), extra)
            ok = ai.validate_v2(dict(data, estilo={"pautas_nuevas": ["Menos adjetivos y remates más secos al final"]}),
                                ed, known, dossier, canon.load(path), extra)
            self.assertEqual(ok["estilo"]["pautas_nuevas"], ["Menos adjetivos y remates más secos al final"])

    def test_lottery(self):
        from roast import sorteo
        ed = {"date": "2026-10-20", "number": 9, "window": [0, 10], "generated_at": 10,
              "ranking": [{"alias": "A", "d": 12}, {"alias": "B", "d": 9}, {"alias": "C", "d": 11}],
              "totals": {"games": 4, "dead_seconds": 600, "deaths": 32}}
        combo, origin = sorteo.combination(ed)
        self.assertEqual(sorted(combo), [9, 11, 12])
        res = sorteo.draw({}, ed, {"sorteo": {"bote": 200}}, tickets=[
            {"nombre": "Lector", "numeros": [12, 9, 11]}, {"nombre": "Otro", "numeros": [12, 9, 50]},
            {"nombre": "Nada", "numeros": [1, 2, 3]}])
        self.assertEqual([a["nombre"] for a in res["acertantes"]], ["Lector"])
        self.assertEqual([a["nombre"] for a in res["segundos"]], ["Otro"])
        self.assertEqual(res["bote"], 0)
        self.assertEqual(sorteo.draw({}, ed, {"sorteo": {"bote": 200}}, tickets=[])["bote"], 300)
        two = dict(ed, ranking=ed["ranking"][:1])
        self.assertEqual(len(sorteo.combination(two)[0]), 3)

    def test_timeline_summary(self):
        from roast.fetch import summarize_timeline
        ev = lambda t, k, v, x=1000, y=1000: {"type": "CHAMPION_KILL", "timestamp": t, "killerId": k, "victimId": v,
                                              "position": {"x": x, "y": y}}
        tl = {"info": {"participants": [{"participantId": 1, "puuid": "yo"}, {"participantId": 6, "puuid": "rival"}],
                       "frames": [{"events": [ev(120000, 6, 1), ev(300000, 6, 1, 1200, 1100), ev(400000, 0, 1, 900, 1000),
                                              ev(900000, 1, 6, 9000, 9000),
                                              {"type": "ELITE_MONSTER_KILL", "killerId": 1, "monsterType": "BARON_NASHOR"}]}]}}
        out = summarize_timeline(tl, {"yo"})
        self.assertEqual(out["fb"], {"killer": "rival", "victim": "yo", "min": 2.0})
        self.assertEqual(out["jug"]["yo"]["mismo_sitio"], 3)
        self.assertEqual(out["jug"]["yo"]["ejecutado"], 1)
        self.assertEqual(out["jug"]["yo"]["antes_del_10"], 3)
        self.assertEqual(out["jug"]["yo"]["objetivos"], ["BARON_NASHOR"])

    def test_lp_market(self):
        from roast.rangos import market, value, snapshot
        roster = [{"slug": "a", "alias": "A", "riot_id": "Main#EUW"}, {"slug": "a", "alias": "A", "riot_id": "Smurf#EUW"},
                  {"slug": "b", "alias": "B", "riot_id": "Bee#EUW"}]
        pos = {"20": {"Main#EUW": {"solo": {"tier": "GOLD", "rank": "I", "lp": 90, "wins": 10, "losses": 10}},
                      "Smurf#EUW": {"flex": {"tier": "DIAMOND", "rank": "IV", "lp": 0, "wins": 5, "losses": 5}}},
               "21": {"Main#EUW": {"solo": {"tier": "PLATINUM", "rank": "IV", "lp": 10, "wins": 11, "losses": 10},
                                   "flex": {"tier": "SILVER", "rank": "II", "lp": 5, "wins": 1, "losses": 0}},
                      "Smurf#EUW": {"flex": {"tier": "DIAMOND", "rank": "IV", "lp": 20, "wins": 6, "losses": 5}},
                      "Bee#EUW": {"solo": {"tier": "IRON", "rank": "IV", "lp": 0, "wins": 0, "losses": 1}}}}
        ranks = {"2026-10-19": {"a": {"solo": {"tier": "IRON", "rank": "IV", "lp": 0}}},     # old file, keyed by person
                 "2026-10-20": snapshot(roster[:2], lambda p: pos["20"][p["riot_id"]]),
                 "2026-10-21": snapshot(roster, lambda p: pos["21"][p["riot_id"]])}
        m = market(ranks, "2026-10-21", roster)
        main, smurf, bee = m["filas"]
        self.assertEqual((main["cuenta"], main["principal"]), ("Main#EUW", True))
        self.assertEqual((smurf["cuenta"], smurf["principal"]), ("Smurf#EUW", False))
        self.assertEqual(main["solo"]["cambio"], "ascenso")
        self.assertEqual(main["solo"]["delta"], value({"tier": "PLATINUM", "rank": "IV", "lp": 10}) - value({"tier": "GOLD", "rank": "I", "lp": 90}))
        self.assertIsNone(main["flex"]["delta"])                      # new in Flex: never compared with the smurf
        self.assertEqual(smurf["flex"]["delta"], 20)
        self.assertIsNone(bee["solo"]["delta"])                       # the old per-person day is ignored
        self.assertEqual(m["desde"], "2026-10-20")
        # a jump that the games played cannot explain is not believed
        pos["21"]["Main#EUW"]["solo"] = {"tier": "DIAMOND", "rank": "IV", "lp": 0, "wins": 11, "losses": 10}
        ranks["2026-10-21"] = snapshot(roster, lambda p: pos["21"][p["riot_id"]])
        row = market(ranks, "2026-10-21", roster)["filas"][0]
        self.assertIsNone(row["solo"]["delta"])
        self.assertTrue(row["solo"]["dudoso"])

    def test_pool_and_readers(self):
        from roast import porra, lectores
        ed = {"date": "2026-10-21", "window": [0, 10], "generated_at": 10,
              "ranking": [{"slug": "a", "alias": "A"}, {"slug": "b", "alias": "B"}],
              "items": [{"id": 1, "headline": "Uno"}, {"id": 2, "headline": "Dos"}]}
        res = porra.resolve({}, ed, None, bets=[{"nombre": "X", "lector": "1", "prediccion": "b"},
                                                {"nombre": "X", "lector": "1", "prediccion": "a"},   # last bet counts
                                                {"nombre": "Y", "lector": "2", "prediccion": "b"}])
        self.assertEqual(res["peor"], "A")
        self.assertEqual([a["nombre"] for a in res["acertantes"]], ["X"])
        self.assertEqual(porra.seers([{"porra": res}, {"porra": res}]), [("X", 2)])
        fb = lectores.feedback({}, ed, reactions=[{"pieza": 2, "emoji": "😂", "nombre": "X"}, {"pieza": 2, "emoji": "💀", "nombre": None}],
                               comments=[{"pieza": 1, "nombre": "Y", "texto": "Vaya"}])
        self.assertEqual(fb["mas_reaccionadas"][0]["titular"], "Dos")
        self.assertEqual(fb["mas_reaccionadas"][0]["total"], 2)
        self.assertEqual(fb["comentarios"][0]["titular"], "Uno")
        sn = lectores.snoops({}, 0, 10, [{"slug": "a", "alias": "A"}],
                             visits=[{"pagina": "jugador:a", "nombre": "B"}, {"pagina": "jugador:a", "nombre": "B"},
                                     {"pagina": "jugador:a", "nombre": "A"}, {"pagina": "jugador:a", "nombre": None}])
        self.assertEqual(sn[0], {"cotilla": "B", "ficha": "A", "veces": 2, "se_mira_a_si_mismo": False})
        self.assertTrue(sn[1]["se_mira_a_si_mismo"])

    def test_admin_corrections_and_style(self):
        from roast import correcciones
        with tempfile.TemporaryDirectory() as tmp:
            cfg, store = demo_store(tmp, days=1)
            ed = store.edition("2026-10-19")
            first = ed["items"][0]
            rows = [{"id": 1, "edicion": "2026-10-19", "pieza": first["id"], "campo": "headline",
                     "antes": first["headline"], "despues": "Titular corregido por el admin", "nota": "más seco"},
                    {"id": 2, "edicion": "2026-10-19", "pieza": 0, "campo": "frase", "antes": ed["frase"],
                     "despues": "Frase corregida", "nota": None}]
            st, sty = Path(tmp) / "corr.json", Path(tmp) / "estilo.json"
            new = correcciones.sync(cfg, store, rows=rows, state_path=st, style_path=sty)
            self.assertEqual(len(new), 2)
            ed = store.edition("2026-10-19")
            self.assertEqual(ed["items"][0]["headline"], "Titular corregido por el admin")
            self.assertEqual(ed["frase"], "Frase corregida")
            self.assertEqual(correcciones.sync(cfg, store, rows=rows, state_path=st, style_path=sty), [])  # only once
            ctx = correcciones.for_context(sty)
            self.assertEqual(len(ctx["correcciones_nuevas"]), 2)
            correcciones.apply_learning({"pautas_nuevas": ["Titulares secos, sin adjetivos de relleno"]}, "2026-10-20", sty)
            correcciones.apply_learning({"pautas_nuevas": ["Titulares secos, sin adjetivos de relleno"]}, "2026-10-20", sty)
            ctx = correcciones.for_context(sty)
            self.assertEqual([p["texto"] for p in ctx["pautas"]], ["Titulares secos, sin adjetivos de relleno"])
            self.assertEqual(ctx["correcciones_nuevas"], [])
            self.assertEqual(len(ctx["ejemplos_anteriores"]), 2)

    def test_same_story_from_several_readers(self):
        from roast import propuestas as voz
        from roast.dossier import build_dossier
        pending = {
            11: {"id": 11, "nombre": "Ana", "titulo": "Wôlf rompe el teclado tras perder con Gragas",
                 "texto": "Después de la tercera derrota con Gragas, Wôlf rompió el teclado de un puñetazo"},
            12: {"id": 12, "nombre": "Luis", "titulo": "Teclado roto: Wôlf y Gragas",
                 "texto": "Wôlf rompió el teclado tras otra derrota con Gragas, el tercer teclado del año"},
            13: {"id": 13, "nombre": "Eva", "titulo": "Saiko se compra ratón nuevo",
                 "texto": "Saiko estrena ratón inalámbrico para la temporada de la ACE League"},
        }
        self.assertGreaterEqual(voz.similarity(pending[11], pending[12]), voz.SIMILAR)
        self.assertLess(voz.similarity(pending[11], pending[13]), voz.SIMILAR)
        old = voz.known_cache
        voz.known_cache = lambda: pending
        try:
            with tempfile.TemporaryDirectory() as tmp:
                cfg, store = demo_store(tmp)
                ed = store.edition("2026-10-19")
                dossier = build_dossier(cfg, store, FRIENDS, ed, store.editions())
                known = {f["slug"] for f in FRIENDS}
                angles = dossier["angulos"]
                faro = next((a for a in angles if a["tipo"] == "faro"), None)
                required = [a for a in angles if a["tipo"] in ("sesion_flex", "colas")]
                first = next(a for a in angles if a is not faro and a not in required)
                roll = ", ".join(r["alias"] for r in ed["ranking"])
                long_text = "Una historia contada con calma y sin tantas cifras por medio. " * 12 + roll + "."
                mid = "Pieza mediana con su mala leche correspondiente. " * 8
                brief = "Breve con veneno para el lector. " * 4
                base = [
                    {"angulo": first["id"], "peso": "grande", "portada": True, "formato": "crónica",
                     "headline": "Portada del día", "body": long_text},
                    {"angulo": faro["id"] if faro else None, "peso": "mediana", "formato": "nota de prensa",
                     "seccion": "EL FARO DE LA ESPERANZA", "headline": "Luz en el Faro", "body": mid},
                    {"angulo": None, "peso": "mediana", "formato": "reportaje", "seccion": "SOCIEDAD",
                     "headline": "Otra pieza mediana", "body": mid + roll},
                    {"angulo": required[0]["id"] if required else None, "peso": "breve", "formato": "telegrama",
                     "headline": "Breve uno", "body": brief},
                    {"angulo": required[1]["id"] if len(required) > 1 else None, "peso": "breve", "formato": "breve",
                     "headline": "Breve dos", "body": brief},
                    {"angulo": None, "peso": "breve", "formato": "anuncio por palabras", "seccion": "SOCIEDAD",
                     "propuestas": [13], "headline": "Ratón nuevo en el Rincón", "body": brief},
                ]
                common = {"frase": "Frase del día de prueba.", "columna": {"titulo": "Columna", "cuerpo": ["Un párrafo de columna de prueba."]},
                          "horoscopo": [{"signo": x, "texto": "Los astros dicen algo bastante largo sobre tu rol hoy."} for x in ai.SIGNOS],
                          "tiempo": [{"jugador": r["slug"], "texto": "Niebla persistente sobre su carril."} for r in ed["ranking"]],
                          **NEWSROOM}
                voz_text = "Varias fuentes nos hacen llegar que el teclado no sobrevivió a Gragas. " * 6
                merged = base + [{"angulo": None, "peso": "mediana", "formato": "noticia", "propuestas": [11, 12],
                                  "headline": "El teclado que no sobrevivió", "body": voz_text}]
                clean = ai.validate_v2(dict(common, piezas=merged), ed, known, dossier)
                voz_piece = next(p for p in clean["piezas"] if p["voz"])
                self.assertEqual(voz_piece["lector"], "Según varias fuentes: Ana y Luis")
                inside = next(p for p in clean["piezas"] if p["headline"] == "Ratón nuevo en el Rincón")
                self.assertEqual((inside["section"], inside["lector"]), ("SOCIEDAD", "Con información de Eva"))
                split = base + [
                    {"angulo": None, "peso": "mediana", "formato": "noticia", "propuesta": 11,
                     "headline": "El teclado de Wôlf", "body": voz_text},
                    {"angulo": None, "peso": "mediana", "formato": "noticia", "propuesta": 12,
                     "headline": "Otra vez el teclado", "body": voz_text}]
                with self.assertRaises(ai.AIError):        # the same story told twice
                    ai.validate_v2(dict(common, piezas=split), ed, known, dossier)
                twice = base + [
                    {"angulo": None, "peso": "mediana", "formato": "noticia", "propuestas": [11, 12],
                     "headline": "El teclado de Wôlf", "body": voz_text},
                    {"angulo": None, "peso": "breve", "formato": "breve", "propuesta": 11, "seccion": "SOCIEDAD",
                     "headline": "Y el teclado otra vez", "body": brief}]
                with self.assertRaises(ai.AIError):        # one proposal in two pieces
                    ai.validate_v2(dict(common, piezas=twice), ed, known, dossier)
        finally:
            voz.known_cache = old

    def test_lonja_de_coronas(self):
        from roast import coronas
        with tempfile.TemporaryDirectory() as tmp:
            cfg, store = demo_store(tmp)
            eds = sorted(store.editions(), key=lambda e: e["date"])
            day, nxt = eds[-2], eds[-1]
            day["mercados"] = coronas.create(day, eds, cfg)
            ids = {m["tipo"]: m for m in day["mercados"]["lista"]}
            self.assertIn("flex", ids)
            for m in day["mercados"]["lista"]:
                self.assertTrue(all(1.1 <= o["cuota"] <= 20 for o in m["opciones"]))
            flex = ids["flex"]
            win = coronas.resolve(flex, nxt)[0]
            lose = next(o["id"] for o in flex["opciones"] if o["id"] != win)
            cuota = next(o["cuota"] for o in flex["opciones"] if o["id"] == win)
            before = coronas._iso(datetime(2026, 10, 18, 10, 0, tzinfo=TZ))
            after = coronas._iso(datetime(2026, 10, 18, 23, 0, tzinfo=TZ))
            bets = [
                {"nombre": "Ana", "mercado": flex["id"], "opcion": win, "importe": 40, "created_at": before},
                {"nombre": "ana ", "mercado": flex["id"], "opcion": lose, "importe": 50, "created_at": before},
                {"nombre": "Ana", "mercado": flex["id"], "opcion": win, "importe": 999, "created_at": before},   # no money
                {"nombre": "Luis", "mercado": flex["id"], "opcion": win, "importe": 10, "created_at": after},    # too late
                {"nombre": "Eva", "mercado": flex["id"], "opcion": "nada", "importe": 10, "created_at": before}, # no such answer
            ]
            led = coronas.ledger(eds, bets)
            acc = {a["nombre"].lower(): a for a in led["cuentas"]}
            self.assertEqual(acc["ana"]["saldo"], 100 - 40 - 50 + int(40 * cuota))
            self.assertNotIn("luis", acc)
            self.assertNotIn("eva", acc)
            self.assertEqual(led["resultados"][flex["id"]]["apuestas"][0]["premio"], int(40 * cuota))
            # a broke reader is rescued once per market day
            broke = coronas.ledger(eds, [{"nombre": "Pepe", "mercado": flex["id"], "opcion": lose, "importe": 100, "created_at": before},
                                         {"nombre": "Pepe", "mercado": flex["id"], "opcion": lose, "importe": 10, "created_at": before}])
            self.assertEqual(broke["cuentas"][0]["rescates"], 1)

    def test_jury_and_puzzle(self):
        from roast import juegos
        with tempfile.TemporaryDirectory() as tmp:
            _, store = demo_store(tmp)
            ed = store.edition("2026-10-19")
            ed["jurado"] = {"pregunta": "¿Culpable?", "opciones": ["Sí", "No"]}
            res = juegos.jury_result({}, ed, votes=[{"opcion": 0, "nombre": "Ana", "lector": "x" * 8},
                                                    {"opcion": 0, "nombre": "Ana", "lector": "x" * 8},   # one vote each
                                                    {"opcion": 1, "nombre": None, "lector": "y" * 8}])
            self.assertEqual([o["votos"] for o in res["opciones"]], [1, 1])
            self.assertEqual(res["total"], 2)
            q = juegos.puzzle(ed)
            self.assertEqual(len(q["pistas"]), 4)
            for role in ("soporte", "tirador", "jungla", "mid", "top"):     # the role would give it away
                self.assertNotIn(role, " ".join(q["pistas"][:3]).lower())
            self.assertIn(q["alias"], [o["alias"] for o in q["opciones"]])
            import base64
            self.assertIn(base64.b64decode(q["clave"]).decode()[::-1], [o["slug"] for o in q["opciones"]])
            self.assertEqual(q, juegos.puzzle(ed))            # the same game all day
            ed["quien_fue"] = q
            r = juegos.puzzle_result({}, ed, rows=[{"nombre": "Ana", "lector": "a", "intentos": 2, "acierto": True},
                                                   {"nombre": "Luis", "lector": "b", "intentos": 4, "acierto": False}])
            self.assertEqual((r["jugaron"], len(r["acertaron"]), r["fallaron"]), (2, 1, 1))

    def test_memes(self):
        from roast import memes
        drake = memes.validate({"plantilla": "drake", "lineas": ["¿Daño? 100%", "a/b_c-d"]}, "t")
        self.assertEqual(memes.url(drake),
                         "https://api.memegen.link/images/drake/%C2%BFDa%C3%B1o~q_100~p/a~sb__c--d.jpg")
        gru = memes.validate({"plantilla": "gru", "lineas": ["uno"]}, "t")
        self.assertEqual(gru["lineas"], ["uno", "", "", ""])          # missing lines go blank
        champ = memes.validate({"campeon": "Kai'Sa", "aspecto": 1, "lineas": ["¿Daño?"]}, "t")
        self.assertIn("background=https%3A%2F%2Fddragon.leagueoflegends.com%2Fcdn%2Fimg%2Fchampion%2Fsplash%2FKaisa_1.jpg",
                      memes.url(champ))
        for ok in ("voz-2.png", "biblioteca/escudo.png", "memes/2026-10-22-1.jpg"):
            self.assertTrue(memes.IMAGE_RE.fullmatch(ok))
        for bad in ("../config.json", "biblioteca/../../x.png", "otra/x.png", ".oculta.png"):
            self.assertFalse(memes.IMAGE_RE.fullmatch(bad))
        # if memegen cannot draw it, the story keeps the text over the champion instead
        clean = {"piezas": [{"headline": "Titular", "campeon": None, "imagen": None, "meme_arriba": "", "meme_abajo": "",
                             "meme": {"campeon": "Zed", "aspecto": 0, "lineas": ["Arriba", "Abajo"]}}]}
        old = memes.make
        memes.make = lambda m, name: (_ for _ in ()).throw(memes.MemeError("sin red"))
        try:
            ai.draw_memes(clean, "2026-10-22", log=lambda *_: None)
        finally:
            memes.make = old
        p = clean["piezas"][0]
        self.assertEqual((p["meme_arriba"], p["meme_abajo"], p["campeon"], p["meme"]), ("Arriba", "Abajo", "Zed", None))

    def test_calendar_and_agenda(self):
        self.assertEqual(ai.edition_kind("2026-10-25"), ["dominical"])
        self.assertEqual(ai.edition_kind("2026-10-26"), ["lunes"])
        self.assertEqual(ai.edition_kind("2026-10-31"), ["fin de mes"])
        self.assertEqual(ai.edition_kind("2026-11-01"), ["dominical", "primero de mes"])
        self.assertEqual(ai.edition_kind("2026-10-21"), ["diaria"])
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "agenda.md"
            path.write_text("# Agenda\n\n## Esta semana\n- (ejemplo)\n- Semana de la ACE League\n\n## Descanso\n- grangalax\n",
                            encoding="utf-8")
            self.assertEqual(ai.read_agenda(path), {"Esta semana": ["Semana de la ACE League"], "Descanso": ["grangalax"]})

    def test_overused_phrases(self):
        eds = [{"items": [{"headline": "La Comisaría de Piltover abre expediente", "body": "otra vez"}]}] * 3
        self.assertIn("comisaría de piltover", ai.overused_phrases(eds))

    def test_events_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "eventos.md"
            path.write_text("# Eventos\n\n## Pendientes\n- Evento uno\n- Evento dos\n\n## Publicados\n",
                            encoding="utf-8")
            events = ai.read_events(path)
            self.assertEqual([e["texto"] for e in events], ["Evento uno", "Evento dos"])
            self.assertEqual(ai.mark_events_published([2], "2026-10-19", path), 1)
            self.assertEqual([e["texto"] for e in ai.read_events(path)], ["Evento uno"])
            self.assertIn("- 2026-10-19 · Evento dos", path.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
