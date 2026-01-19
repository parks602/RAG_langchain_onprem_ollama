"""
Session Manager - 대화 기록 관리
"""
import uuid
from typing import Dict, List, Optional
from datetime import datetime, timedelta
from collections import defaultdict
import threading


class SessionManager:
    """세션별 대화 기록 관리"""
    
    def __init__(self, session_timeout_minutes: int = 60):
        self._sessions: Dict[str, List[Dict]] = defaultdict(list)
        self._session_timestamps: Dict[str, datetime] = {}
        self._session_timeout = timedelta(minutes=session_timeout_minutes)
        self._lock = threading.Lock()
    
    def create_session(self) -> str:
        """새 세션 생성"""
        session_id = str(uuid.uuid4())
        with self._lock:
            self._sessions[session_id] = []
            self._session_timestamps[session_id] = datetime.now()
        return session_id
    
    def get_or_create_session(self, session_id: Optional[str] = None) -> str:
        """세션 가져오기 또는 생성"""
        if session_id and self.session_exists(session_id):
            self._update_session_timestamp(session_id)
            return session_id
        return self.create_session()
    
    def session_exists(self, session_id: str) -> bool:
        """세션 존재 확인"""
        with self._lock:
            return session_id in self._sessions
    
    def add_message(self, session_id: str, role: str, content: str):
        """메시지 추가"""
        with self._lock:
            if session_id not in self._sessions:
                self._sessions[session_id] = []
            
            self._sessions[session_id].append({
                'role': role,
                'content': content,
                'timestamp': datetime.now().isoformat()
            })
            self._update_session_timestamp(session_id)
    
    def get_history(self, session_id: str, max_turns: int = 5) -> List[Dict]:
        """대화 기록 가져오기 (최근 N턴)"""
        with self._lock:
            if session_id not in self._sessions:
                return []
            
            # 최근 max_turns*2 메시지 (질문+답변 쌍)
            history = self._sessions[session_id][-(max_turns * 2):]
            return history
    
    def get_history_for_rag(self, session_id: str, max_turns: int = 3) -> List[tuple]:
        """RAG 시스템용 대화 기록 (질문-답변 쌍)"""
        history = self.get_history(session_id, max_turns)
        
        # [(질문, 답변), ...] 형태로 변환
        rag_history = []
        for i in range(0, len(history) - 1, 2):
            if history[i]['role'] == 'user' and history[i+1]['role'] == 'assistant':
                rag_history.append((
                    history[i]['content'],
                    history[i+1]['content']
                ))
        
        return rag_history
    
    def clear_session(self, session_id: str):
        """세션 삭제"""
        with self._lock:
            if session_id in self._sessions:
                del self._sessions[session_id]
            if session_id in self._session_timestamps:
                del self._session_timestamps[session_id]
    
    def _update_session_timestamp(self, session_id: str):
        """세션 타임스탬프 업데이트"""
        self._session_timestamps[session_id] = datetime.now()
    
    def cleanup_expired_sessions(self):
        """만료된 세션 정리"""
        now = datetime.now()
        expired = []
        
        with self._lock:
            for session_id, timestamp in self._session_timestamps.items():
                if now - timestamp > self._session_timeout:
                    expired.append(session_id)
            
            for session_id in expired:
                del self._sessions[session_id]
                del self._session_timestamps[session_id]
        
        return len(expired)
    
    def get_session_count(self) -> int:
        """활성 세션 수"""
        with self._lock:
            return len(self._sessions)
    
    def get_session_info(self, session_id: str) -> Optional[Dict]:
        """세션 정보"""
        with self._lock:
            if session_id not in self._sessions:
                return None
            
            return {
                'session_id': session_id,
                'message_count': len(self._sessions[session_id]),
                'created_at': self._session_timestamps.get(session_id),
                'last_activity': self._session_timestamps.get(session_id)
            }