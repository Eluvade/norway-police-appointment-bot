"""Check the Norwegian police (Nemo-Q) immigration booking calendar for free appointments and book one."""

import argparse
import json
import logging
import os
import re
import shutil
import subprocess
import sys
import time
import traceback
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import urlparse
from zoneinfo import ZoneInfo

from dotenv import load_dotenv
from playwright.sync_api import TimeoutError as PWTimeout
from playwright.sync_api import sync_playwright

import mail

ROOT = Path(__file__).resolve().parent
STATE = ROOT / "state"
ARTIFACTS = ROOT / "artifacts"
BOOKED_FILE = STATE / "booked.json"
FAILURES_FILE = STATE / "failures.json"
TIMER = "udi-checker.timer"
WORKFLOW = "checker.yml"
OSLO = ZoneInfo("Europe/Oslo")  # slot times are Norwegian local time; servers (e.g. GitHub) may run on UTC
IN_GITHUB_ACTIONS = os.environ.get("GITHUB_ACTIONS") == "true"
KEEP_ARTIFACT_RUNS = 50
FAILURE_ALERT_AFTER = 6  # consecutive failed runs (~1h at 10 min interval)
FAILURE_REALERT_SECS = 24 * 3600
TOO_SOON_FILE = STATE / "too_soon_notified.json"
UDI_FALLBACK_FILE = STATE / "udi_fallback_notified"

load_dotenv(ROOT / ".env")
log = logging.getLogger("checker")


class SlotAvailable(Exception):
    """Wraps an error that happened after a free slot was seen."""


def booking_url():
    """The "Book appointment" link from UDI's receipt page / the police's email."""
    url = os.environ.get("BOOKING_URL") or (
        "https://politietbooking.nemo-q.se/Booking/booking/FromSession/avtale"
        f"?organisationId=2&bookingNumber={os.environ['BOOKING_NUMBER']}"
    )
    if urlparse(url).hostname != "politietbooking.nemo-q.se":  # e.g. a link copied from a phishing email
        raise ValueError("BOOKING_URL must be a https://politietbooking.nemo-q.se/... link")
    return url


def require_host(page, *allowed):
    """Refuse to type credentials or codes into a page on an unexpected website."""
    host = urlparse(page.url).hostname or ""
    if not any(host == h or host.endswith("." + h) for h in allowed):
        raise RuntimeError(f"Refusing to continue on unexpected website {host!r}")


def step_name(page):
    """The wizard step the page shows (its breadcrumb), else its first visible heading."""
    crumb = page.locator(".breadcrumb li").last
    if crumb.count() and crumb.inner_text().strip():
        return crumb.inner_text().lstrip("> ").strip()
    heading = page.locator("h1:visible, h2:visible").first  # skips the hidden session-timeout dialog
    return heading.inner_text().strip() if heading.count() else page.title()


class Run:
    def __init__(self, args):
        self.args = args
        self.dir = ARTIFACTS / datetime.now().strftime("%Y%m%d-%H%M%S")
        self.dir.mkdir(parents=True, exist_ok=True)
        self.snaps = []
        self.too_soon = []  # free slots skipped because they start within MIN_HOURS_AHEAD
        self.target = None

    def snap(self, page, name):
        """Save screenshot + HTML of the current page; never fails the run."""
        try:
            png = self.dir / f"{len(self.snaps):02d}-{name}.png"
            html = png.with_suffix(".html")
            page.screenshot(path=png, full_page=True)
            html.write_text(page.content())
            self.snaps += [png, html]
            log.info("Snapshot %s", png.name)
        except Exception:
            log.exception("Snapshot %s failed", name)

    # --- navigation -------------------------------------------------------

    def open_booking(self, ctx):
        """Return a page showing the nemo-q verification-code form (None in probe mode if there is none)."""
        page = ctx.new_page()
        if not self.args.full_login:
            page.goto(booking_url())
            try:
                page.wait_for_selector("#VerificationCode", timeout=15000)
                log.info("Direct booking link works, skipped UDI login")
                return page
            except PWTimeout:
                self.snap(page, "direct-link-failed")
                log.info("Direct booking link did not show the code form (page: %r)", step_name(page))
                if self.args.probe:
                    # An already-booked application lands on the police's change/cancel page here
                    return None
                log.info("Falling back to UDI login")
                notify_udi_fallback(self)

        page.goto("https://minside.udi.no/")
        page.click("#usernamePassword")
        page.wait_for_selector("#signInName", timeout=60000)
        require_host(page, "udi.no")  # the password form is served by login.udi.no
        page.fill("#signInName", os.environ["UDI_EMAIL"])
        page.fill("#password", os.environ["UDI_PASSWORD"])
        page.click("#next")
        page.wait_for_url(re.compile(r"https://(my|minside)\.udi\.no/.*"), timeout=60000)
        page.goto("https://my.udi.no/?lang=en")
        link = page.locator("#applications tr").first.locator('a[href*="formNext/submitted"]')
        link.wait_for(timeout=60000)
        page.goto(link.get_attribute("href").replace("/nb/", "/en/"))
        book = page.locator('a[href*="politietbooking.nemo-q.se"]').first
        book.wait_for(timeout=60000)
        self.snap(page, "application")
        with ctx.expect_page() as new_page:
            book.click()
        page = new_page.value
        page.wait_for_selector("#VerificationCode", timeout=60000)
        return page

    def submit(self, page, button):
        """Click a submit button (selector or locator) and wait for the resulting page load."""
        with page.expect_navigation(timeout=60000):
            page.click(button) if isinstance(button, str) else button.click()
        page.wait_for_load_state("networkidle")

    # Verified against a live Nemo-Q "Ventus" booking site with free slots (ssc.nemoq.se):
    # each slot is <button data-function="timeTableCell" class="timecell available"
    # data-fromdatetime="2026-10-12 09:55:00" ...>; clicking it fills #ReservedDateTime.
    SLOT = '[data-function="timeTableCell"].available'
    NEXT = '[type="submit"][name="Next"]'  # <input> on some pages, <button> on others
    WIZARD_FORM = 'form[action*="/Booking/Booking/Next/"]'

    def has_slots(self, page):
        return page.locator(self.SLOT).count() > 0

    def classify_slots(self, page):
        """Split the shown slots (all days on the page) into bookable ones, earliest first,
        and ones starting too soon to make it."""
        now = datetime.now(OSLO).replace(tzinfo=None)
        min_start = now + timedelta(hours=float(os.environ.get("MIN_HOURS_AHEAD") or 12))
        ok, too_soon = [], []
        for i, cell in enumerate(page.locator(self.SLOT).all()):
            raw = cell.get_attribute("data-fromdatetime") or ""
            try:
                start = datetime.strptime(raw, "%Y-%m-%d %H:%M:%S")
            except ValueError:
                log.warning("Unparseable slot time %r, not applying the minimum-notice rule to it", raw)
                ok.append((datetime.max, i, cell))  # after every parseable slot, in page order
                continue
            if start >= min_start:
                ok.append((start, i, cell))
            else:
                too_soon.append(raw)
        return [cell for _, _, cell in sorted(ok, key=lambda t: t[:2])], too_soon

    def take_bookable(self, page, label):
        """Classify the shown slots; remember the earliest bookable one. Returns True if there is one."""
        if not self.has_slots(page):
            return False
        ok, too_soon = self.classify_slots(page)
        log.info("%s: %d slot(s) available, %d too soon", label, len(ok) + len(too_soon), len(too_soon))
        self.too_soon += [t for t in too_soon if t not in self.too_soon]
        if ok:
            self.target = ok[0]
        return bool(ok)

    def search(self, page):
        """Run both searches; return True if any slots are shown."""
        for name in ("TimeSearchButton", "TimeSearchFirstAvailableButton"):
            button = f'[type="submit"][name="{name}"]'
            page.wait_for_selector(button, timeout=60000)
            self.submit(page, button)
            self.snap(page, name)
            if self.take_bookable(page, name):
                return True
            if self.has_slots(page):
                continue
            if not page.locator("#no-available-times").is_visible():
                log.warning("%s: neither slots nor the 'no available times' message found", name)
            log.info("%s: no available appointments", name)
        if self.too_soon:
            # Everything shown starts too soon; later days of the same release may be on next week's page
            try:
                next_week = page.locator('a[data-function="navLink"]#nextweek')
                if next_week.count():
                    self.submit(page, next_week)
                    self.snap(page, "next-week")
                    return self.take_bookable(page, "next week")
            except Exception:
                log.exception("Checking next week failed")
        return False

    def pick_first_slot(self, page):
        cell = self.target
        wanted = cell.get_attribute("data-fromdatetime")
        cell.click()
        page.wait_for_function(
            "v => document.getElementById('ReservedDateTime')?.value === v", arg=wanted, timeout=10000
        )
        log.info("Selected a slot")  # no time: GitHub Actions logs are public
        return wanted

    def book(self, page):
        slot = self.pick_first_slot(page)
        self.snap(page, "slot-selected")
        if self.args.dry_run:
            raise RuntimeError("Dry run: selected a slot but did not press Next")
        button = self.NEXT
        for step in range(6):
            self.submit(page, button)
            self.snap(page, f"after-next-{step}")
            text = page.inner_text("body")
            if page.locator(".validation-summary-errors li, .field-validation-error").count():
                # Page text is left out on purpose: it holds personal data and logs may be public
                raise RuntimeError("The booking form showed a validation error (see the attached screenshot)")
            # Every wizard step is a form posting to /Booking/Booking/Next/<config>; the receipt page has none.
            # Only treat it as booked once we have left the wizard, so a "Confirm booking" summary page
            # (which itself contains the word "confirm") is never mistaken for success.
            if not page.locator(self.WIZARD_FORM).count():
                if re.search(r"confirm|bekreft|booked|booking number|bestillingsnummer|takk|thank", text, re.I):
                    return slot, text
                raise RuntimeError("Left the booking wizard but found no confirmation text")
            self.fill_known_fields(page)
            # Details should be prefilled from the application; never guess personal data
            empty = [
                el.get_attribute("name")
                for el in page.locator("input[required]:visible, select[required]:visible").all()
                if el.get_attribute("type") != "checkbox" and not el.input_value()
            ]
            if empty:
                raise RuntimeError(f"Required fields are empty, cannot continue automatically: {empty}")
            button = self.next_or_confirm_button(page)
        raise RuntimeError("Still not confirmed after 6 steps")

    def fill_known_fields(self, page):
        """Fill the generic Nemo-Q wizard steps between the slot and the review page.

        Step layout per a working Nemo-Q booker (github.com/epcosta17/txdmv-appointment):
        Personal data -> Contact information (EmailAddress, ConfirmEmailAddress, PhoneNumber and a
        SelectedContacts grid: confirmation/reminder x email(MessageTypeId 2)/SMS(1)) -> Review -> Confirmation.
        """
        # Only required checkboxes (consent/terms); ticking everything would enable SMS without a phone number
        for cb in page.locator('input[type="checkbox"][required]:not(:checked)').all():
            if cb.is_visible():
                cb.check()
        for name in ("EmailAddress", "ConfirmEmailAddress"):
            field = page.locator(f'input[name="{name}"]:visible')
            if field.count() and not field.input_value():
                field.fill(os.environ["UDI_EMAIL"])
        # Get the confirmation and reminder by email
        for type_id in page.locator('input[name^="SelectedContacts["][name$="].MessageTypeId"][value="2"]').all():
            prefix = type_id.get_attribute("name").removesuffix(".MessageTypeId")
            cb = page.locator(f'input[type="checkbox"][name="{prefix}.IsSelected"]')
            if cb.count() and cb.is_visible() and not cb.is_checked():
                cb.check()

    def next_or_confirm_button(self, page):
        """The button that advances this step: Next, or a final Confirm/Book button if Next is gone."""
        if page.locator(self.NEXT).count():
            return self.NEXT
        for el in page.locator(f'{self.WIZARD_FORM} [type="submit"]:visible').all():
            label = " ".join(filter(None, [el.get_attribute("name"), el.get_attribute("value"), el.inner_text()]))
            if re.search(r"confirm|bekreft|book|bestill|fullf|complete|finish", label, re.I) and not re.search(
                r"TimeSearch|back|tilbake|cancel|avbryt", label, re.I
            ):
                log.info("Using final button: %s", label)
                return el
        raise RuntimeError("Unknown step: no Next or Confirm button found")

    def check(self):
        with sync_playwright() as p:
            headful = self.args.debug and bool(os.environ.get("DISPLAY") or os.environ.get("WAYLAND_DISPLAY"))
            browser = p.chromium.launch(headless=not headful, slow_mo=300 if headful else 0)
            ctx = browser.new_context(locale="en-GB", viewport={"width": 1280, "height": 1000})
            ctx.set_default_timeout(30000)
            page = None
            started = datetime.now(timezone.utc)
            try:
                page = self.open_booking(ctx)
                if page is None:
                    return None
                code = mail.fetch_verification_code(started)
                require_host(page, "politietbooking.nemo-q.se")
                page.fill("#VerificationCode", code)
                self.submit(page, self.NEXT)
                self.snap(page, "verified")
                if self.args.probe:
                    log.info("Probe: code accepted, now at step %r; stopping here", step_name(page))
                    return None
                if not self.search(page):
                    if self.too_soon:
                        notify_too_soon(self)
                    return None
                if os.environ.get("AUTO_BOOK", "true").lower() != "true":
                    raise SlotAvailable("AUTO_BOOK is disabled")
                try:
                    return self.book(page)
                except Exception as e:
                    raise SlotAvailable(f"{e}\n\n{traceback.format_exc()}") from e
            except Exception:
                if page:
                    self.snap(page, "error")
                raise
            finally:
                if headful:
                    input("Press Enter to close the browser...")
                browser.close()
                mail.cleanup_code_emails(started)


# --- notifications & state ---------------------------------------------------


def disable_schedule():
    """Stop whatever runs this script on a schedule. Returns a sentence for the notification email."""
    if IN_GITHUB_ACTIONS:
        cmd = ["gh", "workflow", "disable", WORKFLOW, "--repo", os.environ["GITHUB_REPOSITORY"]]
        manual = f"disable the '{WORKFLOW}' workflow in your repository's Actions tab"
    elif shutil.which("systemctl"):
        cmd = ["systemctl", "--user", "disable", "--now", TIMER]
        manual = f"run: systemctl --user disable --now {TIMER}"
    else:
        return "Remove the scheduled task / cron entry that runs this script; until then each run exits immediately."
    try:
        r = subprocess.run(cmd, capture_output=True, text=True)
        err = r.stderr.strip()
        ok = r.returncode == 0 or "not loaded" in err or "does not exist" in err
    except OSError as e:
        ok, err = False, str(e)
    if ok:
        log.info("Disabled the schedule (%s)", " ".join(cmd[:3]))
        return "The schedule has been disabled automatically."
    log.error("Failed to disable the schedule: %s", err)
    return f"WARNING: could not disable the schedule ({err}). Runs exit early because a booking was recorded, but {manual}."


def on_booked(run, slot, text, simulate=False):
    if not simulate:
        BOOKED_FILE.write_text(json.dumps({"slot": slot, "at": datetime.now().isoformat()}, indent=2))
    timer_msg = disable_schedule()
    mail.send_email(
        "✅ Police appointment BOOKED" + (" (SIMULATED)" if simulate else ""),
        f"An appointment was booked for slot: {slot}\n\n{timer_msg}\n\n"
        f"Watch for the official confirmation email from Politiet. Confirmation page text:\n\n{text[:3000]}",
        run.snaps[-4:],
    )


def on_available_failed(run, err):
    mail.send_email(
        "⚠️ Police appointment AVAILABLE — auto-booking failed, book manually NOW",
        "A free appointment was found but the script could not finish booking it.\n"
        "It may or may not have been booked — check your email for a confirmation, and if there is none, "
        "book manually right away. Pause the checker first, so it doesn't request a new code while you "
        "book (GitHub: set the CHECKER_ENABLED variable to false; Linux: systemctl --user stop udi-checker.timer).\n\n"
        "  https://my.udi.no/?lang=en  →  My applications  →  Go to application  →  Book appointment\n"
        f"  (direct: {booking_url()})\n\n"
        f"Error:\n{err}\n\nScreenshots and page HTML are attached.",
        run.snaps[-6:],
    )


def notify_udi_fallback(run):
    """Warn (at most daily) that runs now log in to UDI, which could get the account flagged."""
    try:
        if UDI_FALLBACK_FILE.exists() and time.time() - UDI_FALLBACK_FILE.stat().st_mtime < FAILURE_REALERT_SECS:
            return
        mail.send_email(
            "UDI checker: direct booking link stopped working, now logging in to UDI every run",
            "The direct police booking link no longer shows the verification-code page, so the checker "
            "fell back to logging in via udi.no on every run. That still works, but frequent logins "
            "could get the UDI account flagged. Consider running it less often, check that BOOKING_URL / "
            "BOOKING_NUMBER is right, or check the project page for an update. (If your appointment is "
            "already booked, this is expected: the booking flow is closed.)",
            run.snaps[-2:],
        )
        UDI_FALLBACK_FILE.touch()
    except Exception:
        log.exception("Failed to send UDI fallback notice")


def notify_too_soon(run):
    """Email once per distinct set of too-soon slots, so a lingering slot doesn't email every run."""
    slots = sorted(run.too_soon)
    if TOO_SOON_FILE.exists() and json.loads(TOO_SOON_FILE.read_text()) == slots:
        log.info("Too-soon slots already notified")
        return
    hours = os.environ.get("MIN_HOURS_AHEAD") or 12
    mail.send_email(
        "⏰ Police appointment free but SOON — not auto-booked",
        f"Free appointment(s) were found, but all start within {hours} hours, so nothing was booked:\n\n  "
        + "\n  ".join(slots)
        + f"\n\nIf you can make it, book manually right away:\n  {booking_url()}\n",
        run.snaps[-2:],
    )
    TOO_SOON_FILE.write_text(json.dumps(slots))


def record_failure(run, err):
    state = json.loads(FAILURES_FILE.read_text()) if FAILURES_FILE.exists() else {"count": 0, "last_alert": 0}
    state["count"] += 1
    now = time.time()
    if state["count"] >= FAILURE_ALERT_AFTER and now - state["last_alert"] > FAILURE_REALERT_SECS:
        mail.send_email(
            f"UDI checker is failing ({state['count']} runs in a row)",
            "The appointment checker has not been able to check for appointments. The site may have "
            f"changed, or credentials may be wrong. Check manually and look at the logs "
            f"(journalctl --user -u udi-checker, or the GitHub Actions run log).\n\nLast error:\n{err}",
            run.snaps[-2:],
        )
        state["last_alert"] = now
    FAILURES_FILE.write_text(json.dumps(state))


def prune_artifacts():
    runs = sorted(d for d in ARTIFACTS.iterdir() if d.is_dir())
    for d in runs[:-KEEP_ARTIFACT_RUNS]:
        shutil.rmtree(d, ignore_errors=True)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--debug", action="store_true", help="visible browser, slow motion, pause before closing")
    ap.add_argument("--probe", action="store_true", help="only enter the verification code and snapshot the next page")
    ap.add_argument("--dry-run", action="store_true", help="select a slot but never press the final Next")
    ap.add_argument("--full-login", action="store_true", help="skip the direct booking link, always log in to UDI")
    ap.add_argument("--simulate-available", action="store_true", help="only send the 'available, booking failed' email")
    ap.add_argument("--simulate-booked", action="store_true", help="only run the success path (email + disable the schedule)")
    args = ap.parse_args()
    os.umask(0o077)  # screenshots and state contain personal data: readable by this user only
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s", stream=sys.stdout)
    STATE.mkdir(exist_ok=True)

    try:
        import fcntl  # not available on Windows, where Task Scheduler can prevent overlapping runs instead

        lock = open(STATE / "lock", "w")
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except ImportError:
        pass
    except BlockingIOError:
        log.info("Another run is in progress, exiting")
        return

    run = Run(args)
    if args.simulate_available:
        on_available_failed(run, "Simulated failure (test of the notification email)")
        return
    if args.simulate_booked:
        on_booked(run, "SIMULATED SLOT", "Simulated confirmation page", simulate=True)
        return
    if BOOKED_FILE.exists() and not args.probe:
        log.info("Already booked (%s), nothing to do", BOOKED_FILE)
        disable_schedule()
        return

    try:
        result = run.check()
        if result:
            on_booked(run, *result)
        elif args.probe:
            log.info("Probe finished")
        else:
            log.info("No appointments available")
        FAILURES_FILE.unlink(missing_ok=True)
    except SlotAvailable as e:
        log.error("Slot available but booking failed: %s", str(e).splitlines()[0])
        on_available_failed(run, e)
        FAILURES_FILE.unlink(missing_ok=True)
    except Exception as e:
        log.exception("Check failed")
        record_failure(run, f"{e}\n\n{traceback.format_exc()}")
        sys.exit(1)
    finally:
        prune_artifacts()


if __name__ == "__main__":
    main()
