# dryday-ics

Fetches the full annual [Mumbai calendar from isitadryday.in](https://isitadryday.in/city/mumbai-dry-days) daily and publishes it as an iCalendar subscription.

The scraper reads structured page data, validates the city, year, dates and reasons, and preserves the previous feed if the source is missing or malformed. It replaces the source year's dates so corrections and removals are reflected, while retaining older years in `data/`.

The feed is titled **Dry Days - Mumbai**. Its existing `/maharashtra.ics` URL stays unchanged for subscription compatibility. Dates reflect the source site's listings; local orders can change at short notice.

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

The source is intentionally validated as Mumbai; changing locations requires updating that validation.

## Landing page

GitHub Pages serves `docs/`, including the landing page and calendar. The preview reads the same `.ics` file subscribers receive; no separate event dataset is needed.

Edit `docs/index.html` and `docs/styles.css` for layout, and `src/app.ts` for interactions. Compile the TypeScript with:

```sh
npx --package typescript@5.9.3 tsc -p tsconfig.json
```

Commit the generated `docs/app.js` along with the source so GitHub Pages needs no build step. Preview locally with `python3 -m http.server 8047 --directory docs`.

The publish workflow runs after both direct site changes and successful daily feed updates, so bot-authored calendar commits are deployed too.
