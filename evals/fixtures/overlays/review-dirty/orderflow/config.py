"""Tunables for the order pipeline. All money amounts are integer cents."""

# Inventory reservations are held this long before they lapse.
RESERVATION_TTL_SECONDS = 120

# Dispatch gives up after this many total attempts and dead-letters the order.
MAX_DISPATCH_ATTEMPTS = 2

# Base delay before the second dispatch attempt; doubles each further attempt.
BASE_RETRY_DELAY_MS = 50

# A carrier send that does not answer within this window counts as a timeout.
CARRIER_SEND_TIMEOUT_SECONDS = 2.0

# Sales tax applied to the discounted goods subtotal (never to shipping).
TAX_RATE = 0.05

# Orders whose goods subtotal, before any discount, reaches this ship free.
FREE_SHIPPING_THRESHOLD_CENTS = 8000_00

# Flat shipping fee for everything below the threshold.
FLAT_SHIPPING_CENTS = 120_00

# Parcels heavier than this (grams) go by freight instead of post.
POST_MAX_WEIGHT_G = 2000
