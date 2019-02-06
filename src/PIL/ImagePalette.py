#
# The Python Imaging Library.
# $Id$
#
# image palette object
#
# History:
# 1996-03-11 fl   Rewritten.
# 1997-01-03 fl   Up and running.
# 1997-08-23 fl   Added load hack
# 2001-04-16 fl   Fixed randint shadow bug in random()
#
# Copyright (c) 1997-2001 by Secret Labs AB
# Copyright (c) 1996-1997 by Fredrik Lundh
#
# See the README file for information on usage and redistribution.
#

import array
from copy import copy
from . import ImageColor, GimpPaletteFile, GimpGradientFile, PaletteFile


def split_abbreviations(s):
    """ Split a string into a tuple of its unique constituents,
        based on its internal capitalization -- to wit:

        >>> split_abbreviations('RGB')
        ('R', 'G', 'B')
        >>> split_abbreviations('CMYK')
        ('C', 'M', 'Y', 'K')
        >>> split_abbreviations('YCbCr')
        ('Y', 'Cb', 'Cr')
        >>> split_abbreviations('sRGB')
        ('R', 'G', 'B')
        >>> split_abbreviations('XYZZ')
        ('X', 'Y', 'Z')
        >>> split_abbreviations('I;16B')
        ('I',)

        If you still find this function inscrutable,
        have a look here: https://gist.github.com/4027079
    """
    abbreviations = []
    current_token = ''
    for char in s.split(';')[0]:
        if current_token == '':
            current_token += char
        elif char.islower():
            current_token += char
        else:
            if not current_token.islower():
                if current_token not in abbreviations:
                    abbreviations.append(current_token)
            current_token = ''
            current_token += char
    if current_token != '':
        if current_token not in abbreviations:
            abbreviations.append(current_token)
    return tuple(abbreviations)


class ImagePalette(object):
    """
    Color palette for palette mapped images

    :param mode: The mode to use for the Palette. See:
        :ref:`concept-modes`. Defaults to "RGB"
    :param channels: A tuple of channel labels to use for the Palette. If
        this is not given or None, it will be derived from the mode string,
        using the ``split_abbreviations(…)`` function. Defaults to None.
    :param palette: An optional palette. If given, it must be a bytearray,
        an array or a list of ints between 0-255 and of length ``size``
        times the number of colors in ``mode``. The list must be aligned
        by channel (All R values must be contiguous in the list before G
        and B values.) Defaults to 0 through 255 per channel.
    :param size: An optional palette size. If given, it cannot be equal to
        or greater than 256. Defaults to 0.
    """

    def __init__(self, mode="RGB", channels=None, palette=None, size=0):
        self.mode = mode
        self.channels = channels or split_abbreviations(self.mode)
        self.rawmode = None  # if set, palette contains raw data
        self.palette = palette or bytearray(range(256)) * len(self.channels)
        self.colors = {}
        self.dirty = None
        if ((size == 0 and len(self.channels) * 256 != len(self.palette)) or
                (size != 0 and size != len(self.palette))):
            raise ValueError("wrong palette size")

    def copy(self):
        new = ImagePalette()

        new.mode = self.mode
        new.channels = copy(self.channels)
        new.rawmode = self.rawmode
        if self.palette is not None:
            new.palette = self.palette[:]
        new.colors = self.colors.copy()
        new.dirty = self.dirty

        return new

    def getdata(self):
        """
        Get palette contents in format suitable for the low-level
        ``im.putpalette`` primitive.

        .. warning:: This method is experimental.
        """
        if self.rawmode:
            return self.rawmode, self.palette
        return self.mode + ";L", self.tobytes()

    def tobytes(self):
        """Convert palette to bytes.

        .. warning:: This method is experimental.
        """
        if self.rawmode:
            raise ValueError("palette contains raw palette data")
        if isinstance(self.palette, bytes):
            return self.palette
        arr = array.array("B", self.palette)
        if hasattr(arr, 'tobytes'):
            return arr.tobytes()
        return arr.tostring()

    # Declare tostring as an alias for tobytes
    tostring = tobytes

    def getcolor(self, color):
        """Given an rgb tuple, allocate palette entry.

        .. warning:: This method is experimental.
        """
        if self.rawmode:
            raise ValueError("palette contains raw palette data")
        if isinstance(color, tuple):
            try:
                return self.colors[color]
            except KeyError:
                # allocate new color slot
                if isinstance(self.palette, bytes):
                    self.palette = bytearray(self.palette)
                index = len(self.colors)
                if index >= 256:
                    raise ValueError("cannot allocate more than 256 colors")
                self.colors[color] = index
                self.palette[index] = color[0]
                self.palette[index+256] = color[1]
                self.palette[index+512] = color[2]
                self.dirty = 1
                return index
        else:
            raise ValueError("unknown color specifier: %r" % color)

    def save(self, fp):
        """Save palette to text file.

        .. warning:: This method is experimental.
        """
        if self.rawmode:
            raise ValueError("palette contains raw palette data")
        if isinstance(fp, str):
            fp = open(fp, "w")
        fp.write("# Palette\n")
        fp.write("# Mode: %s\n" % self.mode)
        for i in range(256):
            fp.write("%d" % i)
            for j in range(i*len(self.channels), (i+1) * len(self.channels)):
                try:
                    fp.write(" %d" % self.palette[j])
                except IndexError:
                    fp.write(" 0")
            fp.write("\n")
        fp.close()


# --------------------------------------------------------------------
# Internal

def raw(rawmode, data):
    palette = ImagePalette()
    palette.rawmode = rawmode
    palette.channels = split_abbreviations(rawmode)
    palette.palette = data
    palette.dirty = 1
    return palette


# --------------------------------------------------------------------
# Factories

def make_linear_lut(black, white):
    lut = []
    if black == 0:
        for i in range(256):
            lut.append(white*i//255)
    else:
        raise NotImplementedError  # FIXME
    return lut


def make_gamma_lut(exp):
    lut = []
    for i in range(256):
        lut.append(int(((i / 255.0) ** exp) * 255.0 + 0.5))
    return lut


def negative(mode="RGB"):
    palette = list(range(256))
    palette.reverse()
    return ImagePalette(mode, palette * len(split_abbreviations(mode)))


def random(mode="RGB"):
    from random import randint
    palette = []
    for i in range(256 * len(split_abbreviations(mode))):
        palette.append(randint(0, 255))
    return ImagePalette(mode, palette)


def sepia(white="#fff0c0"):
    r, g, b = ImageColor.getrgb(white)
    r = make_linear_lut(0, r)
    g = make_linear_lut(0, g)
    b = make_linear_lut(0, b)
    return ImagePalette("RGB", r + g + b)


def wedge(mode="RGB"):
    return ImagePalette(mode, list(range(256)) * len(split_abbreviations(mode)))


def load(filename):

    # FIXME: supports GIMP gradients only

    with open(filename, "rb") as fp:

        for paletteHandler in [
            GimpPaletteFile.GimpPaletteFile,
            GimpGradientFile.GimpGradientFile,
            PaletteFile.PaletteFile
        ]:
            try:
                fp.seek(0)
                lut = paletteHandler(fp).getpalette()
                if lut:
                    break
            except (SyntaxError, ValueError):
                # import traceback
                # traceback.print_exc()
                pass
        else:
            raise IOError("cannot load palette")

    return lut  # data, rawmode
