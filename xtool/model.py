import os

from astropy.io import fits
import numpy as np
from astropy import units as u
from astropy.table import Table

from glob import glob
import re
import xtool

xtool_data_path = os.path.join(xtool.__path__[0], 'data')


class InstrumentData(object):
    pass

class XShooterData(InstrumentData):
    data_fname = 'SCI_SLIT_DIVFF'

    transform_pixel_to_wave_fname = 'SCI_SLIT_WAVE_MAP'
    transform_pixel_to_slit_fname = 'SCI_SLIT_SLIT_MAP'

    spectral_format_fname = 'SPECTRAL_FORMAT_TAB'

    def __init__(self, data_dir):
        """

        Parameters
        ----------
        data_dir : numpy.ndarray

        """


        data_full_fname = glob(os.path.join(
            data_dir, '{0}*'.format(self.data_fname)))
        assert len(data_full_fname) == 1, (
            "More than one datafile found {0}".format(data_full_fname))


        science_data_full_fname = data_full_fname[0]
        self.instrument_arm = fits.getval(science_data_full_fname,
                                          'HIERARCH ESO SEQ ARM')
        self.xshooter_dir = os.path.dirname(science_data_full_fname)

    def __getattr__(self, item):
        read_item = 'read_{0}'.format(item)
        if hasattr(self, read_item):
            if not hasattr(self, '_' + item):
                setattr(self, '_' + item, getattr(self, read_item)())
            return getattr(self, '_' + item)
        else:
            raise AttributeError()

    def __getitem__(self, item):
        if item not in self.order_table.index:
            raise IndexError('Dataset only contains orders {0} - {1}'.format(
                self.order_table.index.min(), self.order_table.index.max()))
        else:
            return Order.from_xshooter_data(self, item)


    @property
    def xbin(self):
        """
        Returns
        -------
            : int
        """
        return self.science_header.get("HIERARCH ESO DET WIN1 BINX", 2)

    @property
    def ybin(self):
        """
        Returns
        -------
            : int
        """

        return self.science_header.get("HIERARCH ESO DET WIN1 BINY", 2)

    def read_data(self, xshooter_dir, data_fname, ext=0):
        """
        This is a helper function to read fits data from an xshooter directory


        Parameters
        ----------
        xshooter_dir : str
          directory for the XShooter science data
        data_fname : str
            name prefix for the datafile
        ext : int
            FITS extension (default = 0)

        Returns
        -------
        data_array : numpy.ndarray
            fits data from that file

        """

        fname = os.path.join(xshooter_dir, "{0}_{1}.fits".format(
            data_fname, self.instrument_arm))

        return fits.getdata(fname, ext=ext)

    def read_science_data(self):
        """
        Utility function to read the science data

        Returns
        -------
            : numpy.ndarray
            science data array
        """

        return self.read_data(self.xshooter_dir, self.data_fname)

    def read_science_header(self):
        """
        Utility function to read the science header
        Returns
        -------
            : astropy.io.fits.header.Header
            Header for the science dataset
        """

        fname = os.path.join(self.xshooter_dir, "{0}_{1}.fits".format(
            self.data_fname, self.instrument_arm))

        return fits.getheader(fname)

    def read_uncertainty(self):
        """
        Utility function to read the science uncertainty
        Returns
        -------
            : numpy.ndarray
        """
        return self.read_data(self.xshooter_dir, self.data_fname, ext=1)

    def read_flags(self):
        """
        Utility function to read the science flags and convert it to an
        integer
        Returns
        -------
            : numpy.ndarray
        """

        return np.int64(
            self.read_data(self.xshooter_dir, self.data_fname, ext=2))

    def read_transform_pix_to_wave(self):
        """
        Utility function to read the transform and convert it to a quantity

        Returns
        -------
        pix_to_wave : astropy.units.Quantity
        """

        return self.read_data(self.xshooter_dir,
                              self.transform_pixel_to_wave_fname) * u.nm

    def read_transform_pix_to_slit(self):
        """
        Utility function to read the transform and convert it to a quantity

        Returns
        -------
        pix_to_wave : astropy.units.Quantity
        """

        return self.read_data(
            self.xshooter_dir,
            self.transform_pixel_to_wave_fname) * u.arcsecond


    def read_spectral_format_table(self):
        """

        Utility function to read the spectral format table


        Returns
        -------
        spectral_format_table : pandas.DataFrame
        """

        spectral_format = Table.read(
            os.path.join(xtool_data_path, '{0}_{1}.fits'.format(
                self.spectral_format_fname, self.instrument_arm))).to_pandas()
        return spectral_format.set_index['ORDER']

    def read_order_table(self):
        """
        Utility function to read the order table

        Returns
        -------
            : pandas.DataFrame
        """

        order_table = Table(self.read_data(self.xshooter_dir,
                              'ORDER_TAB_AFC_SLIT'))
        return order_table.to_pandas().set_index('ABSORDER')

    def __repr__(self):
        return "<XShooterData {0} {1}>".format(self.science_header['ARCFILE'],
                                               self.instrument_arm)


    def get_order_coefficients(self, order_id):
        """
        Getting the polynomial coefficients for a specific order

        Parameters
        ----------
        order_id : int

        Returns
        -------
        slice_y : tuple
            tuple of starty and endy

        edg_up_coef: list
            list of polynomial coefficients for upper edge

        edg_lo_coef: list
            list of polynomial coefficients for lower edge


        """

        order_data = self.order_table.ix[order_id]
        deg = np.int(order_data['DEGY'])
        slice_y = slice(np.int(order_data['STARTY']) - 1,
                        np.int(order_data['ENDY']) - 1)

        edg_up_coef = [order_data['EDGUPCOEF{0}'.format(i)]
                       for i in xrange(deg + 1)]
        edg_lo_coef = [order_data['EDGLOCOEF{0}'.format(i)]
                       for i in xrange(deg + 1)]
        return slice_y, edg_up_coef, edg_lo_coef

    def calculate_edges(self, order_id):
        """
        Calculate the edges for a given order
        Parameters
        ----------
        order_id : int
            absolute order id

        Returns
        -------
        yrange : numpy.ndarray
            y coordinate for order polynomial

        lower_edges : numpy.ndarray
            x coordinate for lower edge of the order

        upper_edges : numpy.ndarray
            x coordinate for lower edge of the order

        """

        slice_y, edg_up_coef, edg_lo_coef = self.get_order_coefficients(order_id)
        yrange = (np.arange(self.science_data.shape[0]))


        lower_edges = np.polynomial.polynomial.polyval(
            yrange, edg_lo_coef)
        upper_edges = np.polynomial.polynomial.polyval(
            yrange, edg_up_coef)

        return slice_y, lower_edges - 1, upper_edges - 1


    def cutout_rectangular_order(self, order_id, data_array, extra_sample=5):
        """
        Cutting out the data in a rectangular fashion for each order without
        masking the other orders

        Parameters
        ----------
        order_id : int
            absolute order id
        data_array : numpy.ndarray
            any numpy.ndarray coming from this dataset
        extra_sample :
            extra marging to cut left and right (defaults to 5 pixels)

        Returns
        -------
        cutout_data_array: numpy.ndarray
            cutout of the data array
        edge_slice: slice
            slice of the whole data_array

        """

        slice_y, lower_edge, upper_edge = self.calculate_edges(order_id)

        edge_slice_start = np.max(
            [0, np.int(lower_edge[slice_y].min() - extra_sample)])
        edge_slice_end = np.int(upper_edge[slice_y].max() + extra_sample)
        edge_slice = slice(edge_slice_start, edge_slice_end)

        return data_array[:, edge_slice], edge_slice

    def cutout_and_mask_order(self, order_id, data_array, extra_sample=5):
        """
        Cutout the order and generate a boolean mask for the data

        Parameters
        ----------
        order_id : int
            Order id
        data_array : numpy.ndarray
            numpy data array to be cut
        extra_sample : int
            pixel to extend either side (default=5)

        Returns
        -------
        cutout_data_array : numpy.ndarray
            cut data array

        mask : numpy.ndarray
            mask only masking the actual order data - dtype = bool

        """
        cutout_data_array, edge_slice = self.cutout_rectangular_order(
            order_id, data_array, extra_sample=extra_sample)

        slice_y, lower_edge, upper_edge = self.calculate_edges(order_id)
        y, x = np.mgrid[
               :cutout_data_array.shape[0], :cutout_data_array.shape[1]]
        mask = ((x > (lower_edge - edge_slice.start)[None].T) &
                (x < (upper_edge - edge_slice.start)[None].T) &
                (y > slice_y.start) & (y < slice_y.stop))

        return cutout_data_array, mask


class Order(object):

    @classmethod
    def from_xshooter_data(cls, xshooter_data, order_id):
        """
        Construct an xtool.model.Order instance from the an XShooter Data
        Parameters
        ----------
        xshooter_data : XShooterData
            input X-shooter data
        order_id : int
            absolute order ID

        Returns
        -------
            : Order
            order object
        """

        data, mask = xshooter_data.cutout_and_mask_order(
            order_id, xshooter_data.science_data)
        uncertainty, _ = xshooter_data.cutout_rectangular_order(
            order_id, xshooter_data.uncertainty)
        flags, _ = xshooter_data.cutout_rectangular_order(
            order_id, xshooter_data.flags)

        transform_pix_to_wave, _ = xshooter_data.cutout_rectangular_order(
            order_id, xshooter_data.transform_pix_to_wave)

        transform_pix_to_slit, _ = xshooter_data.cutout_rectangular_order(
            order_id, xshooter_data.transform_pix_to_slit)

        order_wcs = LUTOrderWCS(transform_pix_to_wave, transform_pix_to_slit,
                                mask)

        return cls(data, uncertainty, flags, mask, order_id,
                   xshooter_data.science_header['ARCFILE'], order_wcs)


    def __init__(self, data, uncertainty, flags, mask, order_id,
                 data_set_id, order_wcs):
        self.mask = mask

        self.data = self._generate_masked_array(data)
        self.uncertainty = self._generate_masked_array(uncertainty)
        self.flags = self._generate_masked_array(flags, fill_value=-1)

        self.order_id = order_id
        self.order_wcs = order_wcs
        self.data_set_id = data_set_id

    def _generate_masked_array(self, data_set, fill_value=np.nan):
        """
        Make a masked array using numpy.ma.MaskedArray
        Parameters
        ----------
        data_set : numpy.ndarray

        Returns
        -------
        masked_data_set : numpy.ma.MaskedArray
        """
        return np.ma.MaskedArray(data_set, ~self.mask, fill_value=fill_value)

    def __repr__(self):
        repr_str = "<Order {num} {dataset}>".format(num=self.order_id,
                                                    dataset=self.data_set_id)
        return repr_str


class LUTOrderWCS(object):
    def __init__(self, transform_pixel_to_wavelength, transform_pixel_to_slit,
                 mask):
        """

        Parameters
        ----------
        transform_pixel_to_wavelength :
        transform_pixel_to_slit :
        mask :
        """

        self.x_grid, self.y_grid = self._generate_coordinate_grid(mask)

        self.pix_to_wave = np.ma.MaskedArray(
            transform_pixel_to_wavelength.value, ~mask, fill_value=np.nan)
        self.pix_to_slit = np.ma.MaskedArray(
            transform_pixel_to_slit.value, ~mask, fill_value=np.nan)

        self.pix_to_wave_unit = transform_pixel_to_wavelength.unit
        self.pix_to_slit_unit = transform_pixel_to_slit.unit


    @property
    def x(self):
        return self.x_grid.compressed()

    @property
    def y(self):
        return self.y_grid.compressed()

    @staticmethod
    def _generate_coordinate_grid(mask):
        """
        generate a coordinate grid for the order slice
        Parameters
        ----------
        mask : numpy.ndarray
            boolean masked with True for valid data and false for invalid data

        Returns
        -------
        x_grid : numpy.ma.MaskedArray
        y_grid : numpy.ma.MaskedArray

        """
        y_grid, x_grid = np.mgrid[:mask.shape[0], :mask.shape[1]]

        return (np.ma.MaskedArray(x_grid, ~mask, fill_value=-1),
                np.ma.MaskedArray(y_grid, ~mask, fill_value=-1))



