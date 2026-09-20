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

/* ── Store performance ─────────────────────────────────────────────────────────────────────────────────────── */
export interface StoreRow {
  dealer_id: string;
  dealer_name: string;
  brand: string;
  city: string | null;
  region: string | null;
  latitude: number | null;
  longitude: number | null;
  units_sold: number;
  revenue: number;
  est_gross: number;
  attainment_pct: number | null;
  yoy_units_pct: number | null;
  close_rate: number | null;
  avg_days_to_close: number | null;
  top_category: string | null;
}
export interface Scorecard {
  rows: StoreRow[];
  behind_plan_pct: number;
}

/* ── Comparative analytics ─────────────────────────────────────────────────────────────────────────────────── */
export type Measure = "units" | "revenue";
export interface Tracking {
  status: "ok" | "no_sales" | "no_history";
  windows?: { cur_label: string };
  comparable?: boolean;
  year?: number;
  rows?: { month: number; last_year: number | null; booked: number | null; forecast: number | null }[];
  has_forecast?: boolean;
  complete_year?: boolean;
  projected_total?: number;
  last_year_total?: number;
  projected_yoy_pct?: number | null;
}
export type Dimension = "store" | "brand" | "category";
export interface Drivers {
  status: "ok" | "no_prior_year";
  dimension?: Dimension;
  specific_label?: string;
  n_significant?: number;
  rows?: { name: string; total: number; structural: number; specific: number; significant: boolean }[];
  sentences?: string[];
}

/* ── Demand forecast ───────────────────────────────────────────────────────────────────────────────────────── */
export interface Lever {
  key: string;
  unit: string;
  current: number;
  min: number;
  max: number;
  step: number;
}
export interface ForecastOptions {
  brands: string[];
  levers: Lever[];
  average_loan: number;
}
export interface ForecastReport {
  status: "ok" | "no_data" | "insufficient_history" | "horizon_too_short";
  target?: string;
  horizon_months?: number;
  headline?: {
    expected: number;
    low: number;
    high: number;
    yoy_pct: number | null;
    run_rate: number;
    run_rate_delta_pct: number | null;
    confidence_pct: number;
  };
  history?: { x: string; y: number }[];
  forecast?: { x: string; expected: number; low: number; high: number }[];
  busiest_month?: number;
  seasonality?: {
    monthly: { month: number; effect: number }[] | null;
    weekly: { day: number; effect: number }[] | null;
  };
  what_if?: { net_pct: number; active: boolean; value_shift: number; average_loan: number; loan_months: number };
}

/* ── Customers ─────────────────────────────────────────────────────────────────────────────────────────────── */
export interface Retention {
  status: "ok" | "no_customers";
  records?: number;
  buyers?: number;
  repeat_rate_pct?: number;
  repeat_share_pct?: number;
  queue_total?: number;
  queue_stores?: string[];
  queue_reasons?: Record<string, number>;
  book?: { band: string; customers: number; lifetime_value: number }[];
  segments?: {
    segment: string;
    customers: number;
    share_pct: number;
    lifetime_revenue: number;
    avg_deal_value: number;
    repeat_rate_pct: number;
    lease_pct: number;
    median_income: number;
    avg_credit: number;
    months_since_deal: number | null;
  }[];
}
export interface QueueRow {
  name: string;
  store: string | null;
  reason: string;
  play: string;
  when_days: number | null;
  vehicle: string | null;
  months_since_last_deal: number | null;
  opportunity_amt: number;
  email_opt_in: boolean | null;
}
export interface QueuePage {
  total: number;
  rows: QueueRow[];
}
export interface NumericRange {
  lo: number;
  hi: number;
  p50: number;
}
export interface LeadStatus {
  state: "not_trained" | "trained" | "cannot_train";
  /** Why the model could not be trained (English, written for the account's administrator). */
  message?: string;
  weak?: boolean;
  /** Inputs this account has no data for; the form leaves them out. */
  missing_features?: string[];
}
export interface LeadForm {
  stores: { store: string; city: string; region: string; brand: string }[];
  model: {
    options: Record<"occupation" | "vehicle_category" | "fuel_type" | "marketing_channel", string[]>;
    stats: Partial<Record<"age" | "annual_income" | "credit_score" | "base_price", NumericRange>>;
  } | null;
  status: LeadStatus;
  relationships: ("new" | "service" | "repeat")[];
}
export interface LeadScore {
  close_probability: number;
  explanations?: { feature: string; score: number; direction: "positive" | "negative" }[];
  explainer_used?: string;
}

/* ── Inventory ─────────────────────────────────────────────────────────────────────────────────────────────── */
export interface StockHealth {
  status: "ok" | "no_inventory";
  kpis?: {
    units: number;
    in_transit: number;
    on_order: number;
    net_days_supply: number;
    healthy_low: number;
    healthy_high: number;
    cost_value: number;
    carry_per_month: number;
    floorplan_per_month: number;
    aged_days: number;
    aged_units: number;
    aged_capital: number;
    aged_burn_per_month: number;
  };
  coverage?: { on_hand: number; with_pipeline: number; demand: { days: number; units: number }[] } | null;
  aging?: { bucket: string; units: number; lines: number; capital_amt: number; holding_cost_amt: number }[];
  stock_vs_demand?: {
    points: {
      brand: string;
      model: string;
      dealer_name: string;
      days_of_supply: number;
      demand_forecast_30d: number;
      current_stock: number;
      inventory_value_amt: number;
      position: "healthy" | "below_reorder" | "overstocked";
    }[];
    stocked_out: { brand: string; model: string; dealer_name: string; demand_forecast_30d: number }[];
    healthy_low: number;
    healthy_high: number;
  };
  reorder?: {
    dealer: string;
    vehicle: string;
    region: string | null;
    on_hand: number;
    inbound: number;
    reorder_point: number;
    net_short: number;
    lead_time_days: number;
    gp_at_risk: number;
    coverage: { kind: "inbound" | "dealer_trade" | "factory_order"; units: number | null; store: string | null };
    urgency: number;
  }[];
  aged?: {
    dealer: string;
    vehicle: string;
    region: string | null;
    units: number;
    days_on_lot: number;
    days_of_supply: number;
    capital: number;
    monthly_burn: number;
    action: { kind: "wholesale" | "dealer_trade" | "hold" | "markdown"; store: string | null };
  }[];
  thresholds?: number[];
}

/* ── Market sentiment ──────────────────────────────────────────────────────────────────────────────────────── */
export interface Article {
  title: string | null;
  url: string | null;
  domain: string | null;
  published_date: string | null;
  theme: string | null;
  demand_direction: "up" | "down" | "neutral" | null;
  demand_change_pct: number | null;
  impact_score: number | null;
  affected_category: string | null;
  signal_summary: string | null;
}
export interface SentimentOverview {
  stats: {
    net_demand_signal_pct: number;
    total_articles: number;
    segment_changes?: Record<string, number>;
    mode?: string;
  };
  articles: Article[];
  monthly_runrate: number;
  timespans: Record<string, string>;
}
export interface PipelineStatus {
  fetch?: { fetched_from_gdelt?: number; inserted?: number; source?: string };
  analyze?: { articles_found?: number };
  summarize?: { rows_computed?: number };
  errors?: string[];
  mode?: string;
}
export interface ForecastCheck {
  status: "ok" | "baseline_failed";
  message?: string;
  rows?: { x: string; actual: number | null; standard: number; news_aware: number | null }[];
  forecast_starts?: string | null;
}
