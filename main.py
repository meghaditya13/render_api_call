# main.py
from fastapi import FastAPI, Request
from pydantic import BaseModel
from summarize import summarize_policy
import uvicorn
import json #edited

app = FastAPI()

class PolicyRequest(BaseModel):
    url: str

@app.post("/summarize")
async def summarize(request: PolicyRequest):
    try:
        summary = await summarize_policy(request.url)
        return {"summary": json.loads(summary)} ## edited 
    except Exception as e:
        import traceback
        print("ERROR:", str(e))
        traceback.print_exc()
        return {"error": str(e) or "Unknown error"}


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8000))  # using 8000 locally 
    uvicorn.run("main:app", host="0.0.0.0", port=port)

    
