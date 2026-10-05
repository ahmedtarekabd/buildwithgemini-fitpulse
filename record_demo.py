import asyncio
import os
from pathlib import Path
from playwright.async_api import async_playwright

FRONTEND_URL = "https://fitpulse-frontend-645014289880.us-east1.run.app"
ARTIFACTS_DIR = "/config/.gemini/antigravity/brain/ccfd054f-593a-4837-b930-2f35430de591"

async def main():
    os.makedirs(ARTIFACTS_DIR, exist_ok=True)
    temp_video_dir = os.path.join(ARTIFACTS_DIR, "demo_recordings")
    os.makedirs(temp_video_dir, exist_ok=True)

    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=True,
            args=["--no-sandbox", "--disable-setuid-sandbox"]
        )
        context = await browser.new_context(
            viewport={"width": 1280, "height": 720},
            record_video_dir=temp_video_dir,
            record_video_size={"width": 1280, "height": 720}
        )
        page = await context.new_page()

        print(f"1. Navigating to {FRONTEND_URL}...")
        await page.goto(FRONTEND_URL, wait_until="networkidle")
        await asyncio.sleep(3)

        print("2. Clicking example prompt chip for Benchmark WODs...")
        # Click the first example chip button
        await page.click(".chip-btn")

        print("3. Waiting for first agent response with A2UI cards...")
        await asyncio.sleep(12)

        print("4. Typing second richer prompt for Omni video generation tool...")
        await page.fill("#input", "Generate a short workout video showing a kettlebell swing with proper form")
        await asyncio.sleep(1)

        print("5. Submitting second prompt...")
        await page.click("form button[type='submit']")

        print("6. Waiting for video generation tool call & response...")
        await asyncio.sleep(35)

        print("7. Finishing recording...")
        await asyncio.sleep(5)

        video_path = await page.video.path()
        await context.close()
        await browser.close()

        final_video_path = os.path.join(ARTIFACTS_DIR, "fitpulse_demo.webm")
        if video_path and os.path.exists(video_path):
            os.rename(video_path, final_video_path)
            print(f"✅ Demo video recorded and saved to: {final_video_path}")
        else:
            print("⚠️ Video recording path not found.")

if __name__ == "__main__":
    asyncio.run(main())
