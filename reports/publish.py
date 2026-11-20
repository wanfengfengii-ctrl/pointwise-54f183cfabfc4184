from analysis.area import area_budget_positions, validate_budget
from analysis.head import validate_head_request
from analysis.positions import qualify_head_positions
from evidence.accept import resolve_qualification_parents
from reports.history import (
    AreaBudgetReport,
    SignedReport,
    insert_area_budget_report,
    insert_report,
)
from reports.receipts import insert_area_budget_receipt, insert_report_receipt


def publish_head(store, first_piece_id, second_piece_id, request):
    request = validate_head_request(request)
    first, second = resolve_qualification_parents(store.catalog, first_piece_id, second_piece_id)
    positions = qualify_head_positions(first.coverage, second.coverage, request)
    parents = (first.piece_id, second.piece_id)
    with store.write_transaction(before_commit=store.before_commit) as connection:
        report_id = insert_report(connection, parents, request, positions)
        receipt = insert_report_receipt(connection, report_id)
    return SignedReport(report_id, parents, request, positions, receipt)


def publish_area_budget(store, first_piece_id, second_piece_id, request, budget):
    request = validate_head_request(request)
    budget = validate_budget(budget)
    first, second = resolve_qualification_parents(store.catalog, first_piece_id, second_piece_id)
    positions = area_budget_positions(first.coverage, second.coverage, request, budget)
    parents = (first.piece_id, second.piece_id)
    with store.write_transaction(before_commit=store.before_commit) as connection:
        report_id = insert_area_budget_report(connection, parents, request, budget, positions)
        receipt = insert_area_budget_receipt(connection, report_id)
    return AreaBudgetReport(report_id, parents, request, budget, positions, receipt)
