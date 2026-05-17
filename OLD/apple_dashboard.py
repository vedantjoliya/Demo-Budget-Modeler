"""
================================================================================
APPLE INC. — LIVE BUDGET & FINANCIAL MODELER
Semester Oct 2026 – Mar 2027  |  Italy & Sweden
Based on the Budgeting Case Study by Prof. Andrea Cilloni
================================================================================
"""

import io
from datetime import datetime

import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import (
    Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle, PageBreak
)

# ============================================================================
# 1. PAGE CONFIG & STYLING
# ============================================================================
st.set_page_config(
    page_title="Apple Financial Modeler",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown("""
<style>
    /* Professional Corporate Theme */
    .stApp { background: #f8fafc; color: #0f172a; }
    h1, h2, h3, h4, h5, h6 { font-family: -apple-system, "SF Pro Display", "Segoe UI", Roboto, sans-serif; color: #0f172a; letter-spacing: -0.01em; font-weight: 600; }
    section[data-testid="stSidebar"] { background: #ffffff; border-right: 1px solid #e2e8f0; }
    div[data-testid="stMetric"] {
        background: #ffffff; padding: 24px; border-radius: 8px;
        box-shadow: 0 1px 3px rgba(0,0,0,0.1); border: 1px solid #e2e8f0;
    }
    div[data-testid="stMetric"] label { color: #64748b !important; font-size: 0.8rem !important; font-weight: 600 !important; text-transform: uppercase; letter-spacing: 0.05em; }
    div[data-testid="stMetric"] div[data-testid="stMetricValue"] { color: #0f172a !important; font-size: 1.8rem !important; font-weight: 700 !important; }
    .stTabs [data-baseweb="tab"] { font-weight: 600; color: #475569; }
    .stTabs [aria-selected="true"] { color: #0f172a !important; border-bottom-color: #0f172a !important; }
    .stDownloadButton button, .stButton button {
        background: #0f172a; color: #ffffff; border: none; border-radius: 6px;
        padding: 8px 16px; font-weight: 500; transition: background 0.2s;
    }
    .stDownloadButton button:hover, .stButton button:hover { background: #334155; color: #ffffff; }
    .css-18e3th9 { padding-top: 1.5rem; padding-bottom: 1.5rem; }
    .block-container { padding-top: 2rem; }
</style>
""", unsafe_allow_html=True)

# ============================================================================
# 2. CASE STUDY DATA
# ============================================================================
PRODUCTS  = ["iPhone", "iPad Pro", "MacBook Pro", "Apple Watch", "AirPods Pro"]
COUNTRIES = ["Italy", "Sweden"]
MONTHS    = ["Oct 2026", "Nov 2026", "Dec 2026", "Jan 2027", "Feb 2027", "Mar 2027"]

SALES_FORECAST = {
    "Italy": {
        "Oct 2026": [42000, 8000, 5400, 15000, 22000],
        "Nov 2026": [48000, 9200, 6000, 17000, 25000],
        "Dec 2026": [60000, 10500, 7200, 20000, 30000],
        "Jan 2027": [25000, 5000, 3000, 9000, 12000],
        "Feb 2027": [28000, 5600, 3300, 10000, 14000],
        "Mar 2027": [35000, 6800, 4000, 12000, 18000],
    },
    "Sweden": {
        "Oct 2026": [46000, 8800, 5940, 16500, 24200],
        "Nov 2026": [52000, 10160, 6600, 18700, 27500],
        "Dec 2026": [65000, 11700, 7920, 22000, 33000],
        "Jan 2027": [27000, 5500, 3300, 10000, 13200],
        "Feb 2027": [30000, 6160, 3630, 11000, 15400],
        "Mar 2027": [38000, 7480, 4400, 13200, 19800],
    },
}

PRICES = {
    "Italy":  {"iPhone": 1099, "iPad Pro": 1119, "MacBook Pro": 1849, "Apple Watch": 459, "AirPods Pro": 249},
    "Sweden": {"iPhone": 1189, "iPad Pro": 1231, "MacBook Pro": 2034, "Apple Watch": 505, "AirPods Pro": 274},
}

INVENTORY_POLICY = {"iPhone": 0.20, "iPad Pro": 0.15, "MacBook Pro": 0.15, "Apple Watch": 0.18, "AirPods Pro": 0.25}

OPENING_INVENTORY = {
    "Italy":  {"iPhone": 8400, "iPad Pro": 1200, "MacBook Pro": 810, "Apple Watch": 2700, "AirPods Pro": 5500},
    "Sweden": {"iPhone": 9200, "iPad Pro": 1320, "MacBook Pro": 891, "Apple Watch": 2970, "AirPods Pro": 6050},
}

BOM = {
    "iPhone": [("PCB", 1, 12.50), ("Battery (Wh)", 10, 1.20), ("Display", 1, 75.00), ("Packaging", 1, 2.50)],
    "iPad Pro": [("PCB", 1, 13.50), ("Battery (Wh)", 20, 1.15), ("Display", 1, 150.00), ("Packaging", 1, 3.00)],
    "MacBook Pro": [("PCB", 1, 18.00), ("Battery (Wh)", 60, 1.10), ("Aluminum chassis", 1, 120.00), ("Packaging", 1, 4.00)],
    "Apple Watch": [("Battery (Wh)", 3, 1.30), ("Sensor module", 1, 22.00), ("Packaging", 1, 1.50)],
    "AirPods Pro": [("PCB", 0.5, 6.00), ("Battery (Wh)", 0.8, 1.30), ("Speaker unit", 2, 8.50), ("Packaging", 1, 1.00)],
}

LABOR_RATE_PER_HOUR = 28.00
LABOR_MINUTES = {"iPhone": 18, "iPad Pro": 25, "MacBook Pro": 45, "Apple Watch": 12, "AirPods Pro": 8}

PRODUCT_COLORS = {
    "iPhone":      "#1e293b",
    "iPad Pro":    "#3b82f6",
    "MacBook Pro": "#64748b",
    "Apple Watch": "#94a3b8",
    "AirPods Pro": "#cbd5e1",
}

# ============================================================================
# 3. CALCULATION ENGINE
# ============================================================================
def material_cost_per_unit(p):
    return sum(q * pr for _, q, pr in BOM[p])

def labor_cost_per_unit(p):
    return (LABOR_MINUTES[p] / 60.0) * LABOR_RATE_PER_HOUR

def adjusted_units(country, month, product, vol_mult):
    idx = PRODUCTS.index(product)
    return int(round(SALES_FORECAST[country][month][idx] * vol_mult[product]))

def adjusted_price(country, product, price_mult):
    return PRICES[country][product] * price_mult[product]

def build_sales_df(filters, scen):
    rows = []
    for c in filters["countries"]:
        for m in filters["months"]:
            for p in filters["products"]:
                u = adjusted_units(c, m, p, scen["vol"])
                pr = adjusted_price(c, p, scen["price"])
                rows.append([c, m, p, u, pr, u * pr])
    return pd.DataFrame(rows, columns=["Country", "Month", "Product", "Units", "Price (€)", "Revenue (€)"])

def build_production_df(filters, scen):
    rows = []
    for c in filters["countries"]:
        for i, m in enumerate(filters["months"]):
            for p in filters["products"]:
                sales = adjusted_units(c, m, p, scen["vol"])
                if i == 0:
                    opening = OPENING_INVENTORY[c][p]
                else:
                    opening = int(round(sales * INVENTORY_POLICY[p]))
                if i == len(filters["months"]) - 1:
                    next_sales = sales
                else:
                    next_sales = adjusted_units(c, filters["months"][i + 1], p, scen["vol"])
                ending = int(round(next_sales * INVENTORY_POLICY[p]))
                production = max(0, sales + ending - opening)
                rows.append([c, m, p, sales, opening, ending, production])
    return pd.DataFrame(rows, columns=["Country", "Month", "Product", "Sales", "Opening Inv.", "Ending Inv.", "Production"])

def build_materials_df(prod_df, scen):
    rows = []
    for p in PRODUCTS:
        sub = prod_df[prod_df["Product"] == p]
        if sub.empty:
            continue
        total_prod = sub["Production"].sum()
        for comp, qty, unit_price in BOM[p]:
            up = unit_price * scen["mat"]
            tot_qty = total_prod * qty
            rows.append([p, comp, qty, up, tot_qty, tot_qty * up])
    return pd.DataFrame(rows, columns=["Product", "Component", "Qty/unit", "Unit price (€)", "Total qty", "Total cost (€)"])

def build_labor_df(prod_df, scen):
    rows = []
    for p in PRODUCTS:
        sub = prod_df[prod_df["Product"] == p]
        if sub.empty:
            continue
        units = int(sub["Production"].sum())
        cost = units * labor_cost_per_unit(p) * scen["labor"]
        rows.append([p, LABOR_MINUTES[p], units, cost])
    return pd.DataFrame(rows, columns=["Product", "Min/unit", "Units produced", "Labor cost (€)"])

def compute_pnl(sales_df, prod_df, scen, filters):
    revenue = sales_df["Revenue (€)"].sum()
    materials = sum(prod_df[prod_df["Product"] == p]["Production"].sum() * material_cost_per_unit(p) * scen["mat"] for p in PRODUCTS)
    labor = sum(prod_df[prod_df["Product"] == p]["Production"].sum() * labor_cost_per_unit(p) * scen["labor"] for p in PRODUCTS)
    cogs = materials + labor
    gross = revenue - cogs
    opex = scen["opex"] * len(filters["countries"])
    op_inc = gross - opex
    return {
        "revenue": revenue, "materials": materials, "labor": labor, "cogs": cogs,
        "gross": gross, "gross_margin": gross / revenue if revenue else 0,
        "opex": opex, "op_inc": op_inc, "op_margin": op_inc / revenue if revenue else 0,
        "units_sold": int(sales_df["Units"].sum()), "units_prod": int(prod_df["Production"].sum()),
    }

def fmt_eur(v): return f"€{v:,.0f}"
def fmt_num(v): return f"{v:,.0f}"
def fmt_pct(v): return f"{v*100:.1f}%"

# ============================================================================
# 4. EXPORT HELPERS
# ============================================================================
def to_excel(sales_df, prod_df, mats_df, labor_df, pnl):
    out = io.BytesIO()
    with pd.ExcelWriter(out, engine="openpyxl") as writer:
        summary = pd.DataFrame({
            "KPI": ["Revenue", "Materials", "Labor", "COGS", "Gross profit", "Gross margin",
                    "OpEx", "Operating income", "Operating margin", "Units sold", "Units produced"],
            "Value": [pnl["revenue"], pnl["materials"], pnl["labor"], pnl["cogs"],
                      pnl["gross"], pnl["gross_margin"], pnl["opex"], pnl["op_inc"],
                      pnl["op_margin"], pnl["units_sold"], pnl["units_prod"]],
        })
        summary.to_excel(writer, sheet_name="Summary", index=False)
        sales_df.to_excel(writer, sheet_name="Sales Budget", index=False)
        prod_df.to_excel(writer, sheet_name="Production Budget", index=False)
        mats_df.to_excel(writer, sheet_name="Materials Budget", index=False)
        labor_df.to_excel(writer, sheet_name="Labor Budget", index=False)
    return out.getvalue()

def to_pdf(sales_df, prod_df, mats_df, labor_df, pnl):
    out = io.BytesIO()
    doc = SimpleDocTemplate(out, pagesize=A4, leftMargin=1.5*cm, rightMargin=1.5*cm, topMargin=1.5*cm, bottomMargin=1.5*cm)
    styles = getSampleStyleSheet()
    story = []

    story.append(Paragraph("<b>Apple Inc. — Semester Budget Report</b>", styles["Title"]))
    story.append(Paragraph(f"Period: Oct 2026 – Mar 2027  |  Generated: {datetime.now():%Y-%m-%d %H:%M}", styles["Normal"]))
    story.append(Spacer(1, 12))

    kpi_data = [["KPI", "Value"],
                ["Revenue", fmt_eur(pnl["revenue"])],
                ["Materials", fmt_eur(pnl["materials"])],
                ["Labor", fmt_eur(pnl["labor"])],
                ["COGS", fmt_eur(pnl["cogs"])],
                ["Gross profit", fmt_eur(pnl["gross"])],
                ["Gross margin", fmt_pct(pnl["gross_margin"])],
                ["OpEx", fmt_eur(pnl["opex"])],
                ["Operating income", fmt_eur(pnl["op_inc"])],
                ["Operating margin", fmt_pct(pnl["op_margin"])],
                ["Units sold", fmt_num(pnl["units_sold"])],
                ["Units produced", fmt_num(pnl["units_prod"])]]
    t = Table(kpi_data, colWidths=[7*cm, 7*cm])
    t.setStyle(TableStyle([
        ("BACKGROUND", (0,0), (-1,0), colors.HexColor("#0f172a")),
        ("TEXTCOLOR", (0,0), (-1,0), colors.white),
        ("FONTNAME", (0,0), (-1,0), "Helvetica-Bold"),
        ("GRID", (0,0), (-1,-1), 0.3, colors.grey),
        ("ROWBACKGROUNDS", (0,1), (-1,-1), [colors.white, colors.HexColor("#f8fafc")]),
    ]))
    story.append(t); story.append(Spacer(1, 12))

    def add_table(title, df, fmt_cols=None):
        story.append(PageBreak())
        story.append(Paragraph(f"<b>{title}</b>", styles["Heading2"]))
        df = df.copy()
        if fmt_cols:
            for col, f in fmt_cols.items():
                if col in df.columns: df[col] = df[col].apply(f)
        data = [list(df.columns)] + df.values.tolist()
        tbl = Table(data, repeatRows=1)
        tbl.setStyle(TableStyle([
            ("BACKGROUND", (0,0), (-1,0), colors.HexColor("#334155")),
            ("TEXTCOLOR", (0,0), (-1,0), colors.white),
            ("FONTNAME", (0,0), (-1,0), "Helvetica-Bold"),
            ("FONTSIZE", (0,0), (-1,-1), 7),
            ("GRID", (0,0), (-1,-1), 0.2, colors.grey),
            ("ROWBACKGROUNDS", (0,1), (-1,-1), [colors.white, colors.HexColor("#f8fafc")]),
        ]))
        story.append(tbl)

    add_table("Sales Budget", sales_df, {"Price (€)": fmt_eur, "Revenue (€)": fmt_eur, "Units": fmt_num})
    add_table("Production Budget", prod_df, {c: fmt_num for c in ["Sales","Opening Inv.","Ending Inv.","Production"]})
    add_table("Materials Budget", mats_df, {"Unit price (€)": fmt_eur, "Total cost (€)": fmt_eur, "Total qty": fmt_num})
    add_table("Labor Budget", labor_df, {"Labor cost (€)": fmt_eur, "Units produced": fmt_num})

    doc.build(story)
    return out.getvalue()

# ============================================================================
# 5. SIDEBAR — FILTERS & SCENARIO CONTROLS
# ============================================================================
st.sidebar.markdown("### Budget Modeler")
st.sidebar.caption("Semester Oct 2026 – Mar 2027")
st.sidebar.divider()

st.sidebar.markdown("#### Parameters")
sel_countries = st.sidebar.multiselect("Country", COUNTRIES, default=COUNTRIES)
sel_products  = st.sidebar.multiselect("Products", PRODUCTS, default=PRODUCTS)
sel_months    = st.sidebar.multiselect("Months", MONTHS, default=MONTHS)

if not sel_countries or not sel_products or not sel_months:
    st.warning("Please select at least one country, product, and month.")
    st.stop()

st.sidebar.divider()
st.sidebar.markdown("#### Scenario Planning")

with st.sidebar.expander("Pricing Multipliers", expanded=False):
    price_mult = {p: 1 + st.slider(f"{p} price", -30, 30, 0, 1, key=f"pr_{p}") / 100 for p in PRODUCTS}

with st.sidebar.expander("Volume Multipliers", expanded=False):
    vol_mult = {p: 1 + st.slider(f"{p} volume", -50, 50, 0, 1, key=f"vol_{p}") / 100 for p in PRODUCTS}

with st.sidebar.expander("Cost Drivers", expanded=False):
    mat_mult = 1 + st.slider("Material cost", -30, 50, 0, 1) / 100
    lab_mult = 1 + st.slider("Labor cost", -30, 50, 0, 1) / 100
    opex     = st.number_input("OpEx per country (€)", 0, 500_000_000, 25_000_000, step=1_000_000)

filters = {"countries": sel_countries, "products": sel_products, "months": sel_months}
scen    = {"price": price_mult, "vol": vol_mult, "mat": mat_mult, "labor": lab_mult, "opex": opex}

# ============================================================================
# 6. COMPUTE
# ============================================================================
sales_df = build_sales_df(filters, scen)
prod_df  = build_production_df(filters, scen)
mats_df  = build_materials_df(prod_df, scen)
labor_df = build_labor_df(prod_df, scen)
pnl      = compute_pnl(sales_df, prod_df, scen, filters)

# ============================================================================
# 7. HEADER + EXPORT BUTTONS
# ============================================================================
hcol1, hcol2, hcol3 = st.columns([6, 1.2, 1.2])
with hcol1:
    st.markdown("""
    <div style='padding-bottom: 1rem;'>
        <h1 style='margin:0; font-size:2rem;'>Apple Financial & Predictive Modeler</h1>
        <p style='margin: 4px 0 0; color:#64748b; font-size:1rem;'>Executive Dashboard · Sales, Production & Revenue Forecasting</p>
    </div>
    """, unsafe_allow_html=True)
with hcol2:
    st.download_button("Export Excel", to_excel(sales_df, prod_df, mats_df, labor_df, pnl),
                       file_name=f"apple-budget-{datetime.now():%Y%m%d}.xlsx",
                       mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                       use_container_width=True)
with hcol3:
    st.download_button("Export PDF", to_pdf(sales_df, prod_df, mats_df, labor_df, pnl),
                       file_name=f"apple-budget-{datetime.now():%Y%m%d}.pdf",
                       mime="application/pdf", use_container_width=True)

st.divider()

# ============================================================================
# 8. KPI TILES
# ============================================================================
k1, k2, k3, k4 = st.columns(4)
k1.metric("Revenue", fmt_eur(pnl["revenue"]), f"{fmt_num(pnl['units_sold'])} Units")
k2.metric("Gross Profit", fmt_eur(pnl["gross"]), fmt_pct(pnl["gross_margin"]))
k3.metric("Production Costs", fmt_eur(pnl["cogs"]), f"{fmt_num(pnl['units_prod'])} Units")
k4.metric("Operating Income", fmt_eur(pnl["op_inc"]), fmt_pct(pnl["op_margin"]))

st.write("")

# ============================================================================
# 9. CHARTS & PREDICTION MODULE
# ============================================================================
st.markdown("### Performance Analytics")
tabs = st.tabs(["Overview", "Sales Details", "Production", "P&L", "Predictive Forecasting"])

with tabs[0]:
    c1, c2 = st.columns([2, 1])
    with c1:
        st.markdown("##### Revenue Trend")
        rev_month = sales_df.groupby(["Month", "Product"], as_index=False)["Revenue (€)"].sum()
        rev_month["Month"] = pd.Categorical(rev_month["Month"], categories=MONTHS, ordered=True)
        rev_month = rev_month.sort_values("Month")
        fig = px.bar(rev_month, x="Month", y="Revenue (€)", color="Product",
                     color_discrete_map=PRODUCT_COLORS, barmode="stack")
        fig.update_layout(height=340, margin=dict(t=10, b=10, l=10, r=10),
                          plot_bgcolor="#ffffff", paper_bgcolor="#ffffff",
                          legend=dict(orientation="h", y=-0.2),
                          font=dict(color="#0f172a"))
        st.plotly_chart(fig, use_container_width=True)

    with c2:
        st.markdown("##### Product Mix")
        mix = sales_df.groupby("Product", as_index=False)["Revenue (€)"].sum()
        fig = px.pie(mix, values="Revenue (€)", names="Product", hole=0.6,
                     color="Product", color_discrete_map=PRODUCT_COLORS)
        fig.update_layout(height=340, margin=dict(t=10, b=10, l=10, r=10), showlegend=True,
                          paper_bgcolor="#ffffff", plot_bgcolor="#ffffff",
                          legend=dict(orientation="h", y=-0.1),
                          font=dict(color="#0f172a"))
        st.plotly_chart(fig, use_container_width=True)

with tabs[1]:
    st.dataframe(sales_df.style.format({"Units": "{:,.0f}", "Price (€)": "€{:,.0f}", "Revenue (€)": "€{:,.0f}"}),
                 use_container_width=True, height=400)

with tabs[2]:
    st.dataframe(prod_df.style.format({c: "{:,.0f}" for c in ["Sales","Opening Inv.","Ending Inv.","Production"]}),
                 use_container_width=True, height=400)

with tabs[3]:
    pnl_rows = pd.DataFrame({
        "Item": ["Revenue", "− Materials", "− Labor", "= COGS", "= Gross profit",
                 "Gross margin", "− OpEx", "= Operating income", "Operating margin"],
        "Value": [fmt_eur(pnl["revenue"]), fmt_eur(pnl["materials"]), fmt_eur(pnl["labor"]),
                  fmt_eur(pnl["cogs"]), fmt_eur(pnl["gross"]), fmt_pct(pnl["gross_margin"]),
                  fmt_eur(pnl["opex"]), fmt_eur(pnl["op_inc"]), fmt_pct(pnl["op_margin"])],
    })
    st.dataframe(pnl_rows, use_container_width=True, hide_index=True, height=380)

# ============================================================================
# 10. PREDICTIVE FORECASTING
# ============================================================================
with tabs[4]:
    st.markdown("#### Revenue Extrapolation Model")
    st.markdown("Uses Ordinary Least Squares (OLS) linear regression to project future revenue growth based on the current timeframe's trend.")
    
    forecast_months = st.slider("Select Forecast Horizon (Months)", 1, 12, 6)
    
    # Aggregate historical data
    hist_trend = sales_df.groupby("Month", as_index=False)["Revenue (€)"].sum()
    hist_trend["Month"] = pd.Categorical(hist_trend["Month"], categories=MONTHS, ordered=True)
    hist_trend = hist_trend.sort_values("Month").reset_index(drop=True)
    
    # Model parameters
    X = np.arange(len(hist_trend))
    y = hist_trend["Revenue (€)"].values
    
    if len(X) > 1:
        # Fit Linear Model
        coeffs = np.polyfit(X, y, 1)
        poly_eq = np.poly1d(coeffs)
        
        # Extrapolate
        future_X = np.arange(len(X), len(X) + forecast_months)
        future_y = poly_eq(future_X)
        
        # Generate future month labels
        last_date = pd.to_datetime("2027-03-01")
        future_dates = [last_date + pd.DateOffset(months=i) for i in range(1, forecast_months + 1)]
        future_labels = [d.strftime("%b %Y") for d in future_dates]
        
        # Plot
        fig_pred = go.Figure()
        fig_pred.add_trace(go.Scatter(x=hist_trend["Month"], y=y, mode="lines+markers", 
                                      name="Historical Revenue", line=dict(color="#0f172a", width=3)))
        fig_pred.add_trace(go.Scatter(x=future_labels, y=future_y, mode="lines+markers", 
                                      name="Linear Forecast", line=dict(color="#3b82f6", width=3, dash="dash")))
        
        fig_pred.update_layout(height=400, margin=dict(t=20, b=20, l=20, r=20),
                               plot_bgcolor="#ffffff", paper_bgcolor="#ffffff",
                               legend=dict(orientation="h", y=-0.2), font=dict(color="#0f172a"))
        st.plotly_chart(fig_pred, use_container_width=True)
        
        # Forecasting Insights
        col1, col2, col3 = st.columns(3)
        col1.metric("Current Run Rate (Monthly)", fmt_eur(y[-1]))
        col2.metric("Projected Monthly (End of Horizon)", fmt_eur(future_y[-1]), f"{((future_y[-1]-y[-1])/y[-1])*100:.1f}%")
        col3.metric("Average Monthly Growth Trend", fmt_eur(coeffs[0]))

st.divider()
st.caption("Apple Inc. Budgeting Modeler · Professional Edition")
