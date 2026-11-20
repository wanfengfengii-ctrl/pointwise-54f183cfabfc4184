"""Station inputs for the area-budget handover and their V1 controls."""
import json
from pathlib import Path
from tempfile import TemporaryDirectory

from analysis.area import missed_area
from analysis.endpoints import encode_exact_positions
from analysis.head import HeadRequest
from analysis.intervals import ClosedInterval
from demo import make_piece
from evidence.accept import accept_piece
from reports.export import export_area_budget, export_report
from reports.history import read_area_budget, read_report
from reports.publish import publish_area_budget, publish_head
from reports.store import ReportStore


SLOPE = (((0, 0), (2, 0), (2, 2), (0, 1)),)
TENT = (
    ((0, -1), (1, -1), (1, 1), (0, 0)),
    ((1, -1), (2, -1), (2, 0), (1, 1)),
)
EXAMPLES = {
    "slope": (SLOPE, (), HeadRequest(0, 2, 1, 0, "3/2")),
    "overlap": (TENT, TENT, HeadRequest(0, 2, 1, 0, 1)),
}
V1_POSITIONS = {
    "slope": (ClosedInterval("3/2", "3/2"),),
    "overlap": (),
}
# Exact expected JSON positions, including independently readable surd endpoints.
EXPECTED_AREA_POSITIONS = {
    ("slope", "1/8"): [[{"offset": "3/2", "scale": "-1/2", "radicand": "2"}, "3/2"]],
    ("slope", "0"): [["3/2", "3/2"]],
    ("overlap", "3/8"): [[
        {"offset": "1", "scale": "-1/4", "radicand": "2"},
        {"offset": "1", "scale": "1/4", "radicand": "2"},
    ]],
    ("overlap", "1/4"): [["1", "1"]],
    ("overlap", "1/8"): [],
}
AREA_BUDGETS = {
    "slope": ("1/8",),
    "overlap": ("3/8", "1/4", "1/8"),
}


def expected_area_positions(name, budget):
    return EXPECTED_AREA_POSITIONS[(name, str(budget))]


def accept_example(center, name, *, station_a=":memory:", station_b=":memory:"):
    """Freeze and issue both inputs, close their station stores, and accept them."""
    first, second, request = EXAMPLES[name]
    a = make_piece(station_a, "A", first)
    b = make_piece(station_b, "B", second)
    parents = (
        accept_piece(center.catalog, a.to_json(), "A").piece_id,
        accept_piece(center.catalog, b.to_json(), "B").piece_id,
    )
    return parents, request


def _closed_store_demo():
    """Issue area budgets after both station libraries are closed, then reopen."""
    with TemporaryDirectory(prefix="area-budget-") as directory:
        root = Path(directory)
        station_a = root / "station-a.sqlite"
        station_b = root / "station-b.sqlite"
        center_path = root / "center.sqlite"
        with ReportStore(center_path) as center:
            parents, request = accept_example(
                center, "slope", station_a=station_a, station_b=station_b
            )
            head = publish_head(center, *parents, request)
            budgeted = publish_area_budget(center, *parents, request, "1/8")
            witness = missed_area(
                center.catalog.get_accepted_piece(parents[0]).coverage,
                center.catalog.get_accepted_piece(parents[1]).coverage,
                request,
                "4/5",
            )
            first_export = export_area_budget(budgeted)
        # An erratum for station B is issued through a fresh revision after reopen.
        revised_envelope = make_piece(station_b, "B", TENT, revision_id="r2")
        with ReportStore(center_path) as center:
            corrected = accept_piece(center.catalog, revised_envelope.to_json(), "B").piece_id
            overlap_request = EXAMPLES["overlap"][2]
            erratum_report = publish_area_budget(
                center, parents[0], corrected, overlap_request, "3/8"
            )
            # The original number still returns the original signed set.
            restored = read_area_budget(center, budgeted.report_id)
            restored_head = read_report(center, head.report_id)
            erratum_text = export_area_budget(erratum_report)
        return {
            "parents": parents,
            "witness_missed_area": str(witness),
            "original_export": json.loads(first_export),
            "restored_export": json.loads(export_area_budget(restored)),
            "head_export": json.loads(export_report(restored_head)),
            "erratum_export": json.loads(erratum_text),
        }


def main():
    with ReportStore(":memory:") as center:
        for name, expected in V1_POSITIONS.items():
            parents, request = accept_example(center, name)
            report = publish_head(center, *parents, request)
            if report.positions != expected or report.parent_ids != parents:
                raise AssertionError(f"{name}: wrong V1 positions or parents: {report!r}")
            recovered = read_report(center, report.report_id)
            if recovered != report:
                raise AssertionError(f"{name}: stored V1 report differs from issuance")
            print(name, export_report(recovered))
            for budget in AREA_BUDGETS[name]:
                area_report = publish_area_budget(center, *parents, request, budget)
                positions = encode_exact_positions(area_report.positions)
                if positions != expected_area_positions(name, budget):
                    raise AssertionError(
                        f"{name} budget {budget}: {positions} != "
                        f"{expected_area_positions(name, budget)}"
                    )
                if read_area_budget(center, area_report.report_id) != area_report:
                    raise AssertionError(f"{name}: stored area report differs from issuance")
                print(name, budget, export_area_budget(area_report))
    summary = _closed_store_demo()
    print("AREA_BUDGET_SCENARIO " + json.dumps(summary, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
