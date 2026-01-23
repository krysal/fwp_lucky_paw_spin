# Lucky Paw Spin Automation Plan

## Overview

Automate the daily Lucky Paw Spin using GitHub Actions running every 30 minutes, with a rolling 24.5-hour interval tracked via a timestamp file.

## Files Structure

```
fwp_lucky_paw_spin/
├── .github/
│   └── workflows/
│       └── spin.yml        # GitHub Actions workflow (runs every 30 min)
├── spin.py                 # Main Playwright automation script
├── last_spin.json          # Stores last successful spin timestamp
├── pyproject.toml          # Python dependencies (uv)
└── .gitignore              # Ignore local artifacts
```

## File Details

### 1. `.github/workflows/spin.yml`
- Cron schedule: every 30 minutes (`*/30 * * * *`)
- Sets up Python and uv
- Installs Playwright and Chromium browser
- Runs `spin.py`
- If a spin occurred, commits the updated `last_spin.json` back to the repo
- Uses GitHub Secret `FWP_EMAIL` for your email

### 2. `spin.py`
- Reads `last_spin.json` to get last spin timestamp
- If 24.5 hours haven't passed, exits early (no action)
- If 24.5+ hours have passed:
  - Launches headless Chromium via Playwright
  - Navigates to `https://ferriswheelpress.com/pages/loyalty-lounge`
  - Waits for Rivo widget to load
  - Enters email and clicks spin
  - Logs the result
  - Updates `last_spin.json` with current timestamp

### 3. `last_spin.json`
```json
{
  "last_spin": null,
  "result": null
}
```

### 4. `pyproject.toml`
- Dependencies: `playwright`
- Python version: 3.12+

## GitHub Setup Required

1. Create repository secret `FWP_EMAIL` with value `ferriswheelpress.store@krysal.co`
2. Enable "Read and write permissions" for Actions in repo settings (to allow committing `last_spin.json`)

## Resource Usage

- ~1,440 runs/month (every 30 min)
- Each run takes ~1-2 minutes max
- Well within GitHub Actions free tier (2,000 min/month)
