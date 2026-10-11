# Run it on GitHub Actions (no computer needed)

GitHub runs the checker for you on its servers, for free. You only need a free GitHub account.

## 1. Make your own copy

At the top of the [repository page](https://github.com/Eluvade/norway-police-appointment-bot), click **Use this template → Create a new repository**.

- **Public:** free, with no limit on minutes. Your passwords and booking number are hidden: GitHub stores them
  encrypted and masks them in logs. But anyone can see the run logs, which show *when* it ran and whether it
  found or booked something (not the time of your appointment).
- **Private:** also works, but the free plan includes 2,000 minutes a month, which is about one run every 30
  minutes. In your copy, edit `.github/workflows/checker.yml` and change `*/10` to `*/30`.

## 2. Add your details

In your new repository, go to **Settings → Secrets and variables → Actions**. Under **Secrets**, click
**New repository secret** and add each of these:

| Secret | Value |
|---|---|
| `BOOKING_NUMBER` | your booking number |
| `GMAIL_ADDRESS` | the email address where the police's emails arrive |
| `GMAIL_APP_PASSWORD` | its app password ([how to get one](email.md)) |
| `UDI_EMAIL` | the email you log in to udi.no with |
| `UDI_PASSWORD` | your udi.no password (only used if the direct booking link stops working) |
| `NOTIFY_TO` | *(optional)* where to send notifications, if not to `GMAIL_ADDRESS` |

If you don't use Gmail, also add `IMAP_HOST` and `SMTP_HOST` under the **Variables** tab ([details](email.md)).

## 3. Test it

Go to **Actions → Appointment checker → Run workflow**, choose a mode, and click **Run workflow**:

1. `test-email`: you should receive a test email within a minute or two.
2. `probe`: it opens your booking link, enters the emailed code, and stops. Open the run: the log should end
   with `Probe: code accepted, now at step 'Select office, date and time'`.

## 4. Switch it on

Under **Settings → Secrets and variables → Actions → Variables**, add the variable `CHECKER_ENABLED` with the
value `true`. From now on it runs every 10 minutes. After it books an appointment, it switches itself off.

Optional variables: `AUTO_BOOK` (`false` means only email you, never book) and `MIN_HOURS_AHEAD` (default
`12`). See [settings](settings.md).

## Good to know

- When GitHub is busy, scheduled runs sometimes start 10–30 minutes late.
- GitHub pauses schedules in repositories that have had no activity for 60 days, and emails you when it does.
  Click the link in that email to turn it back on.
- To stop it yourself, delete the `CHECKER_ENABLED` variable or set it to `false`.
- Don't add collaborators to your copy, and don't accept pull requests to it: anyone who can change the
  workflow could read your secrets.

## After you're booked

Your app password can read your whole mailbox, so don't leave it lying around:

1. Delete the app password at <https://myaccount.google.com/apppasswords>.
2. Delete your repository (**Settings → Delete this repository**), or at least the secrets under
   **Settings → Secrets and variables → Actions**.
