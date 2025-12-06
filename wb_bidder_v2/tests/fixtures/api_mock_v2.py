from __future__ import annotations



from fastapi import FastAPI

from typing import Any, Dict, List



app = FastAPI(title="WB API V2 Mock")



# -----------------------------

# Моковые данные

# -----------------------------



MOCK_ADS = [

    {

        "date": "2025-01-01",

        "nm_id": 123456,

        "impressions": 10000,

        "clicks": 500,

        "spend": 1200.5,

        "orders": 60,

        "revenue": 18000.0,

    }

]



MOCK_QUERIES = [

    {

        "date": "2025-01-01",

        "nm_id": 123456,

        "query": "носки мужские",

        "impressions": 8000,

        "clicks": 300,

        "orders": 40,

        "revenue": 10000.0,

        "spend": 600.0,

    }

]



MOCK_FUNNEL = [

    {

        "date": "2025-01-01",

        "nm_id": 123456,

        "impressions": 15000,

        "clicks": 700,

        "orders": 55,

        "revenue": 17000.0,

    }

]



# -----------------------------

# Эндпоинты

# -----------------------------



@app.get("/ads")

def get_ads() -> Dict[str, Any]:

    return {"items": MOCK_ADS}



@app.get("/search-queries")

def get_search_queries() -> Dict[str, Any]:

    return {"items": MOCK_QUERIES}



@app.get("/sales-funnel")

def get_sales_funnel() -> Dict[str, Any]:

    return {"items": MOCK_FUNNEL}



@app.get("/auto-replies")

def get_auto_replies() -> Dict[str, Any]:

    return {"items": []}

