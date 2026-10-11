# Settings and testing

Settings go in the `.env` file, or under GitHub secrets and variables if you use GitHub Actions.

| Name | Default | Meaning |
|---|---|---|
| `BOOKING_NUMBER` | | Your booking number |
| `BOOKING_URL` | | Optional: the full *Book appointment* link, instead of the number |
| `AUTO_BOOK` | `true` | `false` means only email you when something is free, never book |
| `MIN_HOURS_AHEAD` | `12` | Never book a slot that starts sooner than this many hours |
| `NOTIFY_TO` | `GMAIL_ADDRESS` | Where notifications go |
| `IMAP_HOST` / `SMTP_HOST` | Gmail | Mail servers for non-Gmail providers ([details](email.md)) |

## Emails you can get

| Email | When |
|---|---|
| ✅ Police appointment BOOKED | It booked a slot. The schedule then switches itself off. |
| ⚠️ AVAILABLE, auto-booking failed, book manually NOW | A slot is free but something went wrong. Screenshots are attached, and you still have a chance to book it yourself. |
| ⏰ Free but SOON, not auto-booked | The only free slots start within `MIN_HOURS_AHEAD` hours. Sent once per set of slots. |
| Checker is failing | It couldn't check for about an hour (wrong password, the site changed, …). Sent at most once a day. |

## Command-line flags for testing

| Flag | What it does |
|---|---|
| `--probe` | Enters the emailed code, then stops |
| `--dry-run` | Selects a free slot but doesn't book it |
| `--simulate-available`, `--simulate-booked` | Only sends those emails |
| `--debug` | Shows the browser window |

Screenshots of the last 50 runs are saved in the `artifacts/` folder. They contain your personal data, so keep
them private.

