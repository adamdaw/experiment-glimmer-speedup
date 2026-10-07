# Time zone support (specification)

Today every schedule is interpreted in UTC. Users need wall-clock schedules in their own
IANA time zone. Requirements:

1. **Spec syntax.** Any daily/weekly/interval spec may end with ` tz=ZONE`, e.g.
   `daily 09:30 tz=Europe/Oslo` or `weekly sun 02:30 tz=America/New_York`.
   ZONE is an IANA zone name and is case-sensitive (`Europe/Oslo`, not `europe/oslo`).
   Without `tz=` the zone is `UTC`. An unknown zone raises `ValueError` whose message
   contains the zone name. At most one `tz=` is allowed and it must come last.
2. **Model.** `Schedule` gets a `tz: str = "UTC"` field, set by `parse()`.
3. **next_run(schedule, after)**
   - `after` must be timezone-aware; a naive datetime raises `ValueError`.
   - The result is timezone-aware with `tzinfo == datetime.timezone.utc` and strictly
     after `after`.
   - For daily/weekly schedules, `at` is the wall-clock time in the schedule's zone and
     `weekday` is the weekday in that zone.
   - DST gap: if the wall-clock time does not exist on a day (clocks jump forward), the
     job runs at that time shifted forward by the length of the gap (02:30 on a New York
     spring-forward day runs at 03:30 EDT, i.e. 07:30 UTC).
   - DST overlap: if the wall-clock time occurs twice (clocks fall back), the job runs
     once that day, at the first occurrence.
   - Interval schedules ignore the zone: runs are at whole multiples of the interval
     since 1970-01-01T00:00:00Z.
4. **Storage.** Job files written by older versions (no zone information) must still
   load, as UTC jobs. The zone must survive a save/load round trip.
5. **CLI.**
   - `add` accepts `--tz ZONE` as an alternative to writing `tz=ZONE` in the spec.
     Using both at once is an error.
   - `next --now` must carry a UTC offset; a naive `--now` is an error.
   - Output format is unchanged (ISO 8601 in UTC). Errors keep the existing
     convention: `error: <message>` on stderr and exit code 2.
