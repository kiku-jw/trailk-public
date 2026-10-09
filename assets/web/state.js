import {sentencePrefix} from './segments.js';
import {SpeakerEvidence} from './t9.js';
export class Transcript {
 constructor(){this.draft='';this.history=[];this.rows=[];this.seen=new Set();this.speakers=new SpeakerEvidence();}
 add(event){if(this.seen.has(event.seq))return [];this.seen.add(event.seq);const blocks=[];
 if(event.kind==='delta'){this.draft+=event.text;while(true){const sentence=sentencePrefix(this.draft);if(sentence&&sentence.length<=160){blocks.push(sentence);this.draft=this.draft.slice(sentence.length);continue;}if(this.draft.length<=120)break;let cut=this.draft.lastIndexOf(' ',120);cut=cut<30?120:cut+1;blocks.push(this.draft.slice(0,cut));this.draft=this.draft.slice(cut);}}
 if(['end','boundary'].includes(event.kind)&&this.draft){blocks.push(this.draft);this.draft='';}
 for(const text of blocks){this.history.push(text);this.rows.push({text,speaker_label:this.speakers.label({...event,evidence:event.speaker_evidence||event.evidence}),input_position_seconds:event.input_position_seconds??null,received_elapsed_seconds:event.received_elapsed_seconds??null});}return blocks;}
}
export class Replay {
 constructor(events,onEvent,onState){this.events=events;this.onEvent=onEvent;this.onState=onState;this.cursor=0;this.timer=null;this.sequence=0;}
 start(){if(this.timer!==null)return;this.onState(true);this.timer=setInterval(()=>{if(this.cursor>=this.events.length){this.stop();return;}this.onEvent({...this.events[this.cursor++],seq:++this.sequence});if(this.cursor===this.events.length)this.stop();},35);}
 stop(){if(this.timer!==null)clearInterval(this.timer);this.timer=null;this.onState(false);}
 get running(){return this.timer!==null;}
}
