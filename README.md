# UDI police appointment bot (Norway)

**Can't get an appointment with the police (Politiet) for your UDI application?** This script checks the police
booking calendar (`politietbooking.nemo-q.se`) every 10 minutes for you. When a slot opens it books it, and it
emails you either way.

> I checked by hand every few days for **5 months** and never saw a single free slot.
> I ran this script, and **a few hours later, at 01:30 on a Sunday night, it had booked me an appointment for
> the following week.** Slots do open, but they are taken within minutes, usually at times when no human is
> looking.

Works for any UDI application where you book the police appointment through **My Applications (Mine søknader) →
Book appointment**: EU/EEA registration, residence permits, family immigration, permanent residence, citizenship,
etc. Tested with an EU/EEA registration at Oslo police district's Service Centre for Foreign Workers (SUA).

*Unofficial. Not affiliated with UDI or the Norwegian Police. Use at your own risk. See [Fair use](#fair-use).*

---

## What it does

Every 10 minutes it:

1. opens your **Book appointment** link (the same one as on UDI's receipt page);
2. reads the police's verification code (*"Your code: XXXXXX"*) from your Gmail and enters it;
3. clicks **Show appointments** and **Show first available appointment**;
4. if a slot is free, books the **earliest slot at least 12 hours away** (so you aren't booked for 08:00 while
   you sleep). Your name and contact details are already filled in from your application, and it confirms the
   booking;
5. moves the code email to Trash, so your inbox doesn't fill up.

You get an email when:

| Email | When |
|---|---|
| ✅ Police appointment BOOKED | It booked a slot. The schedule then turns itself off. |
| ⚠️ AVAILABLE, auto-booking failed, book manually NOW | A slot is free but something went wrong. Screenshots are attached, and you still have a chance to book it yourself. |
| ⏰ Free but SOON, not auto-booked | The only free slots start within 12 hours (sent once per set of slots). |
| Checker is failing | It couldn't check for about an hour (wrong password, the site changed, …). Sent at most once a day. |

The full booking flow was confirmed on the real site with a real booking:
*Select office, date and time → Personal data (prefilled) → Contact information (prefilled) → Summary →
"Confirm booking" → Booking Confirmation.*

## What you need

- A UDI application that is waiting for a police appointment, and its **booking number**. You'll find it on the
  application's receipt page on udi.no, or in the email *"Book an appointment with the Police - Immigration
  Authorities"*.
- The **Gmail** account that receives UDI's and the police's emails, plus a Gmail **App Password**:
  1. Turn on 2-Step Verification for the account.
  2. Open <https://myaccount.google.com/apppasswords>. **Check the avatar at the top right: it must be the
     right account.** (If you have several Google accounts, this is the most common mistake.)
  3. Create a password with any name and copy the 16 letters without spaces.

  Other mail providers may work through `IMAP_HOST`/`SMTP_HOST`, but only Gmail has been tested.
- Somewhere to run it every 10 minutes. Pick one of these options:

| Option | Cost | Runs when your computer is off? |
|---|---|---|
| [A. GitHub Actions](#a-github-actions-no-computer-needed) | free | ✅ yes, on GitHub's servers |
| [B. Always-on Linux machine](#b-always-on-linux-home-server-raspberry-pi-vps) (home server, Raspberry Pi, €4/month VPS) | 0–4 €/month | ✅ yes |
| [C. Your Mac/Linux computer](#c-your-own-maclinux-computer-cron) | free | ❌ only while it's on and awake |
| [D. Your Windows computer](#d-windows-task-scheduler) | free | ❌ only while it's on and awake |

Slots appear at random times, often at night, so options A and B catch far more of them.

---

## A. GitHub Actions (no computer needed)

GitHub runs the checker for you on its servers. You need a free GitHub account.

1. At the top of this page, click **Use this template → Create a new repository**.
   - **Public** repository: free, no limit on minutes. Your secrets stay hidden, GitHub masks them in logs,
     and the script never logs your personal data.
   - **Private** repository: also works, but the free plan includes 2,000 minutes a month, which is about one
     run every 30 minutes. Change `*/10` to `*/30` in `.github/workflows/checker.yml`.
2. In your new repository, go to **Settings → Secrets and variables → Actions**. Under **Secrets**, click
   **New repository secret** and add each of these:

   | Secret | Value |
   |---|---|
   | `UDI_EMAIL` | the email you log in to udi.no with |
   | `UDI_PASSWORD` | your udi.no password (only used if the direct link stops working) |
   | `GMAIL_ADDRESS` | the Gmail address that receives the police's emails |
   | `GMAIL_APP_PASSWORD` | the 16-letter App Password |
   | `BOOKING_NUMBER` | your booking number |
   | `NOTIFY_TO` | *(optional)* where to send notifications (defaults to `GMAIL_ADDRESS`) |

3. Test it. Go to **Actions → Appointment checker → Run workflow** and run these modes:
   - `test-email`: you should receive a test email.
   - `probe`: it opens your booking link, enters the emailed code, and stops. The log should end with
     `Probe: code accepted, now at step 'Select office, date and time'`.
4. Switch it on: under **Settings → Secrets and variables → Actions → Variables**, add `CHECKER_ENABLED` =
   `true`. Optional variables: `AUTO_BOOK` (`false` = only notify) and `MIN_HOURS_AHEAD` (default `12`).

After it books, the workflow disables itself. Notes:
- GitHub sometimes starts scheduled runs 10–30 minutes late when it's busy.
- GitHub pauses schedules in repositories that have had no activity for 60 days, and emails you when it does.

## B. Always-on Linux (home server, Raspberry Pi, VPS)

```sh
git clone https://github.com/<you>/<this-repo>.git && cd <this-repo>
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/python -m playwright install --with-deps chromium   # may ask for sudo to install browser libraries
cp .env.example .env && nano .env                              # fill it in

.venv/bin/python mail.py --test        # test email + inbox access
.venv/bin/python checker.py --probe    # enters the code, then stops
./install-systemd.sh                   # runs every 10 minutes from now on
loginctl enable-linger                 # keep it running when you log out / after a reboot
```

To see the logs, run `journalctl --user -u udi-checker -f`. The timer turns itself off after booking. To remove
it completely, run `./install-systemd.sh --remove`.

> If you upgrade your system's Python (e.g. 3.13 → 3.14), the `.venv` breaks. Delete it and rerun the first
> three commands.

## C. Your own Mac/Linux computer (cron)

Do the setup from option B up to and including `--probe`. Then run `crontab -e` and add:

```
*/10 * * * * cd /path/to/this-repo && .venv/bin/python checker.py >> checker.log 2>&1
```

It only runs while the computer is awake. After it books, every run exits immediately, but remove the line
yourself.

## D. Windows (Task Scheduler)

```bat
git clone https://github.com/<you>/<this-repo>.git
cd <this-repo>
py -m venv .venv
.venv\Scripts\pip install -r requirements.txt
.venv\Scripts\python -m playwright install chromium
copy .env.example .env   & REM then fill in .env with Notepad
.venv\Scripts\python mail.py --test
.venv\Scripts\python checker.py --probe
schtasks /Create /SC MINUTE /MO 10 /TN udi-checker /TR "cmd /c cd /d %CD% && .venv\Scripts\python.exe checker.py"
```

After it books, delete the task with `schtasks /Delete /TN udi-checker /F`. On a laptop, also turn off
"Start the task only if the computer is on AC power" in Task Scheduler.

---

## Settings (`.env` or GitHub secrets/variables)

| Name | Default | Meaning |
|---|---|---|
| `BOOKING_NUMBER` | | Your booking number |
| `BOOKING_URL` | | Optional: the full *Book appointment* link instead of the number |
| `AUTO_BOOK` | `true` | `false` = only email you when something is free |
| `MIN_HOURS_AHEAD` | `12` | Never auto-book a slot that starts sooner than this |
| `NOTIFY_TO` | `GMAIL_ADDRESS` | Where notifications go |

Command-line flags for testing: `--probe` (enter the code, then stop), `--dry-run` (select a free slot but don't
book it), `--simulate-available` and `--simulate-booked` (only send the emails), `--debug` (visible browser).
Screenshots of the last 50 runs are saved in `artifacts/`. They contain your personal data, so keep them private.

## Fair use

- It checks once every 10 minutes and books **one** appointment for **your own** application. That's the same
  as a person refreshing the page, just more persistently. Please don't make it check much more often.
- It never changes or cancels an existing appointment. Once you have a booking, the police site only offers
  change/cancel, and the script stops there.
- It never makes up personal data. If a required field is empty, it stops and emails you instead.
- The site can change at any time. If the script breaks, you'll get the "checker is failing" email. Issues and
  pull requests are welcome.

## Troubleshooting

- **`Invalid credentials` from Gmail:** the App Password was probably created on a different Google account.
  Check the avatar on the App Passwords page.
- **No code email arrives:** make sure `GMAIL_ADDRESS` is the mailbox that receives the police's emails (the
  one you registered with UDI).
- **"Direct booking link did not show the code form":** check `BOOKING_NUMBER`, or set `BOOKING_URL`. If you
  already have an appointment, this is expected.

---

## Norsk

**Får du ikke time hos politiet for søknaden din hos UDI?** Dette skriptet sjekker politiets timebestilling
(`politietbooking.nemo-q.se`) hvert 10. minutt. Når en ledig time dukker opp, bestiller det den første som er
minst 12 timer frem i tid, og sender deg en e-post. Det kan kjøres gratis på GitHub Actions (alternativ A), slik
at datamaskinen din ikke trenger å stå på. Uoffisielt, ikke tilknyttet UDI eller politiet.

---

*Keywords: UDI, politiet, police appointment, timebestilling, book appointment police Norway, no available
appointments, ingen ledige timer, SUA Oslo, Service Centre for Foreign Workers, EU/EEA registration,
registreringsbevis, residence permit, oppholdstillatelse, residence card, family immigration, citizenship,
nemo-q, politietbooking, appointment bot, slot checker.*
