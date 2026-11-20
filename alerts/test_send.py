"""python -m unittest alerts/test_send.py"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import send

LEVELS = [{"label": "Elevated", "chance": 0.08}, {"label": "High", "chance": 0.17}]


def fc(h, chance, region="29001"):
    return {"decision_hour": f"2026-11-19T{h:02d}:00Z", "window": [f"2026-11-19T{h + 2:02d}:00Z", "x"],
            "counties": [[region, chance, chance, chance, 0]]}


def run(chances, quiet=6):
    state, sent = {}, []
    for h, c in enumerate(chances):
        sends, state = send.decide(fc(h, c), LEVELS, state, quiet)
        sent += [(h, s["level"]) for s in sends]
    return sent


class Decide(unittest.TestCase):
    def test_once_per_storm(self):
        self.assertEqual(run([0.01, 0.1, 0.12, 0.09, 0.02]), [(1, 0)])

    def test_upgrade(self):
        self.assertEqual(run([0.1, 0.2, 0.1, 0.25]), [(0, 0), (1, 1)])

    def test_new_alert_after_quiet_hours(self):
        self.assertEqual(run([0.1] + [0.0] * 6 + [0.1]), [(0, 0), (7, 0)])

    def test_short_lull_is_the_same_storm(self):
        self.assertEqual(run([0.1] + [0.0] * 5 + [0.1]), [(0, 0)])

    def test_below_every_level(self):
        self.assertEqual(run([0.05] * 10), [])

    def test_slug(self):
        self.assertEqual(send.slug("29189+29510"), "29189-29510")


if __name__ == "__main__":
    unittest.main()
