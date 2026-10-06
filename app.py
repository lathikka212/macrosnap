import smtplib
from email.mime.text import MIMEText
import streamlit as st
from google import genai
from google.genai import types

from prompts import SUMMARY_REQUEST_PROMPT, SYSTEM_PROMPT, WELCOME_MESSAGE_TEMPLATE

MODEL_NAME = "gemini-2.5-flash"
st.set_page_config(page_title="MacroSnap", page_icon="🥗")

# Retrieve Secrets
try:
    GEMINI_API_KEY = st.secrets["GEMINI_API_KEY"]
    GMAIL_ADDRESS = st.secrets["GMAIL_ADDRESS"]
    GMAIL_APP_PASSWORD = st.secrets["GMAIL_APP_PASSWORD"]
except KeyError as e:
    st.error(f"Missing key in secrets.toml: {e}")
    st.stop()


@st.cache_resource
def get_gemini_client():
    return genai.Client(api_key=GEMINI_API_KEY)


gemini_client = get_gemini_client()


def render_message(message):
    with st.chat_message(message["role"]):
        if message["kind"] == "text":
            st.write(message["content"])
        elif message["kind"] == "image":
            st.image(message["content"])


def add_message(role, kind, content):
    st.session_state.messages.append({"role": role, "kind": kind, "content": content})
    render_message(st.session_state.messages[-1])


def ask_gemini(parts):
    try:
        return st.session_state.chat.send_message(parts).text
    except Exception as error:
        return f"Sorry, something went wrong: {error}"


def send_email(to_address, user_name, summary):
    try:
        subject = f"🥗 MacroSnap Daily Summary for {user_name}"
        body = f"Hi {user_name},\n\nHere is your nutrition summary:\n\n{summary}\n\nKeep up the great work!\n- MacroSnap"
        
        message = MIMEText(body)
        message["Subject"] = subject
        message["From"] = GMAIL_ADDRESS
        message["To"] = to_address

        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
            server.login(GMAIL_ADDRESS, GMAIL_APP_PASSWORD)
            server.send_message(message)
        return True, "Success"
    except Exception as error:
        return False, str(error)


# Step 1: Onboarding
if "onboarded" not in st.session_state:
    st.title("🥗 MacroSnap")
    st.caption("Snap it. Track it. Email yourself the results.")
    with st.form("onboarding_form"):
        name = st.text_input("Your name")
        user_email = st.text_input(
            "Your Email Address",
            placeholder="you@example.com",
            help="This is the email MacroSnap will send your summary to.",
        )
        submitted = st.form_submit_button("Let's go 🚀")
    if submitted:
        if not name.strip() or not user_email.strip():
            st.warning("Please fill in both your name and email address.")
        else:
            st.session_state.name = name.strip()
            st.session_state.user_email = user_email.strip()
            st.session_state.chat = gemini_client.chats.create(
                model=MODEL_NAME,
                config=types.GenerateContentConfig(system_instruction=SYSTEM_PROMPT),
            )
            st.session_state.messages = []
            st.session_state.onboarded = True
            st.rerun()
    st.stop()

# Step 2: Main App Interface
header_col, button_col = st.columns([5, 2], vertical_alignment="center")

with header_col:
    st.title("🥗 MacroSnap")

with button_col:
    send_disabled = len(st.session_state.messages) <= 1
    if st.button("📧 Send to Email", disabled=send_disabled, use_container_width=True):
        with st.spinner("Summarizing your day..."):
            summary = ask_gemini([SUMMARY_REQUEST_PROMPT])
        success, info = send_email(st.session_state.user_email, st.session_state.name, summary)
        if success:
            st.success("Sent! Check your Email inbox 📩")
        else:
            st.error(f"Couldn't send email: {info}")

st.caption(f"Logged in as {st.session_state.name} - updates go to {st.session_state.user_email}")

# Display Welcome Message or Existing Chat
if not st.session_state.messages:
    add_message("assistant", "text", WELCOME_MESSAGE_TEMPLATE.format(name=st.session_state.name))
else:
    for message in st.session_state.messages:
        render_message(message)

# Image uploader sidebar for food photos
with st.sidebar:
    st.header("📸 Upload Food Photo")
    uploaded_photo = st.file_uploader("Choose a meal photo...", type=["jpg", "jpeg", "png"])
    if st.button("Analyze Photo 🥗") and uploaded_photo is not None:
        photo_bytes = uploaded_photo.getvalue()
        add_message("user", "image", photo_bytes)
        parts = [
            types.Part.from_bytes(data=photo_bytes, mime_type=uploaded_photo.type),
            "What is this meal? Give me the estimated calories and macros."
        ]
        with st.spinner("Analyzing your meal photo..."):
            answer = ask_gemini(parts)
        add_message("assistant", "text", answer)

# Chat text input
if user_text := st.chat_input("Type what you ate or ask a question..."):
    add_message("user", "text", user_text)
    with st.spinner("Crunching the numbers..."):
        answer = ask_gemini([user_text])
    add_message("assistant", "text", answer)