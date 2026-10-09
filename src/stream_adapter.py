"""Dedicated translations stream. Planned expiry renewal only, no lost-audio replay.
Numerical provider duration comes from session.created/updated.expires_at, not a guess.
One global PCM budget; silence preserved. Unexpected connection loss fails closed.
"""
import asyncio,json,time,ssl,math
from protocol import URL,configure,append,safe_event
from diagnostics import api_error
from websockets.asyncio.client import connect
class StreamPolicyError(ValueError):pass
async def translate_pcm(source,key,emit,consent,connection=connect,clock=time.monotonic,epoch=time.time):
 if not consent or not consent.cloud_allowed or not source.consent or not source.consent.cloud_allowed:raise StreamPolicyError('Cloud transmission not approved for this source.')
 if not 0<consent.maximum_seconds<=min(21600 if consent.unlimited else 10/.034*60,source.consent.maximum_seconds):raise StreamPolicyError('Duration approval mismatch.')
 if source.consent.source!=consent.source:raise StreamPolicyError('Approved source mismatch.')
 import certifi
 context=ssl.create_default_context(cafile=certifi.where());credential=key;current=None;standby=None;number=0;started=clock()
 async def prepare():
  manager=connection(URL,additional_headers={'Authorization':'Bearer '+credential},ssl=context,proxy=None,open_timeout=12,close_timeout=3,max_queue=16,max_size=2**22)
  entered=False
  try:
   ws=await manager.__aenter__();entered=True
   created=json.loads(await asyncio.wait_for(ws.recv(),10))
   if created.get('type')=='error':source.finish('api_error');emit(api_error(created,'session_created'));raise StreamPolicyError('Provider refused session.')
   if created.get('type')!='session.created':raise StreamPolicyError('Unexpected session event.')
   await asyncio.wait_for(ws.send(json.dumps(configure())),5)
   updated=json.loads(await asyncio.wait_for(ws.recv(),10))
   if updated.get('type')=='error':source.finish('api_error');emit(api_error(updated,'configure'));raise StreamPolicyError('Provider refused configuration.')
   if updated.get('type')!='session.updated':raise StreamPolicyError('Unexpected session event.')
   expiry=updated.get('session',{}).get('expires_at',created.get('session',{}).get('expires_at'))
   if expiry is not None and (isinstance(expiry,bool) or not isinstance(expiry,(int,float)) or not math.isfinite(expiry) or expiry-epoch()<45):raise StreamPolicyError('Invalid or too-near provider expiry.')
   return manager,ws,expiry
  except BaseException:
   if entered:await manager.__aexit__(None,None,None)
   raise
 async def dispose(prepared):
  if prepared:await prepared[0].__aexit__(None,None,None)
 try:
  async with asyncio.timeout(consent.maximum_seconds+40):
   current=await prepare()
   while not source.stop.is_set():
    number+=1;manager,ws,expiry=current;planned=False;confirmed=False;seen=set()
    emit({'kind':'ready' if number==1 else 'boundary','text':'Перевод подключён.' if number==1 else 'Соединение API обновлено; история и контекст сохранены.','connection_number':number})
    async def receive():
     nonlocal confirmed
     async for raw in ws:
      raw_event=json.loads(raw);identifier=raw_event.get('event_id')
      if identifier and identifier in seen:continue
      if identifier:seen.add(identifier)
      event=safe_event(raw_event)
      if event:
       emit({**event,'channel':'remote_zoom','speaker_evidence':'mixed_audio','connection_number':number})
       if event['kind'] in ('closed','error'):
        confirmed=event['kind']=='closed'
        if event['kind']=='error':source.finish('api_error')
        elif not planned:source.finish('provider_closed')
        return
    async def send():
     nonlocal planned,standby
     while not source.stop.is_set():
      if clock()-started>=consent.maximum_seconds:source.finish('spend_limit' if consent.budget_limited else 'duration_limit');break
      if not source.running and clock()-started>20:source.finish('native_start_timeout');emit({'kind':'error','text':'Звук Zoom не поступил. Проверьте Zoom и системный доступ.'});break
      if (consent.budget_limited or consent.unlimited) and expiry is not None:
       if epoch()>=expiry-40 and standby is None:standby=asyncio.create_task(prepare())
       if epoch()>=expiry-10:
        if standby and standby.done() and not standby.cancelled():
         if standby.exception():
          source.finish('renewal_failed');emit({'kind':'error','text':'Обновление API не удалось. Сессия остановлена, автоматического повтора нет.'});break
         planned=True;break
        source.finish('renewal_not_ready');emit({'kind':'error','text':'Не удалось вовремя обновить соединение API. Сессия остановлена; звук повторно не отправляется.'});break
      frame=await asyncio.to_thread(source.next_frame)
      if frame and not source.stop.is_set():
       if not source.budget_allows_frame(len(frame)):source.finish('spend_limit');emit({'kind':'notice','text':'Достигнут денежный предел. История сохранена.'});break
       source.mark_cloud_frame(len(frame)) # conservative BEFORE send, never replay an uncertain send
       await asyncio.wait_for(ws.send(json.dumps(append(frame))),5)
     if source.reason=='audio_backlog_stale':emit({'kind':'error','text':'Очередь звука отстала более чем на 2 секунды. Захват остановлен; устаревший звук отброшен и не повторяется. История сохранена. Для продолжения нажмите Старт.'})
     await asyncio.wait_for(ws.send(json.dumps({'type':'session.close'})),5)
    receiver=asyncio.create_task(receive());sender=asyncio.create_task(send())
    try:
     done,_=await asyncio.wait([receiver,sender],return_when=asyncio.FIRST_COMPLETED)
     for task in done:
      if task.exception():raise task.exception()
     if sender in done and receiver not in done:
      try:await asyncio.wait_for(receiver,8)
      except asyncio.TimeoutError:source.finish('tail_unconfirmed');emit({'kind':'notice','text':'Последний текст не подтверждён. Продолжение остановлено.'})
     if receiver in done and sender not in done:emit({'kind':'notice','text':'Соединение прервано. Захват остановлен; автоматического повторения звука нет.'})
    finally:
     for task in (receiver,sender):
      if not task.done():task.cancel()
     await asyncio.gather(receiver,sender,return_exceptions=True)
    await dispose(current);current=None
    if planned and confirmed and not source.stop.is_set():
     current=await standby;standby=None
    else:break
 except StreamPolicyError:
  if source.reason!='api_error':raise
 finally:
  credential=None;key=None;source.finish('connection_ended')
  if standby:
   if not standby.done():standby.cancel()
   try:await dispose(await standby)
   except BaseException:pass
  await dispose(current)
