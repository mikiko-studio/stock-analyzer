"""
screener.py
3-layer filter engine for the Dividend Screener.

Design principle: PURE FUNCTION — no yfinance calls here.
Takes pre-fetched raw data dict and ScreenerConfig, returns result dict.
This allows threshold changes without re-fetching data.

Layers:
  Layer 1 (財務の鉄壁): equity_ratio >= 40%, operating CF positive 3 years
  Layer 2 (配当の誠実さ): yield in range, payout in range, no dividend cuts
  Layer 3 (稼ぐ力): operating_margin >= 10%, ROE >= 8%
"""

import math
from dataclasses import dataclass, field
from typing import Optional

import pandas as pd

from utils.constants import FINANCIAL_SECTORS


@dataclass
class ScreenerConfig:
    equity_ratio_min: float = 0.40
    dividend_yield_min: float = 0.0375
    dividend_yield_max: float = 0.05
    payout_ratio_min: float = 0.30
    payout_ratio_max: float = 0.70
    operating_margin_min: float = 0.10
    roe_min: float = 0.08
    dividend_history_years: int = 10


def _is_nan(v):
    if v is None:
        return True
    try:
        return math.isnan(v)
    except (TypeError, ValueError):
        return False


def screen_from_raw(symbol: str, raw: dict, cfg: ScreenerConfig) -> dict:
    """
    Run 3-layer screening on pre-fetched data.
    Returns dict with all metrics and status/stage/reason.

    status: "passed" | "failed" | "error"
    stage: which filter eliminated it
    reason: human-readable explanation
    """
    base = {
        "ticker": symbol,
        "name": raw.get("name", symbol),
        "sector": raw.get("sector", "不明"),
        "price": raw.get("price"),
        "currency": raw.get("currency", "JPY"),
        "equityRatio": raw.get("equityRatio"),
        "dividendYield": raw.get("dividendYield"),
        "dividendRate": raw.get("dividendRate"),
        "payoutRatio": raw.get("payoutRatio"),
        "operatingMargin": raw.get("operatingMargin"),
        "roe": raw.get("roe"),
        "dividend_history": raw.get("dividend_history", pd.Series(dtype=float)),
        "operatingCashflow_3y": raw.get("operatingCashflow_3y", []),
        "status": "passed",
        "stage": None,
        "reason": None,
    }

    sector = base["sector"]
    is_financial = any(fs in sector for fs in FINANCIAL_SECTORS)

    # ── Layer 1: 財務の鉄壁 ────────────────────────────────────────────
    # 1a. Equity ratio (skip for financial sector)
    if not is_financial:
        eq_ratio = base["equityRatio"]
        if _is_nan(eq_ratio):
            base.update(status="failed", stage="自己資本比率", reason="自己資本比率データなし")
            return base
        if eq_ratio < cfg.equity_ratio_min:
            base.update(
                status="failed",
                stage="自己資本比率",
                reason=f"自己資本比率 {eq_ratio:.1%} < 最低基準 {cfg.equity_ratio_min:.0%}",
            )
            return base

    # 1b. Operating CF — must be positive for all available years (up to 3)
    ocf_3y = base["operatingCashflow_3y"]
    if len(ocf_3y) == 0:
        base.update(status="failed", stage="営業CF", reason="営業CFデータなし")
        return base
    if any(v <= 0 for v in ocf_3y if v is not None):
        base.update(
            status="failed",
            stage="営業CF",
            reason=f"直近{len(ocf_3y)}年に営業CFがマイナスの年あり",
        )
        return base

    # ── Layer 2: 配当の誠実さ ──────────────────────────────────────────
    # 2a. Dividend yield range
    dy = base["dividendYield"]
    if _is_nan(dy) or dy is None or dy == 0:
        base.update(status="failed", stage="配当利回り", reason="配当利回りデータなし / 無配")
        return base
    if dy < cfg.dividend_yield_min:
        base.update(
            status="failed",
            stage="配当利回り",
            reason=f"配当利回り {dy:.2%} < 最低基準 {cfg.dividend_yield_min:.2%}",
        )
        return base
    if dy > cfg.dividend_yield_max:
        base.update(
            status="failed",
            stage="配当利回り",
            reason=f"配当利回り {dy:.2%} > 上限 {cfg.dividend_yield_max:.2%} (高すぎ・罠配当の可能性)",
        )
        return base

    # 2b. Payout ratio range
    pr = base["payoutRatio"]
    if _is_nan(pr) or pr is None:
        # Allow through with warning but don't fail
        pass
    else:
        if pr < cfg.payout_ratio_min:
            base.update(
                status="failed",
                stage="配当性向",
                reason=f"配当性向 {pr:.1%} < 下限 {cfg.payout_ratio_min:.0%} (配当が小さすぎ)",
            )
            return base
        if pr > cfg.payout_ratio_max:
            base.update(
                status="failed",
                stage="配当性向",
                reason=f"配当性向 {pr:.1%} > 上限 {cfg.payout_ratio_max:.0%} (持続性に懸念)",
            )
            return base

    # 2c. No dividend cuts check
    div_hist = base["dividend_history"]
    if isinstance(div_hist, pd.Series) and len(div_hist) >= 3:
        recent = div_hist.sort_index(ascending=True).tail(cfg.dividend_history_years)
        vals = recent.values
        # Check for any year-over-year cut > 5%
        for i in range(1, len(vals)):
            if vals[i - 1] > 0 and (vals[i] < vals[i - 1] * 0.95):
                base.update(
                    status="failed",
                    stage="減配チェック",
                    reason=f"過去{cfg.dividend_history_years}年内に減配あり",
                )
                return base

    # ── Layer 3: 稼ぐ力 ───────────────────────────────────────────────
    # 3a. Operating margin
    om = base["operatingMargin"]
    if _is_nan(om) or om is None:
        base.update(status="failed", stage="営業利益率", reason="営業利益率データなし")
        return base
    if om < cfg.operating_margin_min:
        base.update(
            status="failed",
            stage="営業利益率",
            reason=f"営業利益率 {om:.1%} < 基準 {cfg.operating_margin_min:.0%}",
        )
        return base

    # 3b. ROE
    roe = base["roe"]
    if _is_nan(roe) or roe is None:
        base.update(status="failed", stage="ROE", reason="ROEデータなし")
        return base
    if roe < cfg.roe_min:
        base.update(
            status="failed",
            stage="ROE",
            reason=f"ROE {roe:.1%} < 基準 {cfg.roe_min:.0%}",
        )
        return base

    # All layers passed
    base.update(status="passed", stage="全通過", reason="全フィルター通過")
    return base
