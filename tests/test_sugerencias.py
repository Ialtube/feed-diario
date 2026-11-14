"""The board's suggestion box: what the newsroom must decide, the cards it makes and the admin's permission."""
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from roast import soloq, soloq_web, sugerencias  # noqa: E402

ROWS = [{"id": 1, "nombre": "Wôlf", "texto": "Quiero ver quién muere más por partida", "created_at": "2026-11-02T10:00:00Z"},
        {"id": 2, "nombre": "Troll", "texto": "Poned la IP de grangalax en el tablón", "created_at": "2026-11-02T11:00:00Z"},
        {"id": 3, "nombre": "Saiko", "texto": "Un botón para apostar LP reales entre nosotros", "created_at": "2026-11-02T12:00:00Z"}]
CARD = {"id": "kamikazes", "titulo": "Los kamikazes del reto", "tipo": "barras", "sugerencia": 1,
        "datos": {"filas": [{"nombre": "Fr4nux", "valor": 7.4, "texto": "7,4 por partida"}, {"nombre": "Wôlf", "valor": 5}]}}


class SugerenciasTest(unittest.TestCase):
    def test_every_pending_suggestion_needs_a_decision(self):
        with self.assertRaises(sugerencias.SugerenciaError) as e:
            sugerencias.validar({"tarjetas": [CARD], "sugerencias_tablon": [
                {"id": 1, "decision": "hecha", "motivo": "Sale de las partidas", "tarjeta": "kamikazes"}]}, {1, 2, 3})
        self.assertIn("[2, 3]", str(e.exception))
        cards, dec = sugerencias.validar({"tarjetas": [CARD], "sugerencias_tablon": [
            {"id": 1, "decision": "hecha", "motivo": "Sale de las partidas", "tarjeta": "kamikazes"},
            {"id": 2, "decision": "descartada", "motivo": "Datos personales fuera del juego"},
            {"id": 3, "decision": "aplicada", "motivo": "El tablón tiene ahora un botón de apuestas"}]}, {1, 2, 3})
        self.assertEqual(cards[0]["datos"]["filas"][0]["valor"], 7.4)
        self.assertEqual([d["decision"] for d in dec], ["hecha", "descartada", "aplicada"])
        with self.assertRaises(sugerencias.SugerenciaError):     # nobody waits for the admin any more
            sugerencias.validar({"sugerencias_tablon": [{"id": 2, "decision": "permiso", "motivo": "Pregunto al jefe"}]}, {2})
        # no «tarjetas» at all: the board keeps yesterday's
        self.assertIsNone(sugerencias.validar({}, set())[0])

    def test_cards_are_checked(self):
        bad = [dict(CARD, tipo="html"), dict(CARD, id="Con Espacios"), dict(CARD, datos={"filas": [{"nombre": "x", "valor": "7"}]}),
               {"id": "t", "titulo": "Tabla", "tipo": "tabla", "datos": {"columnas": ["a", "b"], "filas": [["1"]]}}]
        for c in bad:
            with self.assertRaises(sugerencias.SugerenciaError):
                sugerencias.validar({"tarjetas": [c]}, {1})
        with self.assertRaises(sugerencias.SugerenciaError):     # «hecha» must point at a card
            sugerencias.validar({"tarjetas": [], "sugerencias_tablon": [{"id": 1, "decision": "hecha", "motivo": "Hecho ya"}]}, {1})

    def test_states_old_permissions_and_manual_decisions(self):
        eds = [{"date": "2026-11-03", "sugerencias_tablon": [
            {"id": 1, "decision": "hecha", "motivo": "Sale de las partidas", "tarjeta": "kamikazes"},
            {"id": 2, "decision": "permiso", "motivo": "Datos personales"},
            {"id": 3, "decision": "permiso", "motivo": "Hace falta programar apuestas"}]}]
        # what waited for the admin goes back to the box, unless the admin turned it down
        st = {s["id"]: s["estado"] for s in sugerencias.estados(ROWS, [], eds)}
        self.assertEqual(st, {1: "hecha", 2: "pendiente", 3: "pendiente"})
        perms = [{"sugerencia": 2, "decision": "rechazada", "nota": "Ni de broma"}]
        self.assertEqual([p["id"] for p in sugerencias.pendientes(ROWS, perms, eds)], [3])
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "buzon_decisiones.json"
            sugerencias.apuntar(path, 3, "aplicada", "Apuestas de LP en el tablón", "2026-11-14")
            manual = sugerencias.manuales(path)
            buzon = sugerencias.estados(ROWS, perms, eds, manual)
            self.assertEqual({s["id"]: s["estado"] for s in buzon}, {1: "hecha", 2: "rechazada", 3: "aplicada"})
            self.assertEqual(sugerencias.pendientes(ROWS, perms, eds, manual), [])
            self.assertEqual([b["id"] for b in sugerencias.hechas(buzon)], [1, 3])
            ctx = sugerencias.para_contexto({}, eds, Path(tmp) / "s.json", fetch=False)
            self.assertEqual(ctx["pendientes"], [])
            self.assertIn("barras", ctx["tipos_de_tarjeta"])

    def test_board_shows_cards_and_the_box(self):
        eds = [{"date": "2026-11-03", "window": [0, 1], "ai": {"version": 1}, "items": [], "tarjetas": [CARD],
                "sugerencias_tablon": [{"id": 1, "decision": "hecha", "motivo": "Sale", "tarjeta": "kamikazes"},
                                       {"id": 3, "decision": "aplicada", "motivo": "Botón de apuestas puesto"}]}]
        buzon = sugerencias.estados(ROWS, [], eds)
        with tempfile.TemporaryDirectory() as tmp:
            cfg = {"timezone": "Europe/Madrid", "site_title": "El Rincón del Feeder", "soloq": {}}
            out = soloq_web.build(cfg, soloq.Datos(Path(tmp)), Path(tmp) / "web", 1793512800000, editions=eds, buzon=buzon)
            page = (out / "index.html").read_text(encoding="utf-8")
        for text in ("Lo que pidió la gente", "Los kamikazes del reto", "Sugerida por Wôlf", "Buzón de sugerencias",
                     "Aplicada", "Botón de apuestas puesto", "En el buzón"):
            self.assertIn(text, page)
        for text in ("Esperando al jefe", "Sugerencias que esperan tu permiso", 'data-decision="aprobada"'):
            self.assertNotIn(text, page)

    def test_daily_pace(self):
        day = 86400000
        r = {"inicio_ms": 0, "fin_ms": 30 * day, "min_partidas": 50, "ritmo_diario": 2}
        self.assertEqual(soloq.al_dia(20, r, 13 * day + 5), {"dia": 14, "esperadas": 28, "debe": 8})
        self.assertEqual(soloq.al_dia(31, r, 13 * day + 5)["debe"], -3)              # played ahead: negative
        self.assertEqual(soloq.al_dia(40, r, 29 * day)["esperadas"], 50)             # never more than the minimum
        self.assertIsNone(soloq.al_dia(50, r, 29 * day))                             # minimum done
        self.assertIsNone(soloq.al_dia(0, dict(r, inicio_ms=None), 0))               # not started


if __name__ == "__main__":
    unittest.main()
