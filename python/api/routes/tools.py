from fastapi import APIRouter

from schemas.tools import ToolInvokeRequest, ToolInvokeResponse
from tools.registry import tool_registry

router = APIRouter(prefix="/tools", tags=["tools"])


@router.post("/invoke", response_model=ToolInvokeResponse)
async def invoke_tool(request: ToolInvokeRequest) -> ToolInvokeResponse:
    result = await tool_registry.invoke(request.tool_name, request.params)
    return ToolInvokeResponse(result=result)
