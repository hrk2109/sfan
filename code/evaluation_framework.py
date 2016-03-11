"""evaluation_framework.py -- All that is needed to evaluate feature selection algorithms."""

import numpy as np
import sklearn
import subprocess 



def consistency_index(sel1, sel2, num_features):
    """ Compute the consistency index between two sets of features.

    Parameters
    ----------
    sel1: set
        First set of indices of selected features
    sel2: set
        Second set of indices of selected features
    num_features: int
        Total number of features

    Returns
    -------
    cidx: float
        Consistency index between the two sets.

    Reference
    ---------
    Kuncheva, L.I. (2007). A Stability Index for Feature Selection.
    AIAC, pp. 390--395.
    """
    observed = float(len(sel1.intersection(sel2)))
    expected = len(sel1) * len(sel2) / float(num_features)
    maxposbl = float(min(len(sel1), len(sel2)))
    cidx = 0.
    # It's 0 and not 1 as expected if num_features == len(sel1) == len(sel2) => observed = n
    # Because "take everything" and "take nothing" are trivial solutions we don't want to select
    if expected != maxposbl:
        cidx = (observed - expected) / (maxposbl - expected)
    return cidx


def consistency_index_k(sel_list, num_features):
    """ Compute the consistency index between more than 2 sets of features.

    This is done by averaging over all pairwise consistency indices.

    Parameters
    ----------
    sel_list: list of lists
        List of k lists of indices of selected features
    num_features: int
        Total number of features

    Returns
    -------
    cidx: float
        Consistency index between the k sets.

    Reference
    ---------
    Kuncheva, L.I. (2007). A Stability Index for Feature Selection.
    AIAC, pp. 390--395.
    """
    print "*********************** sel_list  = \n", sel_list
    cidx = 0.

    for k1, sel1 in enumerate(sel_list[:-1]):
        # sel_list[:-1] to not take into account the last list.
        # avoid a problem with sel_list[k1+1:] when k1 is the last element,
        # that give an empty list overwise
        # the work is done at the second to last element anyway
        print "=========="
        print "k1 = ",k1, "sel_list[k1+1:]", sel_list[k1+1:]
        for sel2 in sel_list[k1+1:]:
            print sel1, sel2
            cidx += consistency_index(set(sel1), set(sel2), num_features)

    cidx = 2. / (len(sel_list) * (len(sel_list) - 1)) * cidx

    return cidx


def run_sfan(num_tasks, network_fname, weights_fnames, params):
    """ Run single task sfan (on each task).

    Arguments
    ---------
    num_tasks: int
        Number of tasks. 
    network_fname: filename
        Path to the network file.
    weights_fnames: list of filenames
        List of paths to the network nodes files (one per task).
    params: string
        Hyperparameters, in the '-l <lambda> -e <eta> -m <mu>' format.

    Returns
    -------
    sel_list: list of lists
        For each task, a list of selected features, as indices,
        STARTING AT 0.
    """
    # Ideally, I'd do the following:
    # sfan_solver = Sfan(num_tasks, network_fname, weights_fname,
    #                    lbd, eta, 0, precision_fname)
    # tt = sfan_solver.create_dimacs()
    # sfan_solver.run_maxflow()

    # But because cython output to screen is NOT caught by sys.stdout, 
    # we need to run this externally
    argum = ['python', 'multitask_sfan.py',
             '--num_tasks', str(num_tasks),
             '--networks', network_fname,
             '--node_weights']
    argum.extend(weights_fnames)
    argum.extend(params.split())
    argum.extend(['-m', '0'])

    p = subprocess.Popen(argum, stdout=subprocess.PIPE)
    p_out = p.communicate()[0].split("\n")[2:2+num_tasks]

    # Process the output to get lists of selected
    # features
    sel_list = [[(int(x)-1) for x in line.split()] for line in p_out]

    if not sel_list :
        print "returned sel_list empty !! param = ", params
        import pdb ; pdb.set_trace()

    return sel_list
                 

def run_msfan_nocorr(num_tasks, network_fname, weights_fnames, params):
    """ Run multitask sfan (no precision matrix).

    Arguments
    ---------
    num_tasks: int
        Number of tasks. 
    network_fname: filename
        Path to the network file.
    weights_fnames: list of filenames
        List of paths to the network nodes files (one per task).
    params: string
        Hyperparameters, in the '-l <lambda> -e <eta> -m <mu>' format.

    Returns
    -------
    sel_list: list of lists
        For each task, a list of selected features, as indices,
        STARTING AT 0.
    """
    argum = ['python', 'multitask_sfan.py',
             '--num_tasks', str(num_tasks),
             '--networks', network_fname,
             '--node_weights']
    argum.extend(weights_fnames)
    argum.extend(params.split())

    p = subprocess.Popen(argum, stdout=subprocess.PIPE)

    p_out = p.communicate()[0].split("\n")[3:3+num_tasks]

    # Process the output to get lists of selected features
    sel_list = [[(int(x)-1) for x in line.split()] for line in p_out]

    if not sel_list :
        print "returned sel_list empty !! param = ", params
        import pdb ; pdb.set_trace()

    return sel_list
                 

def run_msfan(num_tasks, network_fname, weights_fnames, precision_fname, params):
    """ Run multitask sfan.

    Arguments
    ---------
    num_tasks: int
        Number of tasks. 
    network_fname: filename
        Path to the network file.
    weights_fnames: list of filenames
        List of paths to the network nodes files (one per task).
    precision_fname: filename
        Path to the matrix of precision (similarity) of tasks.
    params: string
        Hyperparameters, in the '-l <lambda> -e <eta> -m <mu>' format.

    Returns
    -------
    sel_list: list of lists
        For each task, a list of selected features, as indices,
        STARTING AT 0.
    """
    argum = ['python', 'multitask_sfan.py',
             '--num_tasks', str(num_tasks),
             '--networks', network_fname,
             '--node_weights']
    argum.extend(weights_fnames)
    argum.extend(['--precision_matrix', precision_fname])
    argum.extend(params.split())
    print " ".join(argum)

    p = subprocess.Popen(argum, stdout=subprocess.PIPE)

    p_out = p.communicate()[0].split("\n")[3:3+num_tasks]

    # Process the output to get lists of selected features
    sel_list = [[(int(x)-1) for x in line.split()] for line in p_out]

    if not sel_list :
        print "returned sel_list empty !! param = ", params
        import pdb ; pdb.set_trace()

    return sel_list
                 

def get_optimal_parameters_from_dict(selected_dict, num_features):
    """ Find optimal parameters from dictionary of selected features

    Arguments
    ---------
    selected_dict: dictionary
        keys = parameters
        values = dictionary
            keys = task index
            values = list of list of selected features (for each subsample)
    num_features: int
        Total number of features

    Returns
    -------
    opt_params: string
        Optimal parameters, leading to highest consistency index.
    """
    opt_params = ''
    opt_cindex = 0
    for (params, selected_dict_p) in selected_dict.iteritems():
        for (task_idx, sel_list) in selected_dict_p.iteritems():
            cidx = consistency_index_k(sel_list, num_features)
            if cidx > opt_cindex:
                opt_cindex = cidx
                opt_params = params
    return opt_params


def run_ridge_selected(selected_features, genotype_fname, phenotype_fname,
                       tr_indices, te_indices, output_fname):
    """ Run a ridge-regression using only the selected features.

    Arguments
    ---------
    selected_features: list
        List of indices of selected features.
    genotype_fname: filename
        Path to genotype data.
    phenotype_fname: filename
        Path to phenotype data.
    tr_indices: list
        List of training indices.
    te_indices: list
        List of test indices.                    
    output_fname: filename
        Path to file where to write list of predictions on the test set.

    Side effects
    ------------
    Write predictions on the test set to output_fname
    """
    # TODO: Read the data

    # Instantiate a ridge regression
    model = sklearn.linear_model.RidgeCV()

    # Train the ridge regression on the training set
    model.fit(Xtr, ytr)

    # Make predictions on the test set
    preds = model.predict(Xte)

    # Save predictions
    np.savetxt(output_fname, preds, fmt='%.3e')


def compute_ppv_sensitivity(causal_fname, selected_list):
    """ Compute PPV and sensitivity (true positive rate) for all tasks.

    Arguments
    ---------
    causal_fname: filename
        File containing causal features (one line per task, space-separated).
    selected_list: list of lists
        List of lists of selected features (one list per task).

    Returns
    -------
    ppv_list: list
        List of PPV (task per task).
    tpr_list: list
        List of sensitivities (TPR), task per task.
    """
    # TODO (use sklearn.metrics)
    
    return ppv_list, tpr_list

    
class Framework(object):
    """ Setting up evaluation framework.

    Attributes
    ----------
    self.num_samples: int
        Number of samples.
    self.num_folds: int
        Number of cross-validation folds
    self.num_subsamples: int
        Number of subsamples (to evaluate stability)
    self.xp_indices: dictionary
        fold_idx:{
            'trIndices': list of train indices,
            'teIndices': list of test indices,
            'ssIndices': list of list of subsample indices}

    """
    def __init__(self, num_samples, num_folds, num_subsamples):
        """
        Parameters
        ----------
        num_samples: int
            Number of samples.
        num_folds: int
            Number of cross-validation folds
        num_subsamples: int
            Number of subsamples (to evaluate stability)
        """
        self.num_samples = num_samples
        self.num_folds = num_folds
        self.num_subsamples = num_subsamples
        self.xp_indices = {key: {'trIndices': None, 'teIndices':None, 'ssIndices':list()} for key in xrange(num_folds)}
        
    def compute_indices(self, seed=None):
        """ Compute the cross-validation folds and subsample indices.

        Parameters
        ----------
        seed: {int, None}, optional
            random seed.
            Will always return the same with the same random seed.

        Modified attributes
        -------------------
        xp_indices: dictionary
            fold_idx:{
                'trIndices': list of train indices,
                'teIndices': list of test indices,
                'ssIndices': list of list of subsample indices}
        """

        # use sklearn.cross_validation
        from sklearn.cross_validation import KFold
        
        # Generate cross-validation indices
        kf = KFold(self.num_samples, n_folds=self.num_folds)
        for i, (train_index, test_index) in enumerate(kf):
            self.xp_indices[i]['trIndices'] = train_index.tolist()
            self.xp_indices[i]['teIndices'] = test_index.tolist()

            # For each train set, generate self.num_subsamples subsample sets of indices
            ss = KFold(self.num_samples, n_folds=self.num_folds)
            for train_index, test_index in ss:
                self.xp_indices[i]['ssIndices'].append(train_index.tolist())
        
    def save_indices(self, data_dir, simu_id):
        """ Save the cross-validation folds and subsample indices to files.

        Parameters
        ----------

        Generated files
        ---------------
        For each fold_idx:
            <data_dir>/<simu_id>.<fold_idx>.trIndices:
                Space-separated list of training indices.
            <data_dir>/<simu_id>.<fold_idx>.teIndices:
                Space-separated list of test indices.
            For each subsample_idx:
                <data_dir>/<simu_id>.<fold_idx>.<ss_idx>.ssIndices
                    Space-separated lists of subsample indices,
                    one line per list / subsample.
        """
        # use np.savetxt 