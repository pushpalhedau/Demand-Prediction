# Next pass — Customer Intelligence: equity-mining / upgrade opportunities

The Customer Intelligence dealer-positioning pass landed on 2026-08-29
(`docs/changelog/2026-08-29-customer-intelligence-dealer-positioning.md`). One item was
deliberately scoped out.

## Equity-mining — "who can we pull forward into a new deal"

The 2026-08-29 pass shipped a **recency-only** "likely back in market" indicator (lease
returns at ~36 months; financed/cash buyers past the ~7.6-year trade cycle). The real
dealer tool is **equity-mining**: for each customer with an open loan or lease, estimate
what they still owe vs what the car is worth today, and surface the ones in a positive-
equity position who could trade into a new vehicle at a similar or lower payment.

**What to build (a dedicated pass):**

- Per open contract: estimated current payoff, estimated current vehicle value, **equity
  position** ($ and %), months remaining, and the payment on a like-for-like replacement.
- A worklist sorted by "pull-ahead value": positive equity + near enough to maturity +
  a replacement in stock (tie into Inventory Intelligence).
- Lease side: this is the **customer/sales** view of the same contracts Inventory
  Intelligence sees from the **supply** side (`get_lease_return_pipeline` /
  `get_lease_maturity_recapture`). The two must reconcile — same contracts, same months,
  no double-count — not be two independent estimates.

**Data caveats to fix first:**

- `Sale.loan_amount_usd` is **origination only** — there is no amortization schedule and
  no `current_payoff`. The generator needs to model a paydown curve (term, APR, start
  date → balance today) or store a `current_balance_usd` snapshot.
- There is no current used-vehicle value. `Vehicle.residual_value_36mo` gives a lease-
  maturity residual; a general "what's this 3-year-old car worth now" needs a depreciation
  curve by age/segment/brand (the residual column is a starting point).
- Leases already carry `residual_value_usd` (contractual buyout) and `lease_maturity_date`
  — the lease half of equity-mining is close to feasible today; the loan half is not.

## Retention vs. the forecast — the "no competitor can do this" view

The 2026-08-29 rework ships the repeat share of *past* sales (~37%) as a headline. The
differentiated follow-up is to connect Customer Intelligence to **Demand Forecasting**:

- Of the ~N units Prophet expects next quarter, what share should come from the existing
  base vs conquest, and which specific customers are that pipeline (lease returns +
  overdue repeat buyers + high-propensity names).
- A gap read: "you have {queue} in-market customers but the forecast implies {repeat_units}
  repeat sales — pipeline is ahead / short by X."
- A scenario slider: "if same-store repeat rate slips 5 points, next quarter loses ~Y
  units / ~$Z gross."

Scoped out of the 2026-08-29 pass to avoid a second Prophet dependency on the tab (it
already retrains twice on the Forecasting page). Needs either a cached forecast or a
lightweight repeat-propensity model.

## The action queue's 4th reason — positive equity

Once the equity-mining data lands (above), add a **"positive equity"** reason to
`_build_action_queue` in `dashboard/customers.py`: customers whose estimated payoff is
below the car's current value and who could trade into a new deal at a similar payment.
Slot it just below "Lease maturing" in `_REASON_PRIORITY`.

**Also still open on this tab (from the changelog §8):**

- `age` retained as a model/segmentation input — revisit if the score ever gates
  anything credit-adjacent.
- Customer credit distribution (`normal(690, 75)`) runs richer in subprime than booked
  new-vehicle loans; acceptable for a prospect-inclusive CRM.
- `train_models.py` still only covers test mode — real-mode retrain is manual.
- `predict_customer_segment` is unwired (no "classify this walk-in" control).
- `dashboard/inventory.py` lease-recapture `loyalty_score >= 0.6` test is effectively
  always-true (0–100 scale vs 0–1 threshold) — pre-existing, not touched.
