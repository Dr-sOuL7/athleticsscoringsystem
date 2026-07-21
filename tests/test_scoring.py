"""Unit tests for the athletics scoring system.

Run with::

    python -m pytest -q          # or:  python -m unittest -v
"""

from __future__ import annotations

import unittest
from pathlib import Path

from athletics_scoring.events import EventRegistry, Gender, normalise_gender
from athletics_scoring.models import AthletePerformance
from athletics_scoring.performance import (
    PerformanceParseError,
    parse_performance,
)
from athletics_scoring.scorer import (
    ScoringEngine,
    aggregate_by_athlete,
    rank_colleges,
)
from athletics_scoring.tables import EventTable, ScoringTables
from athletics_scoring.events import PerformanceType
from athletics_scoring.timing import TimingMethod, to_fat_equivalent

_TABLES = ScoringTables.load()


def _perf(**kwargs) -> AthletePerformance:
    """Build an AthletePerformance with sensible defaults for tests."""
    base = dict(
        name="Test",
        athlete_id="1",
        college="X",
        gender="Male",
        event_name="100m",
        performance_type="TIME",
        result="10.87",
        row_number=2,
    )
    base.update(kwargs)
    return AthletePerformance(**base)


class TestPerformanceParsing(unittest.TestCase):
    def test_plain_seconds(self):
        self.assertAlmostEqual(parse_performance("10.87"), 10.87)

    def test_minutes_seconds(self):
        self.assertAlmostEqual(parse_performance("2:05.31"), 125.31)

    def test_hours_minutes_seconds(self):
        self.assertAlmostEqual(parse_performance("1:02:05.3"), 3725.3)

    def test_distance(self):
        self.assertAlmostEqual(parse_performance("6.72"), 6.72)

    def test_numeric_points(self):
        self.assertAlmostEqual(parse_performance(7265), 7265.0)

    def test_empty_raises(self):
        with self.assertRaises(PerformanceParseError):
            parse_performance(" - ")


class TestEventTableLookup(unittest.TestCase):
    def test_time_lower_is_better(self):
        table = EventTable(
            code="X", performance_type=PerformanceType.TIME,
            perf=(10.0, 10.1, 10.2), pts=(1000, 990, 980),
        )
        self.assertEqual(table.score(10.0), 1000)   # exact
        self.assertEqual(table.score(10.05), 990)   # between -> lower
        self.assertEqual(table.score(9.5), 1000)    # faster than table top
        self.assertEqual(table.score(11.0), 0)      # slower than table -> 0

    def test_distance_higher_is_better(self):
        table = EventTable(
            code="Y", performance_type=PerformanceType.DISTANCE,
            perf=(6.0, 6.5, 7.0), pts=(900, 950, 1000),
        )
        self.assertEqual(table.score(7.0), 1000)    # exact
        self.assertEqual(table.score(6.7), 950)     # between -> lower
        self.assertEqual(table.score(8.0), 1000)    # beyond table top -> cap
        self.assertEqual(table.score(5.0), 0)       # below table -> 0


class TestGenderAndEventResolution(unittest.TestCase):
    def test_gender_aliases(self):
        self.assertEqual(normalise_gender("Male"), Gender.MEN)
        self.assertEqual(normalise_gender("women"), Gender.WOMEN)
        self.assertEqual(normalise_gender("F"), Gender.WOMEN)

    def test_friendly_event_names(self):
        reg = EventRegistry(_TABLES.valid_codes())
        self.assertEqual(reg.resolve("Long Jump"), "LJ")
        self.assertEqual(reg.resolve("shot put"), "SP")
        self.assertEqual(reg.resolve("Javelin Throw"), "JT")
        self.assertEqual(reg.resolve("100M"), "100m")

    def test_unknown_event_raises(self):
        reg = EventRegistry(_TABLES.valid_codes())
        with self.assertRaises(KeyError):
            reg.resolve("Tug of War")


class TestTimingConversion(unittest.TestCase):
    def test_fat_unchanged(self):
        self.assertEqual(to_fat_equivalent(10.5, TimingMethod.FAT, 100), 10.5)

    def test_hand_short_sprint(self):
        self.assertAlmostEqual(
            to_fat_equivalent(10.5, TimingMethod.HAND, 100), 10.74
        )

    def test_hand_medium(self):
        self.assertAlmostEqual(
            to_fat_equivalent(48.0, TimingMethod.HAND, 400), 48.14
        )


class TestScoringEngine(unittest.TestCase):
    def setUp(self):
        self.engine = ScoringEngine(_TABLES)

    def test_scores_valid_row(self):
        result = self.engine.score_one(_perf())
        self.assertEqual(result.score, 925)

    def test_sorted_descending_and_rejects(self):
        rows = [
            _perf(name="Fast", result="10.00"),
            _perf(name="Slow", result="12.00"),
            _perf(name="BadEvent", event_name="Quidditch"),
        ]
        report = self.engine.score_all(rows)
        self.assertEqual(len(report.scored), 2)
        self.assertEqual(len(report.rejected), 1)
        # Descending by score.
        self.assertGreaterEqual(
            report.scored[0].score, report.scored[1].score
        )
        self.assertEqual(report.scored[0].performance.name, "Fast")

    def test_women_event_selected_by_gender(self):
        row = _perf(gender="Female", event_name="100m", result="11.90")
        self.assertEqual(self.engine.score_one(row).score, 1011)


class TestAthleteAggregation(unittest.TestCase):
    def setUp(self):
        self.engine = ScoringEngine(_TABLES)

    def test_scores_are_summed_per_athlete(self):
        rows = [
            _perf(name="Multi", athlete_id="A1", event_name="100m", result="10.87"),
            _perf(name="Multi", athlete_id="A1", event_name="Long Jump",
                  performance_type="DISTANCE", result="7.10"),
        ]
        report = self.engine.score_all(rows)
        aggregates = aggregate_by_athlete(report)
        self.assertEqual(len(aggregates), 1)
        agg = aggregates[0]
        self.assertEqual(agg.event_count, 2)
        self.assertEqual(agg.total_score, sum(r.score for r in report.scored))

    def test_distinct_athletes_grouped_by_name_id_college(self):
        rows = [
            _perf(name="Same", athlete_id="1", college="A", result="10.87"),
            _perf(name="Same", athlete_id="1", college="A", result="11.00"),
            _perf(name="Same", athlete_id="2", college="A", result="10.90"),
        ]
        aggregates = aggregate_by_athlete(self.engine.score_all(rows))
        # Two distinct ids -> two athletes; grouping is case/space-insensitive.
        self.assertEqual(len(aggregates), 2)

    def test_sorted_by_total_descending(self):
        rows = [
            _perf(name="Solo", athlete_id="S", result="12.00"),
            _perf(name="Multi", athlete_id="M", result="12.00"),
            _perf(name="Multi", athlete_id="M", event_name="Long Jump",
                  performance_type="DISTANCE", result="7.00"),
        ]
        aggregates = aggregate_by_athlete(self.engine.score_all(rows))
        self.assertEqual(aggregates[0].name, "Multi")  # summed two events
        self.assertGreater(aggregates[0].total_score, aggregates[1].total_score)


class TestCollegeRanking(unittest.TestCase):
    def setUp(self):
        self.engine = ScoringEngine(_TABLES)

    def test_college_score_is_sum_of_athletes(self):
        rows = [
            _perf(name="A", athlete_id="1", college="Red", result="10.87"),
            _perf(name="B", athlete_id="2", college="Red", result="11.50"),
            _perf(name="C", athlete_id="3", college="Blue", result="10.50"),
        ]
        aggregates = aggregate_by_athlete(self.engine.score_all(rows))
        colleges = rank_colleges(aggregates)
        by_name = {c.college: c for c in colleges}
        red_total = sum(a.total_score for a in aggregates if a.college == "Red")
        self.assertEqual(by_name["Red"].total_score, red_total)
        self.assertEqual(by_name["Red"].athlete_count, 2)

    def test_colleges_sorted_descending(self):
        rows = [
            _perf(name="A", athlete_id="1", college="Strong", result="10.00"),
            _perf(name="B", athlete_id="2", college="Strong", result="10.20"),
            _perf(name="C", athlete_id="3", college="Weak", result="14.00"),
        ]
        colleges = rank_colleges(
            aggregate_by_athlete(self.engine.score_all(rows))
        )
        self.assertEqual(colleges[0].college, "Strong")
        self.assertGreater(colleges[0].total_score, colleges[1].total_score)


class TestBundledDataIntegrity(unittest.TestCase):
    def test_json_exists(self):
        self.assertTrue(Path("data/scoring_tables.json").exists())

    def test_event_counts(self):
        self.assertEqual(_TABLES.meta["event_count_men"], 82)
        self.assertEqual(_TABLES.meta["event_count_women"], 82)


if __name__ == "__main__":
    unittest.main()
