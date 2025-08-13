import chromium from "playwright-aws-lambda";

export default async function handler(req, res) {
  // Extract prompt from URL path `/generate-image/prompt=xxx`
  const path = req.url || "";
  const match = path.match(/\/generate-image\/prompt=(.+)/);
  const prompt = match ? decodeURIComponent(match[1]) : null;

  if (!prompt) {
    return res.status(400).json({ success: false, error: "Prompt is required" });
  }

  const startTime = Date.now();
  let imageUrl = null;

  try {
    const browser = await chromium.launchChromium({
      args: chromium.args,
      executablePath: await chromium.executablePath(),
      headless: chromium.headless
    });

    const context = await browser.newContext();
    const page = await context.newPage();

    await page.goto("https://vheer.com/app/text-to-image", { waitUntil: "domcontentloaded" });
    await page.fill("textarea", prompt);

    page.on("response", async (response) => {
      if (
        response.url().includes("https://access.vheer.com/api/Vheer/UploadByFileNew") &&
        response.request().method() === "POST"
      ) {
        try {
          const resJson = await response.json();
          if (resJson.code === 200) {
            const codeVal = resJson?.data?.code;
            if (codeVal) {
              imageUrl = `https://access.vheer.com/results/${codeVal}.jpg`;
            }
          }
        } catch {}
      }
    });

    await page.click("button:has-text('Generate')");
    await page.waitForResponse(
      (r) =>
        r.url().includes("UploadByFileNew") &&
        r.request().method() === "POST",
      { timeout: 30000 }
    );

    await browser.close();

    if (!imageUrl) {
      return res.status(404).json({ success: false, error: "Image URL not found" });
    }

    const elapsedTime = ((Date.now() - startTime) / 1000).toFixed(2);
    return res.status(200).json({
      success: true,
      image_url: imageUrl,
      processing_time: elapsedTime
    });

  } catch (err) {
    return res.status(500).json({
      success: false,
      error: "Image generation failed",
      detail: err.message
    });
  }
}
