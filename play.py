import subprocess
from dbwork import check_media_dirs, batch_ingest_urls
from pathlib import Path


name = input("What film? ")
print(f"Hello, {name}!")



#extract_film ("FNS-055")
#gg = Path('.')
#ff = gg / 'media_dirs.txt'
h = check_media_dirs(Path('media_dirs.txt'))

MPV_DIRECTORY = "/usr/bin/mpv"
MPV_PLATFORM_OPTIONS = "--fs-screen=0"



#print(h)
t = [MPV_DIRECTORY, '--fs', MPV_PLATFORM_OPTIONS, '--loop-playlist']
for i, j, k in h:
  if j.upper() == name.upper():
    print(f"{i} {j}")
    t.append(i)
    
  
print()
#print(long_string)
subprocess.run(t)
# inn = input("Enter something: ")
 
# for x, y, z in h:
#     #print(f"x={x}, y={y}, z={z}")
#     if not z:
#         print (y)
        
#extract_film ("KAAD-085")

"""
    MIDA-503
  NACR-228
  PRED-160
  SAME-211
  SNOS-003
  SNOS-101
  SONE-760
  START-456
  START-464
  VENX-328   
  VENX-353
 """