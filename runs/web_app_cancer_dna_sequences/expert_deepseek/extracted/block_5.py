import httpx
from fastapi import Request, HTTPException

class OPAMiddleware:
    def __init__(self, opa_url: str):
        self.opa_url = opa_url

    async def authz_middleware(self, request: Request, call_next):
        if "/api" not in request.url.path:
            return await call_next(request)
        
        user = getattr(request.state, "user", None)
        if not user:
            raise HTTPException(status_code=403, detail="Unauthenticated")

        payload = {
            "input": {
                "method": request.method,
                "path": request.url.path,
                "user": {
                    "id": user.get("sub"),
                    "tenant": user.get("tenant"),
                    "roles": user.get("roles", [])
                }
            }
        }
        async with httpx.AsyncClient() as client:
            resp = await client.post(self.opa_url, json=payload)
            result = resp.json()
            if not result.get("result", False):
                raise HTTPException(status_code=403, detail="Access denied by policy")
        
        response = await call_next(request)
        return response
