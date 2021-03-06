
import os
base_dir = os.path.dirname(__file__)

import sys
sys.path.extend([os.path.join(base_dir, '../../..')])

from HetMan.features.variants import MuType
from HetMan.features.cohorts import MutCohort
from HetMan.predict.classifiers import Lasso

import numpy as np
from sklearn.metrics.pairwise import cosine_similarity
from itertools import product
from itertools import combinations as combn

import pickle
import synapseclient


def main(argv):
    """Runs the experiment."""

    # gets the directory where output will be saved and the name of the TCGA
    # cohort under consideration, loads the list of gene sub-variants 
    print(argv)
    out_dir = os.path.join(base_dir, 'output', argv[0], argv[1])
    coh_lbl = 'TCGA-{}'.format(argv[0])
    mtype_list = pickle.load(
        open(os.path.join(out_dir, 'tmp', 'mtype_list.p'), 'rb'))

    # loads the expression data and gene mutation data for the given TCGA
    # cohort, with the training/testing cohort split defined by the
    # cross-validation id for this task
    syn = synapseclient.Synapse()
    syn.login()

    for cv_id in range(5):
        cdata = MutCohort(syn, cohort=coh_lbl, mut_genes=[argv[1]],
                          mut_levels=['Gene', 'Form'],
                          cv_seed=(cv_id + 3) * 19)

        cna_list = [cna_mtype for cna_mtype in
                    [MuType({('Gene', argv[1]): {
                        ('Form', 'CNA_{}'.format(cna)): None}})
                        for cna in (-2,-1,1,2)]
                    if len(cna_mtype.get_samples(cdata.train_mut)) >= 12]

        if len(MuType({('Gene', argv[1]): {
                ('Form', 'CNA_-2'): None
                    }}).get_samples(cdata.train_mut)) > 0:
            cna_list.extend([MuType(
                {('Gene', argv[1]): {
                    ('Form', ('CNA_-1', 'CNA_-2')): None}})])

        if len(MuType({('Gene', argv[1]): {
                ('Form', 'CNA_2'): None
                    }}).get_samples(cdata.train_mut)) > 0:
            cna_list.extend([MuType(
                {('Gene', argv[1]): {
                    ('Form', ('CNA_1', 'CNA_2')): None}})])

        # gets the mutation type representing all of the mutations for the given
        # gene, finds which samples have these mutations in the training and
        # testing cohorts
        base_mtype = MuType({('Gene', argv[1]): None})
        tp53_train_samps = base_mtype.get_samples(cdata.train_mut)
        tp53_test_samps = base_mtype.get_samples(cdata.test_mut)

        out_stat = {mtype: None for mtype in cna_list}
        out_coef = {mtype: None for mtype in cna_list}
        out_acc = {mtype: None for mtype in cna_list}
        out_pred = {mtype: None for mtype in cna_list}

        out_cross = {mtypes: [None, None, None, None]
                     for mtypes in product(cna_list, mtype_list)}
        out_mutex = {tuple(sorted(mtypes)): None
                     for mtypes in product(cna_list, mtype_list)}

        for mtype in cna_list:
            ex_train = tp53_train_samps - mtype.get_samples(cdata.train_mut)
            ex_test = tp53_test_samps - mtype.get_samples(cdata.test_mut)

            test_stat = cdata.test_pheno(mtype)
            out_stat[mtype] = np.where(test_stat)
            print(np.sum(test_stat))

            clf = Lasso()
            clf.tune_coh(cdata, mtype, tune_splits=4,
                         test_count=16, parallel_jobs=8,
                         exclude_genes=[argv[1]], exclude_samps=ex_train)
            print(clf)

            clf.fit_coh(cdata, mtype,
                        exclude_genes=[argv[1]], exclude_samps=ex_train)
            out_coef[mtype] = {gene: val for gene, val in
                               clf.get_coef().items() if val != 0}

            out_acc[mtype] = clf.eval_coh(
                cdata, mtype, exclude_genes=[argv[1]], exclude_samps=ex_test)
            out_pred[mtype] = np.array(
                clf.predict_test(cdata, exclude_genes=[argv[1]]))

            for other_mtype in mtype_list:
                other_stat = cdata.test_pheno(other_mtype)

                none_which = ~test_stat & ~other_stat
                if np.sum(none_which) >= 5:
                    out_cross[mtype, other_mtype][0] = np.mean(
                        out_pred[mtype][none_which])

                other_which = ~test_stat & other_stat
                if np.sum(other_which) >= 5:
                    out_cross[mtype, other_mtype][1] = np.mean(
                        out_pred[mtype][other_which])

                cur_which = test_stat & ~other_stat
                if np.sum(cur_which) >= 5:
                    out_cross[mtype, other_mtype][2] = np.mean(
                        out_pred[mtype][cur_which])

                both_which = test_stat & other_stat
                if np.sum(both_which) >= 5:
                    out_cross[mtype, other_mtype][3] = np.mean(
                        out_pred[mtype][both_which])

                out_mutex[mtype, other_mtype] = cdata.mutex_test(
                    mtype, other_mtype)

        # saves classifier results to file
        out_file = os.path.join(out_dir, 'results',
                                'out__cv-{}_task-cna.p'.format(cv_id))
        pickle.dump({'Stat': out_stat, 'Coef': out_coef, 'Mutex': out_mutex,
                     'Acc': out_acc, 'Pred': out_pred, 'Cross': out_cross},
                    open(out_file, 'wb'))


if __name__ == "__main__":
    main(sys.argv[1:])

