# python 2/3 interoperability
try:
    range = xrange
except NameError:
    pass

import numpy as np
import implicit
from polara.recommender.models import RecommenderModel
from polara.tools.timing import Timer


class ImplicitALS(RecommenderModel):

    def __init__(self, *args, **kwargs):
        super(ImplicitALS, self).__init__(*args, **kwargs)
        self._rank = 10
        self.alpha = 1
        self.weight_func = np.log2
        self.regularization = 0.01
        self.num_epochs = 15
        self.method = 'iALS'
        self._model = None

    @property
    def rank(self):
        return self._rank

    @rank.setter
    def rank(self, new_value):
        if new_value != self._rank:
            self._rank = new_value
            self._is_ready = False
            self._recommendations = None


    @staticmethod
    def confidence(values, alpha=1, weight=None, dtype='double'):
        '''implementation of a generic confidence-based function'''
        values = weight(values) if weight is not None else values
        return (alpha * values).astype(dtype)


    def build(self):
        # define iALS model instance
        self._model = implicit.als.AlternatingLeastSquares(factors=self.rank,
                                                           regularization=self.regularization,
                                                           iterations=self.num_epochs)

        # prepare input matrix for learning the model
        matrix = self.get_training_matrix() # user_by_item sparse matrix
        matrix.data = self.confidence(matrix.data, alpha=self.alpha, weight=self.weight_func)

        with Timer(self.method, verbose=self.verbose):
            # build the model
            # implicit takes item_by_user matrix as input, need to transpose
            self._model.fit(matrix.T)


    def get_recommendations(self):
        recalculate = self.data.warm_start # used to force folding-in computation
        if recalculate:
            # prepare test matrix with preferences of unseen users
            matrix, _ = self.get_test_matrix()
            matrix.data = self.confidence(matrix.data, alpha=self.alpha, weight=self.weight_func)
            num_users = matrix.shape[0]
            users_idx = range(num_users)
        else:
            # prepare traing matrix and convert test user indices into
            # corresponding training matrix rows
            matrix = self.get_training_matrix()
            userid = self.data.fields.userid
            users_idx = self.data.test.holdout[userid].drop_duplicates(keep='first').values
            num_users = len(users_idx)

        top_recs = np.empty((num_users, self.topk), dtype=np.intp)

        if self.filter_seen is False:
            raise ValueError('The model always filters seen items from results.')

        for i, user_row in enumerate(users_idx):
            recs = self._model.recommend(user_row, matrix, N=self.topk, recalculate_user=recalculate)
            top_recs[i, :] = [item for item, _ in recs]
        return top_recs
