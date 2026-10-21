# dryday-ics

Scrapes [dryday.in](https://dryday.in) once a day and publishes the upcoming dry days for Maharashtra as an iCalendar feed you can subscribe to from Google Calendar.

dryday.in has no API. It's a static site that only publishes a rolling four-week window, so this scrapes the today / tomorrow / ahead sections, keeps a JSON history in `data/` so past dry days don't disappear, and writes `docs/<region>.ics`, which GitHub Pages serves.

## Subscribe

Google Calendar → Other calendars → **+** → From URL:

```
https://dryday.iamdobhal.dev/maharashtra.ics
```

Google refreshes subscribed calendars every 12–24 hours. The feed is rebuilt daily at 10:00 IST.

## Run locally

```
python3 scrape.py maharashtra
```

Add regions in `REGIONS` in `scrape.py` and list them in the workflow.

## Landing page

GitHub Pages serves `docs/`, including the landing page and calendar. The preview reads the same `.ics` file subscribers receive; no separate event dataset is needed.

Edit `docs/index.html` and `docs/styles.css` for layout, and `src/app.ts` for interactions. Compile the TypeScript with:

```sh
npx --package typescript@5.9.3 tsc -p tsconfig.json
```

Commit the generated `docs/app.js` along with the source so GitHub Pages needs no build step. Preview locally with `python3 -m http.server 8047 --directory docs`.
