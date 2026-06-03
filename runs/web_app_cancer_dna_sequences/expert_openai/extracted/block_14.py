import os
import httpx
from fastapi import FastAPI, Request, Depends, HTTPException
from fastapi.responses import Response
from genomics_common.auth import require_principal, Principal
from genomics_common.observability import instrument

SERVICE_MAP = {
    "uploads": os.getenv("UPLOAD_SERVICE_URL", "http://upload-service:8080"),
    "search": os.getenv("SEARCH_SERVICE_URL", "http://search-service:8080"),
}

app = FastAPI(title="Genomics API Gateway")
instrument(app, "api-gateway")


@app.get("/healthz")
def healthz():
    return {"status": "ok"}


@app.api_route("/{service}/{path:path}", methods=["GET", "POST", "PUT", "PATCH", "DELETE"])
async def proxy(
    service: str,
    path: str,
    request: Request,
    principal: Principal = Depends(require_principal),
):
    if service not in SERVICE_MAP:
        raise HTTPException(status_code=404, detail="unknown service")

    upstream = f"{SERVICE_MAP[service]}/{path}"

    headers = dict(request.headers)
    headers["x-principal-sub"] = principal.subject
    headers["x-principal-tenant"] = principal.tenant_id
    headers["x-principal-roles"] = ",".join(principal.roles)

    body = await request.body()

    async with httpx.AsyncClient(timeout=120.0) as client:
        res = await client.request(
            request.method,
            upstream,
            params=request.query_params,
            content=body,
            headers=headers,
        )

    return Response(
        content=res.content,
        status_code=res.status_code,
        headers={
            k: v
            for k, v in res.headers.items()
            if k.lower() not in {"content-encoding", "transfer-encoding", "connection"}
        },
    )
