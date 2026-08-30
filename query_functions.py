import json
from datetime import datetime
from monday_data import load_live_data

WORK_ORDERS, DEALS = load_live_data()


def get_deals(sector=None, deal_status=None, deal_stage=None,
              close_after=None, close_before=None):
    results = DEALS
    if sector:
        results = [d for d in results if d["sector_service"] and d["sector_service"].lower() == sector.lower()]
    if deal_status:
        results = [d for d in results if d["deal_status"] and d["deal_status"].lower() == deal_status.lower()]
    if deal_stage:
        results = [d for d in results if d["deal_stage"] and deal_stage.lower() in d["deal_stage"].lower()]
    if close_after:
        results = [d for d in results if d["tentative_close_date"] and d["tentative_close_date"] >= close_after]
    if close_before:
        results = [d for d in results if d["tentative_close_date"] and d["tentative_close_date"] <= close_before]
    return results


def get_deals_with_date_exclusion_note(sector=None, deal_status=None, deal_stage=None,
                                         close_after=None, close_before=None):
    """Same filtering as get_deals, but also reports how many records were excluded purely due to
    missing tentative_close_date, so a 'zero results' from date filtering isn't misread as a confirmed
    zero when the real cause is missing data."""
    base_results = DEALS
    if sector:
        base_results = [d for d in base_results if d["sector_service"] and d["sector_service"].lower() == sector.lower()]
    if deal_status:
        base_results = [d for d in base_results if d["deal_status"] and d["deal_status"].lower() == deal_status.lower()]
    if deal_stage:
        base_results = [d for d in base_results if d["deal_stage"] and deal_stage.lower() in d["deal_stage"].lower()]

    total_before_date_filter = len(base_results)
    missing_date_count = sum(1 for d in base_results if not d["tentative_close_date"])

    date_filtered = base_results
    if close_after:
        date_filtered = [d for d in date_filtered if d["tentative_close_date"] and d["tentative_close_date"] >= close_after]
    if close_before:
        date_filtered = [d for d in date_filtered if d["tentative_close_date"] and d["tentative_close_date"] <= close_before]

    total_value = sum(d["masked_deal_value"] for d in date_filtered if d["masked_deal_value"] is not None)

    return {
        "matched_deals": date_filtered,
        "matched_count": len(date_filtered),
        "matched_total_value": total_value,
        "total_before_date_filter": total_before_date_filter,
        "excluded_due_to_missing_date": missing_date_count,
        "note": f"{missing_date_count} of {total_before_date_filter} deals in scope have no tentative_close_date set, so their timing is unknown rather than confirmed outside the requested period."
    }


def get_work_orders(sector=None, execution_status=None,
                     start_after=None, start_before=None):
    results = WORK_ORDERS
    if sector:
        results = [w for w in results if w["sector"] and w["sector"].lower() == sector.lower()]
    if execution_status:
        results = [w for w in results if w["execution_status"] and w["execution_status"].lower() == execution_status.lower()]
    if start_after:
        results = [w for w in results if w["probable_start_date"] and w["probable_start_date"] >= start_after]
    if start_before:
        results = [w for w in results if w["probable_start_date"] and w["probable_start_date"] <= start_before]
    return results


def get_deal_summary_stats(deals, pipeline_view=False):
    total_deals = len(deals)

    status_breakdown = {}
    for d in deals:
        status = d["deal_status"] or "Unknown"
        status_breakdown[status] = status_breakdown.get(status, 0) + 1

    working_set = deals
    definition_note = "all deals regardless of status"
    if pipeline_view:
        working_set = [d for d in deals if d["deal_status"] and d["deal_status"].lower() == "open"]
        excluded = total_deals - len(working_set)
        definition_note = f"open deals only (pipeline convention) — excluded {excluded} closed deals (Won/Dead/On Hold)"

    total_value = sum(d["masked_deal_value"] for d in working_set if d["masked_deal_value"] is not None)
    deals_with_value = sum(1 for d in working_set if d["masked_deal_value"] is not None)

    stage_breakdown = {}
    for d in working_set:
        stage = d["deal_stage"] or "Unknown"
        stage_breakdown[stage] = stage_breakdown.get(stage, 0) + 1

    probability_breakdown = {}
    for d in working_set:
        prob = d["closure_probability"] or "Not Set"
        probability_breakdown[prob] = probability_breakdown.get(prob, 0) + 1

    return {
        "definition_used": definition_note,
        "total_deals_in_scope": len(working_set),
        "total_deals_all_statuses": total_deals,
        "total_value": total_value,
        "deals_with_known_value": deals_with_value,
        "deals_missing_value": len(working_set) - deals_with_value,
        "full_status_breakdown": status_breakdown,
        "stage_breakdown": stage_breakdown,
        "closure_probability_breakdown": probability_breakdown,
    }


def get_work_order_summary_stats(work_orders):
    total_wo = len(work_orders)
    total_billed = sum(w["billed_value_incl_gst"] for w in work_orders if w["billed_value_incl_gst"] is not None)
    total_receivable = sum(w["amount_receivable"] for w in work_orders if w["amount_receivable"] is not None)
    total_collected = sum(w["collected_amount_incl_gst"] for w in work_orders if w["collected_amount_incl_gst"] is not None)

    status_breakdown = {}
    for w in work_orders:
        status = w["execution_status"] or "Unknown"
        status_breakdown[status] = status_breakdown.get(status, 0) + 1

    return {
        "total_work_orders": total_wo,
        "total_billed_incl_gst": total_billed,
        "total_receivable": total_receivable,
        "total_collected_incl_gst": total_collected,
        "execution_status_breakdown": status_breakdown,
    }


def assess_data_quality(records, fields_to_check):
    total = len(records)
    if total == 0:
        return {"total_records": 0, "field_completeness": {}}

    completeness = {}
    for field in fields_to_check:
        non_null_count = sum(1 for r in records if r.get(field) is not None)
        completeness[field] = {
            "non_null": non_null_count,
            "null": total - non_null_count,
            "completeness_pct": round(100 * non_null_count / total, 1)
        }

    return {"total_records": total, "field_completeness": completeness}


def _days_between(date_str1, date_str2):
    try:
        d1 = datetime.strptime(date_str1, "%Y-%m-%d")
        d2 = datetime.strptime(date_str2, "%Y-%m-%d")
        return abs((d1 - d2).days)
    except (ValueError, TypeError):
        return None


def match_work_order_to_deal(wo):
    name = wo["name"]
    candidates = [d for d in DEALS if d["name"] == name]

    if not candidates:
        return {"status": "no_match", "reason": "deal name not found in Deals board", "candidates": []}

    same_sector = [d for d in candidates if d["sector_service"] == wo["sector"]]

    if same_sector:
        pool = same_sector
        match_basis = "name+sector"
        base_confidence = "high"
    else:
        pool = candidates
        match_basis = f"name only — sector mismatch (WO sector: {wo['sector']}, no deal with this name shares it)"
        base_confidence = "medium"

    if len(pool) == 1:
        return {
            "status": "matched",
            "confidence": base_confidence,
            "basis": match_basis,
            "matched_deal": pool[0],
            "candidates_considered": len(pool)
        }

    wo_po_date = wo.get("date_of_po_loi")
    scored = []
    for d in pool:
        deal_date = d.get("close_date_actual") or d.get("tentative_close_date")
        gap = _days_between(wo_po_date, deal_date) if (wo_po_date and deal_date) else None
        scored.append((d, gap))

    dated = [(d, g) for d, g in scored if g is not None]
    if not dated:
        return {
            "status": "ambiguous",
            "confidence": "low",
            "basis": match_basis,
            "reason": "multiple candidates share this name, and no dates available to disambiguate",
            "candidates": pool,
            "candidates_considered": len(pool)
        }

    dated.sort(key=lambda x: x[1])
    best_deal, best_gap = dated[0]

    if len(dated) == 1 or (dated[1][1] - best_gap) >= 30:
        final_confidence = "medium" if base_confidence == "high" else "low"
        return {
            "status": "matched",
            "confidence": final_confidence,
            "basis": f"{match_basis} + closest PO-to-close-date proximity ({best_gap} days)",
            "matched_deal": best_deal,
            "candidates_considered": len(pool)
        }

    return {
        "status": "ambiguous",
        "confidence": "low",
        "basis": match_basis,
        "reason": f"{len(dated)} candidates have similarly close dates (within 30 days of each other)",
        "candidates": pool,
        "candidates_considered": len(pool)
    }