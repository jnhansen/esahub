""" This module
"""
import sys
import binascii
import hashlib

PY2 = sys.version_info < (3, 0)


def md5(filename):
    """Compute the MD5 hashsum of a local file.

    Parameters
    ----------
    filename : str

    Returns
    -------
    str
        The md5 checksum in lower case.
    """
    hash_md5 = hashlib.md5()
    with open(filename, "rb") as f:
        for chunk in iter(lambda: f.read(4096), b""):
            hash_md5.update(chunk)
    return hash_md5.hexdigest().lower()


def etag(filename, chunksize, system='swift'):
    """Compute the SWIFT etag of a local file.

    If the file is smaller than the chunksize, this is equivalent to the md5
    hashsum. Otherwise, it is the md5 of the concatenated md5 sums of the
    segments.

    Parameters
    ----------
    filename : str
    chunksize : int
        S3 chunksize in MB
    system : str
        One of 'swift' and 'wos'.

    Returns
    -------
    str
        The SWIFT/WOS etag in lower case.
    """
    oneMB = 1024**2
    segment_md5s = []

    with open(filename, 'rb') as f:
        #
        # Read file in 1MB chunks to avoid memory issues
        #
        chunk_counter = 0
        md5 = hashlib.md5()
        for chunk in iter(lambda: f.read(oneMB), b""):
            md5.update(chunk)
            chunk_counter += 1
            if chunk_counter % chunksize == 0:
                #
                # Append the md5 of this chunk and reset.
                #
                segment_md5s.append(md5.hexdigest())
                md5 = hashlib.md5()
        #
        # If there is a 'remainder' left, append the md5.
        #
        if chunk_counter % chunksize != 0:
            segment_md5s.append(md5.hexdigest())

    if len(segment_md5s) == 1:
        return segment_md5s[0].lower()

    if system.lower() == 'swift':
        if PY2:
            return hashlib.md5(''.join(segment_md5s)).hexdigest().lower()
        else:
            return hashlib.md5(''.join(segment_md5s).encode('utf-8')) \
                          .hexdigest().lower()
    elif system.lower() == 'wos':
        if PY2:
            return hashlib.md5(binascii.unhexlify(
                                ''.join(segment_md5s).encode('utf-8'))) \
                .hexdigest().lower() + '-{}'.format(len(segment_md5s))
        else:
            return hashlib.md5(binascii.unhexlify(
                                ''.join(segment_md5s).encode('utf-8'))) \
                .hexdigest().lower() + '-{}'.format(len(segment_md5s))
