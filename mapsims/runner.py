import os.path
import importlib
import numpy as np

import pysm
import toml

import healpy as hp

from so_pysm_models import get_so_models

from . import so_utils
from . import Channel

PYSM_COMPONENTS = {
    comp[0]: comp for comp in ["synchrotron", "dust", "freefree", "cmb", "ame"]
}
default_output_filename_template = "simonsobs_{telescope}{band:03d}_nside{nside}.fits"


def command_line_script(args=None):

    import argparse

    parser = argparse.ArgumentParser(
        description="Execute map based simulations for Simons Observatory"
    )
    parser.add_argument("config", type=str, help="Configuration file", nargs="+")
    res = parser.parse_args(args)
    simulator = from_config(res.config)
    simulator.execute(write_outputs=True)


def import_class_from_string(class_string):
    module_name, class_name = class_string.rsplit(".", 1)
    return getattr(importlib.import_module(module_name), class_name)


def from_config(config_file):
    if isinstance(config_file, str):
        config_file = [config_file]

    config = toml.load(config_file)

    pysm_components_string = None

    components = {}
    for component_type in ["pysm_components", "other_components"]:
        components[component_type] = {}
        if component_type in config:
            component_type_config = config[component_type]
            if component_type == "pysm_components":
                pysm_components_string = component_type_config.pop(
                    "pysm_components_string", None
                )
                pysm_output_reference_frame = component_type_config.pop(
                    "pysm_output_reference_frame", None,
                )
            for comp_name in component_type_config:
                comp_config = component_type_config[comp_name]
                comp_class = import_class_from_string(comp_config.pop("class"))
                components[component_type][comp_name] = comp_class(
                    nside=config["nside"],
                    **comp_config
                )

    map_sim = MapSim(
        channels=config["channels"],
        nside=int(config["nside"]),
        unit=config["unit"],
        output_folder=config.get("output_folder", "output"),
        output_filename_template=config.get(
            "output_filename_template", default_output_filename_template
        ),
        pysm_components_string=pysm_components_string,
        pysm_custom_components=components["pysm_components"],
        pysm_output_reference_frame=pysm_output_reference_frame,
        other_components=components["other_components"],
    )
    return map_sim


class MapSim:

    def __init__(
        self,
        channels,
        nside,
        unit="uK_CMB",
        output_folder="output",
        tag="mapsim",
        output_filename_template=default_output_filename_template,
        pysm_components_string=None,
        pysm_output_reference_frame="C",
        pysm_custom_components=None,
        other_components=None,
    ):
        """Run map based simulations

        MapSim executes PySM for each band of the input channels with a sky defined
        by default PySM components in `pysm_components_string` and custom components in
        `pysm_custom_components` and rotates in Alm space to the reference frame `pysm_output_reference_frame`.
        Then for each of the channels specified, smoothes the map with the channel beam
        and finally adds the map generated by `other_components`, for example noise maps, and writes
        the outputs to disk.

        Parameters
        ----------

        channels : string
            all/SO for all channels, LA for all Large Aperture channels, SA for Small,
            otherwise a single channel label, e.g. LA_27 or a list of channel labels
        nside : int
            output HEALPix Nside
        unit : str
            Unit of output maps
        output_folder : str
            Relative or absolute path to output folder, string template with {nside} and {tag} fields
        tag : str
            String to describe the current simulation, for example its content, which is used into
            string interpolation for `output_folder` and `output_filename_template`
        output_filename_template : str
            String template with {telescope} {channel} {nside} {tag} fields
        pysm_components_string : str
            Comma separated string of PySM components, i.e. "s1,d4,a2"
        pysm_output_reference_frame : str
            The output of PySM is in Galactic coordinates, rotate to C for Equatorial or E for Ecliptic,
            set to None to apply no rotation
        pysm_custom_components : dict
            Dictionary of other components executed through PySM
        other_components : dict
            Dictionary of component name, component class pairs, the output of these are **not** rotated,
            they should already be in the same reference frame specified in pysm_output_reference_frame.

        """

        if channels in ["LA", "SA"]:
            self.channels = [
                Channel(channels, band) for band in so_utils.get_bands(channels)
            ]
        elif channels in ["all", "SO"]:
            self.channels = [
                Channel(telescope, band)
                for telescope in ["LA", "SA"]
                for band in so_utils.get_bands(telescope)
            ]
        else:
            self.channels = []
            if isinstance(channels, str):
                channels = [channels]
            for ch in channels:
                [telescope, str_band] = ch.split("_")
                self.channels.append(Channel(telescope, int(str_band)))

        self.bands = np.unique([ch.band for ch in self.channels])
        self.nside = nside
        self.unit = unit
        self.pysm_components_string = pysm_components_string
        self.pysm_custom_components = pysm_custom_components
        self.run_pysm = not (
            (pysm_components_string is None)
            and (pysm_custom_components is None or len(pysm_custom_components) == 0)
        )
        self.other_components = other_components
        self.tag = tag
        self.output_folder = output_folder.format(nside=self.nside, tag=self.tag)
        if not os.path.exists(self.output_folder):
            os.makedirs(self.output_folder)
        self.output_filename_template = output_filename_template
        self.rot = None
        if pysm_output_reference_frame is not None and pysm_output_reference_frame != "G":
            self.rot = hp.Rotator(coord = ("G", pysm_output_reference_frame))

    def execute(self, write_outputs=False):
        """Run map simulations

        Execute simulations for all channels and write to disk the maps,
        unless `write_outputs` is False, then return them.
        """

        use_pixel_weights = self.nside >= 32

        if self.run_pysm:
            sky_config = {}
            if self.pysm_components_string is not None:
                for model in self.pysm_components_string.split(","):
                    sky_config[PYSM_COMPONENTS[model.split("_")[-1][0]]] = (
                        get_so_models(model, self.nside)
                        if model.startswith("SO")
                        else pysm.nominal.models(model, self.nside)
                    )

            self.pysm_sky = pysm.Sky(sky_config)

            if self.pysm_custom_components is not None:
                for comp_name, comp in self.pysm_custom_components.items():
                    self.pysm_sky.add_component(comp_name, comp)

        if not write_outputs:
            output = {}

        for band in self.bands:

            instrument = {
                "frequencies": np.array([band]),
                "nside": self.nside,
                "use_bandpass": False,
                "add_noise": False,
                "output_units": self.unit,
                "use_smoothing": False,
            }

            if self.run_pysm:
                instrument = pysm.Instrument(instrument)
                band_map = hp.ma(
                    instrument.observe(self.pysm_sky, write_outputs=False)[0][0]
                )
                if len(band_map) == 1:
                    band_map = band_map[0]

                if self.rot is not None:
                    band_map = hp.ma(self.rot.rotate_map_alms(band_map, use_pixel_weights=use_pixel_weights))

            for ch in self.channels:
                if ch.band == band:
                    if self.run_pysm:
                        beam_width_arcmin = so_utils.get_beam(ch.telescope, ch.band)
                        output_map = hp.smoothing(
                            band_map, fwhm=np.radians(beam_width_arcmin / 60), use_pixel_weights=use_pixel_weights,
                        )
                    else:
                        output_map = np.zeros(
                            (3, hp.nside2npix(self.nside)), dtype=np.float64
                        )

                    for comp in self.other_components.values():
                        output_map += hp.ma(comp.simulate(ch, output_units=self.unit))

                    if write_outputs:
                        hp.write_map(
                            os.path.join(
                                self.output_folder,
                                self.output_filename_template.format(
                                    telescope=ch.telescope.lower(),
                                    band=ch.band,
                                    nside=self.nside,
                                    tag=self.tag,
                                ),
                            ),
                            output_map,
                            overwrite=True,
                        )
                    else:
                        output[ch] = output_map.filled()
        if not write_outputs:
            return output
