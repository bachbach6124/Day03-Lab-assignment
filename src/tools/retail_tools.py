import json
from datetime import date, datetime
from pathlib import Path
from typing import Any


DATA_DIR = Path(__file__).parent / "mock_data"
DEMO_TODAY = date(2026, 6, 1)


def load_json(file_name: str) -> Any:
    path = DATA_DIR / file_name
    with path.open("r", encoding="utf-8") as file:
        content = file.read().strip()
        if not content:
            return []
        return json.loads(content)


def save_json(file_name: str, data: Any) -> None:
    path = DATA_DIR / file_name
    temp_path = path.with_suffix(f"{path.suffix}.tmp")
    with temp_path.open("w", encoding="utf-8") as file:
        json.dump(data, file, ensure_ascii=False, indent=2)
        file.write("\n")
    temp_path.replace(path)


def check_order_status(args: dict) -> dict:
    customer_id = args.get("customer_id")
    product_id = args.get("product_id")

    if not customer_id or not product_id:
        return {
            "error": "missing_required_argument",
            "policy_valid": False,
            "reason": "customer_id and product_id are required",
        }

    orders = load_json("orders.json")
    order = next(
        (
            item
            for item in orders
            if item.get("customer_id") == customer_id
            and item.get("product_id") == product_id
        ),
        None,
    )

    if order is None:
        return {
            "error": "order_not_found",
            "policy_valid": False,
            "reason": "Order not found",
        }

    products = load_json("products.json")
    product = next(
        (item for item in products if item.get("product_id") == product_id),
        None,
    )

    base_result = {
        "order_id": order.get("order_id"),
        "delivery_date": order.get("delivery_date"),
        "current_size": order.get("current_size"),
    }

    if product is None:
        return {
            **base_result,
            "error": "product_not_found",
            "policy_valid": False,
            "reason": "Product policy not found",
        }

    if not order.get("is_delivered"):
        return {
            **base_result,
            "policy_valid": False,
            "reason": "Order has not been delivered yet",
        }

    if (
        not order.get("is_returnable", False)
        or not product.get("returnable", False)
        or not product.get("exchangeable", False)
    ):
        return {
            **base_result,
            "policy_valid": False,
            "reason": order.get("reason") or product.get("policy_note"),
        }

    delivery_date = datetime.strptime(order["delivery_date"], "%Y-%m-%d").date()
    days_since_delivery = (DEMO_TODAY - delivery_date).days
    return_window_days = int(order.get("return_window_days", 7))

    if days_since_delivery < 0:
        return {
            **base_result,
            "policy_valid": False,
            "reason": "Delivery date is in the future",
        }

    if days_since_delivery > return_window_days:
        return {
            **base_result,
            "policy_valid": False,
            "reason": "Expired 7-day exchange window",
        }

    return {
        **base_result,
        "policy_valid": True,
        "reason": order.get("reason", "Within 7-day exchange window"),
    }


def check_warehouse_stock(args: dict) -> dict:
    product_id = args.get("product_id")
    size = args.get("size")

    if not product_id or not size:
        return {
            "status": "not_found",
            "stock_quantity": 0,
            "warehouse": None,
            "reason": "product_id and size are required",
        }

    stock_items = load_json("warehouse_stock.json")
    stock = next(
        (
            item
            for item in stock_items
            if item.get("product_id") == product_id and item.get("size") == size
        ),
        None,
    )

    if stock is None:
        return {
            "status": "not_found",
            "stock_quantity": 0,
            "warehouse": None,
        }

    stock_quantity = int(stock.get("stock_quantity", 0))
    status = "available" if stock_quantity > 0 else "out_of_stock"

    return {
        "status": status,
        "stock_quantity": stock_quantity,
        "warehouse": stock.get("warehouse"),
    }


def create_return_ticket(args: dict) -> dict:
    order_id = args.get("order_id")
    action_type = args.get("action_type")
    detail = args.get("detail")

    if not order_id or not action_type or not detail:
        return {
            "error": "missing_required_argument",
            "reason": "order_id, action_type and detail are required",
        }

    tickets = load_json("return_tickets.json")
    ticket = {
        "ticket_id": "TK-8831",
        "order_id": order_id,
        "action_type": action_type,
        "detail": detail,
        "status": "created",
        "shipper_note": "Thu hồi hàng cũ khi giao hàng mới",
        "estimated_process_time": "2-3 ngày",
        "created_at": "2026-06-01T10:00:00",
    }

    tickets = [
        existing
        for existing in tickets
        if existing.get("ticket_id") != ticket["ticket_id"]
    ]
    tickets.append(ticket)
    save_json("return_tickets.json", tickets)

    return {
        "ticket_id": ticket["ticket_id"],
        "shipper_note": ticket["shipper_note"],
        "estimated_process_time": ticket["estimated_process_time"],
    }


TOOLS = [
    {
        "name": "check_order_status",
        "description": "Check whether a customer's order is eligible for return or exchange. Input JSON: customer_id, product_id.",
        "func": check_order_status,
    },
    {
        "name": "check_warehouse_stock",
        "description": "Check product stock by product_id and requested size. Input JSON: product_id, size.",
        "func": check_warehouse_stock,
    },
    {
        "name": "create_return_ticket",
        "description": "Create a return or exchange ticket for a valid order. Input JSON: order_id, action_type, detail.",
        "func": create_return_ticket,
    },
]
