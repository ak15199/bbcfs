import argparse
from exceptions import RunTimeError
from math import floor
import os.path


DEFAULT_DIR = "$"
BYTES_PER_SECTOR = 256
SECTORS_PER_TRACK = 10
TRACK_COUNT = 80
START_SECTOR = 2


class File(object):

    def __init__(self, spec, start_sector):
        self.spec = spec
        self.start_sector = start_sector

        try:
            with open(self.spec["file"], "rb") as f:
                self.content = f.read()

            self.valid = True
            self.length = len(self.content)
            self.sectors = int(floor(self.length / BYTES_PER_SECTOR) + 1)
        except Exception as e:
            self.valid = False
            print str(e)


class Sector(object):

    seq = 0

    def __init__(self, disk):
        self.written = 0
        self.disk = disk
        if Sector.seq > 0 and (Sector.seq % SECTORS_PER_TRACK) == 0:
            print
        print "%02d" % Sector.seq,
        Sector.nextsector()

    def write(self, num, data):
        self.disk.write(data[0:num])
        self.written += num
        if self.written > BYTES_PER_SECTOR:
            raise RuntimeError("Too many bytes in sector")

    def byte(self, byte):
        self.write(1, bytearray([byte]))

    def bitpairs(self, p3, p2, p1, p0):
        self.byte((((((p3 << 2) | p2) << 2) | p1) << 2) | p0)

    def word(self, word):  # 16 bits
        self.byte(word & 0xff)
        self.byte((word >> 8) & 0xff)

    def string(self, num, data, pad="\0"):
        chars = len(data)
        payload = data + (pad * (num-chars))

        self.write(num, bytearray(payload))

    def close(self):
        remaining = BYTES_PER_SECTOR - self.written
        self.write(remaining, bytearray([0]) * remaining)

    def __del__(self):
        if self.written != BYTES_PER_SECTOR:
            raise RuntimeError("Not enough bytes in sector")

    @classmethod
    def nextsector(klass):
        klass.seq += 1


class Surface(object):

    def __init__(self, disk, title, opt):
        self.title = title
        self.opt = opt
        try:
            self.disk = open(disk, "wb")
        except Exception as e:
            print str(e)
            exit(1)

    def _sector00(self, catalog):
        """ Sector 00
        &00 to &07 First eight bytes of the 13-byte disc title
        &08 to &0E First file name
        &0F Directory of first file name
        &10 to &1E Second file name
        &1F Directory of second file name . . . .
        . . and so on
        Repeated up to 31 files.
        """
        s = Sector(self.disk)

        s.string(8, self.title)

        for entry in catalog:
            s.string(7, entry.spec["name"], pad=" ")
            s.write(1, entry.spec["directory"])

        s.close()

    def _sector01(self, catalog):
        """ Sector 01
        &00 to &03 Last four bytes of the disc title
        &04 Sequence number
        &05 The number of catalogue entries multiplied by 8
        &06 (bit 0,1) Number of sectors on disc (2 high order bits of 10 bit int)
            (bit 4,5) !BOOT start-up option
        &07 Number of sectors on disc (8 low order bits of 10 bit number)
        &08 First file's load address, low order bits
        &09 First file's load address, middle order bits
        &OA First file's exec address, low order bits
        &0B First file's exec address, middle order bits
        &0C First file's length in bytes, low order bits
        &0D First file's length in bytes, middle order bits
        &0E (bit 0,1) First file's start sector, 2 high order bits of 10 bit int
        &0E (bit 2,3) First file's load address, high order bits
        &0E (bit 4,5) First file's length in bytes, high order bits
        &0E (bit 6,7) First file's exec address, high order bits
        &0F First file's start sector, eight low order bits of 10 bit number
        . . . and so on
        Repeated for up to 31 files.
        """
        s = Sector(self.disk)

        s.string(4, self.title[8:])
        s.byte(0)
        s.byte(len(catalog)*8)

        sector_count = TRACK_COUNT * SECTORS_PER_TRACK
        boot_opts = {None: 0, "load": 1, "run": 2, "exec": 3}

        s.bitpairs(0, boot_opts[self.opt], 0, sector_count >> 8)
        s.byte(sector_count & 0xff)
        for entry in catalog:
            s.word(entry.spec["load_addr"])
            s.word(entry.spec["exec_addr"])
            s.word(entry.length)
            s.bitpairs(entry.start_sector >> 8, entry.spec["load_addr"] >> 16,
                       entry.length >> 16, entry.spec["exec_addr"] >> 16)
            s.byte(entry.start_sector)

        s.close()

    def _sector(self, block):
        s = Sector(self.disk)

        s.write(len(block), block)
        s.close()

    def write_catalog(self, catalog):

        self._sector00(catalog)
        self._sector01(catalog)

    def write_files(self, catalog):
        sector = 2
        for f in catalog:
            if f.start_sector != sector:
                raise RunTimeError("Block out of sync")

            while len(f.content):
                sector += 1

                try:
                    self._sector(f.content[0:BYTES_PER_SECTOR])
                except IndexError:
                    self._sector(f.content[0:BYTES_PER_SECTOR])
                    break

                f.content = f.content[BYTES_PER_SECTOR:]

            print "[%s] " % f.spec["name"]


class FileSpec(argparse.Action):
    """
    INSPEC is in the format [DIR<.>]FILE[:LOAD[:EXEC]]
    where
    """
    def __init__(self, **kwargs):
        argparse.Action.__init__(self, **kwargs)

    def _extractHex(self, data, field):
        try:
            return int(data[field], 16)
        except IndexError:
            return 0

    def _decode(self, name):
        if len(name) > 1 and name[1] == ".":
            directory, text = name.split(".", 1)
        else:
            directory, text = DEFAULT_DIR, name

        args = text.split(":")
        try:
            filespec = args[0]
        except:
            exit("Invalid file spec")

        filename = os.path.basename(filespec)
        return {
            "directory": directory,
            "file": filespec,
            "name": filename,
            "load_addr": self._extractHex(args, 1),
            "exec_addr": self._extractHex(args, 2),
            }

    def __call__(self, parser, namespace, values, option_string=None):
        if isinstance(values, list):
            values = [self._decode(value) for value in values]
        else:
            values = self._decode(values)

        setattr(namespace, self.dest, values)


def main():
    parser = argparse.ArgumentParser(description="Build a BBC .ssd disk")

    parser.add_argument("files", nargs="+", metavar="INSPEC", action=FileSpec,
                        help="A file to add to the ssd, where INSPEC"
                        " is defined as [DIR.]FILENAME[:LOADADDR[:EXECADDR]]")
    parser.add_argument("-d", "--dest", default="out.ssd", metavar="FILE",
                        help=".ssd file to write to")
    parser.add_argument("-t", "--title", default="XX",
                        help="disk title")
    parser.add_argument("-o", "--opt", choices=("load", "run", "exec"),
                        default=None, help="boot option")

    args = parser.parse_args()

    start_sector = START_SECTOR
    catalog = []
    for file in args.files:
        f = File(file, start_sector)
        if f.valid:
            catalog.append(f)
            start_sector = start_sector + f.sectors

    if len(catalog) == 0:
        exit("No files to process")

    surface = Surface(args.dest, args.title, args.opt)

    surface.write_catalog(catalog)
    surface.write_files(catalog)


if __name__ == "__main__":
    main()
