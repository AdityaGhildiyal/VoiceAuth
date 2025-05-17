import os
import numpy as np
import librosa
import speech_recognition as sr
import cv2
from fastdtw import fastdtw
from scipy.spatial.distance import euclidean
import soundfile as sf
from fuzzywuzzy import fuzz
from cryptography.fernet import Fernet
from datetime import datetime
import logging
import ttkbootstrap as ttk
from ttkbootstrap.constants import *
from ttkbootstrap.scrolled import ScrolledText
from tkinter import messagebox
from PIL import Image, ImageTk
import threading
import time

# Setup logging
logging.basicConfig(filename="auth.log", level=logging.INFO)

# File paths
AUTHORIZED_VOICE_FILE = "authorized_voice.wav"
AUTHORIZED_VOICE1_FILE = "authorized_voice1.wav"
AUTHORIZED_VOICE2_FILE = "authorized_voice2.wav"
AUTHORIZED_PHRASE_FILE = "authorized_phrase.txt"
INTRUDER_IMAGE = "intruder.jpg"
KEY_FILE = "key.key"

class VoiceAuthApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Voice Authentication System")
        self.root.geometry("900x750")
        self.root.resizable(False, False)

        # Main container
        self.main_frame = ttk.Frame(root, padding=20, bootstyle="dark")
        self.main_frame.pack(fill="both", expand=True)

        # Header
        self.header_label = ttk.Label(
            self.main_frame,
            text="🔒 Voice Authentication System",
            font=("Helvetica", 22, "bold"),
            bootstyle="light"
        )
        self.header_label.pack(pady=(10, 20))

        # Tabbed interface
        self.notebook = ttk.Notebook(self.main_frame, bootstyle="primary")
        self.notebook.pack(fill="both", expand=True, pady=10)

        # Setup tab
        self.setup_tab = ttk.Frame(self.notebook, padding=15)
        self.notebook.add(self.setup_tab, text="Setup")

        # Authenticate tab
        self.auth_tab = ttk.Frame(self.notebook, padding=15)
        self.notebook.add(self.auth_tab, text="Authenticate")

        # Security tab
        self.security_tab = ttk.Frame(self.notebook, padding=15)
        self.notebook.add(self.security_tab, text="Security")

        # Setup tab content
        self.setup_button = ttk.Button(
            self.setup_tab,
            text=" Start Setup",
            command=self.start_setup,
            bootstyle="primary-outline",
            width=20,
            compound="left"
        )
        self.setup_button.pack(pady=10)

        self.setup_progress = ttk.Progressbar(
            self.setup_tab,
            bootstyle="primary-striped",
            mode="determinate",
            length=400
        )
        self.setup_progress.pack(pady=10)
        self.setup_progress.pack_forget()

        self.setup_status_label = ttk.Label(
            self.setup_tab,
            text="Setup Status",
            font=("Helvetica", 14, "bold"),
            bootstyle="light"
        )
        self.setup_status_label.pack(pady=(10, 5))

        self.setup_status_text = ScrolledText(
            self.setup_tab,
            height=10,
            width=80,
            font=("Consolas", 10),
            wrap="word",
            bootstyle="dark",
            padding=10
        )
        self.setup_status_text.pack(pady=10)
        self.setup_status_text.text.insert("end", "Click 'Start Setup' to configure voice and phrase.\n")
        self.setup_status_text.text.bind("<Key>", lambda e: "break")

        # Authenticate tab content
        self.auth_button = ttk.Button(
            self.auth_tab,
            text=" Start Authentication",
            command=self.start_authentication,
            bootstyle="success-outline",
            width=20,
            compound="left"
        )
        self.auth_button.pack(pady=10)

        self.auth_progress = ttk.Progressbar(
            self.auth_tab,
            bootstyle="success-striped",
            mode="determinate",
            length=400
        )
        self.auth_progress.pack(pady=10)
        self.auth_progress.pack_forget()

        self.auth_status_label = ttk.Label(
            self.auth_tab,
            text="Authentication Status",
            font=("Helvetica", 14, "bold"),
            bootstyle="light"
        )
        self.auth_status_label.pack(pady=(10, 5))

        self.auth_status_text = ScrolledText(
            self.auth_tab,
            height=10,
            width=80,
            font=("Consolas", 10),
            wrap="word",
            bootstyle="dark",
            padding=10
        )
        self.auth_status_text.pack(pady=10)
        self.auth_status_text.text.insert("end", "Click 'Start Authentication' to unlock.\n")
        self.auth_status_text.text.bind("<Key>", lambda e: "break")

        # Security tab content
        self.photo_button = ttk.Button(
            self.security_tab,
            text=" View Intruder Photo",
            command=self.view_intruder_photo,
            bootstyle="warning-outline",
            width=20,
            compound="left"
        )
        self.photo_button.pack(pady=10)

        self.image_label = ttk.Label(
            self.security_tab,
            text="No intruder photo available",
            font=("Helvetica", 12),
            bootstyle="light"
        )
        self.image_label.pack(pady=10)

        # Status bar
        self.status_bar = ttk.Label(
            self.main_frame,
            text="Ready",
            bootstyle="inverse-dark",
            padding=5
        )
        self.status_bar.pack(fill="x", side="bottom", pady=(10, 0))

        # Initialize variables
        self.running = False
        self.intruder_photo = None

    def log_status(self, tab, message):
        """Update status text area for the specified tab."""
        status_text = self.setup_status_text if tab == "setup" else self.auth_status_text
        status_text.text.configure(state='normal')
        timestamp = datetime.now().strftime('%H:%M:%S')
        status_text.text.insert("end", f"[{timestamp}] {message}\n")
        status_text.text.see("end")
        status_text.text.configure(state='disabled')
        self.status_bar.configure(text=message[:50] + "..." if len(message) > 50 else message)
        self.root.update()

    def save_encrypted_phrase(self, phrase):
        """Encrypt and save the phrase."""
        key = Fernet.generate_key()
        with open(KEY_FILE, "wb") as f:
            f.write(key)
        cipher = Fernet(key)
        encrypted = cipher.encrypt(phrase.encode())
        with open(AUTHORIZED_PHRASE_FILE, "wb") as f:
            f.write(encrypted)

    def load_encrypted_phrase(self):
        """Load and decrypt the phrase."""
        try:
            with open(KEY_FILE, "rb") as f:
                key = f.read()
            cipher = Fernet(key)
            with open(AUTHORIZED_PHRASE_FILE, "rb") as f:
                encrypted = f.read()
            return cipher.decrypt(encrypted).decode().strip().lower()
        except Exception as e:
            self.log_status("auth", f"Error loading phrase: {e}")
            return None

    def extract_features(self, filename):
        """Extract and normalize MFCC features."""
        try:
            y, sr = sf.read(filename)
            mfccs = librosa.feature.mfcc(y=y, sr=sr, n_mfcc=13)
            mfccs = mfccs.T  # Time-series format
            # Normalize using min-max scaling
            mfccs_min = np.min(mfccs, axis=0)
            mfccs_max = np.max(mfccs, axis=0)
            mfccs = (mfccs - mfccs_min) / (mfccs_max - mfccs_min + 1e-8)  # Avoid division by zero
            return mfccs
        except Exception as e:
            self.log_status("setup", f"Error extracting features: {e}")
            return None

    def average_features(self, file1, file2):
        """Average MFCC features from two files."""
        feats1 = self.extract_features(file1)
        feats2 = self.extract_features(file2)
        if feats1 is None or feats2 is None:
            return None
        # Pad shorter sequence
        max_len = max(len(feats1), len(feats2))
        feats1 = np.pad(feats1, ((0, max_len - len(feats1)), (0, 0)), mode='mean')
        feats2 = np.pad(feats2, ((0, max_len - len(feats2)), (0, 0)), mode='mean')
        # Average
        avg_feats = (feats1 + feats2) / 2
        return avg_feats

    def save_average_voice(self):
        """Save averaged voice features as WAV."""
        avg_feats = self.average_features(AUTHORIZED_VOICE1_FILE, AUTHORIZED_VOICE2_FILE)
        if avg_feats is None:
            self.log_status("setup", "Error averaging voice features.")
            return False
        # Inverse MFCC to audio (approximate)
        y_inv = librosa.feature.inverse.mfcc_to_audio(avg_feats.T, n_mels=13, sr=22050)
        sf.write(AUTHORIZED_VOICE_FILE, y_inv, 22050)
        # Clean up temporary files
        if os.path.exists(AUTHORIZED_VOICE1_FILE):
            os.remove(AUTHORIZED_VOICE1_FILE)
        if os.path.exists(AUTHORIZED_VOICE2_FILE):
            os.remove(AUTHORIZED_VOICE2_FILE)
        return True

    def record_audio(self, tab, prompt, filename=None):
        """Record audio and optionally save to file."""
        self.log_status(tab, prompt)
        recognizer = sr.Recognizer()
        with sr.Microphone() as source:
            recognizer.adjust_for_ambient_noise(source, duration=1)
            try:
                audio = recognizer.listen(source, timeout=5, phrase_time_limit=5)
                if filename:
                    with open(filename, "wb") as f:
                        f.write(audio.get_wav_data())
                return audio
            except sr.WaitTimeoutError:
                self.log_status(tab, "No audio detected. Try again.")
                return None
            except Exception as e:
                self.log_status(tab, f"Error recording audio: {e}")
                return None

    def capture_intruder(self):
        """Capture intruder photo using webcam."""
        self.log_status("auth", "Capturing intruder photo...")
        cam = cv2.VideoCapture(0)
        if not cam.isOpened():
            self.log_status("auth", "Camera not available.")
            return
        for _ in range(10):
            cam.read()
            time.sleep(0.1)
        ret, frame = cam.read()
        if ret:
            cv2.imwrite(INTRUDER_IMAGE, frame)
            self.log_status("auth", "Intruder photo saved.")
        else:
            self.log_status("auth", "Failed to capture image.")
        cam.release()

    def view_intruder_photo(self):
        """Display the intruder photo if available."""
        if os.path.exists(INTRUDER_IMAGE):
            img = Image.open(INTRUDER_IMAGE)
            img = img.resize((250, 200), Image.Resampling.LANCZOS)
            self.intruder_photo = ImageTk.PhotoImage(img)
            self.image_label.config(image=self.intruder_photo, text="")
        else:
            self.image_label.config(image=None, text="No intruder photo available")
            messagebox.showinfo("Info", "No intruder photo has been captured.")

    def match_voice(self):
        """Compare recorded voice with stored sample."""
        if not os.path.exists(AUTHORIZED_VOICE_FILE):
            self.log_status("auth", "No authorized voice sample found. Run Setup first.")
            return False

        audio = self.record_audio("auth", "Recording voice for authentication...", "test_voice.wav")
        if not audio:
            return False

        auth_features = self.extract_features(AUTHORIZED_VOICE_FILE)
        test_features = self.extract_features("test_voice.wav")

        if auth_features is None or test_features is None:
            self.log_status("auth", "Error in feature extraction.")
            if os.path.exists("test_voice.wav"):
                os.remove("test_voice.wav")
            return False

        distance, _ = fastdtw(auth_features, test_features, dist=euclidean)
        self.log_status("auth", f"Voice Match Score: {distance:.2f}")
        if distance >= 500:
            self.log_status("auth", "Voice mismatch. Try speaking clearly, closer to the microphone.")
        if os.path.exists("test_voice.wav"):
            os.remove("test_voice.wav")
        return distance < 500  # Relaxed threshold

    def verify_phrase(self):
        """Verify spoken phrase against stored phrase."""
        audio = self.record_audio("auth", "Speak your unlock phrase...")
        if not audio:
            return False

        try:
            recognizer = sr.Recognizer()
            spoken_phrase = recognizer.recognize_google(audio).strip().lower()
            stored_phrase = self.load_encrypted_phrase()
            if stored_phrase is None:
                return False
            similarity = fuzz.ratio(spoken_phrase, stored_phrase)
            self.log_status("auth", f"Phrase Similarity: {similarity}%")
            return similarity > 90
        except Exception as e:
            self.log_status("auth", f"Error recognizing phrase: {e}")
            return False

    def run_setup(self):
        """Perform setup process with progress bar."""
        self.setup_progress.pack(pady=10)
        self.setup_progress["value"] = 0
        self.root.update()

        self.log_status("setup", "Starting setup...")
        # Record first voice sample
        audio = self.record_audio("setup", "Recording first voice sample... Speak any sentence.", AUTHORIZED_VOICE1_FILE)
        if not audio:
            self.log_status("setup", "Setup failed due to voice recording error.")
            self.setup_progress.pack_forget()
            return

        self.setup_progress["value"] = 25
        self.root.update()

        # Record second voice sample
        audio = self.record_audio("setup", "Recording second voice sample... Speak another sentence.", AUTHORIZED_VOICE2_FILE)
        if not audio:
            self.log_status("setup", "Setup failed due to voice recording error.")
            self.setup_progress.pack_forget()
            return

        self.setup_progress["value"] = 50
        self.root.update()

        # Average voice samples
        if not self.save_average_voice():
            self.log_status("setup", "Setup failed due to voice processing error.")
            self.setup_progress.pack_forget()
            return

        self.setup_progress["value"] = 75
        self.root.update()

        # Record phrase
        audio = self.record_audio("setup", "Speak your secret unlock phrase (e.g., 'Open my phone')...")
        if not audio:
            self.log_status("setup", "Setup failed due to phrase recording error.")
            self.setup_progress.pack_forget()
            return

        try:
            recognizer = sr.Recognizer()
            phrase = recognizer.recognize_google(audio)
            self.save_encrypted_phrase(phrase)
            self.setup_progress["value"] = 100
            self.root.update()
            time.sleep(0.5)
            self.log_status("setup", "Setup complete! Voice and phrase saved.")
            messagebox.showinfo("Success", "Setup completed successfully!")
        except Exception as e:
            self.log_status("setup", f"Error saving phrase: {e}")
            self.log_status("setup", "Setup failed.")
        finally:
            self.setup_progress.pack_forget()

    def run_authentication(self):
        """Perform authentication with retries."""
        self.auth_progress.pack(pady=10)
        self.auth_progress["value"] = 0
        self.root.update()

        max_attempts = 3
        for attempt in range(max_attempts):
            self.log_status("auth", f"Authentication Attempt {attempt + 1}/{max_attempts}")
            self.auth_progress["value"] = (attempt / max_attempts) * 100
            self.root.update()
            voice_ok = self.match_voice()
            phrase_ok = self.verify_phrase()
            if voice_ok and phrase_ok:
                self.log_status("auth", "Access Granted! Device unlocked.")
                logging.info(f"Authentication successful at {datetime.now()}")
                messagebox.showinfo("Success", "Access Granted!")
                self.auth_progress.pack_forget()
                return
            else:
                self.log_status("auth", "Authentication failed.")
        self.log_status("auth", "Max attempts reached. Capturing intruder photo...")
        self.capture_intruder()
        logging.info(f"Authentication failed at {datetime.now()}")
        messagebox.showwarning("Failed", "Authentication failed. Intruder photo captured.")
        self.auth_progress.pack_forget()

    def start_setup(self):
        """Run setup in a separate thread."""
        if self.running:
            return
        self.running = True
        self.setup_button.config(state='disabled')
        self.auth_button.config(state='disabled')
        threading.Thread(target=self._run_setup_thread, daemon=True).start()

    def _run_setup_thread(self):
        """Wrapper to run setup and re-enable buttons."""
        self.run_setup()
        self.setup_button.config(state='normal')
        self.auth_button.config(state='normal')
        self.running = False

    def start_authentication(self):
        """Run authentication in a separate thread."""
        if self.running:
            return
        self.running = True
        self.setup_button.config(state='disabled')
        self.auth_button.config(state='disabled')
        threading.Thread(target=self._run_auth_thread, daemon=True).start()

    def _run_auth_thread(self):
        """Wrapper to run authentication and re-enable buttons."""
        self.run_authentication()
        self.setup_button.config(state='normal')
        self.auth_button.config(state='normal')
        self.running = False

if __name__ == "__main__":
    root = ttk.Window(themename="darkly")
    app = VoiceAuthApp(root)
    root.mainloop()