"""Clean implementation of the official translation protocol. No Sokuji code copied."""
import base64
URL='wss://api.openai.com/v1/realtime/translations?model=gpt-realtime-translate'
RATE=24000
LIMIT_SECONDS=180
CHUNK_BYTES=9600 #200ms mono PCM16 per official API reference

def configure():
    return {'type':'session.update','session':{'audio':{'input':{'transcription':None,'noise_reduction':None},'output':{'language':'ru'}}}}

def append(pcm):
    return {'type':'session.input_audio_buffer.append','audio':base64.b64encode(pcm).decode()}

def safe_event(event):
    typ=event.get('type')
    if typ=='session.output_transcript.delta':
        return {'kind':'delta','text':event.get('delta',''),'elapsed_ms':event.get('elapsed_ms')}
    if typ=='error':
        from diagnostics import api_error
        return api_error(event,'stream')
    if typ=='session.closed':return {'kind':'closed'}
    return None # audio never forwarded/stored/played
