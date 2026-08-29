# -*- coding: utf-8 -*-
"""
Minimal, dependency-free safe XML reader/writer for TranslationBuilder.

Qt .ts translation files and Qt Designer .ui files are treated as
untrusted input (they may come from third-party plugins being scanned).
This module intentionally avoids xml.etree.ElementTree, xml.dom.* and
xml.sax altogether -- including the low-level building blocks such as
ParseError, TreeBuilder, parse, tostring, XMLParser and iterparse --
since those names are flagged by static analysis as XML-attack-prone
regardless of how they end up being used, and defusedxml itself has to
import them internally in order to wrap them.

Parsing is instead performed directly on top of xml.parsers.expat, the
low-level, event-driven parser that both the standard library's
ElementTree and defusedxml build on. Any DOCTYPE declaration is
rejected outright: since .ts and .ui files never legitimately contain
one, this alone eliminates the whole class of XML entity expansion /
external entity (XXE) attacks, which all require a DTD to declare the
offending ENTITY. External entity resolution is also explicitly
refused as defense in depth.
"""

import xml.parsers.expat


class XmlParseError(ValueError):
    """Raised when a file cannot be parsed."""


class UnsafeXmlError(XmlParseError):
    """Raised when a file contains a DOCTYPE/DTD declaration."""


# =========================================================
# TREE MODEL
# =========================================================

class Element:
    """A minimal stand-in for xml.etree.ElementTree.Element."""

    __slots__ = ("tag", "attrib", "text", "children")

    def __init__(self, tag, attrib=None):
        self.tag = tag
        self.attrib = dict(attrib) if attrib else {}
        self.text = None
        self.children = []

    def set(self, key, value):
        self.attrib[key] = value

    def get(self, key, default=None):
        return self.attrib.get(key, default)

    def find(self, tag):
        for child in self.children:
            if child.tag == tag:
                return child
        return None

    def findall(self, tag):
        return [child for child in self.children if child.tag == tag]

    def iter(self, tag=None):
        if tag is None or self.tag == tag:
            yield self
        for child in self.children:
            for node in child.iter(tag):
                yield node


def sub_element(parent, tag, attrib=None):
    child = Element(tag, attrib)
    parent.children.append(child)
    return child


# =========================================================
# PARSING
# =========================================================

def parse_bytes(data):
    """
    Parse XML bytes into an Element tree, rejecting any DOCTYPE/DTD.

    Raises XmlParseError (or the more specific UnsafeXmlError) on
    malformed XML or a disallowed construct.
    """

    root_holder = [None]
    stack = []

    parser = xml.parsers.expat.ParserCreate()
    parser.buffer_text = True

    def start_doctype(*_args, **_kwargs):
        raise UnsafeXmlError(
            "DOCTYPE/DTD declarations are not allowed in this file."
        )

    def external_entity_ref(*_args, **_kwargs):
        # Refuse to resolve any external entity, even if one somehow
        # slipped through without a DOCTYPE declaration.
        raise UnsafeXmlError(
            "External entity references are not allowed in this file."
        )

    def start_element(name, attrs):
        element = Element(name, attrs)
        if stack:
            stack[-1].children.append(element)
        else:
            root_holder[0] = element
        stack.append(element)

    def end_element(_name):
        stack.pop()

    def char_data(chunk):
        if not stack:
            return
        current = stack[-1]
        current.text = (current.text or "") + chunk

    parser.StartDoctypeDeclHandler = start_doctype
    parser.ExternalEntityRefHandler = external_entity_ref
    parser.StartElementHandler = start_element
    parser.EndElementHandler = end_element
    parser.CharacterDataHandler = char_data

    try:
        parser.Parse(data, True)
    except xml.parsers.expat.ExpatError as error:
        raise XmlParseError(str(error)) from error

    if root_holder[0] is None:
        raise XmlParseError("Empty or invalid XML document.")

    return root_holder[0]


def parse_file(path):
    with open(path, "rb") as xml_file:
        data = xml_file.read()
    return parse_bytes(data)


# =========================================================
# SERIALIZATION
# =========================================================

def _escape_text(value):
    return (
        value.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
    )


def _escape_attr(value):
    return _escape_text(value).replace('"', "&quot;")


def _write_element(element, buffer, indent=""):
    attrib_str = "".join(
        f' {key}="{_escape_attr(str(value))}"'
        for key, value in element.attrib.items()
    )

    if not element.children and not element.text:
        buffer.append(f"{indent}<{element.tag}{attrib_str}/>\n")
        return

    if not element.children:
        buffer.append(
            f"{indent}<{element.tag}{attrib_str}>"
            f"{_escape_text(element.text)}"
            f"</{element.tag}>\n"
        )
        return

    buffer.append(f"{indent}<{element.tag}{attrib_str}>\n")

    for child in element.children:
        _write_element(child, buffer, indent + "    ")

    buffer.append(f"{indent}</{element.tag}>\n")


def write_file(root, path):
    """Serialize an Element tree to path as UTF-8 XML."""

    buffer = ['<?xml version="1.0" encoding="utf-8"?>\n']
    _write_element(root, buffer)

    with open(path, "w", encoding="utf-8") as out_file:
        out_file.write("".join(buffer))
