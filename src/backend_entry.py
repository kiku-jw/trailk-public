"""App-owned child: frozen runtime, local HTTP only, stops when parent pipe closes."""
import json, os, sys, threading, signal
from pathlib import Path

def prepare_data(root, assets):
    root.mkdir(parents=True, exist_ok=True, mode=0o700)
    os.chmod(root, 0o700)
    for source in (assets/'seeds').glob('*.json'):
        try:
            with (root/source.name).open('x') as out:
                out.write(source.read_text())
            os.chmod(root/source.name, 0o600)
        except FileExistsError:
            pass  # Never reset a reservation, decision or user stop.

def main():
    assets=Path(getattr(sys,'_MEIPASS',Path(__file__).resolve().parents[1]/'assets'))
    if '--self-test' in sys.argv:
        import ssl, certifi, websockets
        print(json.dumps({'frozen':bool(getattr(sys,'frozen',False)), 'python':sys.version.split()[0],
                          'tls':bool(ssl.create_default_context(cafile=certifi.where())),
                          'websockets':websockets.__version__, 'assets':(assets/'web/index.html').is_file()}))
        return
    prepare_data(Path(os.environ['CALM_DATA_ROOT']),assets)
    import backend_server as service
    server=service.Server(('127.0.0.1',0),service.Handler)
    service.HOST='127.0.0.1:'+str(server.server_port)
    stopped=threading.Event()
    def stop(*_):
        if not stopped.is_set():
            stopped.set()
            service.hints.close()
            service.audio.stop()
            if service.receiver: service.receiver.stop()
            threading.Thread(target=server.shutdown,daemon=True).start()
    def parent_pipe():
        # Native parent owns the write end. Crash, force quit and normal close all stop us.
        try: sys.stdin.buffer.readline(32)
        finally: stop()
    for sig in (signal.SIGTERM,signal.SIGINT): signal.signal(sig,stop)
    threading.Thread(target=parent_pipe,daemon=True).start()
    print(json.dumps({'ready':True,'port':server.server_port,'pid':os.getpid()}),flush=True)
    try: server.serve_forever(poll_interval=.1)
    finally:
        service.hints.close()
        service.audio.stop()
        if service.receiver: service.receiver.stop()
        server.server_close()

if __name__=='__main__':
    main()
