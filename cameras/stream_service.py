import io
import math
import time
import socket
import logging
from datetime import datetime
from PIL import Image, ImageDraw, ImageFont

logger = logging.getLogger(__name__)

class CameraStreamService:
    @staticmethod
    def probe_connection(host, port, protocol='RTSP', path='', timeout=2.5):
        """
        Probe network connection and protocol response.
        Returns a dict: { 'success': bool, 'latency_ms': float, 'message': str, 'details': str }
        """
        start_time = time.time()
        
        # 1. TCP Connection probe
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(timeout)
            sock.connect((host, int(port)))
        except socket.timeout:
            return {
                'success': False,
                'latency_ms': round((time.time() - start_time) * 1000, 2),
                'message': f"Délai d'attente dépassé (Timeout {timeout}s) vers {host}:{port}.",
                'details': "La caméra ne répond pas. Vérifiez son alimentation Wi-Fi et son adresse IP."
            }
        except ConnectionRefusedError:
            return {
                'success': False,
                'latency_ms': round((time.time() - start_time) * 1000, 2),
                'message': f"Connexion refusée par l'appareil sur le port {port}.",
                'details': "L'hôte est accessible mais le port spécifié est fermé ou le service vidéo n'est pas démarré."
            }
        except socket.gaierror:
            return {
                'success': False,
                'latency_ms': 0,
                'message': f"Nom d'hôte ou IP invalide : '{host}'.",
                'details': "Impossible de résoudre l'adresse réseau."
            }
        except Exception as e:
            return {
                'success': False,
                'latency_ms': round((time.time() - start_time) * 1000, 2),
                'message': f"Erreur de connexion socket : {str(e)}",
                'details': "Vérifiez la configuration réseau du serveur."
            }

        # 2. Protocol specific handshake
        latency_ms = round((time.time() - start_time) * 1000, 2)
        try:
            if protocol == 'RTSP':
                # Send standard RTSP OPTIONS request
                req = f"OPTIONS rtsp://{host}:{port}/ RTSP/1.0\r\nCSeq: 1\r\nUser-Agent: STAN-CAM-VIEW/1.0\r\n\r\n"
                sock.sendall(req.encode('utf-8'))
                response = sock.recv(1024).decode('utf-8', errors='ignore')
                sock.close()

                if "RTSP/1.0" in response:
                    status_line = response.splitlines()[0] if response.splitlines() else "RTSP OK"
                    return {
                        'success': True,
                        'latency_ms': latency_ms,
                        'message': f"Flux RTSP joignable ({status_line})",
                        'details': f"Temps de réponse : {latency_ms} ms. Serveur RTSP valide."
                    }
                else:
                    return {
                        'success': True,
                        'latency_ms': latency_ms,
                        'message': f"Port ouvert ({latency_ms} ms) mais réponse RTSP non standard.",
                        'details': f"Réponse reçue : {response[:120]}..."
                    }

            elif protocol in ['HTTP_MJPEG', 'HTTP_SNAPSHOT', 'ONVIF']:
                # Send standard HTTP HEAD request
                path_req = path if path else "/"
                req = f"HEAD {path_req} HTTP/1.1\r\nHost: {host}:{port}\r\nUser-Agent: STAN-CAM-VIEW/1.0\r\nConnection: close\r\n\r\n"
                sock.sendall(req.encode('utf-8'))
                response = sock.recv(1024).decode('utf-8', errors='ignore')
                sock.close()

                status_line = response.splitlines()[0] if response.splitlines() else "HTTP Réponse reçue"
                return {
                    'success': True,
                    'latency_ms': latency_ms,
                    'message': f"Service HTTP/ONVIF joignable ({status_line})",
                    'details': f"Temps de réponse : {latency_ms} ms."
                }
            else:
                sock.close()
                return {
                    'success': True,
                    'latency_ms': latency_ms,
                    'message': f"Port {port} ouvert et joignable.",
                    'details': f"Connexion TCP établie en {latency_ms} ms."
                }
        except Exception as e:
            try:
                sock.close()
            except Exception:
                pass
            return {
                'success': True,  # Port was open even if handshake was aborted
                'latency_ms': latency_ms,
                'message': f"Port ouvert ({latency_ms} ms), mais le protocole a émis une erreur : {str(e)}",
                'details': "La caméra est présente sur le réseau local."
            }

    @staticmethod
    def generate_surveillance_frame(camera, width=640, height=360):
        """
        Generates an authentic surveillance camera frame.
        Takes into account camera name, status, PTZ pan/tilt position, and bulb light state.
        """
        now = datetime.now()
        t = time.time()

        # Determine theme and colors
        if camera.status == 'OFFLINE':
            # Offline black/dark slate screen with scanlines
            img = Image.new('RGB', (width, height), color=(18, 20, 26))
            draw = ImageDraw.Draw(img)
            
            # Draw warning banner
            draw.rectangle([40, height // 2 - 45, width - 40, height // 2 + 45], fill=(35, 20, 20), outline=(220, 50, 50), width=2)
            draw.text((width // 2 - 80, height // 2 - 25), "FLUX HORS LIGNE", fill=(240, 70, 70))
            draw.text((width // 2 - 120, height // 2 + 5), f"Dernière vérification: {now.strftime('%H:%M:%S')}", fill=(180, 180, 180))

        elif camera.status == 'ERROR':
            # Error screen
            img = Image.new('RGB', (width, height), color=(30, 15, 15))
            draw = ImageDraw.Draw(img)
            draw.rectangle([30, height // 2 - 50, width - 30, height // 2 + 50], fill=(45, 20, 20), outline=(240, 100, 30), width=2)
            draw.text((width // 2 - 85, height // 2 - 30), "ERREUR DE FLUX VIDÉO", fill=(255, 120, 50))
            err_msg = camera.last_error_message or "Connexion interrompue"
            if len(err_msg) > 40:
                err_msg = err_msg[:37] + "..."
            draw.text((width // 2 - 110, height // 2), err_msg, fill=(220, 200, 200))
            draw.text((width // 2 - 95, height // 2 + 25), "Tentative de reconnexion auto...", fill=(160, 160, 160))

        else:
            # Active camera feed (Online / Testing)
            # Background depends on bulb light status
            is_light_on = getattr(camera, 'bulb_light_status', False)
            if is_light_on:
                # Daylight / warm illuminated interior
                bg_color = (42, 48, 55)
                grid_color = (60, 68, 78)
                ambient_text = "ÉCLAIRAGE AMPOULE: ACTIF [100%]"
            else:
                # Night vision / Infrared surveillance tint
                bg_color = (15, 26, 20)
                grid_color = (25, 42, 32)
                ambient_text = "VISION NOCTURNE IR: ACTIVE"

            img = Image.new('RGB', (width, height), color=bg_color)
            draw = ImageDraw.Draw(img)

            # PTZ Offset calculation for movement visualization
            pan_offset = int((camera.ptz_pan / 180.0) * (width * 0.35))
            tilt_offset = int((camera.ptz_tilt / 90.0) * (height * 0.25))

            # Draw perspective room grid / surveillance scenery
            vanishing_x = (width // 2) - pan_offset
            vanishing_y = (height // 2) - tilt_offset

            # Floor and walls perspective lines
            for i in range(-4, 5):
                draw.line([(vanishing_x + i * 90, height), (vanishing_x, vanishing_y)], fill=grid_color, width=1)
                draw.line([(0, height - (i + 4) * 20), (width, height - (i + 4) * 20)], fill=grid_color, width=1)

            # Simulated moving surveillance target (e.g. slight security motion / patrol)
            motion_x = vanishing_x + int(math.sin(t * 1.2 + camera.id) * 70)
            motion_y = vanishing_y + 40 + int(math.cos(t * 0.8) * 15)
            
            # Target bounding box (AI detection mockup)
            draw.rectangle([motion_x - 22, motion_y - 35, motion_x + 22, motion_y + 35], outline=(0, 255, 180) if is_light_on else (80, 240, 120), width=1)
            draw.text((motion_x - 20, motion_y - 50), "OBJET 98%", fill=(0, 255, 180) if is_light_on else (80, 240, 120))

            # PTZ Reticle / Crosshair in center
            cx, cy = width // 2, height // 2
            reticle_color = (255, 200, 0)
            draw.line([(cx - 15, cy), (cx + 15, cy)], fill=reticle_color, width=1)
            draw.line([(cx, cy - 15), (cx, cy + 15)], fill=reticle_color, width=1)
            draw.ellipse([cx - 8, cy - 8, cx + 8, cy + 8], outline=reticle_color, width=1)

            # PTZ coordinates badge
            ptz_info = f"PAN: {camera.ptz_pan:+04d}° | TILT: {camera.ptz_tilt:+03d}° | ZOOM: {camera.ptz_zoom}x"
            draw.rectangle([width - 230, height - 32, width - 10, height - 10], fill=(20, 25, 30))
            draw.text((width - 220, height - 28), ptz_info, fill=(230, 230, 230))

            # Ambient light badge
            draw.text((15, height - 30), ambient_text, fill=(240, 210, 80) if is_light_on else (100, 200, 140))

        # Common surveillance OSD (On-Screen Display) overlays
        # 1. Header Bar
        draw.rectangle([0, 0, width, 28], fill=(0, 0, 0, 160))
        
        # Camera identifier & location
        cam_title = f"CAM {camera.id:02d} - {camera.name.upper()}"
        if camera.location:
            cam_title += f" [{camera.location}]"
        draw.text((12, 7), cam_title, fill=(255, 255, 255))

        # Brand / Watermark
        draw.text((width - 150, 7), "STANTECH CAM VIEW", fill=(0, 190, 255))

        # Live blinking dot
        if camera.status == 'ONLINE':
            dot_color = (255, 40, 40) if int(t * 2) % 2 == 0 else (120, 0, 0)
            draw.ellipse([width - 175, 9, width - 165, 19], fill=dot_color)

        # 2. Timestamp & FPS info
        time_str = now.strftime('%Y-%m-%d  %H:%M:%S') + f".{int(now.microsecond / 1000):03d}"
        draw.rectangle([10, 34, 210, 52], fill=(0, 0, 0, 140))
        draw.text((15, 37), time_str, fill=(240, 240, 240))

        # Protocol & IP info
        proto_info = f"{camera.protocol} | {camera.host}:{camera.port}"
        draw.rectangle([width - 180, 34, width - 10, 52], fill=(0, 0, 0, 140))
        draw.text((width - 175, 37), proto_info, fill=(180, 210, 240))

        # Convert to JPEG bytes
        buf = io.BytesIO()
        img.save(buf, format='JPEG', quality=85)
        return buf.getvalue()
