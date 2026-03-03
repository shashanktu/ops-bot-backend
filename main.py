from fastapi import FastAPI, HTTPException, File, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from database import (connect_to_retool,
                      get_candidates_db,
                      get_dashboard,
                      get_rrf_details,
                      update_associate_status,
                      update_rrf_status,
                      insert_into_allocation_table,
                      insert_into_bench_table,
                      insert_into_rrf_table,
                      clear_bench_table,
                      clear_rrf_table,
                      get_rrf_by_id,
                      get_allocated_candidates_db)
import pandas as pd
import google.generativeai as genai
import os
import json
from typing import Dict, Any,Optional
import pandas as pd
import io

# from openai import AzureOpenAI



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
                    "account": "string",
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

@app.get("/grade_count")
def get_grade_count():
    bench = get_candidates_db()
    df_bench = pd.DataFrame(bench)
    grade_count = df_bench['grade'].value_counts().to_dict()
    return {"grade_count": grade_count}
    # return grade_count

@app.get("/trends")
def get_trends():
    rrf_details = get_rrf_details()
    df_rrf = pd.DataFrame(rrf_details)
    # Convert created_on to tz-aware UTC
    df_rrf['created_on'] = pd.to_datetime(
        df_rrf['created_on'],
        errors='coerce',
        utc=True
    )
    # Use tz-aware "now" in UTC
    now_utc = pd.Timestamp.now(tz='UTC')
    # Calculate ageing in days
    df_rrf['ageing'] = (now_utc - df_rrf['created_on']).dt.days
    df_rrf_dict = df_rrf.to_dict(orient='records')
    return {"trends": df_rrf_dict}


@app.get("/get_allocated_candidates")
def get_allocated_candidates():
    allocated_candidates = get_allocated_candidates_db()
    return {"allocated_candidates": allocated_candidates}


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



@app.post("/upload-files")
async def upload_excel_files(
    bench_file: Optional[UploadFile] = File(None),
    rrf_file: Optional[UploadFile] = File(None)
):
    """
    Upload and process bench and/or RRF Excel files for AI-powered matching.
    """
    try:
        df_bench = None
        df_rrf = None
        response_files = {}

        # ---------- Bench File ----------
        if bench_file and bench_file.filename:  # Check both file exists and has filename
            if not bench_file.filename.endswith(('.xlsx', '.xls')):
                raise HTTPException(
                    status_code=400,
                    detail="Bench file must be an Excel file (.xlsx or .xls)"
                )

            bench_content = await bench_file.read()  # Use await here
            df_bench = pd.read_excel(io.BytesIO(bench_content))

            df_bench.columns = (
                df_bench.columns
                    .str.strip()
                    .str.lower()
                    .str.replace(r'[^a-z0-9]+', '_', regex=True)
            )
            bench_flag = clear_bench_table()
            if bench_flag:
                response = insert_into_bench_table(df_bench)
            response_files["bench_file"] = {
                "filename": bench_file.filename,
                "columns": df_bench.columns.tolist(),
                "insert_response": response
            }

        # ---------- RRF File ----------
        if rrf_file and rrf_file.filename:  # Check both file exists and has filename
            if not rrf_file.filename.endswith(('.xlsx', '.xls')):
                raise HTTPException(
                    status_code=400,
                    detail="RRF file must be an Excel file (.xlsx or .xls)"
                )

            rrf_content = await rrf_file.read()  # Use await here
            df_rrf = pd.read_excel(io.BytesIO(rrf_content))

            df_rrf.columns = (
                df_rrf.columns
                    .str.strip()
                    .str.lower()
                    .str.replace(r'[^a-z0-9]+', '_', regex=True)
            )
            rrf_flag = clear_rrf_table()
            if rrf_flag:
                response = insert_into_rrf_table(df_rrf)
            response_files["rrf_file"] = {
                "filename": rrf_file.filename,
                "insert_response": response
            }

        # ---------- No files uploaded ----------
        if not (bench_file and bench_file.filename) and not (rrf_file and rrf_file.filename):
            raise HTTPException(
                status_code=400,
                detail="At least one file (bench or rrf) must be uploaded"
            )

        return {
            "success": True,
            "message": "File(s) processed successfully",
            "file_info": response_files
        }

    except HTTPException:
        raise
    except pd.errors.EmptyDataError:
        raise HTTPException(
            status_code=400,
            detail="One or more uploaded files are empty or corrupted"
        )
    except Exception as e:
        print(f"Error processing uploaded files: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Error processing files: {str(e)}"
        )


def find_matching_candidates(rrf_details):
    try:
        # Fetch data
        bench = get_candidates_db()
       

        # Create DataFrames
        df1 = pd.DataFrame(bench)
        df2 = pd.DataFrame(rrf_details, index=[0])  # Convert single RRF details to DataFrame

        # Minimal columns for Gemini
        df1_update = df1[['vamid', 'grade', 'designation', 'current_skill', 'primary_skill']]
        df2_update = df2[['rrf_id', 'pos_title', 'role', 'account']]

        # Call Gemini
        gemini_response = call_gemini_api(df1_update, df2_update)

        # Find the specific RRF match
        for match in gemini_response.get("gemini_analysis", {}).get("matches", []):
            if match.get("rrf_id") == rrf_details.get("rrf_id"):
                return {
                    "ai_matching": match
                }

    except Exception as e:
        print(f"Error in finding matching candidates: {e}")
        return {
            "error": "An error occurred while processing the request"
        }


@app.get("/matching")
def get_matching_candidates():
    try:
        # Fetch data
        bench = get_candidates_db()
        rrf = get_rrf_details()

        # Create DataFrames
        df1 = pd.DataFrame(bench)
        df2 = pd.DataFrame(rrf)

        # Minimal columns for Gemini
        df1_update = df1[['vamid', 'grade', 'designation', 'current_skill', 'primary_skill']]
        df2_update = df2[['rrf_id', 'pos_title', 'role', 'account']]

        # Call Gemini
        gemini_response = call_gemini_api(df1_update, df2_update)

        # Build employee lookup (vamid → full employee details)
        employee_lookup = (
            df1
            .set_index("vamid")
            .to_dict(orient="index")
        )

        # Build RRF lookup (rrf_id → full RRF details)
        rrf_lookup = (
            df2_update
            .set_index("rrf_id")
            .to_dict(orient="index")
        )

        # Enrich Gemini response
        for match in gemini_response.get("gemini_analysis", {}).get("matches", []):
            rrf_id = match.get("rrf_id")

            # Attach RRF details below rrf_id
            match["rrf_details"] = rrf_lookup.get(rrf_id)

            # Attach employee details for each candidate
            for candidate in match.get("recommended_candidates", []):
                vamid = candidate.get("vamid")
                candidate["employee_details"] = employee_lookup.get(vamid)

        return {
            "ai_matching": gemini_response
        }

    except Exception as e:
        print(f"Error in matching: {e}")
        return {
            "error": "An error occurred while processing the request"
        }

@app.get("/match_candidate/{rrf_id}")
def get_candidate_for_rrf(rrf_id: str):
    try:
        rrf_details = get_rrf_by_id(rrf_id)
        if not rrf_details:
            return {
                "message": f"No matching candidates found for RRF ID: {rrf_id}"
            }
        # If RRF details are found, proceed to find matching candidates
        matching_candidates = find_matching_candidates(rrf_details)
        return {
            "ai_matching": matching_candidates
        }

    except Exception as e:
        print(f"Error in matching for RRF ID {rrf_id}: {e}")
        return {
            "error": "An error occurred while processing the request"
        }


# Run the application
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
