import streamlit as st
import pandas as pd
import math

# Optional: yfinance for pulling data
try:
    import yfinance as yf
    HAS_YF = True
except Exception:
    HAS_YF = False


# -------------------------
# Formatting helpers
# -------------------------
def fmt_money_short(x_millions: float) -> str:
    """
    Input is in MILLIONS.
    Output like $948.13B, $35.93B, $272.05B, $885.41B
    """
    if x_millions is None or (isinstance(x_millions, float) and math.isnan(x_millions)):
        return "—"
    x = float(x_millions)
    sign = "-" if x < 0 else ""
    x = abs(x)

    if x >= 1_000_000:  # >= 1T (in millions)
        return f"{sign}${x/1_000_000:,.2f}T"
    if x >= 1_000:      # >= 1B (in millions)
        return f"{sign}${x/1_000:,.2f}B"
    return f"{sign}${x:,.2f}M"


def fmt_num(x: float, decimals: int = 2) -> str:
    if x is None or (isinstance(x, float) and math.isnan(x)):
        return "—"
    return f"{x:,.{decimals}f}"


# -------------------------
# Core model
# -------------------------
def compute_dcf(
    revenue0_m: float,
    fcf_margin: float,
    growth: float,
    wacc: float,
    years: int,
    terminal_growth: float
):
    """
    revenue0_m is starting revenue in MILLIONS.
    fcf_margin, growth, wacc, terminal_growth are decimals (0.10 = 10%).
    Returns:
      df (table)
      pv_forecast_m
      terminal_value_m (undiscounted)
      pv_terminal_m
      enterprise_value_m
      terminal_share_of_ev (0-1)
    """
    if revenue0_m <= 0:
        raise ValueError("Starting revenue must be greater than 0.")
    if years < 1:
        raise ValueError("Projection years must be at least 1.")
    if wacc <= terminal_growth:
        raise ValueError("WACC must be greater than terminal growth.")

    rows = []
    revenue = revenue0_m

    for t in range(1, years + 1):
        revenue = revenue * (1 + growth)
        fcf = revenue * fcf_margin
        pv = fcf / ((1 + wacc) ** t)
        rows.append({
            "Year": t,
            "Revenue (M)": revenue,
            "Projected FCF (M)": fcf,
            "Discounted FCF (PV, M)": pv
        })

    df = pd.DataFrame(rows)

    pv_forecast = float(df["Discounted FCF (PV, M)"].sum())
    final_fcf = float(df.iloc[-1]["Projected FCF (M)"])

    terminal_value = final_fcf * (1 + terminal_growth) / (wacc - terminal_growth)
    pv_terminal = terminal_value / ((1 + wacc) ** years)

    enterprise_value = pv_forecast + pv_terminal
    terminal_share = pv_terminal / enterprise_value if enterprise_value > 0 else 0.0

    return df, pv_forecast, terminal_value, pv_terminal, enterprise_value, terminal_share


def compute_equity_per_share(ev_m, cash_m, debt_m, shares_m):
    equity_value_m = ev_m - debt_m + cash_m
    per_share = equity_value_m / shares_m if shares_m and shares_m > 0 else None
    return equity_value_m, per_share


# -------------------------
# Data pull (yfinance)
# -------------------------
@st.cache_data(show_spinner=False)
def pull_yf_defaults(ticker: str):
    """
    Returns dict with defaults in MILLIONS where relevant:
      revenue0_m, cash_m, debt_m, shares_m, notes(list[str])
    """
    out = {
        "revenue0_m": 1000.0,
        "cash_m": 0.0,
        "debt_m": 0.0,
        "shares_m": 0.0,
        "notes": []
    }

    if not HAS_YF or not ticker:
        out["notes"].append("No live data source (manual inputs).")
        return out

    try:
        t = yf.Ticker(ticker)

        # --- Revenue ---
        rev0 = None

        # Try multiple places depending on yfinance version
        fin = getattr(t, "financials", None)
        if fin is not None and hasattr(fin, "empty") and not fin.empty:
            for label in ["Total Revenue", "TotalRevenue", "Revenue"]:
                if label in fin.index:
                    rev0 = fin.loc[label].iloc[0]
                    break

        if rev0 is None:
            # Some versions expose income_stmt / get_income_stmt
            income = getattr(t, "income_stmt", None)
            if income is not None and hasattr(income, "empty") and not income.empty:
                for label in ["Total Revenue", "TotalRevenue", "Revenue"]:
                    if label in income.index:
                        rev0 = income.loc[label].iloc[0]
                        break

        if rev0 is not None:
            out["revenue0_m"] = float(rev0) / 1_000_000
            out["notes"].append(f"Revenue pulled from yfinance: {out['revenue0_m']:,.2f}M")
        else:
            out["notes"].append("Revenue not found in yfinance (using manual).")

        # --- Balance Sheet cash/debt ---
        bs = getattr(t, "balance_sheet", None)
        if bs is not None and hasattr(bs, "empty") and not bs.empty:
            cash_val = None
            for label in ["Cash And Cash Equivalents", "CashAndCashEquivalents", "Cash"]:
                if label in bs.index:
                    cash_val = bs.loc[label].iloc[0]
                    break

            debt_val = None
            for label in ["Total Debt", "TotalDebt", "Long Term Debt", "LongTermDebt"]:
                if label in bs.index:
                    debt_val = bs.loc[label].iloc[0]
                    break

            if cash_val is not None:
                out["cash_m"] = float(cash_val) / 1_000_000
                out["notes"].append(f"Cash pulled from yfinance: {out['cash_m']:,.2f}M")
            else:
                out["notes"].append("Cash not found in yfinance (using manual).")

            if debt_val is not None:
                out["debt_m"] = float(debt_val) / 1_000_000
                out["notes"].append(f"Debt pulled from yfinance: {out['debt_m']:,.2f}M")
            else:
                out["notes"].append("Debt not found in yfinance (using manual).")
        else:
            out["notes"].append("Balance sheet not available (using manual for cash/debt).")

        # --- Shares ---
        shares = None
        # fast_info is usually more reliable
        fast_info = getattr(t, "fast_info", None)
        if isinstance(fast_info, dict):
            shares = fast_info.get("shares", None)

        if shares is None:
            info = getattr(t, "info", {}) or {}
            shares = info.get("sharesOutstanding", None)

        if shares:
            out["shares_m"] = float(shares) / 1_000_000
            out["notes"].append(f"Shares pulled from yfinance: {out['shares_m']:,.2f}M")
        else:
            out["notes"].append("Shares not found in yfinance (using manual).")

        return out

    except Exception:
        out["notes"] = ["yfinance pull failed (manual inputs)."]
        return out


# -------------------------
# UI
# -------------------------
st.set_page_config(page_title="DCF Valuation Tool", layout="wide")
st.title("DCF Valuation Tool")
st.caption("Simple DCF structure (forecast + terminal value) with optional live inputs from yfinance.")

# Sidebar inputs
st.sidebar.header("Inputs")
ticker = st.sidebar.text_input("Ticker", value="AAPL").strip().upper()

defaults = pull_yf_defaults(ticker)

revenue0_m = st.sidebar.number_input("Starting Revenue (M)", min_value=0.0, value=float(defaults["revenue0_m"]), step=100.0)

fcf_margin_pct = st.sidebar.number_input("FCF Margin (% of revenue)", min_value=0.0, max_value=100.0, value=15.0, step=0.5)
growth_pct = st.sidebar.number_input("Annual Growth (%)", min_value=-50.0, max_value=50.0, value=5.0, step=0.5)
wacc_pct = st.sidebar.number_input("Discount Rate / WACC (%)", min_value=0.1, max_value=30.0, value=10.0, step=0.25)
terminal_growth_pct = st.sidebar.number_input("Terminal Growth (%)", min_value=-5.0, max_value=10.0, value=2.5, step=0.25)
years = st.sidebar.slider("Projection Years", 1, 15, 5)

st.sidebar.divider()
st.sidebar.subheader("Equity Bridge (per share)")
cash_m = st.sidebar.number_input("Cash (M)", min_value=0.0, value=float(defaults["cash_m"]), step=100.0)
debt_m = st.sidebar.number_input("Debt (M)", min_value=0.0, value=float(defaults["debt_m"]), step=100.0)
shares_m = st.sidebar.number_input("Shares Outstanding (M)", min_value=0.0, value=float(defaults["shares_m"]), step=10.0)

st.sidebar.divider()
st.sidebar.subheader("Sensitivity Settings")
g_min = st.sidebar.number_input("Growth min (%)", value=2.0, step=0.5)
g_max = st.sidebar.number_input("Growth max (%)", value=6.0, step=0.5)
r_min = st.sidebar.number_input("WACC min (%)", value=8.0, step=0.5)
r_max = st.sidebar.number_input("WACC max (%)", value=12.0, step=0.5)
step = st.sidebar.number_input("Step (%)", value=1.0, step=0.5)

# Convert to decimals
fcf_margin = fcf_margin_pct / 100.0
growth = growth_pct / 100.0
wacc = wacc_pct / 100.0
terminal_growth = terminal_growth_pct / 100.0

# Tabs (clean, no “A+” labels)
tab_val, tab_sens, tab_notes = st.tabs(["Valuation", "Sensitivity", "Model Notes"])

with tab_val:
    left, right = st.columns([1.1, 1.0])

    with left:
        st.subheader("Inputs Used")
        st.info("\n".join(defaults["notes"]) if defaults["notes"] else "Manual inputs.")

        try:
            df, pv_forecast, terminal_value, pv_terminal, ev, terminal_share = compute_dcf(
                revenue0_m=revenue0_m,
                fcf_margin=fcf_margin,
                growth=growth,
                wacc=wacc,
                years=years,
                terminal_growth=terminal_growth
            )

            # Top metrics (readable!)
            st.subheader("Results")
            m1, m2, m3 = st.columns(3)
            m1.metric("Enterprise Value (PV)", fmt_money_short(ev))
            m2.metric("PV of Forecast FCF", fmt_money_short(pv_forecast))
            m3.metric("PV of Terminal Value", fmt_money_short(pv_terminal))

            m4, m5 = st.columns(2)
            m4.metric("Terminal Share of EV", f"{terminal_share*100:.1f}%")
            m5.metric("Terminal Value (undiscounted)", fmt_money_short(terminal_value))

            equity_value_m, per_share = compute_equity_per_share(ev, cash_m, debt_m, shares_m)

            st.divider()
            st.subheader("Equity Value")
            e1, e2 = st.columns(2)
            e1.metric("Equity Value = EV − Debt + Cash", fmt_money_short(equity_value_m))
            if per_share is not None:
                e2.metric("Intrinsic Value per Share", f"${per_share:,.2f}")
            else:
                e2.metric("Intrinsic Value per Share", "—")
                st.caption("Enter shares outstanding to compute per-share value.")

        except Exception as e:
            st.error(f"Model error: {e}")
            df = None

    with right:
        st.subheader("Projected Cash Flows")

        if df is not None:
            show_full = st.checkbox("Show full numbers (not abbreviated)", value=False)

            display_df = df.copy()
            if not show_full:
                # Keep revenue + FCF columns readable by rounding
                display_df["Revenue (M)"] = display_df["Revenue (M)"].round(2)
                display_df["Projected FCF (M)"] = display_df["Projected FCF (M)"].round(2)
                display_df["Discounted FCF (PV, M)"] = display_df["Discounted FCF (PV, M)"].round(2)

            st.dataframe(display_df, use_container_width=True, hide_index=True)

            # Chart
            chart_df = df.set_index("Year")[["Projected FCF (M)", "Discounted FCF (PV, M)"]]
            st.line_chart(chart_df)

            # Download CSV
            csv = df.to_csv(index=False).encode("utf-8")
            st.download_button("Download projection table (CSV)", csv, file_name=f"{ticker}_dcf_projection.csv")

with tab_sens:
    st.subheader("Sensitivity Table (Enterprise Value, PV)")
    st.caption("How Enterprise Value changes as Growth and WACC change.")

    try:
        # Build ranges safely
        if step <= 0:
            st.warning("Step must be > 0.")
        else:
            g_vals = []
            x = g_min
            while x <= g_max + 1e-9:
                g_vals.append(round(x, 4))
                x += step

            r_vals = []
            y = r_min
            while y <= r_max + 1e-9:
                r_vals.append(round(y, 4))
                y += step

            # Cap grid size so it doesn't explode
            if len(g_vals) * len(r_vals) > 121:
                st.warning("Sensitivity grid too large. Increase Step or tighten ranges.")
            else:
                grid = []
                for r in r_vals:
                    row = []
                    for g in g_vals:
                        try:
                            df_s, pv_f, tv, pv_t, ev_s, ts = compute_dcf(
                                revenue0_m=revenue0_m,
                                fcf_margin=fcf_margin,
                                growth=g / 100.0,
                                wacc=r / 100.0,
                                years=years,
                                terminal_growth=terminal_growth
                            )
                            row.append(ev_s)
                        except Exception:
                            row.append(float("nan"))
                    grid.append(row)

                sens_df = pd.DataFrame(
                    grid,
                    index=[f"{r:.1f}%" for r in r_vals],
                    columns=[f"{g:.1f}%" for g in g_vals]
                )

                st.dataframe(sens_df.round(0), use_container_width=True)

    except Exception as e:
        st.error(f"Sensitivity error: {e}")

with tab_notes:
    st.subheader("Model Notes")
    st.write(
        """
**Core setup**
- Forecast FCF each year using: **FCF = Revenue × FCF margin**
- Discount each year: **PV = FCF / (1 + WACC)^t**
- Terminal value (Gordon Growth): **TV = FCF_N × (1 + g) / (WACC − g)**
- Enterprise value: **EV = PV(FCF years 1..N) + PV(TV)**
- Equity value: **Equity = EV − Debt + Cash**
- Per share: **Equity / Shares**
        """
    )

  