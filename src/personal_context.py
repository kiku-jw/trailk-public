"""Optional user-entered local context; no discovery, default facts or logging."""
import json,threading
from pathlib import Path
MAX_CHARACTERS=4000
MAX_WORDS=250
class PersonalContextError(ValueError):pass
def validate_text(value):
 if not isinstance(value,str) or len(value)>MAX_CHARACTERS or len(value.split())>MAX_WORDS:raise PersonalContextError('Контекст обо мне: до 250 слов и 4000 символов.')
 try:value.encode('utf-8')
 except UnicodeError:raise PersonalContextError('Некорректный текст контекста.') from None
 return value.strip()
class PersonalContext:
 def __init__(self,path):self.path=Path(path);self.lock=threading.RLock()
 def read(self):
  with self.lock:
   try:
    v=json.loads(self.path.read_text());assert v['version']==1 and type(v['revision']) is int and v['revision']>=0
    return {'version':1,'text':validate_text(v['text']),'revision':v['revision']}
   except (OSError,ValueError,TypeError,KeyError,AttributeError,AssertionError):return {'version':1,'text':'','revision':0}
 def save(self,text):
  text=validate_text(text)
  with self.lock:
   old=self.read();v={'version':1,'text':text,'revision':old['revision']+(text!=old['text'])};self.path.parent.mkdir(parents=True,exist_ok=True)
   p=self.path.with_suffix('.tmp');p.write_text(json.dumps(v,ensure_ascii=False));p.chmod(0o600);p.replace(self.path);return v
