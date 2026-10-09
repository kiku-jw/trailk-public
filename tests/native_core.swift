import Foundation
import AVFoundation
@main struct CoreTests {
 static func main()throws {
  assert(descends(40,20,parent:{[40:30,30:20][$0] ?? 1}))
  assert(!descends(40,99,parent:{[40:30,30:40][$0] ?? 1}))
  assert(!descends(40,1,parent:{_ in 1}))
  assert(!descends(40,20,parent:{_ in 0}))
  for rate in [16000.0,44100.0,48000.0] {
   let f=AVAudioFormat(commonFormat:.pcmFormatFloat32,sampleRate:rate,channels:2,interleaved:false)!
   let b=AVAudioPCMBuffer(pcmFormat:f,frameCapacity:AVAudioFrameCount(rate))!;b.frameLength=b.frameCapacity
   for c in 0..<2{for i in 0..<Int(b.frameLength){b.floatChannelData![c][i]=Float(sin(Double(i)*2*Double.pi*440/rate)*0.2)}}
   let out=try PCMConverter(input:f).convert(b)
   FileHandle.standardError.write(Data("RATE \(rate) OUTPUT \(out.count)\n".utf8))
   assert(abs(out.count-48000)<512);assert(out.count%2==0)
   let maximum=out.withUnsafeBytes{raw in raw.bindMemory(to:Int16.self).map{abs(Int($0))}.max() ?? 0}
   assert(maximum>1000 && maximum<=32767)
   print("PASS conversion \(Int(rate)) stereo →24000mono PCM16: \(out.count)bytes")
  }
  let neverStarted=CaptureSession();neverStarted.stop();neverStarted.stop()
  print("PASS process scope/cycle exclusion and idempotent stop without capture")
 }
}
