"""
Module to find out the qualified name of a class.
"""

import ast
import inspect
import os

__all__ = ['qualname']

_cache = {}
_sources = {}


class _Visitor(ast.NodeVisitor):
    def __init__(self, source):
        super(_Visitor, self).__init__()
        self.stack = []
        self.qualnames = {}
        self.source = [''] + source.splitlines()
        self.lineno = 0
        self.type = 'none'

    @property
    def line(self):
        return self.source[self.lineno]

    @property
    def next_line(self):
        if self.lineno >= len(self.source):
            return '<EOF>'
        return self.source[self.lineno + 1]

    @property
    def name(self):
        return self.stack[-1]

    def store_qualname(self):
        # Not sure why the a generator was made from the following line...
        # Assuming it's old code and removing the generator expression
        # Old Line: qn = ".".join(n for n in self.stack)
        qn = ".".join(self.stack)
        if self.name not in self.line or self.type not in self.line:
            if self.line.strip().startswith('@'):
                # Decorated Object, so bump the line number and re-check
                self.lineno += 1
                self.store_qualname()
                return
        self.qualnames[self.lineno] = qn

    def visit_FunctionDef(self, node):
        self.stack.append(node.name)
        self.type = 'def'
        self.lineno = node.lineno
        self.store_qualname()
        self.stack.append('<locals>')
        self.generic_visit(node)
        self.stack.pop()
        self.stack.pop()

    def visit_ClassDef(self, node):
        self.stack.append(node.name)
        self.type = 'class'
        self.lineno = node.lineno
        self.store_qualname()
        self.generic_visit(node)
        self.stack.pop()

def qualname(obj):
    """Find out the qualified name for a class or function."""

    def get_qualnames():
        """
        Re-parse the source file to figure out what the
        __qualname__ should be by analysing the abstract
        syntax tree. Use a cache to avoid doing this more
        than once for the same file.
        """
        qualnames = _cache.get(filename_normalized)
        if qualnames is not None:
            return qualnames
        with open(filename, 'r') as fp:
            source = fp.read()
        node = ast.parse(source, filename)
        visitor = _Visitor(source)
        visitor.visit(node)

        # Save source file so we can check for decorators in get_qualname()
        _sources[filename_normalized] = visitor.source
        _cache[filename_normalized] = visitor.qualnames
        return visitor.qualnames

    def get_qualname(lineno):
        """ If qualname doesn't exist at the line specified by inspect, check for decorators that may be causing a
        mismatch between the line number reported by inspect vs ast """
        try:
            return qualnames[lineno]
        except KeyError:
            line = _sources[filename_normalized][lineno]
            if line.strip().startswith('@'):
                # Decorated Object, so bump the line number and re-check
                return get_qualname(lineno + 1)
            return obj.__qualname__  # raises a sensible error

    # For Python 3.3+, this is straight-forward.
    if hasattr(obj, '__qualname__'):
        return obj.__qualname__

    # For older Python versions, things get complicated.
    # Obtain the filename and the line number where the
    # class/method/function is defined.
    try:
        filename = inspect.getsourcefile(obj)
    except TypeError:
        return obj.__qualname__  # raises a sensible error

    if inspect.isclass(obj):
        try:
            _, lineno = inspect.getsourcelines(obj)
        except (OSError, IOError):
            return obj.__qualname__  # raises a sensible error
    elif inspect.isfunction(obj) or inspect.ismethod(obj):
        if hasattr(obj, 'im_func'):
            # Extract function from unbound method (Python 2)
            obj = obj.im_func
        try:
            code = obj.__code__
        except AttributeError:
            code = obj.func_code
        lineno = code.co_firstlineno
    else:
        return obj.__qualname__  # raises a sensible error

    # Normalize filename so you don't get two different dict entries leading to the same path.
    # This happens sometimes with Python scripts running in a virtualenv
    # E.g. C:\Users\Username\Package\script.py and C:/Users/Username/Package\script.py
    filename_normalized = os.path.abspath(filename)
    qualnames = get_qualnames()
    return get_qualname(lineno)
