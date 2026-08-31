# Next pass — Store Performance: customer-catchment view

The "Regional Intelligence → Store Performance" repositioning landed on 2026-08-29
(`docs/changelog/2026-08-29-store-performance-dealer-positioning.md`). One item was
deliberately deferred out of that pass:

## Customer catchment — "where each store's buyers come from vs where it sits"

**Now feasible.** The 2026-08-29 reseed made `Customer.state` meaningful per store:
each sale is routed to a store that franchises the brand (preferring the shopper's
state), and the customer attached to it is now ~82% in-state (realised 84%), instead of
a fully random draw. So a store's booked deals genuinely reflect a local catchment with
a modest travel tail.

**What to build (a dedicated pass):**

- Per rooftop: the split of its buyers by home state / home city vs the store's own
  location — a small-multiples map or a set of stacked bars.
- "Conquest / leakage": deals a store books from outside its metro, and (harder — needs
  the inverse) buyers in a metro who bought from a *different* group store or left the
  group entirely.
- Frame it as a **network-expansion** question ("where is there unserved demand we could
  put a rooftop on?"), not a store-performance one — that's why it didn't belong in the
  performance pass.

**Data caveats to fix first:**

- Home city is drawn uniformly within the home state; there's no intra-metro geography
  and no real travel-distance model. A catchment view at city grain would need the
  generator to place customers on a coordinate and route on distance.
- Cross-border leakage is a flat 18% with no distance decay — a New York buyer is as
  likely to appear at a California store as at a New Jersey-adjacent one. Fine for
  "mostly local", not fine for a leakage analysis.

**Also still open on this tab (from the changelog §8):**

- Est. gross is a benchmark estimate — no per-deal `gross_profit_usd` column.
- `Dealer.tier` / `performance_score` still populated (random) and read by
  `get_dealer_directory`; drop from the schema in a cross-module sweep.
- Lead Conversion (XGBoost) model retrain is optional cleanup after the reseed.
