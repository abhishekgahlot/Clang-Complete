from ctypes import cdll, Structure, POINTER, c_char_p, c_void_p, c_uint, c_bool, c_ulong, c_int
from clang import CXUnsavedFile, CXCompletionChunkKind, CXCursorKind
from sys import platform as _platform
import os
import re
# It's not who I am underneath,
# but what I do that defines me.
class Batman():
  def __init__(self):
    self.sublime_view = {}

  # print properties
  @staticmethod
  def dump(obj):
   for attr in dir(obj):
       if hasattr( obj, attr ):
           print( "obj.%s = %s" % (attr, getattr(obj, attr)))

  # Somehow imitate sublime view
  @staticmethod
  def fake_view(view):
    return view


current_path = os.path.dirname(os.path.abspath(__file__))
if _platform == "win32":
  os.environ["PATH"] = "%s/lib" % current_path + os.pathsep + os.environ["PATH"]
  libcc = cdll.LoadLibrary("%s/lib/libcc.dll" % current_path)
else:
  libcc = cdll.LoadLibrary("%s/lib/libcc.so" % current_path)

class _cc_symbol(Structure):
  pass

class _cc_result(Structure):
  pass

class CCTrunk(Structure):
  _fields_ = [("_kind", c_int), ("_value", c_char_p)]

  @property
  def value(self):
    return self._value.decode('utf-8')

  @property
  def kind(self):
    return CXCompletionChunkKind(self._kind)


digst_regex = re.compile("^(.+?):(\d+):(\d+): (.+?):.*$")
class CXDiagnosticSet(Structure):
  _fields_ = [("_point", c_void_p)]

  def __del__(self):
    libcc_diagnostic_free(self)

  def __len__(self):
    return libcc_diagnostic_count(self)

  def __iter__(self):
    self.it = 0
    return self

  def __next__(self):
    return self.next()

  def next(self):
    if self.it >= self.length:
      raise StopIteration
    else:
      s = libcc_diagnostic(self, self.it).decode("utf-8")
      ret = digst_regex.match(s)
      if ret != None:
      	(filename, line, col, error_type) = ret.groups()
      else:
      	(filename, line, col, error_type) = ("", 0, 0, "fatal error")
      self.it += 1
      return self.it - 1, (filename, int(line), int(col), error_type, s)

  @property
  def length(self):
    return self.__len__()

  def __getitem__(self, key):
    if key >= self.length:
      raise IndexError
    return libcc_diagnostic(self, key)


class CXCompletionResult(Structure):
  _fields_ = [("CursorKind", c_int), ("CompletionString", c_void_p)]
  cache_info = None

  def __iter__(self):
    self.it = 0
    return self

  def next(self):
    if self.it >= self.length:
      raise StopIteration
    else:
      trunk = libcc_cs_trunk(self.CompletionString, self.it)
      self.it += 1
      return self.it - 1, trunk

  @property
  def name(self):
    return libcc_cs_entryname(self.CompletionString).decode('utf-8')

  @property
  def info(self):
    if self.cache_info == None:
      for _, v in self:
        self.cache_info += v.value.encode('utf-8')

    return self.cache_info

  @property
  def kind(self):
    return CXCursorKind(self.CursorKind)

  @property
  def length(self):
    return self.__len__()

  def __len__(self):
    return libcc_cs_count(self.CompletionString)

  def __getitem__(self, key):
    if key >= self.length:
      raise IndexError
    return libcc_cs_trunk(self.CompletionString, key)


class CCdef(Structure):
  _fields_ = [('_filename', c_char_p), ('line', c_uint), ('col', c_uint)]

  @property
  def filename(self):
    return self._filename.decode('utf-8')

  @property
  def has(self):
    return self.filename != ""

  @property
  def target(self):
  	if not self.has: return None
  	return "%s:%d:%d" % (self.filename, self.line, self.col)


class MatchResult(Structure):
  _fields_ = [("table", POINTER(POINTER(CXCompletionResult))), ("size", c_uint)]

  def __iter__(self):
    self.it = 0
    return self

  def __next__(self):
    return self.next()

  def next(self):
    if self.it >= self.length:
      raise StopIteration
    else:
      result = self.table[self.it][0]
      self.it += 1
      return self.it - 1, result.name, result

  @property
  def length(self):
    return self.__len__()

  def __len__(self):
    return self.size

  def __getitem__(self, key):
    if key >= self.length:
      raise IndexError
    return self.table[key][0]


libcc_symbol_new = libcc.py_symbol_new
libcc_symbol_new.restype = POINTER(_cc_symbol)
libcc_symbol_new.argtypes = [c_char_p, POINTER(c_char_p), c_uint, POINTER(CXUnsavedFile), c_uint]

libcc_symbol_free = libcc.py_symbol_free
libcc_symbol_free.argtypes = [POINTER(_cc_symbol)]

libcc_symbol_def = libcc.py_symbol_def
libcc_symbol_def.argtypes = [POINTER(_cc_symbol), c_char_p, c_uint, c_uint]
libcc_symbol_def.restype = CCdef

libcc_symbol_reparse = libcc.py_symbol_reparse
libcc_symbol_reparse.argtypes = [POINTER(_cc_symbol), POINTER(CXUnsavedFile), c_uint]

libcc_symbol_complete_at = libcc.py_symbol_complete_at
libcc_symbol_complete_at.restype = POINTER(_cc_result)
libcc_symbol_complete_at.argtypes = [POINTER(_cc_symbol), c_uint, c_uint, POINTER(CXUnsavedFile), c_uint]

libcc_result_free = libcc.py_result_free
libcc_result_free.argtypes = [POINTER(_cc_result)]

libcc_cs_entryname = libcc.py_cs_entryname
libcc_cs_entryname.restype = c_char_p
libcc_cs_entryname.argtypes = [c_void_p]

libcc_cs_count = libcc.py_cs_count
libcc_cs_count.restype = c_uint
libcc_cs_count.argtypes = [c_void_p]

libcc_cs_trunk = libcc.py_cs_trunk
libcc_cs_trunk.restype = CCTrunk
libcc_cs_trunk.argtypes = [c_void_p, c_uint]

libcc_result_match = libcc.py_result_match
libcc_result_match.restype = MatchResult
libcc_result_match.argtypes = [POINTER(_cc_result), c_char_p]

libcc_diagnostic_new = libcc.py_diagnostic_new
libcc_diagnostic_new.restype = CXDiagnosticSet
libcc_diagnostic_new.argtypes = [POINTER(_cc_symbol)]

libcc_diagnostic_free = libcc.py_diagnostic_free
libcc_diagnostic_free.argtypes = [CXDiagnosticSet]

libcc_diagnostic_count = libcc.py_diagnostic_num
libcc_diagnostic_count.restype = c_uint
libcc_diagnostic_count.argtypes = [CXDiagnosticSet]

libcc_diagnostic = libcc.py_diagnostic
libcc_diagnostic.restype = c_char_p
libcc_diagnostic.argtypes = [CXDiagnosticSet, c_uint]



class CCHelper(object):
  def to_string_list(self, str_list):
    result = (c_char_p * len(str_list))()
    result[:] = [x.encode("utf-8") for x in str_list]
    return result, len(str_list)

  def to_file_list(self, file_list):
    result = (CXUnsavedFile * len(file_list))()
    for i, (name, value) in enumerate(file_list):
      name = name.encode('utf-8')
      value = value.encode('utf-8')
      result[i].name = name
      result[i].contents = value
      result[i].length = len(value)
    return result, len(file_list)


class CCResult(object):
  def __init__(self, c_obj):
    self.c_obj = c_obj

  def __del__(self):
    libcc_result_free(self.c_obj)

  def match(self, prefix):
    prefix = prefix.encode("utf-8")
    return libcc_result_match(self.c_obj, prefix)


class CCSymbol(object):
  def __init__(self, filename, opt, unsaved_files = []):
    filename = filename.encode('utf-8')
    self.helper = CCHelper()
    opt, opt_len = self.helper.to_string_list(opt)
    unsaved_files, num = self.helper.to_file_list(unsaved_files)
    self.c_obj = libcc_symbol_new(filename, opt, opt_len, unsaved_files, num)

  def __del__(self):
    libcc_symbol_free(self.c_obj)


  def complete_at(self, line, col, unsaved_files = []):
    assert(line > 0)
    assert(col > 0)
    unsaved_files, num = self.helper.to_file_list(unsaved_files)
    c_result_obj = libcc_symbol_complete_at(self.c_obj, line, col, unsaved_files, num)
    return CCResult(c_result_obj)

  def reparse(self, unsaved_files=[]):
    unsaved_files, num = self.helper.to_file_list(unsaved_files)
    libcc_symbol_reparse(self.c_obj, unsaved_files, num)


  def diagnostic(self):
    return libcc_diagnostic_new(self.c_obj)

  def get_def(self, filename, line, col):
    filename = filename.encode('utf-8')
    return libcc_symbol_def(self.c_obj, filename, line, col)

__all__ = ["CCSymbol", "CCResult", "CXDiagnosticSet", "CXUnsavedFile", "CXCompletionChunkKind", "CXCursorKind"]

def main():
  opt = ['-xc++', '-isystem', '/Applications/Xcode.app/Contents/Developer/Toolchains/XcodeDefault.xctoolchain/usr/lib/clang/6.0/include', '-isystem', '/Applications/Xcode.app/Contents/Developer/Platforms/MacOSX.platform/Developer/SDKs/MacOSX10.10.sdk/usr/include/', '-isystem', '/Applications/Xcode.app/Contents/Developer/Platforms/MacOSX.platform/Developer/SDKs/MacOSX10.10.sdk/usr/include/c++/4.2.1', '-F/Applications/Xcode.app/Contents/Developer/Platforms/MacOSX.platform/Developer/SDKs/MacOSX10.10.sdk/System/Library/Frameworks/', '-isystem', '/Applications/Xcode.app/Contents/Developer/Toolchains/XcodeDefault.xctoolchain/usr/include/c++/v1', '-isystem', '/usr/local/opt/llvm/include', '-Wall']

  filename = "/Users/darky/Desktop/test.cpp"
  symbol = CCSymbol(filename, opt, [('/Users/darky/Desktop/test.cpp', '#i')])
  result = symbol.complete_at(1, 2)
  #print(Batman.dump(result))
  print(result,'batman')
  complete = result.match('i')
  ret = []
  for i, name, v in complete:
    print(i, name, v)

if __name__ == '__main__':
  main()


