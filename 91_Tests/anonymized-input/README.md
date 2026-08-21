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
