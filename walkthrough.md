# Walkthrough - FitPulse Project Implementation & Updates ⚡

This document summarizes all the core implementations, features, and verification results for the **FitPulse** project.

## 🎬 Demo Video & UI Interaction
A recorded demo video of FitPulse in action is included in this repository:

![FitPulse Demo](fitpulse_demo.gif)

### Key Flows Shown in Demo:
1. **Interactive Prompt Chips**: Clicking the `"🏋️ Benchmark WODs"` chip retrieves CrossFit benchmark WODs (**Cindy** and **Fran**) from Google Cloud Firestore and renders them as A2UI cards.
2. **Omni Video Generation**: Requesting a kettlebell swing video invokes `generate_workout_demonstration_video` with **`gemini-omni-flash-preview`** in the `global` region, uploading the generated video to Cloud Storage and displaying the public HTTPS video URL in an A2UI card.

---

## 🛠️ Implemented Features

### 1. Omni Model Video Demonstration Tool (`generate_workout_demonstration_video`)
- Generates 5-second exercise demonstration videos using `gemini-omni-flash-preview` (Vertex AI, `global` region).
- **Artifact Saving**: Calls `await tool_context.save_artifact(...)` for ADK Playground visibility.
- **Cloud Storage Upload**: Uploads video bytes directly to public GCS bucket (`fitpulse-media-qwiklabs-gcp-01-be9dafaef3b9`).
- Returns public HTTPS URL (`https://storage.googleapis.com/fitpulse-media-qwiklabs-gcp-01-be9dafaef3b9/...`).

### 2. Firestore Workout Catalog & Logging
- **WOD Retrieval**: `search_workouts` and `get_workout_details` query Firestore for workouts by category, equipment, and duration.
- **Session Logging**: `log_completed_workout` logs scores, times, and scaling notes directly into Firestore.

### 3. Long-Term Memory (Vertex AI Memory Bank)
- Integrates `VertexAiMemoryBankService` and `PreloadMemoryTool` to persist fitness goals, equipment, and user preferences across conversation turns.

### 4. Image & Visual Generation
- `generate_domain_image`: Generates fitness equipment and posture imagery using `gemini-3.1-flash-lite-image`.
- `generate_workout_visual`: Generates SVG visual cards for WOD routines using `gemini-2.5-flash`.

### 5. A2UI Glassmorphism Frontend
- FastAPI proxy translating A2A protocol calls to Agent Runtime.
- Custom dark glassmorphism chat UI featuring example prompt chips, auto-filtering of warnings, and native rendering of A2UI cards and video embeds.

---

## 📁 Repository Structure
- `app/agent.py`: ADK Agent definition, tool registrations, Memory Bank service, and A2UI callbacks.
- `frontend/`: FastAPI A2A proxy (`main.py`) and HTML/CSS/JS frontend (`static/index.html`).
- `README.md`: Project documentation and local run instructions.
- `fitpulse_demo.gif`: Recorded demo GIF.
- `walkthrough.md`: Project walkthrough and architecture summary.
