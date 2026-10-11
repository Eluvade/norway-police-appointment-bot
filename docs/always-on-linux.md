# Run it on an always-on Linux machine

For example a home server, a Raspberry Pi, an old laptop, or a cheap VPS (about €4/month). You need Python 3.10
or newer and git.

## 1. Install

```sh
git clone https://github.com/Eluvade/norway-police-appointment-bot.git
cd norway-police-appointment-bot
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/python -m playwright install --with-deps chromium   # may ask for sudo to install browser libraries
cp .env.example .env && chmod 600 .env                         # only you can read it
nano .env                                                      # fill in your details
```

[How to get the email app password.](email.md)

## 2. Test

```sh
.venv/bin/python mail.py --test        # you should receive a test email
.venv/bin/python checker.py --probe    # enters the emailed code, then stops
```

The probe should end with `Probe: code accepted, now at step 'Select office, date and time'`.

## 3. Run it every 10 minutes

```sh
./install-systemd.sh       # installs a systemd timer for your user
loginctl enable-linger     # keeps it running after you log out and after a reboot
```

The timer switches itself off after booking.

- See what it's doing: `journalctl --user -u udi-checker -f`
- Remove it completely: `./install-systemd.sh --remove`

After you're booked, delete the app password at <https://myaccount.google.com/apppasswords> and the `.env`
file.

If you upgrade your system's Python (for example 3.13 → 3.14), the `.venv` folder breaks. Delete it and
rerun the install commands from `python3 -m venv .venv` onwards.
