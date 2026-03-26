import os
os.environ['KIVY_AUDIO'] = 'ffpyplayer'
import sys
import threading
import requests
import webbrowser
import random
import string
from tempfile import gettempdir

# Librerías de Kivy y KivyMD
from kivy.config import Config
Config.set('graphics', 'width', '360')
Config.set('graphics', 'height', '640')

from kivy.lang import Builder
from kivy.core.audio import SoundLoader
from kivy.clock import Clock
from kivy.properties import NumericProperty, BooleanProperty
from kivymd.app import MDApp
from kivymd.uix.list import OneLineIconListItem, IconLeftWidget
from kivymd.uix.dialog import MDDialog
from kivymd.uix.button import MDRaisedButton, MDIconButton

# Librerías de Google API
from googleapiclient.discovery import build

# Importaciones específicas para Android (SAF)
try:
    from android.storage import app_storage_path, primary_external_storage_path
    from android.permissions import request_permissions, Permission
    from jnius import autoclass, cast
    from android.runnable import run_on_ui_thread
    android_available = True
except ImportError:
    android_available = False

# --- CONFIGURACIÓN ---
API_KEY = "AIzaSyCHX_5qiBnvt9z0XlXaRViWXqf42Oibm9I"
ID_CARPETA_RAIZ = "1DtrXpdv1Xd2IFA8jw0B9bDjjpwR5kuu2"

KV = '''
MDBoxLayout:
    orientation: 'vertical'
    md_bg_color: 38/255, 66/255, 100/255, 1

    # --- HEADER ---
    MDBoxLayout:
        size_hint_y: None
        height: "120dp"
        orientation: 'vertical'
        padding: "10dp"
        spacing: "8dp"

        MDBoxLayout:
            adaptive_height: True
            Image:
                source: 'logo.png'
                size_hint: (None, None)
                size: ("180dp", "40dp")
            
            MDBoxLayout:
                spacing: "5dp"
                adaptive_width: True
                MDRaisedButton:
                    id: btn_drive
                    text: "Drive"
                    md_bg_color: 255/255, 102/255, 0/255, 1
                    on_release: app.switch_to_drive()
                MDRaisedButton:
                    id: btn_local
                    text: "Local"
                    md_bg_color: 26/255, 45/255, 71/255, 1
                    on_release: app.open_local()

        MDBoxLayout:
            spacing: "5dp"
            MDIconButton:
                id: back_btn
                icon: "arrow-left"
                theme_icon_color: "Custom"
                icon_color: 1, 1, 1, 1
                disabled: True
                on_release: app.load_folders()

            MDTextField:
                id: search_field
                hint_text: "Buscar..."
                mode: "round"
                fill_color_normal: 26/255, 45/255, 71/255, 1
                on_text: app.filter_list(self.text)

    # --- LISTA DE MÚSICA ---
    MDScrollView:
        id: scroll_area
        MDList:
            id: container_list

    # --- PANEL REPRODUCTOR (COMPACTO) ---
    MDCard:
        size_hint_y: None
        height: "180dp"
        md_bg_color: 26/255, 45/255, 71/255, 1
        radius: [20, 20, 0, 0]
        orientation: 'vertical'
        padding: "5dp"
        elevation: 4

        MDBoxLayout:
            orientation: 'vertical'
            padding: ["0dp", "10dp", "0dp", "5dp"]
            size_hint_y: None
            height: "50dp"
            
            MDRaisedButton:
                text: "↓ Descargar Audio"
                md_bg_color: 255/255, 102/255, 0/255, 1
                on_release: app.download_track()
                pos_hint: {"center_x": .5}

        # Tiempos y Barra
        MDBoxLayout:
            size_hint_y: None
            height: "40dp"
            padding: ["10dp", 0]
            MDLabel:
                id: time_curr
                text: "00:00"
                font_style: "Caption"
                theme_text_color: "Custom"
                text_color: 142/255, 177/255, 229/255, 1
                size_hint_x: None
                width: "45dp"
            MDSlider:
                id: progress_slider
                min: 0
                max: 100
                value: 0
                color: 142/255, 177/255, 229/255, 1
            MDLabel:
                id: time_total
                text: "00:00"
                font_style: "Caption"
                theme_text_color: "Custom"
                text_color: 142/255, 177/255, 229/255, 1
                size_hint_x: None
                width: "45dp"
                halign: "right"

        # Controles
        MDBoxLayout:
            adaptive_height: True
            pos_hint: {"center_x": .5}
            spacing: "15dp"
            padding: [0, 0, 0, "5dp"]

            MDIconButton:
                id: shuffle_btn
                icon: "shuffle"
                theme_icon_color: "Custom"
                icon_color: 1, 1, 1, 1
                on_release: app.toggle_shuffle()
            MDIconButton:
                icon: "skip-previous"
                on_release: app.prev_track()
            MDIconButton:
                id: play_btn
                icon: "play-circle"
                icon_size: "48dp"
                theme_icon_color: "Custom"
                icon_color: 142/255, 177/255, 229/255, 1
                on_release: app.toggle_play()
            MDIconButton:
                icon: "skip-next"
                on_release: app.next_track()
            MDIconButton:
                id: loop_btn
                icon: "repeat"
                theme_icon_color: "Custom"
                icon_color: 1, 1, 1, 1
                on_release: app.toggle_loop()

    # Botones Redes
    MDBoxLayout:
        spacing: "10dp"
        adaptive_size: True
        pos_hint: {"center_x": .5}
        MDIconButton:
            icon: "facebook"
            on_release: app.open_link("fb")
        MDIconButton:
            icon: "video"
            on_release: app.open_link("tk")
        MDIconButton:
            icon: "whatsapp"
            on_release: app.open_link("wsp")
        MDIconButton:
            icon: "currency-usd"
            on_release: app.open_yape()

    # Marquesina Inferior (Estado)
    MDBoxLayout:
        size_hint_y: None
        height: "30dp"
        md_bg_color: 15/255, 26/255, 43/255, 1
        padding: ["10dp", 0]
        MDLabel:
            id: marquee_label
            text: "Esperando conexión... "
            font_style: "Caption"
            theme_text_color: "Custom"
            text_color: 1, 1, 1, 1
'''

class CapoPlayApp(MDApp):
    angle = NumericProperty(0)
    loop = BooleanProperty(False)
    shuffle = BooleanProperty(False)
    manual_pos = NumericProperty(0)
    is_seeking = BooleanProperty(False)

    def build(self):
        self.title = "Capo Play | v.1.0 Beta"
        self.all_data = []
        self.songs_in_folder = []
        self.current_index = -1
        self.sound = None
        self.is_playing = False
        self.is_in_folder = False
        self.current_song_id = ""
        self.last_temp_file = ""
        self.shuffle_history = []

        # Para Android, usaremos un selector de archivos con SAF
        # En lugar de MDFileManager (que no funciona en Android 10+)
        if android_available:
            # Solicitar permiso de lectura de almacenamiento en tiempo de ejecución
            request_permissions([Permission.READ_EXTERNAL_STORAGE])
        else:
            # En PC, podemos seguir usando MDFileManager para pruebas
            from kivymd.uix.filemanager import MDFileManager
            self.file_manager = MDFileManager(exit_manager=self.exit_manager, select_path=self.select_path_local)

        threading.Thread(target=self.init_drive, daemon=True).start()
        Clock.schedule_interval(self.update_ui_elements, 0.05)

        root = Builder.load_string(KV)
        # Conectar eventos del slider
        slider = root.ids.progress_slider
        slider.bind(on_touch_down=self.on_slider_touch_down)
        slider.bind(on_touch_up=self.on_slider_touch_up)
        return root

    # --- Métodos para Android (SAF) ---
    def open_local(self):
        """Abrir selector de carpeta usando SAF (Android) o file_manager (PC)"""
        if android_available:
            self.select_folder_with_saf()
        else:
            # Usar MDFileManager en PC
            if hasattr(self, 'file_manager'):
                path = self.last_local_path if hasattr(self, 'last_local_path') and os.path.exists(self.last_local_path) else os.path.expanduser("~")
                self.file_manager.show(path)

    def select_folder_with_saf(self):
        """Usar el selector de carpetas de Android (Storage Access Framework)"""
        try:
            from android.storage import StorageAccessFramework
            saf = StorageAccessFramework()
            # Abrir selector de carpeta
            saf.start_activity_for_result(
                saf.ACTION_OPEN_DOCUMENT_TREE,
                on_result=self.on_folder_selected
            )
        except Exception as e:
            self.update_marquee(f"Error SAF: {str(e)[:20]}")

    def on_folder_selected(self, request_code, result_code, data):
        """Callback cuando el usuario selecciona una carpeta"""
        if result_code == -1 and data:  # RESULT_OK
            from android.storage import StorageAccessFramework
            saf = StorageAccessFramework()
            uri = data.getData()
            # Obtener persistencia del permiso
            saf.takePersistableUriPermission(uri)
            # Guardar URI para uso futuro
            self.current_folder_uri = uri
            # Obtener lista de archivos de audio
            self.load_songs_from_uri(uri)

    def load_songs_from_uri(self, uri):
        """Listar archivos de audio dentro de la carpeta URI"""
        from android.storage import StorageAccessFramework
        saf = StorageAccessFramework()
        # Obtener lista de documentos
        docs = saf.list_documents(uri)
        self.songs_in_folder = []
        for doc in docs:
            name = doc['displayName']
            if name.lower().endswith(('.mp3', '.wav', '.flac', '.ogg', '.m4a')):
                # Guardamos el URI completo para cada canción
                song_uri = doc['uri']
                self.songs_in_folder.append({
                    'id': song_uri,
                    'name': name,
                    'type': 'song'
                })
        self.is_in_folder = True
        Clock.schedule_once(lambda dt: self.set_back_btn(False))
        Clock.schedule_once(lambda dt: self.update_ui_list(self.songs_in_folder))
        self.update_marquee("Carpeta cargada.")

    # --- Métodos para PC (MDFileManager) ---
    def select_path_local(self, path):
        """Método usado en PC cuando se selecciona un archivo con MDFileManager"""
        self.exit_manager()
        formatos = ('.mp3', '.wav', '.flac', '.ogg', '.m4a')
        if path.lower().endswith(formatos):
            carpeta = os.path.dirname(path)
            self.last_local_path = carpeta
            try:
                archivos = os.listdir(carpeta)
                canciones = [f for f in archivos if f.lower().endswith(formatos)]
                self.songs_in_folder = [{'id': os.path.join(carpeta, s), 'name': s, 'type': 'song'} for s in sorted(canciones, key=lambda x: x.lower())]
                self.is_in_folder = True
                Clock.schedule_once(lambda dt: self.set_back_btn(False))
                self.update_ui_list(self.songs_in_folder)
                idx = next((i for i, s in enumerate(self.songs_in_folder) if s['id'] == path), 0)
                self.handle_selection(self.songs_in_folder[idx], idx, is_manual=True)
            except:
                self.update_marquee("Error al cargar carpeta local.")

    def exit_manager(self, *args):
        if hasattr(self, 'file_manager'):
            self.file_manager.close()

    # --- Métodos comunes (Drive, reproducción, etc.) ---
    def on_slider_touch_down(self, instance, touch):
        if instance.collide_point(*touch.pos):
            self.is_seeking = True

    def on_slider_touch_up(self, instance, touch):
        if instance.collide_point(*touch.pos) and self.is_seeking:
            self.do_seek(instance.value)
            self.is_seeking = False

    def on_pause(self): return True
    def on_resume(self): pass

    def set_active_source(self, source):
        if source == 'drive':
            self.root.ids.btn_drive.md_bg_color = (255/255, 102/255, 0/255, 1)
            self.root.ids.btn_local.md_bg_color = (26/255, 45/255, 71/255, 1)
        else:
            self.root.ids.btn_local.md_bg_color = (255/255, 102/255, 0/255, 1)
            self.root.ids.btn_drive.md_bg_color = (26/255, 45/255, 71/255, 1)

    def init_drive(self):
        try:
            self.drive_service = build('drive', 'v3', developerKey=API_KEY, static_discovery=False)
            self.load_folders()
        except:
            self.update_marquee("Error de conexión API")

    def load_folders(self):
        self.set_active_source('drive')
        self.is_in_folder = False
        Clock.schedule_once(lambda dt: self.set_back_btn(True))
        self.update_marquee("Cargando Carpetas... ")
        try:
            q = f"mimeType = 'application/vnd.google-apps.folder' and '{ID_CARPETA_RAIZ}' in parents and trashed = false"
            res = self.drive_service.files().list(q=q, fields="files(id, name)").execute()
            folders = res.get('files', [])
            self.all_data = [{'id': f['id'], 'name': f['name'], 'type': 'folder'} for f in sorted(folders, key=lambda x: x['name'].lower())]
            Clock.schedule_once(lambda dt: self.update_ui_list(self.all_data))
            self.update_marquee("Biblioteca lista. ")
        except:
            self.update_marquee("Error al leer carpetas. ")

    def load_songs(self, folder_id, folder_name):
        self.is_in_folder = True
        Clock.schedule_once(lambda dt: self.set_back_btn(False))
        self.update_marquee(f"Abriendo: {folder_name} ")
        try:
            q = f"'{folder_id}' in parents and trashed = false"
            res = self.drive_service.files().list(q=q, fields="files(id, name, mimeType)").execute()
            files = res.get('files', [])
            songs = [f for f in files if f['name'].lower().endswith(('.mp3', '.wav', '.flac', '.ogg', '.m4a'))]
            self.songs_in_folder = [{'id': s['id'], 'name': s['name'], 'type': 'song'} for s in sorted(songs, key=lambda x: x['name'].lower())]
            Clock.schedule_once(lambda dt: self.update_ui_list(self.songs_in_folder))
        except:
            pass

    def update_ui_list(self, data):
        self.root.ids.container_list.clear_widgets()
        for i, item in enumerate(data):
            is_playing_this = (item['id'] == self.current_song_id)
            text_col = (1, 0.4, 0, 1) if is_playing_this else (1, 1, 1, 1)
            icon = "folder" if item['type'] == 'folder' else ("volume-high" if is_playing_this else "music-note")
            list_item = OneLineIconListItem(text=item['name'], theme_text_color="Custom", text_color=text_col,
                                            on_release=lambda x, it=item, idx=i: self.handle_selection(it, idx, is_manual=True))
            icon_w = IconLeftWidget(icon=icon, theme_icon_color="Custom", icon_color=text_col)
            list_item.add_widget(icon_w)
            list_item.song_id, list_item.song_type, list_item.icon_w = item['id'], item['type'], icon_w
            self.root.ids.container_list.add_widget(list_item)

    def refresh_list_colors(self, dt=None):
        if not self.is_in_folder:
            return
        playing_widget = None
        for item in self.root.ids.container_list.children:
            if hasattr(item, 'song_id') and item.song_type != 'folder':
                is_playing_this = (item.song_id == self.current_song_id)
                col = (1, 0.4, 0, 1) if is_playing_this else (1, 1, 1, 1)
                item.text_color = col
                item.icon_w.icon = "volume-high" if is_playing_this else "music-note"
                item.icon_w.icon_color = col
                if is_playing_this:
                    playing_widget = item
        if playing_widget:
            self.root.ids.scroll_area.scroll_to(playing_widget)

    def handle_selection(self, item, idx, is_manual=False):
        if item['type'] == 'folder':
            threading.Thread(target=self.load_songs, args=(item['id'], item['name']), daemon=True).start()
        else:
            self.current_index = idx
            self.current_song_id = item['id']
            self.update_marquee("Cargando audio... ")
            if is_manual:
                self.shuffle_history = []
            if self.is_in_folder:
                Clock.schedule_once(self.refresh_list_colors)
            if self.sound:
                self.sound.stop()
                self.sound = None
            self.manual_pos = 0
            # Si es un URI de Android (comienza con content://) o un archivo local, lo reproducimos directamente
            # Si es un ID de Drive, descargamos
            if isinstance(self.current_song_id, str) and (self.current_song_id.startswith('content://') or os.path.exists(self.current_song_id)):
                Clock.schedule_once(lambda dt: self.play_audio(self.current_song_id))
            else:
                threading.Thread(target=self.download_and_play, args=(self.current_song_id,), daemon=True).start()

    def download_and_play(self, file_id):
        if os.path.exists(file_id):
            if self.current_song_id == file_id:
                Clock.schedule_once(lambda dt: self.play_audio(file_id))
            return
        try:
            if self.last_temp_file and os.path.exists(self.last_temp_file):
                try:
                    os.remove(self.last_temp_file)
                except:
                    pass
            random_str = ''.join(random.choices(string.ascii_lowercase + string.digits, k=5))
            temp_path = os.path.join(gettempdir(), f"capo_{random_str}.mp3")
            self.last_temp_file = temp_path
            url = f"https://drive.google.com/uc?export=download&id={file_id}"
            res = requests.get(url, timeout=30)
            with open(temp_path, "wb") as f:
                f.write(res.content)
            if self.current_song_id == file_id:
                Clock.schedule_once(lambda dt: self.play_audio(temp_path))
        except:
            self.update_marquee("Error de descarga. ")

    def play_audio(self, path_or_uri):
        # En Android, SoundLoader puede cargar desde un URI content://
        self.sound = SoundLoader.load(path_or_uri)
        if self.sound:
            self.sound.loop = self.loop
            self.sound.play()
            self.is_playing = True
            self.root.ids.play_btn.icon = "pause-circle"
            Clock.schedule_once(self.set_max_slider, 0.5)
            self.update_marquee("Reproduciendo ahora... ")
        else:
            self.update_marquee("Formato no soportado.")

    def set_max_slider(self, dt):
        if self.sound:
            self.root.ids.progress_slider.max = self.sound.length
            self.root.ids.time_total.text = "-" + self.format_time(self.sound.length)

    def update_ui_elements(self, dt):
        if self.is_playing and self.sound:
            if not self.is_seeking:
                self.manual_pos += dt
                self.root.ids.progress_slider.value = self.manual_pos
                self.root.ids.time_curr.text = self.format_time(self.manual_pos)
                self.root.ids.time_total.text = "-" + self.format_time(self.sound.length - self.manual_pos)

            if self.manual_pos >= self.sound.length - 0.2:
                if self.loop:
                    self.manual_pos = 0
                    self.sound.seek(0)
                else:
                    self.next_track()

        txt = self.root.ids.marquee_label.text
        if len(txt) > 2:
            self.root.ids.marquee_label.text = txt[1:] + txt[0]

    def do_seek(self, value):
        if self.sound:
            self.manual_pos = value
            self.sound.seek(value)
            self.root.ids.time_curr.text = self.format_time(self.manual_pos)
            self.root.ids.time_total.text = "-" + self.format_time(self.sound.length - self.manual_pos)

    def format_time(self, seconds):
        m, s = divmod(int(max(0, seconds)), 60)
        return f"{m:02d}:{s:02d}"

    def toggle_play(self):
        if self.sound:
            if self.is_playing:
                self.sound.stop()
                self.root.ids.play_btn.icon = "play-circle"
            else:
                self.sound.play()
                self.sound.seek(self.manual_pos)
                self.root.ids.play_btn.icon = "pause-circle"
            self.is_playing = not self.is_playing

    def toggle_loop(self):
        self.loop = not self.loop
        if self.sound:
            self.sound.loop = self.loop
        self.root.ids.loop_btn.icon_color = (1, 0.4, 0, 1) if self.loop else (1, 1, 1, 1)

    def toggle_shuffle(self):
        self.shuffle = not self.shuffle
        self.root.ids.shuffle_btn.icon_color = (1, 0.4, 0, 1) if self.shuffle else (1, 1, 1, 1)

    def download_track(self):
        if self.current_song_id:
            if isinstance(self.current_song_id, str) and (self.current_song_id.startswith('content://') or os.path.exists(self.current_song_id)):
                self.update_marquee("Ya es un archivo local.")
            else:
                webbrowser.open(f"https://drive.google.com/uc?export=download&id={self.current_song_id}")

    def switch_to_drive(self):
        self.set_active_source('drive')
        threading.Thread(target=self.load_folders, daemon=True).start()

    def next_track(self):
        if self.songs_in_folder and self.current_index != -1:
            if self.loop:
                self.handle_selection(self.songs_in_folder[self.current_index], self.current_index, is_manual=False)
                return
            if self.shuffle:
                self.shuffle_history.append(self.current_index)
                possible = [i for i in range(len(self.songs_in_folder)) if i != self.current_index]
                idx = random.choice(possible) if possible else self.current_index
            else:
                idx = (self.current_index + 1) % len(self.songs_in_folder)
            self.handle_selection(self.songs_in_folder[idx], idx, is_manual=False)

    def prev_track(self):
        if self.songs_in_folder and self.current_index != -1:
            if self.loop:
                self.handle_selection(self.songs_in_folder[self.current_index], self.current_index, is_manual=False)
                return
            if self.shuffle and self.shuffle_history:
                idx = self.shuffle_history.pop()
            else:
                idx = (self.current_index - 1) % len(self.songs_in_folder)
            self.handle_selection(self.songs_in_folder[idx], idx, is_manual=False)

    def filter_list(self, query):
        data = self.songs_in_folder if self.is_in_folder else self.all_data
        filtered = [s for s in data if query.lower() in s['name'].lower()]
        self.update_ui_list(filtered)

    def open_link(self, type):
        links = {"fb": "https://www.facebook.com/jhoncapquequijusto",
                 "tk": "https://www.tiktok.com/@blakymixdj",
                 "wsp": "https://api.whatsapp.com/message/MP4MAAPWICFDG1"}
        webbrowser.open(links.get(type, ""))

    def open_yape(self):
        self.dialog = MDDialog(title="Yape", text="935 167 801",
                               buttons=[MDRaisedButton(text="OK", on_release=lambda x: self.dialog.dismiss())])
        self.dialog.open()

    def update_marquee(self, text):
        Clock.schedule_once(lambda dt: self._set_marquee_text(text))

    def _set_marquee_text(self, text):
        self.root.ids.marquee_label.text = text

    def set_back_btn(self, state):
        self.root.ids.back_btn.disabled = state

if __name__ == "__main__":
    CapoPlayApp().run()