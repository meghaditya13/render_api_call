# main.py
from fastapi import FastAPI, Request
from pydantic import BaseModel
from summarize import summarize_policy
import uvicorn

app = FastAPI()

class PolicyRequest(BaseModel):
    url: str

@app.post("/summarize")
async def summarize(request: PolicyRequest):
    try:
        summary = await summarize_policy(request.url)
        return {"summary": summary}
    except Exception as e:
        return {"error": str(e)}

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8000))  # using 8000 locally 
    uvicorn.run("main:app", host="0.0.0.0", port=port)

    
