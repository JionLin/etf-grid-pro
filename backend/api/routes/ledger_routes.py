"""本地挂单账本接口。"""
from flask import Blueprint, jsonify, request

from repositories.ledger_repository import LedgerRepository
from services.analysis.order_ledger import ORDER_STATUSES, StalePostedOrders

ledger_bp = Blueprint("ledger", __name__)


def _price_arg():
    raw = request.args.get("price")
    if raw in (None, "", "null"):
        return None
    try:
        return float(raw)
    except (TypeError, ValueError):
        return None


@ledger_bp.route("/api/ledger/<etf_code>", methods=["GET"])
def get_ledger(etf_code):
    try:
        plan = LedgerRepository().get_plan(etf_code, current_price=_price_arg())
        return jsonify({"success": True, "data": plan, "statuses": list(ORDER_STATUSES)})
    except ValueError as exc:
        return jsonify({"success": False, "error": str(exc)}), 400


@ledger_bp.route("/api/ledger", methods=["POST"])
def save_ledger():
    try:
        data = request.get_json() or {}
        base = data.get("base") or {}
        plan = LedgerRepository().save_plan(
            etf_code=data.get("etfCode") or data.get("etf_code"),
            etf_name=data.get("etfName") or data.get("etf_name") or "",
            anchor_price=data.get("anchorPrice") or data.get("anchor_price") or 0,
            base_shares=base.get("shares") or data.get("baseShares") or 0,
            base_price=base.get("price") or data.get("basePrice") or 0,
            orders=data.get("orders") or [],
            posted_policy=data.get("postedPolicy") or data.get("posted_policy"),
        )
        price = data.get("currentPrice", data.get("current_price"))
        if price not in (None, ""):
            plan = LedgerRepository().get_plan(plan["etf_code"], current_price=float(price))
        return jsonify({"success": True, "data": plan})
    except StalePostedOrders as exc:
        return jsonify({
            "success": False,
            "needs_choice": True,
            "error": "价格变了。旧的已挂单还在，请选择一并作废，或只保留新表里还有的档。",
            "stale_orders": exc.orders,
        }), 409
    except ValueError as exc:
        return jsonify({"success": False, "error": str(exc)}), 400


@ledger_bp.route("/api/ledger/orders/<int:order_id>", methods=["PATCH"])
def update_ledger_order(order_id):
    try:
        data = request.get_json() or {}
        repo = LedgerRepository()
        repo.set_status(order_id, data.get("status"))
        code = data.get("etfCode") or data.get("etf_code") or ""
        price = data.get("currentPrice", data.get("current_price"))
        plan = repo.get_plan(code, current_price=float(price) if price not in (None, "") else None) if code else None
        return jsonify({"success": True, "data": plan})
    except ValueError as exc:
        return jsonify({"success": False, "error": str(exc)}), 400
