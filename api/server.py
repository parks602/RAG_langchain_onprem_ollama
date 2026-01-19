"""
FastAPI Server - RAG 중개 서버
"""
import sys
import os
import time
from pathlib import Path
from typing import List

from fastapi import FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import uvicorn

# 프로젝트 루트 경로 추가
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from api.models import (
    QueryRequest, QueryResponse, Source,
    HealthResponse, DocumentListResponse, DocumentInfo,
    ErrorResponse
)
from api.session_manager import SessionManager
from rag_qa import RAGSystem


# FastAPI 앱 초기화
app = FastAPI(
    title="RAG API Server",
    description="On-Premise RAG 중개 서버 (대화 기록 지원)",
    version="1.0.0"
)

# CORS 설정 (필요시)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 프로덕션에서는 특정 도메인만 허용
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 전역 변수
rag_system: RAGSystem = None
session_manager: SessionManager = None


@app.on_event("startup")
async def startup_event():
    """서버 시작 시 RAG 시스템 초기화"""
    global rag_system, session_manager
    
    print("=" * 60)
    print("RAG API Server 시작 중...")
    print("=" * 60)
    
    # 현재 작업 디렉토리 출력
    print(f"현재 디렉토리: {os.getcwd()}")
    print(f"프로젝트 루트: {project_root}")
    
    # 벡터 스토어 경로
    vectorstore_path = project_root / "output" / "vectorstore"
    chunks_metadata_path = project_root / "output" / "chunks.json"
    
    print(f"\n확인 중:")
    print(f"  - 벡터 스토어: {vectorstore_path}")
    print(f"    존재: {vectorstore_path.exists()}")
    print(f"  - 청크 메타데이터: {chunks_metadata_path}")
    print(f"    존재: {chunks_metadata_path.exists()}")
    
    if not vectorstore_path.exists():
        print(f"\nERROR: 벡터 스토어가 없습니다: {vectorstore_path}")
        print("\n해결 방법:")
        print("  1. 현재 디렉토리 확인: pwd (Linux) 또는 cd (Windows)")
        print("  2. output/vectorstore/ 폴더가 있는지 확인")
        print("  3. 없다면: python build_vectorstore.py ./pdf_files ./output")
        print("  4. 있다면: 올바른 디렉토리에서 실행했는지 확인")
        sys.exit(1)
    
    # RAG 시스템 초기화
    try:
        from vector_store import VectorStoreManager
        
        print(f"\n1. VectorStoreManager 생성 중...")
        vectorstore_manager = VectorStoreManager(
            embedding_model="jhgan/ko-sroberta-multitask"
        )
        
        print(f"2. 벡터 스토어 로딩 중: {vectorstore_path}")
        vectorstore_manager.load_vectorstore(str(vectorstore_path))
        print("✓ VectorStoreManager 로딩 완료!")
        
        print(f"3. RAG 시스템 초기화 중...")
        rag_system = RAGSystem(
            vectorstore_manager=vectorstore_manager,
            model_name="phi4-mini:3.8b-fp16",
            temperature=0.1
        )
        print("✓ RAG 시스템 초기화 완료!")
        
        print(f"4. 세션 매니저 초기화 중...")
        session_manager = SessionManager(session_timeout_minutes=60)
        print("✓ 세션 매니저 초기화 완료!")
        
    except Exception as e:
        print(f"\nERROR: RAG 시스템 초기화 실패")
        print(f"에러 타입: {type(e).__name__}")
        print(f"에러 메시지: {e}")
        import traceback
        print("\n상세 트레이스백:")
        traceback.print_exc()
        sys.exit(1)
    
    print("=" * 60)
    print("서버 준비 완료!")
    print(f"API 문서: http://localhost:8000/docs")
    print(f"상태 확인: http://localhost:8000/api/v1/health")
    print("=" * 60)


@app.get("/", tags=["Root"])
async def root():
    """루트 엔드포인트"""
    return {
        "message": "RAG API Server",
        "version": "1.0.0",
        "docs": "/docs"
    }


@app.get("/api/v1/health", response_model=HealthResponse, tags=["Health"])
async def health_check():
    """서버 상태 확인"""
    if rag_system is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="RAG 시스템이 초기화되지 않았습니다."
        )
    
    return HealthResponse(
        status="healthy",
        message="서버 정상 작동 중",
        version="1.0.0"
    )


@app.post("/api/v1/query", response_model=QueryResponse, tags=["Query"])
async def query(request: QueryRequest):
    """질의 응답 (대화 기록 지원)"""
    if rag_system is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="RAG 시스템이 초기화되지 않았습니다."
        )
    
    start_time = time.time()
    
    try:
        # 세션 ID 가져오기 또는 생성
        session_id = session_manager.get_or_create_session(request.session_id)
        
        # 대화 기록 가져오기 (RAG용)
        conversation_history = session_manager.get_history_for_rag(session_id, max_turns=3)
        
        print(f"\n[세션 {session_id[:8]}...] 질문: {request.question}")
        print(f"대화 기록: {len(conversation_history)}턴")
        
        # RAG 시스템 호출 (메서드명: ask)
        result = rag_system.ask(
            question=request.question,
            return_sources=True,  # 출처 문서 반환
            chat_history=conversation_history
        )
        
        # 응답 시간 계산
        response_time = time.time() - start_time
        
        # 세션에 질문/답변 저장
        session_manager.add_message(session_id, "user", request.question)
        session_manager.add_message(session_id, "assistant", result['answer'])
        
        # Source 객체 생성
        sources = []
        source_docs = result.get('sources', [])  # 딕셔너리에서 가져오기
        for doc in source_docs:
            sources.append(Source(
                document=doc.get('document_name', 'Unknown'),
                section_id=doc.get('section_id', ''),
                section_title=doc.get('section_title', ''),
                page_start=doc.get('page_start', 0),
                page_end=doc.get('page_end', 0),
                content=doc.get('content', '')[:200],  # 처음 200자만
                score=0.0  # 필요시 유사도 점수 추가
            ))
        
        print(f"응답 완료: {response_time:.2f}초")
        
        return QueryResponse(
            answer=result['answer'],
            sources=sources,
            session_id=session_id,
            response_time=response_time
        )
        
    except Exception as e:
        print(f"\n{'='*60}")
        print(f"ERROR: 질의 처리 중 오류 발생")
        print(f"{'='*60}")
        print(f"질문: {request.question}")
        print(f"세션 ID: {session_id if 'session_id' in locals() else 'N/A'}")
        print(f"에러 타입: {type(e).__name__}")
        print(f"에러 메시지: {str(e)}")
        
        import traceback
        print(f"\n상세 트레이스백:")
        traceback.print_exc()
        print(f"{'='*60}\n")
        
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"질의 처리 중 오류: {type(e).__name__} - {str(e)}"
        )


@app.delete("/api/v1/sessions/{session_id}", tags=["Session"])
async def clear_session(session_id: str):
    """세션 삭제 (대화 기록 초기화)"""
    if not session_manager.session_exists(session_id):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="세션을 찾을 수 없습니다."
        )
    
    session_manager.clear_session(session_id)
    return {"message": "세션이 삭제되었습니다.", "session_id": session_id}


@app.get("/api/v1/sessions/{session_id}", tags=["Session"])
async def get_session_info(session_id: str):
    """세션 정보 조회"""
    info = session_manager.get_session_info(session_id)
    if info is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="세션을 찾을 수 없습니다."
        )
    return info


@app.get("/api/v1/sessions/{session_id}/history", tags=["Session"])
async def get_session_history(session_id: str, max_turns: int = 10):
    """세션 대화 기록 조회"""
    if not session_manager.session_exists(session_id):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="세션을 찾을 수 없습니다."
        )
    
    history = session_manager.get_history(session_id, max_turns)
    return {
        "session_id": session_id,
        "history": history,
        "total_messages": len(history)
    }


@app.get("/api/v1/documents", response_model=DocumentListResponse, tags=["Documents"])
async def list_documents():
    """문서 목록 조회"""
    if rag_system is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="RAG 시스템이 초기화되지 않았습니다."
        )
    
    try:
        # chunks.json에서 문서 목록 가져오기
        chunks_metadata_path = project_root / "output" / "chunks.json"
        if not chunks_metadata_path.exists():
            return DocumentListResponse(documents=[], total=0)
        
        import json
        with open(chunks_metadata_path, 'r', encoding='utf-8') as f:
            chunks = json.load(f)
        
        # 문서별 청크 수 계산
        doc_chunks = {}
        for chunk in chunks:
            doc_name = chunk.get('document', 'Unknown')
            if doc_name not in doc_chunks:
                doc_chunks[doc_name] = 0
            doc_chunks[doc_name] += 1
        
        # DocumentInfo 생성
        documents = [
            DocumentInfo(
                filename=doc,
                document_name=doc,
                total_chunks=count
            )
            for doc, count in doc_chunks.items()
        ]
        
        return DocumentListResponse(
            documents=documents,
            total=len(documents)
        )
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"문서 목록 조회 중 오류: {str(e)}"
        )


@app.get("/api/v1/stats", tags=["Stats"])
async def get_stats():
    """서버 통계"""
    return {
        "active_sessions": session_manager.get_session_count(),
        "server_uptime": "N/A"  # 필요시 구현
    }


# 에러 핸들러
@app.exception_handler(HTTPException)
async def http_exception_handler(request, exc):
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": exc.__class__.__name__,
            "message": exc.detail
        }
    )


@app.exception_handler(Exception)
async def general_exception_handler(request, exc):
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "error": exc.__class__.__name__,
            "message": str(exc)
        }
    )


def main():
    """서버 실행"""
    uvicorn.run(
        "api.server:app",
        host="0.0.0.0",
        port=8000,
        reload=False,  # 개발 시 True
        log_level="info"
    )


if __name__ == "__main__":
    main()