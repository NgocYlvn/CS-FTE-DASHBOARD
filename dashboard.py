from pathlib import Path
import io
import re

import numpy as np
import pandas as pd
import plotly.express as px
import streamlit as st

# ============================================================
# APP CONFIGURATION
# ============================================================
st.set_page_config(
    page_title="Operations Performance Dashboard",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded",
)

APP_TITLE = "OPERATIONS PERFORMANCE DASHBOARD"

# 1 FTE = 8h/ngày x 95% hiệu suất x 22 ngày làm việc/tháng
FTE_HOURS_PER_DAY = 8
EFFICIENCY = 0.95
WORKING_DAYS = 22
FTE_MINUTES = FTE_HOURS_PER_DAY * 60 * EFFICIENCY * WORKING_DAYS  # 10,032 phút/tháng

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

MONTH_ORDER = [
    "Apr", "May", "Jun", "Jul", "Aug", "Sep",
    "Oct", "Nov", "Dec", "Jan", "Feb", "Mar",
]

# ============================================================
# STYLE
# ============================================================
st.markdown(
    """
    <style>
    :root {
        --navy:#083B82;
        --blue:#0B63CE;
        --orange:#ED6B21;
        --green:#169B62;
        --amber:#F59E0B;
        --red:#DC2626;
        --muted:#667085;
        --line:#DCE5F0;
        --panel:#FFFFFF;
        --page:#F7F9FC;
    }
    .stApp {background:var(--page);}
    [data-testid="stSidebar"] {
        background:linear-gradient(180deg,#073472 0%,#0B4D9B 100%);
        color:#FFFFFF;
    }
    section[data-testid="stSidebar"] label {
        color:#FFFFFF !important;
        font-weight:600 !important;
    }
    section[data-testid="stSidebar"] div[data-baseweb="select"] > div {
        background-color:#FFFFFF !important;
        color:#172033 !important;
        border-radius:10px !important;
    }
    section[data-testid="stSidebar"] div[data-baseweb="select"] span {
        color:#172033 !important;
    }
    section[data-testid="stSidebar"] div[data-baseweb="select"] input {
        color:#172033 !important;
        -webkit-text-fill-color:#172033 !important;
    }
    section[data-testid="stSidebar"] div[data-baseweb="select"] input::placeholder {
        color:#667085 !important;
        opacity:1 !important;
    }
    div[data-baseweb="popover"] ul,
    div[data-baseweb="menu"] {
        background:#FFFFFF !important;
    }
    div[data-baseweb="popover"] li,
    div[data-baseweb="menu"] li {
        color:#172033 !important;
    }
    section[data-testid="stSidebar"] div[data-baseweb="select"] svg {
        fill:#667085 !important;
        color:#667085 !important;
    }
    .block-container {max-width:1650px;padding-top:3.5rem;padding-bottom:2rem;}
    .dashboard-title {
        font-size:1.85rem;font-weight:850;color:var(--navy);
        margin-bottom:0.2rem;letter-spacing:-0.02em;
    }
    .dashboard-subtitle {color:var(--muted);font-size:0.82rem;margin-bottom:0.9rem;}
    .section-title {
        background:var(--navy);color:#FFFFFF;padding:0.55rem 0.8rem;
        border-radius:10px 10px 0 0;font-weight:800;margin-top:0.25rem;
    }
    .kpi-card {
        background:#FFFFFF;border:1px solid var(--line);border-radius:12px;
        min-height:142px;height:142px;display:flex;flex-direction:column;align-items:center;
        justify-content:center;box-shadow:0 2px 10px rgba(28,54,89,.05);
        text-align:center;padding:10px 12px;box-sizing:border-box;
    }
    .kpi-label {font-size:0.88rem;color:var(--navy);font-weight:800;margin-bottom:10px;line-height:1.15;min-height:1.15rem;display:flex;align-items:center;justify-content:center;}
    .kpi-value {font-size:2.15rem;font-weight:850;color:var(--blue);line-height:1.05;white-space:nowrap;}
    .kpi-note {font-size:0.72rem;color:var(--muted);margin-top:8px;line-height:1.2;min-height:0.86rem;}
    .orange .kpi-value {color:var(--orange);}
    .green .kpi-value {color:var(--green);}
    .amber .kpi-value {color:var(--amber);}
    .red .kpi-value {color:var(--red);}
    div[data-testid="stDataFrame"] {border:1px solid var(--line);border-radius:10px;overflow:hidden;}
    </style>
    """,
    unsafe_allow_html=True,
)

# ============================================================
# HELPERS
# ============================================================
def clean_text(value):
    if pd.isna(value):
        return ""
    return re.sub(r"\s+", " ", str(value)).strip()


def normalize_month(value):
    """Chuẩn hóa header tháng (Apr, Apr-26, ngày Excel...) về dạng viết tắt Apr."""
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return ""

    if isinstance(value, (pd.Timestamp,)):
        return value.strftime("%b")

    if hasattr(value, "strftime") and not isinstance(value, str):
        try:
            return value.strftime("%b")
        except Exception:
            pass

    s = clean_text(value)
    if not s:
        return ""

    try:
        dt = pd.to_datetime(s, errors="raise")
        return dt.strftime("%b")
    except Exception:
        pass

    abbr = s[:3].title()
    return abbr if abbr in MONTH_ORDER else ""


def safe_divide(a, b):
    if b is None or pd.isna(b) or float(b) == 0:
        return 0.0
    return float(a) / float(b)


def fmt_hours(minutes):
    return f"{minutes / 60:,.1f} h"


def kpi_card(label, value, note="", accent=""):
    note_html = f'<div class="kpi-note">{note}</div>' if note else '<div class="kpi-note">&nbsp;</div>'
    st.markdown(
        f"""
        <div class="kpi-card {accent}">
            <div class="kpi-label">{label}</div>
            <div class="kpi-value">{value}</div>
            {note_html}
        </div>
        """,
        unsafe_allow_html=True,
    )


def standard_chart_layout(fig, height=350):
    fig.update_layout(
        height=height,
        margin=dict(l=15, r=15, t=35, b=20),
        paper_bgcolor="white",
        plot_bgcolor="white",
        font=dict(color="#172033"),
        legend_title_text="",
        xaxis_title="",
        yaxis_title="",
        hoverlabel=dict(bgcolor="white"),
    )
    fig.update_xaxes(showgrid=False)
    fig.update_yaxes(gridcolor="#E9EEF5")
    return fig


def check_columns(actual_cols, expected_keywords, sheet_name):
    """
    Kiểm tra nhanh N cột đầu tiên có đúng vị trí như kỳ vọng không, để lỗi hiện rõ
    ngay khi cấu trúc sheet gốc thay đổi (thêm/xóa/đảo cột), thay vì âm thầm map sai.
    """
    cleaned = [clean_text(c).casefold() for c in actual_cols]
    for i, kw in enumerate(expected_keywords):
        if i >= len(cleaned):
            raise ValueError(
                f"Sheet '{sheet_name}' thiếu cột thứ {i + 1} (kỳ vọng chứa '{kw}')."
            )
        if kw not in cleaned[i]:
            raise ValueError(
                f"Sheet '{sheet_name}': cột thứ {i + 1} kỳ vọng chứa '{kw}' nhưng đọc "
                f"được '{actual_cols[i]}'. Cấu trúc file có thể đã thay đổi, vui lòng kiểm tra lại."
            )


# ============================================================
# LOAD SOURCE FILE (cached — dùng nút "Reload data" ở sidebar để làm mới)
# ============================================================
@st.cache_data(show_spinner=False)
def read_source_file():
    app_dir = Path(__file__).resolve().parent
    xlsx_files = [p for p in app_dir.rglob("*.xlsx") if not p.name.startswith("~$")]

    required = {"HC", "BU allocation", "CS FTE"}

    for p in sorted(xlsx_files, key=lambda x: x.stat().st_mtime, reverse=True):
        try:
            xl = pd.ExcelFile(p)
            sheet_names = set(xl.sheet_names)
            has_customer = any(s.startswith("Customer Volume") for s in xl.sheet_names)
            if required.issubset(sheet_names) and has_customer:
                return p.read_bytes(), p.name
        except Exception:
            continue

    return None, None


# ============================================================
# PARSERS
# ============================================================
@st.cache_data(show_spinner=False)
def parse_bu_allocation(file_bytes: bytes) -> pd.DataFrame:
    """
    Sheet 'BU allocation'. Row 1 = tiêu đề, Row 2 = header, Row 3 trở đi = data.
    Business rule:
        Số lô (Shipment Volume) theo BU = Core Volume
        Tổng thời gian theo BU          = Total Workload (min)
        Tỷ trọng theo BU                = Total Workload của BU / tổng Total Workload
    """
    df = pd.read_excel(io.BytesIO(file_bytes), sheet_name="BU allocation", header=1)

    expected_keywords = [
        "office", "month", "segment",
        "core volume", "core workload",
        "ancillary volume", "ancillary workload",
        "supporting volume", "supporting workload",
        "exception volume", "exception workload",
        "total workload", "workload share",
    ]
    check_columns(df.columns, expected_keywords, "BU allocation")

    df = df.iloc[:, :13].copy()
    df.columns = [
        "Office", "Month", "Segment",
        "Core Volume", "Core Workload",
        "Ancillary Volume", "Ancillary Workload",
        "Supporting Volume", "Supporting Workload",
        "Exception Volume", "Exception Workload",
        "Total Workload", "BU Workload Share (raw)",
    ]

    df["Office"] = df["Office"].map(clean_text)
    df["Segment"] = df["Segment"].map(clean_text)
    df["Month"] = df["Month"].map(normalize_month)

    numeric_cols = [
        "Core Volume", "Core Workload",
        "Ancillary Volume", "Ancillary Workload",
        "Supporting Volume", "Supporting Workload",
        "Exception Volume", "Exception Workload",
        "Total Workload", "BU Workload Share (raw)",
    ]
    for c in numeric_cols:
        df[c] = pd.to_numeric(df[c], errors="coerce")

    df = df[
        df["Office"].ne("")
        & df["Month"].isin(MONTH_ORDER)
        & df["Segment"].isin(SERVICE_ORDER)
    ].copy()

    df["Total Workload"] = df["Total Workload"].fillna(0)
    df["Core Volume"] = df["Core Volume"].fillna(0)
    df["Month"] = pd.Categorical(df["Month"], categories=MONTH_ORDER, ordered=True)

    return df.sort_values(["Month", "Office", "Segment"]).reset_index(drop=True)


@st.cache_data(show_spinner=False)
def parse_hc(file_bytes: bytes) -> pd.DataFrame:
    """Sheet 'HC'. Row 1 = tiêu đề, Row 2 = header, Row 3 trở đi = data."""
    df = pd.read_excel(io.BytesIO(file_bytes), sheet_name="HC", header=1)

    expected_keywords = ["office", "month"]
    check_columns(df.columns, expected_keywords, "HC")

    if df.shape[1] < 13:
        raise ValueError("Sheet 'HC' không đủ 13 cột dữ liệu.")

    df = df.iloc[:, :13].copy()
    df.columns = [
        "Office", "Month",
        "Approved HC Mgr", "Approved HC PIC", "Total Approved HC",
        "Actual HC Mgr", "Actual HC PIC", "Total Actual HC",
        "Required HC Mgr", "Required HC PIC", "Total Required HC",
        "HC Utilization", "HC Status",
    ]

    df["Office"] = df["Office"].map(clean_text)
    df["Month"] = df["Month"].map(normalize_month)
    df["HC Status"] = df["HC Status"].map(clean_text)

    numeric_cols = [
        "Approved HC Mgr", "Approved HC PIC", "Total Approved HC",
        "Actual HC Mgr", "Actual HC PIC", "Total Actual HC",
        "Required HC Mgr", "Required HC PIC", "Total Required HC",
        "HC Utilization",
    ]
    for c in numeric_cols:
        df[c] = pd.to_numeric(df[c], errors="coerce")

    df = df[df["Office"].ne("") & df["Month"].isin(MONTH_ORDER)].copy()
    return df.reset_index(drop=True)


@st.cache_data(show_spinner=False)
def parse_cs_fte(file_bytes: bytes) -> pd.DataFrame:
    """
    Sheet 'CS FTE'. Row 1 = tiêu đề, Row 2 = Office / CS PIC / Apr-26 ... Mar-27.
    Vector hóa bằng melt thay vì lặp từng ô để xử lý nhanh khi dữ liệu lớn dần.
    """
    df = pd.read_excel(io.BytesIO(file_bytes), sheet_name="CS FTE", header=1)

    if df.shape[1] < 3:
        return pd.DataFrame(columns=["Office", "CS PIC", "Month", "FTE", "PIC Workload"])

    office_col, pic_col = df.columns[0], df.columns[1]
    df[office_col] = df[office_col].map(clean_text)
    df[pic_col] = df[pic_col].map(clean_text)
    df = df[(df[office_col] != "") & (df[pic_col] != "")]

    month_cols = list(df.columns[2:])
    if not month_cols or df.empty:
        return pd.DataFrame(columns=["Office", "CS PIC", "Month", "FTE", "PIC Workload"])

    long_df = df.melt(
        id_vars=[office_col, pic_col],
        value_vars=month_cols,
        var_name="RawMonth",
        value_name="FTE",
    )
    long_df["Month"] = long_df["RawMonth"].map(normalize_month)
    long_df = long_df[long_df["Month"].isin(MONTH_ORDER)].copy()
    long_df["FTE"] = pd.to_numeric(long_df["FTE"], errors="coerce")
    long_df = long_df.dropna(subset=["FTE"])
    long_df = long_df.rename(columns={office_col: "Office", pic_col: "CS PIC"})
    long_df["PIC Workload"] = long_df["FTE"] * FTE_MINUTES

    return long_df[["Office", "CS PIC", "Month", "FTE", "PIC Workload"]].reset_index(drop=True)


@st.cache_data(show_spinner=False)
def parse_customer_lists(file_bytes: bytes) -> pd.DataFrame:
    """
    Gộp các sheet Customer Volume -> Office / Customer / Month / Shipment Volume.
    Sheet riêng theo Office (HAD/HAN/HLC/HCM...) được ưu tiên; sheet 'Customer
    Volume-N&S' chỉ dùng bổ sung cho các dòng chưa có, tránh đếm trùng.
    Vector hóa bằng melt thay vì lặp từng ô.
    """
    xl = pd.ExcelFile(io.BytesIO(file_bytes))
    candidate_sheets = [s for s in xl.sheet_names if s.startswith("Customer Volume")]

    frames = []
    for sheet in candidate_sheets:
        df = pd.read_excel(io.BytesIO(file_bytes), sheet_name=sheet, header=1)
        if df.shape[1] < 4:
            continue

        office_col = df.columns[1]
        customer_col = df.columns[2]
        df[office_col] = df[office_col].map(clean_text)
        df[customer_col] = df[customer_col].map(clean_text)
        df = df[(df[office_col] != "") & (df[customer_col] != "")]
        if df.empty:
            continue

        value_cols = [c for c in df.columns[3:] if clean_text(c).casefold() != "total"]
        if not value_cols:
            continue

        long_df = df.melt(
            id_vars=[office_col, customer_col],
            value_vars=value_cols,
            var_name="RawMonth",
            value_name="Customer Shipment Volume",
        )
        long_df["Month"] = long_df["RawMonth"].map(normalize_month)
        long_df = long_df[long_df["Month"].isin(MONTH_ORDER)].copy()
        long_df["Customer Shipment Volume"] = pd.to_numeric(
            long_df["Customer Shipment Volume"], errors="coerce"
        )
        long_df = long_df.dropna(subset=["Customer Shipment Volume"])
        long_df = long_df.rename(columns={office_col: "Office", customer_col: "Customer"})
        long_df["_priority"] = 1 if sheet.strip() == "Customer Volume-N&S" else 0

        frames.append(long_df[["Office", "Customer", "Month", "Customer Shipment Volume", "_priority"]])

    if not frames:
        return pd.DataFrame(columns=["Office", "Customer", "Month", "Customer Shipment Volume"])

    out = pd.concat(frames, ignore_index=True)
    out = out.sort_values("_priority")
    out = out.drop_duplicates(subset=["Office", "Customer", "Month"], keep="first")

    return out[["Office", "Customer", "Month", "Customer Shipment Volume"]].reset_index(drop=True)


@st.cache_data(show_spinner=False)
def parse_scope_detail(file_bytes: bytes, sheet_name: str) -> pd.DataFrame:
    """
    Đọc các sheet chi tiết theo mã: C (Core), A (Ancillary), S (Supporting).
    Cấu trúc: Office | Scope | Apr-26 ... Mar-27 | Total.
    Trả về DataFrame rỗng nếu sheet không tồn tại — các sheet này là bổ sung,
    không bắt buộc để dashboard chạy được.
    """
    try:
        df = pd.read_excel(io.BytesIO(file_bytes), sheet_name=sheet_name, header=1)
    except Exception:
        return pd.DataFrame(columns=["Office", "Scope", "Month", "Volume"])

    if df.shape[1] < 3:
        return pd.DataFrame(columns=["Office", "Scope", "Month", "Volume"])

    office_col, scope_col = df.columns[0], df.columns[1]
    df[office_col] = df[office_col].map(clean_text)
    df[scope_col] = df[scope_col].map(clean_text)
    df = df[(df[office_col] != "") & (df[scope_col] != "")]

    value_cols = [c for c in df.columns[2:] if clean_text(c).casefold() != "total"]
    if not value_cols or df.empty:
        return pd.DataFrame(columns=["Office", "Scope", "Month", "Volume"])

    long_df = df.melt(
        id_vars=[office_col, scope_col], value_vars=value_cols,
        var_name="RawMonth", value_name="Volume",
    )
    long_df["Month"] = long_df["RawMonth"].map(normalize_month)
    long_df = long_df[long_df["Month"].isin(MONTH_ORDER)].copy()
    long_df["Volume"] = pd.to_numeric(long_df["Volume"], errors="coerce")
    long_df = long_df.dropna(subset=["Volume"])
    long_df = long_df.rename(columns={office_col: "Office", scope_col: "Scope"})

    return long_df[["Office", "Scope", "Month", "Volume"]].reset_index(drop=True)


@st.cache_data(show_spinner=False)
def parse_exception_detail(file_bytes: bytes) -> pd.DataFrame:
    """
    Đọc sheet E (Exception Handling).
    Cấu trúc: Office | CODE | BU | Criteria | EXCEPTION DETAIL | Apr-26 ... Mar-27 | Total.
    """
    try:
        df = pd.read_excel(io.BytesIO(file_bytes), sheet_name="E", header=1)
    except Exception:
        return pd.DataFrame(columns=["Office", "Code", "BU", "Criteria", "Detail", "Month", "Volume"])

    if df.shape[1] < 6:
        return pd.DataFrame(columns=["Office", "Code", "BU", "Criteria", "Detail", "Month", "Volume"])

    id_cols = ["Office", "Code", "BU", "Criteria", "Detail"]
    df.columns = id_cols + list(df.columns[5:])

    for c in id_cols:
        df[c] = df[c].map(clean_text)
    df = df[df["Office"] != ""]

    value_cols = [c for c in df.columns[5:] if clean_text(c).casefold() != "total"]
    if not value_cols or df.empty:
        return pd.DataFrame(columns=["Office", "Code", "BU", "Criteria", "Detail", "Month", "Volume"])

    long_df = df.melt(id_vars=id_cols, value_vars=value_cols, var_name="RawMonth", value_name="Volume")
    long_df["Month"] = long_df["RawMonth"].map(normalize_month)
    long_df = long_df[long_df["Month"].isin(MONTH_ORDER)].copy()
    long_df["Volume"] = pd.to_numeric(long_df["Volume"], errors="coerce")
    long_df = long_df.dropna(subset=["Volume"])

    return long_df[["Office", "Code", "BU", "Criteria", "Detail", "Month", "Volume"]].reset_index(drop=True)


# ============================================================
# LOAD DATA
# ============================================================
source_bytes, source_name = read_source_file()

if source_bytes is None:
    st.error(
        "Không tìm thấy file Excel có đủ các sheet chính: "
        "HC, BU allocation, CS FTE và Customer Volume."
    )
    st.info("Đặt file Excel cùng thư mục/repository với file .py rồi Reboot app.")
    st.stop()

try:
    hc = parse_hc(source_bytes)
    bu = parse_bu_allocation(source_bytes)
    cs_fte = parse_cs_fte(source_bytes)
    customer = parse_customer_lists(source_bytes)
except Exception as exc:
    st.error("Không thể đọc dữ liệu nguồn. Vui lòng kiểm tra lại cấu trúc file Excel.")
    st.exception(exc)
    st.stop()

# Các sheet chi tiết theo mã (C/A/S/E) là dữ liệu bổ sung — nếu thiếu hoặc lỗi,
# dashboard vẫn chạy bình thường, chỉ ẩn phần "Chi tiết theo mã".
try:
    core_detail = parse_scope_detail(source_bytes, "C")
    ancillary_detail = parse_scope_detail(source_bytes, "A")
    supporting_detail = parse_scope_detail(source_bytes, "S")
    exception_detail = parse_exception_detail(source_bytes)
except Exception:
    core_detail = pd.DataFrame(columns=["Office", "Scope", "Month", "Volume"])
    ancillary_detail = pd.DataFrame(columns=["Office", "Scope", "Month", "Volume"])
    supporting_detail = pd.DataFrame(columns=["Office", "Scope", "Month", "Volume"])
    exception_detail = pd.DataFrame(columns=["Office", "Code", "BU", "Criteria", "Detail", "Month", "Volume"])

# ============================================================
# SIDEBAR FILTERS
# ============================================================
st.sidebar.markdown("## 📊 CS Division")
st.sidebar.markdown(
    "<div style='color:#D8E5F8;font-size:14px;margin-top:-8px;margin-bottom:14px;'>Workload & Capacity Dashboard</div>",
    unsafe_allow_html=True,
)
st.sidebar.markdown("---")


def reset_child_filters():
    """Reset CS PIC / Customer khi Office hoặc Month thay đổi."""
    st.session_state["filter_cs_pic"] = "All CS PIC"
    st.session_state["filter_customer"] = "All Customers"


all_offices = sorted(
    set(hc.get("Office", pd.Series(dtype=str)).dropna().astype(str))
    | set(bu["Office"].dropna().astype(str))
    | set(cs_fte.get("Office", pd.Series(dtype=str)).dropna().astype(str))
    | set(customer.get("Office", pd.Series(dtype=str)).dropna().astype(str))
)

# 1) Office
office = st.sidebar.selectbox(
    "Office",
    ["All Offices"] + all_offices,
    key="filter_office",
    on_change=reset_child_filters,
)

# 2) Month
available_month_set = (
    set(hc.get("Month", pd.Series(dtype=str)).dropna().astype(str))
    | set(bu.get("Month", pd.Series(dtype=str)).dropna().astype(str))
    | set(cs_fte.get("Month", pd.Series(dtype=str)).dropna().astype(str))
    | set(customer.get("Month", pd.Series(dtype=str)).dropna().astype(str))
)
available_months = [m for m in MONTH_ORDER if m in available_month_set]
month_options = ["All"] + available_months

month = st.sidebar.selectbox(
    "Month",
    month_options,
    index=0,
    key="filter_month",
    on_change=reset_child_filters,
)

selected_month_count = len(available_months) if month == "All" else 1
selected_month_count = max(selected_month_count, 1)

# 3) CS PIC (phụ thuộc Office + Month)
if cs_fte.empty:
    pic_scope = cs_fte.copy()
elif month == "All":
    pic_scope = cs_fte.copy()
else:
    pic_scope = cs_fte[cs_fte["Month"].eq(month)].copy()

if office != "All Offices" and not pic_scope.empty:
    pic_scope = pic_scope[pic_scope["Office"].eq(office)]

pic_options = sorted(pic_scope["CS PIC"].dropna().unique().tolist()) if not pic_scope.empty else []
pic_select_options = ["All CS PIC"] + pic_options

if "filter_cs_pic" in st.session_state and st.session_state["filter_cs_pic"] not in pic_select_options:
    st.session_state["filter_cs_pic"] = "All CS PIC"

cs_pic = st.sidebar.selectbox("CS PIC", pic_select_options, key="filter_cs_pic")

# 4) Customer
if customer.empty:
    cust_scope = customer.copy()
elif month == "All":
    cust_scope = customer.copy()
else:
    cust_scope = customer[customer["Month"].eq(month)].copy()

if office != "All Offices" and not cust_scope.empty:
    cust_scope = cust_scope[cust_scope["Office"].eq(office)]

customer_options = sorted(cust_scope["Customer"].dropna().unique().tolist()) if not cust_scope.empty else []
customer_select_options = ["All Customers"] + customer_options

if "filter_customer" in st.session_state and st.session_state["filter_customer"] not in customer_select_options:
    st.session_state["filter_customer"] = "All Customers"

selected_customer = st.sidebar.selectbox("Customer", customer_select_options, key="filter_customer")

st.sidebar.markdown("---")
if st.sidebar.button("🔄 Reload data"):
    st.cache_data.clear()
    st.rerun()
st.sidebar.caption(f"📄 Data source: {source_name}")

# ============================================================
# FILTER / CALCULATION MODEL
# ============================================================
if month == "All":
    base_bu_month = bu.copy()
else:
    base_bu_month = bu[bu["Month"].astype(str).eq(month)].copy()

filtered_bu = base_bu_month.copy()
if office != "All Offices":
    filtered_bu = filtered_bu[filtered_bu["Office"].eq(office)].copy()

if month == "All":
    filtered_hc = hc.copy()
else:
    filtered_hc = hc[hc["Month"].eq(month)].copy()

if office != "All Offices":
    filtered_hc = filtered_hc[filtered_hc["Office"].eq(office)].copy()

# Filter Customer chỉ áp dụng cho Customer Shipment Volume, không làm giảm workload/FTE.
filtered_customer = cust_scope.copy()
if selected_customer != "All Customers" and not filtered_customer.empty:
    filtered_customer = filtered_customer[filtered_customer["Customer"].eq(selected_customer)]

network_base_workload = float(base_bu_month["Total Workload"].sum())
selected_base_workload = float(filtered_bu["Total Workload"].sum())

# --- Phân bổ theo CS PIC ---
# Dữ liệu nguồn không có workload theo từng BU cho mỗi CS PIC, chỉ có FTE theo
# Office/Month. Khi lọc theo 1 CS PIC cụ thể, workload của Office được ƯỚC TÍNH
# phân bổ theo tỷ trọng FTE của CS PIC đó trong tổng FTE của Office/Month.
pic_workload_minutes = None
pic_fte_value = None
pic_share = None

if cs_pic != "All CS PIC" and not pic_scope.empty:
    selected_pic_rows = pic_scope[pic_scope["CS PIC"].eq(cs_pic)]
    pic_fte_value = float(selected_pic_rows["FTE"].sum())
    pic_workload_minutes = float(selected_pic_rows["PIC Workload"].sum())
    office_pic_total = float(pic_scope["PIC Workload"].sum())
    pic_share = safe_divide(pic_workload_minutes, office_pic_total)

    filtered_bu["Total Workload"] = filtered_bu["Total Workload"] * pic_share
    filtered_bu["Core Volume"] = filtered_bu["Core Volume"] * pic_share
    selected_base_workload = float(filtered_bu["Total Workload"].sum())

# Tổng hợp Số lô + Thời gian theo từng BU (AI/AE/OI/OE/TR/CC/WH)
service = (
    filtered_bu.groupby("Segment", as_index=False)
    .agg(Shipment_Volume=("Core Volume", "sum"), Base_Workload=("Total Workload", "sum"))
)
service = (
    pd.DataFrame({"Segment": SERVICE_ORDER})
    .merge(service, on="Segment", how="left")
    .fillna(0)
)

service["Service Share"] = np.where(
    service["Base_Workload"].sum() > 0,
    service["Base_Workload"] / service["Base_Workload"].sum(),
    0,
)
service["Service"] = service["Segment"].map(SERVICE_LABELS)

period_capacity_minutes = FTE_MINUTES * selected_month_count
required_fte = safe_divide(selected_base_workload, period_capacity_minutes)
service["Required FTE"] = service["Base_Workload"] / period_capacity_minutes

total_shipments = float(service["Shipment_Volume"].sum())

# --- HC KPI ---
hc_valid = filtered_hc[
    filtered_hc["Total Actual HC"].notna()
    | filtered_hc["Total Required HC"].notna()
    | filtered_hc["Total Approved HC"].notna()
].copy()

if hc_valid.empty:
    approved_hc = actual_hc = required_hc_total = hc_utilization = np.nan
    hc_status = "No data"
else:
    if month == "All":
        hc_monthly = (
            hc_valid.groupby("Month", as_index=False)
            .agg(
                Approved_HC=("Total Approved HC", "sum"),
                Actual_HC=("Total Actual HC", "sum"),
                Required_HC=("Total Required HC", "sum"),
            )
        )
        approved_hc = float(hc_monthly["Approved_HC"].mean())
        actual_hc = float(hc_monthly["Actual_HC"].mean())
        required_hc_total = float(hc_monthly["Required_HC"].mean())
    else:
        approved_hc = float(hc_valid["Total Approved HC"].sum())
        actual_hc = float(hc_valid["Total Actual HC"].sum())
        required_hc_total = float(hc_valid["Total Required HC"].sum())

    hc_utilization = safe_divide(required_hc_total, actual_hc) if actual_hc else np.nan

    if pd.isna(hc_utilization):
        hc_status = "No data"
    elif hc_utilization > 1.00:
        hc_status = "Overload"
    elif hc_utilization > 0.95:
        hc_status = "High Load"
    elif hc_utilization >= 0.90:
        hc_status = "Balanced"
    else:
        hc_status = "Low Load"

# --- HC status theo từng Office (phục vụ banner cảnh báo) ---
def _office_status(u):
    if pd.isna(u):
        return "No data"
    elif u > 1.00:
        return "Overload"
    elif u > 0.95:
        return "High Load"
    elif u >= 0.90:
        return "Balanced"
    else:
        return "Low Load"


if hc_valid.empty:
    office_hc_status = pd.DataFrame(columns=["Office", "Utilization", "Status"])
else:
    if month == "All":
        office_month = (
            hc_valid.groupby(["Office", "Month"], as_index=False)
            .agg(Actual=("Total Actual HC", "sum"), Required=("Total Required HC", "sum"))
        )
        office_hc_status = (
            office_month.groupby("Office", as_index=False)
            .agg(Actual=("Actual", "mean"), Required=("Required", "mean"))
        )
    else:
        office_hc_status = (
            hc_valid.groupby("Office", as_index=False)
            .agg(Actual=("Total Actual HC", "sum"), Required=("Total Required HC", "sum"))
        )
    office_hc_status["Utilization"] = office_hc_status.apply(
        lambda r: safe_divide(r["Required"], r["Actual"]) if r["Actual"] else np.nan, axis=1
    )
    office_hc_status["Status"] = office_hc_status["Utilization"].map(_office_status)

overloaded_offices = office_hc_status[office_hc_status["Status"].eq("Overload")]["Office"].tolist()

# ============================================================
# HEADER
# ============================================================
st.markdown(f'<div class="dashboard-title">{APP_TITLE}</div>', unsafe_allow_html=True)

filter_summary = (
    f"Month: {month} · Office: {office} · CS PIC: {cs_pic} · Customer: {selected_customer}"
)
st.markdown(f'<div class="dashboard-subtitle">{filter_summary}</div>', unsafe_allow_html=True)

if cs_pic != "All CS PIC":
    st.caption(
        f"⚠️ Workload của CS PIC **{cs_pic}** là ước tính, phân bổ theo tỷ trọng FTE "
        f"({pic_fte_value:.2f} FTE) trên tổng FTE của Office/Month đang chọn — "
        "dữ liệu nguồn chưa có workload theo từng BU cho mỗi CS PIC."
    )

# --- Banner cảnh báo Office đang Overload ---
if overloaded_offices:
    st.error(f"⚠️ Đang quá tải (Overload): {', '.join(overloaded_offices)}")

# ============================================================
# KPI ROW (gộp Volume/Workload/FTE + Capacity vào 1 hàng)
# ============================================================
k1, k2, k3, k4, k5 = st.columns(5, gap="small")
with k1:
    kpi_card("Shipment Volume", f"{total_shipments:,.0f}", "")
with k2:
    kpi_card("Total Workload", fmt_hours(selected_base_workload), "")
with k3:
    kpi_card("Required FTE", f"{required_fte:.2f}", "", "amber")
with k4:
    util_text = "—" if pd.isna(hc_utilization) else f"{hc_utilization:.0%}"
    kpi_card("Capacity Utilization", util_text, "", "amber")
with k5:
    status_accent = {"Overload": "red", "High Load": "orange", "Balanced": "green", "Low Load": ""}.get(hc_status, "")
    kpi_card("Capacity Status", hc_status, "", status_accent)


def _hc_value(v):
    return "—" if pd.isna(v) else f"{v:,.2f}".rstrip("0").rstrip(".")


st.caption(
    f"Headcount: Approved {_hc_value(approved_hc)} · Actual {_hc_value(actual_hc)} · "
    f"Required {_hc_value(required_hc_total)}"
)

# ============================================================
# SHIPMENT VOLUME + SERVICE SHARE
# ============================================================
st.markdown("<br>", unsafe_allow_html=True)
shipment_area, share_area = st.columns([1.8, 1.0], gap="medium")

with shipment_area:
    st.markdown('<div class="section-title">SHIPMENT VOLUME & SHARE BY SERVICE</div>', unsafe_allow_html=True)

    volume_plot = service.copy()
    shipment_total = float(volume_plot["Shipment_Volume"].sum())
    volume_plot["Share"] = np.where(shipment_total > 0, volume_plot["Shipment_Volume"] / shipment_total, 0)

    detail_col, chart_col = st.columns([0.34, 0.66], gap="small")

    with detail_col:
        shipment_detail = volume_plot[["Segment", "Shipment_Volume", "Share"]].rename(
            columns={"Segment": "Service", "Shipment_Volume": "Volume", "Share": "Share (%)"}
        )
        shipment_detail["Share (%)"] = shipment_detail["Share (%)"] * 100

        total_row = pd.DataFrame([{
            "Service": "TOTAL",
            "Volume": shipment_total,
            "Share (%)": 100.0 if shipment_total > 0 else 0.0,
        }])
        shipment_detail = pd.concat([shipment_detail, total_row], ignore_index=True)

        st.dataframe(
            shipment_detail,
            hide_index=True,
            use_container_width=True,
            height=340,
            column_config={
                "Service": st.column_config.TextColumn("Service"),
                "Volume": st.column_config.NumberColumn("Volume", format="%.0f"),
                "Share (%)": st.column_config.NumberColumn("Share (%)", format="%.1f%%"),
            },
        )

    with chart_col:
        fig = px.bar(
            volume_plot, x="Segment", y="Shipment_Volume", text="Shipment_Volume",
            category_orders={"Segment": SERVICE_ORDER},
        )
        fig.update_traces(
            marker_color="#0B63CE", texttemplate="%{text:,.0f}",
            textposition="outside", cliponaxis=False, width=0.62,
        )
        max_volume = volume_plot["Shipment_Volume"].max()
        if pd.notna(max_volume) and max_volume > 0:
            fig.update_yaxes(range=[0, max_volume * 1.15])
        standard_chart_layout(fig, 340)
        fig.update_yaxes(rangemode="tozero")
        st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})

with share_area:
    st.markdown('<div class="section-title">SERVICE SHARE OF TOTAL TIME</div>', unsafe_allow_html=True)

    pie = service[service["Base_Workload"] > 0].copy()
    if pie.empty:
        st.info("No workload data available for selected filters.")
    else:
        fig = px.pie(
            pie, names="Segment", values="Base_Workload", hole=0.58,
            category_orders={"Segment": SERVICE_ORDER},
        )
        fig.update_traces(textposition="inside", textinfo="label+percent")
        fig.update_layout(height=340, margin=dict(l=10, r=10, t=20, b=20), paper_bgcolor="white", showlegend=False)
        st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})

# ============================================================
# WORKLOAD TREND BY MONTH + TOTAL WORKLOAD BY SERVICE (cùng hàng)
# ============================================================
service_hours = service.copy()
service_hours["Hours"] = service_hours["Base_Workload"] / 60

show_trend = False
trend = None
if month == "All":
    trend = (
        filtered_bu.groupby("Month", as_index=False)["Total Workload"].sum()
        .set_index("Month")
        .reindex(available_months)
        .reset_index()
        .rename(columns={"index": "Month"})
    )
    trend["Total Workload"] = trend["Total Workload"].fillna(0)
    trend["Hours"] = trend["Total Workload"] / 60
    show_trend = trend["Hours"].sum() > 0

st.markdown("<br>", unsafe_allow_html=True)

if show_trend:
    trend_col, service_hours_col = st.columns([1, 1], gap="medium")

    with trend_col:
        st.markdown('<div class="section-title">WORKLOAD TREND BY MONTH</div>', unsafe_allow_html=True)
        fig = px.line(trend, x="Month", y="Hours", markers=True)
        fig.update_traces(line_color="#0B63CE", marker=dict(size=7, color="#0B63CE"))
        standard_chart_layout(fig, 300)
        fig.update_yaxes(rangemode="tozero")
        st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})

    with service_hours_col:
        st.markdown('<div class="section-title">TOTAL WORKLOAD BY SERVICE (HOURS)</div>', unsafe_allow_html=True)
        fig = px.bar(
            service_hours, x="Segment", y="Hours", text="Hours",
            category_orders={"Segment": SERVICE_ORDER},
        )
        fig.update_traces(
            marker_color="#169B62", texttemplate="%{text:,.0f}h",
            textposition="outside", cliponaxis=False, width=0.62,
        )
        max_hours_service = service_hours["Hours"].max()
        if pd.notna(max_hours_service) and max_hours_service > 0:
            fig.update_yaxes(range=[0, max_hours_service * 1.15])
        standard_chart_layout(fig, 300)
        fig.update_yaxes(rangemode="tozero")
        st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})
else:
    st.markdown('<div class="section-title">TOTAL WORKLOAD BY SERVICE (HOURS)</div>', unsafe_allow_html=True)
    fig = px.bar(
        service_hours, x="Segment", y="Hours", text="Hours",
        category_orders={"Segment": SERVICE_ORDER},
    )
    fig.update_traces(
        marker_color="#169B62", texttemplate="%{text:,.0f}h",
        textposition="outside", cliponaxis=False, width=0.62,
    )
    max_hours_service = service_hours["Hours"].max()
    if pd.notna(max_hours_service) and max_hours_service > 0:
        fig.update_yaxes(range=[0, max_hours_service * 1.15])
    standard_chart_layout(fig, 260)
    fig.update_yaxes(rangemode="tozero")
    st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})

# ============================================================
# OFFICE / PIC WORKLOAD
# ============================================================
st.markdown("<br>", unsafe_allow_html=True)
workload_area = st.container()

with workload_area:
    if cs_pic != "All CS PIC":
        title = "SELECTED CS PIC WORKLOAD"
    elif office != "All Offices":
        title = f"WORKLOAD - {office}"
    else:
        title = "WORKLOAD BY OFFICE"
    st.markdown(f'<div class="section-title">{title}</div>', unsafe_allow_html=True)

    if cs_pic == "All CS PIC":
        office_workload = (
            filtered_bu.groupby("Office", as_index=False)["Total Workload"].sum()
            .rename(columns={"Total Workload": "Base Workload"})
        )

        # Hiện đầy đủ tất cả VP đã biết, kể cả VP chưa có dữ liệu (Hours = 0),
        # thay vì chỉ hiện VP có workload > 0.
        relevant_offices = all_offices if office == "All Offices" else [office]
        office_workload = (
            pd.DataFrame({"Office": relevant_offices})
            .merge(office_workload, on="Office", how="left")
            .fillna(0)
        )
        office_workload["Hours"] = office_workload["Base Workload"] / 60

        if office_workload.empty:
            st.info("No workload data available for selected filters.")
        else:
            office_workload = office_workload.sort_values("Hours", ascending=True)
            fig = px.bar(office_workload, x="Hours", y="Office", orientation="h", text="Hours")
            fig.update_traces(
                marker_color="#0B63CE", texttemplate="%{text:,.1f}h",
                textposition="outside", cliponaxis=False, width=0.42,
            )
            max_hours = office_workload["Hours"].max()
            if pd.notna(max_hours) and max_hours > 0:
                fig.update_xaxes(range=[0, max_hours * 1.18])
            chart_height = 260 if len(office_workload) == 1 else max(260, 60 + len(office_workload) * 34)
            standard_chart_layout(fig, chart_height)
            st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})
    else:
        pic_display = pic_scope[pic_scope["CS PIC"].eq(cs_pic)].copy()
        if office != "All Offices":
            pic_display = pic_display[pic_display["Office"].eq(office)]

        if month == "All" and not pic_display.empty:
            pic_display = (
                pic_display.groupby(["Office", "CS PIC"], as_index=False)
                .agg(**{"PIC Workload": ("PIC Workload", "mean")})
            )

        if pic_display.empty:
            st.info("No workload data available for selected filters.")
        else:
            pic_display["Hours"] = pic_display["PIC Workload"] / 60
            pic_display = pic_display.sort_values("Hours", ascending=True)
            fig = px.bar(pic_display, x="Hours", y="CS PIC", orientation="h", text="Hours")
            fig.update_traces(
                marker_color="#169B62", texttemplate="%{text:.1f}h",
                textposition="outside", cliponaxis=False,
            )
            standard_chart_layout(fig, 340)
            st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})

# ============================================================
# CS PIC FTE TABLE / CUSTOMER VOLUME
# ============================================================
st.markdown("<br>", unsafe_allow_html=True)
left, right = st.columns([1.25, 1], gap="medium")

with left:
    st.markdown('<div class="section-title">CS PIC FTE & WORKLOAD</div>', unsafe_allow_html=True)

    if month == "All":
        pic_table = cs_fte.copy()
    else:
        pic_table = cs_fte[cs_fte["Month"].eq(month)].copy()

    if office != "All Offices":
        pic_table = pic_table[pic_table["Office"].eq(office)]
    if cs_pic != "All CS PIC":
        pic_table = pic_table[pic_table["CS PIC"].eq(cs_pic)]

    if month == "All" and not pic_table.empty:
        pic_table = (
            pic_table.groupby(["Office", "CS PIC"], as_index=False)
            .agg(FTE=("FTE", "mean"), **{"PIC Workload": ("PIC Workload", "mean")})
        )

    if pic_table.empty:
        st.info("No CS PIC FTE data available for selected filters.")
    else:
        pic_table["Workload Hours"] = pic_table["PIC Workload"] / 60
        pic_table["Capacity Status"] = np.select(
            [pic_table["FTE"] > 1.05, pic_table["FTE"] >= 0.95],
            ["Overload", "Near Full"],
            default="Available",
        )
        st.dataframe(
            pic_table[["Office", "CS PIC", "FTE", "Workload Hours", "Capacity Status"]]
            .sort_values(["Office", "FTE"], ascending=[True, False]),
            hide_index=True,
            use_container_width=True,
            height=335,
            column_config={
                "FTE": st.column_config.NumberColumn("FTE", format="%.2f"),
                "Workload Hours": st.column_config.NumberColumn("Workload Hours", format="%.1f h"),
            },
        )

with right:
    st.markdown('<div class="section-title">CUSTOMER SHIPMENT VOLUME</div>', unsafe_allow_html=True)

    cust_plot = filtered_customer.copy()
    if cust_plot.empty:
        st.info("No customer volume data available for selected filters.")
    else:
        cust_plot = (
            cust_plot.groupby(["Office", "Customer"], as_index=False)["Customer Shipment Volume"].sum()
            .sort_values("Customer Shipment Volume", ascending=False)
            .head(15)
        )
        fig = px.bar(
            cust_plot.sort_values("Customer Shipment Volume"),
            x="Customer Shipment Volume", y="Customer", orientation="h", text="Customer Shipment Volume",
        )
        fig.update_traces(marker_color="#0B63CE", texttemplate="%{text:.0f}", textposition="outside", cliponaxis=False)
        standard_chart_layout(fig, 335)
        st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})

# ============================================================
# SERVICE WORKLOAD DETAIL (thu gọn trong expander — dùng khi cần phân tích sâu)
# ============================================================
st.markdown("<br>", unsafe_allow_html=True)

with st.expander("📋 SERVICE WORKLOAD DETAIL — Xem chi tiết theo từng BU"):
    service_table = service[["Segment", "Service", "Shipment_Volume", "Base_Workload", "Service Share", "Required FTE"]].copy()
    service_table["Total Workload (h)"] = service_table["Base_Workload"] / 60
    service_table = service_table[["Segment", "Service", "Shipment_Volume", "Total Workload (h)", "Service Share", "Required FTE"]]

    st.dataframe(
        service_table,
        hide_index=True,
        use_container_width=True,
        column_config={
            "Shipment_Volume": st.column_config.NumberColumn("Shipment Volume", format="%.0f"),
            "Total Workload (h)": st.column_config.NumberColumn("Total Workload (h)", format="%.1f"),
            "Service Share": st.column_config.NumberColumn("% of Total Time", format="%.1f%%"),
            "Required FTE": st.column_config.NumberColumn("Required FTE", format="%.2f"),
        },
    )

# ============================================================
# CHI TIẾT THEO MÃ (Core / Ancillary / Supporting / Exception)
# Nguồn: sheet C, A, S, E — chỉ hiển thị volume theo mã, không tính FTE
# (các sheet này không có dữ liệu thời gian xử lý theo từng mã).
# ============================================================
has_scope_detail = not (core_detail.empty and ancillary_detail.empty and supporting_detail.empty and exception_detail.empty)

if has_scope_detail:
    st.markdown("<br>", unsafe_allow_html=True)

    with st.expander("🔎 CHI TIẾT THEO MÃ — Core / Ancillary / Supporting / Exception"):
        def _apply_office_month(df, office_val, month_val):
            out = df.copy()
            if office_val != "All Offices" and not out.empty:
                out = out[out["Office"].eq(office_val)]
            if month_val != "All" and not out.empty:
                out = out[out["Month"].eq(month_val)]
            return out

        def _render_scope_tab(df, label):
            scoped = _apply_office_month(df, office, month)
            if scoped.empty:
                st.info(f"Không có dữ liệu {label} cho bộ lọc hiện tại.")
                return

            summary = (
                scoped.groupby("Scope", as_index=False)["Volume"].sum()
                .sort_values("Volume", ascending=False)
                .head(15)
            )

            chart_col, table_col = st.columns([1.4, 1], gap="medium")

            with chart_col:
                fig = px.bar(
                    summary.sort_values("Volume"),
                    x="Volume", y="Scope", orientation="h", text="Volume",
                )
                fig.update_traces(marker_color="#0B63CE", texttemplate="%{text:,.0f}", textposition="outside", cliponaxis=False)
                standard_chart_layout(fig, min(340, 60 + len(summary) * 22))
                st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})

            with table_col:
                st.dataframe(
                    summary.rename(columns={"Scope": label, "Volume": "Volume"}),
                    hide_index=True,
                    use_container_width=True,
                    height=min(340, 60 + len(summary) * 22),
                    column_config={"Volume": st.column_config.NumberColumn("Volume", format="%.0f")},
                )

        tab_core, tab_ancillary, tab_supporting, tab_exception = st.tabs(
            ["Core", "Ancillary", "Supporting", "Exception"]
        )

        with tab_core:
            _render_scope_tab(core_detail, "Scope")
        with tab_ancillary:
            _render_scope_tab(ancillary_detail, "Scope")
        with tab_supporting:
            _render_scope_tab(supporting_detail, "Scope")
        with tab_exception:
            exc_scoped = _apply_office_month(exception_detail, office, month)
            if exc_scoped.empty:
                st.info("Không có dữ liệu Exception cho bộ lọc hiện tại.")
            else:
                exc_summary = (
                    exc_scoped.groupby(["Code", "BU", "Criteria", "Detail"], as_index=False)["Volume"].sum()
                    .sort_values("Volume", ascending=False)
                )

                exc_chart_col, exc_table_col = st.columns([1.4, 1], gap="medium")

                with exc_chart_col:
                    fig = px.bar(
                        exc_summary.head(15).sort_values("Volume"),
                        x="Volume", y="Code", orientation="h", text="Volume",
                    )
                    fig.update_traces(marker_color="#DC2626", texttemplate="%{text:,.0f}", textposition="outside", cliponaxis=False)
                    standard_chart_layout(fig, min(340, 60 + min(len(exc_summary), 15) * 22))
                    st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})

                with exc_table_col:
                    st.dataframe(
                        exc_summary,
                        hide_index=True,
                        use_container_width=True,
                        height=min(340, 60 + min(len(exc_summary), 15) * 22),
                        column_config={"Volume": st.column_config.NumberColumn("Volume", format="%.0f")},
                    )
