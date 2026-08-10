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
        --heading-font:"Cambria","Georgia","Times New Roman",serif;
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
    .kpi-card {
        background:#FFFFFF;border:1px solid var(--line);border-radius:4px;
        min-height:158px;height:158px;display:flex;flex-direction:column;align-items:center;
        justify-content:center;box-shadow:0 1px 2px rgba(16,24,40,.04);
        text-align:center;padding:10px 12px;box-sizing:border-box;
    }
    .kpi-label {font-size:0.8rem;color:var(--muted);font-weight:600;margin-bottom:10px;line-height:1.2;min-height:1.2rem;display:flex;align-items:center;justify-content:center;text-transform:uppercase;letter-spacing:0.04em;}
    .kpi-value {font-size:2.1rem;font-weight:700;color:var(--navy);line-height:1.05;white-space:nowrap;}
    .kpi-note {font-size:0.8rem;color:var(--muted);margin-top:8px;line-height:1.25;min-height:1rem;}
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
    "<div style='color:#FFFFFF;font-family:\"Cambria\",\"Georgia\",\"Times New Roman\",serif;font-size:1.1rem;font-weight:700;letter-spacing:0.02em;'>CS Division</div>",
    unsafe_allow_html=True,
)
st.sidebar.markdown(
    "<div style='color:#A9B6CC;font-size:0.78rem;margin-top:2px;margin-bottom:14px;'>Capacity & Productivity Dashboard</div>",
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

if selected_customer != "All Customers" and not filtered_customer.empty:
    total_shipments = float(
        filtered_customer["Customer Shipment Volume"].fillna(0).sum()
    )
else:
    total_shipments = (
        float(filtered_shipment["TOTAL"].fillna(0).sum())
        if (not filtered_shipment.empty and "TOTAL" in filtered_shipment.columns)
        else 0.0
    )

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
    f"Month: {month} · Office: {office} · CS PIC: {cs_pic} · Customer: {selected_customer}"
)
st.markdown(f'<div class="dashboard-subtitle">{filter_summary}</div>', unsafe_allow_html=True)

if cs_pic != "All CS PIC":
    st.caption(
        f"Workload của CS PIC **{cs_pic}** là ước tính, phân bổ theo tỷ trọng FTE "
        f"({pic_fte_value:.2f} FTE) trên tổng FTE của Office/Month đang chọn — "
        "dữ liệu nguồn chưa có workload theo từng BU cho mỗi CS PIC."
    )

# --- Banner cảnh báo Office đang Overload ---
if overloaded_offices:
    st.error(f"Đang quá tải (Overload): {', '.join(overloaded_offices)}")

# ============================================================
# KHỐI 1: HC STATUS (tính từ sheet HC Capacity — độc lập với BU Workload Allocation)
# ============================================================
st.markdown('<div class="section-title">HEADCOUNT STATUS</div>', unsafe_allow_html=True)


def _hc_value(v):
    return "—" if pd.isna(v) else f"{v:,.2f}".rstrip("0").rstrip(".")


# --- 3 ô Approved/Actual/Required HEADCOUNT gộp chung 1 khối, có nét gạch dọc
#     phân cách, kèm dòng nhỏ MNG/PIC bên dưới mỗi số — Mgr nằm sát trái, PIC
#     nằm sát phải trong ô (đẩy ra 2 đầu) thay vì canh giữa cùng 1 chuỗi.
def _mng_pic_line(mgr, pic):
    if pd.isna(mgr) and pd.isna(pic):
        return '<div class="kpi-note">&nbsp;</div>'
    return (
        '<div class="kpi-note" style="display:flex;justify-content:space-between;">'
        f'<span>MNG: {_hc_value(mgr)}</span><span>PIC: {_hc_value(pic)}</span>'
        '</div>'
    )


hc_group_col, util_col, status_col = st.columns([3, 1, 1], gap="small")

with hc_group_col:
    st.markdown(
        f"""
        <div style="display:grid;grid-template-columns:1fr 1fr 1fr;background:#FFFFFF;
                    border:1px solid var(--line);border-radius:4px;height:158px;box-sizing:border-box;
                    box-shadow:0 1px 2px rgba(16,24,40,.04);">
            <div style="padding:10px 12px;text-align:center;border-right:1px solid var(--line);
                        display:flex;flex-direction:column;justify-content:center;">
                <div class="kpi-label" style="justify-content:center;">Approved Headcount</div>
                <div class="kpi-value" style="font-size:2.1rem;">{_hc_value(approved_hc)}</div>
                {_mng_pic_line(approved_mng, approved_pic)}
            </div>
            <div style="padding:10px 12px;text-align:center;border-right:1px solid var(--line);
                        display:flex;flex-direction:column;justify-content:center;">
                <div class="kpi-label" style="justify-content:center;">Actual Headcount</div>
                <div class="kpi-value" style="font-size:2.1rem;">{_hc_value(actual_hc)}</div>
                {_mng_pic_line(actual_mng, actual_pic)}
            </div>
            <div style="padding:10px 12px;text-align:center;
                        display:flex;flex-direction:column;justify-content:center;">
                <div class="kpi-label" style="justify-content:center;">Required Headcount</div>
                <div class="kpi-value" style="font-size:2.1rem;color:var(--orange);">{_hc_value(required_hc_total)}</div>
                {_mng_pic_line(required_mng, required_pic)}
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

with util_col:
    util_text = "—" if pd.isna(hc_utilization) else f"{hc_utilization:.0%}"
    kpi_card("Capacity Utilization", util_text, "", "amber")
with status_col:
    status_accent = {"Overload": "red", "High Load": "orange", "Balanced": "green", "Low Load": ""}.get(hc_status, "")
    kpi_card("Capacity Status", hc_status, "", status_accent)

st.markdown("<br>", unsafe_allow_html=True)

# ============================================================
# KHỐI 2: KHỐI LƯỢNG CÔNG VIỆC (tính từ BU Workload Allocation)
# ============================================================
st.markdown('<div class="section-title">OPERATIONS WORKLOAD</div>', unsafe_allow_html=True)
k1, k2 = st.columns(2, gap="small")
with k1:
    kpi_card("Shipment Volume", f"{total_shipments:,.0f}", "")
with k2:
    kpi_card("Total Workload", fmt_hours(selected_base_workload), "")

if month == "All":
    if workload_months_with_data:
        st.caption(
            f"Calculation period: {len(workload_months_with_data)} month(s) with actual workload data only "
            f"({', '.join(workload_months_with_data)}). Months without workload are excluded from "
            "Required FTE, HC averages and capacity calculations."
        )
    else:
        st.caption("No month with actual workload data is available for the selected filters.")

# ============================================================
# HEADCOUNT GAP BY OFFICE (Required FTE theo Workload vs Actual PIC)
# ============================================================
st.markdown("<br>", unsafe_allow_html=True)
st.markdown('<div class="section-title">HEADCOUNT GAP BY OFFICE</div>', unsafe_allow_html=True)

gap_bu_scope = base_bu_month.copy()
if office != "All Offices":
    gap_bu_scope = gap_bu_scope[gap_bu_scope["Office"].eq(office)]

gap_hc_scope = hc_valid.copy()

gap_offices = sorted(
    set(gap_bu_scope["Office"].dropna().astype(str)) | set(gap_hc_scope["Office"].dropna().astype(str))
)

office_gap_rows = []
for off in gap_offices:
    off_bu = gap_bu_scope[gap_bu_scope["Office"].eq(off)]

    if month == "All":
        off_months = [
            m for m in MONTH_ORDER
            if m in set(off_bu.loc[off_bu["Total Workload"].fillna(0) != 0, "Month"].astype(str))
        ]
    else:
        off_months = [month] if (not off_bu.empty and off_bu["Total Workload"].fillna(0).sum() != 0) else []

    off_workload = float(off_bu["Total Workload"].sum())
    if off_months:
        off_required_fte = off_workload / (FTE_MINUTES * len(off_months))
    else:
        off_required_fte = np.nan

    off_hc = gap_hc_scope[gap_hc_scope["Office"].eq(off)]
    if off_hc.empty:
        off_actual_pic = np.nan
    elif month == "All":
        off_hc_period = off_hc[off_hc["Month"].astype(str).isin(off_months)]
        off_actual_pic = (
            float(off_hc_period.groupby("Month")["Actual HC PIC"].sum().mean())
            if not off_hc_period.empty else np.nan
        )
    else:
        off_actual_pic = float(off_hc["Actual HC PIC"].sum())

    office_gap_rows.append({"Office": off, "Required FTE": off_required_fte, "Actual PIC": off_actual_pic})

office_gap = pd.DataFrame(office_gap_rows)

if office_gap.empty:
    st.info("Không có dữ liệu để tính Headcount Gap cho bộ lọc hiện tại.")
else:
    office_gap["Gap"] = office_gap["Actual PIC"] - office_gap["Required FTE"]
    office_gap_plot = office_gap.dropna(subset=["Gap"]).copy()

    if office_gap_plot.empty:
        st.info("Chưa đủ dữ liệu Required FTE / Actual PIC để tính Gap cho bộ lọc hiện tại.")
    else:
        office_gap_plot["Status"] = np.where(office_gap_plot["Gap"] >= 0, "Dư PIC", "Thiếu PIC")
        office_gap_plot = office_gap_plot.sort_values("Gap")

        gap_chart_col, gap_table_col = st.columns([1.6, 1], gap="medium")

        with gap_chart_col:
            fig = px.bar(
                office_gap_plot, x="Gap", y="Office", orientation="h", text="Gap",
                color="Status",
                color_discrete_map={"Thiếu PIC": "#B42318", "Dư PIC": "#2F8F6B"},
                category_orders={"Office": office_gap_plot["Office"].tolist()},
            )
            fig.update_traces(texttemplate="%{text:+.2f}", textposition="outside", cliponaxis=False)
            standard_chart_layout(fig, table_height(len(office_gap_plot), cap=340, min_h=220))
            fig.update_layout(showlegend=True, legend=dict(orientation="h", y=-0.15, x=0, title=""))
            fig.add_vline(x=0, line_width=1, line_color="#8A94A6")
            st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})

        with gap_table_col:
            st.dataframe(
                office_gap.rename(columns={"Required FTE": "Required FTE", "Actual PIC": "Actual PIC"}),
                hide_index=True,
                use_container_width=True,
                height=table_height(len(office_gap), cap=340),
                column_config={
                    "Required FTE": st.column_config.NumberColumn("Required FTE", format="%.2f"),
                    "Actual PIC": st.column_config.NumberColumn("Actual PIC", format="%.2f"),
                    "Gap": st.column_config.NumberColumn("Gap", format="%+.2f"),
                },
            )

        st.caption(
            "Gap = Actual PIC − Required FTE (theo khối lượng công việc thực tế). "
            "Gap âm (đỏ) = thiếu PIC, Gap dương (xanh) = dư PIC."
        )

# ============================================================
# SHIPMENT VOLUME & SHARE BY SERVICE (chart + bảng chi tiết)
# ============================================================
st.markdown("<br>", unsafe_allow_html=True)
st.markdown('<div class="section-title">SHIPMENT VOLUME & SHARE BY SERVICE</div>', unsafe_allow_html=True)

volume_plot = service.copy()
shipment_total = float(volume_plot["Shipment_Volume"].sum())
volume_plot["Share"] = np.where(shipment_total > 0, volume_plot["Shipment_Volume"] / shipment_total, 0)

chart_col, detail_col = st.columns([1.6, 1], gap="medium")

with chart_col:
    fig = px.bar(
        volume_plot, x="Segment", y="Shipment_Volume", text="Shipment_Volume",
        category_orders={"Segment": SERVICE_ORDER},
    )
    fig.update_traces(
        marker_color="#0B6FA8",
        texttemplate="%{text:,.0f}",
        textposition="outside", cliponaxis=False, width=0.62,
    )
    max_volume = volume_plot["Shipment_Volume"].max()
    if pd.notna(max_volume) and max_volume > 0:
        fig.update_yaxes(range=[0, max_volume * 1.15])
    standard_chart_layout(fig, 340)
    fig.update_layout(showlegend=False)
    fig.update_yaxes(rangemode="tozero")
    st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})

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
        height=table_height(len(shipment_detail), cap=340),
        column_config={
            "Service": st.column_config.TextColumn("Service"),
            "Volume": st.column_config.NumberColumn("Volume", format="localized"),
            "Share (%)": st.column_config.NumberColumn("Share (%)", format="%.1f%%"),
        },
    )

# ============================================================
# SERVICE SHARE OF TOTAL TIME (chart + bảng chi tiết)
# ============================================================
st.markdown("<br>", unsafe_allow_html=True)
st.markdown('<div class="section-title">SERVICE SHARE OF TOTAL TIME</div>', unsafe_allow_html=True)

pie = service[service["Base_Workload"] > 0].copy()
if pie.empty:
    st.info("No workload data available for selected filters.")
else:
    pie_chart_col, pie_table_col = st.columns([1.6, 1], gap="medium")

    with pie_chart_col:
        fig = px.pie(
            pie, names="Segment", values="Base_Workload", hole=0.58,
            category_orders={"Segment": SERVICE_ORDER},
            color="Segment", color_discrete_map=SEGMENT_COLORS,
        )
        fig.update_traces(textposition="inside", textinfo="percent")
        fig.update_layout(
            height=340, margin=dict(l=10, r=10, t=20, b=20), paper_bgcolor="white",
            font=dict(color="#172033", size=13),
            showlegend=True, legend=dict(orientation="v", x=1.02, y=0.5, title=""),
        )
        st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})

    with pie_table_col:
        pie_detail = service[["Segment", "Base_Workload"]].copy()
        pie_total_wl = float(pie_detail["Base_Workload"].sum())
        pie_detail["Hours"] = pie_detail["Base_Workload"] / 60
        pie_detail["Share (%)"] = np.where(pie_total_wl > 0, pie_detail["Base_Workload"] / pie_total_wl * 100, 0)
        pie_detail = pie_detail[["Segment", "Hours", "Share (%)"]].rename(columns={"Segment": "Service"})

        st.dataframe(
            pie_detail,
            hide_index=True,
            use_container_width=True,
            height=table_height(len(pie_detail), cap=340),
            column_config={
                "Hours": st.column_config.NumberColumn("Total Workload (h)", format="%.1f"),
                "Share (%)": st.column_config.NumberColumn("Share (%)", format="%.1f%%"),
            },
        )

# ============================================================
# WORKLOAD TREND BY MONTH (chart + bảng chi tiết, chỉ hiện khi Month = All)
# ============================================================
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

if show_trend:
    st.markdown("<br>", unsafe_allow_html=True)
    st.markdown('<div class="section-title">WORKLOAD TREND BY MONTH</div>', unsafe_allow_html=True)

    trend_chart_col, trend_table_col = st.columns([1.6, 1], gap="medium")

    with trend_chart_col:
        fig = px.line(trend, x="Month", y="Hours", markers=True)
        fig.update_traces(line_color="#00B9F2", marker=dict(size=7, color="#00B9F2"))
        standard_chart_layout(fig, 300)
        fig.update_yaxes(rangemode="tozero")
        st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})

    with trend_table_col:
        trend_detail = trend[["Month", "Hours"]].copy()
        st.dataframe(
            trend_detail,
            hide_index=True,
            use_container_width=True,
            height=table_height(len(trend_detail), cap=300),
            column_config={"Hours": st.column_config.NumberColumn("Total Workload (h)", format="%.1f")},
        )

# ============================================================
# TOTAL WORKLOAD BY SERVICE (HOURS) — chart + SERVICE WORKLOAD DETAIL đầy đủ
# ============================================================
st.markdown("<br>", unsafe_allow_html=True)
st.markdown('<div class="section-title">TOTAL WORKLOAD BY SERVICE (HOURS)</div>', unsafe_allow_html=True)

service_hours = service.copy()
service_hours["Hours"] = service_hours["Base_Workload"] / 60

swh_chart_col, swh_table_col = st.columns([1.6, 1], gap="medium")

with swh_chart_col:
    fig = px.bar(
        service_hours, x="Segment", y="Hours", text="Hours",
        category_orders={"Segment": SERVICE_ORDER},
    )
    fig.update_traces(
        marker_color="#0B6FA8",
        texttemplate="%{text:,.0f} h",
        textposition="outside", cliponaxis=False, width=0.62,
    )
    max_hours_service = service_hours["Hours"].max()
    if pd.notna(max_hours_service) and max_hours_service > 0:
        fig.update_yaxes(range=[0, max_hours_service * 1.15])
    standard_chart_layout(fig, 340)
    fig.update_layout(showlegend=False)
    fig.update_yaxes(rangemode="tozero")
    st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})

with swh_table_col:
    # SERVICE WORKLOAD DETAIL đầy đủ — dùng khi cần phân tích sâu theo từng BU
    service_table = service[["Segment", "Service", "Shipment_Volume", "Base_Workload", "Service Share", "Required FTE"]].copy()
    service_table["Total Workload (h)"] = service_table["Base_Workload"] / 60
    service_table = service_table[["Segment", "Service", "Shipment_Volume", "Total Workload (h)", "Service Share", "Required FTE"]]

    st.dataframe(
        service_table,
        hide_index=True,
        use_container_width=True,
        height=table_height(len(service_table), cap=340),
        column_config={
            "Shipment_Volume": st.column_config.NumberColumn("Shipment Volume", format="localized"),
            "Total Workload (h)": st.column_config.NumberColumn("Total Workload (h)", format="%.1f"),
            "Service Share": st.column_config.NumberColumn("% of Total Time", format="%.1f%%"),
            "Required FTE": st.column_config.NumberColumn("Required FTE", format="%.2f"),
        },
    )

# ============================================================
# OFFICE / PIC WORKLOAD (chart + bảng chi tiết)
# ============================================================
st.markdown("<br>", unsafe_allow_html=True)

if cs_pic != "All CS PIC":
    workload_title = "SELECTED CS PIC WORKLOAD"
elif office != "All Offices":
    workload_title = f"WORKLOAD - {office}"
else:
    workload_title = "WORKLOAD BY OFFICE"
st.markdown(f'<div class="section-title">{workload_title}</div>', unsafe_allow_html=True)

wl_chart_col, wl_table_col = st.columns([1.6, 1], gap="medium")

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
        with wl_chart_col:
            st.info("No workload data available for selected filters.")
    else:
        office_workload = office_workload.sort_values("Hours", ascending=True)

        with wl_chart_col:
            fig = px.bar(office_workload, x="Hours", y="Office", orientation="h", text="Hours")
            fig.update_traces(
                marker_color="#00B9F2", texttemplate="%{text:,.1f} h",
                textposition="outside", cliponaxis=False, width=0.42,
            )
            max_hours = office_workload["Hours"].max()
            if pd.notna(max_hours) and max_hours > 0:
                fig.update_xaxes(range=[0, max_hours * 1.18])
            chart_h = max(260, min(460, 38 + len(office_workload) * 34))
            standard_chart_layout(fig, chart_h)
            st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})

        with wl_table_col:
            office_detail = office_workload.sort_values("Hours", ascending=False)[["Office", "Hours"]]
            st.dataframe(
                office_detail,
                hide_index=True,
                use_container_width=True,
                height=table_height(len(office_detail), cap=chart_h),
                column_config={"Hours": st.column_config.NumberColumn("Total Workload (h)", format="%.1f")},
            )
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
        with wl_chart_col:
            st.info("No workload data available for selected filters.")
    else:
        pic_display["Hours"] = pic_display["PIC Workload"] / 60
        pic_display = pic_display.sort_values("Hours", ascending=True)

        with wl_chart_col:
            fig = px.bar(pic_display, x="Hours", y="CS PIC", orientation="h", text="Hours")
            fig.update_traces(
                marker_color="#45BD8C", texttemplate="%{text:.1f} h",
                textposition="outside", cliponaxis=False,
            )
            chart_h = max(260, min(460, 38 + len(pic_display) * 34))
            standard_chart_layout(fig, chart_h)
            st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})

        with wl_table_col:
            pic_detail = pic_display.sort_values("Hours", ascending=False)[["Office", "CS PIC", "Hours"]]
            st.dataframe(
                pic_detail,
                hide_index=True,
                use_container_width=True,
                height=table_height(len(pic_detail), cap=chart_h),
                column_config={"Hours": st.column_config.NumberColumn("Total Workload (h)", format="%.1f")},
            )

# ============================================================
# CS PIC FTE & WORKLOAD
# ============================================================
st.markdown("<br>", unsafe_allow_html=True)
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
    pic_table_display = pic_table[["Office", "CS PIC", "FTE", "Workload Hours", "Capacity Status"]].sort_values(
        ["Office", "FTE"], ascending=[True, False]
    )

    pic_chart_col, pic_table_col = st.columns([1.6, 1], gap="medium")

    with pic_chart_col:
        pic_chart_data = pic_table_display.copy()
        pic_chart_data["PIC Label"] = pic_chart_data["Office"] + " · " + pic_chart_data["CS PIC"]
        pic_chart_data = pic_chart_data.sort_values("Workload Hours", ascending=True)

        fig = px.bar(
            pic_chart_data, x="Workload Hours", y="PIC Label", orientation="h", text="Workload Hours",
            color="Capacity Status",
            color_discrete_map={"Overload": "#DC2626", "Near Full": "#FF6D10", "Available": "#45BD8C"},
            category_orders={
                "Capacity Status": ["Overload", "Near Full", "Available"],
                "PIC Label": pic_chart_data["PIC Label"].tolist(),  # ép đúng thứ tự trục Y theo Workload Hours
            },
        )
        fig.update_traces(texttemplate="%{text:,.1f} h", textposition="outside", cliponaxis=False)
        pic_chart_h = max(260, min(500, 60 + len(pic_chart_data) * 26)) + 40  # chừa chỗ cho legend bên dưới
        standard_chart_layout(fig, pic_chart_h)
        fig.update_layout(
            showlegend=True,
            legend=dict(orientation="h", y=-0.12, x=0, title=""),
            yaxis_title="",
            margin=dict(l=15, r=15, t=35, b=60),
        )
        st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})

    with pic_table_col:
        st.dataframe(
            pic_table_display,
            hide_index=True,
            use_container_width=True,
            height=table_height(len(pic_table_display), cap=pic_chart_h),
            column_config={
                "FTE": st.column_config.NumberColumn("FTE", format="%.2f"),
                "Workload Hours": st.column_config.NumberColumn("Workload Hours", format="%.1f h"),
            },
        )

# ============================================================
# TOP 15 CUSTOMERS BY SHIPMENT VOLUME (chart) + đầy đủ Customer Volume (bảng, cuộn)
# ============================================================
st.markdown("<br>", unsafe_allow_html=True)
st.markdown('<div class="section-title">TOP 15 CUSTOMERS BY SHIPMENT VOLUME</div>', unsafe_allow_html=True)

cust_all = filtered_customer.copy()
if cust_all.empty:
    st.info("No customer volume data available for selected filters.")
else:
    cust_all = (
        cust_all.groupby(["Office", "Customer"], as_index=False)["Customer Shipment Volume"].sum()
        .sort_values("Customer Shipment Volume", ascending=False)
    )
    cust_top15 = cust_all.head(15)

    if len(cust_all) > 15:
        st.caption(f"Chart hiển thị Top 15 / {len(cust_all)} khách hàng theo Volume — bảng bên phải có đầy đủ {len(cust_all)} khách hàng (cuộn để xem hết).")

    cust_chart_col, cust_table_col = st.columns([1.6, 1], gap="medium")

    with cust_chart_col:
        fig = px.bar(
            cust_top15.sort_values("Customer Shipment Volume"),
            x="Customer Shipment Volume", y="Customer", orientation="h", text="Customer Shipment Volume",
        )
        fig.update_traces(marker_color="#00B9F2", texttemplate="%{text:.0f}", textposition="outside", cliponaxis=False)
        standard_chart_layout(fig, table_height(len(cust_top15), cap=340, min_h=260))
        st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})

    with cust_table_col:
        st.dataframe(
            cust_all.rename(columns={"Customer Shipment Volume": "Volume"}),
            hide_index=True,
            use_container_width=True,
            height=table_height(len(cust_all), cap=340),
            column_config={"Volume": st.column_config.NumberColumn("Volume", format="localized")},
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
