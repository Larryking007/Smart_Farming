# Smart Farming & Crop Planting Advisor

A python app that helps farmers decide **when and how to plant**. The user enters a location and a crop (maize, cassava, tomato or rice). The app fetches the local forecast, uses AI to advise on planting time, irrigation and pest/disease risk, and helps the farmer track each plot through the season.

**Tech stack:** Python, Streamlit, Requests, JSON, date/time handling, Gemini API, Open-Meteo Forecast API.

---

## 1. Project walkthrough

### What the app does

1. **Advice:** enter a place name (or `lat, lon`) and a crop. The app returns whether to plant now, the best planting window, irrigation needs and likely pest/disease risks, plus any weather alerts.
2. **My Plots:** save farm plots (name, location, crop, planting date) and save/load them from a JSON file.
3. **Activity Log:** log planting, weeding, fertilizing, irrigation and harvest activities per plot.
4. **Calendar:** auto-generate a season calendar (planting → weeding → harvest).
5. **Alerts:** warn about heavy rain, heatwaves and dry spells in the upcoming forecast.

### How a request flows through the code

```
Streamlit UI (app.py)
   │  user enters location + crop
   ▼
validators.py ──► checks coordinates / names / dates (regex)
   ▼
weather_client.py ──► geocode the place, fetch the forecast (Open-Meteo)
   ▼
advisor.py ──► compute_flags() (rain, heat, dry week)
   │            └─► gemini_advisor.py: build prompt → call Gemini → validate JSON
   │            └─► falls back to simple rules if Gemini fails
   ▼
calendar_gen.py ──► season calendar + weather alerts
   ▼
store.py ──► save/load plots, logs and calendars (JSON/CSV)
```

Errors anywhere raise a custom exception from `exceptions.py`. The UI catches them and shows a message box.

### Project structure

| File                | Purpose                                                                 |
| ------------------- | ----------------------------------------------------------------------- |
| `app.py`            | Streamlit UI: here.                                                     |
| `main.py`           | Console smoke test that wires every module together.                    |
| `models.py`         | Shared data shapes (`Crop`, `FarmPlot`, `DailyForecast`, `Advice`...).  |
| `crops.py`          | Supported crops and their profiles.                                     |
| `weather_client.py` | `WeatherClient`: geocoding and daily weather forecasts from Open-Meteo. |
| `advisor.py`        | `PlantingAdvisor`: Gemini advice with a rule-based fallback.            |
| `gemini_advisor.py` | Prompt, response schema, API call and validation.                       |
| `calendar_gen.py`   | Season calendar and weather alert detection.                            |
| `store.py`          | `FarmLogStore`: JSON save/load (CSV export to do).                      |
| `validators.py`     | Regex helpers for coordinates, names, dates and numeric extraction.     |
| `exceptions.py`     | Custom exceptions shared by all modules.                                |
| `tests/`            | Unit tests (`python -m unittest discover -s tests`).                    |

### Python concepts and where they live

- **File handling:** `store.py` (JSON save/load, CSV export)
- **Exception handling:** `exceptions.py`, plus `weather_client.py`, `gemini_advisor.py` and the error dialogs in `app.py`
- **Regular expressions:** `validators.py`
- **OOP:** `Crop`, `WeatherClient`, `PlantingAdvisor`, `FarmLogStore`

---

## 2. Getting started

```bash
git clone <repo-url>
cd farm_advisor
python -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
pip install requests
```

Tkinter ships with Python on Windows and macOS. On Ubuntu/Debian: `sudo apt install python3-tk`.

**Run it:**

```bash
python app.py        # the Streamlit app
python main.py       # console smoke test
python -m unittest discover -s tests   # run tests
```

---

## 3. Team workflow (read before you write any code)

To avoid merge conflicts, **nobody works directly on `main`**. Every task gets its own branch.

### Step by step

1. **Update `main` and create your own branch**

   ```bash
   git checkout main
   git pull origin main
   git checkout -b feature/<short-task-name>
   ```

   Branch names: `feature/weather-client`, `feature/gemini-prompt`, `feature/csv-export`, `fix/date-validation`.

2. **Work and commit often** on your branch, in small commits with clear messages.

   ```bash
   git add <files you changed>
   git commit -m "Add geocoding to WeatherClient"
   ```

3. **Pull before you push.** Always bring in the latest changes first:

   ```bash
   git pull origin main                    # latest main into your branch
   git pull origin feature/<your-branch>   # only if the branch already exists on GitHub
   ```

   If Git reports conflicts, fix them in your editor, then `git add` the files and `git commit`. Run the tests (`python -m unittest discover -s tests`) and `python main.py` to confirm nothing broke.

4. **Push your branch**

   ```bash
   git push -u origin feature/<your-branch>     # later pushes: git push
   ```

5. **Open a Pull Request into `main`.** Describe what you changed and how you tested it, and tag a reviewer. The team lead merges after review.

6. **After your PR is merged**, go back to step 1 for your next task, starting from a fresh `main`.

### Rules

- Only edit the module(s) you own. If you need a change in someone else's file, ask them or open an issue.
- Do not change field names in `models.py` or exception names without telling the team.
- Do not push to `main`, and do not force-push (`git push --force`).
- Do not commit secrets (API keys), `farm_data.json`, `venv/` or `__pycache__/`. Add them to `.gitignore`.
- Add or update tests for your module.

### Module owners

| Area                | Files                                                | Owner  |
| ------------------- | ---------------------------------------------------- | ------ |
| Lead / integration  | `main.py`, reviews                                   | _name_ |
| Weather and data    | `weather_client.py`                                  | _name_ |
| AI and advisor      | `advisor.py`, `gemini_advisor.py`, `exceptions.py`   | _name_ |
| Storage and models  | `models.py`, `store.py`, `crops.py`, `validators.py` | _name_ |
| Calendar and alerts | `calendar_gen.py`                                    | _name_ |
| UI                  | `app.py`                                             | _name_ |

---

## 4. Status and to-do

- [ ] Real Open-Meteo geocoding and forecast calls (with timeouts and error handling)
- [ ] Live test of the Gemini integration with a real key
- [ ] CSV export of activities
- [ ] First real launch and layout polish of the Streamlit UI
- [ ] Unit tests for validators and calendar generator
