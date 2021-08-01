# coding: utf-8
# Copyright (c) Max-Planck-Institut für Eisenforschung GmbH - Computational Materials Design (CM) Department
# Distributed under the terms of "New BSD License", see the LICENSE file.

from __future__ import print_function
import numpy as np
import warnings

"""
Sometimes numpy and scipy are missing things, or I can't find them.
"""

__author__ = "Liam Huber"
__copyright__ = "Copyright 2019, Max-Planck-Institut für Eisenforschung GmbH " \
                "- Computational Materials Design (CM) Department"
__version__ = "0.0"
__maintainer__ = "Liam Huber"
__email__ = "huber@mpie.de"
__status__ = "development"
__date__ = "June 26, 2019"


def welford_online(x, mean, std, k):
    """
    Computes the cumulative mean and standard deviation.

    Note: The standard deviation calculated is for the population (ddof=0). For the sample (ddof=1) it would need to
    be extended.

    Args:
        x (float/numpy.ndarray): The new sample.
        mean (float/numpy.ndarray): The mean so far.
        std (float/numpy.ndarray): The standard deviation so far.
        k (int): How many samples were used to calculate the existing `mean` and `std`.

    Returns:
        float/numpy.ndarray, float/numpy.ndarray: The new mean and standard deviation for `k+1` values.
    """
    warnings.filterwarnings('ignore')
    if np.nan in [x, mean, std, k]:
        new_mean = np.nan
        new_std = np.nan
    else:
        # NOTE: RuntimeWarning is suppressed here!
        warnings.filterwarnings('ignore', category=RuntimeWarning)
        new_mean = (x + k * mean) / (k + 1)
        new_std = np.sqrt((k * std ** 2 + (x - mean) * (x - new_mean)) / (k + 1))
        # and set to default here:
        warnings.filterwarnings('default')
    return new_mean, new_std
