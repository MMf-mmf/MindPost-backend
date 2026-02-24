# Version using Google Gemini Live API for real-time dictation (THE GEMINI VERSION IS NOT COMPLETE YET AND HAS SOME BUGS WHERE IT WILL TRIGGER THE MICROPHONE INPUT EVEN WHEN THE HOTKEY IS NOT PRESSED)
# import asyncio

# from environs import Env
# import sounddevice as sd
# import numpy as np
# from pynput import keyboard
# import threading
# import os
# import time

# env = Env()
# env.read_env()
# # --- IMPORTANT: Install necessary libraries ---
# # pip install google-genai pynput sounddevice numpy

# try:
#     # Use the new, recommended import style
#     from google import genai
#     from google.genai import types as genai_types
# except ImportError:
#     print("Gemini library not found. Please run: pip install google-genai")
#     exit()

# # --- CONFIGURATION ---
# # 1. Set your Gemini API Key
# # It's highly recommended to use an environment variable for security.
# GOOGLE_API_KEY = env("GOOGLE_API_KEY")

# # 2. Define the hotkey for recording.
# HOTKEY = {keyboard.Key.ctrl_l, keyboard.Key.alt_l, keyboard.KeyCode.from_char("s")}

# # 3. Audio recording settings (Gemini prefers 16kHz)
# SAMPLE_RATE = 16000
# CHANNELS = 1
# # ---------------------

# # --- Global State Management ---
# is_recording = False
# hotkey_pressed = set()
# keyboard_controller = keyboard.Controller()
# audio_queue = asyncio.Queue()
# main_loop_running = True


# # --- Thread-Safe Hotkey Handling ---
# def on_press(key):
#     """Callback for pynput listener - runs in a separate thread."""
#     global is_recording, hotkey_pressed
#     if key in HOTKEY:
#         hotkey_pressed.add(key)
#     if HOTKEY.issubset(hotkey_pressed) and not is_recording:
#         print("\nHotkey pressed! Starting transcription...")
#         is_recording = True


# def on_release(key):
#     """Callback for pynput listener - runs in a separate thread."""
#     global is_recording, hotkey_pressed, main_loop_running
#     if key in HOTKEY:
#         print("\nHotkey released. Stopping transcription.")
#         is_recording = False
#         try:
#             hotkey_pressed.remove(key)
#         except KeyError:
#             pass
#     if key == keyboard.Key.esc:
#         print("Escape key pressed. Exiting...")
#         is_recording = False
#         main_loop_running = False  # Signal the main loop to exit
#         return False  # Stops the listener


# # --- Microphone Input Handling (in a separate thread) ---
# def audio_callback(indata, frames, time, status):
#     """This is called (from a separate thread) for each audio block."""
#     if status:
#         print(f"Microphone status warning: {status}")
#     if is_recording:
#         # Put the raw audio data into the asyncio queue
#         audio_queue.put_nowait(bytes(indata))


# def start_mic_stream():
#     """Starts the sounddevice input stream."""
#     print("Microphone stream starting...")
#     with sd.InputStream(
#         samplerate=SAMPLE_RATE,
#         channels=CHANNELS,
#         dtype="int16",
#         callback=audio_callback,
#     ):
#         while main_loop_running:
#             time.sleep(0.1)
#     print("Microphone stream stopped.")


# # --- Main Asynchronous Logic ---
# async def main():
#     """The main entry point for the asyncio application."""
#     global is_recording, main_loop_running

#     if GOOGLE_API_KEY == "YOUR_GOOGLE_API_KEY_HERE" or not GOOGLE_API_KEY:
#         print("=" * 50)
#         print("!!! CONFIGURATION REQUIRED !!!")
#         print("Please set your Gemini API key in the GOOGLE_API_KEY variable")
#         print("at the top of the script.")
#         print("=" * 50)
#         return

#     # Start the pynput listener in its own thread
#     listener = keyboard.Listener(on_press=on_press, on_release=on_release)
#     listener.start()

#     # Start the microphone stream in its own thread
#     mic_thread = threading.Thread(target=start_mic_stream, daemon=True)
#     mic_thread.start()

#     print("\n--- Real-Time Streaming Dictation ---")
#     print(
#         f"Press and hold '{'+'.join(str(k).split('.')[-1] for k in HOTKEY)}' to transcribe."
#     )
#     print("Release the keys to stop.")
#     print("Press 'Esc' to exit the script.")
#     print("------------------------------------")
#     print("Waiting for hotkey...")

#     # Initialize the Gemini client
#     client = genai.Client(api_key=GOOGLE_API_KEY)

#     while main_loop_running:
#         # Wait until the user presses the hotkey
#         while not is_recording and main_loop_running:
#             await asyncio.sleep(0.1)

#         if not main_loop_running:
#             break

#         # --- Start a new Gemini Live session ---
#         try:
#             # Use the new Pydantic-style config object
#             config = genai_types.LiveConnectConfig(
#                 response_modalities=[genai_types.Modality.TEXT],
#                 input_audio_transcription=genai_types.AudioTranscriptionConfig(),
#             )
#             # Use the model name from the new Live API docs
#             model = "gemini-live-2.5-flash-preview"

#             async with client.aio.live.connect(model=model, config=config) as session:
#                 print("Gemini session started. Speak now!")

#                 async def send_audio():
#                     while is_recording:
#                         try:
#                             audio_data = await asyncio.wait_for(
#                                 audio_queue.get(), timeout=0.1
#                             )
#                             await session.send_realtime_input(
#                                 audio=genai_types.Blob(
#                                     data=audio_data,
#                                     mime_type=f"audio/pcm;rate={SAMPLE_RATE}",
#                                 )
#                             )
#                         except asyncio.TimeoutError:
#                             continue
#                         except Exception as e:
#                             print(f"Error sending audio: {e}")
#                             break
#                     print("Send audio task finished.")

#                 async def receive_text():
#                     last_typed_text = ""
#                     while is_recording:
#                         try:
#                             async for msg in session.receive():
#                                 if not is_recording:
#                                     break
#                                 if (
#                                     msg.server_content
#                                     and msg.server_content.input_transcription
#                                 ):
#                                     transcript = (
#                                         msg.server_content.input_transcription.text
#                                     )
#                                     if transcript and transcript != last_typed_text:
#                                         new_text = transcript.replace(
#                                             last_typed_text, "", 1
#                                         )
#                                         if new_text:
#                                             # Add a small delay for focus stability
#                                             time.sleep(0.05)
#                                             keyboard_controller.type(new_text)
#                                         last_typed_text = transcript
#                         except Exception as e:
#                             print(f"Error receiving text: {e}")
#                             break
#                     print("Receive text task finished.")

#                 await asyncio.gather(send_audio(), receive_text())
#                 print("Gemini session ended.")

#         except Exception as e:
#             print(f"An error occurred with the Gemini session: {e}")
#             is_recording = False
#             await asyncio.sleep(1)

#     print("Main loop exited. Stopping listener...")
#     listener.stop()
#     listener.join()
#     print("Script finished.")


# if __name__ == "__main__":
#     try:
#         asyncio.run(main())
#     except KeyboardInterrupt:
#         print("\nScript interrupted by user. Exiting.")


########## OPEN API VERSION THAT DOES NOT USE STREAMING #########

# OPENAI_API_KEY = ""

# import openai
# import sounddevice as sd
# import numpy as np
# import soundfile as sf
# from pynput import keyboard
# import threading
# import io
# import time

# # --- CONFIGURATION ---
# # 1. Replace with your OpenAI API Key
# # It's recommended to use an environment variable for security.
# # For example: os.getenv("OPENAI_API_KEY")

# # 2. Define the hotkey for recording.
# # You can use combinations like '<ctrl>+<alt>+s' or a single key like '<f9>'.
# # Use Key.f9 for function keys, Key.ctrl_l for left control, etc.
# HOTKEY = {keyboard.Key.ctrl_l, keyboard.Key.alt_l, keyboard.KeyCode.from_char("s")}

# # 3. Audio recording settings
# SAMPLE_RATE = 44100
# CHANNELS = 1
# # ---------------------

# # --- Global Variables ---
# is_recording = False
# audio_frames = []
# hotkey_pressed = set()
# keyboard_controller = keyboard.Controller()


# def transcribe_audio(audio_data):
#     """
#     Transcribes audio data using OpenAI's Whisper API.
#     This version is updated for the openai library version >= 1.0.0.
#     """
#     if not audio_data:
#         print("No audio data to transcribe.")
#         return ""

#     print("Transcribing audio...")
#     try:
#         # Concatenate list of numpy arrays into a single array
#         audio_np = np.concatenate(audio_data, axis=0)

#         # Create an in-memory binary stream
#         buffer = io.BytesIO()
#         # The soundfile library needs a file extension to know the format.
#         # We give the buffer a name with a .wav extension.
#         buffer.name = "recording.wav"

#         # Write the NumPy array to the in-memory buffer as a WAV file
#         sf.write(buffer, audio_np, SAMPLE_RATE)

#         # Reset buffer's position to the beginning
#         buffer.seek(0)

#         # Initialize the OpenAI client (for openai library version >= 1.0.0)
#         client = openai.OpenAI(api_key=OPENAI_API_KEY)

#         # Use the new API for audio transcription, requesting plain text response
#         transcript = client.audio.transcriptions.create(
#             model="whisper-1", file=buffer, response_format="text"
#         )

#         return transcript

#     except Exception as e:
#         # Generic error handling for the new library version
#         if "authentication" in str(e).lower() or "api key" in str(e).lower():
#             print("\n[ERROR] Authentication failed. Please check your OpenAI API key.")
#             print(
#                 "Ensure it's correctly set in the script or as an environment variable."
#             )
#             return "[API Key Error]"
#         print(f"An error occurred during transcription: {e}")
#         return ""


# def record_and_transcribe():
#     """
#     Manages the audio recording process and initiates transcription.
#     This function runs in a separate thread to not block the main listener.
#     """
#     global audio_frames
#     audio_frames = []  # Clear previous recording

#     # Use an InputStream to capture audio in chunks
#     with sd.InputStream(samplerate=SAMPLE_RATE, channels=CHANNELS) as stream:
#         print("Recording started... Hold the hotkey.")
#         while is_recording:
#             # Read a chunk of audio from the microphone
#             data, overflowed = stream.read(SAMPLE_RATE)  # Read 1 second of audio
#             if overflowed:
#                 print("Warning: Audio buffer overflowed!")
#             audio_frames.append(data)

#     print("Recording stopped.")

#     # Once recording stops, transcribe the collected audio
#     transcribed_text = transcribe_audio(audio_frames)

#     if transcribed_text:
#         # We add a space before the text to ensure it's separated from the previous word.
#         # The .strip() handles cases where Whisper might return leading/trailing whitespace.
#         text_to_type = " " + transcribed_text.strip()

#         # *** FIX: Add a small delay to prevent focus-stealing issues. ***
#         # This gives the OS a moment to ensure the correct window is active.
#         time.sleep(0.1)

#         # Type the transcribed text at the current cursor position.
#         keyboard_controller.type(text_to_type)

#         # Now, print to the console for logging purposes.
#         print(f"Pasted text:{text_to_type}")


# def on_press(key):
#     """Callback function for when a key is pressed."""
#     global is_recording, hotkey_pressed

#     # Add the pressed key to our set of currently pressed keys
#     if key in HOTKEY:
#         hotkey_pressed.add(key)

#     # If all keys in our hotkey combination are pressed and we are not already recording
#     if HOTKEY.issubset(hotkey_pressed) and not is_recording:
#         is_recording = True
#         # Start the recording in a new thread to avoid blocking the listener
#         recording_thread = threading.Thread(target=record_and_transcribe)
#         recording_thread.start()


# def on_release(key):
#     """Callback function for when a key is released."""
#     global is_recording, hotkey_pressed

#     # If the released key is part of our hotkey, stop recording
#     if key in HOTKEY:
#         is_recording = False
#         try:
#             hotkey_pressed.remove(key)
#         except KeyError:
#             pass  # Ignore if key was already removed

#     # If the script should be stopped with the 'esc' key
#     if key == keyboard.Key.esc:
#         print("Escape key pressed. Exiting...")
#         is_recording = False
#         return False  # Stop the listener


# def main():
#     """Main function to set up and run the listener."""
#     if OPENAI_API_KEY == "YOUR_OPENAI_API_KEY_HERE":
#         print("=" * 50)
#         print("!!! CONFIGURATION REQUIRED !!!")
#         print("Please replace 'YOUR_OPENAI_API_KEY_HERE' with your actual")
#         print("OpenAI API key at the top of the script.")
#         print("=" * 50)
#         return

#     print("--- Real-Time Dictation Script ---")
#     print(
#         f"Press and hold '{'+'.join(str(k).split('.')[-1] for k in HOTKEY)}' to start recording."
#     )
#     print("Release the keys to stop and transcribe.")
#     print("Press 'Esc' to exit the script.")
#     print("-" * 36)
#     print("!!! IMPORTANT PERMISSIONS NOTE !!!")
#     print("On macOS, you MUST grant your terminal/IDE 'Accessibility' and")
#     print("'Input Monitoring' permissions in System Settings > Privacy & Security.")
#     print("On Windows/Linux, ensure the script is run with sufficient privileges.")
#     print("The script will not be able to type outside of its own window otherwise.")
#     print("-" * 36)
#     print("Listening for hotkey...")

#     # Set up the listener
#     with keyboard.Listener(on_press=on_press, on_release=on_release) as listener:
#         listener.join()


# if __name__ == "__main__":
#     main()
