from fastapi import FastAPI
from pydantic import BaseModel
from typing import Optional
from playwright.async_api import async_playwright
import asyncio
import time

app = FastAPI()

class ImageResponse(BaseModel):
    success: bool
    image_url: Optional[str] = None
    processing_time: Optional[float] = None
    error: Optional[str] = None
    detail: Optional[str] = None

# Concurrency control
MAX_CONCURRENT = 5  # Keep lower for Vercel Lambda limits
semaphore = asyncio.Semaphore(MAX_CONCURRENT)

@app.get("/generate-image/prompt={prompt}", response_model=ImageResponse)
async def generate_image(prompt: str):
    async with semaphore:
        start_time = time.time()
        image_url = None

        try:
            async with async_playwright() as pw:
                browser = await pw.chromium.launch(
                    headless=True,
                    args=["--no-sandbox", "--disable-setuid-sandbox"]
                )
                context = await browser.new_context()
                page = await context.new_page()

                await page.goto("https://vheer.com/app/text-to-image", wait_until="domcontentloaded")
                await page.fill("textarea", prompt)

                async def handle_response(response):
                    nonlocal image_url
                    if (
                        "https://access.vheer.com/api/Vheer/UploadByFileNew" in response.url
                        and response.request.method == "POST"
                    ):
                        try:
                            res_json = await response.json()
                            if res_json.get("code") == 200:
                                code_val = res_json.get("data", {}).get("code")
                                if code_val:
                                    image_url = f"https://access.vheer.com/results/{code_val}.jpg"
                        except:
                            pass

                page.on("response", handle_response)

                await page.click("button:has-text('Generate')")
                
                # Wait until we get the API response instead of fixed timeout
                await page.wait_for_response(
                    lambda r: "UploadByFileNew" in r.url and r.request.method == "POST",
                    timeout=30000
                )

                await page.close()
                await context.close()
                await browser.close()

                if not image_url:
                    return ImageResponse(success=False, error="Image URL not found")

                elapsed_time = round(time.time() - start_time, 2)
                return ImageResponse(success=True, image_url=image_url, processing_time=elapsed_time)

        except Exception as e:
            return ImageResponse(success=False, error="Image generation failed", detail=str(e))
