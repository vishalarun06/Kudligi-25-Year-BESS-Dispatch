import os
import uuid

import streamlit as st
import pandas as pd

from ppa_class import PPA
from kudligi_dashboard import KudligiDashboard

# The 9 individual 24H-RTC/LimitedH-RTC companies from the real "PPA" sheet
# (Sr. No. 1-9; the sheet's own "Exchange" row is excluded -- it isn't a
# PPA, it's the residual channel Kudligi already handles directly).
DEFAULT_PPAS = [
    {"Company": "Linde India Ltd (AP)", "Actual Contracted Energy (kWh)": 59_020_000,
     "Min Contracted Energy (kWh)": 53_118_000, "RTC Quantum (MW)": 8.0, "Tariff (Rs/kWh)": 3.67,
     "Discharge Period": "24H-RTC"},
    {"Company": "Linde India Ltd (Gujarat)", "Actual Contracted Energy (kWh)": 27_070_000,
     "Min Contracted Energy (kWh)": 24_363_000, "RTC Quantum (MW)": 5.0, "Tariff (Rs/kWh)": 3.67,
     "Discharge Period": "24H-RTC"},
    {"Company": "Linde India Ltd (Uttarakhand)", "Actual Contracted Energy (kWh)": 58_060_000,
     "Min Contracted Energy (kWh)": 52_254_000, "RTC Quantum (MW)": 8.0, "Tariff (Rs/kWh)": 3.67,
     "Discharge Period": "24H-RTC"},
    {"Company": "Linde India Ltd (Punjab)", "Actual Contracted Energy (kWh)": 59_890_000,
     "Min Contracted Energy (kWh)": 53_901_000, "RTC Quantum (MW)": 8.0, "Tariff (Rs/kWh)": 3.67,
     "Discharge Period": "24H-RTC"},
    {"Company": "Praxair India Ltd (Telangana)", "Actual Contracted Energy (kWh)": 56_637_273.76,
     "Min Contracted Energy (kWh)": 50_973_546.39, "RTC Quantum (MW)": 8.0, "Tariff (Rs/kWh)": 3.58,
     "Discharge Period": "24H-RTC"},
    {"Company": "Linde India Ltd (Orissa)", "Actual Contracted Energy (kWh)": 388_800_000,
     "Min Contracted Energy (kWh)": 349_920_000, "RTC Quantum (MW)": 68.0, "Tariff (Rs/kWh)": 3.67,
     "Discharge Period": "24H-RTC"},
    {"Company": "Chemfab Alkalies (Puducherry)", "Actual Contracted Energy (kWh)": 64_500_000,
     "Min Contracted Energy (kWh)": 58_050_000, "RTC Quantum (MW)": 10.0, "Tariff (Rs/kWh)": 3.65,
     "Discharge Period": "24H-RTC"},
    {"Company": "Green Valley (Meghalaya)", "Actual Contracted Energy (kWh)": 31_870_000,
     "Min Contracted Energy (kWh)": 28_683_000, "RTC Quantum (MW)": 5.0, "Tariff (Rs/kWh)": 4.10,
     "Discharge Period": "24H-RTC"},
    {"Company": "New Clients (Multiple)", "Actual Contracted Energy (kWh)": 550_000_000,
     "Min Contracted Energy (kWh)": 495_000_000, "RTC Quantum (MW)": 94.178082, "Tariff (Rs/kWh)": 3.70,
     "Discharge Period": "LimitedH-RTC"},
]

BLANK_PPA = {
    "Company": "New Offtaker",
    "Actual Contracted Energy (kWh)": 0.0,
    "Min Contracted Energy (kWh)": 0.0,
    "RTC Quantum (MW)": 0.0,
    "Tariff (Rs/kWh)": 0.0,
    "Discharge Period": "24H-RTC",
}

st.set_page_config(
    page_title="Watt-A-Wonder",
    page_icon="\U0001F300",
    layout="wide",
)

# -------------------------------------------------------------------------
# Theme -- dark background + card styling. Streamlit's own theme (colors,
# base font) is normally set in .streamlit/config.toml (shipped alongside
# this file), but the CSS below is what actually gives the card look to
# containers, buttons, metrics, and inputs regardless of the base theme.
# -------------------------------------------------------------------------
st.markdown(
    """
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap');

    html, body, [class*="css"] { font-family: 'Inter', sans-serif; }

    .stApp {
        background: linear-gradient(180deg, #0B1220 0%, #0F172A 45%, #101A2E 100%);
        color: #E2E8F0;
    }

    /* Hero banner */
    .kud-hero {
        background: linear-gradient(120deg, #0EA5A5 0%, #0F766E 45%, #1E293B 100%);
        border-radius: 16px;
        padding: 28px 32px;
        margin-bottom: 28px;
        box-shadow: 0 8px 24px rgba(0,0,0,0.35);
    }
    .kud-hero h1 {
        color: #F8FAFC;
        font-size: 30px;
        font-weight: 800;
        margin: 0 0 6px 0;
    }
    .kud-hero p {
        color: #D1FAE5;
        font-size: 15px;
        margin: 0;
        max-width: 780px;
    }
    .kud-hero .kud-badges { margin-top: 14px; }
    .kud-badge {
        display: inline-block;
        background: rgba(255,255,255,0.12);
        color: #ECFDF5;
        border: 1px solid rgba(255,255,255,0.25);
        border-radius: 999px;
        padding: 4px 12px;
        font-size: 12px;
        font-weight: 600;
        margin-right: 8px;
    }

    /* Section headers */
    .kud-section-title {
        display: flex;
        align-items: center;
        gap: 10px;
        color: #F8FAFC;
        font-size: 20px;
        font-weight: 700;
        margin: 6px 0 14px 0;
        border-left: 4px solid #14B8A6;
        padding-left: 10px;
    }
    .kud-section-sub {
        color: #94A3B8;
        font-size: 13px;
        margin: -10px 0 16px 14px;
    }

    /* Card containers (st.container(border=True)) -- lifted clearly off the
       page background, with a visible border, a soft shadow, a teal top
       edge, and breathing room below so consecutive cards (e.g. one PPA
       after another) don't visually run together. */
    div[data-testid="stVerticalBlockBorderWrapper"] {
        background-color: #17233F !important;
        border: 2px solid #4A6BA0 !important;
        border-radius: 14px !important;
        box-shadow: 0 0 0 1px rgba(94,234,212,0.08), 0 6px 20px rgba(0,0,0,0.45);
        margin-bottom: 20px !important;
        position: relative;
        overflow: hidden;
    }
    div[data-testid="stVerticalBlockBorderWrapper"]::before {
        content: "";
        position: absolute;
        top: 0; left: 0; right: 0;
        height: 3px;
        background: linear-gradient(90deg, #14B8A6, #0EA5A5, #14B8A6);
    }

    /* Inputs */
    div[data-testid="stNumberInput"] input,
    div[data-testid="stTextInput"] input {
        background-color: #0B1424 !important;
        border-radius: 8px !important;
        border: 1px solid #26314A !important;
        color: #E2E8F0 !important;
    }
    label, .stMarkdown p, .stCaption { color: #CBD5E1 !important; }

    /* Select / dropdown -- match the upload box's dark styling. Covers
       both the older Baseweb-based select markup and the newer
       react-aria-based one, since the exact DOM depends on the Streamlit
       version. */
    div[data-testid="stSelectbox"] div[data-baseweb="select"] > div,
    div[data-testid="stSelectbox"] div[role="group"] {
        background-color: #0B1424 !important;
        border: 1px solid #26314A !important;
        border-radius: 8px !important;
        color: #E2E8F0 !important;
    }
    div[data-testid="stSelectbox"] input,
    div[data-testid="stSelectbox"] input[role="combobox"] {
        background-color: transparent !important;
        color: #E2E8F0 !important;
    }
    div[data-testid="stSelectbox"] button svg {
        color: #8FA3C4 !important;
        fill: #8FA3C4 !important;
    }
    /* Dropdown popover (renders in a portal, outside the card) */
    div[data-testid="stSelectboxVirtualDropdown"],
    ul[data-baseweb="menu"],
    div[data-baseweb="popover"] {
        background-color: #111C30 !important;
        border: 1px solid #30456B !important;
        border-radius: 10px !important;
    }
    div[data-testid="stSelectboxVirtualDropdown"] [role="option"],
    li[data-baseweb="menu-item"] {
        background-color: transparent !important;
        color: #E2E8F0 !important;
    }
    div[data-testid="stSelectboxVirtualDropdown"] [data-item-hl],
    li[data-baseweb="menu-item"]:hover,
    li[aria-selected="true"] {
        background-color: #1E2E4D !important;
        color: #5EEAD4 !important;
    }

    /* Number input +/- steppers -- dim them to match the dark surface
       instead of the bright default icon color, with a teal hover cue */
    div[data-testid="stNumberInputContainer"] {
        background-color: #0B1424 !important;
        border: 1px solid #26314A !important;
        border-radius: 8px !important;
    }
    button[data-testid="stNumberInputStepUp"],
    button[data-testid="stNumberInputStepDown"] {
        background-color: #0B1424 !important;
        color: #5B6B85 !important;
        border: none !important;
    }
    button[data-testid="stNumberInputStepUp"]:hover,
    button[data-testid="stNumberInputStepDown"]:hover {
        background-color: #16233B !important;
        color: #5EEAD4 !important;
    }

    /* File uploader -- force a dark dropzone regardless of the base theme */
    section[data-testid="stFileUploaderDropzone"] {
        background-color: #0B1424 !important;
        border: 1.5px dashed #30456B !important;
        border-radius: 10px !important;
    }
    section[data-testid="stFileUploaderDropzone"] button {
        background-color: #16233B !important;
        border: 1px solid #30456B !important;
        color: #E2E8F0 !important;
    }
    section[data-testid="stFileUploaderDropzone"] button:hover {
        border-color: #14B8A6 !important;
        color: #5EEAD4 !important;
    }
    section[data-testid="stFileUploaderDropzone"] span,
    section[data-testid="stFileUploaderDropzone"] small,
    div[data-testid="stFileUploaderDropzoneInstructions"] span {
        color: #94A3B8 !important;
    }
    div[data-testid="stFileUploaderFile"] {
        background-color: #0B1424 !important;
        border: 1px solid #26314A !important;
        border-radius: 8px !important;
    }

    /* Buttons */
    .stButton > button {
        border-radius: 10px;
        font-weight: 600;
        border: 1px solid #26314A;
        background-color: #16233B;
        color: #E2E8F0;
        transition: all 0.15s ease;
    }
    .stButton > button:hover {
        border-color: #14B8A6;
        color: #14B8A6;
    }
    .stButton > button[kind="primary"] {
        background: linear-gradient(120deg, #0EA5A5, #0D9488);
        border: none;
        color: #F0FDFA;
        font-size: 16px;
        padding: 12px 0;
    }
    .stButton > button[kind="primary"]:hover {
        background: linear-gradient(120deg, #14B8A6, #0F766E);
        color: #FFFFFF;
    }
    .stDownloadButton > button {
        border-radius: 10px;
        font-weight: 600;
        background-color: #0B3B36;
        border: 1px solid #14B8A6;
        color: #6EE7B7;
    }

    /* Metric cards */
    div[data-testid="stMetric"] {
        background-color: #111C30;
        border: 1px solid #1F2E4A;
        border-radius: 12px;
        padding: 14px 16px 10px 16px;
    }
    div[data-testid="stMetricLabel"] { color: #94A3B8 !important; }
    div[data-testid="stMetricValue"] { color: #5EEAD4 !important; font-weight: 700; }

    /* PPA card accent */
    .kud-ppa-tag-24h {
        background: rgba(14,165,233,0.15); color: #7DD3FC;
        border: 1px solid rgba(14,165,233,0.4);
        border-radius: 999px; padding: 2px 10px; font-size: 11px; font-weight: 700;
    }
    .kud-ppa-tag-limited {
        background: rgba(245,158,11,0.15); color: #FCD34D;
        border: 1px solid rgba(245,158,11,0.4);
        border-radius: 999px; padding: 2px 10px; font-size: 11px; font-weight: 700;
    }

    hr { border-color: #1F2E4A; }
    </style>
    """,
    unsafe_allow_html=True,
)

# -------------------------------------------------------------------------
# Hero
# -------------------------------------------------------------------------
st.markdown(
    """
    <div class="kud-hero">
        <h1>\U0001F300 Watt-A-Wonder</h1>
        <p>Upload hourly generation and exchange-price data, tune the plant, PPA, and BESS
        parameters, and run the full 25-year hour-by-hour dispatch and financial model.</p>
        <div class="kud-badges">
            <span class="kud-badge">Hybrid Wind + Solar + BESS</span>
            <span class="kud-badge">8,760-hour dispatch</span>
            <span class="kud-badge">25-year IRR model</span>
        </div>
    </div>
    """,
    unsafe_allow_html=True,
)


def section_title(icon, title, subtitle=None):
    st.markdown(f'<div class="kud-section-title">{icon} {title}</div>', unsafe_allow_html=True)
    if subtitle:
        st.markdown(f'<div class="kud-section-sub">{subtitle}</div>', unsafe_allow_html=True)


# -- 1. File Handling: Download Template & Upload Filled File -----------
section_title("\U0001F4C2", "1. Upload Generation and Exchange Data")

with st.container(border=True):
    col_down, col_up = st.columns(2)

    with col_down:
        st.markdown("**Step 1 &mdash; Download the template**")
        st.caption(
            "Fill in your hourly Wind/Solar generation (Wind-Solar+BESS sheet) "
            "and hourly Exchange price forecast for each of the 25 years (Exchange sheet)."
        )
        try:
            with open("Kudligi_Template.xlsx", "rb") as template_file:
                st.download_button(
                    label="\U0001F4E5 Download Kudligi_Template.xlsx",
                    data=template_file,
                    file_name="Kudligi_Template.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    use_container_width=True,
                )
        except FileNotFoundError:
            st.warning("'Kudligi_Template.xlsx' not found in the local directory -- run make_kudligi_template.py once.")

    with col_up:
        st.markdown("**Step 2 &mdash; Upload it back, filled in**")
        st.caption("Accepts the filled-in template, or the full Kudligi Spreadsheet.xlsx.")
        uploaded_file = st.file_uploader(
            "Upload workbook",
            type=["xlsx"],
            label_visibility="collapsed",
        )
        if uploaded_file is not None:
            st.success(f"Loaded **{uploaded_file.name}**", icon="✅")

st.write("")

# -- 2. Parameter Inputs -------------------------------------------------
section_title("⚙️", "2. Plant & Financial Parameters")

tab_grid, tab_bess, tab_degrad, tab_capex = st.tabs(
    ["\U0001F50C  Grid & Plant Capacity", "\U0001F50B  BESS", "\U0001F4C9  Degradation", "\U0001F4B0  CapEx & O&M"]
)

with tab_grid:
    with st.container(border=True):
        st.markdown("**Grid Connection & Off-take Caps**")
        col1, col2, col3 = st.columns(3)
        hybrid_conn = col1.number_input("Hybrid Connectivity / GNA (MW)", value=300.0, step=10.0)
        limitedH_RTC = col2.number_input("LimitedH-RTC Cap (MW)", value=100.0, step=10.0)
        all_day_RTC = col3.number_input("24H-RTC Pool Cap (MW)", value=120.0, step=10.0)
        # LimitedH-RTC Tariff input removed: LimitedH-RTC revenue is resolved
        # entirely from each PPA's own "Tariff (Rs/kWh)" field in the PPA
        # portfolio (see Kudligi.calc_ppa_allocation_limited()) -- there is
        # no code path anywhere that reads a single pooled LimitedH tariff,
        # so this input never affected the simulation.

    with st.container(border=True):
        st.markdown("**Plant Capacity**")
        col5, col6, col7 = st.columns(3)
        wind_capacity = col5.number_input("Wind Capacity (MW)", value=300.3, step=10.0)
        ac_solar_capacity = col6.number_input("AC Solar Capacity (MW)", value=275.0, step=10.0)
        dc_ac_overload = col7.number_input("DC/AC Overload Ratio", value=1.5, step=0.1)

# BESS capacity is entered as hours of storage and scaled up linearly to
# kWh, anchored so 5 hours matches the plant's known as-built capacity of
# 526,210.82 kWh (i.e. 1 hour of storage = 526,210.8234882968 / 5 kWh).
BESS_KWH_PER_HOUR = 526_210.8234882968 / 5.0

with tab_bess:
    with st.container(border=True):
        st.markdown("**BESS Sizing & Efficiency**")
        col8, col9, col10 = st.columns(3)
        bess_hours = col8.number_input("BESS Hours of Storage (h)", min_value=0.0, value=5.0, step=0.5)
        bess_capacity_kwh = bess_hours * BESS_KWH_PER_HOUR
        col8.caption(f"→ BESS Capacity: {bess_capacity_kwh:,.2f} kWh")
        pcs_cap = col9.number_input("PCS Power Cap (MW)", value=100.0, step=10.0)
        rte = col10.number_input("Round-Trip Efficiency (%)", min_value=0.0, max_value=100.0, value=84.78, step=0.5) / 100.0

        col11, col12 = st.columns(2)
        max_soc_perc = col11.number_input("Max SoC (%)", min_value=0.0, max_value=100.0, value=100.0, step=5.0) / 100.0
        min_soc_perc = col12.number_input("Min SoC (%)", min_value=0.0, max_value=100.0, value=0.0, step=5.0) / 100.0


eve_start = 20
eve_end = 24
morn_start = 0
morn_end = 1

with tab_degrad:
    with st.container(border=True):
        st.markdown("**Annual Degradation Rates**")
        col17, col18, col19, col20 = st.columns(4)
        solar_gen_degrad = col17.number_input("Solar Generation (%/yr)", value=0.5, step=0.1)
        wind_gen_degrad = col18.number_input("Wind Generation (%/yr)", value=0.2, step=0.1)
        bess_cap_degrad = col19.number_input("BESS Capacity (%/yr)", value=2.0, step=0.1)
        rte_degrad = col20.number_input("BESS RTE (%/yr)", value=0.1, step=0.1)

with tab_capex:
    with st.container(border=True):
        st.markdown("**CapEx**")
        col21, col22, col23 = st.columns(3)
        solar_capex_rate = col21.number_input("Solar CAPEX (Rs Cr/MW)", value=4.0, step=0.5)
        wind_capex_rate = col22.number_input("Wind CAPEX (Rs Cr/MW)", value=9.0, step=0.5)
        bess_capex_rate = col23.number_input("BESS CAPEX (Rs Cr/MWh)", value=1.0, step=0.1)

    with st.container(border=True):
        st.markdown("**Maintenance Cost (Rs Lakh / Capacity / Year)**")
        col24, col25, col26, col27 = st.columns(4)
        solar_maint_rate = col24.number_input("Solar (Rs Lakh/MW)", value=5.0, step=0.5)
        wind_maint_rate = col25.number_input("Wind (Rs Lakh/MW)", value=9.1, step=0.5)
        bess_maint_rate = col26.number_input("BESS (Rs Lakh/MWh)", value=1.0, step=0.5)
        cost_esc = col27.number_input("Cost Escalation (%/yr)", value=3.0, step=0.5)

st.write("")

# -- 2b. PPA Portfolio (card-based editor, not a raw spreadsheet grid) ---
section_title(
    "\U0001F91D",
    "3. PPA Portfolio",
    "24H-RTC / LimitedH-RTC offtake companies &mdash; add, edit, or remove as needed.",
)

if "ppas" not in st.session_state:
    st.session_state.ppas = [dict(p, _id=uuid.uuid4().hex) for p in DEFAULT_PPAS]


def _add_ppa():
    st.session_state.ppas.append(dict(BLANK_PPA, _id=uuid.uuid4().hex))


def _remove_ppa(pid):
    st.session_state.ppas = [p for p in st.session_state.ppas if p["_id"] != pid]


def _reset_ppas():
    st.session_state.ppas = [dict(p, _id=uuid.uuid4().hex) for p in DEFAULT_PPAS]


total_actual = sum(p["Actual Contracted Energy (kWh)"] for p in st.session_state.ppas)
total_quantum = sum(p["RTC Quantum (MW)"] for p in st.session_state.ppas)
m1, m2, m3 = st.columns(3)
m1.metric("Offtakers", len(st.session_state.ppas))
m2.metric("Total Contracted Energy", f"{total_actual / 1e6:,.1f} Mn kWh")
m3.metric("Total RTC Quantum", f"{total_quantum:,.1f} MW")

for ppa_idx, ppa in enumerate(st.session_state.ppas, start=1):
    pid = ppa["_id"]
    with st.container(border=True):
        top_col1, top_col2, top_col3 = st.columns([4, 2, 1])
        ppa["Company"] = top_col1.text_input(
            f"PPA #{ppa_idx} — Company", value=ppa["Company"], key=f"name_{pid}",
            placeholder="Company name",
        )
        ppa["Discharge Period"] = top_col2.selectbox(
            "Discharge Period", options=["24H-RTC", "LimitedH-RTC"],
            index=["24H-RTC", "LimitedH-RTC"].index(ppa["Discharge Period"]),
            key=f"period_{pid}",
        )
        with top_col3:
            st.write("")
            st.button("\U0001F5D1️ Remove", key=f"remove_{pid}", on_click=_remove_ppa, args=(pid,),
                       use_container_width=True)

        tag_class = "kud-ppa-tag-24h" if ppa["Discharge Period"] == "24H-RTC" else "kud-ppa-tag-limited"
        st.markdown(f'<span class="{tag_class}">{ppa["Discharge Period"]}</span>', unsafe_allow_html=True)

        c1, c2, c3, c4 = st.columns(4)
        ppa["Actual Contracted Energy (kWh)"] = c1.number_input(
            "Actual Contracted Energy (kWh)", value=float(ppa["Actual Contracted Energy (kWh)"]),
            step=1000.0, key=f"actual_{pid}",
        )
        ppa["Min Contracted Energy (kWh)"] = c2.number_input(
            "Min Contracted Energy (kWh)", value=float(ppa["Min Contracted Energy (kWh)"]),
            step=1000.0, key=f"min_{pid}",
        )
        ppa["RTC Quantum (MW)"] = c3.number_input(
            "RTC Quantum (MW)", value=float(ppa["RTC Quantum (MW)"]), step=0.5, key=f"quantum_{pid}",
        )
        ppa["Tariff (Rs/kWh)"] = c4.number_input(
            "Tariff (Rs/kWh)", value=float(ppa["Tariff (Rs/kWh)"]), step=0.01, format="%.2f", key=f"tariff_{pid}",
        )

add_col, reset_col = st.columns([1, 1])
add_col.button("➕ Add PPA", on_click=_add_ppa, use_container_width=True)
reset_col.button("↺ Reset to Default Portfolio", on_click=_reset_ppas, use_container_width=True)

with st.expander("\U0001F4CB View portfolio as a table"):
    st.dataframe(
        pd.DataFrame(st.session_state.ppas).drop(columns=["_id"]),
        use_container_width=True,
        hide_index=True,
    )

st.write("")
st.divider()

# -- 3. Execution & Results Display -------------------------------------
section_title("▶️", "4. Run the Simulation")

run_clicked = st.button("\U0001F680 Run 25-Year Simulation", type="primary", use_container_width=True)

if run_clicked:
    if uploaded_file is None:
        st.error("Please upload the filled-in template file before running.", icon="⚠️")
    elif len(st.session_state.ppas) == 0:
        st.error("Add at least one PPA before running.", icon="⚠️")
    else:
        loader_placeholder = st.empty()
        loader_placeholder.markdown(
            """
            <style>
            @keyframes spin { 100% { transform: rotate(360deg); } }
            .turbine-spinner {
                display: inline-block;
                animation: spin 1.5s linear infinite;
                font-size: 50px;
            }
            .loader-container {
                text-align: center;
                padding: 40px;
                background: linear-gradient(120deg, #0EA5A5 0%, #0F766E 60%, #111C30 100%);
                border-radius: 14px;
                border: 1px solid #1F2E4A;
            }
            </style>
            <div class="loader-container">
                <div class="turbine-spinner">\U0001F300</div>
                <h3 style="color: #F8FAFC; margin-top: 15px;">Simulating 25 years of hourly dispatch...</h3>
                <p style="color: #D1FAE5;">Please wait, running the hour-by-hour dispatch for every year.</p>
            </div>
            """,
            unsafe_allow_html=True,
        )
        progress_bar = st.progress(0, text="Starting simulation...")

        def _update_progress(done, total, label):
            progress_bar.progress(done / total, text=f"{label}  ({done}/{total})")

        # Bug fix: a fixed filename here (and for output_path below) means
        # two users clicking "Run Simulation" at the same moment on a
        # public deployment would read/write/overwrite each other's files
        # mid-run. Give every run its own unique filenames.
        run_id = uuid.uuid4().hex
        temp_file_path = f"temp_uploaded_kudligi_gencons_{run_id}.xlsx"
        with open(temp_file_path, "wb") as f:
            f.write(uploaded_file.getbuffer())

        output_path = None
        hourly_dispatch_path = None
        ppa_summary_path = None
        try:
            ppas = [
                PPA(
                    company_name=p["Company"],
                    Annual_Contracted=p["Actual Contracted Energy (kWh)"],
                    Annual_Guaranteed=p["Min Contracted Energy (kWh)"],
                    RTC_Quantum=p["RTC Quantum (MW)"],
                    tariff=p["Tariff (Rs/kWh)"],
                    discharge_period=p["Discharge Period"],
                )
                for p in st.session_state.ppas
            ]

            dash = KudligiDashboard(
                generation_path=temp_file_path,
                hybrid_conn=hybrid_conn,
                PPAs=ppas,
                limitedH_RTC=limitedH_RTC,
                all_day_RTC=all_day_RTC,
                wind_capacity=wind_capacity,
                ac_solar_capacity=ac_solar_capacity,
                dc_ac_overload=dc_ac_overload,
                BESS_discharge_eve_start=eve_start,
                BESS_discharge_eve_end=eve_end,
                BESS_discharge_morn_start=morn_start,
                BESS_discharge_morn_end=morn_end,
                pcs_cap=pcs_cap,
                BESS_capacity=bess_capacity_kwh,
                max_soc_perc=max_soc_perc,
                min_soc_perc=min_soc_perc,
                rte=rte,
                solar_gen_degrad=solar_gen_degrad,
                wind_gen_degrad=wind_gen_degrad,
                BESS_capacity_degrad=bess_cap_degrad,
                RTE_degrad=rte_degrad,
                solar_capex_rate=solar_capex_rate,
                wind_capex_rate=wind_capex_rate,
                bess_capex_rate=bess_capex_rate,
                solar_maintenance_rate=solar_maint_rate,
                wind_maintenance_rate=wind_maint_rate,
                bess_maintenance_rate=bess_maint_rate,
                costs_escalation=cost_esc,
            )

            output_path = f"Kudligi_Revenue_Costs_EBITDA_Table_{run_id}.xlsx"
            hourly_dispatch_path = f"Kudligi_Hourly_Dispatch_25Yr_{run_id}.xlsx"
            ppa_summary_path = f"Kudligi_PPA_Compliance_25Yr_{run_id}.xlsx"
            results = dash.run_dashboard(
                irr_table_path=output_path,
                hourly_dispatch_path=hourly_dispatch_path,
                ppa_summary_path=ppa_summary_path,
                progress_callback=_update_progress,
            )

            loader_placeholder.empty()
            progress_bar.empty()
            st.success("Simulation completed!", icon="✅")
            st.balloons()

            section_title("\U0001F4CA", "Key Performance Indicators")
            m1, m2, m3 = st.columns(3)
            irr_val = results["irr"]
            m1.metric("Project IRR", f"{irr_val:.2%}" if pd.notna(irr_val) else "N/A")
            m2.metric("Capex/EBITDA Ratio", f"{results['capex_to_ebitda_ratio']:.2f}")
            m3.metric(
                "Cumulative Payback Period",
                f"{results['payback']:.2f} Years" if results["payback"] is not None else "N/A",
            )

            section_title(
                "\U0001F50B",
                "PPA Compliance Summary — All 25 Years",
                "Per-company delivered energy, revenue, and shortfall vs. contracted minimum, year by year.",
            )
            compliance_by_year = {u["Year"]: u for u in results["ppa compliance"]}
            year_tabs = st.tabs([f"Year {y}" for y in range(1, 26)])
            for y, tab in zip(range(1, 26), year_tabs):
                with tab:
                    v_with = compliance_by_year[y]["PPAs Violated with BESS"]
                    v_without = compliance_by_year[y]["PPAs Violated without BESS"]
                    v_due_to_bess = compliance_by_year[y]["PPAs Violated due to lack of BESS"]
                    c1, c2, c3 = st.columns(3)
                    c1.metric("Short of Minimum (with BESS)", len(v_with))
                    c2.metric("Short of Minimum (without BESS)", len(v_without))
                    c3.metric("...only short because there's no BESS", len(v_due_to_bess))
                    if v_with:
                        st.caption("Short of their contracted minimum, with BESS: " + ", ".join(v_with))
                    if v_due_to_bess:
                        st.caption("Would meet their minimum if the BESS were present: " + ", ".join(v_due_to_bess))
                    st.dataframe(
                        results["ppa_summaries_by_year"][y],
                        use_container_width=True,
                        hide_index=True,
                    )

            section_title("\U0001F4C8", "Revenue / Costs / EBITDA by Year")
            st.dataframe(results["irr_table"], use_container_width=True, hide_index=True)

            section_title("⬇️", "Download Results")
            dl_col1, dl_col2, dl_col3 = st.columns(3)
            with dl_col1, open(output_path, "rb") as out_file:
                st.download_button(
                    label="\U0001F4CA Download Revenue, Costs & EBITDA Table",
                    data=out_file,
                    file_name="Kudligi_Revenue_Costs_EBITDA_Table.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    use_container_width=True,
                )
            with dl_col2, open(ppa_summary_path, "rb") as ppa_file:
                st.download_button(
                    label="\U0001F91D Download PPA Compliance (25 Years, 1 Sheet/Year)",
                    data=ppa_file,
                    file_name="Kudligi_PPA_Compliance_25Yr.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    use_container_width=True,
                )
            with dl_col3, open(hourly_dispatch_path, "rb") as hourly_file:
                st.download_button(
                    label="\U0001F4C8 Download Hourly Dispatch — All 25 Years (1 Sheet/Year)",
                    data=hourly_file,
                    file_name="Kudligi_Hourly_Dispatch_25Yr.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    use_container_width=True,
                )

        except Exception as e:
            loader_placeholder.empty()
            progress_bar.empty()
            st.error(f"An error occurred during simulation: {e}")

        finally:
            if os.path.exists(temp_file_path):
                os.remove(temp_file_path)
            if output_path and os.path.exists(output_path):
                os.remove(output_path)
            if hourly_dispatch_path and os.path.exists(hourly_dispatch_path):
                os.remove(hourly_dispatch_path)
            if ppa_summary_path and os.path.exists(ppa_summary_path):
                os.remove(ppa_summary_path)

st.write("")
st.caption("Fourth Partner Energy — Kudligi Wind-Solar+BESS dispatch & financial model")
