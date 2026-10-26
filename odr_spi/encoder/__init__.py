"""Pure-Python DAB SPI encoder.

Replaces the python-dabmot / python-dabmsc / python-hybridspi stack used by the
original ODR-SPI-Generator script.  The MOT directory, datagroup and packet
layers are byte-compatible with python-dabmsc (see tests/test_encoder_compat.py);
the SPI binary (ETSI TS 102 371) layer follows the hand-rolled encoder of the
original script and extends it with descriptions, genres, links and programme
information (EPG).
"""
