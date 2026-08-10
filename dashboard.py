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
    page_title="CS Capacity & Productivity",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded",
)

APP_TITLE = "CS CAPACITY & PRODUCTIVITY"

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
    "AI": "#0B6FA8",  # Yusen Light Blue — hạ độ sáng, dùng làm blue chủ đạo
    "AE": "#2F8F6B",  # Yusen Green — hạ độ sáng cho tông trầm hơn
    "OI": "#C15A0B",  # Yusen Orange — hạ độ sáng, bớt "neon"
    "OE": "#A6791B",  # Yusen Yellow — đổi sang tông vàng đồng (gold), bỏ vàng chanh
    "TR": "#06183D",  # Yusen Dark Blue
    "CC": "#4A6FA1",  # xanh dương thép (bổ sung, cùng họ Light Blue)
    "WH": "#8A94A6",  # xám xanh trung tính (bổ sung)
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
        --navy:#0B1E3F;
        --navy-soft:#16305C;
        --blue:#0B6FA8;
        --orange:#C15A0B;
        --green:#2F8F6B;
        --amber:#A6791B;
        --amber-text:#8A6415;
        --red:#B42318;
        --muted:#5D6B82;
        --line:#DDE3EC;
        --panel:#FFFFFF;
        --page:#F4F6FA;
        --heading-font:"Segoe UI","Helvetica Neue",Arial,sans-serif;
    }
    html, body, [class*="css"] {font-family:"Segoe UI","Helvetica Neue",Arial,sans-serif;}
    .stApp {background:var(--page);}
    [data-testid="stSidebar"] {
        background:var(--navy);
        color:#FFFFFF;
        border-right:1px solid #0A1830;
    }
    section[data-testid="stSidebar"] label {
        color:#DCE3EF !important;
        font-weight:600 !important;
        font-size:0.8rem !important;
        text-transform:uppercase;
        letter-spacing:0.04em;
    }
    section[data-testid="stSidebar"] div[data-baseweb="select"] > div {
        background-color:#FFFFFF !important;
        color:#172033 !important;
        border-radius:4px !important;
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
    .block-container {max-width:1650px;padding-top:2.6rem;padding-bottom:2rem;}
    .dashboard-title {
        font-family:var(--heading-font);
        font-size:1.55rem;font-weight:700;color:var(--navy);
        margin-bottom:0.15rem;letter-spacing:0.01em;
    }
    .dashboard-subtitle {color:var(--muted);font-size:0.8rem;margin-bottom:1.1rem;padding-bottom:0.9rem;border-bottom:1px solid var(--line);}
    .section-title {
        font-family:var(--heading-font);
        background:var(--navy-soft);color:#EAEFF7;padding:0.5rem 0.9rem;
        border-radius:2px;font-weight:700;margin-top:0.25rem;
        font-size:0.92rem;letter-spacing:0.03em;
    }
    /* Executive KPI card — rounded, airy, subtle shadow like the reference dashboard */
    .kpi-card {
        background:#FFFFFF;
        border:1px solid #D9E3F0;
        border-radius:16px;
        min-height:168px;height:168px;
        display:flex;flex-direction:column;align-items:center;justify-content:center;
        box-shadow:0 4px 14px rgba(16,24,40,.055);
        text-align:center;padding:18px 18px;box-sizing:border-box;
    }
    .kpi-label {
        font-size:0.92rem;color:#0B4A8F;font-weight:700;margin-bottom:17px;
        line-height:1.25;min-height:1.2rem;display:flex;align-items:center;justify-content:center;
        text-transform:none;letter-spacing:0;
    }
    .kpi-value {
        font-size:2.35rem;font-weight:800;color:#1266C3;line-height:1.05;white-space:nowrap;
    }
    .kpi-note {font-size:0.78rem;color:#748199;margin-top:10px;line-height:1.25;min-height:1rem;}
    .orange .kpi-value {color:var(--orange);}
    .green .kpi-value {color:var(--green);}
    .amber .kpi-value {color:var(--amber-text);}
    .red .kpi-value {color:var(--red);}
    div[data-testid="stDataFrame"] {border:1px solid var(--line);border-radius:4px;overflow:hidden;}
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
        font=dict(color="#172033", size=13),
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


def read_source_file(path: Path):
    """
    Đọc trực tiếp file Excel mỗi lần rerun — KHÔNG cache ở bước này, vì mtime
    không đáng tin cậy khi Streamlit Cloud deploy lại từ GitHub (git checkout
    gán mtime = thời điểm checkout cho MỌI file, kể cả file không đổi, nên
    không phân biệt được file nào thực sự mới).
    Đọc file thô rất nhanh (chỉ I/O, chưa parse) nên không tốn chi phí đáng kể.
    Phần xử lý nặng (parse Excel) vẫn được cache đúng ở các hàm parse_* bên dưới,
    vì Streamlit tự hash theo NỘI DUNG bytes của file_bytes — tự động nhận diện
    đúng khi nội dung file thay đổi, không phụ thuộc mtime.
    """
    return path.read_bytes(), path.name


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
    """
    Sheet 'Shipment volume'.
    Source of truth for total shipment volume and active customers by Office/Month.
    """
    df = pd.read_excel(
        io.BytesIO(file_bytes),
        sheet_name="Shipment volume",
        header=1,
    )
    df.columns = [clean_text(c) for c in df.columns]

    rename_map = {}
    for c in df.columns:
        cf = c.casefold()
        if cf == "office":
            rename_map[c] = "Office"
        elif cf == "month":
            rename_map[c] = "Month"
        elif cf == "active customers":
            rename_map[c] = "Active Customers"
        elif cf == "total":
            rename_map[c] = "TOTAL"

    df = df.rename(columns=rename_map)

    if "Office" not in df.columns or "Month" not in df.columns:
        return pd.DataFrame()

    df["Office"] = df["Office"].map(clean_text)
    df["Month"] = df["Month"].map(normalize_month)

    numeric_cols = [c for c in df.columns if c not in ["Office", "Month"]]
    for c in numeric_cols:
        df[c] = pd.to_numeric(df[c], errors="coerce")

    return df[
        df["Office"].ne("") & df["Month"].isin(MONTH_ORDER)
    ].reset_index(drop=True)


@st.cache_data(show_spinner=False)
def parse_yvf(file_bytes: bytes) -> pd.DataFrame:
    """
    Sheet 'YVF Promotion Effectiveness':
    OFFICE | Month | Total YVF Bookings | Total IFF Shipments | YVF Booking Ratio
    """
    empty_cols = [
        "Office", "Month",
        "YVF Bookings", "IFF Shipments", "YVF Ratio",
    ]

    try:
        df = pd.read_excel(
            io.BytesIO(file_bytes),
            sheet_name="YVF Promotion Effectiveness",
            header=1,
        )
    except Exception:
        return pd.DataFrame(columns=empty_cols)

    df.columns = [clean_text(c) for c in df.columns]

    exact_map = {
        "OFFICE": "Office",
        "Office": "Office",
        "Month": "Month",
        "Total YVF Bookings": "YVF Bookings",
        "Total IFF Shipments": "IFF Shipments",
        "YVF Booking Ratio": "YVF Ratio",
    }
    df = df.rename(columns={c: exact_map[c] for c in df.columns if c in exact_map})

    if "Office" not in df.columns or "Month" not in df.columns:
        return pd.DataFrame(columns=empty_cols)

    for c in ["YVF Bookings", "IFF Shipments", "YVF Ratio"]:
        if c not in df.columns:
            df[c] = np.nan
        selected = df.loc[:, c]
        if isinstance(selected, pd.DataFrame):
            selected = selected.iloc[:, 0]
        df[c] = pd.to_numeric(selected, errors="coerce")

    df["Office"] = df["Office"].map(clean_text)
    df["Month"] = df["Month"].map(normalize_month)

    # Recalculate ratio to avoid stale Excel formula cache.
    df["YVF Ratio"] = np.where(
        df["IFF Shipments"].fillna(0) > 0,
        df["YVF Bookings"].fillna(0) / df["IFF Shipments"],
        np.nan,
    )

    return df.loc[
        df["Office"].ne("") & df["Month"].isin(MONTH_ORDER),
        empty_cols,
    ].reset_index(drop=True)



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

source_bytes, source_name = read_source_file(source_path)

try:
    hc = parse_hc(source_bytes)
    bu = parse_bu_allocation(source_bytes)
    shipment = parse_shipment_volume(source_bytes)
    cs_fte = parse_cs_fte(source_bytes)
    customer = parse_customer_lists(source_bytes)
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
st.sidebar.markdown(
    "<div style='color:#FFFFFF;font-family:\"Segoe UI\",\"Helvetica Neue\",Arial,sans-serif;font-size:1.1rem;font-weight:700;letter-spacing:0.02em;'>CS Division</div>",
    unsafe_allow_html=True,
)
st.sidebar.markdown(
    "<div style='color:#A9B6CC;font-size:0.78rem;margin-top:2px;margin-bottom:14px;'>Capacity & Productivity Dashboard</div>",
    unsafe_allow_html=True,
)
st.sidebar.markdown("---")


def reset_child_filters():
    """Reset Customer khi Office hoặc Month thay đổi."""
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
hc_months_with_data = set(
    hc.loc[
        hc["Total Approved HC"].notna()
        | hc["Total Actual HC"].notna()
        | (hc["Total Required HC"].fillna(0) > 0),
        "Month",
    ].dropna().astype(str)
)

bu_months_with_data = set(
    bu.loc[
        bu["Total Workload"].fillna(0) != 0,
        "Month",
    ].dropna().astype(str)
)

fte_months_with_data = set(
    cs_fte.loc[
        cs_fte["FTE"].fillna(0) != 0,
        "Month",
    ].dropna().astype(str)
)

customer_months_with_data = set(
    customer.loc[
        customer["Customer Shipment Volume"].fillna(0) != 0,
        "Month",
    ].dropna().astype(str)
)

shipment_months_with_data = set()
if not shipment.empty and "TOTAL" in shipment.columns:
    shipment_months_with_data = set(
        shipment.loc[
            shipment["TOTAL"].fillna(0) != 0,
            "Month",
        ].dropna().astype(str)
    )

yvf_months_with_data = set()
if not yvf.empty:
    yvf_months_with_data = set(
        yvf.loc[
            yvf[["YVF Bookings", "IFF Shipments"]].fillna(0).sum(axis=1) != 0,
            "Month",
        ].dropna().astype(str)
    )

available_month_set = (
    hc_months_with_data
    | bu_months_with_data
    | fte_months_with_data
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

# 3) Phạm vi CS FTE theo Office + Month (dùng cho bảng CS FTE Status bên dưới,
# không còn là filter chọn 1 CS PIC cụ thể)
if cs_fte.empty:
    pic_scope = cs_fte.copy()
elif month == "All":
    pic_scope = cs_fte.copy()
else:
    pic_scope = cs_fte[cs_fte["Month"].eq(month)].copy()

if office != "All Offices" and not pic_scope.empty:
    pic_scope = pic_scope[pic_scope["Office"].eq(office)]

cs_pic = "All CS PIC"  # không còn filter theo CS PIC — giữ biến để tương thích các đoạn tính toán bên dưới

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
st.sidebar.caption(f"Data source: {source_name}")

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

# Shipment volume / YVF filters
filtered_shipment = shipment.copy()
filtered_yvf = yvf.copy()

if month != "All":
    if not filtered_shipment.empty:
        filtered_shipment = filtered_shipment[filtered_shipment["Month"].eq(month)].copy()
    if not filtered_yvf.empty:
        filtered_yvf = filtered_yvf[filtered_yvf["Month"].eq(month)].copy()

if office != "All Offices":
    if not filtered_shipment.empty:
        filtered_shipment = filtered_shipment[filtered_shipment["Office"].eq(office)].copy()
    if not filtered_yvf.empty:
        filtered_yvf = filtered_yvf[filtered_yvf["Office"].eq(office)].copy()

# Filter Customer chỉ áp dụng cho Customer Shipment Volume, không làm giảm workload/FTE.
filtered_customer = cust_scope.copy()
if selected_customer != "All Customers" and not filtered_customer.empty:
    filtered_customer = filtered_customer[filtered_customer["Customer"].eq(selected_customer)]

selected_base_workload = float(filtered_bu["Total Workload"].sum())

# --- Phân bổ theo CS PIC ---
# Dữ liệu nguồn không có workload theo từng BU cho mỗi CS PIC, chỉ có FTE theo
# Office/Month. Khi lọc theo 1 CS PIC cụ thể, workload của Office được ƯỚC TÍNH
# phân bổ theo tỷ trọng FTE của CS PIC đó trong tổng FTE của Office/Month.
pic_workload_minutes = None
pic_fte_value = None
pic_share = None

if cs_pic != "All CS PIC" and not pic_scope.empty:
    selected_pic_rows = pic_scope[pic_scope["CS PIC"].eq(cs_pic)].copy()

    if month == "All":
        selected_pic_rows = selected_pic_rows[
            selected_pic_rows["Month"].astype(str).isin(workload_months_with_data)
        ]
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

# Số tháng dùng làm mẫu số tính Required FTE: đếm theo tháng THỰC SỰ có Workload > 0
# trong BU Workload Allocation (đúng theo Office đang chọn) — không dùng theo union tất cả sheet,
# vì HC/CS FTE có thể có sẵn dòng cho các tháng chưa nhập Workload, làm mẫu số bị thổi phồng
# và Required FTE bị pha loãng sai (VD: workload 2 tháng nhưng chia cho năng lực 12 tháng).
# ============================================================
# MONTHS WITH REAL WORKLOAD DATA
# Chỉ những tháng có Total Workload khác 0 mới được dùng để tính
# Required FTE / bình quân / capacity cho kỳ "All".
# ============================================================
if month == "All":
    workload_months_with_data = [
        m for m in MONTH_ORDER
        if m in set(
            filtered_bu.loc[
                filtered_bu["Total Workload"].fillna(0) != 0,
                "Month",
            ].astype(str)
        )
    ]
else:
    month_has_workload = (
        not filtered_bu.empty
        and filtered_bu["Total Workload"].fillna(0).sum() != 0
    )
    workload_months_with_data = [month] if month_has_workload else []

selected_month_count = len(workload_months_with_data)

if selected_month_count > 0:
    period_capacity_minutes = FTE_MINUTES * selected_month_count
    required_fte = selected_base_workload / period_capacity_minutes
    service["Required FTE"] = service["Base_Workload"] / period_capacity_minutes
else:
    period_capacity_minutes = np.nan
    required_fte = np.nan
    service["Required FTE"] = np.nan

# Shipment Volume = tổng Core Volume theo sheet "BU Workload Allocation"
# (Customer filter không áp dụng ở đây vì sheet này không có breakdown theo khách hàng).
total_shipments = float(filtered_bu["Core Volume"].fillna(0).sum())

# --- YVF KPI ---
yvf_bookings = (
    float(filtered_yvf["YVF Bookings"].fillna(0).sum())
    if not filtered_yvf.empty else 0.0
)
iff_shipments = (
    float(filtered_yvf["IFF Shipments"].fillna(0).sum())
    if not filtered_yvf.empty else 0.0
)
yvf_ratio = (
    yvf_bookings / iff_shipments
    if iff_shipments > 0 else np.nan
)

# --- HC KPI ---
hc_valid = filtered_hc[
    filtered_hc["Total Actual HC"].notna()
    | filtered_hc["Total Required HC"].notna()
    | filtered_hc["Total Approved HC"].notna()
].copy()

if hc_valid.empty:
    approved_hc = actual_hc = required_hc_total = hc_utilization = np.nan
    approved_mng = approved_pic = actual_mng = actual_pic = required_mng = required_pic = np.nan
    hc_status = "No data"
else:
    if month == "All":
        # Chỉ lấy HC của những tháng thực sự có workload.
        hc_for_period = hc_valid[
            hc_valid["Month"].astype(str).isin(workload_months_with_data)
        ].copy()

        if hc_for_period.empty:
            approved_hc = actual_hc = required_hc_total = hc_utilization = np.nan
            approved_mng = approved_pic = actual_mng = actual_pic = required_mng = required_pic = np.nan
            hc_status = "No data"
        else:
            hc_monthly = (
                hc_for_period.groupby("Month", as_index=False)
                .agg(
                    Approved_HC=("Total Approved HC", "sum"),
                    Actual_HC=("Total Actual HC", "sum"),
                    Required_HC=("Total Required HC", "sum"),
                    Approved_MNG=("Approved HC MNG", "sum"),
                    Approved_PIC=("Approved HC PIC", "sum"),
                    Actual_MNG=("Actual HC MNG", "sum"),
                    Actual_PIC=("Actual HC PIC", "sum"),
                    Required_MNG=("Required HC MNG", "sum"),
                    Required_PIC=("Required HC PIC", "sum"),
                )
            )
            approved_hc = float(hc_monthly["Approved_HC"].mean())
            actual_hc = float(hc_monthly["Actual_HC"].mean())
            required_hc_total = float(hc_monthly["Required_HC"].mean())
            approved_mng = float(hc_monthly["Approved_MNG"].mean())
            approved_pic = float(hc_monthly["Approved_PIC"].mean())
            actual_mng = float(hc_monthly["Actual_MNG"].mean())
            actual_pic = float(hc_monthly["Actual_PIC"].mean())
            required_mng = float(hc_monthly["Required_MNG"].mean())
            required_pic = float(hc_monthly["Required_PIC"].mean())
    else:
        approved_hc = float(hc_valid["Total Approved HC"].sum())
        actual_hc = float(hc_valid["Total Actual HC"].sum())
        required_hc_total = float(hc_valid["Total Required HC"].sum())
        approved_mng = float(hc_valid["Approved HC MNG"].sum())
        approved_pic = float(hc_valid["Approved HC PIC"].sum())
        actual_mng = float(hc_valid["Actual HC MNG"].sum())
        actual_pic = float(hc_valid["Actual HC PIC"].sum())
        required_mng = float(hc_valid["Required HC MNG"].sum())
        required_pic = float(hc_valid["Required HC PIC"].sum())

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
        office_hc_period = hc_valid[
            hc_valid["Month"].astype(str).isin(workload_months_with_data)
        ].copy()

        office_month = (
            office_hc_period.groupby(["Office", "Month"], as_index=False)
            .agg(
                Actual=("Total Actual HC", "sum"),
                Required=("Total Required HC", "sum"),
            )
        )

        office_hc_status = (
            office_month.groupby("Office", as_index=False)
            .agg(
                Actual=("Actual", "mean"),
                Required=("Required", "mean"),
            )
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
    f"Month: {month} · Office: {office} · Customer: {selected_customer}"
)
st.markdown(f'<div class="dashboard-subtitle">{filter_summary}</div>', unsafe_allow_html=True)

# --- Banner cảnh báo Office đang Overload ---
if overloaded_offices:
    st.error(f"Đang quá tải (Overload): {', '.join(overloaded_offices)}")

# ============================================================
# OFFICE CAPACITY SNAPSHOT
# Wording / flow aligned to sheet "Ms. HH"
# ============================================================
st.markdown('<div class="section-title">OFFICE CAPACITY SNAPSHOT</div>', unsafe_allow_html=True)
st.markdown("<div style='height:8px'></div>", unsafe_allow_html=True)


def _hc_value(v):
    return "—" if pd.isna(v) else f"{v:,.2f}".rstrip("0").rstrip(".")


def _mng_pic_line(mgr, pic):
    if pd.isna(mgr) and pd.isna(pic):
        return '<div class="kpi-note">&nbsp;</div>'
    return (
        '<div class="kpi-note" style="display:flex;justify-content:space-between;'
        'font-size:0.88rem;font-weight:700;color:var(--orange);">'
        f'<span>MNG: {_hc_value(mgr)}</span><span>PIC: {_hc_value(pic)}</span>'
        '</div>'
    )


def _hc_kpi_card(label, value, note_html="", value_color="#1266C3", value_size="2.1rem"):
    note = note_html if note_html else '<div class="kpi-note">&nbsp;</div>'
    st.markdown(
        f"""
        <div class="kpi-card">
            <div class="kpi-label" style="font-weight:800;">{label}</div>
            <div class="kpi-value" style="font-size:{value_size};font-weight:800;color:{value_color};">{value}</div>
            {note}
        </div>
        """,
        unsafe_allow_html=True,
    )


display_hc_status = "Less Load" if hc_status == "Low Load" else hc_status
status_color_map = {
    "Overload": "var(--red)",
    "High Load": "var(--orange)",
    "Balanced": "var(--green)",
    "Less Load": "var(--navy)",
    "No data": "var(--muted)",
}
status_text_color = status_color_map.get(display_hc_status, "var(--navy)")
util_text = "—" if pd.isna(hc_utilization) else f"{hc_utilization:.0%}"
hc_variance = (actual_hc - required_hc_total) if (not pd.isna(actual_hc) and not pd.isna(required_hc_total)) else np.nan
variance_text = "—" if pd.isna(hc_variance) else f"{hc_variance:+.2f}"
variance_color = "var(--red)" if (not pd.isna(hc_variance) and hc_variance < -0.005) else "var(--green)"

hc1, hc2, hc3, hc4, hc5 = st.columns(5, gap="medium")
with hc1:
    _hc_kpi_card("Approved HC", _hc_value(approved_hc), _mng_pic_line(approved_mng, approved_pic))
with hc2:
    _hc_kpi_card("Actual HC", _hc_value(actual_hc), _mng_pic_line(actual_mng, actual_pic))
with hc3:
    _hc_kpi_card("Required HC", _hc_value(required_hc_total), _mng_pic_line(required_mng, required_pic), "var(--orange)")
with hc4:
    _hc_kpi_card("Capacity Utilization", util_text, value_color="var(--amber-text)", value_size="1.9rem")
with hc5:
    _hc_kpi_card("Workload Status", display_hc_status, value_color=status_text_color, value_size="1.45rem")

st.markdown("<br>", unsafe_allow_html=True)
st.markdown('<div style="font-size:0.82rem;font-weight:700;color:#5D6B82;margin-bottom:6px;">ACTUAL HC vs REQUIRED HC</div>', unsafe_allow_html=True)
hc_gap_data = office_hc_status.dropna(subset=["Actual", "Required"]).copy()
offices_with_actual_data = set(hc_valid.loc[hc_valid["Total Actual HC"].notna(), "Office"].astype(str))
hc_gap_data = hc_gap_data[hc_gap_data["Office"].isin(offices_with_actual_data)].copy()

if hc_gap_data.empty:
    st.info("No Actual HC / Required HC data is available for the selected filters.")
else:
    hc_gap_data["HC Variance"] = hc_gap_data["Actual"] - hc_gap_data["Required"]
    hc_gap_data = hc_gap_data.sort_values("HC Variance", ascending=True).reset_index(drop=True)

    gap_chart_col, gap_table_col = st.columns([1.65, 1], gap="medium")
    with gap_chart_col:
        fig = go.Figure()
        fig.add_trace(go.Bar(
            y=hc_gap_data["Office"], x=hc_gap_data["Actual"], name="Actual HC",
            orientation="h", marker_color="#0B6FA8",
            text=hc_gap_data["Actual"].map(lambda v: f"{v:.2f}"), textposition="outside",
            cliponaxis=False,
            hovertemplate="Office: %{y}<br>Actual HC: %{x:.2f}<extra></extra>",
        ))
        fig.add_trace(go.Bar(
            y=hc_gap_data["Office"], x=hc_gap_data["Required"], name="Required HC",
            orientation="h", marker_color="#C15A0B",
            text=hc_gap_data["Required"].map(lambda v: f"{v:.2f}"), textposition="outside",
            cliponaxis=False,
            hovertemplate="Office: %{y}<br>Required HC: %{x:.2f}<extra></extra>",
        ))
        max_x = float(hc_gap_data[["Actual", "Required"]].max().max()) if not hc_gap_data.empty else 0
        fig.update_layout(
            barmode="group", bargap=0.34, bargroupgap=0.08,
            height=max(260, 150 + len(hc_gap_data) * 62),
            margin=dict(l=15, r=45, t=15, b=55), paper_bgcolor="white", plot_bgcolor="white",
            legend=dict(orientation="h", y=-0.18, x=0, title=""),
            font=dict(color="#172033", size=13), xaxis_title="Headcount", yaxis_title="",
        )
        fig.update_xaxes(range=[0, max(max_x * 1.22, 1)], gridcolor="#E9EEF5", zeroline=False)
        fig.update_yaxes(showgrid=False, autorange="reversed")
        st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})

    with gap_table_col:
        gap_table = hc_gap_data[["Office", "Actual", "Required", "HC Variance"]].rename(
            columns={"Actual": "Actual HC", "Required": "Required HC"}
        )
        st.dataframe(
            gap_table, hide_index=True, use_container_width=True,
            height=table_height(len(gap_table), cap=340),
            column_config={
                "Actual HC": st.column_config.NumberColumn("Actual HC", format="%.2f"),
                "Required HC": st.column_config.NumberColumn("Required HC", format="%.2f"),
                "HC Variance": st.column_config.NumberColumn("HC Variance", format="%+.2f"),
            },
        )

# ============================================================
# WORKLOAD / FTE
# Index 1 in sheet "Ms. HH"
# ============================================================
st.markdown("<br>", unsafe_allow_html=True)
st.markdown('<div class="section-title">WORKLOAD / FTE</div>', unsafe_allow_html=True)
st.markdown("<div style='height:8px'></div>", unsafe_allow_html=True)

wk1, wk2, wk3 = st.columns(3, gap="medium")
with wk1:
    kpi_card("Total Workload", fmt_hours(selected_base_workload), "Total Standard Time")
with wk2:
    req_fte_text = "—" if pd.isna(required_fte) else f"{required_fte:.2f}"
    kpi_card("Required FTE", req_fte_text, "Based on selected workload", "orange")
with wk3:
    kpi_card("Standard Capacity / FTE", f"{FTE_MINUTES / 60:,.1f} h", "8h × 95% × 22 days / month")

st.caption(
    "Total Standard Time = Core Service + Ancillary Services + Supporting Activities + Exception Handling (if applicable). "
    "1 FTE = 10,032 minutes / month."
)

show_trend = False
trend = None
if month == "All":
    trend = (
        filtered_bu.groupby("Month", as_index=False)["Total Workload"].sum()
        .set_index("Month").reindex(available_months).reset_index().rename(columns={"index": "Month"})
    )
    trend["Total Workload"] = trend["Total Workload"].fillna(0)
    trend["Total Workload (h)"] = trend["Total Workload"] / 60
    trend["Required FTE"] = trend["Total Workload"] / FTE_MINUTES
    show_trend = trend["Total Workload (h)"].sum() > 0

if show_trend:
    st.markdown("<br>", unsafe_allow_html=True)
    st.markdown('<div style="font-size:0.82rem;font-weight:700;color:#5D6B82;margin-bottom:6px;">WORKLOAD TREND BY MONTH</div>', unsafe_allow_html=True)
    trend_chart_col, trend_table_col = st.columns([1.65, 1], gap="medium")
    with trend_chart_col:
        fig = px.line(trend, x="Month", y="Total Workload (h)", markers=True)
        fig.update_traces(line_color="#0B6FA8", marker=dict(size=7, color="#0B6FA8"))
        standard_chart_layout(fig, 310)
        fig.update_yaxes(rangemode="tozero")
        st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})
    with trend_table_col:
        trend_detail = trend[["Month", "Total Workload (h)", "Required FTE"]].copy()
        st.dataframe(
            trend_detail, hide_index=True, use_container_width=True,
            height=table_height(len(trend_detail), cap=310),
            column_config={
                "Total Workload (h)": st.column_config.NumberColumn("Total Workload (h)", format="%.1f"),
                "Required FTE": st.column_config.NumberColumn("Required FTE", format="%.2f"),
            },
        )

if month == "All":
    if workload_months_with_data:
        st.caption(
            f"Calculation period: {len(workload_months_with_data)} month(s) with actual workload data "
            f"({', '.join(workload_months_with_data)}). Months without workload are excluded from capacity calculations."
        )
    else:
        st.caption("No month with actual workload data is available for the selected filters.")

# ============================================================
# OFFICE × SEGMENT WORKLOAD MATRIX
# Allocation Time / Allocation Ratio / Required FTE by service
# ============================================================
st.markdown("<br>", unsafe_allow_html=True)
st.markdown('<div class="section-title">WORKLOAD ALLOCATION BY SERVICE</div>', unsafe_allow_html=True)
REPORT_SERVICE_ORDER = ["AE", "AI", "OE", "OI", "CC", "TR", "WH"]

matrix_source = filtered_bu.copy()
workload_matrix = (
    matrix_source.groupby(["Office", "Segment"], as_index=False)["Total Workload"].sum()
    .pivot(index="Office", columns="Segment", values="Total Workload")
    .reindex(columns=REPORT_SERVICE_ORDER, fill_value=0).fillna(0) / 60
)
if office == "All Offices":
    matrix_office_order = [o for o in all_offices if o in workload_matrix.index]
else:
    matrix_office_order = [office] if office in workload_matrix.index else []
workload_matrix = workload_matrix.reindex(matrix_office_order).fillna(0)
workload_matrix["TOTAL"] = workload_matrix.sum(axis=1)
workload_total_row = pd.DataFrame([workload_matrix.sum(axis=0)], index=["TOTAL"]) if not workload_matrix.empty else pd.DataFrame(
    [[0] * (len(REPORT_SERVICE_ORDER) + 1)], index=["TOTAL"], columns=REPORT_SERVICE_ORDER + ["TOTAL"]
)
workload_matrix_display = pd.concat([workload_matrix, workload_total_row])
workload_matrix_display.index.name = "OFFICE"
workload_matrix_display = workload_matrix_display.reset_index()

segment_summary = (
    matrix_source.groupby("Segment", as_index=False)["Total Workload"].sum()
    .rename(columns={"Total Workload": "Workload Minutes"})
)
segment_summary = pd.DataFrame({"Segment": REPORT_SERVICE_ORDER}).merge(segment_summary, on="Segment", how="left").fillna(0)
segment_summary["Workload Hours"] = segment_summary["Workload Minutes"] / 60
segment_total_min = float(segment_summary["Workload Minutes"].sum())
segment_summary["Allocation Ratio"] = np.where(segment_total_min > 0, segment_summary["Workload Minutes"] / segment_total_min, 0)
if selected_month_count > 0:
    segment_summary["Required FTE"] = segment_summary["Workload Minutes"] / (FTE_MINUTES * selected_month_count)
else:
    segment_summary["Required FTE"] = np.nan

matrix_chart_col, matrix_table_col = st.columns([1.35, 1.15], gap="medium")
with matrix_chart_col:
    chart_data = segment_summary.sort_values("Workload Hours", ascending=True)
    fig = px.bar(chart_data, x="Workload Hours", y="Segment", orientation="h", text="Workload Hours",
                 color="Segment", color_discrete_map=SEGMENT_COLORS)
    fig.update_traces(texttemplate="%{text:,.1f} h", textposition="outside", cliponaxis=False)
    standard_chart_layout(fig, 350)
    fig.update_layout(showlegend=False)
    max_h = chart_data["Workload Hours"].max()
    if pd.notna(max_h) and max_h > 0:
        fig.update_xaxes(range=[0, max_h * 1.22])
    st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})
with matrix_table_col:
    st.dataframe(
        workload_matrix_display, hide_index=True, use_container_width=True,
        height=table_height(len(workload_matrix_display), cap=350),
        column_config={
            "OFFICE": st.column_config.TextColumn("OFFICE"),
            **{seg: st.column_config.NumberColumn(seg, format="%.1f") for seg in REPORT_SERVICE_ORDER},
            "TOTAL": st.column_config.NumberColumn("TOTAL", format="%.1f"),
        },
    )

segment_detail = segment_summary[["Segment", "Workload Hours", "Allocation Ratio", "Required FTE"]].copy()
st.dataframe(
    segment_detail, hide_index=True, use_container_width=True,
    height=table_height(len(segment_detail), cap=315),
    column_config={
        "Workload Hours": st.column_config.NumberColumn("Allocation Time (h)", format="%.1f"),
        "Allocation Ratio": st.column_config.NumberColumn("Allocation Ratio", format="%.1f%%"),
        "Required FTE": st.column_config.NumberColumn("Required FTE", format="%.2f"),
    },
)

# ============================================================
# WORKLOAD BREAKDOWN BY SERVICE TYPE AND ACTIVITY
# ============================================================
st.markdown("<br>", unsafe_allow_html=True)
st.markdown('<div class="section-title">WORKLOAD BREAKDOWN BY SERVICE TYPE AND ACTIVITY</div>', unsafe_allow_html=True)

workload_cols = ["Core Workload", "Ancillary Workload", "Supporting Workload", "Exception Workload", "Total Workload"]
workload_service = filtered_bu.groupby("Segment", as_index=False)[workload_cols].sum()
workload_service = pd.DataFrame({"Segment": REPORT_SERVICE_ORDER}).merge(workload_service, on="Segment", how="left").fillna(0)
workload_service["Core Service (h)"] = workload_service["Core Workload"] / 60
workload_service["Ancillary Service (h)"] = workload_service["Ancillary Workload"] / 60
workload_service["Supporting Activity (h)"] = workload_service["Supporting Workload"] / 60
workload_service["Exception Handling (h)"] = workload_service["Exception Workload"] / 60
workload_service["Total Workload (h)"] = workload_service["Total Workload"] / 60

total_workload_hours = float(workload_service["Total Workload (h)"].sum())
workload_service["Ratio"] = np.where(total_workload_hours > 0, workload_service["Total Workload (h)"] / total_workload_hours, 0)
workload_table = workload_service[[
    "Segment", "Core Service (h)", "Ancillary Service (h)", "Supporting Activity (h)",
    "Exception Handling (h)", "Total Workload (h)", "Ratio"
]].copy()
workload_total = pd.DataFrame([{
    "Segment": "TOTAL",
    "Core Service (h)": workload_table["Core Service (h)"].sum(),
    "Ancillary Service (h)": workload_table["Ancillary Service (h)"].sum(),
    "Supporting Activity (h)": workload_table["Supporting Activity (h)"].sum(),
    "Exception Handling (h)": workload_table["Exception Handling (h)"].sum(),
    "Total Workload (h)": workload_table["Total Workload (h)"].sum(),
    "Ratio": 1.0 if total_workload_hours > 0 else 0.0,
}])
workload_table_display = pd.concat([workload_table, workload_total], ignore_index=True)

workload_chart_col, workload_table_col = st.columns([1.45, 1.15], gap="medium")
with workload_chart_col:
    fig = go.Figure()
    activity_series = [
        ("Core Service", "Core Service (h)", "#16305C"),
        ("Ancillary Service", "Ancillary Service (h)", "#0B6FA8"),
        ("Supporting Activity", "Supporting Activity (h)", "#2F8F6B"),
        ("Exception Handling", "Exception Handling (h)", "#C15A0B"),
    ]
    for activity_name, col_name, color in activity_series:
        fig.add_trace(go.Bar(
            y=workload_service["Segment"], x=workload_service[col_name], name=activity_name,
            orientation="h", marker_color=color,
            hovertemplate=f"<b>%{{y}}</b><br>{activity_name}: %{{x:,.1f}} h<extra></extra>",
        ))
    for _, row in workload_service.iterrows():
        if row["Total Workload (h)"] > 0:
            fig.add_annotation(
                x=row["Total Workload (h)"], y=row["Segment"],
                text=f"  {row['Total Workload (h)']:,.1f} h | {row['Ratio']:.1%}",
                showarrow=False, xanchor="left", font=dict(size=11, color="#172033"),
            )
    fig.update_layout(barmode="stack", showlegend=True, legend=dict(orientation="h", y=-0.18, x=0, title=""))
    fig.update_yaxes(categoryorder="array", categoryarray=list(reversed(REPORT_SERVICE_ORDER)), showgrid=False)
    max_workload = workload_service["Total Workload (h)"].max()
    if pd.notna(max_workload) and max_workload > 0:
        fig.update_xaxes(range=[0, max_workload * 1.35])
    standard_chart_layout(fig, 370)
    st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})
with workload_table_col:
    st.dataframe(
        workload_table_display, hide_index=True, use_container_width=True,
        height=table_height(len(workload_table_display), cap=370),
        column_config={
            "Core Service (h)": st.column_config.NumberColumn("Core (h)", format="%.1f"),
            "Ancillary Service (h)": st.column_config.NumberColumn("Ancillary (h)", format="%.1f"),
            "Supporting Activity (h)": st.column_config.NumberColumn("Supporting (h)", format="%.1f"),
            "Exception Handling (h)": st.column_config.NumberColumn("Exception (h)", format="%.1f"),
            "Total Workload (h)": st.column_config.NumberColumn("Total (h)", format="%.1f"),
            "Ratio": st.column_config.NumberColumn("Ratio", format="%.1f%%"),
        },
    )

# ============================================================
# SHIPMENT VOLUME BY SERVICE
# ============================================================
st.markdown("<br>", unsafe_allow_html=True)
st.markdown('<div class="section-title">SHIPMENT VOLUME BY SERVICE</div>', unsafe_allow_html=True)

volume_source = filtered_bu.copy()
volume_by_office = (
    volume_source.groupby(["Office", "Segment"], as_index=False)["Core Volume"].sum()
    .pivot(index="Office", columns="Segment", values="Core Volume")
    .reindex(columns=REPORT_SERVICE_ORDER, fill_value=0).fillna(0)
)
if office == "All Offices":
    volume_office_order = [o for o in all_offices if o in volume_by_office.index]
else:
    volume_office_order = [office] if office in volume_by_office.index else []
volume_by_office = volume_by_office.reindex(volume_office_order).fillna(0)
volume_by_office["TOTAL"] = volume_by_office.sum(axis=1)
volume_total_row = pd.DataFrame([volume_by_office.sum(axis=0)], index=["TOTAL"]) if not volume_by_office.empty else pd.DataFrame(
    [[0] * (len(REPORT_SERVICE_ORDER) + 1)], index=["TOTAL"], columns=REPORT_SERVICE_ORDER + ["TOTAL"]
)
volume_table = pd.concat([volume_by_office, volume_total_row]); volume_table.index.name = "OFFICE"; volume_table = volume_table.reset_index()

volume_service = volume_source.groupby("Segment", as_index=False)["Core Volume"].sum().rename(columns={"Core Volume": "Shipment Volume"})
volume_service = pd.DataFrame({"Segment": REPORT_SERVICE_ORDER}).merge(volume_service, on="Segment", how="left").fillna(0)
shipment_total = float(volume_service["Shipment Volume"].sum())
volume_service["Share"] = np.where(shipment_total > 0, volume_service["Shipment Volume"] / shipment_total, 0)
volume_service["Label"] = volume_service.apply(lambda r: f"{r['Shipment Volume']:,.0f}<br>{r['Share']:.1%}", axis=1)

volume_chart_col, volume_table_col = st.columns([1.35, 1.15], gap="medium")
with volume_chart_col:
    fig = px.bar(volume_service, x="Segment", y="Shipment Volume", text="Label",
                 category_orders={"Segment": REPORT_SERVICE_ORDER}, color="Segment", color_discrete_map=SEGMENT_COLORS)
    fig.update_traces(textposition="outside", cliponaxis=False, width=0.62,
                      hovertemplate="<b>%{x}</b><br>Shipment Volume: %{y:,.0f}<extra></extra>")
    max_volume = volume_service["Shipment Volume"].max()
    if pd.notna(max_volume) and max_volume > 0:
        fig.update_yaxes(range=[0, max_volume * 1.25])
    standard_chart_layout(fig, 330); fig.update_layout(showlegend=False); fig.update_yaxes(rangemode="tozero")
    st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})
with volume_table_col:
    st.dataframe(
        volume_table, hide_index=True, use_container_width=True,
        height=table_height(len(volume_table), cap=330),
        column_config={"OFFICE": st.column_config.TextColumn("OFFICE"),
                       **{seg: st.column_config.NumberColumn(seg, format="localized") for seg in REPORT_SERVICE_ORDER},
                       "TOTAL": st.column_config.NumberColumn("TOTAL", format="localized")},
    )

# ============================================================
# OFFICE WORKLOAD & CAPACITY
# ============================================================
st.markdown("<br>", unsafe_allow_html=True)
st.markdown('<div class="section-title">OFFICE WORKLOAD & CAPACITY</div>', unsafe_allow_html=True)

office_workload = filtered_bu.groupby("Office", as_index=False)["Total Workload"].sum().rename(columns={"Total Workload": "Workload Minutes"})
relevant_offices = all_offices if office == "All Offices" else [office]
office_workload = pd.DataFrame({"Office": relevant_offices}).merge(office_workload, on="Office", how="left").fillna(0)
office_workload["Workload Hours"] = office_workload["Workload Minutes"] / 60

office_capacity = office_hc_status[["Office", "Actual", "Required", "Status"]].copy() if not office_hc_status.empty else pd.DataFrame(columns=["Office","Actual","Required","Status"])
office_detail = office_workload.merge(office_capacity, on="Office", how="left")
office_detail["HC Variance"] = office_detail["Actual"] - office_detail["Required"]
office_detail["Capacity Utilization"] = office_detail.apply(lambda r: safe_divide(r["Required"], r["Actual"]) if pd.notna(r["Actual"]) and r["Actual"] else np.nan, axis=1)
office_detail["Status"] = office_detail["Status"].replace({"Low Load": "Less Load"})

ow_chart_col, ow_table_col = st.columns([1.35, 1.15], gap="medium")
with ow_chart_col:
    chart_data = office_detail.sort_values("Workload Hours", ascending=True)
    fig = px.bar(chart_data, x="Workload Hours", y="Office", orientation="h", text="Workload Hours")
    fig.update_traces(marker_color="#0B6FA8", texttemplate="%{text:,.1f} h", textposition="outside", cliponaxis=False)
    max_hours = chart_data["Workload Hours"].max()
    if pd.notna(max_hours) and max_hours > 0:
        fig.update_xaxes(range=[0, max_hours * 1.18])
    standard_chart_layout(fig, max(270, 90 + len(chart_data) * 46))
    st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})
with ow_table_col:
    office_table_display = office_detail[["Office", "Workload Hours", "Actual", "Required", "HC Variance", "Capacity Utilization", "Status"]].rename(
        columns={"Actual": "Actual HC", "Required": "Required HC", "Status": "Overall Workload Status"}
    )
    st.dataframe(
        office_table_display, hide_index=True, use_container_width=True,
        height=table_height(len(office_table_display), cap=340),
        column_config={
            "Workload Hours": st.column_config.NumberColumn("Workload (h)", format="%.1f"),
            "Actual HC": st.column_config.NumberColumn("Actual HC", format="%.2f"),
            "Required HC": st.column_config.NumberColumn("Required HC", format="%.2f"),
            "HC Variance": st.column_config.NumberColumn("HC Variance", format="%+.2f"),
            "Capacity Utilization": st.column_config.NumberColumn("Utilization", format="%.1f%%"),
        },
    )

# ============================================================
# CS PIC WORKLOAD
# ============================================================
st.markdown("<br>", unsafe_allow_html=True)
st.markdown('<div class="section-title">CS PIC WORKLOAD & FTE</div>', unsafe_allow_html=True)

if month == "All":
    pic_table = cs_fte.copy()
else:
    pic_table = cs_fte[cs_fte["Month"].eq(month)].copy()
if office != "All Offices":
    pic_table = pic_table[pic_table["Office"].eq(office)]
if month == "All" and not pic_table.empty:
    pic_table = pic_table.groupby(["Office", "CS PIC"], as_index=False).agg(FTE=("FTE", "mean"), **{"PIC Workload": ("PIC Workload", "mean")})

if pic_table.empty:
    st.info("No CS PIC FTE data available for selected filters.")
else:
    pic_table["Workload Hours"] = pic_table["PIC Workload"] / 60
    pic_table["Capacity Status"] = np.select(
        [pic_table["FTE"] > 1.00, pic_table["FTE"] > 0.95, pic_table["FTE"] >= 0.90],
        ["Overload", "High Load", "Balanced"], default="Less Load",
    )
    pic_display = pic_table[["Office", "CS PIC", "FTE", "Workload Hours", "Capacity Status"]].sort_values(["Office", "FTE"], ascending=[True, False])
    status_colors = {"Overload": "#B42318", "High Load": "#C15A0B", "Balanced": "#0B6FA8", "Less Load": "#2F8F6B"}
    pic_chart_col, pic_table_col = st.columns([1.35, 1.15], gap="medium")
    with pic_chart_col:
        chart_data = pic_display.copy(); chart_data["PIC"] = chart_data["Office"] + " · " + chart_data["CS PIC"]
        chart_data = chart_data.sort_values("Workload Hours", ascending=True)
        fig = px.bar(chart_data, x="Workload Hours", y="PIC", orientation="h", text="Workload Hours",
                     color="Capacity Status", color_discrete_map=status_colors)
        fig.update_traces(texttemplate="%{text:,.1f} h", textposition="outside", cliponaxis=False)
        pic_h = max(280, min(620, 90 + len(chart_data) * 28))
        standard_chart_layout(fig, pic_h)
        fig.update_layout(legend=dict(orientation="h", y=-0.12, x=0, title=""), margin=dict(l=15, r=15, t=20, b=60))
        st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})
    with pic_table_col:
        st.dataframe(
            pic_display, hide_index=True, use_container_width=True,
            height=table_height(len(pic_display), cap=pic_h),
            column_config={
                "FTE": st.column_config.NumberColumn("FTE", format="%.2f"),
                "Workload Hours": st.column_config.NumberColumn("Workload (h)", format="%.1f"),
            },
        )

# ============================================================
# CUSTOMER SHIPMENT VOLUME
# ============================================================
st.markdown("<br>", unsafe_allow_html=True)
st.markdown('<div class="section-title">CUSTOMER SHIPMENT VOLUME</div>', unsafe_allow_html=True)

cust_all = filtered_customer.copy()
if cust_all.empty:
    st.info("No customer volume data available for selected filters.")
else:
    cust_all = cust_all.groupby(["Office", "Customer"], as_index=False)["Customer Shipment Volume"].sum().sort_values("Customer Shipment Volume", ascending=False)
    cust_top20 = cust_all.head(20)
    cust_chart_col, cust_table_col = st.columns([1.35, 1.15], gap="medium")
    with cust_chart_col:
        fig = px.bar(cust_top20.sort_values("Customer Shipment Volume"), x="Customer Shipment Volume", y="Customer", orientation="h", text="Customer Shipment Volume")
        fig.update_traces(marker_color="#0B6FA8", texttemplate="%{text:.0f}", textposition="outside", cliponaxis=False)
        standard_chart_layout(fig, table_height(len(cust_top20), cap=460, min_h=280))
        st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})
    with cust_table_col:
        st.dataframe(cust_all.rename(columns={"Customer Shipment Volume": "Shipment Volume"}), hide_index=True, use_container_width=True,
                     height=table_height(len(cust_all), cap=460),
                     column_config={"Shipment Volume": st.column_config.NumberColumn("Shipment Volume", format="localized")})
    if len(cust_all) > 20:
        st.caption(f"Chart shows Top 20 / {len(cust_all)} customers. The detail table contains all customers in the selected scope.")

# ============================================================
# CONTROL TOWER EFFECTIVENESS
# Data will be added later by user — reserve section only, no invented KPI.
# ============================================================
st.markdown("<br>", unsafe_allow_html=True)
st.markdown('<div class="section-title">CONTROL TOWER EFFECTIVENESS</div>', unsafe_allow_html=True)
st.info(
    "Data source pending. This section is reserved for: Total Abnormality / Month, "
    "No. of Abnormalities Resolved by CS, and CS Resolution Rate."
)

# ============================================================
# YVF PROMOTER EFFECTIVENESS
# Sheet name remains "YVF Promotion Effectiveness" in Excel source.
# ============================================================
st.markdown("<br>", unsafe_allow_html=True)
st.markdown('<div class="section-title">YVF PROMOTER EFFECTIVENESS</div>', unsafe_allow_html=True)

if filtered_yvf.empty:
    st.info("No YVF Promoter Effectiveness data available for selected filters.")
else:
    yvf_bookings_total = float(filtered_yvf["YVF Bookings"].fillna(0).sum())
    yvf_iff_total = float(filtered_yvf["IFF Shipments"].fillna(0).sum())
    yvf_ratio_total = safe_divide(yvf_bookings_total, yvf_iff_total) * 100

    yk1, yk2, yk3 = st.columns(3, gap="medium")
    with yk1:
        kpi_card("Total YVF Bookings", f"{yvf_bookings_total:,.0f}", "Selected period")
    with yk2:
        kpi_card("Total IFF Shipments", f"{yvf_iff_total:,.0f}", "Selected period")
    with yk3:
        kpi_card("YVF Booking Ratio", f"{yvf_ratio_total:.1f}%", "YVF Bookings / IFF Shipments", "amber")

    st.markdown("<br>", unsafe_allow_html=True)
    yvf_trend = filtered_yvf.groupby("Month", as_index=False).agg(**{"YVF Bookings": ("YVF Bookings", "sum"), "IFF Shipments": ("IFF Shipments", "sum")})
    yvf_trend["Month"] = pd.Categorical(yvf_trend["Month"], categories=MONTH_ORDER, ordered=True)
    yvf_trend = yvf_trend.sort_values("Month")
    yvf_trend_long = yvf_trend.melt(id_vars="Month", value_vars=["YVF Bookings", "IFF Shipments"], var_name="Metric", value_name="Value")
    yvf_chart_col, yvf_table_col = st.columns([1.35, 1.15], gap="medium")
    with yvf_chart_col:
        fig = px.bar(yvf_trend_long, x="Month", y="Value", color="Metric", barmode="group", text="Value",
                     color_discrete_map={"YVF Bookings": "#0B6FA8", "IFF Shipments": "#A6791B"})
        fig.update_traces(texttemplate="%{text:,.0f}", textposition="outside", cliponaxis=False)
        standard_chart_layout(fig, 340)
        fig.update_layout(showlegend=True, legend=dict(orientation="h", y=-0.18, x=0, title=""))
        st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})
    with yvf_table_col:
        yvf_office_table = filtered_yvf.groupby("Office", as_index=False).agg(**{"YVF Bookings": ("YVF Bookings", "sum"), "IFF Shipments": ("IFF Shipments", "sum")})
        yvf_office_table["YVF Booking Ratio"] = yvf_office_table.apply(lambda r: safe_divide(r["YVF Bookings"], r["IFF Shipments"]), axis=1)
        st.dataframe(
            yvf_office_table, hide_index=True, use_container_width=True,
            height=table_height(len(yvf_office_table), cap=340),
            column_config={
                "YVF Bookings": st.column_config.NumberColumn("YVF Bookings", format="localized"),
                "IFF Shipments": st.column_config.NumberColumn("IFF Shipments", format="localized"),
                "YVF Booking Ratio": st.column_config.NumberColumn("YVF Booking Ratio", format="%.1f%%"),
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

    with st.expander("DETAIL VOLUME BY SERVICE — Core / Ancillary / Supporting / Exception"):
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

            full_summary = (
                scoped.groupby("Scope", as_index=False)["Volume"].sum()
                .sort_values("Volume", ascending=False)
            )
            full_summary["Description"] = full_summary["Scope"].map(decode_scope_code)
            top_summary = full_summary.head(15)

            total_codes = len(full_summary)
            if total_codes > 15:
                st.caption(f"Chart hiển thị Top 15 / {total_codes} mã theo Volume — bảng bên phải có đầy đủ {total_codes} mã (cuộn để xem hết).")

            chart_col, table_col = st.columns([1.6, 1], gap="medium")

            # Chiều cao đúng chuẩn Streamlit dataframe: ~38px header + ~35px/dòng.
            table_height = min(460, 38 + 35 * len(full_summary))
            chart_height = min(460, 38 + 26 * len(top_summary))

            with chart_col:
                fig = px.bar(
                    top_summary.sort_values("Volume"),
                    x="Volume", y="Scope", orientation="h", text="Volume",
                    hover_data={"Description": True},
                )
                fig.update_traces(marker_color="#00B9F2", texttemplate="%{text:,.0f}", textposition="outside", cliponaxis=False)
                standard_chart_layout(fig, chart_height)
                st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})

            with table_col:
                st.dataframe(
                    full_summary[["Scope", "Description", "Volume"]].rename(columns={"Scope": label}),
                    hide_index=True,
                    use_container_width=True,
                    height=table_height,
                    column_config={"Volume": st.column_config.NumberColumn("Volume", format="localized")},
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
                exc_top = exc_summary.head(15)
                exc_total_codes = len(exc_summary)
                if exc_total_codes > 15:
                    st.caption(f"Chart hiển thị Top 15 / {exc_total_codes} mã theo Volume — bảng bên phải có đầy đủ {exc_total_codes} mã (cuộn để xem hết).")

                exc_chart_col, exc_table_col = st.columns([1.6, 1], gap="medium")
                exc_table_height = min(460, 38 + 35 * len(exc_summary))
                exc_chart_height = min(460, 38 + 26 * len(exc_top))

                with exc_chart_col:
                    fig = px.bar(
                        exc_top.sort_values("Volume"),
                        x="Volume", y="Code", orientation="h", text="Volume",
                    )
                    fig.update_traces(marker_color="#FF6D10", texttemplate="%{text:,.0f}", textposition="outside", cliponaxis=False)
                    standard_chart_layout(fig, exc_chart_height)
                    st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})

                with exc_table_col:
                    st.dataframe(
                        exc_summary,
                        hide_index=True,
                        use_container_width=True,
                        height=exc_table_height,
                        column_config={"Volume": st.column_config.NumberColumn("Volume", format="localized")},
                    )
