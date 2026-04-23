"""
utils/data_fetcher.py
Unified yfinance data fetcher with Streamlit caching.

Key design:
- @st.cache_data(ttl=3600) for raw yfinance calls (1-hour cache)
- Returns a standardized dict with all fields needed by all 4 apps
- Handles both JP (.T suffix) and US tickers
- Graceful error handling: never crash, return None on failure
"""

import numpy as np
import pandas as pd
import streamlit as st
import yfinance as yf



def _safe_get(info, key, default=None):
    """Safely get a value from yfinance info dict."""
    val = info.get(key, default)
    if val is None:
        return default
    # Convert numpy types to Python native
    if isinstance(val, (np.integer,)):
        return int(val)
    if isinstance(val, (np.floating,)):
        return float(val)
    return val


def _normalize_yield(value) -> float | None:
    """Normalize dividendYield to decimal form (0.0–1.0).

    yfinance 1.x returns dividendYield as a percentage value (e.g. 4.18 for 4.18%).
    Older versions returned a decimal (0.0418).  Any value > 1.0 is assumed to be
    in percentage form and is divided by 100.
    """
    if value is None:
        return None
    try:
        v = float(value)
        return v / 100 if v > 1.0 else v
    except (TypeError, ValueError):
        return None


def _calc_rsi(close_series, period=14):
    """Calculate RSI for a given close price series."""
    try:
        delta = close_series.diff()
        gain = delta.clip(lower=0).rolling(window=period, min_periods=period).mean()
        loss = (-delta.clip(upper=0)).rolling(window=period, min_periods=period).mean()
        rs = gain / loss.replace(0, np.nan)
        rsi = 100 - (100 / (1 + rs))
        return float(rsi.iloc[-1]) if not rsi.empty else None
    except Exception:
        return None


def _calc_ma_deviation(close_series, window=25):
    """Calculate moving average and deviation percentage."""
    try:
        ma = close_series.rolling(window=window, min_periods=window).mean()
        ma_val = float(ma.iloc[-1])
        price = float(close_series.iloc[-1])
        deviation_pct = (price - ma_val) / ma_val * 100
        return ma_val, deviation_pct
    except Exception:
        return None, None


def _get_equity_ratio(ticker_obj):
    """Calculate equity ratio from balance sheet.
    Tries multiple field name variants across yfinance versions.
    """
    try:
        bs = ticker_obj.balance_sheet
        if bs is None or bs.empty:
            return None
        # Expanded key list for yfinance 0.1.x / 0.2.x / newer
        equity_keys = [
            "Stockholders Equity",
            "Total Stockholder Equity",
            "Common Stock Equity",
            "Total Equity Gross Minority Interest",
            "Stockholders' Equity",
            "Total Shareholders Equity",
        ]
        asset_keys = [
            "Total Assets",
            "Total Asset",
        ]
        equity = None
        for k in equity_keys:
            if k in bs.index:
                v = bs.loc[k].iloc[0]
                if v is not None and not np.isnan(float(v)):
                    equity = float(v)
                    break
        total_assets = None
        for k in asset_keys:
            if k in bs.index:
                v = bs.loc[k].iloc[0]
                if v is not None and not np.isnan(float(v)):
                    total_assets = float(v)
                    break
        if equity is not None and total_assets and total_assets != 0:
            return equity / total_assets
        return None
    except Exception:
        return None


def _get_operating_cashflow_3y(ticker_obj):
    """Get last 3 years of operating cash flow.
    Returns (values_list, years_list).
    Falls back from .cashflow to .cash_flow for newer yfinance versions.
    """
    for cf_attr in ("cashflow", "cash_flow"):
        try:
            cf = getattr(ticker_obj, cf_attr, None)
            if cf is None or (hasattr(cf, "empty") and cf.empty):
                continue
            keys = [
                "Operating Cash Flow",
                "Total Cash From Operating Activities",
                "Cash From Operating Activities",
            ]
            for k in keys:
                if k in cf.index:
                    row = cf.loc[k].dropna()
                    pairs = [
                        (col, float(v))
                        for col, v in row.iloc[:3].items()
                        if not np.isnan(float(v))
                    ]
                    if pairs:
                        # cols are Timestamps; extract year string
                        years = [str(pd.Timestamp(col).year) for col, _ in pairs]
                        values = [v for _, v in pairs]
                        return values, years
        except Exception:
            continue
    return [], []


def _get_cash_3y(ticker_obj):
    """Get last 3 years of cash and equivalents."""
    try:
        bs = ticker_obj.balance_sheet
        if bs is None or bs.empty:
            return []
        keys = [
            "Cash And Cash Equivalents", "Cash Cash Equivalents And Short Term Investments",
            "Cash And Short Term Investments"
        ]
        for k in keys:
            if k in bs.index:
                vals = bs.loc[k].dropna()
                return [float(v) for v in vals.iloc[:3]]
        return []
    except Exception:
        return []


def _get_dividend_history(ticker_obj):
    """Get annual dividend history (year → total amount)."""
    try:
        divs = ticker_obj.dividends
        if divs is None or divs.empty:
            return pd.Series(dtype=float)
        # Group by year
        divs.index = pd.to_datetime(divs.index)
        annual = divs.groupby(divs.index.year).sum()
        return annual
    except Exception:
        return pd.Series(dtype=float)


@st.cache_data(ttl=1800, show_spinner=False)
def _cached_fetch(symbol: str) -> dict | None:
    """
    Fetch all data for a symbol from yfinance.
    Cached for 30 minutes. Returns standardized dict or None on failure.
    """
    try:
        ticker = yf.Ticker(symbol)
        info = ticker.info or {}

        # Determine market
        market = "JP" if symbol.endswith(".T") else "US"
        currency = _safe_get(info, "currency", "JPY" if market == "JP" else "USD")

        # Price data
        hist_1y = ticker.history(period="1y", interval="1d")
        hist_5y = ticker.history(period="5y", interval="1mo")

        # Current price
        price = _safe_get(info, "currentPrice") or _safe_get(info, "regularMarketPrice")
        if price is None and not hist_1y.empty:
            price = float(hist_1y["Close"].iloc[-1])

        # Technical indicators
        rsi14 = None
        ma25 = None
        ma25_dev = None
        ma75 = None
        ma200 = None

        if not hist_1y.empty:
            close = hist_1y["Close"]
            rsi14 = _calc_rsi(close, 14)
            ma25, ma25_dev = _calc_ma_deviation(close, 25)
            if len(close) >= 75:
                ma75 = float(close.rolling(75).mean().iloc[-1])
            if len(close) >= 200:
                ma200 = float(close.rolling(200).mean().iloc[-1])

        # FCF per share
        fcf = _safe_get(info, "freeCashflow")
        shares = _safe_get(info, "sharesOutstanding")
        fcf_per_share = None
        if fcf is not None and shares and shares != 0:
            fcf_per_share = fcf / shares

        # Equity ratio
        equity_ratio = _get_equity_ratio(ticker)

        # Operating cash flow
        ocf_3y, ocf_years = _get_operating_cashflow_3y(ticker)

        # Cash
        cash_3y = _get_cash_3y(ticker)

        # Dividend history
        div_history = _get_dividend_history(ticker)

        # News
        try:
            news = ticker.get_news() or []
            # Normalize news items
            normalized_news = []
            for item in news[:10]:
                normalized_news.append({
                    "title": item.get("title", item.get("content", {}).get("title", "")),
                    "link": item.get("link", item.get("content", {}).get("canonicalUrl", {}).get("url", "")),
                    "publisher": item.get("publisher", item.get("content", {}).get("provider", {}).get("displayName", "")),
                })
            news = normalized_news
        except Exception:
            news = []

        # 52-week high/low from info or history
        high_52w = _safe_get(info, "fiftyTwoWeekHigh")
        low_52w = _safe_get(info, "fiftyTwoWeekLow")
        if high_52w is None and not hist_1y.empty:
            high_52w = float(hist_1y["High"].max())
        if low_52w is None and not hist_1y.empty:
            low_52w = float(hist_1y["Low"].min())

        return {
            # Basic
            "symbol": symbol,
            "name": _safe_get(info, "shortName") or _safe_get(info, "longName") or symbol,
            "sector": _safe_get(info, "sector") or _safe_get(info, "industryDisp") or "不明",
            "market": market,
            "currency": currency,
            # Price
            "price": price,
            "price_history_1y": hist_1y,
            "price_history_5y": hist_5y,
            "fifty_two_week_high": high_52w,
            "fifty_two_week_low": low_52w,
            # Fundamentals
            "trailingPE": _safe_get(info, "trailingPE"),
            "forwardPE": _safe_get(info, "forwardPE"),
            "trailingEps": _safe_get(info, "trailingEps"),
            "forwardEps": _safe_get(info, "forwardEps"),
            "bookValue": _safe_get(info, "bookValue"),
            "priceToBook": _safe_get(info, "priceToBook"),
            "freeCashflow": fcf,
            "sharesOutstanding": shares,
            "fcfPerShare": fcf_per_share,
            "revenueGrowth": _safe_get(info, "revenueGrowth"),
            "earningsGrowth": _safe_get(info, "earningsGrowth"),
            # Dividends
            # yfinance 1.x returns dividendYield as a percentage (e.g. 4.18 for 4.18%).
            # Normalize to decimal (0.0418) so screener thresholds are consistent.
            "dividendYield": _normalize_yield(_safe_get(info, "dividendYield")),
            "dividendRate": _safe_get(info, "dividendRate"),
            "payoutRatio": _safe_get(info, "payoutRatio"),
            "dividend_history": div_history,
            # Financial health
            "equityRatio": equity_ratio,
            "operatingMargin": _safe_get(info, "operatingMargins"),
            "roe": _safe_get(info, "returnOnEquity"),
            "operatingCashflow_3y": ocf_3y,
            "operatingCashflow_years": ocf_years,
            "cashAndEquivalents_3y": cash_3y,
            # Technical
            "rsi14": rsi14,
            "ma25": ma25,
            "ma25DeviationPct": ma25_dev,
            "ma75": ma75,
            "ma200": ma200,
            # News
            "news": news,
        }

    except Exception as e:
        return None


def fetch_with_cache_flag(symbol: str):
    """
    Wrapper that returns (data, is_cache_hit) tuple.
    Uses session_state to detect if data was already fetched this session.
    """
    cache_key = f"_fetched_{symbol}"
    is_cache_hit = cache_key in st.session_state
    data = _cached_fetch(symbol)
    if data is not None:
        st.session_state[cache_key] = True
    return data, is_cache_hit
