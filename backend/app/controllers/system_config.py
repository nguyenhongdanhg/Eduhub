
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from typing import List, Optional, Dict, Any
from datetime import datetime, timedelta
import re
from app.db import get_db_connection
from app.services.db_keyring import list_db_keys

router = APIRouter(prefix="/system", tags=["System Config"])

SUPPORTED_PROVIDERS: list[str] = ["OPENAI", "GEMINI", "DEEPSEEK"]

DEFAULT_TOKEN_PRICES_USD_PER_1M: dict[str, dict[str, float]] = {
    "OPENAI": {"prompt_usd_per_1m": 0.15, "completion_usd_per_1m": 0.60},
    "GEMINI": {"prompt_usd_per_1m": 0.075, "completion_usd_per_1m": 0.30},
    "DEEPSEEK": {"prompt_usd_per_1m": 0.28, "completion_usd_per_1m": 0.42},
}

DEFAULT_USD_TO_VND: float = 25000.0


def _normalize_provider(raw: Optional[str]) -> str:
    s = str(raw or "").strip().lower()
    if not s:
        return "UNKNOWN"
    if s in {"openai", "openai_compatible"}:
        return "OPENAI"
    if s == "gemini":
        return "GEMINI"
    if s == "deepseek":
        return "DEEPSEEK"
    return re.sub(r"[^a-z0-9_]+", "_", s).upper()


def _safe_float(v: Any) -> Optional[float]:
    try:
        if v is None:
            return None
        return float(str(v).strip())
    except Exception:
        return None


def _load_token_price_config() -> tuple[float, dict[str, dict[str, Any]]]:
    usd_to_vnd = DEFAULT_USD_TO_VND
    price_map: dict[str, dict[str, Any]] = {}
    for p in SUPPORTED_PROVIDERS:
        base = DEFAULT_TOKEN_PRICES_USD_PER_1M.get(p) or {}
        price_map[p] = {
            "provider": p,
            "prompt_usd_per_1m": float(base.get("prompt_usd_per_1m") or 0.0),
            "completion_usd_per_1m": float(base.get("completion_usd_per_1m") or 0.0),
            "source": {"prompt": "default", "completion": "default"},
        }

    keys: list[str] = ["AI_USD_TO_VND"]
    for p in SUPPORTED_PROVIDERS:
        keys.append(f"AI_PRICE_{p}_PROMPT_USD_PER_1M")
        keys.append(f"AI_PRICE_{p}_COMPLETION_USD_PER_1M")

    try:
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    f"SELECT conf_key, conf_value FROM system_configs WHERE conf_key IN ({','.join(['%s'] * len(keys))})",
                    tuple(keys),
                )
                rows = cur.fetchall() or []
        m = {str(r.get("conf_key") or ""): r.get("conf_value") for r in rows if isinstance(r, dict) and r.get("conf_key")}
        rate = _safe_float(m.get("AI_USD_TO_VND"))
        if rate is not None and rate > 0:
            usd_to_vnd = rate

        for p in SUPPORTED_PROVIDERS:
            pv = _safe_float(m.get(f"AI_PRICE_{p}_PROMPT_USD_PER_1M"))
            cv = _safe_float(m.get(f"AI_PRICE_{p}_COMPLETION_USD_PER_1M"))
            if pv is not None and pv >= 0:
                price_map[p]["prompt_usd_per_1m"] = pv
                price_map[p]["source"]["prompt"] = "db"
            if cv is not None and cv >= 0:
                price_map[p]["completion_usd_per_1m"] = cv
                price_map[p]["source"]["completion"] = "db"
    except Exception:
        pass

    return usd_to_vnd, price_map

class ApiKeyUpdate(BaseModel):
    provider: str
    api_key: str
    base_url: Optional[str] = None
    model: Optional[str] = None

class ConfigItem(BaseModel):
    key: str
    value: str


class TokenPriceItem(BaseModel):
    provider: str
    prompt_usd_per_1m: float
    completion_usd_per_1m: float


class TokenPriceUpdate(BaseModel):
    usd_to_vnd: Optional[float] = None
    prices: List[TokenPriceItem]

@router.get("/api-keys")
def get_api_keys():
    """Get list of configured providers and masked keys"""
    providers = ["OPENAI", "GEMINI", "DEEPSEEK"]
    results = []
    
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            for p in providers:
                keys = list_db_keys(f"AI_{p}_API_KEY")
                has_key = False
                masked_key = ""
                if keys:
                    has_key = True
                    val = keys[0]
                    if len(val) > 8:
                        masked_key = val[:4] + "..." + val[-4:]
                    else:
                        masked_key = "****"
                
                # Get Base URL
                cur.execute("SELECT conf_value FROM system_configs WHERE conf_key = %s", (f"AI_{p}_BASE_URL",))
                row_url = cur.fetchone()
                base_url = row_url.get("conf_value") if row_url else None
                
                # Get Default Model
                cur.execute("SELECT conf_value FROM system_configs WHERE conf_key = %s", (f"AI_{p}_MODEL",))
                row_model = cur.fetchone()
                default_model = row_model.get("conf_value") if row_model else None
                
                results.append({
                    "provider": p,
                    "has_key": has_key,
                    "masked_key": masked_key,
                    "base_url": base_url,
                    "default_model": default_model,
                    "active_key_source": ("db" if bool(keys) else "none"),
                    "key_count": len(keys)
                })
    return results


@router.get("/api-keys/active")
def get_active_api_key_sources() -> dict:
    openai_keys = list_db_keys("AI_OPENAI_API_KEY")
    gemini_keys = list_db_keys("AI_GEMINI_API_KEY")
    deepseek_keys = list_db_keys("AI_DEEPSEEK_API_KEY")
    openai_url_db = ""
    deepseek_url_db = ""
    gemini_url_db = ""
    openai_model_db = ""
    deepseek_model_db = ""
    gemini_model_db = ""
    try:
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT conf_key, conf_value FROM system_configs WHERE conf_key IN (%s,%s,%s,%s,%s,%s,%s,%s,%s)", (
                    "AI_OPENAI_API_KEY","AI_GEMINI_API_KEY","AI_DEEPSEEK_API_KEY",
                    "AI_OPENAI_BASE_URL","AI_GEMINI_BASE_URL","AI_DEEPSEEK_BASE_URL",
                    "AI_OPENAI_MODEL","AI_GEMINI_MODEL","AI_DEEPSEEK_MODEL",
                ))
                rows = cur.fetchall() or []
        m = {str(r.get("conf_key") or ""): str(r.get("conf_value") or "") for r in rows if isinstance(r, dict) and r.get("conf_key")}
        openai_url_db = m.get("AI_OPENAI_BASE_URL", "")
        gemini_url_db = m.get("AI_GEMINI_BASE_URL", "")
        deepseek_url_db = m.get("AI_DEEPSEEK_BASE_URL", "")
        openai_model_db = m.get("AI_OPENAI_MODEL", "")
        gemini_model_db = m.get("AI_GEMINI_MODEL", "")
        deepseek_model_db = m.get("AI_DEEPSEEK_MODEL", "")
    except Exception:
        pass

    return {
        "ok": True,
        "providers": {
            "OPENAI": {
                "active_key_source": ("db" if bool(openai_keys) else "none"),
                "active_base_url_source": ("db" if bool(openai_url_db) else "none"),
                "active_model_source": ("db" if bool(openai_model_db) else "none"),
                "key_count": len(openai_keys),
            },
            "GEMINI": {
                "active_key_source": ("db" if bool(gemini_keys) else "none"),
                "active_base_url_source": ("db" if bool(gemini_url_db) else "none"),
                "active_model_source": ("db" if bool(gemini_model_db) else "none"),
                "key_count": len(gemini_keys),
            },
            "DEEPSEEK": {
                "active_key_source": ("db" if bool(deepseek_keys) else "none"),
                "active_base_url_source": ("db" if bool(deepseek_url_db) else "none"),
                "active_model_source": ("db" if bool(deepseek_model_db) else "none"),
                "key_count": len(deepseek_keys),
            },
        },
    }

@router.post("/api-keys")
def update_api_key(payload: ApiKeyUpdate):
    """Update API Key and settings for a provider"""
    p = payload.provider.upper()
    print(f"Updating API Key for {p}: model={payload.model}, base_url={payload.base_url}")
    if p not in ["OPENAI", "GEMINI", "DEEPSEEK"]:
        raise HTTPException(status_code=400, detail="invalid_provider")
    
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            # Update API Key
            cur.execute("""
                INSERT INTO system_configs (conf_key, conf_value, description) 
                VALUES (%s, %s, %s)
                ON DUPLICATE KEY UPDATE conf_value = VALUES(conf_value)
            """, (f"AI_{p}_API_KEY", payload.api_key, f"API Key for {p}"))
            
            # Update Base URL
            if payload.base_url is not None:
                cur.execute("""
                    INSERT INTO system_configs (conf_key, conf_value, description) 
                    VALUES (%s, %s, %s)
                    ON DUPLICATE KEY UPDATE conf_value = VALUES(conf_value)
                """, (f"AI_{p}_BASE_URL", payload.base_url, f"Base URL for {p}"))
                
            # Update Model
            if payload.model is not None:
                # Normalize model list: split by comma, strip whitespace, join back
                raw_models = str(payload.model).strip()
                if "," in raw_models:
                    model_list = [m.strip() for m in raw_models.split(",") if m.strip()]
                    normalized_model = ",".join(model_list)
                else:
                    normalized_model = raw_models

                cur.execute("""
                    INSERT INTO system_configs (conf_key, conf_value, description) 
                    VALUES (%s, %s, %s)
                    ON DUPLICATE KEY UPDATE conf_value = VALUES(conf_value)
                """, (f"AI_{p}_MODEL", normalized_model, f"Default Model list for {p}"))
                
        conn.commit()
    return {"ok": True}

@router.delete("/api-keys/{provider}")
def delete_api_key(provider: str):
    p = str(provider or "").strip().upper()
    if p not in SUPPORTED_PROVIDERS:
        raise HTTPException(status_code=400, detail="invalid_provider")
    base = f"AI_{p}_API_KEY"
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "DELETE FROM system_configs WHERE conf_key=%s OR conf_key LIKE %s",
                (base, f"{base}_%"),
            )
        conn.commit()
    try:
        from app.services import db_keyring

        db_keyring._rings.pop(base, None)
    except Exception:
        pass
    return {"ok": True}
@router.get("/token-prices")
def get_token_prices():
    usd_to_vnd, price_map = _load_token_price_config()
    return {
        "ok": True,
        "usd_to_vnd": usd_to_vnd,
        "providers": [price_map[p] for p in SUPPORTED_PROVIDERS if p in price_map],
        "defaults": {
            "usd_to_vnd": DEFAULT_USD_TO_VND,
            "providers": [
                {"provider": p, **(DEFAULT_TOKEN_PRICES_USD_PER_1M.get(p) or {})} for p in SUPPORTED_PROVIDERS
            ],
        },
    }


@router.post("/token-prices")
def update_token_prices(payload: TokenPriceUpdate):
    usd_to_vnd = payload.usd_to_vnd
    if usd_to_vnd is not None and usd_to_vnd <= 0:
        raise HTTPException(status_code=400, detail="invalid_usd_to_vnd")

    items = payload.prices or []
    for it in items:
        p = str(it.provider or "").strip().upper()
        if p not in SUPPORTED_PROVIDERS:
            raise HTTPException(status_code=400, detail=f"invalid_provider:{p}")
        if it.prompt_usd_per_1m < 0 or it.completion_usd_per_1m < 0:
            raise HTTPException(status_code=400, detail="invalid_price")

    with get_db_connection() as conn:
        with conn.cursor() as cur:
            if usd_to_vnd is not None:
                cur.execute(
                    """
                    INSERT INTO system_configs (conf_key, conf_value, description)
                    VALUES (%s, %s, %s)
                    ON DUPLICATE KEY UPDATE conf_value = VALUES(conf_value)
                    """,
                    ("AI_USD_TO_VND", str(float(usd_to_vnd)), "FX rate USD->VND for AI cost estimation"),
                )

            for it in items:
                p = str(it.provider or "").strip().upper()
                cur.execute(
                    """
                    INSERT INTO system_configs (conf_key, conf_value, description)
                    VALUES (%s, %s, %s)
                    ON DUPLICATE KEY UPDATE conf_value = VALUES(conf_value)
                    """,
                    (f"AI_PRICE_{p}_PROMPT_USD_PER_1M", str(float(it.prompt_usd_per_1m)), f"AI {p} input price (USD/1M tokens)"),
                )
                cur.execute(
                    """
                    INSERT INTO system_configs (conf_key, conf_value, description)
                    VALUES (%s, %s, %s)
                    ON DUPLICATE KEY UPDATE conf_value = VALUES(conf_value)
                    """,
                    (f"AI_PRICE_{p}_COMPLETION_USD_PER_1M", str(float(it.completion_usd_per_1m)), f"AI {p} output price (USD/1M tokens)"),
                )
        conn.commit()
    return {"ok": True}


@router.get("/token-stats")
def get_token_stats(days: int = 30):
    """Get token usage statistics for charts"""
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            # 1. Stats by Date
            cur.execute("""
                SELECT DATE(created_at) as date, 
                       SUM(prompt_tokens) as prompt, 
                       SUM(completion_tokens) as completion,
                       SUM(prompt_tokens + completion_tokens) as total
                FROM token_usage_logs
                WHERE created_at >= DATE_SUB(NOW(), INTERVAL %s DAY)
                GROUP BY DATE(created_at)
                ORDER BY date ASC
            """, (days,))
            by_date = list(cur.fetchall())
            
            # 2. Stats by Content Type
            cur.execute("""
                SELECT COALESCE(content_type, 'unknown') as type, 
                       SUM(prompt_tokens + completion_tokens) as total
                FROM token_usage_logs
                WHERE created_at >= DATE_SUB(NOW(), INTERVAL %s DAY)
                GROUP BY content_type
            """, (days,))
            by_type = list(cur.fetchall())
            
            # 3. Stats by Provider
            cur.execute("""
                SELECT provider, 
                       SUM(prompt_tokens + completion_tokens) as total
                FROM token_usage_logs
                WHERE created_at >= DATE_SUB(NOW(), INTERVAL %s DAY)
                GROUP BY provider
            """, (days,))
            by_provider = list(cur.fetchall())

            # 3b. Stats by Provider (prompt/completion/calls)
            cur.execute("""
                SELECT provider,
                       COUNT(*) as requests,
                       SUM(prompt_tokens) as prompt,
                       SUM(completion_tokens) as completion,
                       SUM(prompt_tokens + completion_tokens) as total
                FROM token_usage_logs
                WHERE created_at >= DATE_SUB(NOW(), INTERVAL %s DAY)
                GROUP BY provider
                ORDER BY total DESC
            """, (days,))
            by_provider_detail = list(cur.fetchall())

            # 3c. Stats by Provider + Model
            cur.execute("""
                SELECT provider, model,
                       COUNT(*) as requests,
                       SUM(prompt_tokens) as prompt,
                       SUM(completion_tokens) as completion,
                       SUM(prompt_tokens + completion_tokens) as total
                FROM token_usage_logs
                WHERE created_at >= DATE_SUB(NOW(), INTERVAL %s DAY)
                GROUP BY provider, model
                ORDER BY total DESC
            """, (days,))
            by_provider_model = list(cur.fetchall())
            
            # 4. Summary
            cur.execute("""
                SELECT SUM(prompt_tokens) as total_prompt, 
                       SUM(completion_tokens) as total_completion,
                       COUNT(*) as total_requests
                FROM token_usage_logs
                WHERE created_at >= DATE_SUB(NOW(), INTERVAL %s DAY)
            """, (days,))
            summary = cur.fetchone()

    usd_to_vnd, price_map = _load_token_price_config()
    by_provider_cost: list[dict[str, Any]] = []
    agg: dict[str, dict[str, Any]] = {}
    for row in (by_provider_detail or []):
        if not isinstance(row, dict):
            continue
        label = _normalize_provider(row.get("provider"))
        d = agg.get(label)
        if not d:
            d = {"provider": label, "requests": 0, "prompt": 0, "completion": 0, "total": 0}
            agg[label] = d
        d["requests"] += int(row.get("requests") or 0)
        d["prompt"] += int(row.get("prompt") or 0)
        d["completion"] += int(row.get("completion") or 0)
        d["total"] += int(row.get("total") or 0)

    total_cost_usd = 0.0
    for label, row in agg.items():
        prices = price_map.get(label) or {"prompt_usd_per_1m": 0.0, "completion_usd_per_1m": 0.0}
        p_price = float(prices.get("prompt_usd_per_1m") or 0.0)
        c_price = float(prices.get("completion_usd_per_1m") or 0.0)
        cost_usd = (float(row["prompt"]) / 1_000_000.0) * p_price + (float(row["completion"]) / 1_000_000.0) * c_price
        total_cost_usd += cost_usd
        by_provider_cost.append(
            {
                **row,
                "prompt_usd_per_1m": p_price,
                "completion_usd_per_1m": c_price,
                "cost_usd": cost_usd,
                "cost_vnd": cost_usd * float(usd_to_vnd or DEFAULT_USD_TO_VND),
            }
        )

    by_provider_cost.sort(key=lambda x: float(x.get("cost_usd") or 0.0), reverse=True)

    return {
        "by_date": by_date,
        "by_type": by_type,
        "by_provider": by_provider,
        "by_provider_detail": by_provider_detail,
        "by_provider_model": by_provider_model,
        "summary": summary,
        "token_price_config": {
            "usd_to_vnd": usd_to_vnd,
            "providers": [price_map[p] for p in SUPPORTED_PROVIDERS if p in price_map],
        },
        "cost_by_provider": by_provider_cost,
        "cost_summary": {
            "total_cost_usd": total_cost_usd,
            "total_cost_vnd": total_cost_usd * float(usd_to_vnd or DEFAULT_USD_TO_VND),
            "usd_to_vnd": usd_to_vnd,
        },
    }


