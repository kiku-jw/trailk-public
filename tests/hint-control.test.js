import test from 'node:test';
import assert from 'node:assert/strict';
import {ReplyScheduler,ConversationLedger} from '../assets/web/t9.js';
import {LatencyWindow} from '../assets/web/latency.js';
import {KaraokeReader} from '../assets/web/karaoke-model.js';

test('new context and Stop abort transport; a late success never replaces selected text',async()=>{
 let now=0,resolve;const signals=[],generations=[],results=[];
 const scheduler=new ReplyScheduler({clock:()=>now,generate:(context,{signal,requestGeneration})=>{signals.push(signal);generations.push(requestGeneration);return new Promise(r=>resolve=r)},onResult:r=>results.push(r)});
 scheduler.configure(true);scheduler.update('Встреча в четверг?',1,true,0);now=750;let pending=scheduler.tick();
 scheduler.update('Нет, не в четверг, а в пятницу.',2,true,1000);assert.equal(signals[0].aborted,true);resolve({options:[]});await pending;
 now=2750;pending=scheduler.tick();assert.equal(signals.length,2);assert(generations[1]>generations[0]);scheduler.cancel();assert.equal(signals[1].aborted,true);resolve({options:[]});await pending;assert.equal(results.length,0);
 scheduler.reset();scheduler.configure(true);scheduler.update('После нового Start?',1,true,now);now+=1000;pending=scheduler.tick();assert(generations[2]>generations[1]);resolve({options:[]});await pending;
});

test('a synchronous Stop at dispatch prevents the transport from starting',async()=>{
 let now=750,scheduler,calls=0;
 scheduler=new ReplyScheduler({clock:()=>now,generate:async()=>{calls++;return{options:[]}},onResult:()=>assert.fail('Stopped result'),onState:state=>{if(state==='loading')scheduler.cancel()}});
 scheduler.configure(true);scheduler.update('Уточните условия?',1,true,0);await scheduler.tick();assert.equal(calls,0);assert.equal(scheduler.busy,false);
});

test('blocked hints cannot block or trim observed transcript including negation and numbers',async()=>{
 let now=0,resolve;const ledger=new ConversationLedger(),scheduler=new ReplyScheduler({clock:()=>now,generate:()=>new Promise(r=>resolve=r),onResult:()=>assert.fail('Obsolete result')});
 scheduler.configure(true);ledger.observe('Стоимость 3.5, не 35. ',now);scheduler.update(ledger.context(),ledger.revision,true,now);now=750;const pending=scheduler.tick();
 for(let i=0;i<20;i++){now+=100;ledger.observe(`Проверка ${i}, не ${i+1}. `,now);scheduler.update(ledger.context(),ledger.revision,true,now)}
 assert.equal(ledger.items.length,21);assert.equal(ledger.items[0].text,'Стоимость 3.5, не 35.');assert.equal(ledger.items.at(-1).text,'Проверка 19, не 20.');resolve({options:[]});await pending;
});

test('latency percentiles only count accepted stages, bound samples, and contain no text',()=>{
 const metrics=new LatencyWindow(3);
 for(let revision=1;revision<=5;revision++){metrics.mark('context_updated',{revision,changed_at_ms:0,text:'PRIVATE-SYNTHETIC'},0);metrics.mark('dispatch',{revision},10);metrics.mark('response',{revision},10+revision*10);metrics.mark('render_accepted',{revision},10+revision*20)}
 assert.deepEqual(metrics.snapshot().requestToRender,{samples:3,p50:80,p95:100});assert.equal(metrics.changed.size,3);assert.equal(metrics.dispatches.size,0);assert(!JSON.stringify(metrics).includes('PRIVATE-SYNTHETIC'));
 metrics.mark('dispatch',{revision:6},100);metrics.mark('discard',{revision:6},101);metrics.mark('render_accepted',{revision:6},102);assert.equal(metrics.snapshot().requestToRender.samples,3);metrics.clear();assert.equal(metrics.snapshot().requestToRender.samples,0);
});

test('karaoke preserves exact words, negations, punctuation and decimal numbers',()=>{
 const reader=new KaraokeReader();const text='  I do NOT agree.\nThe price is 3.5, not 35.  ';
 reader.prepare(text,1);assert.equal(reader.text,text);assert.deepEqual(reader.words.map(w=>w.text),['I','do','NOT','agree.','The','price','is','3.5,','not','35.']);
 for(const word of reader.words)assert.equal(text.slice(word.start,word.end),word.text);assert.equal(reader.state,'ready');assert.equal(reader.tick(),false);
});

test('karaoke requires explicit play, ignores stale timers and pauses without skipping on interruption',()=>{
 let now=0;const reader=new KaraokeReader({clock:()=>now,wordsPerMinute:120});reader.prepare('Do not send 35.',1);reader.play();const old=reader.generation;now=500;assert(reader.tick(old));assert.equal(reader.index,1);
 reader.interrupt();now=5000;assert.equal(reader.tick(old),false);assert.equal(reader.index,1);reader.play();const resumed=reader.generation;now=10000;reader.tick(resumed);assert.equal(reader.index,2);assert.equal(reader.tick(resumed),false);
 reader.prepare('Do not send 35.',2);assert.equal(reader.index,0);assert.equal(reader.state,'ready');assert.equal(reader.tick(resumed),false);reader.seek(99);assert.equal(reader.index,3);reader.seek(-10);assert.equal(reader.index,0);assert.throws(()=>reader.seek(NaN));
 reader.prepare('   ',3);assert.equal(reader.state,'empty');assert.equal(reader.play(),false);
});
