import AppKit
let size=1024
let image=NSImage(size:NSSize(width:size,height:size))
image.lockFocus()
let rect=NSRect(x:0,y:0,width:size,height:size)
NSColor(calibratedRed:0.12,green:0.27,blue:0.47,alpha:1).setFill()
NSBezierPath(roundedRect:rect.insetBy(dx:28,dy:28),xRadius:210,yRadius:210).fill()
NSColor(calibratedRed:0.95,green:0.97,blue:1,alpha:1).setFill()
NSBezierPath(roundedRect:NSRect(x:180,y:260,width:664,height:520),xRadius:80,yRadius:80).fill()
let tail=NSBezierPath();tail.move(to:NSPoint(x:310,y:300));tail.line(to:NSPoint(x:235,y:155));tail.line(to:NSPoint(x:455,y:300));tail.close();tail.fill()
NSColor(calibratedRed:0.12,green:0.27,blue:0.47,alpha:1).setFill()
for (y,w) in [(640,440),(520,320),(400,410)] {NSBezierPath(roundedRect:NSRect(x:290,y:y,width:w,height:44),xRadius:22,yRadius:22).fill()}
image.unlockFocus()
let bitmap=NSBitmapImageRep(data:image.tiffRepresentation!)!
try bitmap.representation(using:.png,properties:[:])!.write(to:URL(fileURLWithPath:CommandLine.arguments[1]))
