# PyDisdrometer

![DOI](https://zenodo.org/badge/doi/10.5281/zenodo.9991.png)   
[![Coverage Status](https://coveralls.io/repos/josephhardinee/PyDisdrometer/badge.svg?branch=master&service=github)](https://coveralls.io/github/josephhardinee/PyDisdrometer?branch=master)

PyDisdrometer is a Python package to process disdrometer files. It currently is capable of reading several different types of disdrometer formats, with more being added regularly. It currently supports the following functionality:
1) File Reading
2) Microphysics Estimation
3) T-Matrix Scattering of Radar Parameters
4) QPE Relationship Estimation.

It currently supports OTT Parsivel disdrometers, Joss Waldvogel Disdrometers, 2DVD files, and HVPS and 2DS airborne disdrometers.

Author: Joseph C. Hardin

## Usage

An quick example of using the pydisrometer package to read in a parsivel data file and calculate radar scattered parameters is: 

```python
dsd = pydisdrometer.read_parsivel(filename)

dsd.calculate_radar_parameters() 
```

If using NASA Ground Validation Parsivel Disdrometer Data from the IFloodS campaign, usage is 

```python
dsd = pydisdrometer.read_parsivel_gv(filename, campaign='ifloods')
```

The scattered fields will be stored in the fields dictionary of the dsd object. So to plot the reflectivity one can run

```python
plot(dsd.time, dsd.fields['Zh']['data'])
```

For more information, please see the examples in the Notebooks directory. Additionally you can find some initial documentation at [PyDisdrometer Documentation](http://josephhardinee.github.io/PyDisdrometer)

Requirements:
    This library currently requires the normal scientific python stack(numpy+scipy+matplotlib)
    It also requires the [PyTMatrix Package](https://github.com/jleinonen/pytmatrix). 

We welcome contributions from all users. Please see the examples in Notebooks for a more indepth guide on how to use PyDisdrometer.

## User Group
There is now a pydisdrometer user group mailing list at
https://groups.google.com/forum/#!forum/pydisdrometer-user-group



