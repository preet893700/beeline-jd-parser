# app/api/v1/jd_excel.py
"""
Excel JD Extraction Endpoints
"""

from fastapi import APIRouter, UploadFile, File, Form, HTTPException
from fastapi.responses import StreamingResponse
import logging
from io import BytesIO

from app.services.jd.extractor import JDExtractor
from app.services.excel.reader import ExcelReader
from app.core.exceptions import ExcelReadError, AIExtractionError
from app.repositories.jd_repository import JDRepository

router = APIRouter()
logger = logging.getLogger(__name__)

# In-memory storage for Excel files (use Redis in production)
excel_files_cache = {}


@router.post("/upload")
async def upload_excel(file: UploadFile = File(...)):
    """
    Upload Excel file and get preview
    Returns sheet names, headers, and first 50 rows
    """
    try:
        # Validate file
        if not file.filename.endswith(('.xlsx', '.xls')):
            raise HTTPException(
                status_code=400,
                detail="Invalid file type. Only .xlsx and .xls files are allowed"
            )
        
        # Read file
        content = await file.read()
        
        # Parse Excel
        reader = ExcelReader()
        preview_data = await reader.read_file(content)
        
        # Cache file for later extraction
        file_id = file.filename
        excel_files_cache[file_id] = content
        
        return {
            "fileName": file.filename,
            **preview_data
        }
        
    except ExcelReadError as e:
        logger.error(f"Excel read error: {e}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Upload error: {e}")
        raise HTTPException(status_code=500, detail="Failed to process Excel file")


@router.post("/extract")
async def extract_from_excel(
    file: UploadFile = File(...),
    sheet_id: str = Form(...),
    sheet_name: str = Form(...),
    jd_column_index: int = Form(...)
):
    """
    Extract JD data from Excel file
    Processes all JDs in the specified column from the specified sheet
    
    CRITICAL VALIDATIONS:
    - sheet_id must exist in the file
    - sheet_name must match sheet_id
    - Only processes ONE sheet per request
    - Rejects cross-sheet requests
    """
    try:
        # CRITICAL: Validate sheet_id format
        if not sheet_id.startswith('sheet_'):
            raise HTTPException(
                status_code=400,
                detail="Invalid sheet_id format. Must start with 'sheet_'"
            )
        
        # Read file
        content = await file.read()
        
        # CRITICAL: Verify sheet exists in file
        reader = ExcelReader()
        preview_data = await reader.read_file(content)
        
        sheet_ids = [s["id"] for s in preview_data["sheets"]]
        if sheet_id not in sheet_ids:
            raise HTTPException(
                status_code=400,
                detail=f"Sheet ID '{sheet_id}' not found in file. Available sheets: {sheet_ids}"
            )
        
        # CRITICAL: Verify sheet_name matches sheet_id
        matching_sheet = next((s for s in preview_data["sheets"] if s["id"] == sheet_id), None)
        if not matching_sheet or matching_sheet["name"] != sheet_name:
            raise HTTPException(
                status_code=400,
                detail=f"Sheet name mismatch. Expected '{matching_sheet['name']}' for ID '{sheet_id}', got '{sheet_name}'"
            )
        
        # CRITICAL: Validate column index is within bounds
        if jd_column_index < 0 or jd_column_index >= len(matching_sheet.get("headers", [])):
            raise HTTPException(
                status_code=400,
                detail=f"Column index {jd_column_index} out of bounds. Sheet has {len(matching_sheet.get('headers', []))} columns"
            )
        
        # Extract JDs - ONLY from the specified sheet
        extractor = JDExtractor()
        response, excel_bytes = await extractor.extract_from_excel(
            file_content=content,
            file_name=file.filename,
            sheet_id=sheet_id,
            sheet_name=sheet_name,
            jd_column_index=jd_column_index
        )
        
        # Cache result file
        excel_files_cache[f"result_{response.request_id}"] = excel_bytes
        
        logger.info(
            f"Extraction complete: request_id={response.request_id}, "
            f"sheet_id={sheet_id}, sheet_name={sheet_name}, "
            f"column_index={jd_column_index}, processed={response.total_processed}"
        )
        
        return response
        
    except ExcelReadError as e:
        logger.error(f"Excel processing error: {e}")
        raise HTTPException(status_code=400, detail=str(e))
    except AIExtractionError as e:
        logger.error(f"AI extraction error: {e}")
        raise HTTPException(status_code=503, detail=f"AI extraction failed: {str(e)}")
    except HTTPException:
        raise  # Re-raise HTTP exceptions
    except Exception as e:
        logger.error(f"Extraction error: {e}")
        raise HTTPException(status_code=500, detail="Failed to extract JD data")


@router.get("/download/{request_id}")
async def download_excel(request_id: str):
    """Download extraction results as Excel file"""
    try:
        file_key = f"result_{request_id}"
        
        if file_key not in excel_files_cache:
            raise HTTPException(status_code=404, detail="Result file not found")
        
        excel_bytes = excel_files_cache[file_key]
        
        return StreamingResponse(
            BytesIO(excel_bytes),
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={
                "Content-Disposition": f"attachment; filename=jd_extraction_{request_id}.xlsx"
            }
        )
        
    except Exception as e:
        logger.error(f"Download error: {e}")
        raise HTTPException(status_code=500, detail="Failed to download file")