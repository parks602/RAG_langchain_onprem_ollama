"""
Gradio UI Client - API 서버와 통신
"""
import requests
import gradio as gr
from typing import List, Tuple, Optional
import time


# API 서버 URL
API_BASE_URL = "http://localhost:8000"


class RAGClient:
    """RAG API 클라이언트"""
    
    def __init__(self, api_url: str = API_BASE_URL):
        self.api_url = api_url
        self.session_id: Optional[str] = None
    
    def check_health(self) -> bool:
        """서버 상태 확인"""
        try:
            response = requests.get(f"{self.api_url}/api/v1/health", timeout=5)
            return response.status_code == 200
        except:
            return False
    
    def query(self, question: str) -> Tuple[str, List[dict], float]:
        """질문 요청 (대화 기록 자동 유지)"""
        try:
            response = requests.post(
                f"{self.api_url}/api/v1/query",
                json={
                    "question": question,
                    "session_id": self.session_id  # 세션 ID 전달
                },
                timeout=60
            )
            
            if response.status_code == 200:
                data = response.json()
                
                # 세션 ID 저장 (서버에서 반환)
                self.session_id = data.get("session_id")
                
                return (
                    data.get("answer", ""),
                    data.get("sources", []),
                    data.get("response_time", 0.0)
                )
            else:
                error_msg = response.json().get("detail", "알 수 없는 오류")
                return f"오류: {error_msg}", [], 0.0
                
        except requests.exceptions.Timeout:
            return "오류: 서버 응답 시간 초과 (60초)", [], 0.0
        except requests.exceptions.ConnectionError:
            return "오류: API 서버에 연결할 수 없습니다. 서버가 실행 중인지 확인하세요.", [], 0.0
        except Exception as e:
            return f"오류: {str(e)}", [], 0.0
    
    def clear_session(self):
        """대화 기록 초기화"""
        if self.session_id:
            try:
                requests.delete(f"{self.api_url}/api/v1/sessions/{self.session_id}")
            except:
                pass
        self.session_id = None
    
    def get_session_history(self) -> List[dict]:
        """대화 기록 조회"""
        if not self.session_id:
            return []
        
        try:
            response = requests.get(
                f"{self.api_url}/api/v1/sessions/{self.session_id}/history"
            )
            if response.status_code == 200:
                data = response.json()
                return data.get("history", [])
        except:
            pass
        return []


# 클라이언트 초기화
client = RAGClient()


def check_server_status() -> str:
    """서버 상태 체크"""
    if client.check_health():
        return "🟢 서버 연결됨"
    else:
        return "🔴 서버 연결 실패 (http://localhost:8000)"


def ask_question(question: str, history: List) -> Tuple:
    """질문 처리"""
    if not question.strip():
        return history, "", "질문을 입력하세요.", "", check_server_status()
    
    # 서버 상태 확인
    if not client.check_health():
        return (
            history,
            "",
            "오류: API 서버에 연결할 수 없습니다.\n\n서버 실행: python api/server.py",
            "",
            check_server_status()
        )
    
    # 질문 요청
    answer, sources, response_time = client.query(question)
    
    # 대화 기록 업데이트 (딕셔너리 형식 - Gradio 6.x 필수)
    history.append({"role": "user", "content": question})
    history.append({"role": "assistant", "content": answer})
    
    # 참고 문서 포맷팅
    sources_text = format_sources(sources)
    
    # 응답 시간 표시
    time_info = f"응답 시간: {response_time:.2f}초"
    if client.session_id:
        time_info += f" | 세션: {client.session_id[:8]}..."
    
    return (
        history,
        "",  # 질문 입력창 초기화
        sources_text,
        time_info,
        check_server_status()
    )


def format_sources(sources: List[dict]) -> str:
    """참고 문서 포맷팅"""
    if not sources:
        return "참고 문서 없음"
    
    result = []
    for i, source in enumerate(sources, 1):
        doc_info = f"""**[{i}] {source['document']}**
섹션: {source['section_id']} - {source['section_title']}
페이지: {source['page_start']}-{source['page_end']}

{source['content']}...

---
"""
        result.append(doc_info)
    
    return "\n".join(result)


def clear_conversation():
    """대화 초기화"""
    client.clear_session()
    return [], "", "", "대화 기록이 초기화되었습니다.", check_server_status()


def show_history():
    """대화 기록 보기"""
    history = client.get_session_history()
    
    if not history:
        return "대화 기록이 없습니다."
    
    result = []
    for msg in history:
        role = "사용자" if msg['role'] == 'user' else "AI"
        timestamp = msg.get('timestamp', '')
        result.append(f"**[{role}]** ({timestamp})\n{msg['content']}\n")
    
    return "\n---\n".join(result)


# Gradio UI
with gr.Blocks(title="RAG 질의응답 시스템 (API Client)") as demo:
    gr.Markdown("# 📚 RAG 기반 사내규정 검색 시스템 (API Client)")
    gr.Markdown("API 서버와 통신하여 대화 기록을 유지합니다.")
    
    with gr.Row():
        with gr.Column(scale=1):
            server_status = gr.Textbox(
                label="서버 상태",
                value=check_server_status(),
                interactive=False
            )
            refresh_btn = gr.Button("🔄 상태 새로고침", size="sm")
    
    with gr.Row():
        with gr.Column(scale=3):
            # 채팅 인터페이스
            chatbot = gr.Chatbot(
                label="대화",
                height=400,
                show_label=True
            )
            
            with gr.Row():
                question_input = gr.Textbox(
                    label="질문 입력",
                    placeholder="예: 병가 규정은 어디에 있나요?",
                    lines=2,
                    scale=4
                )
                submit_btn = gr.Button("전송", variant="primary", scale=1)
            
            with gr.Row():
                clear_btn = gr.Button("🗑️ 대화 초기화")
                history_btn = gr.Button("📋 대화 기록 보기")
            
            response_info = gr.Textbox(
                label="응답 정보",
                interactive=False,
                lines=1
            )
        
        with gr.Column(scale=2):
            sources_output = gr.Markdown(
                label="참고 문서",
                value="질문을 입력하면 참고 문서가 표시됩니다."
            )
    
    # 대화 기록 모달
    with gr.Accordion("전체 대화 기록", open=False):
        history_output = gr.Markdown()
        show_history_btn = gr.Button("대화 기록 로드")
    
    # 이벤트 핸들러
    submit_btn.click(
        fn=ask_question,
        inputs=[question_input, chatbot],
        outputs=[chatbot, question_input, sources_output, response_info, server_status]
    )
    
    question_input.submit(
        fn=ask_question,
        inputs=[question_input, chatbot],
        outputs=[chatbot, question_input, sources_output, response_info, server_status]
    )
    
    clear_btn.click(
        fn=clear_conversation,
        outputs=[chatbot, question_input, sources_output, response_info, server_status]
    )
    
    refresh_btn.click(
        fn=check_server_status,
        outputs=[server_status]
    )
    
    show_history_btn.click(
        fn=show_history,
        outputs=[history_output]
    )
    
    # 시작 시 서버 상태 확인
    demo.load(
        fn=check_server_status,
        outputs=[server_status]
    )


if __name__ == "__main__":
    print("=" * 60)
    print("RAG UI Client 시작")
    print("=" * 60)
    print(f"API 서버: {API_BASE_URL}")
    print("대화 기록이 세션별로 자동 저장됩니다.")
    print("=" * 60)
    
    demo.launch(
        server_name="0.0.0.0",
        server_port=7860,
        share=False
    )