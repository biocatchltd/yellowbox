# Configuration file for the Sphinx documentation builder.
#
# This file only contains a selection of the most common options. For a full
# list see the documentation:
# https://www.sphinx-doc.org/en/master/usage/configuration.html

# -- Path setup --------------------------------------------------------------

# If extensions (or modules to document with autodoc) are in another directory,
# add these directories to sys.path here. If the directory is relative to the
# documentation root, use os.path.abspath to make it absolute, like shown here.
#
# import os
# import sys
# sys.path.insert(0, os.path.abspath('.'))


# -- Project information -----------------------------------------------------
from enum import EnumMeta
from importlib import import_module
from inspect import getsourcelines, getsourcefile
from traceback import print_exc
import re

project = 'Yellowbox'
copyright = '2021, Biocatch'
author = 'Biocatch'

# -- General configuration ---------------------------------------------------

# Add any Sphinx extension module names here, as strings. They can be
# extensions coming with Sphinx (named 'sphinx.ext.*') or your custom
# ones.
extensions = [
    "sphinx.ext.intersphinx", 'sphinx.ext.linkcode'
]

intersphinx_mapping = {
    'python': ('https://docs.python.org/3/', None),
    'pika': ('https://pika.readthedocs.io/en/stable/', None),
    'sqlalchemy': ('https://docs.sqlalchemy.org/en/14/', None),
    'docker': ('https://docker-py.readthedocs.io/en/stable/', None),
    'kafka-python': ('https://kafka-python.readthedocs.io/en/master/', None),
    'hvac': ('https://hvac.readthedocs.io/en/stable/', None),
    'requests': ('https://requests.readthedocs.io/en/master/', None),
}

import yellowbox
import os
import ast

release = yellowbox.__version__ or 'master'


# Resolve function for the linkcode extension.
def linkcode_resolve(domain, info):
    def find_var_lines(parent_source, parent_start_lineno, var_name):
        class_body = ast.parse(''.join(parent_source)).body[0].body
        for node in class_body:
            if (isinstance(node, ast.Assign)
                and any(isinstance(target, ast.Name) and target.id == var_name for target in node.targets)) \
                    or (isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name)
                        and node.target.id == var_name):
                lineno = node.lineno
                end_lineno = node.end_lineno
                return parent_source[lineno:end_lineno + 1], lineno + parent_start_lineno - 1
        return parent_source, parent_start_lineno

    def find_source():
        obj = import_module('yellowbox.' + info['module'])
        item = None
        for part in info['fullname'].split('.'):
            try:
                new_obj = getattr(obj, part)
            except AttributeError:
                # sometimes we run into an attribute/thing that doesn't exist at import time, just get the last obj
                break
            if isinstance(new_obj, (str, int, float, bool, bytes, type(None))) or isinstance(type(new_obj), EnumMeta):
                # the object is a variable, we search for it's declaration manually
                item = part
                break
            obj = new_obj
        while hasattr(obj, 'fget'):  # for properties
            obj = obj.fget
        while hasattr(obj, 'func'):  # for cached properties
            obj = obj.func
        while hasattr(obj, '__func__'):  # for wrappers
            obj = obj.__func__
        while hasattr(obj, '__wrapped__'):  # for wrappers
            obj = obj.__wrapped__

        fn = getsourcefile(obj)
        fn = os.path.relpath(fn, start=os.path.dirname(yellowbox.__file__))
        source, lineno = getsourcelines(obj)
        if item:
            source, lineno = find_var_lines(source, lineno, item)
        return fn, lineno, lineno + len(source) - 1

    if domain != 'py' or not info['module']:
        return None
    try:
        fn, lineno, endno = find_source()
        filename = f'yellowbox/{fn}#L{lineno}-L{endno}'
    except Exception as e:
        print(f'error getting link code {info}')
        print_exc()
        raise
    return "https://github.com/biocatchltd/yellowbox/blob/%s/%s" % (release, filename)


# Add any paths that contain templates here, relative to this directory.
templates_path = ['_templates']

# List of patterns, relative to source directory, that match files and
# directories to ignore when looking for source files.
# This pattern also affects html_static_path and html_extra_path.
exclude_patterns = ['_build', 'Thumbs.db', '.DS_Store']

# -- Options for HTML output -------------------------------------------------

# The theme to use for HTML and HTML Help pages.  See the documentation for
# a list of builtin themes.
#
html_theme = 'sphinx_rtd_theme'
html_favicon = "_static/favicon.png"

html_theme_options = {
    'vcs_pageview_mode': 'edit'
}

# Add any paths that contain custom static files (such as style sheets) here,
# relative to this directory. They are copied after the builtin static files,
# so a file named "default.css" will overwrite the builtin "default.css".
html_static_path = ['_static']
