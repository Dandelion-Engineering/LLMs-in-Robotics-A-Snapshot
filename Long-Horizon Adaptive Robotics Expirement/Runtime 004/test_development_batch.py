"""Pure plan boundary checks; no queue, model or robot run."""
import copy
import unittest
from development_batch import validate


class DevelopmentPlanTests(unittest.TestCase):
    def row(self):
        return {'run_id':'B01-dev-fixture','kind':'baseline','parts':3,'seed':0,'policy_noise_seed':1,
                'cap':300,'scenario':'nominal','condition':'persistent'}

    def test_duplicate_or_scored_identity_cannot_enter_development_driver(self):
        row=self.row()
        with self.assertRaises(ValueError):validate([row,copy.deepcopy(row)])
        row['run_id']='B01-eval-protected'
        with self.assertRaises(ValueError):validate([row])

    def test_path_traversal_and_unbounded_runs_are_rejected_before_mutation(self):
        for changes in ({'run_id':'B01-dev-../../escape'},{'cap':float('nan')},{'cap':901},{'seed':True},{'parts':100}):
            with self.subTest(changes=changes),self.assertRaises(ValueError):validate([{**self.row(),**changes}])
        with self.assertRaises(ValueError):validate([])


if __name__=='__main__':unittest.main()
