"""Application-only Keychain IPC; no argv secrets or diagnostic body reflection."""
import json,subprocess
from pathlib import Path
import os
BRIDGE=Path(os.environ['CALM_KEYCHAIN_BRIDGE'])
class StoreError(Exception):pass
class KeychainStore:
 def _call(self,action,data=None):
  try:return subprocess.run([str(BRIDGE),action],input=data,stdout=subprocess.PIPE,stderr=subprocess.DEVNULL,timeout=45,check=False)
  except Exception:raise StoreError('Не удалось завершить действие Keychain. Подтвердите доступ самостоятельно.') from None
 def status(self):
  result=self._call('status')
  try:value=json.loads(result.stdout)
  except Exception:raise StoreError('Статус Keychain недоступен.') from None
  return bool(value.get('ok') and value.get('stored'))
 def save_user_submission(self,key):
  # Only invoked on user's explicit Save button. Never passed an old RAM key.
  result=self._call('save',key.encode())
  try:value=json.loads(result.stdout)
  except Exception:raise StoreError('Keychain не подтвердил сохранение.') from None
  if not value.get('ok'):raise StoreError('Keychain не подтвердил сохранение. Проверьте системный диалог доступа.')
 def load_for_application(self):
  # Never call from agent tools or print this return value. Application consumes privately.
  result=self._call('load-for-client')
  if result.returncode!=0:raise StoreError('Keychain не разрешил приложению доступ. Подтвердите системный диалог самостоятельно.')
  try:key=result.stdout.decode()
  except Exception:raise StoreError('Keychain вернул недоступный формат.') from None
  if not 20<=len(key)<=512 or any(c.isspace() for c in key):raise StoreError('Проверьте сохранённый ключ самостоятельно.')
  return key
 def delete_by_user(self):
  result=self._call('delete-by-user')
  try:value=json.loads(result.stdout)
  except Exception:raise StoreError('Удаление Keychain не подтверждено.') from None
  if not value.get('ok'):raise StoreError('Удаление Keychain не подтверждено.')
