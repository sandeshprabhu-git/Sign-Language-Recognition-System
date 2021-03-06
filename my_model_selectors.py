import math
import statistics
import warnings

import numpy as np
from hmmlearn.hmm import GaussianHMM
from sklearn.model_selection import KFold
from asl_utils import combine_sequences


class ModelSelector(object):
    '''
    base class for model selection (strategy design pattern)
    '''

    def __init__(self, all_word_sequences: dict, all_word_Xlengths: dict, this_word: str,
                 n_constant=3,
                 min_n_components=2, max_n_components=10,
                 random_state=14, verbose=False):
        self.words = all_word_sequences
        self.hwords = all_word_Xlengths
        self.sequences = all_word_sequences[this_word]
        self.X, self.lengths = all_word_Xlengths[this_word]
        self.this_word = this_word
        self.n_constant = n_constant
        self.min_n_components = min_n_components
        self.max_n_components = max_n_components
        self.random_state = random_state
        self.verbose = verbose

    def select(self):
        raise NotImplementedError

    def base_model(self, num_states):
        # with warnings.catch_warnings():
        warnings.filterwarnings("ignore", category=DeprecationWarning)
        # warnings.filterwarnings("ignore", category=RuntimeWarning)
        try:
            hmm_model = GaussianHMM(n_components=num_states, covariance_type="diag", n_iter=1000,
                                    random_state=self.random_state, verbose=False).fit(self.X, self.lengths)
            if self.verbose:
                print("model created for {} with {} states".format(self.this_word, num_states))
            return hmm_model
        except:
            if self.verbose:
                print("failure on {} with {} states".format(self.this_word, num_states))
            return None


class SelectorConstant(ModelSelector):
    """ select the model with value self.n_constant

    """

    def select(self):
        """ select based on n_constant value

        :return: GaussianHMM object
        """
        best_num_components = self.n_constant
        return self.base_model(best_num_components)


class SelectorBIC(ModelSelector):
    """ select the model with the lowest Baysian Information Criterion(BIC) score

    http://www2.imm.dtu.dk/courses/02433/doc/ch6_slides.pdf
    Bayesian information criteria: BIC = -2 * logL + p * logN
    """

    def select(self):
        """ select the best model for self.this_word based on
        BIC score for n between self.min_n_components and self.max_n_components

        :return: GaussianHMM object
        """
        warnings.filterwarnings("ignore", category=DeprecationWarning)

        best_score = float('inf')
        best_num_components = 0

        for i in range(self.min_n_components, self.max_n_components):
            #some models create a value error
            try:
                model = GaussianHMM(n_components=i, n_iter = 500)
                model.fit(self.X)
                #based on https://ai-nd.slack.com/archives/C4GQUB39T/p1493492066018049?thread_ts=1493484686.529822&cid=C4GQUB39T
                p = i ** 2 + 2 * (model.n_features) * i - 1
                score = -2 * model.score(self.X) + p * np.log(len(self.X))
                if score < best_score:
                    best_score = score
                    best_num_components = i
            except ValueError:
                pass

        return self.base_model(best_num_components)

class SelectorDIC(ModelSelector):
    ''' select best model based on Discriminative Information Criterion

    Biem, Alain. "A model selection criterion for classification: Application to hmm topology optimization."
    Document Analysis and Recognition, 2003. Proceedings. Seventh International Conference on. IEEE, 2003.
    http://citeseerx.ist.psu.edu/viewdoc/download?doi=10.1.1.58.6208&rep=rep1&type=pdf
    DIC = log(P(X(i)) - 1/(M-1)SUM(log(P(X(all but i))
    '''

    def select(self):
        warnings.filterwarnings("ignore", category=DeprecationWarning)

        best_score = float('-inf')
        best_num_components = 0

        for i in range(self.min_n_components, self.max_n_components):
            antiLogL = 0.0
            word_count = 0

            #some models create a value error
            try:
                model = GaussianHMM(n_components=i, n_iter = 500)
                model.fit(self.X, self.lengths)

                for word in self.hwords:
                    if not word == self.this_word:
                        X, lengths = self.hwords[word]
                        antiLogL += model.score(X, lengths)
                        word_count += 1

                score = model.score(X) - antiLogL / word_count
                if score > best_score or best_score == 0:
                    best_score = score
                    best_num_components = i
            except ValueError:
                pass

        return self.base_model(best_num_components)


class SelectorCV(ModelSelector):
    ''' select best model based on average log Likelihood of cross-validation folds

    '''

    def select(self):
        warnings.filterwarnings("ignore", category=DeprecationWarning)

        best_score = 0
        best_num_components = 0

        for i in range(self.min_n_components, self.max_n_components):
            score = []
            kf = KFold(n_splits=4)
            for train_index, test_index in kf.split(self.X):
                X_train, X_test = self.X[train_index], self.X[test_index]
                #model could fail if there is not enough data for a word
                try:
                    model = GaussianHMM(n_components=i, n_iter = 500)
                    model.fit(X_train)
                    score.append(model.score(X_test))
                except ValueError:
                    pass
            try:
                avg_score = sum(score) / len(score)
            except ZeroDivisionError:
                avg_score = 0
            if avg_score > best_score or best_score == 0:
                best_score = avg_score
                best_num_components = i

        return self.base_model(best_num_components)
