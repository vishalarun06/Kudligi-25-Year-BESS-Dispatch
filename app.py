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

st.set_page_config(page_title="Kudligi Wind-Solar+BESS 25-Year Simulation", layout="wide")

st.title("Kudligi Wind-Solar+BESS 25-Year Simulation")
st.markdown(
    "Upload your generation and exchange-price data, fill in the plant, PPA, and BESS "
    "parameters, and run the 25-year dispatch and financial simulation."
)

# -- 1. File Handling: Download Template & Upload Filled File -----------
st.header("1. Upload Generation and Exchange Data")
col_down, col_up = st.columns(2)

with col_down:
    st.markdown(
        "Download the empty Excel template, fill in your hourly Wind/Solar generation "
        "(Wind-Solar+BESS sheet) and hourly Exchange price forecast (Exchange sheet), "
        "and upload it back."
    )
    try:
        with open("Kudligi_Template.xlsx", "rb") as template_file:
            st.download_button(
                label="\U0001F4E5 Download Kudligi_Template.xlsx",
                data=template_file,
                file_name="Kudligi_Template.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )
    except FileNotFoundError:
        st.warning("'Kudligi_Template.xlsx' not found in the local directory -- run make_kudligi_template.py once.")

with col_up:
    uploaded_file = st.file_uploader(
        "\U0001F4E4 Upload your filled-in Kudligi_Template.xlsx (or the full Kudligi Spreadsheet.xlsx)",
        type=["xlsx"],
    )

st.divider()

# -- 2. Parameter Inputs -------------------------------------------------
st.header("2. Parameters")

st.subheader("Grid Connection & Off-take Caps")
col1, col2, col3, col4 = st.columns(4)
hybrid_conn = col1.number_input("Hybrid Connectivity / GNA (MW)", value=300.0, step=10.0)
limitedH_RTC = col2.number_input("LimitedH-RTC Cap (MW)", value=100.0, step=10.0)
all_day_RTC = col3.number_input("24H-RTC Pool Cap (MW)", value=120.0, step=10.0)
limitedH_tariff = col4.number_input("LimitedH-RTC Tariff (Rs/kWh)", value=5.65, step=0.05)

st.subheader("Plant Capacity")
col5, col6, col7 = st.columns(3)
wind_capacity = col5.number_input("Wind Capacity (MW)", value=300.3, step=10.0)
ac_solar_capacity = col6.number_input("AC Solar Capacity (MW)", value=275.0, step=10.0)
dc_ac_overload = col7.number_input("DC/AC Overload Ratio", value=1.5, step=0.1)

st.subheader("BESS")
col8, col9, col10 = st.columns(3)
bess_capacity_kwh = col8.number_input("BESS Max SoC (kWh)", value=526_210.82, step=1000.0, format="%.2f")
pcs_cap = col9.number_input("PCS Power Cap (MW)", value=100.0, step=10.0)
rte = col10.number_input("Round-Trip Efficiency (%)", min_value=0.0, max_value=100.0, value=84.78, step=0.5) / 100.0

col11, col12 = st.columns(2)
max_soc_perc = col11.number_input("Max SoC (%)", min_value=0.0, max_value=100.0, value=100.0, step=5.0) / 100.0
min_soc_perc = col12.number_input("Min SoC (%)", min_value=0.0, max_value=100.0, value=0.0, step=5.0) / 100.0

st.subheader("BESS Discharge Windows (Hour of day, 1-24)")
col13, col14, col15, col16 = st.columns(4)
eve_start = col13.number_input("Evening Discharge Start", min_value=1, max_value=24, value=20, step=1)
eve_end = col14.number_input("Evening Discharge End", min_value=1, max_value=24, value=24, step=1)
morn_start = col15.number_input("Morning Discharge Start", min_value=0, max_value=24, value=0, step=1)
morn_end = col16.number_input("Morning Discharge End", min_value=0, max_value=24, value=1, step=1)

st.subheader("Degradation (%/yr)")
col17, col18, col19, col20 = st.columns(4)
solar_gen_degrad = col17.number_input("Solar Generation Degradation (%/yr)", value=0.5, step=0.1)
wind_gen_degrad = col18.number_input("Wind Generation Degradation (%/yr)", value=0.2, step=0.1)
bess_cap_degrad = col19.number_input("BESS Capacity Degradation (%/yr)", value=2.0, step=0.1)
rte_degrad = col20.number_input("BESS RTE Degradation (%/yr)", value=0.1, step=0.1)

st.subheader("CapEx")
col21, col22, col23 = st.columns(3)
solar_capex_rate = col21.number_input("Solar CAPEX (Rs Cr/MW)", value=4.0, step=0.5)
wind_capex_rate = col22.number_input("Wind CAPEX (Rs Cr/MW)", value=9.0, step=0.5)
bess_capex_rate = col23.number_input("BESS CAPEX (Rs Cr/MWh)", value=1.0, step=0.1)

st.subheader("Maintenance Cost (Rs Lakh / Capacity / Year)")
col24, col25, col26, col27 = st.columns(4)
solar_maint_rate = col24.number_input("Solar Maintenance (Rs Lakh/MW)", value=5.0, step=0.5)
wind_maint_rate = col25.number_input("Wind Maintenance (Rs Lakh/MW)", value=9.1, step=0.5)
bess_maint_rate = col26.number_input("BESS Maintenance (Rs Lakh/MWh)", value=1.0, step=0.5)
cost_esc = col27.number_input("Cost Escalation (%/yr)", value=3.0, step=0.5)

st.subheader("PPA Portfolio (24H-RTC / LimitedH-RTC companies)")
st.markdown("Edit the table below to match your own PPA book -- add or remove rows as needed.")
ppa_df = st.data_editor(
    pd.DataFrame(DEFAULT_PPAS),
    num_rows="dynamic",
    use_container_width=True,
)

st.divider()

# -- 3. Execution & Results Display -------------------------------------
st.header("3. Run the Simulation")

if st.button("Run Simulation", type="primary"):
    if uploaded_file is None:
        st.error("Please upload the filled-in template file before running.")
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
                color: #F37021;
            }
            .loader-container {
                text-align: center;
                padding: 40px;
                background-color: #1E293B;
                border-radius: 8px;
                border: 1px solid #334155;
            }
            </style>
            <div class="loader-container">
                <div class="turbine-spinner">\U0001F300</div>
                <h3 style="color: #F8FAFC; margin-top: 15px;">Simulating 25 years of hourly dispatch...</h3>
                <p style="color: #9CA3AF;">Please wait, running the hour-by-hour dispatch for every year.</p>
            </div>
            """,
            unsafe_allow_html=True,
        )

        # Bug fix: a fixed filename here (and for output_path below) means
        # two users clicking "Run Simulation" at the same moment on a
        # public deployment would read/write/overwrite each other's files
        # mid-run. Give every run its own unique filenames.
        run_id = uuid.uuid4().hex
        temp_file_path = f"temp_uploaded_kudligi_gencons_{run_id}.xlsx"
        with open(temp_file_path, "wb") as f:
            f.write(uploaded_file.getbuffer())

        output_path = None
        try:
            # Bug fix: ppa_class.PPA's constructor parameters are now named
            # Annual_Contracted / Annual_Guaranteed (not min_contracted_energy /
            # actual_contracted_energy) -- calling with the old keyword names
            # raises TypeError the moment this runs.
            ppas = [
                PPA(
                    company_name=row["Company"],
                    Annual_Contracted=row["Actual Contracted Energy (kWh)"],
                    Annual_Guaranteed=row["Min Contracted Energy (kWh)"],
                    RTC_Quantum=row["RTC Quantum (MW)"],
                    tariff=row["Tariff (Rs/kWh)"],
                    discharge_period=row["Discharge Period"],
                )
                for _, row in ppa_df.iterrows()
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
                limitedH_tariff=limitedH_tariff,
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
            results = dash.run_dashboard(irr_table_path=output_path)

            loader_placeholder.empty()
            st.success("Simulation completed!")
            st.balloons()

            st.subheader("Key Performance Indicators")
            m1, m2, m3 = st.columns(3)
            irr_val = results["irr"]
            m1.metric("Project IRR", f"{irr_val:.2%}" if pd.notna(irr_val) else "N/A")
            m2.metric("Capex/EBITDA Ratio", f"{results['capex_to_ebitda_ratio']:.2f}")
            m3.metric(
                "Cumulative Payback Period",
                f"{results['payback']:.2f} Years" if results["payback"] is not None else "N/A",
            )

            # Bug fix: calc_grid_utilization_comparison() now reports which
            # PPAs' contracted minimums were violated, not a utilization
            # percentage -- results['Grid_Utilization_With_BESS'] no longer
            # exists, so reading it raised a KeyError.
            st.subheader("PPA Minimum-Supply Compliance (Year 1)")
            v_with = results["PPAs Violated with BESS"]
            v_without = results["PPAs Violated without BESS"]
            v_due_to_bess = results["PPAs Violated due to lack of BESS"]
            c1, c2, c3 = st.columns(3)
            c1.metric("PPAs Short of Minimum (with BESS)", len(v_with))
            c2.metric("PPAs Short of Minimum (without BESS)", len(v_without))
            c3.metric("...of which, only short because there's no BESS", len(v_due_to_bess))
            if v_with:
                st.caption("Short of their contracted minimum, with BESS: " + ", ".join(v_with))
            if v_due_to_bess:
                st.caption("Would meet their minimum if the BESS were present: " + ", ".join(v_due_to_bess))

            st.subheader("Revenue / Costs / EBITDA by Year")
            st.dataframe(results["irr_table"], use_container_width=True)

            st.subheader("Year 1 -- Per-Company PPA Summary")
            if dash.year1_plant is not None:
                st.dataframe(dash.year1_plant.ppa_summary(), use_container_width=True)

            st.markdown("### Download Simulation Results")
            dl_col1, dl_col2 = st.columns(2)
            with dl_col1, open(output_path, "rb") as out_file:
                st.download_button(
                    label="\U0001F4CA Download Revenue, Costs & EBITDA Table",
                    data=out_file,
                    file_name="Kudligi_Revenue_Costs_EBITDA_Table.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                )
            if dash.year1_plant is not None:
                hourly_csv = dash.year1_plant.generation.to_csv(index=False).encode("utf-8")
                with dl_col2:
                    st.download_button(
                        label="\U0001F4C8 Download Year 1 Hourly Dispatch (CSV)",
                        data=hourly_csv,
                        file_name="Kudligi_Year1_Hourly_Dispatch.csv",
                        mime="text/csv",
                    )

        except Exception as e:
            loader_placeholder.empty()
            st.error(f"An error occurred during simulation: {e}")

        finally:
            if os.path.exists(temp_file_path):
                os.remove(temp_file_path)
            if output_path and os.path.exists(output_path):
                os.remove(output_path)