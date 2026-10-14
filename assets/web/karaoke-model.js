// Reading pace only. Preserve every word, number, negation and original character.
export class KaraokeReader {
 constructor({clock=()=>performance.now(),wordsPerMinute=180}={}){this.clock=clock;this.wordsPerMinute=wordsPerMinute;this.text='';this.words=[];this.index=0;this.generation=0;this.identity=null;this.state='empty';this.nextAt=0;}
 prepare(text,identity){if(typeof text!=='string')throw TypeError('Text required');if(text===this.text&&identity===this.identity)return false;this.generation++;this.identity=identity;this.text=text;this.words=[...text.matchAll(/\S+/gu)].map(m=>({text:m[0],start:m.index,end:m.index+m[0].length}));this.index=0;this.state=this.words.length?'ready':'empty';return true;}
 play(){if(!this.words.length)return false;if(this.state==='completed')this.index=0;this.generation++;this.state='playing';this.nextAt=this.clock()+60000/this.wordsPerMinute;return true;}
 pause(){this.generation++;if(this.state==='playing')this.state='paused';}
 interrupt(){this.pause();if(this.words.length)this.state='interrupted';}
 pace(value){if(!Number.isFinite(value)||value<80||value>300)throw RangeError('Invalid reading pace');this.wordsPerMinute=value;this.nextAt=this.clock()+60000/value;}
 seek(index){if(!Number.isFinite(index))throw TypeError('Word index required');this.pause();this.index=Math.max(0,Math.min(this.words.length-1,Math.trunc(index)));this.state=this.words.length?'paused':'empty';}
 tick(generation=this.generation){if(generation!==this.generation||this.state!=='playing'||this.clock()<this.nextAt)return false;if(this.index===this.words.length-1){this.state='completed';this.generation++;return true;}this.index++;this.nextAt=this.clock()+60000/this.wordsPerMinute;return true;}
}
