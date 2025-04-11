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
        self.root.geometry("800x700")
        self.root.resizable(False, False)

        # GUI Elements (Dark Theme)
        self.label = ttk.Label(root, text="Voice Authentication System", font=("Arial", 18, "bold"), bootstyle="light")
        self.label.pack(pady=15)

        self.status_text = ScrolledText(root, height=18, width=80, font=("Arial", 10), wrap="word",
                                      bootstyle="dark", padding=5)
        self.status_text.pack(pady=15)
        self.status_text.text.insert("end", "Welcome! Click 'Setup' to configure or 'Authenticate' to unlock.\n")
        self.status_text.text.bind("<Key>", lambda e: "break")  # Prevent typing

        self.progress_bar = ttk.Progressbar(root, bootstyle="primary", mode="determinate", length=300)
        self.progress_bar.pack(pady=10)
        self.progress_bar.pack_forget()  # Hide initially

        self.setup_button = ttk.Button(root, text="Setup", command=self.start_setup, bootstyle="primary", width=15)
        self.setup_button.pack(pady=10)

        self.auth_button = ttk.Button(root, text="Authenticate", command=self.start_authentication, bootstyle="primary", width=15)
        self.auth_button.pack(pady=10)

        self.image_label = ttk.Label(root, text="Intruder Photo (if captured)", font=("Arial", 10), bootstyle="light")
        self.image_label.pack(pady=15)

        # Initialize variables
        self.running = False
        self.intruder_photo = None

    def log_status(self, message):
        """Update status text area with a new message."""
        self.status_text.text.configure(state='normal')
        self.status_text.text.insert("end", f"{datetime.now().strftime('%H:%M:%S')}: {message}\n")
        self.status_text.text.see("end")
        self.status_text.text.configure(state='disabled')
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
            self.log_status(f"Error loading phrase: {e}")
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
            self.log_status(f"Error extracting features: {e}")
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
            self.log_status("Error averaging voice features.")
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

    def record_audio(self, prompt, filename=None):
        """Record audio and optionally save to file."""
        self.log_status(prompt)
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
                self.log_status("No audio detected. Try again.")
                return None
            except Exception as e:
                self.log_status(f"Error recording audio: {e}")
                return None

    def capture_intruder(self):
        """Capture intruder photo using webcam."""
        self.log_status("Capturing intruder photo...")
        cam = cv2.VideoCapture(0)
        if not cam.isOpened():
            self.log_status("Camera not available.")
            return
        for _ in range(10):
            cam.read()
            time.sleep(0.1)
        ret, frame = cam.read()
        if ret:
            cv2.imwrite(INTRUDER_IMAGE, frame)
            self.log_status("Intruder photo saved.")
            img = Image.open(INTRUDER_IMAGE)
            img = img.resize((200, 150), Image.Resampling.LANCZOS)
            self.intruder_photo = ImageTk.PhotoImage(img)
            self.image_label.config(image=self.intruder_photo, text="")
        else:
            self.log_status("Failed to capture image.")
        cam.release()

    def match_voice(self):
        """Compare recorded voice with stored sample."""
        if not os.path.exists(AUTHORIZED_VOICE_FILE):
            self.log_status("No authorized voice sample found. Run Setup first.")
            return False

        audio = self.record_audio("Recording voice for authentication...", "test_voice.wav")
        if not audio:
            return False

        auth_features = self.extract_features(AUTHORIZED_VOICE_FILE)
        test_features = self.extract_features("test_voice.wav")

        if auth_features is None or test_features is None:
            self.log_status("Error in feature extraction.")
            if os.path.exists("test_voice.wav"):
                os.remove("test_voice.wav")
            return False

        distance, _ = fastdtw(auth_features, test_features, dist=euclidean)
        self.log_status(f"Voice Match Score: {distance:.2f}")
        if distance >= 500:
            self.log_status("Voice mismatch. Try speaking clearly, closer to the microphone.")
        if os.path.exists("test_voice.wav"):
            os.remove("test_voice.wav")
        return distance < 500  # Relaxed threshold

    def verify_phrase(self):
        """Verify spoken phrase against stored phrase."""
        audio = self.record_audio("Speak your unlock phrase...")
        if not audio:
            return False

        try:
            spoken_phrase = recognizer.recognize_google(audio).strip().lower()
            stored_phrase = self.load_encrypted_phrase()
            if stored_phrase is None:
                return False
            similarity = fuzz.ratio(spoken_phrase, stored_phrase)
            self.log_status(f"Phrase Similarity: {similarity}%")
            return similarity > 90
        except Exception as e:
            self.log_status(f"Error recognizing phrase: {e}")
            return False

    def run_setup(self):
        """Perform setup process with progress bar."""
        self.progress_bar.pack(pady=10)  # Show progress bar
        self.progress_bar["value"] = 0
        self.root.update()

        self.log_status("Starting setup...")
        # Record first voice sample
        audio = self.record_audio("Recording first voice sample... Speak any sentence.", AUTHORIZED_VOICE1_FILE)
        if not audio:
            self.log_status("Setup failed due to voice recording error.")
            self.progress_bar.pack_forget()
            return

        self.progress_bar["value"] = 25  # 25% complete
        self.root.update()

        # Record second voice sample
        audio = self.record_audio("Recording second voice sample... Speak another sentence.", AUTHORIZED_VOICE2_FILE)
        if not audio:
            self.log_status("Setup failed due to voice recording error.")
            self.progress_bar.pack_forget()
            return

        self.progress_bar["value"] = 50  # 50% complete
        self.root.update()

        # Average voice samples
        if not self.save_average_voice():
            self.log_status("Setup failed due to voice processing error.")
            self.progress_bar.pack_forget()
            return

        self.progress_bar["value"] = 75  # 75% complete
        self.root.update()

        # Record phrase
        audio = self.record_audio("Speak your secret unlock phrase (e.g., 'Open my phone')...")
        if not audio:
            self.log_status("Setup failed due to phrase recording error.")
            self.progress_bar.pack_forget()
            return

        try:
            phrase = recognizer.recognize_google(audio)
            self.save_encrypted_phrase(phrase)
            self.progress_bar["value"] = 100  # 100% complete
            self.root.update()
            time.sleep(0.5)  # Brief pause to show completion
            self.log_status("Setup complete! Voice and phrase saved.")
            messagebox.showinfo("Success", "Setup completed successfully!")
        except Exception as e:
            self.log_status(f"Error saving phrase: {e}")
            self.log_status("Setup failed.")
        finally:
            self.progress_bar.pack_forget()  # Hide progress bar

    def run_authentication(self):
        """Perform authentication with retries."""
        max_attempts = 3
        for attempt in range(max_attempts):
            self.log_status(f"Authentication Attempt {attempt + 1}/{max_attempts}")
            voice_ok = self.match_voice()
            phrase_ok = self.verify_phrase()
            if voice_ok and phrase_ok:
                self.log_status("Access Granted! Device unlocked.")
                logging.info(f"Authentication successful at {datetime.now()}")
                messagebox.showinfo("Success", "Access Granted!")
                return
            else:
                self.log_status("Authentication failed.")
        self.log_status("Max attempts reached. Capturing intruder photo...")
        self.capture_intruder()
        logging.info(f"Authentication failed at {datetime.now()}")
        messagebox.showwarning("Failed", "Authentication failed. Intruder photo captured.")

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
    recognizer = sr.Recognizer()
    root = ttk.Window(themename="darkly")
    app = VoiceAuthApp(root)
    root.mainloop()