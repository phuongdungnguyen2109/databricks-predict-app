"""
╚══════════════════════════════════════════════════════════════╝
║   UBER NCR — REALTIME SURGE PRICING DASHBOARD                ║
║   Databricks Apps  |  Python + Dash + Plotly                 ║
║   INTEGRATION: XGBoost Model Serving API (Cách 2)            ║
╚══════════════════════════════════════════════════════════════╝
"""

import dash
from dash import dcc, html, Input, Output, callback
import dash_bootstrap_components as dbc
import plotly.graph_objects as go
import plotly.express as px
import pandas as pd
import numpy as np
import random
import os
import requests
from datetime import datetime

# ════════════════════════════════════════════════════════════════
# CONFIGURATION & DATA LAYER
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
    Chuẩn bị đặc trưng (Features) và ép kiểu dữ liệu chuẩn xác 100% 
    theo Schema mô hình XGBoost yêu cầu để tránh lỗi HTTP 400.
    """
    DATABRICKS_HOST = os.getenv("DATABRICKS_HOST", "https://dbc-52936fd5-e087.cloud.databricks.com")
    DATABRICKS_TOKEN = os.getenv("DATABRICKS_TOKEN", "dapie52298aa741859bfa3588877a92800e4")
    ENDPOINT_NAME = os.getenv("MODEL_ENDPOINT_NAME", "surge_multiplier_predictor")

    now = datetime.now()
    rows = []
    
    for zone in NCR_ZONES:
        for vtype in random.sample(VEHICLE_TYPES, k=random.randint(4, 6)):
            demand_val = float(random.randint(5, 50))
            supply_val = float(max(1.0, float(demand_val * random.uniform(0.2, 1.1))))
            
            # Ép kiểu chuẩn xác: demand/supply_proxy -> float (double), hour/day -> int (long)
            rows.append({
                "zone": zone,
                "vehicle_type": vtype,
                "demand": float(demand_val),
                "supply_proxy": float(supply_val),
                "hour": int(now.hour),
                "day_of_week": int(now.weekday()),
                "base_price": float(BASE_PRICES.get(vtype, 70))
            })
            
    df = pd.DataFrame(rows)
    
    # 4 cột đặc trưng khớp hoàn toàn với cấu trúc Endpoint hiển thị
    feature_columns = ["demand", "supply_proxy", "hour", "day_of_week"]
    
    # Đóng gói bản ghi gửi API
    scoring_data = {"dataframe_records": df[feature_columns].to_dict(orient="records")}
    
    # Tự động dọn dẹp để đảm bảo đuôi URL luôn luôn chỉ có duy nhất 1 chữ /invocations
    clean_endpoint = ENDPOINT_NAME.split('/invocations')[0].strip()
    url = f"{DATABRICKS_HOST.rstrip('/')}/api/2.0/serving-endpoints/{clean_endpoint}/invocations"
    headers = {
        "Authorization": f"Bearer {DATABRICKS_TOKEN}",
        "Content-Type": "application/json"
    }
    
    try:
        response = requests.post(url, headers=headers, json=scoring_data, timeout=8)
        if response.status_code == 200:
            predictions = response.json().get("predictions", [])
            df["surge_multiplier"] = [round(max(1.0, float(p)), 2) for p in predictions]
            df["api_status"] = "CONNECTED (XGBoost Realtime)"
        else:
            df["api_status"] = f"OFFLINE FALLBACK (HTTP {response.status_code})"
            raise ValueError(f"HTTP {response.status_code}")
            
    except Exception as e:
        # Cơ chế dự phòng an toàn nếu kết nối trục trặc
        if "api_status" not in df.columns:
            df["api_status"] = f"OFFLINE FALLBACK ({str(e)})"
        
        surge_list = []
        for _, r in df.iterrows():
            sdr = r["supply_proxy"] / r["demand"] if r["demand"] > 0 else 1
            if sdr < 0.4: surge = 2.0
            elif sdr < 0.7: surge = 1.5
            else: surge = 1.0
            surge_list.append(surge)
        df["surge_multiplier"] = surge_list

    # Tính toán các cột hỗ trợ giao diện đồ họa
    df["supply_demand_ratio"] = round(df["supply_proxy"] / df["demand"], 3)
    df["final_price"] = round(df["base_price"] * df["surge_multiplier"], 2)
    df["lat"] = df["zone"].map(lambda z: ZONE_COORDS.get(z, (28.60, 77.20))[0]) + np.random.uniform(-0.005, 0.005, len(df))
    df["lon"] = df["zone"].map(lambda z: ZONE_COORDS.get(z, (28.60, 77.20))[1]) + np.random.uniform(-0.005, 0.005, len(df))
    
    df.rename(columns={"supply_proxy": "supply", "base_price": "base_price"}, inplace=True)
    return df
# ════════════════════════════════════════════════════════════════
# LAYOUT & DESIGN SYSTEM
# ════════════════════════════════════════════════════════════════

DARK_BG    = "#0a0e1a"
CARD_BG    = "#111827"
BORDER     = "#1e2d40"
ACCENT     = "#f97316"
ACCENT2    = "#06b6d4"
GREEN      = "#22c55e"
RED        = "#ef4444"
TEXT_MAIN  = "#f1f5f9"
TEXT_SUB   = "#94a3b8"

SURGE_COLORSCALE = [
    [0.00, "#22c55e"], [0.25, "#84cc16"], [0.50, "#eab308"], [0.75, "#f97316"], [1.00, "#ef4444"]
]

app = dash.Dash(
    __name__,
    external_stylesheets=[
        dbc.themes.CYBORG,
        "https://fonts.googleapis.com/css2?family=Space+Mono:wght@400;700&family=Syne:wght@400;600;800&display=swap"
    ],
    title="Uber NCR — Surge Dashboard"
)

def kpi_card(title, value, unit="", color=ACCENT, icon=""):
    return dbc.Col(
        html.Div([
            html.P(f"{icon} {title}", style={
                "color": TEXT_SUB, "fontSize": "11px", "letterSpacing": "2px",
                "textTransform": "uppercase", "marginBottom": "6px", "fontFamily": "Space Mono"
            }),
            html.Div([
                html.Span(value, style={"fontSize": "32px", "fontWeight": "800", "color": color, "fontFamily": "Syne"}),
                html.Span(f" {unit}", style={"fontSize": "14px", "color": TEXT_SUB, "fontFamily": "Space Mono"}),
            ])
        ], style={
            "background": CARD_BG, "border": f"1px solid {BORDER}",
            "borderLeft": f"3px solid {color}", "borderRadius": "8px", "padding": "18px 22px",
        }), md=3, sm=6, xs=12, className="mb-3"
    )

app.layout = html.Div([
    dcc.Interval(id="refresh", interval=30_000, n_intervals=0),
    dcc.Store(id="store"),

    # Header
    html.Div([
        html.Div([
            html.Div("◈ UBER NCR", style={"fontFamily": "Syne", "fontWeight": "800", "fontSize": "22px", "color": ACCENT, "letterSpacing": "3px"}),
            html.Div("REALTIME SURGE PRICING INTELLIGENCE", style={"fontFamily": "Space Mono", "fontSize": "10px", "color": TEXT_SUB, "letterSpacing": "3px", "marginTop": "2px"}),
        ]),
        html.Div([
            html.Span(id="model-status-badge", style={"fontFamily": "Space Mono", "fontSize": "11px", "marginRight": "20px"}),
            html.Span("● LIVE", style={"color": GREEN, "fontFamily": "Space Mono", "fontSize": "11px", "marginRight": "16px"}),
            html.Span(id="clock", style={"color": TEXT_SUB, "fontFamily": "Space Mono", "fontSize": "11px"}),
        ])
    ], style={
        "background": CARD_BG, "borderBottom": f"1px solid {BORDER}", "padding": "16px 32px",
        "display": "flex", "justifyContent": "space-between", "alignItems": "center",
    }),

    # Body
    html.Div([
        # Filter Bar
        dbc.Row([
            dbc.Col([
                html.Label("VEHICLE TYPE", style={"fontFamily": "Space Mono", "fontSize": "10px", "color": TEXT_SUB, "letterSpacing": "2px"}),
                dcc.Dropdown(
                    id="vtype-filter",
                    options=[{"label": "All", "value": "ALL"}] + [{"label": v, "value": v} for v in VEHICLE_TYPES],
                    value="ALL", clearable=False, style={"background": CARD_BG},
                )
            ], md=3),
            dbc.Col([
                html.Label("SURGE THRESHOLD", style={"fontFamily": "Space Mono", "fontSize": "10px", "color": TEXT_SUB, "letterSpacing": "2px"}),
                dcc.Slider(
                    id="surge-threshold", min=1.0, max=3.0, step=0.1, value=1.5,
                    marks={1.0: "1.0×", 1.5: "1.5×", 2.0: "2.0×", 2.5: "2.5×", 3.0: "3.0×"},
                    tooltip={"placement": "bottom"},
                )
            ], md=5),
            dbc.Col([
                html.Label("SẮP XẾP THEO", style={"fontFamily": "Space Mono", "fontSize": "10px", "color": TEXT_SUB, "letterSpacing": "2px"}),
                dcc.RadioItems(
                    id="sort-by",
                    options=[
                        {"label": " Surge", "value": "surge_multiplier"},
                        {"label": " Demand", "value": "demand"},
                        {"label": " Final Price", "value": "final_price"},
                    ],
                    value="surge_multiplier", inline=True,
                    style={"color": TEXT_MAIN, "fontFamily": "Space Mono", "fontSize": "12px", "paddingTop": "8px"},
                    labelStyle={"marginRight": "18px"},
                )
            ], md=4),
        ], className="mb-4", style={"background": CARD_BG, "borderRadius": "8px", "padding": "16px 20px", "border": f"1px solid {BORDER}"}),

        # KPI Row
        dbc.Row(id="kpi-row", className="mb-4"),

        # Charts Row
        dbc.Row([
            dbc.Col([
                html.Div([
                    html.P("HOTSPOT MAP — NCR", style={"fontFamily": "Space Mono", "fontSize": "11px", "color": TEXT_SUB, "letterSpacing": "2px", "marginBottom": "12px"}),
                    dcc.Graph(id="map-chart", style={"height": "420px"}, config={"displayModeBar": False}),
                ], style={"background": CARD_BG, "borderRadius": "8px", "padding": "20px", "border": f"1px solid {BORDER}", "height": "100%"})
            ], md=7, className="mb-4"),

            dbc.Col([
                html.Div([
                    html.P("TOP ZONES — SURGE MULTIPLIER", style={"fontFamily": "Space Mono", "fontSize": "11px", "color": TEXT_SUB, "letterSpacing": "2px", "marginBottom": "12px"}),
                    dcc.Graph(id="surge-bar", style={"height": "420px"}, config={"displayModeBar": False}),
                ], style={"background": CARD_BG, "borderRadius": "8px", "padding": "20px", "border": f"1px solid {BORDER}", "height": "100%"})
            ], md=5, className="mb-4"),
        ]),

        # Bottom Analytics
        dbc.Row([
            dbc.Col([
                html.Div([
                    html.P("DEMAND vs SUPPLY RATIO", style={"fontFamily": "Space Mono", "fontSize": "11px", "color": TEXT_SUB, "letterSpacing": "2px", "marginBottom": "12px"}),
                    dcc.Graph(id="scatter-chart", style={"height": "320px"}, config={"displayModeBar": False}),
                ], style={"background": CARD_BG, "borderRadius": "8px", "padding": "20px", "border": f"1px solid {BORDER}"})
            ], md=6, className="mb-4"),

            dbc.Col([
                html.Div([
                    html.P("GIÁ CUỐI (₹) THEO ZONE × VEHICLE", style={"fontFamily": "Space Mono", "fontSize": "11px", "color": TEXT_SUB, "letterSpacing": "2px", "marginBottom": "12px"}),
                    dcc.Graph(id="price-heatmap", style={"height": "320px"}, config={"displayModeBar": False}),
                ], style={"background": CARD_BG, "borderRadius": "8px", "padding": "20px", "border": f"1px solid {BORDER}"})
            ], md=6, className="mb-4"),
        ]),

        # Table Detail
        html.Div([
            html.P("🔥 HOTSPOT DETAIL TABLE", style={"fontFamily": "Space Mono", "fontSize": "11px", "color": TEXT_SUB, "letterSpacing": "2px", "marginBottom": "16px"}),
            html.Div(id="hotspot-table"),
        ], style={"background": CARD_BG, "borderRadius": "8px", "padding": "20px", "border": f"1px solid {BORDER}", "marginBottom": "24px"}),

    ], style={"padding": "24px 32px", "background": DARK_BG, "minHeight": "100vh"}),
], style={"background": DARK_BG, "minHeight": "100vh"})

# ════════════════════════════════════════════════════════════════
# CALLBACKS MATRIX
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
     Output("hotspot-table", "children"),
     Output("model-status-badge", "children"),
     Output("model-status-badge", "style")],
    [Input("store", "data"),
     Input("vtype-filter", "value"),
     Input("surge-threshold", "value"),
     Input("sort-by", "value")]
)
def update_all(data_json, vtype, threshold, sort_col):
    if not data_json:
        empty = go.Figure()
        return [], empty, empty, empty, empty, [], "LOADING...", {"color": TEXT_SUB}

    df = pd.read_json(data_json, orient="records")
    
    # Render trạng thái kết nối mô hình lên góc màn hình
    api_status_str = df["api_status"].iloc[0] if "api_status" in df.columns else "UNKNOWN"
    status_color = GREEN if "CONNECTED" in api_status_str else RED
    status_style = {"color": status_color, "fontFamily": "Space Mono", "fontSize": "11px", "marginRight": "20px"}

    if vtype != "ALL":
        df = df[df["vehicle_type"] == vtype]

    df_hot = df[df["surge_multiplier"] >= threshold].copy()

    # Tính toán KPIs
    total_demand = int(df["demand"].sum())
    avg_surge = round(df["surge_multiplier"].mean(), 2)
    hot_zones = df_hot["zone"].nunique() if len(df_hot) else 0
    max_price = int(df_hot["final_price"].max()) if len(df_hot) else 0
    surge_color = RED if avg_surge >= 2.0 else ACCENT if avg_surge >= 1.5 else GREEN

    kpis = dbc.Row([
        kpi_card("Total Demand", f"{total_demand:,}", "chuyến", ACCENT2, "📊"),
        kpi_card("Avg Surge", f"{avg_surge}", "×", surge_color, "⚡"),
        kpi_card("Hotspot Zones", f"{hot_zones}", "khu vực", RED, "🔥"),
        kpi_card("Max Final Price", f"₹{max_price}", "", GREEN, "💰"),
    ])

    # Vẽ Map Scattermapbox
    df_map = df.groupby("zone", as_index=False).agg(
        surge_multiplier=("surge_multiplier", "max"), demand=("demand", "sum"),
        lat=("lat", "mean"), lon=("lon", "mean"), final_price=("final_price", "max"),
    )
    fig_map = go.Figure(go.Scattermapbox(
        lat=df_map["lat"], lon=df_map["lon"], mode="markers",
        marker=dict(
            size=df_map["demand"].clip(8, 40), color=df_map["surge_multiplier"],
            colorscale=SURGE_COLORSCALE, cmin=1.0, cmax=3.0, showscale=True,
            colorbar=dict(title=dict(text="Surge ×", font=dict(color=TEXT_SUB, size=10)), thickness=12),
            opacity=0.85
        ),
        text=df_map.apply(lambda r: f"<b>{r['zone']}</b><br>Surge: {r['surge_multiplier']}×<br>Demand: {r['demand']}", axis=1),
        hoverinfo="text"
    ))
    fig_map.update_layout(
        mapbox=dict(style="carto-darkmatter", center=dict(lat=28.60, lon=77.20), zoom=9.2),
        margin=dict(l=0, r=0, t=0, b=0), paper_bgcolor=CARD_BG, plot_bgcolor=CARD_BG
    )

    # Đồ thị Top Surge Bar
    df_bar = df_hot.groupby(["zone", "vehicle_type"], as_index=False)["surge_multiplier"].max()
    if len(df_bar):
        df_bar = df_bar.sort_values("surge_multiplier", ascending=False).head(15)
        b_colors = df_bar["surge_multiplier"].apply(lambda s: RED if s >= 2.2 else ACCENT if s >= 1.7 else GREEN)
        fig_bar = go.Figure(go.Bar(
            x=df_bar["surge_multiplier"], y=df_bar["zone"] + " · " + df_bar["vehicle_type"],
            orientation="h", marker=dict(color=b_colors), text=df_bar["surge_multiplier"].apply(lambda s: f"{s}×"),
            textposition="outside"
        ))
    else:
        fig_bar = go.Figure()
    fig_bar.update_layout(
        paper_bgcolor=CARD_BG, plot_bgcolor=CARD_BG,
        xaxis=dict(gridcolor=BORDER, tickfont=dict(color=TEXT_SUB), range=[0, 3.5]),
        yaxis=dict(tickfont=dict(color=TEXT_MAIN, size=9), autorange="reversed"),
        margin=dict(l=10, r=50, t=10, b=10)
    )

    # Đồ thị Scatter Demand vs Ratio
    fig_scatter = go.Figure(go.Scatter(
        x=df["demand"], y=df["supply_demand_ratio"], mode="markers",
        marker=dict(size=8, color=df["surge_multiplier"], colorscale=SURGE_COLORSCALE, cmin=1.0, cmax=3.0),
        text=df["zone"], hoverinfo="text"
    ))
    fig_scatter.update_layout(
        paper_bgcolor=CARD_BG, plot_bgcolor=CARD_BG,
        xaxis=dict(title="Demand", gridcolor=BORDER, tickfont=dict(color=TEXT_SUB)),
        yaxis=dict(title="Supply/Demand Ratio", gridcolor=BORDER, tickfont=dict(color=TEXT_SUB)),
        margin=dict(l=50, r=20, t=10, b=40)
    )

    # Đồ thị Heatmap Giá Cuối
    t_zones = df.groupby("zone")["demand"].sum().nlargest(8).index.tolist()
    df_heat = df[df["zone"].isin(t_zones)]
    if len(df_heat):
        pivot = df_heat.pivot_table(values="final_price", index="zone", columns="vehicle_type", aggfunc="mean").fillna(0)
        fig_heat = go.Figure(go.Heatmap(z=pivot.values, x=pivot.columns.tolist(), y=pivot.index.tolist(), colorscale="Thermal", showscale=False))
    else:
        fig_heat = go.Figure()
    fig_heat.update_layout(paper_bgcolor=CARD_BG, plot_bgcolor=CARD_BG, margin=dict(l=10, r=10, t=10, b=10), yaxis=dict(autorange="reversed"))

    # Bảng Chi tiết Hotspot Detail Table
    top_hot = df_hot.sort_values(sort_col, ascending=False).head(15) if len(df_hot) else pd.DataFrame()
    
    header = html.Tr([html.Th(h, style={"color": TEXT_SUB, "fontFamily": "Space Mono", "fontSize": "10px", "padding": "8px 12px", "borderBottom": f"2px solid {BORDER}"}) 
                      for h in ["ZONE", "VEHICLE", "DEMAND", "SUPPLY", "S/D RATIO", "SURGE ×", "BASE ₹", "FINAL ₹"]])
    
    rows_html = []
    for _, r in top_hot.iterrows():
        sdr_c = RED if r["supply_demand_ratio"] < 0.4 else ACCENT if r["supply_demand_ratio"] < 0.6 else GREEN
        rows_html.append(html.Tr([
            html.Td(r["zone"], style={"color": TEXT_MAIN, "fontFamily": "Syne", "fontWeight": "600"}),
            html.Td(r["vehicle_type"], style={"color": ACCENT2, "fontFamily": "Space Mono"}),
            html.Td(int(r["demand"]), style={"color": TEXT_MAIN, "fontFamily": "Space Mono"}),
            html.Td(int(r["supply"]), style={"color": TEXT_MAIN, "fontFamily": "Space Mono"}),
            html.Td(f'{r["supply_demand_ratio"]:.2f}', style={"color": sdr_c, "fontFamily": "Space Mono"}),
            html.Td(f'{r["surge_multiplier"]}×', style={"color": RED if r["surge_multiplier"] >= 2.0 else ACCENT, "fontFamily": "Space Mono", "fontWeight": "700"}),
            html.Td(f'₹{r["base_price"]}', style={"color": TEXT_SUB, "fontFamily": "Space Mono"}),
            html.Td(f'₹{r["final_price"]:.0f}', style={"color": GREEN, "fontFamily": "Space Mono", "fontWeight": "700"}),
        ], style={"borderBottom": f"1px solid {BORDER}"}))

    table = html.Table([html.Thead(header), html.Tbody(rows_html)], style={"width": "100%", "borderCollapse": "collapse"})

    return kpis, fig_map, fig_bar, fig_scatter, fig_heat, table, api_status_str, status_style

# ════════════════════════════════════════════════════════════════
# INTERFACE ENTRY POINT
# ════════════════════════════════════════════════════════════════
if __name__ == "__main__":
    port = int(os.environ.get("DATABRICKS_APP_PORT", 8050))
    app.run(host="0.0.0.0", port=port, debug=False)
