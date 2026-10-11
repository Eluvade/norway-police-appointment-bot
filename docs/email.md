# Email setup

The script needs to log in to **the mailbox where the police's emails arrive**. That's the email address you
registered with UDI. It reads the police's verification code (*"Your code: XXXXXX"*) from there and sends you
notifications from the same account.

Your password won't work for this. You need an **app password**, a separate password just for this script.

## Gmail (tested)

1. Turn on [2-Step Verification](https://myaccount.google.com/signinoptions/twosv) for your Google account.
2. Open <https://myaccount.google.com/apppasswords>.
   **Check the avatar at the top right: it must be the right account.** If you have several Google
   accounts, this is the most common mistake, and it shows up as an `Invalid credentials` error.
3. Create a password with any name, and copy the 16 letters without the spaces.

Use your Gmail address as `GMAIL_ADDRESS` and the 16 letters as `GMAIL_APP_PASSWORD`.

## Other providers (untested)

Any provider that allows IMAP and SMTP login with an app password should work, for example iCloud, Yahoo or
Fastmail. Put your address and app password in `GMAIL_ADDRESS` and `GMAIL_APP_PASSWORD` (the names stay the
same), and also set your provider's servers:

| Setting | Example (iCloud) |
|---|---|
| `IMAP_HOST` | `imap.mail.me.com` |
| `SMTP_HOST` | `smtp.mail.me.com` |

The SMTP server must accept SSL on port 465. Outlook and Hotmail no longer allow logging in with a password over
IMAP, so they probably won't work.
