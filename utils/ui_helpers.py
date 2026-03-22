"""
utils/ui_helpers.py
Shared formatting and UI helper functions for all pages.
"""

import pandas as pd
import streamlit as st


def format_pct(val, decimals=2):
    """Format a float as percentage string, or '—' if None/NaN."""
    if val is None:
        return "—"
    if isinstance(val, float) and pd.isna(val):
        return "—"
    try:
        return f"{val:.{decimals}%}"
    except (TypeError, ValueError):
        return "—"


def format_currency(val, currency="JPY"):
    """Format price with currency symbol."""
    if val is None:
        return "—"
    try:
        if pd.isna(val):
            return "—"
    except (TypeError, ValueError):
        pass
    sym = "¥" if currency == "JPY" else "$"
    try:
        if currency == "JPY":
            return f"{sym}{val:,.0f}"
        return f"{sym}{val:,.2f}"
    except (TypeError, ValueError):
        return "—"


def format_number(val, decimals=2):
    """Format a float as number string, or '—' if None/NaN."""
    if val is None:
        return "—"
    try:
        if pd.isna(val):
            return "—"
        return f"{val:.{decimals}f}"
    except (TypeError, ValueError):
        return "—"


def signal_badge(label, color):
    """Return an HTML badge for status indicators."""
    return (
        f'<span style="background:{color};color:#fff;padding:2px 8px;'
        f'border-radius:4px;font-size:0.8rem;font-weight:bold;">{label}</span>'
    )


def score_color(score, max_score=2):
    """Map a score (-2 to +2) to a color."""
    if score >= max_score:
        return "#22c55e"
    if score >= 1:
        return "#86efac"
    if score >= 0:
        return "#fbbf24"
    if score >= -1:
        return "#fb923c"
    return "#ef4444"


def render_metric_card(label, value, delta=None, help_text=None):
    """Render a styled metric card using st.metric."""
    st.metric(label=label, value=value, delta=delta, help=help_text)


def hero_header(title, subtitle, icon="📊"):
    """Render a hero header section."""
    st.markdown(f"# {icon} {title}")
    st.markdown(f"**{subtitle}**")
    st.divider()


def status_badge_html(status):
    """Return colored HTML badge for pass/fail/skip status."""
    color_map = {
        "passed": "#22c55e",
        "failed": "#ef4444",
        "skipped": "#94a3b8",
        "error": "#f97316",
    }
    label_map = {
        "passed": "✅ 合格",
        "failed": "❌ 不合格",
        "skipped": "⏭️ スキップ",
        "error": "⚠️ エラー",
    }
    color = color_map.get(status, "#94a3b8")
    label = label_map.get(status, status)
    return signal_badge(label, color)


def make_color_scale_df(df, col, reverse=False):
    """Apply background color gradient to a DataFrame column."""
    # Returns a styled DataFrame
    return df.style.background_gradient(subset=[col], cmap="RdYlGn" if not reverse else "RdYlGn_r")
