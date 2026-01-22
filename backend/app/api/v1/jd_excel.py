# app/api/v1/jd_excel.py
"""
Excel JD Extraction Endpoints

FINAL VERSION: Async extraction with proper caching
"""

from fastapi import APIRouter, UploadFile, File, Form, HTTPException, BackgroundTasks
from fastapi.responses import StreamingResponse
import logging
from io import BytesIO

from app.services.jd.extractor import JDExtractor, get_cached_excel, get_cached_results
from app.services.excel.reader import ExcelReader
from app.core.exceptions import ExcelReadError

router = APIRouter()
logger = logging.getLogger(__name__)

# In-memory storage for uploaded files
excel_files_cache = {}


@router.post("/upload")
async def upload_excel(file: UploadFile = File(...)):
    """Upload Excel file and get preview"""
    try:
        if not file.filename.endswith(('.xlsx', '.xls')):
            raise HTTPException(
                status_code=400,
                detail="Invalid file type. Only .xlsx and .xls files are allowed"
            )
        
        content = await file.read()
        reader = ExcelReader()
        preview_data = await reader.read_file(content)
        
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
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    sheet_id: str = Form(...),
    sheet_name: str = Form(...),
    jd_column_index: int = Form(...)
):
    """
    Start extraction - returns immediately with request_id
    Frontend polls /api/v1/progress/{request_id} for updates
    """
    try:
        if not sheet_id.startswith('sheet_'):
            raise HTTPException(
                status_code=400,
                detail="Invalid sheet_id format. Must start with 'sheet_'"
            )
        
        content = await file.read()
        reader = ExcelReader()
        preview_data = await reader.read_file(content)
        
        sheet_ids = [s["id"] for s in preview_data["sheets"]]
        if sheet_id not in sheet_ids:
            raise HTTPException(
                status_code=400,
                detail=f"Sheet ID '{sheet_id}' not found in file"
            )
        
        matching_sheet = next((s for s in preview_data["sheets"] if s["id"] == sheet_id), None)
        if not matching_sheet or matching_sheet["name"] != sheet_name:
            raise HTTPException(
                status_code=400,
                detail=f"Sheet name mismatch"
            )
        
        if jd_column_index < 0 or jd_column_index >= len(matching_sheet.get("headers", [])):
            raise HTTPException(
                status_code=400,
                detail=f"Column index {jd_column_index} out of bounds"
            )
        
        # Generate request_id
        import uuid
        request_id = str(uuid.uuid4())
        
        # Start background extraction
        extractor = JDExtractor()
        background_tasks.add_task(
            extractor.extract_from_excel_background,
            request_id=request_id,
            file_content=content,
            file_name=file.filename,
            sheet_id=sheet_id,
            sheet_name=sheet_name,
            jd_column_index=jd_column_index
        )
        
        logger.info(f"Started background extraction: {request_id}")
        
        return {
            "request_id": request_id,
            "status": "processing",
            "message": "Extraction started. Poll /api/v1/progress/{request_id} for updates."
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Extraction error: {e}")
        raise HTTPException(status_code=500, detail="Failed to extract JD data")


@router.get("/status/{request_id}")
async def get_extraction_status(request_id: str):
    """Check if extraction is complete and get results"""
    try:
        results = get_cached_results(request_id)
        
        if results:
            logger.info(f"Status check: {request_id} - COMPLETE with {results['total_processed']} results")
            return {
                "status": "complete",
                "request_id": request_id,
                "results": results["results"],
                "total_processed": results["total_processed"],
                "success_count": results.get("success_count", 0),
                "failure_count": results.get("failure_count", 0)
            }
        else:
            logger.debug(f"Status check: {request_id} - still processing")
            return {
                "status": "processing",
                "request_id": request_id
            }
            
    except Exception as e:
        logger.error(f"Status check error for {request_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to check status")


@router.get("/download/{request_id}")
async def download_excel(request_id: str):
    """Download extraction results as Excel file"""
    try:
        excel_bytes = get_cached_excel(request_id)
        
        if not excel_bytes:
            raise HTTPException(status_code=404, detail="Result file not found")
        
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