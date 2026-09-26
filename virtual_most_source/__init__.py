"""MOST25 frames and Biphase Mark line coding, for the simulations' stimulus.

listener_gw/sim/make_stim.py builds its rings with this: complete 64-byte
MOST25 frames (frame_builder, config) turned into the Biphase Mark line
(bmc), with every constant from the MOST specifications (most_spec, which
cites them). Four modules of a larger desktop MOST source written earlier;
only what the stimulus needs came along.
"""
__version__ = "1.0.0"
