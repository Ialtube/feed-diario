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
                        "columna": {"titulo": "Columna de prueba", "cuerpo": ["Un párrafo de columna de prueba."]}}
                known = {f["slug"] for f in FRIENDS}
                clean = ai.validate_v2(data, ed, known, dossier)
                ai.apply_v2(ed, clean)
                self.assertEqual(ed["items"][0]["headline"], "Titular de portada")
                self.assertEqual(ed["ai"]["formato"], 2)
                self.assertIn(others[0]["clave"], ed["angulos_usados"])
                self.assertTrue(ed["items_plantilla"])
                store.save_edition(ed)
                out = build_site(cfg, FRIENDS, store.editions(), Path(tmp) / "docs")
                html = (out / "index.html").read_text(encoding="utf-8")
                for text in ("Titular de portada", "Breves", "Horóscopo de Runeterra", "Sorteo de la Grieta",
                             'id="boleto"', "Actualidad"):
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
                    dict(data, piezas=piezas[:3] + [dict(p, angulo=None) for p in piezas[3:]]),  # Flex/SoloQ left out
                    dict(data, piezas=[dict(p, body=p["body"].replace(roll, "")) for p in piezas]),  # someone spared
                ]
                for b in bad:
                    with self.assertRaises(ai.AIError):
                        ai.validate_v2(b, ed, known, dossier)
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
                {"angulo": None, "peso": "breve", "formato": "anuncio por palabras", "headline": "Breve tres", "body": brief},
            ]
            data = {"piezas": piezas, "frase": "Frase del día de prueba.",
                    "columna": {"titulo": "Columna", "cuerpo": ["Un párrafo de columna de prueba."]},
                    "horoscopo": [{"signo": s, "texto": "Los astros dicen algo bastante largo sobre tu rol hoy."}
                                  for s in ai.SIGNOS],
                    "tiempo": [{"jugador": r["slug"], "texto": "Niebla Negra persistente sobre su carril."}
                               for r in ed["ranking"]],
                    "canon": {"hilos": [
                        {"id": "moneda", "accion": "avanzar", "estado": "escalando", "resumen": "La moneda vuelve a caer de cruz."},
                        {"id": "dano", "accion": "avanzar", "resumen": "El daño sigue sin aparecer."},
                        {"id": "nuevo-hilo", "accion": "abrir", "titulo": "Una trama nueva", "resumen": "Empieza algo raro."}],
                        "personajes": {"fr4nux": {"apodo": "El Desaparecido"}}, "chistes": ["la moneda"]}}
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
            bad = [
                dict(data, piezas=[dict(p, hilo=None) for p in piezas]),                      # no threads
                dict(data, piezas=[dict(piezas[0], hilo=None)] + piezas[1:]),                  # front page without saga
                dict(data, canon={"hilos": []}),                                               # threads not recorded
                dict(data, tiempo=[]),                                                         # no weather
                dict(data, piezas=[dict(piezas[0], body="El 4/17/23 de las 21:55, con 38 minutos y 59 muertes, "
                                         "deja 7.060 de oro, 9,9 minutos y 0 objetivos. " * 10 + roll)] + piezas[1:]),
                dict(data, piezas=piezas[:5] + [dict(piezas[5], formato="parte meteorológico", seccion="DEPORTES")]),
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
        from roast.rangos import market, value
        ranks = {"2026-10-20": {"a": {"solo": {"tier": "GOLD", "rank": "I", "lp": 90}}},
                 "2026-10-21": {"a": {"solo": {"tier": "PLATINUM", "rank": "IV", "lp": 10}, "flex": {"tier": "SILVER", "rank": "II", "lp": 5}}}}
        m = market(ranks, "2026-10-21", [{"slug": "a", "alias": "A"}])
        row = m["filas"][0]
        self.assertEqual(row["solo"]["cambio"], "ascenso")
        self.assertEqual(row["solo"]["delta"], value({"tier": "PLATINUM", "rank": "IV", "lp": 10}) - value({"tier": "GOLD", "rank": "I", "lp": 90}))
        self.assertIsNone(row["flex"]["delta"])
        self.assertEqual(m["desde"], "2026-10-20")

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
