// Provider-neutral contract only; no fetch, telemetry, auth, generation on receipt, or TTS.
export function makeTextRequest(intent,context,mode){
 if(mode==='reply'){const structured=typeof context==='object'&&context!==null;const latest=structured?context.latest_interlocutor_utterance?.text:context;if(typeof latest!=='string'||!latest.trim())throw Error('Нужны слова собеседника.');if(latest.length>2400)throw Error('Последняя реплика слишком длинна; она не обрезается.');return {version:1,mode,intent_ru:intent.trim().slice(0,3000),selected_context:latest,max_options:3,...(structured?{conversation:context}:{})};}
 if(!intent.trim())throw Error('Сначала напишите свою мысль.');
 if(!['translate','suggest'].includes(mode))throw Error('Неизвестный режим.');
 return {version:1,mode,intent_ru:intent.trim().slice(0,3000),selected_context:context.slice(0,6000),max_options:mode==='suggest'?3:1,
 rules:['Preserve only the user intent; do not invent personal facts.','Use short natural spoken English.','Provide Russian meaning for each English option.','Return options for manual review only; do not send or speak.']};
}
export function validateTextResult(value){
 if(!value||!Array.isArray(value.options)||value.options.length<1||value.options.length>3)throw Error('Неверный ответ текстового адаптера.');
 return value.options.map(o=>{if(typeof o.en!=='string'||typeof o.ru!=='string'||!o.en.trim()||!o.ru.trim()||o.en.length>2000||o.ru.length>2000)throw Error('Неверный вариант.');if(o.kind!==undefined&&!['positive','negative','clarify','uncertain'].includes(o.kind))throw Error('Неизвестная позиция варианта.');return {en:o.en,ru:o.ru,...(o.kind?{kind:o.kind}:{})};});
}
export const demoOptions=validateTextResult({options:[{en:'Could you say that again a little more slowly?',ru:'Повторите, пожалуйста, немного медленнее.'},{en:'Could you explain what you mean by that?',ru:'Объясните, пожалуйста, что вы имеете в виду.'},{en:'Let me check that I understood you correctly.',ru:'Дайте мне проверить, правильно ли я вас понял.'}]});

export function choiceLabel(kind){return ({positive:'Да / подходит',negative:'Нет / не подходит',clarify:'Уточнить',uncertain:'Не знаю / проверить'})[kind]||'Вариант для выбора';}
