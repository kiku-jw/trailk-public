import test from 'node:test';import assert from 'node:assert/strict';
import {sentencePrefix} from '../assets/web/segments.js';
import {Transcript} from '../assets/web/state.js';
import {ConversationLedger,ReplyScheduler} from '../assets/web/t9.js';
test('recorded provider question with closing guillemet commits without waiting for silence',()=>{
 const l=new ConversationLedger(),t=new Transcript();const chunks=['В','сё',':',' «','Ты',' меня',' слыш','ишь','?»'];let seq=0;
 for(const text of chunks){l.observe(text,++seq*100);t.add({kind:'delta',seq,text});}
 assert.equal(l.revision,1);assert.equal(l.items[0].text,'Всё: «Ты меня слышишь?»');assert.equal(l.stabilization,600);assert.equal(t.history.join(''),'Всё: «Ты меня слышишь?»');assert.equal(t.draft,'');
});
test('closing quotes and brackets are retained and following letters do not imply a boundary',()=>{
 for(const s of ['«Где?»','“Как?”','(Почему?)','[Почему?]','"Как?"'])assert.equal(sentencePrefix(s),s);
 assert.equal(sentencePrefix('«Да?» Затем нет.'),'«Да?» ');assert.equal(sentencePrefix('«Да?»продолжение'),null);
 assert.equal(sentencePrefix('Цена 3.'),null);assert.equal(sentencePrefix('Цена 3.5 доллара. '),'Цена 3.5 доллара. ');
});
test('fragmented quote and decimal delivery preserves every character and immutable history',()=>{
 const t=new Transcript();let seq=0;const chunks=['«Цена 3.','5 доллара.','» ','«Где','?» ','Новая мысль'];
 for(const text of chunks)t.add({kind:'delta',seq:++seq,text});const first=t.history[0];assert.equal(t.history.join('')+t.draft,chunks.join(''));t.add({kind:'delta',seq:++seq,text:' продолжается.'});assert.equal(t.history[0],first);
});
test('earlier quoted question is discarded when corrected during its request; Stop still discards',async()=>{
 let now=0,resolve;const results=[],l=new ConversationLedger(),s=new ReplyScheduler({clock:()=>now,generate:()=>new Promise(r=>resolve=r),onResult:r=>results.push(r)});s.configure(true);l.observe('«Онлайн подходит?»',0);s.update(JSON.stringify(l.replyContext()),l.revision,true,l.readyAt);now=750;const old=s.tick();now=1000;l.observe(' Нет, встречаемся лично.',now);s.update(JSON.stringify(l.replyContext()),l.revision,true,l.readyAt);now=2750;resolve({options:[{en:'Online works for me.',ru:'Онлайн подходит.',kind:'positive'}]});await old;assert.equal(results.length,0);
 const pending=s.tick();s.cancel();resolve({options:[{en:'In person works for me.',ru:'Лично подходит.',kind:'positive'}]});await pending;assert.equal(results.length,0);assert.deepEqual(l.replyContext().own_response_state,{spoken:'unknown',selected_draft_is_speech:false});
});
