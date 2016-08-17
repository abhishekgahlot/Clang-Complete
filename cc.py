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

class WraperComplete(object):

  def __init__(self):
    self._dispatch_map = {
      CXCursorKind.FIELD_DECL: self._field,

      CXCursorKind.FUNCTION_TEMPLATE: self._function,
      CXCursorKind.CXX_METHOD: self._function,
      CXCursorKind.FUNCTION_DECL: self._function,
      CXCursorKind.DESTRUCTOR: self._function,

      CXCursorKind.NAMESPACE: self._namespace,
      CXCursorKind.MACRO_DEFINITION: self._macro,
      CXCursorKind.NOT_IMPLEMENTED: self._not_implemented,
      CXCursorKind.VAR_DECL: self._var,
      CXCursorKind.ENUM_CONSTANT_DECL: self._var,

      CXCursorKind.PARM_DECL: self._var,
      CXCursorKind.TYPEDEF_DECL: self._typdef,

      CXCursorKind.CONSTRUCTOR: lambda v:self._struct(v, "constructor"),
      CXCursorKind.UNION_DECL: lambda v:self._struct(v, "union"),
      CXCursorKind.CLASS_TEMPLATE: lambda v:self._struct(v, "classTemplate"),
      CXCursorKind.CLASS_DECL: lambda v:self._struct(v, "class"),
      CXCursorKind.STRUCT_DECL: self._struct,
    }


  def get_entry(self, v):
    if v.kind in self._dispatch_map:
      func = self._dispatch_map[v.kind]
      return func(v)
    return self._unknow(v)


  def _unknow(self, v):
    print("unknow kind: ", v.kind, v.name)
    trigger, contents = self._attach(v)
    return (trigger, contents)


  def _attach(self, v, begin_idx=0):
    decl = ""
    contents = ""
    holder_idx = 1
    for i in range(begin_idx, v.length):
      trunk = v[i]
      value = trunk.value
      delc_value = value
      kind = trunk.kind
      if kind == CXCompletionChunkKind.Placeholder:
        value = "${%d:%s}" % (holder_idx, value)
        holder_idx += 1
      elif kind == CXCompletionChunkKind.Informative:
        value = ""
      elif kind== CXCompletionChunkKind.ResultType:
        value = ""
        delc_value = ""
      contents += value
      decl += delc_value
    return decl, contents


  def _typdef(self, v):
    _v, contents = self._attach(v)
    trigger = "%s\t%s" % (_v, "Typedef")
    return (trigger, contents)


  def _function(self, v):
    return_type = v[0].value
    func_decl, contents = self._attach(v, 1)
    trigger = "%s\t%s" % (func_decl, return_type)
    return (trigger, contents)


  def _not_implemented(self, v):
    _v, contents = self._attach(v)
    trigger = "%s\t%s" % (_v, "KeyWord")
    return (trigger, contents)

  def _namespace(self, v):
    macro, contents = self._attach(v)
    trigger = "%s\t%s" % (macro, "namespace")
    return (trigger, contents)

  def _macro(self, v):
    macro, contents = self._attach(v)
    trigger = "%s\t%s" % (macro, "Macro")
    return (trigger, contents)

  def _var(self, v):
    var = v.name
    var_type = v[0].value
    trigger = "%s\t%s" % (var, var_type)
    return (trigger, var)

  def _field(self, v):
    return self._var(v)


  def _struct(self, v, t="struct"):
    trigger = "%s\t%s" % (v.name, t)
    return (trigger, v.name)

class Complete(object):
  symbol_map = {}
  wraper = WraperComplete()
  member_regex = re.compile(r"(([a-zA-Z_]+[0-9_]*)|([\)\]])+)((\.)|(->)|(::))$")

  @staticmethod
  def clean():
    print('clean')
    Complete.symbol_map = {}

  @staticmethod
  def get_settings():
    print('settings')
    return sublime.load_settings("cc.sublime-settings")

  @staticmethod
  def get_opt(view):
    print('get_opt')
    settings = Complete.get_settings()
    additional_lang_opts = settings.get("additional_language_options", {})
    language = get_language(view)
    project_settings = view.settings()
    include_opts = settings.get("include_options", []) + project_settings.get("cc_include_options", [])

    window = sublime.active_window()
    variables = window.extract_variables()
    include_opts = sublime.expand_variables(include_opts, variables)

    opt = [drivers[language]]
    if language in additional_lang_opts:
      for v in additional_lang_opts[language]:
        opt.append(v)

    for v in include_opts:
      opt.append(v)
    print("clang options: ", opt)
    return opt

  @staticmethod
  def is_inhibit():
    print('is_inhibit')
    settings = Complete.get_settings()
    return settings.has("inhibit") and settings.get("inhibit") or False

  @staticmethod
  def get_symbol(file_name, view, unsaved_files=[]):
    print('get_symbol')
    self = Complete
    if file_name in self.symbol_map:
      return self.symbol_map[file_name]

    else:
      opt = self.get_opt(view)
      sym = CCSymbol(file_name, opt, unsaved_files)
      self.symbol_map[file_name] = sym
      return sym

  @staticmethod
  def del_symbol(file_name):
    print('del_symbol')
    self = Complete
    if file_name in self.symbol_map:
      del self.symbol_map[file_name]

  # checks if last characters
  @staticmethod
  def is_member_completion(view):
    print('is_member_completion', view.sel()[0])
    # fast check
    point = view.sel()[0].begin() - 1
    if point < 0:
      return False

    cur_char = view.substr(point)
    print(cur_char, 'cur_char')
    # print "cur_char:", cur_char
    if cur_char and cur_char != "." and cur_char != ">" and cur_char != ":" and cur_char != "[":
      return False

    caret= view.sel()[0].begin()
    line = view.substr(sublime.Region(view.line(caret).a, caret))
    return Complete.member_regex.search(line) != None

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
  opt = ['-xc++']
  filename = "/Users/darky/Desktop/test.cpp"
  symbol = CCSymbol(filename, opt)
  result = symbol.complete_at(3, 1)
  #print(Batman.dump(result))
  print(result,'batman')
  complete = result.match('p')
  ret = []
  for i, name, v in complete:
    print(i, name, Complete.wraper.get_entry(v))

if __name__ == '__main__':
  main()


