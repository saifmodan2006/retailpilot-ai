from datetime import timedelta
from typing import Protocol

import httpx
from fastapi import HTTPException
from pydantic import BaseModel

from .analytics import analytics, inventory_metrics
from .core import settings

QUESTIONS = {
    "stores": "Which stores had the highest sales last month?",
    "stockouts": "Which products are likely to run out within 14 days?",
    "dead-stock": "Which category has the most dead-stock value?",
    "inventory": "What is our current inventory value?",
    "reorder": "Which SKUs should management review for reordering?",
    "revenue": "Why did revenue change compared with the previous month?",
}


class ToolSelection(BaseModel):
    tool: str


class AnalystProvider(Protocol):
    def select_tool(self, question: str) -> str: ...


class DeterministicProvider:
    def select_tool(self, question):
        q = question.lower().strip()
        if q in QUESTIONS:
            return q
        if "reorder" in q:
            return "reorder"
        if "run out" in q or "stockout" in q:
            return "stockouts"
        if "dead" in q:
            return "dead-stock"
        if "inventory" in q and "value" in q:
            return "inventory"
        if "stores" in q and ("sales" in q or "highest" in q):
            return "stores"
        if "revenue" in q and ("change" in q or "decline" in q):
            return "revenue"
        raise HTTPException(
            422,
            "Choose one of the supported analytical questions. Free-form LLM analysis is not enabled.",
        )


class OpenAICompatibleProvider:
    def select_tool(self, question):
        # Only the question and allowlist leave the service; no uploaded business rows.
        with httpx.Client(timeout=20) as client:
            response = client.post(
                settings.llm_base_url.rstrip("/") + "/chat/completions",
                headers={"Authorization": f"Bearer {settings.llm_api_key}"},
                json={
                    "model": settings.llm_model,
                    "temperature": 0,
                    "messages": [
                        {
                            "role": "system",
                            "content": "Choose one tool from "
                            + str(QUESTIONS)
                            + '. Return JSON {"tool":"key"}. Never emit SQL.',
                        },
                        {"role": "user", "content": question},
                    ],
                    "response_format": {"type": "json_object"},
                },
            )
            response.raise_for_status()
            result = ToolSelection.model_validate_json(
                response.json()["choices"][0]["message"]["content"]
            )
            if result.tool not in QUESTIONS:
                raise HTTPException(422, "Question is outside the approved analytical tools")
            return result.tool


def answer(db, org, question, filters, config):
    provider = (
        OpenAICompatibleProvider()
        if settings.llm_enabled
        and settings.llm_api_key
        and settings.llm_base_url
        and settings.llm_model
        else DeterministicProvider()
    )
    try:
        tool = provider.select_tool(question)
    except (httpx.HTTPError, ValueError, KeyError) as exc:
        raise HTTPException(
            502,
            "Optional provider unavailable; use a predefined question with LLM_ENABLED=false",
        ) from exc
    f = filters
    if tool in ["stores", "revenue"]:
        end = f.end.replace(day=1) - timedelta(days=1)
        f = f.model_copy(update={"start": end.replace(day=1), "end": end})
    data = analytics(db, org, f, config) if tool in ["stores", "revenue", "inventory"] else None
    inventory = (
        inventory_metrics(db, org, f, config)
        if tool in ["dead-stock", "stockouts", "reorder"]
        else []
    )
    if tool == "stores":
        rows, text = (
            data["stores"],
            "Stores ranked by net revenue, including returns and discounts.",
        )
    elif tool == "inventory":
        rows, text = (
            [
                {
                    "metric": "Inventory at purchase cost (INR)",
                    "value": data["metrics"]["inventory_value"],
                }
            ],
            "Latest snapshot per store/SKU, multiplied by product purchase cost. This is inventory capital, not retail selling value.",
        )
    elif tool == "dead-stock":
        totals = {}
        for r in inventory:
            if r["dead_stock"]:
                totals[r["category"]] = totals.get(r["category"], 0) + r["value"]
        rows = sorted(
            [{"category": k, "value": round(v, 2)} for k, v in totals.items()],
            key=lambda r: -r["value"],
        )
        text = f"Positive stock with no positive-unit sale for at least {config.get('dead_days', 90)} days; no-sale SKUs use receipt age."
    elif tool in ["stockouts", "reorder"]:
        chosen = (
            [
                r
                for r in inventory
                if (r["cover_days"] is not None and r["cover_days"] < 14)
                if tool == "stockouts"
            ]
            if tool == "stockouts"
            else [r for r in inventory if r["reorder_quantity"] > 0]
        )
        rows = [
            {
                k: r[k]
                for k in [
                    "sku",
                    "store",
                    "available",
                    "daily_demand",
                    "cover_days",
                    "reorder_quantity",
                ]
            }
            for r in chosen
        ][:100]
        text = "Planning estimate using the trailing 30 calendar days. Assumes demand continues at its recent average; not a guaranteed stockout date."
    else:
        previous_end = f.start - timedelta(days=1)
        previous = analytics(
            db,
            org,
            f.model_copy(update={"start": previous_end.replace(day=1), "end": previous_end}),
            config,
        )
        rows = [
            {
                "period": "Previous calendar month",
                "revenue": previous["metrics"]["revenue"],
            },
            {"period": "Last calendar month", "revenue": data["metrics"]["revenue"]},
            {
                "period": "Change (INR)",
                "revenue": round(data["metrics"]["revenue"] - previous["metrics"]["revenue"], 2),
            },
        ]
        text = "A period comparison identifies the amount of change. Causal explanations require promotion, pricing, footfall, and availability evidence not present here."
    return {
        "mode": "LLM tool selection + validated calculations"
        if isinstance(provider, OpenAICompatibleProvider)
        else "Deterministic analytics · no LLM",
        "tool": tool,
        "explanation": text,
        "rows": rows,
        "filters": f.model_dump(mode="json"),
        "data_label": "Synthetic demonstration data",
    }
