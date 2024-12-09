from ...imports import *


def semimajoraxis_from_period(self, distribution=False):
    """
    Planet Semi-major Axis (AU)

    Calculate "a" from the period and stellar mass.
    This might be used if no semi-major axis is
    available in the standardized table.

    Parameters
    ----------
    distribution : bool
        If False, return a simple array of values.
        If True, return an astropy.uncertainty.Distribution,
        which can be used for error propagation.
    """
    P = self.get("period", distribution=distribution)
    M = self.get("stellar_mass", distribution=distribution)
    G = con.G
    a = ((G * M * P**2 / 4 / np.pi**2) ** (1 / 3)).to("AU")
    return a


def semimajoraxis_from_transit_ar(self, distribution=False):
    """
    Planet Semi-major Axis (AU)

    Calculate "a" from the transit-derived a/Rs.
    This might be used if no semi-major axis is
    available in the standardized table.

    Parameters
    ----------
    distribution : bool
        If False, return a simple array of values.
        If True, return an astropy.uncertainty.Distribution,
        which can be used for error propagation.
    """
    a_over_R = self.get("transit_ar", distribution=distribution)
    R = self.get("stellar_radius", distribution=distribution)
    a = (a_over_R * R).to("AU")
    return a


def _choose_calculation(
    self, methods=[], distribution=False, how_to_choose="preference", **kw
):
    """
    Choose values element-wise from multiple functions.

    This wrapper helps merge together different calculations
    of the same quantity, choosing sources based on preference,
    whether the calculation is finite, and/or uncertainties.

    Parameters
    ----------
    methods : list of strings
        The names of methods to consider for calculating
        the quantity, in order of preference. The order
        matters most if `how_to_choose=='preference'`
        (see below); if `how_to_choose=='precision'`
        then preference doesn't really matter (except
        in cases where two different options have
        identical fractional uncertainties).
    distribution : bool
        If False, return a simple array of values.
        If True, return an astropy.uncertainty.Distribution,
        which can be used for error propagation.
    how_to_choose : str
        A string describing how to pick values from
        among the different possible calculations.
        Options include:
            'preference' = pick the highest preference
            option that produces a finite value
            'precision' = pick the most precise value,
            base on the calculated mean uncertainty
    **kw : dict
        All other keywords will be passed to the functions
        for calculating quantities. All functions must be able
        to accept the same set of keyword.
    """

    # construct a list of arrays of values
    value_estimates = u.Quantity(
        [self.get(m, distribution=distribution, **kw) for m in methods]
    )

    # pick the first option as baseline
    values = value_estimates[0]

    if how_to_choose == "preference":
        # loop through options, picking the first finite value
        for v in value_estimates:
            isnt_good_yet = np.isfinite(values) == False
            values[isnt_good_yet] = v[isnt_good_yet]
    elif how_to_choose == "precision":
        # calculate (symmetric) fractional uncertainties for all options
        mu_estimates = u.Quantity(
            [self.get(m, distribution=False, **kw) for m in methods]
        )
        uncertainty_estimates = u.Quantity(
            [self.get_uncertainty(m, **kw) for m in methods]
        )
        fractional_uncertainty_estimates = u.Quantity(
            [u / v for v, u in zip(mu_estimates, uncertainty_estimates)]
        )

        fractional_uncertainty_estimates[np.isnan(fractional_uncertainty_estimates)] = (
            np.inf
        )
        current_fractional_uncertainty = fractional_uncertainty_estimates[0]

        # loop through options to select the one with smallest uncertainty
        for v, f in zip(value_estimates, fractional_uncertainty_estimates):
            has_smaller_uncertainty = f < current_fractional_uncertainty
            current_fractional_uncertainty[has_smaller_uncertainty] = f[
                has_smaller_uncertainty
            ]
            values[has_smaller_uncertainty] = v[has_smaller_uncertainty]


@property
def semimajoraxis(self):
    """
    Have a safe way to calculate the semimajor axis of planets,
    that fills in gaps as necessary. Basic strategy:

        First from table.
        Then from NVK3L.
        Then from a/R*.

    """

    # pull out the actual values from the table
    a = self.standard["semimajoraxis"].copy()

    # try to replace bad ones with NVK3L
    bad = np.isfinite(a) == False
    self._speak(f"{sum(bad)}/{len(self)} semimajoraxes are missing")

    # calculate from the period and the stellar mass
    P = self.period[bad]
    M = self.stellar_mass[bad]
    G = con.G
    a[bad] = ((G * M * P**2 / 4 / np.pi**2) ** (1 / 3)).to("AU")

    # replace those that are still bad with the a/R*
    stillbad = np.isfinite(a) == False
    self._speak(f"{sum(stillbad)}/{len(self)} are still missing after NVK3L")
    # (pull from table to avoid potential for recursion)
    try:
        a_over_rs = self.standard["transit_ar"][stillbad]
        rs = self.standard["stellar_radius"][stillbad]
        a[stillbad] = a_over_rs * rs
    except KeyError:
        pass

    return a


@property
def a_over_rs(self):
    """
    Have a safe way to calculate the scaled semimajor axis of planets,
    that fills in gaps as necessary. Basic strategy:

        First from table, mostly derived from transit.
        Then from the semimajor axis.
    """

    # pull out the values from the table
    a_over_rs = self.standard["transit_ar"].copy()

    # try to replace bad ones with NVK3L
    bad = np.isfinite(a_over_rs) == False
    self._speak(f"{sum(bad)}/{len(self)} values for a/R* are missing")

    a = self.semimajoraxis[bad]
    R = self.stellar_radius[bad]
    a_over_rs[bad] = a / R

    stillbad = np.isfinite(a_over_rs) == False
    self._speak(f"{sum(stillbad)}/{len(self)} are still missing after a and R*")

    return a_over_rs


@property
def e(self):
    """
    FIXME -- assumes are missing eccentricities are 0!
    """

    # pull out the actual values from the table
    e = self.standard["eccentricity"].copy()

    # try to replace bad ones with NVK3L
    bad = np.isfinite(e) == False
    self._speak(f"{sum(bad)}/{len(self)} eccentricities are missing")
    self._speak(f"assuming they are all zero")
    e[bad] = 0

    return e


@property
def omega(self):
    """
    (FIXME! we need better longitudes of periastron)
    """

    # pull out the actual values from the table
    omega = self.standard["omega"].copy()

    # try to replace bad ones with NVK3L
    bad = np.isfinite(omega) == False
    self._speak(f"{sum(bad)}/{len(self)} longitudes of periastron are missing")
    e_zero = self.e == 0
    self._speak(f"{sum(e_zero)} have eccentricities assumed to be 0")
    omega[e_zero] = 0 * u.deg

    return omega


@property
def b(self):
    """
    Transit impact parameter.
    (FIXME! split this into transit and occultation)
    """

    # pull out the actual values from the table
    b = self.standard["transit_b"].copy()

    # try to replace bad ones with NVK3L
    bad = np.isfinite(b) == False
    self._speak(f"{sum(bad)}/{len(self)} impact parameters are missing")

    # calculate from the period and the stellar mass
    a_over_rs = self.a_over_rs[bad]
    i = self.standard["inclination"][bad]
    e = self.e[bad]
    omega = self.omega[bad]
    b[bad] = a_over_rs * np.cos(i) * ((1 - e**2) / (1 + e * np.sin(omega)))

    # report those that are still bad
    stillbad = np.isfinite(b) == False
    self._speak(f"{sum(stillbad)}/{len(self)} are still missing after using i")

    return b


# the 1360 W/m^2 that Earth receives from the Sun
earth_insolation = (1 * u.Lsun / 4 / np.pi / u.AU**2).to(u.W / u.m**2)


@property
def insolation(self):
    """
    The insolation the planet receives, in W/m^2.
    """

    # calculate the average insolation the planet receives
    insolation = self.stellar_luminosity / 4 / np.pi / self.semimajoraxis**2
    return insolation.to(u.W / u.m**2)


@property
def insolation_uncertainty(self):
    """
    The insolation the planet receives, in W/m^2.
    """

    # calculate the average insolation the planet receives
    dinsolation_dluminosity = 1 / 4 / np.pi / self.semimajoraxis**2
    dinsolation_dsemimajor = (
        -2 * self.stellar_luminosity / 4 / np.pi / self.semimajoraxis**3
    )
    L_uncertainty = self.get_uncertainty("stellar_luminosity")
    a_uncertainty = self.get_uncertainty("semimajoraxis")
    insolation_uncertainty = (
        dinsolation_dluminosity**2 * L_uncertainty**2
        + dinsolation_dsemimajor**2 * a_uncertainty**2
    ) ** 0.5
    return insolation_uncertainty.to(u.W / u.m**2)


@property
def relative_insolation(self):
    """
    The insolation the planet receives, relative to Earth.
    """
    return self.insolation / self.earth_insolation


@property
def relative_insolation_uncertainty(self):
    """
    The insolation the planet receives, relative to Earth.
    """
    return self.insolation_uncertainty / self.earth_insolation


@property
def log_relative_insolation(self):
    return np.log10(self.relative_insolation)


@property
def relative_cumulative_xuv_insolation(self):
    """
    A *very very very* approximate estimate for the cumulative XUV flux (J/m**2)
    felt by a planet over its lifetime. It comes from Zahnle + Catling (2017) Equation 27,
    where they say they did integrals over the Lammer et al. (2009) XUV flux relations.
    This effectively assumes that the early times dominate, so the time integral doesn't
    depend (?!?) on the age of the system. It's very rough!
    """
    xuv_proxy = (self.stellar_luminosity / u.Lsun) ** -0.6
    return self.relative_insolation * xuv_proxy


@property
def teq(self):
    """
    The equilibrium temperature of the planet.
    """
    f = self.insolation
    sigma = con.sigma_sb
    A = 1
    return ((f * A / 4 / sigma) ** (1 / 4)).to(u.K)


@property
def planet_luminosity(self):
    """
    The bolometric luminosity of the planet (assuming zero albedo).
    """
    return (self.teq**4 * con.sigma_sb * 4 * np.pi * self.radius**2).to(u.W)


@property
def transit_depth(self):
    """
    The depth of the transit
    (FIXME, clarify if this is 1.5-3.5 or what)
    """

    # pull out the actual values from the table
    d = self.standard["transit_depth"].copy()

    # try to replace bad ones with NVK3L
    bad = np.isfinite(d) == False
    self._speak(f"{sum(bad)}/{len(self)} transit depths are missing")

    Rp = self.radius[bad]
    Rs = self.stellar_radius[bad]

    d[bad] = (Rp / Rs).decompose() ** 2

    # report those that are still bad
    stillbad = np.isfinite(d) == False
    self._speak(f"{sum(stillbad)}/{len(self)} are still missing after Rp/Rs")

    return d


@property
def transit_duration(self):
    """
    The duration of the transit
    (FIXME, clarify if this is 1.5-3.5 or what)
    """

    with warnings.catch_warnings():
        warnings.simplefilter("ignore")

        # pull out the actual values from the table
        d = self.standard["transit_duration"].copy()

        # try to replace bad ones with NVK3L
        bad = np.isfinite(d) == False
        self._speak(f"{sum(bad)}/{len(self)} transit durations are missing")

        P = self.period[bad]
        a_over_rs = self.a_over_rs[bad]
        b = self.impact_parameter[bad]

        T0 = P / np.pi / a_over_rs
        T = T0 * np.sqrt(1 - b**2)

        e = self.e[bad]
        omega = self.omega[bad]
        factor = np.sqrt(1 - e**2) / (1 + e * np.sin(omega))

        d[bad] = (T * factor).to(u.day)

        # report those that are still bad
        stillbad = np.isfinite(d) == False
        self._speak(f"{sum(stillbad)}/{len(self)} are still missing after P, a/R*, b")

        return d


@property
def kludge_mass(self):
    """
    Have a safe way to calculate the mass of planets,
    that fills in gaps as necessary. Basic strategy:

        First from table.
        Then from msini.
    """

    # pull out the actual values from the table
    M = self.standard["mass"].copy()

    # try to replace bad ones with NVK3L
    bad = np.isfinite(M) == False
    self._speak(f"{sum(bad)}/{len(self)} masses are missing")

    # estimate from the msini
    try:
        M[bad] = self.msini[bad]
    except (KeyError, AssertionError, AtlasError, AttributeError):
        pass

    # replace those that are still bad with the a/R*
    stillbad = np.isfinite(M) == False
    self._speak(f"{sum(stillbad)}/{len(self)} are still missing after msini")

    return M


@property
def kludge_radius(self):
    """
    Have a safe way to calculate the radii of planets,
    that fills in gaps as necessary. Basic strategy:

        First from table.
        Then from mass, via Chen & Kipping (2017).
    """

    # pull out the actual values from the table
    R = self.standard["radius"].copy()

    # try to replace bad ones with NVK3L
    bad = np.isfinite(R) == False
    self._speak(f"{sum(bad)}/{len(self)} radii are missing")

    # estimate from Chen and Kipping
    try:
        M = self.kludge_mass
        R[bad] = estimate_radius(M[bad])
    except (KeyError, AssertionError, AtlasError, AttributeError):
        pass

    # replace those that are still bad with the a/R*
    stillbad = np.isfinite(R) == False
    self._speak(
        f"{sum(stillbad)}/{len(self)} are still missing after Chen & Kipping (2017)"
    )

    return R


@property
def kludge_age(self):
    """
    Have a safe way to calculate the age of planets,
    that fills in gaps as necessary. Basic strategy:

        First from table.
        Then assume 5 Gyr.
    """

    # pull out the actual values from the table
    age = self.standard["stellar_age"].copy()

    # try to replace bad ones with NVK3L
    bad = np.isfinite(age) == False
    self._speak(f"{sum(bad)}/{len(self)} ages are missing")

    # estimate from the msini
    try:
        age[bad] = 5 * u.Gyr
    except (KeyError, AssertionError, AtlasError, AttributeError):
        pass

    # replace those that are still bad with the a/R*
    stillbad = np.isfinite(age) == False
    self._speak(
        f"{sum(stillbad)}/{len(self)} are still missing after blindly assuming 5Gyr for missing ages"
    )

    return age


@property
def surface_gravity(self):
    """
    (FIXME) -- make an assumption for planets without masses
    """

    G = con.G
    M = self.mass
    R = self.radius

    g = (G * M / R**2).to("m/s**2")
    return g


@property
def density(self):
    """
    The density of the planet.
    """
    mass = self.mass
    volume = 4 / 3 * np.pi * (self.radius) ** 3
    return (mass / volume).to("g/cm**3")


@property
def escape_velocity(self):
    """
    The escape velocity of the planet.
    """
    G = con.G
    M = self.mass
    R = self.radius
    return np.sqrt(2 * G * M / R).to("km/s")


@property
def orbital_velocity(self):
    return (2 * np.pi * self.semimajoraxis / self.period).to("km/s")


@property
def impact_velocity(self):
    return np.sqrt(self.orbital_velocity**2 + self.escape_velocity**2)


@property
def escape_parameter(self):
    """
    The Jeans atmospheric escape parameter for atomic hydrogen,
    at the equilibrium temperature of the planet.
    """
    k = con.k_B
    T = self.teq
    mu = 1
    m_p = con.m_p
    G = con.G
    M = self.mass
    R = self.radius

    e_thermal = k * T
    e_grav = G * M * m_p / R
    return (e_grav / e_thermal).decompose()


def scale_height(self, mu=2.32):
    """
    The scale height of the atmosphere, at equilibrium temperature.
    """
    k = con.k_B
    T = self.teq
    m_p = con.m_p
    g = self.surface_gravity
    return (k * T / mu / m_p / g).to("km")
