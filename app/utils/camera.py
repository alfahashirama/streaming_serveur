import cv2
import logging
import os
from datetime import datetime

class Camera:
    _instance = None

    def __init__(self):
        if Camera._instance is not None:
            raise Exception("Cette classe est un singleton !")
        Camera._instance = self
        self.video = None
        self.recording = False
        self.out = None
        self.upload_folder = None
        logging.info("Camera instance created")

    @staticmethod
    def get_instance():
        if Camera._instance is None:
            Camera()
        return Camera._instance

    def start(self, upload_folder=None):
        if self.video is None:
            self.video = cv2.VideoCapture(0)
            if not self.video.isOpened():
                logging.error("Impossible d'ouvrir la webcam")
                raise Exception("Impossible d'ouvrir la webcam")
            self.upload_folder = upload_folder
            logging.info("Webcam démarrée")
        return self.video.isOpened()

    def start_recording(self):
        if self.video is None or not self.video.isOpened():
            return False
        if not self.recording and self.upload_folder:
            filename = f"recording_{datetime.now().strftime('%Y%m%d_%H%M%S')}.mp4"
            filepath = os.path.join(self.upload_folder, filename)
            fourcc = cv2.VideoWriter_fourcc(*'mp4v')
            fps = 20.0
            frame_size = (int(self.video.get(3)), int(self.video.get(4)))
            self.out = cv2.VideoWriter(filepath, fourcc, fps, frame_size)
            self.recording = True
            logging.info(f"Enregistrement démarré : {filepath}")
            return True
        return False

    def stop_recording(self):
        if self.recording and self.out is not None:
            self.out.release()
            self.recording = False
            self.out = None
            logging.info("Enregistrement arrêté")
        return True

    def stop(self):
        self.stop_recording()
        if self.video is not None:
            self.video.release()
            self.video = None
            logging.info("Webcam arrêtée")

    def gen_frames(self):
        while self.video is not None and self.video.isOpened():
            success, frame = self.video.read()
            if not success:
                logging.error("Erreur : impossible de lire le frame")
                break
            if self.recording and self.out is not None:
                self.out.write(frame)
            ret, buffer = cv2.imencode('.jpg', frame)
            if not ret:
                logging.error("Erreur : impossible d'encoder le frame")
                continue
            frame = buffer.tobytes()
            yield (b'--frame\r\n'
                   b'Content-Type: image/jpeg\r\n\r\n' + frame + b'\r\n')
        self.stop()