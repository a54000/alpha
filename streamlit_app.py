#!/usr/bin/env python3
"""Minimal Streamlit Dashboard for NSE Research Platform - Phase 6A

A lightweight operational dashboard to verify the end-to-end pipeline
before investing in a full UI.

Pages:
1. Overview - Pipeline statistics with status indicators
2. Swing Recommendations - Top 20 swing recommendations
3. Positional Recommendations - Top 20 positional recommendations
4. Sector Strength - Latest sector rankings
5. Score Explorer - Searchable/sortable score explorer
"""

from __future__ import annotations

import os
from datetime import date, timedelta

import streamlit as st

from app.dashboard.queries import (
    DashboardQueries,
    PipelineStats,
    RecommendationRow,
    SectorRow,
    ScoreRow,
)


def get_status_color(is_fresh: bool, days_threshold: int = 2) -> str:
    """Return color based on data freshness."""
    if is_fresh:
        return "🟢"
    return "🔴"


def render_overview_page(queries: DashboardQueries) -> None:
    """Render Page 1: Overview with pipeline statistics."""
    st.title("📊 Pipeline Overview")
    st.markdown("---")
    
    stats = queries.get_pipeline_stats()
    
    # Calculate freshness
    today = date.today()
    is_data_fresh = (
        stats.latest_pipeline_date is not None
        and (today - stats.latest_pipeline_date).days <= 2
    )
    
    # Display status
    st.subheader("Pipeline Status")
    status_col1, status_col2 = st.columns(2)
    
    with status_col1:
        st.metric(
            "Latest Pipeline Run",
            str(stats.latest_pipeline_date) if stats.latest_pipeline_date else "No data",
            delta=None,
        )
    
    with status_col2:
        st.metric(
            "Data Freshness",
            get_status_color(is_data_fresh),
            delta=None,
        )
    
    st.markdown("---")
    
    # Display statistics
    st.subheader("Data Statistics")
    
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Total Symbols", stats.total_symbols)
    with col2:
        st.metric("Prices Daily Rows", f"{stats.total_prices:,}")
    with col3:
        st.metric("Features Daily Rows", f"{stats.total_features:,}")
    
    col4, col5, col6 = st.columns(3)
    with col4:
        st.metric("Sector Daily Rows", f"{stats.total_sectors:,}")
    with col5:
        st.metric("Daily Scores Rows", f"{stats.total_scores:,}")
    with col6:
        st.metric("Recommendations", f"{stats.total_recommendations:,}")
    
    # Status indicators
    st.markdown("---")
    st.subheader("Status Indicators")
    
    if stats.latest_pipeline_date is None:
        st.error("⚠️ No pipeline runs found. Run the historical pipeline first.")
    elif not is_data_fresh:
        st.warning(f"⚠️ Data is stale. Last run was {(today - stats.latest_pipeline_date).days} days ago.")
    else:
        st.success("✅ Pipeline data is fresh and up-to-date.")
    
    if stats.total_symbols == 0:
        st.error("⚠️ No symbols loaded. Check symbol ingestion.")
    if stats.total_prices == 0:
        st.error("⚠️ No price data. Check price ingestion.")
    if stats.total_features == 0:
        st.error("⚠️ No feature data. Check feature computation.")
    if stats.total_scores == 0:
        st.error("⚠️ No score data. Check scoring engine.")
    if stats.total_recommendations == 0:
        st.error("⚠️ No recommendations. Check recommendation generation.")


def render_swing_recommendations_page(queries: DashboardQueries) -> None:
    """Render Page 2: Swing Recommendations."""
    st.title("🚀 Swing Recommendations")
    st.markdown("---")
    
    recommendations = queries.get_swing_recommendations(limit=20)
    latest_date = queries.get_latest_recommendation_date("swing")
    
    if latest_date:
        st.subheader(f"Latest Date: {latest_date}")
    else:
        st.warning("No swing recommendations found.")
        return
    
    if not recommendations:
        st.warning("No swing recommendations available for the latest date.")
        return
    
    # Display as table
    st.subheader("Top 20 Swing Recommendations")
    
    data = []
    for rec in recommendations:
        data.append({
            "Rank": rec.rank,
            "Symbol": rec.symbol,
            "Swing Score": f"{rec.score:.1f}" if rec.score is not None else "N/A",
            "Sector": rec.sector or "N/A",
            "Model Version": rec.model_version or "N/A",
        })
    
    st.dataframe(
        data,
        column_config={
            "Rank": st.column_config.NumberColumn("Rank", format="%d"),
            "Symbol": st.column_config.TextColumn("Symbol"),
            "Swing Score": st.column_config.NumberColumn("Swing Score", format="%.1f"),
            "Sector": st.column_config.TextColumn("Sector"),
            "Model Version": st.column_config.TextColumn("Model Version"),
        },
        hide_index=True,
        use_container_width=True,
    )


def render_positional_recommendations_page(queries: DashboardQueries) -> None:
    """Render Page 3: Positional Recommendations."""
    st.title("📈 Positional Recommendations")
    st.markdown("---")
    
    recommendations = queries.get_positional_recommendations(limit=20)
    latest_date = queries.get_latest_recommendation_date("positional")
    
    if latest_date:
        st.subheader(f"Latest Date: {latest_date}")
    else:
        st.warning("No positional recommendations found.")
        return
    
    if not recommendations:
        st.warning("No positional recommendations available for the latest date.")
        return
    
    # Display as table
    st.subheader("Top 20 Positional Recommendations")
    
    data = []
    for rec in recommendations:
        data.append({
            "Rank": rec.rank,
            "Symbol": rec.symbol,
            "Position Score": f"{rec.score:.1f}" if rec.score is not None else "N/A",
            "Sector": rec.sector or "N/A",
            "Model Version": rec.model_version or "N/A",
        })
    
    st.dataframe(
        data,
        column_config={
            "Rank": st.column_config.NumberColumn("Rank", format="%d"),
            "Symbol": st.column_config.TextColumn("Symbol"),
            "Position Score": st.column_config.NumberColumn("Position Score", format="%.1f"),
            "Sector": st.column_config.TextColumn("Sector"),
            "Model Version": st.column_config.TextColumn("Model Version"),
        },
        hide_index=True,
        use_container_width=True,
    )


def render_sector_strength_page(queries: DashboardQueries) -> None:
    """Render Page 4: Sector Strength."""
    st.title("🏢 Sector Strength")
    st.markdown("---")
    
    sectors = queries.get_sector_strength()
    latest_date = queries.get_latest_sector_date()
    
    if latest_date:
        st.subheader(f"Latest Date: {latest_date}")
    else:
        st.warning("No sector data found.")
        return
    
    if not sectors:
        st.warning("No sector strength data available.")
        return
    
    # Display as table, sorted by strongest sector first
    st.subheader("Sector Rankings (Strongest First)")
    
    data = []
    for sector in sectors:
        data.append({
            "Sector": sector.sector,
            "Sector Score": f"{sector.sector_score:.2f}" if sector.sector_score is not None else "N/A",
            "Rank 3M": sector.rank_3m or "N/A",
            "Composite Rank": sector.composite_rank or "N/A",
            "Stock Count": sector.stock_count or 0,
        })
    
    st.dataframe(
        data,
        column_config={
            "Sector": st.column_config.TextColumn("Sector"),
            "Sector Score": st.column_config.NumberColumn("Sector Score", format="%.2f"),
            "Rank 3M": st.column_config.NumberColumn("Rank 3M", format="%d"),
            "Composite Rank": st.column_config.NumberColumn("Composite Rank", format="%d"),
            "Stock Count": st.column_config.NumberColumn("Stock Count", format="%d"),
        },
        hide_index=True,
        use_container_width=True,
    )


def render_score_explorer_page(queries: DashboardQueries) -> None:
    """Render Page 5: Score Explorer."""
    st.title("🔍 Score Explorer")
    st.markdown("---")
    
    latest_date = queries.get_latest_score_date()
    
    if latest_date:
        st.subheader(f"Latest Date: {latest_date}")
    else:
        st.warning("No score data found.")
        return
    
    # Filters
    col1, col2 = st.columns(2)
    
    with col1:
        symbol_filter = st.text_input("Search by Symbol", placeholder="e.g., RELIANCE, TCS")
    
    with col2:
        sort_by = st.selectbox(
            "Sort by",
            options=["swing_score", "position_score", "symbol"],
            format_func=lambda x: {
                "swing_score": "Swing Score",
                "position_score": "Position Score",
                "symbol": "Symbol",
            }[x],
        )
    
    # Get scores
    scores = queries.get_scores(
        symbol_filter=symbol_filter if symbol_filter else None,
        sort_by=sort_by,
        limit=100,
    )
    
    if not scores:
        st.warning("No score data available for the selected filters.")
        return
    
    # Display as table
    st.subheader(f"Scores ({len(scores)} results)")
    
    data = []
    for score in scores:
        data.append({
            "Symbol": score.symbol,
            "Swing Score": f"{score.swing_score:.1f}" if score.swing_score is not None else "N/A",
            "Position Score": f"{score.position_score:.1f}" if score.position_score is not None else "N/A",
            "Sector": score.sector or "N/A",
        })
    
    st.dataframe(
        data,
        column_config={
            "Symbol": st.column_config.TextColumn("Symbol"),
            "Swing Score": st.column_config.NumberColumn("Swing Score", format="%.1f"),
            "Position Score": st.column_config.NumberColumn("Position Score", format="%.1f"),
            "Sector": st.column_config.TextColumn("Sector"),
        },
        hide_index=True,
        use_container_width=True,
    )


def main() -> None:
    """Main entry point for the Streamlit dashboard."""
    st.set_page_config(
        page_title="NSE Research Platform - Validation Dashboard",
        page_icon="📊",
        layout="wide",
    )
    
    # Initialize queries
    try:
        queries = DashboardQueries()
    except Exception as e:
        st.error(f"Failed to connect to database: {e}")
        st.info("Please ensure DATABASE_URL is set in your environment.")
        return
    
    # Page navigation
    page = st.sidebar.selectbox(
        "Navigate",
        ["Overview", "Swing Recommendations", "Positional Recommendations", "Sector Strength", "Score Explorer"],
    )
    
    st.sidebar.markdown("---")
    st.sidebar.markdown("### NSE Research Platform")
    st.sidebar.markdown("Phase 6A: Validation Dashboard")
    
    # Render selected page
    if page == "Overview":
        render_overview_page(queries)
    elif page == "Swing Recommendations":
        render_swing_recommendations_page(queries)
    elif page == "Positional Recommendations":
        render_positional_recommendations_page(queries)
    elif page == "Sector Strength":
        render_sector_strength_page(queries)
    elif page == "Score Explorer":
        render_score_explorer_page(queries)


if __name__ == "__main__":
    main()
