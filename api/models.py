"""
API Request/Response Models
"""
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any


class Message(BaseModel):
    """대화 메시지"""
    role: str = Field(..., description="user 또는 assistant")
    content: str = Field(..., description="메시지 내용")


class QueryRequest(BaseModel):
    """질의 요청"""
    question: str = Field(..., description="사용자 질문")
    session_id: Optional[str] = Field(None, description="세션 ID (대화 기록 유지)")
    history: Optional[List[Message]] = Field(default=[], description="대화 기록 (선택)")


class Source(BaseModel):
    """참고 문서"""
    document: str = Field(..., description="문서명")
    section_id: str = Field(..., description="섹션 번호")
    section_title: str = Field(..., description="섹션 제목")
    page_start: int = Field(..., description="시작 페이지")
    page_end: int = Field(..., description="끝 페이지")
    content: str = Field(..., description="청크 내용")
    score: float = Field(..., description="유사도 점수")


class QueryResponse(BaseModel):
    """질의 응답"""
    answer: str = Field(..., description="답변")
    sources: List[Source] = Field(..., description="참고 문서 목록")
    session_id: str = Field(..., description="세션 ID")
    response_time: float = Field(..., description="응답 시간 (초)")


class HealthResponse(BaseModel):
    """서버 상태"""
    status: str = Field(..., description="서버 상태")
    message: str = Field(..., description="메시지")
    version: str = Field(..., description="API 버전")


class DocumentInfo(BaseModel):
    """문서 정보"""
    filename: str = Field(..., description="파일명")
    document_name: str = Field(..., description="문서명 (한글)")
    total_chunks: int = Field(..., description="총 청크 수")


class DocumentListResponse(BaseModel):
    """문서 목록 응답"""
    documents: List[DocumentInfo] = Field(..., description="문서 목록")
    total: int = Field(..., description="총 문서 수")


class ErrorResponse(BaseModel):
    """에러 응답"""
    error: str = Field(..., description="에러 타입")
    message: str = Field(..., description="에러 메시지")
    detail: Optional[str] = Field(None, description="상세 정보")