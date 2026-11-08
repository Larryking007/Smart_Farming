"""Tkinter UI layout. Owner: UI lead.

Layout: one window, a ttk.Notebook with 5 tabs, a status bar at the bottom.
  1. Advice    - location + crop in, advice and weather alerts out
  2. Plots     - add/delete farm plots, Save / Load file
  3. Activity  - log activities per plot
  4. Calendar  - season calendar per plot
  5. Alerts    - upcoming weather threats per plot
Rules: no business logic here. Tabs call the other modules and show results.
Network calls run in a worker thread via App.run_async so the window never freezes.
"""
import queue
import threading
import uuid
import tkinter as tk
from dotenv import load_dotenv
from datetime import date
from tkinter import ttk, messagebox, filedialog

from advisor import PlantingAdvisor
from calendar_gen import build_season_calendar, detect_alerts
from crops import DEFAULT_CROPS, get_crop
from exceptions import FarmAdvisorError
from models import Activity, FarmPlot
from store import FarmLogStore
from validators import COORD_RE, parse_coordinates, validate_date, validate_location_name
from models import Location
from weather_client import WeatherClient

load_dotenv()  # load GEMINI_API_KEY from .env if present
ACTIVITY_KINDS = ["planting", "weeding", "fertilizing", "irrigation", "harvest", "other"]
PAD = {"padx": 8, "pady": 4}


def make_tree(parent, columns, widths, height=10):
    """Treeview with a vertical scrollbar. Returns the tree (the frame is packed for you)."""
    frame = ttk.Frame(parent)
    frame.pack(fill="both", expand=True, **PAD)
    tree = ttk.Treeview(frame, columns=columns, show="headings", height=height)
    for col, w in zip(columns, widths):
        tree.heading(col, text=col.title())
        tree.column(col, width=w, anchor="w")
    bar = ttk.Scrollbar(frame, orient="vertical", command=tree.yview)
    tree.configure(yscrollcommand=bar.set)
    tree.pack(side="left", fill="both", expand=True)
    bar.pack(side="right", fill="y")
    return tree


class PlotPicker(ttk.Frame):
    """Combobox listing saved plots. Used by the Activity, Calendar and Alerts tabs."""

    def __init__(self, parent, app, on_select=None):
        super().__init__(parent)
        self.app = app
        ttk.Label(self, text="Plot:").pack(side="left")
        self.var = tk.StringVar()
        self.box = ttk.Combobox(self, textvariable=self.var, state="readonly", width=40)
        self.box.pack(side="left", padx=6)
        if on_select:
            self.box.bind("<<ComboboxSelected>>", lambda e: on_select())

    def refresh(self):
        names = [f"{p.name} ({p.crop_name})" for p in self.app.plots]
        self.box["values"] = names
        if names and self.box.current() < 0:
            self.box.current(0)
        elif not names:
            self.var.set("")

    def selected(self):
        i = self.box.current()
        return self.app.plots[i] if 0 <= i < len(self.app.plots) else None


# ---------------------------------------------------------------- Tab 1: Advice
class AdviceTab(ttk.Frame):
    def __init__(self, parent, app):
        super().__init__(parent)
        self.app = app

        form = ttk.LabelFrame(self, text="Where and what?")
        form.pack(fill="x", **PAD)
        ttk.Label(form, text="Location (name or lat, lon):").grid(row=0, column=0, sticky="w", **PAD)
        self.location = ttk.Entry(form, width=32)
        self.location.grid(row=0, column=1, **PAD)
        ttk.Label(form, text="Crop:").grid(row=1, column=0, sticky="w", **PAD)
        self.crop = ttk.Combobox(form, values=[c.title() for c in DEFAULT_CROPS], state="readonly", width=29)
        self.crop.current(0)
        self.crop.grid(row=1, column=1, **PAD)
        self.button = ttk.Button(form, text="Get advice", command=self.get_advice)
        self.button.grid(row=0, column=2, rowspan=2, padx=12)

        out = ttk.LabelFrame(self, text="Advice")
        out.pack(fill="both", expand=True, **PAD)
        self.text = tk.Text(out, height=10, wrap="word", state="disabled")
        self.text.pack(fill="both", expand=True, padx=6, pady=6)

        alerts = ttk.LabelFrame(self, text="Weather alerts")
        alerts.pack(fill="both", expand=True, **PAD)
        self.alert_tree = make_tree(alerts, ("date", "level", "message"), (100, 80, 420), height=5)

    def get_advice(self):
        loc_text, crop_name = self.location.get().strip(), self.crop.get()
        if not loc_text:
            messagebox.showwarning("Missing input", "Enter a location.")
            return
        self.button.state(["disabled"])

        def work():
            crop = get_crop(crop_name)
            loc = self.app.resolve_location(loc_text)
            forecast = self.app.weather.get_forecast(loc.lat, loc.lon)
            return crop, loc, self.app.advisor.advise(crop, forecast, loc), detect_alerts(crop, forecast)

        self.app.run_async(work, self._show, self._done, "Fetching forecast and advice...")

    def _show(self, result):
        crop, loc, advice, alerts = result
        lines = [
            f"{crop.name.title()} at {loc.name}",
            f"Plant now?   {'YES' if advice.plant_now else 'NOT YET'}",
            f"Best window: {advice.best_window}",
            f"Irrigation:  {advice.irrigation}",
            f"Pest/disease risks: {', '.join(advice.pest_risks) or 'none flagged'}",
            "", advice.summary, f"(source: {advice.source})",
        ]
        self.text.configure(state="normal")
        self.text.delete("1.0", "end")
        self.text.insert("1.0", "\n".join(lines))
        self.text.configure(state="disabled")
        self.alert_tree.delete(*self.alert_tree.get_children())
        for a in alerts:
            self.alert_tree.insert("", "end", values=(a.date, a.level, a.message))

    def _done(self):
        self.button.state(["!disabled"])


# ---------------------------------------------------------------- Tab 2: Plots
class PlotsTab(ttk.Frame):
    def __init__(self, parent, app):
        super().__init__(parent)
        self.app = app

        form = ttk.LabelFrame(self, text="New plot")
        form.pack(fill="x", **PAD)
        self.name = ttk.Entry(form, width=22)
        self.location = ttk.Entry(form, width=22)
        self.crop = ttk.Combobox(form, values=[c.title() for c in DEFAULT_CROPS], state="readonly", width=12)
        self.crop.current(0)
        self.pdate = ttk.Entry(form, width=12)
        self.pdate.insert(0, date.today().isoformat())
        for col, (label, widget) in enumerate([("Name", self.name), ("Location", self.location),
                                               ("Crop", self.crop), ("Planting date", self.pdate)]):
            ttk.Label(form, text=label).grid(row=0, column=col, sticky="w", padx=6)
            widget.grid(row=1, column=col, padx=6, pady=4)
        self.add_btn = ttk.Button(form, text="Add plot", command=self.add_plot)
        self.add_btn.grid(row=1, column=4, padx=8)

        self.tree = make_tree(self, ("name", "crop", "location", "planting"), (160, 90, 200, 100))

        bar = ttk.Frame(self)
        bar.pack(fill="x", **PAD)
        ttk.Button(bar, text="Delete selected", command=self.delete_plot).pack(side="left")
        ttk.Button(bar, text="Save to file...", command=self.save).pack(side="right")
        ttk.Button(bar, text="Load from file...", command=self.load).pack(side="right", padx=6)

    def add_plot(self):
        try:
            name = validate_location_name(self.name.get())
            planting = validate_date(self.pdate.get())
        except FarmAdvisorError as e:
            messagebox.showerror("Invalid input", str(e))
            return
        loc_text, crop_name = self.location.get().strip(), self.crop.get()
        self.add_btn.state(["disabled"])

        def work():
            crop = get_crop(crop_name)
            loc = self.app.resolve_location(loc_text)
            plot = FarmPlot(uuid.uuid4().hex[:8], name, loc, crop.name, planting)
            plot.calendar = build_season_calendar(planting, crop)
            return plot

        self.app.run_async(work, self._added, lambda: self.add_btn.state(["!disabled"]), "Adding plot...")

    def _added(self, plot):
        self.app.plots.append(plot)
        self.app.plots_changed()
        self.name.delete(0, "end")

    def delete_plot(self):
        sel = self.tree.selection()
        if sel and messagebox.askyesno("Delete", "Delete the selected plot?"):
            self.app.plots = [p for p in self.app.plots if p.plot_id != sel[0]]
            self.app.plots_changed()

    def save(self):
        path = filedialog.asksaveasfilename(defaultextension=".json", filetypes=[("JSON", "*.json")])
        if path:
            self.app.guard(lambda: FarmLogStore(path).save(self.app.plots), "Saved.")

    def load(self):
        path = filedialog.askopenfilename(filetypes=[("JSON", "*.json")])
        if path:
            def do():
                self.app.plots = FarmLogStore(path).load()
                self.app.plots_changed()
            self.app.guard(do, "Loaded.")

    def refresh(self):
        self.tree.delete(*self.tree.get_children())
        for p in self.app.plots:
            self.tree.insert("", "end", iid=p.plot_id,
                             values=(p.name, p.crop_name, p.location.name, p.planting_date or "-"))


# ---------------------------------------------------------------- Tab 3: Activity log
class ActivityTab(ttk.Frame):
    def __init__(self, parent, app):
        super().__init__(parent)
        self.app = app
        self.picker = PlotPicker(self, app, on_select=self.refresh_list)
        self.picker.pack(anchor="w", **PAD)

        form = ttk.LabelFrame(self, text="Log an activity")
        form.pack(fill="x", **PAD)
        self.adate = ttk.Entry(form, width=12)
        self.adate.insert(0, date.today().isoformat())
        self.kind = ttk.Combobox(form, values=ACTIVITY_KINDS, state="readonly", width=12)
        self.kind.current(0)
        self.notes = ttk.Entry(form, width=36)
        for col, (label, widget) in enumerate([("Date", self.adate), ("Type", self.kind), ("Notes", self.notes)]):
            ttk.Label(form, text=label).grid(row=0, column=col, sticky="w", padx=6)
            widget.grid(row=1, column=col, padx=6, pady=4)
        ttk.Button(form, text="Add", command=self.add).grid(row=1, column=3, padx=8)

        self.tree = make_tree(self, ("date", "type", "notes"), (100, 100, 380))

    def add(self):
        plot = self.picker.selected()
        if not plot:
            messagebox.showinfo("No plot", "Add or select a plot first.")
            return
        try:
            d = validate_date(self.adate.get())
        except FarmAdvisorError as e:
            messagebox.showerror("Invalid date", str(e))
            return
        plot.activities.append(Activity(d, self.kind.get(), self.notes.get().strip()))
        plot.activities.sort(key=lambda a: a.date)
        self.notes.delete(0, "end")
        self.refresh_list()

    def refresh(self):
        self.picker.refresh()
        self.refresh_list()

    def refresh_list(self):
        self.tree.delete(*self.tree.get_children())
        plot = self.picker.selected()
        for a in (plot.activities if plot else []):
            self.tree.insert("", "end", values=(a.date, a.kind, a.notes))


# ---------------------------------------------------------------- Tab 4: Calendar
class CalendarTab(ttk.Frame):
    def __init__(self, parent, app):
        super().__init__(parent)
        self.app = app
        top = ttk.Frame(self)
        top.pack(fill="x", **PAD)
        self.picker = PlotPicker(top, app, on_select=self.refresh_list)
        self.picker.pack(side="left")
        ttk.Button(top, text="Regenerate", command=self.regenerate).pack(side="left", padx=8)
        self.tree = make_tree(self, ("date", "event", "stage"), (110, 260, 100), height=14)

    def regenerate(self):
        plot = self.picker.selected()
        if not plot or not plot.planting_date:
            messagebox.showinfo("Calendar", "Select a plot that has a planting date.")
            return
        self.app.guard(lambda: setattr(plot, "calendar",
                                       build_season_calendar(plot.planting_date, get_crop(plot.crop_name))))
        self.refresh_list()

    def refresh(self):
        self.picker.refresh()
        self.refresh_list()

    def refresh_list(self):
        self.tree.delete(*self.tree.get_children())
        plot = self.picker.selected()
        for e in (plot.calendar if plot else []):
            self.tree.insert("", "end", values=(e.date, e.title, e.kind))


# ---------------------------------------------------------------- Tab 5: Alerts
class AlertsTab(ttk.Frame):
    def __init__(self, parent, app):
        super().__init__(parent)
        self.app = app
        top = ttk.Frame(self)
        top.pack(fill="x", **PAD)
        self.picker = PlotPicker(top, app)
        self.picker.pack(side="left")
        self.button = ttk.Button(top, text="Check forecast", command=self.check)
        self.button.pack(side="left", padx=8)
        self.tree = make_tree(self, ("date", "level", "message"), (110, 90, 400), height=14)

    def check(self):
        plot = self.picker.selected()
        if not plot:
            messagebox.showinfo("Alerts", "Add or select a plot first.")
            return
        self.button.state(["disabled"])

        def work():
            crop = get_crop(plot.crop_name)
            forecast = self.app.weather.get_forecast(plot.location.lat, plot.location.lon)
            return detect_alerts(crop, forecast)

        self.app.run_async(work, self._show, lambda: self.button.state(["!disabled"]), "Checking forecast...")

    def _show(self, alerts):
        self.tree.delete(*self.tree.get_children())
        for a in alerts:
            self.tree.insert("", "end", values=(a.date, a.level, a.message))
        if not alerts:
            self.tree.insert("", "end", values=("-", "ok", "No threats in the next 14 days"))

    def refresh(self):
        self.picker.refresh()


# ---------------------------------------------------------------- App shell
class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Smart Farming & Crop Planting Advisor")
        self.geometry("760x600")
        self.minsize(640, 480)

        self.weather = WeatherClient()
        self.advisor = PlantingAdvisor()
        self.plots = []
        self._queue = queue.Queue()

        self.notebook = ttk.Notebook(self)
        self.notebook.pack(fill="both", expand=True, padx=6, pady=6)
        self.tabs = {}
        for key, label, cls in [("advice", "Advice", AdviceTab), ("plots", "My Plots", PlotsTab),
                                ("activity", "Activity Log", ActivityTab),
                                ("calendar", "Calendar", CalendarTab), ("alerts", "Alerts", AlertsTab)]:
            self.tabs[key] = cls(self.notebook, self)
            self.notebook.add(self.tabs[key], text=label)

        self.status = tk.StringVar(value="Ready")
        ttk.Label(self, textvariable=self.status, relief="sunken", anchor="w").pack(fill="x", side="bottom")
        self.after(100, self._poll)

    # --- shared helpers used by every tab
    def resolve_location(self, text):
        """Coordinates or a place name -> Location. Runs in a worker thread, may raise."""
        if COORD_RE.match(text):
            lat, lon = parse_coordinates(text)
            return Location(text, lat, lon)
        return self.weather.geocode(validate_location_name(text))

    def plots_changed(self):
        for tab in (self.tabs["plots"], self.tabs["activity"], self.tabs["calendar"], self.tabs["alerts"]):
            tab.refresh()

    def run_async(self, work, on_success, on_finally=None, message="Working..."):
        """Run work() in a thread; call on_success(result) or show the error on the UI thread."""
        self.status.set(message)

        def target():
            try:
                self._queue.put(("ok", on_success, work()))
            except FarmAdvisorError as e:
                self._queue.put(("err", None, str(e)))
            except Exception as e:  # unexpected
                self._queue.put(("err", None, f"Unexpected error: {e}"))
            self._queue.put(("fin", on_finally, None))

        threading.Thread(target=target, daemon=True).start()

    def guard(self, func, done_message="Done."):
        """Run func on the UI thread; show app errors in a dialog."""
        try:
            func()
            self.status.set(done_message)
        except FarmAdvisorError as e:
            messagebox.showerror("Error", str(e))
            self.status.set("Error")

    def _poll(self):
        while not self._queue.empty():
            kind, callback, payload = self._queue.get()
            if kind == "ok":
                callback(payload)
                self.status.set("Done.")
            elif kind == "err":
                messagebox.showerror("Error", payload)
                self.status.set("Error")
            elif callback:
                callback()
        self.after(100, self._poll)


if __name__ == "__main__":
    App().mainloop()
