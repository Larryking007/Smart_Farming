import streamlit as st

# ---------- Page setup ----------
st.set_page_config(page_title="Smart Farming Advisor", page_icon="🌱", layout="wide")
st.title("🌱 Smart Farming & Crop Planting Advisor")

CROPS = ["Maize", "Cassava", "Rice", "Tomato"]


# ---------- PLACEHOLDER functions ----------
# Teammates will replace these with the real ones later.
def get_weather(location):
    return {"temperature": 28, "rainfall": 5, "humidity": 70}


def get_advice(crop, weather):
    return {
        "suitable": True,
        "message": f"Conditions look good for planting {crop}.",
        "warnings": ["Heavy rain expected in 3 days."],
    }


def get_ai_explanation(crop, weather, advice):
    return (
        f"This is where Gemini's plain-language explanation for {crop} "
        "will appear, including pest and disease risks and precautions."
    )


def save_farm(farm_name, location, crop):
    return True


# ---------- Memory for the app (survives button clicks) ----------
if "result" not in st.session_state:
    st.session_state.result = None
if "farms" not in st.session_state:
    st.session_state.farms = []

# ---------- Input section (sidebar) ----------
st.sidebar.header("Farm details")
farm_name = st.sidebar.text_input("Farm name")
location = st.sidebar.text_input("Location (e.g. Abuja)")
crop = st.sidebar.selectbox("Choose a crop", CROPS)

get_advice_clicked = st.sidebar.button("Get advice")
save_clicked = st.sidebar.button("Save farm")

# ---------- Save button ----------
if save_clicked:
    if farm_name and location:
        save_farm(farm_name, location, crop)
        st.session_state.farms.append(
            {"Farm": farm_name, "Location": location, "Crop": crop}
        )
        st.sidebar.success("Farm saved!")
    else:
        st.sidebar.error("Please enter a farm name and location.")

# ---------- Advice button ----------
if get_advice_clicked:
    if not location:
        st.error("Please enter a location first.")
    else:
        try:
            with st.spinner("Getting weather and advice..."):
                weather = get_weather(location)
                advice = get_advice(crop, weather)
                ai_text = get_ai_explanation(crop, weather, advice)
            st.session_state.result = {
                "location": location,
                "crop": crop,
                "weather": weather,
                "advice": advice,
                "ai_text": ai_text,
            }
        except Exception as error:
            st.error(f"Something went wrong: {error}")

# ---------- Show the result ----------
result = st.session_state.result
if result:
    weather = result["weather"]
    advice = result["advice"]

    st.subheader(f"Weather in {result['location']}")
    col1, col2, col3 = st.columns(3)
    col1.metric("Temperature", f"{weather['temperature']} °C")
    col2.metric("Rainfall", f"{weather['rainfall']} mm")
    col3.metric("Humidity", f"{weather['humidity']} %")

    st.subheader(f"Recommendation for {result['crop']}")
    if advice["suitable"]:
        st.success(advice["message"])
    else:
        st.error(advice["message"])

    for warning in advice["warnings"]:
        st.warning(warning)

    st.subheader("🤖 AI explanation")
    st.write(result["ai_text"])
else:
    st.info("Fill in the farm details on the left, then click 'Get advice'.")

# ---------- Saved farms ----------
st.divider()
st.subheader("📋 Saved farms")
if st.session_state.farms:
    st.table(st.session_state.farms)
else:
    st.caption("No farms saved yet.")