---
id: pricing-totals
kind: concept
status: canonical
sources:
  - src-code
  - doc-pricing-policy
prerequisites: []
updated_at: 2026-08-05
---

# Pricing totals

[observed] At most one discount applies per order: the highest-priority rule whose minimum subtotal is met. Discounts never stack (src/orderflow/pricing.py, `_select_discount`).
[observed] Tax is charged on the discounted goods subtotal — discount first, then tax. Shipping is never taxed (src/orderflow/pricing.py).
[agreed] Free-shipping eligibility is decided on the goods subtotal BEFORE any discount; applying a discount can never cost an order its free shipping (src/orderflow/pricing.py; confirmed with commerce team 2026-08-05).
[agreed] Discount and shipping rules implement the commercial policy in `doc-pricing-policy`; that document is the tie-breaker when code and expectation disagree.
