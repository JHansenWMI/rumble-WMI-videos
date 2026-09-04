# Rumble feed publishers — Mini vs laptop

Copied from the Mini Desktop (`rumble-feed-publisher-notes.md`, 2026-08-23) so both machines have the same recovery story.

**Status 2026-09-04:** Mini publishes from a sibling worktree at `origin/main` (`…/rumble-WMI-videos-publish`). Desktop WIP (itinerary, etc.) is left untouched. A rejected push retries once inside that worktree (`reset --hard origin/main`, scrape again). Laptop still `--ff-only` with no reset, and still requires a clean working tree.

**Status 2026-08-26:** Section 4 (feed-JSON-only `reset --hard` on the Mini *checkout*) is superseded on Mini by the worktree. Laptop still never resets. Sections 7–8 are historical.

Original notes follow.

---

# Rumble feed publishers — what happened, what to do

Written 2026-08-23 for reading in BBEdit (RustDesk scroll is painful).
Repo: ~/Desktop/rumbleScraper/rumble-WMI-videos
Nothing in git was reset or pushed while looking at this.

------------------------------------------------------------
1. What happened (Saturday 13:00 PDT)
------------------------------------------------------------

Two machines scraped at the same second, from the same parent commit
(ab7844f, Mini’s noon run).

  Laptop → origin/main   3c9fdc6   13:00:53   author: Fred for Jonathan
  Mini   → local HEAD    cf3fb3c   13:01:09   author: JHansenWMI

Same commit message: "Update Rumble feed JSON files"
Same parent. The only difference is JSON clocks (~16 seconds).
Chapel title is in both files. Same URLs.

Mini launchd log:

  13:00:00  pull --ff-only  → already up to date (laptop had not pushed yet)
  13:00:02  scrape rumble / overcoming / tv
  13:01:09  commit cf3fb3c
  13:01:09  git push REJECTED  (laptop had just published 3c9fdc6)
  14:00 on  every Mini run dies at  git pull --ff-only
            “diverging branches can’t be fast-forwarded”

GitHub Pages is frozen at laptop Saturday 13:00.
Mini has been a dead publisher since then (still failing Sun 22:00).

Saturday 13:00 is an intentional Mini slot (plist Weekday 6, chapel).
Laptop chapel handoff also ran publish_rumble_feed.sh at 13:00.
That overlap is the whole incident.

------------------------------------------------------------
2. Goals (your words)
------------------------------------------------------------

- Keep more than one publisher (Mini + laptop / other Macs).
- Mini must not stay blocked.
- Scripts should self-recover. If you are not here, it still works.
- Likely failure is feed JSON, not parser/code.
- Only Mini needs unattended recovery.
- Other publishers can have extra steps; a dev can chat with Grok to clean up.

------------------------------------------------------------
3. Recommendation (short)
------------------------------------------------------------

Keep everyone publishing to main.

Do NOT have Mini merge other people’s branches.
Unattended JSON merge is this same failure, plus conflict markers.

Mini: auto-recover JSON-only races (reset to origin, scrape again).
Laptop: attended. If it cannot fast-forward, stop (or park on a branch)
and fix with Grok. Mini never consumes that branch.

------------------------------------------------------------
4. Mini unattended recovery (the actual fix)
------------------------------------------------------------

File: publish_rumble_feed.sh
Only when RUMBLE_FEED_MODE is unset / production (this Mini).

Keep: git pull --ff-only

When pull fails, or push is rejected:

  1. Unique commits vs origin/main are ALL
     “Update Rumble feed JSON files”
  2. They only touch feed JSON
     (rumble / overcoming / tv feeds + archives)
  3. If anything else is in those commits (parser, thumbs,
     itinerary, schedules) → abort and log. Human needed.
  4. git reset --hard origin/main
  5. Continue THIS run: scrape → maybe commit → push
  6. One recovery, one push retry. No loop.

Why reset + regenerate, not rebase:
  Two “update JSON” commits rebase into conflicts.
  After reset, Mini scrapes on top of whatever already won on GitHub.
  feed_has_meaningful_change already ignores clock-only noise.

What Saturday would have become:
  Take laptop’s main → scrape again → chapel already there →
  nothing worth committing → exit 0. Mini unblocked.

If Mini sees a video laptop missed:
  Reset, re-scrape, commit the new item, push.

Do not auto-reset in development mode (laptop must not wipe WIP).

------------------------------------------------------------
5. Laptop / other publishers
------------------------------------------------------------

Leave --ff-only. Do not auto-reset.

If they collide with Mini:

  1. Stop. Log: diverged, will not reset.
  2. Optional: push HEAD to feed/laptop-YYYYMMDD-HHMM
     so the scrape is not lost.
  3. You or Grok: rebase/reset onto main and push,
     OR just wait — Mini’s next slot will scrape anyway.

A branch is a parking lot, not a Mini merge source.
You still have more than one publisher. The extra one is not
allowed to leave Mini wedged.

------------------------------------------------------------
6. Out of scope for the first change
------------------------------------------------------------

update_tv_schedule.sh and update_radio_schedule.sh also use
pull --ff-only. Friday 4:00 / 4:10 / 4:20 avoids Mini vs Mini.
Mini vs laptop can still wedge those. Same idea later if you want it.

------------------------------------------------------------
7. This checkout, until the script changes
------------------------------------------------------------

Launchd will keep dying at pull.

After recovery is in the script, the NEXT Mini run should unstick
itself (reset to 3c9fdc6, scrape, continue). No hand-reset needed
unless you want the site updated before the next slot.

Do not force-push Mini over origin. Origin already won; Pages is
serving it. Mini’s leftover commit is not unique content.

------------------------------------------------------------
8. Implement next (when you say so)
------------------------------------------------------------

Only publish_rumble_feed.sh
  production-only
  JSON-commit-only
  one retry
  no Mini-side branch merges
