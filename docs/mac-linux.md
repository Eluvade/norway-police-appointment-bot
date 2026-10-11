# Run it on your own Mac or Linux computer

It only checks while your computer is on and awake, so it misses slots released at night. If you can, use
[GitHub Actions](github-actions.md) instead.

## 1. Install and test

Open a terminal and run:

```sh
git clone https://github.com/Eluvade/norway-police-appointment-bot.git
cd norway-police-appointment-bot
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/python -m playwright install chromium
cp .env.example .env
open -e .env                           # Mac; on Linux use: nano .env
.venv/bin/python mail.py --test        # you should receive a test email
.venv/bin/python checker.py --probe    # enters the emailed code, then stops
```

[How to get the email app password.](email.md)

## 2. Run it every 10 minutes

Run `pwd` and copy the folder path it prints. Then run `crontab -e` and add this line, replacing
`/path/to/norway-police-appointment-bot` with that path:

```
*/10 * * * * cd /path/to/norway-police-appointment-bot && .venv/bin/python checker.py >> checker.log 2>&1
```

After it books an appointment, every later run exits immediately. Run `crontab -e` again and delete the line.
Then delete the app password at <https://myaccount.google.com/apppasswords> and the `.env` file.
