Create BBC Micro .ssd files with this script.

bbcfs.py --help
usage: bbcfs.py [-h] [-d FILE] [-t TITLE] [-o {load,run,exec}]
                INSPEC [INSPEC ...]

Build a BBC .ssd disk

positional arguments:
  INSPEC                A file to add to the ssd, where INSPEC is defined as
                        [DIR.]FILENAME[:LOADADDR[:EXECADDR]]

optional arguments:
  -h, --help            show this help message and exit
  -d FILE, --dest FILE  .ssd file to write to
  -t TITLE, --title TITLE
                        disk title
  -o {load,run,exec}, --opt {load,run,exec}
                        boot option



