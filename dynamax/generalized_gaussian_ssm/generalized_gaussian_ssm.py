import chex
from typing import Callable
from jax import numpy as jnp
from dynamax.abstractions import SSM
import tensorflow_probability.substrates.jax as tfp
from tensorflow_probability.substrates.jax.distributions import MultivariateNormalFullCovariance as MVN

from jaxtyping import Array, Float, PyTree, Bool, Int, Num
from typing import Any, Dict, NamedTuple, Optional, Tuple, Union,  TypeVar, Generic, Mapping, Callable

from dynamax.nonlinear_gaussian_ssm.nonlinear_gaussian_ssm import PosteriorNLGSSMFiltered, PosteriorNLGSSMSmoothed, ParamsNLGSSM

tfd = tfp.distributions
tfb = tfp.bijectors

PosteriorGGSSMFiltered = PosteriorNLGSSMFiltered
PosteriorGGSSMSmoothed = PosteriorNLGSSMSmoothed


FnStateToState = Callable[[Float[Array, "state_dim"]], Float[Array, "state_dim"]]
FnStateAndInputToState = Callable[[Float[Array, "state_dim"], Float[Array, "input_dim"]], Float[Array, "state_dim"]]

FnStateToEmission = Callable[[Float[Array, "state_dim"]], Float[Array, "emission_dim"]]
FnStateAndInputToEmission = Callable[[Float[Array, "state_dim"], Float[Array, "input_dim"]], Float[Array, "emission_dim"]]

FnStateToEmission2 = Callable[[Float[Array, "state_dim"]], Float[Array, "emission_dim emission_dim"]]
FnStateAndInputToEmission2 = Callable[[Float[Array, "state_dim"], Float[Array, "input_dim"]], Float[Array, "emission_dim emission_dim"]]

# emission distribution takes a mean vector and covariance matrix and returns a distribution
EmissionDistFn = Callable[ [Float[Array, "state_dim"], Float[Array, "state_dim state_dim"]], tfd.Distribution]


@chex.dataclass
class ParamsGGSSM:
    """Container for GGSSM parameters. Differs from NLGSSM in terms of emission model."""

    initial_mean: Float[Array, "state_dim"]
    initial_covariance: Float[Array, "state_dim state_dim"]
    dynamics_function: Union[FnStateToState, FnStateAndInputToState]
    dynamics_covariance: Float[Array, "state_dim state_dim"]

    emission_mean_function: Union[FnStateToEmission, FnStateAndInputToEmission]
    emission_cov_function: Union[FnStateToEmission2, FnStateAndInputToEmission2]
    emission_dist: EmissionDistFn = MVN



class GeneralizedGaussianSSM(SSM):
    """
    General Gaussian State Space Model is defined as follows:
    p(z_t | z_{t-1}, u_t) = N(z_t | f(z_{t-1}, u_t), Q_t)
    p(y_t | z_t) = Pr(y_t | h(z_t, u_t), R(z_t, u_t))
    p(z_1) = N(z_1 | m, S)
    where z_t = hidden, y_t = observed, u_t = inputs (can be None),
    f = params.dynamics_function
    Q = params.dynamics_covariance 
    h = params.emission_mean_function
    R = params.emission_cov_function
    Pr = params.emission_dist
    m = params.initial_mean
    S = params.initial_covariance
    """

    def __init__(self, state_dim, emission_dim, input_dim=0):
        self.state_dim = state_dim
        self.emission_dim = emission_dim
        self.input_dim = 0

    @property
    def emission_shape(self):
        return (self.emission_dim,)

    @property
    def inputs_shape(self):
        return (self.input_dim,) if self.input_dim > 0 else None

    def initial_distribution(
        self,
        params: ParamsGGSSM, 
        inputs: Optional[Float[Array, "input_dim"]]=None
    ) -> tfd.Distribution:
        return MVN(params.initial_mean, params.initial_covariance)
    
    def transition_distribution(
        self,
        params: ParamsGGSSM, 
        state: Float[Array, "state_dim"],
        inputs: Optional[Float[Array, "input_dim"]]=None
    ) -> tfd.Distribution:
        f = params.dynamics_function
        if inputs is None:
            mean = f(state)
        else:
            mean = f(state, inputs)
        return MVN(mean, params.dynamics_covariance)

    def emission_distribution(
        self,
        params: ParamsGGSSM, 
        state: Float[Array, "state_dim"],
        inputs: Optional[Float[Array, "input_dim"]]=None
    ) -> tfd.Distribution:
        h = params.emission_mean_function
        R = params.emission_cov_function
        if inputs is None:
            mean = h(state)
            cov = R(state)
        else:
            mean = h(state, inputs)
            cov = R(state, inputs)
        return params.emission_dist(mean, cov)