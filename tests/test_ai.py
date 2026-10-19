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
            ctx = ai.build_context(store, "2026-10-19")
            self.assertEqual(ctx["estado_ia"], "pendiente")
            self.assertEqual(len(ctx["historial"]), 2)
            first = ctx["noticias"][0]
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
