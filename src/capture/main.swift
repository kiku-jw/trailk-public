import Foundation
import AppKit
import AVFoundation

final class AppDelegate:NSObject,NSApplicationDelegate,NSWindowDelegate {
 let session=CaptureSession();var window:NSWindow!,status:NSTextField!,source:NSPopUpButton!,start:NSButton!,stop:NSButton!
 var player:AVAudioPlayer?;var beginning=false
 var sessionApproval:[String:Any]? {guard let raw=ProcessInfo.processInfo.environment["CALM_SESSION_APPROVAL"],let data=raw.data(using:.utf8) else{return nil};return (try? JSONSerialization.jsonObject(with:data)) as? [String:Any]}
 let dataRoot=ProcessInfo.processInfo.environment["CALM_DATA_ROOT"] ?? (NSHomeDirectory()+"/Library/Application Support/Calm Translate")
 var socketPath:String {sessionApproval?["socket_path"] as? String ?? (dataRoot+"/runtime/audio.sock")}
 func applicationDidFinishLaunching(_ notification:Notification){
  NSApp.setActivationPolicy(sessionApproval==nil ? .regular:.accessory)
  if ProcessInfo.processInfo.environment["CALM_MANAGED_CHILD"]=="1" {DispatchQueue.global().async {let _=FileHandle.standardInput.readDataToEndOfFile();DispatchQueue.main.async{NSApp.terminate(nil)}}}
  window=NSWindow(contentRect:NSRect(x:0,y:0,width:660,height:260),styleMask:[.titled,.closable,.miniaturizable],backing:.buffered,defer:false)
  window.title="Trailk · доступ к звуку Zoom";window.delegate=self
  let content=window.contentView!
  let heading=NSTextField(labelWithString:"Захват только Zoom. Для первой проверки выберите публичный образец.")
  heading.frame=NSRect(x:22,y:206,width:620,height:30);content.addSubview(heading)
  source=NSPopUpButton(frame:NSRect(x:22,y:153,width:390,height:32));source.addItems(withTitles:["Публичный образец · только звук этого helper","Zoom · только output процесса Zoom"]);content.addSubview(source)
  start=NSButton(title:"Начать локальный захват",target:self,action:#selector(begin));start.frame=NSRect(x:22,y:104,width:250,height:32);content.addSubview(start)
  stop=NSButton(title:"Остановить сессию",target:self,action:#selector(end));stop.frame=NSRect(x:285,y:104,width:220,height:32);stop.isEnabled=false;content.addSubview(stop)
  status=NSTextField(wrappingLabelWithString:"Не запущено. Нужен локальный приёмник и отдельное System Audio Recording Only разрешение. Без микрофона и экрана. Облако запускается только после согласия в Trailk.")
  status.frame=NSRect(x:22,y:20,width:615,height:70);content.addSubview(status)
  session.onState={[weak self] value in self?.status.stringValue=value;let active=self?.session.running ?? false;self?.start.isEnabled = !active;self?.stop.isEnabled=active;self?.source.isEnabled = !active}
  window.center()
  if sessionApproval != nil {source.selectItem(at:1);begin()} else {window.makeKeyAndOrderFront(nil);NSApp.activate(ignoringOtherApps:true)}
 }
 @objc func begin(){
  guard !session.running && !beginning else{return}
  beginning=true;start.isEnabled=false;source.isEnabled=false
  defer{beginning=false;start.isEnabled = !session.running;source.isEnabled = !session.running}
  do {
   let kind=source.indexOfSelectedItem==0 ? "public_sample":"zoom"
   let approval:[String:Any]
   if let grant=sessionApproval {
    guard grant["resume_audio"] as? Bool==true,grant["source"] as? String=="zoom",socketPath.hasPrefix(dataRoot+"/runtime/") else{status.stringValue="Нет отдельного разрешения этой сессии.";return}
    approval=grant
   } else {
    guard !FileManager.default.fileExists(atPath:dataRoot+"/AUDIO-DO-NOT-PLAY.json") else {status.stringValue="Звук остановлен по вашей просьбе. Для нового теста нужна новая просьба; системный захват не запрашивался.";return}
    let approvalPath=dataRoot+"/CAPTURE-APPROVAL.json"
    guard let approvalData=try? Data(contentsOf:URL(fileURLWithPath:approvalPath)),let value=(try? JSONSerialization.jsonObject(with:approvalData)) as? [String:Any] else{status.stringValue="Этот источник ещё не разрешён.";return}
    approval=value
   }
   guard approval["approved"] as? Bool==true,approval["source"] as? String==kind else{status.stringValue="Нет отдельного разрешения этого источника.";return}
   let maximum=kind=="public_sample" ? 150 : (approval["maximum_seconds"] as? Double ?? 0)
   if kind=="zoom" {
    let expiry=approval["expires_unix"] as? Double ?? 0
    guard [2,3,4].contains(approval["schema_version"] as? Int ?? 0),!(approval["approval_id"] as? String ?? "").trimmingCharacters(in:.whitespaces).isEmpty,approval["private_call_capture"] as? Bool==true,approval["capture_scope"] as? String=="zoom_output",approval["microphone"] as? Bool==false,maximum>0,maximum<=(approval["schema_version"] as? Int==4 && approval["unlimited_spend_approved"] as? Bool==true ? 21600:10/0.034*60),expiry>Date().timeIntervalSince1970,expiry<=Date().timeIntervalSince1970+86400 else{status.stringValue="Нужно отдельное действующее согласие на звук Zoom и длительность. Захват заблокирован.";return}
   }
   let pid:pid_t
   if source.indexOfSelectedItem==0 {
    guard let file=Bundle.main.url(forResource:"public-irish",withExtension:"wav") else{throw CaptureFailure.sourceMissing}
    player=try AVAudioPlayer(contentsOf:file);player?.prepareToPlay();player?.play();pid=getpid()
    let deadline=Date().addingTimeInterval(2)
    while scopedObjects(pid).isEmpty && Date()<deadline{RunLoop.current.run(until:Date().addingTimeInterval(0.05))}
   } else {
    guard let selected=zoomRoot() else{throw CaptureFailure.ambiguousSource};pid=selected
   }
   try session.start(root:pid,source:kind,socket:socketPath,maximum:maximum,idleLimit:kind=="zoom" ? 0:60)
  } catch {player?.stop();player=nil;status.stringValue="Захват не начался. Нужен активный публичный источник/Zoom, локальный приёмник и отдельный системный доступ. Поток остановлен; повтор только вручную.";window.makeKeyAndOrderFront(nil);NSApp.activate(ignoringOtherApps:true)}
 }
 @objc func end(){session.stop();player?.stop();player=nil}
 func windowWillClose(_ notification:Notification){end();NSApp.terminate(nil)}
 func applicationWillTerminate(_ notification:Notification){end()}
}
let delegate=AppDelegate();NSApplication.shared.delegate=delegate;NSApplication.shared.run()
