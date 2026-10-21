"use strict";
const feedUrl = 'https://dryday.iamdobhal.dev/maharashtra.ics';
const input = document.querySelector('#feed-url');
const copyButton = document.querySelector('#copy-button');
const copyStatus = document.querySelector('#copy-status');
copyButton.hidden = false;
copyButton.addEventListener('click', async () => {
    try {
        await navigator.clipboard.writeText(feedUrl);
        copyStatus.textContent = 'Copied. Paste it into your calendar’s subscription settings.';
    }
    catch {
        input.focus();
        input.select();
        copyStatus.textContent = 'Select and copy the link above to use it in your calendar.';
    }
});
function unescapeIcs(value) {
    return value.replace(/\\([nN,;\\])/g, (_, char) => char.toLowerCase() === 'n' ? '\n' : char);
}
function parseFeed(text) {
    if (!text.includes('BEGIN:VCALENDAR') || !text.includes('END:VCALENDAR'))
        throw new Error('Invalid calendar');
    const unfolded = text.replace(/\r?\n[ \t]/g, '');
    return [...unfolded.matchAll(/BEGIN:VEVENT\r?\n([\s\S]*?)END:VEVENT/g)].map((match) => {
        const values = new Map();
        for (const line of match[1].split(/\r?\n/)) {
            const colon = line.indexOf(':');
            if (colon === -1)
                continue;
            values.set(line.slice(0, colon).split(';')[0], unescapeIcs(line.slice(colon + 1)));
        }
        const rawDate = values.get('DTSTART') ?? '';
        if (!/^\d{8}$/.test(rawDate))
            throw new Error('Unsupported event date');
        return {
            date: `${rawDate.slice(0, 4)}-${rawDate.slice(4, 6)}-${rawDate.slice(6, 8)}`,
            title: (values.get('SUMMARY') ?? 'Dry day').replace(/^Dry day:\s*/i, ''),
            description: (values.get('DESCRIPTION') ?? '').split('\n').filter(line => !line.startsWith('Source:')).join(' '),
        };
    });
}
async function loadFeed() {
    const state = document.querySelector('#feed-state');
    const heading = state.querySelector('h3');
    const detail = state.querySelector('p');
    const list = document.querySelector('#event-list');
    try {
        const response = await fetch('maharashtra.ics', { signal: AbortSignal.timeout(12000) });
        if (!response.ok)
            throw new Error(`HTTP ${response.status}`);
        const today = new Intl.DateTimeFormat('en-CA', { timeZone: 'Asia/Kolkata', year: 'numeric', month: '2-digit', day: '2-digit' }).format(new Date());
        const events = parseFeed(await response.text()).filter(event => event.date >= today).sort((a, b) => a.date.localeCompare(b.date));
        if (events.length === 0) {
            heading.textContent = 'No upcoming dates in the feed.';
            detail.textContent = 'Subscribe now. New dates will appear here and in your calendar when they’re published.';
            return;
        }
        for (const event of events) {
            const row = document.createElement('li');
            row.className = 'event-row';
            const date = document.createElement('time');
            date.className = 'event-date';
            date.dateTime = event.date;
            const parsed = new Date(`${event.date}T12:00:00+05:30`);
            date.textContent = new Intl.DateTimeFormat('en', { day: '2-digit', timeZone: 'Asia/Kolkata' }).format(parsed);
            const month = document.createElement('small');
            month.textContent = new Intl.DateTimeFormat('en', { month: 'short', year: 'numeric', timeZone: 'Asia/Kolkata' }).format(parsed);
            date.append(month);
            const text = document.createElement('div');
            const title = document.createElement('h3');
            title.textContent = event.title;
            text.append(title);
            if (event.description) {
                const description = document.createElement('p');
                description.textContent = event.description;
                text.append(description);
            }
            row.append(date, text);
            list.append(row);
        }
        state.hidden = true;
        list.hidden = false;
    }
    catch {
        heading.textContent = 'The preview couldn’t load.';
        detail.textContent = 'Try again in a moment, or use the calendar feed link below.';
    }
}
void loadFeed();
