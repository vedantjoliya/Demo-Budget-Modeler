import os
import io
import copy
import base64
from datetime import datetime
import numpy as np
import pandas as pd
from flask import Flask, render_template, jsonify, request, send_file
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import (
    Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle, PageBreak
)

app = Flask(__name__)

# ============================================================================
# 1. CASE STUDY DATA
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

BOM = {
    "iPhone": [("PCB", 1, 12.50), ("Battery (Wh)", 10, 1.20), ("Display", 1, 75.00), ("Packaging", 1, 2.50)],
    "iPad Pro": [("PCB", 1, 13.50), ("Battery (Wh)", 20, 1.15), ("Display", 1, 150.00), ("Packaging", 1, 3.00)],
    "MacBook Pro": [("PCB", 1, 18.00), ("Battery (Wh)", 60, 1.10), ("Aluminum chassis", 1, 120.00), ("Packaging", 1, 4.00)],
    "Apple Watch": [("Battery (Wh)", 3, 1.30), ("Sensor module", 1, 22.00), ("Packaging", 1, 1.50)],
    "AirPods Pro": [("PCB", 0.5, 6.00), ("Battery (Wh)", 0.8, 1.30), ("Speaker unit", 2, 8.50), ("Packaging", 1, 1.00)],
}

LABOR_RATE_PER_HOUR = 28.00
LABOR_MINUTES = {"iPhone": 18, "iPad Pro": 25, "MacBook Pro": 45, "Apple Watch": 12, "AirPods Pro": 8}
INVENTORY_POLICY = {"iPhone": 0.20, "iPad Pro": 0.15, "MacBook Pro": 0.15, "Apple Watch": 0.18, "AirPods Pro": 0.25}
OPENING_INVENTORY = {
    "Italy":  {"iPhone": 8400, "iPad Pro": 1200, "MacBook Pro": 810, "Apple Watch": 2700, "AirPods Pro": 5500},
    "Sweden": {"iPhone": 9200, "iPad Pro": 1320, "MacBook Pro": 891, "Apple Watch": 2970, "AirPods Pro": 6050},
}

def compute_forecast(y_values, steps=3):
    X = np.arange(len(y_values))
    y = np.array(y_values)
    if len(X) < 2: return [0]*steps
    coeffs = np.polyfit(X, y, 1)
    poly_eq = np.poly1d(coeffs)
    future_X = np.arange(len(y_values), len(y_values) + steps)
    return poly_eq(future_X).tolist()

def apply_overrides(overrides):
    sf = copy.deepcopy(SALES_FORECAST)
    pr = copy.deepcopy(PRICES)
    if overrides:
        sales_ov = overrides.get("sales", {})
        price_ov = overrides.get("prices", {})
        for c in COUNTRIES:
            for m in MONTHS:
                for idx, p in enumerate(PRODUCTS):
                    k = f"{c}_{m}_{p}"
                    if k in sales_ov:
                        sf[c][m][idx] = float(sales_ov[k])
        for c in COUNTRIES:
            for p in PRODUCTS:
                k = f"{c}_{p}"
                if k in price_ov:
                    pr[c][p] = float(price_ov[k])
    return sf, pr

def build_dfs(scen, overrides, filters=None):
    sf, pr_base = apply_overrides(overrides)

    # 1. Sales Data
    rows = []
    for c in COUNTRIES:
        for m in MONTHS:
            for p in PRODUCTS:
                idx = PRODUCTS.index(p)
                u = int(round(sf[c][m][idx] * scen["vol"].get(p, 1.0)))
                pr = pr_base[c][p] * scen["price"].get(p, 1.0)
                rows.append([c, m, p, u, pr, u * pr])
    sales_df = pd.DataFrame(rows, columns=["Country", "Month", "Product", "Units", "Price", "Revenue"])
    
    # 2. Production Data
    prod_rows = []
    for c in COUNTRIES:
        for i, m in enumerate(MONTHS):
            for p in PRODUCTS:
                idx = PRODUCTS.index(p)
                sales = int(round(sf[c][m][idx] * scen["vol"].get(p, 1.0)))
                opening = OPENING_INVENTORY[c][p] if i == 0 else int(round(sales * INVENTORY_POLICY[p]))
                next_sales = sales if i == len(MONTHS) - 1 else int(round(sf[c][MONTHS[i+1]][idx] * scen["vol"].get(p, 1.0)))
                ending = int(round(next_sales * INVENTORY_POLICY[p]))
                production = max(0, sales + ending - opening)
                prod_rows.append([c, m, p, sales, opening, ending, production])
    prod_df = pd.DataFrame(prod_rows, columns=["Country", "Month", "Product", "Sales", "Opening Inv", "Ending Inv", "Production"])

    # Apply filters to DataFrames before cost & P&L calculation
    active_countries = COUNTRIES
    active_products = PRODUCTS
    active_months = MONTHS
    if filters:
        def get_filter_list(key, default_choices):
            val = filters.get(key, "All")
            if isinstance(val, list):
                if "All" in val or not val:
                    return default_choices
                return val
            elif isinstance(val, str):
                if val == "All":
                    return default_choices
                return [val]
            return default_choices

        active_countries = get_filter_list("country", COUNTRIES)
        active_products = get_filter_list("product", PRODUCTS)
        active_months = get_filter_list("month", MONTHS)

        sales_df = sales_df[sales_df["Country"].isin(active_countries)]
        prod_df = prod_df[prod_df["Country"].isin(active_countries)]

        sales_df = sales_df[sales_df["Product"].isin(active_products)]
        prod_df = prod_df[prod_df["Product"].isin(active_products)]

        sales_df = sales_df[sales_df["Month"].isin(active_months)]
        prod_df = prod_df[prod_df["Month"].isin(active_months)]

    # 3. Materials
    mats_rows = []
    for p in PRODUCTS:
        sub = prod_df[prod_df["Product"] == p]
        if not sub.empty:
            total_prod = sub["Production"].sum()
            for comp, qty, unit_price in BOM[p]:
                up = unit_price * scen["mat"]
                tot_qty = total_prod * qty
                mats_rows.append([p, comp, qty, up, tot_qty, tot_qty * up])
    mats_df = pd.DataFrame(mats_rows, columns=["Product", "Component", "Qty/unit", "Unit price", "Total qty", "Total cost"])

    # 4. Labor
    labor_rows = []
    for p in PRODUCTS:
        sub = prod_df[prod_df["Product"] == p]
        if not sub.empty:
            units = int(sub["Production"].sum())
            cost = units * (LABOR_MINUTES[p] / 60.0) * LABOR_RATE_PER_HOUR * scen["labor"]
            labor_rows.append([p, LABOR_MINUTES[p], units, cost])
    labor_df = pd.DataFrame(labor_rows, columns=["Product", "Min/unit", "Units produced", "Labor cost"])

    # PnL
    revenue = sales_df["Revenue"].sum()
    materials = mats_df["Total cost"].sum() if not mats_df.empty else 0
    labor = labor_df["Labor cost"].sum() if not labor_df.empty else 0
    cogs = materials + labor
    gross = revenue - cogs
    opex = (scen["opex"] / len(MONTHS)) * len(active_months) * len(active_countries)
    op_inc = gross - opex
    
    pnl = {
        "revenue": float(revenue), "materials": float(materials), "labor": float(labor),
        "cogs": float(cogs), "gross": float(gross), "gross_margin": float((gross / revenue) * 100) if revenue else 0,
        "opex": float(opex), "op_inc": float(op_inc), "op_margin": float((op_inc / revenue) * 100) if revenue else 0,
        "units": int(sales_df["Units"].sum()), "units_prod": int(prod_df["Production"].sum())
    }

    # Charts data
    rev_by_month = sales_df.groupby("Month")["Revenue"].sum().reindex(MONTHS).fillna(0).tolist()
    mix = sales_df.groupby("Product")["Revenue"].sum().to_dict()
    country_perf = sales_df.groupby("Country")["Revenue"].sum().to_dict()
    prod_vol = prod_df.groupby("Month")["Production"].sum().reindex(MONTHS).fillna(0).tolist()
    sales_vol = prod_df.groupby("Month")["Sales"].sum().reindex(MONTHS).fillna(0).tolist()
    
    # Forecasts
    forecast = compute_forecast(rev_by_month, 3)
    product_forecasts = {}
    for p in PRODUCTS:
        p_hist = sales_df[sales_df["Product"]==p].groupby("Month")["Revenue"].sum().reindex(MONTHS).fillna(0).tolist()
        product_forecasts[p] = {"historical": p_hist, "forecast": compute_forecast(p_hist, 3)}

    country_forecasts = {}
    for c in COUNTRIES:
        c_hist = sales_df[sales_df["Country"]==c].groupby("Month")["Revenue"].sum().reindex(MONTHS).fillna(0).tolist()
        country_forecasts[c] = {"historical": c_hist, "forecast": compute_forecast(c_hist, 3)}

    monthly_rev = sales_df.groupby("Month")["Revenue"].sum().reindex(MONTHS).fillna(0)
    monthly_prod = prod_df.groupby("Month")["Production"].sum().reindex(MONTHS).fillna(0)
    total_prod_vol = monthly_prod.sum()
    if total_prod_vol > 0:
        monthly_cogs = cogs * (monthly_prod / total_prod_vol)
        monthly_margin_series = (monthly_rev - monthly_cogs) / monthly_rev.replace(0, np.nan) * 100
        monthly_margin = monthly_margin_series.fillna(0).replace([np.inf, -np.inf], 0).tolist()
    else:
        monthly_margin = [0] * len(MONTHS)
    margin_forecast = compute_forecast(monthly_margin, 3)

    blended_margin_per_unit = gross / pnl["units"] if pnl["units"] else 0
    break_even_units = int(opex / blended_margin_per_unit) if blended_margin_per_unit > 0 else 0
    next_qtr_rev = sum(forecast)
    pnl["break_even"] = break_even_units
    pnl["next_qtr_rev"] = float(next_qtr_rev)

    # Reporting Data
    reports_df = sales_df.groupby(["Month", "Product"]).agg({"Units":"sum", "Revenue":"sum"}).reset_index()
    prod_agg = prod_df.groupby(["Month", "Product"]).agg({"Production":"sum"}).reset_index()
    reports_df = pd.merge(reports_df, prod_agg, on=["Month", "Product"])
    reports_df["Month"] = pd.Categorical(reports_df["Month"], categories=MONTHS, ordered=True)
    reports_df = reports_df.sort_values(["Month", "Product"]).reset_index(drop=True)
    report_data = reports_df.to_dict(orient="records")

    # Insights
    top_product = max(mix, key=mix.get) if mix else "None"
    top_product_pct = (mix[top_product] / revenue) * 100 if revenue else 0
    top_country = max(country_perf, key=country_perf.get) if country_perf else "None"
    top_country_rev = country_perf[top_country] if country_perf else 0
    first_month_rev = rev_by_month[0] if rev_by_month else 0
    last_month_rev = rev_by_month[-1] if rev_by_month else 0
    growth_pct = ((last_month_rev - first_month_rev) / first_month_rev * 100) if first_month_rev else 0
    margin = pnl["gross_margin"]
    margin_status = "strong" if margin > 35 else ("moderate" if margin > 20 else "critical")
    
    insights = [
        {"title": "Top Performing Product", "value": top_product, "description": f"Contributes {top_product_pct:.1f}% of total sales (€{mix.get(top_product, 0):,.0f})."},
        {"title": "Regional Leader", "value": top_country, "description": f"Generated €{top_country_rev:,.0f} in total revenue."},
        {"title": "Semester Trajectory", "value": f"{abs(growth_pct):.1f}% {'Growth' if growth_pct >= 0 else 'Decline'}", "description": f"Revenue went from €{first_month_rev:,.0f} to €{last_month_rev:,.0f}."},
        {"title": "Financial Health", "value": f"{margin:.1f}% Gross Margin", "description": f"Indicates a {margin_status} profitability profile under current scenarios."},
        {"title": "Break-Even Point", "value": f"{break_even_units:,.0f} Units", "description": f"Required sales to cover €{opex:,.0f} in fixed OpEx costs."}
    ]

    return {
        "sales_df": sales_df, "prod_df": prod_df, "mats_df": mats_df, "labor_df": labor_df,
        "pnl": pnl, "charts": {
            "months": MONTHS, "revenue": rev_by_month, "mix_labels": list(mix.keys()), "mix_data": list(mix.values()),
            "country_labels": list(country_perf.keys()), "country_data": list(country_perf.values()),
            "prod_vol": prod_vol, "sales_vol": sales_vol, "forecast_months": ["Apr 2027", "May 2027", "Jun 2027"],
            "forecast": forecast, "product_forecasts": product_forecasts,
            "country_forecasts": country_forecasts, "monthly_margin": monthly_margin, "margin_forecast": margin_forecast
        },
        "reports": report_data, "insights": insights
    }

from reportlab.platypus import Image as RLImage, KeepTogether

def to_pdf(sales_df, prod_df, mats_df, labor_df, pnl, insights, images):
    out = io.BytesIO()
    doc = SimpleDocTemplate(out, pagesize=A4, leftMargin=1.5*cm, rightMargin=1.5*cm, topMargin=1.5*cm, bottomMargin=1.5*cm)
    styles = getSampleStyleSheet()
    story = []

    logo_path = 'static/logo.png'
    if os.path.exists(logo_path):
        try:
            logo_img = RLImage(logo_path, width=40, height=40)
            # Two-column layout: Logo (Col 0), Title (Col 1)
            header_table = Table([[logo_img, Paragraph("<b>Smart Dashboard — Strategy & Forecast Report</b>", styles["Title"])]], colWidths=[1.8*cm, 16.2*cm])
            header_table.setStyle(TableStyle([
                ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
                ('LEFTPADDING', (1,0), (1,0), 6),
                ('BOTTOMPADDING', (0,0), (-1,-1), 10),
            ]))
            story.append(header_table)
        except Exception:
            story.append(Paragraph("<b>Smart Dashboard — Strategy & Forecast Report</b>", styles["Title"]))
    else:
        story.append(Paragraph("<b>Smart Dashboard — Strategy & Forecast Report</b>", styles["Title"]))
        
    story.append(Paragraph(f"Period: Oct 2026 – Mar 2027  |  Generated: {datetime.now():%Y-%m-%d %H:%M}  |  Developed by Vedant Joliya (https://vedantjoliya.free.nf/)", styles["Normal"]))
    story.append(Spacer(1, 15))

    story.append(Paragraph("<b>1. Executive Insights & Predictive Analytics</b>", styles["Heading2"]))
    for ins in insights:
        story.append(Paragraph(f"• <b>{ins['title']}:</b> {ins['value']}", styles["Heading3"]))
        story.append(Paragraph(f"<i>{ins['description']}</i>", styles["Normal"]))
        story.append(Spacer(1, 6))

    story.append(Spacer(1, 10))
    story.append(Paragraph("<b>Strategic Suggestions based on Model</b>", styles["Heading3"]))
    
    suggestions = []
    if pnl["gross_margin"] < 25:
        suggestions.append("<b>Cost Control Required:</b> Gross margins are critically low. Consider renegotiating Material Costs or improving Labor efficiency.")
    elif pnl["gross_margin"] > 40:
        suggestions.append("<b>Excellent Margins:</b> Gross profitability is strong. You have room to experiment with price elasticity to drive more volume.")
        
    if pnl["op_margin"] < 10:
        suggestions.append("<b>OpEx Optimization:</b> Operating income is stressed. Review fixed OpEx allocations.")
        
    if pnl["break_even"] > pnl["units"]:
        deficit = pnl["break_even"] - pnl["units"]
        suggestions.append(f"<b>Volume Deficit Warning:</b> Current volume is insufficient to hit break-even. You are short by {deficit:,.0f} units. Aggressive volume discounts or marketing required.")
    else:
        surplus = pnl["units"] - pnl["break_even"]
        suggestions.append(f"<b>Healthy Margin of Safety:</b> You are operating {surplus:,.0f} units above the break-even volume. Consider reinvesting excess profit.")

    for s in suggestions:
        story.append(Paragraph(f"• {s}", styles["Normal"]))
        story.append(Spacer(1, 4))
        
    story.append(Spacer(1, 20))
    story.append(Paragraph("<b>2. Data Visualizations & Forecasting</b>", styles["Heading2"]))
    
    images_to_render = [
        ("revenue", "Monthly Revenue Run-Rate"),
        ("mix", "Product Revenue Mix"),
        ("prod_sales", "Production vs Sales Volume"),
        ("country", "Historical Country Performance"),
        ("forecast", "Overall Revenue Forecast (Next 3 Months)"),
        ("country_forecast", "Regional Trajectories Forecast"),
        ("margin_forecast", "Gross Margin Forecast (%)"),
        ("product_forecast", "Product-Specific Trajectories Forecast")
    ]

    for img_key, img_title in images_to_render:
        if img_key in images:
            try:
                img_data = base64.b64decode(images[img_key].split(',')[1])
                img_io = io.BytesIO(img_data)
                if img_key == "mix":
                    img = RLImage(img_io, width=10*cm, height=10*cm)
                else:
                    img = RLImage(img_io, width=16*cm, height=8*cm)
                
                chart_story = [
                    Paragraph(f"<b>{img_title}</b>", styles["Heading3"]),
                    Spacer(1, 8),
                    img,
                    Spacer(1, 15)
                ]
                story.append(KeepTogether(chart_story))
            except Exception as e:
                pass
                
    story.append(PageBreak())

    story.append(Paragraph("<b>3. Financial Key Performance Indicators</b>", styles["Heading2"]))
    def fmt_eur(v): return f"€{v:,.0f}"
    def fmt_num(v): return f"{v:,.0f}"
    def fmt_pct(v): return f"{v:.1f}%"

    kpi_data = [["Metric", "Calculated Value", "Notes"],
                ["Total Revenue", fmt_eur(pnl["revenue"]), "Total generated over 6 months"],
                ["Total COGS", fmt_eur(pnl["cogs"]), "Includes all direct materials & labor"],
                ["Gross Profit", fmt_eur(pnl["gross"]), "Revenue minus COGS"],
                ["Gross Margin", fmt_pct(pnl["gross_margin"]), ""],
                ["Operating Expenses", fmt_eur(pnl["opex"]), "Fixed overhead costs"],
                ["Operating Income", fmt_eur(pnl["op_inc"]), "EBIT equivalent"],
                ["Operating Margin", fmt_pct(pnl["op_margin"]), ""],
                ["Total Units Sold", fmt_num(pnl["units"]), ""],
                ["Total Units Produced", fmt_num(pnl["units_prod"]), "Includes inventory adjustments"],
                ["Blended Break-Even", fmt_num(pnl["break_even"]) + " Units", "Volume required to cover OpEx"]]
    
    t = Table(kpi_data, colWidths=[5*cm, 4*cm, 7*cm])
    t.setStyle(TableStyle([
        ("BACKGROUND", (0,0), (-1,0), colors.HexColor("#0f172a")),
        ("TEXTCOLOR", (0,0), (-1,0), colors.white),
        ("FONTNAME", (0,0), (-1,0), "Helvetica-Bold"),
        ("GRID", (0,0), (-1,-1), 0.3, colors.grey),
        ("ROWBACKGROUNDS", (0,1), (-1,-1), [colors.white, colors.HexColor("#f8fafc")]),
        ("VALIGN", (0,0), (-1,-1), "MIDDLE")
    ]))
    story.append(t)
    story.append(Spacer(1, 20))

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

    add_table("Sales Budget", sales_df, {"Price": fmt_eur, "Revenue": fmt_eur, "Units": fmt_num})
    add_table("Production Budget", prod_df, {c: fmt_num for c in ["Sales","Opening Inv","Ending Inv","Production"]})
    add_table("Materials Budget", mats_df, {"Unit price": fmt_eur, "Total cost": fmt_eur, "Total qty": fmt_num})
    add_table("Labor Budget", labor_df, {"Labor cost": fmt_eur, "Units produced": fmt_num})

    doc.build(story)
    return out.getvalue()

@app.route('/')
def index():
    return render_template('dashboard.html')

@app.route('/api/base_data')
def api_base_data():
    return jsonify({
        "sales": SALES_FORECAST,
        "prices": PRICES,
        "countries": COUNTRIES,
        "months": MONTHS,
        "products": PRODUCTS
    })

@app.route('/api/data', methods=['POST'])
def api_data():
    payload = request.json or {}
    scen = payload.get("scen", {
        "vol": {p: 1.0 for p in PRODUCTS},
        "price": {p: 1.0 for p in PRODUCTS},
        "mat": 1.0, "labor": 1.0, "opex": 25000000
    })
    overrides = payload.get("overrides", {})
    filters = payload.get("filters", {"country": "All", "product": "All", "month": "All"})
    data = build_dfs(scen, overrides, filters)
    return jsonify({
        "kpi": data["pnl"],
        "charts": data["charts"],
        "reports": data["reports"],
        "insights": data["insights"]
    })

@app.route('/api/download_pdf', methods=['POST'])
def download_pdf():
    payload = request.json or {}
    scen = payload.get("scen", {
        "vol": {p: 1.0 for p in PRODUCTS},
        "price": {p: 1.0 for p in PRODUCTS},
        "mat": 1.0, "labor": 1.0, "opex": 25000000
    })
    overrides = payload.get("overrides", {})
    filters = payload.get("filters", {"country": "All", "product": "All", "month": "All"})
    images = payload.get("images", {})
    data = build_dfs(scen, overrides, filters)
    pdf_bytes = to_pdf(data["sales_df"], data["prod_df"], data["mats_df"], data["labor_df"], data["pnl"], data["insights"], images)
    
    return send_file(
        io.BytesIO(pdf_bytes),
        mimetype='application/pdf',
        as_attachment=True,
        download_name=f'Apple_Report_{datetime.now():%Y%m%d_%H%M}.pdf'
    )

@app.route('/api/chat', methods=['POST'])
def api_chat():
    payload = request.json or {}
    question = payload.get("question", "").lower()
    
    scen = payload.get("scen", {
        "vol": {p: 1.0 for p in PRODUCTS},
        "price": {p: 1.0 for p in PRODUCTS},
        "mat": 1.0, "labor": 1.0, "opex": 25000000
    })
    overrides = payload.get("overrides", {})
    filters = payload.get("filters", {"country": "All", "product": "All", "month": "All"})
    data = build_dfs(scen, overrides, filters)
    
    pnl = data["pnl"]
    sales_df = data["sales_df"]
    prod_df = data["prod_df"]
    mats_df = data["mats_df"]
    labor_df = data["labor_df"]
    insights = data["insights"]
    
    def get_filter_list(key, default_choices):
        val = filters.get(key, "All")
        if isinstance(val, list):
            if "All" in val or not val:
                return default_choices
            return val
        elif isinstance(val, str):
            if val == "All":
                return default_choices
            return [val]
        return default_choices

    # 1. Advanced Entity Extraction & Synonyms Mapping
    # Countries
    selected_countries = []
    if "italy" in question or "italian" in question:
        selected_countries.append("Italy")
    if "sweden" in question or "swedish" in question or "swed" in question:
        selected_countries.append("Sweden")
    if not selected_countries:
        selected_countries = get_filter_list("country", COUNTRIES)

    # Products
    selected_products = []
    for p in PRODUCTS:
        if p.lower() in question:
            selected_products.append(p)
    # Synonyms mapping
    if "macbook" in question and "MacBook Pro" not in selected_products:
        selected_products.append("MacBook Pro")
    if "airpost" in question or "airpod" in question or "pods" in question:
        if "AirPods Pro" not in selected_products:
            selected_products.append("AirPods Pro")
    if "ipad" in question and "iPad Pro" not in selected_products:
        selected_products.append("iPad Pro")
    if "watch" in question and "Apple Watch" not in selected_products:
        selected_products.append("Apple Watch")
    if ("iphone" in question or "phone" in question) and "iPhone" not in selected_products:
        selected_products.append("iPhone")
    
    if not selected_products:
        selected_products = get_filter_list("product", PRODUCTS)

    # Months
    selected_months = []
    for m in MONTHS:
        if m.lower() in question or m.split(" ")[0].lower() in question:
            selected_months.append(m)
    month_synonyms = {
        "october": "Oct 2026", "nov": "Nov 2026", "december": "Dec 2026", "january": "Jan 2027", "february": "Feb 2027", "march": "Mar 2027",
        "oct": "Oct 2026", "november": "Nov 2026", "dec": "Dec 2026", "jan": "Jan 2027", "feb": "Feb 2027", "mar": "Mar 2027"
    }
    for k, v in month_synonyms.items():
        if k in question and v not in selected_months:
            selected_months.append(v)
            
    if not selected_months:
        selected_months = get_filter_list("month", MONTHS)

    # 2. Slice the DataFrames safely for this query context
    sub_sales = sales_df[
        sales_df["Country"].isin(selected_countries) &
        sales_df["Product"].isin(selected_products) &
        sales_df["Month"].isin(selected_months)
    ]
    
    sub_prod = prod_df[
        prod_df["Country"].isin(selected_countries) &
        prod_df["Product"].isin(selected_products) &
        prod_df["Month"].isin(selected_months)
    ]
    
    # Sliced metrics calculations
    slice_rev = sub_sales["Revenue"].sum() if not sub_sales.empty else 0
    slice_units = sub_sales["Units"].sum() if not sub_sales.empty else 0
    slice_avg_price = sub_sales["Price"].mean() if not sub_sales.empty else 0
    
    slice_prod = sub_prod["Production"].sum() if not sub_prod.empty else 0
    slice_sales_vol = sub_prod["Sales"].sum() if not sub_prod.empty else 0
    
    slice_labor_cost = 0
    for p in selected_products:
        p_prod = sub_prod[sub_prod["Product"] == p]["Production"].sum() if not sub_prod.empty else 0
        slice_labor_cost += p_prod * (LABOR_MINUTES[p] / 60.0) * LABOR_RATE_PER_HOUR * scen["labor"]
        
    slice_mat_cost = 0
    for p in selected_products:
        p_prod = sub_prod[sub_prod["Product"] == p]["Production"].sum() if not sub_prod.empty else 0
        for comp, qty, unit_price in BOM[p]:
            slice_mat_cost += p_prod * qty * unit_price * scen["mat"]
            
    slice_cogs = slice_mat_cost + slice_labor_cost
    slice_gross = slice_rev - slice_cogs
    slice_gross_margin = (slice_gross / slice_rev * 100) if slice_rev > 0 else 0
    
    # Scale OpEx based on active countries and months
    slice_opex = (scen["opex"] / len(MONTHS)) * len(selected_months) * len(selected_countries)
    slice_op_inc = slice_gross - slice_opex
    slice_op_margin = (slice_op_inc / slice_rev * 100) if slice_rev > 0 else 0

    # Build Header showing active slice boundary context
    region_str = ", ".join(selected_countries) if len(selected_countries) < len(COUNTRIES) else "All Regions"
    product_str = ", ".join(selected_products) if len(selected_products) < len(PRODUCTS) else "All Products"
    period_str = ", ".join(selected_months) if len(selected_months) < len(MONTHS) else "Full Semester (6 Months)"
    slice_header = f"<div style='font-size: 0.8rem; color: #64748b; margin-bottom: 12px; padding-bottom: 8px; border-bottom: 1px dashed #e2e8f0;'>" \
                   f"Active Slice Context: 📍 <b>{region_str}</b> | 📦 <b>{product_str}</b> | 📅 <b>{period_str}</b></div>"

    # 3. Intent Classification
    intents = {
        "credits": (["developer", "develop", "developed", "credit", "credits", "who made", "created", "vedant", "portfolio", "joliya", "website", "programmer", "author", "engineer", "write", "wrote"], 5),
        "swot": (["swot", "health", "grade", "performance", "diagnose", "assessment", "score", "audit"], 4),
        "improve": (["improve", "maximize", "optimize", "more profit", "grow profit", "increase margin", "better profit", "help", "suggest", "recommendation"], 4),
        "struggle": (["struggling", "worst", "weakest", "bad product", "lowest margin", "losing money", "least profitable"], 4),
        "forecast": (["forecast", "predict", "trajectory", "next month", "ols", "future", "trend"], 3),
        "break_even": (["break-even", "breakeven", "break even", "cover cost", "fixed cost"], 4),
        "cogs": (["cogs", "cost structure", "materials", "labor", "expense", "spend", "cost", "costs"], 3),
        "revenue": (["revenue", "sales", "total sales", "make money", "turnover", "sold"], 2),
        "profit": (["profit", "net profit", "operating income", "ebit", "earnings", "income"], 2),
        "margin": (["margin", "gross margin", "op margin"], 2),
        "regions": (["italy", "sweden", "country", "regional"], 2),
        "inventory": (["inventory", "stock", "ending inv", "opening inv", "policy", "buffer"], 3),
    }
    
    scores = {}
    for intent, (words, weight) in intents.items():
        score = sum(1 for w in words if w in question) * weight
        if score > 0:
            scores[intent] = score
            
    best_intent = max(scores, key=scores.get) if scores else "fallback"
    
    # 4. Strategy & Dynamic Answer Generator
    if best_intent == "credits":
        ans = (
            "This Apple Enterprise Financial Modeling Platform was developed exclusively by "
            "<b><a href='https://vedantjoliya.free.nf/' target='_blank'>Vedant Joliya</a></b>.<br><br>"
            "His core contributions include:<br>"
            "• Rebuilding the entire Streamlit application into high-speed Flask backend architecture.<br>"
            "• Developing a real-time linear OLS regression pipeline to forecast three-month trends dynamically.<br>"
            "• Designing the comprehensive ReportLab PDF executive case study document generator with dynamic embedded Chart.js graphs.<br>"
            "• Creating a highly interactive, responsive grid dashboard with precision scenario controls and this custom floating AI assistant.<br><br>"
            "Visit his portfolio: <a href='https://vedantjoliya.free.nf/' target='_blank'>vedantjoliya.free.nf</a>"
        )
        
    elif best_intent == "swot":
        score = 0
        if slice_gross_margin >= 40: score += 2
        elif slice_gross_margin >= 25: score += 1
        if slice_op_margin >= 20: score += 2
        elif slice_op_margin >= 10: score += 1
        
        grades = {4: "A+ (Excellent)", 3: "A (Good)", 2: "B (Moderate)", 1: "C (Warning)", 0: "D/F (Critical)"}
        grade = grades.get(score, "B")
        
        ans = (
            f"<h3>📊 Executive Health SWOT: Grade {grade}</h3>"
            f"{slice_header}"
            f"Evaluating P&L parameters under this active configuration slice:<br>"
            f"• <b>Gross Margin:</b> {slice_gross_margin:.1f}% (Gross Profit: €{slice_gross:,.0f})<br>"
            f"• <b>Operating Margin:</b> {slice_op_margin:.1f}% (Operating EBIT: €{slice_op_inc:,.0f})<br>"
            f"• <b>Scaled overhead:</b> €{slice_opex:,.0f} OpEx share<br><br>"
            f"<b>SWOT Diagnosis:</b><br>"
            f"• <b>Strength:</b> High-margin premium product sales hold average price floor of €{slice_avg_price:.2f}/unit.<br>"
            f"• <b>Weakness:</b> BOM Materials represent {(slice_mat_cost/slice_cogs*100 if slice_cogs else 0):.1f}% of cost structure, exposing margins to parts inflation.<br>"
            f"• <b>Opportunity:</b> Adjusting regional product pricing (Sweden vs Italy) to offset materials and labor costs.<br>"
            f"• <b>Threat:</b> Material cost modifier is at <b>{scen['mat']:.2f}x</b>. COGS totals €{slice_cogs:,.0f}."
        )
        
    elif best_intent == "improve":
        base_profit = slice_op_inc
        
        # 1. 5% price increase across selected products
        scen_a = copy.deepcopy(scen)
        for p in selected_products:
            scen_a["price"][p] = scen_a["price"].get(p, 1.0) * 1.05
        res_a_df = build_dfs(scen_a, overrides, filters)
        sub_sales_a = res_a_df["sales_df"][res_a_df["sales_df"]["Country"].isin(selected_countries) & res_a_df["sales_df"]["Product"].isin(selected_products) & res_a_df["sales_df"]["Month"].isin(selected_months)]
        sub_prod_a = res_a_df["prod_df"][res_a_df["prod_df"]["Country"].isin(selected_countries) & res_a_df["prod_df"]["Product"].isin(selected_products) & res_a_df["prod_df"]["Month"].isin(selected_months)]
        a_rev = sub_sales_a["Revenue"].sum() if not sub_sales_a.empty else 0
        a_labor = sum(sub_prod_a[sub_prod_a["Product"]==p]["Production"].sum() * (LABOR_MINUTES[p]/60.0) * LABOR_RATE_PER_HOUR * scen_a["labor"] for p in selected_products)
        a_mat = sum(sub_prod_a[sub_prod_a["Product"]==p]["Production"].sum() * qty * up * scen_a["mat"] for p in selected_products for comp, qty, up in BOM[p])
        a_op_inc = a_rev - (a_labor + a_mat) - slice_opex
        diff_a = a_op_inc - base_profit
        
        # 2. 5% reduction in material costs
        scen_b = copy.deepcopy(scen)
        scen_b["mat"] = max(0.1, scen_b["mat"] * 0.95)
        res_b_df = build_dfs(scen_b, overrides, filters)
        sub_sales_b = res_b_df["sales_df"][res_b_df["sales_df"]["Country"].isin(selected_countries) & res_b_df["sales_df"]["Product"].isin(selected_products) & res_b_df["sales_df"]["Month"].isin(selected_months)]
        sub_prod_b = res_b_df["prod_df"][res_b_df["prod_df"]["Country"].isin(selected_countries) & res_b_df["prod_df"]["Product"].isin(selected_products) & res_b_df["prod_df"]["Month"].isin(selected_months)]
        b_rev = sub_sales_b["Revenue"].sum() if not sub_sales_b.empty else 0
        b_labor = sum(sub_prod_b[sub_prod_b["Product"]==p]["Production"].sum() * (LABOR_MINUTES[p]/60.0) * LABOR_RATE_PER_HOUR * scen_b["labor"] for p in selected_products)
        b_mat = sum(sub_prod_b[sub_prod_b["Product"]==p]["Production"].sum() * qty * up * scen_b["mat"] for p in selected_products for comp, qty, up in BOM[p])
        b_op_inc = b_rev - (b_labor + b_mat) - slice_opex
        diff_b = b_op_inc - base_profit
        
        ans = (
            f"<h3>💡 Strategic recommendations (Sensitivity analysis)</h3>"
            f"{slice_header}"
            f"Here are three actionable optimization paths to improve your current sliced operating income of <b>€{base_profit:,.0f}</b>:<br><br>"
            f"1️⃣ <b>Execute a 5% Pricing Increase Across Product Mix</b>:<br>"
            f"   • Operating EBIT would rise to <b>€{a_op_inc:,.0f}</b> (Net gains: <b>+€{diff_a:,.0f}</b>).<br>"
            f"2️⃣ <b>Negotiate a 5% BOM Components Discount</b>:<br>"
            f"   • Operating EBIT would rise to <b>€{b_op_inc:,.0f}</b> (Net gains: <b>+€{diff_b:,.0f}</b>).<br>"
            f"3️⃣ <b>Optimize Sliced Overhead Allocated Share</b>:<br>"
            f"   • Sliced OpEx allocated is €{slice_opex:,.0f}. Every 5% overhead compression yields €{slice_opex * 0.05:,.0f} net income direct throughput."
        )
        
    elif best_intent == "struggle":
        prod_margins = {}
        for p in selected_products:
            p_rev = sub_sales[sub_sales["Product"] == p]["Revenue"].sum() if not sub_sales.empty else 0
            if p_rev == 0: continue
            p_mats = sub_prod[sub_prod["Product"] == p]["Production"].sum() * sum(qty * up * scen["mat"] for comp, qty, up in BOM[p]) if not sub_prod.empty else 0
            p_labor = sub_prod[sub_prod["Product"] == p]["Production"].sum() * (LABOR_MINUTES[p]/60.0) * LABOR_RATE_PER_HOUR * scen["labor"] if not sub_prod.empty else 0
            p_gross = p_rev - (p_mats + p_labor)
            p_margin = (p_gross / p_rev * 100)
            prod_margins[p] = (p_margin, p_gross, p_rev)
            
        if prod_margins:
            worst_prod = min(prod_margins, key=lambda k: prod_margins[k][0])
            worst_margin, worst_gross, worst_rev = prod_margins[worst_prod]
            ans = (
                f"<h3>⚠️ Product Profitability Analysis</h3>"
                f"{slice_header}"
                f"Sifting through your active query filters, your lowest-margin product is the <b>{worst_prod}</b> at a <b>{worst_margin:.1f}% gross margin</b> "
                f"(Revenue: €{worst_rev:,.0f} | Sliced Gross Profit: €{worst_gross:,.0f}).<br><br>"
                f"<b>Targeted Remedies for {worst_prod}:</b><br>"
                f"• <b>Increase Pricing Modifier:</b> Adjust the {worst_prod} price stepper to offset component costs.<br>"
                f"• <b>Component Negotiation:</b> Target display or PCB components in the {worst_prod} bill of materials to recover margin points."
            )
        else:
            ans = f"<h3>⚠️ No Sliced Data Available</h3>{slice_header}No sales records matched your exact active parameters mix."
            
    elif best_intent == "forecast":
        monthly_revs = []
        for m in MONTHS:
            m_rev = sub_sales[sub_sales["Month"] == m]["Revenue"].sum() if not sub_sales.empty else 0
            monthly_revs.append(m_rev)
        
        # Calculate OLS slope
        X = np.arange(len(monthly_revs))
        y = np.array(monthly_revs)
        if len(X) >= 2:
            coeffs = np.polyfit(X, y, 1)
            poly_eq = np.poly1d(coeffs)
            future_X = np.arange(len(monthly_revs), len(monthly_revs) + 3)
            future_revs = poly_eq(future_X)
            forecast_total = sum(future_revs)
        else:
            forecast_total = slice_rev * 0.50
            
        ans = (
            f"<h3>🔮 OLS Forecasting Summary</h3>"
            f"{slice_header}"
            f"Using linear Ordinary Least Squares (OLS) regression over your active slice monthly history, the model projects:<br>"
            f"• <b>Next Quarter Revenue (Forecast):</b> <b>€{forecast_total:,.0f}</b> across Apr, May, and Jun 2027.<br>"
            f"• <b>Average Sliced Future Run-rate:</b> €{forecast_total/3:,.0f}/month."
        )
        
    elif best_intent == "break_even":
        cm_pct = (slice_gross / slice_rev) if slice_rev > 0 else 0
        be_revenue = slice_opex / cm_pct if cm_pct > 0 else 0
        be_units = be_revenue / slice_avg_price if slice_avg_price > 0 else 0
        
        ans = (
            f"<h3>⚖️ Scaled Break-Even Assessment</h3>"
            f"{slice_header}"
            f"To cover your allocated fixed OpEx share of <b>€{slice_opex:,.0f}</b>, the business units must achieve:<br><br>"
            f"• <b>Required Break-Even Revenue:</b> <b>€{be_revenue:,.0f}</b><br>"
            f"• <b>Equivalent Break-Even Sales:</b> <b>{be_units:,.0f} blended units</b>.<br>"
            f"• <b>Current Sliced Volume:</b> {slice_units:,.0f} units sold (Revenue: €{slice_rev:,.0f}).<br><br>"
        )
        if slice_units >= be_units:
            ans += f"🟢 <b>Profitable Zone:</b> Sliced volumes exceed the break-even threshold by <b>+{slice_units - be_units:,.0f} units</b>."
        else:
            ans += f"🔴 <b>Loss Zone:</b> Sliced volumes are short of break-even by <b>-{be_units - slice_units:,.0f} units</b>."
            
    elif best_intent == "cogs":
        mat_pct = (slice_mat_cost / slice_cogs * 100) if slice_cogs > 0 else 0
        labor_pct = (slice_labor_cost / slice_cogs * 100) if slice_cogs > 0 else 0
        
        ans = (
            f"<h3>💸 Cost & COGS Breakdown</h3>"
            f"{slice_header}"
            f"Your total Cost of Goods Sold (COGS) stands at <b>€{slice_cogs:,.0f}</b>, leaving a gross profit of €{slice_gross:,.0f}. Here is the cost contribution:<br>"
            f"• <b>Materials BOM Cost:</b> €{slice_mat_cost:,.0f} (<b>{mat_pct:.1f}%</b> of COGS).<br>"
            f"• <b>Direct Labor Cost:</b> €{slice_labor_cost:,.0f} (<b>{labor_pct:.1f}%</b> of COGS).<br><br>"
            f"Negotiating components BOM yields the highest structural margin recovery."
        )
        
    elif best_intent == "revenue":
        ans = (
            f"<h3>📈 Sliced Revenue Summary</h3>"
            f"{slice_header}"
            f"Your active parameters project <b>€{slice_rev:,.0f}</b> in revenue across <b>{slice_units:,.0f} sold units</b>.<br><br>"
            f"• <b>Average Selling Price (Blended):</b> €{slice_avg_price:.2f}/unit<br>"
            f"• <b>Average Monthly Sliced Sales:</b> €{slice_rev / len(selected_months):,.0f}/month."
        )
        
    elif best_intent == "profit":
        ans = (
            f"<h3>💼 Sliced Profit & Margins</h3>"
            f"{slice_header}"
            f"Under your active scenario settings, the financial profile is:<br><br>"
            f"• <b>Gross Profit:</b> €{slice_gross:,.0f} (<b>{slice_gross_margin:.1f}%</b> Margin)<br>"
            f"• <b>Operating Profit (EBIT):</b> <b>€{slice_op_inc:,.0f}</b> (<b>{slice_op_margin:.1f}%</b> Margin)<br>"
            f"• <b>Scaled overhead:</b> €{slice_opex:,.0f} OpEx allocated share."
        )
        
    elif best_intent == "margin":
        ans = (
            f"<h3>📊 Sliced Margin Analysis</h3>"
            f"{slice_header}"
            f"• <b>Gross Margin:</b> <b>{slice_gross_margin:.1f}%</b> (Baseline pricing health)<br>"
            f"• <b>Operating Margin:</b> <b>{slice_op_margin:.1f}%</b> (Cushion after fixed cost burden)<br><br>"
            f"Margins expand when materials modifiers are kept low or pricing modifiers are adjusted upwards."
        )
        
    elif best_intent == "regions":
        country_perf = sub_sales.groupby("Country")["Revenue"].sum().to_dict() if not sub_sales.empty else {}
        ans = f"<h3>🌍 Sliced Regional Performance Analysis</h3>{slice_header}"
        for c in selected_countries:
            c_rev = country_perf.get(c, 0)
            c_units = sub_sales[sub_sales["Country"] == c]["Units"].sum() if not sub_sales.empty else 0
            avg_p = c_rev / c_units if c_units else 0
            ans += f"• <b>{c}:</b> €{c_rev:,.0f} revenue, {c_units:,.0f} units sold (Average Price: €{avg_p:.2f}/unit).<br>"
            
    elif best_intent == "inventory":
        avg_open = sub_prod["Opening Inv"].mean() if not sub_prod.empty else 0
        avg_close = sub_prod["Ending Inv"].mean() if not sub_prod.empty else 0
        ans = (
            f"<h3>📦 Sliced Production & Stock Analysis</h3>"
            f"{slice_header}"
            f"• <b>Total Production:</b> {slice_prod:,.0f} units manufactured<br>"
            f"• <b>Total Sliced Sales Demand:</b> {slice_sales_vol:,.0f} units sold<br>"
            f"• <b>Average Sliced Opening Stock:</b> {avg_open:,.0f} units<br>"
            f"• <b>Average Sliced Closing Stock:</b> {avg_close:,.0f} units"
        )
        
    else:
        ans = (
            "I can answer broad, strategic questions about your financial modeling dashboard! Try asking:<br>"
            "• <i>'Who developed this?'</i> to view engineer credits.<br>"
            "• <i>'How to improve profits?'</i> to run dynamic optimization scenarios.<br>"
            "• <i>'Give me a health assessment'</i> to evaluate SWOT/Grade.<br>"
            "• <i>'Which product is struggling?'</i> to identify lowest-margin categories.<br>"
            "• <i>'Tell me about break-even'</i> or <i>'Show COGS breakdown'</i>."
        )
        
    return jsonify({"answer": ans})

if __name__ == '__main__':
    app.run(debug=True, port=5000)
