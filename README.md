# FitPulse — Personal Daily Trainer & CrossFit/HIIT Coach ⚡

FitPulse is an AI-powered fitness assistant built with Google's **Agent Development Kit (ADK)** and deployed on **Agent Platform (Agent Runtime)**. It provides personalized CrossFit WOD recommendations, HIIT interval planning, exercise technique guides, exercise demonstration videos, and workout logging.

![FitPulse Demo](fitpulse_demo.gif)

---

## 🚀 Key Features & Implemented Capabilities

Based strictly on the codebase in `app/`, FitPulse implements the following tools and capabilities:

- **🏋️ Firestore Workout Database**:
  - `search_workouts`: Queries a Google Cloud Firestore collection (`workouts`) for CrossFit benchmark WODs and HIIT routines filtered by duration, equipment (e.g., pull-up bar, barbell, kettlebell), and category.
  - `get_workout_details`: Fetches complete workout specifications, target muscle groups, and movement breakdowns by ID.
  - `log_completed_workout`: Records completed workout sessions, scores/times, and scaling notes directly into Firestore (`workout_logs`).

- **🧠 Cross-Session Long-Term Memory**:
  - **Vertex AI Memory Bank**: Integrates `VertexAiMemoryBankService` and `PreloadMemoryTool` to automatically extract and remember user fitness goals, fitness level, available home/gym equipment, injury history, and past completed WODs across conversation turns.

- **🎥 Omni Model Video Generation**:
  - `generate_workout_demonstration_video`: Uses Google's Omni model (**`gemini-omni-flash-preview`**) in the `global` region to generate short 5-second videos demonstrating proper exercise form and movement mechanics.
  - Saves videos to the Playground's Artifacts panel via `tool_context.save_artifact` and uploads MP4 bytes directly to a public Cloud Storage bucket, returning public HTTPS URLs.

- **🖼️ Image & SVG Visual Generation**:
  - `generate_domain_image`: Generates photo-realistic fitness gear and exercise visuals using **`gemini-3.1-flash-lite-image`** in the `global` region and uploads them to Cloud Storage.
  - `generate_workout_visual`: Generates custom SVG graphic cards for workout routines using `gemini-2.5-flash` and stores them in Cloud Storage.

- **📱 A2UI Rich Display Cards**:
  - Uses the **Agent-to-User Interface (A2UI)** v0.8 Basic Catalog protocol to emit structured cards, text blocks, and embedded media, rendered natively by the custom frontend.

- **📖 External Exercise Database Search**:
  - `search_external_exercise_database`: Queries the public `wger` Workout Manager API for exercise technique guides, targeted muscle groups, and equipment requirements.

- **🐍 Python Code Sandbox**:
  - `AgentEngineSandboxCodeExecutor`: Runs Python code execution inside an Agent Engine sandbox for computing work-to-rest interval ratios, target heart rate zones, and 1-rep max calculations.

---

## 🛠️ Google Cloud & Architecture Stack

| Layer | Service / Technology | Purpose |
| :--- | :--- | :--- |
| **Agent Framework** | Google ADK (`google.adk`) | Core agent orchestration & tool wiring |
| **Foundation Model** | `gemini-2.5-flash` | Primary reasoning and conversational logic |
| **Media Models** | `gemini-omni-flash-preview` & `gemini-3.1-flash-lite-image` | Video demonstration & image generation |
| **Long-Term Memory** | Vertex AI Memory Bank | Remembers user facts across sessions |
| **Database** | Google Cloud Firestore | Storage for workout catalog and user logs |
| **Media Storage** | Google Cloud Storage (GCS) | Bucket storage for generated SVG, images & videos |
| **Code Sandbox** | Agent Engine Sandbox | Isolated Python code executor |
| **Frontend Protocol** | Agent-to-Agent (A2A) & A2UI | Structured UI communication between proxy and agent |

*Note on planned features: Live timer notifications and Cloud Trace observability were brainstormed in the initial brief but are planned for future iterations and not yet implemented.*

---

## 💻 Local Setup & Development Instructions

### Prerequisites
- Python 3.11+
- `uv` package manager (`pip install uv`)
- Google Cloud SDK (`gcloud`) authenticated to your GCP project with permissions for Vertex AI, Firestore, and Cloud Storage.

### 1. Environment Setup
Clone the repository and set up a virtual environment:
```bash
git clone <your-repo-url>
cd fitpulse
uv venv
source .venv/bin/activate
uv pip install -r requirements.txt
```

### 2. Configure Environment Variables
Set the required Google Cloud variables:
```bash
export GOOGLE_CLOUD_PROJECT="<your-gcp-project-id>"
export GOOGLE_CLOUD_LOCATION="us-east1"
```

### 3. Running the Agent Locally
Run the agent locally using the ADK Web interface:
```bash
adk web app/agent.py
```

### 4. Running the Web Frontend Locally
Start the FastAPI proxy server pointing to your local or deployed agent:
```bash
cd frontend
uv run python main.py
```
Open your browser at `http://localhost:8080` to interact with the FitPulse chat UI.

---

## 📦 Deployment

To deploy the agent to Vertex AI Agent Runtime:
```bash
agents-cli deploy --no-confirm-project
```
