from fastapi import FastAPI

app = FastAPI(title="Job Radar API", version="0.2.0")

@app.get("/")
async def root():
    return {"message": "Job Radar API is running"}

@app.get("/jobs")
async def get_jobs():
    return [{"id": 1, "title": "Junior Software Engineer"}]
