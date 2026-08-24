# LHDN Automation — Functionality Overview

A desktop app that automates submitting eStamp duty forms on
`stamps.hasil.gov.my` via data from a SharePoint list. It has a
Tkinter GUI ([gui.py](gui.py)) on top of the automation/backend logic
([lhdn_automation.py](lhdn_automation.py)).

## Installation
Download the latest .zip file under `Releases`. After  mn, unzipping, ensure that the other contents of the .zip file (particularly a folder named `_internal`) are next to the .exe file before running.
You may get a Windows Defender notification. If this happens, click on "More info" and a new "Run anyway" button should appear. After that, the program should run normally.


## First launch

1. **Missing configuration check** — if necessary config data (e.g. tenant/client SharePoint site/list IDs)
   can't be resolved, an error box will flag the missing variables.
   In practice this should never happen; these values are preconfigured by default
   (see [`.envexample`](.envexample) and *Configuration* below).
2. **Sign in with Microsoft** — a browser window opens the
   Microsoft login page for the user's work account (delegated
   MSAL OAuth via [auth.py](auth.py)). The session is cached
   afterwards, so this only happens
   again if the cache is cleared or the session expires.
3. **eStamp sign-in screen** — Shows an input form for MyTax credentials during first run;
   later runs show a profile picker if more than one profile has been saved.
   Profiles can be renamed or deleted from this screen. Saved profiles are
   encrypted (Windows DPAPI, see *Security* below) — see
   [profiles.py](profiles.py).
   
  <img width="207" height="212" alt="image" src="https://github.com/user-attachments/assets/65bb4f28-b5a2-4cee-a3f7-db34ec405275" /><br>
  ###### Example profile picker screen with 2 saved profiles

Only after both authentication steps succeed does the main window appear.

## Main window

### Status bar

<img width="551" height="34" alt="image" src="https://github.com/user-attachments/assets/3e691626-2de4-45c1-a7e8-7909d2c73d71" /><br>
###### Status bar with polling set to Off

| Control | Function |
|---|---|
| **Signed in as: *name* → Switch** | Re-opens the profile picker to switch profiles without restarting the app. |
| **Switch Microsoft Account** | Signs out of the cached Microsoft session and re-triggers sign-in. |
| **Background polling: ● *status* → Enable** | See *Background polling* below. |
| **Close Browser** | Closes the most recently opened Selenium browser window and frees system resources. |

### Background polling

A passive service that runs independent of the open Selenium browser to autofill missing data from list entries. A headless (hidden)
browser window will open upon detecting an entry with specific missing data.

- **Starts automatically** when the app opens, so newly queued entries are checked and autofilled before automation
- **Auto-stops after 10 seconds** (`POLL_AUTO_STOP_SECONDS` in `gui.py`) and
  switches the checkbox off — polling does not run unattended indefinitely.
  The user will have to re-enable it if necessary. The same 10-second window applies even if polling starts manually.
- Each cycle (`poll_for_changes`, every `POLL_INTERVAL` = 30s while enabled):
  1. **Autofills missing company numbers** — any entry with
     `Status` in `Pending` / `Awaiting Review` that is missing its
     `OldCompanyNumber`/`NewCompanyNumber` will undergo a CTOS lookup by client name
     or whichever number is present. Only `Pending` entries have their
     `Status` advanced (→ `Awaiting Review` on success, → `Failed` on
     error).
  2. **Stale `Processing` observation** — if `process_approved_item` crashes,
     hangs, or the app gets force-closed mid-run, an entry can get stuck at
     `Status = Processing` forever. Each poll cycle checks every item's `Modified`
     timestamp; anything still `Processing` after more than 10 minutes 
     (`STALE_PROCESSING_TIMEOUT`) gets marked as `Failed` automatically.

### Edit tab

<img width="674" height="547" alt="image" src="https://github.com/user-attachments/assets/5225f13c-b944-4d69-bedc-3aee1bafa60e" /><br>
###### The Edit tab showing example SharePoint entries

Lists every SharePoint entry with the `Status`: `Approved`/`Failed` and lets
the user run the automation for the selected entry.

- **Refresh List** — re-fetches the list (also runs once automatically at
  startup).
- **Process Selected Entry** — confirms, then runs
  `process_approved_item` in a **visible** browser: parses the entry's
  JSON, sets `Status = Processing`, runs the automation script
  (`main_automate_form`/`main_flow`), then sets `Status = Completed` or
  `Failed`. **Only one Edit/Cleanup automation can run at a time**.

### Cleanup tab

<img width="659" height="166" alt="image" src="https://github.com/user-attachments/assets/8852338f-9877-4b36-bc27-bb651b272337" /><br>
###### The Cleanup tab with today's date

Cancels test draft entries submitted on a given date —
used for cleaning up test submissions, not part of the normal workflow.

- **Date** field (dd/mm/yyyy), defaults to today.
- **Run Cleanup** — first click: opens a new visible browser, signs in,
  and repeatedly scans the listing for a matching entry. If a Cleanup browser from
  earlier is **still open**, clicking again **reuses it** and
  rechecks the table. Each match found is **highlighted directly in the browser** (yellow
  background, red outline) and held there. To continue, select **Continue/Abort**
  in the confirmation banner.

<img width="1228" height="193" alt="image" src="https://github.com/user-attachments/assets/751b6484-9997-4bb2-8922-9304c89f31f0" />

###### Example of a highlighted entry

<img width="1184" height="166" alt="image" src="https://github.com/user-attachments/assets/a6036154-2720-4e03-943e-35b8caa3dd5f" />

###### The inline banner showing options for the matched entry

### Exception handling

The program may occasionally run into errors (these could be non-fatal — in which a simple retry would be sufficient, or fatal — whereby a catastrophic
error involving the program flow/logic has occurred).
Non-fatal errors can be fixed by clicking on **Continue**. Fatal errors may occur due to fundamental website changes or incompatible/incomplete data drawn
from the SharePoint entry. Details of the error will be shown in the log.

If you are unsure, note that the program retries up to three times, including the initial attempt before the error occurs. If all three 
attempts fail, the program has encountered a fatal error. Fatal errors should be reported if they remain unresolved for more than one hour.

<img width="670" height="544" alt="image" src="https://github.com/user-attachments/assets/5b9cec82-0fd5-46b2-a804-7c2aa8d7bdc7" /><br>
###### Edit page with confirmation banner after encountering an error. Note the detailed log at the bottom


## Security

- **MyTax Credentials**: encrypted at rest with Windows DPAPI
  (`secure_storage.py`), scoped to the current Windows user account — 
  no additional credentials for this app are required, and the ciphertext is
  unreadable on a different machine or Windows login.
- **Microsoft/SharePoint access**: delegated, per-user OAuth (`auth.py`),
  — every SharePoint write is traceable to the
  signed-in user. Should be reliant on the delegated `Sites.Selected` Graph permission (app access scoped to
  sites an Entra admin explicitly grants).

## Settings 

**Configuration → Edit Settings...** opens a menu for the environment variables the user may reasonably want to adjust — poll interval, poll
auto-stop duration, element wait timeout, HTTP request timeout/retries/
retry delay, and the stale `Processing` threshold (see `gui.py`'s
`SETTINGS_SCHEMA`). Saving applies each value immediately (no restart
needed) and persists it to `%APPDATA%\LHDNAutomation\settings.json`.

<img width="674" height="44" alt="image" src="https://github.com/user-attachments/assets/407d8324-8a5b-4055-85fa-7961b3d9696c" /><br>
###### The configuration header button dropdown

<img width="476" height="266" alt="image" src="https://github.com/user-attachments/assets/e587f98f-c3bc-41b9-948d-522c855e48fd" /><br>
###### The configuration menu with default values

Excludes preset variables like SharePoint/tenant
IDs and the eStamp portal URL (see *Configuration*
below).

## Configuration

Org-wide values (tenant/client IDs, SharePoint site/list IDs, the eStamping
base URL) are **preset into `lhdn_automation.py` as defaults** — **no `.env` file is needed**. A real `.env` (see
`.envexample`) is only required if you want to override a default — e.g.
pointing a dev/test build at a different tenant or site.

## Distribution

[build.ps1](build.ps1) builds a standalone Windows app via PyInstaller,
inside a disposable virtualenv (to ensure the bundle is not bloated by packages already in the environment during building) and packages the
result into a single `dist\LHDN-Automation.zip` — no additional `pip install` required.

## File reference

| File | Role |
|---|---|
| `gui.py` | Tkinter frontend — all windows, menus, and background threads |
| `lhdn_automation.py` | Automation/backend logic — Selenium form-filling, SharePoint/Graph calls, polling |
| `auth.py` | Delegated Microsoft sign-in (MSAL), token caching |
| `profiles.py` | Encrypted local storage for eStamp IC/password profiles |
| `secure_storage.py` | Shared Windows DPAPI encrypt/decrypt helpers |
| `build.ps1` | Packages the app into a distributable zip |
| `settings.py` | Plain JSON persistence for user-customisable app settings |
| `requirements.txt` | Runtime Python dependencies |
| `.envexample` | Optional override template for the config data |
