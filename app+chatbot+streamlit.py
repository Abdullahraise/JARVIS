import os
import base64
import datetime
import time
import threading
import webbrowser
import smtplib

import streamlit as st
# `pywhatkit` and `pyautogui` require a display (X) and can fail in headless
# environments. Import lazily inside functions that need it so the app can
# start on servers without a DISPLAY.
import pyttsx3
import speech_recognition as sr
# browser recorder (optional)
HAS_BROWSER_RECORDER = False
try:
    from streamlit_audiorecorder import audiorecorder  # type: ignore
    HAS_BROWSER_RECORDER = True
except Exception:
    HAS_BROWSER_RECORDER = False

# Detect whether PyAudio is available (required for `sr.Microphone`).
try:
    import pyaudio  # type: ignore
    HAS_PYAUDIO = True
except Exception:
    HAS_PYAUDIO = False

# LangChain / Groq imports are optional: wrap them so the app can start
# even if these packages are not installed. The chat features will show
# a friendly message asking the user to install required packages.
HAS_LANGCHAIN = True
HAS_GROQ = True
try:
    from langchain.chains import LLMChain
    from langchain_core.prompts import (
        ChatPromptTemplate,
        HumanMessagePromptTemplate,
        MessagesPlaceholder,
    )
    from langchain_core.messages import SystemMessage, HumanMessage
    from langchain.chains.conversation.memory import ConversationBufferWindowMemory
except Exception:
    HAS_LANGCHAIN = False
    LLMChain = ChatPromptTemplate = HumanMessagePromptTemplate = MessagesPlaceholder = None
    SystemMessage = HumanMessage = ConversationBufferWindowMemory = None

try:
    from langchain_groq import ChatGroq
except Exception:
    HAS_GROQ = False
    ChatGroq = None


def speak(text: str):
    """Speak `text` using pyttsx3 in a background thread.

    On servers (deployed) TTS may not be available; exceptions are caught
    and surfaced via Streamlit write so the UI remains responsive.
    """

    # estimate speaking duration (seconds) for mouth animation
    try:
        duration = min(max(len(text) / 15.0, 0.8), 8.0)
    except Exception:
        duration = 1.5
    st.session_state["speaking_until"] = time.time() + duration

    def _run(t: str):
        try:
            engine = pyttsx3.init()
            # Try to pick a deeper/more authoritative voice if available
            try:
                voices = engine.getProperty('voices')
                # prefer voices with 'male' hint or choose the first
                chosen = None
                for v in voices:
                    name = getattr(v, 'name', '') or ''
                    if 'male' in name.lower() or 'alex' in name.lower():
                        chosen = v.id
                        break
                if not chosen and voices:
                    chosen = voices[0].id
                if chosen:
                    engine.setProperty('voice', chosen)
            except Exception:
                pass
            engine.setProperty("rate", 130)
            engine.say(t)
            engine.runAndWait()
        except Exception as e:
            # Do not raise — show message in UI instead
            st.write("TTS error:", e)

    threading.Thread(target=_run, args=(text,), daemon=True).start()


def listen() -> str:
    """Listen from the default microphone and return recognized text.

    Returns empty string on errors or if microphone not available.
    """
    if not HAS_PYAUDIO:
        st.warning(
            "Audio input unavailable: PyAudio is not installed or no microphone found.\n"
            "Install PyAudio locally to enable voice features, or continue using chat."
        )
        return ""

    try:
        recognizer = sr.Recognizer()
        with sr.Microphone() as source:
            st.write("Listening...")
            recognizer.adjust_for_ambient_noise(source)
            audio = recognizer.listen(source, timeout=5)
        try:
            command = recognizer.recognize_google(audio).lower()
            st.write(f"User: {command}")
            return command
        except sr.UnknownValueError:
            st.write("Sorry, I couldn't understand.")
        except sr.RequestError as e:
            st.write("Speech recognition error:", e)
    except Exception as e:
        st.write("Microphone not available or error:", e)
    return ""


def chat_with_groq(query: str, model_name: str = "llama3-8b-8192") -> str:
    """Send `query` to Groq using API key from `GROQ_API_KEY` env var.

    Returns a friendly error message if the key is not set or request fails.
    """
    groq_api_key = os.environ.get("GROQ_API_KEY")
    if not groq_api_key:
        return (
            "Groq API key not configured. Set the GROQ_API_KEY environment variable."
        )
    try:
        empathetic_prompt = (
            "You are an empathetic AI chatbot who is a mental health companion and a general AI assistant. "
            "Make your responses supportive, compassionate, and concise. "
            "If the user expresses distress, respond in a comforting manner. "
            "Keep your responses brief but meaningful."
        )
        full_prompt = f"{empathetic_prompt}\nUser: {query}\nAI:"
        chat_model = ChatGroq(groq_api_key=groq_api_key, model_name=model_name)
        response = chat_model.invoke([HumanMessage(content=full_prompt)])
        return getattr(response, "content", str(response))
    except Exception as e:
        return "Sorry, I couldn't connect to Groq. Error: " + str(e)


def take_command(command: str):
    if not command:
        return
    lc = command.lower()
    try:
        if "hello" in lc or "hey" in lc:
            speak("Hello, how can I assist you?")
        elif "open google" in lc:
            webbrowser.open("https://google.com")
            speak("Opening Google")
        elif "open youtube" in lc:
            webbrowser.open("https://youtube.com")
            speak("Opening YouTube")
        elif "search" in lc:
            search_query = lc.replace("search", "").strip()
            webbrowser.open(f"https://www.google.com/search?q={search_query}")
            speak(f"Searching Google for {search_query}")
        elif "time" in lc:
            current_time = datetime.datetime.now().strftime("%I:%M %p")
            speak(f"The current time is {current_time}")
        elif "date" in lc:
            current_date = datetime.datetime.now().strftime("%B %d, %Y")
            speak(f"Today's date is {current_date}")
        elif "play" in lc:
            song = lc.replace("play", "").strip()
            try:
                import pywhatkit
                pywhatkit.playonyt(song)
                speak(f"Playing {song} on YouTube")
            except Exception as e:
                # Likely running in headless environment or missing dependency.
                st.write("Unable to play media via pywhatkit:", e)
                # Fallback: open YouTube search in browser
                try:
                    webbrowser.open(f"https://www.youtube.com/results?search_query={song}")
                    speak(f"Opened YouTube search for {song}")
                except Exception as e2:
                    st.write("Fallback open failed:", e2)
        elif "shutdown" in lc:
            speak("Shutting down. Have a great day!")
            # in web app it's not appropriate to call exit()
        else:
            response = chat_with_groq(command)
            speak(response)
    except Exception as e:
        st.write("Command handling error:", e)


def send_email(to: str, message: str):
    try:
        server = smtplib.SMTP("smtp.gmail.com", 587)
        server.starttls()
        # Credentials must be provided via env vars or secure storage
        server.login(os.environ.get("EMAIL_USER"), os.environ.get("EMAIL_PASSWORD"))
        server.sendmail(os.environ.get("EMAIL_USER"), to, message)
        server.close()
        speak("Email sent successfully.")
    except Exception as e:
        speak(f"Failed to send email. Error: {str(e)}")


def journaling_entry():
    st.header("Journaling Entry")
    st.text_area("Write your thoughts here:")


def get_base64_image(image_path: str) -> str:
    try:
        with open(image_path, "rb") as img_file:
            return base64.b64encode(img_file.read()).decode()
    except Exception:
        return ""


def show_jarvis_animation(speaking: bool = False, gif_url: str | None = None):
        """Render a simple robot/JARVIS animation using inline SVG/CSS.

        If `speaking` is True, animate the mouth. If `gif_url` is provided or
        a local `jarvis.gif` exists, show that instead of the SVG.
        """
        # show GIF if available
        use_gif = False
        if gif_url:
                use_gif = True
        else:
                try:
                        use_gif = os.path.exists("jarvis.gif")
                        if use_gif:
                                gif_url = "jarvis.gif"
                except Exception:
                        use_gif = False

        if use_gif and gif_url:
                st.markdown(f"<div style='text-align:center'><img src=\"{gif_url}\" width=260/></div>", unsafe_allow_html=True)
                return

        mouth_anim = "animation: talk 0.9s infinite;" if speaking else ""

        st.markdown(
                f"""
                <style>
                .jarvis-container {{ display:flex;align-items:center;gap:20px;padding:10px;justify-content:center; }}
                .jarvis-robot {{ width:180px;height:180px;display:inline-block;position:relative; }}
                .jarvis-eye {{ fill:#00FFFF; animation: blink 3s infinite; }}
                .jarvis-mouth {{ fill:#00FFFF; transform-origin: center; {mouth_anim} }}
                @keyframes blink {{ 0%,90%,100% {{opacity:1}} 95%{{opacity:0.1}} }}
                @keyframes talk {{ 0%{{transform:scaleY(1)}}50%{{transform:scaleY(0.35)}}100%{{transform:scaleY(1)}} }}
                .jarvis-title {{ color:#00FFFF; font-family:monospace; font-weight:700; text-align:center }}
                </style>
                <div class="jarvis-container">
                    <div class="jarvis-robot">
                        <svg viewBox="0 0 140 140" width="180" height="180" xmlns="http://www.w3.org/2000/svg">
                            <rect x="10" y="18" width="120" height="100" rx="14" ry="14" stroke="#00FFFF" stroke-width="2" fill="rgba(0,0,0,0.12)" />
                            <circle class="jarvis-eye" cx="46" cy="60" r="10" />
                            <circle class="jarvis-eye" cx="94" cy="60" r="10" />
                            <rect class="jarvis-mouth" x="46" y="88" width="48" height="10" rx="4" />
                            <rect x="64" y="8" width="12" height="12" rx="3" fill="#00FFFF" opacity="0.7" />
                        </svg>
                    </div>
                </div>
                <div style="text-align:center"><div class="jarvis-title">JARVIS — An empathetic companion</div></div>
                """,
                unsafe_allow_html=True,
        )


def talk_with_ai():
    # show Jarvis animation/header
    show_jarvis_animation()

    image_path = "giphy.gif"  # optional file
    encoded_image = get_base64_image(image_path)

    if encoded_image:
        st.markdown(
            f"""
            <style>
                .talk-ai {{
                    background-image: url("data:image/gif;base64,{encoded_image}");
                    background-size: cover;
                    background-position: center;
                    color: #00FFFF;
                    padding: 20px;
                    border-radius: 10px;
                    height: 80vh;
                    display: flex;
                    align-items: center;
                    justify-content: center;
                    text-align: center;
                }}
                body {{
                    background-color: black;
                    color: #00FFFF;
                }}
            </style>
            """,
            unsafe_allow_html=True,
        )
        st.markdown(
            '<div class="talk-ai"><h1>Talk with AI</h1><p>Welcome to the AI chat section. How can I assist you today?</p></div>',
            unsafe_allow_html=True,
        )
    else:
        st.header("Talk with AI")

    col1, col2 = st.columns(2)
    if "is_listening" not in st.session_state:
        st.session_state.is_listening = False

    with col1:
        if st.button("Start Speaking with AI"):
            st.session_state.is_listening = True

    if st.session_state.is_listening:
        command = listen()
        if command:
            take_command(command)
        st.session_state.is_listening = False

    with col2:
        if st.button("Chat with AI"):
            st.session_state.show_chat = True

    if st.session_state.get("show_chat"):
        chat_interface()


def chat_interface():
    groq_api_key = os.environ.get("GROQ_API_KEY")

    st.sidebar.title("Customization")
    system_prompt = st.sidebar.text_input(
        "System prompt:",
        value=(
            "You are a helpful AI assistant. If the user expresses distress respond in a comforting manner and keep responses brief. "
            "If needed ask more questions and mention helpline numbers in crisis situations."
        ),
    )
    model = st.sidebar.selectbox("Choose a model", ["llama3-8b-8192", "mixtral-8x7b-32768", "gemma-7b-it"])
    conversational_memory_length = st.sidebar.slider("Conversational memory length:", 1, 10, value=5)

    if not groq_api_key:
        st.error("Groq API key not set. Please set the GROQ_API_KEY environment variable to use chat features.")
        return

    memory = ConversationBufferWindowMemory(k=conversational_memory_length, memory_key="chat_history", return_messages=True)

    if "chat_history" not in st.session_state:
        st.session_state.chat_history = []

    for message in st.session_state.chat_history:
        memory.save_context({"input": message["human"]}, {"output": message["AI"]})

    groq_chat = ChatGroq(groq_api_key=groq_api_key, model_name=model)

    user_question = st.text_input("Ask a question:")

    if user_question:
        prompt = ChatPromptTemplate.from_messages([
            SystemMessage(content=system_prompt),
            MessagesPlaceholder(variable_name="chat_history"),
            HumanMessagePromptTemplate.from_template("{human_input}"),
        ])

        conversation = LLMChain(llm=groq_chat, prompt=prompt, verbose=False, memory=memory)

        response = conversation.predict(human_input=user_question)

        message = {"human": user_question, "AI": response}
        st.session_state.chat_history.append(message)

    st.subheader("Conversation History")
    for chat in st.session_state.chat_history:
        st.write(f"**You:** {chat['human']}")
        st.write(f"**AI:** {chat['AI']}")


def cbt_suggestions():
    st.header("CBT Suggestions & Protocols")
    st.write("Here are some Cognitive Behavioral Therapy (CBT) techniques and suggestions.")


# Streamlit App Layout
st.set_page_config(page_title="JARVIS", page_icon="🤖", layout="wide")

# Single-page futuristic UI
st.markdown(
    """
    <style>
      .stApp { background: radial-gradient(circle at 10% 10%, #001219, #000814); color: #00FFFF; }
      .jarvis-shell { max-width:900px; margin:40px auto; padding:30px; border-radius:16px; backdrop-filter: blur(6px); background: linear-gradient(180deg, rgba(255,255,255,0.02), rgba(255,255,255,0.01)); box-shadow: 0 6px 30px rgba(0,0,0,0.6); }
      .chat-box { background: rgba(0,0,0,0.2); padding:18px; border-radius:12px; min-height:320px; }
      .user-msg { background: rgba(0,255,255,0.08); padding:10px 14px; border-radius:12px; color:#bffcff; margin:8px 0; text-align:right; }
      .jarvis-msg { background: rgba(0,255,255,0.06); padding:10px 14px; border-radius:12px; color:#e6ffff; margin:8px 0; text-align:left; }
      .input-row { display:flex; gap:10px; margin-top:12px; }
      .input-row > .stTextInput { flex:1 }
      .muted { color:#7fb8bf; font-size:14px }
    </style>
    <div class="jarvis-shell">
      <!-- content injected by Streamlit below -->
    </div>
    """,
    unsafe_allow_html=True,
)

# Render the single talk page
with st.container():
    # Voice-first UI: single large action for speaking to JARVIS
    st.markdown("", unsafe_allow_html=True)
    speaking_now = False
    if "speaking_until" in st.session_state:
        try:
            speaking_now = time.time() < float(st.session_state.get("speaking_until", 0))
        except Exception:
            speaking_now = False

    # show animation (mouth will animate when `speaking_now`)
    show_jarvis_animation(speaking=speaking_now)
    st.markdown("<div class='muted'>JARVIS — An empathetic companion (voice only)</div>", unsafe_allow_html=True)

    # Voice settings + accessibility
    col_a, col_b = st.columns([1, 1])
    with col_a:
        tts_enabled = st.checkbox("Enable voice responses (TTS)", value=True, key="tts_enabled")
    with col_b:
        mic_enabled = st.checkbox("Enable microphone (for voice input)", value=HAS_PYAUDIO and True, key="mic_enabled")
        if not HAS_PYAUDIO:
            st.info("Microphone not available in this environment. Use Accessibility Mode to type messages.")

    # Accessibility: reveal a text-input fallback when enabled
    accessibility = st.checkbox("Accessibility mode (show text fallback)", value=False, key="accessibility_mode")

    # Big speak button
    speak_btn = st.button("🎤 Speak to JARVIS", key="speak_button")

    # When pressed, capture audio once and process
    if speak_btn:
        # prefer native server mic if available and enabled
        if mic_enabled and HAS_PYAUDIO:
            with st.spinner("Listening... speak now"):
                spoken = listen()
            if spoken:
                if "chat_history" not in st.session_state:
                    st.session_state.chat_history = []
                st.session_state.chat_history.append({"human": spoken, "AI": "..."})
                response = chat_with_groq(spoken)
                st.session_state.chat_history[-1]["AI"] = response
                if tts_enabled:
                    speak(response)
        else:
            # fallback: use browser recorder when PyAudio unavailable
            if HAS_BROWSER_RECORDER:
                st.info("Using browser recorder — click and speak, then press Stop.")
                wav_bytes = audiorecorder()
                if wav_bytes is not None and len(wav_bytes) > 0:
                    # save temp file and transcribe using SpeechRecognition
                    try:
                        import base64, io, tempfile

                        tf = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
                        tf.write(wav_bytes)
                        tf.flush()
                        tf.close()

                        r = sr.Recognizer()
                        with sr.AudioFile(tf.name) as source:
                            audio_data = r.record(source)
                        try:
                            spoken = r.recognize_google(audio_data).lower()
                        except Exception as e:
                            st.error(f"Transcription failed: {e}")
                            spoken = ""

                        if spoken:
                            if "chat_history" not in st.session_state:
                                st.session_state.chat_history = []
                            st.session_state.chat_history.append({"human": spoken, "AI": "..."})
                            response = chat_with_groq(spoken)
                            st.session_state.chat_history[-1]["AI"] = response
                            if tts_enabled:
                                speak(response)
                    except Exception as e:
                        st.error(f"Failed to process browser audio: {e}")
            else:
                st.error("No microphone available and no browser recorder installed. Install streamlit-audiorecorder or enable microphone.")

    # Accessibility text fallback
    if accessibility:
        access_col1, access_col2 = st.columns([4,1])
        with access_col1:
            typed = st.text_input("Type to JARVIS (accessibility)", key="access_input")
        with access_col2:
            if st.button("Send (type)", key="access_send"):
                if typed:
                    if "chat_history" not in st.session_state:
                        st.session_state.chat_history = []
                    st.session_state.chat_history.append({"human": typed, "AI": "..."})
                    response = chat_with_groq(typed)
                    st.session_state.chat_history[-1]["AI"] = response
                    if tts_enabled:
                        speak(response)

    # Display latest transcript and conversation
    st.markdown("<div class='chat-box' id='chat_box'></div>", unsafe_allow_html=True)
    if "chat_history" in st.session_state and st.session_state.chat_history:
        for chat in reversed(st.session_state.chat_history[-8:]):
            st.markdown(f"<div class='jarvis-msg'>{chat['AI']}</div>", unsafe_allow_html=True)
            st.markdown(f"<div class='user-msg'>{chat['human']}</div>", unsafe_allow_html=True)
