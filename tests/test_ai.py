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
                long_text = "Texto de prueba con suficiente longitud para una pieza. " * 16
                mid_text = "Texto de prueba para una pieza mediana del periódico. " * 9
                short_text = "Breve de prueba con unas pocas frases. " * 4
                piezas = [
                    {"angulo": others[0]["id"], "peso": "grande", "portada": True, "formato": "crónica",
                     "headline": "Titular de portada", "body": long_text},
                    {"angulo": faro["id"] if faro else None, "peso": "mediana", "formato": "nota de prensa",
                     "seccion": "EL FARO DE LA ESPERANZA", "headline": "Titular del Faro", "body": mid_text},
                    {"angulo": None, "peso": "mediana", "formato": "parte policial", "seccion": "SUCESOS",
                     "headline": "Titular mediano", "body": mid_text},
                    {"angulo": required[0]["id"] if required else None, "peso": "breve", "formato": "telegrama",
                     "headline": "Breve uno", "body": short_text},
                    {"angulo": required[1]["id"] if len(required) > 1 else None, "peso": "breve", "formato": "breve",
                     "headline": "Breve dos", "body": short_text},
                    {"angulo": None, "peso": "breve", "formato": "anuncio por palabras", "headline": "Breve tres",
                     "body": short_text},
                ]
                horos = [{"signo": s, "texto": "Los astros dicen algo bastante largo sobre tu rol hoy."}
                         for s in ai.SIGNOS]
                data = {"piezas": piezas, "horoscopo": horos, "frase": "Una frase nueva para hoy.",
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
