export type Lang = "en" | "de";

export interface Organisation {
  name: string;
  currency: string;
  currency_symbol: string;
  symbol_position: "prefix" | "suffix" | null;
  language: Lang;
  region_label: string | null;
  country: string;
}

export interface Me {
  user: { email: string; role: string };
  organisation: Organisation;
  ready: boolean;
  tabs: string[];
  data_range: { from: string | null; to: string | null };
  has: Record<string, boolean>;
}

export interface FilterOptions {
  regions: string[];
  cities: string[];
  categories: string[];
  fuel_types: string[];
  brands: string[];
  years: number[];
}

/** A dated point of a monthly series, as the API serialises pandas Series. */
export interface Point {
  x: string;
  y: number | null;
}

export interface Kpis {
  total_sales: number;
  total_sales_delta: number | null;
  total_revenue: number;
  total_revenue_delta: number | null;
  target_attainment_pct: number | null;
  target_attainment_delta: number | null;
  ttm_units: number;
  annual_target: number;
  finance_lease_penetration: number | null;
  finance_lease_penetration_delta: number | null;
}

export interface Glance {
  kpis: Kpis;
  trend: {
    revenue?: Point[];
    units?: Point[];
    revenue_projection?: Point[];
    units_projection?: Point[];
  };
  by_category: { vehicle_category: string; sales: number }[];
  by_fuel: { fuel_type: string; sales: number }[];
  stores: { dealer_name: string; city: string; units: number; revenue: number }[];
  store_average_units: number | null;
}

export interface Play {
  title: string;
  detail: string;
  category: string;
  confidence: "High" | "Medium" | "Low";
  horizon: string;
  impact_amt: number;
  accent: string;
}

export interface Recommendations {
  landing: {
    attainment_pct?: number | null;
    unit_gap?: number;
    gap_per_store_month?: number;
    annual_target?: number;
    history?: Point[];
    projection?: Point[];
  };
  plays: Play[];
  gross_per_unit: number;
}
