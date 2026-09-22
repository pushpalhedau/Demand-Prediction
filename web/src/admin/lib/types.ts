export interface AccountConfig {
  currency?: string;
  currency_symbol?: string;
  symbol_position?: "prefix" | "suffix";
  language?: "en" | "de";
  region_label?: string;
  country_name?: string;
  news_gl?: string;
  news_hl?: string;
}

export interface Account {
  id: string;
  slug: string;
  name: string;
  status: "active" | "suspended";
  config: AccountConfig;
  created_at: string;
}

export interface AccountSummary {
  sales: number;
  dealers: number;
  customers: number;
  inventory: number;
  first_sale: string | null;
  last_sale: string | null;
  models: boolean;
}

export interface AccountDetail extends Account {
  summary: AccountSummary;
}

export interface CreatedCredentials {
  tenant_id: string;
  slug: string;
  email: string;
  password: string;
}

export interface Login {
  id: string;
  email: string;
  role: "tenant_admin" | "tenant_user" | "";
  last_sign_in: string;
  created: string;
}

export interface CreatedLogin {
  tenant_id: string;
  email: string;
  password: string;
  role: string;
}

export interface Job {
  id: string;
  status: "queued" | "running" | "succeeded" | "failed";
  stage: string | null;
  progress: number;
  message: string | null;
  created_by: string | null;
  created_at: string;
  finished_at: string | null;
  kind: "retrain" | "import";
  loaded: Record<string, number>;
  notes: string[];
}

/** The shape of a single job status lookup — unlike the jobs list, its report is nested, not flattened. */
export interface JobStatus {
  id: string;
  status: "queued" | "running" | "succeeded" | "failed";
  stage: string | null;
  progress: number;
  message: string | null;
  report: { loaded?: Record<string, number>; notes?: string[] } | null;
}

export type TableName = "vehicles" | "dealers" | "customers" | "external_factors" | "sales" | "inventory";

export interface FieldDef {
  name: string;
  required: boolean;
  derived: boolean;
}

export interface ImportSchema {
  load_order: TableName[];
  required_tables: TableName[];
  tables: Record<TableName, FieldDef[]>;
  constants: {
    mi_to_km: number;
    sqft_to_sqm: number;
    hp_to_kw: number;
    ps_to_kw: number;
    gal_to_l: number;
    l100_from_mpg: number;
  };
}

export type Transform = { op: "mul" | "inv"; k: number } | null;

export interface MappingChoice {
  source: string;
  transform: Transform;
  confidence: "exact" | "converted" | "alias" | "fuzzy";
}

export interface MappingProposal {
  columns: string[];
  proposal: Record<string, MappingChoice>;
  missing_required: string[];
  imperial_hint: boolean;
  saved: Record<string, { source: string; transform: Transform }> | null;
}

export interface TableMapping {
  columns: Record<string, { source: string; transform: Transform }>;
  extras: true;
}

export interface DryRunReport {
  table: string;
  rows_in: number;
  rows_out: number;
  coercion_failures: Record<string, number>;
  warnings: string[];
}

export interface AuditEvent {
  at: string;
  actor: string;
  action: string;
  account: string;
  outcome: string;
  detail: Record<string, unknown>;
}
