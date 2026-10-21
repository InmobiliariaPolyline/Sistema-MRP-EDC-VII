"""Hora de Perú: todo lo que se muestra o se escribe en un documento va en hora de Lima (UTC−5)."""
import unittest
from datetime import datetime, timedelta

from utils import clock, timeago


class ClockTests(unittest.TestCase):
    def test_now_and_today_are_lima(self):
        self.assertEqual(clock.now().utcoffset(), timedelta(hours=-5))
        self.assertEqual(clock.today(), clock.now().date())

    def test_stored_timestamps_convert_from_utc(self):
        self.assertEqual(clock.local("2026-10-21T20:57:00+00:00"), "2026-10-21 15:57")
        self.assertEqual(clock.local("2026-10-21T20:57:00Z"), "2026-10-21 15:57")
        self.assertEqual(clock.local("2026-10-21 20:57:00"), "2026-10-21 15:57")      # SQLite guarda UTC sin zona
        self.assertEqual(clock.local("2026-10-22T03:30:00+00:00", with_time=False), "2026-10-21")   # pasada la medianoche UTC, en Lima aún es ayer
        self.assertEqual(clock.local("2026-10-21T20:57:00.123456+00:00"), "2026-10-21 15:57")

    def test_plain_dates_and_empty_values_are_left_alone(self):
        self.assertEqual(clock.local("2026-10-21"), "2026-10-21")
        for empty in (None, "", "None", "nan", "NaT"):
            self.assertEqual(clock.local(empty), "")
        self.assertEqual(clock.local("no es una fecha"), "no es una fecha"[:16])
        self.assertIsNone(clock.parse("basura"))

    def test_relative_time_uses_the_same_clock(self):
        hace_una_hora = (clock.now() - timedelta(hours=1, minutes=2)).astimezone(clock.UTC).strftime("%Y-%m-%d %H:%M:%S")   # naive = UTC
        self.assertEqual(timeago.time_ago(hace_una_hora), "hace 1 h")
        self.assertEqual(timeago.age_days((datetime.now(clock.UTC) - timedelta(days=3, hours=1)).isoformat()), 3)

    def test_no_module_reads_the_server_clock_directly(self):
        from pathlib import Path

        root = Path(__file__).resolve().parent.parent
        offenders = []
        for folder in ("modules", "utils", "core"):
            for path in (root / folder).glob("*.py"):
                if path.name == "clock.py":
                    continue
                text = path.read_text(encoding="utf-8")
                if "datetime.now()" in text or "date.today()" in text:
                    offenders.append(path.name)
        self.assertEqual(offenders, [], "usa utils.clock.now() / today() para la hora de Lima")


if __name__ == "__main__":
    unittest.main()
