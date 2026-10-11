# Run it on your own Windows computer

It only checks while your computer is on and awake, so it misses slots released at night. If you can, use
[GitHub Actions](github-actions.md) instead.

You need [Python](https://www.python.org/downloads/) and [Git](https://git-scm.com/download/win) installed.

## 1. Install and test

Open **Command Prompt** and run:

```bat
git clone https://github.com/Eluvade/norway-police-appointment-bot.git
cd norway-police-appointment-bot
py -m venv .venv
.venv\Scripts\pip install -r requirements.txt
.venv\Scripts\python -m playwright install chromium
copy .env.example .env
notepad .env
.venv\Scripts\python mail.py --test
.venv\Scripts\python checker.py --probe
```

Fill in your details in Notepad and save before running the last two commands. The first one should send you
a test email. The second one enters the emailed code, then stops.
[How to get the email app password.](email.md)

## 2. Run it every 10 minutes

In the same Command Prompt window, run:

```bat
schtasks /Create /SC MINUTE /MO 10 /TN udi-checker /TR "cmd /c cd /d %CD% && .venv\Scripts\python.exe checker.py"
```

On a laptop, open Task Scheduler, find `udi-checker`, and on the **Conditions** tab turn off *"Start the task
only if the computer is on AC power"*.

After it books an appointment, delete the task:

```bat
schtasks /Delete /TN udi-checker /F
```

Then delete the app password at <https://myaccount.google.com/apppasswords> and the `.env` file.
