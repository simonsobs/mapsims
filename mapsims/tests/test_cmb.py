import os

import numpy as np
import healpy as hp

from astropy.utils.data import get_pkg_data_filename

import pysm.units as u

from .. import cmb
from .. import so_utils

from astropy.tests.helper import assert_quantity_allclose


def test_load_sim():
    save_name = get_pkg_data_filename("data/test_map.fits")
    cmb_dir = os.path.dirname(save_name)
    nside = 32
    # Make an IQU sim
    imap = cmb.SOPrecomputedCMB(
        iteration_num=0,
        nside=nside,
        cmb_dir=cmb_dir,
        lensed=False,
        aberrated=False,
        input_reference_frequency=148 * u.GHz,
    ).get_emission(148 * u.GHz)
    imap_test = hp.read_map(save_name, field=(0, 1, 2)) << u.uK_RJ
    assert_quantity_allclose(imap, imap_test)
    assert imap.shape[0] == 3
    # Make an I only sim
    imap = cmb.SOPrecomputedCMB(
        iteration_num=0,
        nside=nside,
        has_polarization=False,
        cmb_dir=cmb_dir,
        lensed=False,
        aberrated=False,
        input_reference_frequency=148 * u.GHz,
    ).get_emission(148 * u.GHz)


def test_standalone_cmb():

    save_name = get_pkg_data_filename("data/test_map.fits")
    cmb_dir = os.path.dirname(save_name)
    nside = 32
    ch = so_utils.SOChannel("SA", 145)
    # Make an IQU sim
    imap = cmb.SOStandalonePrecomputedCMB(
        iteration_num=0,
        nside=nside,
        cmb_dir=cmb_dir,
        lensed=False,
        aberrated=False,
        input_units="uK_RJ",
        input_reference_frequency=ch.center_frequency,
    ).get_emission(ch.center_frequency, fwhm=1e-5 * u.arcmin)
    imap_test = hp.read_map(save_name, field=(0, 1, 2)) << u.uK_RJ
    assert_quantity_allclose(imap, imap_test)
