# ruff: noqa
# Copyright 2026 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     https://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import base64
import datetime
import json
import os
from pathlib import Path
import re
import subprocess
import urllib.request
import uuid

from a2ui.basic_catalog.provider import BasicCatalog
from a2ui.schema.manager import A2uiSchemaManager
import google.auth
import google.oauth2.credentials
from google import genai
from google.cloud import firestore, storage

from google.adk.agents import Agent
from google.adk.agents.callback_context import CallbackContext
from google.adk.apps import App
from google.adk.code_executors import AgentEngineSandboxCodeExecutor
from google.adk.memory import VertexAiMemoryBankService
from google.adk.models import Gemini
from google.adk.tools import ToolContext
from google.adk.tools.preload_memory_tool import PreloadMemoryTool
from google.genai import types

from app.a2ui_utils import a2ui_callback

# Hardcoded Project ID, Bucket Name, and Memory Bank ID as required
PROJECT_ID = "qwiklabs-gcp-01-be9dafaef3b9"
BUCKET_NAME = "fitpulse-media-qwiklabs-gcp-01-be9dafaef3b9"
MEMORY_BANK_ID = "624752402506973184"

# Load Agent Engine resource name from deployment_metadata.json
_metadata_path = Path(__file__).parent.parent / "deployment_metadata.json"
_agent_engine_resource_name = f"projects/{PROJECT_ID}/locations/us-east1/reasoningEngines/{MEMORY_BANK_ID}"

if _metadata_path.exists():
    try:
        with open(_metadata_path, "r", encoding="utf-8") as f:
            _meta = json.load(f)
            _agent_engine_resource_name = _meta.get("remote_agent_runtime_id", _agent_engine_resource_name)
    except Exception:
        pass

code_executor = AgentEngineSandboxCodeExecutor(
    agent_engine_resource_name=_agent_engine_resource_name
)

# A2UI Schema Manager setup (v0.8 with BasicCatalog)
schema_manager = A2uiSchemaManager(
    version="0.8",
    catalogs=[BasicCatalog.get_config("0.8")],
)

a2ui_instruction = schema_manager.generate_system_prompt(
    role_description=(
        "You are FitPulse, a personal daily trainer and CrossFit/HIIT coach. "
        "You remember facts, goals, injuries, and preferences shared by the user across conversations. "
        "Use search_workouts to search the Firestore database for workouts by category, equipment, or duration. "
        "Use get_workout_details to fetch full details for a workout. "
        "Use log_completed_workout to save completed workouts into Firestore. "
        "Use generate_workout_visual to create a visual graphic card for a workout and upload it to Cloud Storage. "
        "Use search_external_exercise_database to fetch real-world exercise technique, targeted muscles, and equipment requirements from the public wger API. "
        "Use generate_domain_image to generate photo-realistic fitness gear or exercise images with gemini-3.1-flash-lite-image and upload them to Cloud Storage. "
        "Use generate_workout_demonstration_video to generate short exercise movement or routine demonstration videos with gemini-omni-flash-preview and upload them to Cloud Storage. "
        "You also have a python code_executor sandbox! Use Python code execution to perform calculations when requested."
    ),
    workflow_description="Analyze the user request and return structured A2UI UI cards when appropriate.",
    ui_description=(
        "Keep every surface tiny and flat: ONE Card > ONE Column > a few Text rows. "
        "Never nest a Card inside a Card. "
        "Use ONLY these components: Card, Column, Row, Text, and Image. Do not use "
        "Table or Heading (unsupported), or Buttons, actions, or forms (they do "
        "nothing in adk web). "
        "You may include one Image component, but only when you have a public https "
        "URL for the image (for example the URL an image tool returns after uploading "
        "to a public bucket). Set the Image url to that exact https link, for example "
        '{"Image": {"url": {"literalString": "https://..."}}}. Never point an '
        "Image at a bare filename, an artifact name, or a non-http(s) path. If you do "
        "not have a public URL, add a short Text line noting the image instead. "
        "No markdown in text; use the usageHint property ('h1', 'h2', 'body') for "
        "headings and emphasis. "
        "Output ONLY valid A2UI JSON without wrapping in <a2ui-json> or <a2a_datapart_json> tags."
    ),
    include_schema=True,
    include_examples=True,
)


async def generate_memories_callback(callback_context: CallbackContext):
    """Sends completed turn/session events to Vertex AI Memory Bank for long-term extraction."""
    try:
        await callback_context.add_session_to_memory()
    except Exception:
        pass
    return None


def memory_bank_service_builder():
    """Builds VertexAiMemoryBankService pointing to the deployed Memory Bank Agent Engine instance."""
    return VertexAiMemoryBankService(
        project=PROJECT_ID,
        location="us-east1",
        agent_engine_id=MEMORY_BANK_ID,
    )


def _get_db() -> firestore.Client:
    """Returns a Firestore client pinned to the hardcoded PROJECT_ID."""
    try:
        token = subprocess.check_output(["gcloud", "auth", "print-access-token"], text=True).strip()
        creds = google.oauth2.credentials.Credentials(token)
        return firestore.Client(project=PROJECT_ID, credentials=creds)
    except Exception:
        return firestore.Client(project=PROJECT_ID)


def _get_gcs_client() -> storage.Client:
    """Returns a Storage client pinned to the hardcoded PROJECT_ID."""
    try:
        token = subprocess.check_output(["gcloud", "auth", "print-access-token"], text=True).strip()
        creds = google.oauth2.credentials.Credentials(token)
        return storage.Client(project=PROJECT_ID, credentials=creds)
    except Exception:
        return storage.Client(project=PROJECT_ID)


def search_workouts(category: str = "", equipment: str = "", max_duration: int = 0) -> list[dict]:
    """Search available workouts and WODs from the Firestore backend database.

    Args:
        category: Optional category filter (e.g. "CrossFit Benchmark", "HIIT Interval").
        equipment: Optional equipment keyword filter (e.g. "pull-up bar", "barbell", "kettlebell", "mat").
        max_duration: Optional maximum workout duration in minutes.

    Returns:
        A list of matching workout dictionaries found in Firestore.
    """
    db = _get_db()
    docs = db.collection("workouts").stream()
    results = []

    cat_filter = category.lower().strip() if category else ""
    eq_filter = equipment.lower().strip() if equipment else ""

    for doc in docs:
        data = doc.to_dict()
        if not data:
            continue

        if cat_filter and cat_filter not in data.get("category", "").lower():
            continue

        if eq_filter:
            eq_list = [e.lower() for e in data.get("equipment_needed", [])]
            if not any(eq_filter in eq for eq in eq_list):
                continue

        if max_duration > 0 and data.get("duration_minutes", 0) > max_duration:
            continue

        results.append(data)

    return results


def get_workout_details(workout_id: str) -> dict:
    """Get full details for a specific workout document by ID from Firestore.

    Args:
        workout_id: The document ID of the workout (e.g. "wod_fran", "wod_cindy", "hiit_tabata_core").

    Returns:
        A dictionary containing the workout details or an error message if not found.
    """
    db = _get_db()
    doc_ref = db.collection("workouts").document(workout_id.strip())
    doc = doc_ref.get()

    if doc.exists:
        return doc.to_dict()
    return {"error": f"Workout with ID '{workout_id}' not found in Firestore."}


def log_completed_workout(workout_id: str, user_notes: str = "", score_or_time: str = "") -> dict:
    """Log a completed workout session into the Firestore database.

    Args:
        workout_id: The ID or title of the workout completed (e.g. "wod_fran" or "Fran").
        user_notes: Optional notes on how the session went, scaling used, or energy level.
        score_or_time: Optional completion time or score (e.g. "4:15", "18 rounds + 5 reps").

    Returns:
        A summary dictionary confirming the workout log was created in Firestore.
    """
    db = _get_db()
    timestamp = datetime.datetime.now(datetime.timezone.utc).isoformat()
    log_doc = {
        "workout_id": workout_id,
        "score_or_time": score_or_time,
        "user_notes": user_notes,
        "logged_at": timestamp,
    }

    ref = db.collection("workout_logs").document()
    ref.set(log_doc)

    return {
        "status": "success",
        "log_id": ref.id,
        "workout_id": workout_id,
        "score_or_time": score_or_time,
        "logged_at": timestamp,
        "message": "Workout successfully logged in Firestore!",
    }


def generate_workout_visual(workout_title: str, exercise_description: str = "") -> dict:
    """Generates a custom SVG visual graphic card for a workout routine and uploads it to Cloud Storage.

    Args:
        workout_title: Title of the workout (e.g., "Cindy", "Fran", "Tabata Core Blaster").
        exercise_description: Brief description or list of movements in the workout.

    Returns:
        A dictionary containing the public Cloud Storage image URL, caption, and GCS URI.
    """
    try:
        genai_client = genai.Client(vertexai=True, project=PROJECT_ID, location="us-central1")
        prompt = (
            f"Create a beautiful, modern, vibrant 800x600 SVG graphic card illustrating a workout titled '{workout_title}'. "
            f"Context: {exercise_description}. "
            "Return ONLY the raw valid <svg>...</svg> XML tag without any markdown code blocks or surrounding text."
        )

        res = genai_client.models.generate_content(model="gemini-2.5-flash", contents=prompt)
        raw_text = res.text or ""

        svg_match = re.search(r"(<svg[\s\S]*?</svg>)", raw_text, re.IGNORECASE)
        if svg_match:
            svg_content = svg_match.group(1)
        else:
            svg_content = raw_text.strip()

        svg_content = re.sub(r"^```[a-z]*", "", svg_content, flags=re.MULTILINE)
        svg_content = re.sub(r"```$", "", svg_content, flags=re.MULTILINE).strip()

        gcs_client = _get_gcs_client()
        bucket = gcs_client.bucket(BUCKET_NAME)

        safe_slug = re.sub(r"[^\w]+", "_", workout_title.lower()).strip("_")
        filename = f"workout_visuals/{safe_slug}_{uuid.uuid4().hex[:8]}.svg"
        blob = bucket.blob(filename)
        blob.upload_from_string(svg_content, content_type="image/svg+xml")

        public_url = f"https://storage.googleapis.com/{BUCKET_NAME}/{filename}"
        return {
            "status": "success",
            "workout_title": workout_title,
            "public_image_url": public_url,
            "gcs_uri": f"gs://{BUCKET_NAME}/{filename}",
            "caption": f"Visual graphic card for {workout_title}",
        }
    except Exception as e:
        return {
            "status": "error",
            "error_message": f"Failed to generate workout visual: {str(e)}",
        }


def search_external_exercise_database(exercise_name: str) -> list[dict]:
    """Search for exercise technique guides, targeted muscles, and equipment from the public wger Workout Manager API.

    Args:
        exercise_name: Keyword or exercise name to search for (e.g., "press", "squat", "curl", "lunge").

    Returns:
        A list of exercise dictionaries containing exercise names, targeted muscle groups, equipment required, and technique guides.
    """
    api_key = os.environ.get("WGER_API_KEY", "")
    url = "https://wger.de/api/v2/exerciseinfo/?limit=50"

    headers = {"User-Agent": "FitPulse-Agent/1.0"}
    if api_key:
        headers["Authorization"] = f"Token {api_key}"

    try:
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req) as resp:
            data = json.loads(resp.read().decode())

        results = []
        query = exercise_name.lower().strip()

        for item in data.get("results", []):
            for trans in item.get("translations", []):
                if trans.get("language") == 2:  # English
                    name = trans.get("name", "")
                    if query in name.lower():
                        category = item.get("category", {}).get("name", "")
                        muscles = [m.get("name") for m in item.get("muscles", []) if m.get("name")]
                        equipment = [e.get("name") for e in item.get("equipment", []) if e.get("name")]
                        desc = trans.get("description_source") or trans.get("description", "")
                        desc_clean = re.sub(r"<[^>]+>", "", desc).strip()
                        results.append({
                            "name": name,
                            "category": category,
                            "muscles_targeted": muscles,
                            "equipment_required": equipment,
                            "technique_guide": desc_clean[:300],
                        })

        return results[:5] if results else [{"message": f"No external exercise technique found for query '{exercise_name}'."}]
    except Exception as e:
        return [{"error": f"Failed to fetch external exercise data: {str(e)}"}]


async def generate_domain_image(
    prompt: str,
    tool_context: ToolContext = None,
) -> dict:
    """Generates a high quality fitness image (gear, exercise, or routine item) using gemini-3.1-flash-lite-image in the global region.

    Saves the generated image as an artifact in the Playground and uploads it directly to Cloud Storage, returning its public HTTPS URL.

    Args:
        prompt: Detailed description of the fitness image to generate (e.g., "A heavy kettlebell on a rubber gym floor").
        tool_context: ADK ToolContext provided automatically by the runtime.

    Returns:
        A dictionary containing the public Cloud Storage HTTPS URL of the generated image.
    """
    try:
        genai_client = genai.Client(vertexai=True, project=PROJECT_ID, location="global")
        response = genai_client.models.generate_content(
            model="gemini-3.1-flash-lite-image",
            contents=f"Generate a high quality fitness image of: {prompt}",
            config=types.GenerateContentConfig(
                response_modalities=["TEXT", "IMAGE"]
            ),
        )

        image_bytes = None
        mime_type = "image/jpeg"

        if response.candidates and response.candidates[0].content.parts:
            for part in response.candidates[0].content.parts:
                if part.inline_data and part.inline_data.data:
                    image_bytes = part.inline_data.data
                    if part.inline_data.mime_type:
                        mime_type = part.inline_data.mime_type
                    break

        if not image_bytes:
            return {"status": "error", "error_message": "No image bytes were returned by gemini-3.1-flash-lite-image."}

        safe_slug = re.sub(r"[^\w]+", "_", prompt.lower()[:30]).strip("_")
        ext = "png" if "png" in mime_type else "jpg"
        filename = f"{safe_slug}_{uuid.uuid4().hex[:8]}.{ext}"

        if tool_context:
            artifact_part = types.Part.from_bytes(data=image_bytes, mime_type=mime_type)
            await tool_context.save_artifact(filename=filename, artifact=artifact_part)

        gcs_client = _get_gcs_client()
        bucket = gcs_client.bucket(BUCKET_NAME)
        gcs_object_path = f"workout_images/{filename}"
        blob = bucket.blob(gcs_object_path)
        blob.upload_from_string(image_bytes, content_type=mime_type)

        public_url = f"https://storage.googleapis.com/{BUCKET_NAME}/{gcs_object_path}"

        return {
            "status": "success",
            "prompt": prompt,
            "public_image_url": public_url,
            "filename": filename,
            "message": "Image successfully generated with gemini-3.1-flash-lite-image, saved as artifact, and uploaded to Cloud Storage!",
        }
    except Exception as e:
        return {
            "status": "error",
            "error_message": f"Failed to generate domain image: {str(e)}",
        }


async def generate_workout_demonstration_video(
    prompt: str,
    tool_context: ToolContext = None,
) -> dict:
    """Generates a short demonstration video for a CrossFit/HIIT exercise technique or routine using gemini-omni-flash-preview in the global region.

    Saves the generated video as an artifact in the Playground's Artifacts panel and uploads it directly to Cloud Storage, returning its public HTTPS URL.

    Args:
        prompt: Detailed description of the exercise form or workout item to generate a video for (e.g. "An athlete performing a kettlebell swing with proper hip hinge").
        tool_context: ADK ToolContext provided automatically by the runtime.

    Returns:
        A dictionary containing the public Cloud Storage HTTPS URL of the generated video.
    """
    try:
        genai_client = genai.Client(vertexai=True, project=PROJECT_ID, location="global")
        interaction = genai_client.interactions.create(
            model="gemini-omni-flash-preview",
            input=f"Short 5-second video demonstrating: {prompt}",
        )

        video_bytes = None

        # 1. Check output_video attribute
        if hasattr(interaction, "output_video") and interaction.output_video:
            data = getattr(interaction.output_video, "data", None)
            if data:
                video_bytes = base64.b64decode(data) if isinstance(data, str) else data

        # 2. Fallback: inspect steps in interaction
        if not video_bytes and hasattr(interaction, "steps") and interaction.steps:
            for step in interaction.steps:
                for content in getattr(step, "content", []) or []:
                    d = getattr(content, "data", None)
                    mime = getattr(content, "mime_type", "") or ""
                    if d and ("video" in mime or getattr(content, "type", "") == "video"):
                        video_bytes = base64.b64decode(d) if isinstance(d, str) else d
                        break

        if not video_bytes:
            return {
                "status": "error",
                "error_message": "No video bytes were returned by gemini-omni-flash-preview.",
            }

        safe_slug = re.sub(r"[^\w]+", "_", prompt.lower()[:30]).strip("_")
        filename = f"{safe_slug}_{uuid.uuid4().hex[:8]}.mp4"

        # (1) Save video as artifact so it shows up in Playground's Artifacts panel
        if tool_context:
            artifact_part = types.Part.from_bytes(data=video_bytes, mime_type="video/mp4")
            await tool_context.save_artifact(filename=filename, artifact=artifact_part)

        # (2) Upload same video bytes to the public Cloud Storage bucket and return public HTTPS URL
        gcs_client = _get_gcs_client()
        bucket = gcs_client.bucket(BUCKET_NAME)
        gcs_object_path = f"workout_videos/{filename}"
        blob = bucket.blob(gcs_object_path)
        blob.upload_from_string(video_bytes, content_type="video/mp4")

        public_url = f"https://storage.googleapis.com/{BUCKET_NAME}/{gcs_object_path}"

        return {
            "status": "success",
            "prompt": prompt,
            "public_video_url": public_url,
            "filename": filename,
            "message": "Video successfully generated with gemini-omni-flash-preview, saved as artifact, and uploaded to Cloud Storage!",
        }
    except Exception as e:
        return {
            "status": "error",
            "error_message": f"Failed to generate workout demonstration video: {str(e)}",
        }


root_agent = Agent(
    name="root_agent",
    model=Gemini(
        model="gemini-2.5-flash",
        retry_options=types.HttpRetryOptions(attempts=3),
    ),
    code_executor=code_executor,
    instruction=a2ui_instruction,
    tools=[
        PreloadMemoryTool(),
        search_workouts,
        get_workout_details,
        log_completed_workout,
        generate_workout_visual,
        search_external_exercise_database,
        generate_domain_image,
        generate_workout_demonstration_video,
    ],
    after_agent_callback=generate_memories_callback,
    after_model_callback=a2ui_callback,
)

app = App(
    root_agent=root_agent,
    name="app",
)
