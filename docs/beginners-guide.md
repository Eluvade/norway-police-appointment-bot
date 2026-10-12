# Step-by-step guide (no coding needed)

This guide sets up the appointment robot on GitHub, a free website that can run it for you every 10 minutes,
even while your computer is off. It takes about 15 minutes. You don't need to know anything about code: you'll
only click buttons and copy-paste a few things.

> **Prefer to let an AI do it?** If you use an AI assistant that can work on your computer (Claude Code, Codex,
> Cursor), give it this link and say *"set this up for me using GitHub Actions"*:
> `https://github.com/Eluvade/norway-police-appointment-bot`. Type your passwords yourself when it asks; never
> paste them into the chat.

## What you'll need

- **Your booking number.** It's in the email *"Book an appointment with the Police - Immigration Authorities"*,
  or on your application's page on udi.no.
- **Your UDI login** (the email and password you use on udi.no).
- **The email account where the police's emails arrive.** This guide assumes it's Gmail. For other email
  providers, see [email setup](email.md).

---

## Step 1: Make a free GitHub account

Go to <https://github.com/signup> and create an account. Any username is fine. Confirm your email address
when GitHub asks.

## Step 2: Make your own copy of the robot

1. Open <https://github.com/Eluvade/norway-police-appointment-bot>.
2. Next to the **Code** button, click the green **Use this template** button, then **Create a new repository**.
   (Don't see it? You need to be signed in to GitHub first.)
3. In **Repository name**, type any name, for example `police-appointment`.
4. Leave it on **Public** (it's free that way, and your passwords stay hidden: see the note at the end).
5. Click **Create repository**.

You now have your own copy. Everything from here happens in **your** copy, not on the original page.

## Step 3: Get a Gmail "app password"

The robot needs to read the police's verification code from your email. Gmail doesn't let programs use your
normal password, so you create a separate one just for this.

1. Make sure 2-Step Verification is on: <https://myaccount.google.com/signinoptions/twosv>.
2. Open <https://myaccount.google.com/apppasswords>.
3. **Check the picture at the top right.** It must be the Gmail account that receives the police's emails. If
   it shows a different account, click it and switch.
4. Type any name (for example `police robot`) and click **Create**.
5. Google shows a password of 16 letters. Copy it **without the spaces** and keep the page open for a moment;
   you'll need it in the next step. Google shows it only once.

## Step 4: Give the robot your details

In your copy on GitHub:

1. Click **Settings** (the tab with the gear icon, near the top).
2. In the menu on the left, click **Secrets and variables**, then **Actions**.
3. Click the green **New repository secret** button.
4. In **Name**, type the first name from the table below, exactly as written. In **Secret**, type your value.
   Click **Add secret**.
5. Repeat for each row:

| Name | What to type |
|---|---|
| `BOOKING_NUMBER` | your booking number |
| `GMAIL_ADDRESS` | your Gmail address |
| `GMAIL_APP_PASSWORD` | the 16 letters from step 3 |
| `UDI_EMAIL` | the email you use to log in to udi.no |
| `UDI_PASSWORD` | your udi.no password |

Secrets can't be read by anyone after you save them, not even by you. If you make a typo, click the secret's
pencil icon and type it again.

## Step 5: Test it

1. Click the **Actions** tab at the top. If GitHub asks, click the green button to enable workflows.
2. On the left, click **Appointment checker**.
3. On the right, click **Run workflow**. In the menu that opens, choose **test-email**, then click the green
   **Run workflow** button.
4. Wait a minute. You should get an email titled **"UDI checker: test email"**.
   No email? See [what can go wrong](#what-can-go-wrong).
5. Do the same again, but choose **probe**. This one opens the police booking page, reads the code from your
   email and stops, without booking anything. After a minute or two, click the run, then **check**, and look
   at the last lines. They should say `Probe: code accepted, now at step 'Select office, date and time'`.

## Step 6: Switch it on

1. Go to **Settings → Secrets and variables → Actions** again.
2. Click the **Variables** tab (next to **Secrets**), then **New repository variable**.
3. Name: `CHECKER_ENABLED`. Value: `true`. Click **Add variable**.

That's it. The robot now checks every 10 minutes. When it books an appointment, it emails you
**"✅ Police appointment BOOKED"** and switches itself off. You'll also get an official confirmation from the
police.

If a slot appears but booking fails for some reason, you'll get **"⚠️ AVAILABLE, book manually NOW"**. Open
the link in that email right away and book it yourself.

---

## After you're booked

Tidy up, because the app password can read your whole mailbox:

1. Delete the app password at <https://myaccount.google.com/apppasswords> (click the bin icon next to it).
2. In your copy on GitHub, go to **Settings**, scroll to the very bottom, and click **Delete this repository**.

## What can go wrong

- **A red ❌ next to the run:** click it, then click **check** to see the message.
  - `Invalid credentials`: the app password was made on a different Google account (step 3, point 3), or it was
    copied with spaces. Make a new one and update `GMAIL_APP_PASSWORD`.
  - `Direct booking link did not show the code form`: check `BOOKING_NUMBER`. If you already have an
    appointment, this is normal.
- **No test email:** look in your spam folder, and check `GMAIL_ADDRESS` for typos.
- **Stuck?** Open an issue on the [project page](https://github.com/Eluvade/norway-police-appointment-bot/issues)
  and describe what you see. Never post your passwords or booking number there.

## Is this safe?

- Your passwords are stored as GitHub "secrets": they're encrypted, hidden in all logs, and nobody (including
  the author of this robot) can see them.
- The robot only talks to the police booking site, udi.no (only if the direct link stops working), and your
  email.
- It checks once every 10 minutes, like a very patient person refreshing the page, and it only ever books one
  appointment: yours.
- Because your copy is public, anyone could see *when* the robot ran and whether it booked something, but not
  your details, passwords or appointment time. Your GitHub username is visible, so pick one that isn't your
  full name if you'd rather stay anonymous.
