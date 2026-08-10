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
APP_VERSION = "v3.0-AUDITED"
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
# Bộ màu cố định cho từng BU — dùng nhất quán ở mọi biểu đồ (bar + pie) để
# người xem không phải "học lại" màu mỗi khi chuyển sang biểu đồ khác.
# Dựa theo bộ nhận diện thương hiệu Yusen Logistics (5 màu chính thức: Dark Blue,
# Light Blue, Green, Orange, Yellow); bổ sung 2 màu trung tính (navy đậm, xám xanh)
# cho đủ 7 BU vì thương hiệu chỉ có 5 màu.
SEGMENT_COLORS = {
    "AI": "#00B9F2",  # Yusen Light Blue
    "AE": "#45BD8C",  # Yusen Green
    "OI": "#FF6D10",  # Yusen Orange
    "OE": "#FFC933",  # Yusen Yellow
    "TR": "#06183D",  # Yusen Dark Blue
    "CC": "#0074A6",  # xanh dương đậm (bổ sung, cùng họ Light Blue)
    "WH": "#94A3B8",  # xám xanh trung tính (bổ sung)
}
MONTH_ORDER = [
    "Apr", "May", "Jun", "Jul", "Aug", "Sep",
    "Oct", "Nov", "Dec", "Jan", "Feb", "Mar",
]
# ============================================================
# BẢNG GIẢI MÃ SCOPE (dùng cho phần "CHI TIẾT THEO MÃ")
# Mã trong sheet C/A/S có dạng {Mode}-{Scope of Job}, VD: AE-CTAB
# ============================================================
MODE_LABELS = {
    "AI": "Air Import",
    "AE": "Air Export",
    "OILCL": "Sea Import LCL",
    "OIFCL": "Sea Import FCL",
    "OELCL": "Sea Export LCL",
    "OEFCL": "Sea Export FCL",
    "DI": "Domestic Import",
    "DE": "Domestic Export",
    "DM": "Inland (Point A to B)",
    "CE": "Cross-border Export",
    "CI": "Cross-border Import",
    "HE": "Handcarry Export",
    "HI": "Handcarry Import",
    "RE": "Rail Export",
    "RI": "Rail Import",
    "RD": "Rail Domestic",
}
SCOPE_LABELS = {
    "CTAW": "Customs + Trucking + Air + B.Warehouse",
    "CTOW": "Customs + Trucking + Ocean + B.Warehouse",
    "CTOB": "Customs + Trucking + Ocean",
    "CTAB": "Customs + Trucking + Air",
    "CTWB": "Customs + Trucking + B.Warehouse",
    "CTRB": "Customs + Trucking + Rail",
    "CAWB": "Customs + Air + B.Warehouse",
    "COWB": "Customs + Ocean + B.Warehouse",
    "CTBB": "Customs + Trucking",
    "CWBB": "Customs + B.Warehouse",
    "COBB": "Customs + Ocean",
    "CABB": "Customs + Air",
    "CTCR": "Customs + Trucking + Cross-Border Rail",
    "CRBB": "Customs + Rail",
    "CARB": "Customs + Air + Rail",
    "CWRB": "Customs + B.Warehouse + Rail",
    "CORB": "Customs + Ocean + Rail",
    "COWR": "Customs + Ocean + B.Warehouse + Rail",
    "TAWB": "Trucking + Air + B.Warehouse",
    "TOBB": "Trucking + Ocean",
    "TOWB": "Trucking + Ocean + B.Warehouse",
    "TABB": "Trucking + Air",
    "TBBB": "Trucking Only",
    "TWBB": "Trucking + B.Warehouse",
    "TRBB": "Trucking + Rail",
    "TAOB": "Trucking + Air + Ocean",
    "TARB": "Trucking + Air + Rail",
    "TORB": "Trucking + Ocean + Rail",
    "TWRB": "Trucking + B.Warehouse + Rail",
    "UBBB": "Trucking Round-Use",
    "MBBB": "Trucking Milkrun/Shuttle",
    "ABBB": "Air Freight Only",
    "OBBB": "Ocean Freight Only",
    "WBBB": "B.Warehouse Only",
    "RBBB": "Rail Only",
    "AWBB": "Air + B.Warehouse",
    "OWBB": "Ocean + B.Warehouse",
    "ARBB": "Air + Rail",
    "ORBB": "Ocean + Rail",
    "WRBB": "B.Warehouse + Rail",
    "AWRB": "Air + B.Warehouse + Rail",
    "OWRB": "Ocean + B.Warehouse + Rail",
    "CBTB": "Cross-Border Truck",
    "CBTW": "Cross-Border + B.Warehouse",
    "CBTA": "Cross-Border Truck + Air",
    "CBTO": "Cross-Border + Ocean",
    "CBRB": "Cross-Border Rail",
    "BCLC": "Buyer Consol (Cross-Border Truck/Rail)",
    "BCLO": "Buyer Consol (Ocean)",
    "APRB": "Air Charter",
    "CBBB": "Customs Only",
    "BBBB": "Other",
    "IBBB": "Trouble-shooting Handling",
    "FCTB": "Booking Agent + Customs + Truck",
    "FTBB": "Booking Agent + Truck",
    "FCBB": "Booking Agent + Customs",
    "FWBB": "Booking Agent + B.Warehouse",
    "FTWB": "Booking Agent + Truck + B.Warehouse",
    "FCWB": "Booking Agent + Customs + B.Warehouse",
    "FCTW": "Booking Agent + Customs + Truck + B.Warehouse",
    "FBBB": "Booking Agent",
    "VBBB": "Vendor Booking Release",
    "DBBB": "Vendor Doc",
    "CTAS": "Customs + Trucking + Air + CFS warehouse",
    "CTOS": "Customs + Trucking + Ocean + CFS warehouse",
    "CTSB": "Customs + Trucking + CFS warehouse",
    "CASB": "Customs + Air + CFS warehouse",
    "COSB": "Customs + Ocean + CFS warehouse",
    "CSBB": "Customs + CFS warehouse",
    "TASB": "Trucking + Air + CFS warehouse",
    "TOSB": "Trucking + Ocean + CFS warehouse",
    "TSBB": "Trucking + CFS warehouse",
    "SBBB": "CFS warehouse Only",
    "ASBB": "Air + CFS warehouse",
    "OSBB": "Ocean + CFS warehouse",
    "CBTS": "Cross-Border + CFS warehouse",
    "FSBB": "Booking Agent + CFS warehouse",
    "FTSB": "Booking Agent + Truck + CFS warehouse",
    "FCSB": "Booking Agent + Customs + CFS warehouse",
    "FCTS": "Booking Agent + Customs + Truck + CFS warehouse",
    "CTAG": "Customs + Trucking + Air + General warehouse",
    "CTOG": "Customs + Trucking + Ocean + General warehouse",
    "CTGB": "Customs + Trucking + General warehouse",
    "CAGB": "Customs + Air + General warehouse",
    "COGB": "Customs + Ocean + General warehouse",
    "CGBB": "Customs + General warehouse",
    "TAGB": "Trucking + Air + General warehouse",
    "TOGB": "Trucking + Ocean + General warehouse",
    "TGBB": "Trucking + General warehouse",
    "GBBB": "General warehouse Only",
    "AGBB": "Air + General warehouse",
    "OGBB": "Ocean + General warehouse",
    "CBTG": "Cross-Border + General warehouse",
    "FGBB": "Booking Agent + General warehouse",
    "FTGB": "Booking Agent + Truck + General warehouse",
    "FCGB": "Booking Agent + Customs + General warehouse",
    "FCTG": "Booking Agent + Customs + Truck + General warehouse",
    "TTTB": "Truck Sea Truck",
    "TTBB": "Truck Air Truck",
}
# Một số mã không theo cấu trúc {Mode}-{Scope} (không có dấu gạch nối)
SPECIAL_CODE_LABELS = {
    "AECO": "Air Export · CO only",
    "DECO": "Domestic Export · CO only",
    "OEFCLCO": "Sea Export FCL · CO only",
    "OELCLCO": "Sea Export LCL · CO only",
}
def decode_scope_code(code: str) -> str:
    """Giải mã 1 mã Scope (VD: AE-CTAB) thành mô tả dễ hiểu. Trả về '—' nếu không nhận diện được."""
    code = clean_text(code).upper()
    if not code:
        return "—"
    if code in SPECIAL_CODE_LABELS:
        return SPECIAL_CODE_LABELS[code]
    if "-" in code:
        mode_part, scope_part = code.split("-", 1)
        mode_label = MODE_LABELS.get(mode_part)
        scope_label = SCOPE_LABELS.get(scope_part)
        if mode_label and scope_label:
            return f"{mode_label} · {scope_label}"
        if mode_label:
            return mode_label
        if scope_label:
            return scope_label
    return "—"
# ============================================================
# STYLE
# ============================================================
st.markdown(
    """
    <style>
    :root {
        --navy:#06183D;
        --blue:#00B9F2;
        --orange:#FF6D10;
        --green:#45BD8C;
        --amber:#FFC933;
        --amber-text:#B8860B;
        --red:#DC2626;
        --muted:#667085;
        --line:#DCE5F0;
        --panel:#FFFFFF;
        --page:#F7F9FC;
    }
    .stApp {background:var(--page);}
    [data-testid="stSidebar"] {
        background:linear-gradient(180deg,#06183D 0%,#0A2559 100%);
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
    .block-container {max-width:1700px;padding-top:1.25rem;padding-bottom:1.5rem;}
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
    .kpi-split {
        width:100%;
        display:flex;
        justify-content:space-between;
        align-items:flex-end;
        margin-top:auto;
        padding-top:12px;
        font-size:0.78rem;
        font-weight:800;
        color:var(--navy);
        line-height:1;
    }
    .kpi-split span:first-child {text-align:left;}
    .kpi-split span:last-child {text-align:right;}
    .orange .kpi-value {color:var(--orange);}
    .green .kpi-value {color:var(--green);}
    .amber .kpi-value {color:var(--amber-text);}
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

def kpi_hc_card(label, total_value, mng_value, pic_value, accent=""):
    """HC KPI: tổng ở giữa; MNG góc trái dưới; PIC góc phải dưới."""
    st.markdown(
        f"""
        <div class="kpi-card {accent}">
            <div class="kpi-label">{label}</div>
            <div class="kpi-value">{total_value}</div>
            <div class="kpi-split">
                <span>MNG: {mng_value}</span>
                <span>PIC: {pic_value}</span>
            </div>
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
def table_height(n_rows, cap=340, min_h=120):
    """Chiều cao bảng đúng chuẩn Streamlit (~38px header + ~35px/dòng), có cuộn nếu vượt cap."""
    return max(min_h, min(cap, 38 + 35 * max(n_rows, 1)))
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
# LOAD SOURCE FILE (tự động phát hiện file Excel đã cập nhật trên GitHub —
# cache theo (đường dẫn, thời điểm sửa đổi cuối), tự đọc lại khi deploy file mới,
# không cần thao tác thủ công.)
# ============================================================
def find_source_path():
    """Quét tìm file Excel phù hợp — KHÔNG cache, chạy lại mỗi lần rerun để
    luôn thấy được file mới nhất/mtime mới nhất ngay sau khi deploy."""
    app_dir = Path(__file__).resolve().parent
    xlsx_files = [p for p in app_dir.rglob("*.xlsx") if not p.name.startswith("~$")]
    preferred = [p for p in xlsx_files if p.name.casefold() == "cs workload & capacity.xlsx".casefold()]
    if preferred:
        xlsx_files = preferred + [p for p in xlsx_files if p not in preferred]
    required = {"HC Capacity", "BU Workload Allocation", "CS FTE", "Shipment volume"}
    for p in sorted(xlsx_files, key=lambda x: x.stat().st_mtime, reverse=True):
        try:
            xl = pd.ExcelFile(p)
            sheet_names = set(xl.sheet_names)
            has_customer = any(s.startswith("Customer Volume") for s in xl.sheet_names)
            if required.issubset(sheet_names) and has_customer:
                return p
        except Exception:
            continue
    return None
@st.cache_data(show_spinner=False)
def read_source_file(path_str: str, mtime: float):
    """
    Cache theo (đường dẫn, mtime). Khi chị cập nhật file Excel trên GitHub và
    Streamlit Cloud deploy lại (hoặc file trên đĩa đổi mtime), cache sẽ tự
    invalidate và đọc lại tự động.
    """
    p = Path(path_str)
    return p.read_bytes(), p.name
# ============================================================
# PARSERS
# ============================================================
@st.cache_data(show_spinner=False)
def parse_bu_allocation(file_bytes: bytes) -> pd.DataFrame:
    """
    Sheet 'BU Workload Allocation'. Row 1 = tiêu đề, Row 2 = header, Row 3 trở đi = data.
    Business rule:
        Số lô (Shipment Volume) theo BU = Core Volume
        Tổng thời gian theo BU          = Total Workload (min)
        Tỷ trọng theo BU                = Total Workload của BU / tổng Total Workload
    """
    df = pd.read_excel(io.BytesIO(file_bytes), sheet_name="BU Workload Allocation", header=1)
    expected_keywords = [
        "office", "month", "segment",
        "core volume", "core workload",
        "ancillary volume", "ancillary workload",
        "supporting volume", "supporting workload",
        "exception volume", "exception workload",
        "total workload", "workload share",
    ]
    check_columns(df.columns, expected_keywords, "BU Workload Allocation")
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

    # QUAN TRỌNG:
    # Workbook có một số ô nhìn giống số nhưng thực tế là TEXT (ví dụ "541").
    # Excel SUM bỏ qua các ô text này. pd.to_numeric() trước đây lại biến "541"
    # thành 541 và làm sai Workload Breakdown. Chỉ nhận cell thực sự là numeric.
    def _excel_numeric_only(v):
        if isinstance(v, (int, float, np.integer, np.floating)) and not isinstance(v, (bool, np.bool_)):
            return float(v)
        return np.nan

    for c in numeric_cols:
        df[c] = df[c].map(_excel_numeric_only)

    df = df[
        df["Office"].ne("")
        & df["Month"].isin(MONTH_ORDER)
        & df["Segment"].isin(SERVICE_ORDER)
    ].copy()

    for c in [
        "Core Volume", "Core Workload",
        "Ancillary Volume", "Ancillary Workload",
        "Supporting Volume", "Supporting Workload",
        "Exception Volume", "Exception Workload",
        "Total Workload",
    ]:
        df[c] = df[c].fillna(0.0)

    # Recalculate workload share from Total Workload to avoid stale Excel formula cache.
    office_month_total = df.groupby(["Office", "Month"], observed=True)["Total Workload"].transform("sum")
    df["BU Workload Share (raw)"] = np.where(
        office_month_total > 0,
        df["Total Workload"] / office_month_total,
        0.0,
    )

    df["Month"] = pd.Categorical(df["Month"], categories=MONTH_ORDER, ordered=True)
    return df.sort_values(["Month", "Office", "Segment"]).reset_index(drop=True)
@st.cache_data(show_spinner=False)
def parse_hc(file_bytes: bytes) -> pd.DataFrame:
    """Sheet 'HC Capacity'. Row 1 = tiêu đề, Row 2 = header, Row 3 trở đi = data."""
    df = pd.read_excel(io.BytesIO(file_bytes), sheet_name="HC Capacity", header=1)
    expected_keywords = ["office", "month"]
    check_columns(df.columns, expected_keywords, "HC Capacity")
    if df.shape[1] < 13:
        raise ValueError("Sheet 'HC Capacity' không đủ 13 cột dữ liệu.")
    df = df.iloc[:, :13].copy()
    df.columns = [
        "Office", "Month",
        "Approved HC MNG", "Approved HC PIC", "Total Approved HC",
        "Actual HC MNG", "Actual HC PIC", "Total Actual HC",
        "Required HC MNG", "Required HC PIC", "Total Required HC",
        "HC Utilization", "HC Status",
    ]
    df["Office"] = df["Office"].map(clean_text)
    df["Month"] = df["Month"].map(normalize_month)
    df["HC Status"] = df["HC Status"].map(clean_text)
    numeric_cols = [
        "Approved HC MNG", "Approved HC PIC", "Total Approved HC",
        "Actual HC MNG", "Actual HC PIC", "Total Actual HC",
        "Required HC MNG", "Required HC PIC", "Total Required HC",
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
        df = pd.read_excel(io.BytesIO(file_bytes), sheet_name="Exception Handling Volume", header=1)
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

@st.cache_data(show_spinner=False)
def parse_shipment_volume(file_bytes: bytes) -> pd.DataFrame:
    """Shipment volume: mỗi dòng = Office + Month; dùng cho volume thực tế và Active Customers."""
    df = pd.read_excel(io.BytesIO(file_bytes), sheet_name="Shipment volume", header=1)
    if df.shape[1] < 4:
        return pd.DataFrame()
    df = df.copy()
    df.columns = [clean_text(c) for c in df.columns]
    # Chuẩn hóa các cột khóa
    rename_map = {}
    for c in df.columns:
        if c.casefold() == "office":
            rename_map[c] = "Office"
        elif c.casefold() == "month":
            rename_map[c] = "Month"
        elif c.casefold() == "active customers":
            rename_map[c] = "Active Customers"
        elif c.casefold() == "total":
            rename_map[c] = "TOTAL"
    df = df.rename(columns=rename_map)
    if "Office" not in df or "Month" not in df:
        return pd.DataFrame()
    df["Office"] = df["Office"].map(clean_text)
    df["Month"] = df["Month"].map(normalize_month)
    numeric_cols = [c for c in df.columns if c not in ["Office", "Month"]]
    for c in numeric_cols:
        df[c] = pd.to_numeric(df[c], errors="coerce")

    # TOTAL được tính lại từ các mode để tránh phụ thuộc cached formula trong Excel.
    shipment_mode_cols = [
        c for c in [
            "AI", "AE", "OILCL", "OIFCL", "OELCL", "OEFCL",
            "DI", "DE", "DM", "CE", "CI", "HE", "HI", "RE", "RI", "RD"
        ] if c in df.columns
    ]
    if shipment_mode_cols:
        has_any_mode = df[shipment_mode_cols].notna().any(axis=1)
        calc_total = df[shipment_mode_cols].fillna(0).sum(axis=1)
        df["TOTAL"] = np.where(has_any_mode, calc_total, np.nan)

    return df[df["Office"].ne("") & df["Month"].isin(MONTH_ORDER)].reset_index(drop=True)

@st.cache_data(show_spinner=False)
def parse_yvf(file_bytes: bytes) -> pd.DataFrame:
    """Index YVF Promotion Effectiveness theo Office + Month."""
    try:
        df = pd.read_excel(io.BytesIO(file_bytes), sheet_name="YVF Promotion Effectiveness", header=1)
    except Exception:
        return pd.DataFrame(columns=["Office","Month","Total YVF Bookings","Total IFF Shipments","YVF Booking Ratio"])
    df.columns = [clean_text(c) for c in df.columns]
    df = df.rename(columns={"OFFICE": "Office"})
    needed = ["Office","Month","Total YVF Bookings","Total IFF Shipments","YVF Booking Ratio"]
    if not set(["Office","Month"]).issubset(df.columns):
        return pd.DataFrame(columns=needed)
    df["Office"] = df["Office"].map(clean_text)
    df["Month"] = df["Month"].map(normalize_month)
    for c in ["Total YVF Bookings","Total IFF Shipments","YVF Booking Ratio"]:
        if c in df:
            df[c] = pd.to_numeric(df[c], errors="coerce")
    if "YVF Booking Ratio" not in df:
        df["YVF Booking Ratio"] = 0.0
    # Tính lại ratio để tránh phụ thuộc cached formula.
    # Không có denominator => N/A, không gán 0% vì sẽ gây hiểu nhầm.
    if {"Total YVF Bookings","Total IFF Shipments"}.issubset(df.columns):
        df["YVF Booking Ratio"] = np.where(
            df["Total IFF Shipments"].fillna(0) > 0,
            df["Total YVF Bookings"].fillna(0) / df["Total IFF Shipments"],
            np.nan
        )
    return df[df["Office"].ne("") & df["Month"].isin(MONTH_ORDER)].reset_index(drop=True)


# ============================================================
# LOAD DATA
# ============================================================
source_path = find_source_path()
if source_path is None:
    st.error(
        "Không tìm thấy file Excel có đủ các sheet chính: "
        "HC Capacity, BU Workload Allocation, CS FTE, Shipment volume và Customer Volume."
    )
    st.info("Đặt file Excel cùng thư mục/repository với file .py rồi Reboot app.")
    st.stop()
source_bytes, source_name = read_source_file(str(source_path), source_path.stat().st_mtime)
try:
    hc = parse_hc(source_bytes)
    bu = parse_bu_allocation(source_bytes)
    cs_fte = parse_cs_fte(source_bytes)
    customer = parse_customer_lists(source_bytes)
    shipment = parse_shipment_volume(source_bytes)
    yvf = parse_yvf(source_bytes)
except Exception as exc:
    st.error("Không thể đọc dữ liệu nguồn. Vui lòng kiểm tra lại cấu trúc file Excel.")
    st.exception(exc)
    st.stop()
# Các sheet chi tiết theo mã (C/A/S/E) là dữ liệu bổ sung — nếu thiếu hoặc lỗi,
# dashboard vẫn chạy bình thường, chỉ ẩn phần "Chi tiết theo mã".
try:
    core_detail = parse_scope_detail(source_bytes, "Core Service Volume")
    ancillary_detail = parse_scope_detail(source_bytes, "Ancillary Service Volume")
    supporting_detail = parse_scope_detail(source_bytes, "Supporting Activity Volume")
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
    | set(shipment.get("Office", pd.Series(dtype=str)).dropna().astype(str))
    | set(yvf.get("Office", pd.Series(dtype=str)).dropna().astype(str))
)
# 1) Office
office = st.sidebar.selectbox(
    "Office",
    ["All Offices"] + all_offices,
    key="filter_office",
    on_change=reset_child_filters,
)
# 2) Month
# Chỉ hiện Month thực sự có dữ liệu ở ít nhất một nguồn; không lấy các dòng template trống.
hc_months_with_data = set(
    hc.loc[
        hc["Total Approved HC"].notna()
        | hc["Total Actual HC"].notna()
        | (hc["Total Required HC"].fillna(0) > 0),
        "Month",
    ].dropna().astype(str)
)
bu_months_with_data = set(
    bu.loc[bu["Total Workload"].fillna(0) > 0, "Month"].dropna().astype(str)
)
cs_months_with_data = set(
    cs_fte.loc[cs_fte["FTE"].fillna(0) > 0, "Month"].dropna().astype(str)
)
customer_months_with_data = set(
    customer.loc[
        customer["Customer Shipment Volume"].fillna(0) > 0, "Month"
    ].dropna().astype(str)
)

shipment_months_with_data = set()
if not shipment.empty and "TOTAL" in shipment.columns:
    shipment_months_with_data = set(
        shipment.loc[shipment["TOTAL"].fillna(0) > 0, "Month"].dropna().astype(str)
    )

yvf_months_with_data = set()
if not yvf.empty:
    yvf_cols = [c for c in ["Total YVF Bookings", "Total IFF Shipments"] if c in yvf.columns]
    if yvf_cols:
        yvf_has_data = yvf[yvf_cols].fillna(0).sum(axis=1) > 0
        yvf_months_with_data = set(yvf.loc[yvf_has_data, "Month"].dropna().astype(str))

available_month_set = (
    hc_months_with_data
    | bu_months_with_data
    | cs_months_with_data
    | customer_months_with_data
    | shipment_months_with_data
    | yvf_months_with_data
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
if cs_pic != "All CS PIC" and not pic_scope.empty:
    selected_pic_rows = pic_scope[pic_scope["CS PIC"].eq(cs_pic)]
    # FTE trong sheet CS FTE là input trực tiếp theo từng PIC.
    # Không phân bổ BU Workload theo tỷ trọng FTE vì file nguồn không có mapping
    # CS PIC -> Segment/Core/Ancillary/Supporting/Exception.
    pic_fte_value = float(selected_pic_rows["FTE"].mean()) if not selected_pic_rows.empty else np.nan
    pic_workload_minutes = (
        float(selected_pic_rows["PIC Workload"].mean())
        if not selected_pic_rows.empty else np.nan
    )
# Tổng hợp Số lô + Thời gian theo từng BU (AI/AE/OI/OE/TR/CC/WH)
service = (
    filtered_bu.groupby("Segment", as_index=False)
    .agg(Service_Volume=("Core Volume", "sum"), Base_Workload=("Total Workload", "sum"))
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
# Số tháng dùng làm mẫu số tính Required FTE: đếm theo tháng THỰC SỰ có Workload > 0
# trong BU allocation (đúng theo Office đang chọn) — không dùng theo union tất cả sheet,
# vì HC/CS FTE có thể có sẵn dòng cho các tháng chưa nhập Workload, làm mẫu số bị thổi phồng
# và Required FTE bị pha loãng sai (VD: workload 2 tháng nhưng chia cho năng lực 12 tháng).
if month == "All":
    workload_months_with_data = sorted(
        filtered_bu.loc[filtered_bu["Total Workload"] > 0, "Month"].astype(str).unique().tolist(),
        key=lambda m: MONTH_ORDER.index(m),
    )
    selected_month_count = max(len(workload_months_with_data), 1)
else:
    workload_months_with_data = [month]
    selected_month_count = 1
period_capacity_minutes = FTE_MINUTES * selected_month_count
required_fte = safe_divide(selected_base_workload, period_capacity_minutes)
service["Required FTE"] = service["Base_Workload"] / period_capacity_minutes
# TOTAL SHIPMENT lấy từ sheet Shipment volume, KHÔNG cộng Core Volume của BU.
# Một shipment có thể đồng thời phát sinh nhiều service nên cộng BU Core Volume sẽ double-count.
filtered_shipment = shipment.copy()
if month != "All" and not filtered_shipment.empty:
    filtered_shipment = filtered_shipment[filtered_shipment["Month"].eq(month)].copy()
if office != "All Offices" and not filtered_shipment.empty:
    filtered_shipment = filtered_shipment[filtered_shipment["Office"].eq(office)].copy()

if selected_customer != "All Customers" and not filtered_customer.empty:
    # Khi lọc 1 customer, Shipment KPI lấy từ Customer Volume vì Shipment volume
    # không có dimension Customer.
    total_shipments = float(filtered_customer["Customer Shipment Volume"].fillna(0).sum())
else:
    total_shipments = (
        float(filtered_shipment["TOTAL"].fillna(0).sum())
        if (not filtered_shipment.empty and "TOTAL" in filtered_shipment.columns)
        else 0.0
    )
# --- HC KPI ---
# Chỉ coi là tháng có dữ liệu HC khi có Approved/Actual hoặc Required HC > 0.
# Các tháng template trống có Total Required HC = 0 không được đưa vào bình quân.
hc_valid = filtered_hc[
    filtered_hc["Total Approved HC"].notna()
    | filtered_hc["Total Actual HC"].notna()
    | (filtered_hc["Total Required HC"].fillna(0) > 0)
].copy()
if hc_valid.empty:
    approved_hc = actual_hc = required_hc_total = hc_utilization = np.nan
    approved_mng = approved_pic = np.nan
    actual_mng = actual_pic = np.nan
    required_mng = required_pic = np.nan
    hc_status = "No data"
else:
    if month == "All":
        hc_monthly = (
            hc_valid.groupby("Month", as_index=False)
            .agg(
                Approved_HC=("Total Approved HC", "sum"),
                Approved_MNG=("Approved HC MNG", "sum"),
                Approved_PIC=("Approved HC PIC", "sum"),
                Actual_HC=("Total Actual HC", "sum"),
                Actual_MNG=("Actual HC MNG", "sum"),
                Actual_PIC=("Actual HC PIC", "sum"),
                Required_HC=("Total Required HC", "sum"),
                Required_MNG=("Required HC MNG", "sum"),
                Required_PIC=("Required HC PIC", "sum"),
            )
        )
        approved_hc = float(hc_monthly["Approved_HC"].mean())
        approved_mng = float(hc_monthly["Approved_MNG"].mean())
        approved_pic = float(hc_monthly["Approved_PIC"].mean())

        actual_hc = float(hc_monthly["Actual_HC"].mean())
        actual_mng = float(hc_monthly["Actual_MNG"].mean())
        actual_pic = float(hc_monthly["Actual_PIC"].mean())

        required_hc_total = float(hc_monthly["Required_HC"].mean())
        required_mng = float(hc_monthly["Required_MNG"].mean())
        required_pic = float(hc_monthly["Required_PIC"].mean())
    else:
        approved_hc = float(hc_valid["Total Approved HC"].sum())
        approved_mng = float(hc_valid["Approved HC MNG"].sum())
        approved_pic = float(hc_valid["Approved HC PIC"].sum())

        actual_hc = float(hc_valid["Total Actual HC"].sum())
        actual_mng = float(hc_valid["Actual HC MNG"].sum())
        actual_pic = float(hc_valid["Actual HC PIC"].sum())

        required_hc_total = float(hc_valid["Total Required HC"].sum())
        required_mng = float(hc_valid["Required HC MNG"].sum())
        required_pic = float(hc_valid["Required HC PIC"].sum())
    hc_utilization = safe_divide(required_hc_total, actual_hc) if actual_hc else np.nan
    if pd.isna(hc_utilization):
        hc_status = "No data"
    elif hc_utilization > 1.00:
        hc_status = "Overload"
    elif hc_utilization > 0.95:
        hc_status = "High load"
    elif hc_utilization >= 0.90:
        hc_status = "Balanced"
    else:
        hc_status = "Less load"
# --- HC status theo từng Office (phục vụ banner cảnh báo) ---
def _office_status(u):
    if pd.isna(u):
        return "No data"
    elif u > 1.00:
        return "Overload"
    elif u > 0.95:
        return "High load"
    elif u >= 0.90:
        return "Balanced"
    else:
        return "Less load"
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

st.markdown(
    """
    <style>
    /* ===== EXECUTIVE COMPACT LAYOUT ===== */
    .section-title {
        background:#06183D !important;
        color:#FFFFFF !important;
        padding:0.52rem 0.82rem !important;
        border-radius:9px 9px 0 0 !important;
        font-weight:800 !important;
        font-size:0.92rem !important;
        margin:0.25rem 0 0 0 !important;
        letter-spacing:0.01em;
    }

    .kpi-card {
        background:#FFFFFF !important;
        border:1px solid #DCE5F0 !important;
        border-radius:11px !important;
        min-height:138px !important;
        height:138px !important;
        padding:11px 16px 10px 16px !important;
        box-sizing:border-box !important;
        display:flex !important;
        flex-direction:column !important;
        justify-content:flex-start !important;
        align-items:stretch !important;
        text-align:center !important;
        box-shadow:0 2px 8px rgba(28,54,89,.045) !important;
    }

    .kpi-label {
        min-height:28px !important;
        margin:0 !important;
        display:flex !important;
        align-items:center !important;
        justify-content:center !important;
        font-size:0.80rem !important;
        line-height:1.15 !important;
        font-weight:800 !important;
        color:#06183D !important;
    }

    .kpi-value {
        height:56px !important;
        display:flex !important;
        align-items:center !important;
        justify-content:center !important;
        font-size:2.05rem !important;
        line-height:1 !important;
        font-weight:850 !important;
        color:#00B9F2 !important;
        white-space:nowrap !important;
    }

    .kpi-split {
        width:100% !important;
        margin-top:auto !important;
        padding-top:5px !important;
        display:flex !important;
        justify-content:space-between !important;
        align-items:center !important;
        font-size:0.70rem !important;
        line-height:1 !important;
        font-weight:800 !important;
        color:#06183D !important;
        border-top:1px solid #EEF2F7;
    }

    .kpi-note {
        min-height:19px !important;
        margin-top:auto !important;
        padding-top:4px !important;
        font-size:0.69rem !important;
        line-height:1.05 !important;
        font-weight:700 !important;
        color:#344054 !important;
    }

    .orange .kpi-value {color:#FF6D10 !important;}
    .amber .kpi-value  {color:#B8860B !important;}
    .green .kpi-value  {color:#169B62 !important;}
    .red .kpi-value    {color:#DC2626 !important;}

    .dashboard-title {
        font-size:1.55rem !important;
        margin:0 0 0.15rem 0 !important;
    }
    .dashboard-subtitle {
        margin-bottom:0.55rem !important;
        font-size:0.76rem !important;
    }

    div[data-testid="stPlotlyChart"] {
        background:#FFFFFF;
        border:1px solid #DCE5F0;
        border-radius:11px;
        padding:0.20rem 0.35rem 0.10rem 0.35rem;
    }

    div[data-testid="stDataFrame"] {
        background:#FFFFFF;
        border:1px solid #DCE5F0 !important;
        border-radius:11px !important;
        overflow:hidden;
    }

    .compact-caption {
        color:#98A2B3;
        font-size:0.69rem;
        margin-top:0.25rem;
    }
    </style>
    """,
    unsafe_allow_html=True,
)



def add_right_note(fig, text):
    """Add a consistent note on the right side of Plotly charts."""
    if not text:
        return fig
    fig.add_annotation(
        xref="paper",
        yref="paper",
        x=1.0,
        y=1.16,
        xanchor="right",
        yanchor="top",
        text=text,
        showarrow=False,
        align="right",
        font=dict(size=9, color="#667085"),
        bgcolor="rgba(255,255,255,0.85)",
        bordercolor="rgba(0,0,0,0)",
        borderpad=2,
    )
    return fig

# ============================================================
# EXECUTIVE DASHBOARD — COMPACT DESIGN
# Filters remain in the LEFT sidebar.
# ============================================================

st.markdown(f'<div class="dashboard-title">{APP_TITLE}</div>', unsafe_allow_html=True)
filter_summary = (
    f"Month: {month} · Office: {office} · CS PIC: {cs_pic} · Customer: {selected_customer}"
)
st.markdown(f'<div class="dashboard-subtitle">{filter_summary}</div>', unsafe_allow_html=True)

# ============================================================
# 1. HEADCOUNT / CAPACITY STATUS — 5 KPI CARDS
# ============================================================
st.markdown(
    '<div class="section-title">HEADCOUNT / CAPACITY STATUS</div>',
    unsafe_allow_html=True,
)

def _hc_value(v):
    return "—" if pd.isna(v) else f"{v:,.2f}".rstrip("0").rstrip(".")

# Gap dùng cho note của Capacity Status
hc_gap = (
    actual_hc - required_hc_total
    if (not pd.isna(actual_hc) and not pd.isna(required_hc_total))
    else np.nan
)

h1, h2, h3, h4, h5 = st.columns([1, 1, 1, 1, 1], gap="medium")

with h1:
    kpi_hc_card(
        "Approved HC",
        _hc_value(approved_hc),
        _hc_value(approved_mng),
        _hc_value(approved_pic),
    )

with h2:
    kpi_hc_card(
        "Actual HC",
        _hc_value(actual_hc),
        _hc_value(actual_mng),
        _hc_value(actual_pic),
    )

with h3:
    kpi_hc_card(
        "Required HC",
        _hc_value(required_hc_total),
        _hc_value(required_mng),
        _hc_value(required_pic),
        "orange",
    )

with h4:
    util_text = "—" if pd.isna(hc_utilization) else f"{hc_utilization:.0%}"
    kpi_card(
        "Capacity Utilization",
        util_text,
        "Vs Required HC" if not pd.isna(hc_utilization) else "",
        "amber",
    )

with h5:
    status_accent = {
        "Overload": "red",
        "High load": "orange",
        "Balanced": "green",
        "Less load": "",
    }.get(hc_status, "")
    if pd.isna(hc_gap):
        status_note = ""
    elif hc_gap < 0:
        status_note = f"Over by {abs(hc_gap):.2f} HC"
    else:
        status_note = f"Available {hc_gap:.2f} HC"

    kpi_card(
        "Capacity Status",
        hc_status,
        status_note,
        status_accent,
    )

# ============================================================
# OFFICE-LEVEL DATA FOR THE 3 CHARTS + STATUS TABLE
# ============================================================
relevant_offices = all_offices if office == "All Offices" else [office]

office_hc = filtered_hc.copy()
office_hc = office_hc[
    office_hc["Total Approved HC"].notna()
    | office_hc["Total Actual HC"].notna()
    | (office_hc["Total Required HC"].fillna(0) > 0)
].copy()

if office_hc.empty:
    office_summary = pd.DataFrame({"Office": relevant_offices})
    for c in [
        "Actual HC", "Required HC", "Actual MNG", "Actual PIC",
        "Capacity Utilization", "Gap", "Status",
    ]:
        office_summary[c] = np.nan if c != "Status" else "No data"
else:
    if month == "All":
        office_monthly = (
            office_hc.groupby(["Office", "Month"], as_index=False)
            .agg(
                **{
                    "Actual HC": ("Total Actual HC", "sum"),
                    "Required HC": ("Total Required HC", "sum"),
                    "Actual MNG": ("Actual HC MNG", "sum"),
                    "Actual PIC": ("Actual HC PIC", "sum"),
                }
            )
        )
        office_summary = (
            office_monthly.groupby("Office", as_index=False)
            .agg(
                **{
                    "Actual HC": ("Actual HC", "mean"),
                    "Required HC": ("Required HC", "mean"),
                    "Actual MNG": ("Actual MNG", "mean"),
                    "Actual PIC": ("Actual PIC", "mean"),
                }
            )
        )
    else:
        office_summary = (
            office_hc.groupby("Office", as_index=False)
            .agg(
                **{
                    "Actual HC": ("Total Actual HC", "sum"),
                    "Required HC": ("Total Required HC", "sum"),
                    "Actual MNG": ("Actual HC MNG", "sum"),
                    "Actual PIC": ("Actual HC PIC", "sum"),
                }
            )
        )

    office_summary = pd.DataFrame({"Office": relevant_offices}).merge(
        office_summary, on="Office", how="left"
    )

    office_summary["Capacity Utilization"] = np.where(
        office_summary["Actual HC"].fillna(0) > 0,
        office_summary["Required HC"] / office_summary["Actual HC"],
        np.nan,
    )
    office_summary["Gap"] = office_summary["Actual HC"] - office_summary["Required HC"]
    office_summary["Status"] = office_summary["Capacity Utilization"].map(_office_status)

office_summary = office_summary.sort_values("Office").reset_index(drop=True)

# ============================================================
# 2. THREE COMPACT OFFICE CHARTS
# ============================================================
c1, c2, c3 = st.columns([1, 1, 1], gap="medium")

with c1:
    util_plot = office_summary.copy()
    util_plot["Util %"] = util_plot["Capacity Utilization"] * 100

    fig = go.Figure()
    fig.add_trace(
        go.Bar(
            x=util_plot["Office"],
            y=util_plot["Util %"].fillna(0),
            marker_color="#06183D",
            text=[
                "—" if pd.isna(v) else f"{v:.0f}%"
                for v in util_plot["Util %"]
            ],
            textposition="outside",
            cliponaxis=False,
            name="Capacity Utilization (%)",
        )
    )
    fig.add_hline(
        y=100,
        line_dash="dash",
        line_width=1.2,
        line_color="#FF6D10",
    )
    add_right_note(fig, "Target: 100%")
    fig.update_layout(
        title=dict(
            text="CAPACITY UTILIZATION BY OFFICE",
            x=0.02, xanchor="left",
            font=dict(size=13, color="#06183D"),
        ),
        height=300,
        margin=dict(l=15, r=95, t=55, b=25),
        paper_bgcolor="white",
        plot_bgcolor="white",
        showlegend=False,
        font=dict(color="#172033", size=10),
        xaxis=dict(showgrid=False),
        yaxis=dict(
            ticksuffix="%",
            gridcolor="#E9EEF5",
            zeroline=False,
            rangemode="tozero",
        ),
        hoverlabel=dict(bgcolor="white"),
    )
    st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})

with c2:
    compare = office_summary.melt(
        id_vars="Office",
        value_vars=["Actual HC", "Required HC"],
        var_name="Metric",
        value_name="HC",
    )
    fig = px.bar(
        compare,
        x="Office",
        y="HC",
        color="Metric",
        barmode="group",
        text="HC",
        color_discrete_map={
            "Actual HC": "#2F73D9",
            "Required HC": "#FF6D10",
        },
    )
    fig.update_traces(
        texttemplate="%{text:.2f}",
        textposition="outside",
        cliponaxis=False,
    )
    fig.update_layout(
        title=dict(
            text="ACTUAL VS REQUIRED HC BY OFFICE",
            x=0.02, xanchor="left",
            font=dict(size=13, color="#06183D"),
        ),
        height=300,
        margin=dict(l=15, r=15, t=55, b=25),
        paper_bgcolor="white",
        plot_bgcolor="white",
        font=dict(color="#172033", size=10),
        legend=dict(
            orientation="v",
            y=0.98,
            x=1.02,
            xanchor="left",
            yanchor="top",
            title="",
        ),
        xaxis=dict(showgrid=False),
        yaxis=dict(gridcolor="#E9EEF5", zeroline=False, rangemode="tozero"),
        hoverlabel=dict(bgcolor="white"),
    )
    add_right_note(fig, "Actual vs Required HC")
    st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})

with c3:
    fig = go.Figure()
    fig.add_trace(
        go.Bar(
            x=office_summary["Office"],
            y=office_summary["Actual MNG"].fillna(0),
            name="MNG",
            marker_color="#06183D",
            text=office_summary["Actual MNG"].fillna(0),
            texttemplate="%{text:.1f}",
            textposition="inside",
        )
    )
    fig.add_trace(
        go.Bar(
            x=office_summary["Office"],
            y=office_summary["Actual PIC"].fillna(0),
            name="PIC",
            marker_color="#63B3F3",
            text=office_summary["Actual PIC"].fillna(0),
            texttemplate="%{text:.1f}",
            textposition="inside",
        )
    )
    total_actual = office_summary["Actual HC"].fillna(0)
    for i, (off, total) in enumerate(zip(office_summary["Office"], total_actual)):
        fig.add_annotation(
            x=off, y=total,
            text=f"<b>{total:.1f}</b>" if total > 0 else "0.0",
            showarrow=False,
            yshift=10,
            font=dict(size=10, color="#06183D"),
        )

    fig.update_layout(
        barmode="stack",
        title=dict(
            text="HC COMPOSITION BY OFFICE (ACTUAL)",
            x=0.02, xanchor="left",
            font=dict(size=13, color="#06183D"),
        ),
        height=300,
        margin=dict(l=15, r=90, t=55, b=25),
        paper_bgcolor="white",
        plot_bgcolor="white",
        font=dict(color="#172033", size=10),
        legend=dict(
            orientation="v",
            y=0.98,
            x=1.02,
            xanchor="left",
            yanchor="top",
            title="",
        ),
        xaxis=dict(showgrid=False),
        yaxis=dict(gridcolor="#E9EEF5", zeroline=False, rangemode="tozero"),
        hoverlabel=dict(bgcolor="white"),
    )
    add_right_note(fig, "MNG + PIC = Total Actual HC")
    st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})

# ============================================================
# 3. WORKLOAD BY SERVICE + WORKLOAD STATUS BY OFFICE
# ============================================================
left, right = st.columns([0.78, 1.65], gap="small")

with left:
    donut = service.copy()
    donut = donut[donut["Base_Workload"].fillna(0) > 0].copy()

    if donut.empty:
        st.info("No workload data available for selected filters.")
    else:
        fig = px.pie(
            donut,
            names="Segment",
            values="Base_Workload",
            hole=0.55,
            color="Segment",
            color_discrete_map=SEGMENT_COLORS,
            category_orders={"Segment": SERVICE_ORDER},
        )
        fig.update_traces(
            textinfo="percent",
            textposition="inside",
            hovertemplate="<b>%{label}</b><br>%{value:,.0f} min<br>%{percent}<extra></extra>",
        )
        center_actual = "—" if pd.isna(actual_hc) else f"{actual_hc:.2f}"
        fig.add_annotation(
            x=0.5, y=0.52,
            text=f"<b>{center_actual}</b><br><span style='font-size:10px'>Total Actual HC</span>",
            showarrow=False,
            font=dict(size=18, color="#06183D"),
        )
        fig.update_layout(
            title=dict(
                text=f"WORKLOAD BY SERVICE{' (' + month.upper() + ')' if month != 'All' else ''}",
                x=0.02, xanchor="left",
                font=dict(size=13, color="#06183D"),
            ),
            height=310,
            margin=dict(l=10, r=95, t=55, b=15),
            paper_bgcolor="white",
            font=dict(color="#172033", size=10),
            legend=dict(
                orientation="v",
                y=0.5,
                x=1.02,
                xanchor="left",
                title="",
            ),
        )
        add_right_note(fig, "Share based on Total Workload")
        st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})

with right:
    status_display = office_summary[
        ["Office", "Actual HC", "Required HC", "Gap", "Capacity Utilization", "Status"]
    ].copy()

    # Streamlit dataframe: numeric formatting kept clean and compact.
    st.markdown(
        f"<div style='font-size:13px;font-weight:800;color:#06183D;margin:8px 0 6px 4px;'>"
        f"WORKLOAD STATUS BY OFFICE"
        f"{' (' + month.upper() + ')' if month != 'All' else ''}</div>",
        unsafe_allow_html=True,
    )

    st.dataframe(
        status_display,
        hide_index=True,
        use_container_width=True,
        height=max(205, 40 + 36 * max(len(status_display), 1)),
        column_config={
            "Office": st.column_config.TextColumn("Office"),
            "Actual HC": st.column_config.NumberColumn("Actual HC", format="%.2f"),
            "Required HC": st.column_config.NumberColumn("Required HC", format="%.2f"),
            "Gap": st.column_config.NumberColumn("Gap (Actual - Required)", format="%+.2f"),
            "Capacity Utilization": st.column_config.NumberColumn(
                "Capacity Utilization", format="%.0%%"
            ),
            "Status": st.column_config.TextColumn("Status"),
        },
    )

st.markdown(
    "<div class='compact-caption'>"
    "HC = Headcount | MNG = Manage / Management | PIC = Direct PIC"
    "</div>",
    unsafe_allow_html=True,
)
