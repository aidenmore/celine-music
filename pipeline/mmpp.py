"""
mmpp.py - Programmatic builder for LMMS 1.2.x project files (.mmpp).

Timeline model: 192 ticks per 4/4 bar (48 ticks per beat, 24 per 16th).
"""
from __future__ import annotations

import os
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from typing import Optional

TICKS_PER_BAR = 192
TICKS_PER_BEAT = 48
TICKS_PER_16TH = 24

# --- Reusable XML fragments lifted verbatim from LMMS 1.2.2 output -------------
ELVOL = ('<elvol lspd="0.1" ctlenvamt="0" lpdel="0" pdel="0" amt="0" hold="0.5" '
         'syncmode="0" userwavefile="" latt="0" sustain="0.5" lamt="0" lshp="0" '
         'lspd_denominator="4" lspd_numerator="4" x100="0" rel="0.1" dec="0.5" att="0"/>')
ELCUT = ('<elcut lspd="0.1" ctlenvamt="0" lpdel="0" pdel="0" amt="0" hold="0.5" '
         'syncmode="0" userwavefile="" latt="0" sustain="0.5" lamt="0" lshp="0" '
         'lspd_denominator="4" lspd_numerator="4" x100="0" rel="0.1" dec="0.5" att="0"/>')
ELRES = ('<elres lspd="0.1" ctlenvamt="0" lpdel="0" pdel="0" amt="0" hold="0.5" '
         'syncmode="0" userwavefile="" latt="0" sustain="0.5" lamt="0" lshp="0" '
         'lspd_denominator="4" lspd_numerator="4" x100="0" rel="0.1" dec="0.5" att="0"/>')
MIDIPORT = ('<midiport inputchannel="0" fixedinputvelocity="0" outputcontroller="0" '
            'outputchannel="1" fixedoutputvelocity="0" readable="0" fixedoutputnote="-1" '
            'outputprogram="1" writable="0" basevelocity="127" inputcontroller="0"/>')


@dataclass
class Note:
    """A note event. `key` is the MIDI note number, `pos` is in ticks."""
    key: int
    pos: int
    len: int = -1
    vol: int = 100
    pan: int = 0

    def to_xml(self) -> ET.Element:
        e = ET.Element("note", {
            "key": str(self.key),
            "vol": str(self.vol),
            "pos": str(self.pos),
            "pan": str(self.pan),
            "len": str(self.len),
        })
        return e


@dataclass
class Pattern:
    """A chunk of notes. `pos` is the start tick in the timeline."""
    notes: list[Note] = field(default_factory=list)
    pos: int = 0
    len: int = TICKS_PER_BAR
    name: str = "Default"
    steps: int = 16
    type: int = 0
    muted: int = 0

    def to_xml(self) -> ET.Element:
        p = ET.Element("pattern", {
            "type": str(self.type),
            "muted": str(self.muted),
            "steps": str(self.steps),
            "name": self.name,
            "pos": str(self.pos),
            "len": str(self.len),
        })
        for n in self.notes:
            p.append(n.to_xml())
        return p


@dataclass
class LadspaEffect:
    """A LADSPA plugin instance in an FX chain."""
    file: str
    plugin: str
    controls: dict[str, float] = field(default_factory=dict)
    wet: float = 1.0
    on: int = 1

    def to_xml(self) -> ET.Element:
        e = ET.Element("effect", {
            "on": str(self.on),
            "wet": str(self.wet),
            "autoquit_denominator": "1",
            "gate": "0",
            "name": "ladspaeffect",
            "autoquit_numerator": "1",
            "syncmode": "0",
            "autoquit": "2400",
        })
        ctrls = ET.SubElement(e, "ladspacontrols", {"ports": str(len(self.controls))})
        for k, v in self.controls.items():
            c = ET.SubElement(ctrls, f"port{k}")
            c.set("data", repr(float(v)))
        key = ET.SubElement(e, "key")
        a1 = ET.SubElement(key, "attribute", {"name": "file", "value": self.file})
        a2 = ET.SubElement(key, "attribute", {"name": "plugin", "value": self.plugin})
        return e


@dataclass
class Effect:
    """A native LMMS effect plugin in an FX chain."""
    name: str
    params: dict[str, str] = field(default_factory=dict)
    wet: float = 1.0
    on: int = 1

    def to_xml(self) -> ET.Element:
        e = ET.Element("effect", {
            "on": str(self.on),
            "wet": str(self.wet),
            "autoquit_denominator": "1",
            "gate": "0",
            "name": self.name,
            "autoquit_numerator": "1",
            "syncmode": "0",
            "autoquit": "2400",
        })
        for k, v in self.params.items():
            ET.SubElement(e, k, {"data": v})
        key = ET.SubElement(e, "key")
        return e


@dataclass
class InstrumentTrack:
    """A single LMMS instrument track with its instrument + patterns."""
    name: str
    instrument: str = ""                 # plugin name, e.g. "kicker"
    instrument_params: dict[str, str] = field(default_factory=dict)
    instrument_variant: Optional[str] = None   # child tag; defaults to instrument name
    instrument_element: Optional[ET.Element] = None  # full <instrument> subtree from a preset
    eldata_element: Optional[ET.Element] = None     # full <eldata> subtree from a preset
    patterns: list[Pattern] = field(default_factory=list)
    vol: int = 100
    pan: int = 0
    pitch: int = 0
    basenote: int = 57
    fxchain: list = field(default_factory=list)
    muted: int = 0
    solo: int = 0
    automation_track: Optional[str] = None

    def to_xml(self) -> ET.Element:
        t = ET.Element("track", {
            "type": "0", "muted": str(self.muted),
            "name": self.name, "solo": str(self.solo),
        })
        it = ET.SubElement(t, "instrumenttrack", {
            "pitch": str(self.pitch), "vol": str(self.vol), "fxch": "0",
            "pan": str(self.pan), "basenote": str(self.basenote),
            "usemasterpitch": "1", "pitchrange": "1",
        })
        if self.instrument_element is not None:
            it.append(self.instrument_element)
        else:
            inst = ET.SubElement(it, "instrument", {"name": self.instrument})
            variant = ET.SubElement(inst, self.instrument_variant or self.instrument)
            for k, v in self.instrument_params.items():
                variant.set(k, str(v))

        if self.eldata_element is not None:
            it.append(self.eldata_element)
        else:
            eld = ET.SubElement(it, "eldata", {
                "fwet": "0", "ftype": "0", "fres": "0.5", "fcut": "14000"})
            ET.SubElement(eld, "elvol", _elattrs(None))
            ET.SubElement(eld, "elcut", _elattrs(None))
            ET.SubElement(eld, "elres", _elattrs(None))

        ET.SubElement(it, "chordcreator", {
            "chordrange": "1", "chord": "0", "chord-enabled": "0"})
        ET.SubElement(it, "arpeggiator", {
            "arpdir": "0", "arpgate": "100", "arptime_denominator": "4", "syncmode": "0",
            "arp-enabled": "0", "arprange": "1", "arptime_numerator": "4",
            "arpmode": "0", "arp": "0", "arptime": "100"})
        ET.SubElement(it, "midiport", _midiport_attrs())

        chain = ET.SubElement(it, "fxchain", {
            "numofeffects": str(len(self.fxchain)), "enabled": "1"})
        for fx in self.fxchain:
            chain.append(fx if isinstance(fx, ET.Element) else fx.to_xml())

        for p in self.patterns:
            t.append(p.to_xml())
        return t


def _elattrs(points):
    base = dict(lspd="0.1", ctlenvamt="0", lpdel="0", pdel="0", amt="0", hold="0.5",
                syncmode="0", userwavefile="", latt="0", sustain="0.5", lamt="0",
                lshp="0", lspd_denominator="4", lspd_numerator="4", x100="0",
                rel="0.1", dec="0.5", att="0")
    return base


def _midiport_attrs():
    return dict(inputchannel="0", fixedinputvelocity="0", outputcontroller="0",
                outputchannel="1", fixedoutputvelocity="0", readable="0",
                fixedoutputnote="-1", outputprogram="1", writable="0",
                basevelocity="127", inputcontroller="0")


@dataclass
class Song:
    name: str = "Song"
    bpm: int = 128
    timesig_numerator: int = 4
    timesig_denominator: int = 4
    mastervol: int = 100
    masterpitch: int = 0
    tracks: list[InstrumentTrack] = field(default_factory=list)
    notes_html: str = ""
    master_fx: list = field(default_factory=list)

    def to_xml(self) -> ET.Element:
        root = ET.Element("lmms-project", {
            "type": "song", "version": "1.0",
            "creator": "LMMS", "creatorversion": "1.2.0",
        })
        ET.SubElement(root, "head", {
            "timesig_denominator": str(self.timesig_denominator),
            "bpm": str(self.bpm),
            "masterpitch": str(self.masterpitch),
            "mastervol": str(self.mastervol),
            "timesig_numerator": str(self.timesig_numerator),
        })
        song = ET.SubElement(root, "song")
        tc = ET.SubElement(song, "trackcontainer", {
            "visible": "1", "width": "635", "height": "278", "type": "song",
            "x": "15", "y": "1", "maximized": "0", "minimized": "0"})
        for tr in self.tracks:
            tc.append(tr.to_xml())

        mix = ET.SubElement(song, "fxmixer", {
            "visible": "0", "width": "0", "height": "0", "x": "5", "y": "310",
            "maximized": "0", "minimized": "0"})
        chan = ET.SubElement(mix, "fxchannel", {
            "num": "0", "muted": "0", "volume": "1", "name": "Master", "soloed": "0"})
        mchain = ET.SubElement(chan, "fxchain", {
            "numofeffects": str(len(self.master_fx)),
            "enabled": "1" if self.master_fx else "0"})
        for fx in self.master_fx:
            mchain.append(fx if isinstance(fx, ET.Element) else fx.to_xml())

        ET.SubElement(song, "ControllerRackView", {
            "visible": "0", "width": "400", "height": "300", "x": "880",
            "y": "310", "maximized": "0", "minimized": "0"})
        ET.SubElement(song, "pianoroll", {
            "visible": "0", "width": "640", "height": "480", "x": "199",
            "y": "91", "maximized": "0", "minimized": "0"})
        ET.SubElement(song, "automationeditor", {
            "visible": "0", "width": "640", "height": "400", "x": "350",
            "y": "127", "maximized": "0", "minimized": "0"})
        ET.SubElement(song, "projectnotes", {
            "visible": "1", "width": "382", "height": "200", "x": "712",
            "y": "79", "maximized": "0", "minimized": "0"})
        ET.SubElement(song, "timeline", {"lp0pos": "0", "lp1pos": "768", "lpstate": "1"})
        ET.SubElement(song, "controllers")
        return root


def write_song(song: Song, path: str) -> str:
    root = song.to_xml()
    tree = ET.ElementTree(root)
    ET.indent(tree, space="  ")
    body = ET.tostring(root, encoding="unicode")
    with open(path, "w", encoding="utf-8") as fh:
        fh.write('<?xml version="1.0"?>\n<!DOCTYPE lmms-project>\n')
        fh.write(body)
        fh.write("\n")
    return path
