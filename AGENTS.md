# Instructions for AI assistants

This repository books a Norwegian police (Politiet) appointment for a UDI application. It checks
`politietbooking.nemo-q.se` every 10 minutes, reads the emailed verification code over IMAP, books the first
free slot at least `MIN_HOURS_AHEAD` hours away, and emails the user. If someone asks you to set it up for them,
follow the guide they choose:

- [docs/github-actions.md](docs/github-actions.md): recommended, needs no computer that stays on
- [docs/always-on-linux.md](docs/always-on-linux.md): systemd user timer
- [docs/mac-linux.md](docs/mac-linux.md): cron
- [docs/windows.md](docs/windows.md): Task Scheduler
- [docs/email.md](docs/email.md): the app password, and other email providers
- [docs/settings.md](docs/settings.md): all settings and test flags

## Rules

- **Never read, print or ask for the user's passwords.** Don't open `.env`, don't echo environment variables,
  and don't ask the user to paste a password into the chat. Let them type secrets themselves:
  - GitHub: the repository's **Settings → Secrets and variables → Actions** page, or `gh secret set NAME` run
    by the user in their own terminal (it asks for the value with hidden input).
  - Local: the user edits `.env` themselves, after you run `cp .env.example .env && chmod 600 .env`.
- Before switching on the schedule, test with `mail.py --test` and `checker.py --probe` (on GitHub: the
  `test-email` and `probe` modes of the workflow). The probe should end with
  `Probe: code accepted, now at step 'Select office, date and time'`.
- Don't make it check more often than every 10 minutes.
- Don't change the booking flow in `checker.py` unless the user asks for it.
