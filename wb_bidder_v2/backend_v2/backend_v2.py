from fastapi import FastAPI, Query, HTTPException
from typing import Optional, Any, Dict, List
import datetime as dt
import requests
import logging

from pydantic import BaseModel

from wb_bidder_v2.wb_api.client import WildberriesClient
from wb_bidder_v2.wb_api.api_client_v2 import ApiClientV2
from wb_bidder_v2.core.auth import load_token
from wb_bidder_v2.wb_api.raw.ads_client import AdsRawClient
from wb_bidder_v2.wb_api.raw.sales_funnel_client import SalesFunnelRawClient
from wb_bidder_v2.wb_api.raw.search_report_client import SearchReportRawClient
from wb_bidder_v2.wb_api.raw.feedbacks_client import FeedbacksRawClient
from wb_bidder_v2.bidder.campaign_controls import verify_change, cache_command_result
from wb_bidder_v2.adapters.state_store import state_store, load_state, update_from_campaigns_api
logger = logging.getLogger(__name__)

WB_TOKEN: str = load_token()
if not WB_TOKEN:
    logger.warning("WB_TOKEN is empty; WB API requests may fail")

_ads_raw_client = AdsRawClient.from_env()
_sales_funnel_raw_client = SalesFunnelRawClient.from_env()
_search_report_raw_client = SearchReportRawClient.from_env()
_feedbacks_raw_client = FeedbacksRawClient.from_env()
_api_v2_client = ApiClientV2()


class SetBidRequest(BaseModel):
    campaignId: int
    bid: int


class CampaignToggleRequest(BaseModel):
    campaignId: int


def set_bid_command(campaign_id: int, new_bid: int) -> Dict[str, Any]:
    client = WildberriesClient(token=WB_TOKEN)
    try:
        client.set_bids(
            advert_id=campaign_id,
            bids=[{"bid": int(new_bid)}],
        )
    except Exception as exc:
        logger.error("WB set_bids failed: %s", exc)
        return {"success": False, "campaignId": campaign_id, "bid": new_bid, "error": str(exc)}

    success = verify_change(campaign_id, {"bid": int(new_bid)})
    if success:
        cache_command_result(campaign_id, bid=int(new_bid))
    return {"success": success, "campaignId": campaign_id, "bid": int(new_bid)}


def enable_campaign_command(campaign_id: int) -> Dict[str, Any]:
    success = _update_campaign_status(campaign_id, desired="active")
    if success:
        cache_command_result(campaign_id, status="active")
    return {"success": success, "campaignId": campaign_id, "status": "active"}


def disable_campaign_command(campaign_id: int) -> Dict[str, Any]:
    success = _update_campaign_status(campaign_id, desired="stopped")
    if success:
        cache_command_result(campaign_id, status="stopped")
    return {"success": success, "campaignId": campaign_id, "status": "stopped"}


def _update_campaign_status(campaign_id: int, desired: str) -> bool:
    client = WildberriesClient(token=WB_TOKEN)
    payload = {"campaignId": campaign_id, "status": desired}
    try:
        resp = client.post("/adv/v1/campaigns/status", json=payload, timeout=10.0)
        resp.raise_for_status()
    except Exception as exc:
        logger.error("WB status update failed: %s", exc)
        return False
    return verify_change(campaign_id, {"status": desired})


def _safe_float(value: Any) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def _safe_int(value: Any) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


def _parse_id_list(raw: Optional[str], field_name: str) -> List[int]:
    if not raw:
        return []
    ids: List[int] = []
    for part in raw.split(","):
        part = part.strip()
        if not part:
            continue
        try:
            ids.append(int(part))
        except ValueError as exc:
            raise HTTPException(
                status_code=400,
                detail=f"Неверный формат {field_name}. Ожидается список чисел через запятую",
            ) from exc
    return ids


def _extract_nm_id_from_campaign(campaign: Dict[str, Any]) -> Optional[int]:
    for key in ("nmId", "nm_id", "nm", "item_id"):
        value = campaign.get(key)
        if value is not None:
            nm = _safe_int(value)
            if nm:
                return nm
    params = campaign.get("params")
    if isinstance(params, list):
        for param in params:
            if isinstance(param, dict):
                for key in ("nm", "nmId", "nm_id"):
                    value = param.get(key)
                    if value is not None:
                        nm = _safe_int(value)
                        if nm:
                            return nm
    nms = campaign.get("nms")
    if isinstance(nms, list):
        for nm in nms:
            if isinstance(nm, dict):
                value = nm.get("nm") or nm.get("nmId") or nm.get("nm_id")
                if value is not None:
                    nm_val = _safe_int(value)
                    if nm_val:
                        return nm_val
    return None


def _extract_nm_id_from_entry(entry: Dict[str, Any]) -> Optional[int]:
    for key in ("nm", "nmId", "nm_id", "item_id"):
        if key in entry and entry[key] is not None:
            nm = _safe_int(entry[key])
            if nm:
                return nm
    apps = entry.get("apps")
    if isinstance(apps, list):
        for app in apps:
            if not isinstance(app, dict):
                continue
            nms = app.get("nms")
            if isinstance(nms, list):
                for nm in nms:
                    if isinstance(nm, dict):
                        value = nm.get("nm") or nm.get("nmId") or nm.get("nm_id")
                        if value is not None:
                            nm_val = _safe_int(value)
                            if nm_val:
                                return nm_val
    return None


def _aggregate_campaign_row(campaign: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    advert_id_raw = campaign.get("advertId") or campaign.get("advert_id") or campaign.get("id")
    advert_id = _safe_int(advert_id_raw)
    if advert_id <= 0:
        return None

    totals = {
        "views": 0.0,
        "clicks": 0.0,
        "orders": 0.0,
        "spent": 0.0,
        "revenue": 0.0,
    }

    stats_entries: List[Dict[str, Any]] = []
    for key in ("stats", "days"):
        block = campaign.get(key)
        if isinstance(block, list):
            stats_entries.extend([entry for entry in block if isinstance(entry, dict)])

    nm_id = _extract_nm_id_from_campaign(campaign)
    for entry in stats_entries:
        nm_id = nm_id or _extract_nm_id_from_entry(entry)
        totals["views"] += _safe_float(entry.get("views") or entry.get("impressions") or entry.get("shows"))
        totals["clicks"] += _safe_float(entry.get("clicks"))
        totals["orders"] += _safe_float(entry.get("orders") or entry.get("purchases") or entry.get("sales"))
        spent_value = entry.get("sum")
        if spent_value is None:
            spent_value = entry.get("spent") or entry.get("expense") or entry.get("cost")
        totals["spent"] += _safe_float(spent_value)
        revenue_value = entry.get("sum_price") or entry.get("sumPrice") or entry.get("revenue")
        totals["revenue"] += _safe_float(revenue_value)

    if not stats_entries:
        totals["views"] = _safe_float(campaign.get("views") or campaign.get("impressions") or campaign.get("shows"))
        totals["clicks"] = _safe_float(campaign.get("clicks"))
        totals["orders"] = _safe_float(campaign.get("orders") or campaign.get("purchases"))
        totals["spent"] = _safe_float(campaign.get("sum") or campaign.get("spent") or campaign.get("expense"))
        totals["revenue"] = _safe_float(campaign.get("sum_price") or campaign.get("revenue"))

    views = totals["views"]
    clicks = totals["clicks"]
    orders = totals["orders"]
    spent = totals["spent"]
    revenue = totals["revenue"]

    ctr = (clicks / views * 100.0) if views > 0 else 0.0
    cpc = (spent / clicks) if clicks > 0 else 0.0
    cpo = (spent / orders) if orders > 0 else 0.0

    return {
        "advertId": advert_id,
        "campaign_id": advert_id,
        "nmId": nm_id,
        "views": views,
        "clicks": clicks,
        "orders": orders,
        "revenue": revenue,
        "spent": spent,
        "ctr": ctr,
        "cpc": cpc,
        "cpo": cpo,
    }


def _normalize_ads_response(payload: Any) -> List[Dict[str, Any]]:
    campaigns: List[Dict[str, Any]] = []
    if isinstance(payload, dict) and "wb_raw" in payload:
        payload = payload["wb_raw"]
    if isinstance(payload, dict):
        campaigns = [payload]
    elif isinstance(payload, list):
        campaigns = [item for item in payload if isinstance(item, dict)]
    else:
        return []

    normalized: List[Dict[str, Any]] = []
    for campaign in campaigns:
        row = _aggregate_campaign_row(campaign)
        if row:
            normalized.append(row)
    return normalized


def _fetch_fullstats_data(campaign_ids: List[int], date_from: str, date_to: str) -> Any:
    return _ads_raw_client.fetch_fullstats(
        campaign_ids=campaign_ids,
        date_from=date_from,
        date_to=date_to,
    )


app = FastAPI(

    title="WB-BIDDER v2 backend API",

    version="0.0.1",

)



@app.get("/health")

def health():

    """

    Простой ping-эндпоинт, чтобы проверить, что backend_v2 жив.

    """

    return {

        "status": "ok",

        "time": dt.datetime.utcnow().isoformat() + "Z",

    }


@app.get("/state")
def get_state():
    """
    Return the current bidder state (campaign/item mappings) for diagnostics.
    """
    return load_state()



# ========================================

# /campaigns — список рекламных кампаний

# ========================================

@app.get("/campaigns")

def get_campaigns(

    type: int = Query(0, ge=0, description="Тип кампании: 0=все, 4=поиск, 5=автореклама, 6=рекомендации"),

):

    """

    Получить список всех рекламных кампаний из WB API.

    

    Возвращает:

    - campaigns: список кампаний с полной информацией

    - item_to_campaign: словарь связки nm_id -> [advert_id, ...]

    - campaign_to_item: словарь связки advert_id -> nm_id

    

    Параметры:

    - type: фильтр по типу кампании (0 = все типы)

    """

    campaigns = _api_v2_client.get_campaigns()
    if not isinstance(campaigns, list):
        campaigns = []

    # Фильтруем по типу, если указан
    if type > 0:
        campaigns = [c for c in campaigns if c.get("type") == type]

    # Строим связки item_id ↔ campaign_id
    # В структуре кампании WB может быть поле "nm" (nm_id) или "nmId"
    item_to_campaign: dict[int, list[int]] = {}
    campaign_to_item: dict[int, int] = {}
    
    # Нормализуем кампании в единый формат
    normalized_campaigns = []



    for camp in campaigns:
        advert_id = camp.get("advertId") or camp.get("advert_id") or camp.get("id")
        if not advert_id:
            continue

        # Пытаемся извлечь nm_id из разных полей
        nm_id = None
        if "nm" in camp:
            nm_id = camp["nm"]
        elif "nmId" in camp:
            nm_id = camp["nmId"]
        elif "nm_id" in camp:
            nm_id = camp["nm_id"]
        elif "params" in camp and isinstance(camp["params"], list):
            # Иногда nm_id лежит в params[].nm
            for param in camp["params"]:
                if isinstance(param, dict):
                    nm_id = param.get("nm") or param.get("nmId") or param.get("nm_id")
                    if nm_id:
                        break

        try:
            advert_id_int = int(advert_id)
        except (ValueError, TypeError):
            continue

        # Нормализуем кампанию в единый формат
        normalized_camp = {
            "campaign_id": advert_id_int,
            "item_id": None,
            "name": camp.get("name") or camp.get("campaignName") or "",
            "type": camp.get("type"),
            "status": camp.get("status") or camp.get("state"),
        }

        if nm_id:
            try:
                nm_id_int = int(nm_id)
                normalized_camp["item_id"] = nm_id_int
                
                # item_to_campaign: один товар может иметь несколько кампаний
                if nm_id_int not in item_to_campaign:
                    item_to_campaign[nm_id_int] = []
                if advert_id_int not in item_to_campaign[nm_id_int]:
                    item_to_campaign[nm_id_int].append(advert_id_int)

                # campaign_to_item: одна кампания обычно связана с одним товаром
                if advert_id_int not in campaign_to_item:
                    campaign_to_item[advert_id_int] = nm_id_int
            except (ValueError, TypeError):
                pass

        normalized_campaigns.append(normalized_camp)

    update_from_campaigns_api(
        {
            "campaigns": normalized_campaigns,
        }
    )

    return {
        "campaigns": normalized_campaigns,
        "item_to_campaign": item_to_campaign,
        "campaign_to_item": campaign_to_item,
        "total": len(normalized_campaigns),
    }



# ===========================

# /ads — минимальная версия

# ===========================



@app.get("/ads")
def get_ads(
    date_from: str = Query(..., description="Начальная дата YYYY-MM-DD"),
    date_to: str = Query(..., description="Конечная дата YYYY-MM-DD"),
    campaign_ids: Optional[str] = Query(None, description="ID кампаний через запятую"),
    ids: Optional[str] = Query(None, description="Alias для campaign_ids"),
    nm_ids: Optional[str] = Query(None, description="Список nmId через запятую"),
    placement: Optional[str] = Query(None, description="Тип размещения (зарезервировано)"),
):
    """
    Возвращает нормализованную статистику по рекламным кампаниям.

    Поведение:
    - если переданы campaign_ids или ids — считаем только по ним;
    - если campaign_ids/ids не переданы — автоматически берём все кампании из WB;
    - nm_ids (если переданы) ограничивают список кампаний по товарам.
    """
    # Пока параметр placement не используем, но сохраняем для совместимости
    del placement

    # Простейшая проверка формата дат
    if len(date_from) != 10 or len(date_to) != 10:
        raise HTTPException(status_code=400, detail="Неверный формат даты")

    # Фильтр по товарам (nm_ids)
    nm_id_filter: set[int] = set(_parse_id_list(nm_ids, "nm_ids")) if nm_ids else set()

    # Входной список кампаний: campaign_ids или ids
    campaign_ids_param = ids or campaign_ids
    campaign_ids_list: List[int] = []

    if campaign_ids_param:
        campaign_ids_list = _parse_id_list(campaign_ids_param, "campaign_ids")
    else:
        logger.warning("ADS: campaign_ids не переданы — включён автоматический режим сбора кампаний.")
        campaigns_list = _api_v2_client.get_campaigns()
        if not isinstance(campaigns_list, list):
            campaigns_list = []

        if nm_id_filter:
            filtered_campaigns: List[Dict[str, Any]] = []
            for camp in campaigns_list:
                if not isinstance(camp, dict):
                    continue
                nm_candidate = camp.get("nmId") or camp.get("nm_id") or camp.get("nm") or camp.get("item_id")
                try:
                    nm_value = int(nm_candidate)
                except (TypeError, ValueError):
                    continue
                if nm_value in nm_id_filter:
                    filtered_campaigns.append(camp)
            campaigns_list = filtered_campaigns

        campaign_ids_list = []
        for camp in campaigns_list:
            if not isinstance(camp, dict):
                continue
            campaign_id = camp.get("id") or camp.get("campaignId") or camp.get("advertId")
            try:
                campaign_ids_list.append(int(campaign_id))
            except (TypeError, ValueError):
                continue

    # Если после всех попыток список кампаний пуст — просто возвращаем пустую статистику,
    # чтобы full_analysis и остальные части пайплайна не падали по 400.
    if not campaign_ids_list:
        logger.info(
            "В /ads не найдено ни одной кампании под фильтры "
            "campaign_ids=%s, ids=%s, nm_ids=%s",
            campaign_ids,
            ids,
            nm_ids,
        )
        return []

    # Запрашиваем fullstats по собранному списку кампаний
    try:
        raw_data = _fetch_fullstats_data(campaign_ids_list, date_from, date_to)
    except requests.exceptions.HTTPError as exc:
        error_detail = f"WB API error: {getattr(exc.response, 'status_code', None)}"
        try:
            error_detail += f" - {exc.response.json()}"
        except Exception:
            if exc.response is not None:
                error_detail += f" - {exc.response.text}"
        status_code = getattr(exc.response, "status_code", 500) or 500
        raise HTTPException(status_code=status_code, detail=error_detail) from exc
    except Exception as exc:
        logger.exception("Ошибка при запросе fullstats: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    normalized = _normalize_ads_response(raw_data)

    # Дополнительный фильтр по nm_ids на уровне нормализованных строк
    if nm_id_filter:
        normalized = [
            row
            for row in normalized
            if row.get("nmId") is not None and row.get("nmId") in nm_id_filter
        ]

    return normalized



# =====================================

# Подключаем реальные данные WB в /ads

# =====================================

@app.get("/ads_real")

def ads_real(

    date_from: str = Query(...),

    date_to: str = Query(...),

    ids: str = Query(None, description="ID кампаний через запятую"),

    campaign_ids: str = Query(None, description="ID кампаний через запятую (альтернатива ids)"),

):

    """

    Минимальная реальная версия /ads:

    - ходит в WB /adv/v3/fullstats

    - возвращает сырые данные

    """

    # Используем ids или campaign_ids (если передан)
    campaign_ids_param = ids or campaign_ids

    # WB API требует параметр ids, поэтому если он не передан, возвращаем ошибку
    if not campaign_ids_param:
        raise HTTPException(
            status_code=400,
            detail="Параметр 'ids' или 'campaign_ids' обязателен. Укажите ID кампаний через запятую, например: ?ids=12345,67890"
        )

    # Парсим campaign_ids
    try:
        campaign_ids_list = [int(x.strip()) for x in campaign_ids_param.split(",") if x.strip()]
    except ValueError:
        raise HTTPException(status_code=400, detail="Неверный формат ids. Ожидается список чисел через запятую")

    # Используем WildberriesClient (как в рабочем коде)
    try:
        client = WildberriesClient(token=WB_TOKEN)
        
        # Логируем входные параметры (без токена)
        logger.info(f"/ads_real: запрос для campaign_ids={campaign_ids_list}, date_from={date_from}, date_to={date_to}")
        
        # Формируем параметры для WB API (как в эталоне v1)
        # Эталон: ids через запятую, beginDate, endDate
        ids_str = ",".join(str(i) for i in campaign_ids_list)
        logger.info(f"/ads_real: WB API params: ids={ids_str}, beginDate={date_from}, endDate={date_to}")
        
        data = _fetch_fullstats_data(campaign_ids_list, date_from, date_to)
        
        # Логируем структуру ответа (без чувствительных данных)
        if isinstance(data, list):
            logger.info(f"/ads_real: получен список из {len(data)} элементов")
            if data:
                first_campaign = data[0]
                if isinstance(first_campaign, dict):
                    has_stats = "stats" in first_campaign and isinstance(first_campaign.get("stats"), list)
                    has_days = "days" in first_campaign and isinstance(first_campaign.get("days"), list)
                    stats_len = len(first_campaign.get("stats", [])) if has_stats else 0
                    days_len = len(first_campaign.get("days", [])) if has_days else 0
                    logger.info(f"/ads_real: первая кампания: advertId={first_campaign.get('advertId')}, stats={has_stats}({stats_len}), days={has_days}({days_len})")
        elif isinstance(data, dict):
            logger.info(f"/ads_real: получен dict с ключами: {list(data.keys())[:5]}")
        
        normalized = _normalize_ads_response(data)
        return {"items": normalized, "wb_raw": data}

    except requests.exceptions.HTTPError as e:

        # Если ошибка от WB API, вернем детали ошибки

        error_detail = f"WB API error: {e.response.status_code}"

        try:

            error_body = e.response.json()

            error_detail += f" - {error_body}"

        except:

            error_detail += f" - {e.response.text}"

        raise HTTPException(status_code=e.response.status_code, detail=error_detail)



# ========================================

# /search-queries — реальные поисковые запросы WB

# ========================================

@app.get("/search-queries")
def search_queries(
    date_from: str = Query(..., description="Начальная дата в формате YYYY-MM-DD"),
    date_to: str = Query(..., description="Конечная дата в формате YYYY-MM-DD"),
    nm_ids: Optional[str] = Query(None, description="Список nmID через запятую"),
    limit: int = Query(500, description="Лимит записей"),
    offset: int = Query(0, description="Смещение для пагинации"),
):
    """
    Получение поисковых запросов из WB Analytics API.
    Использует POST запрос к /api/v2/search-report/report согласно официальной документации.
    """
    parsed_nm_ids = _parse_id_list(nm_ids, "nm_ids") if nm_ids else []
    try:
        data = _search_report_raw_client.fetch_search_report(
            nm_ids=parsed_nm_ids,
            date_from=date_from,
            date_to=date_to,
            limit=limit,
            offset=offset,
        )
    except (requests.RequestException, ValueError) as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    return {"wb_raw": data}


@app.get("/sales-funnel")
def sales_funnel(
    date_from: str = Query(..., description="Начальная дата в формате YYYY-MM-DD"),
    date_to: str = Query(..., description="Конечная дата в формате YYYY-MM-DD"),
    nm_ids: Optional[str] = Query(None, description="Список nmID через запятую"),
):
    """
    Обёртка над WB Seller Analytics v3 sales-funnel/products.
    Возвращает JSON WB как есть (формат analytics v3).
    """

    nm_list: List[int] = _parse_id_list(nm_ids, "nm_ids") if nm_ids else []

    try:
        data = _sales_funnel_raw_client.fetch_sales_funnel(
            nm_ids=nm_list,
            date_from=date_from,
            date_to=date_to,
        )
    except (requests.RequestException, ValueError) as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    return data


# =====================================
# RAW proxy endpoints
# =====================================


@app.post("/raw/ads")
def fetch_raw_ads(
    date_from: str = Query(..., description="Начальная дата YYYY-MM-DD"),
    date_to: str = Query(..., description="Конечная дата YYYY-MM-DD"),
    campaign_ids: str = Query(..., description="ID кампаний через запятую"),
    version: str = Query("v3", description="Версия WB эндпоинта fullstats"),
):
    campaign_ids_list = _parse_id_list(campaign_ids, "campaign_ids")
    data = _ads_raw_client.fetch_fullstats(
        campaign_ids=campaign_ids_list,
        date_from=date_from,
        date_to=date_to,
        version=version,
    )
    return {
        "status": "ok",
        "campaign_ids": campaign_ids_list,
        "payload_type": type(data).__name__,
    }


@app.post("/raw/sales-funnel")
def fetch_raw_sales_funnel(
    date_from: str = Query(..., description="Начальная дата YYYY-MM-DD"),
    date_to: str = Query(..., description="Конечная дата YYYY-MM-DD"),
    nm_ids: Optional[str] = Query(None, description="nmId через запятую"),
):
    nm_list = _parse_id_list(nm_ids, "nm_ids") if nm_ids else []
    data = _sales_funnel_raw_client.fetch_sales_funnel(
        nm_ids=nm_list,
        date_from=date_from,
        date_to=date_to,
    )
    return {
        "status": "ok",
        "nm_ids": nm_list,
        "payload_type": type(data).__name__,
    }


@app.post("/raw/search-report")
def fetch_raw_search_report(
    date_from: str = Query(..., description="Начальная дата YYYY-MM-DD"),
    date_to: str = Query(..., description="Конечная дата YYYY-MM-DD"),
    nm_ids: Optional[str] = Query(None, description="nmId через запятую"),
    limit: int = Query(500),
    offset: int = Query(0),
):
    nm_list = _parse_id_list(nm_ids, "nm_ids") if nm_ids else []
    data = _search_report_raw_client.fetch_search_report(
        nm_ids=nm_list,
        date_from=date_from,
        date_to=date_to,
        limit=limit,
        offset=offset,
    )
    return {
        "status": "ok",
        "nm_ids": nm_list,
        "payload_type": type(data).__name__,
    }


@app.post("/raw/feedbacks")
def fetch_raw_feedbacks(
    nm_id: int = Query(..., description="Артикул товара"),
    is_answered: bool = Query(False),
    take: int = Query(100, ge=1, le=500),
    skip: int = Query(0, ge=0),
    order: str = Query("dateDesc"),
):
    data = _feedbacks_raw_client.fetch_feedbacks(
        nm_id=nm_id,
        is_answered=is_answered,
        take=take,
        skip=skip,
        order=order,
    )
    return {
        "status": "ok",
        "nm_id": nm_id,
        "payload_type": type(data).__name__,
    }


@app.post("/commands/set-bid")
def api_set_bid(request: SetBidRequest) -> Dict[str, Any]:
    return set_bid_command(request.campaignId, request.bid)


@app.post("/commands/enable-campaign")
def api_enable_campaign(request: CampaignToggleRequest) -> Dict[str, Any]:
    return enable_campaign_command(request.campaignId)


@app.post("/commands/disable-campaign")
def api_disable_campaign(request: CampaignToggleRequest) -> Dict[str, Any]:
    return disable_campaign_command(request.campaignId)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8002, reload=True)

