""" generate_data.py: Generate test data for multitask_sfan.
"""

import argparse
import logging
import numpy as np
import os
import tables as tb
import scipy.stats as st 
import sys

NUM_CAUSAL_TOTAL = 30 # total number of causal features
NUM_CAUSAL_EACH = 20 # how many of these features are causal for each task
MOD_SIZE = 15 # number of nodes in each fully connected module of the network.


class SyntheticDataGenerator(object):
    """ Class for the generation of synthetic data.

    Attributes
    ----------
    num_tasks: int
        Number of tasks.
    num_features: int
        Number of features.
    num_samples: int
        Number of samples
    root_dir: filename
        Path of the directory in which to save the simulated data.
    simu_id: string
        Name of the simulation, to be used to name files within args.root_dir.
    """
    def __init__(self, num_tasks, num_features, num_samples, root_dir, simu_id):
        """
        Parameters
        ----------
        num_tasks: int
            Number of tasks.
        num_features: int
            Number of features.
        num_samples: int
            Number of samples
        root_dir: filename
            Path of the directory in which to save the simulated data.
        simu_id: string
            Name of the simulation, to be used to name files within args.root_dir.
        """
        self.num_tasks = num_tasks
        self.num_features = num_features
        self.num_samples = num_samples
        self.root_dir = root_dir
        self.simu_id = simu_id

        # Create simulated data repository if it does not exist
        if not os.path.isdir(self.root_dir):
            logging.info("Creating %s\n" % self.root_dir)
            try: 
                os.makedirs(self.root_dir)
            except OSError:
                if not os.path.isdir(self.root_dir):
                    raise

    def generate_modular(self):
        """
        Generate synthetic data with a modular network and a genotype matrix
        made of random {0, 1, 2}.
        
        Generated files
        ---------------
        <root_dir>/<simu_id>.readme:
            README file describing the simulation paramters.
        <root_dir>/<simu_id>.task_similarities.txt:
            args.num_tasks x args.num_tasks matrix \Omega^{-1}
            of similarities between tasks.
        <root_dir>/<simu_id>.causal_features:
            args.num_tasks lists of NUM_CAUSAL_EACH causal features,
            chosen from the first NUM_CAUSAL_TOTAL features.
            One list per task. Indices start at 0.
        <root_dir>/<simu_id>.causal_weights:
            Lists of the weights given to the causal features,
            generated so as to respect the covariance structure given by Omega.
            One list per task, in the order of <simu_id>.causal_features.
        <root_dir>/<simu_id>.genotypes.txt:
            num_features x num_samples matrix of {0, 1, 2} (representing SNPs).
        <root_dir>/<simu_id>.network.dimacs:
            A modular network over the self.num_features features,
            with fully connected modules of size MOD_SIZE.
        For task_id in 0, ..., args.num_tasks:
            <root_dir>/<simu_id>.phenotype_<task_id>.txt:
                Phenotype vector (of size args.num_samples) for task <task_id>.
            <root_dir>/<simu_id>.scores_<task_id>.txt
                Node weights (of size args.num_features) for task <task_id>.
                Computed as Pearson correlation.
        """
        # Writing readme
        readme_f = '%s/%s.readme' % (self.root_dir, self.simu_id)
        with open(readme_f, 'w') as f:
            f.write("# Features generated by generate_data.generate_modular\n")
            f.write("%d\tfeatures\n" % self.num_features)
            f.write("%d\tsamples\n" % self.num_samples)
            f.write("%d\ttasks\n" % self.num_tasks)
            f.close()
        logging.info("README file created under %s\n" % readme_f)

        # Generate a matrix of similarities between tasks
        omega_inv = np.random.uniform(size = (self.num_tasks, self.num_tasks))
        omega_inv = omega_inv.transpose().dot(omega_inv)
        d = np.diag(omega_inv)
        d.shape = (self.num_tasks, 1)
        omega_inv = omega_inv / np.sqrt(d.dot(d.transpose()))

        # Save omega_inv to file
        fname = "%s/%s.task_similarities.txt" % (self.root_dir, self.simu_id)
        np.savetxt(fname, omega_inv, fmt='%.3f')
        logging.info("Precision matrix saved under %s\n" % fname)

        # Generate beta vectors that are correlated according to omega
        # Trick: cov(Ax) = Acov(x)A'
        omega = np.linalg.inv(omega_inv)
        L = np.linalg.cholesky(omega) # i.e. LL' = omega
        b = np.random.normal(size=(self.num_tasks, NUM_CAUSAL_TOTAL))
        beta = L.dot(b)

        # For each task, keep the NUM_CAUSAL_EACH features with highest weight
        # as causal;
        # drop the weight of the others to 0.
        causal_features = []
        for k in range(self.num_tasks):
            b = [x for x in beta[k, :]]
            b.sort()
            causal_features.append(np.where(beta[k, :] >= b[-NUM_CAUSAL_EACH])[0])
            beta[k, np.where(beta[k, :] < b[-NUM_CAUSAL_EACH])[0]] = 0.

        # Save causal features to file
        fname = "%s/%s.causal_features.txt"  % (self.root_dir, self.simu_id)
        np.savetxt(fname, causal_features, fmt='%d')
        logging.info("Causal features saved under %s\n" % fname)

        # Save beta to file
        fname = "%s/%s.causal_weights.txt"  % (self.root_dir, self.simu_id)
        np.savetxt(fname, beta)
        logging.info("Causal weights saved under %s\n" % fname)

        # Generate genotypes
        # Create PyTables structure for X transposed (so as to access rows, not cols)
        fname = "%s/%s.genotypes.txt"  % (self.root_dir, self.simu_id)
        with tb.open_file(fname, 'w') as h5f:
            filters = tb.Filters(complevel=5, complib='blosc')
            Xtr = h5f.create_carray(h5f.root, 'Xtr', tb.Int8Atom(),
                                    shape=(self.num_features, self.num_samples))
            for row in xrange(self.num_features):
                Xtr[row, :] = np.random.random_integers(0, high=2, size=self.num_samples)
            h5f.close()
        logging.info("Genotypes saved under %s\n" % fname)

        # generate phenotypes and Pearson scores, and save to file
        with tb.open_file(fname, 'r') as h5f:
            Xtr = h5f.root.Xtr
            for task_idx in range(self.num_tasks):
                y = Xtr[:NUM_CAUSAL_TOTAL,:].transpose().dot(beta.transpose()[:,
                                                                              task_idx])
                y += np.random.normal(scale=0.1, size=(self.num_samples, ))
                fname = "%s/%s.phenotype_%d.txt" % (self.root_dir,
                                                    self.simu_id, task_idx)
                np.savetxt(fname, y, fmt='%.3f')
                logging.info("Phenotype for task %d saved under %s\n" % (task_idx,
                                                                         fname))

                # compute feature-phenotype correlations
                r2 = [st.pearsonr(Xtr[feat_idx, :].transpose(), y)[0]**2 \
                      for feat_idx in range(self.num_features)]
                fname = "%s/%s.scores_%d.txt" % (self.root_dir, self.simu_id, task_idx)
                np.savetxt(fname, r2, fmt='%.3e')
                logging.info("Node weights for task %d saved under %s\n" % (task_idx,
                                                                            fname))


        # Generate network in dimacs format
        # Careful: node indices must start at 1
        num_modules = self.num_features / MOD_SIZE
        num_edges = MOD_SIZE * (MOD_SIZE - 1) * num_modules + \
                    2 * (num_modules - 1) + 2 * (self.num_features - \
                                                 MOD_SIZE * num_modules)
        dimacs_f = '%s/%s.network.dimacs' % (self.root_dir, self.simu_id)
        with open(dimacs_f, 'w') as g:
            g.write("p max %d %d\n" % ((self.num_features), num_edges))

            # create fully connected modules of size MOD_SIZE
            # connect each to the next one
            for mod_idx in range(num_modules):
                x = mod_idx * MOD_SIZE
                if mod_idx > 0:
                    g.write("a %d %d 1\n" % ((x+1), (x))) # connect to previous module
                for x_idx1 in range(MOD_SIZE):
                    for x_idx2 in range(MOD_SIZE):
                        if x_idx1 != x_idx2:
                            g.write("a %d %d 1\n" % ((x+x_idx1+1), (x+x_idx2+1)))
                if (x+MOD_SIZE) < self.num_features: # connect to next module
                    g.write("a %d %d 1\n" % ((x+MOD_SIZE), (x+MOD_SIZE+1)))
            # connect each of the remaining nodes to its neighbor
            for x_idx in range(x+MOD_SIZE+1, self.num_features):
                g.write("a %d %d 1\n" % ((x_idx), (x_idx-1)))
                g.write("a %d %d 1\n" % ((x_idx), (x_idx+1)))
            # last connection (mirror from the previous one)
            g.write("a %d %d 1\n" % ((x_idx+1), (x_idx)))

            g.close()
        logging.info("Network saved under %s\n" % fname)




def main():
    """
    Given a number of samples (n), a number of features (m), and a number of tasks (k)
    generate
    - a modular network of size m, with fully connected modules of size MOD_SIZE;
    - a genotype matrix X of size n x m (as random integers between 0 and 2);
    - a kxk similarity matrix $\Omega^{-1}$ between tasks;
    - k lists of NUM_CAUSAL_EACH causal features, chosen from the first
    NUM_CAUSAL_TOTAL features,
    with corresponding weights (beta) generated so as to respect the covariance
    structure given by $\Omega$;    
    - the corresponding k phenotypes and vectors of node weights.

    Arguments
    ---------
    args.num_tasks: int
        Number of tasks.
    args.num_features: int
        Number of features.
    args.num_samples: int
        Number of samples
    args.root_dir: filename
        Path of the directory in which to save the simulated data.
    args.simu_id: string
        Name of the simulation, to be used to name files within args.root_dir.

    Generated files
    ---------------
    <root_dir>/<simu_id>.readme:
        README file describing the simulation paramters
    <root_dir>/<simu_id>.task_similarities.txt:
        Matrix of precision between tasks
    <root_dir>/<simu_id>.causal_features:
        Lists of causal features.
        One list per task. Indices start at 0.
    <root_dir>/<simu_id>.causal_weights:
        Lists of the weights given to the causal features.
        One list per task. Same order as in <root_dir>/<simu_id>.causal_features.
    <root_dir>/<simu_id>.genotypes.txt:
        num_features x num_samples matrix of {0, 1, 2} (representing SNPs).
    <root_dir>/<simu_id>.network.dimacs:
        Network over the features.
    For task_id in 0, ..., args.num_tasks:
        <root_dir>/<simu_id>.phenotype_<task_id>.txt:
            Phenotype (outcome) vector (of size args.num_samples) for task <task_id>.
        <root_dir>/<simu_id>.scores_<task_id>.txt
            Node weights (of size args.num_features) for task <task_id>.
            Computed as Pearson correlation.
    
    For file format specifications, see README.md

    Example
    -------
    $ python generate_data.py -k 3 -m 1000 -n 50 ../data/simu_synth_01 simu_01 -v
    """
    # Get arguments values
    parser = argparse.ArgumentParser(description="Generate data for multitask_sfan",
                                     add_help=True)
    parser.add_argument("-k", "--num_tasks", help="Number of tasks", type=int)
    parser.add_argument("-m", "--num_features", help="Number of features", type=int)
    parser.add_argument("-n", "--num_samples", help="Number of samples", type=int)
    parser.add_argument("-v", "--verbose", help="Turn on more detailed info log",
                        action='store_true')
    parser.add_argument("root_dir", help="Simulated data directory")
    parser.add_argument("simu_id", help="Simulation name")
    args = parser.parse_args()

    # Check arguments integrity
    try:
        assert(args.num_tasks >= 1)
    except AssertionError:
        logging.error("There must be at least one task specified.\n")
        logging.error("Use --help for help.\n")
        sys.exit(-1)

    try:
        assert(args.num_features >= NUM_CAUSAL_TOTAL)
    except AssertionError:
        logging.error("The number of features must be larger than " + \
                      "NUM_CAUSAL_TOTAL (%d).\n" % NUM_CAUSAL_TOTAL)
        logging.error("Use --help for help.\n")
        sys.exit(-1)

    try:
        assert(args.num_samples > 0)
    except AssertionError:
        logging.error("The number of samples must be strictly positive\n")
        logging.error("Use --help for help.\n")
        sys.exit(-1)

    # Verbose
    if args.verbose:
        logging.basicConfig(format="[%(levelname)s] %(message)s", level=logging.DEBUG)
        logging.info("Verbose output.")
    else:
        logging.basicConfig(format="%[(levelname)s] %(message)s")

    # Instantiate data generator
    data_gen = SyntheticDataGenerator(args.num_tasks, args.num_features,
                                      args.num_samples,
                                      args.root_dir, args.simu_id)

    # Generate modular data
    data_gen.generate_modular()
        

if __name__ == "__main__":
    main()
