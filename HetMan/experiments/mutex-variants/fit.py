
import sys
sys.path.extend(['/home/exacloud/lustre1/CompBio/mgrzad/bergamot/'])

import os
base_dir = os.path.dirname(__file__)

import numpy as np
import pickle
from functools import reduce

from HetMan.features.cohorts import VariantCohort
from HetMan.predict.classifiers import Lasso
from sklearn.metrics.pairwise import cosine_similarity

import synapseclient


def main(argv):
    """Runs the experiment."""

    print(argv)
    out_dir = os.path.join(base_dir, 'output', argv[0])
    coh_lbl = 'TCGA-{}'.format(argv[0])
    mutex_dict = pickle.load(
        open(os.path.join(out_dir, 'tmp', 'mutex_dict.p'), 'rb'))

    common_genes = reduce(lambda x,y: x | y,
                          [set([[k for k,v in mtype1][0]])
                           | set([[k for k,v in mtype2][0]])
                           for (mtype1, mtype2), _ in mutex_dict])

    print('loading mutations for {} genes...'.format(len(common_genes)))
    syn = synapseclient.Synapse()
    syn.login()
    cdata = VariantCohort(syn, cohort=coh_lbl, mut_genes=common_genes,
                          mut_levels=['Gene', 'Form', 'Location'],
                          cv_seed=99)
    print('TCGA-Z7-A8R6-01A' in cdata.test_samps)

    out_acc = {mtypes: [0,0] for mtypes, _ in mutex_dict}
    out_stat = {mtypes: [[0,0,0,0], [0,0,0,0]] for mtypes, _ in mutex_dict}
    out_dist = {mtypes: 0 for mtypes, _ in mutex_dict}
    out_coef = {mtypes: [None, None] for mtypes, _ in mutex_dict}

    for i, ((mtype1, mtype2), mutex) in enumerate(mutex_dict):
        if i % 20 == (int(argv[-1]) - 1):
            print('{}  +  {}'.format(mtype1, mtype2))

            gn1 = [k for k,v in mtype1][0]
            gn2 = [k for k,v in mtype2][0]
            ex_samps1 = mtype2.get_samples(cdata.train_mut)
            ex_samps2 = mtype1.get_samples(cdata.train_mut)

            stat1 = cdata.test_pheno(mtype1)
            stat2 = cdata.test_pheno(mtype2)
            print('{} --- {} --- {}'.format(
                np.sum(stat1 & ~stat2), np.sum(~stat1 & stat2),
                np.sum(stat1 & stat2)
                ))

            clf1 = Lasso()
            clf1.tune_coh(cdata, mtype1, tune_splits=4,
                          test_count=16, parallel_jobs=8,
                          exclude_genes=[gn1, gn2], exclude_samps=ex_samps1)
            clf1.fit_coh(cdata, mtype1,
                         exclude_genes=[gn1, gn2], exclude_samps=ex_samps1)

            out_acc[(mtype1, mtype2)][0] = clf1.eval_coh(
                cdata, mtype1,
                exclude_genes=[gn1, gn2],
                exclude_samps=mtype2.get_samples(cdata.test_mut)
                )

            test1 = np.array(
                clf1.predict_test(cdata, exclude_genes=[gn1, gn2]))

            out_stat[(mtype1, mtype2)][0][0] = np.mean(test1[~stat1 & ~stat2])
            out_stat[(mtype1, mtype2)][0][1] = np.mean(test1[~stat1 & stat2])
            out_stat[(mtype1, mtype2)][0][2] = np.mean(test1[stat1 & ~stat2])

            clf2 = Lasso()
            clf2.tune_coh(cdata, mtype2, tune_splits=4,
                          test_count=16, parallel_jobs=8,
                          exclude_genes=[gn1, gn2], exclude_samps=ex_samps2)
            clf2.fit_coh(cdata, mtype2,
                         exclude_genes=[gn1, gn2], exclude_samps=ex_samps2)

            out_acc[(mtype1, mtype2)][1] = clf2.eval_coh(
                cdata, mtype2,
                exclude_genes=[gn1, gn2],
                exclude_samps=mtype1.get_samples(cdata.test_mut)
                )

            test2 = np.array(
                clf2.predict_test(cdata, exclude_genes=[gn1, gn2]))

            out_stat[(mtype1, mtype2)][1][0] = np.mean(test2[~stat1 & ~stat2])
            out_stat[(mtype1, mtype2)][1][1] = np.mean(test2[stat1 & ~stat2])
            out_stat[(mtype1, mtype2)][1][2] = np.mean(test2[~stat1 & stat2])

            if np.sum(stat1 & stat2) > 0:
                out_stat[(mtype1, mtype2)][0][3] = np.mean(test1[stat1 & stat2])
                out_stat[(mtype1, mtype2)][1][3] = np.mean(test2[stat1 & stat2])

            coef1 = clf1.get_coef()
            coef2 = clf2.get_coef()
            coef_list1 = []
            coef_list2 = []

            for gn in coef1.keys() & coef2.keys():
                coef_list1 += [coef1[gn]]
                coef_list2 += [coef2[gn]]
            
                out_dist[(mtype1, mtype2)] = cosine_similarity(
                    np.array([coef_list1]), np.array([coef_list2])
                    )

            out_coef[(mtype1, mtype2)][0] = coef1
            out_coef[(mtype1, mtype2)][1] = coef2

        else:
            del(out_acc[(mtype1, mtype2)])
            del(out_stat[(mtype1, mtype2)])
            del(out_dist[(mtype1, mtype2)])
            del(out_coef[(mtype1, mtype2)])

    # saves classifier results to file
    out_file = os.path.join(out_dir, 'results', 'ex___run' + argv[-1] + '.p')
    pickle.dump({'Acc': out_acc, 'Stat': out_stat,
                 'Dist': out_dist, 'Coef': out_coef},
                open(out_file, 'wb'))


if __name__ == "__main__":
    main(sys.argv[1:])

