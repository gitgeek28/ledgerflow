"""Seed (or reset + reseed) the demo environment with fictional reference data and policy v1.

Usage:  uv run python -m app.seed.seed [--reset]
"""
import argparse
import shutil
from datetime import UTC, datetime
from decimal import Decimal

from sqlalchemy import select, text
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.db.models import GoodsReceipt, GoodsReceiptLine, Policy, POLine, PurchaseOrder, User, Vendor
from app.db.session import session_scope
from app.seed.reference_data import GOODS_RECEIPTS, PURCHASE_ORDERS, USERS, VENDOR_BY_CODE, VENDORS
from app.services.identifiers import bank_fingerprint, make_gstin
from app.services.money import q2
from app.services.policy import PolicySettings, settings_to_json
from app.services.text_norm import normalise_description

TABLES = ["audit_events", "run_events", "jobs", "invoice_checks", "po_line_consumptions", "invoice_notes",
          "invoice_lines", "processing_runs", "invoices", "intake_batches", "goods_receipt_lines",
          "goods_receipts", "po_lines", "purchase_orders", "policies", "vendors", "users"]


def reset(db: Session) -> None:
    db.execute(text(f"TRUNCATE {', '.join(TABLES)} RESTART IDENTITY CASCADE"))
    db.execute(text("ALTER SEQUENCE invoice_reference_seq RESTART WITH 1001"))
    storage = get_settings().storage_dir
    if storage.exists():
        for child in storage.iterdir():
            if child.is_dir():
                shutil.rmtree(child)
            elif child.name != ".gitkeep":
                child.unlink()


def seed(db: Session) -> dict:
    if db.scalar(select(Vendor).limit(1)) is not None:
        return {"skipped": True}
    now = datetime.now(UTC)
    users = {}
    for u in USERS:
        user = User(**u)
        db.add(user)
        users[u["email"]] = user
    db.flush()

    manager = users["vikram.iyer@kestrel.example"]
    policy = Policy(version=1, name="Demo AP policy", settings=settings_to_json(PolicySettings()),
                    change_note="Initial sample policy (illustrative demo tolerances, not accounting advice).",
                    is_active=True, created_by_id=manager.id, effective_from=now)
    db.add(policy)

    vendors = {}
    for v in VENDORS:
        vendor = Vendor(
            vendor_code=v.code, legal_name=v.legal_name, display_name=v.display_name, aliases=v.aliases,
            tax_id=make_gstin(v.state_code, v.pan), pan=v.pan, country_code="IN", state_code=v.state_code,
            registered_address=v.address, city=v.city, approved_status=v.status, status_reason=v.status_reason,
            currency="INR", payment_terms_days=v.terms, category=v.category, contact_email=v.email,
            bank_account_fingerprint=bank_fingerprint(v.account), bank_account_last4=v.account[-4:],
            bank_ifsc=v.ifsc, bank_name=v.bank_name, bank_details_version=1, bank_details_updated_at=now,
        )
        db.add(vendor)
        vendors[v.code] = vendor
    db.flush()

    pos = {}
    for p in PURCHASE_ORDERS:
        vdef = VENDOR_BY_CODE[p.vendor_code]
        po = PurchaseOrder(po_number=p.po_number, vendor_id=vendors[p.vendor_code].id, status=p.status,
                           po_type=p.po_type, currency="INR", po_date=p.po_date, valid_until=p.valid_until,
                           description=p.description, requester=p.requester, cost_centre=p.cost_centre,
                           subtotal=Decimal(0), tax_total=Decimal(0), total_amount=Decimal(0))
        subtotal = tax = Decimal(0)
        for n, (item_idx, qty) in enumerate(p.lines, start=1):
            item = vdef.items[item_idx]
            line_sub = q2(Decimal(qty) * Decimal(item.price))
            line_tax = q2(line_sub * Decimal(item.tax_rate) / Decimal(100))
            po.lines.append(POLine(line_number=n, item_code=item.item_code, description=item.description,
                                   normalised_description=normalise_description(item.description),
                                   quantity_ordered=Decimal(qty), unit=item.unit, unit_price=Decimal(item.price),
                                   tax_rate=Decimal(item.tax_rate), line_subtotal=line_sub,
                                   line_total=line_sub + line_tax))
            subtotal += line_sub
            tax += line_tax
        po.subtotal, po.tax_total, po.total_amount = subtotal, tax, subtotal + tax
        db.add(po)
        pos[p.po_number] = po
    db.flush()

    for g in GOODS_RECEIPTS:
        po = pos[g.po_number]
        grn = GoodsReceipt(grn_number=g.grn_number, po_id=po.id, received_date=g.received_date,
                           received_by=g.received_by, warehouse=g.warehouse)
        by_number = {line.line_number: line for line in po.lines}
        for line_no, qty in g.quantities.items():
            grn.lines.append(GoodsReceiptLine(po_line_id=by_number[line_no].id, quantity_received=Decimal(qty)))
        db.add(grn)
    db.flush()
    return {"users": len(users), "vendors": len(vendors), "purchase_orders": len(pos),
            "goods_receipts": len(GOODS_RECEIPTS), "policy_version": 1}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--reset", action="store_true", help="Delete ALL data (incl. invoices) before seeding")
    args = parser.parse_args()
    get_settings().storage_dir.mkdir(parents=True, exist_ok=True)
    with session_scope() as db:
        if args.reset:
            reset(db)
        result = seed(db)
    print(result)


if __name__ == "__main__":
    main()
