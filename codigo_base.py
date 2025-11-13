from socket import *
import sys
import os
from urllib.parse import parse_qs, urlparse
import qrcode
import mimetypes
import gzip
import io
import time
#FUNCIONES AUXILIARES

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

    qr.print_ascii(invert=True)

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
    if not os.path.exists(archivo):
        respuesta = (
            "HTTP/1.1 404 Not Found\r\n"
            "Content-Type: text/html\r\n\r\n"
            "<html><body><h1>404 - Archivo no encontrado</h1></body></html>"
        )
        return respuesta.encode()
    
    tipo, _ = mimetypes.guess_type(archivo)
    if tipo is None:
        tipo = "application/octet-stream"
    tamaño = os.path.getsize(archivo)
    nombre_archivo = os.path.basename(archivo)

    with open(archivo, "rb") as f:
        contenido = f.read()

    if usar_gzip and acepta_gzip:
        buffer = io.BytesIO()
        with gzip.GzipFile(fileobj=buffer, mode="wb") as gz:
            gz.write(contenido)
        contenido = buffer.getvalue()
        content_encoding = "gzip"
        print(f"[GZIP] Archivo comprimido: {len(contenido)} bytes (original {os.path.getsize(archivo)} bytes)")
        ratio = os.path.getsize(archivo) / len(contenido)
        print(ratio)
    else:
        content_encoding = None

    headers = (
        f"HTTP/1.1 200 OK\r\n"
        f"Content-Type: {tipo}\r\n"
        f"Content-Length: {tamaño}\r\n"
        f"Content-Disposition: attachment; filename=\"{nombre_archivo}\"\r\n"
        f"\r\n"
    )

    tamaño = len(contenido)

    if content_encoding:
        headers += f"Content-Encoding: gzip\r\n"

    headers += "\r\n"
    # Devolver respuesta completa (headers + contenido)
    return headers.encode() + contenido

def manejar_carga(body, boundary, directorio_destino="."):
    """
    Procesa un POST con multipart/form-data, guarda el archivo y devuelve una página de confirmación.
    """
    filename, file_content = parsear_multipart(body, boundary)

    if not filename or not file_content:
        respuesta = (
            "HTTP/1.1 400 Bad Request\r\n"
            "Content-Type: text/html\r\n\r\n"
            "<html><body><h1>Error: archivo inválido o vacío</h1></body></html>"
        )
        return respuesta.encode()
    
    os.makedirs(directorio_destino, exist_ok=True)

    ruta_destino = os.path.join(directorio_destino, filename)
    with open(ruta_destino, "wb") as f:
        f.write(file_content)

    print(f"Archivo recibido y guardado en: {ruta_destino}")

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

    respuesta = (
        "HTTP/1.1 200 OK\r\n"
        "Content-Type: text/html\r\n"
        f"Content-Length: {len(html.encode())}\r\n\r\n"
        + html
    )

    return respuesta.encode()


def start_server(archivo_descarga=None, modo_upload=False, usar_gzip=False):

    """
    Inicia el servidor TCP.
    - Si se especifica archivo_descarga, se inicia en modo 'download'.
    - Si modo_upload=True, se inicia en modo 'upload'.
    """

    # 1. Obtener IP local y poner al servidor a escuchar en un puerto aleatorio

    ip_server = get_wifi_ip()
    puerto = 5000
    server_socket = socket(AF_INET, SOCK_STREAM)

    server_socket.bind((ip_server, puerto))
    server_socket.listen(1)

    # 2. Mostrar información del servidor y el código QR
    # COMPLETAR: imprimir URL y modo de operación (download/upload)

    url = f"http://{ip_server}:{puerto}"
    print(f"Servidor inicializado en: {url}")
    modo = ""
    if modo_upload:
        modo = "UPLOAD"
    else:
        modo = "DOWNLOAD"

    print(f"Modo: {modo}")

    imprimir_qr_en_terminal(url)
    # 3. Esperar conexiones y atender un cliente
    # COMPLETAR:
    # - aceptar la conexión (accept)
    while True:
        client_socket, client_addr = server_socket.accept()
        print(f"Cliente conectado desde {client_addr}")

        # - recibir los datos (recv)

        request_data = client_socket.recv(10240).decode(errors='ignore')
        print("Solicitud recibida:", request_data)

        # - decodificar la solicitud HTTP

        request_line = request_data.split('\r\n')[0]
        method, path, _ = request_line.split(' ')
        response = b""

        # - determinar método (GET/POST) y ruta (/ o /download)
        # - generar la respuesta correspondiente (HTML o archivo)
        if modo_upload:
            if method == "GET":
                html = generar_html_interfaz("upload")
                response = (
                    "HTTP/1.1 200 OK\r\n"
                    "Content-Type: text/html\r\n"
                    f"Content-Length: {len(html.encode())}\r\n\r\n"
                    + html
                ).encode()
            elif method == "POST":
                headers, body = request_data.split("\r\n\r\n", 1)
                content_type_line = [h for h in headers.split("\r\n") if "Content-Type" in h][0]
                boundary = content_type_line.split("boundary=")[1]
                body_bytes = body.encode()
                response = manejar_carga(body_bytes, boundary, "archivos_servidor")
            else:
                response = b"HTTP/1.1 405 Method Not Allowed\r\n\r\n"
        else:
            if method == "GET":
                if path == "/" or path == "/index.html":
                    html = generar_html_interfaz("download")
                    response = (
                        "HTTP/1.1 200 OK\r\n"
                        "Content-Type: text/html\r\n"
                        f"Content-Length: {len(html.encode())}\r\n\r\n"
                        + html
                    ).encode()
                elif path == "/download":
                    acepta_gzip = "Accept-Encoding: gzip" in request_data
                    inicio = time.time()
                    response = manejar_descarga(archivo_descarga, request_line, usar_gzip=usar_gzip, acepta_gzip=acepta_gzip)
                    fin = time.time()
                    print(f"Tiempo de transferencia {'con' if usar_gzip else 'sin'} compresión: {fin - inicio:.4f} s")
                else:
                    response = (
                        "HTTP/1.1 404 Not Found\r\n"
                        "Content-Type: text/html\r\n\r\n"
                        "<h1>404 Not Found</h1>"
                    ).encode()

        client_socket.sendall(response)
        client_socket.close()
        print("Conexión cerrada. Esperando nuevo cliente...")
    server_socket.close()

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
