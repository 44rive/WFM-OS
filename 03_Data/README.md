# 03 · Data landing zones

The numbered folders are stable Power Query landing zones. Their contents are
ignored by Git; only their instructions are version-controlled.

```text
01_People/           workforce master and effective-dated organization
02_Contacts/         voice, chat, and other synchronous interactions
03_Work_Items/       email, cases, dispatch, tickets, and backlog
04_Agent_Events/     availability, handling, ACW, aux, and offline events
05_Login_Sessions/   login/logout or presence sessions
06_Schedules/        planned shifts, breaks, activities, and skills
07_Absence_Leave/    absence, leave, holiday, and exception inputs
08_Quality/          quality and customer-outcome results
09_Forecasts/        external/client/global forecast inputs
90_Quarantine/       rejected files or rows requiring resolution
99_Snapshots/        approved dated operational snapshots
```

Never force-add operational files to Git.
