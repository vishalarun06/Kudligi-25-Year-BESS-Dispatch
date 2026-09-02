import copy

import numpy as np
import pandas as pd
import numpy_financial as npf

from kudligi_implementation import Kudligi

YEARS = range(26)  # 0 = CAPEX outlay year, 1..25 = operating years


class KudligiDashboard:

    def __init__(self,
                 generation_path,
                 hybrid_conn, PPAs, limitedH_RTC, all_day_RTC,
                 wind_capacity, ac_solar_capacity, dc_ac_overload,
                 BESS_discharge_eve_start, BESS_discharge_eve_end,
                 BESS_discharge_morn_start, BESS_discharge_morn_end,
                 pcs_cap, BESS_capacity, max_soc_perc, min_soc_perc, rte,
                 solar_gen_degrad, wind_gen_degrad, BESS_capacity_degrad, RTE_degrad,
                 solar_capex_rate, wind_capex_rate, bess_capex_rate,
                 solar_maintenance_rate, wind_maintenance_rate, bess_maintenance_rate,
                 costs_escalation,
                 exchange_path=None):

        self.generation_path = generation_path
        # Kudligi now takes generation_path and exchange_path separately
        # (its own Exchange sheet has per-year "Year 1".."Year 25" columns
        # instead of one flat "Average_5Yr" column). The app only ever
        # uploads ONE workbook containing both sheets, so default to
        # reusing generation_path unless a genuinely separate file is given.
        self.exchange_path = exchange_path if exchange_path is not None else generation_path
        self.hybrid_conn = hybrid_conn
        self.PPAs = PPAs
        self.limitedH_RTC = limitedH_RTC
        self.all_day_RTC = all_day_RTC
        self.wind_capacity = wind_capacity
        self.ac_solar_capacity = ac_solar_capacity
        self.dc_ac_overload = dc_ac_overload
        self.BESS_discharge_eve_start = BESS_discharge_eve_start
        self.BESS_discharge_eve_end = BESS_discharge_eve_end
        self.BESS_discharge_morn_start = BESS_discharge_morn_start
        self.BESS_discharge_morn_end = BESS_discharge_morn_end
        self.pcs_cap = pcs_cap
        self.BESS_capacity = BESS_capacity
        self.max_soc_perc = max_soc_perc
        self.min_soc_perc = min_soc_perc
        self.rte = rte

        self.solar_gen_degrad = solar_gen_degrad
        self.wind_gen_degrad = wind_gen_degrad
        self.BESS_capacity_degrad = BESS_capacity_degrad
        self.RTE_degrad = RTE_degrad

        self.solar_capex_rate = solar_capex_rate
        self.wind_capex_rate = wind_capex_rate
        self.bess_capex_rate = bess_capex_rate
        self.solar_maintenance_rate = solar_maintenance_rate
        self.wind_maintenance_rate = wind_maintenance_rate
        self.bess_maintenance_rate = bess_maintenance_rate
        self.costs_escalation = costs_escalation

        self.irr_table = None
        self.year1_plant = None       # kept for the per-company PPA summary / hourly detail views
        self.year1_plant_no_bess = None
        self.hourly_dispatch_by_year = {}   # {year: hourly dispatch DataFrame}, with BESS, all 25 years
        self.ppa_summaries_by_year = {}     # {year: ppa_summary() DataFrame}, with BESS, all 25 years

    def _build_plant_for_year(self, year, bess_capacity_override=None, pcs_cap_override=None):
        """
        Builds and runs a fresh Kudligi instance for the given operating
        year (>=1), with degradation applied. bess_capacity_override /
        pcs_cap_override let calc_grid_utilization_comparison() force a
        zero-BESS run using the exact same generation/PPA/tariff setup.
        """
        if bess_capacity_override is not None:
            bess_capacity_year = bess_capacity_override
        else:
            bess_capacity_year = self.BESS_capacity * (((100 - self.BESS_capacity_degrad) / 100) ** (year - 1))
        pcs_cap_year = self.pcs_cap if pcs_cap_override is None else pcs_cap_override

        plant = Kudligi(
            generation_path=self.generation_path,
            exchange_path=self.exchange_path,
            hybrid_conn=self.hybrid_conn,
            # Bug fix: self.PPAs is one shared list of PPA objects reused
            # across every year AND across the with/without-BESS
            # comparison below. Kudligi.run() mutates each PPA's
            # delivered_energy/revenue/shortfall_vs_minimum IN PLACE, so
            # without a deep copy here, every later year's (or scenario's)
            # run silently overwrites the numbers on the very same PPA
            # objects an earlier year's plant (e.g. self.year1_plant) is
            # still holding a reference to -- so dash.year1_plant.ppa_summary()
            # would end up showing whichever run happened LAST, not Year 1.
            PPAs=copy.deepcopy(self.PPAs),
            limitedH_RTC=self.limitedH_RTC,
            all_day_RTC=self.all_day_RTC,
            wind_capacity=self.wind_capacity,
            ac_solar_capacity=self.ac_solar_capacity,
            dc_ac_overload=self.dc_ac_overload,
            BESS_discharge_eve_start=self.BESS_discharge_eve_start,
            BESS_discharge_eve_end=self.BESS_discharge_eve_end,
            BESS_discharge_morn_start=self.BESS_discharge_morn_start,
            BESS_discharge_morn_end=self.BESS_discharge_morn_end,
            pcs_cap=pcs_cap_year,   # MW -- Kudligi's own __init__ converts this to kW internally
            BESS_capacity=bess_capacity_year,
            max_soc_perc=self.max_soc_perc,
            min_soc_perc=self.min_soc_perc,
            rte=self.rte * (((100 - self.RTE_degrad) / 100) ** (year - 1)),
            year=year,
        )

        wind_factor = ((100 - self.wind_gen_degrad) / 100) ** (year - 1)
        solar_factor = ((100 - self.solar_gen_degrad) / 100) ** (year - 1)
        plant.generation["Wind Generation"] = plant.generation["Wind Generation"] * wind_factor
        plant.generation["Solar Generation"] = plant.generation["Solar Generation"] * solar_factor
        plant.generation["Solar Generation2"] = plant.generation["Solar Generation2"] * solar_factor

        plant.run()
        return plant

    def calc_revenue(self, year):
        """Returns (revenue_RsCr, discharged_MnkWh) for the given year."""
        if year == 0:
            return 0.0, 0.0
        plant = self._build_plant_for_year(year)
        if year == 1:
            self.year1_plant = plant  # kept for the UI's per-company / hourly detail views

        revenue_rs = (
            plant.total_limitedh_rev
            + plant.total24H_rev
            + plant.generation["Exchange Revenue"].sum()
        )
        discharged_kwh = plant.generation["Total Grid Injection"].sum()
        return revenue_rs / 1e7, discharged_kwh / 1e6   # Rs Crore, Mn kWh

    def calc_capex(self):
        """Year-0 CAPEX outlay, Rs Crore."""
        return (
            self.solar_capex_rate * self.ac_solar_capacity
            + self.wind_capex_rate * self.wind_capacity
            + self.bess_capex_rate * (self.BESS_capacity / 1000.0)   # kWh -> MWh
        )

    def calc_maintenance_cost(self, year):
        """O&M cost for the given operating year (>=1), Rs Crore, escalated."""
        bess_capacity_year = self.BESS_capacity * (((100 - self.BESS_capacity_degrad) / 100) ** (year - 1))
        escalation = ((100 + self.costs_escalation) / 100) ** (year - 1)
        cost_lakh = (
            self.solar_maintenance_rate * self.ac_solar_capacity
            + self.wind_maintenance_rate * self.wind_capacity
            + self.bess_maintenance_rate * (bess_capacity_year / 1000.0)
        ) * escalation
        return cost_lakh / 100.0  # Lakh -> Crore

    def calc_irr_table(self, progress_callback=None):
        """
        progress_callback, if given, is called as progress_callback(done, total, label)
        once per year processed -- lets the caller (e.g. a Streamlit progress bar)
        show real progress instead of just a spinner.
        """
        rows = []
        total = len(YEARS)
        for i, year in enumerate(YEARS):
            if year == 0:
                revenue, discharged = 0.0, 0.0
                costs = self.calc_capex()
            else:
                revenue, discharged = self.calc_revenue(year)
                costs = self.calc_maintenance_cost(year)
            rows.append({
                "Year": year,
                "Discharged_MnkWh": discharged,
                "Revenue_RsCr": revenue,
                "Costs_RsCr": costs,
                "EBITDA_RsCr": revenue - costs,
            })
            if progress_callback is not None:
                progress_callback(i + 1, total, f"Revenue / cost model — Year {year}")
        self.irr_table = pd.DataFrame(rows)
        return self.irr_table

    def calc_irr(self):
        if self.irr_table is None:
            self.calc_irr_table()
        return npf.irr(self.irr_table["EBITDA_RsCr"])

    def calc_capex_ebitda_ratio(self):
        if self.irr_table is None:
            self.calc_irr_table()
        capex = self.irr_table.loc[self.irr_table["Year"] == 0, "Costs_RsCr"].iloc[0]
        ebitda_y1 = self.irr_table.loc[self.irr_table["Year"] == 1, "EBITDA_RsCr"].iloc[0]
        return capex / ebitda_y1

    def calc_cumulative_payback_period(self):
        if self.irr_table is None:
            self.calc_irr_table()
        current_val = 0.0
        payback = None
        for i in range(len(self.irr_table)):
            this_year = self.irr_table["EBITDA_RsCr"].iloc[i]
            current_val += this_year
            if current_val >= 0:
                payback = (i - 1) - (current_val - this_year) / this_year
                break
        return payback

    def save_irr_table(self, path="Kudligi_Revenue_Costs_EBITDA_Table.xlsx"):
        if self.irr_table is None:
            self.calc_irr_table()
        self.irr_table.to_excel(path, sheet_name="Revenue_Costs_EBITDA", index=False)
        return path

    def calc_grid_utilization_comparison(self, year=1):
        """
        Kudligi has no "Effective Replacement" concept (that's specific to
        Wind_SolarBESS's PPA-vs-consumption model) -- the closest analogue
        here is grid utilization (actual delivered energy / the hybrid
        connection's theoretical max for the year) with vs. without the
        BESS, isolating exactly how much of that utilization the battery
        is responsible for.
        """
        with_bess = self._build_plant_for_year(year)
        violated_PPAs_BESS = [ppa.company_name for ppa in with_bess.PPAs if ppa.shortfall_vs_minimum != 0.0]
        without_bess = self._build_plant_for_year(year, bess_capacity_override=0.0, pcs_cap_override=0.0)
        violated_PPAs_noBESS = [ppa.company_name for ppa in without_bess.PPAs if ppa.shortfall_vs_minimum != 0.0]
        self.year1_plant_no_bess = without_bess

        # Keep this year's full hourly dispatch (with BESS) -- this is what
        # powers the 25-year hourly-dispatch workbook download, reusing the
        # plant we already built above instead of a fourth simulation run.
        self.hourly_dispatch_by_year[year] = with_bess.generation

        # Keep the full per-company PPA summary (with BESS) for this year --
        # this is what powers the 25-year PPA compliance tabs / downloadable
        # workbook, so we don't need a third build_plant_for_year() call.
        self.ppa_summaries_by_year[year] = with_bess.ppa_summary()

        return {
            "Year": year,
            "PPAs Violated with BESS": violated_PPAs_BESS,
            "PPAs Violated without BESS": violated_PPAs_noBESS,
            "PPAs Violated due to lack of BESS": list(set(violated_PPAs_noBESS) - set(violated_PPAs_BESS)),
        }

    def save_hourly_dispatch_by_year(self, path="Kudligi_Hourly_Dispatch_25Yr.xlsx"):
        """
        Writes one sheet per operating year (Year 1 .. Year 25), each holding
        that year's full 8,760-row hourly dispatch table. Requires
        calc_grid_utilization_comparison() to have already been run for the
        years you want included (run_dashboard() does this for all 25 years).
        """
        if not self.hourly_dispatch_by_year:
            raise RuntimeError(
                "No hourly dispatch computed yet -- call calc_grid_utilization_comparison() "
                "for each year (or run_dashboard()) before saving."
            )
        # xlsxwriter instead of openpyxl here -- with 25 sheets x 8,760 rows
        # each, openpyxl's write path is meaningfully slower. Needs
        # `xlsxwriter` added to requirements.txt.
        with pd.ExcelWriter(path, engine="xlsxwriter") as writer:
            for year in sorted(self.hourly_dispatch_by_year):
                self.hourly_dispatch_by_year[year].to_excel(writer, sheet_name=f"Year {year}", index=False)
        return path

    def save_ppa_summaries_by_year(self, path="Kudligi_PPA_Compliance_25Yr.xlsx"):
        """
        Writes one sheet per operating year (Year 1 .. Year 25), each holding
        that year's full per-company PPA summary (delivered energy, revenue,
        shortfall vs. minimum, etc.) -- the same table shown on the
        dashboard's PPA compliance tabs. Requires calc_grid_utilization_comparison()
        to have already been run for the years you want included (run_dashboard()
        does this for all 25 years).
        """
        if not self.ppa_summaries_by_year:
            raise RuntimeError(
                "No PPA summaries computed yet -- call calc_grid_utilization_comparison() "
                "for each year (or run_dashboard()) before saving."
            )
        with pd.ExcelWriter(path, engine="openpyxl") as writer:
            for year in sorted(self.ppa_summaries_by_year):
                self.ppa_summaries_by_year[year].to_excel(writer, sheet_name=f"Year {year}", index=False)
        return path

    def run_dashboard(self, irr_table_path="Kudligi_Revenue_Costs_EBITDA_Table.xlsx",
                      hourly_dispatch_path="Kudligi_Hourly_Dispatch_25Yr.xlsx",
                      ppa_summary_path="Kudligi_PPA_Compliance_25Yr.xlsx",
                      progress_callback=None):
        """
        progress_callback, if given, is called as progress_callback(done, total, label)
        as work proceeds across all three phases (the IRR table's 26-year pass,
        the 25-year PPA-compliance/hourly-dispatch pass, and the two final
        workbook saves) -- pass e.g. a function that updates a Streamlit
        st.progress() bar.
        """
        n_irr_years = len(YEARS)   # 26 (years 0..25)
        n_compliance_years = 25    # years 1..25
        total_steps = n_irr_years + n_compliance_years + 2   # +2 for the two final saves

        def _irr_progress(done, _total, label):
            if progress_callback is not None:
                progress_callback(done, total_steps, label)

        self.calc_irr_table(progress_callback=_irr_progress)
        self.save_irr_table(irr_table_path)
        irr = self.calc_irr()
        capex_ebitda = self.calc_capex_ebitda_ratio()
        payback = self.calc_cumulative_payback_period()
        utilizations = []
        # Bug fix: range(1, 25) stopped at year 24 and silently dropped
        # Year 25 from both the compliance list and the hourly-dispatch /
        # PPA-summary workbooks below.
        for i in range(1, 26):
            utilization = self.calc_grid_utilization_comparison(year=i)
            utilizations.append(utilization)
            if progress_callback is not None:
                progress_callback(n_irr_years + i, total_steps, f"PPA compliance & hourly dispatch — Year {i}")

        hourly_dispatch_path = self.save_hourly_dispatch_by_year(hourly_dispatch_path)
        if progress_callback is not None:
            progress_callback(n_irr_years + n_compliance_years + 1, total_steps, "Saving hourly dispatch workbook")

        ppa_summary_path = self.save_ppa_summaries_by_year(ppa_summary_path)
        if progress_callback is not None:
            progress_callback(total_steps, total_steps, "Saving PPA compliance workbook")

        year1_compliance = utilizations[0]
        return {
            "irr_table": self.irr_table,
            "irr": irr,
            "capex_to_ebitda_ratio": capex_ebitda,
            "payback": payback,
            "ppa compliance": utilizations,
            "ppa_summaries_by_year": self.ppa_summaries_by_year,
            "hourly_dispatch_excel_path": hourly_dispatch_path,
            "ppa_summary_excel_path": ppa_summary_path,
            # Bug fix: app.py reads these three keys at the top level of the
            # results dict (for the Year-1 compliance summary card), but this
            # method previously only ever returned them nested inside the
            # per-year "ppa compliance" list -- so every run raised a
            # KeyError as soon as results were displayed. Surface Year 1's
            # numbers at the top level too, matching what app.py expects.
            "PPAs Violated with BESS": year1_compliance["PPAs Violated with BESS"],
            "PPAs Violated without BESS": year1_compliance["PPAs Violated without BESS"],
            "PPAs Violated due to lack of BESS": year1_compliance["PPAs Violated due to lack of BESS"],
        }
