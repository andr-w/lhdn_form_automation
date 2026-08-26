import dataclasses
import logging
import os
import queue
import sys
import threading
import webbrowser
import tkinter as tk
from datetime import date, timedelta
from tkinter import filedialog, messagebox, scrolledtext, simpledialog, ttk

from lhdn_automation.authentication import auth, profiles
from lhdn_automation import models, exceptions, interaction
from lhdn_automation.config import constants, settings, validation
from lhdn_automation.browser import driver, cleanup
from lhdn_automation.sharepoint import client as sharepoint_client, token as sharepoint_token, audit_log, polling, processing
from lhdn_automation.update import updater

if sys.platform == "win32":
    import ctypes
    from ctypes import wintypes

    class _FLASHWINFO(ctypes.Structure):
        _fields_ = [
            ("cbSize", wintypes.UINT), # size of structure in bytes
            ("hwnd", wintypes.HWND),  # window handle
            ("dwFlags", wintypes.DWORD), # double word that influences window flash behaviour
            ("uCount", wintypes.UINT), # unsigned int. determines the number of times the window flashes
            ("dwTimeout", wintypes.DWORD), # dounle word. rate of flashing in ms
        ]

    # windows hex flags
    _FLASHW_STOP = 0 
    _FLASHW_ALL = 0x00000003 # flash both the window caption and taskbar button
    _FLASHW_TIMERNOFG = 0x0000000C  # flash continuously until the window becomes foreground
    _GA_ROOT = 2

    def _root_hwnd(window):
        return ctypes.windll.user32.GetAncestor(window.winfo_id(), _GA_ROOT)

def flash_taskbar_icon(window, count=8):
    if sys.platform != "win32":
        return
    try:
        info = _FLASHWINFO(ctypes.sizeof(_FLASHWINFO), _root_hwnd(window), _FLASHW_ALL | _FLASHW_TIMERNOFG, count, 0)
        ctypes.windll.user32.FlashWindowEx(ctypes.byref(info))
    except Exception:
        logging.debug("Unable to flash taskbar icon", exc_info=True)


def stop_taskbar_flash(window):
    if sys.platform != "win32":
        return
    try:
        info = _FLASHWINFO(ctypes.sizeof(_FLASHWINFO), _root_hwnd(window), _FLASHW_STOP, 0, 0)
        ctypes.windll.user32.FlashWindowEx(ctypes.byref(info))
    except Exception:
        pass


class QueueLogHandler(logging.Handler):
    """Pushes formatted log records into a queue for the Tk main loop to drain."""

    def __init__(self, log_queue):
        super().__init__()
        self.log_queue = log_queue

    def emit(self, record):
        self.log_queue.put(self.format(record))


class PauseBanner(ttk.Frame):

    def __init__(self, parent):
        super().__init__(parent, padding=10, relief="ridge", borderwidth=1)
        self._message_var = tk.StringVar()
        self._on_resolve = None

        ttk.Label(self, text="Paused:", font=("", 9, "bold")).pack(side="left", padx=(0, 8))
        ttk.Label(self, textvariable=self._message_var, wraplength=520, justify="left").pack(
            side="left", fill="x", expand=True
        )

        button_row = ttk.Frame(self)
        button_row.pack(side="right")
        self.continue_btn = ttk.Button(button_row, text="Continue", command=lambda: self._resolve(True))
        self.continue_btn.pack(side="left", padx=(0, 6))
        self.abort_btn = ttk.Button(button_row, text="Abort", command=lambda: self._resolve(False))
        self.abort_btn.pack(side="left")

    def show(self, message, allow_abort, on_resolve, before_widget):
        self._message_var.set(message)
        self._on_resolve = on_resolve
        self.abort_btn.config(state="normal" if allow_abort else "disabled")
        self.pack(fill="x", padx=8, pady=(8, 0), before=before_widget)

    def _resolve(self, should_continue):
        callback = self._on_resolve
        self._on_resolve = None
        self.pack_forget()
        if callback:
            callback(should_continue)


class PauseManager:
    """
    Backs lhdn_automation.PAUSE_HANDLER with the inline PauseBanner instead
    of input(). confirm() is safe to call from a worker thread: it enqueues
    a request and blocks on a threading.Event, while the banner itself is
    only ever touched on the Tk main thread (via root.after polling), since
    Tkinter widgets cannot be touched safely from a background thread.

    on_alert_shown/on_alert_resolved let the caller hook window-level
    attention cues (bring to front, pin on top, flash the taskbar icon)
    without PauseManager needing to know about any of that itself.
    """

    def __init__(self, root, banner, before_widget, on_alert_shown=None, on_alert_resolved=None):
        self.root = root
        self.banner = banner
        self.before_widget = before_widget
        self.on_alert_shown = on_alert_shown
        self.on_alert_resolved = on_alert_resolved
        self._requests = queue.Queue()
        self.root.after(100, self._poll)

    def _poll(self):
        try:
            while True:
                message, allow_abort, event, result = self._requests.get_nowait()
                self._show(message, allow_abort, event, result)
        except queue.Empty:
            pass
        self.root.after(100, self._poll)

    def _show(self, message, allow_abort, event, result):
        def on_resolve(should_continue):
            result["continue"] = should_continue
            event.set()
            if self.on_alert_resolved:
                self.on_alert_resolved()

        self.banner.show(message, allow_abort, on_resolve, self.before_widget)
        if self.on_alert_shown:
            self.on_alert_shown()

    def confirm(self, message, allow_abort=False):
        event = threading.Event()
        result = {"continue": True}
        self._requests.put((message, allow_abort, event, result))
        event.wait()
        if not result["continue"]:
            raise exceptions.AutomationAborted("User aborted during manual pause.")
        return True


class ProfileDialog(tk.Toplevel):
    def __init__(self, root, store):
        super().__init__(root)
        self.store = store
        self.result = None

        self.title("LHDN Automation - Sign in")
        self.resizable(False, False)
        self.transient(root)
        self.protocol("WM_DELETE_WINDOW", self._cancel)

        self._body = ttk.Frame(self, padding=20)
        self._body.pack(fill="both", expand=True)

        profile_list = self.store.list_profiles()
        if profile_list:
            self._build_picker(profile_list)
        else:
            self._build_setup_form(is_first_run=True)

        self.update_idletasks()
        self._center_on(root)
        self.grab_set()
        self.focus_force()

    def _center_on(self, root):
        self.update_idletasks()
        w, h = self.winfo_width(), self.winfo_height()
        root.update_idletasks()
        x = root.winfo_x() + max((root.winfo_width() - w) // 2, 0)
        y = root.winfo_y() + max((root.winfo_height() - h) // 2, 0)
        self.geometry(f"+{max(x, 0)}+{max(y, 0)}")

    def _clear_body(self):
        for child in self._body.winfo_children():
            child.destroy()

    # ---- Picker screen (2+ runs, once a profile exists) ----

    def _build_picker(self, profile_list):
        self._clear_body()
        ttk.Label(self._body, text="Who's using LHDN Automation?", font=("", 11, "bold")).pack(
            anchor="w", pady=(0, 10)
        )

        self._profile_ids = [pid for pid, _ in profile_list]
        self._listbox = tk.Listbox(self._body, height=6, width=38, exportselection=False)
        for _, name in profile_list:
            self._listbox.insert("end", name)
        self._listbox.pack(fill="x")
        self._listbox.bind("<Double-Button-1>", lambda e: self._use_selected())

        last_used = self.store.get_last_used()
        default_index = self._profile_ids.index(last_used) if last_used in self._profile_ids else 0
        self._listbox.selection_set(default_index)
        self._listbox.see(default_index)

        btn_row = ttk.Frame(self._body)
        btn_row.pack(fill="x", pady=(12, 0))
        ttk.Button(btn_row, text="Continue", command=self._use_selected).pack(side="left")
        ttk.Button(btn_row, text="Rename", command=self._rename_selected).pack(side="left", padx=(8, 0))
        ttk.Button(btn_row, text="Delete", command=self._delete_selected).pack(side="left", padx=(8, 0))

        ttk.Separator(self._body, orient="horizontal").pack(fill="x", pady=12)
        ttk.Button(
            self._body, text="+ Add another person", command=lambda: self._build_setup_form(is_first_run=False)
        ).pack(anchor="w")

    def _selected_profile_id(self):
        selection = self._listbox.curselection()
        return self._profile_ids[selection[0]] if selection else None

    def _use_selected(self):
        profile_id = self._selected_profile_id()
        if not profile_id:
            messagebox.showinfo("Select a profile", "Choose a profile from the list first.", parent=self)
            return
        name = self._listbox.get(self._listbox.curselection()[0])
        ic, password = self.store.get_credentials(profile_id)
        self.store.set_last_used(profile_id)
        self.result = (name, ic, password)
        self.destroy()

    def _rename_selected(self):
        profile_id = self._selected_profile_id()
        if not profile_id:
            return
        current_name = self._listbox.get(self._listbox.curselection()[0])
        new_name = simpledialog.askstring(
            "Rename profile", "New name:", initialvalue=current_name, parent=self
        )
        if new_name and new_name.strip():
            self.store.rename_profile(profile_id, new_name.strip())
            self._build_picker(self.store.list_profiles())

    def _delete_selected(self):
        profile_id = self._selected_profile_id()
        if not profile_id:
            return
        name = self._listbox.get(self._listbox.curselection()[0])
        if not messagebox.askyesno("Delete profile", f"Delete the saved profile '{name}'?", parent=self):
            return
        self.store.delete_profile(profile_id)
        remaining = self.store.list_profiles()
        if remaining:
            self._build_picker(remaining)
        else:
            self._build_setup_form(is_first_run=True)

    # ---- Setup form (first run, or adding another person) ----

    def _build_setup_form(self, is_first_run):
        self._clear_body()
        heading = "Welcome! Let's set up your LHDN login." if is_first_run else "Add another person"
        ttk.Label(self._body, text=heading, font=("", 11, "bold")).pack(anchor="w", pady=(0, 4))
        ttk.Label(
            self._body,
            text="This is your own IC number and eStamp password - it stays on this computer only.",
            wraplength=340,
            justify="left",
            foreground="gray",
        ).pack(anchor="w", pady=(0, 14))

        form = ttk.Frame(self._body)
        form.pack(fill="x")

        ttk.Label(form, text="Your name:").grid(row=0, column=0, sticky="w", pady=4)
        name_var = tk.StringVar()
        ttk.Entry(form, textvariable=name_var, width=28).grid(row=0, column=1, pady=4)

        ttk.Label(form, text="IC Number:").grid(row=1, column=0, sticky="w", pady=4)
        ic_var = tk.StringVar()
        ttk.Entry(form, textvariable=ic_var, width=28).grid(row=1, column=1, pady=4)

        ttk.Label(form, text="eStamp Password:").grid(row=2, column=0, sticky="w", pady=4)
        password_var = tk.StringVar()
        ttk.Entry(form, textvariable=password_var, width=28, show="*").grid(row=2, column=1, pady=4)

        remember_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(
            self._body, text="Remember me on this computer (encrypted)", variable=remember_var
        ).pack(anchor="w", pady=(10, 0))

        btn_row = ttk.Frame(self._body)
        btn_row.pack(fill="x", pady=(14, 0))

        def submit():
            ic = ic_var.get().strip()
            password = password_var.get()
            if not ic or not password:
                messagebox.showerror(
                    "Missing info", "Please enter both your IC number and password.", parent=self
                )
                return
            name = name_var.get().strip() or ic
            if remember_var.get():
                self.store.add_profile(name, ic, password)
            self.result = (name, ic, password)
            self.destroy()

        ttk.Button(btn_row, text="Continue", command=submit).pack(side="left")
        if not is_first_run:
            ttk.Button(
                btn_row, text="Back", command=lambda: self._build_picker(self.store.list_profiles())
            ).pack(side="left", padx=(8, 0))

    def _cancel(self):
        self.result = None
        self.destroy()


def sign_in_with_microsoft(root, first_run):
    """
    Ensures a valid delegated Microsoft session before anything talks to
    Graph/SharePoint. Silent/cached almost always, except the very first
    run (or an explicit "Switch Microsoft Account") where MSAL opens the
    system browser to the real Microsoft sign-in page - shown with a brief
    heads-up first so a non-technical coworker isn't startled by a browser
    tab opening out of nowhere.
    """
    if first_run or not auth.has_cached_account(constants.TENANT_ID, constants.CLIENT_ID):
        messagebox.showinfo(
            "Sign in with Microsoft",
            "Your browser will open so you can sign in with your usual Microsoft work account.\n\n"
            "This lets the app read and update the SharePoint list on your behalf.",
            parent=root,
        )
    auth.get_delegated_token(constants.TENANT_ID, constants.CLIENT_ID)


# How long background polling stays on before switching itself back off,
# whether it was started automatically at app launch or manually via the
# checkbox. Requires an operator to notice and re-enable it afterward,
# rather than running unattended indefinitely.
POLL_AUTO_STOP_SECONDS = 10

def _set_poll_auto_stop_seconds(value):
    global POLL_AUTO_STOP_SECONDS
    POLL_AUTO_STOP_SECONDS = value


# Tunable operational parameters an operator might reasonably want to
# adjust - polling cadence, wait/retry timeouts, max form-automation
# retries. SharePoint site/list names and the eStamp base URL live in the
# separate SHAREPOINT_CONFIG_SCHEMA/SharePointConfigDialog below instead,
# since they're strings rather than plain positive integers. Both schemas
# deliberately exclude anything identifying or sensitive - SharePoint site
# ID, list ID, tenant/client ID, and credentials stay either required org
# config (lhdn_automation.py's env-var-only values, see validate_runtime_config)
# or per-user encrypted profiles (profiles.py), never exposed in either
# settings screen.
#
# Each "set" writes directly onto the live module global it corresponds
# to, so a change here takes effect immediately - this only works because
# every place that reads these values does so at call time (inside a
# function body), not as a bound default parameter value captured once at
# import; request_with_retries was refactored for exactly this reason.
SETTINGS_SCHEMA = [
    {
        "key": "poll_interval",
        "label": "Poll interval",
        "unit": "seconds",
        "description": "How often a poll cycle runs while background polling is enabled.",
        "get": lambda: constants.POLL_INTERVAL,
        "set": lambda v: setattr(constants, "POLL_INTERVAL", v),
    },
    {
        "key": "poll_auto_stop_seconds",
        "label": "Poll auto-stop duration",
        "unit": "seconds",
        "description": "How long polling stays on before switching itself back off.",
        "get": lambda: POLL_AUTO_STOP_SECONDS,
        "set": _set_poll_auto_stop_seconds,
    },
    {
        "key": "wait_time",
        "label": "Element wait timeout",
        "unit": "seconds",
        "description": "Default timeout waiting for a page element before giving up.",
        "get": lambda: constants.WAIT_TIME,
        "set": lambda v: setattr(constants, "WAIT_TIME", v),
    },
    {
        "key": "request_timeout",
        "label": "HTTP request timeout",
        "unit": "seconds",
        "description": "Timeout for SharePoint/Graph API calls.",
        "get": lambda: constants.REQUEST_TIMEOUT,
        "set": lambda v: setattr(constants, "REQUEST_TIMEOUT", v),
    },
    {
        "key": "request_retries",
        "label": "HTTP request retries",
        "unit": "attempts",
        "description": "Number of attempts for a failed SharePoint/Graph API call.",
        "get": lambda: constants.REQUEST_RETRIES,
        "set": lambda v: setattr(constants, "REQUEST_RETRIES", v),
    },
    {
        "key": "request_retry_delay",
        "label": "HTTP retry delay",
        "unit": "seconds",
        "description": "Delay between retry attempts for a failed API call.",
        "get": lambda: constants.REQUEST_RETRY_DELAY ,
        "set": lambda v: setattr(constants, "REQUEST_RETRY_DELAY", v),
    },
    {
        "key": "stale_processing_minutes",
        "label": "Stale 'Processing' timeout",
        "unit": "minutes",
        "description": "How long an entry can sit at Status=Processing before being marked Failed.",
        "get": lambda: int(constants.STALE_PROCESSING_TIMEOUT.total_seconds() // 60),
        "set": lambda v: setattr(constants, "STALE_PROCESSING_TIMEOUT", timedelta(minutes=v)),
    },
    {
        "key": "max_retry_attempts",
        "label": "Max retry attempts",
        "unit": "attempts",
        "description": "How many times the eStamp form automation retries before marking an entry Failed.",
        "get": lambda: constants.MAX_RETRY_ATTEMPTS,
        "set": lambda v: setattr(constants, "MAX_RETRY_ATTEMPTS", v),
    },
]


# Non-numeric SharePoint/app configuration an operator might reasonably want
# to adjust - site location, list names, the eStamp base URL. Excludes the
# underlying SharePoint site ID and list ID (opaque GUID pointers, not
# something an operator ever needs to see or edit) - lhdn_automation.py
# re-resolves those from these values automatically (see
# get_effective_site_id/get_effective_list_id) when they no longer match the
# baked-in defaults, so a change here takes effect immediately, same as
# SETTINGS_SCHEMA above.
SHAREPOINT_CONFIG_SCHEMA = [
    {
        "key": "sharepoint_hostname",
        "label": "SharePoint hostname",
        "description": "The tenant's SharePoint hostname (e.g. contoso.sharepoint.com).",
        "get": lambda: constants.SHAREPOINT_HOSTNAME,
        "set": lambda v: setattr(constants, "SHAREPOINT_HOSTNAME", v),
    },
    {
        "key": "sharepoint_site_path",
        "label": "SharePoint site path",
        "description": "The site's relative path (e.g. /sites/EStampingDutyTracker).",
        "get": lambda: constants.SHAREPOINT_SITE_PATH,
        "set": lambda v: setattr(constants, "SHAREPOINT_SITE_PATH", v),
    },
    {
        "key": "sharepoint_list_name",
        "label": "Tracking list name",
        "description": "Display name of the SharePoint list that tracks eStamp entries.",
        "get": lambda: constants.SHAREPOINT_LIST_NAME,
        "set": lambda v: setattr(constants, "SHAREPOINT_LIST_NAME", v),
    },
    {
        "key": "sharepoint_log_list_name",
        "label": "Automation Logs list name",
        "description": "Display name of the SharePoint list that receives a log row for each processed entry.",
        "get": lambda: constants.SHAREPOINT_LOG_LIST_NAME,
        "set": lambda v: setattr(constants, "SHAREPOINT_LOG_LIST_NAME", v),
    },
    {
        "key": "ESTAMP_PORTAL_URL",
        "label": "eStamp base URL",
        "description": "Base URL for the LHDN eStamp site.",
        "get": lambda: constants.BASE_URL,
        "set": lambda v: setattr(constants, "BASE_URL", v),
    },
]


def apply_saved_sharepoint_config():
    """Loads persisted SharePoint/app configuration (if any) and applies it onto the live modules. Call once at startup."""
    saved = settings.load()
    for entry in SHAREPOINT_CONFIG_SCHEMA:
        if entry["key"] in saved:
            try:
                entry["set"](saved[entry["key"]])
            except Exception:
                logging.exception("Failed to apply saved SharePoint config %s", entry["key"])


def apply_saved_settings():
    """Loads persisted settings (if any) and applies them onto the live modules. Call once at startup."""
    saved = settings.load()
    for entry in SETTINGS_SCHEMA:
        if entry["key"] in saved:
            try:
                entry["set"](saved[entry["key"]])
            except Exception:
                logging.exception("Failed to apply saved setting %s", entry["key"])


class SettingsDialog(tk.Toplevel):
    """
    Lets the operator view/edit the tunable operational parameters in
    SETTINGS_SCHEMA. Saving writes each value onto its live module global
    (taking effect immediately) and persists them via settings.py so they
    survive the next launch too.
    """

    def __init__(self, root):
        super().__init__(root)
        self.title("Settings")
        self.resizable(False, False)
        self.transient(root)

        body = ttk.Frame(self, padding=16)
        body.pack(fill="both", expand=True)

        ttk.Label(
            body,
            text="Operational settings - polling cadence, wait/retry timeouts.",
            font=("", 10, "bold"),
        ).grid(row=0, column=0, columnspan=3, sticky="w", pady=(0, 12))

        self._vars = {}
        for row, entry in enumerate(SETTINGS_SCHEMA, start=1):
            ttk.Label(body, text=f"{entry['label']} ({entry['unit']}):").grid(
                row=row, column=0, sticky="w", pady=4, padx=(0, 10)
            )
            var = tk.StringVar(value=str(entry["get"]()))
            ttk.Entry(body, textvariable=var, width=10).grid(row=row, column=1, sticky="w", pady=4)
            ttk.Label(
                body, text=entry["description"], foreground="gray", wraplength=340, justify="left"
            ).grid(row=row, column=2, sticky="w", padx=(10, 0), pady=4)
            self._vars[entry["key"]] = var

        button_row = ttk.Frame(body)
        button_row.grid(row=len(SETTINGS_SCHEMA) + 1, column=0, columnspan=3, sticky="w", pady=(16, 0))
        ttk.Button(button_row, text="Save", command=self._save).pack(side="left")
        ttk.Button(button_row, text="Cancel", command=self.destroy).pack(side="left", padx=(8, 0))

        self.grab_set()
        self.focus_set()

    def _save(self):
        parsed = {}
        for entry in SETTINGS_SCHEMA:
            raw = self._vars[entry["key"]].get().strip()
            try:
                value = int(raw)
                if value <= 0:
                    raise ValueError
            except ValueError:
                messagebox.showerror(
                    "Invalid value",
                    f"'{entry['label']}' must be a positive whole number.",
                    parent=self,
                )
                return
            parsed[entry["key"]] = value

        for entry in SETTINGS_SCHEMA:
            entry["set"](parsed[entry["key"]])
        settings.update(parsed)
        logging.info("Settings updated: %s", parsed)
        self.destroy()


class SharePointConfigDialog(tk.Toplevel):
    """
    Lets the operator view/edit the tunable SharePoint/app configuration in
    SHAREPOINT_CONFIG_SCHEMA. Saving writes each value onto its live module
    global (taking effect immediately - see get_effective_site_id/
    get_effective_list_id) and persists them via settings.py so they survive
    the next launch too.
    """

    def __init__(self, root):
        super().__init__(root)
        self.title("SharePoint Configuration")
        self.resizable(False, False)
        self.transient(root)

        body = ttk.Frame(self, padding=16)
        body.pack(fill="both", expand=True)

        ttk.Label(
            body,
            text="SharePoint site/list names and the eStamp base URL.",
            font=("", 10, "bold"),
        ).grid(row=0, column=0, columnspan=2, sticky="w", pady=(0, 4))
        ttk.Label(
            body,
            text="Site ID and list ID are internal pointers, not shown here - they're\n"
                 "resolved automatically from the values below.",
            foreground="gray",
            justify="left",
        ).grid(row=1, column=0, columnspan=2, sticky="w", pady=(0, 12))

        self._vars = {}
        for row, entry in enumerate(SHAREPOINT_CONFIG_SCHEMA, start=2):
            ttk.Label(body, text=f"{entry['label']}:").grid(
                row=row, column=0, sticky="nw", pady=4, padx=(0, 10)
            )
            var = tk.StringVar(value=str(entry["get"]()))
            frame = ttk.Frame(body)
            frame.grid(row=row, column=1, sticky="w", pady=4)
            ttk.Entry(frame, textvariable=var, width=42).pack(anchor="w")
            ttk.Label(
                frame, text=entry["description"], foreground="gray", wraplength=340, justify="left"
            ).pack(anchor="w")
            self._vars[entry["key"]] = var

        button_row = ttk.Frame(body)
        button_row.grid(row=len(SHAREPOINT_CONFIG_SCHEMA) + 2, column=0, columnspan=2, sticky="w", pady=(16, 0))
        ttk.Button(button_row, text="Save", command=self._save).pack(side="left")
        ttk.Button(button_row, text="Cancel", command=self.destroy).pack(side="left", padx=(8, 0))

        self.grab_set()
        self.focus_set()

    def _save(self):
        parsed = {}
        for entry in SHAREPOINT_CONFIG_SCHEMA:
            value = self._vars[entry["key"]].get().strip()
            if not value:
                messagebox.showerror(
                    "Invalid value",
                    f"'{entry['label']}' cannot be blank.",
                    parent=self,
                )
                return
            parsed[entry["key"]] = value

        for entry in SHAREPOINT_CONFIG_SCHEMA:
            entry["set"](parsed[entry["key"]])
        settings.update(parsed)
        logging.info("SharePoint configuration updated: %s", parsed)
        self.destroy()


def apply_saved_firm_data(firm_data):
    """Loads a persisted FirmData override (if any) and applies it onto the given instance. Call once per LHDNApp startup, right after models.default_firm_data()."""
    all_settings = settings.load()
    saved = all_settings.get("firm_data")
    for field in dataclasses.fields(models.FirmData):
        if field.name in saved:
            setattr(firm_data, field.name, saved[field.name])


class FirmDataDialog(tk.Toplevel):
    """
    Lets the operator view/edit the firm's own company details (models.FirmData) -
    the agent/filer info stamped onto every eStamp submission, as opposed to
    the per-client ClientQuotationData parsed from each SharePoint entry's
    JSON. Fields are generated directly from FirmData's own dataclass field
    names rather than a hand-maintained label list, so this dialog can't
    drift out of sync if that dataclass ever changes.
    """

    def __init__(self, root, app):
        super().__init__(root)
        self.app = app
        self.title("Edit Company Details")
        self.resizable(False, False)
        self.transient(root)

        body = ttk.Frame(self, padding=16)
        body.pack(fill="both", expand=True)

        ttk.Label(
            body,
            text="The firm's own company details, used as the agent/filer info on every eStamp submission.",
            font=("", 10, "bold"),
            wraplength=420,
            justify="left",
        ).grid(row=0, column=0, columnspan=2, sticky="w", pady=(0, 12))

        self._fields = dataclasses.fields(models.FirmData)
        self._vars = {}
        for row, field in enumerate(self._fields, start=1):
            ttk.Label(body, text=f"{field.name}:").grid(row=row, column=0, sticky="w", pady=4, padx=(0, 10))
            current_value = getattr(app.firm_data, field.name)
            var = tk.StringVar(value="" if current_value is None else str(current_value))
            ttk.Entry(body, textvariable=var, width=42).grid(row=row, column=1, sticky="w", pady=4)
            self._vars[field.name] = var

        button_row = ttk.Frame(body)
        button_row.grid(row=len(self._fields) + 1, column=0, columnspan=2, sticky="w", pady=(16, 0))
        ttk.Button(button_row, text="Save", command=self._save).pack(side="left")
        ttk.Button(button_row, text="Cancel", command=self.destroy).pack(side="left", padx=(8, 0))

        self.grab_set()
        self.focus_set()

    def _save(self):
        # No blank-field validation: default_firm_data() itself already ships
        # EmailAddress="" out of the box, so a required plain-str field
        # being blank is an accepted, real value here, not an error - only
        # AddressLine3 (Optional[str] = None in FirmData) is normalised from
        # blank to None so the dataclass keeps its actual None, rather than
        # storing "" where the rest of the app expects None. A field whose
        # default is literally None (as opposed to dataclasses.MISSING,
        # which every other field has) is exactly that field, so this stays
        # correct if FirmData's fields ever change without needing to name
        # AddressLine3 specifically.
        parsed = {}
        for field in self._fields:
            value = self._vars[field.name].get().strip()
            parsed[field.name] = None if (not value and field.default is None) else value

        for field in self._fields:
            setattr(self.app.firm_data, field.name, parsed[field.name])
        settings.update({"firm_data": dataclasses.asdict(self.app.firm_data)})
        logging.info("Firm data updated.")
        self.destroy()


class LHDNApp:
    def __init__(self, root, profile_name=None):
        self.root = root
        root.title("LHDN Automation")
        root.geometry("900x700")

        self.firm_data = models.default_firm_data()
        apply_saved_firm_data(self.firm_data)
        self.log_queue = queue.Queue()
        self.profile_name = profile_name or "Not signed in"
        self.profile_store = profiles.ProfileStore()

        self.poll_stop_event = threading.Event()
        self.poll_thread = None
        self.poll_auto_stop_job = None
        self.worker_busy = threading.Event()
        self.selectable_items = []
        self.cleanup_driver = None  # tracks an already-open cleanup browser, if any

        self._setup_logging()
        self._build_menu()
        self._build_layout()

        root.protocol("WM_DELETE_WINDOW", self._on_close)
        self.root.after(150, self._drain_log_queue)

        # Setting poll_toggle_var above doesn't itself invoke _on_poll_toggle
        # (Tkinter only calls a Checkbutton's command on real user
        # interaction, not on var.set()) - so both of these are started
        # explicitly here, right away, instead of waiting on the operator to
        # click Enable / Refresh List.
        self._start_polling()
        self._refresh_entries()

    def _setup_logging(self):
        handler = QueueLogHandler(self.log_queue)
        handler.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(message)s", "%H:%M:%S"))
        logging.getLogger().addHandler(handler)
        logging.getLogger().setLevel(logging.INFO)

    def _build_menu(self):
        menubar = tk.Menu(self.root)
        config_menu = tk.Menu(menubar, tearoff=False)
        config_menu.add_command(label="Edit Settings...", command=self._open_settings)
        config_menu.add_command(label="Edit SharePoint Configuration...", command=self._open_sharepoint_config)
        config_menu.add_command(label="Edit Company Details...", command=self._open_firm_data)
        config_menu.add_separator()
        config_menu.add_command(label="Export Settings...", command=self._export_settings)
        config_menu.add_command(label="Import Settings...", command=self._import_settings)
        config_menu.add_separator()
        config_menu.add_command(label="Test Automation Logs Access...", command=self._test_automation_log_access)
        menubar.add_cascade(label="Configuration", menu=config_menu)

        help_menu = tk.Menu(menubar, tearoff=False)
        help_menu.add_command(label="Check for Updates...", command=self._check_for_updates)
        menubar.add_cascade(label="Help", menu=help_menu)

        self.root.config(menu=menubar)

    def _open_settings(self):
        SettingsDialog(self.root)

    def _open_sharepoint_config(self):
        SharePointConfigDialog(self.root)

    def _open_firm_data(self):
        FirmDataDialog(self.root, self)

    def _export_settings(self):
        try:
            path = settings.export_settings()
        except OSError as error:
            messagebox.showerror("Export Settings", f"Couldn't write settings export:\n{error}")
            return
        logging.info("Settings exported to %s", path)
        messagebox.showinfo("Export Settings", f"Settings exported to:\n{path}")

    def _import_settings(self):
        path = filedialog.askopenfilename(
            title="Import Settings",
            initialdir=os.path.dirname(settings.export_path()),
            filetypes=[("JSON files", "*.json"), ("All files", "*.*")],
        )
        if not path:
            return  # user cancelled
        if not messagebox.askyesno(
            "Import Settings",
            "This will overwrite your current settings, SharePoint configuration, "
            "and company details with the values from the selected file. Continue?",
        ):
            return
        try:
            imported = settings.import_settings(path)
        except (OSError, ValueError) as error:
            messagebox.showerror("Import Settings", f"Couldn't read settings export:\n{error}")
            return

        apply_saved_settings()
        apply_saved_sharepoint_config()
        apply_saved_firm_data(self.firm_data)
        logging.info("Settings imported: %s", imported)
        messagebox.showinfo("Import Settings", "Settings imported and applied.")

    def _test_automation_log_access(self):
        if self.worker_busy.is_set():
            messagebox.showinfo("Busy", "Please wait for the current task to finish.")
            return
        self.worker_busy.set()
        threading.Thread(target=self._test_automation_log_access_worker, daemon=True).start()

    def _test_automation_log_access_worker(self):
        try:
            token = sharepoint_token.get_access_token()
            results = audit_log.diagnose_automation_log_access(token)
        except Exception as error:
            logging.exception("Automation Logs access test failed to run")
            self.worker_busy.clear()
            self.root.after(
                0,
                lambda: messagebox.showerror(
                    "Test Automation Logs Access",
                    f"Couldn't run the diagnostic:\n{error}",
                ),
            )
            return

        lines = [f"[{'OK' if ok else 'FAILED'}] {step}: {detail}" for step, ok, detail in results]
        message = "\n".join(lines)
        all_ok = all(ok for _, ok, _ in results)
        logging.info("Automation Logs access test: %s", message.replace("\n", " | "))

        def show_result():
            self.worker_busy.clear()
            if all_ok:
                messagebox.showinfo("Test Automation Logs Access", message)
            else:
                messagebox.showerror("Test Automation Logs Access", message)

        self.root.after(0, show_result)

    def _check_for_updates(self):
        if self.worker_busy.is_set():
            messagebox.showinfo("Busy", "Please wait for the current task to finish.")
            return
        threading.Thread(target=self._check_for_updates_worker, daemon=True).start()

    def _check_for_updates_worker(self):
        try:
            update_available, latest_version = updater.check_for_update()
        except Exception:
            logging.exception("Update check failed")
            self.root.after(
                0,
                lambda: messagebox.showerror(
                    "Check for Updates",
                    "Couldn't check for updates. Check your internet connection and try again.",
                ),
            )
            return

        def show_result():
            if update_available:
                if messagebox.askyesno(
                    "Update Available",
                    f"A new version ({latest_version}) is available (you're on {constants.APP_VERSION}).\n\n"
                    "Open the releases page?",
                ):
                    webbrowser.open(constants.GITHUB_RELEASES_URL)
            else:
                messagebox.showinfo("Check for Updates", f"You're running the latest version ({constants.APP_VERSION}).")

        self.root.after(0, show_result)

    def _build_layout(self):
        self._build_status_bar()

        self.pause_banner = PauseBanner(self.root)  # created hidden; shown/hidden on demand

        notebook = ttk.Notebook(self.root)
        notebook.pack(fill="both", expand=True, padx=8, pady=(8, 4))
        self.pause_manager = PauseManager(
            self.root,
            self.pause_banner,
            before_widget=notebook,
            on_alert_shown=self._on_alert_shown,
            on_alert_resolved=self._on_alert_resolved,
        )
        interaction.PAUSE_HANDLER = self.pause_manager.confirm

        self._build_edit_tab(notebook)
        self._build_cleanup_tab(notebook)

        log_frame = ttk.LabelFrame(self.root, text="Log")
        log_frame.pack(fill="both", expand=False, padx=8, pady=(4, 8))
        self.log_text = scrolledtext.ScrolledText(log_frame, height=10, state="disabled", wrap="word")
        self.log_text.pack(fill="both", expand=True)

    # ---- Persistent status bar: background polling toggle + close-browser ----

    def _build_status_bar(self):
        bar = ttk.Frame(self.root, padding=(10, 8))
        bar.pack(fill="x", side="top")

        ttk.Label(bar, text="Signed in as:").pack(side="left")
        self.profile_name_var = tk.StringVar(value=self.profile_name)
        ttk.Label(bar, textvariable=self.profile_name_var, font=("", 9, "bold")).pack(
            side="left", padx=(6, 6)
        )
        ttk.Button(bar, text="Switch", command=self._switch_profile).pack(side="left")

        ttk.Separator(bar, orient="vertical").pack(side="left", fill="y", padx=12)
        ttk.Button(bar, text="Switch Microsoft Account", command=self._switch_microsoft_account).pack(side="left")

        ttk.Separator(bar, orient="vertical").pack(side="left", fill="y", padx=12)

        ttk.Label(bar, text="Background polling:").pack(side="left")
        self.poll_indicator_var = tk.StringVar(value="● Off")
        self.poll_indicator_label = ttk.Label(bar, textvariable=self.poll_indicator_var, foreground="gray")
        self.poll_indicator_label.pack(side="left", padx=(6, 12))

        # Starts on automatically (see __init__) so Pending items are
        # picked up the moment the app opens, but only for
        # POLL_AUTO_STOP_SECONDS - it switches itself back off after that
        # (see _auto_stop_polling) rather than running unattended
        # indefinitely, and needs a person to notice and re-enable it here
        # if it should keep going.
        self.poll_toggle_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(
            bar, text="Enable", variable=self.poll_toggle_var, command=self._on_poll_toggle
        ).pack(side="left")

        ttk.Separator(bar, orient="vertical").pack(side="left", fill="y", padx=12)
        ttk.Button(bar, text="Close Browser", command=self._close_browser).pack(side="left")

    def _on_poll_toggle(self):
        if self.poll_toggle_var.get():
            self._start_polling()
        else:
            self._stop_polling()

    def _start_polling(self):
        if self.poll_thread and self.poll_thread.is_alive():
            return
        self.poll_stop_event.clear()
        self.poll_thread = threading.Thread(target=self._poll_loop, daemon=True)
        self.poll_thread.start()
        self.poll_toggle_var.set(True)
        self.poll_indicator_var.set(f"● Running (every {constants.POLL_INTERVAL}s, hidden browser)")
        self.poll_indicator_label.config(foreground="green")
        logging.info("Background polling enabled.")

        self._cancel_poll_auto_stop()
        self.poll_auto_stop_job = self.root.after(POLL_AUTO_STOP_SECONDS * 1000, self._auto_stop_polling)

    def _stop_polling(self):
        self._cancel_poll_auto_stop()
        self.poll_stop_event.set()
        self.poll_toggle_var.set(False)
        self.poll_indicator_var.set("● Off")
        self.poll_indicator_label.config(foreground="gray")
        logging.info("Background polling disabled.")

    def _auto_stop_polling(self):
        self.poll_auto_stop_job = None
        self._stop_polling()
        logging.info(
            "Background polling auto-stopped after %ds - re-enable it manually if required.",
            POLL_AUTO_STOP_SECONDS,
        )

    def _cancel_poll_auto_stop(self):
        if self.poll_auto_stop_job is not None:
            self.root.after_cancel(self.poll_auto_stop_job)
            self.poll_auto_stop_job = None

    def _poll_loop(self):
        while not self.poll_stop_event.is_set():
            try:
                polling.poll_for_changes(self.firm_data, headless=True)
            except Exception:
                logging.exception("Unhandled error during poll cycle, continuing")
            self.poll_stop_event.wait(constants.POLL_INTERVAL)

    def _close_browser(self):
        threading.Thread(target=self._close_browser_worker, daemon=True).start()

    def _close_browser_worker(self):
        was_cleanup_driver = self.cleanup_driver is not None and driver.LAST_DRIVER is self.cleanup_driver
        closed = driver.close_last_driver()
        if closed:
            logging.info("Browser closed.")
            if was_cleanup_driver:
                self.cleanup_driver = None
        else:
            logging.info("No browser window to close.")

    def _switch_profile(self):
        if self.worker_busy.is_set():
            messagebox.showinfo("Busy", "Please wait for the current task to finish.")
            return
        dialog = ProfileDialog(self.root, self.profile_store)
        self.root.wait_window(dialog)
        if dialog.result is None:
            return
        name, ic, password = dialog.result
        constants.PROD_IC, constants.PROD_PASSWORD = ic, password
        self.profile_name = name
        self.profile_name_var.set(name)
        logging.info("Switched active profile to %s.", name)

    def _switch_microsoft_account(self):
        if self.worker_busy.is_set():
            messagebox.showinfo("Busy", "Please wait for the current task to finish.")
            return
        auth.sign_out(constants.TENANT_ID, constants.CLIENT_ID)
        try:
            sign_in_with_microsoft(self.root, first_run=False)
        except Exception as error:
            logging.exception("Microsoft sign-in failed: %s", error)
            messagebox.showerror("Sign-in failed", f"Could not sign in with Microsoft:\n{error}")

    # ---- Edit tab ----

    def _build_edit_tab(self, notebook):
        frame = ttk.Frame(notebook, padding=12)
        notebook.add(frame, text="Edit")

        ttk.Label(
            frame,
            text="Select an Approved or Failed SharePoint entry to run the eStamp form automation for it.",
            wraplength=820,
            justify="left",
        ).pack(anchor="w", pady=(0, 8))

        toolbar = ttk.Frame(frame)
        toolbar.pack(fill="x", pady=(0, 8))
        self.refresh_btn = ttk.Button(toolbar, text="Refresh List", command=self._refresh_entries)
        self.refresh_btn.pack(side="left")
        # Plain tk.Button, not ttk: on Windows the ttk theme draws native
        # buttons and ignores background color, so a soft-blue tint needs
        # the classic widget. pady/bd/highlightthickness are tuned to land
        # within 1px of the neighboring ttk.Button's rendered height.
        self.process_btn = tk.Button(
            toolbar,
            text="Process Selected Entry",
            command=self._process_selected,
            state="disabled",
            bg="#cfe2ff",
            fg="#052c65",
            activebackground="#b6d4fe",
            activeforeground="#052c65",
            disabledforeground="#9db8d9",
            relief="flat",
            bd=0,
            highlightthickness=0,
            padx=12,
            pady=3,
            cursor="hand2",
        )
        self.process_btn.pack(side="left", padx=(8, 0))

        ttk.Separator(toolbar, orient="vertical").pack(side="left", fill="y", padx=8)
        ttk.Button(toolbar, text="Edit Entries", command=self._open_edit_entries).pack(side="left")

        columns = ("id", "status", "client_name", "effective_date", "quote_date", "created_date")
        headings = ("ID", "Status", "Client", "Effective Date", "Quote Date", "Created")
        self.entry_tree = ttk.Treeview(frame, columns=columns, show="headings", selectmode="browse", height=16)
        for col, heading in zip(columns, headings):
            self.entry_tree.heading(col, text=heading)
            self.entry_tree.column(col, width=240 if col == "client_name" else 130)
        self.entry_tree.pack(fill="both", expand=True)
        self.entry_tree.bind(
            "<<TreeviewSelect>>",
            lambda e: self.process_btn.config(state="normal" if self.entry_tree.selection() else "disabled"),
        )

    def _open_edit_entries(self):
        if not constants.EDIT_ENTRIES_URL:
            messagebox.showerror(
                "Not configured",
                "POWERAPP_EDIT_ENTRIES_URL is not set. Add it to your .env file to enable this feature.",
            )
            return
        if not webbrowser.open(constants.EDIT_ENTRIES_URL):
            logging.warning("Could not open the default browser for Edit Entries.")
            messagebox.showerror(
                "Couldn't open browser",
                f"Open this link manually:\n{constants.EDIT_ENTRIES_URL}",
            )

    def _refresh_entries(self):
        if self.worker_busy.is_set():
            messagebox.showinfo("Busy", "Please wait for the current task to finish.")
            return
        self.refresh_btn.config(state="disabled")
        threading.Thread(target=self._refresh_entries_worker, daemon=True).start()

    def _refresh_entries_worker(self):
        try:
            token = sharepoint_token.get_access_token()
            items = sharepoint_client.get_selectable_items(token)
        except Exception:
            logging.exception("Failed to refresh SharePoint entries")
            items = []
        self.root.after(0, self._populate_entries, items)

    def _populate_entries(self, items):
        self.selectable_items = items
        self.entry_tree.delete(*self.entry_tree.get_children())
        for index, item in enumerate(items):
            summary = sharepoint_client.summarise_item(item)
            self.entry_tree.insert(
                "",
                "end",
                iid=str(index),
                values=(
                    summary["id"],
                    summary["status"],
                    summary["client_name"],
                    summary["effective_date"],
                    summary["quote_date"],
                    summary["created_date"],
                ),
            )
        self.refresh_btn.config(state="normal")
        self.process_btn.config(state="disabled")
        logging.info("Loaded %d selectable entries.", len(items))

    def _process_selected(self):
        if self.worker_busy.is_set():
            messagebox.showinfo("Busy", "Please wait for the current task to finish.")
            return
        selection = self.entry_tree.selection()
        if not selection:
            return
        item = self.selectable_items[int(selection[0])]
        summary = sharepoint_client.summarise_item(item)
        if not messagebox.askyesno(
            "Confirm",
            f"Process entry ID {summary['id']} ({summary['client_name']})?\nA visible browser window will open.",
        ):
            return

        self.worker_busy.set()
        self.process_btn.config(state="disabled")
        self.refresh_btn.config(state="disabled")
        threading.Thread(target=self._process_selected_worker, args=(item,), daemon=True).start()

    def _process_selected_worker(self, item):
        try:
            token = sharepoint_token.get_access_token()
            processing.process_approved_item(token, item, self.firm_data)
        except Exception:
            logging.exception("Failed to process selected entry")
        finally:
            self.worker_busy.clear()
            self.root.after(0, self._refresh_entries)

    # ---- Cleanup tab ----

    def _build_cleanup_tab(self, notebook):
        frame = ttk.Frame(notebook, padding=12)
        notebook.add(frame, text="Cleanup")

        ttk.Label(
            frame,
            text=(
                "Cancels test draft entries submitted on the given date.\n"
                "A browser will open and the program wil sort through all table entries. If a "
                "search finds nothing, the browser stays open - clicking the button again rechecks "
                "the same window instead of opening a new one and signing in again."
            ),
            wraplength=820,
            justify="left",
        ).pack(anchor="w", pady=(0, 12))

        date_row = ttk.Frame(frame)
        date_row.pack(anchor="w", pady=(0, 12))
        ttk.Label(date_row, text="Date (dd/mm/yyyy):").pack(side="left")
        self.cleanup_date_var = tk.StringVar(value=date.today().strftime("%d/%m/%Y"))
        ttk.Entry(date_row, textvariable=self.cleanup_date_var, width=14).pack(side="left", padx=(6, 0))

        self.cleanup_btn = ttk.Button(frame, text="Run Cleanup", command=self._run_cleanup)
        self.cleanup_btn.pack(anchor="w")

    def _cleanup_session_active(self):
        """True if a cleanup browser from an earlier click is still open and usable."""
        return driver.is_driver_alive(self.cleanup_driver)

    def _run_cleanup(self):
        if self.worker_busy.is_set():
            messagebox.showinfo("Busy", "Please wait for the current task to finish.")
            return
        cleanup_date = self.cleanup_date_var.get().strip()
        if not cleanup_date:
            messagebox.showerror("Missing date", "Enter a date in dd/mm/yyyy format.")
            return

        retrying = self._cleanup_session_active()
        if retrying:
            prompt = f"Recheck the already-open browser for date {cleanup_date}?"
        else:
            prompt = f"Run cleanup for date {cleanup_date}?\nA visible browser window will open."
        if not messagebox.askyesno("Confirm", prompt):
            return

        self.worker_busy.set()
        self.cleanup_btn.config(state="disabled")
        threading.Thread(target=self._run_cleanup_worker, args=(cleanup_date, retrying), daemon=True).start()

    def _run_cleanup_worker(self, cleanup_date, retrying):
        try:
            if retrying:
                browser_driver = self.cleanup_driver
                logging.info("Rechecking the table on the already-open cleanup browser.")
                while cleanup.cleanup_loop(browser_driver, cleanup_date):
                    pass
            else:
                browser_driver = driver.setup_driver(constants.BASE_URL)
                self.cleanup_driver = browser_driver
                cleanup.cleanup_test_entries(browser_driver, cleanup_date)
            logging.info("Cleanup finished. Browser left open for review.")
        except exceptions.AutomationAborted:
            logging.info("Cleanup aborted by user. Browser left open for review.")
        except Exception:
            logging.exception("Cleanup failed. Browser left open for debugging.")
        finally:
            # Deliberately not closing the driver here - see close_last_driver().
            # self.cleanup_driver is left set so a later click can retry against
            # it; _cleanup_session_active() re-checks it's still alive first.
            self.worker_busy.clear()
            self.root.after(0, lambda: self.cleanup_btn.config(state="normal"))

    # ---- Shared ----

    def _on_alert_shown(self):
        """
        A pause is now waiting on the operator. Bring the window forward and
        give it focus once, and flash the taskbar icon as an attention cue
        that keeps working even while minimized - it's a one-time nudge, not
        a persistent on-top pin, so the operator can freely switch back to
        whatever else they were doing afterward.
        """
        self.root.deiconify()
        self.root.lift()
        self.root.focus_force()
        flash_taskbar_icon(self.root)

    def _on_alert_resolved(self):
        """The pause was answered (Continue/Abort) - release the attention cues."""
        stop_taskbar_flash(self.root)

    def _drain_log_queue(self):
        try:
            while True:
                message = self.log_queue.get_nowait()
                self.log_text.config(state="normal")
                self.log_text.insert("end", message + "\n")
                self.log_text.see("end")
                self.log_text.config(state="disabled")
        except queue.Empty:
            pass
        self.root.after(150, self._drain_log_queue)

    def _on_close(self):
        self._cancel_poll_auto_stop()
        self.poll_stop_event.set()
        self.root.destroy()


def _check_for_updates_at_startup():
    """
    Runs synchronously, before anything else in main() - validate_runtime_config,
    sign-in, etc. Silent on "no update available" or a failed check (an
    operator shouldn't be nagged just for being offline or a release not
    existing yet) - only interrupts startup with a dialog when a newer
    version genuinely exists. check_for_update()'s short timeout/no-retry
    defaults keep this from meaningfully delaying launch when offline.
    """
    try:
        update_available, latest_version = updater.check_for_update()
    except Exception:
        return
    if not update_available:
        return

    root = tk.Tk()
    root.withdraw()
    if messagebox.askyesno(
        "Update Available",
        f"A new version ({latest_version}) is available (you're on {constants.APP_VERSION}).\n\n"
        "Open the releases page?",
    ):
        webbrowser.open(constants.GITHUB_RELEASES_URL)
    root.destroy()


def main():
    _check_for_updates_at_startup()

    try:
        validation.validate_runtime_config()
    except RuntimeError as error:
        # Packaged as --windowed (no console), so an uncaught exception here
        # would otherwise fail silently with nothing visible to the operator -
        # this is also the single most likely first-run mistake (no .env yet).
        root = tk.Tk()
        root.withdraw()
        messagebox.showerror(
            "Missing configuration",
            f"{error}\n\nCreate a .env file next to this program (see .envexample for the "
            "expected keys) and fill in the real values, then restart.",
        )
        return

    # Before anything reads POLL_INTERVAL/WAIT_TIME/etc. - LHDNApp.__init__
    # starts polling immediately, so any saved override needs to be in
    # place before that, not applied afterward.
    apply_saved_settings()
    apply_saved_sharepoint_config()

    # Visible immediately, before anything network-dependent runs - a
    # withdrawn/hidden window during a slow or blocked Microsoft sign-in
    # check looks indistinguishable from "double-clicking did nothing".
    root = tk.Tk()
    root.title("LHDN Automation")
    root.resizable(False, False)
    status_var = tk.StringVar(value="Starting...")
    ttk.Label(root, textvariable=status_var, padding=32, font=("", 10)).pack()
    root.update()  # force the window to actually paint before any blocking call

    def set_status(text):
        status_var.set(text)
        root.update()

    try:
        set_status("Signing in with Microsoft...")
        sign_in_with_microsoft(root, first_run=not auth.has_cached_account(constants.TENANT_ID, constants.CLIENT_ID))
    except Exception as error:
        messagebox.showerror(
            "Microsoft sign-in failed",
            f"Could not sign in with Microsoft:\n{error}\n\nRestart the app to try again.",
        )
        root.destroy()
        return

    set_status("Loading...")

    store = profiles.ProfileStore()
    dialog = ProfileDialog(root, store)
    root.wait_window(dialog)

    if dialog.result is None:
        root.destroy()
        return

    name, ic, password = dialog.result
    constants.PROD_IC, constants.PROD_PASSWORD = ic, password

    for child in root.winfo_children():
        child.destroy()
    root.resizable(True, True)
    LHDNApp(root, profile_name=name)
    root.mainloop()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    main()
