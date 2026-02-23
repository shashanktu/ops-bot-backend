from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from database import connect_to_retool,get_candidates_db,get_dashboard,get_rrf_details

# Create FastAPI instance
app = FastAPI()

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allows all origins
    allow_credentials=True,
    allow_methods=["*"],  # Allows all methods
    allow_headers=["*"],  # Allows all headers
)

# Create a simple endpoint that returns "Hello World"
@app.get("/")
async def read_root():
    return {"message": "Hello World"}

# Additional endpoint with path parameter
@app.get("/hello/{name}")
async def say_hello(name: str):
    return {"message": f"Hello {name}"}


@app.get("/candidates")
async def get_candidates():
    candidates = get_candidates_db()
    return {"candidates": candidates}


@app.get("/dashboard")
async def get_dashboard_data():
    value = get_dashboard()
    return {"value": value}


@app.get("/rrf")
def get_rrf():
    rrf = get_rrf_details()
    return {"rrf": rrf}

@app.get("/get_all_details")
def get_all_details():
    bench_details = get_candidates_db()
    rrf_details = get_rrf_details()
    return {"bench_details": bench_details, "rrf_details": rrf_details}

@app.post("/update_position/{rrf_id}")
def update_position(rrf_id: str):
    # Logic to update the position for the given rrf_id
    return {"message": f"Position updated for RRF ID: {rrf_id}"}

# Run the application
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
