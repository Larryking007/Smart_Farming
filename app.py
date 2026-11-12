import streamlit as st
from datetime import date
from uuid import uuid4

from advisor import PlantingAdvisor
from calendar_gen import build_season_calendar, detect_alerts
from crops import get_crop
from exceptions import FarmAdvisorError
from models import Activity, FarmPlot
from store import FarmLogStore
from validators import validate_date
from weather_client import WeatherClient


st.set_page_config(page_title="Smart Farming Advisor", page_icon="🌱", layout="wide")
st.title("🌱 Smart Farming & Crop Planting Advisor")

CROPS = ["Maize", "Cassava", "Rice", "Tomato"]
ACTIVITY_TYPES = ["planting", "weeding", "fertilizing", "irrigation", "harvest", "other"]
farm_store = FarmLogStore()

st.session_state.setdefault("result", None)
st.session_state.setdefault("storage_error", None)
if "plots" not in st.session_state:
    try:
        st.session_state.plots = farm_store.load()
    except FarmAdvisorError as error:
        st.session_state.plots = []
        st.session_state.storage_error = str(error)

with st.sidebar:
    st.header("Farm details")
    farm_name = st.text_input("Farm or plot name", key="farm_name")
    location = st.text_input("Location (e.g. Abuja)", key="location")
    crop = st.selectbox("Choose a crop", CROPS, key="crop")
    planting_date = st.date_input("Planting date", value=date.today(), key="planting_date")
    get_advice_clicked = st.button("Get advice", key="get_advice")
    save_clicked = st.button(
        "Save plot",
        key="save_plot",
        disabled=bool(st.session_state.storage_error),
    )

if st.session_state.storage_error:
    st.error(
        "Saved plot data could not be loaded, so changes are disabled to avoid "
        f"overwriting it. {st.session_state.storage_error}"
    )

if save_clicked:
    if not farm_name.strip() or not location.strip():
        st.sidebar.error("Enter a plot name and location before saving.")
    else:
        try:
            crop_profile = get_crop(crop)
            planting_date_text = validate_date(planting_date.isoformat())
            with st.spinner("Saving plot..."):
                resolved_location = WeatherClient().geocode(location.strip())
                plot = FarmPlot(
                    plot_id=str(uuid4()),
                    name=farm_name.strip(),
                    location=resolved_location,
                    crop_name=crop_profile.name,
                    planting_date=planting_date_text,
                    calendar=build_season_calendar(planting_date_text, crop_profile),
                )
                plots = [*st.session_state.plots, plot]
                farm_store.save(plots)
                st.session_state.plots = plots
            st.sidebar.success("Plot saved.")
        except FarmAdvisorError as error:
            st.sidebar.error(f"Unable to save plot: {error}")
        except ValueError as error:
            st.sidebar.error(f"Unable to build the plot calendar: {error}")

if get_advice_clicked:
    if not location.strip():
        st.error("Enter a location first.")
    else:
        try:
            with st.spinner("Getting weather and advice..."):
                crop_profile = get_crop(crop)
                weather_client = WeatherClient()
                resolved_location = weather_client.geocode(location.strip())
                forecast = weather_client.get_forecast(
                    resolved_location.lat,
                    resolved_location.lon,
                )
                advisor = PlantingAdvisor()
                advice = advisor.advise(crop_profile, forecast, resolved_location)
                alerts = detect_alerts(crop_profile, forecast)
            st.session_state.result = {
                "location": resolved_location.name,
                "crop": crop_profile.name,
                "forecast": forecast,
                "advisor_error": advisor.last_error,
                "advice": advice,
                "alerts": alerts,
            }
        except FarmAdvisorError as error:
            st.error(f"Unable to get planting advice: {error}")
        except ValueError as error:
            st.error(f"Unable to analyze the forecast: {error}")

advice_tab, plots_tab, activity_tab, calendar_tab = st.tabs(
    ["Advice", "My plots", "Activity log", "Calendar"]
)

with advice_tab:
    result = st.session_state.result
    if result:
        forecast = result["forecast"]
        first_day = forecast[0]
        advice = result["advice"]

        st.subheader(f"Weather in {result['location']}")
        st.caption(f"Forecast: {forecast[0].date} to {forecast[-1].date}")
        col1, col2, col3 = st.columns(3)
        col1.metric("First-day high", f"{first_day.temp_max:.1f} °C")
        col2.metric("First-day low", f"{first_day.temp_min:.1f} °C")
        rain_7d = sum(day.rain_mm for day in forecast[:7])
        col3.metric("Rain next 7 days", f"{rain_7d:.1f} mm")

        st.subheader(f"Recommendation for {result['crop'].title()}")
        if advice.plant_now:
            st.success("The available forecast supports planting now.")
        else:
            st.warning("Wait and check conditions before planting.")
        st.write(f"**Recommended window:** {advice.best_window}")
        st.write(advice.summary)
        st.write(f"**Irrigation:** {advice.irrigation}")

        if result["advisor_error"]:
            st.warning(
                "Gemini was unavailable; rule-based advice is shown. "
                f"{result['advisor_error']}"
            )
        else:
            st.caption(f"Advice source: {advice.source}")

        if advice.pest_risks:
            st.subheader("Pest and disease risks")
            for risk in advice.pest_risks:
                st.warning(risk)

        st.subheader("Weather alerts")
        if result["alerts"]:
            for alert in result["alerts"]:
                if alert.level == "danger":
                    st.error(f"{alert.date}: {alert.message}")
                else:
                    st.warning(f"{alert.date}: {alert.message}")
        else:
            st.success("No weather alerts for the available forecast.")
    else:
        st.info("Enter a location and crop, then select Get advice.")

with plots_tab:
    st.subheader("My plots")
    if st.session_state.plots:
        st.table([
            {
                "Plot": plot.name,
                "Location": plot.location.name,
                "Crop": plot.crop_name.title(),
                "Planting date": plot.planting_date or "Not set",
                "Activities": len(plot.activities),
            }
            for plot in st.session_state.plots
        ])
    else:
        st.info("No saved plots yet. Add one using the farm details in the sidebar.")

with activity_tab:
    st.subheader("Activity log")
    if not st.session_state.plots:
        st.info("Save a plot before logging activities.")
    else:
        plot_names = {
            plot.plot_id: f"{plot.name} ({plot.crop_name.title()})"
            for plot in st.session_state.plots
        }
        selected_plot_id = st.selectbox(
            "Plot",
            list(plot_names),
            format_func=plot_names.get,
            key="activity_plot_id",
        )
        with st.form("activity_form"):
            activity_kind = st.selectbox("Activity", ACTIVITY_TYPES, key="activity_kind")
            activity_date = st.date_input("Activity date", key="activity_date")
            activity_notes = st.text_area("Notes", key="activity_notes")
            log_activity_clicked = st.form_submit_button("Log activity")

        if log_activity_clicked:
            try:
                activity_date_text = validate_date(activity_date.isoformat())
                selected_plot = next(
                    plot for plot in st.session_state.plots
                    if plot.plot_id == selected_plot_id
                )
                selected_plot.activities.append(
                    Activity(activity_date_text, activity_kind, activity_notes.strip())
                )
                if activity_kind == "planting":
                    crop_profile = get_crop(selected_plot.crop_name)
                    selected_plot.planting_date = activity_date_text
                    selected_plot.calendar = build_season_calendar(
                        activity_date_text,
                        crop_profile,
                    )
                farm_store.save(st.session_state.plots)
                st.success("Activity logged.")
            except FarmAdvisorError as error:
                st.error(f"Unable to log activity: {error}")
            except ValueError as error:
                st.error(f"Unable to update the season calendar: {error}")

        selected_plot = next(
            plot for plot in st.session_state.plots
            if plot.plot_id == selected_plot_id
        )
        if selected_plot.activities:
            st.table([
                {"Date": activity.date, "Activity": activity.kind.title(), "Notes": activity.notes}
                for activity in sorted(selected_plot.activities, key=lambda item: item.date)
            ])
        else:
            st.caption("No activities logged for this plot.")

with calendar_tab:
    st.subheader("Season calendar")
    plots_with_calendars = [plot for plot in st.session_state.plots if plot.calendar]
    if not plots_with_calendars:
        st.info("Save a plot with a planting date to generate its calendar.")
    else:
        calendar_names = {
            plot.plot_id: f"{plot.name} ({plot.crop_name.title()})"
            for plot in plots_with_calendars
        }
        calendar_plot_id = st.selectbox(
            "Plot calendar",
            list(calendar_names),
            format_func=calendar_names.get,
            key="calendar_plot_id",
        )
        calendar_plot = next(
            plot for plot in plots_with_calendars
            if plot.plot_id == calendar_plot_id
        )
        st.table([
            {"Date": event.date, "Event": event.title, "Stage": event.kind.title()}
            for event in calendar_plot.calendar
        ])