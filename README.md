# Corporate Valuation Application – DCF Tool

## Project Overview
This application estimates intrinsic value using a Discounted Cash Flow (DCF) model.
Users can enter a stock ticker and adjust key assumptions such as WACC, growth rate, and terminal growth.

## Core Features
- Automatic financial data retrieval via yfinance
- Adjustable WACC and growth assumptions
- Enterprise Value calculation
- Equity Value and Per-Share Value output
- Sensitivity analysis across WACC and growth ranges

## DCF Methodology
1. Forecast revenue growth
2. Estimate free cash flow using FCF margin
3. Discount projected cash flows using WACC
4. Estimate terminal value using Gordon Growth model
5. Compute Enterprise Value = PV(FCF) + PV(Terminal Value)
6. Compute Equity Value = EV − Debt + Cash

## How to Run
pip install -r requirements.txt
streamlit run app.py

## AI Usage Disclosure
AI tools (ChatGPT) were used to assist with code structure, debugging, and interface formatting.
All financial logic and valuation assumptions were independently reviewed and validated.
