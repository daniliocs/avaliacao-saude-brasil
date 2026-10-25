"""
serve_local.py

Servidor local para desenvolvimento e homologação do Índice de Saúde Municipal.
- Força diretório raiz do projeto como base do servidor web.
- Desativa completamente o cache do navegador (HTTP no-cache/no-store) para garantir
  que qualquer alteração em arquivos HTML, JS, CSS e JSON seja carregada imediatamente.
- Redireciona a raiz (/) automaticamente para /site/index.html com cache-buster.
- Libera automaticamente instâncias zumbis anteriores do Python na porta 8000 se houver.
- Abre o navegador na porta exata onde o servidor subiu.
"""

import http.server
import os
import socketserver
import subprocess
import sys
import threading
import time
import webbrowser

PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
os.chdir(PROJECT_ROOT)

DEFAULT_PORT = 8000


class NoCacheHTTPRequestHandler(http.server.SimpleHTTPRequestHandler):
    def do_GET(self):
        # Se acessar http://localhost:8000/ ou /index.html direto, redireciona para a versão limpa
        if self.path in ("/", "/index.html"):
            ts = int(time.time())
            self.send_response(302)
            self.send_header("Location", f"/site/index.html?v=0.7.4&t={ts}")
            self.send_header("Cache-Control", "no-store, no-cache, must-revalidate, max-age=0")
            self.send_header("Pragma", "no-cache")
            self.send_header("Expires", "0")
            self.end_headers()
            return
        super().do_GET()

    def end_headers(self):
        self.send_header("Cache-Control", "no-store, no-cache, must-revalidate, max-age=0")
        self.send_header("Pragma", "no-cache")
        self.send_header("Expires", "0")
        super().end_headers()

    def log_message(self, format, *args):
        # Suprime logs de requisições rotineiras para manter o console limpo
        if "200 -" in format % args or "304 -" in format % args or "302 -" in format % args:
            return
        super().log_message(format, *args)


def free_zombie_python(port: int):
    """Encerra processos python órfãos que possam ter ficado travando a porta especificada."""
    try:
        cmd = f"netstat -ano -p tcp | findstr :{port}"
        out = subprocess.check_output(cmd, shell=True, text=True, errors="ignore")
        for line in out.strip().splitlines():
            if "LISTENING" in line:
                parts = line.strip().split()
                pid = parts[-1]
                if pid and pid != "0":
                    task_out = subprocess.check_output(f'tasklist /FI "PID eq {pid}" /NH', shell=True, text=True, errors="ignore").lower()
                    if "python" in task_out:
                        print(f"  [Info] Liberando porta {port} ocupada por processo Python anterior (PID {pid})...")
                        subprocess.run(f"taskkill /F /PID {pid}", shell=True, capture_output=True)
                        time.sleep(0.6)
    except Exception:
        pass


def start_server():
    ports_to_try = [DEFAULT_PORT, 8080, 8081, 8088]
    if len(sys.argv) > 1:
        try:
            ports_to_try = [int(sys.argv[1])] + ports_to_try
        except ValueError:
            pass

    httpd = None
    active_port = None
    socketserver.TCPServer.allow_reuse_address = True

    for port in ports_to_try:
        free_zombie_python(port)
        try:
            httpd = socketserver.TCPServer(("", port), NoCacheHTTPRequestHandler)
            active_port = port
            break
        except OSError:
            continue

    if not httpd:
        print("[Erro Crítico] Nenhuma das portas de desenvolvimento (8000, 8080, 8081) está disponível.")
        sys.exit(1)

    ts = int(time.time())
    url = f"http://localhost:{active_port}/site/index.html?v=0.7.4&t={ts}"

    print("===================================================================")
    print(f"  Servidor Local Ativo (SEM CACHE) na porta {active_port}")
    print(f"  Versão: v0.7.4 (Fase 2: Urgência & Oncologia Completa)")
    print(f"  Acessando: {url}")
    print("  (Para encerrar o servidor, basta fechar esta janela)")
    print("===================================================================")

    # Abre o navegador no navegador padrão após 400ms
    threading.Timer(0.4, lambda: webbrowser.open(url)).start()

    with httpd:
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print("\nServidor encerrado pelo usuário.")
            sys.exit(0)


if __name__ == "__main__":
    start_server()
