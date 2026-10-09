import Foundation
import AppKit
import CoreAudio
import AudioToolbox
import AVFoundation
import Darwin

// Own implementation following AudioCap's BSD CoreAudio lifecycle pattern.
// No ScreenCaptureKit, microphone, private TCC SPI, global/exclusive tap or driver.
let zoomBundle = "us.zoom.xos"
enum CaptureFailure: Error {case sourceMissing, ambiguousSource, socketUnavailable, tapCreation, aggregateCreation, format, io, backlog, targetChanged, noInput}
func address(_ selector:AudioObjectPropertySelector)->AudioObjectPropertyAddress {
 AudioObjectPropertyAddress(mSelector:selector,mScope:kAudioObjectPropertyScopeGlobal,mElement:kAudioObjectPropertyElementMain)
}
func readValue<T>(_ object:AudioObjectID,_ selector:AudioObjectPropertySelector,_ initial:T)->T? {
 var a=address(selector),value=initial,size=UInt32(MemoryLayout<T>.size)
 let status=withUnsafeMutablePointer(to:&value){AudioObjectGetPropertyData(object,&a,0,nil,&size,$0)}
 return status == noErr ? value:nil
}
func processObjects()->[AudioObjectID] {
 var a=address(kAudioHardwarePropertyProcessObjectList),size:UInt32=0
 guard AudioObjectGetPropertyDataSize(AudioObjectID(kAudioObjectSystemObject),&a,0,nil,&size)==noErr else{return []}
 var objects=[AudioObjectID](repeating:0,count:Int(size)/MemoryLayout<AudioObjectID>.size)
 guard AudioObjectGetPropertyData(AudioObjectID(kAudioObjectSystemObject),&a,0,nil,&size,&objects)==noErr else{return []}
 return objects
}
func parentPID(_ pid:pid_t)->pid_t {
 var info=proc_bsdinfo()
 let size=Int32(MemoryLayout<proc_bsdinfo>.size)
 guard proc_pidinfo(pid,PROC_PIDTBSDINFO,0,&info,size)==size else{return 0}
 return pid_t(info.pbi_ppid)
}
func descends(_ pid:pid_t,_ root:pid_t,parent:(pid_t)->pid_t=parentPID)->Bool {
 var current=pid;var seen=Set<pid_t>()
 for _ in 0..<16 {
  if current<=1 || seen.contains(current){return false}
  if current==root{return true};seen.insert(current);current=parent(current)
 }
 return false
}
func scopedObjects(_ root:pid_t)->[AudioObjectID] {
 processObjects().filter{obj in
  guard let pid:pid_t=readValue(obj,kAudioProcessPropertyPID,0),pid>1 else{return false}
  return descends(pid,root)
 }.sorted()
}
func zoomRoot()->pid_t? {
 let apps=NSRunningApplication.runningApplications(withBundleIdentifier:zoomBundle).filter{!$0.isTerminated}
 guard apps.count==1,let app=apps.first,app.bundleURL?.lastPathComponent=="zoom.us.app" else{return nil}
 return app.processIdentifier
}
final class PCMConverter {
 let input:AVAudioFormat,output:AVAudioFormat,converter:AVAudioConverter
 init(input:AVAudioFormat)throws {
  self.input=input
  guard let output=AVAudioFormat(commonFormat:.pcmFormatInt16,sampleRate:24000,channels:1,interleaved:true),let converter=AVAudioConverter(from:input,to:output) else{throw CaptureFailure.format}
  self.output=output;self.converter=converter;converter.primeMethod = .none
 }
 func convert(_ buffer:AVAudioPCMBuffer)throws->Data {
  let capacity=AVAudioFrameCount(ceil(Double(buffer.frameLength)*24000/input.sampleRate)+128)
  guard let out=AVAudioPCMBuffer(pcmFormat:output,frameCapacity:capacity) else{throw CaptureFailure.format}
  var cursor:AVAudioFrameCount=0,error:NSError?
  let status=converter.convert(to:out,error:&error){requested,state in
   guard cursor<buffer.frameLength else{state.pointee = .noDataNow;return nil}
   let frames=min(AVAudioFrameCount(requested),buffer.frameLength-cursor)
   guard let chunk=AVAudioPCMBuffer(pcmFormat:self.input,frameCapacity:frames) else{state.pointee = .noDataNow;return nil}
   chunk.frameLength=frames
   let source=UnsafeMutableAudioBufferListPointer(buffer.mutableAudioBufferList)
   let destination=UnsafeMutableAudioBufferListPointer(chunk.mutableAudioBufferList)
   let stride=Int(self.input.streamDescription.pointee.mBytesPerFrame)
   for i in 0..<min(source.count,destination.count){
    if let from=source[i].mData,let to=destination[i].mData{memcpy(to,from.advanced(by:Int(cursor)*stride),Int(frames)*stride)}
   }
   cursor+=frames;state.pointee = .haveData;return chunk
  }
  guard error==nil,status != .error,let samples=out.int16ChannelData else{throw CaptureFailure.format}
  return Data(bytes:samples[0],count:Int(out.frameLength)*2)
 }
}
// Nonblocking local pipe. A slow/disconnected consumer stops capture; no growing backlog.
final class LocalPipe {
 private var descriptor:Int32 = -1
 init(path:String,source:String)throws {
  guard path.utf8.count<104 else{throw CaptureFailure.socketUnavailable}
  var socketAddress=sockaddr_un();socketAddress.sun_family=sa_family_t(AF_UNIX)
  socketAddress.sun_len=UInt8(MemoryLayout<sockaddr_un>.size)
  withUnsafeMutableBytes(of:&socketAddress.sun_path){target in
   target.initializeMemory(as:UInt8.self,repeating:0)
   for (i,byte) in path.utf8.enumerated(){target[i]=byte}
  }
  descriptor=socket(AF_UNIX,SOCK_STREAM,0)
  guard descriptor>=0 else{throw CaptureFailure.socketUnavailable}
  let status=withUnsafePointer(to:&socketAddress){ptr in ptr.withMemoryRebound(to:sockaddr.self,capacity:1){Darwin.connect(descriptor,$0,socklen_t(MemoryLayout<sockaddr_un>.size))}}
  guard status==0 else{close();throw CaptureFailure.socketUnavailable}
  var one:Int32=1
  setsockopt(descriptor,SOL_SOCKET,SO_NOSIGPIPE,&one,socklen_t(MemoryLayout<Int32>.size))
  _ = fcntl(descriptor,F_SETFL,O_NONBLOCK)
  let header=try JSONSerialization.data(withJSONObject:["source":source,"rate":24000,"channels":1,"encoding":"s16le"])
  try writePCM(header+Data([10]))
 }
 func writePCM(_ data:Data)throws {
  guard descriptor>=0 else{throw CaptureFailure.socketUnavailable}
  let sent=data.withUnsafeBytes{p in Darwin.write(descriptor,p.baseAddress,data.count)}
  guard sent==data.count else{throw CaptureFailure.backlog}
 }
 func close(){if descriptor>=0{Darwin.close(descriptor);descriptor = -1}}
 deinit{close()}
}
final class CaptureSession: @unchecked Sendable {
 private var tap:AudioObjectID=0,aggregate:AudioObjectID=0,io:AudioDeviceIOProcID?
 private let queue=DispatchQueue(label:"local.calm.capture",qos:.userInitiated)
 private var timer:DispatchSourceTimer?,pipe:LocalPipe?,converter:PCMConverter?
 private var root:pid_t=0,objects:[AudioObjectID]=[],started=Date(),lastSound=Date(),lastBuffer=Date()
 private var outputDevice:AudioObjectID=0
 private var active=false
 private let stateLock=NSLock()
 var running:Bool{stateLock.lock();defer{stateLock.unlock()};return active}
 private func setRunning(_ value:Bool){stateLock.lock();active=value;stateLock.unlock()}
 var onState:((String)->Void)?
 // Called on main, single lifecycle owner. No auto-resume or broadened source.
 func start(root:pid_t,source:String,socket:String,maximum:Double=150,idleLimit:Double=60)throws {
  guard (source=="public_sample" && root==getpid()) || (source=="zoom" && root==zoomRoot()) else{throw CaptureFailure.ambiguousSource}
  guard !running else{return}
  guard maximum>0 && maximum<=21600 else{throw CaptureFailure.format}
  self.root=root;objects=scopedObjects(root)
  guard root>1,!objects.isEmpty else{throw CaptureFailure.sourceMissing}
  let desc=CATapDescription(monoMixdownOfProcesses:objects);desc.uuid=UUID();desc.name="Calm Translate scoped output";desc.isPrivate=true;desc.muteBehavior = .unmuted
  do {
   pipe=try LocalPipe(path:socket,source:source) // local consumer must exist BEFORE permission/tap
   guard AudioHardwareCreateProcessTap(desc,&tap)==noErr else{throw CaptureFailure.tapCreation}
   guard var format:AudioStreamBasicDescription=readValue(tap,kAudioTapPropertyFormat,AudioStreamBasicDescription()),let avFormat=AVAudioFormat(streamDescription:&format) else{throw CaptureFailure.format}
   converter=try PCMConverter(input:avFormat)
   let config:[String:Any]=[kAudioAggregateDeviceNameKey:"Calm Translate private tap",kAudioAggregateDeviceUIDKey:UUID().uuidString,kAudioAggregateDeviceIsPrivateKey:true,kAudioAggregateDeviceIsStackedKey:false,kAudioAggregateDeviceTapAutoStartKey:true,kAudioAggregateDeviceSubDeviceListKey:[],kAudioAggregateDeviceTapListKey:[[kAudioSubTapUIDKey:desc.uuid.uuidString,kAudioSubTapDriftCompensationKey:true]]]
   guard AudioHardwareCreateAggregateDevice(config as CFDictionary,&aggregate)==noErr else{throw CaptureFailure.aggregateCreation}
   guard AudioDeviceCreateIOProcIDWithBlock(&io,aggregate,queue,{[weak self] _,input,_,_,_ in
    guard let self,let c=self.converter,self.running else{return}
    do {
     guard let buffer=AVAudioPCMBuffer(pcmFormat:c.input,bufferListNoCopy:input,deallocator:nil) else{throw CaptureFailure.format}
     let pcm=try c.convert(buffer);self.lastBuffer=Date()
     let audible=pcm.withUnsafeBytes{raw in raw.bindMemory(to:Int16.self).contains{abs(Int($0))>100}}
     if audible{self.lastSound=Date()}
     try self.pipe?.writePCM(pcm)
    } catch {DispatchQueue.main.async{self.stop(reason:"Поток остановлен: конверсия/буфер/локальный приёмник.")}}
   })==noErr,io != nil else{throw CaptureFailure.io}
   started=Date();lastSound=started;lastBuffer=started;setRunning(true)
   guard AudioDeviceStart(aggregate,io)==noErr else{throw CaptureFailure.io}
   outputDevice=readValue(AudioObjectID(kAudioObjectSystemObject),kAudioHardwarePropertyDefaultOutputDevice,AudioObjectID(0)) ?? 0
   let watch=DispatchSource.makeTimerSource(queue:queue)
   watch.schedule(deadline:.now() + .milliseconds(250),repeating:.milliseconds(250))
   watch.setEventHandler{[weak self] in
    guard let self,self.running else{return}
    let targetGone=kill(self.root,0) != 0 && errno==ESRCH
    let changed=scopedObjects(self.root) != self.objects
    let device=readValue(AudioObjectID(kAudioObjectSystemObject),kAudioHardwarePropertyDefaultOutputDevice,AudioObjectID(0)) ?? 0
    let age=Date().timeIntervalSince(self.started),idle=Date().timeIntervalSince(self.lastSound)
    if targetGone||changed||device != self.outputDevice||age>=maximum||(idleLimit>0 && idle>=idleLimit)||Date().timeIntervalSince(self.lastBuffer)>5 {
     DispatchQueue.main.async{self.stop(reason:"Остановлено: источник/устройство изменились, нет входа или достигнут лимит. Продолжение вручную.")}
    }
   };timer=watch;watch.resume();onState?("Захват включён. Только выбранный процесс; без микрофона. Лимит \(Int(maximum))с; при изменении источника — остановка.")
  } catch {stop(reason:"Захват не начался. Проверьте отдельное разрешение и публичный источник.");throw error}
 }
 func stop(reason:String="Остановлено пользователем.") {
  guard running||tap != 0||aggregate != 0||pipe != nil else{return}
  setRunning(false);timer?.cancel();timer=nil
  if aggregate != 0,let io{AudioDeviceStop(aggregate,io);AudioDeviceDestroyIOProcID(aggregate,io)}
  self.io=nil
  // Wait for the serial conversion callback before releasing its state/pipe.
  queue.sync{}
  converter=nil;pipe?.close();pipe=nil
  if aggregate != 0{AudioHardwareDestroyAggregateDevice(aggregate);aggregate=0}
  if tap != 0{AudioHardwareDestroyProcessTap(tap);tap=0}
  onState?(reason)
 }
 deinit{stop()}
}
