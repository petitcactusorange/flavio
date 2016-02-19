import yaml
import pkgutil
from flavio.classes import *
import numpy as np
from math import sqrt

def _load(obj):
    """Read measurements from a YAML stream or file."""
    measurements = yaml.load(obj)
    for m_name, m_data in measurements.items():
        m = Measurement(m_name)
        for arg in ['inspire', 'hepdata', 'experiment', 'url']:
            if arg in m_data:
                setattr(m, arg, m_data[arg])
        if 'correlation' not in m_data:
            if isinstance(m_data['values'], list):
                for value_dict in m_data['values']:
                    # if "value" is a list, it contains the values of observable
                    # arguments (like q^2)
                    args = Observable.get_instance(value_dict['name']).arguments
                    args_num = [value_dict[a] for a in args]
                    constraints = constraints_from_string(value_dict['value'])
                    args_num.insert(0, value_dict['name'])
                    obs_tuple = tuple(args_num)
                    for constraint in constraints:
                        m.add_constraint([obs_tuple], constraint)
            else: # otherwise, 'values' is a dict just containing name: constraint_string
                for obs, value in m_data['values'].items():
                    constraints = constraints_from_string(value)
                    for constraint in constraints:
                        m.add_constraint([obs], constraint)
        else:
            observables = []
            central_values = []
            errors = []
            if isinstance(m_data['values'], list):
                for value_dict in m_data['values']:
                    # if "value" is a list, it contains the values of observable
                    # arguments (like q^2)
                    args = Observable.get_instance(value_dict['name']).arguments
                    args_num = [value_dict[a] for a in args]
                    error_dict = errors_from_string(value_dict['value'])
                    args_num.insert(0, value_dict['name'])
                    obs_tuple = tuple(args_num)
                    observables.append(obs_tuple)
                    central_values.append(error_dict['central_value'])
                    squared_error = 0.
                    for sym_err in error_dict['symmetric_errors']:
                        squared_error += sym_err**2
                    for asym_err in error_dict['asymmetric_errors']:
                        squared_error += asym_err[0]*asym_err[1]
                    errors.append(sqrt(squared_error))
            else: # otherwise, 'values' is a dict just containing name: constraint_string
                for obs, value in m_data['values'].items():
                    observables.append(obs)
                    error_dict = errors_from_string(value)
                    central_values.append(error_dict['central_value'])
                    squared_error = 0.
                    for sym_err in error_dict['symmetric_errors']:
                        squared_error += sym_err**2
                    for asym_err in error_dict['asymmetric_errors']:
                        squared_error += asym_err[0]*asym_err[1]
                        errors.append(sqrt(squared_error))
            correlation = _fix_correlation_matrix(m_data['correlation'], len(observables))
            covariance = np.outer(np.asarray(errors), np.asarray(errors))*correlation
            if not np.all(np.linalg.eigvals(covariance) > 0):
                # if the covariance matrix is not positive definite, try a dirty trick:
                # multiply all the correlations by 0.99.
                n_dim = len(correlation)
                correlation = (correlation - np.eye(n_dim))*0.99 + np.eye(n_dim)
                covariance = np.outer(np.asarray(errors), np.asarray(errors))*correlation
                # if it still isn't positive definite, give up.
                assert np.all(np.linalg.eigvals(covariance) > 0), "The covariance matrix is not positive definite!" + str(covariance)
            m.add_constraint(observables, MultivariateNormalDistribution(central_values, covariance))



def _fix_correlation_matrix(corr, n_dim):
    """In the input file, the correlation matrix can be specified as a list
    of lists containing only the upper right of the symmetric correlation
    matrix, e.g. [[1, 0.1, 0.2], [1, 0.3], [1, 0.05]]. This function builds the
    full matrix."""
    if n_dim == 2:
        # if the number of dimensions is just 2, the correlation could just
        # be given as a number
        try:
            float(corr)
        except ValueError:
            # if it's not a number, go on below
            pass
        else:
            # if it's a number, return the 2x2 matrix
            return  [[1, float(corr)], [float(corr), 1]]
    if not isinstance(corr, list):
        raise TypeError("Correlation matrix must be of type list")
    if len(corr) != n_dim:
        raise ValueError("The correlation matrix has inappropriate number of dimensions")
    corr_out = np.zeros((n_dim, n_dim))
    for i, line in enumerate(corr):
        if len(line) == n_dim:
            if line[i] != 1:
                raise ValueError("The correlation matrix must have 1.0 on the diagonal")
            corr_out[i] = line
        elif len(line) == n_dim - i:
            if line[0] != 1:
                raise ValueError("The correlation matrix must have 1.0 on the diagonal")
            corr_out[i,i:] = line
        else:
            raise ValueError("Correlation matrix not understood")
    if not np.allclose(corr_out, corr_out.T):
        # if the covariance is not symmetric, it is assumed that only the values above the diagonal are present.
        # then: M -> M + M^T - diag(M)
        corr_out = corr_out + corr_out.T - np.diag(np.diag(corr_out))
    return corr_out


def load(filename):
    """Read measurements from a YAML file."""
    with open(filename, 'r') as f:
        _load(f)

_load(pkgutil.get_data('flavio', 'data/measurements.yml'))