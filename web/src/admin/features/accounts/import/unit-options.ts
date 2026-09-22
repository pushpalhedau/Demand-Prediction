import type { ImportSchema, Transform } from "@/admin/lib/types";

export interface UnitOption {
  label: string;
  transform: Transform;
}

/** Mirrors frontend/admin_console/views/import_wizard.py's _UNIT_OPTIONS; the numbers come from the backend catalog. */
export function buildUnitOptions(constants: ImportSchema["constants"]): UnitOption[] {
  return [
    { label: "None", transform: null },
    { label: "× 12  (monthly to annual)", transform: { op: "mul", k: 12 } },
    { label: "× 0.7457  (horsepower to kW)", transform: { op: "mul", k: constants.hp_to_kw } },
    { label: "× 0.7355  (PS to kW)", transform: { op: "mul", k: constants.ps_to_kw } },
    { label: "100 / x  (km per litre to l/100km)", transform: { op: "inv", k: 100 } },
    { label: "235.2 / x  (mpg to l/100km)", transform: { op: "inv", k: constants.l100_from_mpg } },
    { label: "× 1.609  (miles to km)", transform: { op: "mul", k: constants.mi_to_km } },
    { label: "× 0.0929  (sq ft to sq m)", transform: { op: "mul", k: constants.sqft_to_sqm } },
    { label: "× 0.264  (per gallon to per litre)", transform: { op: "mul", k: 1 / constants.gal_to_l } },
  ];
}

export function unitLabel(options: UnitOption[], transform: Transform): string {
  if (!transform) return "None";
  const hit = options.find(
    (o) =>
      o.transform &&
      o.transform.op === transform.op &&
      Math.abs(o.transform.k - transform.k) <= 1e-6 * Math.max(1, Math.abs(o.transform.k)),
  );
  return hit ? hit.label : "None";
}
