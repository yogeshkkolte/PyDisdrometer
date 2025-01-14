# -*- coding: utf-8 -*-
'''
The Drop Size Distribution model contains the DropSizeDistribution class.
This class represents drop size distributions returned from the various
readers in the io module. The class knows how to perform scattering
simulations on itself.
'''

import numpy as np
import pytmatrix
from pytmatrix.tmatrix import Scatterer
from pytmatrix.psd import PSDIntegrator
from pytmatrix import orientation, radar, tmatrix_aux, refractive
from . import DSR
from datetime import date
from expfit import expfit, expfit2
from scipy.optimize import curve_fit
import scipy


class DropSizeDistribution(object):

    '''
    DropSizeDistribution class to hold DSD's and calculate parameters
    and relationships. Should be returned from the disdrometer*reader style
    functions.

    Attributes
    ----------
        time: array_like
            An array of times corresponding to the time each dsd was sampled in minutes relative to time_start.
        time_start: datetime
            A datetime object indicated start of disdrometer recording.
        fields: dictionary
            Dictionary of scattered components.
        Nd : 2d Array
            A list of drop size distributions
        spread: array_like
            Array giving the bin spread size for each size bin of the
            disdrometer.
        velocity: array_like
            Terminal Fall Velocity for each size bin. This is based on the
            disdrometer assumptions.
        Z: array_like
            The equivalent reflectivity factory from the disdrometer. Often
            taken as D**6.

        bin_edges: array_like
            N+1 sized array of the boundaries of each size bin. For 30 bins
            for instance, there will be 31 different bin boundaries.
        diameter: array_like
            The center size for each dsd bin.

    '''

    def __init__(self, time, Nd, spread, rain_rate=None, velocity=None, Z=None,
                 num_particles=None, bin_edges=None, diameter=None, time_start = None, location=None,
                 scattering_temp = '10C'):
        '''Initializer for the dropsizedistribution class.

        The DropSizeDistribution class holds dsd's returned from the various
        readers in the io module.

        Parameters
        ----------
        time: array_like
            An array of times corresponding to the time each dsd was sampled in minutes relative to time_start.
        Nd : 2d Array
            A list of drop size distributions
        spread: array_like
            Array giving the bin spread size for each size bin of the
            disdrometer.
        velocity: optional, array_like
            Terminal Fall Velocity for each size bin. This is based on the
            disdrometer assumptions.
        Z: optional, array_like
            The equivalent reflectivity factory from the disdrometer. Often
            taken as D**6.
        num_particles: optional, array_like
            Number of measured particles for each time instant.
        bin_edges: optional, array_like
            N+1 sized array of the boundaries of each size bin. For 30 bins
            for instance, there will be 31 different bin boundaries.
        diameter: optional, array_like
            The center size for each dsd bin.
        time_start: datetime
            Recording Start time.
        location: tuple
            (Latitude, Longitude) pair in decimal format.
        scattering_temp: optional, string
            Scattering temperature string. One of ("0C","10C","20C").
            Defaults to "10C"

        Returns
        -------
        dsd: `DropSizeDistribution` instance
            Drop Size Distribution instance.

        '''
        self.time = time
        self.Nd = Nd
        self.spread = spread
        self.rain_rate = rain_rate
        self.velocity = velocity
        # I need to fix this later, but this is the disdrometer intrinsic Z.
        self.Z = Z
        self.num_particles = num_particles
        self.bin_edges = bin_edges
        self.diameter = diameter
        self.fields = {}
        self.time_start = time_start
        
        self.m_w_dict = {'0C': refractive.m_w_0C ,'10C': refractive.m_w_10C , '20C':  refractive.m_w_20C  }

        self.m_w = self.m_w_dict[scattering_temp]

        lt = len(time)
        location = {}

        if location:
            self.location = {'latitude': location[0], 'longitude': location[1]}

    def change_scattering_temperature(self, scattering_temp='10C'):
        ''' Change the scattering temperature. After use, re-run calculate_radar_parameters
        to see the effect this has on the parameters

        Parameters
        ----------
        temp: optional, string
            String of temperature to scatter at. Choice of ("0C","10C","20C").
        '''
        self.m_w = self.m_w_dict[scattering_temp]



    def calculate_radar_parameters(self, wavelength=tmatrix_aux.wl_X, dsr_func = DSR.bc, scatter_time_range = None ):
        ''' Calculates radar parameters for the Drop Size Distribution.

        Calculates the radar parameters and stores them in the object.
        Defaults to X-Band,Beard and Chuang 10C setup.

        Sets the dictionary parameters in fields dictionary:
            Zh, Zdr, Kdp, Ai(Attenuation)

        Parameters:
        ----------
            wavelength: optional, pytmatrix wavelength
                Wavelength to calculate scattering coefficients at.
            dsr_func: optional, function
                Drop Shape Relationship function. Several are availab le in the `DSR` module.
                Defaults to Beard and Chuang
            scatter_time_range: optional, tuple
                Parameter to restrict the scattering to a time interval. The first element is the start time,
                while the second is the end time. 
        '''
        self._setup_scattering(wavelength, dsr_func)
        self._setup_empty_fields()

        if scatter_time_range is None:
            self.scatter_start_time = 0
            self.scatter_end_time = len(self.time)
        else:
            if scatter_time_range[0] < 0:
                print("Invalid Start time specified, aborting")
                return
            self.scatter_start_time = scatter_time_range[0]
            self.scatter_end_time = scatter_time_range[1]

            if scatter_time_range[1] > len(self.time):
                print("End of Scatter time is greater than end of file. Scattering to end of included time.")
                self.scatter_end_time = len(self.time)

        self.scatterer.set_geometry(tmatrix_aux.geom_horiz_back) # We break up scattering to avoid regenerating table.

        for t in range(self.scatter_start_time, self.scatter_end_time):
            if np.sum(self.Nd[t]) is 0:
                continue
            BinnedDSD = pytmatrix.psd.BinnedPSD(self.bin_edges,  self.Nd[t])
            self.scatterer.psd = BinnedDSD
            self.fields['Zh']['data'][t] = 10 * \
                np.log10(radar.refl(self.scatterer))
            self.fields['Zdr']['data'][t] = 10 * \
                np.log10(radar.Zdr(self.scatterer))

        self.scatterer.set_geometry(tmatrix_aux.geom_horiz_forw)

        for t in range(self.scatter_start_time, self.scatter_end_time):
            self.fields['Kdp']['data'][t] = radar.Kdp(self.scatterer)
            self.fields['Ai']['data'][t] = radar.Ai(self.scatterer)
            self.fields['Ad']['data'][t] = radar.Ai(self.scatterer) -radar.Ai(self.scatterer, h_pol=False)

    def _setup_empty_fields(self, ):
        ''' Preallocate arrays of zeros for the radar moments
        '''
        self.fields['Zh'] = {'data': np.zeros(len(self.time))}
        self.fields['Zdr'] = {'data': np.zeros(len(self.time))}
        self.fields['Kdp'] = {'data': np.zeros(len(self.time))}
        self.fields['Ai'] = {'data': np.zeros(len(self.time))}
        self.fields['Ad'] = {'data': np.zeros(len(self.time))}

    def _setup_scattering(self, wavelength, dsr_func):
        ''' Internal Function to create scattering tables.

        This internal function sets up the scattering table. It takes a
        wavelength as an argument where wavelength is one of the pytmatrix
        accepted wavelengths.

        Parameters:
        -----------
            wavelength : tmatrix wavelength
                PyTmatrix wavelength.
            dsr_func : function
                Drop Shape Relationship function. Several built-in are available in the `DSR` module.

        '''
        self.scatterer = Scatterer(wavelength=wavelength,
                                   m=self.m_w[wavelength])
        self.scatterer.psd_integrator = PSDIntegrator()
        self.scatterer.psd_integrator.axis_ratio_func = lambda D: 1.0 / \
            dsr_func(D)
        self.dsr_func = dsr_func
        self.scatterer.psd_integrator.D_max = 10.0
        self.scatterer.psd_integrator.geometries = (
            tmatrix_aux.geom_horiz_back, tmatrix_aux.geom_horiz_forw)
        self.scatterer.or_pdf = orientation.gaussian_pdf(20.0)
        self.scatterer.orient = orientation.orient_averaged_fixed
        self.scatterer.psd_integrator.init_scatter_table(self.scatterer)

    def _calc_mth_moment(self, m):
        '''Calculates the mth moment of the drop size distribution.

        Returns the mth moment of the drop size distribution E[D^m].

        Parameters:
        -----------
        m: float
            order of the moment
        '''

        if len(self.spread) > 0:
            bin_width=self.spread
        else:
            bin_width = [self.bin_edges[i + 1] - self.bin_edges[i]
                     for i in range(0, len(self.bin_edges) - 1)]
        mth_moment = np.zeros(len(self.time))

        for t in range(0, len(self.time)):
            dmth = np.power(self.diameter, m)
            mth_moment[t] = np.dot(np.multiply(dmth, self.Nd[t]), bin_width)

        return mth_moment

    def calculate_dsd_parameterization(self, method='bringi'):
        '''Calculates DSD Parameterization.

        This calculates the dsd parameterization and stores the result in the fields dictionary. 
        This includes the following parameters:
        Nt, W, D0, Nw, Dmax, Dm, N0, mu

        Parameters:
        -----------
        method: optional, string
            Method to use for DSD estimation


        Further Info:
        ------
        For D0 and Nw we use the method due to Bringi and Chandrasekar.

        '''

        self.fields['Nt'] = {'data': np.zeros(len(self.time))}
        self.fields['W'] = {'data': np.zeros(len(self.time))}
        self.fields['D0'] = {'data': np.zeros(len(self.time))}
        self.fields['Nw'] = {'data': np.zeros(len(self.time))}
        self.fields['Dmax'] = {'data': np.zeros(len(self.time))}
        self.fields['Dm'] = {'data': np.zeros(len(self.time))}
        self.fields['Nw'] = {'data': np.zeros(len(self.time))}
        self.fields['N0'] = {'data': np.zeros(len(self.time))}
        self.fields['mu'] = {'data': np.zeros(len(self.time))}

        rho_w = 1e-03  # grams per mm cubed Density of Water
        vol_constant = np.pi / 6.0 * rho_w 
        self.fields['Dm']['data'] = np.divide(self._calc_mth_moment(4), self._calc_mth_moment(3))
        for t in range(0, len(self.time)):
            if np.sum(self.Nd[t]) == 0:
                continue
            self.fields['Nt']['data'][t] = np.dot(self.spread, self.Nd[t])
            self.fields['W']['data'][t] = vol_constant * np.dot(np.multiply(self.Nd[t], self.spread),
                                                                np.array(self.diameter) ** 3)
            self.fields['D0']['data'][t] = self._calculate_D0(self.Nd[t])
            self.fields['Nw']['data'][t] =  256.0 / \
                (np.pi * rho_w) * np.divide(self.fields['W']['data'][t], self.fields['Dm']['data'][t] ** 4)

            self.fields['Dmax']['data'][t] = self.__get_last_nonzero(self.Nd[t])

        self.fields['mu']['data'][:] = map(self._estimate_mu, range(0,len(self.time)))

    def __get_last_nonzero(self, N): 
        ''' Gets last nonzero entry in an array. Gets last non-zero entry in an array.

        Parameters
        ----------
        N: array_like
            Array to find nonzero entry in

        Returns
        -------
        max: int
            last nonzero entry in an array.
        '''

        if np.count_nonzero(N):
            return self.diameter[np.max(N.nonzero())]
        else:
            return 0

    def _calculate_D0(self, N):
        ''' Calculate Median Drop diameter.

        Calculates the median drop diameter for the array N. This assumes diameter and bin widths in the 
        dsd object have been properly set. 

        Parameters:
        -----------
        N: array_like
            Array of drop counts for each size bin.

        Notes:
        ------
        This works by calculating the two bins where cumulative water content goes over 0.5, and then interpolates
        the correct D0 value between these two bins. 
        '''

        rho_w = 1e-3
        W_const = rho_w * np.pi / 6.0

        if np.sum(N) == 0:
            return 0

        cum_W = W_const * \
            np.cumsum([N[k] * self.spread[k] * (self.diameter[k] ** 3)
                       for k in range(0, len(N))])
        cross_pt = list(cum_W < (cum_W[-1] * 0.5)).index(False) - 1
        slope = (cum_W[cross_pt + 1] - cum_W[cross_pt]) / \
            (self.diameter[cross_pt + 1] - self.diameter[cross_pt])
        run = (0.5 * cum_W[-1] - cum_W[cross_pt]) / slope
        return self.diameter[cross_pt] + run

    def calculate_RR(self):
        '''Calculate instantaneous rain rate.

        This calculates instantaneous rain rate based on the flux of water. 
        '''
        self.fields['rain_rate'] = {'data': np.zeros(len(self.time))}
        for t in range(0, len(self.time)):
            # self.rain_rate[t] = 0.6*3.1415 * 10**(-3) * np.dot(np.multiply(self.velocity,np.multiply(self.Nd[t],self.spread )),
            #    np.array(self.diameter)**3)
            velocity = 9.65 - 10.3 * np.exp(-0.6 * self.diameter)
            velocity[0] = 0.5
            self.fields['rain_rate']['data'][t] = 0.6 * np.pi * 1e-03 * np.sum(self._mmultiply(
                velocity, self.Nd[t], self.spread, np.array(self.diameter) ** 3))

    def calculate_R_Kdp_relationship(self):
        '''
        calculate_R_kdp_relationship calculates a power fit for the rainfall-kdp
        relationship based upon the calculated radar parameters(which should
        have already been run). It returns the scale and exponential
        parameter a and b in the first tuple, and the second returned argument
        gives the covariance matrix of the fit.
        '''

        if 'rain_rate' in self.fields.keys():
            filt = np.logical_and(
                self.fields['Kdp']['data'] > 0, self.fields['rain_rate']['data'] > 0)
            popt, pcov = expfit(self.fields['Kdp']['data'][filt],
                                self.fields['rain_rate']['data'][filt])

            return popt, pcov
        else:
            print("Please run calculate_RR() function first.")
            return None

    def calculate_R_Zh_relationship(self):
        '''
        calculate_R_Zh_relationship calculates the power law fit for Zh based
        upon scattered radar parameters. It returns the scale and exponential
        parameter a and b in the first tuple, and the second returned argument
        gives the covariance matrix of the fit.

        Returns:
        --------
        popt: tuple
            a,b,c fits for relationship.
        pcov: array
            Covariance matrix of fits.
        '''

        popt, pcov = expfit(np.power(10, 0.1 * self.fields['Zh']['data'][self.rain_rate['data'] > 0]),
                            self.fields['rain_rate']['data'][self.fields['rain_rate']['data'] > 0])
        return popt, pcov

    def calculate_R_Zh_Zdr_relationship(self):
        '''
        calculate_R_Zh_Zdr_relationship calculates the power law fit for Zh,Zdr
        based upon scattered radar parameters. It returns the scale and
        exponential parameters a, b, and c in the first tuple, and the
        second returned argument gives the covariance matrix of the fit.
        Uses a set of filters to remove bad data:
        rain_rate > 0
        Zdr > 0
        Kdp > 0
        '''
        filt = np.logical_and(
            np.logical_and(self.fields['rain_rate']['data'] > 0, np.greater(self.fields['Zdr']['data'], 0)), self.fields['Kdp']['data'] > 0)
        popt, pcov = expfit2([self._idb(self.fields['Zh']['data'][filt]),
                              self._idb(self.fields['Zdr']['data'][filt])],
                             self.fields['rain_rate']['data'][filt])
        return popt, pcov

    def calculate_R_Zh_Kdp_relationship(self):
        '''
        calculate_R_Zh_Kdp_relationship calculates the power law fit for Zh,Kdp
        based upon scattered radar parameters. It returns the scale and
        exponential parameters a, b, and c in the first tuple, and the
        second returned argument gives the covariance matrix of the fit.
        rain_rate > 0
        Zdr > 0
        Kdp > 0
       '''

        filt = np.logical_and(
            np.logical_and(self.fields['rain_rate']['data'] > 0, self.fields['Zdr']['data'] > 0), self.fields['Kdp']['data'] > 0)
        popt, pcov = expfit2([self._idb(self.fields['Zh']['data'][filt]),
                              self.fields['Kdp']['data'][filt]],
                             self.fields['rain_rate']['data'][filt])
        return popt, pcov

    def calculate_R_Zdr_Kdp_relationship(self):
        '''
        calculate_R_Zdr_Kdp_relationship calculates the power law fit for Zdr,Kdp
        based upon scattered radar parameters. It returns the scale and
        exponential parameters a, b, and c in the first tuple, and the
        second returned argument gives the covariance matrix of the fit.
        rain_rate > 0
        Zdr > 0
        Kdp > 0
      '''

        filt = np.logical_and(np.logical_and(self.fields['rain_rate']['data'] > 0, self.fields['Zdr']['data'] > 0),
                              self.fields['Kdp']['data'] > 0)

        popt, pcov = expfit2([self._idb(self.fields['Zdr']['data'][filt]),
                              self.fields['Kdp']['data'][filt]],
                             self.fields['rain_rate']['data'][filt])
        return popt, pcov

    def _idb(self, db):
        '''
        Converts dB to linear scale.
        '''
        return np.power(10, np.multiply(0.1, db))

    def _mmultiply(self, *args):
        '''
        _mmultiply extends numpy multiply to arbitrary number of same
        sized matrices. Multiplication is elementwise.

        Parameters:
        -----------
        *args: matrices
            Matrices to multiply. Must be same shape.
        '''
        i_value = np.ones(len(args[0]))
        for i in args:
            i_value = np.multiply(i_value, i)

        return i_value

    def _estimate_mu(self, idx):
        """ Estimate $\mu$ for a single drop size distribution

        Estimate the shape parameter $\mu$ for the drop size distribution `Nd`. This uses the method
        due to Bringi and Chandrasekar. It is a minimization of the MSE error of a created gamma and 
        measured DSD. 

        Parameters
        ----------
        Nd : array_like 
            A drop size distribution
        D0: optional, float
            Median drop diameter in mm. If none is given, it will be estimated.
        Nw: optional, float
            Normalized Intercept Parameter. If none is given, it will be estimated.

        Returns
        -------
        mu: integer
            Best estimate for DSD shape parameter $\mu$.
        """
        if np.sum(self.Nd[idx]) == 0 :
            return np.nan
        res = scipy.optimize.minimize_scalar(self._mu_cost, bounds = (-10,20), args = (idx,), method='bounded')
        if self._mu_cost(res.x, idx) == np.nan or res.x > 20:
            return np.nan
        else:
            return res.x

    def _mu_cost(self, mu, idx):
        """ Cost function for goodness of fit of a distribution.

        Calculates the MSE cost comparison of two distributions to fit $\mu$. 

        Parameters
        ----------
        idx: integer
            index into DSD field
        mu: float
            Potential Mu value
        """
        
        gdsd  = pytmatrix.psd.GammaPSD(self.fields['D0']['data'][idx], self.fields['Nw']['data'][idx],mu)
        return np.sqrt(np.nansum(np.power(np.abs(self.Nd[idx] - gdsd(self.diameter)),2)))


        






