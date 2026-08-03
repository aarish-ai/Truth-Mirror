import os
import logging
import itertools
import threading
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

_gemini_keys = []
_gemini_key_cycle = None
_lock = threading.RLock()
_current_key = None

def init_keys(force_reload=False):
    global _gemini_keys, _gemini_key_cycle, _current_key
    with _lock:
        if not _gemini_keys or force_reload:
            if force_reload:
                load_dotenv(override=True)
            keys_str = os.getenv("GEMINI_API_KEYS")
            if not keys_str:
                keys_str = os.getenv("GEMINI_API_KEY", "")
                
            parsed = [k.strip() for k in keys_str.split(",") if k.strip()]
            
            seen = set()
            _gemini_keys = []
            for k in parsed:
                if k not in seen:
                    seen.add(k)
                    _gemini_keys.append(k)
                    
            if _gemini_keys:
                _gemini_key_cycle = itertools.cycle(_gemini_keys)
                _current_key = next(_gemini_key_cycle)

def rotate_gemini_key():
    global _gemini_keys, _gemini_key_cycle, _current_key
    with _lock:
        init_keys() 
        if _gemini_key_cycle and len(_gemini_keys) > 1:
            _current_key = next(_gemini_key_cycle)
            logger.info(f"[KeyRotator] Switched to new Gemini API Key: {_current_key[:10]}...")
            return True
        return False
        
def get_current_key():
    init_keys()
    if not _current_key:
        init_keys(force_reload=True)
    return _current_key
