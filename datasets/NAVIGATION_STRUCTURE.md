# Final Locked Navigation — 7 Tabs, 20 Screens

## Quick Reference

| Tab | Nav Item | Screen # | Screen Name | Route |
|-----|----------|:--------:|-------------|-------|
| **Home** | CEO Dashboard | 1 | CEO Executive Dashboard | `/` |
| | AI Copilot | 2 | AI Executive Copilot | `/copilot` |
| **Sales** | Sales Performance | 3 | Sales Performance Dashboard | `/sales/performance` |
| | Lead Intelligence | 4 | Lead Intelligence Dashboard | `/sales/leads` |
| | Lead Quality | 5 | Lead Source Quality Dashboard | `/sales/lead-quality` |
| | Customer 360 | 6 | Customer 360 Dashboard | `/sales/customer360` |
| | Buyer Segmentation | 7 | Buyer Segmentation Dashboard | `/sales/segments` |
| **Projects** | Project Performance | 8 | Project Performance Dashboard | `/projects/performance` |
| | Construction Intelligence | 9 | Construction Intelligence Dashboard | `/projects/construction` |
| **Market** | Demand Forecast | 12 | Demand Forecast Dashboard | `/market/forecast` |
| | Market Intelligence | 13 | Market Intelligence Dashboard | `/market/intelligence` |
| | Builder Launch Tracker | 14 | Builder Launch Tracker | `/market/launches` |
| | Rental Trends | 15 | Rental Trends Dashboard | `/market/rental` |
| **Finance** | Financial Intelligence | 17 | Revenue + Cash Flow (two sections) | `/finance/intelligence` |
| | Risk Management | 18 | Risk Management Dashboard | `/finance/risk` |
| **Investors** | Investor Intelligence | 16 | ROI Calculator + Opportunities (two panels) | `/investors` |
| **Operations** | Inventory Intelligence | 10 | Inventory Intelligence Dashboard | `/operations/inventory` |
| | Pricing Intelligence | 11 | Pricing Intelligence Dashboard | `/operations/pricing` |
| | Document Intelligence | 19 | Document Intelligence Dashboard | `/operations/documents` |
| | Strategic Planning | 20 | Strategic Planning Dashboard | `/operations/strategy` |

---

## Tab Summary

| Tab | Screen Count | Screen Numbers | Nav Items |
|-----|:------------:|----------------|-----------|
| Home | 2 | 1, 2 | CEO Dashboard, AI Copilot |
| Sales | 5 | 3, 4, 5, 6, 7 | Sales Performance, Lead Intelligence, Lead Quality, Customer 360, Buyer Segmentation |
| Projects | 2 | 8, 9 | Project Performance, Construction Intelligence |
| Market | 4 | 12, 13, 14, 15 | Demand Forecast, Market Intelligence, Builder Launch Tracker, Rental Trends |
| Finance | 2 | 17, 18 | Financial Intelligence, Risk Management |
| Investors | 1 | 16 | Investor Intelligence |
| Operations | 4 | 10, 11, 19, 20 | Inventory Intelligence, Pricing Intelligence, Document Intelligence, Strategic Planning |
| **Total** | **20** | **1–20** | **21 nav items** |

---

## Layout Decisions (Locked)

- **Finance → Screen 17:** Single page. Revenue Analytics section on top, Cash Flow section below — single scroll, one route `/finance/intelligence`.
- **Investors → Screen 16:** Single page. ROI Calculator panel on top, Best Investment Opportunities ranked list below — one route `/investors`.
- **Screen 7 (Buyer Segmentation):** Placed under Sales tab (not in original nav spec; added here as the logical home).

---

## Implementation Order (Suggested)

| Priority | Tab | Screens | Reason |
|----------|-----|---------|--------|
| 1 | Home | 1, 2 | CEO dashboard is the entry point; sets the tone for the whole app |
| 2 | Sales | 3, 4, 5 | Sales funnel data drives immediate business value |
| 3 | Market | 12, 13, 14, 15 | Demand forecast + market intelligence are core AI features |
| 4 | Finance | 17, 18 | Revenue and risk are CEO priorities |
| 5 | Projects | 8, 9 | Construction tracking depends on real project data |
| 6 | Operations | 10, 11, 19, 20 | Inventory, pricing, documents, strategy |
| 7 | Sales (cont.) | 6, 7 | Customer 360 and segmentation need CRM data layer |
| 8 | Investors | 16 | ROI calculator — depends on rental and property datasets |
