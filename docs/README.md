# LHDN Automation — Functionality Overview

A desktop app that automates submitting E-Stamping forms on
`ESTAMP_PORTAL_URL` via data from a SharePoint list. It has a
Tkinter GUI ([app.py](../src/lhdn_automation/gui/app.py)) on top of the
automation/backend logic, split across the package
[src/lhdn_automation](../src/lhdn_automation).

## Installation
Download the latest .zip file under `Releases`. After unzipping, ensure that the other contents of the .zip file (particularly a folder named `_internal`) are next to the .exe file before running.
You may get a Windows Defender notification. If this happens, click on "More info" and a new "Run anyway" button should appear. After that, the program should run normally.

## First launch

1. **Missing configuration check** — If necessary config data (e.g. tenant/client SharePoint site/list IDs)
   can't be resolved, an error box will flag the missing variables.
   In practice this should never happen; these values are preconfigured by default
   (see [`.envexample`](../src/lhdn_automation/config/.envexample) and *Configuration* below).   
    1. **Default Firm Data** — Upon launch, the program checks if the necessary data required by the online form is present. If it isn't, a menu will appear. Settings can be exported and imported from this menu (see [settings.py](../lhdn_automation/config/settings.py)).
    
2. **Microsoft sign in** — A browser window opens the
   Microsoft login page for the user's work account (delegated
   MSAL OAuth via [auth.py](../src/lhdn_automation/authentication/auth.py)). The session is cached
   afterwards, so this only happens
   again if the cache is cleared or the session expires.
3. **Sign in screen** — Shows an input form for credentials during first run;
   later runs show a profile picker if more than one profile has been saved.
   Profiles can be renamed or deleted from this screen. Saved profiles are
   encrypted (Windows DPAPI, see *Security* below) and
   [profiles.py](../src/lhdn_automation/authentication/profiles.py).
   
<img width="420" height="427" alt="image" src="https://github.com/user-attachments/assets/b0e3d14c-9bb9-4e63-ba65-4d4870a25d58" /><br>
  ###### Example profile picker screen with 2 saved profiles

  <img width="278" height="222" alt="image" src="https://github.com/user-attachments/assets/e8d7cf26-101b-42b1-858c-51d118adcf55" /><br>
  ###### Profile setup menu

Only **after** both authentication steps succeed will the main window appear.

## Main window

### Status bar

<img width="1378" height="64" alt="image" src="https://github.com/user-attachments/assets/f2bf485f-a7bb-434f-bbdb-a0808e746151" /><br>
##### Status bar with polling set to On

| Control | Function |
|---|---|
| **Signed in as: *name*   [Switch]** | Re-opens the profile picker to switch profiles without restarting the app. |
| **Switch Microsoft Account** | Signs out of the cached Microsoft session and re-triggers sign-in. |
| **Background polling: ● *status* → Enable** | See *Background polling for SharePoint entries* below. |
| **Close Browser** | Closes the most recently opened Selenium browser window and frees system resources. Same as closing the browser instance normally but can be used when browser is unresponsive |

### Background polling for SharePoint entries

A passive service that runs independent of the open Selenium browser to autofill missing data from list entries. A headless browser window will open upon detecting an entry with specific missing data.

- It **starts automatically** when the app opens, so newly queued entries are checked and autofilled before automation
- **Auto-stops after** (`POLL_AUTO_STOP_SECONDS` in
  [constants.py](../src/lhdn_automation/config/constants.py)) **seconds** — polling does not run unattended indefinitely.    
  * The user will have to re-enable it if necessary. The same interval applies **even if polling starts manually**.
- Each cycle (see `poll_for_changes` in [polling.py](../src/lhdn_automation/sharepoint/polling.py), every `POLL_INTERVAL` while enabled):
  1. **Autofills missing company numbers** — any entry with
     `Status` in `Pending` / `Awaiting Review` that is missing its
     `OldCompanyNumber`/`NewCompanyNumber` will undergo a CTOS lookup by client name
     or whichever number is present. Only `Pending` entries have their
     `Status` advanced (→ `Awaiting Review` on success, → `Failed` on
     error).
  2. **Stale `Processing` observation** — if `process_approved_item` crashes,
     hangs, or the app gets force-closed mid-run, an entry can get stuck at
     `Status = Processing`. Each poll cycle checks every item's `Modified`
     timestamp. Anything still `Processing` after more than
     `STALE_PROCESSING_TIMEOUT` minutes gets marked as `Failed` automatically.

### Edit tab

<img width="634" height="516" alt="image" src="https://github.com/user-attachments/assets/d6c9f771-7de1-4e65-a47e-37785ed6b056" /><br>
###### The Edit tab showing example SharePoint entries

Lists every SharePoint entry with the `Status`: `Approved`/`Failed` and lets
the user run the automation for the selected entry.

- **Refresh List** — re-fetches the list (also runs once automatically at
  startup).
- **Process Selected Entry** — confirms, then runs
  `process_approved_item` (see [processing.py](../src/lhdn_automation/sharepoint/processing.py)) in a **visible** browser: parses the entry's
  JSON, sets `Status = Processing`, runs the automation script
  (`main_automate_form`/`main_flow` in [orchestrator.py](../src/lhdn_automation/browser/forms/orchestrator.py)), then sets `Status = Completed` or
  `Failed`. **Only one Edit/Cleanup automation can run at a time**.

### Cleanup tab

<img width="655" height="164" alt="image" src="https://github.com/user-attachments/assets/8db05d36-7781-4cbb-8ce1-561276278e77" /><br>
###### The Cleanup tab with today's date

Cancels test draft entries submitted on a given date —
used for cleaning up test submissions, not part of the normal workflow.

- **Date** field (dd/mm/yyyy), defaults to today.
- **Run Cleanup** — first click: opens a new visible browser, signs in,
  and repeatedly scans the listing for a matching entry, paging through
  every page of the table until a match is found or
  the listing is exhausted. If a Cleanup browser from
  earlier is **still open**, clicking Run Cleanup again **reuses it** and
  rechecks the table. Each match found is **highlighted directly in the browser** (yellow
  background, red outline) and held there. To continue, select **Continue/Abort**
  in the confirmation banner.

<img width="1895" height="294" alt="image" src="https://github.com/user-attachments/assets/bf3b173b-ad0e-4ffa-b080-6fa42ca4a752" />

###### Example of a highlighted entry

<img width="1889" height="239" alt="image" src="https://github.com/user-attachments/assets/1399802f-6282-4b20-b8f0-35a04df671f8" />

###### The inline banner showing options for the matched entry

## Exception handling

The program may occasionally run into errors (these could be non-fatal — in which a simple retry would be sufficient, or fatal — whereby a catastrophic
error involving the program flow/logic has occurred).
Non-fatal errors can be fixed by clicking on **Continue**, which causes the program to reattempt automation. Fatal errors may occur due to **fundamental website changes or incompatible/incomplete data** drawn from the SharePoint entry. Details of the error will be shown in the **log**.

Note that the program retries up to three times, including the initial attempt before the error occurs. If all three
attempts fail, the program has encountered a fatal error. Fatal errors should be reported if they remain unresolved for more than one hour.
 
* **Fallback behaviour** — The LHDN website is known for removing options from their State/Office dropdowns to more evenly distribute workflow between branches. The program can handles this by featuring a priority list when the highest priority state cannot be found (see [settings.py](../lhdn_automation/config/settings.py) and *Configuration* below)

<img width="1017" height="817" alt="image" src="https://github.com/user-attachments/assets/738c75ba-4052-4db3-9280-2319d3d7b351" /><br>
###### Edit page with confirmation banner after encountering an error. Note the detailed log at the bottom

## Security

- **MyTax Credentials** — encrypted at rest with Windows DPAPI
  ([secure_storage.py](../src/lhdn_automation/authentication/secure_storage.py)), scoped to the current Windows user account —
  no additional credentials for this app are required, and the ciphertext is
  unreadable on a different machine or Windows login.
- **Microsoft/SharePoint access** — delegated, per-user OAuth ([auth.py](../src/lhdn_automation/authentication/auth.py)),
  — every SharePoint write is traceable to the signed-in user. Should be reliant on the delegated `Sites.Selected` Graph permission (app access scoped to sites granted by an Entra admin).

## Configuration
### Application settings

<img width="315" height="234" alt="image" src="https://github.com/user-attachments/assets/43508757-c2ac-459e-af49-2630096f7b8c" /><br>
###### The configuration header button dropdown

**Edit Settings...**: opens a menu for variables the user may reasonably want to adjust — poll interval, poll
auto-stop duration, element wait timeout, HTTP request timeout/retries/
retry delay, and the stale `Processing` threshold (see [app.py](../src/lhdn_automation/gui/app.py)'s
`SETTINGS_SCHEMA`). Saving applies each value immediately (no restart
needed) and persists it to `%APPDATA%\LHDNAutomation\settings.json`.

<img width="951" height="593" alt="image" src="https://github.com/user-attachments/assets/2e8f967e-19d1-4a25-8819-09346085eb36" /><br>
###### The settings menu with default values

**Edit SharePoint Configuration...**: opens a menu for adjusting SharePoint/URL variables. This includes host name, site path, list names and stamping portal URL.

<img width="386" height="326" alt="image" src="https://github.com/user-attachments/assets/ab832ce7-0e53-4588-a8d1-f0e949ca751b" /><br>

###### The SharePoint Configuration menu    

**Edit Company Details...**: opens a menu for amending the default company data that will be used for stamping. This menu has two sections:    
  1. Company Data — features fields that allows the user to customise company data.
  2. City/State priority — features 5 dropdown boxes for the problem stated above in *Exception Handling* whereby multiple stamping office locations can be chosen in the event that one of the options is missing from the website.

<img width="329" height="543" alt="image" src="https://github.com/user-attachments/assets/5d3352b2-e157-4a55-aecc-b347ebc64297" /><br>

###### The Company Details menu. Note that certain fields are dropdown menus.

Settings not mentioned above (like SharePoint Site/Tenant IDs and secrets) are required to be stored in a real `.env` file (see
[`.envexample`](../src/lhdn_automation/config/.envexample)). The program will warn you if not all `.env` variables are present.

## Distribution

[build.ps1](../src/lhdn_automation/tools/build.ps1) builds a standalone Windows app via PyInstaller,
inside a disposable virtualenv (to ensure the bundle is not bloated by packages already in the environment during building) and packages the
result into a single `dist\LHDN-Automation.zip` — no additional `pip install` required.

### Export / Import Settings

**Export Settings...** writes the current `settings.json`
contents to a `settings_export.json` file next to `.env`, so it can be
handed to another install or committed alongside the rest of the app's
local config.

**Import Settings...** opens a file browser to pick any
exported settings JSON file, then merges it into `settings.json` the same
way **Edit Settings...** does, and re-applies settings, SharePoint
configuration, and company details immediately. As with **Edit
Settings...**, tenant/client IDs and other preset variables are never part
of the export.

## File reference

| File | Role |
|---|---|
| `gui/app.py` | Tkinter frontend — all windows, menus, and background threads |
| `browser/forms/orchestrator.py` | Automation/backend entry points (`main_flow`, `main_automate_form`) — Selenium form-filling |
| `browser/cleanup.py` | Cleanup tab automation — scans and cancels matching test entries across every listing page |
| `sharepoint/processing.py` | Runs `process_approved_item` for the Edit tab |
| `sharepoint/polling.py` | Background polling (`poll_for_changes`) |
| `sharepoint/client.py` | SharePoint/Graph API calls |
| `authentication/auth.py` | Delegated Microsoft sign-in (MSAL), token caching |
| `authentication/profiles.py` | Encrypted local storage for eStamp IC/password profiles |
| `authentication/secure_storage.py` | Shared Windows DPAPI encrypt/decrypt helpers |
| `tools/build.ps1` | Packages the app into a distributable zip |
| `config/settings.py` | Plain JSON persistence for user-customisable app settings, plus export/import |
| `requirements.txt` | Runtime Python dependencies |
| `config/.envexample` | Optional override template for the config data |


