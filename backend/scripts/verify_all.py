import sys
import os
import json

sys.path.insert(0, os.path.abspath("."))

from backend.app.core.database import SessionLocal
from backend.app.models.artifact import Artifact
from backend.app.schemas.rag import QueryRequest
from backend.app.services.rag_service import RagService

COSMETICS_PID = "65f0d22a-2969-42b8-873d-ff653651170b"
FARM_PID = "024194af-bf30-48e5-bb7f-c2c24f086b62"

def verify_cosmetics_schema(db):
    print("\n==========================================")
    print("VERIFYING COSMETICS SCHEMA")
    print("==========================================")
    art = db.query(Artifact).filter(Artifact.project_id == COSMETICS_PID, Artifact.artifact_type == "schema").first()
    if not art:
        print("ERROR: Cosmetics schema not found!")
        return
    data = json.loads(art.content_json)
    tables = {t["name"]: t for t in data.get("tables", [])}
    print(f"Total tables: {len(tables)}")
    print(f"Tables: {list(tables.keys())}")
    
    # 1. order items link to stock batch (batch_id)
    order_items_tbl = tables.get("order_items") or tables.get("order_item")
    has_batch_id = False
    if order_items_tbl:
        cols = [c["name"] for c in order_items_tbl.get("columns", [])]
        print(f"order_items columns: {cols}")
        has_batch_id = "batch_id" in cols
    print(f"Order items link to batch (batch_id): {has_batch_id}")

    # 2. delivered_at on orders
    orders_tbl = tables.get("orders") or tables.get("order")
    has_delivered_at = False
    if orders_tbl:
        cols = [c["name"] for c in orders_tbl.get("columns", [])]
        print(f"orders columns: {cols}")
        has_delivered_at = "delivered_at" in cols
    print(f"Delivered at on orders (delivered_at): {has_delivered_at}")

    # 3. coupon usage counter/table (usage_count / coupon_usages)
    coupons_tbl = tables.get("coupons") or tables.get("coupon") or tables.get("discounts")
    has_coupon_usage = False
    if coupons_tbl:
        cols = [c["name"] for c in coupons_tbl.get("columns", [])]
        print(f"coupons columns: {cols}")
        has_coupon_usage = "usage_count" in cols or "times_used" in cols
    coupon_usages_tbl = tables.get("coupon_usages") or tables.get("coupon_usage") or tables.get("user_coupons") or tables.get("coupon_usage_ledger")
    if coupon_usages_tbl:
        print(f"Dedicated coupon usages table exists: {coupon_usages_tbl['name']}")
        has_coupon_usage = True
    print(f"Coupon usage tracking exists: {has_coupon_usage}")

def verify_farm_schema(db):
    print("\n==========================================")
    print("VERIFYING FARM SCHEMA")
    print("==========================================")
    art = db.query(Artifact).filter(Artifact.project_id == FARM_PID, Artifact.artifact_type == "schema").first()
    if not art:
        print("ERROR: Farm schema not found!")
        return
    data = json.loads(art.content_json)
    tables = {t["name"]: t for t in data.get("tables", [])}
    print(f"Total tables: {len(tables)}")
    print(f"Table names: {list(tables.keys())}")

    checks = {}

    # 1. harvest_date
    for tname, tbl in tables.items():
        cols = [c["name"] for c in tbl.get("columns", [])]
        if "harvest_date" in cols:
            checks["harvest_date"] = f"Found in table '{tname}'"
            break
    if "harvest_date" not in checks:
        checks["harvest_date"] = "Missing"

    # 2. shelf life or expiry per listing
    for tname, tbl in tables.items():
        cols = [c["name"] for c in tbl.get("columns", [])]
        if any("shelf_life" in c or "expiry" in c for c in cols):
            checks["shelf_life_or_expiry"] = f"Found in table '{tname}': {[c for c in cols if 'shelf' in c or 'expir' in c]}"
            break
    if "shelf_life_or_expiry" not in checks:
        checks["shelf_life_or_expiry"] = "Missing"

    # 3. stock reservation with expiry time
    for tname, tbl in tables.items():
        cols = [c["name"] for c in tbl.get("columns", [])]
        if "reservation" in tname or any("reserve" in c or "reservation" in c for c in cols):
            checks["stock_reservation"] = f"Found in table '{tname}': {cols}"
            break
    if "stock_reservation" not in checks:
        checks["stock_reservation"] = "Missing"

    # 4. delivered_at on sub-orders
    sub_orders_tbl = tables.get("sub_orders") or tables.get("sub_order")
    if sub_orders_tbl:
        cols = [c["name"] for c in sub_orders_tbl.get("columns", [])]
        checks["delivered_at_sub_orders"] = f"Found in 'sub_orders': {cols}" if any("deliver" in c for c in cols) else f"Missing 'delivered_at' in sub_orders: {cols}"
    else:
        checks["delivered_at_sub_orders"] = "Missing sub_orders table"

    # 5. rating count or a review table
    for tname, tbl in tables.items():
        if any(k in tname for k in ["review", "rating"]):
            cols = [c["name"] for c in tbl.get("columns", [])]
            checks["reviews_or_ratings"] = f"Found in table '{tname}': {cols}"
            break
    if "reviews_or_ratings" not in checks:
        checks["reviews_or_ratings"] = "Missing"

    # 6. wallet and wallet transactions
    for tname, tbl in tables.items():
        if "wallet" in tname:
            checks["wallet_and_transactions"] = f"Found wallet table '{tname}'"
            break
    if "wallet_and_transactions" not in checks:
        checks["wallet_and_transactions"] = "Missing"

    # 7. payouts
    for tname, tbl in tables.items():
        cols = [c["name"] for c in tbl.get("columns", [])]
        if "payout" in tname or any("payout" in c for c in cols):
            checks["payouts"] = f"Found in table '{tname}': {cols}"
            break
    if "payouts" not in checks:
        checks["payouts"] = "Missing"

    # 8. complaints
    for tname, tbl in tables.items():
        if any(k in tname for k in ["complaint", "issue", "dispute"]):
            cols = [c["name"] for c in tbl.get("columns", [])]
            checks["complaints"] = f"Found in table '{tname}': {cols}"
            break
    if "complaints" not in checks:
        checks["complaints"] = "Missing"

    # 9. delivery slots with capacity
    for tname, tbl in tables.items():
        cols = [c["name"] for c in tbl.get("columns", [])]
        if "slot" in tname:
            checks["delivery_slots_capacity"] = f"Found in table '{tname}': {cols}"
            break
    if "delivery_slots_capacity" not in checks:
        checks["delivery_slots_capacity"] = "Missing"

    # 10. subscriptions
    for tname, tbl in tables.items():
        if "subscription" in tname:
            checks["subscriptions"] = f"Found subscription table '{tname}'"
            break
    if "subscriptions" not in checks:
        checks["subscriptions"] = "Missing"

    print("\nFarm Schema Checks Summary:")
    for k, v in checks.items():
        print(f"  {k}: {v}")

def test_query_assistant(db):
    print("\n==========================================")
    print("TESTING QUERY ASSISTANT ON FARM PROJECT")
    print("==========================================")
    chips = RagService.get_suggested_questions(FARM_PID, db)
    print(f"Suggested chips ({len(chips)}):")
    for c in chips:
        print(f"  - {c}")

    chip_questions = [c["q"] for c in chips] if chips else [
        "Why is the farm_profiles table required?",
        "Explain the system architecture of Farm produce Management.",
        "What are the non-functional requirements?",
        "What authentication method is required?"
    ]

    all_questions = chip_questions + [
        "list all modules",
        "what are the actors?",
        "how long does a farmer wait for a payout?",
        "who won the world cup?"  # must be refused!
    ]

    for q in all_questions:
        print(f"\n--- Query: '{q}' ---")
        req = QueryRequest(question=q)
        res = RagService.query_project(FARM_PID, req, db)
        answer = res.answer
        citations = res.citations
        is_refusal = "not covered" in answer.lower() or "cannot answer" in answer.lower() or "unrelated" in answer.lower()
        print(f"Refusal: {is_refusal}")
        print(f"Answer: {answer}")
        print(f"Citations: {[c.source for c in citations]}")

if __name__ == "__main__":
    db = SessionLocal()
    try:
        verify_cosmetics_schema(db)
        verify_farm_schema(db)
        test_query_assistant(db)
    finally:
        db.close()
