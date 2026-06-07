"""
╔══════════════════════════════════════════════════════════════╗
║   UBER NCR — REALTIME SURGE PRICING DASHBOARD               ║
║   Databricks Apps  |  Python + Dash + Plotly                ║
╚══════════════════════════════════════════════════════════════╝

Cách deploy lên Databricks Apps:
1. Tạo file này trong Workspace hoặc upload lên Databricks
2. Vào "Compute" → "Apps" → "Create App"
3. Chọn "Custom" → trỏ tới file này
4. Đặt tên app: surge-pricing-dashboard
5. Click "Deploy"

Nếu muốn kết nối Delta Table thực:
  - Thay hàm generate_mock_data() bằng spark.table(...)
  - Đảm bảo App có quyền truy cập catalog
"""

# ── INSTALL (chạy 1 lần trong terminal Databricks) ────────────
# %pip install dash dash-bootstrap-components plotly pandas numpy

import dash
from dash import dcc, html, Input, Output, callback
import dash_bootstrap_components as dbc
import plotly.graph_objects as go
import plotly.express as px
import pandas as pd
import numpy as np
import random
from datetime import datetime, timedelta

# ════════════════════════════════════════════════════════════════
# 1. DATA LAYER — thay bằng spark.table() khi dùng thực tế
# ════════════════════════════════════════════════════════════════

NCR_ZONES = [
    "Connaught Place", "IGI Airport", "Gurugram Cyber City",
    "Noida Sector 62", "Dwarka Sector 10", "Rohini",
    "Vaishali", "AIIMS", "Malviya Nagar", "Pitampura",
    "Kashmere Gate", "Lajpat Nagar", "Saket", "Janakpuri",
    "Hauz Khas", "Mayur Vihar", "Palam Vihar", "Faridabad",
    "Ghaziabad", "Central Secretariat"
]

VEHICLE_TYPES = ["Go Mini", "Go Sedan", "Premier Sedan", "Uber XL", "Auto", "Bike", "eBike"]

BASE_PRICES = {
    "Go Mini": 70, "Go Sedan": 100, "Premier Sedan": 130,
    "Uber XL": 160, "Auto": 50, "Bike": 30, "eBike": 30
}

# Tọa độ gần đúng các khu vực NCR (lat, lon)
ZONE_COORDS = {
    "Connaught Place":      (28.6315, 77.2167),
    "IGI Airport":          (28.5562, 77.1000),
    "Gurugram Cyber City":  (28.4958, 77.0880),
    "Noida Sector 62":      (28.6271, 77.3710),
    "Dwarka Sector 10":     (28.5823, 77.0500),
    "Rohini":               (28.7120, 77.1300),
    "Vaishali":             (28.6441, 77.3367),
    "AIIMS":                (28.5675, 77.2100),
    "Malviya Nagar":        (28.5330, 77.2090),
    "Pitampura":            (28.7050, 77.1400),
    "Kashmere Gate":        (28.6671, 77.2267),
    "Lajpat Nagar":         (28.5680, 77.2430),
    "Saket":                (28.5220, 77.2150),
    "Janakpuri":            (28.6230, 77.0830),
    "Hauz Khas":            (28.5434, 77.2047),
    "Mayur Vihar":          (28.6100, 77.2950),
    "Palam Vihar":          (28.5100, 77.0400),
    "Faridabad":            (28.4089, 77.3178),
    "Ghaziabad":            (28.6692, 77.4538),
    "Central Secretariat":  (28.6145, 77.2090),
}


def generate_live_data():
    """
    Sinh dữ liệu surge theo logic thực tế:
    surge = f(demand, supply_ratio, peak_hour, weather)
    
    ── THAY THẾ BẰNG SPARK ──────────────────────────────────
    try:
        from pyspark.sql import SparkSession
        spark = SparkSession.builder.getOrCreate()
        df = spark.table("default.uber_gold_pricing").toPandas()
        return df
    except:
        pass  # fallback to mock below
    ─────────────────────────────────────────────────────────
    """
    now = datetime.now()
    hour = now.hour
    is_peak = (7 <= hour <= 9) or (17 <= hour <= 20)

    rows = []
    for zone in NCR_ZONES:
        for vtype in random.sample(VEHICLE_TYPES, k=random.randint(3, 6)):
            demand      = random.randint(2, 45)
            supply      = max(1, int(demand * random.uniform(0.3, 1.2)))
            sdr         = round(supply / demand, 3)
            meantemp    = random.uniform(28, 42)
            humidity    = random.uniform(40, 95)
            wind_speed  = random.uniform(5, 35)
            cancel_rate = random.uniform(0, 45)
            avg_eta     = random.uniform(3, 18)

            # ── Logic surge giống Module 5 ──
            if demand > 30 and sdr < 0.3:
                surge = 2.8
            elif demand > 20 and sdr < 0.4:
                surge = 2.3
            elif demand > 15 and sdr < 0.5:
                surge = 2.0
            elif demand > 10 and is_peak:
                surge = 1.8
            elif demand > 10 and sdr < 0.6:
                surge = 1.6
            elif meantemp > 38:
                surge = 1.6
            elif humidity > 80 and wind_speed > 25:
                surge = 1.5
            elif avg_eta > 12:
                surge = 1.4
            elif avg_eta > 8:
                surge = 1.25
            elif is_peak:
                surge = 1.35
            elif cancel_rate > 30:
                surge = 1.3
            else:
                surge = 1.0

            base  = BASE_PRICES.get(vtype, 70)
            lat, lon = ZONE_COORDS.get(zone, (28.6, 77.2))

            rows.append({
                "zone":            zone,
                "vehicle_type":    vtype,
                "demand":          demand,
                "supply":          supply,
                "supply_demand_ratio": sdr,
                "surge_multiplier": surge,
                "base_price":      base,
                "final_price":     round(base * surge, 2),
                "meantemp":        round(meantemp, 1),
                "humidity":        round(humidity, 1),
                "wind_speed":      round(wind_speed, 1),
                "cancel_rate":     round(cancel_rate, 1),
                "avg_eta":         round(avg_eta, 1),
                "is_peak":         is_peak,
                "lat":             lat + random.uniform(-0.01, 0.01),
                "lon":             lon + random.uniform(-0.01, 0.01),
            })

    return pd.DataFrame(rows)


# ════════════════════════════════════════════════════════════════
# 2. LAYOUT
# ════════════════════════════════════════════════════════════════

DARK_BG    = "#0a0e1a"
CARD_BG    = "#111827"
BORDER     = "#1e2d40"
ACCENT     = "#f97316"       # orange
ACCENT2    = "#06b6d4"       # cyan
GREEN      = "#22c55e"
RED        = "#ef4444"
TEXT_MAIN  = "#f1f5f9"
TEXT_SUB   = "#94a3b8"

SURGE_COLORSCALE = [
    [0.00, "#22c55e"],   # 1.0  — green
    [0.25, "#84cc16"],   # 1.3
    [0.50, "#eab308"],   # 1.6  — yellow
    [0.75, "#f97316"],   # 2.0  — orange
    [1.00, "#ef4444"],   # 2.8  — red
]

app = dash.Dash(
    __name__,
    external_stylesheets=[
        dbc.themes.CYBORG,
        "https://fonts.googleapis.com/css2?family=Space+Mono:wght@400;700&family=Syne:wght@400;600;800&display=swap"
    ],
    title="Uber NCR — Surge Dashboard"
)


# ── Helpers ──────────────────────────────────────────────────
def kpi_card(title, value, unit="", color=ACCENT, icon=""):
    return dbc.Col(
        html.Div([
            html.P(f"{icon} {title}", style={
                "color": TEXT_SUB, "fontSize": "11px",
                "letterSpacing": "2px", "textTransform": "uppercase",
                "marginBottom": "6px", "fontFamily": "Space Mono"
            }),
            html.Div([
                html.Span(value, style={
                    "fontSize": "32px", "fontWeight": "800",
                    "color": color, "fontFamily": "Syne"
                }),
                html.Span(f" {unit}", style={
                    "fontSize": "14px", "color": TEXT_SUB,
                    "fontFamily": "Space Mono"
                }),
            ])
        ], style={
            "background": CARD_BG,
            "border": f"1px solid {BORDER}",
            "borderLeft": f"3px solid {color}",
            "borderRadius": "8px",
            "padding": "18px 22px",
        }),
        md=3, sm=6, xs=12, className="mb-3"
    )


app.layout = html.Div([

    # ── Auto-refresh ──
    dcc.Interval(id="refresh", interval=30_000, n_intervals=0),
    dcc.Store(id="store"),

    # ── Header ───────────────────────────────────────────────
    html.Div([
        html.Div([
            html.Div("◈ UBER NCR", style={
                "fontFamily": "Syne", "fontWeight": "800",
                "fontSize": "22px", "color": ACCENT,
                "letterSpacing": "3px"
            }),
            html.Div("REALTIME SURGE PRICING INTELLIGENCE", style={
                "fontFamily": "Space Mono", "fontSize": "10px",
                "color": TEXT_SUB, "letterSpacing": "3px", "marginTop": "2px"
            }),
        ]),
        html.Div([
            html.Span("● LIVE", style={
                "color": GREEN, "fontFamily": "Space Mono",
                "fontSize": "11px", "marginRight": "16px"
            }),
            html.Span(id="clock", style={
                "color": TEXT_SUB, "fontFamily": "Space Mono", "fontSize": "11px"
            }),
        ])
    ], style={
        "background": CARD_BG,
        "borderBottom": f"1px solid {BORDER}",
        "padding": "16px 32px",
        "display": "flex",
        "justifyContent": "space-between",
        "alignItems": "center",
    }),

    # ── Body ─────────────────────────────────────────────────
    html.Div([

        # ── Filter Bar ───────────────────────────────────────
        dbc.Row([
            dbc.Col([
                html.Label("VEHICLE TYPE", style={
                    "fontFamily": "Space Mono", "fontSize": "10px",
                    "color": TEXT_SUB, "letterSpacing": "2px"
                }),
                dcc.Dropdown(
                    id="vtype-filter",
                    options=[{"label": "All", "value": "ALL"}] +
                            [{"label": v, "value": v} for v in VEHICLE_TYPES],
                    value="ALL", clearable=False,
                    style={"background": CARD_BG},
                )
            ], md=3),
            dbc.Col([
                html.Label("SURGE THRESHOLD", style={
                    "fontFamily": "Space Mono", "fontSize": "10px",
                    "color": TEXT_SUB, "letterSpacing": "2px"
                }),
                dcc.Slider(
                    id="surge-threshold",
                    min=1.0, max=3.0, step=0.1, value=1.5,
                    marks={1.0: "1.0×", 1.5: "1.5×", 2.0: "2.0×", 2.5: "2.5×", 3.0: "3.0×"},
                    tooltip={"placement": "bottom"},
                )
            ], md=5),
            dbc.Col([
                html.Label("SẮP XẾP THEO", style={
                    "fontFamily": "Space Mono", "fontSize": "10px",
                    "color": TEXT_SUB, "letterSpacing": "2px"
                }),
                dcc.RadioItems(
                    id="sort-by",
                    options=[
                        {"label": " Surge", "value": "surge_multiplier"},
                        {"label": " Demand", "value": "demand"},
                        {"label": " Final Price", "value": "final_price"},
                    ],
                    value="surge_multiplier", inline=True,
                    style={"color": TEXT_MAIN, "fontFamily": "Space Mono",
                           "fontSize": "12px", "paddingTop": "8px"},
                    labelStyle={"marginRight": "18px"},
                )
            ], md=4),
        ], className="mb-4", style={
            "background": CARD_BG, "borderRadius": "8px",
            "padding": "16px 20px",
            "border": f"1px solid {BORDER}",
        }),

        # ── KPI Row ──────────────────────────────────────────
        dbc.Row(id="kpi-row", className="mb-4"),

        # ── Main Charts ──────────────────────────────────────
        dbc.Row([
            # Map
            dbc.Col([
                html.Div([
                    html.P("HOTSPOT MAP — NCR", style={
                        "fontFamily": "Space Mono", "fontSize": "11px",
                        "color": TEXT_SUB, "letterSpacing": "2px",
                        "marginBottom": "12px"
                    }),
                    dcc.Graph(id="map-chart", style={"height": "420px"},
                              config={"displayModeBar": False}),
                ], style={
                    "background": CARD_BG, "borderRadius": "8px",
                    "padding": "20px", "border": f"1px solid {BORDER}",
                    "height": "100%"
                })
            ], md=7, className="mb-4"),

            # Surge bar
            dbc.Col([
                html.Div([
                    html.P("TOP ZONES — SURGE MULTIPLIER", style={
                        "fontFamily": "Space Mono", "fontSize": "11px",
                        "color": TEXT_SUB, "letterSpacing": "2px",
                        "marginBottom": "12px"
                    }),
                    dcc.Graph(id="surge-bar", style={"height": "420px"},
                              config={"displayModeBar": False}),
                ], style={
                    "background": CARD_BG, "borderRadius": "8px",
                    "padding": "20px", "border": f"1px solid {BORDER}",
                    "height": "100%"
                })
            ], md=5, className="mb-4"),
        ]),

        # ── Bottom Row ───────────────────────────────────────
        dbc.Row([
            # Supply vs Demand scatter
            dbc.Col([
                html.Div([
                    html.P("DEMAND vs SUPPLY RATIO", style={
                        "fontFamily": "Space Mono", "fontSize": "11px",
                        "color": TEXT_SUB, "letterSpacing": "2px",
                        "marginBottom": "12px"
                    }),
                    dcc.Graph(id="scatter-chart", style={"height": "320px"},
                              config={"displayModeBar": False}),
                ], style={
                    "background": CARD_BG, "borderRadius": "8px",
                    "padding": "20px", "border": f"1px solid {BORDER}",
                })
            ], md=6, className="mb-4"),

            # Price heatmap
            dbc.Col([
                html.Div([
                    html.P("GIÁ CUỐI (₹) THEO ZONE × VEHICLE", style={
                        "fontFamily": "Space Mono", "fontSize": "11px",
                        "color": TEXT_SUB, "letterSpacing": "2px",
                        "marginBottom": "12px"
                    }),
                    dcc.Graph(id="price-heatmap", style={"height": "320px"},
                              config={"displayModeBar": False}),
                ], style={
                    "background": CARD_BG, "borderRadius": "8px",
                    "padding": "20px", "border": f"1px solid {BORDER}",
                })
            ], md=6, className="mb-4"),
        ]),

        # ── Hotspot Table ─────────────────────────────────────
        html.Div([
            html.P("🔥 HOTSPOT DETAIL TABLE", style={
                "fontFamily": "Space Mono", "fontSize": "11px",
                "color": TEXT_SUB, "letterSpacing": "2px",
                "marginBottom": "16px"
            }),
            html.Div(id="hotspot-table"),
        ], style={
            "background": CARD_BG, "borderRadius": "8px",
            "padding": "20px", "border": f"1px solid {BORDER}",
            "marginBottom": "24px"
        }),

    ], style={"padding": "24px 32px", "background": DARK_BG, "minHeight": "100vh"}),

], style={"background": DARK_BG, "minHeight": "100vh"})


# ════════════════════════════════════════════════════════════════
# 3. CALLBACKS
# ════════════════════════════════════════════════════════════════

@app.callback(
    Output("store", "data"),
    Input("refresh", "n_intervals")
)
def refresh_data(n):
    df = generate_live_data()
    return df.to_json(orient="records")


@app.callback(
    Output("clock", "children"),
    Input("refresh", "n_intervals")
)
def update_clock(n):
    return datetime.now().strftime("%d/%m/%Y  %H:%M:%S")


@app.callback(
    [Output("kpi-row", "children"),
     Output("map-chart", "figure"),
     Output("surge-bar", "figure"),
     Output("scatter-chart", "figure"),
     Output("price-heatmap", "figure"),
     Output("hotspot-table", "children")],
    [Input("store", "data"),
     Input("vtype-filter", "value"),
     Input("surge-threshold", "value"),
     Input("sort-by", "value")]
)
def update_all(data_json, vtype, threshold, sort_col):
    if not data_json:
        empty = go.Figure()
        return [], empty, empty, empty, empty, []

    df = pd.read_json(data_json, orient="records")

    # Filter
    if vtype != "ALL":
        df = df[df["vehicle_type"] == vtype]

    df_hot = df[df["surge_multiplier"] >= threshold].copy()

    # ── KPIs ──────────────────────────────────────────────
    total_demand  = int(df["demand"].sum())
    avg_surge     = round(df["surge_multiplier"].mean(), 2)
    hot_zones     = df_hot["zone"].nunique()
    max_price     = int(df_hot["final_price"].max()) if len(df_hot) else 0

    surge_color = RED if avg_surge >= 2.0 else ACCENT if avg_surge >= 1.5 else GREEN

    kpis = dbc.Row([
        kpi_card("Total Demand",   f"{total_demand:,}", "chuyến",  ACCENT2,  "📊"),
        kpi_card("Avg Surge",      f"{avg_surge}",      "×",       surge_color, "⚡"),
        kpi_card("Hotspot Zones",  f"{hot_zones}",      "khu vực", RED,     "🔥"),
        kpi_card("Max Final Price",f"₹{max_price}",     "",        GREEN,   "💰"),
    ])

    # ── Map ───────────────────────────────────────────────
    df_map = df.groupby("zone", as_index=False).agg(
        surge_multiplier=("surge_multiplier", "max"),
        demand=("demand", "sum"),
        lat=("lat", "mean"),
        lon=("lon", "mean"),
        final_price=("final_price", "max"),
    )

    fig_map = go.Figure(go.Scattermapbox(
        lat=df_map["lat"], lon=df_map["lon"],
        mode="markers",
        marker=dict(
            size=df_map["demand"].clip(8, 40),
            color=df_map["surge_multiplier"],
            colorscale=SURGE_COLORSCALE,
            cmin=1.0, cmax=3.0,
            showscale=True,
            colorbar=dict(
                title=dict(text="Surge ×", font=dict(color=TEXT_SUB, size=10)),
                tickfont=dict(color=TEXT_SUB, size=9),
                bgcolor=CARD_BG,
                bordercolor=BORDER,
                thickness=12,
            ),
            opacity=0.85,
        ),
        text=df_map.apply(
            lambda r: f"<b>{r['zone']}</b><br>"
                      f"Surge: {r['surge_multiplier']}×<br>"
                      f"Demand: {r['demand']}<br>"
                      f"Max Price: ₹{r['final_price']:.0f}",
            axis=1
        ),
        hoverinfo="text",
    ))
    fig_map.update_layout(
        mapbox=dict(
            style="carto-darkmatter",
            center=dict(lat=28.60, lon=77.20),
            zoom=9.5,
        ),
        margin=dict(l=0, r=0, t=0, b=0),
        paper_bgcolor=CARD_BG,
        plot_bgcolor=CARD_BG,
    )

    # ── Surge Bar ─────────────────────────────────────────
    df_bar = (
        df_hot.groupby(["zone", "vehicle_type"], as_index=False)["surge_multiplier"]
        .max()
        .sort_values(sort_col if sort_col == "surge_multiplier" else "surge_multiplier",
                     ascending=False)
        .head(15)
    )

    bar_colors = df_bar["surge_multiplier"].apply(
        lambda s: RED if s >= 2.5 else ACCENT if s >= 1.8 else "#eab308" if s >= 1.5 else GREEN
    )

    fig_bar = go.Figure(go.Bar(
        x=df_bar["surge_multiplier"],
        y=df_bar["zone"] + " · " + df_bar["vehicle_type"],
        orientation="h",
        marker=dict(color=bar_colors, line=dict(width=0)),
        text=df_bar["surge_multiplier"].apply(lambda s: f"{s}×"),
        textfont=dict(color=TEXT_MAIN, size=11, family="Space Mono"),
        textposition="outside",
        hovertemplate="<b>%{y}</b><br>Surge: %{x}×<extra></extra>",
    ))
    fig_bar.update_layout(
        paper_bgcolor=CARD_BG, plot_bgcolor=CARD_BG,
        xaxis=dict(
            showgrid=True, gridcolor=BORDER,
            tickfont=dict(color=TEXT_SUB, family="Space Mono", size=10),
            range=[0, 3.4],
        ),
        yaxis=dict(
            tickfont=dict(color=TEXT_MAIN, family="Space Mono", size=10),
            autorange="reversed",
        ),
        margin=dict(l=10, r=60, t=10, b=10),
        bargap=0.25,
    )
    # Đường reference 1.0×
    fig_bar.add_vline(x=1.0, line_dash="dot",
                      line_color=GREEN, line_width=1,
                      annotation_text="base",
                      annotation_font=dict(color=GREEN, size=9))

    # ── Scatter: Demand vs Supply Ratio ───────────────────
    fig_scatter = go.Figure(go.Scatter(
        x=df["demand"], y=df["supply_demand_ratio"],
        mode="markers",
        marker=dict(
            size=8,
            color=df["surge_multiplier"],
            colorscale=SURGE_COLORSCALE,
            cmin=1.0, cmax=3.0,
            opacity=0.75,
            line=dict(width=0),
        ),
        text=df.apply(
            lambda r: f"{r['zone']}<br>Surge: {r['surge_multiplier']}×", axis=1
        ),
        hoverinfo="text",
    ))
    fig_scatter.add_hline(y=0.5, line_dash="dot", line_color=ACCENT,
                          line_width=1,
                          annotation_text="supply thấp (0.5)",
                          annotation_font=dict(color=ACCENT, size=9))
    fig_scatter.update_layout(
        paper_bgcolor=CARD_BG, plot_bgcolor=CARD_BG,
        xaxis=dict(title=dict(text="Demand", font=dict(color=TEXT_SUB, size=11)),
                   showgrid=True, gridcolor=BORDER,
                   tickfont=dict(color=TEXT_SUB, size=10)),
        yaxis=dict(title=dict(text="Supply/Demand Ratio", font=dict(color=TEXT_SUB, size=11)),
                   showgrid=True, gridcolor=BORDER,
                   tickfont=dict(color=TEXT_SUB, size=10)),
        margin=dict(l=50, r=20, t=10, b=40),
    )

    # ── Heatmap: Final Price ──────────────────────────────
    top_zones    = df.groupby("zone")["demand"].sum().nlargest(8).index.tolist()
    df_heat      = df[df["zone"].isin(top_zones)]
    pivot        = df_heat.pivot_table(
        values="final_price", index="zone",
        columns="vehicle_type", aggfunc="mean"
    ).fillna(0)

    fig_heat = go.Figure(go.Heatmap(
        z=pivot.values,
        x=pivot.columns.tolist(),
        y=pivot.index.tolist(),
        colorscale=[[0, CARD_BG], [0.3, "#1e3a5f"],
                    [0.6, ACCENT], [1.0, RED]],
        text=np.round(pivot.values, 0),
        texttemplate="₹%{text:.0f}",
        textfont=dict(size=9, color=TEXT_MAIN, family="Space Mono"),
        hovertemplate="<b>%{y}</b> · %{x}<br>₹%{z:.0f}<extra></extra>",
        showscale=False,
    ))
    fig_heat.update_layout(
        paper_bgcolor=CARD_BG, plot_bgcolor=CARD_BG,
        xaxis=dict(tickfont=dict(color=TEXT_SUB, size=9, family="Space Mono"),
                   side="bottom"),
        yaxis=dict(tickfont=dict(color=TEXT_MAIN, size=9, family="Space Mono"),
                   autorange="reversed"),
        margin=dict(l=10, r=10, t=10, b=10),
    )

    # ── Hotspot Table ─────────────────────────────────────
    top_hot = (
        df_hot.sort_values(sort_col, ascending=False)
        .groupby(["zone", "vehicle_type"], as_index=False)
        .first()
        .head(20)
    )

    def surge_badge(s):
        c = RED if s >= 2.5 else ACCENT if s >= 1.8 else "#eab308" if s >= 1.5 else GREEN
        lbl = "🚨 KHẨN CẤP" if s >= 2.5 else "⚠️ CAO" if s >= 2.0 else "ℹ️ TRUNG BÌNH"
        return html.Span(lbl, style={
            "background": c + "22", "color": c,
            "border": f"1px solid {c}",
            "borderRadius": "4px", "padding": "2px 8px",
            "fontFamily": "Space Mono", "fontSize": "10px",
            "whiteSpace": "nowrap"
        })

    header = html.Tr([
        html.Th(h, style={
            "color": TEXT_SUB, "fontFamily": "Space Mono",
            "fontSize": "10px", "letterSpacing": "1px",
            "padding": "8px 12px", "borderBottom": f"2px solid {BORDER}",
            "whiteSpace": "nowrap"
        })
        for h in ["ZONE", "VEHICLE", "DEMAND", "SUPPLY", "S/D RATIO",
                  "SURGE ×", "BASE ₹", "FINAL ₹", "TEMP °C", "STATUS"]
    ], style={"background": "#0d1520"})

    rows_html = []
    for _, r in top_hot.iterrows():
        sdr_color = RED if r["supply_demand_ratio"] < 0.4 else \
                    ACCENT if r["supply_demand_ratio"] < 0.6 else GREEN
        rows_html.append(html.Tr([
            html.Td(r["zone"],          style={"color": TEXT_MAIN, "fontFamily": "Syne",
                                               "fontWeight": "600", "fontSize": "13px"}),
            html.Td(r["vehicle_type"],  style={"color": ACCENT2, "fontFamily": "Space Mono",
                                               "fontSize": "11px"}),
            html.Td(int(r["demand"]),   style={"color": TEXT_MAIN, "fontFamily": "Space Mono",
                                               "fontSize": "12px"}),
            html.Td(int(r["supply"]),   style={"color": TEXT_MAIN, "fontFamily": "Space Mono",
                                               "fontSize": "12px"}),
            html.Td(f'{r["supply_demand_ratio"]:.2f}',
                    style={"color": sdr_color, "fontFamily": "Space Mono", "fontSize": "12px"}),
            html.Td(f'{r["surge_multiplier"]}×',
                    style={"color": RED if r["surge_multiplier"] >= 2.0 else ACCENT,
                           "fontFamily": "Space Mono", "fontWeight": "700", "fontSize": "14px"}),
            html.Td(f'₹{r["base_price"]}',
                    style={"color": TEXT_SUB, "fontFamily": "Space Mono", "fontSize": "11px"}),
            html.Td(f'₹{r["final_price"]:.0f}',
                    style={"color": GREEN, "fontFamily": "Space Mono",
                           "fontWeight": "700", "fontSize": "13px"}),
            html.Td(f'{r["meantemp"]}°',
                    style={"color": TEXT_SUB, "fontFamily": "Space Mono", "fontSize": "11px"}),
            html.Td(surge_badge(r["surge_multiplier"])),
        ], style={
            "borderBottom": f"1px solid {BORDER}",
            "transition": "background 0.2s",
        }))

    table = html.Table(
        [html.Thead(header), html.Tbody(rows_html)],
        style={"width": "100%", "borderCollapse": "collapse",
               "tableLayout": "auto"}
    )

    return kpis, fig_map, fig_bar, fig_scatter, fig_heat, table


# ════════════════════════════════════════════════════════════════
# 4. ENTRY POINT
# ════════════════════════════════════════════════════════════════
if __name__ == "__main__":
    # Databricks Apps tự inject PORT qua biến môi trường
    import os
    port = int(os.environ.get("DATABRICKS_APP_PORT", 8050))
    app.run(host="0.0.0.0", port=port, debug=False)
