# DRIVER Framework Documentation – Project 1

## D – Discover & Define
Objective: Build a DCF-based valuation tool that accepts any stock ticker and produces intrinsic value with adjustable assumptions.

## R – Represent
Designed system structure:
- Data retrieval module (yfinance)
- Valuation engine (DCF calculation)
- Sensitivity analysis module
- Equity bridge (EV to per-share)

## I – Implement
Implemented in Python using Streamlit for UI and yfinance for financial data retrieval.

## V – Validate
Validated outputs by:
- Checking financial data consistency
- Testing multiple tickers
- Stress testing assumptions (WACC, growth)
- Ensuring DCF formula matches financial theory

## E – Evolve
Improved formatting, readability, and added sensitivity analysis to meet project requirements.

## R – Reflect
The model is sensitive to discount rate and terminal growth assumptions.
Terminal value accounts for a significant portion of enterprise value, highlighting long-term assumption impact.
