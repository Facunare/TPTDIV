from socket import *
import sys
import os
from urllib.parse import parse_qs, urlparse
import qrcode
import mimetypes
import gzip
import io
import time

def imprimir_qr_en_terminal(url):
    """Dada una URL la imprime por terminal como un QR"""
    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_L,
        box_size=10,
        border=4,
    )
    qr.add_data(url)
    qr.make(fit=True)

    qr.print_ascii(invert=True) # Permite imprimir en la consola

def get_wifi_ip():
    """Obtiene la IP local asociada a la interfaz de red (por ejemplo, Wi-Fi)."""
    s = socket(AF_INET, SOCK_DGRAM)
    try:
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
    finally:
        s.close()
    return ip #Devuelve la IP como string

def parsear_multipart(body, boundary):
    """Función auxiliar (ya implementada) para parsear multipart/form-data."""
    try:
        # Se divide el cuerpo por el boundary para luego poder extraer el nombre y contenido del archivo
        parts = body.split(f'--{boundary}'.encode())
        for part in parts:
            if b'filename=' in part:
                # Se extrae el nombre del archivo
                filename_start = part.find(b'filename="') + len(b'filename="')
                filename_end = part.find(b'"', filename_start)
                filename = part[filename_start:filename_end].decode()

                # Se extrae el contenido del archivo que arranca después de los headers
                header_end = part.find(b'\r\n\r\n')
                if header_end == -1:
                    header_end = part.find(b'\n\n')
                    content_start = header_end + 2
                else:
                    content_start = header_end + 4

                # El contenido va hasta el último CRLF antes del boundary
                content_end = part.rfind(b'\r\n')
                if content_end <= content_start:
                    content_end = part.rfind(b'\n')

                file_content = part[content_start:content_end]
                if filename and file_content:
                    return filename, file_content
        return None, None
    except Exception as e:
        print(f"Error al parsear multipart: {e}")
        return None, None

def generar_html_interfaz(modo):
    """
    Genera el HTML de la interfaz principal:
    - Si modo == 'download': incluye un enlace o botón para descargar el archivo.
    - Si modo == 'upload': incluye un formulario para subir un archivo.
    """
    if modo == 'download':
        return """
<html>
  <head>
    <meta charset="utf-8">
    <title>Descargar archivo</title>
    <style>
      body { font-family: sans-serif; max-width: 500px; margin: 50px auto; }
      a { display: inline-block; padding: 10px 20px; background: #007bff; color: white; text-decoration: none; border-radius: 5px; }
    </style>
  </head>
  <body>
    <h1>Descargar archivo</h1>
    <p>Haz click en el botón para descargar:</p>
    <a href="/download">Descargar archivo</a>
  </body>
</html>
"""
    
    else:  # upload
        return """
<html>
  <head>
    <meta charset="utf-8">
    <title>Subir archivo</title>
    <style>
      body { font-family: sans-serif; max-width: 500px; margin: 50px auto; }
      form { border: 2px dashed #ccc; padding: 20px; border-radius: 5px; }
      input[type="submit"] { padding: 10px 20px; background: #28a745; color: white; border: none; border-radius: 5px; cursor: pointer; }
    </style>
  </head>
  <body>
    <h1>Subir archivo</h1>
    <form method="POST" enctype="multipart/form-data">
      <input type="file" name="file" required>
      <input type="submit" value="Subir">
    </form>
  </body>
</html>
"""



#CODIGO A COMPLETAR



def manejar_descarga(archivo, request_line, usar_gzip=False, acepta_gzip=False):
    """
    Genera una respuesta HTTP con el archivo solicitado. 
    Si el archivo no existe debe devolver un error.
    Debe incluir los headers: Content-Type, Content-Length y Content-Disposition.
    """
    # Usamos el parametro request_line para solo aceptar GET y /download.
    try:
        metodo = request_line.split(" ")[0]
        ruta = request_line.split(" ")[1]
    except:
        return b"HTTP/1.1 400 Bad Request\r\n\r\n"

    if metodo != "GET":
        return b"HTTP/1.1 405 Method Not Allowed\r\nAllow: GET\r\n\r\n"

    if ruta != "/download":
        return b"HTTP/1.1 404 Not Found\r\n\r\n"
    
    # Error si el archivo no existe
    if not os.path.exists(archivo):
        respuesta = (
            "HTTP/1.1 404 Not Found\r\n"
            "Content-Type: text/html\r\n\r\n"
            "<html><body><h1>404 - Archivo no encontrado</h1></body></html>"
        )
        return respuesta.encode()
    
    # Adivina el tipo MIME del archivo
    tipo = mimetypes.guess_type(archivo)[0]
    if tipo is None:
        tipo = "application/octet-stream" # Esto es cuando no reconce el tipo
    tamano = os.path.getsize(archivo)
    nombre_archivo = os.path.basename(archivo)

    with open(archivo, "rb") as f:
       contenido = f.read()

    # Esto es para el caso en que se incluya el comando "gzip"
    if usar_gzip and acepta_gzip:
        buffer = io.BytesIO()
        with gzip.GzipFile(fileobj=buffer, mode="wb") as gz:
            gz.write(contenido)
        contenido = buffer.getvalue()
        content_encoding = "gzip"

        # Experimentacion con gzip
        print(f"Archivo comprimido: {len(contenido)} bytes (el original {os.path.getsize(archivo)} bytes)")
        ratio = os.path.getsize(archivo) / len(contenido)
        print(f"Ratio: {ratio}.")
    else:
        content_encoding = None

    # Respuesta 200 OK con los headers Content-Type, Content-Length y Content-Disposition
    tamano = len(contenido)

    headers = (
        f"HTTP/1.1 200 OK\r\n"
        f"Content-Type: {tipo}\r\n"
        f"Content-Disposition: attachment; filename=\"{nombre_archivo}\"\r\n"
    )

    if content_encoding:
        headers += "Content-Encoding: gzip\r\n"

    headers += f"Content-Length: {tamano}\r\n\r\n"

    return headers.encode() + contenido

def manejar_carga(body, boundary, directorio_destino="."):
    """
    Procesa un POST con multipart/form-data, guarda el archivo y devuelve una página de confirmación.
    """
    filename, file_content = parsear_multipart(body, boundary)

    # Error cuando el archivo es invalido o vacio
    if not filename or not file_content:
        respuesta = (
            "HTTP/1.1 400 Bad Request\r\n"
            "Content-Type: text/html\r\n\r\n"
            "<html><body><h1>Error: archivo inválido o vacío</h1></body></html>"
        )
        return respuesta.encode()
    
    # Se crea el directorio archivo_servidor donde se guardan los "uploads"
    os.makedirs(directorio_destino, exist_ok=True)
    ruta_destino = os.path.join(directorio_destino, filename)
    with open(ruta_destino, "wb") as f:
       f.write(file_content)

    html = f"""
    <html>
        <head><meta charset="utf-8"><title>Archivo subido</title></head>
        <body style="font-family: sans-serif; text-align: center; margin-top: 50px;">
        <h1>Archivo subido con éxito</h1>
        <p>Nombre: <b>{filename}</b></p>
        <a href="/">Volver</a>
        </body>
    </html>
    """

    # Se devuelve 200 OK junto con una pagina de confirmacion
    respuesta = (
        "HTTP/1.1 200 OK\r\n"
        "Content-Type: text/html\r\n"
        f"Content-Length: {len(html.encode())}\r\n\r\n"
        + html
    )

    return respuesta.encode()


def start_server(archivo_descarga=None, modo_upload=False, usar_gzip=False):
    #Inicializacion del servidor
    ip_server = get_wifi_ip()
    puerto = 5000

    server_socket = socket(AF_INET, SOCK_STREAM)
    server_socket.bind((ip_server, puerto))
    server_socket.listen(1)

    url = f"http://{ip_server}:{puerto}"
    print(f"Servidor inicializado en: {url}")
    if modo_upload:
        print("Modo:", "UPLOAD")
    else: 
        print("Modo:", "DOWNLOAD")
    imprimir_qr_en_terminal(url)

    while True:
        client_socket, client_addr = server_socket.accept()
        print(f"Cliente conectado desde {client_addr}")
        buffer = b""
        while b"\r\n\r\n" not in buffer: # Lee hasta el fianl del header
            chunk = client_socket.recv(10240)
            if not chunk:
                break
            buffer += chunk # Acumula los bytes recibidos del encabezado

        if not buffer:
            client_socket.close()
            continue

        request_line = buffer.split(b"\r\n", 1)[0].decode(errors="ignore") # Se recibe GET /index.html HTTP/1.1
        parts = request_line.split(" ") # Queda asi: ["GET", "/index.html", "HTTP/1.1"]

        if len(parts) < 3:
            client_socket.close()
            continue

        method, path, version = parts

        # Cuando estamos en modo upload
        if modo_upload:
            if method == "GET":
                # Devuelve el html con el formulario
                html = generar_html_interfaz("upload")
                response = (
                    "HTTP/1.1 200 OK\r\n"
                    "Content-Type: text/html\r\n"
                    "Connection: close\r\n"
                    f"Content-Length: {len(html.encode())}\r\n\r\n"
                    + html
                ).encode()

            elif method == "POST":
                headers_section, body = buffer.split(b"\r\n\r\n", 1)
                # Obtiene Content-Length para saber cuantos bytes leer
                content_length = 0
                for line in headers_section.split(b"\r\n"):
                    if line.lower().startswith(b"content-length:"):
                        content_length = int(line.split(b":")[1].strip())
                        break
                # Sigue leyendo hasta completar el cuerpo POST
                while len(body) < content_length:
                    body += client_socket.recv(10240)

                for line in headers_section.split(b"\r\n"):
                    if b"boundary=" in line:
                        boundary = line.split(b"boundary=")[1].decode()
                        break

                response = manejar_carga(body, boundary, "archivos_servidor")

            else:
                # Si no es GET o POST, devuelve error.
                response = b"HTTP/1.1 405 Method Not Allowed\r\nConnection: close\r\n\r\n"
        # Si es modo download
        else:
            if method == "GET":
                if path == "/" or path == "/index.html":
                    # Devuelve el html con la interfaz para descargar archivos
                    html = generar_html_interfaz("download")
                   
                    response = (
                        "HTTP/1.1 200 OK\r\n"
                        "Content-Type: text/html\r\n"
                        "Connection: close\r\n"
                        f"Content-Length: {len(html.encode())}\r\n\r\n"
                        + html
                    ).encode()


                elif path == "/download":
                    # Chequea si el cliente acepta gzip
                    acepta_gzip = b"gzip" in buffer
                    inicio = time.time()
                    response = manejar_descarga(
                        archivo_descarga,
                        request_line,
                        usar_gzip,
                        acepta_gzip
                    )
                    fin = time.time()

                    if usar_gzip:
                        print(f"Tiempo de transferencia con compresion: {fin - inicio} s")
                    else:
                        print(f"Tiempo de transferencia sin compresion: {fin - inicio} s")
                else:
                    # Ruta no encontrada
                    response = (
                        "HTTP/1.1 404 Not Found\r\n"
                        "Content-Type: text/html\r\n"
                        "Connection: close\r\n\r\n"
                        "<h1>404 Not Found</h1>"
                    ).encode()

        client_socket.sendall(response)
        client_socket.close()
        print("Conexión cerrada. Esperando nuevo cliente...")

    

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Uso:")
        print("  python tp.py upload                    # Servidor para subir archivos")
        print("  python tp.py download archivo.txt      # Servidor para descargar un archivo")
        sys.exit(1)

    comando = sys.argv[1].lower()

    if comando == "upload":
        start_server(archivo_descarga=None, modo_upload=True)

    elif comando == "download" and len(sys.argv) > 2:
        archivo = sys.argv[2]
        usar_gzip = len(sys.argv) > 3 and sys.argv[3].lower() == "gzip"
        ruta_archivo = os.path.join("archivos_servidor", archivo)
        start_server(archivo_descarga=ruta_archivo, modo_upload=False, usar_gzip=usar_gzip)


    else:
        print("Comando no reconocido o archivo faltante")
        sys.exit(1)
