from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from database import connect_to_retool,get_candidates_db,get_dashboard,get_rrf_details,update_associate_status,update_rrf_status,insert_into_allocation_table
import pandas as pd
import google.generativeai as genai
import os
import json
from typing import Dict, Any
from openai import AzureOpenAI
from pydantic import BaseModel


app = FastAPI()


# Configure Gemini API
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
if not GEMINI_API_KEY:
    print("Warning: GEMINI_API_KEY environment variable not set")
else:
    genai.configure(api_key=GEMINI_API_KEY)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allows all origins
    allow_credentials=True,
    allow_methods=["*"],  # Allows all methods
    allow_headers=["*"],  # Allows all headers
)

# Create a simple endpoint that returns "Hello World"


def get_azure_response(text):
    try:
        endpoint = "https://defaultresourcegroup-ccan-resource-0475.cognitiveservices.azure.com/"
        deployment = "gpt-4.1-mini-312634"
        subscription_key = os.environ.get("AZURE_AI_API_KEY")
        api_version = "2024-12-01-preview"
 
        if not subscription_key:
            return "Error: AZURE_OPENAI_KEY not found in environment variables"
 
        client = AzureOpenAI(
            api_version=api_version,
            azure_endpoint=endpoint,
            api_key=subscription_key,
        )
 
        response = client.chat.completions.create(
            messages=[
                {
                    "role": "system",
                    "content": "You are a helpful assistant.",
                },
                {
                    "role": "user",
                    "content": text,
                }
            ],
            max_tokens=1000,
            temperature=0.7,
            model=deployment
        )
 
        return response.choices[0].message.content
    except Exception as e:
        # AI_ERROR_COUNT.labels(model='azure', error_type=type(e).__name__).inc()
        return f"Azure Error: {str(e)}"
 



def call_gemini_api(df1: pd.DataFrame, df2: pd.DataFrame) -> Dict[str, Any]:
    """
    Call Gemini API to get AI-powered matching between candidates and job requirements.
    
    Args:
        df1: DataFrame with candidate details (vamid, grade, designation, primary skill, secondary skill)
        df2: DataFrame with RRF details (rrf_id, pos_title, role, account)
        
    Returns:
        Dict containing AI analysis and matching recommendations
    """
    try:
        if not GEMINI_API_KEY:
            return {"error": "Gemini API key not configured"}
        
        # Convert DataFrames to JSON for better API consumption
        candidates_data = df1.to_json(orient='records', indent=2)
        rrf_data = df2.to_json(orient='records', indent=2)
        
        # Create the prompt for Gemini
        prompt = f"""
        You are an HR AI assistant specializing in candidate-to-role matching. 
        
        Given the following candidate data and role requirements, provide detailed matching analysis:
        
        CANDIDATES DATA:
        {candidates_data}
        
        ROLE REQUIREMENTS DATA:
        {rrf_data}
        
        Please analyze and provide:
        1. Top 3 candidate matches for each role requirement
        2. Matching score (0-100) for each candidate-role pair
        3. Reasoning for each match (A single line: skills alignment, experience level, etc.)
        4. Potential skill gaps and recommendations (A single line)
        5. Alternative role suggestions for candidates if primary matches are not ideal
        
        Format the response as a structured JSON with the following structure:
        {{
            "matches": [
                {{
                    "rrf_id": "string",
                    "pos_title": "string",
                    "recommended_candidates": [
                        {{
                            "vamid": "string",
                            "match_score": number,
                            "reasoning": "string",
                            "skill_alignment": "string",
                            "potential_gaps": ["string"]
                        }}
                    ]
                }}
            ],
        }}
        """
        
        # Initialize the Gemini model
        model = genai.GenerativeModel('gemini-2.5-flash')
        
        # Generate response
        response = model.generate_content(prompt)
        
        # Parse the response
        try:
            # Try to extract JSON from the response
            response_text = response.text
            
            # Find JSON content (sometimes Gemini wraps JSON in markdown)
            if "```json" in response_text:
                json_start = response_text.find("```json") + 7
                json_end = response_text.find("```", json_start)
                json_content = response_text[json_start:json_end].strip()
            else:
                json_content = response_text
            
            parsed_response = json.loads(json_content)
            
            return {
                "success": True,
                "gemini_analysis": parsed_response,
                # "raw_response": response_text
            }
            
        except json.JSONDecodeError:
            # If JSON parsing fails, return the raw text
            return {
                "success": True,
                "gemini_analysis": {"raw_analysis": response.text},
                "raw_response": response.text,
                "note": "Response was not in JSON format"
            }
            
    except Exception as e:
        print(f"Error calling Gemini API: {e}")
        return {
            "success": False,
            "error": f"Failed to call Gemini API: {str(e)}"
        }
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

@app.post("/update_position/{rrf_id}/{vam_id}")
def update_position(rrf_id: str, vam_id: str):
    try:
        rrf_status=update_rrf_status(rrf_id)
        associate_status=update_associate_status(vam_id)

        if rrf_status and associate_status:
            insert_into_allocation_table(rrf_id, vam_id)
            return {"message": f"Position updated for RRF ID: {rrf_id} and VAM ID: {vam_id}"}
    except Exception as e:
        print(f"Error updating position: {e}")
    return {"message": f"Failed to update position for RRF ID: {rrf_id} and VAM ID: {vam_id}"}





# @app.get("/matching")
# def get_matching_candidates():
#     try:
#         bench = get_candidates_db()
#         rrf = get_rrf_details()
#         df1=pd.DataFrame(bench)
#         df2=pd.DataFrame(rrf)
#         df1_update=df1[['vamid', 'grade', 'designation', 'current_skill', 'primary_skill']]
#         df2=df2[['rrf_id', 'pos_title', 'role', 'account']]
        
#         # Call Gemini API for AI-powered matching
#         gemini_response = call_gemini_api(df1_update, df2)
        
#         return {
#             "ai_matching": gemini_response
#         }
#     except Exception as e:
#         print(f"Error in matching: {e}")
#         return {"error": "An error occurred while processing the request"}


@app.get("/matching")
def get_matching_candidates():
    try:
        bench = get_candidates_db()
        rrf = get_rrf_details()

        df1 = pd.DataFrame(bench)
        df2 = pd.DataFrame(rrf)

        df1_update = df1[['vamid', 'grade', 'designation', 'current_skill', 'primary_skill']]
        df2 = df2[['rrf_id', 'pos_title', 'role', 'account']]

        # Call Gemini
        gemini_response = call_gemini_api(df1_update, df2)

        # Build employee lookup
        employee_lookup = (
            df1
            .set_index("vamid")
            .to_dict(orient="index")
        )

        # Enrich response
        for match in gemini_response["gemini_analysis"]["matches"]:
            for candidate in match.get("recommended_candidates", []):
                vamid = candidate.get("vamid")
                candidate["employee_details"] = employee_lookup.get(vamid)

        return {
            "ai_matching": gemini_response
        }

    except Exception as e:
        print(f"Error in matching: {e}")
        return {"error": "An error occurred while processing the request"}


@app.post("/gemini/analyze")
async def analyze_with_gemini(prompt: str):
    """
    Direct endpoint to test Gemini API with custom prompts.
    """
    try:
        if not GEMINI_API_KEY:
            raise HTTPException(status_code=500, detail="Gemini API key not configured")
        
        model = genai.GenerativeModel('gemini-pro')
        response = model.generate_content(prompt)
        
        return {
            "success": True,
            "response": response.text,
            "prompt": prompt
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error calling Gemini API: {str(e)}")



# Run the application
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
