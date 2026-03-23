from kivymd.app import MDApp
from kivymd.uix.screen import MDScreen
# from kivymd.uix.widget import Widget
from kivymd.uix.boxlayout import MDBoxLayout
# from kivymd.uix.label import MDLabel
from kivymd.uix.recycleview import MDRecycleView 
# #from kivymd.uix.button import MDRectangleFlatButton
# from kivymd.uix.button import MDIconButton
from kivymd.uix.imagelist.imagelist import MDSmartTile
# from kivymd.uix.list.list import OneLineListItem, MDList
# #from kivymd.uix.toolbar import MDTopAppBar
# from kivymd.uix.scrollview import MDScrollView
from kivy.properties import StringProperty, NumericProperty, BooleanProperty
from kivy.properties import ObjectProperty, ListProperty
# from kivymd.uix.button import MDRaisedButton
# import itertools
# from icecream import ic
# from pathlib import Path
# from functools import partial
# from kivy.uix.recycleview.views import RecycleDataViewBehavior
from kivymd.uix.recyclegridlayout import MDRecycleGridLayout
from kivymd.app import MDApp
import icecream
from logic import Film, MainLogic
from logic.film_wrapper import codes_list_to_asdicts
from dataclasses import asdict
from dotenv import load_dotenv
import os
from pathlib import Path
from kivymd.uix.menu import MDDropdownMenu

env_path = Path(__file__).parent.parent / "trust1.env"
load_dotenv(env_path, interpolate=True)

FDB = os.getenv("FILM_DB_PATH")
IP = os.getenv("FILM_IMAGES_PATH")
BP = os.getenv("BOOKMARK_PATH")




#from mainS import play_me




class MyRV(MDRecycleView):
    
    #data_items = ListProperty([])
    #films = [Film(film_code="SSIS-816"), Film(film_code="SHKD-736"), Film(film_code="ADN-412"), Film(film_code="SHKD-736")]
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        """
        ,"GVH-528","MIKR-074","IPX-665", "PRED-059","FNS-134","MBDD-2148","WAAA-311","IPX-381","JUL-518"
        """
        films2 = ['PRED-765','PRED-839' , 'GVH-528', 'MIKR-074', 'IPX-665', 'GVH-528', 'ADN-412', 
                  'ADN-412', 'PRED-059',"GVH-528","MIKR-074","IPX-665", "PRED-059","FNS-134","MBDD-2148","WAAA-311","IPX-381","JUL-518"]

        self.data = codes_list_to_asdicts(films2)
        MDApp.get_running_app().collector = self
    
    def reset_films(self):
        MainLogic().addnew()
        #MainLogic()._initialized = False
    
    def collect_idols(self, idol_id):
        #h = MainLogic()
        uu = MainLogic().collect_idols(idol_id)
        self.data = []
        self.data = [asdict(film) for film in uu]

    def collect_search(self, idol_id):
        uu = MainLogic().collect_search(idol_id)
        print("searching for ", idol_id)
        self.data = []
        self.data = [asdict(film) for film in uu]



    def collect_series(self, idol_id):
        #h = MainLogic()
        uu = MainLogic().collect_series(idol_id)
        self.data = []
        self.data = [asdict(film) for film in uu]


class FilmTile (MDSmartTile):
    film_code = StringProperty()
    description = StringProperty()
    idols = ObjectProperty()
    idol_count = NumericProperty()
    series_name = StringProperty()
    series_id = NumericProperty()
    image_path = StringProperty()
    idol_id = NumericProperty()
    idol_name = StringProperty()
    def play_me(self):
        pass #play_me(self.film_code)
        
    # def on_kv_post(self, base_widget):
    #     self.change_idol()
    #self.ids.film_code_label.text = "self.film_code"
    
    def change_idol(self):
        idol_idx, idol_namex = next(self.idols)
        if idol_idx == self.idol_id:
            idol_idx, idol_namex = next(self.idols)
        self.idol_id = idol_idx
        self.idol_name = idol_namex        
        return self.idol_id
        

class MyScreen(MDRecycleGridLayout):
    pass

class MainScreemApp(MDApp):
    #main_logic = MainLogic()
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        
    def play_me(self, film_code):
        #self.main_logic = MainLogic()
        MainLogic().play_me(film_code)
        
        
    def load_bookmark(self, callr):
        menu = MDDropdownMenu( caller=callr, items=[])
        menu_items = [
            {'text': f.name, 'on_release': lambda x=f: self.load_bookmark_films(x, menu)} for f in Path(BP).iterdir() if f.is_file()]
        #MDDropdownMenu(caller=callr, items=menu_items).open()
        menu.items = menu_items
        menu.open()
         #for f in Path(BP).iterdir() if f.is_file()]
        #self.main_logic = MainLogic()
        #MainLogic().load_bookmark(bookmark_name)

        
    def save_bookmark(self, callr, film_code):
        menu = MDDropdownMenu( caller=callr, items=[])
        menu_items = [
            {'text': f.name, 'on_release': lambda x=f: self.save_bookmark_film(x, menu, film_code)} for f in Path(BP).iterdir() if f.is_file()]
        #MDDropdownMenu(caller=callr, items=menu_items).open()
        menu.items = menu_items
        menu.open()

    def save_bookmark_film(self, bookmark_path, menu, film_code):
        menu.dismiss()
        bookmark_path = Path(bookmark_path)
        with bookmark_path.open("a", encoding="utf-8") as fh:
            fh.write(f"{film_code}\n")



    def load_bookmark_films(self, bookmark_path, menu):
        menu.dismiss()
        bookmark_path = Path(bookmark_path)
        with bookmark_path.open("r", encoding="utf-8") as fh:
            codes = [line.strip() for line in fh if line.strip()]
        self.collector.data = []
        self.collector.data = codes_list_to_asdicts(codes)

if __name__ == "__main__":    
    app = MainScreemApp()
    app.run()