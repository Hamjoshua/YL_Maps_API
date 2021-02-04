# This Python file uses the following encoding: utf-8
import os
import sys
from io import BytesIO

import requests
from PIL import Image
from PyQt5.QtGui import QPixmap, QCursor
from PyQt5.QtWidgets import QMainWindow, QApplication, QWidget, QLabel, QPushButton
from PyQt5.QtCore import Qt

from PyQt5 import uic

MAP_SIZE = ["650", "450"]
DEFAULT_MAP_CENTER = ["0", "0"]
DEFAULT_ZOOM = "1"
MAP_STEP = 5
TYPE_MARK = 'pm2rdl'


class MainWindow(QMainWindow):
    def __init__(self):
        super(MainWindow, self).__init__()
        uic.loadUi('form.ui', self)

        self.geocoder_api_server = "http://geocode-maps.yandex.ru/1.x/"
        self.geocoder_api_key = "40d1649f-0493-4b70-98ba-98533de7710b"
        self.map_api_server = "http://static-maps.yandex.ru/1.x/"
        self.search_api_server = "https://search-maps.yandex.ru/v1/"
        self.search_api_key = "dda3ddba-c9ea-4ead-9010-f43fbc15c6e3"

        self.map_params = dict()
        self.set_default_values()
        self.press_del_button()

        self.postalcode_checkBox.stateChanged.connect(self.is_show_postal_code)
        self.type_map_comboBox.activated[str].connect(self.update_map_type)
        self.search_btn.clicked.connect(self.press_search_button)
        self.del_btn.clicked.connect(self.press_del_button)

        self.show_postal_code = self.postalcode_checkBox.isChecked()

        self.map_file = self.getImage()
        self.initUI()

    def initUI(self):
        self.setWindowTitle('Отображение карты')
        self.update_map()

    def getImage(self):
        response = requests.get(self.map_api_server, params=self.map_params)

        if not response:
            print("Ошибка выполнения запроса:")
            print(response.url)
            print("Http статус:", response.status_code, "(", response.reason, ")")
            sys.exit(1)

        # Write the resulting image to a file.
        map_file = "map.png"
        with open(map_file, "wb") as file:
            file.write(response.content)
        return map_file

    # Search API actions

    def get_geocoder_result(self, toponym_to_find):
        response = requests.get(
            self.geocoder_api_server,
            params={"apikey": self.geocoder_api_key,
                    "geocode": toponym_to_find,
                    "format": "json"})

        if not response:  # handling an error situation
            self.output_textBrowser.setText(
                "Ошибка выполнения запроса:" + response.url+
                f"Http статус: {response.status_code}(){response.reason}")
            return 0

        json_response = response.json()
        toponym = json_response["response"]["GeoObjectCollection"]["featureMember"]

        if not len(toponym):
            self.output_textBrowser.setText(
                f"По запросу {toponym_to_find} ничего не найдено.")
            return 0

        toponym = toponym[0]["GeoObject"]
        return toponym

    # UI

    def press_search_button(self):
        search_request = self.search_lineEdit.text()

        toponym = self.get_geocoder_result(search_request)
        self.last_request = search_request
        if not toponym:
            return

        toponym_address = toponym["metaDataProperty"]["GeocoderMetaData"]["text"]
        toponym_coodrinates = toponym["Point"]["pos"]
        toponym_postal_code = ''
        if self.show_postal_code:
            toponym_postal_code = toponym['metaDataProperty'][
                'GeocoderMetaData']['Address']
            if 'postal_code' in toponym_postal_code.keys():
                toponym_postal_code = toponym_postal_code["postal_code"]
            else:
                toponym_postal_code = 'None'
            toponym_postal_code = f"\nPost code: {toponym_postal_code}"

        self.output_textBrowser.setText(
            toponym_address + "\nИмеет координаты:" +
            toponym_coodrinates + toponym_postal_code)
        self.find_obj_on_map(toponym)

    def press_del_button(self):
        self.search_lineEdit.setText('')
        self.output_textBrowser.setText('')
        self.set_default_values()
        self.update_map()

    def is_show_postal_code(self):
        self.show_postal_code = \
            self.postalcode_checkBox.isChecked()
        if self.last_request:
            self.press_search_button()

    # Keyboard events.

    def keyPressEvent(self, event):
        print(event.key(), Qt.Key_Enter)

        # Zoom events.
        if event.key() == Qt.Key_PageDown:
            self.increase_map()
        elif event.key() == Qt.Key_PageUp:
            self.reduce_map()

        # Moving around the map.
        cur_lon, cur_lat = self.map_params['ll'].split(',')
        if event.key() in [Qt.Key_Up, Qt.Key_W]:
            self.set_map_center(float(cur_lon), float(cur_lat) + MAP_STEP)
        elif event.key() in [Qt.Key_Down, Qt.Key_S]:
            self.set_map_center(float(cur_lon), float(cur_lat) - MAP_STEP)
        elif event.key() in [Qt.Key_Right, Qt.Key_D]:
            self.set_map_center(float(cur_lon) + MAP_STEP, float(cur_lat))
        elif event.key() in [Qt.Key_Left, Qt.Key_A]:
            self.set_map_center(float(cur_lon) - MAP_STEP, float(cur_lat))
        elif event.key() == Qt.Key_P:  # FOR TESTING
            response = requests.get(
                self.map_api_server,
                params=self.map_params)
            print(response.url)
        elif event.key() == Qt.Key_O:  # FOR TESTING
            response = requests.get(
                self.map_api_server,
                params=self.map_params)
            Image.open(BytesIO(
                response.content)).show()
        elif event.key() == Qt.Key_Enter - 1:
            self.search_btn.click()

    # Mouse events.

    def mousePressEvent(self, event):
        event_map_pos = self.display_map_label.mapFromGlobal(QCursor.pos())
        print(event_map_pos.x(), event_map_pos.y())
        print(event.button())

    # Map actions

    def update_map(self):
        self.map_file = self.getImage()
        self.display_map_label.setPixmap(QPixmap(self.map_file))
        self.scale_value_label.setText(self.map_params['z'])

    def find_obj_on_map(self, toponym):
        self.map_params['ll'] = toponym['Point']['pos'].replace(' ', ',')
        self.map_params['spn'] = ','.join(self.get_spn(toponym))
        self.map_params['pt'] = f"{self.map_params['ll']},{TYPE_MARK}"
        self.update_map()

    def set_default_values(self):
        self.map_params = {"ll": ",".join(DEFAULT_MAP_CENTER),
                           "l": self.type_map_comboBox.currentText(),
                           "size": ",".join(MAP_SIZE),
                           "z": DEFAULT_ZOOM}

    # Actions with map parameters.

    def update_map_type(self):
        self.map_params['l'] = \
            self.type_map_comboBox.currentText()
        self.update_map()

    def set_map_center(self, lon, lat):
        if -180 <= lon <= 180 and -90 <= lat <= 90:
            self.map_params['ll'] = \
                ",".join([str(lon), str(lat)])
            self.update_map()

    def set_spn(self, lon_delta, lat_delta):
        self.map_params['spn'] = \
            ",".join([str(lon_delta), str(lat_delta)])
        self.update_map()

    def increase_map(self):
        self.map_params['z'] = str((int(self.map_params['z']) + 1) % 18)
        self.update_map()

    def reduce_map(self):
        if int(self.map_params['z']):
            self.map_params['z'] = \
                str((int(self.map_params['z']) - 1) % 18)
            self.update_map()

    # Get params.

    def get_spn(self, toponym):
        lower_corner, upper_corner = [v.split() for v in toponym[
            "boundedBy"]["Envelope"].values()]
        lon_delta = float(upper_corner[0]) - float(lower_corner[0])
        lat_delta = float(upper_corner[1]) - float(lower_corner[1])
        return str(lon_delta), str(lat_delta)

    def get_map_step(self, toponym):
        pass

    # Close.

    def closeEvent(self, event):
        """При закрытии формы подчищаем за собой"""
        os.remove(self.map_file)


def except_hook(cls, exception, traceback):
    sys.__excepthook__(cls, exception, traceback)


if __name__ == "__main__":
    app = QApplication(sys.argv)
    widget = MainWindow()
    widget.show()
    sys.excepthook = except_hook
    sys.exit(app.exec_())
