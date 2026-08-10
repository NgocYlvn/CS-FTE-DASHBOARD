
from pathlib import Path
import io
import re

import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st


# ============================================================
# APP CONFIGURATION
# ============================================================
st.set_page_config(
    page_title="CS Workload & Capacity Dashboard",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded",
)

APP_TITLE = "CS WORKLOAD & CAPACITY DASHBOARD"
APP_VERSION = "v4.0 – FULL REQUIREMENTS"

FTE_HOURS_PER_DAY = 8
EFFICIENCY = 0.95
WORKING_DAYS = 22
FTE_MINUTES = FTE_HOURS_PER_DAY * 60 * EFFICIENCY * WORKING_DAYS  # 10,032 min/month

SERVICE_ORDER = ["AI", "AE", "OI", "OE", "TR", "CC", "WH"]
SERVICE_LABELS = {
    "AI": "Air Import",
    "AE": "Air Export",
    "OI": "Ocean Import",
    "OE": "Ocean Export",
    "TR": "Trucking",
    "CC": "Customs Clearance",
    "WH": "Warehouse",
}
SERVICE_COLORS = {
    "AI": "#0B6FA8",
    "AE": "#2F8F6B",
    "OI": "#C15A0B",
    "OE": "#A6791B",
    "TR": "#06183D",
    "CC": "#4A6FA1",
    "WH": "#8A94A6",
}

MONTH_ORDER = [
    "Apr-26", "May-26", "Jun-26", "Jul-26", "Aug-26", "Sep-26",
    "Oct-26", "Nov-26", "Dec-26", "Jan-27", "Feb-27", "Mar-27",
]

ACTIVITY_COLS = {
    "Core": "Core Workload",
    "Ancillary": "Ancillary Workload",
    "Supporting": "Supporting Workload",
    "Exception": "Exception Workload",
}
ACTIVITY_COLORS = {
    "Core": "#0B6FA8",
    "Ancillary": "#2F8F6B",
    "Supporting": "#A6791B",
    "Exception": "#B42318",
}


# ============================================================
# STYLE
# ============================================================
st.markdown(
    """
    <style>
    :root{
        --navy:#06183D;
        --navy2:#0B2B61;
        --blue:#0B6FA8;
        --orange:#C15A0B;
        --green:#2F8F6B;
        --amber:#A6791B;
        --red:#B42318;
        --text:#172033;
        --muted:#667085;
        --line:#DCE5F0;
        --page:#F5F7FB;
        --panel:#FFFFFF;
    }

    html, body, [class*="css"]{
        font-family:"Segoe UI",Arial,sans-serif;
    }

    .stApp{background:var(--page);color:var(--text);}
    .block-container{
        max-width:1700px;
        padding-top:1.25rem;
        padding-bottom:2rem;
    }

    [data-testid="stSidebar"]{
        background:linear-gradient(180deg,#06183D 0%,#0B2B61 100%);
    }
    [data-testid="stSidebar"] *{color:#FFFFFF;}
    section[data-testid="stSidebar"] label{
        color:#E8EEF8 !important;
        font-weight:700 !important;
        font-size:.78rem !important;
    }
    section[data-testid="stSidebar"] div[data-baseweb="select"] > div{
        background:#FFFFFF !important;
        color:#172033 !important;
        border-radius:8px !important;
    }
    section[data-testid="stSidebar"] div[data-baseweb="select"] span,
    section[data-testid="stSidebar"] div[data-baseweb="select"] input{
        color:#172033 !important;
        -webkit-text-fill-color:#172033 !important;
    }
    section[data-testid="stSidebar"] div[data-baseweb="select"] svg{
        fill:#667085 !important;
        color:#667085 !important;
    }
    div[data-baseweb="popover"] li,
    div[data-baseweb="menu"] li{color:#172033 !important;}

    .dashboard-title{
        font-size:1.8rem;
        font-weight:850;
        color:var(--navy);
        letter-spacing:-.02em;
        margin:0 0 .15rem 0;
    }
    .dashboard-subtitle{
        font-size:.78rem;
        color:var(--muted);
        margin-bottom:.85rem;
    }

    .section-title{
        background:var(--navy);
        color:#FFFFFF;
        padding:.56rem .85rem;
        border-radius:10px 10px 0 0;
        font-weight:800;
        font-size:.90rem;
        letter-spacing:.01em;
        margin:0;
    }

    .kpi-card{
        height:142px;
        min-height:142px;
        background:#FFFFFF;
        border:1px solid var(--line);
        border-radius:12px;
        padding:11px 14px 10px 14px;
        box-sizing:border-box;
        display:flex;
        flex-direction:column;
        justify-content:flex-start;
        text-align:center;
        box-shadow:0 2px 8px rgba(20,50,90,.045);
    }
    .kpi-label{
        min-height:30px;
        display:flex;
        align-items:center;
        justify-content:center;
        font-size:.78rem;
        font-weight:800;
        line-height:1.15;
        color:var(--navy);
    }
    .kpi-value{
        height:58px;
        display:flex;
        align-items:center;
        justify-content:center;
        font-size:2.05rem;
        font-weight:850;
        line-height:1;
        color:var(--blue);
        white-space:nowrap;
    }
    .kpi-note{
        margin-top:auto;
        min-height:21px;
        font-size:.69rem;
        line-height:1.15;
        color:var(--muted);
        font-weight:650;
    }
    .kpi-split{
        width:100%;
        margin-top:auto;
        padding-top:6px;
        border-top:1px solid #EEF2F7;
        display:flex;
        justify-content:space-between;
        align-items:center;
        font-size:.69rem;
        font-weight:800;
        color:var(--navy);
    }
    .orange .kpi-value{color:var(--orange);}
    .amber .kpi-value{color:var(--amber);}
    .green .kpi-value{color:var(--green);}
    .red .kpi-value{color:var(--red);}

    div[data-testid="stPlotlyChart"]{
        background:#FFFFFF;
        border:1px solid var(--line);
        border-radius:12px;
        padding:.15rem .35rem .05rem .35rem;
        margin-bottom:4px;
    }
    div[data-testid="stDataFrame"]{
        border:1px solid var(--line);
        border-radius:10px;
        overflow:hidden;
    }

    .note-box{
        background:#F8FAFD;
        border:1px solid var(--line);
        border-left:4px solid var(--blue);
        border-radius:8px;
        padding:.55rem .75rem;
        color:#475467;
        font-size:.73rem;
        line-height:1.35;
        margin:.35rem 0 .75rem 0;
    }
    .small-note{
        color:#98A2B3;
        font-size:.69rem;
        margin-top:.35rem;
    }

    [data-testid="stTabs"] button{
        font-weight:750;
    }
    </style>
    """,
    unsafe_allow_html=True,
)


# ============================================================
# HELPERS
# ============================================================
def clean_text(v):
    if pd.isna(v):
        return ""
    return re.sub(r"\s+", " ", str(v)).strip()


def normalize_month(v):
    if v is None or (isinstance(v, float) and pd.isna(v)):
        return ""
    if isinstance(v, pd.Timestamp):
        return v.strftime("%b-%y")
    if hasattr(v, "strftime") and not isinstance(v, str):
        try:
            return v.strftime("%b-%y")
        except Exception:
            pass

    s = clean_text(v)
    if not s:
        return ""

    # Excel/text dates
    for dayfirst in (False, True):
        try:
            dt = pd.to_datetime(s, errors="raise", dayfirst=dayfirst)
            if pd.notna(dt):
                return dt.strftime("%b-%y")
        except Exception:
            pass

    # Apr-26 / Apr / Apr 2026
    m = re.match(r"^([A-Za-z]{3})(?:[- /](\d{2,4}))?$", s)
    if m:
        mon = m.group(1).title()
        yr = m.group(2)
        if yr:
            yr = yr[-2:]
            label = f"{mon}-{yr}"
            if label in MONTH_ORDER:
                return label
        # fallback to FY match by month
        matches = [x for x in MONTH_ORDER if x.startswith(mon + "-")]
        if matches:
            return matches[0]
    return ""


def safe_div(a, b):
    if b is None or pd.isna(b) or float(b) == 0:
        return np.nan
    return float(a) / float(b)


def fmt_num(v, decimals=2):
    if v is None or pd.isna(v):
        return "—"
    if decimals == 0:
        return f"{v:,.0f}"
    return f"{v:,.{decimals}f}".rstrip("0").rstrip(".")


def fmt_hours(minutes):
    if minutes is None or pd.isna(minutes):
        return "—"
    return f"{minutes / 60:,.1f} h"


def kpi_card(label, value, note="", accent=""):
    note_html = note if note else "&nbsp;"
    st.markdown(
        f"""
        <div class="kpi-card {accent}">
            <div class="kpi-label">{label}</div>
            <div class="kpi-value">{value}</div>
            <div class="kpi-note">{note_html}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def hc_kpi_card(label, total, mng, pic, accent=""):
    st.markdown(
        f"""
        <div class="kpi-card {accent}">
            <div class="kpi-label">{label}</div>
            <div class="kpi-value">{fmt_num(total)}</div>
            <div class="kpi-split">
                <span>MNG: {fmt_num(mng)}</span>
                <span>PIC: {fmt_num(pic)}</span>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def section_title(title):
    st.markdown(f'<div class="section-title">{title}</div>', unsafe_allow_html=True)


def spacer(px=18):
    st.markdown(f"<div style='height:{px}px'></div>", unsafe_allow_html=True)


def style_chart(fig, height=340, right_margin=30):
    fig.update_layout(
        height=height,
        margin=dict(l=18, r=right_margin, t=60, b=34),
        paper_bgcolor="white",
        plot_bgcolor="white",
        font=dict(family='"Segoe UI",Arial,sans-serif', color="#172033", size=10),
        hoverlabel=dict(bgcolor="white"),
        legend_title_text="",
    )
    fig.update_xaxes(showgrid=False, linecolor="#DCE5F0")
    fig.update_yaxes(gridcolor="#E9EEF5", zeroline=False)
    return fig


def add_right_note(fig, text):
    if not text:
        return fig
    fig.add_annotation(
        xref="paper", yref="paper",
        x=0.995, y=1.07,
        xanchor="right", yanchor="bottom",
        text=text,
        showarrow=False,
        align="right",
        font=dict(size=9, color="#667085"),
    )
    return fig


def status_from_util(u):
    if pd.isna(u):
        return "No data"
    if u > 1.00:
        return "Overload"
    if u > 0.95:
        return "High Load"
    if u >= 0.90:
        return "Balanced"
    return "Less Load"


def period_count(df, workload_col="Total Workload"):
    if df.empty:
        return 1
    months = (
        df.loc[df[workload_col].fillna(0) != 0, "Month"]
        .dropna().astype(str).unique().tolist()
    )
    return max(len(months), 1)


# ============================================================
# SOURCE FILE
# ============================================================
def find_source_path():
    app_dir = Path(__file__).resolve().parent
    candidates = [
        p for p in app_dir.rglob("*.xlsx")
        if not p.name.startswith("~$")
    ]
    preferred = [
        p for p in candidates
        if p.name.casefold() == "cs workload & capacity.xlsx".casefold()
    ]
    candidates = preferred + [p for p in candidates if p not in preferred]

    required = {
        "HC Capacity",
        "BU Workload Allocation",
        "Shipment volume",
        "CS FTE",
    }

    for p in candidates:
        try:
            xl = pd.ExcelFile(p)
            names = set(xl.sheet_names)
            has_customer = any(s.startswith("Customer Volume") for s in xl.sheet_names)
            if required.issubset(names) and has_customer:
                return p
        except Exception:
            continue
    return None


@st.cache_data(show_spinner=False)
def load_bytes(path_str, mtime):
    p = Path(path_str)
    return p.read_bytes(), p.name


# ============================================================
# PARSERS — MATCH THE PROVIDED WORKBOOK
# ============================================================
@st.cache_data(show_spinner=False)
def parse_hc(file_bytes):
    df = pd.read_excel(io.BytesIO(file_bytes), sheet_name="HC Capacity", header=1)
    df = df.iloc[:, :13].copy()
    df.columns = [
        "Office", "Month",
        "Approved HC MNG", "Approved HC PIC", "Total Approved HC",
        "Actual HC MNG", "Actual HC PIC", "Total Actual HC",
        "Required HC MNG", "Required HC PIC", "Total Required HC",
        "Capacity Utilization", "Workload Status",
    ]
    df["Office"] = df["Office"].map(clean_text)
    df["Month"] = df["Month"].map(normalize_month)
    df["Workload Status"] = df["Workload Status"].map(clean_text)
    for c in df.columns:
        if c not in ["Office", "Month", "Workload Status"]:
            df[c] = pd.to_numeric(df[c], errors="coerce")
    return df[df["Office"].ne("") & df["Month"].isin(MONTH_ORDER)].reset_index(drop=True)


@st.cache_data(show_spinner=False)
def parse_bu(file_bytes):
    df = pd.read_excel(io.BytesIO(file_bytes), sheet_name="BU Workload Allocation", header=1)
    df = df.iloc[:, :13].copy()
    df.columns = [
        "Office", "Month", "Segment",
        "Core Volume", "Core Workload",
        "Ancillary Volume", "Ancillary Workload",
        "Supporting Volume", "Supporting Workload",
        "Exception Volume", "Exception Workload",
        "Total Workload", "Workload Share Raw",
    ]
    for c in ["Office", "Segment"]:
        df[c] = df[c].map(clean_text)
    df["Month"] = df["Month"].map(normalize_month)
    for c in df.columns:
        if c not in ["Office", "Month", "Segment"]:
            df[c] = pd.to_numeric(df[c], errors="coerce")
    df = df[
        df["Office"].ne("")
        & df["Month"].isin(MONTH_ORDER)
        & df["Segment"].isin(SERVICE_ORDER)
    ].copy()
    num_cols = [
        "Core Volume", "Core Workload",
        "Ancillary Volume", "Ancillary Workload",
        "Supporting Volume", "Supporting Workload",
        "Exception Volume", "Exception Workload", "Total Workload",
    ]
    df[num_cols] = df[num_cols].fillna(0)
    office_month_total = df.groupby(["Office", "Month"])["Total Workload"].transform("sum")
    df["Workload Share"] = np.where(
        office_month_total != 0,
        df["Total Workload"] / office_month_total,
        0,
    )
    return df.reset_index(drop=True)


@st.cache_data(show_spinner=False)
def parse_shipment(file_bytes):
    df = pd.read_excel(io.BytesIO(file_bytes), sheet_name="Shipment volume", header=1)
    df.columns = [clean_text(c) for c in df.columns]
    rename = {}
    for c in df.columns:
        cf = c.casefold()
        if cf == "office":
            rename[c] = "Office"
        elif cf == "month":
            rename[c] = "Month"
        elif cf == "active customers":
            rename[c] = "Active Customers"
        elif cf == "total":
            rename[c] = "TOTAL"
    df = df.rename(columns=rename)
    if "Office" not in df or "Month" not in df:
        return pd.DataFrame()
    df["Office"] = df["Office"].map(clean_text)
    df["Month"] = df["Month"].map(normalize_month)
    for c in df.columns:
        if c not in ["Office", "Month"]:
            df[c] = pd.to_numeric(df[c], errors="coerce")
    return df[df["Office"].ne("") & df["Month"].isin(MONTH_ORDER)].reset_index(drop=True)


@st.cache_data(show_spinner=False)
def parse_cs_fte(file_bytes):
    df = pd.read_excel(io.BytesIO(file_bytes), sheet_name="CS FTE", header=1)
    office_col, pic_col = df.columns[:2]
    df[office_col] = df[office_col].map(clean_text)
    df[pic_col] = df[pic_col].map(clean_text)
    df = df[(df[office_col] != "") & (df[pic_col] != "")]
    value_cols = list(df.columns[2:])
    long = df.melt(
        id_vars=[office_col, pic_col],
        value_vars=value_cols,
        var_name="RawMonth",
        value_name="FTE",
    )
    long["Month"] = long["RawMonth"].map(normalize_month)
    long["FTE"] = pd.to_numeric(long["FTE"], errors="coerce")
    long = long.dropna(subset=["FTE"])
    long = long.rename(columns={office_col: "Office", pic_col: "CS PIC"})
    long["PIC Workload"] = long["FTE"] * FTE_MINUTES
    return long[["Office", "CS PIC", "Month", "FTE", "PIC Workload"]].reset_index(drop=True)


@st.cache_data(show_spinner=False)
def parse_customer(file_bytes):
    xl = pd.ExcelFile(io.BytesIO(file_bytes))
    # Prefer office-specific sheets. Use N&S only if office-specific rows are unavailable.
    specific = [s for s in xl.sheet_names if s.startswith("Customer Volume - ")]
    sheets = specific if specific else [s for s in xl.sheet_names if s.startswith("Customer Volume")]

    frames = []
    for s in sheets:
        df = pd.read_excel(io.BytesIO(file_bytes), sheet_name=s, header=1)
        if df.shape[1] < 4:
            continue
        office_col = df.columns[1]
        cust_col = df.columns[2]
        df[office_col] = df[office_col].map(clean_text)
        df[cust_col] = df[cust_col].map(clean_text)
        df = df[(df[office_col] != "") & (df[cust_col] != "")]
        if df.empty:
            continue
        value_cols = [c for c in df.columns[3:] if clean_text(c).casefold() != "total"]
        long = df.melt(
            id_vars=[office_col, cust_col],
            value_vars=value_cols,
            var_name="RawMonth",
            value_name="Shipment Volume",
        )
        long["Month"] = long["RawMonth"].map(normalize_month)
        long["Shipment Volume"] = pd.to_numeric(long["Shipment Volume"], errors="coerce")
        long = long.dropna(subset=["Shipment Volume"])
        long = long.rename(columns={office_col: "Office", cust_col: "Customer"})
        frames.append(long[["Office", "Customer", "Month", "Shipment Volume"]])

    if not frames:
        return pd.DataFrame(columns=["Office", "Customer", "Month", "Shipment Volume"])

    out = pd.concat(frames, ignore_index=True)
    out = out.drop_duplicates(["Office", "Customer", "Month"], keep="first")
    return out[out["Month"].isin(MONTH_ORDER)].reset_index(drop=True)


@st.cache_data(show_spinner=False)
def parse_yvf(file_bytes):
    try:
        df = pd.read_excel(io.BytesIO(file_bytes), sheet_name="YVF Promotion Effectiveness", header=1)
    except Exception:
        return pd.DataFrame(columns=["Office", "Month", "YVF Bookings", "IFF Shipments", "YVF Ratio"])
    df.columns = [clean_text(c) for c in df.columns]
    rename = {}
    for c in df.columns:
        cf = c.casefold()
        if cf == "office":
            rename[c] = "Office"
        elif cf == "month":
            rename[c] = "Month"
        elif "yusen" in cf or "yvf booking" in cf:
            rename[c] = "YVF Bookings"
        elif "iff" in cf:
            rename[c] = "IFF Shipments"
        elif "ratio" in cf:
            rename[c] = "YVF Ratio"
    df = df.rename(columns=rename)
    needed = ["Office", "Month", "YVF Bookings", "IFF Shipments"]
    if not set(["Office", "Month"]).issubset(df.columns):
        return pd.DataFrame(columns=needed + ["YVF Ratio"])
    for c in ["YVF Bookings", "IFF Shipments", "YVF Ratio"]:
        if c not in df:
            df[c] = np.nan
        df[c] = pd.to_numeric(df[c], errors="coerce")
    df["Office"] = df["Office"].map(clean_text)
    df["Month"] = df["Month"].map(normalize_month)
    df["YVF Ratio"] = np.where(
        df["IFF Shipments"].fillna(0) > 0,
        df["YVF Bookings"].fillna(0) / df["IFF Shipments"],
        np.nan,
    )
    return df[df["Office"].ne("") & df["Month"].isin(MONTH_ORDER)].reset_index(drop=True)


@st.cache_data(show_spinner=False)
def parse_scope(file_bytes, sheet_name):
    try:
        df = pd.read_excel(io.BytesIO(file_bytes), sheet_name=sheet_name, header=1)
    except Exception:
        return pd.DataFrame(columns=["Office", "Scope", "Month", "Volume"])
    if df.shape[1] < 3:
        return pd.DataFrame(columns=["Office", "Scope", "Month", "Volume"])
    office_col, scope_col = df.columns[:2]
    df[office_col] = df[office_col].map(clean_text)
    df[scope_col] = df[scope_col].map(clean_text)
    df = df[(df[office_col] != "") & (df[scope_col] != "")]
    values = [c for c in df.columns[2:] if clean_text(c).casefold() != "total"]
    long = df.melt(
        id_vars=[office_col, scope_col],
        value_vars=values,
        var_name="RawMonth",
        value_name="Volume",
    )
    long["Month"] = long["RawMonth"].map(normalize_month)
    long["Volume"] = pd.to_numeric(long["Volume"], errors="coerce")
    long = long.dropna(subset=["Volume"])
    long = long.rename(columns={office_col: "Office", scope_col: "Scope"})
    return long[["Office", "Scope", "Month", "Volume"]].reset_index(drop=True)


@st.cache_data(show_spinner=False)
def parse_exception(file_bytes):
    try:
        df = pd.read_excel(io.BytesIO(file_bytes), sheet_name="Exception Handling Volume", header=1)
    except Exception:
        return pd.DataFrame(columns=["Office", "Code", "BU", "Criteria", "Detail", "Month", "Volume"])

    if df.shape[1] < 6:
        return pd.DataFrame(columns=["Office", "Code", "BU", "Criteria", "Detail", "Month", "Volume"])

    # first five columns
    first = list(df.columns[:5])
    rename = {
        first[0]: "Office",
        first[1]: "Code",
        first[2]: "BU",
        first[3]: "Criteria",
        first[4]: "Detail",
    }
    df = df.rename(columns=rename)
    ids = ["Office", "Code", "BU", "Criteria", "Detail"]
    for c in ids:
        df[c] = df[c].map(clean_text)
    df = df[df["Office"] != ""]
    values = [c for c in df.columns[5:] if clean_text(c).casefold() != "total"]
    long = df.melt(
        id_vars=ids,
        value_vars=values,
        var_name="RawMonth",
        value_name="Volume",
    )
    long["Month"] = long["RawMonth"].map(normalize_month)
    long["Volume"] = pd.to_numeric(long["Volume"], errors="coerce")
    long = long.dropna(subset=["Volume"])
    return long[ids + ["Month", "Volume"]].reset_index(drop=True)


# ============================================================
# LOAD DATA
# ============================================================
source_path = find_source_path()
if source_path is None:
    st.error(
        "Không tìm thấy file Excel phù hợp. File cần có các sheet: "
        "HC Capacity, BU Workload Allocation, Shipment volume, CS FTE và Customer Volume."
    )
    st.stop()

source_bytes, source_name = load_bytes(str(source_path), source_path.stat().st_mtime)

try:
    hc = parse_hc(source_bytes)
    bu = parse_bu(source_bytes)
    shipment = parse_shipment(source_bytes)
    cs_fte = parse_cs_fte(source_bytes)
    customer = parse_customer(source_bytes)
    yvf = parse_yvf(source_bytes)

    core_detail = parse_scope(source_bytes, "Core Service Volume")
    ancillary_detail = parse_scope(source_bytes, "Ancillary Service Volume")
    supporting_detail = parse_scope(source_bytes, "Supporting Activity Volume")
    exception_detail = parse_exception(source_bytes)
except Exception as exc:
    st.error("Không thể đọc dữ liệu nguồn. Vui lòng kiểm tra cấu trúc workbook.")
    st.exception(exc)
    st.stop()


# ============================================================
# SIDEBAR FILTERS
# ============================================================
st.sidebar.markdown(
    "<div style='font-size:1.28rem;font-weight:850;margin-bottom:2px;'>FILTERS</div>",
    unsafe_allow_html=True,
)
st.sidebar.markdown(
    "<div style='font-size:.75rem;color:#C7D4EA;margin-bottom:16px;'>CS Workload & Capacity</div>",
    unsafe_allow_html=True,
)

def reset_children():
    st.session_state["filter_pic"] = "All CS PIC"
    st.session_state["filter_customer"] = "All Customers"

all_offices = sorted(
    set(hc["Office"].dropna().astype(str))
    | set(bu["Office"].dropna().astype(str))
    | set(shipment.get("Office", pd.Series(dtype=str)).dropna().astype(str))
    | set(cs_fte["Office"].dropna().astype(str))
    | set(customer["Office"].dropna().astype(str))
)

office = st.sidebar.selectbox(
    "Office",
    ["All Offices"] + all_offices,
    key="filter_office",
    on_change=reset_children,
)

# Months: only if data exists in at least one business source.
data_months = set()
for df, value_col in [
    (bu, "Total Workload"),
    (shipment, "TOTAL"),
    (customer, "Shipment Volume"),
    (cs_fte, "FTE"),
]:
    if not df.empty and value_col in df.columns:
        data_months |= set(
            df.loc[df[value_col].fillna(0) != 0, "Month"]
            .dropna().astype(str)
        )
# HC approved/actual months
if not hc.empty:
    hmask = (
        hc["Total Approved HC"].notna()
        | hc["Total Actual HC"].notna()
        | (hc["Total Required HC"].fillna(0) != 0)
    )
    data_months |= set(hc.loc[hmask, "Month"].dropna().astype(str))

available_months = [m for m in MONTH_ORDER if m in data_months]
month = st.sidebar.selectbox(
    "Month",
    ["All"] + available_months,
    key="filter_month",
    on_change=reset_children,
)

# PIC options by office/month
pic_scope = cs_fte.copy()
if office != "All Offices":
    pic_scope = pic_scope[pic_scope["Office"].eq(office)]
if month != "All":
    pic_scope = pic_scope[pic_scope["Month"].eq(month)]
pic_options = sorted(pic_scope["CS PIC"].dropna().unique().tolist())
pic_select = ["All CS PIC"] + pic_options
if st.session_state.get("filter_pic") not in pic_select:
    st.session_state["filter_pic"] = "All CS PIC"
cs_pic = st.sidebar.selectbox("CS PIC", pic_select, key="filter_pic")

# Customer options by office/month
cust_scope = customer.copy()
if office != "All Offices":
    cust_scope = cust_scope[cust_scope["Office"].eq(office)]
if month != "All":
    cust_scope = cust_scope[cust_scope["Month"].eq(month)]
cust_options = sorted(cust_scope["Customer"].dropna().unique().tolist())
cust_select = ["All Customers"] + cust_options
if st.session_state.get("filter_customer") not in cust_select:
    st.session_state["filter_customer"] = "All Customers"
selected_customer = st.sidebar.selectbox("Customer", cust_select, key="filter_customer")

st.sidebar.markdown("---")
st.sidebar.caption(f"Data source: {source_name}")
st.sidebar.caption(
    f"1 FTE = 8h × 95% × 22 days = {FTE_MINUTES:,} min/month"
)
st.sidebar.caption(
    "Customer filter applies to customer/shipment views. "
    "Source workbook has no Customer → Service/Workload mapping."
)
st.sidebar.caption(
    "CS PIC filter applies to CS FTE/PIC workload. "
    "Source workbook has no CS PIC → Service/Activity mapping."
)


# ============================================================
# FILTER MODEL
# ============================================================
def apply_om(df):
    out = df.copy()
    if "Office" in out.columns and office != "All Offices":
        out = out[out["Office"].eq(office)]
    if "Month" in out.columns and month != "All":
        out = out[out["Month"].eq(month)]
    return out

f_hc = apply_om(hc)
f_bu = apply_om(bu)
f_ship = apply_om(shipment)
f_fte = apply_om(cs_fte)
f_cust = apply_om(customer)
f_yvf = apply_om(yvf)
f_core = apply_om(core_detail)
f_anc = apply_om(ancillary_detail)
f_sup = apply_om(supporting_detail)
f_exc = apply_om(exception_detail)

if cs_pic != "All CS PIC":
    f_fte = f_fte[f_fte["CS PIC"].eq(cs_pic)]

if selected_customer != "All Customers":
    f_cust = f_cust[f_cust["Customer"].eq(selected_customer)]

# HC valid
hc_valid = f_hc[
    f_hc["Total Approved HC"].notna()
    | f_hc["Total Actual HC"].notna()
    | (f_hc["Total Required HC"].fillna(0) != 0)
].copy()

def hc_period_metric(col):
    if hc_valid.empty:
        return np.nan
    if month == "All":
        monthly = hc_valid.groupby("Month", as_index=False)[col].sum(min_count=1)
        return float(monthly[col].mean())
    return float(hc_valid[col].sum(min_count=1))

approved_total = hc_period_metric("Total Approved HC")
approved_mng = hc_period_metric("Approved HC MNG")
approved_pic = hc_period_metric("Approved HC PIC")
actual_total = hc_period_metric("Total Actual HC")
actual_mng = hc_period_metric("Actual HC MNG")
actual_pic = hc_period_metric("Actual HC PIC")
required_total = hc_period_metric("Total Required HC")
required_mng = hc_period_metric("Required HC MNG")
required_pic = hc_period_metric("Required HC PIC")

capacity_util = safe_div(required_total, actual_total)
capacity_status = status_from_util(capacity_util)

# Workload / service
service = (
    f_bu.groupby("Segment", as_index=False)
    .agg(
        Service_Volume=("Core Volume", "sum"),
        Core=("Core Workload", "sum"),
        Ancillary=("Ancillary Workload", "sum"),
        Supporting=("Supporting Workload", "sum"),
        Exception=("Exception Workload", "sum"),
        Total_Workload=("Total Workload", "sum"),
    )
)
service = pd.DataFrame({"Segment": SERVICE_ORDER}).merge(service, on="Segment", how="left").fillna(0)
total_workload = float(service["Total_Workload"].sum())
service["Share"] = np.where(total_workload != 0, service["Total_Workload"] / total_workload, 0)
service["Hours"] = service["Total_Workload"] / 60

months_for_workload = period_count(f_bu)
required_pic_fte_calc = safe_div(total_workload, FTE_MINUTES * months_for_workload)

# Shipment KPI from Shipment volume (unique transport shipment universe)
if selected_customer != "All Customers":
    total_shipments = float(f_cust["Shipment Volume"].fillna(0).sum())
else:
    total_shipments = (
        float(f_ship["TOTAL"].fillna(0).sum())
        if (not f_ship.empty and "TOTAL" in f_ship.columns)
        else 0.0
    )

active_customers = (
    int(f_cust.loc[f_cust["Shipment Volume"].fillna(0) > 0, "Customer"].nunique())
    if not f_cust.empty
    else 0
)

# PIC workload / FTE
pic_fte = float(f_fte["FTE"].sum()) if not f_fte.empty else 0.0
pic_workload = float(f_fte["PIC Workload"].sum()) if not f_fte.empty else 0.0

# Management allocation by service
# Allocate ACTUAL MNG capacity proportionally to BU workload share.
# For month=All, use monthly actual manager capacity sum across months to avoid averaging.
mgr_hc_for_alloc = apply_om(hc)
mgr_hc_for_alloc = mgr_hc_for_alloc[mgr_hc_for_alloc["Actual HC MNG"].notna()]
mgr_capacity_min = float(mgr_hc_for_alloc["Actual HC MNG"].sum() * FTE_MINUTES)
service["MNG Allocated Min"] = service["Share"] * mgr_capacity_min
service["MNG Allocated Hours"] = service["MNG Allocated Min"] / 60

# YVF
yvf_bookings = float(f_yvf["YVF Bookings"].fillna(0).sum()) if not f_yvf.empty else 0.0
iff_shipments = float(f_yvf["IFF Shipments"].fillna(0).sum()) if not f_yvf.empty else 0.0
yvf_ratio = safe_div(yvf_bookings, iff_shipments)


# ============================================================
# HEADER
# ============================================================
st.markdown(f'<div class="dashboard-title">{APP_TITLE}</div>', unsafe_allow_html=True)
st.markdown(
    f'<div class="dashboard-subtitle">'
    f'{APP_VERSION} · Month: {month} · Office: {office} · CS PIC: {cs_pic} · Customer: {selected_customer}'
    f'</div>',
    unsafe_allow_html=True,
)

if capacity_status == "Overload":
    st.error(
        f"⚠️ Capacity alert: Required HC is above Actual HC "
        f"by {abs(required_total - actual_total):.2f} HC."
    )


# ============================================================
# KPI ROW 1 — HC / CAPACITY
# ============================================================
section_title("HEADCOUNT / CAPACITY STATUS")
k1, k2, k3, k4, k5 = st.columns([1, 1, 1, 1, 1], gap="large")

with k1:
    hc_kpi_card("Approved HC", approved_total, approved_mng, approved_pic)
with k2:
    hc_kpi_card("Actual HC", actual_total, actual_mng, actual_pic)
with k3:
    hc_kpi_card("Required HC", required_total, required_mng, required_pic, "orange")
with k4:
    kpi_card(
        "Capacity Utilization",
        "—" if pd.isna(capacity_util) else f"{capacity_util:.0%}",
        "Required HC ÷ Actual HC",
        "amber",
    )
with k5:
    gap = actual_total - required_total if not pd.isna(actual_total) and not pd.isna(required_total) else np.nan
    gap_note = (
        "No HC data"
        if pd.isna(gap)
        else (f"Over by {abs(gap):.2f} HC" if gap < 0 else f"Available {gap:.2f} HC")
    )
    accent = {
        "Overload": "red",
        "High Load": "orange",
        "Balanced": "green",
    }.get(capacity_status, "")
    kpi_card("Capacity Status", capacity_status, gap_note, accent)

spacer(22)

# ============================================================
# KPI ROW 2 — WORKLOAD / BUSINESS
# ============================================================
section_title("WORKLOAD / PRODUCTIVITY SNAPSHOT")
w1, w2, w3, w4, w5, w6 = st.columns([1, 1, 1, 1, 1, 1], gap="large")
with w1:
    kpi_card("Total Shipments", f"{total_shipments:,.0f}", "Shipment volume / Customer volume")
with w2:
    kpi_card("Total Workload", fmt_hours(total_workload), "Core + Ancillary + Supporting + Exception")
with w3:
    kpi_card(
        "Required PIC FTE",
        "—" if pd.isna(required_pic_fte_calc) else f"{required_pic_fte_calc:.2f}",
        f"Workload ÷ {FTE_MINUTES:,} min",
        "amber",
    )
with w4:
    pic_gap = actual_pic - required_pic_fte_calc if not pd.isna(actual_pic) and not pd.isna(required_pic_fte_calc) else np.nan
    kpi_card(
        "PIC Gap",
        "—" if pd.isna(pic_gap) else f"{pic_gap:+.2f}",
        "Actual PIC − Workload-based FTE",
        "green" if (not pd.isna(pic_gap) and pic_gap >= 0) else "red",
    )
with w5:
    kpi_card("Active Customers", f"{active_customers:,}", "Customers with shipment volume > 0")
with w6:
    kpi_card(
        "YVF Booking Ratio",
        "N/A" if pd.isna(yvf_ratio) else f"{yvf_ratio:.1%}",
        f"{yvf_bookings:,.0f} YVF / {iff_shipments:,.0f} IFF",
        "green" if (not pd.isna(yvf_ratio) and yvf_ratio >= 0.5) else "",
    )

spacer(22)


# ============================================================
# TABS
# ============================================================
tab_overview, tab_service, tab_office_pic, tab_customer, tab_yvf_detail = st.tabs(
    [
        "Executive Overview",
        "Service & Activity",
        "Office & CS PIC",
        "Customer",
        "YVF & Operational Detail",
    ]
)


# ============================================================
# TAB 1 — EXECUTIVE OVERVIEW
# ============================================================
with tab_overview:
    c1, c2, c3 = st.columns([1, 1, 1], gap="large")

    # Office summary
    office_hc = apply_om(hc)
    office_hc = office_hc[
        office_hc["Total Actual HC"].notna()
        | (office_hc["Total Required HC"].fillna(0) != 0)
    ].copy()
    if month == "All" and not office_hc.empty:
        om = (
            office_hc.groupby(["Office", "Month"], as_index=False)
            .agg(
                Actual=("Total Actual HC", "sum"),
                Required=("Total Required HC", "sum"),
            )
        )
        office_sum = (
            om.groupby("Office", as_index=False)
            .agg(Actual=("Actual", "mean"), Required=("Required", "mean"))
        )
    elif not office_hc.empty:
        office_sum = (
            office_hc.groupby("Office", as_index=False)
            .agg(Actual=("Total Actual HC", "sum"), Required=("Total Required HC", "sum"))
        )
    else:
        office_sum = pd.DataFrame(columns=["Office", "Actual", "Required"])

    office_list = all_offices if office == "All Offices" else [office]
    office_sum = pd.DataFrame({"Office": office_list}).merge(office_sum, on="Office", how="left")
    office_sum["Utilization"] = np.where(
        office_sum["Actual"].fillna(0) > 0,
        office_sum["Required"] / office_sum["Actual"],
        np.nan,
    )

    with c1:
        p = office_sum.copy()
        p["Util %"] = p["Utilization"] * 100
        fig = go.Figure(
            go.Bar(
                x=p["Office"],
                y=p["Util %"].fillna(0),
                marker_color="#06183D",
                text=["—" if pd.isna(x) else f"{x:.0f}%" for x in p["Util %"]],
                textposition="outside",
                cliponaxis=False,
            )
        )
        fig.add_hline(y=100, line_dash="dash", line_color="#C15A0B", line_width=1.3)
        fig.update_layout(title="CAPACITY UTILIZATION BY OFFICE", showlegend=False)
        add_right_note(fig, "Target: 100%")
        style_chart(fig, 335, 35)
        fig.update_yaxes(ticksuffix="%", rangemode="tozero")
        st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})

    with c2:
        comp = office_sum.melt(
            id_vars="Office",
            value_vars=["Actual", "Required"],
            var_name="HC Type",
            value_name="HC",
        )
        fig = px.bar(
            comp,
            x="Office",
            y="HC",
            color="HC Type",
            barmode="group",
            text="HC",
            color_discrete_map={"Actual": "#2F73D9", "Required": "#C15A0B"},
        )
        fig.update_traces(texttemplate="%{text:.2f}", textposition="outside", cliponaxis=False)
        fig.update_layout(
            title="ACTUAL VS REQUIRED HC BY OFFICE",
            legend=dict(orientation="v", x=1.02, y=1.0),
        )
        add_right_note(fig, "Actual / Required")
        style_chart(fig, 335, 110)
        st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})

    with c3:
        pie = service[service["Total_Workload"] != 0].copy()
        fig = px.pie(
            pie,
            names="Segment",
            values="Total_Workload",
            hole=.56,
            color="Segment",
            color_discrete_map=SERVICE_COLORS,
            category_orders={"Segment": SERVICE_ORDER},
        )
        fig.update_traces(textinfo="percent", textposition="inside")
        fig.update_layout(
            title="WORKLOAD SHARE BY SERVICE",
            legend=dict(orientation="v", x=1.02, y=.80),
        )
        fig.add_annotation(
            x=.5, y=.5,
            text=f"<b>{total_workload / 60:,.1f}h</b><br>Total",
            showarrow=False,
            font=dict(size=15, color="#06183D"),
        )
        add_right_note(fig, "% of Total Workload")
        style_chart(fig, 335, 105)
        st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})

    spacer(16)

    # Trend overview — always useful
    trend_bu = apply_om(bu if office == "All Offices" else bu[bu["Office"].eq(office)])
    if office == "All Offices":
        trend_bu = bu.copy()
    else:
        trend_bu = bu[bu["Office"].eq(office)].copy()

    trend = (
        trend_bu.groupby("Month", as_index=False)["Total Workload"].sum()
        if not trend_bu.empty
        else pd.DataFrame(columns=["Month", "Total Workload"])
    )
    trend_ship = shipment.copy()
    if office != "All Offices":
        trend_ship = trend_ship[trend_ship["Office"].eq(office)]
    if not trend_ship.empty and "TOTAL" in trend_ship.columns:
        ts = trend_ship.groupby("Month", as_index=False)["TOTAL"].sum()
        trend = trend.merge(ts, on="Month", how="outer")
    else:
        trend["TOTAL"] = 0

    trend["Sort"] = trend["Month"].map({m:i for i,m in enumerate(MONTH_ORDER)})
    trend = trend.sort_values("Sort")
    trend["Workload Hours"] = trend["Total Workload"].fillna(0) / 60

    l, r = st.columns([1.45, 1], gap="large")
    with l:
        fig = go.Figure()
        fig.add_trace(
            go.Bar(
                x=trend["Month"], y=trend["Workload Hours"],
                name="Workload (h)", marker_color="#0B6FA8",
            )
        )
        fig.add_trace(
            go.Scatter(
                x=trend["Month"], y=trend["TOTAL"].fillna(0),
                name="Shipments", mode="lines+markers",
                line=dict(color="#C15A0B", width=2.2),
                yaxis="y2",
            )
        )
        fig.update_layout(
            title="MONTHLY WORKLOAD & SHIPMENT TREND",
            yaxis=dict(title="Workload (h)", gridcolor="#E9EEF5"),
            yaxis2=dict(title="Shipments", overlaying="y", side="right", showgrid=False),
            legend=dict(orientation="h", y=1.03, x=0),
        )
        add_right_note(fig, "Trend by reporting month")
        style_chart(fig, 345, 70)
        st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})

    with r:
        office_workload = (
            f_bu.groupby("Office", as_index=False)["Total Workload"].sum()
            if not f_bu.empty else pd.DataFrame(columns=["Office", "Total Workload"])
        )
        office_workload["Hours"] = office_workload["Total Workload"] / 60
        fig = px.bar(
            office_workload,
            x="Hours",
            y="Office",
            orientation="h",
            text="Hours",
        )
        fig.update_traces(
            marker_color="#06183D",
            texttemplate="%{text:.1f}h",
            textposition="outside",
            cliponaxis=False,
        )
        fig.update_layout(title="TOTAL WORKLOAD BY OFFICE", showlegend=False)
        add_right_note(fig, "Office comparison")
        style_chart(fig, 345, 55)
        st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})


# ============================================================
# TAB 2 — SERVICE & ACTIVITY
# ============================================================
with tab_service:
    section_title("SERVICE VOLUME / WORKLOAD / FTE")
    spacer(8)

    s1, s2 = st.columns([1.2, 1], gap="large")

    with s1:
        fig = px.bar(
            service,
            x="Segment",
            y="Service_Volume",
            color="Segment",
            text="Service_Volume",
            category_orders={"Segment": SERVICE_ORDER},
            color_discrete_map=SERVICE_COLORS,
        )
        fig.update_traces(texttemplate="%{text:,.0f}", textposition="outside", cliponaxis=False)
        fig.update_layout(title="SERVICE VOLUME", showlegend=False)
        add_right_note(fig, "Core Volume by service")
        style_chart(fig, 350, 45)
        st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})

    with s2:
        detail = service[
            ["Segment", "Service_Volume", "Hours", "Share"]
        ].copy()
        detail["Required PIC FTE"] = service["Total_Workload"] / (FTE_MINUTES * months_for_workload)
        detail["MNG Allocated (h)"] = service["MNG Allocated Hours"]
        detail["Share"] = detail["Share"] * 100
        detail = detail.rename(
            columns={
                "Segment": "Service",
                "Service_Volume": "Volume",
                "Hours": "Workload (h)",
                "Share": "Workload Share (%)",
            }
        )
        st.dataframe(
            detail,
            hide_index=True,
            use_container_width=True,
            height=350,
            column_config={
                "Volume": st.column_config.NumberColumn("Volume", format="%.0f"),
                "Workload (h)": st.column_config.NumberColumn("Workload (h)", format="%.1f"),
                "Workload Share (%)": st.column_config.NumberColumn("Workload Share (%)", format="%.1f"),
                "Required PIC FTE": st.column_config.NumberColumn("Required PIC FTE", format="%.2f"),
                "MNG Allocated (h)": st.column_config.NumberColumn("MNG Allocated (h)", format="%.1f"),
            },
        )

    spacer(18)
    section_title("WORKLOAD BREAKDOWN — CORE / ANCILLARY / SUPPORTING / EXCEPTION")
    spacer(8)

    act = service[["Segment", "Core", "Ancillary", "Supporting", "Exception"]].copy()
    act_long = act.melt(
        id_vars="Segment",
        var_name="Activity",
        value_name="Minutes",
    )
    act_long["Hours"] = act_long["Minutes"] / 60

    a1, a2 = st.columns([1.25, 1], gap="large")
    with a1:
        fig = px.bar(
            act_long,
            x="Segment",
            y="Hours",
            color="Activity",
            barmode="stack",
            color_discrete_map=ACTIVITY_COLORS,
            category_orders={"Segment": SERVICE_ORDER, "Activity": list(ACTIVITY_COLS.keys())},
        )
        fig.update_layout(
            title="WORKLOAD HOURS BY SERVICE & ACTIVITY TYPE",
            legend=dict(orientation="v", x=1.02, y=1),
        )
        add_right_note(fig, "C + A + S + E")
        style_chart(fig, 370, 120)
        st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})

    with a2:
        activity_summary = (
            act_long.groupby("Activity", as_index=False)["Hours"].sum()
            .sort_values("Hours", ascending=False)
        )
        total_hours = activity_summary["Hours"].sum()
        activity_summary["Share (%)"] = np.where(
            total_hours != 0,
            activity_summary["Hours"] / total_hours * 100,
            0,
        )
        st.dataframe(
            activity_summary,
            hide_index=True,
            use_container_width=True,
            height=240,
            column_config={
                "Hours": st.column_config.NumberColumn("Workload (h)", format="%.1f"),
                "Share (%)": st.column_config.NumberColumn("Share (%)", format="%.1f"),
            },
        )
        st.markdown(
            "<div class='note-box'>"
            "<b>Manager allocation:</b> Actual MNG monthly capacity is allocated to AI/AE/OI/OE/TR/CC/WH "
            "proportionally to each service's share of Total Workload."
            "</div>",
            unsafe_allow_html=True,
        )

    spacer(16)
    section_title("MANAGEMENT TIME ALLOCATION BY SERVICE")
    spacer(8)
    mgr_plot = service[["Segment", "MNG Allocated Hours", "Share"]].copy()
    fig = px.bar(
        mgr_plot,
        x="Segment",
        y="MNG Allocated Hours",
        color="Segment",
        text="MNG Allocated Hours",
        color_discrete_map=SERVICE_COLORS,
        category_orders={"Segment": SERVICE_ORDER},
    )
    fig.update_traces(texttemplate="%{text:.1f}h", textposition="outside", cliponaxis=False)
    fig.update_layout(title="ALLOCATED MNG CAPACITY BY SERVICE", showlegend=False)
    add_right_note(fig, "Allocated by workload share")
    style_chart(fig, 340, 50)
    st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})


# ============================================================
# TAB 3 — OFFICE & CS PIC
# ============================================================
with tab_office_pic:
    section_title("OFFICE CAPACITY / WORKLOAD")
    spacer(8)

    office_bu = (
        f_bu.groupby("Office", as_index=False)["Total Workload"].sum()
        if not f_bu.empty else pd.DataFrame(columns=["Office", "Total Workload"])
    )
    office_bu["Workload (h)"] = office_bu["Total Workload"] / 60
    office_bu["Required PIC FTE (Calc)"] = office_bu["Total Workload"] / (FTE_MINUTES * months_for_workload)

    office_hc_detail = apply_om(hc)
    if month == "All" and not office_hc_detail.empty:
        om = office_hc_detail.groupby(["Office", "Month"], as_index=False).agg(
            **{
                "Actual HC": ("Total Actual HC", "sum"),
                "Actual PIC": ("Actual HC PIC", "sum"),
                "Required HC": ("Total Required HC", "sum"),
            }
        )
        oh = om.groupby("Office", as_index=False).agg(
            **{
                "Actual HC": ("Actual HC", "mean"),
                "Actual PIC": ("Actual PIC", "mean"),
                "Required HC": ("Required HC", "mean"),
            }
        )
    else:
        oh = office_hc_detail.groupby("Office", as_index=False).agg(
            **{
                "Actual HC": ("Total Actual HC", "sum"),
                "Actual PIC": ("Actual HC PIC", "sum"),
                "Required HC": ("Total Required HC", "sum"),
            }
        ) if not office_hc_detail.empty else pd.DataFrame(columns=["Office","Actual HC","Actual PIC","Required HC"])

    office_detail = pd.DataFrame({"Office": all_offices if office == "All Offices" else [office]})
    office_detail = office_detail.merge(office_bu, on="Office", how="left").merge(oh, on="Office", how="left")
    office_detail["Capacity Utilization"] = np.where(
        office_detail["Actual HC"].fillna(0) > 0,
        office_detail["Required HC"] / office_detail["Actual HC"],
        np.nan,
    )
    office_detail["Status"] = office_detail["Capacity Utilization"].map(status_from_util)

    st.dataframe(
        office_detail[
            ["Office", "Workload (h)", "Actual HC", "Actual PIC", "Required HC",
             "Required PIC FTE (Calc)", "Capacity Utilization", "Status"]
        ],
        hide_index=True,
        use_container_width=True,
        column_config={
            "Workload (h)": st.column_config.NumberColumn("Workload (h)", format="%.1f"),
            "Actual HC": st.column_config.NumberColumn("Actual HC", format="%.2f"),
            "Actual PIC": st.column_config.NumberColumn("Actual PIC", format="%.2f"),
            "Required HC": st.column_config.NumberColumn("Required HC", format="%.2f"),
            "Required PIC FTE (Calc)": st.column_config.NumberColumn("Required PIC FTE (Calc)", format="%.2f"),
            "Capacity Utilization": st.column_config.NumberColumn("Capacity Utilization", format="%.1%"),
        },
    )

    spacer(18)
    section_title("CS PIC FTE / WORKLOAD")
    spacer(8)

    pic_data = apply_om(cs_fte)
    if cs_pic != "All CS PIC":
        pic_data = pic_data[pic_data["CS PIC"].eq(cs_pic)]
    if not pic_data.empty:
        pic_summary = (
            pic_data.groupby(["Office", "CS PIC"], as_index=False)
            .agg(
                FTE=("FTE", "sum"),
                Workload_Min=("PIC Workload", "sum"),
            )
        )
        pic_summary["Workload (h)"] = pic_summary["Workload_Min"] / 60
        pic_summary = pic_summary.sort_values("FTE", ascending=False)

        p1, p2 = st.columns([1.2, 1], gap="large")
        with p1:
            fig = px.bar(
                pic_summary,
                x="CS PIC",
                y="FTE",
                color="Office",
                text="FTE",
            )
            fig.update_traces(texttemplate="%{text:.2f}", textposition="outside", cliponaxis=False)
            fig.update_layout(title="FTE BY CS PIC")
            add_right_note(fig, "Source: CS FTE")
            style_chart(fig, 360, 60)
            st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})
        with p2:
            st.dataframe(
                pic_summary[["Office", "CS PIC", "FTE", "Workload (h)"]],
                hide_index=True,
                use_container_width=True,
                height=360,
                column_config={
                    "FTE": st.column_config.NumberColumn("FTE", format="%.2f"),
                    "Workload (h)": st.column_config.NumberColumn("Workload (h)", format="%.1f"),
                },
            )
    else:
        st.info("No CS PIC FTE data for selected filters.")

    st.markdown(
        "<div class='note-box'>"
        "CS PIC workload shown here is calculated directly from CS FTE × 10,032 min/FTE. "
        "The workbook does not contain CS PIC → Service mapping, so service charts remain Office/Month-based."
        "</div>",
        unsafe_allow_html=True,
    )


# ============================================================
# TAB 4 — CUSTOMER
# ============================================================
with tab_customer:
    section_title("CUSTOMER PORTFOLIO / SHIPMENT VOLUME")
    spacer(8)

    cdata = f_cust.copy()
    if cdata.empty:
        st.info("No customer volume data for selected filters.")
    else:
        cust_summary = (
            cdata.groupby(["Office", "Customer"], as_index=False)["Shipment Volume"].sum()
            .sort_values("Shipment Volume", ascending=False)
        )
        top15 = cust_summary.head(15).sort_values("Shipment Volume")

        c1, c2 = st.columns([1.35, 1], gap="large")
        with c1:
            fig = px.bar(
                top15,
                x="Shipment Volume",
                y="Customer",
                orientation="h",
                color="Office",
                text="Shipment Volume",
            )
            fig.update_traces(texttemplate="%{text:,.0f}", textposition="outside", cliponaxis=False)
            fig.update_layout(title="TOP 15 CUSTOMERS BY SHIPMENT VOLUME")
            add_right_note(fig, "Selected filters")
            style_chart(fig, 440, 65)
            st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})

        with c2:
            st.dataframe(
                cust_summary,
                hide_index=True,
                use_container_width=True,
                height=440,
                column_config={
                    "Shipment Volume": st.column_config.NumberColumn("Shipment Volume", format="%.0f"),
                },
            )

        # customer monthly trend
        cm = cdata.groupby("Month", as_index=False)["Shipment Volume"].sum()
        cm["Sort"] = cm["Month"].map({m:i for i,m in enumerate(MONTH_ORDER)})
        cm = cm.sort_values("Sort")
        fig = px.line(cm, x="Month", y="Shipment Volume", markers=True, text="Shipment Volume")
        fig.update_traces(line_color="#0B6FA8", texttemplate="%{text:,.0f}", textposition="top center")
        fig.update_layout(title="CUSTOMER SHIPMENT TREND")
        add_right_note(fig, "Customer-filter responsive")
        style_chart(fig, 330, 55)
        st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})

    st.markdown(
        "<div class='note-box'>"
        "Customer filter cannot reduce Service Workload/FTE because the workbook does not contain a "
        "Customer → BU/Service workload mapping. It is applied to customer shipment views and Total Shipments KPI."
        "</div>",
        unsafe_allow_html=True,
    )


# ============================================================
# TAB 5 — YVF & OPERATIONAL DETAIL
# ============================================================
with tab_yvf_detail:
    section_title("YVF PROMOTION EFFECTIVENESS")
    spacer(8)

    y1, y2, y3 = st.columns(3, gap="large")
    with y1:
        kpi_card("YVF Bookings", f"{yvf_bookings:,.0f}", "Selected period")
    with y2:
        kpi_card("IFF Shipments", f"{iff_shipments:,.0f}", "Eligible denominator")
    with y3:
        kpi_card("YVF Booking Ratio", "N/A" if pd.isna(yvf_ratio) else f"{yvf_ratio:.1%}", "YVF ÷ IFF")

    spacer(16)

    if not f_yvf.empty:
        yplot = f_yvf.copy()
        yplot["Ratio %"] = yplot["YVF Ratio"] * 100
        fig = px.bar(
            yplot,
            x="Month",
            y="Ratio %",
            color="Office",
            barmode="group",
            text="Ratio %",
        )
        fig.update_traces(texttemplate="%{text:.1f}%", textposition="outside", cliponaxis=False)
        fig.update_layout(title="YVF BOOKING RATIO BY OFFICE / MONTH")
        add_right_note(fig, "YVF Bookings ÷ IFF Shipments")
        style_chart(fig, 340, 60)
        fig.update_yaxes(ticksuffix="%")
        st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})

    spacer(18)
    section_title("OPERATIONAL DETAIL — CORE / ANCILLARY / SUPPORTING / EXCEPTION")
    spacer(8)

    d1, d2 = st.columns(2, gap="large")

    with d1:
        detail_type = st.selectbox(
            "Detail type",
            ["Core Service", "Ancillary Service", "Supporting Activity", "Exception Handling"],
            key="detail_type",
        )

        if detail_type == "Core Service":
            dd = f_core.copy()
            cols = ["Office", "Scope", "Month", "Volume"]
        elif detail_type == "Ancillary Service":
            dd = f_anc.copy()
            cols = ["Office", "Scope", "Month", "Volume"]
        elif detail_type == "Supporting Activity":
            dd = f_sup.copy()
            cols = ["Office", "Scope", "Month", "Volume"]
        else:
            dd = f_exc.copy()
            cols = ["Office", "Code", "BU", "Criteria", "Detail", "Month", "Volume"]

        if dd.empty:
            st.info("No detail data for selected filters.")
        else:
            st.dataframe(
                dd[cols].sort_values("Volume", ascending=False),
                hide_index=True,
                use_container_width=True,
                height=430,
                column_config={
                    "Volume": st.column_config.NumberColumn("Volume", format="%.0f"),
                },
            )

    with d2:
        if not f_exc.empty:
            exc_summary = (
                f_exc.groupby(["BU", "Code", "Detail"], as_index=False)["Volume"].sum()
                .sort_values("Volume", ascending=False)
                .head(12)
            )
            fig = px.bar(
                exc_summary.sort_values("Volume"),
                x="Volume",
                y="Detail",
                orientation="h",
                color="BU",
                text="Volume",
            )
            fig.update_traces(texttemplate="%{text:.0f}", textposition="outside", cliponaxis=False)
            fig.update_layout(title="TOP EXCEPTION DRIVERS")
            add_right_note(fig, "Exception Handling Volume")
            style_chart(fig, 430, 80)
            st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})
        else:
            st.info("No exception data for selected filters.")


st.markdown(
    "<div class='small-note'>"
    "HC = Headcount | MNG = Manage / Management | PIC = Direct PIC | "
    "1 FTE = 8h/day × 95% efficiency × 22 days = 10,032 min/month"
    "</div>",
    unsafe_allow_html=True,
)
