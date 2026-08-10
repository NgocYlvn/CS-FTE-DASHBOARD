# -*- coding: utf-8 -*-
"""
CS WORKLOAD & CAPACITY DASHBOARD
=================================
Dashboard tra loi 7 cau hoi quan tri chinh cho CS Management.
Nguon du lieu: CS_WORKLOAD_CAPACITY.xlsx

Cach chay:
    streamlit run cs_workload_dashboard.py

Tac gia: Xay dung theo yeu cau Ms. Ngoc - CS Logistics
"""

import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
from pathlib import Path

# =============================================================================
# CONFIG CHUNG
# =============================================================================
st.set_page_config(
    page_title="CS Workload & Capacity Dashboard",
    page_icon="📦",
    layout="wide",
    initial_sidebar_state="expanded",
)

DEFAULT_FILE = "CS_WORKLOAD_CAPACITY.xlsx"

MONTH_ORDER = ["Apr-26", "May-26", "Jun-26", "Jul-26", "Aug-26", "Sep-26",
               "Oct-26", "Nov-26", "Dec-26", "Jan-27", "Feb-27", "Mar-27"]

OFFICE_ORDER = ["HAD", "HAN", "HLC", "HCM"]

FTE_MINUTES = 10032  # 8h x 95% x 22 ngay/thang (theo Guidelines & Definitions)
OVERLOAD_THRESHOLD = 1.0
HIGHLOAD_THRESHOLD = 0.95
BALANCED_THRESHOLD = 0.90

STATUS_COLOR = {
    "Overload": "#E24A4A",
    "High load": "#F2A93B",
    "Balanced": "#3BB273",
    "Less load": "#4C8BF5",
    "Unknown": "#B0B0B0",
}

SEGMENT_LABELS = {
    "AE": "Air Export", "AI": "Air Import", "OE": "Ocean Export",
    "OI": "Ocean Import", "CC": "Customs Clearance", "TR": "Trucking",
    "WH": "Warehouse",
}

# =============================================================================
# HELPER FUNCTIONS
# =============================================================================

def clean_columns(df: pd.DataFrame) -> pd.DataFrame:
    """Chuan hoa ten cot: gop nhieu space, strip."""
    df = df.copy()
    df.columns = [str(c).strip() for c in df.columns]
    df.columns = [" ".join(c.split()) for c in df.columns]
    return df


def month_sort(df: pd.DataFrame, col: str = "Month") -> pd.DataFrame:
    df = df.copy()
    df[col] = pd.Categorical(df[col], categories=MONTH_ORDER, ordered=True)
    return df.sort_values(col)


def office_sort(df: pd.DataFrame, col: str = "Office") -> pd.DataFrame:
    df = df.copy()
    present = [o for o in OFFICE_ORDER if o in df[col].unique()]
    df[col] = pd.Categorical(df[col], categories=present + [o for o in df[col].unique() if o not in present], ordered=True)
    return df.sort_values(col)


def status_badge(status: str) -> str:
    color = STATUS_COLOR.get(status, STATUS_COLOR["Unknown"])
    return f'<span style="background-color:{color};color:white;padding:2px 10px;border-radius:10px;font-size:0.85em;">{status}</span>'


def kpi_card(label, value, delta=None, help_text=None):
    st.metric(label=label, value=value, delta=delta, help=help_text)


def no_data_msg(scope: str):
    st.info(f"ℹ️ Chưa có dữ liệu cho **{scope}** trong lựa chọn hiện tại. "
            f"Dashboard sẽ tự cập nhật khi Sếp bổ sung số liệu vào file nguồn.")


# =============================================================================
# LOAD DATA
# =============================================================================

@st.cache_data(show_spinner="Đang tải dữ liệu...")
def load_data(file):
    xls = pd.ExcelFile(file)

    # ---- HC Capacity ----
    hc = clean_columns(pd.read_excel(xls, "HC Capacity", header=1))
    hc.columns = ["Office", "Month", "Approved_HC_MNG", "Approved_HC_PIC", "Total_Approved_HC",
                  "Actual_HC_MNG", "Actual_HC_PIC", "Total_Actual_HC", "Required_HC_MNG",
                  "Required_HC_PIC", "Total_Required_HC", "Capacity_Utilization", "Workload_Status"]
    hc = hc.dropna(subset=["Total_Actual_HC"], how="all")
    hc["HC_Gap"] = hc["Total_Actual_HC"] - hc["Total_Required_HC"]
    hc["Workload_Status"] = hc["Workload_Status"].fillna("Unknown")

    # ---- BU Workload Allocation ----
    bu = clean_columns(pd.read_excel(xls, "BU Workload Allocation", header=1))
    bu.columns = ["Office", "Month", "Segment", "Core_Volume", "Core_Workload_min",
                  "Ancillary_Volume", "Ancillary_Workload_min", "Supporting_Volume",
                  "Supporting_Workload_min", "Exception_Volume", "Exception_Workload_min",
                  "Total_Workload_min", "BU_Workload_Share_pct"]
    # Cac thang chua nhap lieu co Total_Workload_min = 0 (khong phai NaN) -> loc bo de tranh nhieu bieu do
    bu = bu[(bu["Total_Workload_min"].fillna(0) != 0) |
            (bu[["Core_Volume", "Ancillary_Volume", "Supporting_Volume", "Exception_Volume"]].notna().any(axis=1))]
    bu["Segment_Label"] = bu["Segment"].map(SEGMENT_LABELS).fillna(bu["Segment"])

    # ---- YVF Promotion Effectiveness ----
    yvf = clean_columns(pd.read_excel(xls, "YVF Promotion Effectiveness", header=1))
    yvf.columns = ["Office", "Month", "Total_YVF_Bookings", "Total_IFF_Shipments", "YVF_Booking_Ratio"]
    yvf = yvf.dropna(subset=["Total_YVF_Bookings", "Total_IFF_Shipments"], how="all")

    # ---- Shipment volume ----
    sv = clean_columns(pd.read_excel(xls, "Shipment volume", header=1))
    sv.columns = ["Office", "Month", "Active_Customers", "AI", "AE", "OILCL", "OIFCL",
                  "OELCL", "OEFCL", "DI", "DE", "DM", "CE", "CI", "HE", "HI", "RE", "RI", "RD", "TOTAL"]
    sv = sv.dropna(subset=["TOTAL"], how="all")

    # ---- CS FTE (wide -> long) ----
    fte_wide = clean_columns(pd.read_excel(xls, "CS FTE", header=1))
    fte_wide.columns = ["Office", "CS_PIC"] + MONTH_ORDER
    fte_wide = fte_wide.dropna(subset=["CS_PIC"])
    fte = fte_wide.melt(id_vars=["Office", "CS_PIC"], value_vars=MONTH_ORDER,
                         var_name="Month", value_name="FTE_Ratio")
    fte = fte.dropna(subset=["FTE_Ratio"])

    def fte_status(v):
        if v > OVERLOAD_THRESHOLD:
            return "Overload"
        elif v >= HIGHLOAD_THRESHOLD:
            return "High load"
        elif v >= BALANCED_THRESHOLD:
            return "Balanced"
        else:
            return "Less load"
    fte["Status"] = fte["FTE_Ratio"].apply(fte_status)

    # ---- Customer Volume theo tung Office ----
    cust_frames = []
    for off in ["HAD", "HAN", "HLC", "HCM"]:
        sheet_name = f"Customer Volume - {off}"
        if sheet_name in xls.sheet_names:
            cdf = clean_columns(pd.read_excel(xls, sheet_name, header=1))
            cdf.columns = ["No", "Office", "Customer"] + MONTH_ORDER + ["Total"]
            cdf = cdf.dropna(subset=["Customer"])
            cust_frames.append(cdf)
    customers = pd.concat(cust_frames, ignore_index=True) if cust_frames else pd.DataFrame(
        columns=["No", "Office", "Customer"] + MONTH_ORDER + ["Total"])

    return {
        "hc": hc, "bu": bu, "yvf": yvf, "sv": sv, "fte": fte, "customers": customers,
    }


# =============================================================================
# SIDEBAR - FILE & FILTERS
# =============================================================================
st.sidebar.title("📦 CS Workload & Capacity")
st.sidebar.caption("Dashboard quản trị Customer Service - Logistics")

uploaded = st.sidebar.file_uploader("Cập nhật file dữ liệu (.xlsx)", type=["xlsx"])
data_source = uploaded if uploaded is not None else (DEFAULT_FILE if Path(DEFAULT_FILE).exists() else None)

if data_source is None:
    st.warning("⚠️ Chưa có file dữ liệu. Vui lòng upload file `CS_WORKLOAD_CAPACITY.xlsx` ở sidebar.")
    st.stop()

data = load_data(data_source)
hc, bu, yvf, sv, fte, customers = data["hc"], data["bu"], data["yvf"], data["sv"], data["fte"], data["customers"]

st.sidebar.markdown("---")
all_offices = sorted(set(hc["Office"]).union(bu["Office"]).union(sv["Office"]).union(fte["Office"]).union(customers["Office"]))
sel_offices = st.sidebar.multiselect("Office", options=all_offices, default=all_offices)

all_months = [m for m in MONTH_ORDER if m in set(hc["Month"]).union(bu["Month"]).union(sv["Month"]).union(fte["Month"])]
sel_months = st.sidebar.multiselect("Tháng", options=all_months, default=all_months)

st.sidebar.markdown("---")
st.sidebar.caption(
    "⚠️ **Ghi chú độ phủ dữ liệu:**\n"
    "- HC Capacity / BU Workload: chỉ có HAD (Apr–May)\n"
    "- Shipment volume: HAD, HAN, HLC (Apr–May)\n"
    "- CS FTE theo PIC: chỉ HAD (Apr–Jul)\n"
    "- Customer Volume: chỉ HAD có dữ liệu chi tiết\n"
    "- YVF Promotion: dữ liệu chưa nhất quán, xem Tab ⑦"
)


def f_office(df):
    return df[df["Office"].isin(sel_offices)] if len(sel_offices) else df.iloc[0:0]


def f_month(df):
    return df[df["Month"].isin(sel_months)] if len(sel_months) else df.iloc[0:0]


def apply_filters(df):
    return f_month(f_office(df))


# =============================================================================
# HEADER + KPI TỔNG QUAN
# =============================================================================
st.title("📦 CS Workload & Capacity Dashboard")
st.caption("Theo dõi khối lượng công việc, năng lực nhân sự và hiệu quả vận hành CS")

hc_f = apply_filters(hc)
sv_f = apply_filters(sv)
fte_f = apply_filters(fte)

k1, k2, k3, k4, k5 = st.columns(5)
with k1:
    total_actual_hc = hc_f["Total_Actual_HC"].sum()
    total_required_hc = hc_f["Total_Required_HC"].sum()
    kpi_card("Total Actual HC", f"{total_actual_hc:.0f}" if len(hc_f) else "N/A")
with k2:
    gap = total_actual_hc - total_required_hc if len(hc_f) else None
    kpi_card("HC Gap", f"{gap:+.1f}" if gap is not None else "N/A",
              help_text="Actual HC − Required HC. Âm = thiếu người, Dương = dư người")
with k3:
    total_volume = sv_f["TOTAL"].sum() if len(sv_f) else 0
    kpi_card("Tổng Volume", f"{total_volume:,.0f}" if len(sv_f) else "N/A")
with k4:
    total_active_cust = sv_f["Active_Customers"].sum() if len(sv_f) else 0
    kpi_card("Active Customers", f"{total_active_cust:,.0f}" if len(sv_f) else "N/A")
with k5:
    n_overload = fte_f[fte_f["Status"] == "Overload"]["CS_PIC"].nunique() if len(fte_f) else 0
    kpi_card("CS PIC Overload", f"{n_overload}", help_text="Số CS PIC có FTE ratio > 1.0 trong kỳ đã chọn")

st.markdown("---")

# =============================================================================
# TABS - 7 CÂU HỎI QUẢN TRỊ
# =============================================================================
tab1, tab2, tab3, tab4, tab5, tab6, tab7 = st.tabs([
    "① Đủ HC?", "② Office quá tải?", "③ Volume từ đâu?", "④ Workload ở đâu?",
    "⑤ Ai quá tải?", "⑥ Khách hàng", "⑦ YVF Promotion"
])

# -----------------------------------------------------------------------
# TAB 1: Chúng ta có đủ HC không? -> Actual HC vs Required FTE + Gap
# -----------------------------------------------------------------------
with tab1:
    st.subheader("① Actual HC vs Required FTE — HC Gap")
    if hc_f.empty:
        no_data_msg("HC Capacity theo lựa chọn hiện tại")
    else:
        hc_view = month_sort(office_sort(hc_f.copy()))
        hc_view["Label"] = hc_view["Office"].astype(str) + " - " + hc_view["Month"].astype(str)

        c1, c2 = st.columns([2, 1])
        with c1:
            plot_df = hc_view.melt(
                id_vars=["Label"],
                value_vars=["Total_Actual_HC", "Total_Required_HC", "Total_Approved_HC"],
                var_name="Loại HC", value_name="Số lượng"
            )
            plot_df["Loại HC"] = plot_df["Loại HC"].map({
                "Total_Actual_HC": "Actual HC", "Total_Required_HC": "Required HC",
                "Total_Approved_HC": "Approved HC"
            })
            fig = px.bar(plot_df, x="Label", y="Số lượng", color="Loại HC", barmode="group",
                         color_discrete_map={"Actual HC": "#4C8BF5", "Required HC": "#E24A4A",
                                              "Approved HC": "#B0B0B0"},
                         title="Actual HC vs Required HC vs Approved HC theo Office & Tháng")
            fig.update_layout(legend_title_text="", xaxis_title="", yaxis_title="Headcount")
            st.plotly_chart(fig, use_container_width=True)
        with c2:
            fig_gap = px.bar(hc_view, x="Label", y="HC_Gap",
                              color=hc_view["HC_Gap"] > 0,
                              color_discrete_map={True: "#3BB273", False: "#E24A4A"},
                              title="HC Gap (Actual − Required)")
            fig_gap.update_layout(showlegend=False, xaxis_title="", yaxis_title="Gap (người)")
            fig_gap.add_hline(y=0, line_dash="dash", line_color="gray")
            st.plotly_chart(fig_gap, use_container_width=True)

        st.markdown("**Chi tiết theo Office - Tháng**")
        show_cols = ["Office", "Month", "Total_Approved_HC", "Total_Actual_HC",
                     "Total_Required_HC", "HC_Gap", "Capacity_Utilization"]
        tbl = hc_view[show_cols].copy()
        tbl["Capacity_Utilization"] = (tbl["Capacity_Utilization"] * 100).round(1).astype(str) + "%"
        tbl["HC_Gap"] = tbl["HC_Gap"].round(2)
        st.dataframe(tbl, use_container_width=True, hide_index=True)

        missing_off = [o for o in sel_offices if o not in hc["Office"].unique()]
        if missing_off:
            st.caption(f"⚠️ Chưa có dữ liệu HC Capacity cho: {', '.join(missing_off)}")

# -----------------------------------------------------------------------
# TAB 2: Office nào đang quá tải? -> Workload/Available Time + Capacity Status
# -----------------------------------------------------------------------
with tab2:
    st.subheader("② Capacity Utilization & Workload Status theo Office")
    if hc_f.empty:
        no_data_msg("HC Capacity theo lựa chọn hiện tại")
    else:
        hc_view = month_sort(office_sort(hc_f.copy()))
        hc_view["Label"] = hc_view["Office"].astype(str) + " - " + hc_view["Month"].astype(str)
        hc_view["Utilization_pct"] = hc_view["Capacity_Utilization"] * 100

        fig = px.bar(hc_view, x="Label", y="Utilization_pct", color="Workload_Status",
                     color_discrete_map=STATUS_COLOR,
                     title="Capacity Utilization (%) theo Office & Tháng",
                     labels={"Utilization_pct": "Capacity Utilization (%)"})
        fig.add_hline(y=100, line_dash="dash", line_color="#E24A4A", annotation_text="Overload (>100%)")
        fig.add_hline(y=95, line_dash="dot", line_color="#F2A93B", annotation_text="High load (95%)")
        fig.add_hline(y=90, line_dash="dot", line_color="#3BB273", annotation_text="Balanced (90%)")
        fig.update_layout(xaxis_title="", legend_title_text="Status")
        st.plotly_chart(fig, use_container_width=True)

        st.markdown("**Bảng trạng thái năng lực**")
        for _, row in hc_view.iterrows():
            c1, c2, c3, c4 = st.columns([2, 2, 2, 2])
            c1.write(f"**{row['Office']} - {row['Month']}**")
            c2.write(f"Utilization: **{row['Utilization_pct']:.1f}%**")
            c3.markdown(status_badge(row["Workload_Status"]), unsafe_allow_html=True)
            c4.write(f"Gap: {row['HC_Gap']:+.1f} người")

        st.caption("Công thức: Capacity Utilization = Actual Workload / Available Time "
                   "(Available Time = Actual HC × 10,032 phút/FTE/tháng). "
                   "Ngưỡng theo Guidelines & Definitions: Overload >100%, High load 95–100%, "
                   "Balanced 90–<95%, Less load <90%.")

# -----------------------------------------------------------------------
# TAB 3: Volume đang đến từ đâu? -> Shipment Volume theo Month x Office x Segment
# -----------------------------------------------------------------------
with tab3:
    st.subheader("③ Shipment Volume theo Office, Tháng & Segment")
    if sv_f.empty:
        no_data_msg("Shipment volume theo lựa chọn hiện tại")
    else:
        sv_view = month_sort(office_sort(sv_f.copy()))

        c1, c2 = st.columns([1.4, 1])
        with c1:
            fig = px.bar(sv_view, x="Month", y="TOTAL", color="Office", barmode="group",
                         category_orders={"Month": MONTH_ORDER, "Office": OFFICE_ORDER},
                         title="Tổng Volume theo Office qua các Tháng")
            fig.update_layout(xaxis_title="", yaxis_title="Volume (shipment)")
            st.plotly_chart(fig, use_container_width=True)
        with c2:
            trend = sv_view.groupby("Office", observed=True)["Active_Customers"].mean().reset_index()
            fig2 = px.bar(trend, x="Office", y="Active_Customers", color="Office",
                          category_orders={"Office": OFFICE_ORDER},
                          title="Active Customers trung bình theo Office")
            fig2.update_layout(showlegend=False, xaxis_title="", yaxis_title="Active Customers")
            st.plotly_chart(fig2, use_container_width=True)

        st.markdown("**Cơ cấu Volume theo Segment (donut theo từng Office)**")
        segment_cols = ["AI", "AE", "OILCL", "OIFCL", "OELCL", "OEFCL", "DI", "DE", "DM",
                         "CE", "CI", "HE", "HI", "RE", "RI", "RD"]
        available_off_in_sv = [o for o in OFFICE_ORDER if o in sv_view["Office"].unique()]
        if available_off_in_sv:
            donut_cols = st.columns(len(available_off_in_sv))
            for i, off in enumerate(available_off_in_sv):
                off_data = sv_view[sv_view["Office"] == off][segment_cols].sum()
                off_data = off_data[off_data > 0]
                with donut_cols[i]:
                    fig_d = px.pie(names=off_data.index, values=off_data.values, hole=0.55,
                                    title=f"{off}")
                    fig_d.update_layout(showlegend=False, margin=dict(t=40, b=0, l=0, r=0))
                    fig_d.update_traces(textposition="inside", textinfo="percent+label")
                    st.plotly_chart(fig_d, use_container_width=True)

        missing_off = [o for o in sel_offices if o not in sv["Office"].unique()]
        if missing_off:
            st.caption(f"⚠️ Chưa có dữ liệu Shipment volume cho: {', '.join(missing_off)}")

# -----------------------------------------------------------------------
# TAB 4: Workload nằm ở đâu? -> Segment + C/A/S/E breakdown
# -----------------------------------------------------------------------
with tab4:
    st.subheader("④ Workload theo Segment & theo loại Core/Ancillary/Supporting/Exception")
    bu_f = apply_filters(bu)
    if bu_f.empty:
        no_data_msg("BU Workload Allocation theo lựa chọn hiện tại")
    else:
        bu_view = month_sort(office_sort(bu_f.copy()))

        c1, c2 = st.columns(2)
        with c1:
            seg_total = bu_view.groupby("Segment_Label", observed=True)["Total_Workload_min"].sum().reset_index()
            seg_total = seg_total.sort_values("Total_Workload_min", ascending=True)
            fig = px.bar(seg_total, x="Total_Workload_min", y="Segment_Label", orientation="h",
                         title="Tổng Workload (phút) theo Segment",
                         labels={"Total_Workload_min": "Workload (phút)", "Segment_Label": ""})
            st.plotly_chart(fig, use_container_width=True)
        with c2:
            fig_donut = px.pie(seg_total, names="Segment_Label", values="Total_Workload_min", hole=0.55,
                               title="Tỷ trọng Workload theo Segment")
            fig_donut.update_traces(textposition="inside", textinfo="percent+label")
            st.plotly_chart(fig_donut, use_container_width=True)

        st.markdown("**Breakdown Core / Ancillary / Supporting / Exception theo Segment**")
        case_cols = ["Core_Workload_min", "Ancillary_Workload_min", "Supporting_Workload_min", "Exception_Workload_min"]
        case_labels = {"Core_Workload_min": "Core", "Ancillary_Workload_min": "Ancillary",
                       "Supporting_Workload_min": "Supporting", "Exception_Workload_min": "Exception"}
        case_df = bu_view.groupby("Segment_Label", observed=True)[case_cols].sum().reset_index()
        case_long = case_df.melt(id_vars="Segment_Label", value_vars=case_cols,
                                  var_name="Loại", value_name="Workload (phút)")
        case_long["Loại"] = case_long["Loại"].map(case_labels)
        fig3 = px.bar(case_long, x="Segment_Label", y="Workload (phút)", color="Loại", barmode="stack",
                     title="Workload theo Segment, breakdown Core/Ancillary/Supporting/Exception")
        fig3.update_layout(xaxis_title="")
        st.plotly_chart(fig3, use_container_width=True)

        if (bu_view["Supporting_Workload_min"] < 0).any():
            st.warning("⚠️ **Data quality issue**: Phát hiện giá trị **âm** trong `Supporting Workload (min)` "
                       "ở segment CC (Customs Clearance). Đây là lỗi công thức/nhập liệu từ nguồn, "
                       "cần Sếp kiểm tra lại trước khi dùng số này để ra quyết định phân bổ nhân sự.")

        missing_off = [o for o in sel_offices if o not in bu["Office"].unique()]
        if missing_off:
            st.caption(f"⚠️ Chưa có dữ liệu BU Workload Allocation cho: {', '.join(missing_off)}")

# -----------------------------------------------------------------------
# TAB 5: Ai đang quá tải? -> CS PIC FTE & Workload + Overload Person
# -----------------------------------------------------------------------
with tab5:
    st.subheader("⑤ Workload theo CS PIC (FTE Ratio) & Overload Person")
    if fte_f.empty:
        no_data_msg("CS FTE theo lựa chọn hiện tại")
    else:
        fte_view = month_sort(fte_f.copy())
        pic_order = fte_view.groupby("CS_PIC")["FTE_Ratio"].mean().sort_values(ascending=False).index.tolist()

        fig = px.bar(fte_view, x="CS_PIC", y="FTE_Ratio", color="Status", barmode="group",
                     facet_col="Month", facet_col_wrap=2,
                     category_orders={"CS_PIC": pic_order, "Month": MONTH_ORDER},
                     color_discrete_map=STATUS_COLOR,
                     title="FTE Ratio theo CS PIC qua các Tháng (>1.0 = Overload)")
        fig.add_hline(y=1.0, line_dash="dash", line_color="#E24A4A")
        fig.update_layout(height=600, xaxis_title="")
        st.plotly_chart(fig, use_container_width=True)

        st.markdown("**🔴 Danh sách CS PIC đang Overload trong kỳ đã chọn**")
        overload_tbl = fte_view[fte_view["Status"] == "Overload"].sort_values("FTE_Ratio", ascending=False)
        if overload_tbl.empty:
            st.success("✅ Không có CS PIC nào vượt ngưỡng Overload (FTE ratio > 1.0) trong kỳ đã chọn.")
        else:
            overload_count = overload_tbl.groupby("CS_PIC").agg(
                So_thang_overload=("Month", "nunique"),
                FTE_TB=("FTE_Ratio", "mean"),
                FTE_Max=("FTE_Ratio", "max"),
            ).reset_index().sort_values("So_thang_overload", ascending=False)
            overload_count["FTE_TB"] = overload_count["FTE_TB"].round(2)
            overload_count["FTE_Max"] = overload_count["FTE_Max"].round(2)
            st.dataframe(overload_count, use_container_width=True, hide_index=True)

        st.caption("Ngưỡng theo Guidelines & Definitions: Overload > 1.0, High load 0.95–1.0, "
                   "Balanced 0.90–0.95, Less load < 0.90. Dữ liệu CS PIC hiện chỉ có tại office HAD.")

# -----------------------------------------------------------------------
# TAB 6: Khách hàng nào đang tạo workload/volume lớn?
# -----------------------------------------------------------------------
with tab6:
    st.subheader("⑥ Active Customers & Top 20 Khách hàng")
    c1, c2 = st.columns([1, 1.4])
    with c1:
        if sv_f.empty:
            no_data_msg("Active Customers theo lựa chọn hiện tại")
        else:
            sv_view = month_sort(office_sort(sv_f.copy()))
            fig = px.line(sv_view, x="Month", y="Active_Customers", color="Office", markers=True,
                         category_orders={"Month": MONTH_ORDER, "Office": OFFICE_ORDER},
                         title="Xu hướng Active Customers theo Office")
            fig.update_layout(xaxis_title="", yaxis_title="Active Customers")
            st.plotly_chart(fig, use_container_width=True)

    with c2:
        cust_offices = sorted(customers["Office"].unique()) if not customers.empty else []
        if not cust_offices:
            no_data_msg("Customer Volume chi tiết")
        else:
            default_off = "HAD" if "HAD" in cust_offices else cust_offices[0]
            sel_cust_office = st.selectbox("Chọn Office để xem Top 20 khách hàng", options=cust_offices,
                                            index=cust_offices.index(default_off))
            cust_off_df = customers[customers["Office"] == sel_cust_office]
            top20 = cust_off_df.nlargest(20, "Total")[["Customer", "Total"]].sort_values("Total", ascending=True)
            if top20.empty:
                no_data_msg(f"Customer Volume của {sel_cust_office}")
            else:
                fig2 = px.bar(top20, x="Total", y="Customer", orientation="h",
                             title=f"Top 20 Khách hàng theo Volume — {sel_cust_office}",
                             labels={"Total": "Tổng Volume", "Customer": ""})
                fig2.update_layout(height=550)
                st.plotly_chart(fig2, use_container_width=True)

    other_offices = [o for o in OFFICE_ORDER if o not in customers["Office"].unique()]
    if other_offices:
        st.caption(f"⚠️ Chưa có dữ liệu Customer Volume chi tiết (theo tên KH) cho: {', '.join(other_offices)}. "
                   f"Riêng số Active Customers tổng vẫn có tại sheet Shipment volume nếu đã nhập liệu.")

# -----------------------------------------------------------------------
# TAB 7: YVF Promotion Effectiveness
# -----------------------------------------------------------------------
with tab7:
    st.subheader("⑦ YVF Promotion Effectiveness")
    yvf_f = apply_filters(yvf.rename(columns={"Office": "Office"}))
    if yvf_f.empty:
        no_data_msg("YVF Promotion Effectiveness theo lựa chọn hiện tại")
    else:
        yvf_view = month_sort(office_sort(yvf_f.copy()))

        st.error(
            "🚫 **Data quality issue nghiêm trọng**: Trong toàn bộ dữ liệu hiện có, "
            "`Total YVF Bookings` và `Total IFF Shipments` **chưa từng có giá trị khác 0 trong cùng một "
            "tháng của cùng một Office** → `YVF Booking Ratio` luôn tính ra 0. "
            "Điều này có nghĩa: **câu hỏi 'YVF Promotion có hiệu quả không?' hiện chưa thể trả lời đáng tin cậy** "
            "bằng dữ liệu nguồn. Khuyến nghị: kiểm tra lại cách ghi nhận IFF Shipments trong các tháng có phát sinh "
            "YVF Bookings (Jul–Aug tại HAD) trước khi dùng chỉ số này để đánh giá chương trình khuyến mãi."
        )

        c1, c2 = st.columns(2)
        with c1:
            fig = px.bar(yvf_view, x="Month", y="Total_YVF_Bookings", color="Office", barmode="group",
                         category_orders={"Month": MONTH_ORDER, "Office": OFFICE_ORDER},
                         title="Total YVF Bookings theo Tháng (dữ liệu thô)")
            fig.update_layout(xaxis_title="")
            st.plotly_chart(fig, use_container_width=True)
        with c2:
            fig2 = px.bar(yvf_view, x="Month", y="Total_IFF_Shipments", color="Office", barmode="group",
                          category_orders={"Month": MONTH_ORDER, "Office": OFFICE_ORDER},
                          title="Total IFF Shipments theo Tháng (dữ liệu thô)")
            fig2.update_layout(xaxis_title="")
            st.plotly_chart(fig2, use_container_width=True)

        st.dataframe(yvf_view[["Office", "Month", "Total_YVF_Bookings", "Total_IFF_Shipments", "YVF_Booking_Ratio"]],
                     use_container_width=True, hide_index=True)

st.markdown("---")
st.caption("CS Workload & Capacity Dashboard · Nguồn: CS_WORKLOAD_CAPACITY.xlsx · "
           "Các KPI được tính trực tiếp từ dữ liệu nguồn, không suy diễn số liệu còn thiếu.")
