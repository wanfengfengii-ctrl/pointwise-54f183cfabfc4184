"""Station inputs for the area-budget handover and their V1 controls."""
from analysis.head import HeadRequest
from analysis.intervals import ClosedInterval
from demo import make_piece
from evidence.accept import accept_piece
from reports.export import export_report
from reports.history import read_report
from reports.publish import publish_head
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
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
