# Anonymized input fixtures

These are deliberately small, entirely fabricated source files for repeatable
adapter and model tests. The names, IDs, organization, activity, times, and
events do not represent an enterprise or person.

The workforce-cycle fixture contains:

- three current agents and one recycled operational identity with nonoverlapping
  effective dates, resolved separately for schedule, login, event, and HR
  system keys;
- four paid schedule segments, including one planned break;
- three login sessions with controlled late/early boundaries;
- six mapped agent-state events and one separate unknown-identity event;
- four 30-minute staffing requirements, including one deliberately uncovered
  interval;
- an existing closed snapshot containing one prior day and one deliberately
  stale current-day row for close-day replacement testing.

The planning-to-supply fixtures add fabricated daily candidates, effective
`ALL` and weekday interval profiles, approved/draft scenarios, interval
capacity, weekly supply movements, and two nonoverlapping hiring policies. They
contain no enterprise data.

The v0.6 named-roster fixtures add two pseudonymous active agents, fabricated
skills, eligibility, contracts, availability, preferences, leave requests,
an external entitlement snapshot, and one consented bilateral swap. No real
identity, diagnosis, protected attribute, or entitlement balance is present.
