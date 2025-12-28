import os
from typing import Optional
import uvicorn
from fastapi import FastAPI, File, Form, HTTPException, Depends, Body, UploadFile
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi.staticfiles import StaticFiles
from loguru import logger
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

from models.api import (
    DeleteRequest,
    DeleteResponse,
    QueryRequest,
    QueryResponse,
    UpsertRequest,
    UpsertResponse,
)
from datastore.factory import get_datastore
from services.file import get_document_from_file

from models.models import DocumentMetadata, Source

bearer_scheme = HTTPBearer()
BEARER_TOKEN = os.environ.get("BEARER_TOKEN")
assert BEARER_TOKEN is not None


def validate_token(credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme)):
    if credentials.scheme != "Bearer" or credentials.credentials != BEARER_TOKEN:
        raise HTTPException(status_code=401, detail="Invalid or missing token")
    return credentials


app = FastAPI(dependencies=[Depends(validate_token)])
app.mount("/.well-known", StaticFiles(directory=".well-known"), name="static")

# Create a sub-application, in order to access just the query endpoint in an OpenAPI schema, found at http://0.0.0.0:8000/sub/openapi.json when the app is running locally
sub_app = FastAPI(
    title="Retrieval Plugin API",
    description="A retrieval API for querying and filtering documents based on natural language queries and metadata",
    version="1.0.0",
    servers=[{"url": "https://your-app-url.com"}],
    dependencies=[Depends(validate_token)],
)
app.mount("/sub", sub_app)


@app.post(
    "/upsert-file",
    response_model=UpsertResponse,
)
async def upsert_file(
    file: UploadFile = File(...),
    metadata: Optional[str] = Form(None),
):
    try:
        metadata_obj = (
            DocumentMetadata.parse_raw(metadata)
            if metadata
            else DocumentMetadata(source=Source.file)
        )
    except:
        metadata_obj = DocumentMetadata(source=Source.file)

    document = await get_document_from_file(file, metadata_obj)

    try:
        ids = await datastore.upsert([document])
        return UpsertResponse(ids=ids)
    except Exception as e:
        logger.error(e)
        raise HTTPException(status_code=500, detail=f"str({e})")


@app.post(
    "/upsert",
    response_model=UpsertResponse,
)
async def upsert(
    request: UpsertRequest = Body(...),
):
    try:
        ids = await datastore.upsert(request.documents)
        return UpsertResponse(ids=ids)
    except Exception as e:
        logger.error(f"Error in upsert endpoint: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Upsert failed: {str(e)}")


@app.post(
    "/query",
    response_model=QueryResponse,
)
async def query_main(
    request: QueryRequest = Body(...),
):
    try:
        results = await datastore.query(
            request.queries,
        )
        return QueryResponse(results=results)
    except Exception as e:
        logger.error(f"Error in query_main endpoint: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Query failed: {str(e)}")


@sub_app.post(
    "/query",
    response_model=QueryResponse,
    # NOTE: We are describing the shape of the API endpoint input due to a current limitation in parsing arrays of objects from OpenAPI schemas. This will not be necessary in the future.
    description="Accepts search query objects array each with query and optional filter. Break down complex questions into sub-questions. Refine results by criteria, e.g. time / source, don't do this often. Split queries if ResponseTooLargeError occurs.",
)
async def query(
    request: QueryRequest = Body(...),
):
    try:
        results = await datastore.query(
            request.queries,
        )
        return QueryResponse(results=results)
    except Exception as e:
        logger.error(f"Error in sub_app query endpoint: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Query failed: {str(e)}")


@app.delete(
    "/delete",
    response_model=DeleteResponse,
)
async def delete(
    request: DeleteRequest = Body(...),
):
    if not (request.ids or request.filter or request.delete_all):
        raise HTTPException(
            status_code=400,
            detail="One of ids, filter, or delete_all is required",
        )
    try:
        success = await datastore.delete(
            ids=request.ids,
            filter=request.filter,
            delete_all=request.delete_all,
        )
        return DeleteResponse(success=success)
    except Exception as e:
        logger.error(f"Error in delete endpoint: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Delete failed: {str(e)}")


@app.get("/health")
async def health_check():
    """Health check endpoint to verify datastore connectivity."""
    try:
        # Check if datastore is initialized
        if 'datastore' not in globals() or datastore is None:
            logger.warning("Health check failed: datastore not initialized")
            raise HTTPException(
                status_code=503,
                detail="Datastore not initialized"
            )

        # For Milvus/Zilliz, verify the connection is alive
        if hasattr(datastore, 'col') and hasattr(datastore.col, 'num_entities'):
            try:
                # Quick check that collection is accessible
                _ = datastore.col.num_entities
                logger.info("Health check passed: datastore is healthy")
                return {
                    "status": "healthy",
                    "datastore": "connected",
                    "message": "Service is operational"
                }
            except Exception as e:
                logger.error(f"Health check failed: collection not accessible - {str(e)}")
                raise HTTPException(
                    status_code=503,
                    detail=f"Datastore connection issue: {str(e)}"
                )

        # Generic health check for other datastores
        logger.info("Health check passed: datastore initialized")
        return {
            "status": "healthy",
            "datastore": "initialized",
            "message": "Service is operational"
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Health check failed with unexpected error: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=503,
            detail=f"Health check failed: {str(e)}"
        )


@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=2, max=10),
    retry=retry_if_exception_type(Exception),
    reraise=True
)
async def initialize_datastore():
    """Initialize datastore with retry logic."""
    logger.info("Attempting to connect to datastore...")
    ds = await get_datastore()
    logger.info("Successfully connected to datastore")
    return ds

@app.on_event("startup")
async def startup():
    global datastore
    try:
        datastore = await initialize_datastore()
    except Exception as e:
        logger.error(f"Failed to initialize datastore after retries: {str(e)}", exc_info=True)
        raise


def start():
    uvicorn.run("server.main:app", host="0.0.0.0", port=8000, reload=True)
