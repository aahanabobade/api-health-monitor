from fastapi import FastAPI, Query
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from typing import List
import httpx, asyncio, time, os
from dotenv import load_dotenv
import os
app = FastAPI()
load_dotenv()

# --- Google API config ---
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
CSE_ID = os.getenv("CSE_ID")

# --------- Static files setup ----------
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
STATIC_DIR = os.path.join(BASE_DIR, "static")
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


# --------- Frontend ----------
@app.get("/", response_class=HTMLResponse)
async def serve_ui():
    with open(os.path.join(STATIC_DIR, "index.html"), "r", encoding="utf-8") as f:
        return f.read()


# --------- Suggest endpoint (Google Custom Search) ----------
@app.get("/suggest")
async def suggest(query: str = Query(..., description="Search query")):
    search_url = "https://www.googleapis.com/customsearch/v1"
    params = {
        "key": GOOGLE_API_KEY,
        "cx": CSE_ID,
        "q": query,
        "num": 5
    }

    async with httpx.AsyncClient() as client:
        try:
            res = await client.get(search_url, params=params)
            data = res.json()
            urls = [item["link"] for item in data.get("items", [])]
            return JSONResponse(urls)
        except Exception as e:
            return JSONResponse([], status_code=500)


# --------- Single Health Check ----------
@app.get("/health")
async def check_health(
    url: str = Query(..., description="API URL to check"),
    retries: int = 2
):
    timeout = httpx.Timeout(5.0)
    attempt = 0
    last_error = None

    while attempt <= retries:
        start_time = time.time()

        try:
            async with httpx.AsyncClient(timeout=timeout) as client:
                response = await client.get(url, follow_redirects=True)

            response_time = round((time.time() - start_time) * 1000, 2)

            return {
                "url": url,
                "status": "UP",
                "status_code": response.status_code,
                "response_time_ms": response_time,
                "attempts": attempt + 1
            }

        except (httpx.ConnectTimeout, httpx.RequestError) as e:
            last_error = str(e)
            attempt += 1
            await asyncio.sleep(1)

    return {
        "url": url,
        "status": "DOWN",
        "error": "All retries failed",
        "attempts": retries + 1,
        "last_error": last_error
    }


# --------- Bulk Health Check ----------
@app.post("/health/bulk")
async def bulk_health_check(urls: List[str]):
    async def check(url: str):
        timeout = httpx.Timeout(5.0)

        try:
            start = time.time()
            async with httpx.AsyncClient(timeout=timeout) as client:
                response = await client.get(url, follow_redirects=True)

            return {
                "url": url,
                "status": "UP",
                "status_code": response.status_code,
                "response_time_ms": round((time.time() - start) * 1000, 2)
            }

        except Exception as e:
            return {
                "url": url,
                "status": "DOWN",
                "error": str(e)
            }

    results = await asyncio.gather(*(check(url) for url in urls))
    return {"total": len(urls), "results": results}
