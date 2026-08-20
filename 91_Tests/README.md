# Tests

Tests use anonymized source fixtures and expected outputs.

The workbook test harness will cover:

- required source fields and compatible types;
- unique dimension keys;
- unknown agent, queue, activity, and state mappings;
- live/closed date overlap;
- duplicate fact keys;
- source-to-fact offered and handled reconciliation;
- DAX service-level, abandon-rate, AHT, occupancy, and adherence cases;
- forecast aggregation and capacity conservation;
- repeat-refresh idempotence.

The current automated fixture covers the first contact-service slice: daily
offered/handled counts, short-abandon treatment, service level, AHT, unique
contact IDs, and visible quarantine of an unknown queue. Desktop Excel remains
the release authority for Power Query, Power Pivot, and visual validation.
