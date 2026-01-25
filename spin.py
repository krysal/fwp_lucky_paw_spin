#!/usr/bin/env python3
"""
Lucky Paw Spin Automation for Ferris Wheel Press Loyalty Lounge.

This script automates the daily spin wheel on the Ferris Wheel Press loyalty page.
It tracks the last spin time and only spins if 24.5 hours have passed.
"""

import argparse
import json
import os
import random
import string
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeout

# Configuration
LOYALTY_URL = "https://ferriswheelpress.com/pages/loyalty-lounge"
SPIN_INTERVAL_HOURS = 24.25
LAST_SPIN_FILE = Path(__file__).parent / "last_spin.json"
SCREENSHOTS_DIR = Path(__file__).parent / "screenshots"

# Selectors for the spin wheel
EMAIL_INPUT_SELECTORS = [
    "#email_input_text",  # Primary: by ID
]

SPIN_BUTTON_SELECTORS = [
    "#spin-button", # Primary: by ID
    "button:has-text('SPIN')",
    "button[type='submit']",
    "input[type='submit']",
    "[class*='spin' i] button",
]

RESULT_SELECTORS = [
    "#win_header_text",  # Primary: "CONGRATULATIONS!"
    "#win_text",  # Contains the prize/reward text
]

MODAL_SELECTORS = [
    "button.modal__close",  # Double underscore
    "button.modal-close",   # Single hyphen (found in debug)
    "[data-micromodal-close]",
    "button[aria-label='Close modal']",
    "button[aria-label='Close']",  # Generic close
    ".modal__close",
    ".modal-close",
]

def generate_random_email() -> str:
    """Generate a random email for testing."""
    random_str = "".join(random.choices(string.ascii_lowercase + string.digits, k=10))
    # return f"test_{random_str}@example.com"
    return "ginaf97689@noihse.com"


def load_last_spin() -> dict:
    """Load the last spin data from file."""
    if LAST_SPIN_FILE.exists():
        with open(LAST_SPIN_FILE) as f:
            return json.load(f)
    return {"last_spin": None, "result": None}


def save_last_spin(result: str | None = None) -> None:
    """Save the current spin time and result."""
    data = {
        "last_spin": datetime.now(timezone.utc).isoformat(),
        "result": result,
    }
    with open(LAST_SPIN_FILE, "w") as f:
        json.dump(data, f, indent=2)
    print(f"Saved spin data: {data}")


def should_spin() -> bool:
    """Check if enough time has passed since the last spin."""
    data = load_last_spin()
    last_spin = data.get("last_spin")

    if last_spin is None:
        print("No previous spin recorded. Will spin now.")
        return True

    last_spin_time = datetime.fromisoformat(last_spin)
    elapsed = datetime.now(timezone.utc) - last_spin_time
    required = timedelta(hours=SPIN_INTERVAL_HOURS)

    if elapsed >= required:
        print(f"Last spin was {elapsed.total_seconds() / 3600:.2f} hours ago. Will spin now.")
        return True

    remaining = required - elapsed
    print(f"Only {elapsed.total_seconds() / 3600:.2f} hours since last spin.")
    print(f"Need to wait {remaining.total_seconds() / 3600:.2f} more hours.")
    return False


def perform_spin(email: str, headless: bool = True, debug: bool = False, pause: int = 0) -> str | None:
    """
    Perform the spin action on the loyalty page.

    Args:
        email: Email address to use for the spin
        headless: Run browser in headless mode
        debug: Enable debug mode with screenshots
        pause: Seconds to wait before closing browser (for inspection)

    Returns:
        The result/prize text if successful, None otherwise
    """
    print(f"Starting spin for email: {email}")
    print(f"Navigating to: {LOYALTY_URL}")

    # Ensure screenshots directory exists
    SCREENSHOTS_DIR.mkdir(exist_ok=True)

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=headless)
        context = browser.new_context(
            viewport={"width": 1280, "height": 720},
            user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
        )
        page = context.new_page()

        try:
            # Navigate to the loyalty page
            page.goto(LOYALTY_URL, wait_until="load", timeout=60000)
            print("Page loaded successfully")

            if debug:
                page.screenshot(path=SCREENSHOTS_DIR / "debug_01_page_loaded.png")

            # Wait for the Rivo widget popup to appear
            page.wait_for_timeout(5000)

            if debug:
                page.screenshot(path=SCREENSHOTS_DIR / "debug_02_after_wait.png")

            # Step 1a: Close the Rivo modal popup if present (it's inside an iframe!)
            print("Checking for Rivo modal popup (inside iframe)...")
            modal_closed = False

            # The Rivo modal is inside an iframe with ID like "rivo-form-*-iframe"
            # We need to find that iframe and click the close button inside it
            for frame in page.frames:
                frame_url = frame.url or ""
                frame_name = frame.name or ""

                # Look for Rivo iframe (URL contains 'rivo' or name contains 'rivo')
                if "rivo" in frame_url.lower() or "rivo" in frame_name.lower():
                    print(f"  Found Rivo iframe: {frame_url[:60]}")

                    try:
                        # Look for the close button inside this iframe
                        close_btn = frame.locator("button.modal__close")
                        if close_btn.count() > 0:
                            print(f"    Found {close_btn.count()} close button(s) in iframe")
                            if close_btn.first.is_visible(timeout=2000):
                                print("    Clicking close button...")
                                close_btn.first.click()
                                page.wait_for_timeout(1000)
                                print("    Closed Rivo modal!")
                                modal_closed = True
                                break
                    except Exception as e:
                        print(f"    Error closing modal in iframe: {e}")

            if not modal_closed:
                # Fallback: try to find any iframe with a modal close button
                print("  Trying all frames for modal close button...")
                for frame in page.frames:
                    try:
                        close_btn = frame.locator("button.modal__close, button[aria-label='Close modal']")
                        if close_btn.count() > 0 and close_btn.first.is_visible(timeout=1000):
                            print(f"    Found close button in frame: {frame.url[:40] if frame.url else 'unnamed'}")
                            close_btn.first.click()
                            page.wait_for_timeout(1000)
                            print("    Closed modal!")
                            modal_closed = True
                            break
                    except Exception:
                        pass

            if not modal_closed:
                print("  No Rivo modal found to close (may not be present)")

            # Step 1b: Close the Rivo popup if present (it blocks interaction)
            print("Attempting to close Rivo popup...")
            try:
                # Try to click the X button to close popup
                close_clicked = page.evaluate("""
                    () => {
                        // Look for close button (X) in the popup
                        const closeButtons = document.querySelectorAll('button[aria-label*="close" i], button[class*="close" i]');
                        for (const btn of closeButtons) {
                            if (typeof btn.click === 'function') {
                                btn.click();
                                return true;
                            }
                        }
                        // Try clicking outside the popup to dismiss it
                        const overlay = document.querySelector('[class*="overlay" i], [class*="backdrop" i]');
                        if (overlay && typeof overlay.click === 'function') {
                            overlay.click();
                            return true;
                        }
                        return false;
                    }
                """)
                if close_clicked:
                    print("Closed popup via JavaScript")
                else:
                    # Click outside popup area to dismiss
                    print("Trying to dismiss popup by clicking outside...")
                    page.mouse.click(100, 400)
            except Exception as e:
                print(f"Could not close popup: {e}")

            page.wait_for_timeout(2000)

            if debug:
                page.screenshot(path=SCREENSHOTS_DIR / "debug_03_popup_closed.png")

            # Step 2: Look for the spin wheel email input
            # The wheel appears as the last element after 24 hours
            print("Looking for spin wheel email input...")
            print(f"Number of frames on page: {len(page.frames)}")

            email_input = None
            target_frame = page

            # Search in main page and all frames using multiple selectors
            for frame in page.frames:
                frame_name = frame.url[:60] if frame.url else "main"
                print(f"  Checking frame: {frame_name}")

                for selector in EMAIL_INPUT_SELECTORS:
                    try:
                        inputs = frame.locator(selector)
                        count = inputs.count()
                        # print(f"    Selector '{selector}': found {count} element(s)")

                        if count > 0:
                            email_input = inputs.first
                            target_frame = frame
                            print(f"  SUCCESS: Found email input with selector '{selector}' in frame: {frame_name}")
                            break
                    except Exception as e:
                        print(f"    Selector '{selector}': error - {e}")

                if email_input is not None:
                    break

            # If no email input found, log available inputs for debugging and exit
            if email_input is None:
                print("FAILED: Could not find email input with any selector")
                print("Dumping all input elements on page for debugging...")

                try:
                    all_inputs = page.evaluate("""
                        () => {
                            const inputs = document.querySelectorAll('input');
                            return Array.from(inputs).map(i => ({
                                id: i.id,
                                type: i.type,
                                name: i.name,
                                placeholder: i.placeholder,
                                className: i.className
                            }));
                        }
                    """)
                    for inp in all_inputs:
                        print(f"  Input: id='{inp.get('id')}' type='{inp.get('type')}' "
                              f"name='{inp.get('name')}' placeholder='{inp.get('placeholder')}'")
                except Exception as e:
                    print(f"  Could not dump inputs: {e}")

                page.screenshot(path=SCREENSHOTS_DIR / "wheel_not_available.png", full_page=True)
                print(f"Screenshot saved to {SCREENSHOTS_DIR / 'wheel_not_available.png'}")
                print("WHEEL_NOT_AVAILABLE")
                raise Exception("Spin wheel not available - email input not found (wheel may appear after 24 hours)")

            # Fill the email
            email_input.wait_for(state="visible", timeout=10000)
            print("Found email input, filling...")
            email_input.fill(email)

            if debug:
                page.screenshot(path=SCREENSHOTS_DIR / "debug_04_email_filled.png")

            # Step 3: Find and click the spin/submit button
            print("Looking for spin button...")

            spin_button = None
            for selector in SPIN_BUTTON_SELECTORS:
                try:
                    btn = target_frame.locator(selector).first
                    count = btn.count()
                    print(f"  Selector '{selector}': found {count} element(s)")

                    if count > 0 and btn.is_visible():
                        spin_button = btn
                        print(f"SUCCESS: Found spin button with selector '{selector}'")
                        break
                except Exception as e:
                    print(f"  Selector '{selector}': error - {e}")

            if spin_button is None:
                # Log all buttons for debugging
                print("FAILED: Could not find spin button")
                print("Dumping all button elements for debugging...")
                try:
                    all_buttons = page.evaluate("""
                        () => {
                            const buttons = document.querySelectorAll('button, input[type="submit"]');
                            return Array.from(buttons).map(b => ({
                                tag: b.tagName,
                                type: b.type,
                                text: b.textContent?.trim().substring(0, 50),
                                className: b.className
                            }));
                        }
                    """)
                    for btn in all_buttons:
                        print(f"  Button: tag='{btn.get('tag')}' type='{btn.get('type')}' "
                              f"text='{btn.get('text')}' class='{btn.get('className')}'")
                except Exception as e:
                    print(f"  Could not dump buttons: {e}")

                page.screenshot(path=SCREENSHOTS_DIR / "error_no_spin_button.png")
                raise Exception("Could not find spin/submit button")

            print("Clicking spin button...")
            spin_button.click()

            # Wait for the spin animation and result
            page.wait_for_timeout(10000)

            if debug:
                page.screenshot(path=SCREENSHOTS_DIR / "debug_05_after_spin.png")

            # Try to capture the result
            print("Looking for spin result...")
            result = None

            # Try to get the win header (e.g., "CONGRATULATIONS!")
            try:
                header = page.locator("#win_header_text")
                if header.is_visible(timeout=5000):
                    header_text = header.text_content()
                    print(f"  Win header: {header_text}")
                    result = header_text
            except Exception as e:
                print(f"  Could not get win header: {e}")

            # Try to get the win text (contains reward details)
            try:
                win_text = page.locator("#win_text")
                if win_text.is_visible(timeout=3000):
                    win_text_content = win_text.text_content()
                    print(f"  Win text: {win_text_content}")
                    if result:
                        result = f"{result} - {win_text_content}"
                    else:
                        result = win_text_content
            except Exception as e:
                print(f"  Could not get win text: {e}")

            if result is None:
                print("Could not capture result text (spin may still have succeeded)")
            else:
                print(f"SUCCESS: Spin result: {result}")

            # Always take a final screenshot
            page.screenshot(path=SCREENSHOTS_DIR / "spin_result.png")
            print(f"Screenshot saved to {SCREENSHOTS_DIR / 'spin_result.png'}")

            # Pause for inspection if requested
            if pause > 0:
                print(f"Pausing for {pause} seconds before closing browser...")
                page.wait_for_timeout(pause * 1000)

            return result

        except PlaywrightTimeout as e:
            print(f"Timeout error: {e}")
            page.screenshot(path=SCREENSHOTS_DIR / "error_timeout.png")
            raise
        except Exception as e:
            print(f"Error during spin: {e}")
            page.screenshot(path=SCREENSHOTS_DIR / "error_unknown.png")
            raise
        finally:
            browser.close()


def main():
    parser = argparse.ArgumentParser(description="Lucky Paw Spin Automation")
    parser.add_argument(
        "--test",
        action="store_true",
        help="Use a random email for testing instead of the configured email",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Force spin regardless of time elapsed",
    )
    parser.add_argument(
        "--no-headless",
        action="store_true",
        help="Run browser with visible window (for debugging)",
    )
    parser.add_argument(
        "--debug",
        action="store_true",
        help="Enable debug mode with screenshots at each step",
    )
    parser.add_argument(
        "--pause",
        type=int,
        default=0,
        help="Seconds to wait before closing browser (for manual inspection)",
    )
    args = parser.parse_args()

    # Determine email to use
    if args.test:
        email = generate_random_email()
        print(f"TEST MODE: Using random email: {email}")
    else:
        email = os.environ.get("FWP_EMAIL")
        if not email:
            print("Error: FWP_EMAIL environment variable not set")
            print("Set it with: export FWP_EMAIL='your-email@example.com'")
            print("Or use --test flag for testing with random email")
            sys.exit(1)

    # Check if we should spin
    if not args.force and not args.test:
        if not should_spin():
            print("Skipping spin - not enough time has passed")
            sys.exit(0)

    # Perform the spin
    try:
        result = perform_spin(
            email=email,
            headless=not args.no_headless,
            debug=args.debug,
            pause=args.pause,
        )

        # Save the spin time (only for non-test runs)
        if not args.test:
            save_last_spin(result)
            print("SPIN_PERFORMED=true")
        else:
            print("TEST MODE: Not saving spin time")

        print("Spin completed successfully!")

    except Exception as e:
        error_msg = str(e)
        if "not available" in error_msg.lower():
            # Wheel not available is not an error - just means we need to wait
            print(f"Wheel not ready: {error_msg}")
            print("WHEEL_NOT_AVAILABLE=true")
            sys.exit(0)  # Exit cleanly, not an error
        else:
            print(f"Spin failed: {error_msg}")
            sys.exit(1)


if __name__ == "__main__":
    main()
