"""Only fixed categories and numeric metadata; never exception strings or headers."""
import json, socket, ssl
from websockets.exceptions import InvalidStatus, ConnectionClosed, InvalidHandshake
STAGES={'tls_setup','connect','session_created','configure','session_updated','stream','drain','complete'}
CODES={
 'invalid_api_key':'auth', 'missing_api_key':'auth', 'authentication_error':'auth',
 'insufficient_quota':'quota', 'rate_limit_exceeded':'rate_limit',
 'model_not_found':'model_access', 'permission_denied':'model_access',
 'invalid_request_error':'protocol', 'invalid_value':'protocol',
 'unknown_parameter':'protocol', 'missing_required_parameter':'protocol',
 'invalid_event':'protocol', 'session_expired':'session_expired',
 'server_error':'provider', 'internal_error':'provider',
}
TEXT={
 'tls_certificate':'Проверка TLS-сертификата не прошла. Проверка сертификата не отключалась.',
 'tls':'TLS-соединение не установлено.', 'dns':'Не удалось разрешить имя api.openai.com.',
 'timeout':'Истёк таймаут указанной стадии; автоматического повтора нет.',
 'network':'Сетевое соединение прервалось.', 'http':'Сервер отклонил WebSocket upgrade.',
 'auth':'API отклонил авторизацию. Ключ не выводится.',
 'quota':'API сообщил об отсутствии доступной квоты.',
 'rate_limit':'API сообщил об ограничении частоты.',
 'model_access':'API сообщил об ошибке доступа к модели или её наличия.',
 'protocol':'API отклонил конфигурацию или событие протокола.',
 'provider':'API сообщил о внутренней ошибке.',
 'api_error':'API прислал ошибку с неклассифицированным кодом; сырое сообщение скрыто.',
 'malformed_json':'API прислал некорректный JSON.',
 'unexpected_event':'Первое событие не является session.created или error.',
 'closed':'WebSocket закрылся до завершения сессии.',
 'handshake':'WebSocket handshake не прошёл.', 'client':'Ошибка клиента; секреты и сырые исключения скрыты.',
 'session_expired':'API сообщил об истечении сессии.',
}
def detail(category, stage, **fields):
 return {'kind':'error','code':category,'stage':stage if stage in STAGES else 'unknown',
         'text':TEXT[category]+' Стадия: '+(stage if stage in STAGES else 'unknown')+'.',**fields}
def api_error(event, stage):
 error=event.get('error')
 error=error if isinstance(error,dict) else {}
 code=error.get('code')
 # No arbitrary provider string is permitted, even if it looks like an identifier.
 category=CODES.get(code,'api_error') if isinstance(code,str) else 'api_error'
 return detail(category,stage,api_code=code if isinstance(code,str) and code in CODES else 'unclassified')
def exception_error(exc,stage):
 if isinstance(exc,ssl.SSLCertVerificationError):
  return detail('tls_certificate',stage,verify_code=exc.verify_code if isinstance(exc.verify_code,int) else None)
 if isinstance(exc,ssl.SSLError):return detail('tls',stage)
 if isinstance(exc,socket.gaierror):return detail('dns',stage)
 if isinstance(exc,TimeoutError):return detail('timeout',stage)
 if isinstance(exc,InvalidStatus):
  status=exc.response.status_code
  return detail('http',stage,http_status=status if isinstance(status,int) and 100<=status<=599 else None)
 if isinstance(exc,ConnectionClosed):
  code=exc.rcvd.code if exc.rcvd else None
  return detail('closed',stage,close_code=code if isinstance(code,int) else None)
 if isinstance(exc,InvalidHandshake):return detail('handshake',stage)
 if isinstance(exc,json.JSONDecodeError):return detail('malformed_json',stage)
 if isinstance(exc,OSError):return detail('network',stage,errno=exc.errno if isinstance(exc.errno,int) else None)
 return detail('client',stage)
