# -*- coding: utf-8 -*-
"""
    pyxs.helpers
    ~~~~~~~~~~~~

    Implements various helpers.

    :copyright: (c) 2011 by Selectel, see AUTHORS for more details.
    :license: LGPL, see LICENSE for more details.
"""

from __future__ import unicode_literals

__all__ = ["validate_path", "validate_watch_path", "validate_perms",
           "error"]

import errno
import re
import os
import posixpath
import sys

if sys.version_info[0] is not 3:
    bytes, str = str, unicode

from .exceptions import InvalidPath, InvalidPermission, PyXSError


#: A reverse mapping for :data:`errno.errorcode`.
_codeerror = dict((message, code)
                  for code, message in errno.errorcode.items())


if os.name in ["posix"]:
    def osnmopen(path, *args):
        return os.open(path, *args)

    def osnmclose(fd):
        os.close(fd)

    def osnmwrite(fd, data):
        return os.write(fd, data)

    def osnmread(fd, length):
        return os.read(fd, length)

elif os.name in ["nt"]:
    from win32file import CreateFile, CloseHandle, ReadFile, WriteFile
    from win32file import FILE_GENERIC_READ, FILE_GENERIC_WRITE, OPEN_EXISTING, FILE_ATTRIBUTE_NORMAL

    def osnmopen(path, *args):
        # CreateFile(path, FILE_GENERIC_READ|FILE_GENERIC_WRITE, 0, NULL, OPEN_EXISTING, FILE_ATTRIBUTE_NORMAL, NULL);
        # http://docs.activestate.com/activepython/2.7/pywin32/win32file__CreateFile_meth.html
        # PyHANDLE = CreateFile(fileName, desiredAccess , shareMode , attributes , CreationDisposition , flagsAndAttributes , hTemplateFile )
        return CreateFile(path, FILE_GENERIC_READ|FILE_GENERIC_WRITE, 0, None, OPEN_EXISTING, FILE_ATTRIBUTE_NORMAL, None)

    def osnmclose(fd):
        # http://docs.activestate.com/activepython/2.7/pywin32/win32file__CloseHandle_meth.html
        # CloseHandle(handle)
        CloseHandle(fd)

    def osnmread(fd, length):
        # ReadFile(handle, buf, 1024, &bytes_read, NULL)
        # http://docs.activestate.com/activepython/2.7/pywin32/win32file__ReadFile_meth.html
        # (int, string) = ReadFile(hFile, buffer/bufSize , ol )
        (lread, data) = ReadFile(fd, length, None)
        return data

    def osnmwrite(fd, data):
        # WriteFile(handle, buf, sizeof(*msg) + msg->len, &bytes_written, NULL)
        # http://docs.activestate.com/activepython/2.7/pywin32/win32file__WriteFile_meth.html
        # int, int = WriteFile(hFile, data , ol )
        errCode, lwrite = WriteFile(fd, data, None)
        return lwrite

else:
    raise NotImplemented("No operating system fd interface defined")


def writeall(fd, data):
    """Writes a data string to the file descriptor.

    Calls :func:`os.write` repeatedly, unless all data is written.
    If an error occurs, it's impossible to tell how much data has
    been written.
    """
    length = len(data)
    while length:
        length -= osnmwrite(fd, data[-length:])


def readall(fd, length):
    """Reads a data string of a given length from the file descriptor.

    Calls :func:`os.read` repeatedly, unless all data is read. If an
    error occurs, it's impossible to tell how much data has been read.
    """
    chunks = []
    while length:
        chunks.append(osnmread(fd, length))
        length -= len(chunks[-1])
    else:
        return b"".join(chunks)


def dict_merge(*dicts):
    """Merges given dicts to a single one.

    >>> dict_merge()
    {}
    >>> dict_merge({"foo": "bar", "baz": "boo"})
    {'foo': 'bar', 'baz': 'boo'}
    """
    base = {}

    for d in dicts:
        base.update(d)
    else:
        return base


def error(smth):
    """Returns a :class:`~pyxs.exceptions.PyXSError` matching a given
    errno or error name.

    >>> error(22)
    pyxs.exceptions.PyXSError: (22, 'Invalid argument')
    >>> error("EINVAL")
    pyxs.exceptions.PyXSError: (22, 'Invalid argument')
    """
    if isinstance(smth, basestring):
        smth = _codeerror.get(smth, 0)

    return PyXSError(smth, os.strerror(smth))


def force_unicode(value):
    """Coerces a given value to :func:`unicode`.

    >>> force_bytes(b"foo")
    u'foo'
    >>> force_bytes(None)
    u'None'
    """
    if isinstance(value, bytes):
        return value.decode("utf-8")
    else:
        return str(value)


def validate_path(path):
    """Checks if a given path is valid, see
    :exc:`~pyxs.exceptions.InvalidPath` for details.

    :param str path: path to check.
    :raises pyxs.exceptions.InvalidPath: when path fails to validate.
    """
    # Paths longer than 3072 bytes are forbidden; clients specifying
    # relative paths should keep them to within 2048 bytes.
    max_len = 3072 if posixpath.abspath(path) else 2048

    if not (re.match("^[a-zA-Z0-9-/_@]+\x00?$", path) and
            len(path) <= max_len):
        raise InvalidPath(path)

    # A path is not allowed to have a trailing /, except for the
    # root path and shouldn't have dount //'s.
    if (len(path) > 1 and path[-1] == "/") or "//" in path:
        raise InvalidPath(path)

    return path


def validate_watch_path(wpath):
    """Checks if a given watch path is valid -- it should either be a
    valid path or a special, starting with ``@`` character.

    :param str wpath: watch path to check.
    :raises pyxs.exceptions.InvalidPath: when path fails to validate.
    """
    if (wpath.startswith("@") and not
        re.match("^@(?:introduceDomain|releaseDomain)\x00?$", wpath)):
        raise InvalidPath(wpath)
    else:
        validate_path(wpath)

    return wpath


def validate_perms(perms):
    """Checks if a given list of permision follows the format described
    in :meth:`~pyxs.client.Client.get_permissions`.

    :param list perms: permissions to check.
    :raises pyxs.exceptions.InvalidPermissions:
        when any of the permissions fail to validate.
    """
    for perm in perms:
        if not re.match("[wrbn]\d+", perm):
            raise InvalidPermission(perm)

    return perms
