// Suppress accidental repeated clicks. No provider retry or implicit restart.
export class SessionClicks{
 constructor(interval=300){this.interval=interval;this.previous=-Infinity;}
 accept(now){if(now-this.previous<this.interval)return false;this.previous=now;return true;}
}
