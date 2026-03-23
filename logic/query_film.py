from dataclasses import dataclass, asdict, field
from dotenv import load_dotenv
import os
from pathlib import Path
import sqlite3
import subprocess
from dbwork import check_media_dirs, batch_ingest_urls
from pathlib import Path
import threading
import multiprocessing
from collections import defaultdict
from itertools import cycle
from typing import List, Tuple, Iterator



env_path = Path(__file__).parent.parent / "trust1.env"
load_dotenv(env_path, interpolate=True)

FDB = os.getenv("FILM_DB_PATH")
IP = os.getenv("FILM_IMAGES_PATH")
MPV = os.getenv("MPV_DIRECTORY")

def play_me_out_deleted(files):
    MPV_DIRECTORY = "/usr/bin/mpv"
    MPV_PLATFORM_OPTIONS = "--fs-screen=0"
    t = [MPV_DIRECTORY, '--fs', MPV_PLATFORM_OPTIONS, '--loop-playlist']
    cnt = 0
    # for i, j, k in self.film_path:
    #     if j.upper() == name.upper():
    #         print(f"{i} {j}")
    #         t.append(i)
    #         cnt += 1
    # for media_path in self.films_loc[name.upper()]:
    #     print(f"{media_path} {name.upper()}")
    #     t.append(media_path)
    #     cnt += 1
    for media_path in files:
        #print(f"{media_path}")
        t.append(media_path)
        cnt += 1
    
    if cnt > 0:
        subprocess.run(t)



def play_me_out(name, film_path):

    MPV_PLATFORM_OPTIONS = "--fs-screen=0"
    t = [MPV, '--fs', MPV_PLATFORM_OPTIONS, '--loop-playlist']
    cnt = 0
    for i, j, k in film_path:
        if j.upper() == name.upper():
            print(f"{i} {j}")
            t.append(i)
            cnt += 1
    if cnt > 0:
        subprocess.run(t)

class MainLogic:
    film_path = []
    films = {}
    films_loc = defaultdict(list)
    collector = None
    
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance    
    
    
    
    
    
    
    
    def __init__(self   , **kwargs):
        """Read a text file of directories and check every media file against the DB.
        Reads one directory path per line from input_file, scans each for video files, extracts the film code (stripping download-tag suffixes), and checks whether it exists in unified.db.
        Blank lines and lines starting with '#' are ignored. Directories that don't exist are skipped with a warning.
        Returns a sorted list of (media_path, film_code, status) tuples where status is 'exists' if the film is in the DB, or None if it's new."""
        if hasattr(self, '_initialized') and self._initialized:
            return

        self._initialized = True
        
        self.films_loc.clear()
        film_path1 = check_media_dirs(Path('media_dirs.txt'))
        for media_path, film,  exusts in film_path1:
            if not exusts:
                print(f"Warning: {media_path} has film code {film} which is not in the database.")
                input("Press Enter to continue...")
            else:
                self.films_loc[film].append(media_path)


        film_path2 = check_media_dirs(Path('new_dirs.txt'))
        for media_path, film,  exusts in film_path2:
            if not exusts:
                print(f"Warning: {media_path} has film code {film} which is not in the database.")
                input("Press Enter to continue...")
            else:
                self.films_loc[film].append(media_path)
                
        
        
        
        
        conn = sqlite3.connect(FDB)
        cursor = conn.cursor()
        cursor.execute("SELECT film_code FROM films")  
        result = cursor.fetchall()
        for film_code, in result:
            self.films[film_code] = Film(film_code)
        cursor.execute("DELETE FROM new_films") 
        conn.commit()
        conn.close()


        
    def addnew(self):
        film_path2 = check_media_dirs(Path('new_dirs.txt'))
        for media_path, film,  exusts in film_path2:
            if not exusts:
                print(f"Warning: {media_path} has film code {film} which is not in the database.")
                input("Press Enter to continue...")
            else:
                if media_path not in self.films_loc[film]:
                    self.films_loc[film].append(media_path)
        
        conn = sqlite3.connect(FDB)
        cursor = conn.cursor()
        cursor.execute("SELECT film FROM new_films")  
        result = cursor.fetchall()
        for film_code, in result:
            print (f"checking {film_code}")
            if film_code not in self.films:
                self.films[film_code] = Film(film_code)
                print (f"added {film_code}")
        cursor.execute("DELETE FROM new_films")  
        conn.commit()
        conn.close()
        


        
        
    def play_me_out_deleted3(self, name):
        MPV_DIRECTORY = "/usr/bin/mpv"
        MPV_PLATFORM_OPTIONS = "--fs-screen=0"
        t = [MPV_DIRECTORY, '--fs', MPV_PLATFORM_OPTIONS, '--loop-playlist']
        cnt = 0
        # for i, j, k in self.film_path:
        #     if j.upper() == name.upper():
        #         print(f"{i} {j}")
        #         t.append(i)
        #         cnt += 1
        for media_path in self.films_loc[name.upper()]:
            print(f"{media_path} {name.upper()}")
            t.append(media_path)
            cnt += 1
        if cnt > 0:
            subprocess.run(t)
            
    def play_me(self, film_name):
        """
        Play video files matching film name using MPV (non-blocking).

        Spawns separate process to avoid blocking GUI.

        Args:
            film_name: Film code to play

        Database Access: None (multiprocess subprocess)

        KivyMD Event: Called by play-outline icon on_release
        """
        process = multiprocessing.Process(target=play_me_out_deleted, args=[self.films_loc[film_name.upper()]])
        process.start()

    def collect_idols(self, idol_id):
            film_list = []
            conn = sqlite3.connect(FDB)
            cursor = conn.cursor()
            cursor.execute("SELECT film_code, idol_name FROM film_summary_with_idols WHERE idol_id = ?", (idol_id,))  
            
            result = cursor.fetchall()
            conn.close()
            # for film_code, in result:
            #     filmed =Film(film_code)
            #     if filmed.film_code:
            #         print(film_code)
            #         film_list.append(filmed)
            for film_code, idol_name in result:
                filmed = self.films.get(film_code)
                if filmed:
                    if filmed.film_code:
                        #print(film_code)
                        filmed.change_idol_order(idol_id, idol_name)
                        film_list.append(filmed)
            return film_list

    def collect_search(self, search_term):
            film_list = []
            conn = sqlite3.connect(FDB)
            cursor = conn.cursor()
            cursor.execute("SELECT film_code FROM film_summary WHERE description LIKE ?", (f"%{search_term}%",))  
            
            result = cursor.fetchall()
            conn.close()
            # for film_code, in result:
            #     filmed =Film(film_code)
            #     if filmed.film_code:
            #         print(film_code)
            #         film_list.append(filmed)
            for film_code, in result:
                filmed = self.films.get(film_code)
                if filmed:
                    if filmed.film_code:
                        #print(film_code)
                        #filmed.change_idol_order(idol_id, idol_name)
                        film_list.append(filmed)
            return film_list




    def collect_series(self, idol_id):
            film_list = []
            conn = sqlite3.connect(FDB)
            cursor = conn.cursor()
            cursor.execute("SELECT film_code FROM film_summary WHERE series_id = ?", (idol_id,))  
            
            result = cursor.fetchall()
            conn.close()
            # for film_code, in result:
            #     filmed =Film(film_code)
            #     if filmed.film_code:
            #         print(film_code)
            #         film_list.append(filmed)
            for film_code, in result:
                filmed = self.films.get(film_code)
                if filmed:
                    if filmed.film_code:
                        print(film_code)
                        film_list.append(filmed)
            return film_list
                    
@dataclass (frozen=True)
class Film:
    film_code: str
    idol_count: int = field(init=False, default=0)
    idols:  Iterator[Tuple[int, str]] = field(init=False)    #list[tuple[int,str]] = field(init=False, default_factory=list)
    description: str = field(init=False)
    series_name: str = field(init=False, default="No series")
    idol_name: str = field(init=False, default="")
    series_id: int = field(init=False, default=0)
    idol_id: int = field(init=False, default=0)
    image_path: str = field(init=False, default=None)
    
    def change_idol_ordera(self, idol_idx):
        pass
        # if self.idol_count > 1:
        #     idol_idy = self.idol_id
        #     idol_namey = self.idol_name
        #     for i in (1, 20):                
        #         if idol_idy == idol_idx:
        #             print(idol_idy, idol_namey, idol_idx)
        #             break
        #         idol_idy, idol_namey = next(self.idols)
        #     object.__setattr__(self, 'idol_id', idol_idy)
        #     object.__setattr__(self, 'idol_name', idol_namey)
    def change_idol_order(self, idol_idx, idol_namex):
            object.__setattr__(self, 'idol_id', idol_idx)
            object.__setattr__(self, 'idol_name', idol_namex)


    def __post_init__(self):
        conn = sqlite3.connect(FDB)
        cursor = conn.cursor()
        cursor.execute("SELECT description, series_id, series_name, idol_count FROM film_summary WHERE film_code = ?", (self.film_code,))  
        result = cursor.fetchone()
        if result:
            object.__setattr__(self, 'description', result[0])
            if result[1]:
                object.__setattr__(self, 'series_id', result[1])
                object.__setattr__(self, 'series_name', result[2])
            temp_list = None
            if result[3] > 0:
                cursor.execute("SELECT idol_id, idol_name FROM film_summary_with_idols WHERE film_code = ?", (self.film_code,))
                object.__setattr__(self, 'idol_count', result[3])   
                temp_list = cycle(cursor.fetchall())
                #object.__setattr__(self, 'idols', cycle(cursor.fetchall()))
            else:
                my_tuple = (0, '')
                my_list = [my_tuple]
                object.__setattr__(self, 'idol_count', 0)   
                temp_list = cycle(my_list)
            idol_ida, idol_namea = next(temp_list)
            object.__setattr__(self, 'idol_id', idol_ida)
            object.__setattr__(self, 'idol_name', idol_namea)
            object.__setattr__(self, 'idols', temp_list)
                
            image_path = f"{IP}/{self.film_code}.jpg"
            image = Path(image_path)
            if image.is_file():
                object.__setattr__(self, 'image_path', image_path)
        else:
            object.__setattr__(self, 'film_code', None)
        conn.close()
        
if __name__ == "__main__":
    #ff = Film(film_code="SSIS-816")
    ff = Film(film_code="ADN-412")
    # Print the instance
    if ff.film_code is not None:
        print(asdict(ff))
