/** Mirrors backend/services/accounts.py — the server is the source of truth and validates every value anyway. */
export const CURRENCY_SYMBOLS: Record<string, string> = {
  USD: "$", EUR: "€", GBP: "£", INR: "₹", AED: "AED", SAR: "SAR", CHF: "CHF", CAD: "$", AUD: "$", JPY: "¥", CNY: "¥",
};

export const REGION_LABELS = ["Region", "State", "Province", "Emirate", "Bundesland", "County"] as const;

export const LANGUAGES = { en: "English", de: "Deutsch" } as const;
