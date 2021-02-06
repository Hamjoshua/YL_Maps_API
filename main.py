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
TYPE_MARK = 'pm2rdl'
ZOOM_BORDER_DICT = {"sat": 14, "map": 22, "skl": 24}
ORG_MARK = 'comma'


class MainWindow(QMainWindow):
    def __init__(self, *args, **kwargs):
        super(MainWindow, self).__init__(*args, **kwargs)
        uic.loadUi('form.ui', self)

        self.geocoder_api_server = "http://geocode-maps.yandex.ru/1.x/"
        self.geocoder_api_key = "40d1649f-0493-4b70-98ba-98533de7710b"
        self.map_api_server = "http://static-maps.yandex.ru/1.x/"
        self.search_api_server = "https://search-maps.yandex.ru/v1/"
        self.search_api_key = "dda3ddba-c9ea-4ead-9010-f43fbc15c6e3"

        self.map_params = dict()
        self.map_org_params = dict()
        self.set_default_values()

        self.postalcode_checkBox.stateChanged.connect(self.show_postal_code)
        self.type_map_comboBox.activated[str].connect(self.update_map_type)
        self.search_btn.clicked.connect(self.press_search_button)
        self.del_btn.clicked.connect(self.press_del_button)

        self.del_btn.click()  # clear current parameters

        self.cur_postal_code = False

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

        if 'sat' in self.map_params['l']:
            # Load image
            im = Image.open(map_file)
            # Convert to palette mode and save
            im.convert('P').save(map_file)

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
                "Ошибка выполнения запроса:" + response.url +
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

    def get_search_result(self):
        response = requests.get(
            self.search_api_server,
            params=self.map_org_params
        )

        if not response:  # handling an error situation
            self.output_textBrowser.setText(
                "Ошибка выполнения запроса:" + response.url +
                f"Http статус: {response.status_code}(){response.reason}")
            return 0

        json_response = response.json()
        toponym = json_response['features']
        if toponym:
            if len(toponym) == 0:
                self.output_textBrowser.setText(
                    f"Ближайших организаций нет.")
                return 0
            return toponym[0]
        self.output_textBrowser.setText(
            f"Ближайших организаций нет.")
        return 0

    # UI

    def press_search_button(self):
        search_request = self.search_lineEdit.text()

        toponym = self.get_geocoder_result(search_request)
        # self.show_result_frame(True)

        self.cur_postal_code = False
        self.show_toponym_info(toponym)
        self.find_obj_on_map(toponym)

    def show_toponym_info(self, toponym, org=False):
        if not isinstance(toponym, int):
            if org:
                toponym_coordinates = ','.join([str(i) for i in toponym['geometry']['coordinates']])
                self.map_org_params['text'] = toponym_coordinates
                toponym_address = f"{toponym['properties']['CompanyMetaData']['name']}.\n" \
                                  f"Адрес: {toponym['properties']['CompanyMetaData']['address']}"
                self.cur_postal_code = ""
            else:
                toponym_address = toponym["metaDataProperty"]["GeocoderMetaData"]["text"]
                toponym_coordinates = toponym["Point"]["pos"]
                toponym_postal_code = toponym['metaDataProperty']['GeocoderMetaData']['Address']
                if self.postalcode_checkBox.isChecked():
                    self.cur_postal_code = "\nPost code: -"
                    if 'postal_code' in toponym_postal_code.keys():
                        self.cur_postal_code = f"\nPost code: {toponym_postal_code['postal_code']}"

            self.output_textBrowser.setText(
                toponym_address + "\nИмеет координаты: " +
                toponym_coordinates + (self.cur_postal_code if self.cur_postal_code else ''))

    def press_del_button(self):
        # self.show_result_frame(False)
        self.search_lineEdit.setText('')
        self.output_textBrowser.setText('')

        # self.show_result_frame(False)
        self.set_default_values()
        self.cur_postal_code = False

        self.update_map()

    def show_postal_code(self):
        if isinstance(self.cur_postal_code, str):
            if self.postalcode_checkBox.isChecked():
                self.output_textBrowser.setText(
                    self.output_textBrowser.toPlainText() + self.cur_postal_code)
            else:
                self.output_textBrowser.setText(
                    '\n'.join(self.output_textBrowser.toPlainText().split('\n')[:-1]))

    # Keyboard events.

    def keyPressEvent(self, event):
        print(self.map_params['ll'], 'Key:', event.key())
        # Zoom events.
        if event.key() == Qt.Key_PageDown:
            self.increase_map()
        elif event.key() == Qt.Key_PageUp:
            self.reduce_map()

        # Moving around the map.
        map_step = 55 / 2 ** int(self.map_params['z'])
        cur_lon, cur_lat = self.map_params['ll'].split(',')
        if event.key() in [Qt.Key_Up, Qt.Key_W]:
            self.set_map_center(float(cur_lon), float(cur_lat) + map_step)
        elif event.key() in [Qt.Key_Down, Qt.Key_S]:
            self.set_map_center(float(cur_lon), float(cur_lat) - map_step)
        elif event.key() in [Qt.Key_Right, Qt.Key_D]:
            self.set_map_center(float(cur_lon) + map_step, float(cur_lat))
        elif event.key() in [Qt.Key_Left, Qt.Key_A]:
            self.set_map_center(float(cur_lon) - map_step, float(cur_lat))
        elif event.key() == Qt.Key_Enter - 1:
            self.search_btn.click()
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

    # Mouse events.

    def mousePressEvent(self, event):
        event_map_pos = self.display_map_label.mapFromGlobal(QCursor.pos())
        if event.button() == 1:
            self.search_object_by_click(event_map_pos.x(), event_map_pos.y())
        elif event.button() == 2:
            self.search_org_by_click(event_map_pos.x(), event_map_pos.y())

    # Result frame actions

    def show_result_frame(self, is_show):
        self.results_label.setVisible(is_show)
        self.output_textBrowser.setVisible(is_show)
        self.postalcode_checkBox.setVisible(is_show)

    # Map actions

    def update_map(self):
        self.map_file = self.getImage()
        self.display_map_label.setPixmap(QPixmap(self.map_file))
        self.scale_value_label.setText(self.map_params['z'])

    def find_obj_on_map(self, toponym):
        self.map_params['ll'] = toponym['Point']['pos'].replace(' ', ',')
        self.map_params['pt'] = f"{self.map_params['ll']},{TYPE_MARK}"
        self.update_map()

    def set_default_values(self):
        self.map_params = {"ll": ",".join(DEFAULT_MAP_CENTER),
                           "l": self.type_map_comboBox.currentText(),
                           "size": ",".join(MAP_SIZE),
                           "z": DEFAULT_ZOOM}

        self.map_org_params = {"lang": "ru-RU",
                               "apikey": self.search_api_key,
                               "text": self.map_params['ll'],
                               "ll": self.map_params['ll'],
                               "results": 1,
                               "type": "biz",
                               "spn": "0.0000005, 0.0000005"}

    def calculate_lon_lat(self, x, y):
        x_coef = 0.55384615384521762582
        y_coef = 0.40000000000000002220
        zoom_coef = pow(2, int(self.map_params['z']) - 1)

        if x in range(0, 600) and y in range(0, 450):
            dx, dy = x - int(MAP_SIZE[0]) // 2, int(MAP_SIZE[1]) // 2 - y
            lon, lat = float(self.map_params['ll'].split(',')[0]) + (dx * x_coef / zoom_coef), \
                       float(self.map_params['ll'].split(',')[1]) + (dy * y_coef / zoom_coef)
            if lon > 180:
                lon -= 180
            elif lon < -180:
                lon += 180
            if lat > 90:
                lat -= 90
            elif lat < -90:
                lat += 90
            print(f"mpos {x}, {y}\n"
                  f"cntr {float(self.map_params['ll'].split(',')[0])} "
                  f"{float(self.map_params['ll'].split(',')[1])}\n"
                  f"crds {dx} {dy}\nhave {lon} {lat}")
            return lon, lat
        return None, None

    def search_object_by_click(self, x, y):
        lon, lat = self.calculate_lon_lat(x, y)
        if not (lon is None) and not (lat is None):
            self.map_params['pt'] = f"{lon},{lat},{TYPE_MARK}"
            toponym = self.get_geocoder_result(f'{lon},{lat}')

            self.show_toponym_info(toponym)

            self.update_map()

    def search_org_by_click(self, x, y):
        lon, lat = self.calculate_lon_lat(x, y)
        if not (lon is None) and not (lat is None):
            toponym = self.get_geocoder_result(f'{lon},{lat}')
            toponym_address = toponym["metaDataProperty"]["GeocoderMetaData"]["text"]
            self.map_org_params['text'] = toponym_address
            self.map_org_params['ll'] = f"{lon},{lat}"

            toponym = self.get_search_result()
            self.show_toponym_info(toponym, org=True)

            if self.map_org_params['text'] == toponym_address:
                self.map_org_params['text'] = self.map_org_params['ll']

            self.map_params['pt'] = f"{self.map_org_params['text']},{ORG_MARK}"
            self.map_params['ll'] = self.map_org_params['text']

            self.update_map()

    # Actions with map parameters.

    def update_map_type(self):
        self.map_params['l'] = self.type_map_comboBox.currentText()
        border = ZOOM_BORDER_DICT[self.map_params['l']]
        self.map_params['z'] = str((int(self.map_params['z'])) % border)
        self.update_map()

    def set_map_center(self, lon, lat):
        lon = (360 + lon) if lon < -180 else \
            (-360 + lon) if lon > 180 else lon
        if -180 <= lon <= 180 and -90 < lat < 90:
            self.map_params['ll'] = \
                ",".join([str(lon), str(lat)])
            self.update_map()

    def increase_map(self):
        border = ZOOM_BORDER_DICT[self.map_params['l']]
        self.map_params['z'] = \
            str((int(self.map_params['z']) + 1) % border)
        self.update_map()

    def reduce_map(self):
        border = ZOOM_BORDER_DICT[self.map_params['l']]
        self.map_params['z'] = \
            str((int(self.map_params['z']) - 1) % border)
        self.update_map()

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
